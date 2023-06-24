CREATE TABLE vote(
    game_id INTEGER,
    user_id INTEGER,
    vote INTEGER,
    PRIMARY KEY (game_id, user_id, vote),
    FOREIGN KEY (game_id) REFERENCES game(game_id),
    FOREIGN KEY (user_id) REFERENCES user(user_id)
);