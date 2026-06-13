import json
import math
import sqlite3
from datetime import datetime

DB_NAME = "league_bot.db"


def connect():
    return sqlite3.connect(DB_NAME)


def setup_database():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        discord_id INTEGER PRIMARY KEY,
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
        losses INTEGER DEFAULT 0
    )
    """)

    cursor.execute("PRAGMA table_info(players)")
    existing_columns = [column[1] for column in cursor.fetchall()]

    if "avoided_role" not in existing_columns:
        cursor.execute("ALTER TABLE players ADD COLUMN avoided_role TEXT DEFAULT 'None'")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        primary_role, secondary_role, avoided_role
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(discord_id) DO UPDATE SET
        name = excluded.name,
        rank = excluded.rank,
        rating = excluded.rating,
        top_rating = excluded.top_rating,
        jungle_rating = excluded.jungle_rating,
        mid_rating = excluded.mid_rating,
        adc_rating = excluded.adc_rating,
        support_rating = excluded.support_rating,
        primary_role = excluded.primary_role,
        secondary_role = excluded.secondary_role,
        avoided_role = excluded.avoided_role
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
        "losses": row[13]
    }


def get_player(discord_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT discord_id, name, rank, rating,
           top_rating, jungle_rating, mid_rating, adc_rating, support_rating,
           primary_role, secondary_role, avoided_role, wins, losses
    FROM players
    WHERE discord_id = ?
    """, (discord_id,))

    row = cursor.fetchone()
    conn.close()

    return row_to_player(row)


def update_player_after_match(discord_id, assigned_role, rating_change, won):
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

    if won:
        cursor.execute(f"""
        UPDATE players
        SET rating = rating + ?,
            {role_column} = {role_column} + ?,
            wins = wins + 1
        WHERE discord_id = ?
        """, (rating_change, rating_change, discord_id))
    else:
        cursor.execute(f"""
        UPDATE players
        SET rating = rating + ?,
            {role_column} = {role_column} + ?,
            losses = losses + 1
        WHERE discord_id = ?
        """, (rating_change, rating_change, discord_id))

    conn.commit()
    conn.close()


def get_leaderboard(limit=10):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT name, rank, rating, primary_role, secondary_role, wins, losses
    FROM players
    ORDER BY rating DESC
    LIMIT ?
    """, (limit,))

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
    VALUES (?, ?, ?, ?, ?, ?, ?)
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
    LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return rows


def expected_score(team_rating, opponent_rating):
    return 1 / (1 + math.pow(10, (opponent_rating - team_rating) / 400))


def calculate_elo_change(winner_rating, loser_rating, k=32):
    expected = expected_score(winner_rating, loser_rating)
    change = round(k * (1 - expected))
    return max(5, min(30, change))
