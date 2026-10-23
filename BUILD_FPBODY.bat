@echo off
setlocal
rem Builds the True First Person client.dll (Release | Win32) with your installed Visual Studio.
cd /d "%~dp0"

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

rem Unknown/newer version: use the highest toolset installed for Win32
if defined TOOLSET goto :havetoolset
for %%d in ("%MSBUILD%\..\..\..") do set "MSBROOT=%%~fd"
for /f "delims=" %%t in ('dir /b /ad /on "%MSBROOT%\Microsoft\VC\v*" 2^>nul') do set "VCDIR=%%t"
for /f "delims=" %%t in ('dir /b /ad /on "%MSBROOT%\Microsoft\VC\%VCDIR%\Platforms\Win32\PlatformToolsets\v1??" 2^>nul') do set "TOOLSET=%%t"
if not defined TOOLSET set "TOOLSET=v145"
:havetoolset

echo Using: %MSBUILD%
echo Toolset: %TOOLSET%
echo.
"%MSBUILD%" "projects\vs2019\hl_cdll.vcxproj" /p:Configuration=Release /p:Platform=Win32 /p:PlatformToolset=%TOOLSET% /m /nologo /v:minimal
if errorlevel 1 (
  echo.
  echo BUILD FAILED. Copy the error lines above and paste them to Claude.
  goto :end
)

rem Make sure the DLL is in this repository's mod folder
if not exist "fpbody\cl_dlls" mkdir "fpbody\cl_dlls"
copy /y "projects\vs2019\Release\hl_cdll\client.dll" "fpbody\cl_dlls\client.dll" >nul
echo.
if exist "fpbody\cl_dlls\client.dll" (
  echo SUCCESS: client.dll is in fpbody\cl_dlls\
  echo Copy the fpbody folder into your Half-Life folder, next to valve,
  echo add valve\dlls\hl.dll to fpbody\dlls, then run hl.exe -game fpbody
) else (
  echo Build finished, but client.dll was not found in projects\vs2019\Release\hl_cdll\
)

:end
echo.
pause
