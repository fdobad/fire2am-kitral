#!/bin/env python3
import re
import numpy as np
import networkx as nx
from pathlib import Path

# read all files from current directory matching Messages??.csv
directory = Path.cwd()
file_name = 'MessagesFile'
file_list = sorted( directory.glob( file_name+'[0-9]*.csv'))
file_string = ' '.join([ f.stem for f in file_list ])

# sort acording to simulation number
sim_num = np.fromiter( re.findall( '([0-9]+)', file_string), dtype=int, count=len(file_list))
asort = np.argsort( sim_num)
sim_num = sim_num[ asort]
file_list = np.array( file_list)[ asort]

# sim stats
num_width = len(str(np.max( sim_num)))
nsim = len(sim_num)

# load all data as numpy arrays
data = []
for afile in file_list:
    #data += [ np.loadtxt( afile, delimiter=',', dtype=[('i',np.int32),('j',np.int32),('t',np.int16),('hros',np.float32)])]
    data +=[ np.loadtxt( afile, delimiter=',', dtype=[('i',np.int32),('j',np.int32),('t',np.int16)], usecols=(0,1,2))]
    #print('read file',afile)

# make a graph with keys=simulations, weights=burnt time
MDG = nx.MultiDiGraph()
for k,dat in enumerate(data):
    func = np.vectorize(lambda x:{'weight':x})
    # ebunch_to_add : container of 4-tuples (u, v, k, d) for an edge with data and key k
    bunch = np.vstack(( dat['i'], dat['j'], [k]*len(dat), func(dat['t']) )).T
    MDG.add_edges_from( bunch)
    print('sim',k,bunch[:3])

# do it
centrality = nx.betweenness_centrality(MDG, weight='weight')
