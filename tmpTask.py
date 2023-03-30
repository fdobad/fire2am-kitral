from .qgis_utils import array2rasterFloat32, rasterRenderInterpolatedPseudoColor, writeVectorLayer
from qgis.core import QgsApplication, QgsTask, QgsMessageLog, Qgis, QgsRasterBandStats
from pandas import DataFrame, concat
from shutil import rmtree
from pathlib import Path
from scipy import stats
import numpy as np
import re
from .fire2am_utils import log, aName, check

MESSAGE_CATEGORY = 'Background_'+aName

class tmpTask(QgsTask):
    def __init__(self, description, iface, dlg, args, dirName, fileName, layerName, out_gpkg, stats_gpkg, extent, crs):
        super().__init__(description, QgsTask.CanCancel)
        self.exception = None
        self.args = args
        self.dlg = dlg
        self.iface = iface
        self.dirName = dirName 
        self.directory = Path( self.args['OutFolder'], self.dirName)
        self.fileName = fileName 
        self.layerName = layerName
        self.out_gpkg = out_gpkg
        self.stats_gpkg = stats_gpkg
        self.extent = extent 
        self.crs = crs 
        self.data = []
        self.simNum = 0
        self.filelist = []
        self.widthNum = 0
        self.nsim = 0
        self.subTask = None

    def run(self):
        QgsMessageLog.logMessage(self.description()+' Started',MESSAGE_CATEGORY, Qgis.Info)
        ''' get filelist '''
        filelist = sorted( self.directory.glob( self.fileName+'[0-9]*.asc'))
        filestring = ' '.join([ f.stem for f in filelist ])
        simNum = np.fromiter( re.findall( '([0-9]+)', filestring), dtype=int, count=len(filelist))
        asort = np.argsort( simNum)
        simNum = simNum[ asort]
        filelist = np.array( filelist)[ asort]
        widthNum = len(str(np.max( simNum)))
        nsim = len(simNum)
        QgsMessageLog.logMessage(self.description()+' getting %s files'%nsim,MESSAGE_CATEGORY, Qgis.Info)
        ''' get all asc 2 array '''
        for i,afile in enumerate(filelist):
            self.data += [ np.loadtxt( afile, dtype=np.float32, skiprows=6)]
            self.setProgress((i+1)/nsim*50)
            if self.isCanceled():
                QgsMessageLog.logMessage(self.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                return False
            '''# simulate exceptions to show how to abort task
            if False:
                self.exception = Exception('bad value!')
                return False
            '''
        ''' store for next stage '''
        self.data = np.array(self.data)
        self.filelist = filelist
        self.widthNum = widthNum 
        self.simNum = simNum
        self.nsim = nsim
        return True

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage(self.description()+' Got files w/result %s data shape %s'%(result, self.data.shape), MESSAGE_CATEGORY, Qgis.Info)
            # write mean raster
            '''
            if self.nsim>1:
                meanData = np.mean( self.data, axis=0, dtype=np.float32)
            else:
                meanData  = self.data
            '''
            meanData = np.mean( self.data, axis=0, dtype=np.float32)
            array2rasterFloat32( meanData, self.layerName, self.stats_gpkg, self.extent, self.crs, nodata = 0.0)
            ''' show layer '''
            layer = self.iface.addRasterLayer('GPKG:'+str(self.stats_gpkg)+':'+self.layerName, self.layerName)
            minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
            maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
            rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)
            log('shown... now storing rasters', pre=self.layerName, level=4, msgBar=self.dlg.msgBar)
            # describe mean raster into table
            st = stats.describe( meanData, axis=None)
            #df = DataFrame( st, index=st._fields, columns=[self.layerName])
            df = DataFrame( (self.layerName,*st), index=('Name',*st._fields), columns=[self.layerName])
            # get current table add column, store, reset
            bf = self.dlg.statdf
            df = concat([bf,df], axis=1)
            self.dlg.statdf = df
            self.dlg.tableView_1.setModel(self.dlg.PandasModel(df))
            #QgsMessageLog.logMessage(self.description()+' strdf %s'%(df), MESSAGE_CATEGORY, Qgis.Info)
            # write all rasters to gpkg in subtask
            if self.nsim > 1:
                self.subTask = QgsTask.fromFunction(self.description()+' store rasters', self.sub_run, on_finished=sub_finished)
                QgsApplication.taskManager().addTask( self.subTask)
            else:
                rmtree(self.directory)
                QgsMessageLog.logMessage(self.description()+' done', MESSAGE_CATEGORY, Qgis.Info)
        else:
            if self.exception is None:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
            else:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w exception %s'%self.exception, MESSAGE_CATEGORY, Qgis.Warning)
                raise self.exception

    def cancel(self):
        QgsMessageLog.logMessage(self.description()+' was canceled', MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()

    def sub_run(self, task):
        # write all rasters to gpkg
        task.setProgress(50)
        for i,(s,afile) in enumerate(zip(self.simNum,self.filelist)):
            array2rasterFloat32( self.data[i], self.layerName+str(s).zfill(self.widthNum), self.out_gpkg, self.extent, self.crs, nodata = 0.0)
            task.setProgress(s/self.nsim*50+50)
            if task.isCanceled():
                QgsMessageLog.logMessage(self.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                return {'result':False}
        return {'result':True, 'description':task.description(), 'directory':self.directory}

def sub_finished(exception, result):
    if exception is None:
        if result is None:
            #log('L sub Finished w/o result w/o exception', level=1)
            QgsMessageLog.logMessage('sub ? Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
        else:
            #log('L sub %s Got files w/result %s'%(result['description'], result['result']), level=0)
            QgsMessageLog.logMessage('sub %s Finished w/result %s'%(result['description'], result['result']), MESSAGE_CATEGORY, Qgis.Info)
            rmtree(result['directory'])
    else:
        #log('L sub Finished w exception %s', level=1)
        QgsMessageLog.logMessage('sub ? Finished w exception %s'%exception, MESSAGE_CATEGORY, Qgis.Warning)
        raise exception
    
