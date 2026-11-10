r"""Half-Life: Decay as a single-player game with saves: Gina, and Colette as
an NPC companion who does her half of the puzzles. Run after apply_decay.py:

  python3 tools/port/fpbody_decay.py fpbody_decay_sdk

The 2008 PC port plays Decay as a two-player LAN game (a bot is Colette), and
Half-Life won't save a game with two players in it. Here the game is a normal
single-player one (maxplayers 1: New Game, quicksave / quickload, a death
reloads the last save) and Colette is the fpbody companion
(dlls/fpbody_buddy.inl, FPB_DECAY: models/fpbody_colette.mdl, always there,
invincible, follows / teleports, fights). Decay's puzzles check who's who
with a "player index" (1 = Gina, 2 = Colette) on triggers; FPDecay_Id() gives
the player 1 and Colette 2, so:

  dlls/triggers.cpp  trigger_multiple / once / teleport with Decay's
                     "specific player" flag and trigger_clientspawn accept
                     Colette as player 2 (and "both players inside" counts her)
  dlls/weapons.cpp   Colette's weapon boxes go to Gina (Colette has her own guns)
  dlls/decay/decay_gamerules.cpp  in single player: no bot (trigger_autobot),
                     no locked missions, a death doesn't fail the mission (the
                     game reloads instead), the player is always Gina (id 1)
                     after a loaded game too
  dlls/world.cpp     no trigger_autobot in single player
Colette goes to her half of each puzzle by herself (FPBuddy_DecayGoal in
fpbody_buddy.inl): into a "both players" trigger Gina stands in, and to the
Colette trigger that pairs with the Gina trigger Gina stands in (by name:
gina <-> colette, p1 <-> p2, player1 <-> player2).
"""
import os
import sys

SDK = sys.argv[1]


def rep(rel, pairs):
    p = os.path.join(SDK, rel)
    s = open(p, encoding='latin-1', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    s = s.replace('\r\n', '\n')
    if 'FPDecay_Id' in s and rel != 'dlls/barney.cpp':
        print('already', rel); return
    for old, new, *cnt in pairs:
        c = cnt[0] if cnt else 1
        n = s.count(old)
        if n != c:
            sys.exit('%s: expected %d of %r, found %d' % (rel, c, old[:70], n))
        s = s.replace(old, new)
    open(p, 'w', encoding='latin-1', newline='').write(s.replace('\n', nl))
    print('patched', rel)


# the companion is Colette
rep('dlls/barney.cpp', [('#include "fpbody_buddy.inl"', '#define FPB_DECAY	// fpbody: Colette, always there (fpbody_decay.py)\n#include "fpbody_buddy.inl"')])

ID = '''
// fpbody: who's who in Decay's puzzles - 1 = Gina (the player), 2 = Colette
// (the companion, fpbody_buddy.inl), 0 = anyone else
int FPDecay_Id( CBaseEntity *pEnt );
'''
rep('dlls/triggers.cpp', [
    ('#define PF_PLAYER2  2\n', '#define PF_PLAYER2  2\n' + ID),
    # trigger_clientspawn
    ('''			if ( pActivator )
				if (pActivator->IsPlayer())
				{
					CBasePlayer *g_pPlayer;
					g_pPlayer = (CBasePlayer*)pActivator;

					if (m_iPlayerIndex != 0)
					{	// check if Gina or Colette
						if (g_pPlayer->m_iDecayId != m_iPlayerIndex)
							return;
					}
				}''', '''			if ( pActivator && FPDecay_Id( pActivator ) )	// fpbody: Colette is player 2
			{
				if (m_iPlayerIndex != 0)
				{	// check if Gina or Colette
					if (FPDecay_Id( pActivator ) != m_iPlayerIndex)
						return;
				}
			}'''),
    # trigger_multiple / once: Colette may touch the specific-player ones
    ('''		 ( ( pevToucher->flags & FL_MONSTER ) && (pev->spawnflags & SF_TRIGGER_ALLOWMONSTERS ) ) ||''',
     '''		 ( ( pevToucher->flags & FL_MONSTER ) && (pev->spawnflags & SF_TRIGGER_ALLOWMONSTERS ) ) ||
		 ( ( pev->spawnflags & SF_SPECIFICPLAYER ) && FPDecay_Id( pOther ) == 2 ) ||	// fpbody: Colette'''),
    ('''			if (pOther->IsPlayer())
			{
				CBasePlayer *g_pPlayer;
				g_pPlayer = (CBasePlayer*)pOther;

				if (m_iPlayerIndex != 0)
				{	// check if Gina or Colette
					if (g_pPlayer->m_iDecayId != m_iPlayerIndex)
						return;
				} else
				{	// check if both are inside

					m_bPreviousPlayer = m_bCurrentPlayer;
					m_bCurrentPlayer = g_pPlayer->m_iDecayId;

					SetBits( m_iPlayersInside, g_pPlayer->m_iDecayId);''', '''			if (FPDecay_Id( pOther ))	// fpbody: the player or Colette
			{
				if (m_iPlayerIndex != 0)
				{	// check if Gina or Colette
					if (FPDecay_Id( pOther ) != m_iPlayerIndex)
						return;
				} else
				{	// check if both are inside

					m_bPreviousPlayer = m_bCurrentPlayer;
					m_bCurrentPlayer = FPDecay_Id( pOther );

					SetBits( m_iPlayersInside, FPDecay_Id( pOther ));'''),
    # trigger_teleport
    ('''		if (pOther->IsPlayer())
		{
			CBasePlayer *g_pPlayer;
			g_pPlayer = (CBasePlayer*)pOther;

			if (m_iPlayerIndex != 0)
			{	// check if Gina or Colette
				if (g_pPlayer->m_iDecayId != m_iPlayerIndex)
					return;
			} // Vyacheslav Dzhura''', '''		if (FPDecay_Id( pOther ))	// fpbody: the player or Colette
		{
			if (m_iPlayerIndex != 0)
			{	// check if Gina or Colette
				if (FPDecay_Id( pOther ) != m_iPlayerIndex)
					return;
			} // Vyacheslav Dzhura'''),
])

rep('dlls/weapons.cpp', [
    ('''		if (pPlayer->m_iDecayId	!= this->m_iPlayerIndex)
			return;''', '''		if (pPlayer->m_iDecayId	!= this->m_iPlayerIndex && gpGlobals->maxClients > 1)	// fpbody: single player, Gina takes Colette's too
			return;'''),
])

rep('dlls/world.cpp', [
    ('''		CBaseEntity *pEntity;
		pEntity = CBaseEntity::Create( "trigger_autobot", g_vecZero, g_vecZero, edict() );
		if ( !pEntity )''', '''		CBaseEntity *pEntity = NULL;
		if ( gpGlobals->maxClients > 1 )	// fpbody: single player has Colette as an NPC, no bot
			pEntity = CBaseEntity::Create( "trigger_autobot", g_vecZero, g_vecZero, edict() );
		if ( !pEntity && gpGlobals->maxClients > 1 )'''),
])

rep('dlls/decay/decay_gamerules.cpp', [
    ('''void CDecayRules :: PlayerThink( CBasePlayer *pPlayer )
{
}''', '''void CDecayRules :: PlayerThink( CBasePlayer *pPlayer )
{
	// fpbody: single player - the player is Gina, also after a loaded game
	// (which restores the player without spawning him)
	if ( gpGlobals->maxClients == 1 )
	{
		pPlayers[ 0 ] = pPlayer;
		if ( PlayersCount < 1 )
			PlayersCount = 1;
		pPlayer->m_iDecayId = 1;
	}
}'''),
    ('''	char enddecayname[32];
	sprintf( enddecayname, "decay_player%d_dead", pVictim->m_iDecayId ); // decay_player2_dead''', '''	if ( gpGlobals->maxClients == 1 )
		return;		// fpbody: single player - the game reloads the last save instead of failing the mission

	char enddecayname[32];
	sprintf( enddecayname, "decay_player%d_dead", pVictim->m_iDecayId ); // decay_player2_dead'''),
    ('		if ( decayMaps[ getMapEntryId(curMapId) ].m_bLocked == true )',
     '		if ( decayMaps[ getMapEntryId(curMapId) ].m_bLocked == true && gpGlobals->maxClients > 1 )	// fpbody: single player plays every mission'),
])
print('ok', SDK)
