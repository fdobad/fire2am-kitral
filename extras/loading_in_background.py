
from functools import partial
from qgis.core import QgsTask ,QgsApplication, QgsMessageLog 

    plugin init
        # QgsTask
        self.task = {} 
        self.taskManager = QgsApplication.taskManager()

    def slot_doit(self):
        QgsMessageLog.logMessage('Setting up background tasks...', aName, Qgis.Info)
        # TODO
        nsims = 9
        self.dlg.update()
        self.updateProject()
        outfolder = '/home/fdo/dev/Zona21/Instance23-03-18_01-12-17/results'
        stat_gpkg=outfolder+os.sep+'stats.gpkg'
        out_gpkg=outfolder+os.sep+'outputs.gpkg'

        logfile = outfolder+os.sep+'LogFile.txt'
        ''' load simulation log '''
        with open(logfile, 'rb', buffering=0) as afile:
            simLog = afile.read().decode()
            self.externalProcess_message( simLog)

        layerName = 'Ignition_Points'
        self.task[layerName] = QgsTask.fromFunction( description = layerName, 
                                                     function = task_ignitionPointsLayer, 
                                                     on_finished = task_completed, 
                                                     baseLayer = self.dlg.state['layerComboBox_fuels'],
                                                     geopackage = stat_gpkg,
                                                     layerName = layerName,
                                                     text = simLog)
        self.task[layerName].taskCompleted.connect( partial( self.ui_addVectorLayer, stat_gpkg, layerName, 'points_layerStyle.qml'))
        self.taskManager.addTask(self.task[layerName])

        doit = [ True for i in range(4) ]
        '''
        doit = [ 'OutFl' in self.args.keys(),
                 'OutIntensity' in self.args.keys(),
                 'OutRos' in self.args.keys(),
                 'OutCrownConsumption' in self.args.keys()]
        '''
        directories = ['FlameLength', 'Intensity', 'RateOfSpread', 'CrownFractionBurn']
        filenames = ['FL', 'Intensity', 'ROSFile', 'Cfb']
        names = ['flame_length', 'Byram_intensity', 'hit_ROS', 'crown_fire_fuel_consumption_ratio']

        if nsims > 1:
            names = ['mean_'+n for n in names ]

        for i,(d,f,n) in filter( lambda x: doit[x[0]] , enumerate(zip(directories, filenames, names))):
            self.task[n] = QgsTask.fromFunction( description= n, 
                                            function   = task_asciiDir2float32Rasters,
                                            on_finished= task_completed,
                                            dirName    = d          ,
                                            fileName   = f          ,
                                            layerName  = n          ,
                                            outfolder  = outfolder  ,
                                            out_gpkg   = out_gpkg   ,
                                            stat_gpkg  = stat_gpkg  ,
                                            extent     = self.extent,
                                            crs        = self.crs   ,
                                            nodata     = 0.0        )
            self.task[n].taskCompleted.connect( partial( self.ui_addRasterLayer, stat_gpkg, n))
            self.taskManager.addTask(self.task[n])
            QgsMessageLog.logMessage('launch %s %s %s %s'%(d,f,n,doit[i]), aName, Qgis.Info)
   
        QgsMessageLog.logMessage('Background tasks running...', aName, Qgis.Info)

    def ui_addVectorLayer(self, geopackage, layerName, styleName):
        vectorLayer = self.iface.addVectorLayer( geopackage+'|layername='+layerName, layerName, 'ogr')
        vectorLayer.loadNamedStyle( os.path.join( self.plugin_dir, 'img'+os.sep+styleName))

    def ui_addRasterLayer(self, geopackage, layerName):
        self.externalProcess_message('wtf!')
        layer = self.iface.addRasterLayer('GPKG:'+geopackage+':'+layerName, layerName)
        minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
        maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
        rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)

'''
task = QgsTask.fromFunction('my task', calculate, on_finished=calculation_finished)
task = QgsTask.fromFunction( description, function, *args, on_finished=None, flags=2, **kwargs)
QgsApplication.taskManager().addTask(task)
def task(task, *args, **kwargs):
    QgsMessageLog.logMessage('task {}\t{}\t{}'.format(task.description(), str(args), str(kwargs)), aName, Qgis.Info)
'''
def task_asciiDir2float32Rasters(task, *args, **kwargs):
    QgsMessageLog.logMessage('task Start {}'.format(task.description()), aName, Qgis.Info)
    task.setProgress(0)
    dirName   = kwargs['dirName']
    fileName  = kwargs['fileName']
    layerName = kwargs['layerName']
    outfolder = kwargs['outfolder']
    out_gpkg  = kwargs['out_gpkg']
    stat_gpkg = kwargs['stat_gpkg']
    extent    = kwargs['extent']
    crs       = kwargs['crs']
    nodata    = kwargs['nodata']

    filelist = glob( outfolder+os.sep+dirName+os.sep+fileName+'[0-9]*.asc')
    nsim = np.fromiter( re.findall( dirName+os.sep+fileName+'([0-9]+).asc', ' '.join( filelist)), dtype=int)
    asort = np.argsort( nsim)
    nsim = nsim[ asort]
    filelist = np.array( filelist)[ asort]
    widthNum = len(str(np.max( nsim)))
    ''' get all asc 2 array '''
    task.setProgress(10)
    data = []
    for afile in filelist:
        data += [ np.loadtxt( afile,  dtype=np.float32, skiprows=6)]
        if task.isCanceled():
            task_stopped(task)
            return None
    data = np.array(data)
    task.setProgress(50)
    '''global stats'''
    #self.externalProcess_message(layerName+' global statistics '+str(stats.describe(data, axis=None)))
    ''' calc mean '''
    #self.externalProcess_message('Calculating '+layerName+'...')
    array2rasterFloat32( np.mean( data, axis=0, dtype=np.float32), layerName, stat_gpkg, extent, crs, nodata = nodata)
    task.setProgress(100)
    QgsMessageLog.logMessage('task Ended {}'.format(task.description()), aName, Qgis.Info)
    task.addSubTask( qgsTask_data2rasters32( layerName+' store rasters', data, nsim, widthNum, extent, crs, nodata, layerName))
    return True

class qgsTask_loadFolder(QgsTask):
    def __init__(self, description, folder):
        super().__init__(description, QgsTask.CanCancel)
        filelist = glob( folder+os.sep+'*

    def getData(self):

data, nsim, widthNum, extent, crs, nodata, layerName

class qgsTask_data2rasters32(QgsTask):
    """This shows how to subclass QgsTask"""
    def __init__(self, description, data, nsim, widthNum, extent, crs, nodata, layerName):
        super().__init__(description, QgsTask.CanCancel)
        self.exception = None
        self.data = data
        self.nsim = nsim
        self.widthNum = widthNum
        self.extent = extent
        self.crs = crs
        self.nodata = nodata
        self.layerName = layerName
    def run(self):
        c=0
        cc = len(nsim)
        for d,n in zip(data,nsim):
            array2rasterFloat32( d, layerName+str(n).zfill(widthNum), out_gpkg, extent, crs, nodata)
            self.setProgress(c/cc)

def task_ignitionPointsLayer(task, *args, **kwargs):
    QgsMessageLog.logMessage('task Started {}'.format(task.description()), aName, Qgis.Info)
    task.setProgress(0)
    
    text = kwargs['text']
    baseLayer = kwargs['baseLayer']
    crs = baseLayer.crs()
    geopackage = kwargs['geopackage']
    layerName = kwargs['layerName']

    data = np.fromiter( re.findall( 'ignition point for Year [0-9]*, sim ([0-9]+): ([0-9]+)', text), dtype=np.dtype((int,2)) )
    simulation, ignitionCell = data.T
    npts = len(ignitionCell)
    feats = []
    c=0
    for s,(x,y) in zip(simulation, matchRasterCellIds2points( ignitionCell-1, baseLayer)):
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x,y)))
        f.setId(s)
        feats += [ f]
        task.setProgress(c/npts*80)
        if task.isCanceled():
            task_stopped(task)
            return None
        c+=1

    QgsMessageLog.logMessage('task {}\tadded feature points'.format(task.description()), aName, Qgis.Info)

    vectorLayer = QgsVectorLayer( 'point', layerName, 'memory')
    vectorLayer.setCrs( crs)
    ret, val = vectorLayer.dataProvider().addFeatures(feats)
    if not ret:
        raise Exception('created vector layer in memory, added features'+str(val))
        return False
    QgsMessageLog.logMessage('task {}\tcreated vector layer in memory, added features'.format(task.description()), aName, Qgis.Info)
    task.setProgress(90)
    ret, val = writeVector( vectorLayer, layerName, geopackage)
    QgsMessageLog.logMessage('task {}\twriting to geopackage'.format(task.description()), aName, Qgis.Info)
    if ret != 0:
        raise Exception('written to geopackage'+str(val))
        return False
    task.setProgress(100)
    QgsMessageLog.logMessage('task Ended {}'.format(task.description()), aName, Qgis.Info)
    return True

def writeVector( vectorLayer, layerName, geopackage):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    options.layerName = layerName
    if os.path.exists(geopackage):
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    else:
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    return QgsVectorFileWriter.writeAsVectorFormat( vectorLayer , geopackage, options)

def task_stopped(task):
    QgsMessageLog.logMessage(f'task {task.description()}\twas cancelled', aName, Qgis.Info)

def task_completed(exception, result=None):
    """ NEVER WORKS WITH TASK FROM FUNCTION !!
        this is called when run is finished. Exception is not None if run
        raises an exception. Result is the return value of run."""
    if exception is None:
        if result is None:
            QgsMessageLog.logMessage('task ?\tCompleted with no exception and no result (probably the task was manually canceled by the user)', aName, Qgis.Warning)
        else:
            QgsMessageLog.logMessage('task {}\tCompleted! after {} iterations'.format(result['task'],result['iterations']), aName, Qgis.Warning)
    else:
        QgsMessageLog.logMessage("Exception: {}".format(exception), aName, Qgis.Critical)
        raise exception

        QgsMessageLog.logMessage('Setting up background tasks...', aName, Qgis.Info)
        # TODO
        nsims = 9
        self.dlg.update()
        self.updateProject()
        outfolder = '/home/fdo/dev/Zona21/Instance23-03-18_01-12-17/results'
        stat_gpkg=outfolder+os.sep+'stats.gpkg'
        out_gpkg=outfolder+os.sep+'outputs.gpkg'

        logfile = outfolder+os.sep+'LogFile.txt'
        ''' load simulation log '''
        with open(logfile, 'rb', buffering=0) as afile:
            simLog = afile.read().decode()
            self.externalProcess_message( simLog)

        layerName = 'Ignition_Points'
        self.task[layerName] = QgsTask.fromFunction( description = layerName, 
                                                     function = task_ignitionPointsLayer, 
                                                     on_finished = task_completed, 
                                                     baseLayer = self.dlg.state['layerComboBox_fuels'],
                                                     geopackage = stat_gpkg,
                                                     layerName = layerName,
                                                     text = simLog)
        self.task[layerName].taskCompleted.connect( partial( self.ui_addVectorLayer, stat_gpkg, layerName, 'points_layerStyle.qml'))
        self.taskManager.addTask(self.task[layerName])

        doit = [ True for i in range(4) ]
        '''
        doit = [ 'OutFl' in self.args.keys(),
                 'OutIntensity' in self.args.keys(),
                 'OutRos' in self.args.keys(),
                 'OutCrownConsumption' in self.args.keys()]
        '''
        directories = ['FlameLength', 'Intensity', 'RateOfSpread', 'CrownFractionBurn']
        filenames = ['FL', 'Intensity', 'ROSFile', 'Cfb']
        names = ['flame_length', 'Byram_intensity', 'hit_ROS', 'crown_fire_fuel_consumption_ratio']

        if nsims > 1:
            names = ['mean_'+n for n in names ]

        for i,(d,f,n) in filter( lambda x: doit[x[0]] , enumerate(zip(directories, filenames, names))):
            self.task[n] = QgsTask.fromFunction( description= n, 
                                            function   = task_asciiDir2float32Rasters,
                                            on_finished= task_completed,
                                            dirName    = d          ,
                                            fileName   = f          ,
                                            layerName  = n          ,
                                            outfolder  = outfolder  ,
                                            out_gpkg   = out_gpkg   ,
                                            stat_gpkg  = stat_gpkg  ,
                                            extent     = self.extent,
                                            crs        = self.crs   ,
                                            nodata     = 0.0        )
            self.task[n].taskCompleted.connect( partial( self.ui_addRasterLayer, stat_gpkg, n))
            self.taskManager.addTask(self.task[n])
            QgsMessageLog.logMessage('launch %s %s %s %s'%(d,f,n,doit[i]), aName, Qgis.Info)
   
        QgsMessageLog.logMessage('Background tasks running...', aName, Qgis.Info)

    def ui_addVectorLayer(self, geopackage, layerName, styleName):
        vectorLayer = self.iface.addVectorLayer( geopackage+'|layername='+layerName, layerName, 'ogr')
        vectorLayer.loadNamedStyle( os.path.join( self.plugin_dir, 'img'+os.sep+styleName))

    def ui_addRasterLayer(self, geopackage, layerName):
        self.externalProcess_message('wtf!')
        layer = self.iface.addRasterLayer('GPKG:'+geopackage+':'+layerName, layerName)
        minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
        maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
        rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)

'''
task = QgsTask.fromFunction('my task', calculate, on_finished=calculation_finished)
task = QgsTask.fromFunction( description, function, *args, on_finished=None, flags=2, **kwargs)
QgsApplication.taskManager().addTask(task)
def task(task, *args, **kwargs):
    QgsMessageLog.logMessage('task {}\t{}\t{}'.format(task.description(), str(args), str(kwargs)), aName, Qgis.Info)
'''
def task_asciiDir2float32Rasters(task, *args, **kwargs):
    QgsMessageLog.logMessage('task Start {}'.format(task.description()), aName, Qgis.Info)
    task.setProgress(0)
    dirName   = kwargs['dirName']
    fileName  = kwargs['fileName']
    layerName = kwargs['layerName']
    outfolder = kwargs['outfolder']
    out_gpkg  = kwargs['out_gpkg']
    stat_gpkg = kwargs['stat_gpkg']
    extent    = kwargs['extent']
    crs       = kwargs['crs']
    nodata    = kwargs['nodata']

    filelist = glob( outfolder+os.sep+dirName+os.sep+fileName+'[0-9]*.asc')
    nsim = np.fromiter( re.findall( dirName+os.sep+fileName+'([0-9]+).asc', ' '.join( filelist)), dtype=int)
    asort = np.argsort( nsim)
    nsim = nsim[ asort]
    filelist = np.array( filelist)[ asort]
    widthNum = len(str(np.max( nsim)))
    ''' get all asc 2 array '''
    task.setProgress(10)
    data = []
    for afile in filelist:
        data += [ np.loadtxt( afile,  dtype=np.float32, skiprows=6)]
        if task.isCanceled():
            task_stopped(task)
            return None
    data = np.array(data)
    task.setProgress(50)
    '''global stats'''
    #self.externalProcess_message(layerName+' global statistics '+str(stats.describe(data, axis=None)))
    ''' calc mean '''
    #self.externalProcess_message('Calculating '+layerName+'...')
    array2rasterFloat32( np.mean( data, axis=0, dtype=np.float32), layerName, stat_gpkg, extent, crs, nodata = nodata)
    task.setProgress(100)
    QgsMessageLog.logMessage('task Ended {}'.format(task.description()), aName, Qgis.Info)
    task.addSubTask( qgsTask_data2rasters32( layerName+' store rasters', data, nsim, widthNum, extent, crs, nodata, layerName))
    return True

class qgsTask_loadFolder(QgsTask):
    def __init__(self, description, folder):
        super().__init__(description, QgsTask.CanCancel)
        filelist = glob( folder+os.sep+'*

    def getData(self):

data, nsim, widthNum, extent, crs, nodata, layerName

class qgsTask_data2rasters32(QgsTask):
    """This shows how to subclass QgsTask"""
    def __init__(self, description, data, nsim, widthNum, extent, crs, nodata, layerName):
        super().__init__(description, QgsTask.CanCancel)
        self.exception = None
        self.data = data
        self.nsim = nsim
        self.widthNum = widthNum
        self.extent = extent
        self.crs = crs
        self.nodata = nodata
        self.layerName = layerName
    def run(self):
        c=0
        cc = len(nsim)
        for d,n in zip(data,nsim):
            array2rasterFloat32( d, layerName+str(n).zfill(widthNum), out_gpkg, extent, crs, nodata)
            self.setProgress(c/cc)

def task_ignitionPointsLayer(task, *args, **kwargs):
    QgsMessageLog.logMessage('task Started {}'.format(task.description()), aName, Qgis.Info)
    task.setProgress(0)
    
    text = kwargs['text']
    baseLayer = kwargs['baseLayer']
    crs = baseLayer.crs()
    geopackage = kwargs['geopackage']
    layerName = kwargs['layerName']

    data = np.fromiter( re.findall( 'ignition point for Year [0-9]*, sim ([0-9]+): ([0-9]+)', text), dtype=np.dtype((int,2)) )
    simulation, ignitionCell = data.T
    npts = len(ignitionCell)
    feats = []
    c=0
    for s,(x,y) in zip(simulation, matchRasterCellIds2points( ignitionCell-1, baseLayer)):
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x,y)))
        f.setId(s)
        feats += [ f]
        task.setProgress(c/npts*80)
        if task.isCanceled():
            task_stopped(task)
            return None
        c+=1

    QgsMessageLog.logMessage('task {}\tadded feature points'.format(task.description()), aName, Qgis.Info)

    vectorLayer = QgsVectorLayer( 'point', layerName, 'memory')
    vectorLayer.setCrs( crs)
    ret, val = vectorLayer.dataProvider().addFeatures(feats)
    if not ret:
        raise Exception('created vector layer in memory, added features'+str(val))
        return False
    QgsMessageLog.logMessage('task {}\tcreated vector layer in memory, added features'.format(task.description()), aName, Qgis.Info)
    task.setProgress(90)
    ret, val = writeVector( vectorLayer, layerName, geopackage)
    QgsMessageLog.logMessage('task {}\twriting to geopackage'.format(task.description()), aName, Qgis.Info)
    if ret != 0:
        raise Exception('written to geopackage'+str(val))
        return False
    task.setProgress(100)
    QgsMessageLog.logMessage('task Ended {}'.format(task.description()), aName, Qgis.Info)
    return True

def writeVector( vectorLayer, layerName, geopackage):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    options.layerName = layerName
    if os.path.exists(geopackage):
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    else:
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    return QgsVectorFileWriter.writeAsVectorFormat( vectorLayer , geopackage, options)

def task_stopped(task):
    QgsMessageLog.logMessage(f'task {task.description()}\twas cancelled', aName, Qgis.Info)

def task_completed(exception, result=None):
    """ NEVER WORKS WITH TASK FROM FUNCTION !!
        this is called when run is finished. Exception is not None if run
        raises an exception. Result is the return value of run."""
    if exception is None:
        if result is None:
            QgsMessageLog.logMessage('task ?\tCompleted with no exception and no result (probably the task was manually canceled by the user)', aName, Qgis.Warning)
        else:
            QgsMessageLog.logMessage('task {}\tCompleted! after {} iterations'.format(result['task'],result['iterations']), aName, Qgis.Warning)
    else:
        QgsMessageLog.logMessage("Exception: {}".format(exception), aName, Qgis.Critical)
        raise exception

