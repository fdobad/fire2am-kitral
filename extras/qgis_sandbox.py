
import os
from .fire2am_utils import check, aName, log, get_params, , randomDataFrame, csv2rasterInt16, mergeVectorLayers, cellIds2matchingLayer
from .qgis_utils import check_gdal_driver_name, id2uglyId, uglyId2xy, matchPointLayer2RasterLayer
''' getting layers '''
layer = iface.mapCanvas().currentLayer()
# { name : layer }
layers = { l.name():l for l in QgsProject.instance().mapLayers().values()}
# { id : layer }
layers_id = QgsProject.instance().mapLayers()

''' add layer from file '''
rasterLayer = QgsRasterLayer('GPKG:/home/fdo/source/C2FSB/data/Vilopriu_2013/raster.gpkg:tableName')
QgsProject.instance().addMapLayer(layer)

''' common properties '''
''' crs '''
aCrs = QgsCoordinateReferenceSystem('IGNF:UTM31ETRS89')
bCrs = layer.crs()
layer.setCrs( aCrs)
layer.setCrs( QgsCoordinateReferenceSystem(4326))

''' extent '''
e = layer.extent()

project = QgsProject.instance() 
project
mc = iface.mapCanvas()
mc
layers_byName = { l.name():l for l in QgsProject.instance().mapLayers().values()}
layers_byName
layer = iface.mapCanvas().currentLayer()
layer

from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsFeature, QgsPointXY, QgsGeometry #QgsPoint, 
def cellIds2matchingLayer( ignitionPoints, rasterLayer, geo_package_file='outputs.gpkg', layerName='ignition points'):
    rex = rasterLayer.extent()
    w, h = rasterLayer.width(), rasterLayer.height()
    xs = np.linspace( rex.xMinimum(), rex.xMaximum(), w+1 )
    ys = np.linspace( rex.yMinimum(), rex.yMaximum(), h+1 )
    dx = xs[1]-xs[0]
    dy = ys[1]-ys[0]
    
    pts = []
    for p in ignitionPoints:
        x,y = id2cellxy( p, w, h)
        f = QgsFeature()
        #f.setGeometry( QgsPoint( xs[x]+dx/2, ys[y]+dy/2)) 
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(xs[x]+dx/2, ys[y]+dy/2)))
        pts += [ f]
    
    vectorLayer = QgsVectorLayer( 'point', layerName, 'memory')
    ret, val = vectorLayer.dataProvider().addFeatures(pts)
    print('addFeatures',ret, val)
    
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    options.layerName = layerName
    if os.path.exists(geo_package_file):
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    else:
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    ret, val = QgsVectorFileWriter.writeAsVectorFormat( vectorLayer , geo_package_file, options)
    print('VectorFileWriter', ret, val)

from qgis.core import Qgis, QgsRasterFileWriter, QgsRasterBlock, QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QByteArray
def csv2rasterInt16( extent, layerName, filepath = 'result/Grids/Grids1/ForestGrid04.csv', crs = QgsCoordinateReferenceSystem('IGNF:UTM31ETRS89'), outpath= 'rastersInt16.gpkg'):
    data = np.loadtxt( filepath, dtype=np.int16, delimiter=',')
    if not np.any(np.where( data == 1 )):
        return False, 'no ones'
    h,w = data.shape
    bites = QByteArray( data.tobytes() ) 
    block = QgsRasterBlock( Qgis.CInt16, w, h)
    block.setData( bites)
    if not block.isValid():
        return False, 'block invalid'
    fw = QgsRasterFileWriter(outpath)
    fw.setOutputFormat('gpkg')
    fw.setCreateOptions(['RASTER_TABLE='+layerName, 'APPEND_SUBDATASET=YES'])
    provider = fw.createOneBandRaster( Qgis.Int16, w, h, extent, crs )
    ''' mark zeros as nodata '''
    provider.setNoDataValue(1, 0)
    if not provider.isValid():
        return False, 'provider invalid'
    if not provider.isEditable():
        return False, 'provider not editable'
    if not provider.writeBlock( block, 1, 0, 0):
        return False, 'provider failed to write block'
    return True, 'sucess for'+layerName

import processing
from qgis.core import QgsVectorDataProvider, QgsField, QgsGeometry #, QgsFeatureRequest
from qgis.PyQt.QtCore import QVariant

def rasterpolygonize(layer, output=None):# ): #
    ''' processing.algorithmHelp('gdal:polygonize')
    { 'BAND' : 1, 'EIGHT_CONNECTEDNESS' : False, 'EXTRA' : '', 'FIELD' : 'DN', 'INPUT' : layer, 'OUTPUT' : 'TEMPORARY_OUTPUT' })
    '''
    tmp = processing.run('gdal:polygonize',{ 'BAND' : 1, 'EIGHT_CONNECTEDNESS' : False, 'EXTRA' : '', 'FIELD' : 'DN', 'INPUT' : layer, 'OUTPUT' : output })
    return tmp['OUTPUT']

def mergeVectorLayers(layerList, ogrDB, tableName):
    '''processing.algorithmHelp('native:mergevectorlayers') -> Merge vector layers
            { 'CRS' : None, 'LAYERS' : layerList, 'OUTPUT' : 'TEMPORARY_OUTPUT' })
            ['/home/.../FireEvolution.gpkg|layername=polygon_ForestGrid01','/home...FireEvolution.gpkg|layername=polygon_ForestGrid02', ...]
            'OUTPUT' : 'ogr:dbname=\'/home/.../FireEvolution.gpkg\' table=\"merged_polygons\" (geom) sql='
    '''
    tmp = processing.run('native:mergevectorlayers',
            { 'CRS' : None, 'LAYERS' : layerList, 'OUTPUT' : 'ogr:dbname=\''+ogrDB+'\' table=\"'+tableName+'\" (geom) sql=' })
    return tmp

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

def addautoincrementalfield(layer):
    '''processing.algorithmHelp('native:addautoincrementalfield')
    '''
    tmp = processing.run('native:addautoincrementalfield',
           {'FIELD_NAME' : 'index', 
            'GROUP_FIELDS' : [], 
            'INPUT' : layer, 
            'OUTPUT' : 'TEMPORARY_OUTPUT', 
            'SORT_ASCENDING' : True, 
            'SORT_EXPRESSION' : '\"id\"', 
            'SORT_NULLS_FIRST' : True, 
            'START' : 0 })
    return tmp['OUTPUT']

def add2dIndex( layer, x='x', y='y'):
    ''' add integer 2d integer index relative position pos_x pos_y
    '''
    layerStuff = getVectorLayerStuff( layer)
    fields_name = layerStuff.names
    if not (x in fields_name and y in fields_name):
        layer = addxyfields(layer)
        layerStuff = getVectorLayerStuff( layer)
        fields_name = layerStuff.names
    idx = fields_name.index(x)
    idy = fields_name.index(y)
    data = layerStuff.attr
    ''' get unique values for x and y assuming they're aligned '''
    xun = np.unique( data[:,idx] )
    yun = np.unique( data[:,idy] )
    ''' position is index of data in the unique value '''
    # TODO np.isclose(a,b) for floats
    pos_x = [ np.where( xun == p)[0][0] for p in data[:,idx] ]
    pos_y = [ np.where( yun == p)[0][0] for p in data[:,idy] ]
    ''' add calculated arrays '''
    layer.dataProvider().addAttributes([QgsField('pos_x',QVariant.Int)])
    layer.dataProvider().addAttributes([QgsField('pos_y',QVariant.Int)])
    layer.updateFields()
    fields_name = [f.name() for f in layer.fields()]
    idposx = fields_name.index('pos_x')
    idposy = fields_name.index('pos_y')
    for i,feature in enumerate(layer.getFeatures()):
        attrx = { idposx : int(pos_x[i]) }
        attry = { idposy : int(pos_y[i]) }
        layer.dataProvider().changeAttributeValues({feature.id() : attrx })
        layer.dataProvider().changeAttributeValues({feature.id() : attry })
        
def addXYcentroid( layer ):
    ''' add 'center_x' & 'center_y' attr to polyLayer '''
    fields_name = [f.name() for f in layer.fields()]
    caps = layer.dataProvider().capabilities()
    if caps & QgsVectorDataProvider.AddAttributes:
        if 'center_x' not in fields_name:
            layer.dataProvider().addAttributes([QgsField('center_x', QVariant.Double)])
        if 'center_y' not in fields_name:
            layer.dataProvider().addAttributes([QgsField('center_y', QVariant.Double)])
        layer.updateFields()
        fields_name = [f.name() for f in layer.fields()]
        fareaidx = fields_name.index('center_x')
        fareaidy = fields_name.index('center_y')
    if caps & QgsVectorDataProvider.ChangeAttributeValues:
        for feature in layer.getFeatures():
            centr = QgsGeometry.centroid(feature.geometry())
            attrx = { fareaidx : centr.asPoint().x() }
            attry = { fareaidy : centr.asPoint().y() }
            layer.dataProvider().changeAttributeValues({feature.id() : attrx })
            layer.dataProvider().changeAttributeValues({feature.id() : attry })


def createRasterFloat(  filename = 'testpy.tif', 
                        extent = layer.extent(), 
                        crs = layer.crs(),
                        data = None ):
    if not data:
        data = np.zeros((3,4), dtype=np.float64)
        data[0,0] = 1.0
    if not date.dtype == np.float64:
        data = np.float64( data)
    h,w = data.shape()
    # set 
    bites = QByteArray( data.tobytes() ) 
    block = QgsRasterBlock( Qgis.Float64, w, h)
    block.setData( bites)
    if not block.isValid():
        return False, 'block invalid'
    # write
    # 1 ok
    fw = QgsRasterFileWriter( filename )
    # 2 nop
    #fw = QgsRasterFileWriter('testpy.asc')
    #fw.setOutputFormat('AAIGrid')
    # 3 Float64 not supported
    #fw = QgsRasterFileWriter('test.gpkg')
    #fw.setOutputFormat('gpkg')
    #fw.setCreateOptions(['RASTER_TABLE=testpy', 'APPEND_SUBDATASET=YES'])
    provider = fw.createOneBandRaster( Qgis.Float64, w, h, extent, crs )
    ''' mark zeros as nodata '''
    provider.setNoDataValue(1, -1.0)
    if not provider.isValid():
        return False, 'provider invalid'
    if not provider.isEditable():
        return False, 'provider not editable'
    if not provider.writeBlock( block, 1, 0, 0):
        return False, 'provider failed to write block'
    return True, ''

def checkPointsInRasterExtent( raster, points):
    ''' returns a list indicating True/False for each point
    for p in points.getFeatures():
        if raster.extent().contains(  p.geometry().asPoint() ) :
            print(p, 'ok')
        else:
            print(p, 'no')
    '''
    re = raster.extent()
    return [ re.contains(  p.geometry().asPoint() ) for p in points.getFeatures() ]

def matchPointLayer2RasterLayer( raster, point):
    pointsIn = checkPointsInRasterExtent( raster, point) 
    re = raster.extent()
    xspace = np.linspace( re.xMinimum(), re.xMaximum(), raster.width() )
    yspace = np.linspace( re.yMinimum(), re.yMaximum(), raster.height())
    pt = [ p.geometry().asPoint() for p in point.getFeatures() ]
    pts = [ [p.x(),p.y()] for p in pt ]
    cellxy = []
    cellid = []
    dx = xspace[1] - xspace[0]
    dy = yspace[1] - yspace[0]
    for i,(px,py) in enumerate(pts):
        if pointsIn[i]:
            cx = np.where( np.isclose( xspace, px, atol=dx/2, rtol=0))[0][0]
            cy = np.where( np.isclose( yspace, py, atol=dy/2, rtol=0))[0][0]
            #cx = np.where( np.isclose( xspace, px, atol=0, rtol=dx/px/2))[0][0]
            #cy = np.where( np.isclose( yspace, py, atol=0, rtol=dy/py/2))[0][0]
            cellxy += [[cx,cy]]
            cellid += [ cx + raster.height()*cy ]
            #print('px',px,xspace[cx],cx)
            #print('py',py,xspace[cy],cy)
            #print('id',cellid[-1])
        else:
            cellxy += [[-1,-1]]
            cellid += [ -1 ]
    return cellid, cellxy

''' adding layer group '''
groupName="test group"
root = QgsProject.instance().layerTreeRoot()
group = root.addGroup(groupName)
group.insertChildNode(0,raster)
QgsProject.instance().addMapLayer(polyLayer)


print('layer type', layer.type())
if QgsMapLayerType.VectorLayer == layer.type():
    field_names = [f.name() for f in layer.fields()]
    field_names
    field_types = [f.typeName() for f in layer.fields()]
    field_types
    layerStuff = getVectorLayerStuff( layer)
    # TODO
    #f.attributeMap()
    #f.attributes()[field_names.index('hey')]
elif QgsMapLayerType.RasterLayer == layer.type():
    layerData = convertRasterToNumpyArray(layer)
else:
    print('nothing done')

layer.setName('layer_name')
QgsProject.instance().addMapLayer(polyLayer)
QgsVectorFileWriter.writeAsVectorFormat(ignition_cells, "ignition_cells.gpkg")

import os.path
plugin_dir = '/home/fdo/dev/fire2am/img'
polyLayer.loadNamedStyle(os.path.join( plugin_dir, 'instanceGrid_layerStyle.qml'))

''' in which cell a ignition point belongs '''
ignitions = layers_byName['ignitions']
for ig in ignitions.getFeatures():
    for p in polyLayer.getFeatures():
        if p.geometry().contains(ig.geometry()):
            polyLayer.select(p.id())
            #print(p.attributes(),ig.geometry())

ignition_cells = polyLayer.materialize(QgsFeatureRequest().setFilterFids(polyLayer.selectedFeatureIds()))

ignitions = layers_byName['ignition points']
raster =  layers_byName['model_21_ascii']
from itertools import combinations
def checkAllLayersHaveSameExtent( layers = QgsProject.instance().mapLayers()):
    for layer1,layer2 in combinations( layers, 2):
        if not layer1.extent() == layer2.extent():
            return False, (layer1.name(),layer2.name())
    return True, _

''' v1 for standalone use '''
from qgis.testing import start_app
app = start_app()
''' v2 for standalone use '''
from qgis.core import QgsApplication
app = QgsApplication([], True)
app.initQgis()

from osgeo import gdal
import tempfile
from pathlib import Path
from glob import glob
import sys
from qgis.core import Qgis, QgsApplication, QgsRasterLayer, QgsRasterBlock, QgsMapLayerType
from qgis.PyQt.QtCore import QByteArray
from tempfile import mkstemp

from qgis.core import Qgis, QgsRasterFileWriter, QgsRasterBlock
from qgis.PyQt.QtCore import QByteArray
import numpy as np
def csv2rasterInt16( extent, layerName, filepath = 'result/Grids/Grids1/ForestGrid04.csv', crs = QgsCoordinateReferenceSystem('IGNF:UTM31ETRS89') ):
    data = np.loadtxt( filepath, dtype=np.int16, delimiter=',')
    h,w = data.shape
    bites = QByteArray( data.tobytes() ) 
    block = QgsRasterBlock( Qgis.CInt16, w, h)
    block.setData( bites)
    if not block.isValid():
        return False
    fw = QgsRasterFileWriter('rastersInt16.gpkg')
    fw.setOutputFormat('gpkg')
    fw.setCreateOptions(['RASTER_TABLE='+layerName, 'APPEND_SUBDATASET=YES'])
    provider = fw.createOneBandRaster( Qgis.Int16, w, h, extent, crs )
    if not provider.isValid():
        return False
    if not provider.isEditable():
        return False
    if not provider.writeBlock( block, 1, 0, 0):
        return False
    return True

from itertools import islice
def csv2ascList( file_list = ['ForestGrid00.csv','ForestGrid01.csv'], header_file = 'elev.asc' ):
    with open( head_file, 'r') as afile:
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
            outfile.writelines(infile.readlines().replace(b',',b' ')

def rasterFromNpArray():
    data = np.array([ np.loadtxt(f, dtype=np.float64, delimiter=',') for f in glob('Grids1/*csv')])
    p,h,w = data.shape
    
    bites = QByteArray( data[1].ravel().tobytes() ) 
    
    block = QgsRasterBlock( Qgis.CFloat64, w, h)
    block.setData( bites)
    
    fd, fname = mkstemp(suffix='.tif')
    r = QgsRasterLayer(fname,'name')
    dp = r.dataProvider()


from qgis.core import (QgsApplication, QgsCoordinateReferenceSystem, QgsProject, QgsRasterLayer, QgsRectangle)
from qgis.core import Qgis

'gdal:buildvirtualraster'


    

tdir = '/home/fdo/source/C2FSB/data/Vilopriu_2013/result/Grids/Grids1/'
data = np.loadtxt( tdir+'ForestGrid02.csv', dtype=np.float64, delimiter=',')
print('data ',data.shape)
bites = QByteArray( data.tobytes() ) 
bites = QByteArray( data.ravel().tobytes() ) 
assert np.dot( *data.shape) * 8 == len(bites)

#layer = iface.mapCanvas().currentLayer()
base = iface.mapCanvas().currentLayer()
assert np.all( data.shape == (base.height(), base.width()))

#provider = layer.dataProvider()
#provider = base.dataProvider()
prov = base.dataProvider()
provider = prov.clone()

block = provider.block(1, base.extent(), base.width(), base.height())
QgsRasterBlock(dataType: Qgis.DataType, width: int, height: int)
#block = QgsRasterBlock( Qgis.Byte, base.height(), base.width())
#block = QgsRasterBlock( Qgis.Byte, base.width(), base.height())
block = QgsRasterBlock( Qgis.Byte, layer.width(), layer.height())
block.setData( bites)

if not provider.setEditable(True):
    print('error enabling editing')
if not provider.writeBlock(block,1,0,0):
    print('error writing block')
if not provider.setEditable(False):
    print('error disabling editing')


out_file='result/grid.tif'
file_writer = QgsRasterFileWriter(out_file)

pipe = QgsRasterPipe()
if not pipe.set(provider):
    print('error pipe setting provider')
if not file_writer.writeRaster(pipe, provider.xSize(), provider.ySize(), provider.extent(), provider.crs()):
    print('error file writer')

def writeRaster(layer, data):
    fd, tname = tempfile.mkstemp(suffix='asc')
    file_writer = QgsRasterFileWriter(tname)

    pipe = QgsRasterPipe()
    or_provider = layer.dataProvider()
    provider = or_provider.clone()  

    bites = QByteArray( data.ravel().tobytes() ) 
    block = provider.block(1, layer.extent(), layer.width(), layer.height())
    if not block.setData( bites):
        return print('error setData')
    provider.setEditable(True)
    provider.writeBlock(block, 1, 0, 0)
    provider.setEditable(False)

    projector = QgsRasterProjector()
    projector.setCrs(layer.crs(), layer.crs())    

    if not pipe.set(projector):
        print('error pipe setting projector')
    if not pipe.set(provider):
        print('error pipe setting provider')
    #renderer = layer.renderer()
    #pipe.set(renderer.clone())
    if not file_writer.writeRaster(pipe,
                                 provider.xSize(),
                                 provider.ySize(),
                                 tr.transform(provider.extent()),
                                 layer.crs()):
        print('error file writing asc')

def addautoincrementalfield(layer):
    '''processing.algorithmHelp('native:addautoincrementalfield')
    '''
    tmp = processing.run('native:addautoincrementalfield',
           {'FIELD_NAME' : 'index', 
            'GROUP_FIELDS' : [], 
            'INPUT' : layer, 
            'OUTPUT' : 'TEMPORARY_OUTPUT', 
            'SORT_ASCENDING' : True, 
            'SORT_EXPRESSION' : '\"id\"', 
            'SORT_NULLS_FIRST' : True, 
            'START' : 0 })
    return tmp['OUTPUT']

def routascii(layer, filename='TEMPORARY_OUTPUT'):
    '''returns filename as path string
    Not same format as fire2aascii used files
    processing.algorithmHelp('grass7:r.out.ascii')
    '''
    tmp = processing.run('grass7:r.out.ascii',
           { '-i' : False,
           '-m' : False,
           '-s' : False,
           'GRASS_REGION_CELLSIZE_PARAMETER' : 0,
           'GRASS_REGION_PARAMETER' : None,
           'input' : layer, 
           'null_value' : '*', 
           'output' : filename,
           'precision' : None,
           'width' : None })
    return tmp['OUTPUT']

def buildVirtualRaster( layer, name='vrt'):
    tmp =  processing.run('gdal:buildvirtualraster', { 'ADD_ALPHA' : False, 'ASSIGN_CRS' : layer.crs(), 'EXTRA' : '', 'INPUT' : layer, 'OUTPUT' : 'TEMPORARY_OUTPUT', 'PROJ_DIFFERENCE' : False, 'RESAMPLING' : 0, 'RESOLUTION' : 0, 'SEPARATE' : False, 'SRC_NODATA' : '' })
    return QgsRasterLayer( tmp['OUTPUT'], name)

from osgeo import gdal
import tempfile
from pathlib import Path
#Path(gpkg_file).touch()
from qgis.core import QgsCoordinateReferenceSystem
def writeRaster( raster_file, tableName='forestgrids', crs = QgsCoordinateReferenceSystem('IGNF:UTM31ETRS89')):
    fname = tempfile.mktemp( suffix='.gpkg', dir=os.getcwd() )
    gdal.GetDriverByName('GPKG').Create(fname, 1, 1, 1)
    source = QgsRasterLayer( raster_file, 'rasterName', 'gdal')
    source.setCrs(QgsCoordinateReferenceSystem('IGNF:UTM31ETRS89'))
    print('source.isValid()',source.isValid(), source)
    provider = source.dataProvider()
    print('provider.isValid()',provider.isValid(), provider)
    fw = QgsRasterFileWriter(fname)
    fw.setOutputFormat('gpkg')
    fw.setCreateOptions(['RASTER_TABLE='+str(tableName), 'APPEND_SUBDATASET=YES'])
    pipe = QgsRasterPipe()
    print( pipe.set(provider.clone()) )
    projector = QgsRasterProjector()
    projector.setCrs(crs, crs)
    if pipe.insert(2, projector) is True:
        if fw.writeRaster(pipe, provider.xSize(),provider.ySize(),provider.extent(),crs) == 0:
            print("ok")
        else:
            print("error")

def writeRaster(layer,  out_file = '/tmp/reprojected_raster.asc', 
                        dest_crs_def = "EPSG:24879"):
    ''' 
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"),
                                QgsCoordinateReferenceSystem("EPSG:24879"), 
                                QgsProject.instance())
                                
    assert QgsRasterFileWriter.driverForExtension('asc') == 'AAIGrid'
    No es texto
    #provider.block(1, provider.extent(), source.width(), source.height()).data(),
    '''
    
    if layer.crs() == QgsCoordinateReferenceSystem():
        layer.setCrs( QgsCoordinateReferenceSystem("EPSG:4326") )
        #layer.setCrs( QgsProject.instance().crs() )
        print('source layer without crs set to ', layer.crs())
    
    orig_crs = layer.crs()
    dest_crs = QgsCoordinateReferenceSystem(dest_crs_def)
    
    
    tr = QgsCoordinateTransform(orig_crs, dest_crs, QgsProject.instance())
    file_writer = QgsRasterFileWriter(out_file)
    # .setOutputFormat('asc')
    pipe = QgsRasterPipe()
    provider = layer.dataProvider()
    projector = QgsRasterProjector()
    projector.setCrs(orig_crs, dest_crs)    
    if not pipe.set(projector):
        print('error pipe setting projector')
    if not pipe.set(provider.clone()):
        print('error pipe setting provider')
    #renderer = layer.renderer()
    #pipe.set(renderer.clone())
    if not file_writer.writeRaster(pipe,
                                 provider.xSize(),
                                 provider.ySize(),
                                 tr.transform(provider.extent()),
                                 dest_crs):
        print('error file writing asc')
def add2dIndex( layer, x='x', y='y'):
    ''' add integer 2d integer index relative position pos_x pos_y
    '''
    layerStuff = getVectorLayerStuff( layer)
    fields_name = layerStuff.names
    if not (x in fields_name and y in fields_name):
        layer = addxyfields(layer)
        layerStuff = getVectorLayerStuff( layer)
        fields_name = layerStuff.names
    idx = fields_name.index(x)
    idy = fields_name.index(y)
    data = layerStuff.attr
    ''' get unique values for x and y assuming they're aligned '''
    xun = np.unique( data[:,idx] )
    yun = np.unique( data[:,idy] )
    ''' position is index of data in the unique value '''
    # TODO np.isclose(a,b) for floats
    pos_x = [ np.where( xun == p)[0][0] for p in data[:,idx] ]
    pos_y = [ np.where( yun == p)[0][0] for p in data[:,idy] ]
    ''' add calculated arrays '''
    layer.dataProvider().addAttributes([QgsField('pos_x',QVariant.Int)])
    layer.dataProvider().addAttributes([QgsField('pos_y',QVariant.Int)])
    layer.updateFields()
    fields_name = [f.name() for f in layer.fields()]
    idposx = fields_name.index('pos_x')
    idposy = fields_name.index('pos_y')
    for i,feature in enumerate(layer.getFeatures()):
        attrx = { idposx : int(pos_x[i]) }
        attry = { idposy : int(pos_y[i]) }
        layer.dataProvider().changeAttributeValues({feature.id() : attrx })
        layer.dataProvider().changeAttributeValues({feature.id() : attry })
        
def addXYcentroid( layer ):
    ''' add 'center_x' & 'center_y' attr to polyLayer '''
    fields_name = [f.name() for f in layer.fields()]
    caps = layer.dataProvider().capabilities()
    if caps & QgsVectorDataProvider.AddAttributes:
        if 'center_x' not in fields_name:
            layer.dataProvider().addAttributes([QgsField('center_x', QVariant.Double)])
        if 'center_y' not in fields_name:
            layer.dataProvider().addAttributes([QgsField('center_y', QVariant.Double)])
        layer.updateFields()
        fields_name = [f.name() for f in layer.fields()]
        fareaidx = fields_name.index('center_x')
        fareaidy = fields_name.index('center_y')
    if caps & QgsVectorDataProvider.ChangeAttributeValues:
        for feature in layer.getFeatures():
            centr = QgsGeometry.centroid(feature.geometry())
            attrx = { fareaidx : centr.asPoint().x() }
            attry = { fareaidy : centr.asPoint().y() }
            layer.dataProvider().changeAttributeValues({feature.id() : attrx })
            layer.dataProvider().changeAttributeValues({feature.id() : attry })

class myarray(np.ndarray):
    def __new__(cls, *args, **kwargs):
        return np.array(*args, **kwargs).view(myarray)
    def index(self, value):
        '''
        int : return np.where(self == value)
        floats : return np.where( np.isclose( self, value))
        '''
        return np.where( np.isclose( self, value))

def checkPointsInRasterExtent( raster, points):
    ''' returns a list indicating True/False for each point
    for p in points.getFeatures():
        if raster.extent().contains(  p.geometry().asPoint() ) :
            print(p, 'ok')
        else:
            print(p, 'no')
    '''
    re = raster.extent()
    return [ re.contains(  p.geometry().asPoint() ) for p in points.getFeatures() ]


''' ugly : 0,0 is at top left, ids start at 1
    xy : 0,0 is at bottom left ids start at 0
    '''
def xy2uglyXy( x, y, w, h):
    ''' flipMinusOne i: index, w: width, h:height '''
    return (x+1, h-y+1)
def uglyXy2xy( x, y, w, h):
    return (x-1, h-y+1)
def id2uglyId( idx, w, h):
    return w*(h-idx//w) - (w-idx-1)%w
def uglyId2xy( uid, w, h):
    uid -= 1
    return uid%w, h-uid//w-1

'''
def testTransforms( w=6, h=4):
    c = 0
    for j in range(h):
        print('')
        for i in range(w):
            #print(c,i,j,end='\t')
            assert xy2id( i, j, w, h) == c
            assert np.all( id2xy( c, w, h) == (i,j))
            assert np.all( uglyId2xy( id2uglyId( c, w, h), w, h) == (i,j))
            xu, yu = xy2uglyXy( i, j, w, h)
            assert np.all( uglyXy2xy( xu, yu, w, h) == (i,j))
            c+=1

testTransforms( w=6, h=4)
'''
