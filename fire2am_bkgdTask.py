#!/bin/env python3
import re
from datetime import datetime, timedelta
from os import sep
from os.path import join as os_path_join
from pathlib import Path
from shutil import rmtree
import networkx as nx
import numpy as np
from scipy import stats
from pandas import DataFrame, Timestamp, concat
# QGIS
import processing
# pylint: disable=no-name-in-module
from qgis.core import (Qgis, QgsApplication, QgsCoordinateReferenceSystem,
                       QgsFeature, QgsField, QgsGeometry, QgsMessageLog,
                       QgsPointXY, QgsRasterBandStats, QgsRasterLayer,
                       QgsRectangle, QgsTask, QgsVectorFileWriter,
                       QgsVectorLayer)
from qgis.PyQt.Qt import Qt
from qgis.PyQt.QtCore import QVariant
# pylint: enable=no-name-in-module
# plugin
from .extras.downstream_protection_value import digraph_from_messages, shortest_propagation_tree, dpv_maskG, get_flat_pv
from .fire2am_utils import aName  # , log,
from .qgis_utils import (array2rasterFloat32, array2rasterInt16, id2xy,
                         matchRasterCellIds2points, mergeVectorLayers,
                         rasterRenderInterpolatedPseudoColor, writeVectorLayer)

MESSAGE_CATEGORY = 'Background_'+aName

class after_ForestGrid(QgsTask):
    '''
    TODO: replace polygons timestamp with Weather datetime

    prerequisite : results/Grids exists
    run:
        glob filelist 'Grids(int)/ForestGrid(int).csv'
        sort & order (simulation,grid) indexes descending (later layers under sooner & smaller early layers)
        split indexes per simulation
        load data array (also test if != 0s)
        test all zeros -> exit
            some zeros -> warning
    onfinished:
        subTask mean_FireScar:
            run:
                if nsim > 1: mean data on first axis
                array to stats raster
                calc stats
            onfinished:
                load & style raster
                load stats dataframe
        for each simulation s:
            subTask FireEvolution_s:
                run:
                    for all nonZero grids:
                        data to raster
                    if nonZero grids > 1:
                        rasterS to polygonS
                        merge polygonS
                onfinished:
                    load & style merged
    '''
    def __init__(self, description, layerName, iface, dlg, args, extent, crs, plugin_dir):
        super().__init__(description, QgsTask.CanCancel)
        self.exception = None
        self.layerName = layerName
        self.args = args
        self.dlg = dlg
        self.iface = iface
        self.extent = extent 
        self.crs = crs 
        self.plugin_dir = plugin_dir
        assert isinstance( self.extent , QgsRectangle)
        assert isinstance( self.crs , QgsCoordinateReferenceSystem)
        self.subTask = {}
        self.filelist = []
        self.numbers = []
        self.sim_num = []
        self.final_grid_idx = []
        self.sim_totals = []
        self.total = 0
        self.sim_idx = []
        self.sim_nu = []
        self.sim_fi = []
        self.data = []
        self.sim_zeros = []
        self.width1stNum = 0
        self.width2ndNum = 0
        self.directory = args['OutFolder'] / 'Grids'
        self.out_gpkg = args['OutFolder'] / (layerName+'.gpkg')
        self.rout_gpkg = args['OutFolder'] / ('r'+layerName+'.gpkg')
        self.vout_gpkg = args['OutFolder'] / ('v'+layerName+'.gpkg')
        self.evout_gpkg = args['OutFolder'] / (layerName+'Evolution.gpkg')
        #TODO: all datetimes start same day
        #self.now = datetime.now()
        self.now = datetime(2023, 1, 1, 0, 0)
        self.dt = []
        self.sim_dt = []

    def run(self):
        QgsMessageLog.logMessage(self.description()+' bg Started',MESSAGE_CATEGORY, Qgis.Info)
        ''' get filelist '''
        filelist = list(self.directory.glob('Grids[0-9]*'+sep+'ForestGrid[0-9]*.csv'))
        filestring = ' '.join([ f'{f.parts[-2]}_{f.parts[-1]}' for f in filelist ])
        numbers = np.fromiter( re.findall( 'Grids([0-9]+)_ForestGrid([0-9]+).csv', filestring), dtype=[('x',int),('y',int)], count=len(filelist))
        # sorts ascending
        asort = np.argsort(numbers, order=('x','y'))
        # descending + unique gives last grid index
        numbers = np.array([ [n[0],n[1]] for n in numbers ])[asort][::-1]
        filelist = np.array(filelist)[asort][::-1]
        total = len(filelist)
        # get
        uniques, indexes, counts = np.unique( numbers[:,0], return_index=True, return_counts=True)
        sim_num = uniques[::-1]
        final_grid_idx = indexes[::-1]
        sim_totals = counts[::-1]
        ''' last of every sim'''
        #numbers[final_grid_idx]
        #filelist[final_grid_idx]
        ''' sim splited '''
        sim_idx = np.split( range(total),final_grid_idx)[1:]
        sim_nu = np.split( numbers,final_grid_idx)[1:]
        sim_fi = np.split( filelist,final_grid_idx)[1:]
        #for s,tg,nu,fi,ii in zip(sim_num,sim_totals,sim_nu,sim_fi,sim_idx):
        #    assert np.all(fi == filelist[ii])
        #    assert np.all(nu == numbers[ii])
        #    print('sim',s,'total grids',tg)
        #    #print('\tnu',nu,'\tfi',fi)
        #    print('\tnu',nu.T,'\tfi',[ (f.parts[-2],f.stem) for f in fi])
        ''' get all data'''
        data = []
        data_isZeros = []
        for i,afile in enumerate(filelist):
            #QgsMessageLog.logMessage(self.description()+' loading %s,%s'%(i,afile), MESSAGE_CATEGORY, Qgis.Warning)
            data += [ np.loadtxt( afile , delimiter=',', dtype=np.int8)]
            if np.any( data[-1] != 0 ):
                data_isZeros += [ False]
            else:
                data_isZeros += [ True ]
            self.setProgress((i+1)/total*50)
            if self.isCanceled():
                QgsMessageLog.logMessage(self.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                return False
        data = np.array(data)
        sim_zeros = np.split( data_isZeros,final_grid_idx)[1:]
        ''' exit if nothing burned '''
        if all( data_isZeros):
            QgsMessageLog.logMessage(self.description()+' Nothing Burned! All %s data is zero'%len(total), MESSAGE_CATEGORY, Qgis.Warning)
            return False
        if any( data_isZeros):
            # TODO get to msgBar self.=
            QgsMessageLog.logMessage(self.description()+' Not Burned for %s'%[ f.parts[-2]+'/'+f.stem for f in filelist[ data_isZeros]], MESSAGE_CATEGORY, Qgis.Warning)
        ''' store for next stage '''
        self.filelist = filelist
        self.numbers = numbers
        self.sim_num = sim_num 
        self.final_grid_idx = final_grid_idx 
        self.sim_totals = sim_totals 
        self.total = total
        self.sim_idx = sim_idx 
        self.sim_nu = sim_nu 
        self.sim_fi = sim_fi 
        self.data = data
        self.data_isZeros = data_isZeros 
        self.sim_zeros = sim_zeros 
        first, second = numbers.T
        self.width1stNum, self.width2ndNum = len(str(np.max(first))), len(str(np.max(second)))
        #TODO note ascending datetime, inverts simulation num
        #self.dt = [ self.now-timedelta(hours=i) for i in range(total)]
        self.dt = [ self.now+timedelta(hours=i) for i in range(total)]
        self.sim_dt = np.split( self.dt, final_grid_idx)[1:]
        QgsMessageLog.logMessage(self.description()+' bg Ended',MESSAGE_CATEGORY, Qgis.Info)
        return True

    def finished(self, result):
        QgsMessageLog.logMessage(self.description()+' fg Started', MESSAGE_CATEGORY, Qgis.Info)
        if result:
            QgsMessageLog.logMessage(self.description()+' fg Got files w/result %s data shape %s'%(result, self.data.shape), MESSAGE_CATEGORY, Qgis.Info)
            ''' sub meanFireScar '''
            self.subTask['meanFireScar'] = QgsTask.fromFunction(self.description()+' mean calculation', self.sub_meanFireScar, on_finished=after_ForestGrid_meanFireScar_finished)
            QgsApplication.taskManager().addTask( self.subTask['meanFireScar'])
            ''' sub for each sim FireEvolution '''
            for s,t,z,nu,fi,ii,dt in zip(self.sim_num, self.sim_totals, self.sim_zeros, self.sim_nu, self.sim_fi, self.sim_idx, self.sim_dt):
                tg = t - np.sum(z) # total good != 0 data
                if tg>1:
                    mergedName = 'FireEvolution_'+str(s).zfill(self.width1stNum)
                    self.subTask[mergedName] = QgsTask.fromFunction(self.description()+' FireEvolution simulation %s'%s, self.sub_FireEvolution, s, tg, ii, nu, dt, mergedName, on_finished=after_ForestGrid_FireEvolution_finished)
                    QgsApplication.taskManager().addTask( self.subTask[mergedName])

        else:
            if self.exception is None:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
            else:
                QgsMessageLog.logMessage(self.description()+' fg Finished w/o result w exception %s'%self.exception, MESSAGE_CATEGORY, Qgis.Warning)
                raise self.exception
        QgsMessageLog.logMessage(self.description()+' fg Ended', MESSAGE_CATEGORY, Qgis.Info)

    def cancel(self):
        QgsMessageLog.logMessage(self.description()+' was canceled', MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()

    def sub_meanFireScar(self, task):
        QgsMessageLog.logMessage(task.description()+' bg Started', MESSAGE_CATEGORY, Qgis.Info)
        ''' get burn prob '''
        meanData = np.mean( self.data[self.final_grid_idx], axis=0, dtype=np.float32)
        name_prefix = 'mean_' if len(self.sim_num) > 1 else ''
        layerName = name_prefix + self.layerName
        array2rasterFloat32( meanData, layerName, self.out_gpkg, self.extent, self.crs, nodata = 0.0)
        st = stats.describe( meanData, axis=None)
        df = DataFrame( (layerName,*st), index=('Name',*st._fields), columns=[layerName])
        QgsMessageLog.logMessage(task.description()+' bg Ended', MESSAGE_CATEGORY, Qgis.Info)
        return {'result':True, 'description':task.description(), 'df':df, 'iface':self.iface, 'dlg':self.dlg, 'out_gpkg':self.out_gpkg, 'layerName':layerName }

    def sub_FireEvolution(self, task, s, tg, ii, nu, dt, mergedName):
        QgsMessageLog.logMessage(task.description()+' bg Started ', MESSAGE_CATEGORY, Qgis.Info)
        #QgsMessageLog.logMessage(task.description()+f' started {s} {tg} {ii} {nu} {dt}', MESSAGE_CATEGORY, Qgis.Info)
        # TODO task.setProgress(s/self.total*50+50)
        task.setProgress(50)
        #TODO on next line:datetime inverted with dt[::-1]
        for i,(nsim,ngrid),timestamp in zip(ii,nu,dt[::-1]):
            if not self.data_isZeros[i]:
                evolayer = self.layerName+'_'+str(nsim).zfill(self.width1stNum)+'_'+str(ngrid).zfill(self.width2ndNum)
                #QgsMessageLog.logMessage(task.description()+f' evolayer {evolayer}', MESSAGE_CATEGORY, Qgis.Info)
                array2rasterInt16( self.data[i], evolayer, self.rout_gpkg, self.extent, self.crs, nodata = 0)
                raster2vector_wTimestamp( evolayer, self.rout_gpkg, self.vout_gpkg, self.extent, self.crs, timestamp)
                if task.isCanceled():
                    QgsMessageLog.logMessage(task.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                    return {'result':False}
        if tg > 1:
            #QgsMessageLog.logMessage(task.description()+' tg>1 1', MESSAGE_CATEGORY, Qgis.Info)
            polys=[ str(self.vout_gpkg)+'|layername='+self.layerName+'_'+str(nsim).zfill(self.width1stNum)+'_'+str(ngrid).zfill(self.width2ndNum) \
                    for i,(nsim,ngrid) in zip(ii,nu) if not self.data_isZeros[i]]
            #QgsMessageLog.logMessage(task.description()+f' tg>1 {polys[-1]}', MESSAGE_CATEGORY, Qgis.Info)
            #mergeVectorLayers( polys, str(self.vout_gpkg), mergedName )
            mergeVectorLayers( polys, str(self.evout_gpkg), mergedName )
            #QgsMessageLog.logMessage(task.description()+' tg>1 2', MESSAGE_CATEGORY, Qgis.Info)
        QgsMessageLog.logMessage(task.description()+' bg Ended', MESSAGE_CATEGORY, Qgis.Info)
        return {'result':True, 'description':task.description(), 'iface':self.iface, 'dlg':self.dlg, 'vout_gpkg':self.evout_gpkg, 'mergedName':mergedName, 'plugin_dir':self.plugin_dir}

def after_ForestGrid_meanFireScar_finished(exception, result):
    QgsMessageLog.logMessage(result['description']+' fg Started', MESSAGE_CATEGORY, Qgis.Info)
    if exception is None:
        if result is None:
            QgsMessageLog.logMessage(result['description']+' Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
        else:
            QgsMessageLog.logMessage(result['description']+' Finished w/result %s'%result['result'], MESSAGE_CATEGORY, Qgis.Info)
            layer = result['iface'].addRasterLayer('GPKG:'+str(result['out_gpkg'])+':'+result['layerName'], result['layerName'])
            minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
            maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
            rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)
            bf = result['dlg'].statdf
            df = concat([bf,result['df']], axis=1)
            result['dlg'].statdf = df
            result['dlg'].tableView_1.setModel(result['dlg'].PandasModel(df))
            QgsMessageLog.logMessage(result['description']+f' done ui update {type(result["dlg"])} {type(result["iface"])}', MESSAGE_CATEGORY, Qgis.Info)
    else:
        QgsMessageLog.logMessage(result['description']+' Finished w exception %s'%exception, MESSAGE_CATEGORY, Qgis.Warning)
        raise exception
    QgsMessageLog.logMessage(result['description']+' fg Ended', MESSAGE_CATEGORY, Qgis.Info)
    
def after_ForestGrid_FireEvolution_finished(exception, result):
    QgsMessageLog.logMessage(result['description']+' fg Started', MESSAGE_CATEGORY, Qgis.Info)
    if exception is None:
        if result is None:
            QgsMessageLog.logMessage(result['description']+' Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
        else:
            QgsMessageLog.logMessage(result['description']+' Finished w/result %s'%result['result'], MESSAGE_CATEGORY, Qgis.Info)
            vectorLayer = result['iface'].addVectorLayer( str(result['vout_gpkg'])+'|layername='+result['mergedName'], result['mergedName'], 'ogr')
            vectorLayer.loadNamedStyle( os_path_join( result['plugin_dir'], 'img'+sep+'Fire_Evolution_layerStyle.qml'))
            QgsMessageLog.logMessage(result['description']+' fg ui updated', MESSAGE_CATEGORY, Qgis.Info)
    else:
        QgsMessageLog.logMessage(result['description']+' fg Finished w exception %s'%exception, MESSAGE_CATEGORY, Qgis.Warning)
        raise exception
    QgsMessageLog.logMessage(result['description']+' fg Ended', MESSAGE_CATEGORY, Qgis.Info)

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
            #log('shown... now storing rasters', pre=self.layerName, level=4, msgBar=self.dlg.msgBar)
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
    
def raster2vector_wTimestamp( layerName, rout_gpkg, vout_gpkg, extent, crs, dt):
    ''' from rout_gpkg to vout_gpkg geopackages '''
    rasterLayer = QgsRasterLayer('GPKG:'+str(rout_gpkg)+':'+layerName, layerName)
    tmp = processing.run('gdal:polygonize',
               {'BAND' : 1, 
                'EIGHT_CONNECTEDNESS' : False, 
                'EXTRA' : '', 
                'FIELD' : 'DN', 
                'INPUT' : rasterLayer, 
                'OUTPUT' : 'TEMPORARY_OUTPUT' })['OUTPUT']
    vectorLayer = QgsVectorLayer( tmp, layerName)
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    options.layerName = layerName
    # add datetime field
    if not vectorLayer.isEditable():
        vectorLayer.startEditing()
    vectorLayer.dataProvider().addAttributes([QgsField('datetime',QVariant.DateTime)])
    vectorLayer.updateFields()
    idx = vectorLayer.fields().indexFromName('datetime')
    for feature in vectorLayer.getFeatures():
        attr = { idx: Timestamp(dt).isoformat(timespec='seconds')}
        #attr = { idx: dt}
        vectorLayer.dataProvider().changeAttributeValues({ feature.id() : attr})
    vectorLayer.commitChanges()
    # write
    if vout_gpkg.is_file():
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    else:
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    QgsVectorFileWriter.writeAsVectorFormat( vectorLayer, str(vout_gpkg), options)

'''
from datetime import datetime, timedelta
class nextHour:
    def __init__(self):
        self.now = datetime.now()
    def next(self):
        self.now -= timedelta(hours=1)
        return Timestamp(self.now).isoformat(timespec='seconds')
'''

def afterTask_logFile(task, logText, layerName, baseLayer, out_gpkg):
    QgsMessageLog.logMessage(task.description()+' Started ', MESSAGE_CATEGORY, Qgis.Info)
    task.setProgress(0)
    ''' get [sim,cell] from regex '''
    simulation, ignitionCell = np.fromiter( re.findall( 'ignition point for Year [0-9]*, sim ([0-9]+): ([0-9]+)',
                                                        logText), dtype=np.dtype((int,2)) ).T
    ''' add each point feature '''
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
            raise Exception('canceled')
        c+=1
    QgsMessageLog.logMessage(task.description()+' added feature points', MESSAGE_CATEGORY, Qgis.Info)
    ''' create vector layer '''
    vectorLayer = QgsVectorLayer( 'point', layerName, 'memory')
    vectorLayer.setCrs( baseLayer.crs())
    ret, val = vectorLayer.dataProvider().addFeatures(feats)
    if not ret:
        raise Exception(task.description()+' exception creating vector layer in memory adding features '+str(val))
    QgsMessageLog.logMessage(task.description()+' created vector layer in memory, added features', MESSAGE_CATEGORY, Qgis.Info)
    task.setProgress(90)
    ret, val = writeVectorLayer( vectorLayer, layerName, out_gpkg)
    if ret != 0:
        raise Exception(task.description()+' exception written to geopackage '+str(val))
    QgsMessageLog.logMessage(task.description()+' wrote geopackage', MESSAGE_CATEGORY, Qgis.Info)
    task.setProgress(100)
    QgsMessageLog.logMessage(task.description()+' Ended', MESSAGE_CATEGORY, Qgis.Info)

class after_betweenness_centrality(QgsTask):
    def __init__(self, description, iface, dlg, args, folder_name, file_name, extent, crs, plugin_dir):
        super().__init__(description, QgsTask.CanCancel)
        self.exception = None
        self.args = args
        self.directory = Path( self.args['OutFolder'], folder_name)
        self.layer_name = description
        self.file_name = file_name
        self.gpkg = Path( self.args['OutFolder'], description+'.gpkg')
        self.dlg = dlg
        self.iface = iface
        self.extent = extent
        self.crs = crs
        self.bc = None
        self.data = []
        self.plugin_dir = plugin_dir

    def run(self):
        QgsMessageLog.logMessage(self.description()+' Started ',MESSAGE_CATEGORY, Qgis.Info)
        ''' get filelist '''
        file_list = sorted( self.directory.glob( self.file_name+'[0-9]*.csv'))
        file_string = ' '.join([ f.stem for f in file_list ])
        ''' sort by number '''
        sim_num = np.fromiter( re.findall( '([0-9]+)', file_string), dtype=int, count=len(file_list))
        asort = np.argsort( sim_num)
        sim_num = sim_num[ asort]
        file_list = np.array( file_list)[ asort]
        num_width = len(str(np.max( sim_num)))
        nsim = len(sim_num)

        QgsMessageLog.logMessage(self.description()+' getting %s files'%nsim,MESSAGE_CATEGORY, Qgis.Info)
        ''' get all asc 2 array '''
        for i,afile in enumerate(file_list):
            self.data +=[ np.loadtxt( afile, delimiter=',', dtype=[('i',np.int32),('j',np.int32),('t',np.int16)], usecols=(0,1,2))]
            self.setProgress((i+1)/nsim*10)
            if self.isCanceled():
                QgsMessageLog.logMessage(self.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                return False
        ''' make a graph with keys=simulations, weights=burnt time '''
        QgsMessageLog.logMessage(self.description()+' building MultiDiGraph',MESSAGE_CATEGORY, Qgis.Info)
        mdg = nx.MultiDiGraph()
        func = np.vectorize(lambda x:{'weight':x})
        for k,dat in enumerate(self.data):
            # ebunch_to_add : container of 4-tuples (u, v, k, d) for an edge with data and key k
            bunch = np.vstack(( dat['i'], dat['j'], [k]*len(dat), func(dat['t']) )).T
            mdg.add_edges_from( bunch)
            #print('sim',k,bunch[:3])
            self.setProgress(0.1+(i+1)/nsim*10)
            if self.isCanceled():
                QgsMessageLog.logMessage(self.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                return False
        
        QgsMessageLog.logMessage(self.description()+' calculating betweenness_centrality k=int(5*sqrt(|G|))',MESSAGE_CATEGORY, Qgis.Info)
        # outputs {nodes:betweenness_centrality_float_value}
        #checks for raise ValueError("Sample larger than population or is negative")
        ksample = np.min(( mdg.number_of_nodes(), int(5*np.sqrt(mdg.number_of_nodes()))))
        centrality = nx.betweenness_centrality(mdg, k=ksample, weight='weight')
        #log(centrality, level=0)

        QgsMessageLog.logMessage(self.description()+' building resulting layer',MESSAGE_CATEGORY, Qgis.Info)

        self.setProgress(0.9)
        layer = self.dlg.state['layerComboBox_fuels']
        W,H = layer.width(), layer.height()
        centrality_xy = [ [*id2xy( key-1, W, H), value] for key,value in centrality.items() ]
        centrality_array = np.zeros((H,W), dtype=np.float32)

        self.layer_name='betweenness_centrality'
        for x,y,v in centrality_xy:
            centrality_array[y,x]=v
        array2rasterFloat32( centrality_array, self.layer_name, self.gpkg, self.extent, self.crs, nodata = 0.0)
        QgsMessageLog.logMessage(self.description()+' foo ',MESSAGE_CATEGORY, Qgis.Info)
        # TODO 
        # fix self.data = np.array(self.data)
        # is it tuples inside ?
        QgsMessageLog.logMessage(self.description()+' bar ',MESSAGE_CATEGORY, Qgis.Info)
        return True

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage(self.description()+' finished w/result %s'%result, MESSAGE_CATEGORY, Qgis.Info)
            #QgsMessageLog.logMessage(self.description()+' finished w/result %s data shape %s'%(result, self.data.shape), MESSAGE_CATEGORY, Qgis.Info)
            ''' show layer '''
            layer = self.iface.addRasterLayer('GPKG:'+str(self.gpkg)+':'+self.layer_name, self.layer_name)
            minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
            maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
            rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)
            '''
            #log('shown... now storing rasters', pre=self.layerName, level=4, msgBar=self.dlg.msgBar)
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
            '''
        else:
            if self.exception is None:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
            else:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w exception %s'%self.exception, MESSAGE_CATEGORY, Qgis.Warning)
                raise self.exception

    def cancel(self):
        QgsMessageLog.logMessage(self.description()+' was canceled', MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()

class after_downstream_protection_value(QgsTask):
    def __init__(self, description, iface, dlg, args, plugin_dir, fuel_layer, protection_value_layer=None):
        super().__init__(description, QgsTask.CanCancel)
        self.layer_name = description
        self.exception = None
        self.iface = iface
        self.dlg = dlg
        self.args = args
        self.plugin_dir = plugin_dir
        self.directory = self.args['OutFolder'] / 'Messages'
        self.file_name = 'MessagesFile'
        self.gpkg = self.args['OutFolder'] / (description+'.gpkg')
        if protection_value_layer:
            #TODO basename?
            self.pv, self.W, self.H = get_flat_pv( protection_value_layer.publicSource())

        else:
            self.W = fuel_layer.width()
            self.H = fuel_layer.height()
            self.pv = np.ones(self.H*self.W)
        self.crs = fuel_layer.crs()
        self.extent = fuel_layer.extent()
        self.dpv = np.zeros(self.H*self.W)

    def run(self):
        QgsMessageLog.logMessage(self.description()+' Started ',MESSAGE_CATEGORY, Qgis.Info)
        # get filelist
        file_list = [ f for f in self.directory.glob( self.file_name+'[0-9]*.csv') if f.stat().st_size > 0]
        file_string = ' '.join([ f.stem for f in file_list ])
        # sort by number
        sim_num = np.fromiter( re.findall( '([0-9]+)', file_string), dtype=int, count=len(file_list))
        asort = np.argsort( sim_num)
        sim_num = sim_num[ asort]
        file_list = np.array( file_list)[ asort]
        # get stats
        num_width = len(str(np.max( sim_num)))
        nsim = len(sim_num)
        # loop add dpv
        QgsMessageLog.logMessage(f'{self.description()} looping through {nsim} files',MESSAGE_CATEGORY, Qgis.Info)
        for i,msgfile in enumerate(file_list):
            QgsMessageLog.logMessage(f'{self.description()} 1 end loop {i}',MESSAGE_CATEGORY, Qgis.Info)
            msgG, root = digraph_from_messages(msgfile)
            QgsMessageLog.logMessage(f'{self.description()} 2 end loop {i}',MESSAGE_CATEGORY, Qgis.Info)
            treeG = shortest_propagation_tree(msgG, root)
            QgsMessageLog.logMessage(f'{self.description()} 3 end loop {i}',MESSAGE_CATEGORY, Qgis.Info)
            i2n = [n-1 for n in treeG] # TODO change to generator?
            QgsMessageLog.logMessage(f'{self.description()} 4 end loop {i}',MESSAGE_CATEGORY, Qgis.Info)
            mdpv = dpv_maskG(treeG, root, self.pv, i2n)
            QgsMessageLog.logMessage(f'{self.description()} 5 end loop {i}',MESSAGE_CATEGORY, Qgis.Info)
            #TODO-1ok?
            self.dpv[i2n] += mdpv
            QgsMessageLog.logMessage(f'{self.description()} 6 end loop {i}',MESSAGE_CATEGORY, Qgis.Info)
            self.setProgress((i+1)/nsim*100)
            if self.isCanceled():
                QgsMessageLog.logMessage(self.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                return False
        self.dpv=self.dpv/nsim
        QgsMessageLog.logMessage(f'{self.description()} creating raster',MESSAGE_CATEGORY, Qgis.Info)
        #TODO nodata?
        array2rasterFloat32( self.dpv.reshape(self.H,self.W), self.layer_name, self.gpkg, self.extent, self.crs)
        return True

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage(self.description()+' finished w/result %s'%result, MESSAGE_CATEGORY, Qgis.Info)
            ''' show layer '''
            layer = self.iface.addRasterLayer('GPKG:'+str(self.gpkg)+':'+self.layer_name, self.layer_name)
            minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
            maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
            rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)
            '''
            #log('shown... now storing rasters', pre=self.layerName, level=4, msgBar=self.dlg.msgBar)
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
            '''
        else:
            if self.exception is None:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
            else:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w exception %s'%self.exception, MESSAGE_CATEGORY, Qgis.Warning)
                raise self.exception

    def cancel(self):
        QgsMessageLog.logMessage(self.description()+' was canceled', MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()
