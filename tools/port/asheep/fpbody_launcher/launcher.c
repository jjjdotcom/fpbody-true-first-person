/* fpbody_launcher: starts Half-Life with a mod (the gamedir is set at build time).
   Put the exe in the Half-Life folder, next to hl.exe; extra arguments are passed on. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

#ifndef FPBODY_GAMEDIR
#define FPBODY_GAMEDIR "fpbody_asheep"
#endif

int WINAPI WinMain( HINSTANCE inst, HINSTANCE prev, LPSTR args, int show )
{
	char dir[ MAX_PATH ], exe[ MAX_PATH ], cmd[ 4096 ];
	char *slash;
	STARTUPINFOA si;
	PROCESS_INFORMATION pi;

	GetModuleFileNameA( NULL, dir, sizeof( dir ) );
	slash = strrchr( dir, '\\' );
	if( slash )
		*slash = 0;
	_snprintf( exe, sizeof( exe ), "%s\\hl.exe", dir );
	if( GetFileAttributesA( exe ) == INVALID_FILE_ATTRIBUTES )
	{
		MessageBoxA( NULL, "hl.exe was not found next to this launcher.\nPut it in your Half-Life folder.", "True First Person", MB_ICONERROR );
		return 1;
	}
	_snprintf( cmd, sizeof( cmd ), "\"%s\" -game " FPBODY_GAMEDIR " %s", exe, args ? args : "" );
	ZeroMemory( &si, sizeof( si ) );
	si.cb = sizeof( si );
	if( !CreateProcessA( exe, cmd, NULL, NULL, FALSE, 0, NULL, dir, &si, &pi ) )
	{
		MessageBoxA( NULL, "Could not start hl.exe.", "True First Person", MB_ICONERROR );
		return 1;
	}
	CloseHandle( pi.hThread );
	CloseHandle( pi.hProcess );
	return 0;
}
