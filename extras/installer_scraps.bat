
IF "%~1"=="" (
python -c "import sys; print(sys.executable); import site; print(site.getsitepackages())"
python -c "import fastparquet; print('fastparquet:',fastparquet.__version__)"
python -c "import imread; print('imread:',imread.__version__)"
)

