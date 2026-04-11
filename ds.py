import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
from dotenv import load_dotenv
from datetime import datetime, UTC

# ---------------------- ЗАГРУЗКА НАСТРОЕК ----------------------
load_dotenv()

TOKEN = os.environ.get("DISCORD_TOKEN")
ARTICLE_CHANNEL_ID = int(os.getenv("ARTICLE_CHANNEL_ID", "0"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

DATABASE = "classic_coins.db"

COINS_PER_HOUR_VOICE = 10
COINS_PER_ARTICLE = 30
COINS_PER_REFERRAL = 50
ARTICLE_COOLDOWN = 3600  # 1 час

# ---------------------- INTENTS ----------------------
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

voice_sessions = {}
invite_cache = {}

# ---------------------- БАЗА ДАННЫХ ----------------------
async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                coins INTEGER DEFAULT 0,
                voice_seconds INTEGER DEFAULT 0,
                last_article_time INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                invited_id INTEGER PRIMARY KEY,
                inviter_id INTEGER,
                joined_at TEXT
            )
        """)

        await db.commit()

async def log_to_channel(guild, text):
    if not LOG_CHANNEL_ID:
        return

    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        try:
            await channel.send(text)
        except:
            pass

# ---------------------- КОИНЫ ----------------------
async def add_coins(user_id: int, amount: int):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            INSERT INTO users (user_id, coins)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET coins = coins + ?
        """, (user_id, amount, amount))
        await db.commit()

async def add_voice_time(user_id: int, seconds: int):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, coins, voice_seconds)
            VALUES (?, 0, 0)
        """, (user_id,))

        async with db.execute(
            "SELECT voice_seconds FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        current = row[0] if row else 0
        total = current + seconds

        hours = total // 3600
        remaining = total % 3600
        coins = hours * COINS_PER_HOUR_VOICE

        await db.execute("""
            UPDATE users
            SET coins = coins + ?, voice_seconds = ?
            WHERE user_id = ?
        """, (coins, remaining, user_id))

        await db.commit()

async def get_user_data(user_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id)
            VALUES (?)
        """, (user_id,))
        await db.commit()

        async with db.execute(
            "SELECT coins, voice_seconds FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row if row else (0, 0)
async def add_coins(user_id: int, amount: int, guild=None):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            INSERT INTO users (user_id, coins)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET coins = coins + ?
        """, (user_id, amount, amount))
        await db.commit()

    if guild:
        user = await bot.fetch_user(user_id)
        await log_to_channel(guild, f"💰 {user} получил {amount} коинов")

# ---------------------- READY ----------------------
@bot.event
async def on_ready():
    await init_db()
    print(f"✅ Бот {bot.user} запущен!")

    try:
        synced = await tree.sync()
        print(f"✅ Slash-команд: {len(synced)}")
    except Exception as e:
        print("Ошибка sync:", e)

    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invite_cache[guild.id] = {i.code: i.uses for i in invites}
        except:
            invite_cache[guild.id] = {}

# ---------------------- РЕФЕРАЛЫ ----------------------
@bot.event
async def on_member_join(member):
    guild = member.guild

    try:
        new_invites = await guild.invites()
    except:
        return

    old = invite_cache.get(guild.id, {})
    inviter = None

    for invite in new_invites:
        if invite.uses > old.get(invite.code, 0):
            inviter = invite.inviter
            break

    invite_cache[guild.id] = {i.code: i.uses for i in new_invites}

    if inviter and inviter.id != member.id:
        await add_coins(inviter.id, COINS_PER_REFERRAL)

        async with aiosqlite.connect(DATABASE) as db:
            await db.execute("""
                INSERT OR IGNORE INTO referrals (invited_id, inviter_id, joined_at)
                VALUES (?, ?, ?)
            """, (member.id, inviter.id, datetime.now(UTC).isoformat()))
            await db.commit()
    await log_to_channel(
        member.guild,
        f"🎉 {inviter} пригласил {member} (+{COINS_PER_REFERRAL})"
    )

# ---------------------- СТАТЬИ + КУЛДАУН ----------------------
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # Проверяем что это тред форума
    if isinstance(message.channel, discord.Thread):
        if message.channel.parent_id != ARTICLE_CHANNEL_ID:
            return

        # Проверяем что это первое сообщение в треде
        if message.channel.message_count is None or message.channel.message_count > 1:
            return

        user_id = message.author.id
        now = int(datetime.now(UTC).timestamp())

        async with aiosqlite.connect(DATABASE) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id)
                VALUES (?)
            """, (user_id,))
            await db.commit()

            async with db.execute(
                "SELECT last_article_time FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()

            last_time = row[0] if row else 0

            # ⏳ кулдаун
            if now - last_time < ARTICLE_COOLDOWN:
                remain = ARTICLE_COOLDOWN - (now - last_time)
                minutes = remain // 60

                await message.channel.send(
                    f"⏳ Подожди **{minutes} мин.** перед новой статьёй."
                )
                return

            # 💰 выдача
            await db.execute("""
                UPDATE users
                SET coins = coins + ?, last_article_time = ?
                WHERE user_id = ?
            """, (COINS_PER_ARTICLE, now, user_id))
            await db.commit()

        await message.channel.send(
            f"📝 <@{user_id}> получил **{COINS_PER_ARTICLE}** коинов за публикацию!"
        )

    await log_to_channel(
        message.guild,
        f"📝 {message.author} получил {COINS_PER_ARTICLE} коинов за статью"
    )

# ---------------------- ГОЛОС ----------------------
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    now = datetime.now(UTC)

    if before.channel is None and after.channel is not None:
        voice_sessions[member.id] = now

    elif before.channel is not None and after.channel is None:
        start = voice_sessions.pop(member.id, None)
        if start:
            seconds = int((now - start).total_seconds())
            await add_voice_time(member.id, seconds)
    await log_to_channel(
        message.guild,
        f"📝 {message.author} получил {COINS_PER_ARTICLE} коинов за статью"
    )
# ---------------------- КОМАНДЫ ----------------------
@tree.command(name="balance", description="Баланс")
async def balance(interaction: discord.Interaction):
    coins, seconds = await get_user_data(interaction.user.id)

    if seconds == 0:
        minutes_left = 59
    else:
        minutes_left = max(0, (3600 - seconds) // 60)

    await interaction.response.send_message(
        f"💰 {coins} коинов\n⏳ До награды: {minutes_left} мин.",
        ephemeral=True
    )

@tree.command(name="top", description="Топ")
async def top(interaction: discord.Interaction):
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute(
            "SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT 10"
        ) as cursor:
            rows = await cursor.fetchall()

    text = "🏆 Топ:\n"
    for i, (uid, coins) in enumerate(rows, 1):
        user = await bot.fetch_user(uid)
        text += f"{i}. {user.name} — {coins}\n"

    await interaction.response.send_message(text)

@tree.command(name="referral", description="Рефералка")
async def referral(interaction: discord.Interaction):
    invite = await interaction.channel.create_invite(max_age=0, max_uses=0)

    await interaction.response.send_message(
        f"🔗 {invite.url}\n+{COINS_PER_REFERRAL} коинов за друга",
        ephemeral=True
    )

# ---------------------- ЗАПУСК ----------------------
print("TOKEN:", TOKEN)

if not TOKEN:
    raise ValueError("Нет токена в ENV")

bot.run(TOKEN)