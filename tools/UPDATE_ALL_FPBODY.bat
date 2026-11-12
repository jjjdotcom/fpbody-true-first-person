@echo off
setlocal EnableDelayedExpansion
rem Builds every True First Person mod in one go, in the right order:
rem Half-Life, Blue Shift, Opposing Force, Echoes, Field Intensity, Decay,
rem Azure Sheep, then Uplink (it copies Half-Life's new DLLs and models).
rem Put it in your Half-Life folder. Each build's output goes to
rem fpbody_update_all.log; a summary is shown at the end. Close the game first.
cd /d "%~dp0"
set "HL=%~dp0"
set "LOG=%HL%fpbody_update_all.log"
set "STEP=%TEMP%\fpbody_update_step.log"
echo UPDATE_ALL_FPBODY started %DATE% %TIME% > "%LOG%"
set "OKS="
set "FAILS="

call :build "Half-Life"        "fpbody_sdk\BUILD_FPBODY.bat"
call :build "Blue Shift"       "fpbody_bs_sdk\BUILD_FPBODY_BS.bat"
call :build "Opposing Force"   "fpbody_op4_sdk\BUILD_FPBODY_OP4.bat"
call :build "Echoes"           "INSTALL_FPBODY_ECHOES.bat"
call :build "Field Intensity"  "INSTALL_FPBODY_FI.bat"
call :build "Decay"            "INSTALL_FPBODY_DECAY.bat"
call :build "Azure Sheep"      "INSTALL_FPBODY_ASHEEP.bat"
call :build "Uplink"           "INSTALL_FPBODY_UPLINK.bat"

echo.
echo ============================================================
if defined OKS echo  Built:  !OKS!
if defined FAILS (
  echo  FAILED: !FAILS!
  echo.
  echo  The error lines are in fpbody_update_all.log - paste them to Claude.
) else (
  echo  All mods updated.
)
echo ============================================================
echo Finished %DATE% %TIME% >> "%LOG%"
echo.
pause
exit /b

:build
set "NAME=%~1"
echo.
echo [%TIME:~0,8%] Building %NAME% ...
echo. >> "%LOG%"
echo ==================== %NAME% (%~2) ==================== >> "%LOG%"
cd /d "%HL%"
if not exist "%~2" (
  echo     missing %~2
  echo missing %~2 >> "%LOG%"
  set "FAILS=!FAILS! [%NAME%]"
  exit /b
)
rem (its own window settings; input from nul: its "press any key" doesn't wait)
cmd /d /c ""%HL%%~2"" < nul > "%STEP%" 2>&1
cd /d "%HL%"
type "%STEP%" >> "%LOG%"
findstr /i /c:"FAILED" /c:": error" /c:"fatal error" /c:"is missing" /c:"Could not" /c:"was not found" /c:"is not built" "%STEP%" > nul
if errorlevel 1 (
  echo     OK
  set "OKS=!OKS! [%NAME%]"
) else (
  echo     FAILED:
  findstr /i /c:"FAILED" /c:": error" /c:"fatal error" /c:"is missing" /c:"Could not" /c:"was not found" /c:"is not built" "%STEP%"
  set "FAILS=!FAILS! [%NAME%]"
)
exit /b
