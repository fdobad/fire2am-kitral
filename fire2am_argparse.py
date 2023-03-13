#!/usr/bin/env python3
'''
#NOREPLENV: /home/fdo/pyvenv/qgis
standalone run:
    python3 -m fire2am.fire2am_argparse
'''
from qgis.gui import QgsFileWidget
from qgis.PyQt import QtWidgets, QtCore, QtGui
from qgis.PyQt.QtCore import Qt
from argparse import Namespace
import sys, pickle
import pyperclip
import os.path
from .fire2am_utils import safe_cast_ok, aName, get_params, log
from .ParseInputs2 import Parser2

class fire2amClassDialogArgparse(QtWidgets.QDialog):
    def __init__(self, parent=None):
        """Constructor."""
        self.plugin_dir = os.path.dirname(__file__)
        self.args, self.parser, self.groups = get_params(Parser2)
        super(fire2amClassDialogArgparse, self).__init__(parent)
        # mild consistency check
        if any( g in self.args.keys() for g in self.groups):
            offenders = [ g for g in self.groups if g in self.args.keys() ]
            msg = aName+' ERROR:Group name (parser_group.title) in args.dest names:\n\t'\
                                + str(offenders)\
                                +'\nCorrect in ParseInputs.py file'
            layout = QtWidgets.QHBoxLayout()
            btn = QtWidgets.QPushButton( self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxCritical), '')
            layout.addWidget( btn )
            layout.addWidget( QtWidgets.QLabel(msg))
            self.setLayout(layout)
            return
        self.setupUi()

        self.header = None
        self.arg_str = None
        self.gen_args = None
        self.gen_cmd()
        log('argparse init completed',self.gen_args,__name__)

    def setupUi(self):
        self.setWindowFlags( Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)
        self.setWindowTitle(aName +' all options (very experimental)')
        # add stuff to a layout
        vlayout = QtWidgets.QVBoxLayout()
        #vlayout.addWidget( QtWidgets.QSpacerItem(1,1))
        # tree
        self.tree = self.init_Tree()
        vlayout.addWidget( self.tree)
        self.tree.itemChanged.connect( self.slot_itemChanged)
        self.tree.itemClicked.connect( self.slot_itemClicked)
        # text browser containing the output command
        text = QtWidgets.QTextBrowser()
        fm = text.fontMetrics()
        text.setMinimumHeight(round(1.1*fm.height()))
        text.setMaximumHeight(4*fm.height())
        text.setVisible(False)
        vlayout.addWidget(text)
        self.text = text
        # options
        hlayout = QtWidgets.QHBoxLayout()
        # clipboard check box
        self.clipboard_checkBox = QtWidgets.QCheckBox('Put generated command on system clipboard. ')
        self.clipboard_checkBox.setVisible(False)
        hlayout.addWidget( self.clipboard_checkBox)
        # label_header
        self.label_header = QtWidgets.QLabel(' Header:')
        self.label_header.setAlignment( Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter )
        self.label_header.setVisible(False)
        hlayout.addWidget( self.label_header)
        # textEdit_header 
        self.textEdit_header = QtWidgets.QTextEdit('python3 main.py ')
        self.textEdit_header.setMaximumHeight(1.1*fm.height())
        self.textEdit_header.setVisible(False)
        hlayout.addWidget( self.textEdit_header)
        # label_directory
        self.label_directory = QtWidgets.QLabel('Cell2Fire directory:')
        self.label_directory.setAlignment( Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter )
        self.label_directory.setVisible(False)
        hlayout.addWidget( self.label_directory)
        # fileWidget_directory 
        self.fileWidget_directory = QgsFileWidget(storageMode = QgsFileWidget.StorageMode.GetDirectory)
        self.fileWidget_directory.setFilePath(os.path.join( self.plugin_dir, 'C2FSB'))
        self.fileWidget_directory.setVisible(False)
        hlayout.addWidget( self.fileWidget_directory)
        # add hlayout
        vlayout.addLayout( hlayout)
        # buttons
        hlayout = QtWidgets.QHBoxLayout()
        self.button_load = QtWidgets.QPushButton( self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogOpenButton), 'Load')
        self.button_save = QtWidgets.QPushButton( self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogSaveButton), 'Save')
        self.button_toggle = QtWidgets.QPushButton( self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowUp), '')
        self.state_visible = False
        self.button_load.clicked.connect( self.slot_button_load_clicked)
        self.button_save.clicked.connect( self.slot_button_save_clicked)
        self.button_toggle.clicked.connect( self.slot_button_toggle_clicked)
        hlayout.addWidget( self.button_load)
        hlayout.addWidget( self.button_save)
        hlayout.addWidget( self.button_toggle)
        vlayout.addLayout( hlayout)
        # end
        self.setLayout(vlayout)

    def slot_button_toggle_clicked(self):
        if self.text.isVisible():
            self.button_toggle.setIcon( self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowUp))
            self.text.setVisible(False)
            self.clipboard_checkBox.setVisible(False)
            self.label_header.setVisible(False)
            self.textEdit_header.setVisible(False)
            self.label_directory.setVisible(False)
            self.fileWidget_directory.setVisible(False)
        else:
            self.button_toggle.setIcon( self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowDown))
            self.text.setVisible(True)
            self.clipboard_checkBox.setVisible(True)
            self.label_header.setVisible(True)
            self.textEdit_header.setVisible(True)
            self.label_directory.setVisible(True)
            self.fileWidget_directory.setVisible(True)

    def init_Tree(self):
        tree = QtWidgets.QTreeWidget()
        tree.setHeaderLabels(['dest','option_strings[0]','default->args.dest=value','type','help'])
        tree.setColumnCount(5)
        for group in self.groups:
            parent = QtWidgets.QTreeWidgetItem(tree)
            parent.setText(0, group)
            parent.setFlags(parent.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
            parent.setExpanded(True)
            for key,val in self.parser.items():
                if val['group'] == group:
                    child = QtWidgets.QTreeWidgetItem(parent)
                    child.setFlags(child.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
                    child.setText(0, str(val['dest']             ))
                    child.setText(1, str(val['option_strings'][0]))
                    child.setText(3, str(val['type']))
                    child.setText(4, str(val['help']))
                    # 2
                    child.setCheckState(0, Qt.Unchecked)
                    if val['type'] is None:
                        if self.args[key]:
                            child.setCheckState(0, Qt.Checked)
                        else:
                            child.setCheckState(0, Qt.Unchecked)
                    child.setText(2, str(self.args[key]))
                    child.setHidden(False)
        tree.setItemDelegateForColumn(0,DisableEditorDelegate())
        tree.sortItems(0,Qt.SortOrder.AscendingOrder)
        tree.resizeColumnToContents(0)
        tree.resizeColumnToContents(1)
        tree.updateGeometry()
        return tree

    def slot_itemChanged( self, item, column):
        '''
            print('\nitemChanged','self.args',self.args,'kwargs',kwargs,sep='\t')
            print(item.text(0),column, item.text(2))
        print('\titemChanged col',column,end='\t')
        TODO test column in [1,3,4]
        '''
        if column in [1,3,4]:
            return
        # value is string
        key, value = item.text(0), item.text(2)
        if key in self.groups:
            #print('ich group',key,value,column)
            return
        #antes=self.args[key]
        ok = False
        if self.parser[key]['type'] is str:
            self.args[key], ok = safe_cast_ok( value, str,   self.parser[key]['default'])
        elif self.parser[key]['type'] is int:
            self.args[key], ok = safe_cast_ok( value, int,   self.parser[key]['default'])
        elif self.parser[key]['type'] is float:
            self.args[key], ok = safe_cast_ok( value, float, self.parser[key]['default'])
        elif self.parser[key]['type'] is None:
            if value == 'True':
                self.args[key] = True
                ok = True
            elif value == 'False':
                self.args[key] = False
                ok = True
            else:
                ok = False
        else:
            print('Item type %s not implemented!'%self.parser[key]['type'])
            raise NotImplementedError
        if not ok:
            item.setText( 2, str(self.parser[key]['default']))
        #print('antes',antes,'despues',self.args[key],sep='\t')
        #print('end itemChanged',key,value,column)
        self.gen_cmd()
    
    def slot_itemClicked( self, item, column):
        '''CheckState
            Checked             2 The item is checked.
            PartiallyChecked    1 The item is partially checked. Items in hierarchical
                                  models may be partially checked if some, but not all,
                                  of their children are checked.
            Unchecked           0 The item is unchecked.
    
            def slot_itemClicked(*args, **kwargs):
                print('\nitemClicked','args',args,'kwargs',kwargs,sep='\t')
                item, column = args
        '''
        #print('\titemClicked',end='\t')
        if column != 0:
            return
        # value is string
        key, value = item.text(0), item.text(2)
        #print(key, value, column, item.checkState(0))
        if key in self.groups:
            parent = item
            group = key
            value = item.checkState(0)
            #print('parent:',parent,'group:',group,'value:',value)
            iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
            item: QtWidgets.QTreeWidgetItem = iterator.value()
            while item is not None:
                key = item.text(0)
                if key in self.groups:
                    pass
                elif self.parser[key]['group'] == group and self.parser[key]['type'] is None:
                    if value == 2:
                        item.setText(2, 'True')
                        self.args[key] = True
                    elif value == 0:
                        item.setText(2, 'False')
                        self.args[key] = False
                    else:
                        pass
                        #print('itemClicked do nothin',key,value)
                else:
                    pass
                iterator += 1
                item = iterator.value()
        else:
            #antes=self.args[key]
            if self.parser[key]['type'] is None:
                if item.checkState(0) == 2:
                    self.args[key] = True
                    item.setText(2,'True')
                if item.checkState(0) == 0:
                    self.args[key] = False
                    item.setText(2,'False')
            #print('antes',antes,'despues',self.args[key],sep='\t')
        self.gen_cmd()

    def gen_cmd(self):
        self.gen_args = {}
        self.header = self.textEdit_header.toPlainText()
        self.arg_str = ''
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
        item: QtWidgets.QTreeWidgetItem = iterator.value()
        while item is not None:
            key = item.text(0)
            if key in self.groups or item.checkState(0)==0:
                pass
            elif self.parser[key]['type'] is None:
                self.arg_str += self.parser[key]['option_strings'][0] + ' '
                self.gen_args[key] = True
            else:
                self.arg_str += self.parser[key]['option_strings'][0] + ' ' + str(self.args[key]) + ' '
                self.gen_args[key] = self.args[key]
            iterator += 1
            item = iterator.value()
        cmd = self.header + ' ' + self.arg_str
        self.text.setPlainText(cmd)
        if self.clipboard_checkBox.isChecked():
            pyperclip.copy(cmd)

    def get(self):
        self.gen_cmd()
        return self.header, self.arg_str, self.gen_args, self.fileWidget_directory.filePath()

    def reloadTree(self, check_list):
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
        item: QtWidgets.QTreeWidgetItem = iterator.value()
        while item is not None:
            key = item.text(0)
            if key not in self.groups:
                item.setText( 2, str(self.args[key]))
            item.setCheckState( 0, check_list[key])
            item.setHidden( False)
            iterator += 1
            item = iterator.value()

    def get_check_list( self):
        check_list = {}
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
        item: QtWidgets.QTreeWidgetItem = iterator.value()
        while item is not None:
            check_list[ item.text(0)] = item.checkState(0)
            iterator += 1
            item = iterator.value()
        return check_list
    
    def dumpState( self, atuple):
        '''
            dumpState((parser, groups, args, get_check_list()))
        '''
        with open('dump.pickle','wb') as afile:
            pickle.dump( atuple , afile)
    
    def loadState( self):
        '''
            parser, groups, args, check_list = loadState()
            parser, groups, args, check_list = pickle.load( open('dump.pickle','rb'))
        '''
        if os.path.isfile('dump.pickle'):
            with open('dump.pickle','rb') as afile:
                return pickle.load( afile)

    def slot_button_load_clicked( self):
        self.parser, self.groups, self.args, check_list = self.loadState()
        self.reloadTree( check_list)
    
    def slot_button_save_clicked( self):
        self.dumpState(( self.parser, self.groups, self.args, self.get_check_list()))

class DisableEditorDelegate(QtWidgets.QItemDelegate):
    '''QItemDelegate, QAbstractItemDelegate, QStyledItemDelegate
    '''
    def __init__(self, *args, **kwargs):
        super(DisableEditorDelegate, self).__init__(*args, **kwargs)
    def createEditor(self, *args, **kwargs):
        return None 

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = fire2amClassDialogArgparse()
    window.show()
    sys.exit(app.exec_())
