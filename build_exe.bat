@echo off
REM Run this on Windows (with Python installed) to produce dist\resize_images.exe
python -m pip install pillow pyinstaller
python -m PyInstaller --onefile --windowed --name ImageResizer resize_images.py
echo.
echo Done. The .exe is in the "dist" folder.
pause
