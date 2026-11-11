"""A still camera through a hard landing; swimming with the gun in one hand.

  python3 land_swim.py <sdk dir> [...]          (idempotent)

cl_dll/fpbody_anim.cpp / .h
  cl_fpbody_fixedcam 1: while the hard landing (fm_hardland) or the landing
    roll (fm_roll) plays, the camera stays at eye height instead of following
    the head down and round (FPAnim_FixedCamWeight, eased in and out)
  cl_fpbody_swimarm 1: swimming with a gun, the right hand holds it and the
    left arm swims (the swim's strokes on the left arm, FPAnim_SwimOneArm /
    FPAnim_LeftArmBone; the left hand lets go of the gun)
cl_dll/fpbody.cpp            the camera blends to eye height by that weight
cl_dll/StudioModelRenderer.cpp  the gait (swim) also drives the left arm
"""
import re
import sys

H_ADD = '''float FPAnim_FixedCamWeight( void );	// 0..1 while a hard landing / roll plays: the camera stays at eye height
int FPAnim_SwimOneArm( int entindex );	// swimming with a gun: the left arm swims (the gait drives it)
int FPAnim_LeftArmBone( const char *name );
'''

FUNCS = '''
// cl_fpbody_fixedcam: a hard landing / landing roll keeps the camera at eye
// height (it doesn't follow the head down and round); eased in and out
float FPAnim_FixedCamWeight( void )
{
	static cvar_t *fixed;
	if ( !fixed )
		fixed = gEngfuncs.pfnRegisterVariable( "cl_fpbody_fixedcam", "1", FCVAR_ARCHIVE );
	static float w = 0.0f, last = -1.0f;
	float now = gEngfuncs.GetClientTime();
	bool on = fixed && fixed->value != 0.0f && g_ovSeq >= 0 && g_ovKind == OVK_MOVE &&
			  ( OverlayIs( "fm_hardland" ) || OverlayIs( "fm_roll" ) );
	float dt = ( last < 0.0f || now < last ) ? 0.0f : Clamp( now - last, 0.0f, 0.1f );
	last = now;
	w += ( ( on ? 1.0f : 0.0f ) - w ) * Clamp01( dt * ( on ? 14.0f : 4.0f ) );
	return w;
}

// swimming with a gun (cl_fpbody_swimarm): the right hand holds it, the left
// arm swims - the renderer lets the swim (the gait) drive the left arm too
int FPAnim_SwimOneArm( int entindex )
{
	cl_entity_t *local = gEngfuncs.GetLocalPlayer();
	return ( g_swimOneArm && local && entindex == local->index ) ? 1 : 0;
}

int FPAnim_LeftArmBone( const char *name )
{
	if ( strncmp( name, "Bip01 L ", 8 ) )
		return 0;
	return !strstr( name, "Leg" ) && !strstr( name, "Foot" ) && !strstr( name, "Toe" ) && !strstr( name, "Thigh" ) &&
		   !strstr( name, "Calf" );
}
'''

CAM = '''	// a hard landing / landing roll: the camera stays at eye height
	// (cl_fpbody_fixedcam) instead of following the head down and round
	{
		float fw = FPAnim_FixedCamWeight();
		if ( fw > 0.001f )
			for ( int i = 0; i < 3; i++ )
				target[ i ] += ( pparams->simorg[ i ] + pparams->viewheight[ i ] - target[ i ] ) * fw;
	}

'''


def rd(p):
    s = open(p, encoding='latin-1', newline='').read()
    return s.replace('\r\n', '\n'), ('\r\n' if '\r\n' in s else '\n')


def wr(p, s, nl):
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))


def need(s, old, p):
    if old not in s:
        sys.exit('not found in %s: %r' % (p, old[:60]))


for d in sys.argv[1:]:
    p = d + '/cl_dll/fpbody_anim.h'
    s, nl = rd(p)
    if 'FPAnim_FixedCamWeight' not in s:
        old = 'float FPAnim_HunchWeight( void );'
        need(s, old, p)
        i = s.index('\n', s.index(old)) + 1
        s = s[:i] + H_ADD + s[i:]
    wr(p, s, nl)

    p = d + '/cl_dll/fpbody_anim.cpp'
    s, nl = rd(p)
    if 'FPAnim_FixedCamWeight' not in s:
        old = 'static cvar_t *cl_fpbody_swimhold;\n'
        need(s, old, p)
        s = s.replace(old, old + 'static cvar_t *cl_fpbody_swimarm;\nstatic bool g_swimOneArm;\t\t\t// swimming with a gun, the left arm swims\n', 1)
        m = re.search(r'\n(\s*)cl_fpbody_swimhold\s*=\s*gEngfuncs\.pfnRegisterVariable\( "cl_fpbody_swimhold", "1", FCVAR_ARCHIVE \);\n', s)
        if not m:
            sys.exit('swimhold register: ' + p)
        s = s[:m.end()] + m.group(1) + 'cl_fpbody_swimarm = gEngfuncs.pfnRegisterVariable( "cl_fpbody_swimarm", "1", FCVAR_ARCHIVE );\n' + s[m.end():]
        old = 'static bool OffHandBusy( float now )\n{\n'
        need(s, old, p)
        s = s.replace(old, old + '\tif ( g_swimOneArm )\n\t\treturn true;\t\t\t\t// swimming: the left arm strokes\n', 1)
        old = '\tif ( !from || !to || !local || entindex != local->index || srvSeq < 0 || srvSeq >= from->numseq )\n\t\treturn;\n'
        need(s, old, p)
        a = s.index('void FPAnim_SwimHold(')
        i = s.index(old, a) + len(old)
        s = s[:i] + '\tg_swimOneArm = false;\n' + s[i:]
        old = '\t*gait = *seq;\t\t\t// the swim kicks the legs\n'
        need(s, old, p)
        s = s.replace(old, old + '\tg_swimOneArm = cl_fpbody_swimarm && cl_fpbody_swimarm->value != 0.0f;\t// and the left arm swims\n', 1)
        old = 'int FPAnim_ActCamActive( void )\n'
        need(s, old, p)
        s = s.replace(old, FUNCS.lstrip('\n') + '\n' + old, 1)
        s = s.replace('//   cl_fpbody_swimhold', '//   cl_fpbody_swimarm   1    swimming with a gun: one hand holds it, the left arm swims\n'
                      '//   cl_fpbody_fixedcam  1    a hard landing / roll keeps the camera at eye height\n//   cl_fpbody_swimhold', 1)
    wr(p, s, nl)

    p = d + '/cl_dll/fpbody.cpp'
    s, nl = rd(p)
    if 'FPAnim_FixedCamWeight' not in s:
        old = '\t// Keep the eyes off the floor:'
        need(s, old, p)
        s = s.replace(old, CAM + old, 1)
    wr(p, s, nl)

    p = d + '/cl_dll/StudioModelRenderer.cpp'
    s, nl = rd(p)
    if 'FPAnim_SwimOneArm' not in s:
        m = re.search(r'StudioCalcRotations\(\s*pos2,\s*q2,\s*pseqdesc,\s*panim,\s*m_pPlayerInfo->gaitframe\s*\);\n', s)
        if not m:
            sys.exit('gait calc: ' + p)
        ind = re.match(r'[ \t]*', s[s.rfind('\n', 0, m.start()) + 1:]).group(0)
        s = s[:m.end()] + ind + 'int fpSwimArm = FPAnim_SwimOneArm( m_pCurrentEntity->index );\t// fpbody: swimming with a gun, the left arm swims\n' + s[m.end():]
        s, k = re.subn(r'if\s*\(\s*copy\s*\|\|\s*(?:0\s*!=\s*)?FPBody_WholeBodyGait\(\)\s*\)',
                       'if ( copy || FPBody_WholeBodyGait() || ( fpSwimArm && FPAnim_LeftArmBone( pbones[ i ].name ) ) )', s, count=1)
        if not k:
            sys.exit('gait copy: ' + p)
    wr(p, s, nl)
    print('ok', d)
