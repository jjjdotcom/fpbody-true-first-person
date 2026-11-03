@echo off
setlocal
rem Builds "Azure Sheep: True First Person" (client.dll + hl.dll, Release | Win32)
rem with your installed Visual Studio and CMake, sets up the fpbody_asheep mod
rem folder and makes a launcher, "Azure Sheep True First Person.exe", in the
rem Half-Life folder. Put this SDK folder (fpbody_asheep_sdk) in your Half-Life
rem folder, next to the asheep folder (Azure Sheep must be installed there).
rem The code is the Azure Sheep reimplementation (github.com/HL1-Mods-Reimplementations-and-Ports/hl-asheep)
rem with the True First Person code added.
cd /d "%~dp0.."
set "HL=%CD%"
cd /d "%~dp0"
set "MOD=%HL%\fpbody_asheep"
set "GAME=%HL%\asheep"
rem everything is also written to this log (send it to Claude if something fails)
set "LOG=%HL%\fpbody_asheep_build.log"
echo Azure Sheep: True First Person build, %DATE% %TIME% >> "%LOG%"

if not exist "%GAME%\liblist.gam" (
  call :say Azure Sheep is not installed in %GAME%
  call :say Install Azure Sheep there first - its folder must be called asheep - then run this again.
  goto :end
)

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
  call :say Could not find vswhere.exe. Is Visual Studio installed?
  goto :end
)

rem CMake: one that comes with any installed Visual Studio (newest last), else one on the PATH
set "CMAKE="
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -all -prerelease -products * -sort -find Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe`) do if not defined CMAKE set "CMAKE=%%i"
if not defined CMAKE for /f "delims=" %%i in ('where cmake 2^>nul') do if not defined CMAKE set "CMAKE=%%i"
if not defined CMAKE (
  call :say Could not find CMake. In Visual Studio Installer, modify your Visual Studio and tick
  call :say "C++ CMake tools for Windows" under Desktop development with C++, then run this again.
  goto :end
)
call :say Using: %CMAKE%
echo.

if not exist "%MOD%" mkdir "%MOD%"
call :say Configuring ...
"%CMAKE%" -A Win32 -B build -DCMAKE_INSTALL_PREFIX="%MOD%" -DENABLE_MOD_ARCHIVE=OFF >> "%LOG%" 2>&1
if errorlevel 1 goto :failed
call :say Building - this takes a few minutes ...
"%CMAKE%" --build build --config Release --parallel >> "%LOG%" 2>&1
if errorlevel 1 goto :failed
"%CMAKE%" --install build --config Release >> "%LOG%" 2>&1
if errorlevel 1 goto :failed

if not exist "%MOD%\cl_dlls\client.dll" (
  call :say Build finished, but client.dll was not copied to %MOD%\cl_dlls
  goto :end
)
if not exist "%MOD%\dlls\hl.dll" (
  call :say Build finished, but hl.dll was not copied to %MOD%\dlls
  goto :end
)

rem The mod folder: Azure Sheep's own liblist.gam with Azure Sheep as the
rem fallback (its maps, sounds, models and settings come from the asheep folder)
echo.
call :say Setting up %MOD% ...
(
  echo game "Azure Sheep: True First Person"
  echo gamedir "fpbody_asheep"
  echo fallback_dir "asheep"
  echo gamedll "dlls\hl.dll"
  echo gamedll_linux "dlls/hl.so"
  echo cldll "1"
) > "%MOD%\liblist.gam"
findstr /v /i /r /c:"^game " /c:"^gamedir" /c:"^fallback_dir" /c:"^gamedll" /c:"^cldll" "%GAME%\liblist.gam" >> "%MOD%\liblist.gam"
call :say liblist.gam written

rem The body models and the network settings come from the Half-Life mod (fpbody)
if not exist "%HL%\fpbody\models\player.mdl" (
  call :say The fpbody folder - Half-Life: True First Person - is missing its models. Install that first.
  goto :end
)
if not exist "%MOD%\models" mkdir "%MOD%\models"
copy /y "%HL%\fpbody\models\player.mdl" "%MOD%\models\" >nul
copy /y "%HL%\fpbody\models\fpbody_*.mdl" "%MOD%\models\" >nul
rem Barney's outfits: the guard uniform, then the blue HEV suit (Azure Sheep's HEV Barney), kept next to this file in asheep_models
if exist "%~dp0asheep_models\*.mdl" copy /y "%~dp0asheep_models\*.mdl" "%MOD%\models\" >nul
rem the Half-Life guns you tuned, where Azure Sheep has no model of its own
for %%f in ("%HL%\fpbody\models\p_*.mdl") do if not exist "%GAME%\models\%%~nxf" copy /y "%%f" "%MOD%\models\" >nul
rem network settings, with room for the body's move state (fuser4)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$src = Join-Path $env:GAME 'delta.lst'; if (-not (Test-Path $src)) { $src = Join-Path $env:HL 'fpbody\delta.lst' }; (Get-Content $src) -replace 'DEFINE_DELTA\( fuser4, DT_SIGNED \| DT_FLOAT, \d+, [0-9.]+ \)', 'DEFINE_DELTA( fuser4, DT_SIGNED | DT_FLOAT, 24, 1.0 )' | Set-Content (Join-Path $env:MOD 'delta.lst') -Encoding ASCII" >> "%LOG%" 2>&1
findstr /c:"fuser4, DT_SIGNED | DT_FLOAT, 24" "%MOD%\delta.lst" >nul || call :say Warning: delta.lst was not updated - the move animations may not show.
rem your settings: copied once, then they're this mod's own
if not exist "%MOD%\autoexec.cfg" copy /y "%HL%\fpbody\autoexec.cfg" "%MOD%\" >nul
if not exist "%MOD%\fpbody_grips.cfg" if exist "%HL%\fpbody\fpbody_grips.cfg" copy /y "%HL%\fpbody\fpbody_grips.cfg" "%MOD%\" >nul
if not exist "%MOD%\fpbody_guns.cfg" if exist "%HL%\fpbody\fpbody_guns.cfg" copy /y "%HL%\fpbody\fpbody_guns.cfg" "%MOD%\" >nul

rem The launcher: "Azure Sheep True First Person.exe" in the Half-Life folder (hl.exe -game fpbody_asheep)
call :say Making the launcher ...
"%CMAKE%" -A Win32 -S fpbody_launcher -B build_launcher -DFPBODY_GAMEDIR=fpbody_asheep "-DFPBODY_EXE_NAME=Azure Sheep True First Person" "-DFPBODY_ICON=%GAME%\AzureSheep.ico" >> "%LOG%" 2>&1
if errorlevel 1 goto :nolauncher
"%CMAKE%" --build build_launcher --config Release >> "%LOG%" 2>&1
if errorlevel 1 goto :nolauncher
copy /y "build_launcher\Release\Azure Sheep True First Person.exe" "%HL%\" >nul
if errorlevel 1 goto :nolauncher
call :say Launcher: %HL%\Azure Sheep True First Person.exe
goto :done
:nolauncher
call :say Warning: the launcher exe was not made - start the mod with hl.exe -game fpbody_asheep
:done

echo.
call :say SUCCESS: Azure Sheep: True First Person is in %MOD%
call :say Start it with "Azure Sheep True First Person.exe" in your Half-Life folder, or restart Steam
call :say and launch "Azure Sheep: True First Person".
goto :end

:failed
echo.
type "%LOG%" | findstr /i /c:"error" /c:"CMake Error" /c:"failed"
call :say BUILD FAILED. The full log is %LOG% - tell Claude.

:end
echo.
pause
exit /b

:say
echo %*
echo %* >> "%LOG%"
exit /b
