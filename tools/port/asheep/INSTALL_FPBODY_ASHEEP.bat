@echo off
setlocal
rem Unpacks the Azure Sheep: True First Person source (fpbody_asheep_sdk.zip, next to
rem this file in your Half-Life folder) and builds the mod. Progress also goes to
rem fpbody_asheep_build.log.
cd /d "%~dp0"
set "LOG=%~dp0fpbody_asheep_build.log"
echo INSTALL_FPBODY_ASHEEP started %DATE% %TIME% > "%LOG%"
if not exist "fpbody_asheep_sdk.zip" (
  echo fpbody_asheep_sdk.zip is missing.
  echo fpbody_asheep_sdk.zip is missing. >> "%LOG%"
  pause
  exit /b 1
)
echo Unpacking fpbody_asheep_sdk.zip ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force -Path 'fpbody_asheep_sdk.zip' -DestinationPath '.'" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo Could not unpack fpbody_asheep_sdk.zip - see fpbody_asheep_build.log
  echo Could not unpack fpbody_asheep_sdk.zip >> "%LOG%"
  pause
  exit /b 1
)
echo Unpacked. >> "%LOG%"
if not exist "fpbody_asheep_sdk\BUILD_FPBODY_ASHEEP.bat" (
  echo The unpacked folder has no BUILD_FPBODY_ASHEEP.bat >> "%LOG%"
  echo The unpacked folder has no BUILD_FPBODY_ASHEEP.bat
  pause
  exit /b 1
)
call "fpbody_asheep_sdk\BUILD_FPBODY_ASHEEP.bat"
