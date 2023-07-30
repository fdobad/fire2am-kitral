# Kitral fire2am : AAM : advanced analytics and management

## Documentation
The same folder is published as:

    ./docs
    https://fdobad.github.io/fire2am-kitral/

## What's here:
This repo is a QGIS plugin module, for development clone it as fire2am (drop the -kitral):

     .local/share/QGIS/QGIS3/profiles/default/python/plugins/fire2am

Contents:
     ```
    __init__.py
    fire2am*
    metadata.txt            <- plugin id
    qgis_utils.py
    ParseInputs2.py
    spain_lookup_table.csv
    img/                    <- ui resources
    C2F/                    <-simulator binaries
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

## Give us feedback
At the issues or directly to fire2a@fire2a.com

## Tips & tricks

    # fix headers replacing MT for TMP
    sed -i '1{s/MT/TMP/}' Weather*.csv
