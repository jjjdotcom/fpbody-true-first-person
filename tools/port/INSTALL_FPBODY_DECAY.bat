@echo off
setlocal
rem Unpacks the Decay: True First Person source (fpbody_decay_sdk.zip, next to
rem this file in your Half-Life folder) and builds the mod. Progress also goes to
rem fpbody_decay_build.log.
cd /d "%~dp0"
set "LOG=%~dp0fpbody_decay_build.log"
echo INSTALL_FPBODY_DECAY started %DATE% %TIME% > "%LOG%"
if not exist "fpbody_decay_sdk.zip" (
  echo fpbody_decay_sdk.zip is missing.
  echo fpbody_decay_sdk.zip is missing. >> "%LOG%"
  pause
  exit /b 1
)
echo Unpacking fpbody_decay_sdk.zip ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force -Path 'fpbody_decay_sdk.zip' -DestinationPath '.'" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo Could not unpack fpbody_decay_sdk.zip - see fpbody_decay_build.log
  echo Could not unpack fpbody_decay_sdk.zip >> "%LOG%"
  pause
  exit /b 1
)
echo Unpacked. >> "%LOG%"
if not exist "fpbody_decay_sdk\BUILD_FPBODY_DECAY.bat" (
  echo The unpacked folder has no BUILD_FPBODY_DECAY.bat >> "%LOG%"
  echo The unpacked folder has no BUILD_FPBODY_DECAY.bat
  pause
  exit /b 1
)
call "fpbody_decay_sdk\BUILD_FPBODY_DECAY.bat"
