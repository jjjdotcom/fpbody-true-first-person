@echo off
setlocal
rem Builds "Field Intensity: True First Person" (client.dll + hl.dll, Release | Win32)
rem with your installed Visual Studio and CMake, and sets up the fpbody_fi mod
rem folder. Put this SDK folder (fpbody_fi_sdk) in your Half-Life folder, next to
rem the field_intensity folder (Half-Life: Field Intensity must be installed there).
rem the Half-Life folder is the one this SDK folder sits in
cd /d "%~dp0.."
set "HL=%CD%"
cd /d "%~dp0"
set "MOD=%HL%\fpbody_fi"
set "GAME=%HL%\field_intensity"
rem everything is also written to this log (send it to Claude if something fails)
set "LOG=%HL%\fpbody_fi_build.log"
echo Field Intensity: True First Person build, %DATE% %TIME% >> "%LOG%"

if not exist "%GAME%\liblist.gam" (
  call :say Half-Life: Field Intensity is not installed in %GAME%
  call :say Install Field Intensity there first - its folder must be called field_intensity - then run this again.
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

call :say Configuring ...
"%CMAKE%" -A Win32 -B build -DCMAKE_INSTALL_PREFIX="%HL%" >> "%LOG%" 2>&1
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

rem The mod folder: Field Intensity's own liblist.gam with Field Intensity as the
rem fallback (its maps, sounds, models and settings come from the field_intensity folder)
echo.
call :say Setting up %MOD% ...
if not exist "%MOD%" mkdir "%MOD%"
(
  echo game "Field Intensity: True First Person"
  echo gamedir "fpbody_fi"
  echo fallback_dir "field_intensity"
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
rem the Half-Life guns you tuned, where Field Intensity has no model of its own
for %%f in ("%HL%\fpbody\models\p_*.mdl") do if not exist "%GAME%\models\%%~nxf" copy /y "%%f" "%MOD%\models\" >nul
rem Field Intensity's network settings, with room for the body's move state (fuser4)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$src = Join-Path $env:GAME 'delta.lst'; if (-not (Test-Path $src)) { $src = Join-Path $env:HL 'fpbody\delta.lst' }; (Get-Content $src) -replace 'DEFINE_DELTA\( fuser4, DT_SIGNED \| DT_FLOAT, \d+, [0-9.]+ \)', 'DEFINE_DELTA( fuser4, DT_SIGNED | DT_FLOAT, 24, 1.0 )' | Set-Content (Join-Path $env:MOD 'delta.lst') -Encoding ASCII" >> "%LOG%" 2>&1
findstr /c:"fuser4, DT_SIGNED | DT_FLOAT, 24" "%MOD%\delta.lst" >nul || call :say Warning: delta.lst was not updated - the move animations may not show.
rem your settings: copied once, then they're this mod's own
if not exist "%MOD%\autoexec.cfg" copy /y "%HL%\fpbody\autoexec.cfg" "%MOD%\" >nul
if not exist "%MOD%\fpbody_grips.cfg" if exist "%HL%\fpbody\fpbody_grips.cfg" copy /y "%HL%\fpbody\fpbody_grips.cfg" "%MOD%\" >nul
if not exist "%MOD%\fpbody_guns.cfg" if exist "%HL%\fpbody\fpbody_guns.cfg" copy /y "%HL%\fpbody\fpbody_guns.cfg" "%MOD%\" >nul

echo.
call :say SUCCESS: Field Intensity: True First Person is in %MOD%
call :say Restart Steam and launch "Field Intensity: True First Person", or run hl.exe -game fpbody_fi
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
