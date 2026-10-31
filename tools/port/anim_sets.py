"""Lets the server pick between the player models' Condition Zero and
Counter-Strike 1.6 weapon animations.

  python3 anim_sets.py <sdk folder>

sv_fpbody_anims "cz" (default) plays <stance>_<part>_<ext> as before; "cs"
plays cs_<stance>_<part>_<ext> when the player model has it (the fpbody classic
models do, see tools/gmod_anims/add_cs.py) and falls back to the plain one.
"""
import os
import re
import sys

HELPER = '''// fpbody: sv_fpbody_anims "cs" prefers the Counter-Strike 1.6 set (cs_<name>)
static int FPBody_LookupAnim( CBaseAnimating *ent, const char *name )
{
	const char *set = sv_fpbody_anims.string;
	if ( set && set[ 0 ] && strcmp( set, "cz" ) && strcmp( set, "0" ) )
	{
		char alt[ 80 ];
		snprintf( alt, sizeof( alt ), "%s_%s", set, name );
		int seq = ent->LookupSequence( alt );
		if ( seq >= 0 )
			return seq;
	}
	return ent->LookupSequence( name );
}

'''


def edit(path, fn):
    s = open(path, encoding='latin-1', newline='').read()
    if 'sv_fpbody_anims' in s:
        print('already patched', path)
        return
    nl = '\r\n' if '\r\n' in s else '\n'
    s2 = fn(s, nl)
    assert s2 != s, path
    open(path, 'w', encoding='latin-1', newline='').write(s2)
    print('patched', path)


def main(sdk):
    d = os.path.join(sdk, 'dlls')

    def game_cpp(s, nl):
        s = re.sub(r'(cvar_t sv_buddha = [^\n]*\n)', lambda m: m.group(1) +
                   'cvar_t sv_fpbody_anims = { "sv_fpbody_anims", "cz", FCVAR_ARCHIVE };\t// fpbody: cz / cs player weapon animations' + nl, s, count=1)
        return re.sub(r'(\n([ \t]*)CVAR_REGISTER\( ?&sv_buddha ?\);[^\n]*\n)',
                      lambda m: m.group(1) + m.group(2) + 'CVAR_REGISTER( &sv_fpbody_anims );' + nl, s, count=1)

    def game_h(s, nl):
        return re.sub(r'(extern cvar_t sv_buddha;[^\n]*\n)', lambda m: m.group(1) +
                      'extern cvar_t sv_fpbody_anims;\t// fpbody: cz / cs player weapon animations' + nl, s, count=1)

    def player_cpp(s, nl):
        s, n = re.subn(r'animDesired = LookupSequence\( ?szAnim ?\);', 'animDesired = FPBody_LookupAnim( this, szAnim );', s)
        assert n == 2, n
        i = s.index('void CBasePlayer::SetAnimation')
        return s[:i] + HELPER.replace('\n', nl) + s[i:]

    edit(os.path.join(d, 'game.cpp'), game_cpp)
    edit(os.path.join(d, 'game.h'), game_h)
    edit(os.path.join(d, 'player.cpp'), player_cpp)


if __name__ == '__main__':
    main(sys.argv[1])
