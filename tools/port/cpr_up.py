"""Helping up after CPR, and the downed camera.

  python3 cpr_up.py <hlsdk dir> <sdk dir> [...]          (idempotent)

dlls/fpbody_buddy.inl  copied from hlsdk (the reviver helps the patient up:
                       the scientist's cprscientistrevive; FPDown state 4)
cl_dll/fpbody_anim.cpp state 4 plays fm_cpr_up; the get-up from a quarter in;
                       FPAnim_DownedWeight
cl_dll/fpbody_anim.h   FPAnim_DownedWeight
cl_dll/fpbody.cpp      downed: the camera at the face (not out over the chest)
"""
import shutil
import sys


def rd(p):
    s = open(p, encoding='latin-1', newline='').read()
    return s.replace('\r\n', '\n'), ('\r\n' if '\r\n' in s else '\n')


def wr(p, s, nl):
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))


def rep(s, old, new, p):
    if old not in s:
        sys.exit('not found in %s: %r' % (p, old[:70]))
    return s.replace(old, new, 1)


GETUP_OLD = '''			 StartOverlayKind( "fm_down_up", OVK_MOVE, 5.0f ) )
		{
			g_ovStart -= 0.45f * g_ovDur;		// past the lying part
			oneShot = true;
		}
		prev = g_fpDown;'''
GETUP_NEW = '''			 StartOverlayKind( "fm_down_up", OVK_MOVE, 5.5f ) )
		{
			g_ovStart -= 0.25f * g_ovDur;		// past the lying still (as the companion's)
			oneShot = true;
		}
		// the CPR worked: help him up (the scientist's), in step with his getting up
		if ( g_fpDown == 4 && prev != 4 && FindSeq( g_playerHdr, "fm_cpr_up" ) >= 0 &&
			 StartOverlayKind( "fm_cpr_up", OVK_MOVE, 5.15f ) )
		{
			g_ovStart -= 0.25f * g_ovDur;
			oneShot = true;
		}
		prev = g_fpDown;'''
MSG_OLD = '''	g_fpDown = ( iSize > 0 && pbuf ) ? *(const unsigned char *)pbuf : 0;
	return 1;
}
'''
MSG_NEW = MSG_OLD + '''
// the camera while you're down: 0..1 (eased), lying on your back or getting up
float FPAnim_DownedWeight( void )
{
	static float w = 0.0f, last = -1.0f;
	float now = gEngfuncs.GetClientTime();
	bool on = g_fpDown == 1 || g_fpDown == 2 || ( g_ovSeq >= 0 && OverlayIs( "fm_down_up" ) &&
			  g_ovDur > 0.0f && ( now - g_ovStart ) / g_ovDur < 0.6f );
	float dt = ( last < 0.0f || now < last ) ? 0.0f : Clamp( now - last, 0.0f, 0.1f );
	last = now;
	w += ( ( on ? 1.0f : 0.0f ) - w ) * Clamp01( dt * 5.0f );
	return w;
}
'''
CAM = '''	// downed, on your back: the head is behind the body, so the usual offset
	// out in front of the face (along the view) goes into the chest - the
	// face looks up, the eyes go up off the head instead
	{
		float dw = FPAnim_DownedWeight();
		if ( dw > 0.001f )
		{
			fwd *= 1.0f - dw;
			upOfs += 4.0f * dw;
		}
	}

'''
CAM_AT = '''	Vector target;
	for ( int i = 0; i < 3; i++ )
	{
		target[ i ] = pparams->simorg[ i ] + rel[ i ]'''

hl = sys.argv[1]
for d in sys.argv[2:]:
    if d != hl:
        shutil.copy(hl + '/dlls/fpbody_buddy.inl', d + '/dlls/fpbody_buddy.inl')
    p = d + '/cl_dll/fpbody_anim.cpp'
    s, nl = rd(p)
    if 'FPAnim_DownedWeight' not in s:
        s = rep(s, GETUP_OLD, GETUP_NEW, p)
        s = rep(s, MSG_OLD, MSG_NEW, p)
        s = s.replace('3 you give the companion CPR\n', '3 you give the companion CPR, 4 you help him up\n', 1)
    wr(p, s, nl)
    p = d + '/cl_dll/fpbody_anim.h'
    s, nl = rd(p)
    if 'FPAnim_DownedWeight' not in s:
        old = 'float FPAnim_HunchWeight( void );'
        if old not in s:
            sys.exit('hunch decl: ' + p)
        i = s.index('\n', s.index(old)) + 1
        s = s[:i] + 'float FPAnim_DownedWeight( void );\t// 0..1 lying downed: the camera at the face, not out over the chest\n' + s[i:]
    wr(p, s, nl)
    p = d + '/cl_dll/fpbody.cpp'
    s, nl = rd(p)
    if 'FPAnim_DownedWeight' not in s:
        s = rep(s, CAM_AT, CAM + CAM_AT, p)
    wr(p, s, nl)
    print('ok', d)
