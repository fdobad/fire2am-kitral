#!/bin/env python3
''' 
    # v1 for standalone use 
    from qgis.testing import start_app
    app = start_app()
    # v2 for standalone use 
    from qgis.core import QgsApplication
    app = QgsApplication([], True)
    app.initQgis()

    # processing must be in PYTHONPATH 
    <module 'processing' from '/usr/share/qgis/python/plugins/processing/__init__.py'>
'''
import os.path
from collections import namedtuple

import numpy as np
import processing
from osgeo import gdal
# pylint: disable=no-name-in-module
from qgis.core import (Qgis, QgsColorRampShader, QgsMapLayerType,
                       QgsField, QgsGeometry, QgsRasterBlock,
                       QgsRasterFileWriter, QgsRasterLayer, QgsRasterShader,
                       QgsSingleBandPseudoColorRenderer,
                       QgsVectorFileWriter, QgsVectorLayer, QgsWkbTypes)
from qgis.PyQt.QtCore import QByteArray #, QVariant
from qgis.PyQt.QtGui import QColor
# pylint: enable=no-name-in-module

from .fire2am_utils import log

def checkLayerPoints(layer):
    if not layer:
        return -1, 'Empty'
    if not layer.type() == QgsMapLayerType.VectorLayer:
        return -1, 'Not vector layer'
    if not layer.wkbType() == QgsWkbTypes.Point:
        return -1, 'Not point type '
    pts = [ f.geometry() for f in layer.getFeatures() \
            if hasattr( f, 'geometry') and callable(getattr( f, 'geometry')) and \
               f.geometry().wkbType() == QgsWkbTypes.Point]
    return len(pts), 'Ok'


def pointsInRaster( points, raster):
    ''' returns a numpy array with point.id 
        and a boolean indicating if point is inside the raster extent '''
    extent = raster.extent()
    return np.array([ [p.id(),
                       extent.contains( p.geometry().asPoint())]
                       for p in points.getFeatures() ])

def getPoints( layer):
    ''' gets Vector layer features, transforms it
        geometry -> point -> px, py '''
    points = [ f.geometry().asPoint() for f in layer.getFeatures() ]
    return [ [p.x(),p.y()] for p in points ]

def getRaster(layer):
    ''' raster layer into numpy array
        slower alternative:
            for i in range(lyr.width()):
                for j in range(lyr.height()):
                    values.append(block.value(i,j))
    '''
    provider = layer.dataProvider()
    block = provider.block(1, layer.extent(), layer.width(), layer.height())
    qByteArray = block.data()
    npArr = np.frombuffer( qByteArray)  #,dtype=float)
    return npArr.reshape( (layer.height(),layer.width()))

def getVector( layer) -> namedtuple:
    ''' returns an object with attributes field type attr geom id len
    '''
    LayerStuff = namedtuple('layerStuff', 'field type attr geom id len')
    attributes = []
    geometry = []
    fid = []
    for f in layer.getFeatures():
        attributes += [f.attributes()]
        geometry += [ f.geometry() ]
        fid += [ f.id() ]
    return LayerStuff(  field = np.array([ f.name() for f in layer.fields()]),
                        type = np.array([ f.typeName() for f in layer.fields()]), 
                        attr = np.array(attributes), 
                        geom = np.array(geometry), 
                        id = np.array(fid),
                        len = len(fid) )

def writeVectorLayer( vectorLayer, layerName, geopackage, transformContext=None):
    ''' TODO warning writeAsVectorFormat deprecated '''
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    options.layerName = layerName
    if geopackage.is_file():
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    else:
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    if transformContext:
        return QgsVectorFileWriter.writeAsVectorFormatV3(layer=vectorLayer,
                                                         fileName=str(geopackage),
                                                         transformContext=vectorLayer.transformContext(),
                                                         options=options)
    else:
        return QgsVectorFileWriter.writeAsVectorFormat(layer=vectorLayer,
                                                       fileName=str(geopackage),
                                                       options=options)

def mergeVectorLayers(layerList, ogrDB, tableName):
    ''' Has no output because writes into database
        processing.algorithmHelp('native:mergevectorlayers') -> Merge vector layers
            { 'CRS' : None, 'LAYERS' : layerList, 'OUTPUT' : 'TEMPORARY_OUTPUT' })
            ['/home/.../FireEvolution.gpkg|layername=polygon_ForestGrid01','/home...FireEvolution.gpkg|layername=polygon_ForestGrid02', ...]
            'OUTPUT' : 'ogr:dbname=\'/home/.../FireEvolution.gpkg\' table=\"merged_polygons\" (geom) sql='

    '''
    tmp = processing.run('native:mergevectorlayers',
            { 'CRS' : None, 'LAYERS' : layerList, 'OUTPUT' : 'ogr:dbname=\''+ogrDB+'\' table=\"'+tableName+'\" (geom) sql=' })
    return tmp

def rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue, minColor=(68,1,84), maxColor=(253,231,37)):
    ''' colorizes a layer '''
    fcn = QgsColorRampShader()
    fcn.setColorRampType(QgsColorRampShader.Interpolated)
    lst = [ QgsColorRampShader.ColorRampItem(minValue, QColor(*minColor)),
            QgsColorRampShader.ColorRampItem(maxValue, QColor(*maxColor)) ]
    fcn.setColorRampItemList(lst)
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(fcn)
    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
    layer.setRenderer(renderer)
    layer.triggerRepaint()

def raster2polygon(layerName : str, geopackage : str) -> None:
    ''' loads a raster layer writes it as vector layer into geopackages
        raster is named "r"+layerName
        vector is named "v"+layerName
    '''
    log('raster2polygon', layerName, geopackage, level=1)
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    rasterLayer = QgsRasterLayer('GPKG:'+geopackage+':r'+layerName, 'r'+layerName)
    #vectorLayer = QgsVectorLayer( 'Memory', 'v'+layerName)
    tmp = processing.run('gdal:polygonize',
               {'BAND' : 1, 
                'EIGHT_CONNECTEDNESS' : False, 
                'EXTRA' : '', 
                'FIELD' : 'DN', 
                'INPUT' : rasterLayer, 
                'OUTPUT' : 'TEMPORARY_OUTPUT' })['OUTPUT']
                #'OUTPUT' : vectorLayer})
    vectorLayer = QgsVectorLayer( tmp, 'v'+layerName)
    options.layerName = 'v'+layerName
    if os.path.exists(geopackage):
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    else:
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    QgsVectorFileWriter.writeAsVectorFormatV3(layer=vectorLayer,
                                              fileName=geopackage,
                                              transformContext=rasterLayer.transformContext(),
                                              options=options)
    os.remove(tmp)
    del rasterLayer, vectorLayer, options, tmp

def array2rasterInt16( data, name, geopackage, extent, crs, nodata = None):
    ''' numpy array to gpkg casts to name '''
    data = np.int16(data)
    h,w = data.shape
    bites = QByteArray( data.tobytes() ) 
    block = QgsRasterBlock( Qgis.CInt16, w, h)
    block.setData( bites)
    fw = QgsRasterFileWriter(str(geopackage))
    fw.setOutputFormat('gpkg')
    fw.setCreateOptions(['RASTER_TABLE='+name, 'APPEND_SUBDATASET=YES'])
    provider = fw.createOneBandRaster( Qgis.Int16, w, h, extent, crs )
    provider.setEditable(True)
    provider.writeBlock( block, 1, 0, 0)
    if nodata != None:
        provider.setNoDataValue(1, nodata)
    provider.setEditable(False)
    del provider, fw, block

def array2rasterFloat32( data, name, geopackage, extent, crs, nodata = None):
    ''' numpy array to gpkg casts to name '''
    dataf32 = np.float32( data)
    h,w = dataf32.shape
    bites = QByteArray( dataf32.tobytes() ) 
    block = QgsRasterBlock( Qgis.Float32, w, h)
    block.setData( bites)
    fw = QgsRasterFileWriter(str(geopackage))
    fw.setOutputFormat('gpkg')
    fw.setCreateOptions(['RASTER_TABLE='+name, 'APPEND_SUBDATASET=YES'])
    provider = fw.createOneBandRaster( Qgis.Float32, w, h, extent, crs )
    provider.setEditable(True)
    provider.writeBlock( block, 1, 0, 0)
    if nodata != None:
        provider.setNoDataValue(1, nodata)
    provider.setEditable(False)
    del provider, fw, block

def array2rasterFloat64( data, name, geopackage, extent, crs, nodata = None):
    ''' numpy array to gpkg casts to name '''
    dataf64 = np.float64( data)
    h,w = dataf64.shape
    bites = QByteArray( dataf64.tobytes() ) 
    block = QgsRasterBlock( Qgis.Float64, w, h)
    block.setData( bites)
    fw = QgsRasterFileWriter(str(geopackage))
    fw.setOutputFormat('gpkg')
    fw.setCreateOptions(['RASTER_TABLE='+name, 'APPEND_SUBDATASET=YES'])
    provider = fw.createOneBandRaster( Qgis.Float64, w, h, extent, crs )
    provider.setEditable(True)
    provider.writeBlock( block, 1, 0, 0)
    if nodata != None:
        provider.setNoDataValue(1, nodata)
    provider.setEditable(False)
    del provider, fw, block

def matchPoints2Raster( raster, points):
    ''' returns 3 lists: [ cell_id], [[ coord_x, coord_y]], [ feature ids] for points
        if the point is not in the extent it will not be returned: len(points) <= len(response)
    '''
    extent = raster.extent()
    dx = raster.rasterUnitsPerPixelX()
    dy = raster.rasterUnitsPerPixelY()
    dx2 = dx/2
    dy2 = dy/2
    xspace = np.arange( extent.xMinimum()+dx2, extent.xMaximum()+dx2, dx)
    yspace = np.arange( extent.yMinimum()+dy2, extent.yMaximum()+dy2, dy)[::-1]
    coord = []
    cellid = []
    featid = []
    for feat in points.getFeatures():
        point = feat.geometry().asPoint()
        if extent.contains( point):
            coordx = np.where( np.isclose( xspace, point.x(), atol=dx2, rtol=0))[0][0]
            coordy = np.where( np.isclose( yspace, point.y(), atol=dy2, rtol=0))[0][0]
            coord += [ [coordx, coordy]]
            cellid+= [ coordx + raster.width()*coordy ]
            featid+= [ feat.id()] 
    return cellid, coord, featid

def matchRasterCellIds2points( cellIds, raster):
    ''' matches cell ids (topleft=0, 1=one to the right like a picture, ... bottomright=w*h)
        to a raster, does not check if id is out of bounds '''
    extent = raster.extent()
    dx = raster.rasterUnitsPerPixelX()
    dy = raster.rasterUnitsPerPixelY()
    dx2 = dx/2
    dy2 = dy/2
    xspace = np.arange( extent.xMinimum()+dx2, extent.xMaximum()+dx2, dx)
    yspace = np.arange( extent.yMinimum()+dy2, extent.yMaximum()+dy2, dy)[::-1]
    xy = [ id2xy( c, raster.width(), raster.height()) for c in cellIds ]
    return [ [xspace[x], yspace[y]] for x,y in xy ]

def check_gdal_driver_name( layer, driver_name='AAIGrid'):
    ''' opens layer file with gdal
        check gdal driver name '''
    afile = layer.publicSource()
    if not afile:
        return False, 'no public source'
    dataset = gdal.Open(afile, gdal.GA_ReadOnly)
    if not dataset:
        return False, 'gdal cannot open it'
    driver = dataset.GetDriver()
    return driver.ShortName == driver_name, driver.LongName

def id2xy( idx, w=6, h=4):
    ''' idx: index, w: width, h:height '''
    return idx%w, idx//w 

def xy2id( x, y, w, h):
    ''' x-> w: width, y-> h:height '''
    return y*w+x

'''
def testTransforms( w=6, h=4):
    c = 0
    for j in range(h):
        print('')
        for i in range(w):
            #print(c,i,j,end='\t')
            assert xy2id( i, j, w, h) == c
            assert np.all( id2xy( c, w, h) == (i,j))
            c+=1

testTransforms( w=6, h=4)
'''
