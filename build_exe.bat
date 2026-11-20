@echo off
echo ====================================================
echo  Building schedule-matcher.exe with PyInstaller
echo ====================================================

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo Running tests...
pytest -v
if %ERRORLEVEL% NEQ 0 (
    echo Tests failed! Aborting build.
    pause
    exit /b %ERRORLEVEL%
)

echo Packaging into dist\schedule-matcher.exe...
pyinstaller schedule-matcher.spec

echo ====================================================
echo  Build complete! Output is in dist\schedule-matcher.exe
echo ====================================================
pause
