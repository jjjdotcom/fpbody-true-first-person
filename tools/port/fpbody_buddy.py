"""The HEV companion (sv_fpbody_buddy): copy dlls/fpbody_buddy.inl into an SDK
and hook it in. Run after the fpbody port (apply_*.py / freeman_moves.py).

  python3 fpbody_buddy.py <sdk root> <classic|updated|fi>

classic: Valve's SDK and close relatives (Half-Life, Echoes, Azure Sheep);
updated: Half-Life Updated (Blue Shift, Opposing Force); fi: Featureful
(Field Intensity).
  dlls/barney.cpp   #include "fpbody_buddy.inl" (monster_fpbody_buddy)
  dlls/game.cpp     sv_fpbody_buddy (0 / 1, archived)
  dlls/client.cpp   ClientPrecache: FPBuddy_Precache()
  dlls/player.cpp   PostThink: FPBuddy_PlayerThink( this )
The model, models/fpbody_buddy.mdl, comes from tools/gmod_anims/make_buddy.py.
"""
import os, re, shutil, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
root, flavour = sys.argv[1], sys.argv[2]
def rd(p):
    return open(os.path.join(root, p), encoding='latin-1', newline='').read()
def wr(p, s):
    open(os.path.join(root, p), 'w', encoding='latin-1', newline='').write(s)
def nl(s):
    return '\r\n' if '\r\n' in s else '\n'
if os.path.abspath(root) != REPO:
    shutil.copy(os.path.join(REPO, 'dlls/fpbody_buddy.inl'), os.path.join(root, 'dlls/fpbody_buddy.inl'))
# barney.cpp
p = 'dlls/barney.cpp'; s = rd(p); n = nl(s)
if 'fpbody_buddy.inl' not in s:
    d = {'classic': '', 'updated': '#define FPB_SDK_UPDATED 1' + n, 'fi': '#define FPB_SDK_FI 1' + n}[flavour]
    s = s.rstrip() + n + n + d + '#include "fpbody_buddy.inl"\t// fpbody: the HEV companion (sv_fpbody_buddy)' + n
    wr(p, s)
# game.cpp
p = 'dlls/game.cpp'; s = rd(p); n = nl(s)
if 'sv_fpbody_buddy' not in s:
    a = 'cvar_t sv_fpbody_anims = { "sv_fpbody_anims", "cz", FCVAR_ARCHIVE };'
    i = s.index(a); j = s.index(n, i) + len(n)
    s = s[:j] + 'cvar_t sv_fpbody_buddy = { "sv_fpbody_buddy", "0", FCVAR_ARCHIVE };\t// fpbody: 1 = the HEV companion' + n + s[j:]
    a = 'CVAR_REGISTER( &sv_fpbody_anims );'
    i = s.index(a); j = s.index(n, i) + len(n)
    ind = s[s.rindex(n, 0, i) + len(n):i]
    s = s[:j] + ind + 'CVAR_REGISTER( &sv_fpbody_buddy );' + n + s[j:]
    wr(p, s)
# client.cpp
p = 'dlls/client.cpp'; s = rd(p); n = nl(s)
if 'FPBuddy_Precache' not in s:
    m = re.search(r'^void ClientPrecache\s*\(\s*(void)?\s*\)\s*\r?\n\{\r?\n', s, re.M)
    s = s[:m.start()] + 'void FPBuddy_Precache( void );\t// fpbody: the HEV companion (barney.cpp)' + n + n + s[m.start():m.end()] + \
        '\tFPBuddy_Precache();\t// fpbody: the HEV companion' + n + s[m.end():]
    wr(p, s)
# player.cpp
p = 'dlls/player.cpp'; s = rd(p); n = nl(s)
if 'FPBuddy_PlayerThink' not in s:
    a = '\tFPMoves_Think();\t// fpbody: kick, redeploy after holster-all' + n
    assert s.count(a) == 1, 'FPMoves_Think'
    s = s.replace(a, a + '\tFPBuddy_PlayerThink( this );\t// fpbody: the HEV companion' + n)
    m = re.search(r'^void CBasePlayer\s*::\s*PostThink\s*\(', s, re.M)
    s = s[:m.start()] + 'void FPBuddy_PlayerThink( CBasePlayer *pPlayer );\t// fpbody: the HEV companion (barney.cpp)' + n + n + s[m.start():]
    wr(p, s)
print('ok', root)
