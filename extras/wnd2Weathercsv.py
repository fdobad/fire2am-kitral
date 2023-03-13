import numpy as np
from datetime import datetime
from sys import argv
import sys
import os.path

def main(afile):
    if not os.path.isfile(afile):
        print('not a file')
        return 1
     
    year = datetime.fromtimestamp( os.path.getmtime( afile)).year

    df = np.loadtxt( afile, skiprows=1, 
            dtype=[('m',int),('d',int),('hm',int),('ws',int),('wd',int),('x',int)])
    
    def getNonEmptyRow( df, i=0):
        if df[0]['ws']==df[0]['wd']==df[0]['x']==0:
            return getNonEmptyRow( df[1:], i+1)
        return i
    last = len(df) - getNonEmptyRow( df[::-1])
    
    outfile = afile.replace('.','_')+'.csv'
    with open( outfile, 'w') as f:
        f.write('Instance,datetime,WD,WS,FireScenario\n')
        for row in df[:last]:
            dt = datetime( year=year, month=row['m'], day=row['d'], hour=row['hm']//100, minute=row['hm']%100).isoformat(sep=' ', timespec='minutes')
            f.write('i,{},{},{},2\n'.format(dt,row['wd'],row['ws']))

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))

