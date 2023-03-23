ECHO :: fire2am says :: Welcome to the plugin installer
ECHO.

CALL "C:\OSGeo4W\bin\o4w_env.bat" || ECHO :: fire2am says :: Qgis Environment failed
IF %ERRORLEVEL% neq 0 goto ProcessError

python -m pip install --upgrade setuptools wheel pip || ECHO :: fire2am says :: Upgrading pip tools failed
IF %ERRORLEVEL% neq 0 goto ProcessError

pip install -r requirements.txt || ECHO :: fire2am says :: Installing python packages failed
IF %ERRORLEVEL% neq 0 goto ProcessError

IF EXIST "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\fire2am" RMDIR /s /q "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\fire2am"
XCOPY /e /k /h /i /q "..\fire2am" "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\fire2am"
IF %ERRORLEVEL% neq 0 goto ProcessError

REM happy ending
ECHO.
COLOR 2
ECHO :: fire2am says :: Success
PAUSE
exit /b 0

:ProcessError
REM process error
ECHO.
COLOR 4
ECHO	:: fire2am says :: Errors were made
ECHO	Please run 'install_debug.bat' and report the issue at https://www.github.com/fire2aam/fire2aam-qgis-plugin/issues
PAUSE
exit /b 1
