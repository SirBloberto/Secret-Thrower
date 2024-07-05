CREATE TABLE IF NOT EXISTS game(
    game_id INTEGER,
    guild_id INTEGER,
    game_time TEXT,
    info TEXT,
    PRIMARY KEY (game_id),
    FOREIGN KEY (guild_id) REFERENCES guild(guild_id)
);