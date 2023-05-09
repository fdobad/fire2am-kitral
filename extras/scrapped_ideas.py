
def sample():
    ''' fixed simple graph for counting children '''
    G = nx.full_rary_tree(3, 1+3+8, create_using=nx.DiGraph())
    
    # init empty set
    reviewed = set()

    # new node
    # 
    G.nodes[0]['dv']=0
    reviewed.add(0)

    for r in reviewed:
        G.nodes[r]['dv'] += len(G[r])
    for s in G[0]:
        G.nodes[s]['dv']=0
        reviewed.add(s)
    for r in reviewed:
        G.nodes[r]['dv'] += len(G[r])

    G.nodes[root]['dpv'] = len(nx.descendants(G,root))
    for s in G.successors(root):
        print(s, np.sum(len(nx.descendants(G,s))))
        G.nodes[s]['dpv'] = np.sum(len(nx.descendants(G,s)))
def tmp():
    # sim stats
    num_width = len(str(np.max( sim_num)))
    nsim = len(sim_num)
    
    # load all data as numpy arrays
    data = []
    for afile in file_list:
        #data += [ np.loadtxt( afile, delimiter=',', dtype=[('i',np.int32),('j',np.int32),('t',np.int16),('hros',np.float32)])]
        data +=[ np.loadtxt( afile, delimiter=',', dtype=[('i',np.int32),('j',np.int32)], usecols=(0,1))]
        #print('read file',afile)
    
    # make a graph with keys=simulations, weights=burnt time
    MDG = nx.MultiDiGraph()
    func = np.vectorize(lambda x:{'weight':x})
    for k,dat in enumerate(data):
        # ebunch_to_add : container of 4-tuples (u, v, k, d) for an edge with data and key k
        bunch = np.vstack(( dat['i'], dat['j'], [k]*len(dat), func(dat['t']) )).T
        MDG.add_edges_from( bunch)
        print('sim',k,bunch[:3])
