#!/bin/env python3
"""
    Data check for cell2fire simulator & fire2am qgis plugin
"""
from pathlib import Path
import sys
import re
from logging import error, warning
from osgeo import gdal
from pandas import read_csv
from pandas.api.types import is_numeric_dtype
import numpy as np

# header = 'Scenario,datetime,WS,WD,FireScenario'
# header.split(',')
WEATHER_FILE_HEADER = ['Scenario', 'datetime', 'WS', 'WD', 'FireScenario']

def weather_file(afile : str) -> bool:
    """ check   column header match WEATHER_FILE_HEADER
                WS and WD are numeric data types
                by opening as pandas dataframe
    """
    #header = list(map( str.strip, read_csv( afile, nrows=1).columns))
    if np.any( read_csv( afile, nrows=1).columns != WEATHER_FILE_HEADER):
        warning(f'weather file {afile} header is invalid')
        return False
    df_dtypes = read_csv( afile).dtypes
    if not (is_numeric_dtype(df_dtypes.WS) and is_numeric_dtype(df_dtypes.WD)):
        warning(f'weather file {afile} column is not numeric')
        return False
    return True

def weather_file_quick(afile : str) -> bool:
    """ check   column header : trimmed names match WEATHER_FILE_HEADER
                data types : only checking first data row types
    """
    io_text = open( afile, encoding='UTF-8')
    header = io_text.readline().replace('\n','').split(',')
    #header.replace(' ','').replace('\t','').split(',')
    if np.any( header != WEATHER_FILE_HEADER):
        warning(f'weather file {afile} header is invalid')
        return False
    first_row = io_text.readline()
    if not all(np.char.isnumeric(first_row.split(',')[-3:-1])):
        warning(f'weather file {afile} column is not numeric')
        return False
    return True

def weather_folder( apath : Path) -> bool:
    """ recursive glob Weather numbers """
    if not apath.is_dir():
        return False
    if filelist:= list(apath.glob('Weather[0-9]*.csv')):
        numbers = np.fromiter( re.findall( 'Weather([0-9]+)',
                        ''.join([ f.stem for f in filelist])),
                        dtype=np.int32, count=len(filelist))
        asort = np.argsort(numbers)
        filelist = np.array(filelist)[asort]
        numbers = numbers[asort]
        for i,afile in enumerate(filelist):
            if i+1 != numbers[i]:
                warning(f'weather file {afile} not sequentially numerated {i+1} in {apath}')
                return False
            if not weather_file(str(afile)): #, quick=True
            #if not weather_file_quick(str(afile)): #, quick=True
                return False
        return True
    return False

def get_raster_metadata( afile : Path):
    """ extract info from raster using gdal 
    """
    dataset = gdal.Open(afile, gdal.GA_ReadOnly)
    band = dataset.GetRasterBand(1)
    band_type = gdal.GetDataTypeName(band.DataType)
    band_min = band.GetMinimum()
    band_max = band.GetMaximum()
    if not band_min or not band_max:
        (band_min,band_max) = band.ComputeRasterMinMax(True)
    metadata = {'driver':dataset.GetDriver().ShortName,
            'name':Path(afile).name,
            'x': dataset.RasterXSize,
            'y': dataset.RasterYSize,
            'min':band_min,
            'max':band_max,
            'type':band_type,
            'rc': dataset.RasterCount}
    dataset = None
    return metadata

def check_raster_congruence( raster_list : [str]) -> bool:
    metadata = list(map( get_raster_metadata, raster_list))
    for meta in metadata:
        if meta['driver']!='AAIGrid':
            warning(f"raster {meta['name']} is not of AAIGrid type")
            return False
        if meta['rc']!=1:
            warning(f"raster {meta['name']} has more than 1 band")
            return False
    metai = metadata[0]
    for metaj in metadata[1:]:
        if metai['x'] != metaj['x']:
            warning(f"different rasters x size {metai['name']} {metai['x']} != {metaj['x']} {metaj['name']}")
            return False
        if metai['y'] != metaj['y']:
            warning(f"different rasters y size {metai['name']} {metai['y']} != {metaj['y']} {metaj['name']}")
            return False
    return True

def raster_in01( afile):
    meta = get_raster_metadata( afile)
    if not 'Float' in meta['type']:
        warning(f"raster {meta['name']} is not float")
        return False
    if not meta['min']>=0:
        warning(f"raster {meta['name']} minimun is below zero")
        return False
    if not meta['max']<=1:
        warning(f"raster {meta['name']} maximum is above one")
        return False
    return True

if __name__ == "__main__":
    if arg:=sys.argv[1:]:
        if len(arg)==1:
            arg=arg[0]
            if arg[-4:]=='.csv':
                #In [2]: %run /home/fdo/dev/fire2am/fire_check.py /home/fdo/dev/C2FSB/data/Zona_60/Weathers.csv
                print(arg,'weather file check',weather_file(arg))
            if arg[-4:]=='.asc':
                print(arg,'probability map check',raster_in01(arg))
            else:
                #In [5]: %run /home/fdo/dev/fire2am/fire_check.py /home/fdo/dev/C2FSB/data/Zona_60/Weathers
                print(arg,'weather folder check',weather_folder(Path(arg)))
        else:
            #In [25]: %run /home/fdo/dev/fire2am/fire_check.py fuels.asc elevation.asc py.asc ../Zona_60/fuels.asc
            print(arg,'raster congruence check',check_raster_congruence(arg))
    else:
        print('Hello World!')

