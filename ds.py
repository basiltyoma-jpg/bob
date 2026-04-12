import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import os
from datetime import datetime, UTC

TOKEN = os.environ.get("DISCORD_TOKEN")
ARTICLE_CHANNEL_ID = int(os.environ.get("ARTICLE_CHANNEL_ID", 0))
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", 0))

DATABASE = "classic_coins.db"

COINS_PER_HOUR_VOICE = 10
COINS_PER_ARTICLE = 30
COINS_PER_REFERRAL = 50
ARTICLE_COOLDOWN = 3600

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

voice_sessions = {}
invite_cache = {}

# ---------------------- БД ----------------------
async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            coins INTEGER DEFAULT 0,
            voice_seconds INTEGER DEFAULT 0,
            last_article INTEGER DEFAULT 0
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            invited_id INTEGER PRIMARY KEY,
            inviter_id INTEGER
        )
        """)
        await db.commit()

async def ensure_user(user_id):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def add_coins(user_id, amount):
    await ensure_user(user_id)
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

# ---------------------- ЛОГ ----------------------
async def log(text):
    if LOG_CHANNEL_ID:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel:
            await channel.send(text)

# ---------------------- READY ----------------------
@bot.event
async def on_ready():
    await init_db()

    synced = await tree.sync()
    print(f"✅ Slash-команд: {len(synced)}")

    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invite_cache[guild.id] = {i.code: i.uses for i in invites}
            print(f"✅ Инвайты загружены: {guild.name}")
        except Exception as e:
            print(f"❌ Ошибка инвайтов {guild.name}: {e}")
            invite_cache[guild.id] = {}

    voice_reward_loop.start()
    print("✅ Бот запущен")

# ---------------------- РЕФЕРАЛ ----------------------
@bot.event
async def on_member_join(member):
    guild = member.guild

    try:
        invites = await guild.invites()
    except Exception as e:
        print("❌ Ошибка получения инвайтов:", e)
        return

    old = invite_cache.get(guild.id, {})
    inviter = None

    for invite in invites:
        if invite.code in old and invite.uses > old[invite.code]:
            inviter = invite.inviter
            break

    invite_cache[guild.id] = {i.code: i.uses for i in invites}

    if not inviter:
        print("⚠️ Не удалось определить кто пригласил")
        return

    if inviter.id == member.id:
        return

    await ensure_user(member.id)
    await ensure_user(inviter.id)

    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
        INSERT OR IGNORE INTO referrals (invited_id, inviter_id)
        VALUES (?, ?)
        """, (member.id, inviter.id))
        await db.commit()

    await add_coins(inviter.id, COINS_PER_REFERRAL)

    print(f"🎉 {inviter} пригласил {member}")

    await log(f"🎉 {inviter} пригласил {member} (+{COINS_PER_REFERRAL})")

# ---------------------- ФОРУМ ----------------------
@bot.event
async def on_thread_create(thread):
    if thread.parent_id != ARTICLE_CHANNEL_ID:
        return

    user_id = thread.owner_id
    await ensure_user(user_id)

    now = int(datetime.now(UTC).timestamp())

    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute(
            "SELECT last_article FROM users WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

        last = row[0] if row else 0

        if now - last < ARTICLE_COOLDOWN:
            return

        await db.execute(
            "UPDATE users SET last_article = ? WHERE user_id = ?",
            (now, user_id)
        )
        await db.commit()

    await add_coins(user_id, COINS_PER_ARTICLE)
    await log(f"📝 <@{user_id}> создал тему (+{COINS_PER_ARTICLE})")

# ---------------------- ВОЙС ----------------------
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    if before.channel is None and after.channel is not None:
        voice_sessions[member.id] = datetime.now(UTC)

    elif before.channel and after.channel is None:
        voice_sessions.pop(member.id, None)

# ---------------------- АВТО НАГРАДА ВОЙС ----------------------
@tasks.loop(minutes=1)
async def voice_reward_loop():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            members = [m for m in vc.members if not m.bot]

            if len(members) < 2:
                continue

            for member in members:
                user_id = member.id
                await ensure_user(user_id)

                async with aiosqlite.connect(DATABASE) as db:
                    async with db.execute(
                        "SELECT voice_seconds FROM users WHERE user_id = ?",
                        (user_id,)
                    ) as cur:
                        row = await cur.fetchone()

                    seconds = row[0] if row else 0
                    seconds += 60

                    if seconds >= 3600:
                        seconds -= 3600
                        await add_coins(user_id, COINS_PER_HOUR_VOICE)
                        await log(f"🎙 {member} получил {COINS_PER_HOUR_VOICE} коинов")

                    await db.execute(
                        "UPDATE users SET voice_seconds = ? WHERE user_id = ?",
                        (seconds, user_id)
                    )
                    await db.commit()

# ---------------------- КОМАНДЫ ----------------------
@tree.command(name="balance")
async def balance(interaction: discord.Interaction):
    user_id = interaction.user.id
    await ensure_user(user_id)

    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute(
            "SELECT coins, voice_seconds FROM users WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

    coins = row[0]
    seconds = row[1]

    if user_id in voice_sessions:
        now = datetime.now(UTC)
        start = voice_sessions[user_id]
        seconds += int((now - start).total_seconds())

    mins = max(1, (3600 - seconds) // 60)

    await interaction.response.send_message(
        f"💰 {coins} коинов\n⏳ До награды: {mins} мин",
        ephemeral=True
    )

@tree.command(name="top")
async def top(interaction: discord.Interaction):
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute(
            "SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT 10"
        ) as cur:
            rows = await cur.fetchall()

    text = "🏆 Топ:\n"
    for i, (uid, coins) in enumerate(rows, 1):
        user = await bot.fetch_user(uid)
        text += f"{i}. {user} — {coins}\n"

    await interaction.response.send_message(text)

# ---------------------- СТАРТ ----------------------
if not TOKEN:
    raise ValueError("Нет токена")

bot.run(TOKEN)