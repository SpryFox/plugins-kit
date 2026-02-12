@echo off
:: UE Python API — One-shot setup. Requires Python on PATH.
:: Tries python, then py (Windows launcher).
python "%~dp0setup.py" %* 2>nul && exit /b %ERRORLEVEL%
py "%~dp0setup.py" %* 2>nul && exit /b %ERRORLEVEL%
echo [setup] ERROR: Python not found on PATH.
echo [setup] Add Python to PATH, or run setup directly with a known Python:
echo [setup]   Common locations:
echo [setup]     C:\Python3*\python.exe
echo [setup]     %LOCALAPPDATA%\Programs\Python\Python3*\python.exe
echo [setup]     Engine\Binaries\ThirdParty\Python3\Win64\python.exe (UE bundled)
echo [setup]   Example:
echo [setup]     "C:\path\to\python.exe" "%~dp0setup.py"
exit /b 1
