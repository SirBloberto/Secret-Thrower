# Secret Thrower

A Discord bot for a social deduction game played across two voice channel teams. One or more players on each team are secretly assigned as "throwers" — their goal is to make their team lose without being detected. After the match, players vote on who they think the thrower was.

## Game Loop

1. **`/game setup`** — Start a game by selecting two voice channels as teams. Players currently in those channels are pulled in automatically.
2. **`/game add` / `/game remove`** — Adjust the player list before the game begins.
3. **`/game start`** — Secretly assigns throwers on each team and DMs them their role. Thrower selection is weighted so players who haven't thrown recently are more likely to be chosen.
4. Play the game.
5. **`/game result`** — Declare the winning team and open the voting phase. An interactive button panel appears on the game embed — one button per player per team. Players click to accuse who they think the thrower was. Voting closes automatically when the timer runs out.
6. Results are revealed: throwers are unmasked, vote tallies are shown, and caught/escaped status is displayed. The game record is saved to the database.

## Commands

### Game Management

| Command | Arguments | Description |
|---|---|---|
| `/game setup` | `team1`, `team2` | Initialize a game from two voice channels |
| `/game add` | `team`, `user` | Add or move a player to a team |
| `/game remove` | `user` | Remove a player from the game |
| `/game start` | `team1_count?`, `team2_count?` | Assign throwers and begin the game |
| `/game result` | `winner` | Declare the winning team and start voting |
| `/game cancel` | — | Cancel the current game |

### Profile

| Command | Arguments | Description |
|---|---|---|
| `/profile stats` | `user?` | View game statistics and ELO for yourself or another player |

### General

| Command | Arguments | Description |
|---|---|---|
| `/settings` | `voting_timer?`, `thrower_info?` | View or update server settings |
| `/help` | — | Show the game loop and available commands |

## Settings

| Setting | Default | Description |
|---|---|---|
| `voting_timer` | `60` | Seconds players have to vote after a result is declared |
| `thrower_info` | `false` | If enabled, publicly shows thrower counts and tells throwers the names of their partners |

## Self-Hosting

### Environment Variables

Create a `.env` file in the project root:

```env
TOKEN=your_discord_bot_token
DATABASE_URL=postgresql://user:password@host:port/dbname
```

The Redis connection is managed internally by Docker Compose and does not need to be set manually.

### Running with Docker

```bash
docker-compose up --build -d
```

The bot runs database migrations automatically on startup.

### Running Locally (Development)

```bash
uv sync
alembic upgrade head
python bot.py
```

## Requirements

- Python 3.12+
- PostgreSQL (or a Supabase project)
- Redis
