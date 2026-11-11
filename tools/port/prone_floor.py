"""Prone back on, with the camera kept off the floor.

  python3 prone_floor.py <sdk dir> [...]          (idempotent)

pm_shared/fpbody_pm.h   FPM_ENABLE_PRONE 1 (pm_prone, double-tap duck)
cl_dll/fpbody.cpp       the camera follows the head; lying down (and looking
                        down, which bends the spine) the head comes within the
                        view's near plane of the floor and you saw through it.
                        The camera now stays at least cl_fpbody_floorclear
                        (default 10) units above the floor under it.
"""
import sys

CLAMP = '''	// Keep the eyes off the floor: lying down (and looking down, which bends the
	// spine) the head comes within the view's near plane (4 units) of the floor
	// and the view would cut through it. Stay cl_fpbody_floorclear above it.
	{
		static cvar_t *clear;
		if ( !clear )
			clear = gEngfuncs.pfnRegisterVariable( "cl_fpbody_floorclear", "10", FCVAR_ARCHIVE );
		float c = clear ? clear->value : 10.0f;
		if ( c > 0.0f )
		{
			Vector below = target;
			below[ 2 ] -= c;
			pmtrace_t ftr;
			gEngfuncs.pEventAPI->EV_SetUpPlayerPrediction( false, true );
			gEngfuncs.pEventAPI->EV_PushPMStates();
			gEngfuncs.pEventAPI->EV_SetSolidPlayers( -1 );
			gEngfuncs.pEventAPI->EV_SetTraceHull( 2 );	// point hull
			gEngfuncs.pEventAPI->EV_PlayerTrace( target, below, PM_WORLD_ONLY, -1, &ftr );
			gEngfuncs.pEventAPI->EV_PopPMStates();
			if ( !ftr.startsolid && ftr.fraction < 1.0f && ftr.plane.normal[ 2 ] > 0.5f )
			{
				float z = ftr.endpos[ 2 ] + c;
				if ( z > eye[ 2 ] )
					z = eye[ 2 ];				// never above the normal eye height
				if ( target[ 2 ] < z )
					target[ 2 ] = z;
			}
		}
	}

'''

for d in sys.argv[1:]:
    p = d + '/pm_shared/fpbody_pm.h'
    s = open(p, encoding='latin-1', newline='').read()
    s = s.replace('#define FPM_ENABLE_PRONE\t0', '#define FPM_ENABLE_PRONE\t1')
    s = s.replace('// Moves that are switched off (1 = on): prone (pm_prone, double-tap duck) and',
                  '// Moves that can be switched off (1 = on): prone (pm_prone, double-tap duck) and')
    open(p, 'w', encoding='latin-1', newline='').write(s)

    p = d + '/cl_dll/fpbody.cpp'
    s = open(p, encoding='latin-1', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    s = s.replace('\r\n', '\n')
    if 'cl_fpbody_floorclear' not in s:
        old = '\t\tVectorCopy( eye, target );\n\t}\n\n\tVectorCopy( target, outOrigin );\n'
        if s.count(old) != 1:
            sys.exit('fpbody.cpp: ' + p)
        s = s.replace(old, old.replace('\tVectorCopy( target, outOrigin );\n', CLAMP + '\tVectorCopy( target, outOrigin );\n'))
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))
    print('ok', d)
