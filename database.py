import json
import os
from datetime import datetime

import psycopg
from psycopg.rows import tuple_row


DATABASE_URL = os.getenv("DATABASE_URL")


# Database access and schema creation.
def connect():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is missing. Add PostgreSQL to Railway and attach DATABASE_URL to the bot service."
        )

    return psycopg.connect(DATABASE_URL, row_factory=tuple_row)


def setup_database():
    """
    Creates the tables used by the bot. The ALTER statements keep older
    deployments compatible when new columns are added.
    """
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
        season_rating_change INTEGER DEFAULT 0,
        coins BIGINT DEFAULT 0
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
    ALTER TABLE players
    ADD COLUMN IF NOT EXISTS coins BIGINT DEFAULT 0
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
        season_rating_change INTEGER DEFAULT 0,
        coins BIGINT DEFAULT 0
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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS betting_matches (
        id SERIAL PRIMARY KEY,
        created_at TEXT NOT NULL,
        closes_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        blue_team TEXT NOT NULL,
        red_team TEXT NOT NULL,
        blue_pool BIGINT DEFAULT 0,
        red_pool BIGINT DEFAULT 0,
        winner TEXT,
        message_id BIGINT,
        channel_id BIGINT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bets (
        id SERIAL PRIMARY KEY,
        betting_match_id INTEGER NOT NULL REFERENCES betting_matches(id) ON DELETE CASCADE,
        discord_id BIGINT NOT NULL,
        side TEXT NOT NULL,
        amount BIGINT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(betting_match_id, discord_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS betting_payouts (
        id SERIAL PRIMARY KEY,
        betting_match_id INTEGER NOT NULL REFERENCES betting_matches(id) ON DELETE CASCADE,
        discord_id BIGINT NOT NULL,
        amount BIGINT NOT NULL,
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mayram_players (
        discord_id BIGINT PRIMARY KEY,
        name TEXT NOT NULL,
        rating INTEGER NOT NULL DEFAULT 1000,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mayram_matches (
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

    conn.commit()
    conn.close()


def make_role_ratings(base_rating, primary_role, secondary_role):
    """
    Initializes role ratings from the player's starting overall rating.
    Preferred roles start higher; off-roles start lower.
    """
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
    """
    Converts a positional database row into the player dict used by bot.py.
    """
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
        "season_rating_change": row[15] if len(row) > 15 and row[15] is not None else 0,
        "coins": row[16] if len(row) > 16 and row[16] is not None else 0
    }


def get_player(discord_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT discord_id, name, rank, rating,
           top_rating, jungle_rating, mid_rating, adc_rating, support_rating,
           primary_role, secondary_role, avoided_role, wins, losses, streak, season_rating_change, coins
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
            wins, losses, streak, season_rating_change, coins
        )
        SELECT
            %s, %s,
            discord_id, name, rank, rating,
            top_rating, jungle_rating, mid_rating, adc_rating, support_rating,
            primary_role, secondary_role, avoided_role,
            wins, losses, streak, season_rating_change, coins
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



def get_all_player_ids():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT discord_id FROM players")
    rows = cursor.fetchall()

    conn.close()

    return [row[0] for row in rows]


def get_player_coin_balance(discord_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT coins FROM players WHERE discord_id = %s", (discord_id,))
    row = cursor.fetchone()

    conn.close()

    if not row:
        return None

    return row[0] or 0


def reset_all_player_coins():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET coins = 0
    """)

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed


def add_coins(discord_id, amount):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET coins = GREATEST(coins + %s, 0)
        WHERE discord_id = %s
    """, (amount, discord_id))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed > 0


def award_match_coin_rewards(played_ids, signed_reward=1000, played_reward=30000):
    """
    Awards participation coins after a match.
    Players in the match get the larger reward; all other signed-up players get the smaller one.
    """
    played_ids = set(int(player_id) for player_id in played_ids)

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT discord_id FROM players")
    player_rows = cursor.fetchall()

    rewards = []

    for (discord_id,) in player_rows:
        reward = played_reward if int(discord_id) in played_ids else signed_reward

        cursor.execute("""
            UPDATE players
            SET coins = coins + %s
            WHERE discord_id = %s
        """, (reward, discord_id))

        rewards.append((discord_id, reward))

    conn.commit()
    conn.close()

    return rewards


def get_coin_leaderboard(limit=10, offset=0):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, coins
        FROM players
        ORDER BY coins DESC, name ASC
        LIMIT %s OFFSET %s
    """, (limit, offset))

    rows = cursor.fetchall()
    conn.close()

    return rows


def create_betting_match(blue_team, red_team, closes_at, channel_id=None, message_id=None):
    """
    Stores a betting window tied to the Discord teams message.
    Team data is snapshotted so later result settlement knows who was on each side.
    """
    conn = connect()
    cursor = conn.cursor()

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO betting_matches (
            created_at, closes_at, status,
            blue_team, red_team,
            blue_pool, red_pool,
            channel_id, message_id
        )
        VALUES (%s, %s, 'open', %s, %s, 0, 0, %s, %s)
        RETURNING id
    """, (
        now_text,
        closes_at,
        json.dumps(blue_team),
        json.dumps(red_team),
        channel_id,
        message_id
    ))

    betting_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()

    return betting_id


def set_betting_message(betting_match_id, channel_id, message_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE betting_matches
        SET channel_id = %s,
            message_id = %s
        WHERE id = %s
    """, (channel_id, message_id, betting_match_id))

    conn.commit()
    conn.close()


def row_to_betting_match(row):
    if not row:
        return None

    return {
        "id": row[0],
        "created_at": row[1],
        "closes_at": row[2],
        "status": row[3],
        "blue_team": json.loads(row[4]),
        "red_team": json.loads(row[5]),
        "blue_pool": row[6] or 0,
        "red_pool": row[7] or 0,
        "winner": row[8],
        "message_id": row[9],
        "channel_id": row[10]
    }


def get_betting_match(betting_match_id):
    if betting_match_id is None:
        return None

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, created_at, closes_at, status,
               blue_team, red_team, blue_pool, red_pool,
               winner, message_id, channel_id
        FROM betting_matches
        WHERE id = %s
    """, (betting_match_id,))

    row = cursor.fetchone()
    conn.close()

    return row_to_betting_match(row)


def close_betting_match(betting_match_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE betting_matches
        SET status = 'closed'
        WHERE id = %s AND status = 'open'
    """, (betting_match_id,))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed > 0


def recompute_betting_pools(cursor, betting_match_id):
    cursor.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN side = 'blue' THEN amount ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN side = 'red' THEN amount ELSE 0 END), 0)
        FROM bets
        WHERE betting_match_id = %s
    """, (betting_match_id,))

    blue_pool, red_pool = cursor.fetchone()

    cursor.execute("""
        UPDATE betting_matches
        SET blue_pool = %s,
            red_pool = %s
        WHERE id = %s
    """, (blue_pool, red_pool, betting_match_id))

    return blue_pool, red_pool


def place_or_update_bet(betting_match_id, discord_id, side, amount):
    """
    Reserves coins immediately. If the player changes their bet, the old reserved
    amount is first treated as available balance, then the new amount is reserved.
    """
    amount = int(amount)

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status
        FROM betting_matches
        WHERE id = %s
        FOR UPDATE
    """, (betting_match_id,))

    match_row = cursor.fetchone()

    if not match_row:
        conn.close()
        return False, "Betting match not found."

    if match_row[0] != "open":
        conn.close()
        return False, "Betting is already closed."

    cursor.execute("""
        SELECT coins
        FROM players
        WHERE discord_id = %s
        FOR UPDATE
    """, (discord_id,))

    player_row = cursor.fetchone()

    if not player_row:
        conn.close()
        return False, "You need to sign up before betting."

    current_balance = player_row[0] or 0

    cursor.execute("""
        SELECT amount
        FROM bets
        WHERE betting_match_id = %s AND discord_id = %s
        FOR UPDATE
    """, (betting_match_id, discord_id))

    previous_bet = cursor.fetchone()
    previous_amount = previous_bet[0] if previous_bet else 0

    available_balance = current_balance + previous_amount

    if amount > available_balance:
        conn.close()
        return False, f"Not enough coins. Available: {available_balance:,}."

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if previous_bet:
        cursor.execute("""
            UPDATE bets
            SET side = %s,
                amount = %s,
                created_at = %s
            WHERE betting_match_id = %s AND discord_id = %s
        """, (side, amount, now_text, betting_match_id, discord_id))
    else:
        cursor.execute("""
            INSERT INTO bets (
                betting_match_id, discord_id, side, amount, created_at
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (betting_match_id, discord_id, side, amount, now_text))

    cursor.execute("""
        UPDATE players
        SET coins = %s
        WHERE discord_id = %s
    """, (available_balance - amount, discord_id))

    recompute_betting_pools(cursor, betting_match_id)

    conn.commit()
    conn.close()

    return True, "Bet placed."


def get_bets_for_match(betting_match_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT b.discord_id, p.name, b.side, b.amount
        FROM bets b
        LEFT JOIN players p ON p.discord_id = b.discord_id
        WHERE b.betting_match_id = %s
        ORDER BY b.amount DESC
    """, (betting_match_id,))

    rows = cursor.fetchall()
    conn.close()

    return rows


def settle_betting_match(betting_match_id, winner):
    """
    Pays winning bettors from the losing pool, proportional to their winning stake.
    If nobody picked the winner, everyone is refunded.
    """
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status
        FROM betting_matches
        WHERE id = %s
        FOR UPDATE
    """, (betting_match_id,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"settled": False, "reason": "not_found"}

    if row[0] == "settled":
        conn.close()
        return {"settled": False, "reason": "already_settled"}

    if row[0] == "refunded":
        conn.close()
        return {"settled": False, "reason": "refunded"}

    cursor.execute("""
        SELECT discord_id, side, amount
        FROM bets
        WHERE betting_match_id = %s
    """, (betting_match_id,))

    bets = cursor.fetchall()

    total_pool = sum(row[2] for row in bets)
    winning_pool = sum(row[2] for row in bets if row[1] == winner)
    losing_pool = total_pool - winning_pool

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payouts = []

    if total_pool == 0:
        cursor.execute("""
            UPDATE betting_matches
            SET status = 'settled',
                winner = %s
            WHERE id = %s
        """, (winner, betting_match_id))

        conn.commit()
        conn.close()

        return {
            "settled": True,
            "total_pool": 0,
            "winning_pool": 0,
            "losing_pool": 0,
            "payouts": []
        }

    if winning_pool <= 0:
        # Nobody picked the winner. Refund all bets.
        for discord_id, side, amount in bets:
            cursor.execute("""
                UPDATE players
                SET coins = coins + %s
                WHERE discord_id = %s
            """, (amount, discord_id))

            cursor.execute("""
                INSERT INTO betting_payouts (
                    betting_match_id, discord_id, amount, reason, created_at
                )
                VALUES (%s, %s, %s, 'no_winners_refund', %s)
            """, (betting_match_id, discord_id, amount, now_text))

            payouts.append((discord_id, amount))

    else:
        for discord_id, side, amount in bets:
            if side != winner:
                continue

            profit = (amount * losing_pool) // winning_pool
            payout = amount + profit

            cursor.execute("""
                UPDATE players
                SET coins = coins + %s
                WHERE discord_id = %s
            """, (payout, discord_id))

            cursor.execute("""
                INSERT INTO betting_payouts (
                    betting_match_id, discord_id, amount, reason, created_at
                )
                VALUES (%s, %s, %s, 'settlement', %s)
            """, (betting_match_id, discord_id, payout, now_text))

            payouts.append((discord_id, payout))

    cursor.execute("""
        UPDATE betting_matches
        SET status = 'settled',
            winner = %s
        WHERE id = %s
    """, (winner, betting_match_id))

    conn.commit()
    conn.close()

    return {
        "settled": True,
        "total_pool": total_pool,
        "winning_pool": winning_pool,
        "losing_pool": losing_pool,
        "payouts": payouts
    }


def rollback_betting_settlement(betting_match_id):
    """
    Removes settlement payouts so a mistaken result can be corrected.
    Original reserved bets remain in place and the betting match returns to closed.
    """
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT discord_id, amount
        FROM betting_payouts
        WHERE betting_match_id = %s
    """, (betting_match_id,))

    payouts = cursor.fetchall()

    for discord_id, amount in payouts:
        cursor.execute("""
            UPDATE players
            SET coins = GREATEST(coins - %s, 0)
            WHERE discord_id = %s
        """, (amount, discord_id))

    cursor.execute("""
        DELETE FROM betting_payouts
        WHERE betting_match_id = %s
    """, (betting_match_id,))

    cursor.execute("""
        UPDATE betting_matches
        SET status = 'closed',
            winner = NULL
        WHERE id = %s AND status = 'settled'
    """, (betting_match_id,))

    conn.commit()
    conn.close()

    return len(payouts)


def refund_betting_match(betting_match_id):
    """
    Returns all original bet amounts. If the match was already settled,
    settlement payouts are reversed before original bets are refunded.
    """
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status
        FROM betting_matches
        WHERE id = %s
        FOR UPDATE
    """, (betting_match_id,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return 0

    if row[0] == "refunded":
        conn.close()
        return 0

    if row[0] == "settled":
        # Undo settlement payouts first, then refund original reserved bets.
        cursor.execute("""
            SELECT discord_id, amount
            FROM betting_payouts
            WHERE betting_match_id = %s
        """, (betting_match_id,))

        payouts = cursor.fetchall()

        for discord_id, amount in payouts:
            cursor.execute("""
                UPDATE players
                SET coins = GREATEST(coins - %s, 0)
                WHERE discord_id = %s
            """, (amount, discord_id))

        cursor.execute("""
            DELETE FROM betting_payouts
            WHERE betting_match_id = %s
        """, (betting_match_id,))

    cursor.execute("""
        SELECT discord_id, amount
        FROM bets
        WHERE betting_match_id = %s
    """, (betting_match_id,))

    bets = cursor.fetchall()

    for discord_id, amount in bets:
        cursor.execute("""
            UPDATE players
            SET coins = coins + %s
            WHERE discord_id = %s
        """, (amount, discord_id))

    cursor.execute("""
        UPDATE betting_matches
        SET status = 'refunded'
        WHERE id = %s
    """, (betting_match_id,))

    conn.commit()
    conn.close()

    return len(bets)


def get_bet_history(discord_id, limit=10):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT bm.id, bm.status, bm.winner, b.side, b.amount, b.created_at
        FROM bets b
        JOIN betting_matches bm ON bm.id = b.betting_match_id
        WHERE b.discord_id = %s
        ORDER BY b.id DESC
        LIMIT %s
    """, (discord_id, limit))

    rows = cursor.fetchall()
    conn.close()

    return rows



def save_mayram_player(discord_id, name):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO mayram_players (discord_id, name, rating, wins, losses)
        VALUES (%s, %s, 1000, 0, 0)
        ON CONFLICT(discord_id) DO UPDATE SET
            name = EXCLUDED.name
    """, (discord_id, name))

    conn.commit()
    conn.close()


def get_mayram_player(discord_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT discord_id, name, rating, wins, losses
        FROM mayram_players
        WHERE discord_id = %s
    """, (discord_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "discord_id": row[0],
        "name": row[1],
        "rating": row[2],
        "wins": row[3],
        "losses": row[4]
    }


def update_mayram_player_after_match(discord_id, won, rating_change=50):
    delta = rating_change if won else -rating_change

    conn = connect()
    cursor = conn.cursor()

    if won:
        cursor.execute("""
            UPDATE mayram_players
            SET rating = rating + %s,
                wins = wins + 1
            WHERE discord_id = %s
        """, (delta, discord_id))
    else:
        cursor.execute("""
            UPDATE mayram_players
            SET rating = rating + %s,
                losses = losses + 1
            WHERE discord_id = %s
        """, (delta, discord_id))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed > 0


def save_mayram_match(winner, blue_team, red_team, blue_rating, red_rating, rating_change=50):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO mayram_matches (
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


def get_mayram_leaderboard(limit=10, offset=0):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, rating, wins, losses
        FROM mayram_players
        ORDER BY rating DESC, wins DESC, name ASC
        LIMIT %s OFFSET %s
    """, (limit, offset))

    rows = cursor.fetchall()
    conn.close()

    return rows


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

