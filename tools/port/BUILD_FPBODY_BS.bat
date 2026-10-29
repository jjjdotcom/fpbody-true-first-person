@echo off
setlocal
rem Builds "Blue Shift: True First Person" (client.dll + hl.dll, Release | Win32)
rem with your installed Visual Studio and sets up the fpbody_bs mod folder.
rem Put this SDK folder (fpbody_bs_sdk) in your Half-Life folder, next to bshift.
cd /d "%~dp0"
set "MOD=%~dp0..\fpbody_bs"
set "GAME=%~dp0..\bshift"

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
  echo Could not find vswhere.exe. Is Visual Studio installed?
  goto :end
)

for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.Component.MSBuild -find MSBuild\**\Bin\MSBuild.exe`) do set "MSBUILD=%%i"
if not defined MSBUILD (
  echo Could not find MSBuild. Install the "Desktop development with C++" workload in Visual Studio Installer.
  goto :end
)

rem Pick the C++ toolset that matches this Visual Studio version
rem (VS 2019 = 16 = v142, VS 2022 = 17 = v143, VS 2026 = 18 = v145)
set "TOOLSET="
for /f "usebackq tokens=1 delims=." %%v in (`"%VSWHERE%" -latest -products * -requires Microsoft.Component.MSBuild -property installationVersion`) do set "VSMAJOR=%%v"
if "%VSMAJOR%"=="16" set "TOOLSET=v142"
if "%VSMAJOR%"=="17" set "TOOLSET=v143"
if "%VSMAJOR%"=="18" set "TOOLSET=v145"

if defined TOOLSET goto :havetoolset
for %%d in ("%MSBUILD%\..\..\..") do set "MSBROOT=%%~fd"
for /f "delims=" %%t in ('dir /b /ad /on "%MSBROOT%\Microsoft\VC\v*" 2^>nul') do set "VCDIR=%%t"
for /f "delims=" %%t in ('dir /b /ad /on "%MSBROOT%\Microsoft\VC\%VCDIR%\Platforms\Win32\PlatformToolsets\v1??" 2^>nul') do set "TOOLSET=%%t"
if not defined TOOLSET set "TOOLSET=v145"
:havetoolset

echo Using: %MSBUILD%
echo Toolset: %TOOLSET%
echo.
for %%p in (hl_cdll hldll) do (
  echo Building %%p ...
  "%MSBUILD%" "projects\vs2019\%%p.vcxproj" /p:Configuration=Release /p:Platform=Win32 /p:PlatformToolset=%TOOLSET% /m /nologo /v:minimal
  if errorlevel 1 goto :failed
)

if not exist "%MOD%\cl_dlls\client.dll" (
  echo Build finished, but client.dll was not copied to %MOD%\cl_dlls
  goto :end
)
if not exist "%MOD%\dlls\hl.dll" (
  echo Build finished, but hl.dll was not copied to %MOD%\dlls
  goto :end
)

rem Blue Shift's maps store their first two BSP lumps in swapped order, which
rem only the original bshift folder understands. Copy them into the mod with
rem the standard order (the same change as Blue Shift Updated's installer).
echo.
echo Converting Blue Shift maps ...
if not exist "%MOD%\maps" mkdir "%MOD%\maps"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$src = Join-Path $env:GAME 'maps'; $dst = Join-Path $env:MOD 'maps'; $n = 0;" ^
  "Get-ChildItem -Path $src -Filter *.bsp | ForEach-Object {" ^
  "  $b = [IO.File]::ReadAllBytes($_.FullName);" ^
  "  $off1 = [BitConverter]::ToInt32($b, 12);" ^
  "  if ($b[$off1] -eq 123) { $t = New-Object byte[] 8; [Array]::Copy($b, 4, $t, 0, 8); [Array]::Copy($b, 12, $b, 4, 8); [Array]::Copy($t, 0, $b, 12, 8) }" ^
  "  [IO.File]::WriteAllBytes((Join-Path $dst $_.Name), $b); $n++ };" ^
  "Write-Host ([string]$n + ' maps converted')"
if errorlevel 1 (
  echo Map conversion failed.
  goto :end
)

echo.
echo SUCCESS: Blue Shift: True First Person is in %MOD%
echo Restart Steam and launch "Blue Shift: True First Person", or run hl.exe -game fpbody_bs
goto :end

:failed
echo.
echo BUILD FAILED. Copy the error lines above and paste them to Claude.

:end
echo.
pause
