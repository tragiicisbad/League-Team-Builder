import os
from dotenv import load_dotenv

load_dotenv()
print("DATABASE_URL =", os.getenv("DATABASE_URL"))

import sqlite3
import psycopg

SQLITE_DB = "league_bot.db"
DATABASE_URL = os.getenv("DATABASE_URL")


def migrate():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Add it to your local .env or Railway variables.")

    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_cursor = sqlite_conn.cursor()

    pg_conn = psycopg.connect(DATABASE_URL)
    pg_cursor = pg_conn.cursor()

    # Make sure PostgreSQL tables exist.
    from database import setup_database
    setup_database()

    sqlite_cursor.execute("""
        SELECT discord_id, name, rank, rating,
               top_rating, jungle_rating, mid_rating, adc_rating, support_rating,
               primary_role, secondary_role, avoided_role, wins, losses
        FROM players
    """)
    players = sqlite_cursor.fetchall()

    for player in players:
        pg_cursor.execute("""
            INSERT INTO players (
                discord_id, name, rank, rating,
                top_rating, jungle_rating, mid_rating, adc_rating, support_rating,
                primary_role, secondary_role, avoided_role, wins, losses
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                avoided_role = EXCLUDED.avoided_role,
                wins = EXCLUDED.wins,
                losses = EXCLUDED.losses
        """, player)

    sqlite_cursor.execute("""
        SELECT id, date_played, winner, blue_team, red_team, blue_rating, red_rating, rating_change
        FROM matches
        ORDER BY id ASC
    """)
    matches = sqlite_cursor.fetchall()

    for match in matches:
        pg_cursor.execute("""
            INSERT INTO matches (
                id, date_played, winner, blue_team, red_team,
                blue_rating, red_rating, rating_change
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(id) DO NOTHING
        """, match)

    pg_cursor.execute("""
        SELECT setval(
            pg_get_serial_sequence('matches', 'id'),
            COALESCE((SELECT MAX(id) FROM matches), 1),
            true
        )
    """)

    pg_conn.commit()

    sqlite_conn.close()
    pg_conn.close()

    print(f"Migrated {len(players)} players and {len(matches)} matches to PostgreSQL.")


if __name__ == "__main__":
    migrate()
