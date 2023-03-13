# Cell 2 Fire QGIS plugin

This repo contains a [QGIS](https://qgis.org) [plugin](https://plugins.qgis.org/) for graphically interfacing with Cell2Fire [SB](https://github.com/fire2a/C2FSB) simulator.  
Choose your guide:
- [User](readme_user.md)
- [Developer](readme_dev.md)

## Quickstart
0. Have QGIS installed (developed using 3.1 long term version)  
1. Download the whole repo, put in your qgis plugin folders  
    - Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/fire2am`
    - Windows: `C:\Users\ \AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\fire2am`
2. Compile cell2fire
2. Install python3 dependencies `requirements.txt` 
3. Activate the plugin: 
    - QGIS Menu > Plugins > Manage ... > enable plugins
    - type 'fire'
    - click 'install plugin'
Now you have a new icon on the plugin toolbar and a new plugin menu.
[icon](img/icon.png)

## Known issues
- Don't close the current project with the dialogs opened
