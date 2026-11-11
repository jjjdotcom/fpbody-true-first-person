"""The companion doesn't block the player; Garry's Mod's per-weapon jumps.

  python3 buddy_jump.py <sdk dir> [...]          (idempotent)

dlls/game.cpp            sv_fpbody_buddy_solid 0 (1 = the companion blocks you again)
dlls/fpbody_buddy.inl    the companion carries iuser4 = FPB_PASSTHRU while not solid
pm_shared/pm_shared.c(pp) PM_Move leaves anything with iuser4 FPB_PASSTHRU out of
                         the player's collision (server and client prediction)
cl_dll/fpbody_anim.cpp   in the air, the body plays gm_jump_<hold> for the weapon
                         in your hands (tools/gmod_anims/add_jumps.py puts them in
                         the models), like Garry's Mod's jump_<hold type>
"""
import os
import re
import sys

PASS = '0x46504253'      # 'FPBS'


def rd(p):
    s = open(p, encoding='latin-1', newline='').read()
    return s.replace('\r\n', '\n'), ('\r\n' if '\r\n' in s else '\n')


def wr(p, s, nl):
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))


def game(p):
    s, nl = rd(p)
    if 'sv_fpbody_buddy_solid' not in s:
        s = re.sub(r'(cvar_t sv_fpbody_buddy = [^\n]*\n)',
                   lambda m: m.group(1) + 'cvar_t sv_fpbody_buddy_solid = { "sv_fpbody_buddy_solid", "0", FCVAR_ARCHIVE };'
                   '\t// fpbody: 1 = the companion blocks you (0: you walk through him)\n', s, count=1)
        s = re.sub(r'(\n(\s*)CVAR_REGISTER\( &sv_fpbody_buddy \);\n)',
                   lambda m: m.group(1) + m.group(2) + 'CVAR_REGISTER( &sv_fpbody_buddy_solid );\n', s, count=1)
        if s.count('sv_fpbody_buddy_solid') != 3:
            sys.exit('game.cpp: ' + p)
    wr(p, s, nl)


def buddy(p):
    s, nl = rd(p)
    if 'FPB_PASSTHRU' not in s:
        s = s.replace('extern cvar_t sv_fpbody_buddy;\n',
                      'extern cvar_t sv_fpbody_buddy;\n'
                      'extern cvar_t sv_fpbody_buddy_solid;\n'
                      '// iuser4 tag: pm_shared leaves the companion out of the player\'s collision\n'
                      '// (sv_fpbody_buddy_solid 0), so you walk through him\n'
                      '#define FPB_PASSTHRU\t' + PASS + '\n'
                      '#define FPB_SETSOLID()\t( pev->iuser4 = sv_fpbody_buddy_solid.value != 0 ? 0 : FPB_PASSTHRU )\n', 1)
        s = s.replace('void CFPBuddy::RunAI( void )\n{\n',
                      'void CFPBuddy::RunAI( void )\n{\n\tFPB_SETSOLID();\n', 1)
        s = s.replace('\tpev->takedamage = DAMAGE_NO;\t\t// invincible\n',
                      '\tpev->takedamage = DAMAGE_NO;\t\t// invincible\n\tFPB_SETSOLID();\n', 1)
        if s.count('FPB_SETSOLID()') != 3:
            sys.exit('buddy: ' + p)
    wr(p, s, nl)


PM = '''	// fpbody: the companion (iuser4 FPB_PASSTHRU, dlls/fpbody_buddy.inl) is left
	// out of the player's collision: walk through him
	{
		int i, n = 1;
		for ( i = 1; i < pmove->numphysent; i++ )
		{
			if ( pmove->physents[ i ].iuser4 == ''' + PASS + ''' )
				continue;
			if ( n != i )
				pmove->physents[ n ] = pmove->physents[ i ];
			n++;
		}
		if ( pmove->numphysent > 0 )
			pmove->numphysent = n;
	}

'''


def pm(p):
    s, nl = rd(p)
    if PASS not in s:
        m = re.search(r'\n\tpmove = ppmove;\n(?:[ \t]*\n)?', s[s.index('void PM_Move'):])
        if not m:
            sys.exit('pm: ' + p)
        at = s.index('void PM_Move') + m.end()
        s = s[:at] + PM + s[at:]
    wr(p, s, nl)


JUMP = '''	// in the air: Garry's Mod's jump for the weapon in your hands (jump_<hold
	// type>, as gm_jump_<hold> in the model: tools/gmod_anims/add_jumps.py);
	// empty hands its "normal" hold's, jump_slam
	if ( !stricmp( label, "jump" ) || !stricmp( label, "long_jump" ) )
	{
		static const char *jumps[][ 2 ] = {
			{ "crowbar", "melee" }, { "pipe_wrench", "melee" }, { "knife", "knife" }, { "onehanded", "revolver" },
			{ "python", "revolver" }, { "shotgun", "shotgun" }, { "mp5", "smg1" }, { "rifle", "smg1" },
			{ "m249", "ar2" }, { "saw", "ar2" }, { "sniper", "ar2" }, { "bow", "crossbow" }, { "rpg", "rpg" },
			{ "gauss", "physgun" }, { "egon", "physgun" }, { "displacer", "physgun" }, { "hive", "ar2" },
			{ "squeak", "grenade" }, { "penguin", "grenade" }, { "grenade", "grenade" }, { "trip", "slam" },
			{ "c4", "slam" }, { "bgrap", "pistol" },
		};
		const char *hold = "slam";
		if ( weaponmodel > 0 && g_lastHoldExt[ 0 ] && stricmp( g_lastHoldExt, "unarmed" ) )
		{
			hold = "smg1";
			for ( int i = 0; i < (int)( sizeof( jumps ) / sizeof( jumps[ 0 ] ) ); i++ )
				if ( !stricmp( g_lastHoldExt, jumps[ i ][ 0 ] ) )
					hold = jumps[ i ][ 1 ];
		}
		char want[ 48 ];
		snprintf( want, sizeof( want ), "gm_jump_%s", hold );
		int m = FindSeq( to, want );
		if ( m >= 0 )
			*seq = m;
		return;
	}
'''


def anim(p):
    s, nl = rd(p)
    if 'gm_jump_%s' not in s:
        old = '\tif ( weaponmodel <= 0 || !g_lastHoldExt[ 0 ] || !cl_fpbody_swimhold || cl_fpbody_swimhold->value == 0.0f )\n'
        if old not in s:
            sys.exit('anim: ' + p)
        s = s.replace(old, JUMP + old, 1)
    wr(p, s, nl)


for d in sys.argv[1:]:
    game(d + '/dlls/game.cpp')
    buddy(d + '/dlls/fpbody_buddy.inl')
    pm(next(d + '/pm_shared/' + f for f in ('pm_shared.c', 'pm_shared.cpp') if os.path.exists(d + '/pm_shared/' + f)))
    anim(d + '/cl_dll/fpbody_anim.cpp')
    print('ok', d)
