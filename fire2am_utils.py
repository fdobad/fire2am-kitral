#!/usr/bin/env python3
#REPLENV: /home/fdo/pyenv/qgis
from pandas import DataFrame, Series
import numpy as np
import os

'''CONSTANTS'''
aName = 'fire2am'


''' 
    matplotlib into qt
      fig,canvas from matplotlib.backends.backend_qtagg
      -> into QGraphicsProxyWidget
      -> into QGraphicsScene (multi figure manager)
      -> rendered by a QGraphicsView (ui component)

    https://matplotlib.org/stable/api/figure_api.html
    class matplotlib.figure.Figure(figsize=None, dpi=None, *, facecolor=None, edgecolor=None, linewidth=0.0, frameon=None, subplotpars=None, tight_layout=None, constrained_layout=None, layout=None, **kwargs)
    ax          = canvas.figure.add_axes
    add_subplot
    subplots
    clf
'''
from qgis.PyQt.QtWidgets import QGraphicsScene, QGraphicsProxyWidget, QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
class MatplotlibModel(QGraphicsScene):
    def __init__(self, parent=None):
        super(MatplotlibModel, self).__init__(parent)
        self.static_canvas = None
        self.static_ax = None

    def newStaticFigCanvas(self, w=4, h=6):
        self.static_canvas = FigureCanvas(Figure(figsize=(w, h)))
        self.static_ax = self.static_canvas.figure.subplots()
        return self.static_canvas, self.static_ax

    def setGraphicsView(self, gv):
        #scene = QGraphicsScene() <-- scene is self!!
        proxy_widget = QGraphicsProxyWidget()
        widget = QWidget()
        layout = QVBoxLayout()
        #
        layout.addWidget(NavigationToolbar(self.static_canvas))
        layout.addWidget(self.static_canvas)
        #
        widget.setLayout(layout)
        proxy_widget.setWidget(widget)
        # insert widget into scene into view:
        self.addItem(proxy_widget)
        gv.setScene(self)

from qgis.PyQt.QtWidgets import QGraphicsScene, QGraphicsView, QWidget, QVBoxLayout, QGraphicsProxyWidget
from matplotlib.backends.backend_qtagg import FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
class MatplotlibFigures(QGraphicsScene):
    def __init__(self, parent = None, graphicsView = None):
        super(MatplotlibFigures, self).__init__(parent)
        self.canvass = []
        self.proxy_widgets = []
        self.resize = []
        self.cv = -1
        self.graphicsView = graphicsView
        self.oldResizeEvent = self.graphicsView.resizeEvent
        self.graphicsView.resizeEvent = self.resizeEvent
        self.graphicsView.setScene(self)

    def resizeEvent(self, QResizeEvent):
        if self.cv == -1:
            return
        if not self.resize[self.cv]:
            return
        oldSize = QResizeEvent.oldSize()
        ow = oldSize.width()
        oh = oldSize.height()
        size = QResizeEvent.size()
        w = size.width()
        h = size.height()
        ds = abs(w-ow)+abs(h-oh)
        if ds < 4:
            return
        if ds < 8:
            self.fit2gv(self.cv)
            return
        self.proxy_widgets[self.cv].resize(w-5,h-5)
        self.oldResizeEvent( QResizeEvent)

    def new(self, w = None, h = None, **kwargs):
        if w and h:
            canvas = FigureCanvas( Figure( figsize=(w, h), **kwargs))
            self.resize += [ False ]
        else:
            canvas = FigureCanvas( Figure( **kwargs))
            self.resize += [ True ]
        proxy_widget = QGraphicsProxyWidget()
        widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget( NavigationToolbar(canvas))
        layout.addWidget( canvas)
        widget.setLayout( layout)
        proxy_widget.setWidget(widget)
        proxy_widget.setVisible(False)
        self.addItem(proxy_widget)
        self.canvass += [ canvas ]
        self.proxy_widgets += [ proxy_widget]
        return canvas

    def resize2gv(self, idx):
        w = self.graphicsView.size().width() - 5
        h = self.graphicsView.size().height() - 5
        self.proxy_widgets[idx].resize(w,h)

    def fit2gv(self, idx):
        self.graphicsView.fitInView( self.proxy_widgets[idx])

    def show(self, idx):
        if self.cv == idx:
            return
        if self.resize[idx]:
            self.resize2gv(idx)
        self.proxy_widgets[idx].setVisible(True)
        self.proxy_widgets[self.cv].setVisible(False)
        self.cv = idx


from qgis.PyQt.QtCore import Qt, QVariant, QAbstractTableModel
''' show pandas dataframe in qt '''
class PandasModel(QAbstractTableModel):
    def __init__(self, data, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole:
                return QVariant(str(self._data.iloc[index.row(), index.column()]))
        return None

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._data.columns[col]
        return None

''' Argparse '''
def get_params(Parser):
    ''' get an argparse object that has groups 
        args, parser, groups = get_params(Parser)

        from argparse import ArgumentParser
        parser = ArgumentParser()

    '''
    parser, groups = get_grouped_parser(Parser())
    args = { dest:parser[dest]['default'] for dest in parser.keys() }
    return args, parser, groups

def get_grouped_parser(parser):
    ''' groupObject = parser.add_argument_group(title='groupTitle to show')
        groupObject.add_argument("--le-argument", ...
        see usr/lib/python39/argparse.py for details
        groups are stored on _action_groups, lines: 1352, 1448
    '''
    pag = parser.__dict__['_action_groups']
    '''
        p[0]['title'] : 'positional' 
        p[1]['title'] : 'optional arguments'
        p[2:]['title'] : groups
    '''
    q = {}
    for p in pag[2:]:
        r = p.__dict__
        q[r['title']] = r['_group_actions']
    groups = set(q.keys())
    # normalize 
    args = {}
    for k,v in q.items():
        for w in v:
            x = w.__dict__
            args[x['dest']] = x  
            args[x['dest']].pop( 'container')
            args[x['dest']].update({ 'group' : k})

    return args, groups

import logging
#logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)-8s %(message)s' ,datefmt='%Y-%m-%d %H:%M:%S')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s' ,datefmt='%Y-%m-%d %H:%M:%S')
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
from qgis.core import Qgis, QgsMessageLog
def log(*args, pre='', level=1, plugin=aName, msgBar=None):
    '''
    log(*args, level=1)

    logMessage(message: str, tag: str = '', level: Qgis.MessageLevel = Qgis.Warning, notifyUser: bool = True)
    
    import logging
    logging.warning('%s before you %s', 'Look', 'leap!')

    log = lambda m: QgsMessageLog.logMessage(m,'My Plugin') 
    log('My message')
          Qgis.[Info,   Warning, Critical,          Success]
    log.[debug, info,   warning, error and critical]
             0, 1   ,   2,          3               ,   4
    '''
    plugin = str(plugin)+' ' if plugin!='' else ''
    pre = str(pre)+' ' if pre!='' else ''
    
    if isinstance(args,tuple) and args!='':
        tmp = []
        for a in args:
            tmp += [str(a)]
        args = ' '.join(tmp)

    if level == 0:
        logging.debug( plugin+pre+args)
        QgsMessageLog.logMessage( 'debug '+pre+args, plugin, level=Qgis.Info) 
        if msgBar:
            msgBar.pushMessage( pre+'debug', args, level=Qgis.Info, duration=1)
    elif level == 1:
        QgsMessageLog.logMessage( pre+args, plugin, level=Qgis.Info) 
        logging.info( plugin+pre+args)
        if msgBar:
            msgBar.pushMessage( pre, args, level=Qgis.Info)
    elif level == 2:
        QgsMessageLog.logMessage( pre+args, plugin, level=Qgis.Warning) 
        logging.warning( plugin+pre+args)
        if msgBar:
            msgBar.pushMessage( pre, args, level=Qgis.Warning)
    elif level == 3:
        QgsMessageLog.logMessage( pre+args, plugin, level=Qgis.Critical) 
        logging.critical( plugin+pre+args)
        if msgBar:
            msgBar.pushMessage( pre, args, level=Qgis.Critical)
    elif level == 4:
        QgsMessageLog.logMessage( pre+args, plugin, level=Qgis.Success) 
        logging.info( plugin+'success '+pre+args)
        if msgBar:
            msgBar.pushMessage( pre, args, level=Qgis.Success)

def randomNames(n=8, l=4):
    ''' n words, l word length
    for i in range(20):
        for j in range(1,i):
           print(i,j,randomNames(i,j))
    '''
    m = n*l
    lis = map( chr, np.random.randint(97,123,size=m))
    joi = ''.join(lis)
    return [ joi[i:i+l] for i in range(0,m,l) ]

def randomDataFrame(rows=8, cols=4, dtype=float):
    if dtype == float:
        data = np.round( np.random.random(size=(rows,cols)) , 2)
    elif dtype == int:
        data =           np.random.randint(99, size=(rows,cols))
    else:
        raise NotImplementedError
    df = DataFrame( data, columns=randomNames(cols,3))
    df.insert( 0, randomNames(1,6)[0], Series(randomNames(rows,4)))
    return df

def safe_cast(val, to_type, default=None):
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default

def safe_cast_ok(val, to_type, default=None):
    try:
        return to_type(val), True
    except (ValueError, TypeError):
        return default, False

def check(obj,key):
    return hasattr(obj, key) and callable(getattr(obj, key))

def rgb2hex_color(r,g,b) -> str:
    ''' int 0-255 rgb to hex '''
    return '#%02x%02x%02x'%(r,g,b)
    #return '%02x%02x%02x'%(int(r*255), int(g*255), int(b*255))

def fuel_lookuptable_colorconvert(afile = 'spain_lookup_table.csv'):
    df = read_csv(afile, usecols=['grid_value','r','g','b','h','s','l'], dtype=np.int16)
    from colorsys import rgb_to_hls
    from colorsys import hls_to_rgb
    for t in df.itertuples():
        print((t.r,t.g,t.b),hls_to_rgb(t.h,t.l,t.s),rgb_to_hls(t.r,t.g,t.b),(t.h,t.l,t.s))
        assert np.all( rgb_to_hls(t.r,t.g,t.b)==(t.h,t.l,t.s)) and np.all( (t.r,t.g,t.b)==hls_to_rgb(t.h,t.l,t.s))


if __name__ == "__main__":
    '''
    from qgis.core import QgsApplication, QgsProject
    from qgis.gui import QgsMapCanvas
    app = QgsApplication([], True)
    app.initQgis()
    canvas = QgsMapCanvas()
    project = QgsProject.instance()
    '''
    import sys
    from qgis.PyQt import QtWidgets
    app    = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QMainWindow()
    scene = QtWidgets.QScene()
    graphicsView = QtWidgets.QGraphicsView()

