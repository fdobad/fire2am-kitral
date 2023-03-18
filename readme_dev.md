# Developer guide

## Introduction
- pyqgis: Open the python console, use the provided `extras/qgis_sandbox.py` to test commands  
- IPythonQgis : Install the IPython Console plugin (`pip install qtconsole` is required)  
- qgis plugin: The easiest way to get up to speed with developing QGIS plugins is using the 'Plugin Builder' plugin and build a template.  
- cell2fire: Run the included examples 

## Object Naming Convention
To coordinate `C2FSB/Cell2Fire/ParseInputs.py`, QtDesigner and the plugin code, the following standard must be followed: 

Mostly when adding components in QtDesigner their object name is assigned `classType_n`, so you must change its `objectName` to `prefixName_destName`.  

1.1 Prefix simplified component type: 

| prefixName	| 	`<class type>` |
| --- | --- |
| layerComboBox	|	QgsMapLayerComboBox |
| fileWidget	|	QgsFileWidget |
| radioButton	|	QRadioButton |
| spinBox	|	QSpingBox |
| doubleSpinBox	|	QDoubleSpingBox |

1.2 Suffix, `destName` is the same used in `ParseInputs.py` by the `argparse` object:

| suffixName 	|	`<argparse.item.dest>` |
| --- | --- |
| ROS_CV	|	ROS_CV |

1.3 The results is that the ui values can be easily retrieved. For example for double|spinBoxes (example: doubleSpinBox_ROS_CV):

        args.update( { o.objectName()[ o.objectName().index('_')+1: ]: o.value() 
            for o in self.dlg.findChildren( (QDoubleSpinBox, QSpinBox), 
                                        options= Qt.FindChildrenRecursively)})

1.4 RadioButton Groups share the same startin suffix name, then Uppercase diverge:
	radioButton_weatherFile, 
	radioButton_weatherFolder, 
	radioButton_weatherRandom, 
	radioButton_weatherConst
	
	radioButton_ignitionRandom, 
	radioButton_ignitionPoints, 
	radioButton_ignitionProbMap

## adding new resources
### compile resources if new icons added
```
pyrcc5 -o resources.py resources.qrc
```
### Qt Designer bug when adding a resource
If the plugin won't start after adding a resource with `No module named 'resources_rc'`.
Delete the line in between 
```
 <resources>
  <include location="resources.qrc"/>
 </resources>
```
Ref: [broken plugin](https://gis.stackexchange.com/questions/271848/the-plug-in-is-broken-no-module-named-resources)

## For cell2fire developer tips
- use print('...', flush=True) for rasing the message to the gui
- never use import *
- prefer np.loadtxt over pd.read_csv

## References
### Required
- [qgis docs](https://docs.qgis.org/latest/en/docs/index.html)
- [pyqgis api](https://www.qgis.org/pyqgis/master/index.html)
- [qgis developer cookbook](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/intro.html)
- [PyQt5.QtWidgets](https://www.riverbankcomputing.com/static/Docs/PyQt5/api/qtwidgets/qtwidgets-module.html)
### Plugin specific
- [tutorial](https://gis-ops.com/qgis-3-plugin-tutorial-plugin-development-reference-guide/)
- [minimal plugin repo](https://github.com/wonder-sk/qgis-minimal-plugin)
- [plugin debugger](https://github.com/wonder-sk/qgis-first-aid-plugin)
- [videoTutorialPluginBuilder](https://opensourceoptions.com/lesson/build-and-deploy-a-plugin-with-plugin-builder-and-pb_tool/)
- [pb_tools build tools](https://github.com/g-sherman/plugin_build_tool)
- [homepage](https://plugins.qgis.org/)
- [no binaries!!](https://plugins.qgis.org/publish/)
- [windows python packages?](https://landscapearchaeology.org/2018/installing-python-packages-in-qgis-3-for-windows/)
- [windows python packages ugly](https://www.lutraconsulting.co.uk/blog/2016/03/02/installing-third-party-python-modules-in-qgis-windows/)
### qgis
- [gisops](https://gis-ops.com/qgis-3-plugin-tutorial-background-processing/)
- [gis.ch](https://www.opengis.ch/2018/06/22/threads-in-pyqgis3/)
- [core developer tips](https://woostuff.wordpress.com/)
- [core developer tips](http://nyalldawson.net/)
- [workshop](https://madmanwoo.gitlab.io/foss4g-python-workshop/)
- [custom processing script](https://madmanwoo.gitlab.io/foss4g-python-workshop/processing/)
- [qgisblog](https://kartoza.com/search?q=qgis)
