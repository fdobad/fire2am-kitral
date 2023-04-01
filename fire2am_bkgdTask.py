from .qgis_utils import array2rasterFloat32, rasterRenderInterpolatedPseudoColor, writeVectorLayer
from qgis.core import QgsApplication, QgsTask, QgsMessageLog, Qgis, QgsRasterBandStats
from pandas import DataFrame, concat
from shutil import rmtree
from pathlib import Path
from scipy import stats
import numpy as np
import re
from .fire2am_utils import log, aName, check
from os import sep

MESSAGE_CATEGORY = 'Background_'+aName

class after_ForestGrid(QgsTask):
    def __init__(self, description, iface, dlg, args, layerName, out_gpkg, stats_gpkg, extent, crs):
        super().__init__(description, QgsTask.CanCancel)
        self.exception = None
        self.args = args
        self.dlg = dlg
        self.iface = iface
        self.directory = self.args['OutFolder'] / 'Grids'
        self.layerName = layerName
        self.out_gpkg = out_gpkg
        self.stats_gpkg = stats_gpkg
        self.extent = extent 
        self.crs = crs 
        self.data = []
        self.filelist = []
        self.lastSimIdx = []
        self.width1stNum = 0
        self.width2ndNum = 0
        self.numbers = 0
        self.total = 0
        self.subTask = {}

    def run(self):
        QgsMessageLog.logMessage(self.description()+' Started',MESSAGE_CATEGORY, Qgis.Info)
        ''' get filelist '''
        filelist = sorted( self.directory.glob('Grids[0-9]*'+sep+'ForestGrid[0-9]*.csv'))
        filestring = ' '.join([ f'{f.parts[-2]}_{f.parts[-1]}' for f in filelist ])
        numbers = np.fromiter( re.findall( 'Grids([0-9]+)_ForestGrid([0-9]+).csv', filestring), dtype=np.dtype((int,2)), count=len(filelist))
        ''' last simulation index, reversed '''
        lastSimIdx = np.unique( numbers[::-1][:,0], return_index=True)[1]
        filelist = np.array(filelist)[::-1]
        QgsMessageLog.logMessage(self.description()+'fllsi'+str(filelist[lastSimIdx]), MESSAGE_CATEGORY, Qgis.Warning)
        numbers = numbers[::-1]
        first, second = numbers.T
        width1stNum, width2ndNum = len(str(np.max(first))), len(str(np.max(second)))
        total = len(filelist)
        ''' get all csv 2 array '''
        data = []
        for i,afile in enumerate(filelist):
            data += [ np.loadtxt( afile, delimiter=',', dtype=np.int8)]
            self.setProgress((i+1)/total*50)
            if self.isCanceled():
                QgsMessageLog.logMessage(self.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                return False
        data = np.array(data)
        ''' store for next stage '''
        self.data = np.array(self.data)
        self.filelist = filelist
        self.width1stNum = width1stNum 
        self.width2ndNum = width2ndNum 
        self.numbers = numbers
        self.total = total
        return True

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage(self.description()+' Got files w/result %s data shape %s'%(result, self.data.shape), MESSAGE_CATEGORY, Qgis.Info)
            ''' map mean '''
            #self.subTask = QgsTask.fromFunction(self.description()+' store rasters', self.sub_run, on_finished=sub_finished)
            #QgsApplication.taskManager().addTask( self.subTask)
            meanData = np.mean( self.data[self.lastSimIdx], axis=0, dtype=np.float32)
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
            '''
            if self.nsim > 1:
                self.subTask = QgsTask.fromFunction(self.description()+' store rasters', self.sub_run, on_finished=sub_finished)
                QgsApplication.taskManager().addTask( self.subTask)
            else:
                rmtree(self.directory)
                QgsMessageLog.logMessage(self.description()+' done', MESSAGE_CATEGORY, Qgis.Info)
            '''
            self.subTask = QgsTask.fromFunction(self.description()+' store rasters', self.sub_raster2gpkg, on_finished=after_ForestGrid_sub_finished)
            QgsApplication.taskManager().addTask( self.subTask)
        else:
            if self.exception is None:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
            else:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w exception %s'%self.exception, MESSAGE_CATEGORY, Qgis.Warning)
                raise self.exception

    def cancel(self):
        QgsMessageLog.logMessage(self.description()+' was canceled', MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()

    def sub_mean(self, task):
        pass

    def sub_raster2gpkg(self, task):
        # write all rasters to gpkg
        task.setProgress(50)
        for i,(nsim,ngrid) in enumerate(numbers):
            name = self.layerName+'_'+str(nsim).zfill(self.width1stNum)+'_'+str(ngrid).zfill(self.width2ndNum)
            array2rasterInt16( self.data[i], name, self.out_gpkg, self.extent, self.crs, nodata = 0.0)
            task.setProgress(s/self.total*50+50)
            if task.isCanceled():
                QgsMessageLog.logMessage(self.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                return {'result':False}
        return {'result':True, 'description':task.description(), 'directory':self.directory}

def after_ForestGrid_sub_finished(exception, result):
    if exception is None:
        if result is None:
            QgsMessageLog.logMessage('sub ? Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
        else:
            QgsMessageLog.logMessage('sub %s Finished w/result %s'%(result['description'], result['result']), MESSAGE_CATEGORY, Qgis.Info)
            #rmtree(result['directory'])
    else:
        QgsMessageLog.logMessage('sub ? Finished w exception %s'%exception, MESSAGE_CATEGORY, Qgis.Warning)
        raise exception
    
def after_ForestGrid_sub_mean_finished(exception, result):
    if exception is None:
        if result is None:
            QgsMessageLog.logMessage('sub ? Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
        else:
            QgsMessageLog.logMessage('sub %s Finished w/result %s'%(result['description'], result['result']), MESSAGE_CATEGORY, Qgis.Info)
            #rmtree(result['directory'])
    else:
        QgsMessageLog.logMessage('sub ? Finished w exception %s'%exception, MESSAGE_CATEGORY, Qgis.Warning)
        raise exception

class after_asciiDir(QgsTask):
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
                self.subTask = QgsTask.fromFunction(self.description()+' store rasters', self.sub_run, on_finished=after_AsciiDir_sub_finished)
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

def after_AsciiDir_sub_finished(exception, result):
    if exception is None:
        if result is None:
            QgsMessageLog.logMessage('sub ? Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
        else:
            QgsMessageLog.logMessage('sub %s Finished w/result %s'%(result['description'], result['result']), MESSAGE_CATEGORY, Qgis.Info)
            rmtree(result['directory'])
    else:
        QgsMessageLog.logMessage('sub ? Finished w exception %s'%exception, MESSAGE_CATEGORY, Qgis.Warning)
        raise exception
    
