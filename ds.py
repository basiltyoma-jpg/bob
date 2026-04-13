import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
from dotenv import load_dotenv
from datetime import datetime, UTC

# ---------------------- НАСТРОЙКИ ----------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Укажите ID вашего сервера и канала со статьями
GUILD_ID = 1492164546926739577  # Замените на ID вашего сервера
ARTICLE_CHANNEL_ID = int(os.getenv("ARTICLE_CHANNEL_ID", "0"))

DATABASE = "classic_coins.db"

COINS_PER_HOUR_VOICE = 10
COINS_PER_ARTICLE = 30
COINS_PER_REFERRAL = 50
COINS_FOR_MEETING = 300
MIN_ARTICLE_LENGTH = 200

# ---------------------- INTENTS ----------------------
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
guild = discord.Object(id=GUILD_ID)

voice_sessions = {}
invite_cache = {}

# ---------------------- БАЗА ДАННЫХ ----------------------
async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                coins INTEGER DEFAULT 0
            )
        """)

        # Добавление столбца voice_seconds, если его нет
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = [row[1] async for row in cursor]
        if "voice_seconds" not in columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN voice_seconds INTEGER DEFAULT 0"
            )

        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                invited_id INTEGER PRIMARY KEY,
                inviter_id INTEGER,
                joined_at TEXT
            )
        """)
        await db.commit()

# ---------------------- РАБОТА С КОИНАМИ ----------------------
async def ensure_user(user_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, coins, voice_seconds) VALUES (?, 0, 0)",
            (user_id,)
        )
        await db.commit()

async def add_coins(user_id: int, amount: int):
    await ensure_user(user_id)
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(
            "UPDATE users SET coins = coins + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()

async def remove_coins(user_id: int, amount: int) -> bool:
    await ensure_user(user_id)
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute(
            "SELECT coins FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            coins = (await cursor.fetchone())[0]

        if coins < amount:
            return False

        await db.execute(
            "UPDATE users SET coins = coins - ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()
        return True

async def get_user_data(user_id: int):
    await ensure_user(user_id)
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute(
            "SELECT coins, voice_seconds FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            return await cursor.fetchone()

async def add_voice_time(user_id: int, seconds: int):
    await ensure_user(user_id)
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute(
            "SELECT voice_seconds FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            current_seconds = (await cursor.fetchone())[0]

        total_seconds = current_seconds + seconds
        hours = total_seconds // 3600
        remaining_seconds = total_seconds % 3600
        coins_to_add = hours * COINS_PER_HOUR_VOICE

        await db.execute(
            "UPDATE users SET coins = coins + ?, voice_seconds = ? WHERE user_id = ?",
            (coins_to_add, remaining_seconds, user_id)
        )
        await db.commit()

# ---------------------- СОБЫТИЯ ----------------------
@bot.event
async def on_ready():
    await init_db()
    print(f"✅ Бот {bot.user} запущен!")

    # Мгновенная синхронизация команд для сервера
    await tree.sync(guild=guild)
    print("✅ Slash-команды синхронизированы для сервера.")

    # Кэш приглашений
    for g in bot.guilds:
        try:
            invites = await g.invites()
            invite_cache[g.id] = {invite.code: invite.uses for invite in invites}
        except discord.Forbidden:
            invite_cache[g.id] = {}

# ---------------------- РЕФЕРАЛЬНАЯ СИСТЕМА ----------------------
@tree.command(name="referral", description="Получить реферальную ссылку", guild=guild)
async def referral(interaction: discord.Interaction):
    invite = await interaction.channel.create_invite(
        max_age=0,
        max_uses=0,
        unique=True,
        reason=f"Referral for {interaction.user}"
    )

    await interaction.response.send_message(
        f"🔗 Ваша реферальная ссылка: {invite.url}\n"
        f"Вы получите {COINS_PER_REFERRAL} коинов за каждого приглашённого!",
        ephemeral=True
    )

@bot.event
async def on_member_join(member):
    guild_obj = member.guild
    try:
        new_invites = await guild_obj.invites()
    except discord.Forbidden:
        return

    old_invites = invite_cache.get(guild_obj.id, {})
    inviter = None

    for invite in new_invites:
        if invite.uses > old_invites.get(invite.code, 0):
            inviter = invite.inviter
            break

    invite_cache[guild_obj.id] = {
        invite.code: invite.uses for invite in new_invites
    }

    if inviter and inviter.id != member.id:
        await add_coins(inviter.id, COINS_PER_REFERRAL)
        try:
            await inviter.send(
                f"🎉 Вы пригласили {member.mention} и получили {COINS_PER_REFERRAL} коинов!"
            )
        except discord.Forbidden:
            pass

# ---------------------- НАГРАДА ЗА СТАТЬИ ----------------------
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    if message.channel.id == ARTICLE_CHANNEL_ID:
        if len(message.content) >= MIN_ARTICLE_LENGTH:
            await add_coins(message.author.id, COINS_PER_ARTICLE)
            await message.add_reaction("🪙")
        else:
            await message.reply(
                f"Статья должна содержать не менее {MIN_ARTICLE_LENGTH} символов."
            )

    await bot.process_commands(message)

# ---------------------- ГОЛОСОВАЯ АКТИВНОСТЬ ----------------------
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

# ---------------------- КОМАНДЫ ----------------------
@tree.command(name="balance", description="Показать баланс", guild=guild)
async def balance(interaction: discord.Interaction):
    coins, seconds = await get_user_data(interaction.user.id)
    minutes_left = (3600 - seconds) // 60 if seconds else 0
    await interaction.response.send_message(
        f"💰 Баланс: **{coins}** коинов\n"
        f"🕒 До следующего начисления: **{minutes_left} мин.**",
        ephemeral=True
    )

@tree.command(name="top", description="Топ участников", guild=guild)
async def top(interaction: discord.Interaction):
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute(
            "SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT 10"
        ) as cursor:
            rows = await cursor.fetchall()

    text = "🏆 **Топ участников:**\n"
    for i, (uid, coins) in enumerate(rows, start=1):
        user = await bot.fetch_user(uid)
        text += f"{i}. {user.name} — {coins} коинов\n"

    await interaction.response.send_message(text)

# ---------------------- ПОКУПКА МИТИНГА ----------------------
@tree.command(name="buy_meeting", description="Купить организацию митинга", guild=guild)
@app_commands.describe(
    title="Название митинга",
    requirements="Требования или описание митинга",
    participants="Упоминания участников (например: @user1 @user2)"
)
async def buy_meeting(
    interaction: discord.Interaction,
    title: str,
    requirements: str,
    participants: str
):
    if not await remove_coins(interaction.user.id, COINS_FOR_MEETING):
        await interaction.response.send_message(
            f"❌ Недостаточно коинов. Требуется {COINS_FOR_MEETING}.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"📢 Митинг: {title}",
        description=requirements,
        color=discord.Color.red(),
        timestamp=datetime.now(UTC)
    )
    embed.add_field(name="Организатор", value=interaction.user.mention, inline=False)
    embed.add_field(name="Участники", value=participants, inline=False)
    embed.set_footer(text="Оплачено Классик Коинами")

    await interaction.response.send_message(
        "✅ Митинг успешно создан!", ephemeral=True
    )
    await interaction.channel.send(content=participants, embed=embed)

# ---------------------- ЗАПУСК БОТА ----------------------
if not TOKEN:
    raise ValueError("Токен бота не найден.")

bot.run(TOKEN)