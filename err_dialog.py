from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QErrorMessage
from .img.resources import *
# TODO from qgis.core import Qgis, QgsMessageLog
class ErrDialog:
    def __init__(self, iface, msg):
        self.iface = iface
        self.msg=str(msg)
        icon = QIcon(':/plugins/fire2am/img/icon.png')
        self.text = 'Fire2am packages missing'
        self.action = QAction(icon, self.text, self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.action.setEnabled(True)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(self.text, self.action)
        self.first_start = None

    def initGui(self):
        self.first_start = True

    def run(self):
        if self.first_start == True:
            self.dlg = QErrorMessage()
            self.dlg.setWindowTitle('Fire2am Plugin Error')
            self.dlg.showMessage('Not found modules: '+self.msg+'\nThe plugin will not run until pip packages are installed, QGIS is restarted and the plugin is reinstalled.\nPlease visit https://fdobad.github.io/doctest/ for instructions. At this point you may https://fdobad.github.io/doctest/#forcing-python-requirements-in-qgis-console')
            self.first_start = False
        self.dlg.show()
        self.dlg.exec_()

    def unload(self):
        self.iface.removeToolBarIcon( self.action)
        self.iface.removePluginMenu( self.text, self.action)
