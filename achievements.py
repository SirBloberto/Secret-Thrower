from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from models import User as DBUser


@dataclass
class Achievement:
    bit: int
    name: str
    emoji: str
    description: str
    condition: Callable[[DBUser], bool] = field(repr=False, compare=False)
    progress: Callable[[DBUser], str] | None = field(default=None, repr=False, compare=False)

    @property
    def mask(self) -> int:
        return 1 << self.bit


def _innocent_wins(user: DBUser) -> int:
    return max(0, user.games_won - (user.games_as_thrower - user.games_thrown))


# Per-game achievements (Double Vision, Lone Wolf, Phantom) cannot be checked from
# cumulative stats alone — their condition is always False here and they unlock only
# through check_game_achievements() called at the end of each game.
ACHIEVEMENTS: list[Achievement] = [
    Achievement(0,  "First Blood",    "🩸", "Play your first game",                   lambda u: u.games_played >= 1),
    Achievement(1,  "Sharp Eye",      "🔍", "10 correct votes",                        lambda u: u.votes_cast_on_thrower >= 10,
                progress=lambda u: f"{min(u.votes_cast_on_thrower, 10)}/10"),
    Achievement(2,  "Eagle Eye",      "👁️", "50 correct votes",                        lambda u: u.votes_cast_on_thrower >= 50,
                progress=lambda u: f"{min(u.votes_cast_on_thrower, 50)}/50"),
    Achievement(3,  "Mastermind",     "🧠", "10 clean throws",                         lambda u: u.games_evaded >= 10,
                progress=lambda u: f"{min(u.games_evaded, 10)}/10"),
    Achievement(4,  "Ghost",          "👻", "25 clean throws",                         lambda u: u.games_evaded >= 25,
                progress=lambda u: f"{min(u.games_evaded, 25)}/25"),
    Achievement(5,  "Team Player",    "🤝", "25 innocent wins",                        lambda u: _innocent_wins(u) >= 25,
                progress=lambda u: f"{min(_innocent_wins(u), 25)}/25"),
    Achievement(6,  "Veteran",        "🎖️", "100 games played",                        lambda u: u.games_played >= 100,
                progress=lambda u: f"{min(u.games_played, 100)}/100"),
    Achievement(7,  "Elite",          "⭐", "Reach Innocent ELO 75",                   lambda u: u.innocent_elo >= 75.0,
                progress=lambda u: f"{u.innocent_elo:.0f}/75"),
    Achievement(8,  "Double Vision",  "🎭", "Found both throwers in one game",         lambda u: False),
    Achievement(9,  "Lone Wolf",      "🐺", "Only player to correctly vote a thrower", lambda u: False),
    Achievement(10, "Phantom",        "🫥", "Played thrower and received zero votes",  lambda u: False),
    Achievement(11, "Hot Streak",     "🔥", "Win 5 games in a row",                    lambda u: u.best_win_streak >= 5,
                progress=lambda u: f"{min(u.best_win_streak, 5)}/5"),
    Achievement(12, "Unstoppable",    "⚡", "Win 10 games in a row",                   lambda u: u.best_win_streak >= 10,
                progress=lambda u: f"{min(u.best_win_streak, 10)}/10"),
]

_BY_NAME: dict[str, Achievement] = {a.name: a for a in ACHIEVEMENTS}


def check_new_achievements(user: DBUser) -> int:
    """Return bitmask of cumulative-stat achievements just earned (not yet held)."""
    newly = 0
    for ach in ACHIEVEMENTS:
        if not (user.achievements & ach.mask) and ach.condition(user):
            newly |= ach.mask
    return newly


def check_game_achievements(
    user: DBUser,
    *,
    found_both: bool = False,
    lone_correct: bool = False,
    perfect_throw: bool = False,
) -> int:
    """Return bitmask of per-game achievements earned in the just-finished game."""
    newly = 0
    flags = [
        (found_both,    "Double Vision"),
        (lone_correct,  "Lone Wolf"),
        (perfect_throw, "Phantom"),
    ]
    for flag, name in flags:
        ach = _BY_NAME[name]
        if flag and not (user.achievements & ach.mask):
            newly |= ach.mask
    return newly


def unlocked_list(mask: int) -> list[Achievement]:
    return [ach for ach in ACHIEVEMENTS if mask & ach.mask]


def format_achievements(mask: int, user: DBUser | None = None) -> str:
    unlocked: list[str] = []
    locked: list[str] = []
    for ach in ACHIEVEMENTS:
        if mask & ach.mask:
            unlocked.append(f"{ach.emoji} **{ach.name}** — {ach.description}")
        else:
            prog = f" `{ach.progress(user)}`" if ach.progress and user else ""
            locked.append(f"**{ach.name}**{prog}")
    result = unlocked if unlocked else ["None yet — play a game to earn your first badge!"]
    if locked:
        result.append(f"\n🔒 *{' · '.join(locked)}*")
    return "\n".join(result)
