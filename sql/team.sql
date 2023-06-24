CREATE TABLE team(
    game_id INTEGER,
    channel_id INTEGER,
    winner INTEGER,
    PRIMARY KEY (game_id, channel_id),
    FOREIGN KEY (game_id) REFERENCES game(game_id),
    FOREIGN KEY (channel_id) REFERENCES channel(channe_id)
);