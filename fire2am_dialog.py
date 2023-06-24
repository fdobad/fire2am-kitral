# -*- coding: utf-8 -*-
#!/usr/bin/env python3
#REPLENV: /home/fdo/pyenv/qgis
'''
/***************************************************************************
 fire2amClassDialog
                                 A QGIS plugin
 Simulate a forest fires under different weather and fire model scenarios
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2023-02-07
        git sha              : $Format:%H$
        copyright            : (C) 2023 by fdobadvel (gui) & fire2a team
        email                : fire2a@fire2a.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
'''
import csv
import io
import os
from multiprocessing import cpu_count

import numpy as np
from qgis.gui import QgsFileWidget, QgsMapLayerComboBox, QgsMessageBar
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import QEvent, Qt
from qgis.PyQt.QtGui import QKeySequence
from qgis.core import Qgis, QgsMessageLog

from .fire2am_utils import MatplotlibFigures, PandasModel, aName

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'fire2am_dialog_base.ui'))

'''if Interactive (maybe comment PandasModel also)
    os.getcwd(), 'fire2am_dialog_base.ui'))
    fr om qgis.core import QgsApplication
    app = QgsApplication([], True)
    dlg = fire2amClassDialog()
    
'''

class fire2amClassDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        '''Constructor.'''
        super(fire2amClassDialog, self).__init__(parent)
        self.setupUi(self)
        '''Customize.'''
        self.setWindowFlags( Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)
        self.msgBar = QgsMessageBar()
        self.msgBar.setSizePolicy( QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred) #Fixed Maximum
        ''' TODO qlabel vertical expand 
            self.msgBar.setSizePolicy( QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding) #Fixed Maximum
                for c in self.msgBar.children():
                    if type(c) == QtWidgets.QLabel:
                        c.setSizePolicy( QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding )
                        #c.setSizePolicy( c.sizePolicy().horizontalPolicy(), c.sizePolicy().horizontalPolicy() )
                        c.setMaximumHeight( c.maximumWidth() )
        '''
        self.layout().addWidget(self.msgBar) # at the end: .insertRow . see qformlayout
        self.PandasModel = PandasModel
        self.plt = MatplotlibFigures( parent = parent, graphicsView = self.graphicsView)
        self.stats.installEventFilter(self)
        self.statsdf = None
        self.state = {}
        self.updateState()
        self.args = {}
        self.layerComboBoxes = { o.objectName():o for o in self.findChildren( QgsMapLayerComboBox, options= Qt.FindChildrenRecursively) }
        self.init_default_values()
        self.pushButton_windRandomize.pressed.connect( self.slot_windRandomize)
        self.tables = {}
        self.df = {}
        self.update_tables()

    def update_tables(self):
        self.tables.update({o.objectName(): o
                            for o in self.findChildren(QtWidgets.QTableView, 
                                                        options= Qt.FindChildrenRecursively)})
        qlog(self.tables)

    def update_data(self, name, df, **kwargs):
        assert name in self.tables.keys()
        old = self.dlg.df[name]
        df['Index'] = df.index
        df = concat((old,df), kwargs)
        self.dlg.add_data(name,df)
        qlog(f'update {name}:{df}')

    def add_data(self, name, df):
        self.df[name] = df
        df['Index'] = df.index
        self.tables[name].setModel(PandasModel(df))
        qlog(f'add {name}:{df}')

    def add_table(self, name='hola'):
        if name in self.tables:
            return
        widget = QtWidgets.QWidget()
        tableview = QtWidgets.QTableView(parent=widget)
        tableview.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        tableview.setObjectName(name)
        tableview.installEventFilter(self)
        widget.setLayout(QtWidgets.QGridLayout())
        widget.layout().addWidget(tableview)
        widget.setToolTip(name)
        self.tabWidget_tables.addTab( widget, name)
        self.tables[name] = tableview

    def updateState(self):
        ''' for widgets put their state, value, layer or filepath into a self.state dict 
            objectNames are defined on QtDesigner
        '''
        # radio button
        self.state.update( { o.objectName(): o.isChecked() 
            for o in self.findChildren( QtWidgets.QRadioButton, 
                                        options= Qt.FindChildrenRecursively)})
        # layer combobox
        self.state.update( { o.objectName(): o.currentLayer() 
            for o in self.findChildren( QgsMapLayerComboBox, 
                                        options= Qt.FindChildrenRecursively)})
        # file chooser
        self.state.update( { o.objectName(): o.filePath() 
            for o in self.findChildren( QgsFileWidget, 
                                        options= Qt.FindChildrenRecursively)})
        # Double|SpinBox
        self.state.update( { o.objectName(): o.value()
            for o in self.findChildren( (QtWidgets.QDoubleSpinBox, QtWidgets.QSpinBox),
                                        options= Qt.FindChildrenRecursively)})
        # CheckBox
        self.state.update( { o.objectName(): o.isChecked()
            for o in self.findChildren( QtWidgets.QCheckBox,
                                        options= Qt.FindChildrenRecursively)})

    def eventFilter(self, source, event):
        if isinstance(source, QtWidgets.QTableView):
            if event.type() == QEvent.KeyPress:
                if event.matches(QKeySequence.Copy):
                    self.copySelection(source)
                    return True
                '''TBD
                if event.matches(QKeySequence.Paste):
                    self.pasteSelection()
                    return True
                '''
        return super(fire2amClassDialog, self).eventFilter(source, event)

    def copySelection(self, fromTable):
        selection = fromTable.selectedIndexes()
        if selection:
            rows = sorted(index.row() for index in selection)
            columns = sorted(index.column() for index in selection)
            rowcount = rows[-1] - rows[0] + 1
            colcount = columns[-1] - columns[0] + 1
            table = [[''] * colcount for _ in range(rowcount)]
            for index in selection:
                row = index.row() - rows[0]
                column = index.column() - columns[0]
                table[row][column] = index.data()
            stream = io.StringIO()
            csv.writer(stream, delimiter='\t').writerows(table)
            QtWidgets.qApp.clipboard().setText(stream.getvalue())
        return

    def init_default_values(self):
        self.spinBox_nthreads.setValue( max(cpu_count() - 1, 1))
        self.spinBox_nthreads.setMaximum(cpu_count())
        self.msgBar.pushMessage(aName+' says:','Keep a saved project open, drag&drop rasters from the ProjectHome then Restore Defaults', duration=0, level=Qgis.Info)

    def slot_windRandomize(self):
        WD = np.random.randint(0,359)
        WS = np.random.randint(1,100)
        self.spinBox_windDirection.setValue(WD)
        self.spinBox_windSpeed.setValue(WS)

def qlog(msg, level=Qgis.Info):
    """ <0 ''
        0:Qgis.Info
        1:  .Warning
        2:  .Critical
        3:  .Success
        >3: NONE
    """
    QgsMessageLog.logMessage(str(msg), aName+'_dialog', level)

    ''' TBD if user pastes tabular data into table
    def pasteSelection(self):
        selection = self.selectedIndexes()
        if selection:
            model = self.model()
    
            buffer = QtWidgets.qApp.clipboard().text()
            rows = sorted(index.row() for index in selection)
            columns = sorted(index.column() for index in selection)
            reader = csv.reader(io.StringIO(buffer), delimiter='\t')
            if len(rows) == 1 and len(columns) == 1:
                for i, line in enumerate(reader):
                    for j, cell in enumerate(line):
                        model.setData(model.index(rows[0]+i,columns[0]+j), cell)
            else:
                arr = [ [ cell for cell in row ] for row in reader]
                for index in selection:
                    row = index.row() - rows[0]
                    column = index.column() - columns[0]
                    model.setData(model.index(index.row(), index.column()), arr[row][column])
        return
    scrap init
        self.stats.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
    '''

