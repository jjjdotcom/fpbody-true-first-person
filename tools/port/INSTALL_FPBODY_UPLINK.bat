@echo off
setlocal
rem Sets up "Uplink Extended: True First Person" (fpbody_uplink): The Mighty
rem Atom's Half-Life: Uplink Extended 1.1 (five maps remaking the Uplink demo)
rem played with Half-Life: True First Person's body, animations and companion.
rem Put this file in your Half-Life folder and run it after BUILD_FPBODY.bat
rem (the fpbody game code knows Uplink Extended's zombie guard, zombie soldier
rem and env_model). Uplink Extended itself is looked for in
rem .Maps\hl_uplink_ext_11\uplink_ext or uplink_ext. Run it again after
rem rebuilding Half-Life: True First Person to bring its new DLLs and models over.
cd /d "%~dp0"
set "HL=%CD%"
set "MOD=%HL%\fpbody_uplink"
set "LOG=%HL%\fpbody_uplink_install.log"
echo INSTALL_FPBODY_UPLINK %DATE% %TIME% > "%LOG%"

set "SRC=%HL%\.Maps\hl_uplink_ext_11\uplink_ext"
if not exist "%SRC%\maps\uplink_ext1.bsp" set "SRC=%HL%\uplink_ext"
if not exist "%SRC%\maps\uplink_ext1.bsp" (
  call :say Uplink Extended was not found - looked in .Maps\hl_uplink_ext_11\uplink_ext and uplink_ext
  goto :end
)
if not exist "%HL%\fpbody\dlls\hl.dll" (
  call :say Half-Life: True First Person - the fpbody folder - is not built. Run fpbody_sdk\BUILD_FPBODY.bat first.
  goto :end
)
if not exist "%HL%\fpbody\cl_dlls\client.dll" (
  call :say fpbody\cl_dlls\client.dll is missing. Run fpbody_sdk\BUILD_FPBODY.bat first.
  goto :end
)
call :say Uplink Extended: %SRC%

if not exist "%MOD%\dlls" mkdir "%MOD%\dlls"
if not exist "%MOD%\cl_dlls" mkdir "%MOD%\cl_dlls"
rem The game code: True First Person's - not Uplink Extended's own DLLs
copy /y "%HL%\fpbody\dlls\hl.dll" "%MOD%\dlls\" >> "%LOG%" 2>&1
if errorlevel 1 (
  call :say Could not copy hl.dll - is the game still running?
  goto :end
)
copy /y "%HL%\fpbody\cl_dlls\client.dll" "%MOD%\cl_dlls\" >> "%LOG%" 2>&1
if errorlevel 1 (
  call :say Could not copy client.dll - is the game still running?
  goto :end
)
rem The body models, weapons and settings from Half-Life: True First Person
robocopy "%HL%\fpbody\models" "%MOD%\models" /E /NFL /NDL /NJH /NJS >> "%LOG%" 2>&1
copy /y "%HL%\fpbody\delta.lst" "%MOD%\" >nul
if exist "%HL%\fpbody\skill.cfg" copy /y "%HL%\fpbody\skill.cfg" "%MOD%\" >nul
if not exist "%MOD%\autoexec.cfg" if exist "%HL%\fpbody\autoexec.cfg" copy /y "%HL%\fpbody\autoexec.cfg" "%MOD%\" >nul
if not exist "%MOD%\fpbody_grips.cfg" if exist "%HL%\fpbody\fpbody_grips.cfg" copy /y "%HL%\fpbody\fpbody_grips.cfg" "%MOD%\" >nul
if not exist "%MOD%\fpbody_guns.cfg" if exist "%HL%\fpbody\fpbody_guns.cfg" copy /y "%HL%\fpbody\fpbody_guns.cfg" "%MOD%\" >nul
rem the HD and add-on models of Half-Life: True First Person, for the same look
if exist "%HL%\fpbody_hd\models" robocopy "%HL%\fpbody_hd\models" "%HL%\fpbody_uplink_hd\models" /E /NFL /NDL /NJH /NJS >> "%LOG%" 2>&1
for %%d in (models sprites sound) do if exist "%HL%\fpbody_addon\%%d" robocopy "%HL%\fpbody_addon\%%d" "%HL%\fpbody_uplink_addon\%%d" /E /NFL /NDL /NJH /NJS >> "%LOG%" 2>&1
rem Uplink Extended's maps, models, sounds, textures and menu art (its own
rem ones win over Half-Life's here, as in Uplink Extended)
robocopy "%SRC%" "%MOD%" /E /XD dlls cl_dlls /XF liblist.gam *.dll /NFL /NDL /NJH /NJS >> "%LOG%" 2>&1

(
  echo game "Uplink Extended: True First Person"
  echo version "1.1"
  echo startmap "uplink_ext1"
  echo trainmap "t0a0"
  echo type "singleplayer_only"
  echo gamedll "dlls\hl.dll"
  echo gamedll_linux "dlls/hl.so"
  echo cldll "1"
  echo icon "resource\hlue"
  echo developer "The Mighty Atom - Uplink Extended"
) > "%MOD%\liblist.gam"
call :say liblist.gam written

echo.
call :say SUCCESS: Uplink Extended: True First Person is in %MOD%
call :say Restart Steam and launch "Uplink Extended: True First Person", or run hl.exe -game fpbody_uplink
call :say New Game starts at uplink_ext1.
goto :end

:end
echo.
pause
exit /b

:say
echo %*
echo %* >> "%LOG%"
exit /b
