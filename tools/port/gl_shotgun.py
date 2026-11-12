"""The 9mmAR grenade launcher reload: Garry's Mod's shotgun reload.

  python3 gl_shotgun.py <sdk dir> [...]          (idempotent)

cl_dll/fpbody_anim.cpp  after each grenade, a Garry's Mod player model plays
  gm_reload_shotgun (the shell pushed in, then the pump: the grenade into the
  tube, the breech shut) instead of the procedural launcher reload; classic
  models keep the procedural one
"""
import sys

OLD = '''		g_glReloadAt = 0.0f;
		if ( g_ovSeq < 0 )
		{
			StartClip( CLIP_RELOAD, 1, 1.0f, 1.3f );
			g_mvActivity = g_now;
		}'''
NEW = '''		g_glReloadAt = 0.0f;
		if ( g_ovSeq < 0 )
		{
			// a Garry's Mod model: its shotgun reload (the shell pushed in, the pump)
			if ( g_bGmodModel && g_playerHdr && cl_fpbody_gmod->value != 0.0f && !MoveBusy() &&
				 FindSeq( g_playerHdr, "gm_reload_shotgun" ) >= 0 && StartOverlay( "gm_reload_shotgun", false, 1.8f ) )
			{
				g_ovLoop = false;
				StartClip( CLIP_NONE, 0, 0.0f, 0.0f );
			}
			else
				StartClip( CLIP_RELOAD, 1, 1.0f, 1.3f );
			g_mvActivity = g_now;
		}'''

for d in sys.argv[1:]:
    p = d + '/cl_dll/fpbody_anim.cpp'
    raw = open(p, encoding='latin-1', newline='').read()
    nl = '\r\n' if '\r\n' in raw else '\n'
    s = raw.replace('\r\n', '\n')
    if 'StartOverlay( "gm_reload_shotgun", false, 1.8f )' not in s:
        if OLD not in s:
            sys.exit('not found: ' + p)
        s = s.replace(OLD, NEW, 1)
        s = s.replace('//   cl_fpbody_glreload  1    reload the 9mmAR grenade launcher after every shot (body animation)',
                      '//   cl_fpbody_glreload  1    reload the 9mmAR grenade launcher after every shot (Garry\'s Mod models: its shotgun reload)', 1)
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))
    print('ok', d)
