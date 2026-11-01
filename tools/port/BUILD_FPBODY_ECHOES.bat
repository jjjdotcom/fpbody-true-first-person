@echo off
setlocal
rem Builds "Echoes: True First Person" (client.dll + echoes.dll, Release | Win32)
rem with your installed Visual Studio and CMake, and sets up the fpbody_echoes
rem mod folder. Put this SDK folder (fpbody_echoes_sdk) in your Half-Life folder,
rem next to the echoes folder (Half-Life: Echoes must be installed there).
cd /d "%~dp0"
for %%d in ("%~dp0..") do set "HL=%%~fd"
set "MOD=%HL%\fpbody_echoes"
set "GAME=%HL%\echoes"

if not exist "%GAME%\liblist.gam" (
  echo Half-Life: Echoes is not installed in %GAME%
  echo Install Echoes there first ^(its folder must be called "echoes"^), then run this again.
  goto :end
)

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
  echo Could not find vswhere.exe. Is Visual Studio installed?
  goto :end
)

rem CMake: the one that comes with Visual Studio, else one on the PATH
set "CMAKE="
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -find Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe`) do set "CMAKE=%%i"
if not defined CMAKE for /f "delims=" %%i in ('where cmake 2^>nul') do if not defined CMAKE set "CMAKE=%%i"
if not defined CMAKE (
  echo Could not find CMake. In Visual Studio Installer, modify your Visual Studio and tick
  echo "C++ CMake tools for Windows" ^(under Desktop development with C++^), then run this again.
  goto :end
)
echo Using: %CMAKE%
echo.

"%CMAKE%" -A Win32 -B build -DCMAKE_INSTALL_PREFIX="%HL%"
if errorlevel 1 goto :failed
"%CMAKE%" --build build --config Release --parallel
if errorlevel 1 goto :failed
"%CMAKE%" --install build --config Release
if errorlevel 1 goto :failed

if not exist "%MOD%\cl_dlls\client.dll" (
  echo Build finished, but client.dll was not copied to %MOD%\cl_dlls
  goto :end
)

rem The mod folder: Echoes' own liblist.gam with our DLL and Echoes as the fallback
rem (its maps, sounds and models come from the echoes folder)
echo.
echo Setting up %MOD% ...
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
echo liblist.gam written

rem The body models and the network settings come from the Half-Life mod (fpbody)
if not exist "%HL%\fpbody\models\player.mdl" (
  echo The fpbody folder ^(Half-Life: True First Person^) is missing its models - install that first.
  goto :end
)
if not exist "%MOD%\models" mkdir "%MOD%\models"
copy /y "%HL%\fpbody\models\player.mdl" "%MOD%\models\" >nul
copy /y "%HL%\fpbody\models\fpbody_*.mdl" "%MOD%\models\" >nul
copy /y "%HL%\fpbody\models\p_*.mdl" "%MOD%\models\" >nul
copy /y "%HL%\fpbody\delta.lst" "%MOD%\" >nul
rem your settings: copied once, then they're the Echoes mod's own
if not exist "%MOD%\autoexec.cfg" copy /y "%HL%\fpbody\autoexec.cfg" "%MOD%\" >nul
if not exist "%MOD%\fpbody_grips.cfg" if exist "%HL%\fpbody\fpbody_grips.cfg" copy /y "%HL%\fpbody\fpbody_grips.cfg" "%MOD%\" >nul
if not exist "%MOD%\fpbody_guns.cfg" if exist "%HL%\fpbody\fpbody_guns.cfg" copy /y "%HL%\fpbody\fpbody_guns.cfg" "%MOD%\" >nul

echo.
echo SUCCESS: Echoes: True First Person is in %MOD%
echo Restart Steam and launch "Echoes: True First Person", or run hl.exe -game fpbody_echoes
goto :end

:failed
echo.
echo BUILD FAILED. Copy the error lines above and paste them to Claude.

:end
echo.
pause
