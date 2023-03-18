# Cell 2 Fire QGIS plugin

This repo contains a [QGIS](https://qgis.org) [plugin](https://plugins.qgis.org/) for graphically interfacing with Cell2Fire [SB](https://github.com/fire2a/C2FSB) simulator.  
Choose your guide:
- [User](readme_user.md)![icon](img/icon.png)
- [Developer](readme_dev.md)![icon](img/icon_dev.png)

## Developer Quickstart
### Install
```
# QGIS >=3.1 LTR installed
cd ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins
git clone --recursive git@github.com:fdobad/fire2am-qgis-plugin.git fire2am
cd fire2am
pip install -r requirements.txt #virtualenv recommended!
cd C2FSB/Cell2Fire
sudo apt install g++ libboost-all-dev libeigen3-dev
make #makefile assumes EIGENDIR = /usr/include/eigen3/ change if needed
(venv) $ qgis
```
### Update
This plugin uses Cell2Fire [SB](https://github.com/fire2a/C2FSB) as a submodule  
```
# plugin
git pull
# latest Cell2FireSB 
git submodule update --recursive --remote  
```
## Install
### Windows
0. Install QGIS, using OSGeo4W net installer  
    - https://qgis.org/en/site/forusers/alldownloads.html#osgeo4w-installer  
    - tick QGIS & pip modules  
1. Download & unzip a release (from the right tab)  
2. Run installer.bat  

### Linux  
0. Install QGIS  
    - (Debian LTR version) Super Key > type 'QGIS' > Click Install
    - https://qgis.org/en/site/forusers/alldownloads.html#linux
1. Donwload release, unzip into plugin folder
    - `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/fire2am`
2. `cd` into it  
3. Python requirements 
3.1 Optional virtual environment 
```
python3 -m venv --include-system-packages ~/pyenvs/pyqgis 
echo 'alias pyqgis="source ~/pyenvs/pyqgis/bin/activate"'>>~/.bashrc
bash
pyqgis
```
3.2 Install requirements  
```
pip install -r requirements.txt
```
4. Compile cell2fire c++ binary
```
cd C2FSB/Cell2Fire
sudo apt install g++ libboost-all-dev libeigen3-dev
# makefile assumes EIGENDIR = /usr/include/eigen3/ adjust if needed
make 
```

### Activate  
1. QGIS Menu > Plugins > Manage and Install Plugins > All  
2. type 'fire', select 'Fire Simulator Analytics Management'  
3. click 'Install Plugin'  
Now you have a new icon on the plugin toolbar and a new plugin menu.  

## Usage Overview
0. Open & save a qgis project  
1. At least have a fuel raster layer in ascii AAIGrid format, according to Scott & Burgan fuels [definition](spain_lookup_table.csv)  
2. Set project & layers CRS  
3. Open the dialog, setup the layers, ignitions, weather & click Run!  

## Screenshot  
![panel_screenshot](img/panel_screenshot.png)  

0. On the Plugin Menu this plugin is shown selected  
1. Its icon is also available on the Plugin Toolbar ![icon](img/icon.png)  
2. Along other very useful plugins:  
    - Plugin Builder : For developers wanting a minimal working plugin template  
    - Plugin Reloader : If the provided Restore Defaults button doesn't work, use this  
    - Time Manager : For earlier versions of QGIS (<3.2) this is needed for animating the fire isochrones (merged fire evolution layer)  
    - IPython QGIS Console : A introspection capable ipython session based on qtconsole  

## Known issues  
- Don't close the current project with the dialogs opened  
- Don't try opening the results directory while the simulation is running, specially after the simulation while calculating statistics
