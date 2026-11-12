"""Downed / revived on the client; the hard landing's still camera taken out.

  python3 downed_client.py <sdk dir> [...]          (idempotent)

cl_dll/fpbody_anim.cpp  the FPDown message (dlls/fpbody_buddy.inl): lying on
                        your back (fm_down) while down or being revived, kneeling
                        at the companion's CPR (fm_cpr), getting up (the end of
                        fm_down_up) when it's over
cl_dll/fpbody.cpp / fpbody_anim.cpp / .h  cl_fpbody_fixedcam removed (the
                        hard landing follows the head again)
"""
import re
import sys


def rd(p):
    s = open(p, encoding='latin-1', newline='').read()
    return s.replace('\r\n', '\n'), ('\r\n' if '\r\n' in s else '\n')


def wr(p, s, nl):
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))


MSG = '''
// downed / revived (dlls/fpbody_buddy.inl, the FPDown message): 0 up, 1 down,
// 2 down and the companion's CPR, 3 you give the companion CPR
static int g_fpDown;
static int MsgFunc_FPDown( const char *pszName, int iSize, void *pbuf )
{
	g_fpDown = ( iSize > 0 && pbuf ) ? *(const unsigned char *)pbuf : 0;
	return 1;
}

'''

LOOPS_OLD = '''	// looping states
	const char *loop = NULL;
	float rate = 0.0f;
	if ( st & FPM_BARNACLE )
'''
LOOPS_NEW = '''	// downed: on your back until revived, then up (the end of the guard's
	// revive); giving the companion CPR: kneeling at it
	{
		static int prev;
		if ( ( prev == 1 || prev == 2 ) && !g_fpDown && FindSeq( g_playerHdr, "fm_down_up" ) >= 0 &&
			 StartOverlayKind( "fm_down_up", OVK_MOVE, 5.0f ) )
		{
			g_ovStart -= 0.45f * g_ovDur;		// past the lying part
			oneShot = true;
		}
		prev = g_fpDown;
	}

	// looping states
	const char *loop = NULL;
	float rate = 0.0f;
	if ( ( g_fpDown == 1 || g_fpDown == 2 ) && FindSeq( g_playerHdr, "fm_down" ) >= 0 )
		loop = "fm_down";
	else if ( g_fpDown == 3 && FindSeq( g_playerHdr, "fm_cpr" ) >= 0 )
		loop = "fm_cpr";
	else if ( st & FPM_BARNACLE )
'''

for d in sys.argv[1:]:
    p = d + '/cl_dll/fpbody_anim.cpp'
    s, nl = rd(p)
    if 'MsgFunc_FPDown' not in s:
        old = 'static void PM_KickCmd( void )\n{'
        assert old in s, p
        s = s.replace(old, MSG.lstrip('\n') + old, 1)
        old = '\tgEngfuncs.pfnAddCommand( "pm_kick", PM_KickCmd );\n'
        assert old in s, p
        s = s.replace(old, old + '\tgEngfuncs.pfnHookUserMsg( "FPDown", MsgFunc_FPDown );\t// downed / revived\n', 1)
        old = 'static bool g_swimOneArm;\t\t\t// swimming with a gun, the left arm swims\n'
        assert old in s, p
        s = s.replace(old, old + 'static int MsgFunc_FPDown( const char *pszName, int iSize, void *pbuf );\t// downed / revived\n', 1)
        assert LOOPS_OLD in s, p
        s = s.replace(LOOPS_OLD, LOOPS_NEW, 1)
        old = '\t\tg_mvLastDuck = g_mvLastReload = -10.0f; g_epaLastHurt = -100.0f;'
        assert old in s, p
        s = s.replace(old, old + ' g_fpDown = 0;', 1)
    # the hard landing's still camera: out
    a = s.find('// cl_fpbody_fixedcam: a hard landing / landing roll keeps the camera at eye')
    if a >= 0:
        b = s.index('\n}\n', a) + 3
        s = s[:a] + s[b:].lstrip('\n')
    s = s.replace('//   cl_fpbody_fixedcam  1    a hard landing / roll keeps the camera at eye height\n', '')
    wr(p, s, nl)

    p = d + '/cl_dll/fpbody_anim.h'
    s, nl = rd(p)
    s = re.sub(r'float FPAnim_FixedCamWeight\( void \);[^\n]*\n', '', s)
    wr(p, s, nl)

    p = d + '/cl_dll/fpbody.cpp'
    s, nl = rd(p)
    a = s.find('\t// a hard landing / landing roll: the camera stays at eye height\n')
    if a >= 0:
        b = s.index('\t}\n\n', a) + 4
        s = s[:a] + s[b:]
    assert 'FixedCamWeight' not in s, p
    wr(p, s, nl)
    print('ok', d)
