@echo off
setlocal
rem Builds "Opposing Force: True First Person" (client.dll + hl.dll, Release | Win32)
rem with your installed Visual Studio into the fpbody_op4 mod folder.
rem Put this SDK folder (fpbody_op4_sdk) in your Half-Life folder, next to gearbox.
cd /d "%~dp0"
set "MOD=%~dp0..\fpbody_op4"

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

echo.
echo SUCCESS: Opposing Force: True First Person is in %MOD%
echo Restart Steam and launch "Opposing Force: True First Person", or run hl.exe -game fpbody_op4
goto :end

:failed
echo.
echo BUILD FAILED. Copy the error lines above and paste them to Claude.

:end
echo.
pause
