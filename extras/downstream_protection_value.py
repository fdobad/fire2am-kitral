#!/bin/env python3
'''
Calculate downstream protection value from Messages/MessagesFile<int>.csv files
Each file has 4 columns: from cellId, to cellId, period when burns & hit ROS

arbol= nx.subgraph(H, {i} | nx.descendants(H, i))

https://networkx.org/documentation/networkx-1.8/reference/algorithms.shortest_paths.html
https://github.com/fire2a/C2FK/blob/main/Cell2Fire/Heuristics.py

(c) fire shortest traveling times

RESULTS
1. is faster to dijkstra than minimun spanning

    In [50]: %timeit shortest_propagation_tree(G,root)
    1.53 ms ± 5.47 µs per loop (mean ± std. dev. of 7 runs, 1000 loops each)
    
    In [51]: %timeit minimum_spanning_arborescence(G)
    16.4 ms ± 61 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)

2. is faster numpy+add_edges than nx.from_csv

    In [63]: %timeit custom4(afile)
    2.3 ms ± 32 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)
    
    In [64]: %timeit canon4(afile)
    3.35 ms ± 20 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)

2.1 even faster is you discard a column!!
    In [65]: %timeit custom3(afile)
    1.84 ms ± 15.4 µs per loop (mean ± std. dev. of 7 runs, 1000 loops each)



'''
import sys
from pathlib import Path
import re
import networkx as nx
import numpy as np
from matplotlib import pyplot as plt



def downstream_protection_value():
    ''' load one diGraph count succesors '''
    afile = Path.cwd() / 'MessagesFile01.csv'
    G = nx.DiGraph() # pylint: disable=invalid-name
    # 1
    data_i, data_j = np.loadtxt( afile, delimiter=',', dtype=np.int32, usecols=(0,1), max_rows=100, unpack=True)
    bunch = np.vstack(( data_i, data_j, [{'weight':0}]*len(data_i))).T
    G.add_edges_from(bunch)
    # 2
    data = np.loadtxt( afile, delimiter=',', dtype=[('i',np.int32),('j',np.int32),('t',np.int16)], usecols=(0,1,2))
    G.add_edges_from(data)


    G.nodes[root]['dpv'] = len(nx.descendants(G,root))
    for s in G.successors(root):
        print(s, np.sum(len(nx.descendants(G,s))))
        G.nodes[s]['dpv'] = np.sum(len(nx.descendants(G,s)))

def downtream_protection_value():
    afile = Path.cwd() / 'MessagesFile01.csv'
    G = nx.DiGraph() # pylint: disable=invalid-name
    data = np.loadtxt( afile, delimiter=',', dtype=[('i',np.int32),('j',np.int32)], usecols=(0,1))
    G.add_edges_from(data)
    for i in G.nodes:
        G.nodes[i]['dpv'] = 0
        G.nodes[i]['var'] = 1

    for i in G.nodes:
        arbol= nx.subgraph(G, {i} | nx.descendants(G, i))
        print('an', arbol.nodes)
        print('de', nx.descendants(G, i).add(i))
        G.nodes[i]['dpv'] += np.sum([G.nodes[j]['var'] for j in arbol.nodes])
        print(i,{i} | nx.descendants(G, i),G.nodes[i]['dpv'])
    return G

def single_source_dijkstra_path(file_list):
    afile = file_list[0]

def canon3(afile):
    # NO IMPLEMENTADO
    G = nx.read_edgelist(path=afile, create_using=nx.DiGraph(), nodetype=np.int32, data=[('time', np.int16)], delimiter=',')
    return G
def canon4(afile):
    G = nx.read_edgelist(path=afile, create_using=nx.DiGraph(), nodetype=np.int32, data=[('time', np.int16), ('ros', np.float32)], delimiter=',')
    return G

def custom3(afile):
    data = np.loadtxt( afile, delimiter=',', dtype=[('i',np.int32),('j',np.int32),('time',np.int16)], usecols=(0,1,2))
    root = data[0][0]
    G = nx.DiGraph()
    G.add_weighted_edges_from(data)
    return G, root

func = np.vectorize(lambda x,y:{'time':x,'ros':y})
def custom4(afile):
    data = np.loadtxt( afile, delimiter=',', dtype=[('i',np.int32),('j',np.int32),('time',np.int16),('ros',np.float32)])
    root = data[0][0]
    G = nx.DiGraph()
    bunch = np.vstack(( data['i'], data['j'], func(data['time'], data['ros']))).T
    G.add_edges_from(bunch)
    return G.add_edges_from(bunch), root

def shortest_propagation_tree(G, root):
    ''' construct a tree with the all shortest path from root 
        TODO try accumulating already added edges
        TODO for i,node in enumerate(shopat[:-1]):
    '''
    # { node : [root,...,node], ... }
    shortest_paths = nx.single_source_dijkstra_path(G, root, weight='time')
    del shortest_paths[root]
    T = nx.DiGraph()
    for node, shopat in shortest_paths.items():
        len_shopat = len(shopat)
        for i,node in enumerate(shopat):
            if i+1<len_shopat:
                T.add_edge(node,shopat[i+1])
    return T

def minimum_spanning_arborescence(G):
    return nx.minimum_spanning_arborescence(G, attr='time')


def recursiveUp(G):
    ''' count up WTF!!!
        leafs = [x for x in T.nodes if T.out_degree(x)==0]
    '''
    for i in G.nodes:
        G.nodes[i]['dv']=1
        #G.nodes[i]['dv']=0
    #for leaf in (x for x in G.nodes if G.out_degree(x)==0):
    #    G.nodes[leaf]['dv']=1
    def count_up( G, j):
        for i in G.predecessors(j):
            #G.nodes[i]['dv']+=G.nodes[j]['dv']
            G.nodes[i]['dv']+=1
            print(i,j,G.nodes[i]['dv'])
            count_up(G,i)
    for leaf in (x for x in G.nodes if G.out_degree(x)==0):
        count_up(G,leaf)

def recuDown(G,root):
    assert nx.is_tree(G), 'not tree'
    for i in G.nodes:
        G.nodes[i]['dv']=1
    def count_down( G, i):
        for j in G.successors(i):
            G.nodes[i]['dv']+=count_down(G,j)
        return G.nodes[i]['dv'] 
    count_down(G,root)

def not():
    reviewed = set()
    for t in times[::-1]:
        for j in data['j'][ data['t'] == t]:
            if j not in reviewed:
                reviewed.add(j)
                count_up(G,j)
            #else:
            #    print(j)
    return G

def read_files(apath):
    ''' read all MessagesFile<int>.csv files from Messages directory
        return ordered pathlib filelist & simulation_number lists
    ''' 
    directory = Path(apath,'Messages')
    file_name = 'MessagesFile'
    file_list = list( directory.glob( file_name+'[0-9]*.csv'))
    file_string = ' '.join([ f.stem for f in file_list ])
    # sort
    sim_num = np.fromiter( re.findall( '([0-9]+)', file_string), dtype=int, count=len(file_list))
    asort = np.argsort( sim_num)
    sim_num = sim_num[ asort]
    file_list = np.array( file_list)[ asort]
    return file_list

def plot(G, pos=None):
    ''' matplotlib'''
    if not pos:
        pos = { node : [*id2xy(node)] for node in G.nodes}
    plt.figure()
    nx.draw_networkx(G, pos)#_edges(H, pos, alpha=0.3, edge_color="k")
    plt.axis("off")
    plt.show()

def id2xy( idx, w=40, h=40):
    ''' idx: index, w: width, h:height '''
    idx-=1
    return idx%w, idx//w 

if __name__ == "__main__":
    if len(sys.argv)>1:
        results_dir = sys.argv[1]
    else:
        file_list = read_files(Path.cwd())
        afile = file_list[0]
        G, root = custom3(afile )
        T = shortest_propagation_tree(G, root)
        recuDown(T,root)
        print('dpv is',T.nodes[root])

