"""The prone camera floor clearance, round two (cl_dll/fpbody.cpp):

  python3 prone_floor2.py <sdk dir> [...]          (idempotent)

Looking straight ahead lying down, the head sits at about the floor: the first
version traced down from the head, which started inside the floor every other
frame (no lift) and the camera jumped 10 units up and down. Now the floor is
found from eye height, before the wall check, and the lift is eased.
"""
import sys

NEW = '\t// Keep the eyes off the floor: lying down (and looking down, which bends the\n\t// spine) the head comes within the view\'s near plane (4 units) of the floor\n\t// - or below it - and the view cuts through it. Find the floor under the\n\t// head from eye height (open space, so the trace can\'t start inside the\n\t// floor) and stay cl_fpbody_floorclear above it, before the wall check\n\t// below; the lift is eased so it doesn\'t jump between frames.\n\t{\n\t\tstatic cvar_t *clear;\n\t\tstatic float lift, liftTime;\n\t\tif ( !clear )\n\t\t\tclear = gEngfuncs.pfnRegisterVariable( "cl_fpbody_floorclear", "10", FCVAR_ARCHIVE );\n\t\tfloat c = clear ? clear->value : 10.0f;\n\t\tfloat want = 0.0f;\n\t\tif ( c > 0.0f )\n\t\t{\n\t\t\tfloat eyeZ = pparams->simorg[ 2 ] + pparams->viewheight[ 2 ];\n\t\t\tVector from( target[ 0 ], target[ 1 ], eyeZ );\n\t\t\tVector to( target[ 0 ], target[ 1 ], target[ 2 ] - c );\n\t\t\tif ( to[ 2 ] < from[ 2 ] )\n\t\t\t{\n\t\t\t\tpmtrace_t ftr;\n\t\t\t\tgEngfuncs.pEventAPI->EV_SetUpPlayerPrediction( false, true );\n\t\t\t\tgEngfuncs.pEventAPI->EV_PushPMStates();\n\t\t\t\tgEngfuncs.pEventAPI->EV_SetSolidPlayers( -1 );\n\t\t\t\tgEngfuncs.pEventAPI->EV_SetTraceHull( 2 );\t// point hull\n\t\t\t\tgEngfuncs.pEventAPI->EV_PlayerTrace( from, to, PM_WORLD_ONLY, -1, &ftr );\n\t\t\t\tgEngfuncs.pEventAPI->EV_PopPMStates();\n\t\t\t\tif ( !ftr.startsolid && ftr.fraction < 1.0f && ftr.plane.normal[ 2 ] > 0.5f )\n\t\t\t\t{\n\t\t\t\t\tfloat z = ftr.endpos[ 2 ] + c;\n\t\t\t\t\tif ( z > eyeZ )\n\t\t\t\t\t\tz = eyeZ;\t\t\t\t\t// never above the normal eye height\n\t\t\t\t\tif ( z > target[ 2 ] )\n\t\t\t\t\t\twant = z - target[ 2 ];\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t\tfloat dt = now - liftTime;\n\t\tliftTime = now;\n\t\tif ( dt < 0.0f || dt > 0.3f )\n\t\t\tlift = want;\n\t\telse if ( want > lift )\n\t\t\tlift += ( want - lift ) * ( 1.0f - (float)exp( -dt / 0.03f ) );\t// up quickly\n\t\telse\n\t\t\tlift += ( want - lift ) * ( 1.0f - (float)exp( -dt / 0.12f ) );\t// down gently\n\t\ttarget[ 2 ] += lift;\n\t}\n\n'

for d in sys.argv[1:]:
    p = d + '/cl_dll/fpbody.cpp'
    s = open(p, encoding='latin-1', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    s = s.replace('\r\n', '\n')
    if 'static float lift, liftTime;' not in s:
        if '\t// Keep the eyes off the floor:' in s:
            a = s.index('\t// Keep the eyes off the floor:')
            b = s.index('\tVectorCopy( target, outOrigin );\n', a)
            s = s[:a] + s[b:]
        w = "\t// Don't let the camera poke through walls:"
        if s.count(w) != 1:
            sys.exit('fpbody.cpp: ' + p)
        s = s.replace(w, NEW + w)
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))
    print('ok', d)
