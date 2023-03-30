from .qgis_utils import array2rasterFloat32, rasterRenderInterpolatedPseudoColor, writeVectorLayer
from qgis.core import QgsApplication, QgsTask, QgsMessageLog, Qgis, QgsRasterBandStats
from datetime import datetime
from pandas import DataFrame
from pathlib import Path
from scipy import stats
import numpy as np
import re
from .fire2am_utils import log, aName

MESSAGE_CATEGORY = 'Background_'+aName

class tmpTask(QgsTask):
    def __init__(self, description, iface, dlg, args, dirName, fileName, layerName, out_gpkg, stats_gpkg, extent, crs):
        super().__init__(description, QgsTask.CanCancel)
        self.exception = None
        self.args = args
        self.dlg = dlg
        self.iface = iface
        self.dirName = dirName 
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
        QgsMessageLog.logMessage(self.description()+' Started %s'%datetime.now(),MESSAGE_CATEGORY, Qgis.Info)
        ''' get filelist '''
        filelist = sorted( Path( self.args['OutFolder'], self.dirName).glob( self.fileName+'[0-9]*.asc'))
        filestring = ' '.join([ f.stem for f in filelist ])
        simNum = np.fromiter( re.findall( '([0-9]+)', filestring), dtype=int, count=len(filelist))
        asort = np.argsort( simNum)
        simNum = simNum[ asort]
        filelist = np.array( filelist)[ asort]
        widthNum = len(str(np.max( simNum)))
        nsim = len(simNum)
        QgsMessageLog.logMessage(self.description()+' getting %s files'%len(simNum),MESSAGE_CATEGORY, Qgis.Info)
        ''' get all asc 2 array '''
        for i,afile in zip(simNum,filelist):
            self.data += [ np.loadtxt( afile,  dtype=np.float32, skiprows=6)]
            self.setProgress(i/nsim*50)
            if self.isCanceled():
                QgsMessageLog.logMessage(self.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                return False
            # simulate exceptions to show how to abort task
            if False:
                self.exception = Exception('bad value!')
                return False

        ''' store for next stage '''
        self.simNum = simNum
        self.nsim = len(simNum)
        self.filelist = filelist
        self.widthNum = widthNum 
        self.data = np.array(self.data)
        return True

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage(self.description()+' Got files w/result %s data shape %s'%(result, self.data.shape), MESSAGE_CATEGORY, Qgis.Info)

            # write mean raster
            meanData = np.mean( self.data, axis=0, dtype=np.float32)
            array2rasterFloat32( meanData, self.layerName, self.stats_gpkg, self.extent, self.crs, nodata = 0.0)
            ''' show layer '''
            layer = self.iface.addRasterLayer('GPKG:'+str(self.stats_gpkg)+':'+self.layerName, self.layerName)
            minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
            maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
            rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)
            log('mean calculated... now storing rasters', pre=self.layerName, level=4, msgBar=self.dlg.msgBar)

            # describe mean raster 2 table
            st = stats.describe( meanData, axis=None)
            df = DataFrame( st, index=st._fields, columns=['hey'])
            QgsMessageLog.logMessage(self.description()+' strdf %s'%(df), MESSAGE_CATEGORY, Qgis.Info)

            # write all rasters to gpkg in subtask
            self.subTask = QgsTask.fromFunction('to rasters', self.func, on_finished=None)
            QgsApplication.taskManager().addTask( self.subTask)

            QgsMessageLog.logMessage(self.description()+' super end', MESSAGE_CATEGORY, Qgis.Info)
        else:
            if self.exception is None:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
            else:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w exception %s'%self.exception, MESSAGE_CATEGORY, Qgis.Warning)
                raise self.exception

    def cancel(self):
        QgsMessageLog.logMessage(self.description()+' was canceled', MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()

    def func(self, task):
        # write all rasters to gpkg
        task.setProgress(0)
        for i,(s,afile) in enumerate(zip(self.simNum,self.filelist)):
            array2rasterFloat32( self.data[i], self.layerName+str(s).zfill(self.widthNum), self.out_gpkg, self.extent, self.crs, nodata = 0.0)
            task.setProgress(s/self.nsim*50+50)
            if task.isCanceled():
                QgsMessageLog.logMessage(self.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                return False
    
