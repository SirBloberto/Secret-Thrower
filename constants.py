WINNER = "👑"
THROWER = "🕵️"
VS_EMOJI = "⚔️"

# Team 1 uses letters A–J, team 2 uses numbers 1–10. Max 10 per team.
TEAM1_EMOJIS = ["🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭", "🇮", "🇯"]
TEAM2_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

BASE_RECENT = 5

ELO_K = 20
ELO_STARTING = 50
ELO_ABSTAIN_PENALTY = 0.05  # per un-voted team slot (minor)
ELO_INCORRECT_PENALTY = 0.15  # per wrong vote (worse than abstaining)
ELO_K_FLEX = 0.5  # how strongly K scales away from ELO 50 (0 = fixed K, 1 = max asymmetry)

MAX_PLAYERS_PER_TEAM = 10
MIN_PLAYERS_PER_TEAM = 2

MIN_VOTING_TIMER = 10
