import os
import asyncio
import threading
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import discord
from discord import app_commands
from discord.ext import commands, tasks

from database import init_db


# =========================================================
# DATABASE
# =========================================================

init_db()

DB_FILE = "ctrp_system.db"


def db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


# =========================================================
# TOKEN
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN غير موجود في Environment Variables"
    )


# =========================================================
# RENDER PORT
# =========================================================

PORT = int(os.getenv("PORT", "10000"))


class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )
        self.end_headers()

        self.wfile.write(
            b"CTRP Bot is Online!"
        )

    def log_message(self, format, *args):
        pass


def start_web_server():

    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler
    )

    print("━━━━━━━━━━━━━━━━━━━━")
    print(f"🌐 Render Port: {PORT}")
    print("🟢 Web Server Online")
    print("━━━━━━━━━━━━━━━━━━━━")

    server.serve_forever()


# =========================================================
# DISCORD
# =========================================================

intents = discord.Intents.default()

intents.members = True
intents.message_content = True
intents.voice_states = True
intents.presences = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# DATABASE SETTINGS
# =========================================================

def ensure_guild_settings(guild_id: int):

    con = db()

    con.execute(
        """
        INSERT OR IGNORE INTO settings
        (
            guild_id,
            log_channel,
            broadcast_channel,
            suggestion_channel,
            auto_member_role,
            auto_bot_role
        )
        VALUES (?, NULL, NULL, NULL, NULL, NULL)
        """,
        (guild_id,)
    )

    con.commit()
    con.close()


def get_settings(guild_id: int):

    ensure_guild_settings(guild_id)

    con = db()

    row = con.execute(
        """
        SELECT *
        FROM settings
        WHERE guild_id = ?
        """,
        (guild_id,)
    ).fetchone()

    con.close()

    return row


def set_setting(
    guild_id: int,
    column: str,
    value
):

    allowed = {
        "log_channel",
        "broadcast_channel",
        "suggestion_channel",
        "auto_member_role",
        "auto_bot_role"
    }

    if column not in allowed:
        return

    ensure_guild_settings(guild_id)

    con = db()

    con.execute(
        f"""
        UPDATE settings
        SET {column} = ?
        WHERE guild_id = ?
        """,
        (value, guild_id)
    )

    con.commit()
    con.close()


# =========================================================
# LOG SYSTEM
# =========================================================

async def get_log_channel(guild: discord.Guild):

    row = get_settings(guild.id)

    channel_id = row["log_channel"]

    if not channel_id:
        return None

    channel = guild.get_channel(channel_id)

    if channel:
        return channel

    try:
        channel = await bot.fetch_channel(channel_id)
        return channel
    except Exception:
        return None


async def send_log(
    guild: discord.Guild,
    title: str,
    description: str,
    emoji: str = "📋",
    color: discord.Color = discord.Color.blurple()
):

    channel = await get_log_channel(guild)

    if not channel:
        return

    embed = discord.Embed(
        title=f"{emoji} {title}",
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_footer(
        text=f"CTRP • {guild.name}"
    )

    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(
            f"❌ Log Send Error [{guild.name}]: {e}"
        )


# =========================================================
# AUDIT LOG HELPER
# =========================================================

async def get_recent_audit_entry(
    guild: discord.Guild,
    action: discord.AuditLogAction,
    target_id: int,
    limit: int = 10
):

    try:

        async for entry in guild.audit_logs(
            limit=limit,
            action=action
        ):

            if entry.target and entry.target.id == target_id:
                return entry

    except Exception:
        return None

    return None


# =========================================================
# AUTO ROLES
# =========================================================

async def give_auto_role(
    member: discord.Member,
    role_id: int,
    role_type: str
):

    if not role_id:
        return

    role = member.guild.get_role(role_id)

    if not role:
        return

    if role in member.roles:
        return

    me = member.guild.me

    if not me:
        return

    if not me.guild_permissions.manage_roles:
        print(
            f"⚠️ البوت لا يملك Manage Roles في {member.guild.name}"
        )
        return

    if role >= me.top_role:
        print(
            f"⚠️ الرتبة {role.name} أعلى من رتبة البوت"
        )
        return

    try:

        await member.add_roles(
            role,
            reason=f"CTRP Auto Role - {role_type}"
        )

        print(
            f"✅ Auto Role: {member} -> {role.name}"
        )

    except Exception as e:

        print(
            f"❌ Auto Role Error: {e}"
        )


# =========================================================
# MEMBER JOIN
# =========================================================

@bot.event
async def on_member_join(member: discord.Member):

    row = get_settings(member.guild.id)

    if member.bot:

        role_id = row["auto_bot_role"]

        if role_id:
            await give_auto_role(
                member,
                role_id,
                "Bot"
            )

    else:

        role_id = row["auto_member_role"]

        if role_id:
            await give_auto_role(
                member,
                role_id,
                "Member"
            )

    await send_log(
        member.guild,
        "دخول عضو",
        (
            f"**العضو:** {member.mention}\n"
            f"**الاسم:** `{member}`\n"
            f"**ID:** `{member.id}`"
        ),
        "📥",
        discord.Color.green()
    )


# =========================================================
# MEMBER LEAVE / KICK
# =========================================================

@bot.event
async def on_member_remove(member: discord.Member):

    await asyncio.sleep(1)

    kick_entry = await get_recent_audit_entry(
        member.guild,
        discord.AuditLogAction.kick,
        member.id
    )

    if kick_entry:

        executor = kick_entry.user

        await send_log(
            member.guild,
            "طرد عضو",
            (
                f"**العضو:** `{member}`\n"
                f"**ID:** `{member.id}`\n"
                f"**بواسطة:** "
                f"{executor.mention if executor else 'غير معروف'}"
            ),
            "👢",
            discord.Color.orange()
        )

        return

    await send_log(
        member.guild,
        "خروج عضو",
        (
            f"**العضو:** `{member}`\n"
            f"**ID:** `{member.id}`"
        ),
        "📤",
        discord.Color.dark_gray()
    )


# =========================================================
# BAN
# =========================================================

@bot.event
async def on_member_ban(
    guild: discord.Guild,
    user: discord.User
):

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        guild,
        discord.AuditLogAction.ban,
        user.id
    )

    executor = (
        entry.user
        if entry
        else None
    )

    reason = (
        entry.reason
        if entry and entry.reason
        else "بدون سبب"
    )

    await send_log(
        guild,
        "حظر عضو",
        (
            f"**العضو:** {user.mention}\n"
            f"**ID:** `{user.id}`\n"
            f"**بواسطة:** "
            f"{executor.mention if executor else 'غير معروف'}\n"
            f"**السبب:** `{reason}`"
        ),
        "🔨",
        discord.Color.red()
    )


# =========================================================
# MESSAGE DELETE
# =========================================================

@bot.event
async def on_message_delete(
    message: discord.Message
):

    if not message.guild:
        return

    if message.author.bot:
        return

    content = message.content or "لا يوجد محتوى نصي"

    if len(content) > 1000:
        content = content[:1000] + "..."

    await send_log(
        message.guild,
        "حذف رسالة",
        (
            f"**العضو:** {message.author.mention}\n"
            f"**الروم:** {message.channel.mention}\n"
            f"**الرسالة:**\n"
            f"```{content}```"
        ),
        "🗑️",
        discord.Color.red()
    )


# =========================================================
# MESSAGE EDIT
# =========================================================

@bot.event
async def on_message_edit(
    before: discord.Message,
    after: discord.Message
):

    if not before.guild:
        return

    if before.author.bot:
        return

    if before.content == after.content:
        return

    old_content = before.content or "فارغ"
    new_content = after.content or "فارغ"

    if len(old_content) > 700:
        old_content = old_content[:700] + "..."

    if len(new_content) > 700:
        new_content = new_content[:700] + "..."

    await send_log(
        before.guild,
        "تعديل رسالة",
        (
            f"**العضو:** {before.author.mention}\n"
            f"**الروم:** {before.channel.mention}\n\n"
            f"**قبل:**\n"
            f"```{old_content}```\n"
            f"**بعد:**\n"
            f"```{new_content}```"
        ),
        "✏️",
        discord.Color.orange()
    )


# =========================================================
# CHANNEL CREATE
# =========================================================

@bot.event
async def on_guild_channel_create(
    channel: discord.abc.GuildChannel
):

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        channel.guild,
        discord.AuditLogAction.channel_create,
        channel.id
    )

    executor = entry.user if entry else None

    await send_log(
        channel.guild,
        "إنشاء روم",
        (
            f"**الروم:** {channel.mention}\n"
            f"**الاسم:** `{channel.name}`\n"
            f"**بواسطة:** "
            f"{executor.mention if executor else 'غير معروف'}"
        ),
        "📁",
        discord.Color.green()
    )


# =========================================================
# CHANNEL DELETE
# =========================================================

@bot.event
async def on_guild_channel_delete(
    channel: discord.abc.GuildChannel
):

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        channel.guild,
        discord.AuditLogAction.channel_delete,
        channel.id
    )

    executor = entry.user if entry else None

    await send_log(
        channel.guild,
        "حذف روم",
        (
            f"**الروم:** `#{channel.name}`\n"
            f"**ID:** `{channel.id}`\n"
            f"**بواسطة:** "
            f"{executor.mention if executor else 'غير معروف'}"
        ),
        "🗑️",
        discord.Color.red()
    )


# =========================================================
# ROLE CREATE
# =========================================================

@bot.event
async def on_guild_role_create(
    role: discord.Role
):

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        role.guild,
        discord.AuditLogAction.role_create,
        role.id
    )

    executor = entry.user if entry else None

    await send_log(
        role.guild,
        "إنشاء رتبة",
        (
            f"**الرتبة:** {role.mention}\n"
            f"**الاسم:** `{role.name}`\n"
            f"**بواسطة:** "
            f"{executor.mention if executor else 'غير معروف'}"
        ),
        "🏷️",
        discord.Color.green()
    )


# =========================================================
# ROLE DELETE
# =========================================================

@bot.event
async def on_guild_role_delete(
    role: discord.Role
):

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        role.guild,
        discord.AuditLogAction.role_delete,
        role.id
    )

    executor = entry.user if entry else None

    await send_log(
        role.guild,
        "حذف رتبة",
        (
            f"**الرتبة:** `{role.name}`\n"
            f"**ID:** `{role.id}`\n"
            f"**بواسطة:** "
            f"{executor.mention if executor else 'غير معروف'}"
        ),
        "🗑️",
        discord.Color.red()
    )


# =========================================================
# ROLE UPDATE
# =========================================================

@bot.event
async def on_guild_role_update(
    before: discord.Role,
    after: discord.Role
):

    if before.name == after.name:
        return

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        after.guild,
        discord.AuditLogAction.role_update,
        after.id
    )

    executor = entry.user if entry else None

    await send_log(
        after.guild,
        "تعديل رتبة",
        (
            f"**قبل:** `{before.name}`\n"
            f"**بعد:** `{after.name}`\n"
            f"**بواسطة:** "
            f"{executor.mention if executor else 'غير معروف'}"
        ),
        "✏️",
        discord.Color.orange()
    )


# =========================================================
# MEMBER ROLE ADD / REMOVE
# =========================================================

@bot.event
async def on_member_update(
    before: discord.Member,
    after: discord.Member
):

    before_roles = set(before.roles)
    after_roles = set(after.roles)

    added = after_roles - before_roles
    removed = before_roles - after_roles

    if not added and not removed:
        return

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        after.guild,
        discord.AuditLogAction.member_role_update,
        after.id
    )

    executor = entry.user if entry else None

    executor_text = (
        executor.mention
        if executor
        else "غير معروف"
    )

    for role in added:

        if role.is_default():
            continue

        await send_log(
            after.guild,
            "إعطاء رتبة",
            (
                f"**العضو الذي أخذ الرتبة:** "
                f"{after.mention}\n"
                f"**الرتبة:** {role.mention}\n"
                f"**بواسطة:** {executor_text}"
            ),
            "➕",
            discord.Color.green()
        )

    for role in removed:

        if role.is_default():
            continue

        await send_log(
            after.guild,
            "سحب رتبة",
            (
                f"**العضو الذي سُحبت منه الرتبة:** "
                f"{after.mention}\n"
                f"**الرتبة:** {role.mention}\n"
                f"**بواسطة:** {executor_text}"
            ),
            "➖",
            discord.Color.red()
        )


# =========================================================
# AUTO ROLE SELECT
# =========================================================

class AutoRoleSelect(discord.ui.RoleSelect):

    def __init__(self, role_type: str):

        self.role_type = role_type

        super().__init__(
            placeholder="اختر الرتبة",
            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        role = self.values[0]
        me = interaction.guild.me

        if not me.guild_permissions.manage_roles:

            await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية إدارة الرتب.",
                ephemeral=True
            )

            return

        if role >= me.top_role:

            await interaction.response.send_message(
                "❌ هذه الرتبة أعلى من رتبة البوت أو مساوية لها.",
                ephemeral=True
            )

            return

        if self.role_type == "member":

            set_setting(
                interaction.guild.id,
                "auto_member_role",
                role.id
            )

            text = (
                f"تم تحديد رتبة الأعضاء التلقائية: "
                f"{role.mention}"
            )

        else:

            set_setting(
                interaction.guild.id,
                "auto_bot_role",
                role.id
            )

            text = (
                f"تم تحديد رتبة البوتات التلقائية: "
                f"{role.mention}"
            )

        await interaction.response.send_message(
            f"✅ {text}",
            ephemeral=True
        )


class AutoRoleView(discord.ui.View):

    def __init__(self, role_type: str):

        super().__init__(timeout=60)

        self.add_item(
            AutoRoleSelect(role_type)
        )


# =========================================================
# LOG CHANNEL SELECT
# =========================================================

class LogChannelSelect(discord.ui.ChannelSelect):

    def __init__(self):

        super().__init__(
            placeholder="اختر روم اللوق",
            channel_types=[
                discord.ChannelType.text
            ],
            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        channel = self.values[0]

        set_setting(
            interaction.guild.id,
            "log_channel",
            channel.id
        )

        await interaction.response.send_message(
            f"✅ تم تحديد روم اللوق: {channel.mention}",
            ephemeral=True
        )


class LogChannelView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=60)

        self.add_item(
            LogChannelSelect()
        )


# =========================================================
# SLASH COMMANDS
# =========================================================

@bot.tree.command(
    name="تحديد_اللوق",
    description="تحديد روم سجلات السيرفر"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def set_log(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        "اختر روم اللوق من القائمة:",
        view=LogChannelView(),
        ephemeral=True
    )


@bot.tree.command(
    name="رتبة_تلقائية_عضو",
    description="تحديد الرتبة التلقائية للأعضاء"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def auto_member_role(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        "اختر الرتبة التي يأخذها العضو تلقائيًا:",
        view=AutoRoleView("member"),
        ephemeral=True
    )


@bot.tree.command(
    name="رتبة_تلقائية_بوت",
    description="تحديد الرتبة التلقائية للبوتات"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def auto_bot_role(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        "اختر الرتبة التي يأخذها البوت تلقائيًا:",
        view=AutoRoleView("bot"),
        ephemeral=True
    )


@bot.tree.command(
    name="اعدادات_اللوق",
    description="عرض إعدادات اللوق والرتب التلقائية"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def log_settings(
    interaction: discord.Interaction
):

    row = get_settings(
        interaction.guild.id
    )

    log_channel = (
        interaction.guild.get_channel(
            row["log_channel"]
        )
        if row["log_channel"]
        else None
    )

    member_role = (
        interaction.guild.get_role(
            row["auto_member_role"]
        )
        if row["auto_member_role"]
        else None
    )

    bot_role = (
        interaction.guild.get_role(
            row["auto_bot_role"]
        )
        if row["auto_bot_role"]
        else None
    )

    embed = discord.Embed(
        title="⚙️ إعدادات CTRP",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="📋 روم اللوق",
        value=(
            log_channel.mention
            if log_channel
            else "غير محدد"
        ),
        inline=False
    )

    embed.add_field(
        name="👤 رتبة الأعضاء",
        value=(
            member_role.mention
            if member_role
            else "غير محددة"
        ),
        inline=False
    )

    embed.add_field(
        name="🤖 رتبة البوتات",
        value=(
            bot_role.mention
            if bot_role
            else "غير محددة"
        ),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# WARNING LOG SYSTEM
# =========================================================

last_warning_id = {}


def prepare_warning_ids():

    con = db()

    rows = con.execute(
        """
        SELECT guild_id, MAX(id) AS max_id
        FROM warnings
        GROUP BY guild_id
        """
    ).fetchall()

    con.close()

    for row in rows:

        last_warning_id[
            row["guild_id"]
        ] = row["max_id"] or 0


@tasks.loop(seconds=5)
async def warning_watcher_task():

    try:

        con = db()

        rows = con.execute(
            """
            SELECT *
            FROM warnings
            WHERE id > ?
            ORDER BY id ASC
            """,
            (
                min(last_warning_id.values())
                if last_warning_id
                else 0,
            )
        ).fetchall()

        con.close()

        for row in rows:

            guild_id = row["guild_id"]
            warning_id = row["id"]

            old_id = last_warning_id.get(
                guild_id,
                0
            )

            if warning_id <= old_id:
                continue

            last_warning_id[
                guild_id
            ] = warning_id

            guild = bot.get_guild(
                guild_id
            )

            if not guild:
                continue

            user = guild.get_member(
                row["user_id"]
            )

            moderator = guild.get_member(
                row["moderator_id"]
            )

            user_text = (
                user.mention
                if user
                else f"`{row['user_id']}`"
            )

            moderator_text = (
                moderator.mention
                if moderator
                else f"`{row['moderator_id']}`"
            )

            await send_log(
                guild,
                "تحذير عضو",
                (
                    f"**العضو:** {user_text}\n"
                    f"**بواسطة:** {moderator_text}\n"
                    f"**السبب:** "
                    f"`{row['reason'] or 'بدون سبب'}`"
                ),
                "⚠️",
                discord.Color.orange()
            )

    except Exception as e:

        print(
            f"❌ Warning Watcher Error: {e}"
        )


@warning_watcher_task.before_loop
async def before_warning_watcher():

    await bot.wait_until_ready()


# =========================================================
# LOAD SYSTEMS
# =========================================================

async def load_systems():

    systems_folder = "systems"

    if not os.path.exists(
        systems_folder
    ):

        os.makedirs(
            systems_folder
        )

    for filename in os.listdir(
        systems_folder
    ):

        if not filename.endswith(".py"):
            continue

        if filename == "__init__.py":
            continue

        module_name = filename[:-3]

        extension = (
            f"{systems_folder}.{module_name}"
        )

        try:

            await bot.load_extension(
                extension
            )

            print(
                f"✅ Loaded: {extension}"
            )

        except Exception as e:

            print(
                f"❌ Failed: {extension}"
            )

            print(
                f"   {e}"
            )


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    print("━━━━━━━━━━━━━━━━━━━━")
    print(f"🤖 Bot: {bot.user}")
    print("🟢 CTRP System Online")
    print("━━━━━━━━━━━━━━━━━━━━")

    try:

        synced = await bot.tree.sync()

        print(
            f"✅ Synced {len(synced)} slash commands"
        )

    except Exception as e:

        print(
            f"❌ Sync Error: {e}"
        )


# =========================================================
# MAIN
# =========================================================

async def main():

    init_db()

    prepare_warning_ids()

    await load_systems()

    if not warning_watcher_task.is_running():

        warning_watcher_task.start()

    await bot.start(TOKEN)


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    web_thread = threading.Thread(
        target=start_web_server,
        daemon=True
    )

    web_thread.start()

    asyncio.run(main())
