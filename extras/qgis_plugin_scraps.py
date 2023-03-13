from glob import glob
import os
import re
import numpy as np


def chunks(l, n):
    n = max(1, n)
    return (l[i:i+n] for i in range(0, len(l), n))

'<QgsCoordinateReferenceSystem: IGNF:ETRS89UTM31>'

file_list = glob('**/*asc') + glob('*asc')

if file_list is []:
    print('empty')

#    '' : '',
file2layer = {
    'model' : 'fuels',
    'mdt' : 'elevation',
    'cbh' : 'cbh',
    'cbd' : 'cbd',
    'fcc' : 'fcc',
    }

    def temp():
        #iface.addVectorLayer( v.publicSource() , 'tmpName', v.providerType())
        options = QgsVectorFileWriter.SaveVectorOptions()
        context = QgsProject.instance().transformContext()
        QgsVectorFileWriter.writeAsVectorFormatV2(vl1,uri,context,options)
        QgsVectorFileWriter.writeAsVectorFormatV2(vl2,uri,context,options)

        d = QgsProcessingOutputLayerDefinition('/home/fdo/source/C2FSB/data/Vilopriu_2013/result/output.gpkg')
        d.createOptions['POLYGON_TABLE'] = 'hola'
        d.createOptions['APPEND_SUBDATASET'] = 'YES'
        tmp = processing.run('gdal:polygonize',{ 'BAND' : 1, 'EIGHT_CONNECTEDNESS' : False, 'EXTRA' : '', 'FIELD' : 'DN', 'INPUT' : layer, 'OUTPUT' : d })
        for csvGrid in grid_list:
            layerName = os.path.basename( csvGrid)[:-4]

        layers = { layer.name():[layer.id(),layer] for layer in QgsProject.instance().mapLayers().values() }
        for csvGrid in grid_list:
            layerName = os.path.basename( csvGrid)[:-4]
            lid = layers[ layerName][0]
            clone = layers[ layerName][1].clone()
            root.removeChildNode(lid)
            layer = QgsRasterLayer('GPKG:'+outpath+':'+layerName, layerName)
            gridGroup.insertLayer(0, layer)
            #layer = root.findLayer(vlayer.id())
            #QgsProject.instance().addMapLayer(QgsRasterLayer('GPKG:'+outpath+':'+layerName, layerName))
            #gridGroup.addLayer()
            #gridGroup.addMapLayer(QgsRasterLayer('GPKG:'+outpath+':'+layerName, layerName))

        crs = self.project.crs()
        rlayers = []
        vlayers = []
        # todo order glob
        asc_list = sorted(glob(grid_directory + os.sep + 'ForestGrid[0-9]*.asc'), key=os.path.getmtime)

        assert len(asc_list) == len(df) + 1

        for i,afile in enumerate( asc_list[1:]):
            dt = Timestamp(df.datetime.iloc[i])
            dt_nice = dt.strftime('%a_%I_%m')
            dt_date= dt.strftime('%Y-%m-%d')
            dt_time= dt.strftime('%I:%M:%S')
            dt_sec = dt.to_pydatetime().timestamp()
            # raster
            rlayer = QgsRasterLayer( afile, dt_nice)
            #rlayer.setCrs( crs)
            a2ndfile = rasterpolygonize( rlayer , grid_directory + os.sep + dt_nice+'.shp')
            rlayers += [rlayer]
            log('rasterlayer',i,rlayer, level=0)
            # vector
            log('a2ndfile',a2ndfile,level=0)
            vlayer = QgsVectorLayer( a2ndfile)
            vlayer.startEditing()
            vlayer.setName( dt_nice)
            #vlayer.setCrs( crs)
            vlayer.deleteFeatures([ f.id() for f in vlayer.getFeatures() if f.attribute('DN')==0 ]) #DN is default created value in rasterpolygonize
            vlayer.dataProvider().addAttributes([QgsField('date',QVariant.Date)])
            #vlayer.dataProvider().addAttributes([QgsField('time',QVariant.Time)])
            vlayer.dataProvider().addAttributes([QgsField('epoch',QVariant.Double)])
            vlayer.updateFields()
            fields_name = [f.name() for f in vlayer.fields()]
            id_d = fields_name.index('date')
            #id_t = fields_name.index('time')
            id_s = fields_name.index('epoch')
            for feature in vlayer.getFeatures():
                attr = { id_d : dt_date, id_s : dt_sec}
                #attr = { id_d : dt_date, id_t : dt_time, id_s : dt_sec}
                print(vlayer.dataProvider().changeAttributeValues({ feature.id() : attr}))
            vlayer.commitChanges()
            vlayers += [vlayer]
            log('vlayer',i,vlayer, level=0)

        log('add vl',[ polyGroup.addLayer(v) for v in vlayers], level=0)
        log('add rl',[ gridGroup.addLayer(r) for r in rlayers], level=0)

        log('asc loaded!', level=0)
        '''
        if os.path.isfile( os.path.join( self.args['InFolder'] , 'Weather.csv')):
            df = read_csv(os.path.join( self.args['InFolder'] , 'Weather.csv'))
            df.datetime
        '''


def nsimsraster2poly():
    ''' fire scars rasters to polygons '''
    self.externalProcess_message('Making fire scar polygons...')
    for i,(nsim,ngrid) in enumerate(numbers):
        layerName = 'FireScar_'+str(nsim).zfill(width1stNum)+'_'+str(ngrid).zfill(width2ndNum)
        raster2polygon( layerName, geo_package_file)

    '''Merging fire scars polygons...'''
    self.externalProcess_message('Merging fire scars polygons...')
    polys=[]
    for i,(nsim,ngrid) in enumerate(numbers):
        layerName = 'vFireScar_'+str(nsim).zfill(width1stNum)+'_'+str(ngrid).zfill(width2ndNum)
        polys += [ geo_package_file+'|layername='+layerName ]
    mergeVectorLayers( polys, geo_package_file, 'merged_Fire_Scars')


def processLayers(self):
    # TODO too slow
    # TODO clip layers to study area instead of taking fuels as base
    log('processing layers',level=0)#, msgBar=self.dlg.msgBar)

    '''create a numerated cell grid BASED ON FUELS'''
    polyLayer = pixelstopolygons(self.dlg.state['layerComboBox_fuels'])
    log('pixelstopolygons',level=0)#, msgBar=self.dlg.msgBar)
    polyLayer = addautoincrementalfield(polyLayer)
    log('addautoincrementalfield',level=0)#, msgBar=self.dlg.msgBar)
    addXYcentroid( polyLayer )
    log('addXYcentroid',level=0)#, msgBar=self.dlg.msgBar)
    add2dIndex( polyLayer, x='center_x', y='center_y')
    log('add2dIndex',level=0)#, msgBar=self.dlg.msgBar)
    ''' add to project '''
    polyLayer.setName('instance_grid')
    polyLayer.loadNamedStyle(os.path.join( self.plugin_dir, 'img/instanceGrid_layerStyle.qml'))
    QgsProject.instance().addMapLayer(polyLayer)
    self.layer['grid'] = polyLayer

    ''' create ignition cells layer '''
    if self.dlg.state['radioButton_ignitionRandom'] or self.dlg.state['radioButton_ignitionPoints']:

        if self.dlg.state['radioButton_ignitionRandom']:
            polyLayer.select( np.random.randint( len(polyLayer)))
            log('select random',level=0)#, msgBar=self.dlg.msgBar)

        elif self.dlg.state['radioButton_ignitionPoints']:
            ''' in which cell a ignition point belongs to '''
            ignitions = self.dlg.state['layerComboBox_ignitionPoints']
            log('entra for de match',level=0)#, msgBar=self.dlg.msgBar)
            for ig in ignitions.getFeatures():
                for p in polyLayer.getFeatures():
                    if p.geometry().contains(ig.geometry()):
                        polyLayer.select(p.id())
            log('sale for de match',level=0)#, msgBar=self.dlg.msgBar)
        ''' new layer from selected cells '''
        ignition_cells = polyLayer.materialize(QgsFeatureRequest().setFilterFids(polyLayer.selectedFeatureIds()))
        ''' add to project '''
        ignition_cells.setName('ignition_cells')
        ignition_cells.loadNamedStyle(os.path.join( self.plugin_dir, 'img/ignitionCells_layerStyle.qml'))
        QgsProject.instance().addMapLayer(ignition_cells)
        self.layer['ignitionPoints'] = ignition_cells

    elif self.dlg.state['radioButton_ignitionProbMap']:
        # TODO
        log( 'Checks not implemented', pre='ignitionProbMap',level=0, msgBar=self.dlg.msgBar)

''' 
ignitions '''
if self.dlg.state['radioButton_ignitionRandom'] or self.dlg.state['radioButton_ignitionPoints']:
    ''' ignition points are cells, read index, write csv '''
    ic_stuff = getVectorLayerStuff( self.layer['ignitionPoints'])
    data = { 'Year':None, 'Ncell': np.int16( ic_stuff.attr[ :, ic_stuff.names.index('index')])}
    df = DataFrame.from_dict( data)
    df.fillna(1, inplace=True)
    df.to_csv( os.path.join( self.args['InFolder'],'Ignitions.csv'), header=True, index=False)
    log( 'written', pre='Ignition points', level=0, msgBar=self.dlg.msgBar)
elif self.dlg.state['radioButton_ignitionProbMap']:
    ipm_layer = self.dlg.state['layerComboBox_ignitionProbMap']
    copy( ipm_layer.publicSource() , self.args['InFolder'])
    log( 'ignitionProbMap copied', level=0, msgBar=self.dlg.msgBar)

for key,val in file2layer.items():
    #pattern = '^a...s$'
    pattern = '.*{}.*asc$'.format(key)
    for afile in file_list:
        result = re.match(pattern, os.path.basename(afile))
        if result:
            print(pattern, result.string)

def slot_button_box_clicked(self, button):
    if button.text() == 'Reset':
        print('Reset')
        self.cancelTask()
    elif button.text() == 'Apply':
        print('Apply')
        #self.dummyResults()
        self.run_C2F()
    elif button.text() == 'Restore Defaults':
        print('Restore Defaults')


    self.timer_weatherFile.stop()
    self.timer_weatherFolder.stop()
    self.timer_weatherFile.stop()
    self.timer_weatherFolder.stop()
    # radioButton delay actions timers
    self.timer_weatherFile = QTimer()
    self.timer_weatherFile.setSingleShot(True)
    self.timer_weatherFolder = QTimer()
    self.timer_weatherFolder.setSingleShot(True)
    self.timer_wait_time = 5000

def slot_tabWidget_currentChanged(self):
    ''' connect signals when tab is opened
    sender = self.dlg.sender()
    senderName = sender.objectName()
    QgsMessageLog.logMessage('tab_callback\tci:%s\tname:%s'%(ci,senderName), MESSAGE_CATEGORY, level = Qgis.Info)
    TBD track connections id
            self.conn_id[ci] += [ self.dlg.radioButton_ignitionPoints.clicked.connect(self.slot_ignitionPoints_clicked)]
            self.conn_id[ci] += [ self.dlg.layerComboBox_ignitionPoints.layerChanged.connect(self.slot_ignitionPoints_layerChanged)]
    '''
    ci = self.dlg.tabWidget.currentIndex()
    if ci == 0:
        pass
    elif ci == 1:
        pass
    elif ci == 2:
        pass
        '''
        # TODO check raster layer prob data
        #self.dlg.layerComboBox_ignitionProbMap.layerChanged.connect(self.slot_layerComboBox_ignitionProbMap_layerChanged)
        # TBD recheck?
        #self.dlg.radioButton_ignitionPoints.clicked.connect(self.slot_radioButton_ignitionPoints_clicked)
        #self.dlg.radioButton_ignitionProbMap.clicked.connect(self.slot_radioButton_ignitionProbMap_clicked)
        '''
    elif ci == 4:
        self.dlg.pushButton_dev.pressed.connect(self.start_dev)
        self.dlg.pushButton_run.pressed.connect(self.start_process)
        self.dlg.pushButton_kill.pressed.connect(self.kill_process)
        self.dlg.pushButton_terminate.pressed.connect(self.terminate_process)
        self.dlg.pushButton_processLayers.pressed.connect(self.processLayers)
    elif ci == 5:
        self.dlg.toolButton_next.clicked.connect(self.slot_toolButton_next_clicked)
        self.dlg.toolButton_prev.clicked.connect(self.slot_toolButton_prev_clicked)

def slot_radioButton_weatherFile_clicked(self):
    filepath = self.dlg.fileWidget_weatherFile.filePath()
    if self.dlg.state['fileWidget_weatherFile'] == filepath and filepath[:-3]=='csv' or filepath == None:
        return
    self.timer_weatherFile.timeout.connect( 
            lambda : self.slot_fileWidget_weatherFile_fileChanged(self.dlg.fileWidget_weatherFile.filePath()))
    self.timer_weatherFile.start(self.timer_wait_time)

def slot_radioButton_weatherFolder_clicked(self):
    filepath = self.dlg.fileWidget_weatherFolder.filePath()
    if self.dlg.state['fileWidget_weatherFile'] == filepath and self.dlg.state['nweathers'] != 0 or filepath == None:
        return
    #self.timer_weatherFolder.timeout.connect( lambda : self.slot_fileWidget_weatherFolder_fileChanged(filepath))
    self.timer_weatherFolder.timeout.connect( lambda : self.slot_fileWidget_weatherFolder_fileChanged(self.dlg.fileWidget_weatherFolder.filePath()))
    self.timer_weatherFolder.start(self.timer_wait_time)

def slot_radioButton_ignitionPoints_clicked(self):
    layer = self.dlg.layerComboBox_ignitionPoints.currentLayer()
    if self.state['layerComboBox_ignitionPoints'] == layer:
        return
    self.timer_ignitionPoints.timeout.connect( 
            lambda : self.slot_layerComboBox_ignitionPoints_layerChanged(self.dlg.layerComboBox_ignitionPoints.currentLayer()))
    self.timer_ignitionPoints.start(5000)

    # external running task
    self.task = None
    self.taskManager = QgsApplication.taskManager()

def startTask(self):
    argsNs = Namespace(**self.args)
    run = False
    if not hasattr(self,'task'):
        run = True
    elif self.task is None:
        run = True
    elif isinstance( self.task, QgsTask) and hasattr( self.task, 'status') and self.task.status()==4:
        run = True
    if run:
        self.task = Cell2FireTask(argsNs , self.args['InFolder'])
        self.taskManager.addTask(self.task)
        log('Task status %s'%self.task.status(),pre = 'Task added!', level=4, msgBar=self.dlg.msgBar)
    else:
        log('Task status %s'%self.task.status(),pre = 'Already running!', level=3, msgBar=self.dlg.msgBar)

def cancelTask(self):
    if self.task is None:
        log('Task is None',pre = 'Nothing to cancel!', level=0, msgBar=self.dlg.msgBar)
        return
    if self.task.canCancel():
        self.task.cancel()
        log('Task status %s'%self.task.status(),pre = 'Cancel signal sent!', level=0, msgBar=self.dlg.msgBar)
        return
    log('Task status %s'%self.task.status(),pre = 'Not canceled!', level=0, msgBar=self.dlg.msgBar)

def load1simOLD(self):
    grid_directory = os.path.join( self.args['OutFolder'], 'Grids')
    grid_directory = os.path.join( grid_directory, 'Grids1')
    if not os.path.isdir( grid_directory):
        log('Grids1 folder in results folder', grid_directory, pre='Does NOT exist', msgBar=self.dlg.msgBar, level=3)
        return

    grid_list = sorted(glob( grid_directory + os.sep + 'ForestGrid[0-9]*.csv'), key=os.path.getmtime)
    if not grid_list:
        log('ForestGrid[0-9]*.csv in results folder', grid_directory, pre='Do NOT exist', msgBar=self.dlg.msgBar, level=3)
        return

    #geo_package_file= '/home/fdo/source/C2FSB/data/Vilopriu_2013/result/FireEvoRasters.gpkg'
    geo_package_file=os.path.join(self.args['OutFolder'], 'outputs.gpkg')
    rasterOk = []
    for csvGrid in grid_list:
        layerName = 'raster_FireEvolution_'+os.path.basename( csvGrid)[:-4]
        ret, val = csv2rasterInt16( extent = self.dlg.state['layerComboBox_elevation'].extent(),
                         layerName = layerName,
                         filepath = csvGrid,
                         crs = self.project.crs(),
                         outpath = geo_package_file)
        #if ret:
        #    self.iface.addRasterLayer( 'GPKG:'+geo_package_file+':'+layerName, layerName)
        rasterOk += [ret]

    log('rasters written', rasterOk, level=0)
    #outpath = '/home/fdo/source/C2FSB/data/Vilopriu_2013/result/polygons.gpkg'
    #outpath = os.path.join(self.args['OutFolder'], 'outputPolygons.gpkg')

    weather_file = os.path.join( self.args['InFolder'], 'Weather.csv')
    if not os.path.isfile( weather_file):
        log('Weather.csv in input instance folder', pre='Does NOT exist', msgBar=self.dlg.msgBar, level=3)
        return
    df = read_csv( weather_file)
    #df = read_csv( 'Weather.csv')

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    #geo_package_file= '/home/fdo/source/C2FSB/data/Vilopriu_2013/result/polygons.gpkg'
    for i,csvGrid in enumerate( grid_list):
        if not rasterOk[i]:
            continue
        # TODO i-1 -> check index exists
        dt = Timestamp(df.datetime.iloc[i-1]).strftime('%Y-%m-%d %I:%H:%M')
        layerName = os.path.basename( csvGrid)[:-4]
        rasterLayer = QgsRasterLayer('GPKG:'+geo_package_file+':'+'raster_FireEvolution_'+layerName, 'raster_FireEvolution_'+layerName)
        tmp = processing.run('gdal:polygonize',{ 'BAND' : 1, 'EIGHT_CONNECTEDNESS' : False, 'EXTRA' : '', 'FIELD' : 'DN', 'INPUT' : rasterLayer, 'OUTPUT' : 'TEMPORARY_OUTPUT' })
        vectorLayer = QgsVectorLayer( tmp['OUTPUT'], 'polygon_'+layerName )
        if not vectorLayer.isEditable():
            vectorLayer.startEditing()
        vectorLayer.dataProvider().addAttributes([QgsField('datetime',QVariant.DateTime)])
        vectorLayer.updateFields()
        id_dt = vectorLayer.fields().indexFromName('datetime')
        for feature in vectorLayer.getFeatures():
            attr = { id_dt : dt}
            vectorLayer.dataProvider().changeAttributeValues({ feature.id() : attr})
        vectorLayer.commitChanges()
        options.layerName = 'polygon_FireEvolution_'+layerName
        if os.path.exists(geo_package_file):
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        else:
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        QgsVectorFileWriter.writeAsVectorFormat( vectorLayer, geo_package_file, options)

    ''' merge polygons
        ['/home/fdo/source/C2FSB/data/Vilopriu_2013/result/FireEvolution.gpkg|layername=polygon_ForestGrid01','/home/fdo/source/C2FSB/data/Vilopriu_2013/result/FireEvolution.gpkg|layername=polygon_ForestGrid02','/home/fdo/source/C2FSB/data/Vilopriu_2013/result/FireEvolution.gpkg|layername=polygon_ForestGrid03','/home/fdo/source/C2FSB/data/Vilopriu_2013/result/FireEvolution.gpkg|layername=polygon_ForestGrid04','/home/fdo/source/C2FSB/data/Vilopriu_2013/result/FireEvolution.gpkg|layername=polygon_ForestGrid05','/home/fdo/source/C2FSB/data/Vilopriu_2013/result/FireEvolution.gpkg|layername=polygon_ForestGrid06','/home/fdo/source/C2FSB/data/Vilopriu_2013/result/FireEvolution.gpkg|layername=polygon_ForestGrid07']
        'OUTPUT' : 'ogr:dbname=\'/home/fdo/source/C2FSB/data/Vilopriu_2013/result/FireEvolution.gpkg\' table=\"merged_polygons\" (geom) sql='
    '''
    layerList = [ geo_package_file+'|layername=polygon_FireEvolution_'+os.path.basename( csvGrid)[:-4] for i,csvGrid in enumerate( grid_list) if rasterOk[i] ]
    print('layerList', layerList)
    log('layerList', layerList, level=1)
    ogrDB = geo_package_file
    tableName = 'merged_polygons'
    tmp = mergeVectorLayers( layerList, ogrDB, tableName)
    if tmp:
        self.iface.addVectorLayer( geo_package_file+'|layername='+tableName , 'Single Fire Evolution' , 'ogr')
        # TODO select by loading it from geo_package
        polyLayer = QgsProject.instance().mapLayersByName( 'Single Fire Evolution '+tableName )[0] 
        polyLayer.loadNamedStyle(os.path.join( self.plugin_dir, 'img/mergedPolygons_layerStyle.qml'))
        #polyLayer = QgsVectorLayer( tmp['OUTPUT'], 'Single Fire Evolution')
    log('FIN', level=0)

def setInitialSelectedLayers():
    layers_byName = { l.name():l for l in QgsProject.instance().mapLayers().values()}
    for key,val in file2layer.items():
        pattern = '.*{}.*asc$'.format(key)
        for lname,layer in layers_byName.items():
            result = re.match(pattern, lname)
            if result:
                cmb = 'layerComboBox_'+lname
                self.dlg.cmb.setLayer(layer)
                print(pattern, result.string)
