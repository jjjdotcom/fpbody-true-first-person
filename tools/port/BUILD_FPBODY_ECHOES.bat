@echo off
setlocal
rem Builds "Echoes: True First Person" (client.dll + echoes.dll, Release | Win32)
rem with your installed Visual Studio and CMake, and sets up the fpbody_echoes
rem mod folder. Put this SDK folder (fpbody_echoes_sdk) in your Half-Life folder,
rem next to the echoes folder (Half-Life: Echoes must be installed there).
rem the Half-Life folder is the one this SDK folder sits in
rem this folder, kept before any cd (the bat's own folder can come out wrong after a cd when it was started by a relative path)
set "SDK=%~dp0"
cd /d "%SDK%.."
set "HL=%CD%"
cd /d "%SDK%"
set "MOD=%HL%\fpbody_echoes"
set "GAME=%HL%\echoes"
rem everything is also written to this log (send it to Claude if something fails)
set "LOG=%HL%\fpbody_echoes_build.log"
echo Echoes: True First Person build, %DATE% %TIME% >> "%LOG%"

if not exist "%GAME%\liblist.gam" (
  call :say Half-Life: Echoes is not installed in %GAME%
  call :say Install Echoes there first - its folder must be called echoes - then run this again.
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

rem The mod folder: Echoes' own liblist.gam with our DLL and Echoes as the fallback
rem (its maps, sounds and models come from the echoes folder)
echo.
call :say Setting up %MOD% ...
if not exist "%MOD%" mkdir "%MOD%"
(
  echo game "Echoes: True First Person"
  echo gamedir "fpbody_echoes"
  echo fallback_dir "echoes"
  echo gamedll "dlls\echoes.dll"
  echo gamedll_linux "dlls/echoes.so"
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
rem Echoes' own outfits (the suit from RUIN on), kept next to this file in echoes_models
if exist "%SDK%echoes_models\*.mdl" copy /y "%SDK%echoes_models\*.mdl" "%MOD%\models\" >nul
copy /y "%HL%\fpbody\models\p_*.mdl" "%MOD%\models\" >nul
copy /y "%HL%\fpbody\delta.lst" "%MOD%\" >nul
rem your settings: copied once, then they're the Echoes mod's own
if not exist "%MOD%\autoexec.cfg" copy /y "%HL%\fpbody\autoexec.cfg" "%MOD%\" >nul
if not exist "%MOD%\fpbody_grips.cfg" if exist "%HL%\fpbody\fpbody_grips.cfg" copy /y "%HL%\fpbody\fpbody_grips.cfg" "%MOD%\" >nul
if not exist "%MOD%\fpbody_guns.cfg" if exist "%HL%\fpbody\fpbody_guns.cfg" copy /y "%HL%\fpbody\fpbody_guns.cfg" "%MOD%\" >nul

echo.
call :say SUCCESS: Echoes: True First Person is in %MOD%
call :say Restart Steam and launch "Echoes: True First Person", or run hl.exe -game fpbody_echoes
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
