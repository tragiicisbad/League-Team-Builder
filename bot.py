import os
import itertools
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import (
    connect,
    setup_database,
    save_player,
    get_player,
    update_player_after_match,
    get_leaderboard,
    save_match,
    get_match_history,
    calculate_elo_change
)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

JOIN_EMOJI = "✅"
STAFF_ROLE_NAMES = ["Customs Admin", "Moderator"]
PROMOTION_CHANNEL_NAME = "general"
MATCH_HISTORY_CHANNEL_NAME = "match-history"
WINRATE_CHANNEL_NAME = "winrates"
RANK_ROLE_NAMES = [
    "Iron", "Bronze", "Silver", "Gold", "Platinum", "Emerald", "Diamond",
    "Master", "Grandmaster", "Challenger"
]
MAX_QUEUE_SIZE = 10
BASE_RATING_CHANGE = 15
MIN_RATING_CHANGE = 5
MAX_RATING_CHANGE = 30
MIN_LEADERBOARD_GAMES = 5

ROLES = ["Top", "Jungle", "Mid", "ADC", "Support"]

COLOR_QUEUE = discord.Color.blue()
COLOR_SUCCESS = discord.Color.green()
COLOR_WARNING = discord.Color.orange()
COLOR_ERROR = discord.Color.red()
COLOR_PROFILE = discord.Color.purple()
COLOR_BLUE_TEAM = discord.Color.from_rgb(52, 152, 219)
COLOR_RED_TEAM = discord.Color.from_rgb(231, 76, 60)

RANK_RATINGS = {
    "Iron": 800,
    "Bronze": 950,
    "Silver": 1100,
    "Gold": 1250,
    "Platinum": 1400,
    "Emerald": 1550,
    "Diamond": 1700,
    "Master": 1900,
    "Grandmaster": 2100,
    "Challenger": 2300
}

RANK_EMOJIS = {
    "Iron": "<:iron:1515345800354332783>",
    "Bronze": "<:bronze:1515345342374215821>",
    "Silver": "<:silver:1515345381595283559>",
    "Gold": "<:gold:1515345215328751657>",
    "Platinum": "<:platinum:1515345359612674188>",
    "Emerald": "<:emerald:1515346336453623859>",
    "Diamond": "<:diamond:1515345320169439404>",
    "Master": "<:master:1515345415594180618>",
    "Grandmaster": "<:grandmaster:1515345456786571325>",
    "Challenger": "<:challenger:1515345436527952084>"
}

ROLE_EMOJIS = {
    "Top": "<:top:1515345567553683589>",
    "Jungle": "<:jungle:1515345505142444125>",
    "Mid": "<:mid:1515345549086298192>",
    "ADC": "<:bot:1515345591218208810>",
    "Support": "<:support:1515347187473580123>",
    "Fill": "🎲"
}


def rank_emoji(rank):
    return RANK_EMOJIS.get(rank, "")


def role_emoji(role):
    return ROLE_EMOJIS.get(role, "")


def option_emoji(emoji_text):
    """
    Converts a custom emoji string like <:top:123> into a Discord PartialEmoji
    so it can appear inside select menu options.
    Unicode emoji such as 🎲 and ✅ still work normally.
    """
    try:
        return discord.PartialEmoji.from_str(emoji_text)
    except Exception:
        return emoji_text


def rank_option(rank):
    return discord.SelectOption(
        label=rank,
        emoji=option_emoji(rank_emoji(rank)),
        description=f"Starting rating: {RANK_RATINGS[rank]}"
    )


def role_option(role, description=None):
    return discord.SelectOption(
        label=role,
        emoji=option_emoji(role_emoji(role)),
        description=description
    )


def avoid_role_display(role):
    if not role or role == "None":
        return "None"
    return f"{role_emoji(role)} {role}"


def normalize_rank(rank):
    for valid_rank in RANK_RATINGS:
        if valid_rank.lower() == rank.lower():
            return valid_rank
    return None


def normalize_role(role):
    for valid_role in ROLES:
        if valid_role.lower() == role.lower():
            return valid_role
    return None


def rank_for_rating(rating):
    """
    Returns the highest rank a rating qualifies for.
    Example: 1710 -> Diamond
    """
    qualified_rank = "Iron"

    for rank, required_rating in RANK_RATINGS.items():
        if rating >= required_rating:
            qualified_rank = rank

    return qualified_rank


def selected_role_rating(player, selected_role):
    """
    Returns the rating to use for a selected preference role.
    If the player selected Fill, use the average of all role ratings.
    """
    if selected_role == "Fill":
        role_values = [player["role_ratings"][role] for role in ROLES]
        return round(sum(role_values) / len(role_values))

    return player["role_ratings"][selected_role]


def calculate_overall_from_selected_roles(player):
    """
    Overall rating is now the average of the player's selected primary and secondary roles.
    """
    primary_rating = selected_role_rating(player, player["primary_role"])
    secondary_rating = selected_role_rating(player, player["secondary_role"])

    return round((primary_rating + secondary_rating) / 2)


def update_overall_rating_from_selected_roles(discord_id):
    """
    Recalculates and saves overall rating from selected primary/secondary roles.
    Does not change role ratings.
    """
    player = get_player(discord_id)

    if not player:
        return None

    new_overall = calculate_overall_from_selected_roles(player)

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET rating = %s
        WHERE discord_id = %s
    """, (new_overall, discord_id))

    conn.commit()
    conn.close()

    return new_overall


async def sync_member_rank_role(member, overall_rating):
    """
    Updates the Discord rank role based on overall rating.
    The bot needs Manage Roles permission and must be above the rank roles.
    """
    if member is None or member.guild is None:
        return

    new_rank = rank_for_rating(overall_rating)

    rank_roles = [
        role for role in member.guild.roles
        if role.name in RANK_ROLE_NAMES
    ]

    role_to_add = discord.utils.get(member.guild.roles, name=new_rank)

    if role_to_add is None:
        print(f"Rank role not found: {new_rank}")
        return

    roles_to_remove = [
        role for role in rank_roles
        if role in member.roles and role.name != new_rank
    ]

    try:
        if roles_to_remove:
            await member.remove_roles(
                *roles_to_remove,
                reason="League bot rank role sync"
            )

        if role_to_add not in member.roles:
            await member.add_roles(
                role_to_add,
                reason="League bot rank role sync"
            )

    except discord.Forbidden:
        print("Could not update rank role: missing Manage Roles permission or role hierarchy issue.")
    except Exception as e:
        print(f"Could not update rank role: {e}")


def check_role_promotion(player, assigned_role, rating_change):
    """
    Checks whether a player's role rating crossed into a new rank after a win.
    Only announces promotions, not demotions.
    """
    old_rating = role_rating(player, assigned_role)
    new_rating = old_rating + rating_change

    old_rank = rank_for_rating(old_rating)
    new_rank = rank_for_rating(new_rating)

    if new_rank == old_rank:
        return None

    if RANK_RATINGS[new_rank] <= RANK_RATINGS[old_rank]:
        return None

    return {
        "discord_id": player["discord_id"],
        "name": player["name"],
        "role": assigned_role,
        "old_rating": old_rating,
        "new_rating": new_rating,
        "old_rank": old_rank,
        "new_rank": new_rank
    }


def get_promotion_channel(guild):
    if guild is None:
        return None

    return discord.utils.get(guild.text_channels, name=PROMOTION_CHANNEL_NAME)


async def send_promotion_announcement(ctx, promotion):
    channel = get_promotion_channel(ctx.guild)

    if channel is None:
        print(f"Could not find promotion channel named #{PROMOTION_CHANNEL_NAME}")
        return

    embed = discord.Embed(
        title="🎉 Role Promotion!",
        description=(
            f"<@{promotion['discord_id']}> has been promoted!\n\n"
            f"{rank_emoji(promotion['new_rank'])} **{promotion['new_rank']}** "
            f"on {role_emoji(promotion['role'])} **{promotion['role']}**"
        ),
        color=COLOR_SUCCESS
    )

    embed.add_field(
        name="Rating",
        value=f"**{promotion['old_rating']}** → **{promotion['new_rating']}**",
        inline=False
    )

    embed.set_footer(text="Keep climbing.")

    await channel.send(
        content=f"🎉 <@{promotion['discord_id']}> just ranked up!",
        embed=embed
    )


def role_column(role):
    return {
        "Top": "top_rating",
        "Jungle": "jungle_rating",
        "Mid": "mid_rating",
        "ADC": "adc_rating",
        "Support": "support_rating"
    }[role]


def update_player_rank_manual(discord_id, rank, rating):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET rank = %s, rating = %s
        WHERE discord_id = %s
    """, (rank, rating, discord_id))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed > 0


def update_player_rating_manual(discord_id, rating):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET rating = %s
        WHERE discord_id = %s
    """, (rating, discord_id))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed > 0


def update_player_role_rating_manual(discord_id, role, rating):
    column = role_column(role)

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(f"""
        UPDATE players
        SET {column} = %s
        WHERE discord_id = %s
    """, (rating, discord_id))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed > 0


def update_player_avoided_role_manual(discord_id, avoided_role):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET avoided_role = %s
        WHERE discord_id = %s
    """, (avoided_role, discord_id))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed > 0


def update_player_role_preferences_manual(discord_id, primary_role, secondary_role, avoided_role):
    """
    Updates only role preferences.
    Does NOT reset rank, overall rating, role ratings, wins, losses, or match history.
    """
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET primary_role = %s,
            secondary_role = %s,
            avoided_role = %s
        WHERE discord_id = %s
    """, (primary_role, secondary_role, avoided_role, discord_id))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed > 0


def reset_player_ratings_manual(discord_id):
    player = get_player(discord_id)

    if not player:
        return False

    base_rating = RANK_RATINGS[player["rank"]]
    role_ratings = make_manual_role_ratings(
        base_rating,
        player["primary_role"],
        player["secondary_role"]
    )

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET rating = %s,
            top_rating = %s,
            jungle_rating = %s,
            mid_rating = %s,
            adc_rating = %s,
            support_rating = %s,
            wins = 0,
            losses = 0
        WHERE discord_id = %s
    """, (
        base_rating,
        role_ratings["Top"],
        role_ratings["Jungle"],
        role_ratings["Mid"],
        role_ratings["ADC"],
        role_ratings["Support"],
        discord_id
    ))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed > 0


def make_manual_role_ratings(base_rating, primary_role, secondary_role):
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


def clear_match_history_manual():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM matches")
    deleted_matches = cursor.rowcount

    # Reset PostgreSQL sequence for match IDs.
    cursor.execute("ALTER SEQUENCE matches_id_seq RESTART WITH 1")

    conn.commit()
    conn.close()

    return deleted_matches


def reset_all_players_ratings_manual():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT discord_id, rank, primary_role, secondary_role
        FROM players
    """)
    players = cursor.fetchall()

    for discord_id, rank, primary_role, secondary_role in players:
        base_rating = RANK_RATINGS[rank]
        role_ratings = make_manual_role_ratings(base_rating, primary_role, secondary_role)

        cursor.execute("""
            UPDATE players
            SET rating = %s,
                top_rating = %s,
                jungle_rating = %s,
                mid_rating = %s,
                adc_rating = %s,
                support_rating = %s,
                wins = 0,
                losses = 0
            WHERE discord_id = %s
        """, (
            base_rating,
            role_ratings["Top"],
            role_ratings["Jungle"],
            role_ratings["Mid"],
            role_ratings["ADC"],
            role_ratings["Support"],
            discord_id
        ))

    conn.commit()
    conn.close()

    return len(players)



def remove_player_from_database(discord_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM players
        WHERE discord_id = %s
    """, (discord_id,))

    rows_deleted = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_deleted > 0


def refresh_player_in_queues(discord_id):
    player = get_player(discord_id)

    if not player:
        return

    if discord_id in player_queue:
        player_queue[discord_id] = player

    if discord_id in waitlist_queue:
        waitlist_queue[discord_id] = player


queue_message_id = None
queue_channel_id = None

player_queue = {}
waitlist_queue = {}
queue_locked = False
last_blue_team = []
last_red_team = []
last_teams_message_id = None
last_teams_channel_id = None
winrate_message_id = None


def is_admin(ctx):
    if ctx.author.guild_permissions.administrator:
        return True

    return any(
        role.name in STAFF_ROLE_NAMES
        for role in ctx.author.roles
    )


async def require_admin(ctx):
    if is_admin(ctx):
        return True

    embed = discord.Embed(
        title="Admin Only",
        description=(
            "You need Administrator permissions or one of these roles:\n"
            + ", ".join(f"`{role}`" for role in STAFF_ROLE_NAMES)
        ),
        color=COLOR_ERROR
    )
    await ctx.send(embed=embed)
    return False


def is_admin_member(member):
    if member.guild_permissions.administrator:
        return True

    return any(
        role.name in STAFF_ROLE_NAMES
        for role in member.roles
    )


def role_rating(player, role):
    return player["role_ratings"].get(role, player["rating"])


def clean_player_line(player):
    """
    Compact queue line to prevent Discord embeds from cutting off around 7-8 players.
    Format:
    RankEmoji Name — Primary/Secondary — Rating — Avoid
    """
    avoided_role = player.get("avoided_role", "None")

    avoid_text = ""
    if avoided_role != "None":
        avoid_text = f" • Avoid {role_emoji(avoided_role)}"

    current_overall = calculate_overall_from_selected_roles(player)
    current_rank = rank_for_rating(current_overall)

    return (
        f"{rank_emoji(current_rank)} **{player['name']}** — "
        f"{role_emoji(player['primary_role'])}/{role_emoji(player['secondary_role'])} — "
        f"**{current_overall}**{avoid_text}"
    )


def clean_waitlist_line(index, player):
    avoided_role = player.get("avoided_role", "None")

    avoid_text = ""
    if avoided_role != "None":
        avoid_text = f" • Avoid {role_emoji(avoided_role)}"

    current_overall = calculate_overall_from_selected_roles(player)
    current_rank = rank_for_rating(current_overall)

    return (
        f"**#{index}** {rank_emoji(current_rank)} **{player['name']}** — "
        f"{role_emoji(player['primary_role'])}/{role_emoji(player['secondary_role'])} — "
        f"**{current_overall}**{avoid_text}"
    )


def clean_assigned_line(player):
    assigned_role = player["assigned_role"]
    assigned_rating = role_rating(player, assigned_role)
    avoided_role = player.get("avoided_role", "None")

    avoid_warning = ""
    if avoided_role == assigned_role:
        avoid_warning = " ⚠️ avoided"

    current_rank = rank_for_rating(assigned_rating)

    return (
        f"{role_emoji(assigned_role)} <@{player['discord_id']}>{avoid_warning}\n"
        f"{rank_emoji(current_rank)} **{assigned_rating}** role rating"
    )


def find_player_on_current_teams(member_id):
    for team_name, team in [("blue", last_blue_team), ("red", last_red_team)]:
        for index, player in enumerate(team):
            if player["discord_id"] == member_id:
                return team_name, team, index, player

    return None, None, None, None


def find_player_by_swap_arg(arg):
    """
    Finds a player on the current teams by mention, Discord ID, test-player ID,
    or exact player name. This lets admins swap real players and test players.
    """
    cleaned_arg = str(arg).strip()
    cleaned_arg = cleaned_arg.replace("<@", "").replace(">", "").replace("!", "")

    try:
        discord_id = int(cleaned_arg)
        return find_player_on_current_teams(discord_id)
    except ValueError:
        pass

    for team_name, team in [("blue", last_blue_team), ("red", last_red_team)]:
        for index, player in enumerate(team):
            if player["name"].lower() == cleaned_arg.lower():
                return team_name, team, index, player

    return None, None, None, None


def player_swap_display(ctx, player):
    member = ctx.guild.get_member(player["discord_id"]) if ctx.guild else None

    if member:
        return member.mention

    return player["name"]


def calculate_current_team_totals():
    blue_total = sum(role_rating(p, p["assigned_role"]) for p in last_blue_team)
    red_total = sum(role_rating(p, p["assigned_role"]) for p in last_red_team)
    return blue_total, red_total


def build_teams_embed(title="Balanced Teams Generated", description=None):
    blue_total, red_total = calculate_current_team_totals()

    rating_diff = abs(blue_total - red_total)

    lane_diff = 0
    for role in ROLES:
        blue_player = next((p for p in last_blue_team if p["assigned_role"] == role), None)
        red_player = next((p for p in last_red_team if p["assigned_role"] == role), None)

        if blue_player and red_player:
            lane_diff += abs(role_rating(blue_player, role) - role_rating(red_player, role))

    role_penalty_total = (
        sum(role_penalty(p, p["assigned_role"]) for p in last_blue_team)
        + sum(role_penalty(p, p["assigned_role"]) for p in last_red_team)
    )

    if description is None:
        description = "Teams were balanced by role fit, lane matchup rating, and total team rating. The active queue is now locked."

    embed = discord.Embed(
        title=title,
        description=description,
        color=COLOR_SUCCESS
    )

    embed.add_field(
        name=f"Blue Team — {blue_total} Rating",
        value="\n\n".join(clean_assigned_line(p) for p in last_blue_team),
        inline=True
    )

    embed.add_field(
        name=f"Red Team — {red_total} Rating",
        value="\n\n".join(clean_assigned_line(p) for p in last_red_team),
        inline=True
    )

    embed.add_field(
        name="Balance Stats",
        value=(
            f"**Team Rating Difference:** {rating_diff}\n"
            f"**Lane Matchup Difference:** {int(lane_diff)}\n"
            f"**Role Penalty:** {role_penalty_total}\n"
            f"**Waitlisted Players:** {len(waitlist_queue)}"
        ),
        inline=False
    )

    embed.set_footer(text="Use !swap @player1 @player2 to adjust teams. Result buttons are posted in #match-history.")
    return embed


def simple_match_history_team_lines(team):
    return "\n".join(
        f"{role_emoji(player['assigned_role'])} **{player['assigned_role']}** — {player['name']}"
        for player in team
    )


async def post_generated_teams_to_match_history(guild):
    if guild is None:
        return

    channel = discord.utils.get(guild.text_channels, name=MATCH_HISTORY_CHANNEL_NAME)

    if channel is None:
        print(f"Could not find #{MATCH_HISTORY_CHANNEL_NAME} channel.")
        return

    embed = discord.Embed(
        title="New Match Generated",
        description="Admins can report the winner using the buttons below.",
        color=COLOR_QUEUE
    )

    embed.add_field(
        name="Blue Team",
        value=simple_match_history_team_lines(last_blue_team),
        inline=True
    )

    embed.add_field(
        name="Red Team",
        value=simple_match_history_team_lines(last_red_team),
        inline=True
    )

    await channel.send(embed=embed, view=ResultView())


async def update_teams_message(embed=None):
    if last_teams_message_id is None or last_teams_channel_id is None:
        return False

    channel = bot.get_channel(last_teams_channel_id)

    if channel is None:
        return False

    try:
        msg = await channel.fetch_message(last_teams_message_id)

        if embed is None:
            embed = build_teams_embed(
                title="Teams Updated",
                description="Teams were manually adjusted by an admin."
            )

        await msg.edit(embed=embed)
        return True

    except Exception as e:
        print(f"Could not update teams message: {e}")
        return False


def add_to_queue_or_waitlist(user_id, player):
    """
    First 10 players go into the active queue.
    Any player after 10 automatically goes to the waitlist.
    """
    if user_id in player_queue:
        return "active"

    if user_id in waitlist_queue:
        return "waitlist"

    if queue_locked:
        waitlist_queue[user_id] = player
        return "waitlist_locked"

    if len(player_queue) < MAX_QUEUE_SIZE:
        player_queue[user_id] = player
        return "active"

    waitlist_queue[user_id] = player
    return "waitlist"


def promote_next_waitlisted_player():
    """
    If someone leaves the active queue, move the first waitlisted player into active queue.
    """
    if len(player_queue) >= MAX_QUEUE_SIZE:
        return None

    if not waitlist_queue:
        return None

    next_user_id = next(iter(waitlist_queue))
    promoted_player = waitlist_queue.pop(next_user_id)
    player_queue[next_user_id] = promoted_player

    return promoted_player


async def send_embed(ctx, title, description, color):
    embed = discord.Embed(title=title, description=description, color=color)
    await ctx.send(embed=embed)


def add_queue_chunks(embed, title, lines, chunk_size=5):
    """
    Discord embed fields have size limits.
    Keeping each player on one compact line and splitting into chunks prevents cutoffs.
    """
    if not lines:
        embed.add_field(name=title, value="No players.", inline=False)
        return

    for index in range(0, len(lines), chunk_size):
        chunk = lines[index:index + chunk_size]
        start_number = index + 1
        end_number = index + len(chunk)

        field_title = title
        if len(lines) > chunk_size:
            field_title = f"{title} #{start_number}-{end_number}"

        embed.add_field(
            name=field_title,
            value="\n".join(chunk),
            inline=False
        )


def build_queue_embed():
    lock_status = "🔒 Locked" if queue_locked else "🔓 Open"

    embed = discord.Embed(
        title=f"League 5v5 Queue ({len(player_queue)}/{MAX_QUEUE_SIZE}) — {lock_status}",
        description=(
            "React with ✅ to join. First 10 are active. Extra players go to waitlist."
        ),
        color=COLOR_QUEUE
    )

    if not player_queue:
        embed.add_field(name="Active Queue", value="No players queued yet.", inline=False)
    else:
        active_lines = [
            f"**#{index}** {clean_player_line(player)}"
            for index, player in enumerate(player_queue.values(), start=1)
        ]

        add_queue_chunks(
            embed,
            f"Active Queue ({len(player_queue)}/{MAX_QUEUE_SIZE})",
            active_lines,
            chunk_size=5
        )

        ratings = [player["rating"] for player in player_queue.values()]
        avg_rating = round(sum(ratings) / len(ratings))
        highest = max(ratings)
        lowest = min(ratings)

        embed.add_field(
            name="Queue Stats",
            value=(
                f"**Avg:** {avg_rating}  •  "
                f"**High:** {highest}  •  "
                f"**Low:** {lowest}"
            ),
            inline=False
        )

    if waitlist_queue:
        waitlist_lines = [
            clean_waitlist_line(index, player)
            for index, player in enumerate(waitlist_queue.values(), start=1)
        ]

        add_queue_chunks(
            embed,
            f"Waitlist ({len(waitlist_queue)})",
            waitlist_lines,
            chunk_size=5
        )
    else:
        embed.add_field(name="Waitlist", value="No players waiting.", inline=False)

    embed.set_footer(text="Use !teams when 10 players are active. After !result, a fresh queue post is created.")
    return embed

async def update_queue_message():
    if queue_message_id is None or queue_channel_id is None:
        return

    channel = bot.get_channel(queue_channel_id)
    if channel is None:
        return

    try:
        msg = await channel.fetch_message(queue_message_id)
        await msg.edit(embed=build_queue_embed())
    except Exception as e:
        print(f"Could not update queue message: {e}")


async def delete_queue_message():
    global queue_message_id, queue_channel_id

    if queue_message_id is None or queue_channel_id is None:
        return None

    channel = bot.get_channel(queue_channel_id)

    if channel is None:
        queue_message_id = None
        queue_channel_id = None
        return None

    try:
        msg = await channel.fetch_message(queue_message_id)
        await msg.delete()
    except discord.NotFound:
        # Queue post was already deleted. Clear the stale saved IDs.
        pass
    except discord.Forbidden:
        print("Could not delete queue message: missing permissions.")
    except Exception as e:
        print(f"Could not delete queue message: {e}")

    queue_message_id = None
    queue_channel_id = None

    return channel


async def create_queue_message(channel, replace_existing=True):
    global queue_message_id, queue_channel_id

    if channel is None:
        return None

    if replace_existing and queue_message_id is not None:
        await delete_queue_message()

    msg = await channel.send(embed=build_queue_embed())
    queue_message_id = msg.id
    queue_channel_id = channel.id

    try:
        await msg.add_reaction(JOIN_EMOJI)
    except Exception as e:
        print(f"Could not add join reaction to queue message: {e}")

    return msg


class SignupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.signup_data = {}

    async def try_save_signup(self, interaction: discord.Interaction, incomplete_message: str):
        user_id = interaction.user.id
        data = self.signup_data[user_id]
        required = ["rank", "rating", "primary_role", "secondary_role"]

        if not all(field in data for field in required):
            await interaction.response.send_message(incomplete_message, ephemeral=True)
            return

        primary_role = data["primary_role"]
        secondary_role = data["secondary_role"]

        if primary_role == secondary_role:
            await interaction.response.send_message(
                "Your primary and secondary role cannot be the same. Please choose a different secondary role.",
                ephemeral=True
            )
            return

        save_player(
            discord_id=user_id,
            name=interaction.user.display_name,
            rank=data["rank"],
            rating=data["rating"],
            primary_role=primary_role,
            secondary_role=secondary_role,
            avoided_role=data.get("avoided_role", "None")
        )

        new_overall = update_overall_rating_from_selected_roles(user_id)
        await sync_member_rank_role(interaction.user, new_overall)

        await interaction.response.send_message(
            (
                "Signup complete and saved.\n"
                f"Overall Rating: **{new_overall}** "
                f"({rank_emoji(rank_for_rating(new_overall))} **{rank_for_rating(new_overall)}**)"
            ),
            ephemeral=True
        )

    @discord.ui.select(
        placeholder="Select your League rank",
        options=[
            rank_option(rank)
            for rank in RANK_RATINGS
        ]
    )
    async def rank_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        user_id = interaction.user.id
        self.signup_data.setdefault(user_id, {})

        rank = select.values[0]
        self.signup_data[user_id]["rank"] = rank
        self.signup_data[user_id]["rating"] = RANK_RATINGS[rank]

        await interaction.response.send_message(
            f"Rank saved as **{rank}**. Starting rating: **{RANK_RATINGS[rank]}**.",
            ephemeral=True
        )

    @discord.ui.select(
        placeholder="Select your primary role",
        options=[
            role_option("Top", "Primary solo lane"),
            role_option("Jungle", "Primary jungle"),
            role_option("Mid", "Primary mid lane"),
            role_option("ADC", "Primary bot carry"),
            role_option("Support", "Primary support"),
            role_option("Fill", "Comfortable filling")
        ]
    )
    async def primary_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        user_id = interaction.user.id
        self.signup_data.setdefault(user_id, {})
        self.signup_data[user_id]["primary_role"] = select.values[0]

        if self.signup_data[user_id].get("secondary_role") == select.values[0]:
            await interaction.response.send_message(
                "Primary role saved, but it matches your secondary role. Please choose a different secondary role.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Primary role saved as **{select.values[0]}**.",
            ephemeral=True
        )

    @discord.ui.select(
        placeholder="Select your secondary role",
        options=[
            role_option("Top", "Secondary solo lane"),
            role_option("Jungle", "Secondary jungle"),
            role_option("Mid", "Secondary mid lane"),
            role_option("ADC", "Secondary bot carry"),
            role_option("Support", "Secondary support"),
            role_option("Fill", "Can fill if needed")
        ]
    )
    async def secondary_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        user_id = interaction.user.id
        self.signup_data.setdefault(user_id, {})
        self.signup_data[user_id]["secondary_role"] = select.values[0]

        if self.signup_data[user_id].get("primary_role") == select.values[0]:
            await interaction.response.send_message(
                "Your secondary role cannot be the same as your primary role. Please choose a different secondary role.",
                ephemeral=True
            )
            return

        await self.try_save_signup(
            interaction,
            "Secondary role saved. Make sure you also selected rank and primary role."
        )


    @discord.ui.select(
        placeholder="Select a role to avoid",
        options=[
            discord.SelectOption(label="None", emoji="✅", description="I do not want to avoid any role"),
            role_option("Top", "Avoid top if possible"),
            role_option("Jungle", "Avoid jungle if possible"),
            role_option("Mid", "Avoid mid if possible"),
            role_option("ADC", "Avoid ADC if possible"),
            role_option("Support", "Avoid support if possible")
        ]
    )
    async def avoided_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        user_id = interaction.user.id
        self.signup_data.setdefault(user_id, {})
        self.signup_data[user_id]["avoided_role"] = select.values[0]

        await self.try_save_signup(
            interaction,
            "Avoided role saved. Make sure you also selected rank, primary role, and secondary role."
        )


class RoleChangeView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=300)
        self.player = player
        self.role_data = {
            "primary_role": player["primary_role"],
            "secondary_role": player["secondary_role"],
            "avoided_role": player.get("avoided_role", "None")
        }

    async def save_if_valid(self, interaction: discord.Interaction):
        primary_role = self.role_data["primary_role"]
        secondary_role = self.role_data["secondary_role"]
        avoided_role = self.role_data.get("avoided_role", "None")

        if primary_role == secondary_role:
            await interaction.response.send_message(
                "Your primary and secondary role cannot be the same. Please choose a different role.",
                ephemeral=True
            )
            return

        updated = update_player_role_preferences_manual(
            discord_id=interaction.user.id,
            primary_role=primary_role,
            secondary_role=secondary_role,
            avoided_role=avoided_role
        )

        if not updated:
            await interaction.response.send_message(
                "Could not update your roles. Make sure you have signed up first.",
                ephemeral=True
            )
            return

        new_overall = update_overall_rating_from_selected_roles(interaction.user.id)
        await sync_member_rank_role(interaction.user, new_overall)

        refresh_player_in_queues(interaction.user.id)
        await update_queue_message()

        await interaction.response.send_message(
            (
                "Role preferences updated without resetting your role ratings or match history.\n\n"
                f"Primary: {role_emoji(primary_role)} **{primary_role}**\n"
                f"Secondary: {role_emoji(secondary_role)} **{secondary_role}**\n"
                f"Avoid: **{avoid_role_display(avoided_role)}**\n"
                f"New Overall Rating: **{new_overall}** "
                f"({rank_emoji(rank_for_rating(new_overall))} **{rank_for_rating(new_overall)}**)"
            ),
            ephemeral=True
        )

    @discord.ui.select(
        placeholder="Change your primary role",
        options=[
            role_option("Top", "Primary solo lane"),
            role_option("Jungle", "Primary jungle"),
            role_option("Mid", "Primary mid lane"),
            role_option("ADC", "Primary bot carry"),
            role_option("Support", "Primary support"),
            role_option("Fill", "Comfortable filling")
        ]
    )
    async def primary_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.player["discord_id"]:
            await interaction.response.send_message("This role menu is not for you.", ephemeral=True)
            return

        self.role_data["primary_role"] = select.values[0]

        await self.save_if_valid(interaction)

    @discord.ui.select(
        placeholder="Change your secondary role",
        options=[
            role_option("Top", "Secondary solo lane"),
            role_option("Jungle", "Secondary jungle"),
            role_option("Mid", "Secondary mid lane"),
            role_option("ADC", "Secondary bot carry"),
            role_option("Support", "Secondary support"),
            role_option("Fill", "Can fill if needed")
        ]
    )
    async def secondary_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.player["discord_id"]:
            await interaction.response.send_message("This role menu is not for you.", ephemeral=True)
            return

        self.role_data["secondary_role"] = select.values[0]

        await self.save_if_valid(interaction)

    @discord.ui.select(
        placeholder="Change your avoided role",
        options=[
            discord.SelectOption(label="None", emoji="✅", description="I do not want to avoid any role"),
            role_option("Top", "Avoid top if possible"),
            role_option("Jungle", "Avoid jungle if possible"),
            role_option("Mid", "Avoid mid if possible"),
            role_option("ADC", "Avoid ADC if possible"),
            role_option("Support", "Avoid support if possible")
        ]
    )
    async def avoided_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.player["discord_id"]:
            await interaction.response.send_message("This role menu is not for you.", ephemeral=True)
            return

        self.role_data["avoided_role"] = select.values[0]

        await self.save_if_valid(interaction)


@bot.event
async def on_ready():
    setup_database()

    try:
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} slash commands to {guild.name}")

    except Exception as e:
        print(f"Could not sync slash commands: {e}")

    print(f"Logged in as {bot.user}")


@bot.hybrid_command(name="signup")
async def signup(ctx):
    embed = discord.Embed(
        title="League 5v5 Signup",
        description=(
            "Select your rank, primary role, secondary role, and optional avoided role below.\n\n"
            "Your choices are saved automatically once your rank, primary role, and secondary role are selected."
        ),
        color=COLOR_SUCCESS
    )
    embed.add_field(
        name="Ranks",
        value="<:iron:1515345800354332783> **Iron** — 800\n<:bronze:1515345342374215821> **Bronze** — 950\n<:silver:1515345381595283559> **Silver** — 1100\n<:gold:1515345215328751657> **Gold** — 1250\n<:platinum:1515345359612674188> **Platinum** — 1400\n<:emerald:1515346336453623859> **Emerald** — 1550\n<:diamond:1515345320169439404> **Diamond** — 1700\n<:master:1515345415594180618> **Master** — 1900\n<:grandmaster:1515345456786571325> **Grandmaster** — 2100\n<:challenger:1515345436527952084> **Challenger** — 2300",
        inline=True
    )
    embed.add_field(
        name="Roles",
        value="<:top:1515345567553683589> **Top**\n<:jungle:1515345505142444125> **Jungle**\n<:mid:1515345549086298192> **Mid**\n<:bot:1515345591218208810> **ADC**\n<:support:1515347187473580123> **Support**\n🎲 **Fill**",
        inline=True
    )
    embed.add_field(
        name="How Ratings Work",
        value=(
            "Your main role starts at your rank rating.\n"
            "Your secondary starts slightly lower.\n"
            "Off-roles start much lower unless you choose Fill.\n"
            "Primary and secondary roles cannot be the same.\n"
            "Avoided roles are heavily penalized during team generation."
        ),
        inline=False
    )
    if ctx.interaction:
        await ctx.interaction.response.send_message(
            embed=embed,
            view=SignupView(),
            ephemeral=True
        )
    else:
        await ctx.send(
            "Use the Discord slash command `/signup` from the command popup to open the private signup menu. "
            "If it does not appear yet, restart the bot once and wait a few seconds."
        )


@bot.hybrid_command(name="changeroles")
async def changeroles(ctx):
    player = get_player(ctx.author.id)

    if not player:
        await send_embed(
            ctx,
            "Profile Not Found",
            "You need to use `/signup` before changing roles.",
            COLOR_ERROR
        )
        return

    embed = discord.Embed(
        title="Change Role Preferences",
        description=(
            "Update your primary, secondary, or avoided role.\n\n"
            "**This will not reset your rank, rating, role ratings, wins, losses, or match history.**"
        ),
        color=COLOR_PROFILE
    )

    embed.add_field(
        name="Current Roles",
        value=(
            f"Primary: {role_emoji(player['primary_role'])} **{player['primary_role']}**\n"
            f"Secondary: {role_emoji(player['secondary_role'])} **{player['secondary_role']}**\n"
            f"Avoid: **{avoid_role_display(player.get('avoided_role', 'None'))}**"
        ),
        inline=False
    )

    if ctx.interaction:
        await ctx.interaction.response.send_message(
            embed=embed,
            view=RoleChangeView(player),
            ephemeral=True
        )
    else:
        await ctx.send(
            embed=embed,
            view=RoleChangeView(player)
        )


@bot.command()
async def profile(ctx, member: discord.Member = None):
    member = member or ctx.author
    player = get_player(member.id)

    if not player:
        await send_embed(ctx, "Profile Not Found", f"{member.display_name} has not signed up yet. Use `!signup`.", COLOR_ERROR)
        return

    role_lines = []
    for role in ROLES:
        role_lines.append(f"{role_emoji(role)} **{role}:** {player['role_ratings'][role]}")

    embed = discord.Embed(title=f"{player['name']}'s Profile", color=COLOR_PROFILE)

    calculated_overall = calculate_overall_from_selected_roles(player)
    current_rank = rank_for_rating(calculated_overall)

    embed.add_field(name="Rank", value=f"{rank_emoji(current_rank)} {current_rank}", inline=True)
    embed.add_field(name="Overall Rating", value=str(calculated_overall), inline=True)
    embed.add_field(name="Record", value=f"{player['wins']}W / {player['losses']}L", inline=True)
    embed.add_field(
        name="Preferred Roles",
        value=(
            f"{role_emoji(player['primary_role'])} {player['primary_role']}\n"
            f"{role_emoji(player['secondary_role'])} {player['secondary_role']}"
        ),
        inline=False
    )
    embed.add_field(name="Avoided Role", value=avoid_role_display(player.get("avoided_role", "None")), inline=False)
    embed.add_field(name="Role Ratings", value="\n".join(role_lines), inline=False)

    await ctx.send(embed=embed)


@bot.command()
async def queuepost(ctx):
    try:
        await create_queue_message(ctx.channel, replace_existing=True)

        await ctx.send(
            embed=discord.Embed(
                title="Queue Post Refreshed",
                description="A fresh queue post has been created. Any old queue post was removed if it still existed.",
                color=COLOR_SUCCESS
            ),
            delete_after=8
        )
    except Exception as e:
        print(f"Queuepost error: {e}")

        await ctx.send(
            embed=discord.Embed(
                title="Queue Post Error",
                description=(
                    "The bot could not create the queue post. "
                    "Check that it has permission to send messages, embed links, and add reactions in this channel."
                ),
                color=COLOR_ERROR
            )
        )


@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    if payload.message_id != queue_message_id:
        return

    if str(payload.emoji) != JOIN_EMOJI:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)

    if member is None:
        return

    player = get_player(payload.user_id)

    if not player:
        channel = bot.get_channel(payload.channel_id)
        await channel.send(
            embed=discord.Embed(
                title="Signup Required",
                description=f"{member.mention}, use `!signup` before joining the queue.",
                color=COLOR_WARNING
            )
        )
        return

    result = add_to_queue_or_waitlist(payload.user_id, player)

    if result in ["waitlist", "waitlist_locked"]:
        channel = bot.get_channel(payload.channel_id)
        if channel:
            reason = (
                "the queue is currently locked"
                if result == "waitlist_locked"
                else "the active queue is full"
            )
            await channel.send(
                embed=discord.Embed(
                    title="Added to Waitlist",
                    description=f"{member.mention}, {reason}, so you were automatically added to the waitlist.",
                    color=COLOR_WARNING
                )
            )

    await update_queue_message()


@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == bot.user.id:
        return

    if payload.message_id != queue_message_id:
        return

    if str(payload.emoji) != JOIN_EMOJI:
        return

    removed_from_active = False

    if payload.user_id in player_queue:
        if queue_locked:
            await update_queue_message()
            return

        del player_queue[payload.user_id]
        removed_from_active = True

    if payload.user_id in waitlist_queue:
        del waitlist_queue[payload.user_id]

    if removed_from_active:
        promoted_player = promote_next_waitlisted_player()

        if promoted_player and queue_channel_id:
            channel = bot.get_channel(queue_channel_id)
            if channel:
                await channel.send(
                    embed=discord.Embed(
                        title="Waitlist Promotion",
                        description=f"**{promoted_player['name']}** was automatically moved into the active queue.",
                        color=COLOR_SUCCESS
                    )
                )

    await update_queue_message()


@bot.command(name="queue")
async def show_queue(ctx):
    await ctx.send(embed=build_queue_embed())


@bot.command()
async def waitlist(ctx):
    if not waitlist_queue:
        await send_embed(ctx, "Waitlist", "No players are currently waiting.", COLOR_QUEUE)
        return

    lines = [
        clean_waitlist_line(index, player)
        for index, player in enumerate(waitlist_queue.values(), start=1)
    ]

    embed = discord.Embed(
        title=f"Waitlist ({len(waitlist_queue)})",
        description="\n".join(lines),
        color=COLOR_QUEUE
    )

    await ctx.send(embed=embed)


@bot.command()
async def clearqueue(ctx):
    global queue_locked, last_blue_team, last_red_team, last_teams_message_id, last_teams_channel_id

    if not await require_admin(ctx):
        return

    player_queue.clear()
    waitlist_queue.clear()
    queue_locked = False
    last_blue_team = []
    last_red_team = []
    last_teams_message_id = None
    last_teams_channel_id = None

    await delete_queue_message()

    await send_embed(
        ctx,
        "Queue Cleared",
        "The League 5v5 queue and waitlist have been reset. The old queue post was removed.",
        COLOR_SUCCESS
    )


@bot.command()
async def addtestplayers(ctx):
    if not await require_admin(ctx):
        return

    test_players = [
        {"discord_id": 900001, "name": "TestTop", "rank": "Gold", "rating": 1250, "role_ratings": {"Top": 1250, "Jungle": 1000, "Mid": 1150, "ADC": 1000, "Support": 1000}, "primary_role": "Top", "secondary_role": "Mid", "wins": 0, "losses": 0},
        {"discord_id": 900002, "name": "TestJungle", "rank": "Silver", "rating": 1100, "role_ratings": {"Top": 850, "Jungle": 1100, "Mid": 850, "ADC": 850, "Support": 1000}, "primary_role": "Jungle", "secondary_role": "Support", "wins": 0, "losses": 0},
        {"discord_id": 900003, "name": "TestMid", "rank": "Platinum", "rating": 1400, "role_ratings": {"Top": 1150, "Jungle": 1150, "Mid": 1400, "ADC": 1300, "Support": 1150}, "primary_role": "Mid", "secondary_role": "ADC", "wins": 0, "losses": 0},
        {"discord_id": 900004, "name": "TestADC", "rank": "Bronze", "rating": 950, "role_ratings": {"Top": 700, "Jungle": 700, "Mid": 700, "ADC": 950, "Support": 850}, "primary_role": "ADC", "secondary_role": "Support", "wins": 0, "losses": 0},
        {"discord_id": 900005, "name": "TestSupport", "rank": "Emerald", "rating": 1550, "role_ratings": {"Top": 1300, "Jungle": 1450, "Mid": 1300, "ADC": 1300, "Support": 1550}, "primary_role": "Support", "secondary_role": "Jungle", "wins": 0, "losses": 0},
        {"discord_id": 900006, "name": "TestFill1", "rank": "Iron", "rating": 800, "role_ratings": {"Top": 800, "Jungle": 800, "Mid": 800, "ADC": 800, "Support": 800}, "primary_role": "Fill", "secondary_role": "Top", "wins": 0, "losses": 0},
        {"discord_id": 900007, "name": "TestFill2", "rank": "Diamond", "rating": 1700, "role_ratings": {"Top": 1700, "Jungle": 1600, "Mid": 1450, "ADC": 1450, "Support": 1450}, "primary_role": "Top", "secondary_role": "Jungle", "wins": 0, "losses": 0},
        {"discord_id": 900008, "name": "TestFill3", "rank": "Gold", "rating": 1250, "role_ratings": {"Top": 1000, "Jungle": 1000, "Mid": 1250, "ADC": 1000, "Support": 1150}, "primary_role": "Mid", "secondary_role": "Support", "wins": 0, "losses": 0},
        {"discord_id": 900009, "name": "TestFill4", "rank": "Silver", "rating": 1100, "role_ratings": {"Top": 1000, "Jungle": 850, "Mid": 850, "ADC": 1100, "Support": 850}, "primary_role": "ADC", "secondary_role": "Top", "wins": 0, "losses": 0}
    ]

    for player in test_players:
        add_to_queue_or_waitlist(player["discord_id"], player)

    await update_queue_message()
    await send_embed(ctx, "Test Players Added", "Added test players. First 10 are active; extras go to the waitlist.", COLOR_SUCCESS)


def refill_active_queue_from_waitlist():
    promoted = []

    while len(player_queue) < MAX_QUEUE_SIZE and waitlist_queue:
        next_user_id = next(iter(waitlist_queue))
        promoted_player = waitlist_queue.pop(next_user_id)
        player_queue[next_user_id] = promoted_player
        promoted.append(promoted_player)

    return promoted


def clear_completed_game_players():
    played_ids = set()

    for player in last_blue_team + last_red_team:
        played_ids.add(player["discord_id"])

    for discord_id in played_ids:
        player_queue.pop(discord_id, None)


def role_penalty(player, assigned_role):
    primary = player["primary_role"]
    secondary = player["secondary_role"]
    avoided_role = player.get("avoided_role", "None")

    if avoided_role == assigned_role:
        return 6000

    if primary == assigned_role:
        return 0

    if secondary == assigned_role:
        return 100

    if primary == "Fill" or secondary == "Fill":
        return 200

    return 2000


def best_role_assignment(team):
    best_assignment = None
    best_penalty = None

    for perm in itertools.permutations(team, 5):
        assigned = []
        total_penalty = 0

        for index, player in enumerate(perm):
            assigned_role = ROLES[index]
            penalty = role_penalty(player, assigned_role)

            assigned_player = player.copy()
            assigned_player["assigned_role"] = assigned_role
            assigned.append(assigned_player)

            total_penalty += penalty

        if best_penalty is None or total_penalty < best_penalty:
            best_penalty = total_penalty
            best_assignment = assigned

    return best_assignment, best_penalty


def find_balanced_teams(players):
    best_blue = None
    best_red = None
    best_score = None
    best_rating_diff = None
    best_lane_diff = None
    best_role_penalty = None

    for blue_group in itertools.combinations(players, 5):
        red_group = [p for p in players if p not in blue_group]

        blue_assigned, blue_penalty = best_role_assignment(list(blue_group))
        red_assigned, red_penalty = best_role_assignment(red_group)

        blue_total = sum(role_rating(p, p["assigned_role"]) for p in blue_assigned)
        red_total = sum(role_rating(p, p["assigned_role"]) for p in red_assigned)

        rating_diff = abs(blue_total - red_total)

        lane_diff = 0
        for role in ROLES:
            blue_player = next(p for p in blue_assigned if p["assigned_role"] == role)
            red_player = next(p for p in red_assigned if p["assigned_role"] == role)
            lane_diff += abs(role_rating(blue_player, role) - role_rating(red_player, role))

        total_role_penalty = blue_penalty + red_penalty

        score = rating_diff + lane_diff * 2 + total_role_penalty * 3

        if best_score is None or score < best_score:
            best_score = score
            best_blue = blue_assigned
            best_red = red_assigned
            best_rating_diff = rating_diff
            best_lane_diff = lane_diff
            best_role_penalty = total_role_penalty

    return best_blue, best_red, best_rating_diff, best_lane_diff, best_role_penalty


@bot.command()
async def setrank(ctx, member: discord.Member, *, rank: str):
    if not await require_admin(ctx):
        return

    player = get_player(member.id)

    if not player:
        await send_embed(
            ctx,
            "Player Not Found",
            f"{member.display_name} has not signed up yet. They need to use `!signup` first.",
            COLOR_ERROR
        )
        return

    normalized_rank = normalize_rank(rank)

    if not normalized_rank:
        valid_ranks = ", ".join(RANK_RATINGS.keys())
        await send_embed(
            ctx,
            "Invalid Rank",
            f"Valid ranks are: {valid_ranks}",
            COLOR_ERROR
        )
        return

    new_rating = RANK_RATINGS[normalized_rank]
    updated = update_player_rank_manual(member.id, normalized_rank, new_rating)

    if not updated:
        await send_embed(ctx, "Update Failed", "Could not update that player's rank.", COLOR_ERROR)
        return

    refresh_player_in_queues(member.id)
    await update_queue_message()

    await send_embed(
        ctx,
        "Rank Updated",
        f"{rank_emoji(normalized_rank)} **{member.display_name}** is now **{normalized_rank}** with **{new_rating}** overall rating.",
        COLOR_SUCCESS
    )


@bot.command()
async def setrating(ctx, member: discord.Member, rating: int):
    if not await require_admin(ctx):
        return

    player = get_player(member.id)

    if not player:
        await send_embed(
            ctx,
            "Player Not Found",
            f"{member.display_name} has not signed up yet. They need to use `!signup` first.",
            COLOR_ERROR
        )
        return

    if rating < 0:
        await send_embed(ctx, "Invalid Rating", "Rating must be 0 or higher.", COLOR_ERROR)
        return

    updated = update_player_rating_manual(member.id, rating)

    if not updated:
        await send_embed(ctx, "Update Failed", "Could not update that player's rating.", COLOR_ERROR)
        return

    refresh_player_in_queues(member.id)
    await update_queue_message()

    await send_embed(
        ctx,
        "Rating Updated",
        f"**{member.display_name}** now has **{rating}** overall rating.",
        COLOR_SUCCESS
    )


@bot.command()
async def setrolerating(ctx, member: discord.Member, role: str, rating: int):
    if not await require_admin(ctx):
        return

    player = get_player(member.id)

    if not player:
        await send_embed(
            ctx,
            "Player Not Found",
            f"{member.display_name} has not signed up yet. They need to use `!signup` first.",
            COLOR_ERROR
        )
        return

    normalized_role = normalize_role(role)

    if not normalized_role:
        valid_roles = ", ".join(ROLES)
        await send_embed(
            ctx,
            "Invalid Role",
            f"Valid roles are: {valid_roles}",
            COLOR_ERROR
        )
        return

    if rating < 0:
        await send_embed(ctx, "Invalid Rating", "Rating must be 0 or higher.", COLOR_ERROR)
        return

    updated = update_player_role_rating_manual(member.id, normalized_role, rating)

    if not updated:
        await send_embed(ctx, "Update Failed", "Could not update that player's role rating.", COLOR_ERROR)
        return

    new_overall = update_overall_rating_from_selected_roles(member.id)
    await sync_member_rank_role(member, new_overall)

    refresh_player_in_queues(member.id)
    await update_queue_message()

    await send_embed(
        ctx,
        "Role Rating Updated",
        (
            f"{role_emoji(normalized_role)} **{member.display_name}'s {normalized_role}** rating is now **{rating}**.\n"
            f"Overall rating is now **{new_overall}** "
            f"({rank_emoji(rank_for_rating(new_overall))} **{rank_for_rating(new_overall)}**)."
        ),
        COLOR_SUCCESS
    )


@bot.command()
async def setavoidrole(ctx, member: discord.Member, *, role: str):
    if not await require_admin(ctx):
        return

    player = get_player(member.id)

    if not player:
        await send_embed(
            ctx,
            "Player Not Found",
            f"{member.display_name} has not signed up yet. They need to use `!signup` first.",
            COLOR_ERROR
        )
        return

    if role.lower() in ["none", "clear", "remove"]:
        normalized_role = "None"
    else:
        normalized_role = normalize_role(role)

    if not normalized_role:
        valid_roles = ", ".join(ROLES + ["None"])
        await send_embed(
            ctx,
            "Invalid Role",
            f"Valid avoided roles are: {valid_roles}",
            COLOR_ERROR
        )
        return

    updated = update_player_avoided_role_manual(member.id, normalized_role)

    if not updated:
        await send_embed(ctx, "Update Failed", "Could not update that player's avoided role.", COLOR_ERROR)
        return

    refresh_player_in_queues(member.id)
    await update_queue_message()

    await send_embed(
        ctx,
        "Avoided Role Updated",
        f"**{member.display_name}** will now avoid: **{avoid_role_display(normalized_role)}**.",
        COLOR_SUCCESS
    )


@bot.command()
async def resetplayer(ctx, member: discord.Member):
    if not await require_admin(ctx):
        return

    player = get_player(member.id)

    if not player:
        await send_embed(
            ctx,
            "Player Not Found",
            f"{member.display_name} has not signed up yet.",
            COLOR_ERROR
        )
        return

    updated = reset_player_ratings_manual(member.id)

    if not updated:
        await send_embed(ctx, "Reset Failed", "Could not reset that player's ratings.", COLOR_ERROR)
        return

    new_overall = update_overall_rating_from_selected_roles(member.id)
    await sync_member_rank_role(member, new_overall)

    refresh_player_in_queues(member.id)
    await update_queue_message()

    base_rating = RANK_RATINGS[player["rank"]]

    await send_embed(
        ctx,
        "Player Reset",
        (
            f"{rank_emoji(player['rank'])} **{member.display_name}** has been reset to **{player['rank']}**.\n"
            f"Overall rating reset to **{base_rating}**.\n"
            "Role ratings, wins, and losses were reset. Signup choices were kept."
        ),
        COLOR_SUCCESS
    )


@bot.command()
async def clearhistory(ctx):
    if not await require_admin(ctx):
        return

    deleted_matches = clear_match_history_manual()

    await send_embed(
        ctx,
        "Match History Cleared",
        f"Deleted **{deleted_matches}** match history entries. Player profiles and ratings were not changed.",
        COLOR_SUCCESS
    )


@bot.command()
async def resetallratings(ctx):
    if not await require_admin(ctx):
        return

    reset_count = reset_all_players_ratings_manual()

    player_queue.clear()
    waitlist_queue.clear()
    await update_queue_message()

    await send_embed(
        ctx,
        "All Ratings Reset",
        (
            f"Reset ratings, role ratings, wins, and losses for **{reset_count}** players.\n"
            "Player signup profiles were kept."
        ),
        COLOR_SUCCESS
    )


@bot.command()
async def fullseasonreset(ctx):
    if not await require_admin(ctx):
        return

    deleted_matches = clear_match_history_manual()
    reset_count = reset_all_players_ratings_manual()

    player_queue.clear()
    waitlist_queue.clear()
    await update_queue_message()

    await send_embed(
        ctx,
        "Season Reset Complete",
        (
            f"Deleted **{deleted_matches}** matches.\n"
            f"Reset ratings, role ratings, wins, and losses for **{reset_count}** players.\n"
            "Player signup profiles were kept."
        ),
        COLOR_SUCCESS
    )


@bot.command()
async def syncrankroles(ctx):
    if not await require_admin(ctx):
        return

    synced_count = 0

    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT discord_id FROM players")
    rows = cursor.fetchall()
    conn.close()

    for (discord_id,) in rows:
        new_overall = update_overall_rating_from_selected_roles(discord_id)
        member = ctx.guild.get_member(discord_id) if ctx.guild else None

        if member and new_overall is not None:
            await sync_member_rank_role(member, new_overall)
            synced_count += 1

    await send_embed(
        ctx,
        "Rank Roles Synced",
        f"Updated rank roles for **{synced_count}** players.",
        COLOR_SUCCESS
    )




@bot.command()
async def removeplayer(ctx, member: discord.Member):
    if not await require_admin(ctx):
        return

    player = get_player(member.id)

    if not player:
        await send_embed(
            ctx,
            "Player Not Found",
            f"{member.display_name} is not currently in the database.",
            COLOR_ERROR
        )
        return

    removed = remove_player_from_database(member.id)

    if not removed:
        await send_embed(
            ctx,
            "Remove Failed",
            f"Could not remove **{member.display_name}** from the database.",
            COLOR_ERROR
        )
        return

    player_queue.pop(member.id, None)
    waitlist_queue.pop(member.id, None)
    await update_queue_message()
    await update_winrate_channel(ctx.guild)

    await send_embed(
        ctx,
        "Player Removed",
        (
            f"Removed **{member.display_name}** from the database.\n"
            "They will need to use `/signup` again if they want to play."
        ),
        COLOR_SUCCESS
    )


@bot.command()
async def removeplayerid(ctx, discord_id: int):
    if not await require_admin(ctx):
        return

    player = get_player(discord_id)

    if not player:
        await send_embed(
            ctx,
            "Player Not Found",
            f"No player found with ID `{discord_id}`.",
            COLOR_ERROR
        )
        return

    removed = remove_player_from_database(discord_id)

    if not removed:
        await send_embed(
            ctx,
            "Remove Failed",
            f"Could not remove **{player['name']}** from the database.",
            COLOR_ERROR
        )
        return

    player_queue.pop(discord_id, None)
    waitlist_queue.pop(discord_id, None)
    await update_queue_message()
    await update_winrate_channel(ctx.guild)

    await send_embed(
        ctx,
        "Player Removed",
        (
            f"Removed **{player['name']}** from the database.\n"
            "They will need to use `/signup` again if they want to play."
        ),
        COLOR_SUCCESS
    )

@bot.command()
async def lockqueue(ctx):
    global queue_locked

    if not await require_admin(ctx):
        return

    queue_locked = True
    await update_queue_message()
    await send_embed(ctx, "Queue Locked", "The active queue is now locked. New players will be placed on the waitlist.", COLOR_WARNING)


@bot.command()
async def unlockqueue(ctx):
    global queue_locked

    if not await require_admin(ctx):
        return

    queue_locked = False
    promoted = refill_active_queue_from_waitlist()
    await update_queue_message()

    if promoted:
        promoted_names = ", ".join(player["name"] for player in promoted)
        await send_embed(ctx, "Queue Unlocked", f"The queue is open again. Promoted from waitlist: {promoted_names}", COLOR_SUCCESS)
    else:
        await send_embed(ctx, "Queue Unlocked", "The queue is open again.", COLOR_SUCCESS)



class InteractionResultContext:
    """
    Small adapter so the result buttons can reuse the existing !result command logic.
    """
    def __init__(self, interaction):
        self.interaction = interaction
        self.author = interaction.user
        self.guild = interaction.guild
        self.channel = interaction.channel
        self.message = interaction.message

    async def send(self, *args, **kwargs):
        return await self.interaction.followup.send(*args, **kwargs)


class ResultView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.result_recorded = False

    def disable_all_buttons(self):
        for child in self.children:
            child.disabled = True

    async def handle_result(self, interaction: discord.Interaction, winner: str):
        if not is_admin_member(interaction.user):
            await interaction.response.send_message(
                "Only admins can report match results.",
                ephemeral=True
            )
            return

        if self.result_recorded:
            await interaction.response.send_message(
                "A result has already been recorded for this match.",
                ephemeral=True
            )
            return

        self.result_recorded = True
        self.disable_all_buttons()

        await interaction.response.edit_message(view=self)

        ctx = InteractionResultContext(interaction)
        result_command = bot.get_command("result")

        if result_command is None:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Result Error",
                    description="The result command could not be found.",
                    color=COLOR_ERROR
                )
            )
            return

        try:
            await result_command.callback(ctx, winner)
        except Exception as e:
            print(f"Result button error: {e}")

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Result Error",
                    description="Something went wrong while recording the match result. Check Railway logs.",
                    color=COLOR_ERROR
                )
            )

    @discord.ui.button(
        label="Blue Victory",
        style=discord.ButtonStyle.primary,
        emoji="🔵"
    )
    async def blue_victory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_result(interaction, "blue")

    @discord.ui.button(
        label="Red Victory",
        style=discord.ButtonStyle.danger,
        emoji="🔴"
    )
    async def red_victory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_result(interaction, "red")


@bot.command()
async def teams(ctx):
    global last_blue_team, last_red_team, queue_locked, last_teams_message_id, last_teams_channel_id

    if len(player_queue) < MAX_QUEUE_SIZE:
        await send_embed(
            ctx,
            "Not Enough Active Players",
            f"Need exactly {MAX_QUEUE_SIZE} active players. Current active queue: **{len(player_queue)}/{MAX_QUEUE_SIZE}**.",
            COLOR_WARNING
        )
        return

    players = list(player_queue.values())[:MAX_QUEUE_SIZE]
    best_blue, best_red, rating_diff, lane_diff, role_penalty_total = find_balanced_teams(players)

    last_blue_team = best_blue
    last_red_team = best_red
    queue_locked = True
    await update_queue_message()

    embed = build_teams_embed()

    msg = await ctx.send(embed=embed)
    last_teams_message_id = msg.id
    last_teams_channel_id = ctx.channel.id

    await post_generated_teams_to_match_history(ctx.guild)


@bot.command()
async def swap(ctx, player_one_arg: str, player_two_arg: str):
    if not await require_admin(ctx):
        return

    if not last_blue_team or not last_red_team:
        await send_embed(
            ctx,
            "No Active Teams",
            "Use `!teams` before swapping players.",
            COLOR_WARNING
        )
        return

    team_one_name, team_one, index_one, player_one = find_player_by_swap_arg(player_one_arg)
    team_two_name, team_two, index_two, player_two = find_player_by_swap_arg(player_two_arg)

    if player_one is None or player_two is None:
        await send_embed(
            ctx,
            "Player Not Found",
            "Both players must be on the current generated teams. You can use mentions, Discord IDs, test-player IDs, or exact player names.",
            COLOR_ERROR
        )
        return

    player_one_display = player_swap_display(ctx, player_one)
    player_two_display = player_swap_display(ctx, player_two)

    player_one_old_role = player_one["assigned_role"]
    player_two_old_role = player_two["assigned_role"]

    if team_one_name == team_two_name:
        # Same team swap: players keep their team, but trade roles.
        team_one[index_one]["assigned_role"] = player_two_old_role
        team_two[index_two]["assigned_role"] = player_one_old_role

        swap_description = (
            f"{player_one_display} and {player_two_display} swapped roles on "
            f"**{team_one_name.capitalize()} Team**.\n"
            f"{player_one_display}: {role_emoji(player_one_old_role)} **{player_one_old_role}** "
            f"→ {role_emoji(player_two_old_role)} **{player_two_old_role}**\n"
            f"{player_two_display}: {role_emoji(player_two_old_role)} **{player_two_old_role}** "
            f"→ {role_emoji(player_one_old_role)} **{player_one_old_role}**"
        )

    else:
        # Cross-team swap: players switch teams, but the role slots stay on each side.
        # This keeps each team at one Top, one Jungle, one Mid, one ADC, and one Support.
        team_one[index_one], team_two[index_two] = team_two[index_two], team_one[index_one]

        team_one[index_one]["assigned_role"] = player_one_old_role
        team_two[index_two]["assigned_role"] = player_two_old_role

        swap_description = (
            f"{player_one_display} and {player_two_display} swapped teams.\n"
            f"{player_one_display} moved to **{team_two_name.capitalize()} Team** "
            f"as {role_emoji(player_two_old_role)} **{player_two_old_role}**.\n"
            f"{player_two_display} moved to **{team_one_name.capitalize()} Team** "
            f"as {role_emoji(player_one_old_role)} **{player_one_old_role}**."
        )

    embed = build_teams_embed(
        title="Teams Updated",
        description=swap_description
    )

    updated = await update_teams_message(embed)

    if updated:
        await ctx.message.add_reaction("✅")
    else:
        await ctx.send(embed=embed)

def format_result_change_lines(player_changes, sign):
    lines = []

    for player, change in player_changes:
        role = player["assigned_role"]
        name = player["name"]
        rating = role_rating(player, role)
        change_text = f"{sign}{change}"

        lines.append(
            f"{role_emoji(role)} **{name}**\n"
            f"Role Rating: **{rating}** • Change: `{change_text}`"
        )

    return "\n\n".join(lines)


def build_short_rating_formula(lobby_average, base_rating_change):
    return (
        f"**Lobby Avg:** {lobby_average}  •  "
        f"**Base:** ±{base_rating_change}  •  "
        f"**Range:** {MIN_RATING_CHANGE}-{MAX_RATING_CHANGE}"
    )


def calculate_player_lobby_rating_change(player, lobby_average, base_change, won):
    """
    Competitive lobby-average rating system.

    Everyone starts from BASE_RATING_CHANGE, then the player's assigned-role
    rating is compared to the lobby average.

    Examples:
    - Lower-rated player wins in a high-rated lobby: gains more.
    - Lower-rated player loses in a high-rated lobby: loses less.
    - Higher-rated player wins in a low-rated lobby: gains less.
    - Higher-rated player loses in a low-rated lobby: loses more.
    """
    player_rating = role_rating(player, player["assigned_role"])
    rating_gap = lobby_average - player_rating

    if won:
        if rating_gap >= 0:
            # Underdog win bonus
            adjusted_change = BASE_RATING_CHANGE + (rating_gap / 70)
        else:
            # Favorite win reduction
            adjusted_change = BASE_RATING_CHANGE + (rating_gap / 150)
    else:
        if rating_gap >= 0:
            # Underdog loss protection
            adjusted_change = BASE_RATING_CHANGE - (rating_gap / 100)
        else:
            # Favorite loss penalty
            adjusted_change = BASE_RATING_CHANGE - (rating_gap / 120)

    adjusted_change = round(adjusted_change)
    adjusted_change = max(MIN_RATING_CHANGE, min(MAX_RATING_CHANGE, adjusted_change))

    return adjusted_change


@bot.command()
async def result(ctx, winner: str):
    global queue_locked, last_blue_team, last_red_team, last_teams_message_id, last_teams_channel_id

    if not await require_admin(ctx):
        return

    winner = winner.lower()

    if winner not in ["blue", "red"]:
        await send_embed(ctx, "Invalid Result", "Use `!result blue` or `!result red`.", COLOR_ERROR)
        return

    if not last_blue_team or not last_red_team:
        await send_embed(ctx, "No Teams Found", "Use `!teams` before recording a result.", COLOR_WARNING)
        return

    blue_rating = sum(role_rating(p, p["assigned_role"]) for p in last_blue_team)
    red_rating = sum(role_rating(p, p["assigned_role"]) for p in last_red_team)

    lobby_players = last_blue_team + last_red_team
    lobby_average = round(
        sum(role_rating(p, p["assigned_role"]) for p in lobby_players) / len(lobby_players)
    )

    base_rating_change = BASE_RATING_CHANGE

    if winner == "blue":
        winning_team = last_blue_team
        losing_team = last_red_team
    else:
        winning_team = last_red_team
        losing_team = last_blue_team

    winner_changes = []
    loser_changes = []
    promoted_players = []

    for player in winning_team:
        player_change = calculate_player_lobby_rating_change(
            player=player,
            lobby_average=lobby_average,
            base_change=base_rating_change,
            won=True
        )

        promotion = check_role_promotion(
            player,
            player["assigned_role"],
            player_change
        )

        if promotion:
            promoted_players.append(promotion)

        update_player_after_match(
            player["discord_id"],
            player["assigned_role"],
            player_change,
            won=True
        )

        new_overall = update_overall_rating_from_selected_roles(player["discord_id"])
        member = ctx.guild.get_member(player["discord_id"]) if ctx.guild else None
        await sync_member_rank_role(member, new_overall)

        winner_changes.append((player, player_change))

    for player in losing_team:
        player_change = calculate_player_lobby_rating_change(
            player=player,
            lobby_average=lobby_average,
            base_change=base_rating_change,
            won=False
        )

        update_player_after_match(
            player["discord_id"],
            player["assigned_role"],
            -player_change,
            won=False
        )

        new_overall = update_overall_rating_from_selected_roles(player["discord_id"])
        member = ctx.guild.get_member(player["discord_id"]) if ctx.guild else None
        await sync_member_rank_role(member, new_overall)

        loser_changes.append((player, player_change))

    blue_names = [f"{role_emoji(p['assigned_role'])} {p['assigned_role']}: {p['name']}" for p in last_blue_team]
    red_names = [f"{role_emoji(p['assigned_role'])} {p['assigned_role']}: {p['name']}" for p in last_red_team]

    save_match(
        winner=winner,
        blue_team=blue_names,
        red_team=red_names,
        blue_rating=blue_rating,
        red_rating=red_rating,
        rating_change=base_rating_change
    )

    color = COLOR_BLUE_TEAM if winner == "blue" else COLOR_RED_TEAM

    embed = discord.Embed(
        title=f"{winner.capitalize()} Team Wins",
        color=color
    )
    winner_change_text = format_result_change_lines(winner_changes, "+")
    loser_change_text = format_result_change_lines(loser_changes, "-")

    embed.add_field(
        name="Match Rating Info",
        value=build_short_rating_formula(lobby_average, base_rating_change),
        inline=False
    )

    embed.add_field(
        name="Winner Changes",
        value=winner_change_text,
        inline=True
    )

    embed.add_field(
        name="Loser Changes",
        value=loser_change_text,
        inline=True
    )

    embed.add_field(name="Blue Team Rating", value=str(blue_rating), inline=True)
    embed.add_field(name="Red Team Rating", value=str(red_rating), inline=True)

    if promoted_players:
        promotion_lines = []

        for promotion in promoted_players:
            promotion_lines.append(
                f"<@{promotion['discord_id']}> promoted to "
                f"{rank_emoji(promotion['new_rank'])} **{promotion['new_rank']}** "
                f"on {role_emoji(promotion['role'])} **{promotion['role']}** "
                f"({promotion['old_rating']} → {promotion['new_rating']})"
            )

        embed.add_field(
            name="Rank Promotions",
            value="\n".join(promotion_lines),
            inline=False
        )

        for promotion in promoted_players:
            await send_promotion_announcement(ctx, promotion)

    clear_completed_game_players()
    queue_locked = False
    promoted = refill_active_queue_from_waitlist()
    last_blue_team = []
    last_red_team = []
    last_teams_message_id = None
    last_teams_channel_id = None

    # Delete the old queue post after a game result, then create a fresh queue post in the same channel.
    old_queue_channel = await delete_queue_message()
    new_queue_message = await create_queue_message(old_queue_channel, replace_existing=False)

    if promoted:
        promoted_names = ", ".join(player["name"] for player in promoted)
        embed.add_field(
            name="Queue Updated",
            value=f"Active game players were cleared. Queue unlocked. Promoted from waitlist: {promoted_names}\nA fresh queue post was created automatically.",
            inline=False
        )
    else:
        embed.add_field(
            name="Queue Updated",
            value="Active game players were cleared, the queue is unlocked, and a fresh queue post was created automatically.",
            inline=False
        )

    await ctx.send(embed=embed)

    await update_winrate_channel(ctx.guild)






PLAYER_HISTORY_PER_PAGE = 5


def safe_json_loads(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def normalize_history_player(raw_player):
    """
    Supports both newer match history dictionaries and older string-only entries.
    """
    if isinstance(raw_player, dict):
        return {
            "discord_id": raw_player.get("discord_id"),
            "name": raw_player.get("name", "Unknown Player"),
            "assigned_role": raw_player.get("assigned_role", raw_player.get("role", "Unknown"))
        }

    text_value = str(raw_player).replace("**", "").strip()
    assigned_role = "Unknown"
    name = text_value

    for role in ROLES:
        if role.lower() in text_value.lower():
            assigned_role = role
            break

    for separator in [" — ", " - ", ": "]:
        if separator in text_value:
            left, right = text_value.split(separator, 1)
            name = right.strip()

            for role in ROLES:
                if role.lower() in left.lower():
                    assigned_role = role
                    break

            break

    return {
        "discord_id": None,
        "name": name,
        "assigned_role": assigned_role
    }


def normalize_history_team(team_value):
    team_value = safe_json_loads(team_value)

    if isinstance(team_value, dict):
        team_value = list(team_value.values())

    if isinstance(team_value, str):
        team_value = [
            line.strip()
            for line in team_value.splitlines()
            if line.strip()
        ]

    if not isinstance(team_value, list):
        return []

    return [normalize_history_player(player) for player in team_value]


def history_team_contains_player(team, discord_id, display_name=None):
    for player in team:
        player_id = player.get("discord_id")

        if player_id is not None:
            try:
                if int(player_id) == int(discord_id):
                    return True
            except Exception:
                pass

        # Fallback for older saved matches that only stored player names.
        if display_name and player.get("name", "").lower() == display_name.lower():
            return True

    return False


def player_team_history_lines(team):
    return "\n".join(
        f"{role_emoji(player.get('assigned_role', ''))} **{player.get('assigned_role', 'Unknown')}** — {player.get('name', 'Unknown Player')}"
        for player in team
    )


def get_player_match_history(discord_id, display_name=None, limit=5, offset=0):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, date_played, winner, blue_team, red_team
        FROM matches
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    found_matches = []

    for match_id, date_played, winner, blue_team_json, red_team_json in rows:
        blue_team = normalize_history_team(blue_team_json)
        red_team = normalize_history_team(red_team_json)
        winner_text = str(winner).lower()

        if history_team_contains_player(blue_team, discord_id, display_name):
            found_matches.append({
                "match_id": match_id,
                "date_played": date_played,
                "team_name": "blue",
                "team": blue_team,
                "winner": winner_text,
                "won": winner_text == "blue"
            })

        elif history_team_contains_player(red_team, discord_id, display_name):
            found_matches.append({
                "match_id": match_id,
                "date_played": date_played,
                "team_name": "red",
                "team": red_team,
                "winner": winner_text,
                "won": winner_text == "red"
            })

    return found_matches[offset:offset + limit]


async def send_player_match_history(ctx, member, page=1):
    if page < 1:
        page = 1

    per_page = PLAYER_HISTORY_PER_PAGE
    offset = (page - 1) * per_page

    matches = get_player_match_history(
        member.id,
        display_name=member.display_name,
        limit=per_page,
        offset=offset
    )

    if not matches:
        await send_embed(
            ctx,
            "Match History",
            f"No match history found for **{member.display_name}** on page **{page}**.",
            COLOR_WARNING
        )
        return

    embed = discord.Embed(
        title=f"{member.display_name}'s Match History — Page {page}",
        description="Shows the teammates they played with. No rating or Elo info included.",
        color=COLOR_PROFILE
    )

    for match in matches:
        team_icon = "🔵" if match["team_name"] == "blue" else "🔴"
        result_text = "WIN" if match["won"] else "LOSS"
        result_icon = "✅" if match["won"] else "❌"

        embed.add_field(
            name=f"Match #{match['match_id']} — {result_icon} {result_text} {team_icon} {match['team_name'].capitalize()} Team",
            value=(
                f"**Date:** {match['date_played']}\n"
                f"{player_team_history_lines(match['team'])}"
            ),
            inline=False
        )

    embed.set_footer(text=f"Use !myhistory {page + 1} for your next page, or !playerhistory @player {page + 1} for another player.")

    await ctx.send(embed=embed)


@bot.command()
async def myhistory(ctx, page: int = 1):
    await send_player_match_history(ctx, ctx.author, page=page)


@bot.command()
async def playerhistory(ctx, member: discord.Member, page: int = 1):
    await send_player_match_history(ctx, member, page=page)


MIN_WINRATE_GAMES = 5
WINRATE_AUTOUPDATE_PAGES = 3
WINRATE_PLAYERS_PER_PAGE = 10


def get_winrate_page(limit=10, offset=0):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, rank, rating, primary_role, secondary_role, wins, losses
        FROM players
        WHERE (wins + losses) >= %s
        ORDER BY
            (wins::float / NULLIF((wins + losses), 0)) DESC,
            (wins + losses) DESC,
            rating DESC
        LIMIT %s OFFSET %s
    """, (MIN_WINRATE_GAMES, limit, offset))

    rows = cursor.fetchall()
    conn.close()

    return rows


def format_winrate_medal(position):
    if position == 1:
        return "🥇"
    if position == 2:
        return "🥈"
    if position == 3:
        return "🥉"
    return f"`#{position}`"


def add_winrate_rows_to_embed(embed, rows, offset):
    for index, row in enumerate(rows, start=offset + 1):
        name, stored_rank, rating, primary_role, secondary_role, wins, losses = row
        games_played = wins + losses
        winrate_percent = round((wins / games_played) * 100, 1)

        current_rank = rank_for_rating(rating)
        medal = format_winrate_medal(index)

        embed.add_field(
            name=f"{medal} {rank_emoji(current_rank)} {name}",
            value=(
                f"`{winrate_percent}% WR`  •  `{wins}W - {losses}L`  •  `{games_played} GP`\n"
                f"{role_emoji(primary_role)} {primary_role} / "
                f"{role_emoji(secondary_role)} {secondary_role}  •  `{rating}` rating"
            ),
            inline=False
        )


def build_winrate_embed(page=1, compact_top_10=False, auto_page=None):
    per_page = WINRATE_PLAYERS_PER_PAGE

    if page < 1:
        page = 1

    if auto_page is not None:
        page = auto_page

    offset = (page - 1) * per_page
    rows = get_winrate_page(per_page, offset)

    if compact_top_10:
        title = f"🏆 Top Winrates — Page {page}/3"
        description = f"Auto-updated after each result. Minimum **{MIN_WINRATE_GAMES} games played** required."
    else:
        title = f"🏆 Winrate Leaderboard — Page {page}"
        description = f"Only players with at least **{MIN_WINRATE_GAMES} games played** are shown."

    embed = discord.Embed(
        title=title,
        description=description,
        color=COLOR_PROFILE
    )

    if not rows:
        embed.add_field(
            name="No eligible players yet",
            value=f"Players need at least **{MIN_WINRATE_GAMES} games played** to appear.",
            inline=False
        )
    else:
        add_winrate_rows_to_embed(embed, rows, offset)

    if compact_top_10:
        embed.set_footer(text="This #winrates message auto-updates after every !result.")
    else:
        embed.set_footer(text=f"Use !winrate {page + 1} for the next page.")

    return embed


async def winrate_page(ctx, page=1):
    embed = build_winrate_embed(page=page, compact_top_10=False)

    if embed.fields and embed.fields[0].name == "No eligible players yet":
        await send_embed(
            ctx,
            "Winrate Leaderboard",
            f"No eligible players found for page **{page}**.\n\nPlayers need at least **{MIN_WINRATE_GAMES} games played** to appear.",
            COLOR_WARNING
        )
        return

    await ctx.send(embed=embed)


async def update_winrate_channel(guild):
    """
    Keeps exactly three bot winrate messages in #winrates.
    They show players 1-10, 11-20, and 21-30, and update after every result.
    """
    global winrate_message_id

    if guild is None:
        return

    channel = discord.utils.get(guild.text_channels, name=WINRATE_CHANNEL_NAME)

    if channel is None:
        print(f"Could not find #{WINRATE_CHANNEL_NAME} channel.")
        return

    embeds = [
        build_winrate_embed(page=page, compact_top_10=True, auto_page=page)
        for page in range(1, WINRATE_AUTOUPDATE_PAGES + 1)
    ]

    try:
        existing_messages = []

        async for message in channel.history(limit=75):
            if message.author == bot.user and message.embeds:
                title = message.embeds[0].title or ""
                if "Winrate" in title or "Winrates" in title:
                    existing_messages.append(message)

        existing_messages = list(reversed(existing_messages))

        for index, embed in enumerate(embeds):
            if index < len(existing_messages):
                await existing_messages[index].edit(embed=embed)
            else:
                new_message = await channel.send(embed=embed)
                existing_messages.append(new_message)

        for extra_message in existing_messages[WINRATE_AUTOUPDATE_PAGES:]:
            try:
                await extra_message.delete()
            except Exception as e:
                print(f"Could not delete extra winrate message: {e}")

        if existing_messages:
            winrate_message_id = existing_messages[0].id

    except discord.Forbidden:
        print(f"Could not update #{WINRATE_CHANNEL_NAME}: missing permissions.")
    except Exception as e:
        print(f"Could not update winrate channel: {e}")


@bot.command()
async def winrate(ctx, page: int = 1):
    await winrate_page(ctx, page=page)


def get_leaderboard_page(limit=10, offset=0):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, rank, rating, primary_role, secondary_role, wins, losses
        FROM players
        WHERE (wins + losses) >= %s
        ORDER BY rating DESC
        LIMIT %s OFFSET %s
    """, (MIN_LEADERBOARD_GAMES, limit, offset))

    rows = cursor.fetchall()
    conn.close()

    return rows


async def leaderboard_page(ctx, page=1):
    per_page = 10

    if page < 1:
        page = 1

    offset = (page - 1) * per_page
    rows = get_leaderboard_page(per_page, offset)

    if not rows:
        await send_embed(
            ctx,
            "Leaderboard",
            f"No eligible players found for page **{page}**.\n\nPlayers need at least **{MIN_LEADERBOARD_GAMES} games played** to appear.",
            COLOR_WARNING
        )
        return

    embed = discord.Embed(
        title=f"Leaderboard — Page {page}",
        description=f"Minimum **{MIN_LEADERBOARD_GAMES} games played** required.",
        color=COLOR_SUCCESS
    )

    for index, row in enumerate(rows, start=offset + 1):
        name, stored_rank, rating, primary_role, secondary_role, wins, losses = row
        games_played = wins + losses
        current_rank = rank_for_rating(rating)

        embed.add_field(
            name=f"`#{index}` {rank_emoji(current_rank)} {name}",
            value=(
                f"**Rating:** `{rating}`  •  **Record:** `{wins}W - {losses}L`  •  **Games:** `{games_played}`\n"
                f"**Roles:** {role_emoji(primary_role)} {primary_role} / {role_emoji(secondary_role)} {secondary_role}"
            ),
            inline=False
        )

    embed.set_footer(text=f"Use !leaderboard {page + 1} for the next page.")

    await ctx.send(embed=embed)


@bot.command()
async def leaderboard(ctx, page: int = 1):
    await leaderboard_page(ctx, page=page)


@bot.command()
async def leaderboard2(ctx):
    await leaderboard_page(ctx, page=2)


@bot.command()
async def leaderboard3(ctx):
    await leaderboard_page(ctx, page=3)

@bot.command()
async def history(ctx):
    rows = get_match_history(5)

    if not rows:
        await send_embed(ctx, "Match History", "No matches have been recorded yet.", COLOR_WARNING)
        return

    embed = discord.Embed(title="Recent Match History", color=discord.Color.teal())

    for row in rows:
        match_id, date_played, winner, blue_team_json, red_team_json, blue_rating, red_rating, rating_change = row
        blue_team = json.loads(blue_team_json)
        red_team = json.loads(red_team_json)

        embed.add_field(
            name=f"Match #{match_id} — {winner.capitalize()} Win",
            value=(
                f"**Date:** {date_played}\n"
                f"**Blue Rating:** {blue_rating}\n"
                f"**Red Rating:** {red_rating}\n"
                f"**Rating Change:** ±{rating_change}\n"
                f"**Blue:** {', '.join(blue_team)}\n"
                f"**Red:** {', '.join(red_team)}"
            ),
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command()
async def ping(ctx):
    await send_embed(ctx, "Pong", "The bot is online and responding.", COLOR_SUCCESS)


bot.run(TOKEN)
