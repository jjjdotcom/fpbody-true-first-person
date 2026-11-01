@echo off
setlocal
rem Unpacks the Field Intensity: True First Person source (fpbody_fi_sdk.zip, next to
rem this file in your Half-Life folder) and builds the mod. Progress also goes to
rem fpbody_fi_build.log.
cd /d "%~dp0"
set "LOG=%~dp0fpbody_fi_build.log"
echo INSTALL_FPBODY_FI started %DATE% %TIME% > "%LOG%"
if not exist "fpbody_fi_sdk.zip" (
  echo fpbody_fi_sdk.zip is missing.
  echo fpbody_fi_sdk.zip is missing. >> "%LOG%"
  pause
  exit /b 1
)
echo Unpacking fpbody_fi_sdk.zip ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force -Path 'fpbody_fi_sdk.zip' -DestinationPath '.'" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo Could not unpack fpbody_fi_sdk.zip - see fpbody_fi_build.log
  echo Could not unpack fpbody_fi_sdk.zip >> "%LOG%"
  pause
  exit /b 1
)
echo Unpacked. >> "%LOG%"
if not exist "fpbody_fi_sdk\BUILD_FPBODY_FI.bat" (
  echo The unpacked folder has no BUILD_FPBODY_FI.bat >> "%LOG%"
  echo The unpacked folder has no BUILD_FPBODY_FI.bat
  pause
  exit /b 1
)
call "fpbody_fi_sdk\BUILD_FPBODY_FI.bat"
