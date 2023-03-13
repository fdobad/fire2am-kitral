from qgis.core import QgsVectorDataProvider, QgsField, QgsGeometry #, QgsFeatureRequest
from qgis.PyQt.QtCore import QVariant
from collections import namedtuple
from datetime import datetime
import numpy as np
import processing
''' 
    # v1 for standalone use 
    from qgis.testing import start_app
    app = start_app()
    # v2 for standalone use 
    from qgis.core import QgsApplication
    app = QgsApplication([], True)
    app.initQgis()

    # processing is in PYTHONPATH 
    <module 'processing' from '/usr/share/qgis/python/plugins/processing/__init__.py'>
'''

def pointsInRaster( points, raster):
    extent = raster.extent()
    return np.array([ [f.id(),
                       extent.contains( p.geometry().asPoint())]
                       for p in points.getFeatures() ])

def getPoints( layer):
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
    
from collections import namedtuple
import numpy as np
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

from qgis.PyQt.QtGui import QColor
from qgis.core import QgsColorRampShader, QgsRasterShader, QgsSingleBandPseudoColorRenderer
def rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue, minColor=(68,1,84), maxColor=(253,231,37)):
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

from qgis.core import QgsVectorFileWriter, QgsRasterLayer, QgsVectorLayer
import processing
from .fire2am_utils import log
import os.path
def raster2polygon( layerName, geopackage):
    ''' loads a raster layer writes it as vector layer in a geopackage
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
    QgsVectorFileWriter.writeAsVectorFormat( vectorLayer, geopackage, options)
    os.remove(tmp)
    del rasterLayer, vectorLayer, options, tmp

from qgis.PyQt.QtCore import QByteArray
from qgis.core import Qgis, QgsRasterFileWriter, QgsRasterBlock
def array2rasterInt16( data, name, geopackage, extent, crs, nodata = None):
    data = np.int16(data)
    h,w = data.shape
    bites = QByteArray( data.tobytes() ) 
    block = QgsRasterBlock( Qgis.CInt16, w, h)
    block.setData( bites)
    fw = QgsRasterFileWriter(geopackage)
    fw.setOutputFormat('gpkg')
    fw.setCreateOptions(['RASTER_TABLE='+name, 'APPEND_SUBDATASET=YES'])
    provider = fw.createOneBandRaster( Qgis.Int16, w, h, extent, crs )
    provider.setEditable(True)
    provider.writeBlock( block, 1, 0, 0)
    if nodata != None:
        provider.setNoDataValue(1, nodata)
    provider.setEditable(False)
    del provider, fw, block

from qgis.PyQt.QtCore import QByteArray
from qgis.core import Qgis, QgsRasterBlock, QgsRasterFileWriter
def array2rasterFloat32( data, name, geopackage, extent, crs, nodata = None):
    dataf32 = np.float32( data)
    h,w = dataf32.shape
    bites = QByteArray( dataf32.tobytes() ) 
    block = QgsRasterBlock( Qgis.Float32, w, h)
    block.setData( bites)
    fw = QgsRasterFileWriter(geopackage)
    fw.setOutputFormat('gpkg')
    fw.setCreateOptions(['RASTER_TABLE='+name, 'APPEND_SUBDATASET=YES'])
    provider = fw.createOneBandRaster( Qgis.Float32, w, h, extent, crs )
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
    extent = raster.extent()
    dx = raster.rasterUnitsPerPixelX()
    dy = raster.rasterUnitsPerPixelY()
    dx2 = dx/2
    dy2 = dy/2
    xspace = np.arange( extent.xMinimum()+dx2, extent.xMaximum()+dx2, dx)
    yspace = np.arange( extent.yMinimum()+dy2, extent.yMaximum()+dy2, dy)[::-1]
    xy = [ id2xy( c, raster.width(), raster.height()) for c in cellIds ]
    return [ [xspace[x], yspace[y]] for x,y in xy ]

from osgeo import gdal
def check_gdal_driver_name( layer, driver_name='AAIGrid'):
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

from itertools import islice
def csv2ascList( file_list = ['ForestGrid00.csv','ForestGrid01.csv'], header_file = 'elev.asc' ):
    with open( header_file, 'r') as afile:
        header = list(islice(afile, 6))
    for afile in file_list:
        fname = afile[:-4]
        csv2ascFile( in_file = afile, header = header, out_file = fname+'.asc')

def csv2ascFile( in_file = 'ForestGrid00.csv', 
        header = ['ncols 508\n', 'nrows 610\n', 'xllcorner 494272.38261041\n', 'yllcorner 4652115.6527613\n', 'cellsize 20\n', 'NODATA_value -9999\n'],
        out_file = 'ForestGrid00.asc'):
    
    with open(out_file, 'w') as outfile:
        outfile.writelines(header)

    with open( in_file, 'rb', buffering=0) as infile:
        with open(out_file, 'ab') as outfile:
            outfile.write(infile.read().replace(b',',b' '))

def clipRasterLayerByMask(raster, polygon, nodata=-32768):
    ''' Algorithm 'Clip raster by mask layer' 
    gdal:cliprasterbymasklayer -> Clip raster by mask layer
    make sure both layers are saved to disk, & same CRS
    adds new layer to project
    returns filepath str
    '''
    outname = raster.name() + '_clippedBy_' + polygon.name() + '.asc'
    outname = outname.replace(' ','')
    outpath = QgsProject().instance().absolutePath()
    out = os.path.join( outpath, outname )

    tmp = processing.run('gdal:cliprasterbymasklayer', 
            { 'ALPHA_BAND' : False, 'CROP_TO_CUTLINE' : True, 'DATA_TYPE' : 0, 'EXTRA' : '', 'INPUT' : raster, 'KEEP_RESOLUTION' : True, 'MASK' : polygon, 'MULTITHREADING' : True, 'NODATA' : nodata, 'OPTIONS' : '', 'OUTPUT' : out, 'SET_RESOLUTION' : False, 'SOURCE_CRS' : raster.crs(), 'TARGET_CRS' : raster.crs(), 'X_RESOLUTION' : None, 'Y_RESOLUTION' : None })
    iface.addRasterLayer( out, outname)
    return tmp['OUTPUT'] 

def clipVectorByPolygon(layer, polygon):
    ''' gdal:clipvectorbypolygon
    adds new layer to project
    returns filepath str
    '''
    outname = layer.name() + '_clippedBy_' + polygon.name() + '.shp'
    outname = outname.replace(' ','')
    outpath = QgsProject().instance().absolutePath()
    out = os.path.join( outpath, outname )
    tmp = processing.run('gdal:clipvectorbypolygon', 
            { 'INPUT' : layer, 'MASK' : polygon, 'OPTIONS' : '', 'OUTPUT' : out })
            #{ 'INPUT' : layer, 'MASK' : polygon, 'OPTIONS' : '', 'OUTPUT' : 'TEMPORARY_OUTPUT' })
    iface.addVectorLayer(out , ' ', 'ogr') #layer.providerType())
    return tmp['OUTPUT'] 

def clipVectorLayerByExtent(layer, extent, clip=True):
    '''processing.algorithmHelp('native:extractbyextent')
    Extract/clip by extent
             'EXTENT' : extent, #'-70.651805555556,-70.60828703703399,-33.434398148148,-33.411249999998', 
             'INPUT' : layer, #'/home/fdo/dev/fire2am/userFolder/ignitions.shp', 
    '''
    tmp = processing.run('native:extractbyextent', 
            {'CLIP' : clip, 
             'EXTENT' : extent,
             'INPUT' : layer,
             'OUTPUT' : 'TEMPORARY_OUTPUT' })
    return tmp['OUTPUT'] 

def pixelstopolygons(layer): 
    '''processing.algorithmHelp('native:pixelstopolygons')
        TODO add params , band=1, field_name='VALUE')
    '''
    tmp = processing.run('native:pixelstopolygons', 
               {'INPUT_RASTER' : layer, 
                'RASTER_BAND' : 1,
                'FIELD_NAME' : 'VALUE', 
                'OUTPUT' : 'TEMPORARY_OUTPUT' })
    return tmp['OUTPUT'] 

def listAllProcessingAlgorithms():
    ''' processing must be added to PYTHONPATH
    import processing
    or 
    from qgis import processing

    get help string example:
        processing.algorithmHelp('native:pixelstopolygons')

    'native:native:adduniquevalueindexfield' NOT FOUND
    '''
    for alg in QgsApplication.processingRegistry().algorithms():
            print(alg.id(), "->", alg.displayName())
