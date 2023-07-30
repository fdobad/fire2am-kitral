# fire2am ~ fire 2 advanced analytics and management

## 0. [Plugin users check documentation here](https://fdobad.github.io/doctest/)  
(the one here at docs/ may be not uptodate)

## 1. What's here:
- This repo is QGIS plugin root, strictly necessary files:  
    ```
    fire2am*
    __init__.py
    metadata.txt            <- plugin id
    qgis_utils.py
    ParseInputs2.py
    spain_lookup_table.csv
    img/                    <- ui resources
    C2FSB/                  <-simulator binaries
    ```

- Extras
    ```
    # previncat wnd 2 weather.csv transformer
    wnd2Weathercsv.py

    # qgis related
    qgis_allProcessingAlgorithmsNames.txt
    qgis_plugin_scraps.py
    qgis_sandbox.py

    # plugin related 
    dummy_proc.py
    installer_scraps.bat
    PluginBuilderResults.txt
    loading_in_background.py
    
    # c2f related
    Stats.py
    Statspy_Grid.py
    ```

# 2. Give us feedback
At the issues or directly to fire2a@fire2a.com

# Tips & tricks

    # fix headers replacing MT for TMP
    sed -i '1{s/MT/TMP/}' Weather*.csv
