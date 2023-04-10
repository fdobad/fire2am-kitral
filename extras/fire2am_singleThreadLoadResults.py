
    def checkSameRasterExtentAndResolution(self):
        ''' TODO
        '''
        for i,li in enumerate(lyrs):
            for j,lj in enumerate(lyrs):
                if i<j:
                    self.externalProcess_message(str(lyrs[li][0].extent().asWktCoordinates()))
                    self.externalProcess_message(str(lyrs[li][0].extent().asWktCoordinates()))
                    self.externalProcess_message(str(lyrs[lj][0].extent().asWktCoordinates()))
                    self.externalProcess_message( str(lyrs[li][0].extent().contains( lyrs[lj][0].extent())))
                    if not (lyrs[li][0].extent().contains( lyrs[lj][0].extent()) and \
                            lyrs[lj][0].extent().contains( lyrs[li][0].extent()) ):
                        log('have different extents!',lyrs[li][0].name(), lyrs[lj][0].name(), pre='CRS!', level=3, msgBar=self.dlg.msgBar)
                        self.externalProcess_message(str(lyrs[li][0].extent()))
                        self.externalProcess_message(str(lyrs[lj][0].extent()))
                        return False
        return True


    def loadResults(self):
        ''' read LogFile.txt 
            generate ignition point(s) layer
            if nsim = 1 : isochrones
            else : heatmap
        '''
        ''' print LogFile.txt '''
        logfile = os.path.join(self.args['OutFolder'], 'LogFile.txt')
        with open(logfile, 'rb', buffering=0) as afile:
            text = afile.read().decode()
            self.externalProcess_message( text)


        ''' add output layer GROUP : 
            MOVING LAYERS AND ADDING TO GROUPS IS BUGGY 
            outputGroupName='OUTPUT_'+os.path.basename(os.path.normpath(self.args['OutFolder']))
            root = QgsProject.instance().layerTreeRoot()
            outputGroup = root.addGroup(outputGroupName)
            fireEvGroup = outputGroup.addGroup('Fire Evolution')
            gridGroup = fireEvGroup.addGroup('Grids')
            polyGroup = fireEvGroup.addGroup('Polygons')
             TODO handle removing older/other output groups
            group = root.findGroup(groupName)
            if not group:
                group = root.addGroup(groupName)
        '''
        ''' how many sims were ran '''
        if 'nsims' in self.args.keys():
            nsims = self.args['nsims']
        else:
            nsims = self.default_args['nsims']
        if nsims == 1:
            self.load1sim()
        else:
            self.loadsims()

        self.after_ignitionPoints( text)

        doit = [ 'OutFl' in self.args.keys(),
                 'OutIntensity' in self.args.keys(),
                 'OutRos' in self.args.keys(),
                 'OutCrownConsumption' in self.args.keys()]
        directories = ['FlameLength', 'Intensity', 'RateOfSpread', 'CrownFractionBurn']
        filenames = ['FL', 'Intensity', 'ROSFile', 'Cfb']
        names = ['flame_length', 'Byram_intensity', 'hit_ROS', 'crown_fire_fuel_consumption_ratio']
        if nsims > 1:
            names = ['mean_'+n for n in names ]

        for i,(d,f,n) in filter( lambda x: doit[x[0]] , enumerate(zip(directories, filenames, names))):
            self.after_asciiDir2float32MeanRaster(d, f, n, self.args['OutFolder'], self.geopackage, self.extent, self.crs, nodata=0.0)

        if 'OutCrown' in self.args.keys():
            layerName = 'crown_fire_scar'
            if nsims > 1:
                layerName = 'mean_'+layerName
            self.after_asciiDir2Int16MeanRaster( 'CrownFire', 'Crown', layerName, self.args['OutFolder'], self.geopackage, self.extent, self.crs, nodata=0.0)

    def after_ignitionPoints(self, text):
        data = np.fromiter( re.findall( 'ignition point for Year [0-9]*, sim ([0-9]+): ([0-9]+)', text), dtype=np.dtype((int,2)) )
        simulation, ignitionCell = data.T
        feats = []
        for s,(x,y) in zip(simulation, matchRasterCellIds2points( ignitionCell-1, self.dlg.state['layerComboBox_fuels'])):
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x,y)))
            f.setId(s)
            feats += [ f]
        layerName = 'ignition points'
        vectorLayer = QgsVectorLayer( 'point', layerName, 'memory')
        vectorLayer.setCrs( self.crs)
        ret, val = vectorLayer.dataProvider().addFeatures(feats)
        log( ret, val, layerName, pre = 'vectorLayer data provider added features', level=0)
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = 'GPKG'
        options.layerName = layerName
        if os.path.exists(self.geopackage):
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        else:
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        ret, val = QgsVectorFileWriter.writeAsVectorFormat( vectorLayer , self.geopackage, options)
        log( ret, val, layerName, pre = 'vectorLayer writeAsVectorFormat', level=1)
        vectorLayer = self.iface.addVectorLayer( self.geopackage+'|layername='+layerName, layerName, 'ogr')
        vectorLayer.loadNamedStyle( os.path.join( self.plugin_dir, 'img'+sep+'points_layerStyle.qml'))
        log('finished loading results', pre='Done!', level=4, msgBar=self.dlg.msgBar)

    def after_asciiDir2Int16MeanRaster(self, dirName, fileName, layerName, outfolder, geopackage, extent, crs, nodata = None):
        ''' get filelist '''
        filelist = sorted( Path( outfolder, dirName).glob(fileName+'[0-9]*.asc'))
        filestring = ' '.join([ f.stem for f in filelist ])
        nsim = np.fromiter( re.findall( '([0-9]+)', filestring), dtype=int, count=len(filelist))
        asort = np.argsort( nsim)
        nsim = nsim[ asort]
        filelist = np.array( filelist)[ asort]
        widthNum = len(str(np.max( nsim)))
        ''' get all asc 2 array '''
        self.externalProcess_message('Getting '+layerName+' grids to arrays...')
        data = []
        for afile in filelist:
            data += [ np.loadtxt( afile,  dtype=bool, skiprows=6)]
        data = np.array(data)
        '''global stats'''
        self.externalProcess_message(layerName+' global statistics '+str(stats.describe(data, axis=None)))
        ''' calc mean '''
        self.externalProcess_message('Calculating '+layerName+'...')
        array2rasterFloat32( np.mean( data, axis=0, dtype=np.float32), layerName, self.geopackage, extent, crs, nodata = 0.0)
        ''' show layer '''
        layer = self.iface.addRasterLayer('GPKG:'+str(self.geopackage)+':'+layerName, layerName)
        minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
        maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
        rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)

    def after_asciiDir2float32MeanRaster(self, dirName, fileName, layerName, outfolder, geopackage, extent, crs, nodata = None):
        '''
            dirName = 'FlameLength'
            fileName ='FL'
            layerName ='mean_flame_length'
            outfolder = self.args['OutFolder']
            geopackage= os.path.join(self.args['OutFolder'], 'outputs.gpkg')
            extent = None,
            crs = self.project.crs,
            nodata = 0.0 ):
            ['CrownFire'      ] ['FlameLength'      , 'Intensity'           , 'RateOfSpread']
            ['Crown'          ] ['FL'               , 'Intensity'           , 'ROSFile'     ]
            ['mean_crown_fire'] ['mean_flame_length', 'mean_Byram_intensity', 'mean_hit_ROS']
            import os.path
            from glob import glob
            import numpy as np
            import re
            outfolder = '/home/fdo/dev/Zona21/Instance23-03-14_15-49-22/results'
            filelist = glob( outfolder+sep+'FlameLength'+sep+'FL[0-9]*.asc')
            nsim = np.fromiter( re.findall( 'FlameLength'+sep+'FL([0-9]+).asc', ' '.join(filelist)), dtype=int)
            array2rasterFloat32( np.mean( data, axis=0), 'mean_flame_length', self.geopackage, extent, crs, nodata = 0.0)
        '''
        ''' get filelist '''
        filelist = sorted( Path( outfolder, dirName).glob(fileName+'[0-9]*.asc'))
        filestring = ' '.join([ f.stem for f in filelist ])
        nsim = np.fromiter( re.findall( '([0-9]+)', filestring), dtype=int, count=len(filelist))
        asort = np.argsort( nsim)
        nsim = nsim[ asort]
        filelist = np.array( filelist)[ asort]
        widthNum = len(str(np.max( nsim)))
        ''' get all asc 2 array '''
        self.externalProcess_message('Getting '+layerName+' grids to arrays...')
        data = []
        for afile in filelist:
            data += [ np.loadtxt( afile,  dtype=np.float32, skiprows=6)]
        data = np.array(data)
        '''global stats'''
        self.externalProcess_message(layerName+' global statistics '+str(stats.describe(data, axis=None)))
        ''' calc mean '''
        self.externalProcess_message('Calculating '+layerName+'...')
        array2rasterFloat32( np.mean( data, axis=0, dtype=np.float32), layerName, self.geopackage, extent, crs, nodata = 0.0)
        ''' show layer '''
        layer = self.iface.addRasterLayer('GPKG:'+str(self.geopackage)+':'+layerName, layerName)
        minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
        maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
        rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)

    def loadsims(self):
        extent = self.dlg.state['layerComboBox_fuels'].extent()
        crs = self.project.crs()
        outfolder = self.args['OutFolder']

        ''' get ordered file list '''
        # debug filelist = sorted( Path.cwd().joinpath('Grids').glob('Grids[0-9]*'+sep+'ForestGrid[0-9]*.csv'))
        filelist = sorted( Path( outfolder, 'Grids').glob('Grids[0-9]*'+sep+'ForestGrid[0-9]*.csv'))
        filestring = ' '.join([ f'{f.parts[-2]}_{f.parts[-1]}' for f in filelist ])
        numbers = np.fromiter( re.findall( 'Grids([0-9]+)_ForestGrid([0-9]+).csv', filestring), dtype=np.dtype((int,2)), count=len(filelist))
        # get the last forest_grid for each grid_folder
        doindex = np.unique( numbers[::-1][:,0], return_index=True)[1]
        filelist = np.array(filelist)[::-1][doindex]
        numbers = numbers[::-1][doindex]
        first, second = numbers.T
        width1stNum, width2ndNum = len(str(np.max(first))), len(str(np.max(second)))

        ''' get all csv 2 array '''
        self.externalProcess_message('Getting csv grids to arrays...')
        data = []
        for afile in filelist:
            data += [ np.loadtxt( afile , delimiter=',', dtype=np.int8)]
        data = np.array(data)

        ''' calc burnprob '''
        self.externalProcess_message('Calculating burn probabilities...')
        array2rasterFloat32( np.mean( data, axis=0), 'mean_prob_burn', self.geopackage, extent, crs, nodata = 0.0)
        self.externalProcess_message('Added mean_prob_burn raster')
        array2rasterFloat32(  np.std( data, axis=0),  'std_prob_burn', self.geopackage, extent, crs, nodata = 0.0)
        self.externalProcess_message('Added std_prob_burn raster')
        self.externalProcess_message('Burn probabilities global statistics'+str(stats.describe(data, axis=None)))
        layer = self.iface.addRasterLayer('GPKG:'+str(self.geopackage)+':mean_prob_burn', 'mean_prob_burn')

        minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
        maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
        rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)

        ''' calc fire scars'''
        self.externalProcess_message('Making fire scar rasters...')
        for i,(nsim,ngrid) in enumerate(numbers):
            layerName = 'rFireScar_'+str(nsim).zfill(width1stNum)+'_'+str(ngrid).zfill(width2ndNum)
            array2rasterInt16( data[i], layerName, self.geopackage, extent, crs, nodata = 0)
        self.externalProcess_message('All done!...')
        log('Simulations loaded correctly',pre='All done!', level=4, msgBar=self.dlg.msgBar)

    def load1sim(self):
        extent = self.dlg.state['layerComboBox_fuels'].extent()
        crs = self.project.crs()
        outfolder = self.args['OutFolder']

        ''' get ordered file list '''
        filelist = sorted( Path( outfolder, 'Grids').glob('Grids[0-9]*'+sep+'ForestGrid[0-9]*.csv'))
        filestring = ' '.join([ f'{f.parts[-2]}_{f.parts[-1]}' for f in filelist ])
        numbers = np.fromiter( re.findall( 'Grids([0-9]+)_ForestGrid([0-9]+).csv', filestring), dtype=np.dtype((int,2)))
        first, second = numbers.T
        width1stNum, width2ndNum = len(str(np.max(first))), len(str(np.max(second)))

        ''' get all csv 2 array '''
        self.externalProcess_message('Getting csv grids to arrays...')
        data = []
        for afile in filelist:
            data += [ np.loadtxt( afile , delimiter=',', dtype=np.int8)]
        data = np.array(data)

        ''' calc fire evo raster '''
        self.externalProcess_message('Making fire evolution rasters...')
        for i,(nsim,ngrid) in enumerate(numbers):
            layerName = 'rFireEvolution_'+str(nsim).zfill(width1stNum)+'_'+str(ngrid).zfill(width2ndNum)
            array2rasterInt16( data[i], layerName, self.geopackage, extent, crs, nodata = 0)
            #raster = array2rasterLayerInt16( data[i], layerName, self.geopackage, extent, crs, nodata = 0)
            #poly = raster2poly( raster, layerName, extent, crs)
        ''' raster 2 poly 
            1 get weather for datetime tagging
        '''

        self.externalProcess_message('Making fire evolution polygons...')
        ''' try WheatherHistory folder '''
        weather_folder = self.args['OutFolder'] / 'WeatherHistory'
        weather_hist_file = weather_folder / 'WeatherHistory.csv'
        ok = False
        if weather_folder.is_dir() and weather_hist_file.is_file():
            with open( weather_hist_file, 'r') as afile:
                if weather_file := afile.readline():
                    weather_file = Path(weather_file[:-1]) #erase last char \n
                    if weather_file.is_file():
                        ok = True
        ''' try Wheather.csv'''
        if not ok:
            weather_file = Path( self.args['InFolder'], 'Weather.csv')

        if weather_file.is_file():
            ds = read_csv( weather_file).datetime
            log('Weather.csv.datetime found with length',len(ds), level=1)
            while len(ds) < len(numbers):
                nextdt = Timestamp(ds.iloc[-1]) + timedelta(hours=1)
                nextidx= ds.index[-1] + 1
                ds = concat(( ds, Series( nextdt, index=[nextidx])))
        else:
            log('Weather.csv in input instance folder', pre='Does NOT exist', msgBar=self.dlg.msgBar, level=3)
            plop = self.now - timedelta(years=1)
            ds = Series( [ plop + timedelta(hours=i) for i in range(len(numbers)) ],
                           index=range(len(numbers)) )
        ds = ds.apply( lambda x: Timestamp(x).isoformat(timespec='seconds'))
        log('adjusted Weather.csv.datetime length',len(ds), level=1)
        ''' 2 load raster, make poly, add datetime fields, write '''
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = 'GPKG'
        for i,(nsim,ngrid) in enumerate(numbers):
            layerName = 'FireEvolution_'+str(nsim).zfill(width1stNum)+'_'+str(ngrid).zfill(width2ndNum)
            rasterLayer = QgsRasterLayer('GPKG:'+str(self.geopackage)+':r'+layerName, 'r'+layerName)
            tmp = processing.run('gdal:polygonize',
                       {'BAND' : 1, 
                        'EIGHT_CONNECTEDNESS' : False, 
                        'EXTRA' : '', 
                        'FIELD' : 'DN', 
                        'INPUT' : rasterLayer, 
                        'OUTPUT' : 'TEMPORARY_OUTPUT' })['OUTPUT']
            vectorLayer = QgsVectorLayer( tmp, 'v'+layerName)
            options.layerName = 'v'+layerName
            # add datetime field
            if not vectorLayer.isEditable():
                vectorLayer.startEditing()
            vectorLayer.dataProvider().addAttributes([QgsField('datetime',QVariant.DateTime)])
            vectorLayer.updateFields()
            id_dt = vectorLayer.fields().indexFromName('datetime')
            for feature in vectorLayer.getFeatures():
                attr = { id_dt : ds.iloc[i]}
                vectorLayer.dataProvider().changeAttributeValues({ feature.id() : attr})
            vectorLayer.commitChanges()
            # write
            if self.geopackage.is_file():
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
            else:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
            QgsVectorFileWriter.writeAsVectorFormat( vectorLayer, str(self.geopackage), options)
            del rasterLayer, vectorLayer

        ''' merge '''
        self.externalProcess_message('Merging fire evolution polygons...')
        polys=[]
        for i,(nsim,ngrid) in enumerate(numbers):
            layerName = 'vFireEvolution_'+str(nsim).zfill(width1stNum)+'_'+str(ngrid).zfill(width2ndNum)
            polys += [ str(self.geopackage)+'|layername='+layerName ]
        mergedName = 'merged_Fire_Evolution'
        mergeVectorLayers( polys, str(self.geopackage), mergedName )
        vectorLayer = self.iface.addVectorLayer( str(self.geopackage)+'|layername='+mergedName, mergedName, 'ogr')
        vectorLayer.loadNamedStyle( os.path.join( self.plugin_dir, 'img'+sep+mergedName+'_layerStyle.qml'))
    def oneThreadFireScars(self):
        self.iface.messageBar().pushSuccess(aName+': do it', 'push button pressed')
        self.project = QgsProject().instance()
        #self.now = datetime(23,3,30,0,22,13 )
        self.now = datetime(23,3,30,12,30,9)
        self.makeArgs()
        #self.args['InFolder'] = Path('/home/fdo/dev/C2FSB/data/Vilopriu_2013/Instance23-03-30_00-22-13/')
        self.args['InFolder'] = Path('/home/fdo/dev/C2FSB/data/Vilopriu_2013/Instance1simEmulated3/')
        self.args['InFolder'] = Path('/home/fdo/dev/C2FSB/data/Vilopriu_2013/Instance23-04-03_18-00-02/')
        self.args['OutFolder'] = self.args['InFolder'] / 'results'
        self.out_gpkg = self.args['OutFolder'] / 'Fire_Scar.gpkg'
        self.stats_gpkg = self.args['OutFolder'] / 'statistics.gpkg'
        self.extent = self.dlg.state['layerComboBox_fuels'].extent()
        self.crs = self.dlg.state['layerComboBox_fuels'].crs()
        #self.after()
        # t
        '''
        descr='after_ForestGrid'
        self.task[descr] = after_ForestGrid(descr, self.iface, self.dlg, self.args, 'Fire_Scar', self.out_gpkg, self.stats_gpkg, self.extent, self.crs)
        self.taskManager.addTask( self.task[descr])
        '''

        '''
        cd ~/dev/C2FSB/data/Vilopriu_2013/Instance23-03-31_19-24-13/results
        ipython3
        %autoindent
        from pathlib import Path
        from os import sep
        from re import findall, match
        import re
        import numpy as np
        filelist = list( (Path.cwd()/'Grids').glob('Grids[0-9]*'+sep+'ForestGrid[0-9]*.csv'))
        '''

        # cant trust folder and files are ordered
        filelist = list(Path(self.args['OutFolder'],'Grids').glob('Grids[0-9]*'+sep+'ForestGrid[0-9]*.csv'))
        filestring = ' '.join([ f'{f.parts[-2]}_{f.parts[-1]}' for f in filelist ])
        numbers = np.fromiter( re.findall( 'Grids([0-9]+)_ForestGrid([0-9]+).csv', filestring), dtype=[('x',int),('y',int)], count=len(filelist))
        # sorts ascending
        asort = np.argsort(numbers, order=('x','y'))
        # descending + unique gives last grid index
        numbers = np.array([ [n[0],n[1]] for n in numbers ])[asort][::-1]
        filelist = np.array(filelist)[asort][::-1]
        # get
        uniques, indexes, counts = np.unique( numbers[:,0], return_index=True, return_counts=True)
        sim_num = uniques[::-1]
        final_grid_idx = indexes[::-1]
        sim_totals = counts[::-1]

        ''' last of every sim'''
        #numbers[final_grid_idx]
        #filelist[final_grid_idx]

        total = len(filelist)
        ''' sim splited '''
        sim_idx = np.split( range(total),final_grid_idx)[1:]
        sim_nu = np.split( numbers,final_grid_idx)[1:]
        sim_fi = np.split( filelist,final_grid_idx)[1:]
        for s,tg,nu,fi,ii in zip(sim_num,sim_totals,sim_nu,sim_fi,sim_idx):
            assert np.all(fi == filelist[ii])
            assert np.all(nu == numbers[ii])
        #    print('sim',s,'total grids',tg)
        #    #print('\tnu',nu,'\tfi',fi)
        #    print('\tnu',nu.T,'\tfi',[ (f.parts[-2],f.stem) for f in fi])
        ''' get all data'''
        data = []
        data_isZeros = []
        for afile in filelist:
            data += [ np.loadtxt( afile , delimiter=',', dtype=np.int8)]
            if np.any( data[-1] != 0 ):
                data_isZeros += [ False]
            else:
                data_isZeros += [ True ]
        data = np.array(data)
        sim_zeros = np.split( data_isZeros,final_grid_idx)[1:]

        ''' exit if nothing burned '''
        if all( data_isZeros):
            log('All %s forest grids are zero'%len(total), pre='Nothing Burned!', level=3, msgBar=self.dlg.msgBar)
            return
        if any( data_isZeros):
            log('For %s'%[ f.parts[-2]+'/'+f.stem for f in filelist[ data_isZeros]], pre='Nothing Burned!', level=2, msgBar=self.dlg.msgBar)

        ''' get burn prob '''
        if len(sim_num) > 1:
            meanData = np.mean( data[final_grid_idx], axis=0, dtype=np.float32)
            name_prefix = 'mean_'
        else:
            meanData = data[final_grid_idx]
            name_prefix = ''
        layerName = name_prefix+'FireScar'
        array2rasterFloat32( meanData, layerName, self.stats_gpkg, self.extent, self.crs, nodata = 0.0)
        layer = self.iface.addRasterLayer('GPKG:'+str(self.stats_gpkg)+':'+layerName, layerName)
        minValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Min).minimumValue
        maxValue = layer.dataProvider().bandStatistics(1, QgsRasterBandStats.Max).maximumValue
        rasterRenderInterpolatedPseudoColor(layer, minValue, maxValue)
        st = stats.describe( meanData, axis=None)
        df = DataFrame( (layerName,*st), index=('Name',*st._fields), columns=[layerName])
        bf = self.dlg.statdf
        df = concat([bf,df], axis=1)
        self.dlg.statdf = df
        self.dlg.tableView_1.setModel(self.dlg.PandasModel(df))

        ''' for each sim calc isochrones
        array 2 raster 
        data[i] -> raster[i]
        load weather 
        	!e : create
        	file : enlarge ?
        	history : select : enlarge?
        raster 2 poly
        polys add attr datetime
        merge poly
        show mergedPoly
        '''
        log('saving all rasters',level=0)
        first, second = numbers.T
        width1stNum, width2ndNum = len(str(np.max(first))), len(str(np.max(second)))
        nh = nextHour()
        rout = Path( self.out_gpkg.parent , 'r'+self.out_gpkg.name )
        vout = Path( self.out_gpkg.parent , 'v'+self.out_gpkg.name )
        for s,t,z,nu,fi,ii in zip(sim_num,sim_totals,sim_zeros,sim_nu,sim_fi,sim_idx):
            tg = t - np.sum(z)
            #print('sim', s, 'total good', tg)
            log('sim', s, 'total good', tg, level=0)
            if tg > 0:
                for i,(nsim,ngrid) in zip(ii,nu):
                    #print(i,(nsim,ngrid))
                    if not data_isZeros[i]:
                        layerName = 'FireScar_'+str(nsim).zfill(width1stNum)+'_'+str(ngrid).zfill(width2ndNum)
                        log('arr2vec',layerName, level=0)

                        array2rasterInt16( data[i], layerName, rout, self.extent, self.crs, nodata = 0)
                        raster2vector_wTimestamp( layerName, rout, vout, self.extent, self.crs, nh)
                    #else:
                    #    print('data is zero')
            if tg > 1:
                polys=[ str(vout)+'|layername=FireScar_'+str(nsim).zfill(width1stNum)+'_'+str(ngrid).zfill(width2ndNum) \
                        for i,(nsim,ngrid) in zip(ii,nu) if not data_isZeros[i]]
                log('merging ',s,polys, level=0)
                mergedName = 'Fire_Evolution_%s'%s
                # TBD tmp is VectorMapLayer?
                tmp = mergeVectorLayers( polys, str(self.stats_gpkg), mergedName )
                log('tmp',tmp,level=1)
                vectorLayer = self.iface.addVectorLayer( str(self.stats_gpkg)+'|layername='+mergedName, mergedName, 'ogr')
                vectorLayer.loadNamedStyle( os.path.join( self.plugin_dir, 'img'+sep+'Fire_Evolution_layerStyle.qml'))

def afterTask_logFile(task, logText, layerName, baseLayer, out_gpkg, stats_gpkg):
    QgsMessageLog.logMessage('task {} Started processing output'.format(task.description()), aName, Qgis.Info)
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
    QgsMessageLog.logMessage('task {}\tadded feature points'.format(task.description()), aName, Qgis.Info)
    ''' create vector layer '''
    vectorLayer = QgsVectorLayer( 'point', layerName, 'memory')
    vectorLayer.setCrs( baseLayer.crs())
    ret, val = vectorLayer.dataProvider().addFeatures(feats)
    if not ret:
        raise Exception('creating vector layer in memory, added features'+str(val))
    QgsMessageLog.logMessage('task {}\tcreated vector layer in memory, added features'.format(task.description()), aName, Qgis.Info)
    task.setProgress(90)
    '''
    # TODO write to every gpkg
    ret, val = writeVectorLayer( vectorLayer, layerName, out_gpkg)
    if ret != 0:
        raise Exception('written to geopackage'+str(val))
    '''
    ret, val = writeVectorLayer( vectorLayer, layerName, stats_gpkg)
    if ret != 0:
        raise Exception('written to geopackage'+str(val))
    QgsMessageLog.logMessage('task {}\twriting to geopackage'.format(task.description()), aName, Qgis.Info)
    task.setProgress(100)
    QgsMessageLog.logMessage('task {} Ended'.format(task.description()), aName, Qgis.Info)

