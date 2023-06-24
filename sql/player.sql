CREATE TABLE player(
    game_id INTEGER,
    channel_id INTEGER,
    user_id INTEGER,
    thrower INTEGER,
    PRIMARY KEY (game_id, user_id),
    FOREIGN KEY (game_id) REFERENCES game(game_id),
    FOREIGN KEY (channel_id) REFERENCES channel(channel_id),
    FOREIGN KEY (user_id) REFERENCES user(user_id)
);