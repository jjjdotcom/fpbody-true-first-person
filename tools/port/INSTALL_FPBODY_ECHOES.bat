@echo off
setlocal
rem Unpacks the Echoes: True First Person source (fpbody_echoes_sdk.zip, next to
rem this file in your Half-Life folder) and builds the mod. Progress also goes to
rem fpbody_echoes_build.log.
cd /d "%~dp0"
set "LOG=%~dp0fpbody_echoes_build.log"
echo INSTALL_FPBODY_ECHOES started %DATE% %TIME% > "%LOG%"
if not exist "fpbody_echoes_sdk.zip" (
  echo fpbody_echoes_sdk.zip is missing.
  echo fpbody_echoes_sdk.zip is missing. >> "%LOG%"
  pause
  exit /b 1
)
echo Unpacking fpbody_echoes_sdk.zip ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force -Path 'fpbody_echoes_sdk.zip' -DestinationPath '.'" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo Could not unpack fpbody_echoes_sdk.zip - see fpbody_echoes_build.log
  echo Could not unpack fpbody_echoes_sdk.zip >> "%LOG%"
  pause
  exit /b 1
)
echo Unpacked. >> "%LOG%"
if not exist "fpbody_echoes_sdk\BUILD_FPBODY_ECHOES.bat" (
  echo The unpacked folder has no BUILD_FPBODY_ECHOES.bat >> "%LOG%"
  echo The unpacked folder has no BUILD_FPBODY_ECHOES.bat
  pause
  exit /b 1
)
call "fpbody_echoes_sdk\BUILD_FPBODY_ECHOES.bat"
