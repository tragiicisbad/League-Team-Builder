import json
import math
import os
from datetime import datetime

import psycopg
from psycopg.rows import tuple_row


DATABASE_URL = os.getenv("DATABASE_URL")


def connect():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is missing. Add PostgreSQL to Railway and attach DATABASE_URL to the bot service."
        )

    return psycopg.connect(DATABASE_URL, row_factory=tuple_row)


def setup_database():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        discord_id BIGINT PRIMARY KEY,
        name TEXT NOT NULL,
        rank TEXT NOT NULL,
        rating INTEGER NOT NULL,
        top_rating INTEGER NOT NULL,
        jungle_rating INTEGER NOT NULL,
        mid_rating INTEGER NOT NULL,
        adc_rating INTEGER NOT NULL,
        support_rating INTEGER NOT NULL,
        primary_role TEXT NOT NULL,
        secondary_role TEXT NOT NULL,
        avoided_role TEXT DEFAULT 'None',
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0,
        season_rating_change INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    ALTER TABLE players
    ADD COLUMN IF NOT EXISTS avoided_role TEXT DEFAULT 'None'
    """)

    cursor.execute("""
    ALTER TABLE players
    ADD COLUMN IF NOT EXISTS wins INTEGER DEFAULT 0
    """)

    cursor.execute("""
    ALTER TABLE players
    ADD COLUMN IF NOT EXISTS losses INTEGER DEFAULT 0
    """)

    cursor.execute("""
    ALTER TABLE players
    ADD COLUMN IF NOT EXISTS streak INTEGER DEFAULT 0
    """)

    cursor.execute("""
    ALTER TABLE players
    ADD COLUMN IF NOT EXISTS season_rating_change INTEGER DEFAULT 0
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id SERIAL PRIMARY KEY,
        date_played TEXT NOT NULL,
        winner TEXT NOT NULL,
        blue_team TEXT NOT NULL,
        red_team TEXT NOT NULL,
        blue_rating INTEGER NOT NULL,
        red_rating INTEGER NOT NULL,
        rating_change INTEGER NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS season_player_history (
        id SERIAL PRIMARY KEY,
        season_name TEXT NOT NULL,
        archived_at TEXT NOT NULL,
        discord_id BIGINT NOT NULL,
        name TEXT NOT NULL,
        rank TEXT NOT NULL,
        rating INTEGER NOT NULL,
        top_rating INTEGER NOT NULL,
        jungle_rating INTEGER NOT NULL,
        mid_rating INTEGER NOT NULL,
        adc_rating INTEGER NOT NULL,
        support_rating INTEGER NOT NULL,
        primary_role TEXT NOT NULL,
        secondary_role TEXT NOT NULL,
        avoided_role TEXT DEFAULT 'None',
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0,
        season_rating_change INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS season_match_history (
        id SERIAL PRIMARY KEY,
        season_name TEXT NOT NULL,
        archived_at TEXT NOT NULL,
        original_match_id INTEGER NOT NULL,
        date_played TEXT NOT NULL,
        winner TEXT NOT NULL,
        blue_team TEXT NOT NULL,
        red_team TEXT NOT NULL,
        blue_rating INTEGER NOT NULL,
        red_rating INTEGER NOT NULL,
        rating_change INTEGER NOT NULL
    )
    """)

    conn.commit()
    conn.close()


def make_role_ratings(base_rating, primary_role, secondary_role):
    ratings = {
        "Top": base_rating - 250,
        "Jungle": base_rating - 250,
        "Mid": base_rating - 250,
        "ADC": base_rating - 250,
        "Support": base_rating - 250
    }

    if primary_role == "Fill":
        for role in ratings:
            ratings[role] = base_rating
    else:
        ratings[primary_role] = base_rating

    if secondary_role == "Fill":
        for role in ratings:
            ratings[role] = max(ratings[role], base_rating - 100)
    else:
        ratings[secondary_role] = max(ratings[secondary_role], base_rating - 100)

    return ratings


def save_player(discord_id, name, rank, rating, primary_role, secondary_role, avoided_role="None"):
    role_ratings = make_role_ratings(rating, primary_role, secondary_role)

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO players (
        discord_id, name, rank, rating,
        top_rating, jungle_rating, mid_rating, adc_rating, support_rating,
        primary_role, secondary_role, avoided_role, streak
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
    ON CONFLICT(discord_id) DO UPDATE SET
        name = EXCLUDED.name,
        rank = EXCLUDED.rank,
        rating = EXCLUDED.rating,
        top_rating = EXCLUDED.top_rating,
        jungle_rating = EXCLUDED.jungle_rating,
        mid_rating = EXCLUDED.mid_rating,
        adc_rating = EXCLUDED.adc_rating,
        support_rating = EXCLUDED.support_rating,
        primary_role = EXCLUDED.primary_role,
        secondary_role = EXCLUDED.secondary_role,
        avoided_role = EXCLUDED.avoided_role
    """, (
        discord_id, name, rank, rating,
        role_ratings["Top"],
        role_ratings["Jungle"],
        role_ratings["Mid"],
        role_ratings["ADC"],
        role_ratings["Support"],
        primary_role, secondary_role, avoided_role
    ))

    conn.commit()
    conn.close()


def row_to_player(row):
    if not row:
        return None

    return {
        "discord_id": row[0],
        "name": row[1],
        "rank": row[2],
        "rating": row[3],
        "role_ratings": {
            "Top": row[4],
            "Jungle": row[5],
            "Mid": row[6],
            "ADC": row[7],
            "Support": row[8]
        },
        "primary_role": row[9],
        "secondary_role": row[10],
        "avoided_role": row[11] or "None",
        "wins": row[12],
        "losses": row[13],
        "streak": row[14] if len(row) > 14 and row[14] is not None else 0,
        "season_rating_change": row[15] if len(row) > 15 and row[15] is not None else 0
    }


def get_player(discord_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT discord_id, name, rank, rating,
           top_rating, jungle_rating, mid_rating, adc_rating, support_rating,
           primary_role, secondary_role, avoided_role, wins, losses, streak, season_rating_change
    FROM players
    WHERE discord_id = %s
    """, (discord_id,))

    row = cursor.fetchone()
    conn.close()

    return row_to_player(row)


def calculate_streak_rating_change(current_streak, won):
    """
    Base result is 30 rating.
    A streak adds +5 rating per extra game on that streak, capped at 50.

    Win examples:
    current streak 0 or negative -> +30
    current streak 1 -> +35
    current streak 2 -> +40
    current streak 3 -> +45
    current streak 4+ -> +50

    Loss examples:
    current streak 0 or positive -> -30
    current streak -1 -> -35
    current streak -2 -> -40
    current streak -3 -> -45
    current streak -4 or lower -> -50
    """
    base_change = 30
    bonus_per_streak_game = 5
    max_change = 50

    if won:
        streak_bonus_steps = current_streak if current_streak > 0 else 0
        return min(base_change + (streak_bonus_steps * bonus_per_streak_game), max_change)

    streak_bonus_steps = abs(current_streak) if current_streak < 0 else 0
    return -min(base_change + (streak_bonus_steps * bonus_per_streak_game), max_change)


def update_player_after_match(discord_id, assigned_role, rating_change=None, won=False):
    column_map = {
        "Top": "top_rating",
        "Jungle": "jungle_rating",
        "Mid": "mid_rating",
        "ADC": "adc_rating",
        "Support": "support_rating"
    }

    role_column = column_map[assigned_role]

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT streak FROM players WHERE discord_id = %s", (discord_id,))
    row = cursor.fetchone()
    current_streak = row[0] if row and row[0] is not None else 0

    final_rating_change = calculate_streak_rating_change(current_streak, won)

    if won:
        new_streak = current_streak + 1 if current_streak > 0 else 1
        cursor.execute(f"""
        UPDATE players
        SET rating = rating + %s,
            {role_column} = {role_column} + %s,
            wins = wins + 1,
            streak = %s,
            season_rating_change = season_rating_change + %s
        WHERE discord_id = %s
        """, (final_rating_change, final_rating_change, new_streak, final_rating_change, discord_id))
    else:
        new_streak = current_streak - 1 if current_streak < 0 else -1
        cursor.execute(f"""
        UPDATE players
        SET rating = rating + %s,
            {role_column} = {role_column} + %s,
            losses = losses + 1,
            streak = %s,
            season_rating_change = season_rating_change + %s
        WHERE discord_id = %s
        """, (final_rating_change, final_rating_change, new_streak, final_rating_change, discord_id))

    conn.commit()
    conn.close()

    return final_rating_change, new_streak


def drop_all_role_ratings_to_nearest_hundred():
    """
    Season reset helper:
    Drops every role rating down to the nearest hundred.
    Example: 1499 -> 1400, 1500 -> 1500.
    Overall rating is recalculated from selected primary/secondary role ratings.
    Wins, losses, and streaks are reset to 0. Match history is not deleted here.
    """
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET top_rating = FLOOR(top_rating / 100.0)::int * 100,
            jungle_rating = FLOOR(jungle_rating / 100.0)::int * 100,
            mid_rating = FLOOR(mid_rating / 100.0)::int * 100,
            adc_rating = FLOOR(adc_rating / 100.0)::int * 100,
            support_rating = FLOOR(support_rating / 100.0)::int * 100,
            wins = 0,
            losses = 0,
            streak = 0,
            season_rating_change = 0
    """)

    cursor.execute("""
        SELECT discord_id, primary_role, secondary_role,
               top_rating, jungle_rating, mid_rating, adc_rating, support_rating
        FROM players
    """)

    players = cursor.fetchall()
    updated_count = 0

    for row in players:
        discord_id, primary_role, secondary_role, top, jungle, mid, adc, support = row

        role_ratings = {
            "Top": top,
            "Jungle": jungle,
            "Mid": mid,
            "ADC": adc,
            "Support": support
        }

        def selected_rating(role):
            if role == "Fill":
                return round(sum(role_ratings.values()) / len(role_ratings))
            return role_ratings[role]

        new_overall = round((selected_rating(primary_role) + selected_rating(secondary_role)) / 2)

        cursor.execute("""
            UPDATE players
            SET rating = %s
            WHERE discord_id = %s
        """, (new_overall, discord_id))

        updated_count += 1

    conn.commit()
    conn.close()

    return updated_count



def full_season_rollover(season_name="Season 1"):
    """
    Full season rollover:
    1. Archives current player standings into season_player_history.
    2. Archives current match history into season_match_history.
    3. Drops every role rating down to the nearest hundred.
    4. Recalculates overall rating from selected primary/secondary roles.
    5. Resets wins, losses, and streaks to 0.
    6. Clears current match history.

    It does not delete player profiles.
    """
    conn = connect()
    cursor = conn.cursor()

    archived_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    cursor.execute("""
        INSERT INTO season_player_history (
            season_name, archived_at,
            discord_id, name, rank, rating,
            top_rating, jungle_rating, mid_rating, adc_rating, support_rating,
            primary_role, secondary_role, avoided_role,
            wins, losses, streak, season_rating_change
        )
        SELECT
            %s, %s,
            discord_id, name, rank, rating,
            top_rating, jungle_rating, mid_rating, adc_rating, support_rating,
            primary_role, secondary_role, avoided_role,
            wins, losses, streak, season_rating_change
        FROM players
    """, (season_name, archived_at))

    archived_players = cursor.rowcount

    cursor.execute("""
        INSERT INTO season_match_history (
            season_name, archived_at,
            original_match_id, date_played, winner,
            blue_team, red_team, blue_rating, red_rating, rating_change
        )
        SELECT
            %s, %s,
            id, date_played, winner,
            blue_team, red_team, blue_rating, red_rating, rating_change
        FROM matches
    """, (season_name, archived_at))

    archived_matches = cursor.rowcount

    cursor.execute("""
        UPDATE players
        SET top_rating = FLOOR(top_rating / 100.0)::int * 100,
            jungle_rating = FLOOR(jungle_rating / 100.0)::int * 100,
            mid_rating = FLOOR(mid_rating / 100.0)::int * 100,
            adc_rating = FLOOR(adc_rating / 100.0)::int * 100,
            support_rating = FLOOR(support_rating / 100.0)::int * 100,
            wins = 0,
            losses = 0,
            streak = 0,
            season_rating_change = 0
    """)

    cursor.execute("""
        SELECT discord_id, primary_role, secondary_role,
               top_rating, jungle_rating, mid_rating, adc_rating, support_rating
        FROM players
    """)

    players = cursor.fetchall()
    updated_players = 0

    for row in players:
        discord_id, primary_role, secondary_role, top, jungle, mid, adc, support = row

        role_ratings = {
            "Top": top,
            "Jungle": jungle,
            "Mid": mid,
            "ADC": adc,
            "Support": support
        }

        def selected_rating(role):
            if role == "Fill":
                return round(sum(role_ratings.values()) / len(role_ratings))
            return role_ratings[role]

        new_overall = round((selected_rating(primary_role) + selected_rating(secondary_role)) / 2)

        cursor.execute("""
            UPDATE players
            SET rating = %s
            WHERE discord_id = %s
        """, (new_overall, discord_id))

        updated_players += 1

    cursor.execute("DELETE FROM matches")
    deleted_matches = cursor.rowcount

    cursor.execute("ALTER SEQUENCE matches_id_seq RESTART WITH 1")

    conn.commit()
    conn.close()

    return {
        "season_name": season_name,
        "archived_players": archived_players,
        "archived_matches": archived_matches,
        "updated_players": updated_players,
        "deleted_matches": deleted_matches
    }



def get_leaderboard(limit=10, offset=0):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT name, rank, rating, primary_role, secondary_role, wins, losses, season_rating_change
    FROM players
    ORDER BY rating DESC
    LIMIT %s OFFSET %s
    """, (limit, offset))

    rows = cursor.fetchall()
    conn.close()

    return rows


def save_match(winner, blue_team, red_team, blue_rating, red_rating, rating_change):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO matches (
        date_played, winner, blue_team, red_team,
        blue_rating, red_rating, rating_change
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        winner,
        json.dumps(blue_team),
        json.dumps(red_team),
        blue_rating,
        red_rating,
        rating_change
    ))

    conn.commit()
    conn.close()


def get_match_history(limit=5):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, date_played, winner, blue_team, red_team, blue_rating, red_rating, rating_change
    FROM matches
    ORDER BY id DESC
    LIMIT %s
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return rows


def expected_score(team_rating, opponent_rating):
    return 1 / (1 + math.pow(10, (opponent_rating - team_rating) / 400))


def calculate_elo_change(winner_rating, loser_rating, k=32):
    return 30
