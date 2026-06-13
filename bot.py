import os
import itertools
import json
import sqlite3
import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import (
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
ADMIN_ROLE_NAME = "Customs Admin"
MAX_QUEUE_SIZE = 10
BASE_RATING_CHANGE = 15
MIN_RATING_CHANGE = 5
MAX_RATING_CHANGE = 30

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


def role_column(role):
    return {
        "Top": "top_rating",
        "Jungle": "jungle_rating",
        "Mid": "mid_rating",
        "ADC": "adc_rating",
        "Support": "support_rating"
    }[role]


def update_player_rank_manual(discord_id, rank, rating):
    conn = sqlite3.connect("league_bot.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET rank = ?, rating = ?
        WHERE discord_id = ?
    """, (rank, rating, discord_id))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed > 0


def update_player_rating_manual(discord_id, rating):
    conn = sqlite3.connect("league_bot.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET rating = ?
        WHERE discord_id = ?
    """, (rating, discord_id))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed > 0


def update_player_role_rating_manual(discord_id, role, rating):
    column = role_column(role)

    conn = sqlite3.connect("league_bot.db")
    cursor = conn.cursor()

    cursor.execute(f"""
        UPDATE players
        SET {column} = ?
        WHERE discord_id = ?
    """, (rating, discord_id))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_changed > 0


def update_player_avoided_role_manual(discord_id, avoided_role):
    conn = sqlite3.connect("league_bot.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET avoided_role = ?
        WHERE discord_id = ?
    """, (avoided_role, discord_id))

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

    conn = sqlite3.connect("league_bot.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET rating = ?,
            top_rating = ?,
            jungle_rating = ?,
            mid_rating = ?,
            adc_rating = ?,
            support_rating = ?,
            wins = 0,
            losses = 0
        WHERE discord_id = ?
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
    conn = sqlite3.connect("league_bot.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM matches")
    deleted_matches = cursor.rowcount

    # Reset autoincrement counter for match IDs if the table uses sqlite_sequence.
    cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'matches'")

    conn.commit()
    conn.close()

    return deleted_matches


def reset_all_players_ratings_manual():
    conn = sqlite3.connect("league_bot.db")
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
            SET rating = ?,
                top_rating = ?,
                jungle_rating = ?,
                mid_rating = ?,
                adc_rating = ?,
                support_rating = ?,
                wins = 0,
                losses = 0
            WHERE discord_id = ?
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


def is_admin(ctx):
    if ctx.author.guild_permissions.administrator:
        return True

    return any(role.name == ADMIN_ROLE_NAME for role in ctx.author.roles)


async def require_admin(ctx):
    if is_admin(ctx):
        return True

    embed = discord.Embed(
        title="Admin Only",
        description=f"You need Administrator permissions or the `{ADMIN_ROLE_NAME}` role to use this command.",
        color=COLOR_ERROR
    )
    await ctx.send(embed=embed)
    return False


def role_rating(player, role):
    return player["role_ratings"].get(role, player["rating"])


def clean_player_line(player):
    avoided_role = player.get("avoided_role", "None")

    avoid_text = ""
    if avoided_role != "None":
        avoid_text = f" • Avoid: {role_emoji(avoided_role)}"

    return (
        f"{rank_emoji(player['rank'])} **{player['name']}**\n"
        f"{role_emoji(player['primary_role'])} {role_emoji(player['secondary_role'])} "
        f"**{player['rating']}** rating{avoid_text}"
    )


def clean_waitlist_line(index, player):
    avoided_role = player.get("avoided_role", "None")

    avoid_text = ""
    if avoided_role != "None":
        avoid_text = f" • Avoid: {role_emoji(avoided_role)}"

    return (
        f"**#{index}** {rank_emoji(player['rank'])} **{player['name']}** — "
        f"{role_emoji(player['primary_role'])} {role_emoji(player['secondary_role'])} "
        f"**{player['rating']}**{avoid_text}"
    )


def clean_assigned_line(player):
    assigned_role = player["assigned_role"]
    assigned_rating = role_rating(player, assigned_role)
    avoided_role = player.get("avoided_role", "None")

    avoid_warning = ""
    if avoided_role == assigned_role:
        avoid_warning = " ⚠️ avoided"

    return (
        f"{role_emoji(assigned_role)} **{player['name']}**{avoid_warning}\n"
        f"{rank_emoji(player['rank'])} **{assigned_rating}** role rating"
    )


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


def build_queue_embed():
    lock_status = "🔒 Locked" if queue_locked else "🔓 Open"

    embed = discord.Embed(
        title=f"League 5v5 Queue ({len(player_queue)}/{MAX_QUEUE_SIZE}) — {lock_status}",
        description=(
            "React with ✅ to join the queue.\n"
            "The first 10 players enter the active queue.\n"
            "Everyone after that is automatically placed on the waitlist.\n"
            "When the queue is locked, new players go straight to the waitlist."
        ),
        color=COLOR_QUEUE
    )

    if not player_queue:
        embed.add_field(name="Active Queue", value="No players queued yet.", inline=False)
    else:
        lines = [clean_player_line(player) for player in player_queue.values()]
        embed.add_field(name="Active Queue", value="\n\n".join(lines), inline=False)

        ratings = [player["rating"] for player in player_queue.values()]
        avg_rating = round(sum(ratings) / len(ratings))
        highest = max(ratings)
        lowest = min(ratings)

        embed.add_field(
            name="Queue Stats",
            value=(
                f"**Players:** {len(player_queue)}/{MAX_QUEUE_SIZE}\n"
                f"**Average Rating:** {avg_rating}\n"
                f"**Highest Rating:** {highest}\n"
                f"**Lowest Rating:** {lowest}"
            ),
            inline=False
        )

    if waitlist_queue:
        waitlist_lines = [
            clean_waitlist_line(index, player)
            for index, player in enumerate(waitlist_queue.values(), start=1)
        ]
        embed.add_field(
            name=f"Waitlist ({len(waitlist_queue)})",
            value="\n".join(waitlist_lines),
            inline=False
        )
    else:
        embed.add_field(name="Waitlist", value="No players waiting.", inline=False)

    embed.set_footer(text="!teams locks the active queue. !result saves the match, clears active players, unlocks queue, and promotes waitlisted players.")
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

        await interaction.response.send_message(
            "Signup complete and saved.",
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
    embed.add_field(name="Rank", value=f"{rank_emoji(player['rank'])} {player['rank']}", inline=True)
    embed.add_field(name="Overall Rating", value=str(player["rating"]), inline=True)
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
    global queue_message_id, queue_channel_id

    msg = await ctx.send(embed=build_queue_embed())
    queue_message_id = msg.id
    queue_channel_id = ctx.channel.id

    await msg.add_reaction(JOIN_EMOJI)


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
    global queue_locked, last_blue_team, last_red_team

    if not await require_admin(ctx):
        return

    player_queue.clear()
    waitlist_queue.clear()
    queue_locked = False
    last_blue_team = []
    last_red_team = []
    await update_queue_message()
    await send_embed(ctx, "Queue Cleared", "The League 5v5 queue and waitlist have been reset.", COLOR_SUCCESS)


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

    refresh_player_in_queues(member.id)
    await update_queue_message()

    await send_embed(
        ctx,
        "Role Rating Updated",
        f"{role_emoji(normalized_role)} **{member.display_name}'s {normalized_role}** rating is now **{rating}**.",
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


@bot.command()
async def teams(ctx):
    global last_blue_team, last_red_team, queue_locked

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

    blue_total = sum(role_rating(p, p["assigned_role"]) for p in best_blue)
    red_total = sum(role_rating(p, p["assigned_role"]) for p in best_red)

    embed = discord.Embed(
        title="Balanced Teams Generated",
        description="Teams were balanced by role fit, lane matchup rating, and total team rating. The active queue is now locked.",
        color=COLOR_SUCCESS
    )

    embed.add_field(name=f"Blue Team — {blue_total} Rating", value="\n\n".join(clean_assigned_line(p) for p in best_blue), inline=True)
    embed.add_field(name=f"Red Team — {red_total} Rating", value="\n\n".join(clean_assigned_line(p) for p in best_red), inline=True)
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

    embed.set_footer(text="Use !result blue or !result red after the game.")
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
    global queue_locked, last_blue_team, last_red_team

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

    for player in winning_team:
        player_change = calculate_player_lobby_rating_change(
            player=player,
            lobby_average=lobby_average,
            base_change=base_rating_change,
            won=True
        )

        update_player_after_match(
            player["discord_id"],
            player["assigned_role"],
            player_change,
            won=True
        )

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

    clear_completed_game_players()
    queue_locked = False
    promoted = refill_active_queue_from_waitlist()
    last_blue_team = []
    last_red_team = []
    await update_queue_message()

    if promoted:
        promoted_names = ", ".join(player["name"] for player in promoted)
        embed.add_field(
            name="Queue Updated",
            value=f"Active game players were cleared. Queue unlocked. Promoted from waitlist: {promoted_names}",
            inline=False
        )
    else:
        embed.add_field(
            name="Queue Updated",
            value="Active game players were cleared and the queue is unlocked.",
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command()
async def leaderboard(ctx):
    rows = get_leaderboard(10)

    if not rows:
        await send_embed(ctx, "Leaderboard", "No players found.", COLOR_WARNING)
        return

    lines = []

    for index, row in enumerate(rows, start=1):
        name, rank, rating, primary, secondary, wins, losses = row
        lines.append(
            f"**#{index}** {rank_emoji(rank)} **{name}** — **{rating}** rating\n"
            f"{role_emoji(primary)} {role_emoji(secondary)} `{primary}/{secondary}` • {wins}W/{losses}L"
        )

    embed = discord.Embed(
        title="League Customs Leaderboard",
        description="\n\n".join(lines),
        color=discord.Color.gold()
    )

    await ctx.send(embed=embed)


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
