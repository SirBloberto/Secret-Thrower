CREATE VIEW IF NOT EXISTS v_recent(
    user_id,
    recent)
AS SELECT
    user_id,
    CASE recent_game
        WHEN NULL THEN COUNT(*)
        ELSE COUNT(*) - 1
    END
FROM player
LEFT JOIN
    (SELECT
        user_id,
        MAX(game_time) AS recent_game
    FROM player
    INNER JOIN game USING(game_id)
    WHERE thrower = 1
    GROUP BY user_id) recent USING(user_id)
INNER JOIN game USING (game_id)
WHERE game.game_time >= recent.recent_game OR recent.recent_game IS NULL
GROUP BY user_id;