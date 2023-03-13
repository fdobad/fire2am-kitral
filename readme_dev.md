# Developer guide

## Introduction
- qgis: The easiest way to get up to speed with developing QGIS plugins is using the 'Plugin Builder' plugin and build a template.
- cell2fire: Run the included examples

## Coordinating QtDesigner and python code
1. Object Naming Convention : 
To coordinate from argparse dest names to QtDesigner, modules follow this prefix_suffix standard:

1.1 Prefix simplified component type: 
	prefixName	:	<class type> 
	layerComboBox	:	QgsMapLayerComboBox 
	fileWidget	:	QgsFileWidget
	radioButton	:	QRadioButton
	spinBox		:	QSpingBox
	doubleSpinBox	:	QDoubleSpingBox

1.2 Suffix:
	suffixName 	:	<argparse.item.dest>
	ROS_CV		:	ROS_CV

1.3 Mandatory for double|spinBoxes, example: doubleSpinBox_ROS_CV. They are retrieved like this:

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
### qtDesigner bug when adding a resource
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
