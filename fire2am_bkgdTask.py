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
                       QgsVectorLayer, QgsProject)
from qgis.PyQt.Qt import Qt
from qgis.PyQt.QtCore import QVariant
# pylint: enable=no-name-in-module
# plugin
from .fire2am_CONSTANTS import TAG, STATS_DESCRIBE_NAMES, STATS_BASE_NAMES, STATS_BASE_DF, GRID_NAMES, GRID_EMPTY_DF
from .extras.downstream_protection_value import digraph_from_messages, shortest_propagation_tree, dpv_maskG, get_flat_pv
from . import fire2a_checks
from .qgis_utils import (array2rasterFloat32, array2rasterInt16, id2xy,
                         matchRasterCellIds2points, mergeVectorLayers,
                         rasterRenderInterpolatedPseudoColor, writeVectorLayer)

MESSAGE_CATEGORY = TAG+'_background'

class after_ForestGrid(QgsTask):
    """
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
    """
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
        self.rout_gpkg = args['OutFolder'] / (layerName+'_sim.gpkg')
        self.vout_gpkg = args['OutFolder'] / (layerName+'_sim_polygon.gpkg')
        self.evout_gpkg = args['OutFolder'] / (layerName+'Evolution.gpkg')
        #TODO: all datetimes start same day
        #self.now = datetime.now()
        self.now = datetime(2023, 1, 1, 0, 0)
        self.dt = []
        self.sim_dt = []
        self.df = None
        self.tasklist_FE = []
        self.tasklist_FS = []

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
            ''' accum sub for each sim FireEvolution or simply Store '''
            for s,t,z,nu,fi,ii,dt in zip(self.sim_num, self.sim_totals, self.sim_zeros, self.sim_nu, self.sim_fi, self.sim_idx, self.sim_dt):
                tg = t - np.sum(z) # total good != 0 data
                if tg>1:
                    mergedName = 'FireEvolution_'+str(s).zfill(self.width1stNum)
                    self.tasklist_FE += [QgsTask.fromFunction(self.description()+' FireEvolution simulation %s'%s, self.sub_FireEvolution, s, tg, ii, nu, dt, mergedName, on_finished=after_ForestGrid_FireEvolution_finished)]
                elif tg==1:
                    name = 'FireSim_'+str(s).zfill(self.width1stNum)
                    self.tasklist_FS += [QgsTask.fromFunction(self.description()+' simulation %s store'%s, self.sub_StoreFireSim, s, tg, ii, nu, on_finished=after_ForestGrid_StoreFireSim_finished)]
            ''' execute chained '''
            if self.tasklist_FE != []:
                for i in range(len(self.tasklist_FE)-1):
                    self.tasklist_FE[i].addSubTask(self.tasklist_FE[i+1], [], QgsTask.ParentDependsOnSubTask)
                QgsApplication.taskManager().addTask(self.tasklist_FE[0])
            if self.tasklist_FS != []:
                for i in range(len(self.tasklist_FS)-1):
                    self.tasklist_FS[i].addSubTask(self.tasklist_FS[i+1], [], QgsTask.ParentDependsOnSubTask)
                QgsApplication.taskManager().addTask(self.tasklist_FS[0])
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
        stat = stats.describe( meanData, axis=None)
        stat_col = [layerName,'probability',*stat]
        QgsMessageLog.logMessage(task.description()+' bg Ended', MESSAGE_CATEGORY, Qgis.Info)
        return {'result':True, 'description':task.description(), 'stat_col':stat_col, 'iface':self.iface, 'dlg':self.dlg, 'out_gpkg':self.out_gpkg, 'layerName':layerName }

    def sub_StoreFireSim(self, task, s, tg, ii, nu):
        QgsMessageLog.logMessage(task.description()+' bg Started ', MESSAGE_CATEGORY, Qgis.Info)
        #QgsMessageLog.logMessage(task.description()+f' started {s} {tg} {ii} {nu} {dt}', MESSAGE_CATEGORY, Qgis.Info)
        # TODO task.setProgress(s/self.total*50+50)
        task.setProgress(50)
        #TODO on next line:datetime inverted with dt[::-1]
        stat_row = []
        for i,(nsim,ngrid) in zip(ii,nu):
            if not self.data_isZeros[i]:
                layerName = self.layerName+'_'+str(nsim).zfill(self.width1stNum)+'_'+str(ngrid).zfill(self.width2ndNum)
                #QgsMessageLog.logMessage(task.description()+f' layerName {layerName}', MESSAGE_CATEGORY, Qgis.Info)
                array2rasterInt16( self.data[i], layerName, self.rout_gpkg, self.extent, self.crs, nodata = 0)
                if task.isCanceled():
                    QgsMessageLog.logMessage(task.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                    return {'result':False}
                # add stat
                describe_result = stats.describe(self.data[i], axis=None)
                burned = self.data[i].sum()
                stat_row += [[nsim, ngrid, burned, *describe_result]]
                # QgsMessageLog.logMessage(task.description()+f' stat_row-1:{stat_row[-1]}', MESSAGE_CATEGORY, Qgis.Critical)

        return {'result':True, 'description':task.description(), 'stat_row':stat_row, 'dlg':self.dlg}

    def sub_FireEvolution(self, task, s, tg, ii, nu, dt, mergedName):
        QgsMessageLog.logMessage(task.description()+' bg Started ', MESSAGE_CATEGORY, Qgis.Info)
        #QgsMessageLog.logMessage(task.description()+f' started {s} {tg} {ii} {nu} {dt}', MESSAGE_CATEGORY, Qgis.Info)
        # TODO task.setProgress(s/self.total*50+50)
        task.setProgress(50)
        #TODO on next line:datetime inverted with dt[::-1]
        stat_row = []
        for i,(nsim,ngrid),timestamp in zip(ii,nu,dt[::-1]):
            if not self.data_isZeros[i]:
                evolayer = self.layerName+'_'+str(nsim).zfill(self.width1stNum)+'_'+str(ngrid).zfill(self.width2ndNum)
                #QgsMessageLog.logMessage(task.description()+f' evolayer {evolayer}', MESSAGE_CATEGORY, Qgis.Info)
                array2rasterInt16( self.data[i], evolayer, self.rout_gpkg, self.extent, self.crs, nodata = 0)
                raster2vector_wTimestamp( evolayer, self.rout_gpkg, self.vout_gpkg, self.extent, self.crs, timestamp)
                if task.isCanceled():
                    QgsMessageLog.logMessage(task.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                    return {'result':False}
                # new df
                describe_result = stats.describe(self.data[i], axis=None)
                burned = self.data[i].sum()
                stat_row += [[nsim, ngrid, burned, *describe_result]]
        if tg > 1:
            #QgsMessageLog.logMessage(task.description()+' tg>1 1', MESSAGE_CATEGORY, Qgis.Info)
            polys=[ str(self.vout_gpkg)+'|layername='+self.layerName+'_'+str(nsim).zfill(self.width1stNum)+'_'+str(ngrid).zfill(self.width2ndNum) \
                    for i,(nsim,ngrid) in zip(ii,nu) if not self.data_isZeros[i]]
            #QgsMessageLog.logMessage(task.description()+f' tg>1 {polys[-1]}', MESSAGE_CATEGORY, Qgis.Info)
            #mergeVectorLayers( polys, str(self.vout_gpkg), mergedName )
            mergeVectorLayers( polys, str(self.evout_gpkg), mergedName )
            #QgsMessageLog.logMessage(task.description()+' tg>1 2', MESSAGE_CATEGORY, Qgis.Info)
        QgsMessageLog.logMessage(task.description()+' bg Ended', MESSAGE_CATEGORY, Qgis.Info)
        return {'result':True, 'description':task.description(), 'iface':self.iface, 'dlg':self.dlg, 'stat_row':stat_row, 'vout_gpkg':self.evout_gpkg, 'mergedName':mergedName, 'plugin_dir':self.plugin_dir}

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

            result["dlg"].add_table('Stats')
            result["dlg"].add_col_to_stats(result['layerName'], result['stat_col'])

            QgsMessageLog.logMessage(result['description']+f" done table stat update {result['stat_col']}", MESSAGE_CATEGORY, Qgis.Info)
    else:
        QgsMessageLog.logMessage(result['description']+' Finished w exception %s'%exception, MESSAGE_CATEGORY, Qgis.Warning)
        raise exception
    QgsMessageLog.logMessage(result['description']+' fg Ended', MESSAGE_CATEGORY, Qgis.Info)

def after_ForestGrid_StoreFireSim_finished(exception, result):
    QgsMessageLog.logMessage(result['description']+' fg Started', MESSAGE_CATEGORY, Qgis.Info)
    if exception is None:
        if result is None:
            QgsMessageLog.logMessage(result['description']+' Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
        else:
            QgsMessageLog.logMessage(result['description']+' Finished w/result %s'%result['result'], MESSAGE_CATEGORY, Qgis.Info)
            result["dlg"].add_table('FireScar[px]', GRID_NAMES)
            for row in result['stat_row']:
                result["dlg"].add_row_to_table('FireScar[px]', row)
    else:
        QgsMessageLog.logMessage(result['description']+' fg Finished w exception %s'%exception, MESSAGE_CATEGORY, Qgis.Warning)
        raise exception
    QgsMessageLog.logMessage(result['description']+' fg Ended', MESSAGE_CATEGORY, Qgis.Info)

def after_ForestGrid_FireEvolution_finished(exception, result):
    # TODO add table with evolution & graph
    QgsMessageLog.logMessage(result['description']+' fg Started', MESSAGE_CATEGORY, Qgis.Info)
    if exception is None:
        if result is None:
            QgsMessageLog.logMessage(result['description']+' Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
        else:
            QgsMessageLog.logMessage(result['description']+' Finished w/result %s'%result['result'], MESSAGE_CATEGORY, Qgis.Info)
            vectorLayer = result['iface'].addVectorLayer( str(result['vout_gpkg'])+'|layername='+result['mergedName'], result['mergedName'], 'ogr')
            vectorLayer.loadNamedStyle( os_path_join( result['plugin_dir'], 'img'+sep+'Fire_Evolution_layerStyle.qml'))
            QgsMessageLog.logMessage(result['description']+' fg ui updated', MESSAGE_CATEGORY, Qgis.Info)
            result["dlg"].add_table('FireScar[px]', GRID_NAMES)
            for row in result['stat_row']:
                result["dlg"].add_row_to_table('FireScar[px]', row)
    else:
        QgsMessageLog.logMessage(result['description']+' fg Finished w exception %s'%exception, MESSAGE_CATEGORY, Qgis.Warning)
        raise exception
    QgsMessageLog.logMessage(result['description']+' fg Ended', MESSAGE_CATEGORY, Qgis.Info)

class after_asciiDir(QgsTask):
    def __init__(self, description, iface, dlg, args, dirName, fileName, layerName, unit_name, extent, crs):
        super().__init__(description, QgsTask.CanCancel)
        self.exception = None
        self.args = args
        self.dlg = dlg
        self.iface = iface
        self.dirName = dirName
        self.directory = Path( self.args['OutFolder'], self.dirName)
        self.fileName = fileName
        self.layerName = layerName
        self.unit_name = unit_name
        self.sims_gpkg =  self.args['OutFolder'] / (layerName+'_sims.gpkg')
        self.stat_gpkg =  self.args['OutFolder'] / (layerName+'.gpkg')
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
            meanData = np.mean( self.data, axis=0, dtype=np.float32)
            array2rasterFloat32( meanData, self.layerName, self.stat_gpkg, self.extent, self.crs, nodata = 0.0)
            ''' show layer '''
            layer = self.iface.addRasterLayer('GPKG:'+str(self.stat_gpkg)+':'+self.layerName, self.layerName)
            minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
            maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
            rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)

            describe_result = stats.describe( meanData, axis=None)
            stat_col = [self.layerName, self.unit_name, *describe_result]
            self.dlg.add_table('Stats')
            self.dlg.add_col_to_stats(self.layerName, stat_col)

            # QgsMessageLog.logMessage(f'WTF asciiDir! {self.dlg.table.keys()} {self.description()}', MESSAGE_CATEGORY, Qgis.Info)

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
            array2rasterFloat32( self.data[i], self.layerName+str(s).zfill(self.widthNum), self.sims_gpkg, self.extent, self.crs, nodata = 0.0)
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

class check_weather_folder_bkgd(QgsTask):
    def __init__(self, description, directory, dlg, nlog):
        super().__init__(description, QgsTask.CanCancel)
        self.exception = None
        self.directory = Path(directory)
        self.finished = False
        self.dlg = dlg
        self.nweathers = None
        self.nlog = nlog
    def run(self):
        try:
            self.setProgress(0)
            QgsMessageLog.logMessage(self.description()+' run started', MESSAGE_CATEGORY, Qgis.Info)
            if not self.directory.is_dir():
                self.nlog(text=f'Is not a directory: {self.directory}', title='Bad Weather Folder!', level=2, to_bar=True)
                return False
            if file_list:= list(self.directory.glob('Weather[0-9]*.csv')):
                self.nweathers = len(file_list)
                numbers = np.fromiter( re.findall( 'Weather([0-9]+)',
                                ''.join([ f.stem for f in file_list])),
                                dtype=np.int32, count=self.nweathers)
                asort = np.argsort(numbers)
                file_list = np.array(file_list)[asort]
                numbers = numbers[asort]
                for i,afile in enumerate(file_list):
                    if i+1 != numbers[i]:
                        self.nlog(text=f'weather file {afile} not sequentially numerated {i+1} in {self.directory}', title='Bad Weather Folder!', level=2, to_bar=True)
                        return False
                    if not fire2a_checks.weather_file(str(afile)): #, quick=True
                        self.nlog(text=f'bad weather file {afile} in {self.directory}', title='Bad Weather Folder!', level=2, to_bar=True)
                        return False
                    if self.isCanceled():
                        QgsMessageLog.logMessage(self.description()+' run was canceled', MESSAGE_CATEGORY, Qgis.Warning)
                        self.exception = Exception('run was canceled')
                        return False
                    self.setProgress((i+1)/self.nweathers*100)
                QgsMessageLog.logMessage(self.description()+' run ended', MESSAGE_CATEGORY, Qgis.Info)
                return True
            return False
        except Exception as e:
            self.exception = e
            return False
    def cancel(self):
        QgsMessageLog.logMessage(self.description()+' was canceled', MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()
    def finished(self, result):
        if self.exception:
            QgsMessageLog.logMessage(self.description()+' Finished w exception %s'%self.exception, MESSAGE_CATEGORY, Qgis.Warning)
            self.nlog(' Finished w exception {self.exception}', title='Weathers Folder Check!', level=4, to_bar=True)
        elif result:
            QgsMessageLog.logMessage(self.description()+' finished w/result %s'%result, MESSAGE_CATEGORY, Qgis.Info)
            self.dlg.args['nweathers'] = self.nweathers
            self.dlg.radioButton_weatherFolder.setChecked(True)
            self.dlg.state['radioButton_weatherFolder'] = True
            self.dlg.fileWidget_weatherFolder.blockSignals(True)
            self.dlg.fileWidget_weatherFolder.setFilePath( str(self.directory))
            self.dlg.fileWidget_weatherFolder.blockSignals(False)
            self.nlog(text=f'Found in {self.directory}', title=f"Weathers[1..{self.dlg.args['nweathers']}].csv", level=4, to_bar=True)
        else:
            self.dlg.fileWidget_weatherFolder.blockSignals(True)
            self.dlg.args['nweathers'] = None
            self.dlg.fileWidget_weatherFolder.setFilePath( QgsProject().instance().absolutePath())
            self.dlg.fileWidget_weatherFolder.blockSignals(False)
            self.dlg.radioButton_weatherConstant.setChecked(True)
            self.nlog(text=f'at {self.directory}', title='Bad Weathers Folder!', level=2, to_bar=True)
        self.finished = True

class after_logFile(QgsTask):
    def __init__(self, description, dlg, iface, nlog, log_file, base_layer, plugin_dir):
        super().__init__(description, QgsTask.CanCancel)
        self.exception = None
        self.dlg = dlg
        self.iface = iface
        self.nlog = nlog
        self.log_file = log_file
        self.base_layer = base_layer
        self.style_file = str(Path( plugin_dir, 'img', 'points_layerStyle.qml'))
        self.out_file = self.log_file.absolute().parent / (self.description()+'.gpkg')
        self.setProgress(1)

    def run(self):
        self.nlog(title=self.description(), text='Started', progress=self.progress())
        text = self.log_file.read_text()
        # get [sim,cell] from regex
        simulation, ignitionCell = np.fromiter(re.findall('ignition point for Year [0-9]*, sim ([0-9]+): ([0-9]+)',
                                                          text),
                                               dtype=np.dtype((int,2))).T
        self.setProgress(10)
        # add each point feature
        npts = len(ignitionCell)
        ignitionCell = ignitionCell - 1
        self.nlog(title=self.description(), text='Run Started (showing 5 max)', ignitionCells=ignitionCell[:5], progress=self.progress())
        features = []
        points = []
        c=0
        for s,(x,y) in zip(simulation, matchRasterCellIds2points( ignitionCell, self.base_layer)):
            points += [(x,y)]
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x,y)))
            f.setId(s)
            features += [f]
            self.setProgress(10+c/npts*60)
            c+=1
            if self.isCanceled():
                raise Exception('User canceled')
        self.nlog(title=self.description(), text='Features (showing 5 max)', points=points[:5], progress=self.progress())
        # create & write vector layer
        vector_layer = QgsVectorLayer('point', self.description(), 'memory')
        vector_layer.setCrs( self.base_layer.crs())
        ret, val = vector_layer.dataProvider().addFeatures(features)
        self.setProgress(80)
        if not ret:
            raise Exception(f"Exception creating vector layer in memory or adding features {val}")
        ret, val = writeVectorLayer( vector_layer, self.description(), self.out_file)
        if ret != 0:
            raise Exception(f"Exception writing to geopackage {val}")
        self.setProgress(90)
        self.nlog(title=self.description(), text='Run Ended', progress=self.progress())
        return True 

    def cancel(self):
        super().cancel()
        self.nlog(title=self.description(), text='Canceled signal sent', progress=self.progress())

    def finished(self, result):
        if self.exception:
            self.nlog(title=self.description(), text='Finished', exception=self.exception, level=2, to_bar=True)
        elif result:
            self.iface.addVectorLayer(
                                    f"{self.out_file}|layername={self.description()}",
                                    self.description(),
                                    "ogr"
            ).loadNamedStyle(self.style_file)
            self.setProgress(100)
            self.nlog(title=self.description(), text='Finished ok!', result=result, level=3, progress=self.progress(), to_bar=True)
        else:
            self.nlog(title=self.description(), text='Finished ? no exception & no result!', result=result, level=1, to_bar=True)

class after_betweenness_centrality(QgsTask):
    def __init__(self, description, iface, dlg, args, folder_name, file_name, extent, crs, plugin_dir):
        super().__init__(description, QgsTask.CanCancel)
        self.layer_name = description
        self.exception = None
        self.args = args
        self.directory = Path( self.args['OutFolder'], folder_name)
        self.file_name = file_name
        self.gpkg = Path( self.args['OutFolder'], description+'.gpkg')
        self.dlg = dlg
        self.iface = iface
        self.extent = extent
        self.crs = crs
        self.data = []
        self.centrality_stats = None
        self.plugin_dir = plugin_dir

    def run(self):
        QgsMessageLog.logMessage(self.description()+' Started ',MESSAGE_CATEGORY, Qgis.Info)
        ''' get filelist '''
        file_list = [ f for f in self.directory.glob( self.file_name+'[0-9]*.csv') if f.stat().st_size > 0]
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
        # checks for raise ValueError("Sample larger than population or is negative")
        ksample = np.min(( mdg.number_of_nodes(), int(5*np.sqrt(mdg.number_of_nodes()))))
        centrality = nx.betweenness_centrality(mdg, k=ksample, weight='weight')

        QgsMessageLog.logMessage(self.description()+' building resulting layer & getting statistics',MESSAGE_CATEGORY, Qgis.Info)

        self.setProgress(0.9)
        layer = self.dlg.state['layerComboBox_fuels']
        W,H = layer.width(), layer.height()
        centrality_array = np.zeros((H,W), dtype=np.float32)
        centrality_values = []
        for key,value in centrality.items():
            x,y = id2xy( key-1, W, H)
            centrality_array[y,x]=value
            centrality_values += [value]

        array2rasterFloat32( centrality_array, self.layer_name, self.gpkg, self.extent, self.crs, nodata = 0.0)
        self.centrality_stats = stats.describe(centrality_values, axis=None)
        return True

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage(self.description()+' finished w/result %s'%result, MESSAGE_CATEGORY, Qgis.Info)
            # show layer
            layer = self.iface.addRasterLayer('GPKG:'+str(self.gpkg)+':'+self.layer_name, self.layer_name)
            minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
            maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
            rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)
            # show stats
            stat_col = [self.layer_name,'adim',*self.centrality_stats]
            self.dlg.add_table('Stats')
            self.dlg.add_col_to_stats(self.layer_name, stat_col)
        else:
            if self.exception is None:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
            else:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w exception %s'%self.exception, MESSAGE_CATEGORY, Qgis.Warning)
                raise self.exception
        QgsMessageLog.logMessage(self.description()+' finished end', MESSAGE_CATEGORY, Qgis.Info)

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
            self.pv, self.W, self.H = get_flat_pv( protection_value_layer.publicSource())
        else:
            self.W = fuel_layer.width()
            self.H = fuel_layer.height()
            self.pv = np.ones(self.H*self.W)
        self.crs = fuel_layer.crs()
        self.extent = fuel_layer.extent()
        self.dpv = np.zeros(self.H*self.W)
        self.dpv_stats = None

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
            msgG, root = digraph_from_messages(msgfile)
            treeG = shortest_propagation_tree(msgG, root)
            i2n = [n-1 for n in treeG] # TODO change to generator?
            mdpv = dpv_maskG(treeG, root, self.pv, i2n)
            self.dpv[i2n] += mdpv
            self.setProgress((i+1)/nsim*100)
            if self.isCanceled():
                QgsMessageLog.logMessage(self.description()+' is Canceled', MESSAGE_CATEGORY, Qgis.Warning)
                return False
        self.dpv=self.dpv/nsim
        QgsMessageLog.logMessage(f'{self.description()} creating raster & describing statistics',MESSAGE_CATEGORY, Qgis.Info)
        # TODO nodata == 0?
        array2rasterFloat32( self.dpv.reshape(self.H,self.W), self.layer_name, self.gpkg, self.extent, self.crs)
        self.dpv_stats = stats.describe(self.dpv[self.dpv!=0.0], axis=None)
        return True

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage(self.description()+' finished w/result %s'%result, MESSAGE_CATEGORY, Qgis.Info)
            # show layer
            layer = self.iface.addRasterLayer('GPKG:'+str(self.gpkg)+':'+self.layer_name, self.layer_name)
            minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
            maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
            rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)
            # show stats
            stat_col = [self.layer_name,'pv/fires',*self.dpv_stats]
            self.dlg.add_table('Stats')
            self.dlg.add_col_to_stats(self.layer_name, stat_col)
        else:
            if self.exception is None:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w/o exception', MESSAGE_CATEGORY, Qgis.Warning)
            else:
                QgsMessageLog.logMessage(self.description()+' Finished w/o result w exception %s'%self.exception, MESSAGE_CATEGORY, Qgis.Warning)
                raise self.exception

    def cancel(self):
        QgsMessageLog.logMessage(self.description()+' was canceled', MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()
'''
from datetime import datetime, timedelta
class nextHour:
    def __init__(self):
        self.now = datetime.now()
    def next(self):
        self.now -= timedelta(hours=1)
        return Timestamp(self.now).isoformat(timespec='seconds')
'''
