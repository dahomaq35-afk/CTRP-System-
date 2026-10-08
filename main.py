# =========================================================
# CTRP SYSTEM
# main.py
# FULL VERSION
# =========================================================

import os
import json
import asyncio
import threading
import sqlite3

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands, tasks

from database import init_db


# =========================================================
# DATABASE
# =========================================================

DB_FILE = "ctrp_system.db"

init_db()


def db():

    con = sqlite3.connect(
        DB_FILE,
        timeout=30
    )

    con.row_factory = sqlite3.Row

    return con


# =========================================================
# TOKEN
# =========================================================

TOKEN = os.getenv(
    "DISCORD_TOKEN"
)

if not TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN غير موجود في Environment Variables"
    )


# =========================================================
# PANEL API
# =========================================================

PANEL_SECRET = os.getenv(
    "CT_PANEL_SECRET"
)

PANEL_ORIGIN = os.getenv(
    "CT_PANEL_ORIGIN",
    "*"
)


# =========================================================
# RENDER PORT
# =========================================================

PORT = int(
    os.getenv(
        "PORT",
        "10000"
    )
)


# =========================================================
# HTTP API
# =========================================================

class HealthHandler(
    BaseHTTPRequestHandler
):

    def send_json(
        self,
        status: int,
        data: dict
    ):

        body = json.dumps(
            data,
            ensure_ascii=False
        ).encode(
            "utf-8"
        )

        self.send_response(
            status
        )

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            PANEL_ORIGIN
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-CT-PANEL-SECRET"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )

        self.end_headers()

        self.wfile.write(
            body
        )

    def do_OPTIONS(self):

        self.send_response(
            204
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            PANEL_ORIGIN
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-CT-PANEL-SECRET"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )

        self.end_headers()

    def do_GET(self):

        parsed = urlparse(
            self.path
        )

        path = parsed.path

        if path in (
            "/",
            "/health"
        ):

            self.send_json(
                200,
                {
                    "status": "online",
                    "bot": "CTRP Bot"
                }
            )

            return

        self.send_json(
            404,
            {
                "success": False,
                "error": "Not Found"
            }
        )

    def do_POST(self):

        self.send_json(
            404,
            {
                "success": False,
                "error": "Not Found"
            }
        )

    def log_message(
        self,
        format,
        *args
    ):

        pass


def start_web_server():

    server = HTTPServer(
        (
            "0.0.0.0",
            PORT
        ),
        HealthHandler
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━"
    )

    print(
        f"🌐 Render Port: {PORT}"
    )

    print(
        "🟢 Web/API Server Online"
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━"
    )

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
# GENERAL SETTINGS
# =========================================================

def ensure_guild_settings(
    guild_id: int
):

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
        VALUES (
            ?,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        )
        """,
        (guild_id,)
    )

    con.execute(
        """
        INSERT OR IGNORE INTO log_settings
        (
            guild_id,
            member_log,
            role_log,
            message_log,
            channel_log,
            warning_log,
            ticket_log,
            application_log,
            moderation_log,
            suggestion_log,
            notification_log,
            voice_log,
            level_log,
            points_log
        )
        VALUES (
            ?,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        )
        """,
        (guild_id,)
    )

    con.commit()
    con.close()


def get_settings(
    guild_id: int
):

    ensure_guild_settings(
        guild_id
    )

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

    ensure_guild_settings(
        guild_id
    )

    con = db()

    con.execute(
        f"""
        UPDATE settings
        SET {column} = ?
        WHERE guild_id = ?
        """,
        (
            value,
            guild_id
        )
    )

    con.commit()
    con.close()


# =========================================================
# LOG SETTINGS
# =========================================================

LOG_TYPES = {

    "member":
        "لوق الأعضاء",

    "role":
        "لوق الرتب",

    "message":
        "لوق الرسائل",

    "channel":
        "لوق القنوات",

    "warning":
        "لوق التحذيرات",

    "ticket":
        "لوق التذاكر",

    "application":
        "لوق التقديمات",

    "moderation":
        "لوق الإدارة",

    "suggestion":
        "لوق الاقتراحات",

    "notification":
        "لوق الإشعارات",

    "voice":
        "لوق الفويس",

    "level":
        "لوق اللفلات",

    "points":
        "لوق النقاط"
}


# =========================================================
# GET LOG CHANNEL
# =========================================================

async def get_section_log_channel(
    guild: discord.Guild,
    log_type: str
):

    if log_type not in LOG_TYPES:

        return None

    ensure_guild_settings(
        guild.id
    )

    con = db()

    row = con.execute(
        f"""
        SELECT {log_type}_log
        FROM log_settings
        WHERE guild_id = ?
        """,
        (
            guild.id,
        )
    ).fetchone()

    con.close()

    if not row:

        return None

    channel_id = row[
        f"{log_type}_log"
    ]

    if not channel_id:

        return None

    channel = guild.get_channel(
        int(channel_id)
    )

    if channel:

        return channel

    try:

        return await bot.fetch_channel(
            int(channel_id)
        )

    except Exception:

        return None


# =========================================================
# SEND LOG
# =========================================================

async def send_log(
    guild: discord.Guild,
    log_type: str,
    title: str,
    description: str,
    emoji: str = "📋",
    color: discord.Color =
        discord.Color.blurple()
):

    channel = (
        await get_section_log_channel(
            guild,
            log_type
        )
    )

    if not channel:

        return

    embed = discord.Embed(
        title=f"{emoji} {title}",
        description=description,
        color=color,
        timestamp=datetime.now(
            timezone.utc
        )
    )

    embed.set_footer(
        text=f"CTRP • {guild.name}"
    )

    try:

        await channel.send(
            embed=embed
        )

    except Exception as e:

        print(
            f"❌ Log Error "
            f"[{log_type}] "
            f"[{guild.name}]: {e}"
        )


# =========================================================
# AUDIT LOG
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

            if (
                entry.target
                and
                entry.target.id
                ==
                target_id
            ):

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

    role = member.guild.get_role(
        int(role_id)
    )

    if not role:

        return

    if role in member.roles:

        return

    me = member.guild.me

    if not me:

        return

    if not me.guild_permissions.manage_roles:

        return

    if role >= me.top_role:

        return

    try:

        await member.add_roles(
            role,
            reason=
                f"CTRP Auto Role - {role_type}"
        )

    except Exception as e:

        print(
            f"❌ Auto Role Error: {e}"
        )


# =========================================================
# MEMBER JOIN
# =========================================================

@bot.event
async def on_member_join(
    member
):

    # -----------------------------------------------------
    # AUTO ROLE
    # -----------------------------------------------------

    row = get_settings(
        member.guild.id
    )

    if member.bot:

        await give_auto_role(
            member,
            row["auto_bot_role"],
            "Bot"
        )

    else:

        await give_auto_role(
            member,
            row["auto_member_role"],
            "Member"
        )

    # -----------------------------------------------------
    # MEMBER LOG
    # -----------------------------------------------------

    await send_log(
        member.guild,
        "member",
        "دخول عضو",
        (
            f"**العضو:** "
            f"{member.mention}\n"

            f"**الاسم:** "
            f"`{member}`\n"

            f"**ID:** "
            f"`{member.id}`"
        ),
        "📥",
        discord.Color.green()
    )


# =========================================================
# MEMBER LEAVE
# =========================================================

@bot.event
async def on_member_remove(
    member
):

    await asyncio.sleep(
        1
    )

    entry = (
        await get_recent_audit_entry(
            member.guild,
            discord.AuditLogAction.kick,
            member.id
        )
    )

    if entry:

        executor = entry.user

        await send_log(
            member.guild,
            "member",
            "طرد عضو",
            (
                f"**العضو:** "
                f"`{member}`\n"

                f"**ID:** "
                f"`{member.id}`\n"

                f"**بواسطة:** "
                f"{
                    executor.mention
                    if executor
                    else 'غير معروف'
                }"
            ),
            "👢",
            discord.Color.orange()
        )

        return

    await send_log(
        member.guild,
        "member",
        "خروج عضو",
        (
            f"**العضو:** "
            f"`{member}`\n"

            f"**ID:** "
            f"`{member.id}`"
        ),
        "📤",
        discord.Color.dark_gray()
    )


# =========================================================
# BAN
# =========================================================

@bot.event
async def on_member_ban(
    guild,
    user
):

    await asyncio.sleep(
        1
    )

    entry = (
        await get_recent_audit_entry(
            guild,
            discord.AuditLogAction.ban,
            user.id
        )
    )

    executor = (
        entry.user
        if entry
        else None
    )

    reason = (
        entry.reason
        if entry
        and entry.reason
        else "بدون سبب"
    )

    await send_log(
        guild,
        "member",
        "حظر عضو",
        (
            f"**العضو:** "
            f"{user.mention}\n"

            f"**ID:** "
            f"`{user.id}`\n"

            f"**بواسطة:** "
            f"{
                executor.mention
                if executor
                else 'غير معروف'
            }\n"

            f"**السبب:** "
            f"`{reason}`"
        ),
        "🔨",
        discord.Color.red()
    )


# =========================================================
# MESSAGE DELETE
# =========================================================

@bot.event
async def on_message_delete(
    message
):

    if not message.guild:

        return

    if message.author.bot:

        return

    content = (
        message.content
        or
        "لا يوجد محتوى نصي"
    )

    if len(content) > 1000:

        content = (
            content[:1000]
            + "..."
        )

    await send_log(
        message.guild,
        "message",
        "حذف رسالة",
        (
            f"**العضو:** "
            f"{message.author.mention}\n"

            f"**الروم:** "
            f"{message.channel.mention}\n"

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
    before,
    after
):

    if not before.guild:

        return

    if before.author.bot:

        return

    if before.content == after.content:

        return

    old_content = (
        before.content
        or "فارغ"
    )

    new_content = (
        after.content
        or "فارغ"
    )

    if len(old_content) > 700:

        old_content = (
            old_content[:700]
            + "..."
        )

    if len(new_content) > 700:

        new_content = (
            new_content[:700]
            + "..."
        )

    await send_log(
        before.guild,
        "message",
        "تعديل رسالة",
        (
            f"**العضو:** "
            f"{before.author.mention}\n"

            f"**الروم:** "
            f"{before.channel.mention}\n\n"

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
    channel
):

    await asyncio.sleep(
        1
    )

    entry = (
        await get_recent_audit_entry(
            channel.guild,
            discord.AuditLogAction.channel_create,
            channel.id
        )
    )

    executor = (
        entry.user
        if entry
        else None
    )

    await send_log(
        channel.guild,
        "channel",
        "إنشاء روم",
        (
            f"**الروم:** "
            f"{channel.mention}\n"

            f"**الاسم:** "
            f"`{channel.name}`\n"

            f"**بواسطة:** "
            f"{
                executor.mention
                if executor
                else 'غير معروف'
            }"
        ),
        "📁",
        discord.Color.green()
    )


# =========================================================
# CHANNEL DELETE
# =========================================================

@bot.event
async def on_guild_channel_delete(
    channel
):

    await asyncio.sleep(
        1
    )

    entry = (
        await get_recent_audit_entry(
            channel.guild,
            discord.AuditLogAction.channel_delete,
            channel.id
        )
    )

    executor = (
        entry.user
        if entry
        else None
    )

    await send_log(
        channel.guild,
        "channel",
        "حذف روم",
        (
            f"**الروم:** "
            f"`#{channel.name}`\n"

            f"**ID:** "
            f"`{channel.id}`\n"

            f"**بواسطة:** "
            f"{
                executor.mention
                if executor
                else 'غير معروف'
            }"
        ),
        "🗑️",
        discord.Color.red()
    )


# =========================================================
# ROLE CREATE
# =========================================================

@bot.event
async def on_guild_role_create(
    role
):

    await asyncio.sleep(
        1
    )

    entry = (
        await get_recent_audit_entry(
            role.guild,
            discord.AuditLogAction.role_create,
            role.id
        )
    )

    executor = (
        entry.user
        if entry
        else None
    )

    await send_log(
        role.guild,
        "role",
        "إنشاء رتبة",
        (
            f"**الرتبة:** "
            f"{role.mention}\n"

            f"**الاسم:** "
            f"`{role.name}`\n"

            f"**بواسطة:** "
            f"{
                executor.mention
                if executor
                else 'غير معروف'
            }"
        ),
        "🏷️",
        discord.Color.green()
    )


# =========================================================
# ROLE DELETE
# =========================================================

@bot.event
async def on_guild_role_delete(
    role
):

    await asyncio.sleep(
        1
    )

    entry = (
        await get_recent_audit_entry(
            role.guild,
            discord.AuditLogAction.role_delete,
            role.id
        )
    )

    executor = (
        entry.user
        if entry
        else None
    )

    await send_log(
        role.guild,
        "role",
        "حذف رتبة",
        (
            f"**الرتبة:** "
            f"`{role.name}`\n"

            f"**ID:** "
            f"`{role.id}`\n"

            f"**بواسطة:** "
            f"{
                executor.mention
                if executor
                else 'غير معروف'
            }"
        ),
        "🗑️",
        discord.Color.red()
    )


# =========================================================
# ROLE UPDATE
# =========================================================

@bot.event
async def on_guild_role_update(
    before,
    after
):

    if before.name == after.name:

        return

    await asyncio.sleep(
        1
    )

    entry = (
        await get_recent_audit_entry(
            after.guild,
            discord.AuditLogAction.role_update,
            after.id
        )
    )

    executor = (
        entry.user
        if entry
        else None
    )

    await send_log(
        after.guild,
        "role",
        "تعديل رتبة",
        (
            f"**قبل:** "
            f"`{before.name}`\n"

            f"**بعد:** "
            f"`{after.name}`\n"

            f"**بواسطة:** "
            f"{
                executor.mention
                if executor
                else 'غير معروف'
            }"
        ),
        "✏️",
        discord.Color.orange()
    )


# =========================================================
# MEMBER ROLE UPDATE
# =========================================================

@bot.event
async def on_member_update(
    before,
    after
):

    before_roles = set(
        before.roles
    )

    after_roles = set(
        after.roles
    )

    added = (
        after_roles
        -
        before_roles
    )

    removed = (
        before_roles
        -
        after_roles
    )

    if not added and not removed:

        return

    await asyncio.sleep(
        1
    )

    entry = (
        await get_recent_audit_entry(
            after.guild,
            discord.AuditLogAction.member_role_update,
            after.id
        )
    )

    executor = (
        entry.user
        if entry
        else None
    )

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
            "role",
            "إعطاء رتبة",
            (
                f"**العضو:** "
                f"{after.mention}\n"

                f"**الرتبة:** "
                f"{role.mention}\n"

                f"**بواسطة:** "
                f"{executor_text}"
            ),
            "➕",
            discord.Color.green()
        )

    for role in removed:

        if role.is_default():

            continue

        await send_log(
            after.guild,
            "role",
            "سحب رتبة",
            (
                f"**العضو:** "
                f"{after.mention}\n"

                f"**الرتبة:** "
                f"{role.mention}\n"

                f"**بواسطة:** "
                f"{executor_text}"
            ),
            "➖",
            discord.Color.red()
        )


# =========================================================
# LOG CHANNEL SELECT
# =========================================================

class LogChannelSelect(
    discord.ui.ChannelSelect
):

    def __init__(
        self,
        log_type
    ):

        self.log_type = log_type

        super().__init__(
            placeholder=
                "اختر روم اللوق",

            channel_types=[
                discord.ChannelType.text
            ],

            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction
    ):

        ensure_guild_settings(
            interaction.guild.id
        )

        con = db()

        con.execute(
            f"""
            UPDATE log_settings
            SET {self.log_type}_log = ?
            WHERE guild_id = ?
            """,
            (
                self.values[0].id,
                interaction.guild.id
            )
        )

        con.commit()
        con.close()

        await interaction.response.send_message(
            f"✅ تم تحديد "
            f"{LOG_TYPES[self.log_type]}: "
            f"{self.values[0].mention}",
            ephemeral=True
        )


class LogChannelView(
    discord.ui.View
):

    def __init__(
        self,
        log_type
    ):

        super().__init__(
            timeout=60
        )

        self.add_item(
            LogChannelSelect(
                log_type
            )
        )


# =========================================================
# LOG TYPE SELECT
# =========================================================

class LogTypeSelect(
    discord.ui.Select
):

    def __init__(self):

        options = []

        for key, name in LOG_TYPES.items():

            options.append(
                discord.SelectOption(
                    label=name,
                    value=key,
                    emoji="📋"
                )
            )

        super().__init__(
            placeholder=
                "اختر نوع اللوق",

            min_values=1,
            max_values=1,

            options=options
        )

    async def callback(
        self,
        interaction
    ):

        log_type = self.values[0]

        await interaction.response.send_message(
            f"اختر روم "
            f"{LOG_TYPES[log_type]}:",

            view=LogChannelView(
                log_type
            ),

            ephemeral=True
        )


class LogTypeView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=60
        )

        self.add_item(
            LogTypeSelect()
        )


# =========================================================
# AUTO ROLE SELECT
# =========================================================

class AutoRoleSelect(
    discord.ui.RoleSelect
):

    def __init__(
        self,
        role_type
    ):

        self.role_type = role_type

        super().__init__(
            placeholder=
                "اختر الرتبة",

            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction
    ):

        role = self.values[0]

        me = interaction.guild.me

        if not me.guild_permissions.manage_roles:

            return await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية إدارة الرتب.",
                ephemeral=True
            )

        if role >= me.top_role:

            return await interaction.response.send_message(
                "❌ هذه الرتبة أعلى من رتبة البوت أو مساوية لها.",
                ephemeral=True
            )

        if self.role_type == "member":

            set_setting(
                interaction.guild.id,
                "auto_member_role",
                role.id
            )

            text = (
                "تم تحديد رتبة الأعضاء "
                "التلقائية: "
                f"{role.mention}"
            )

        else:

            set_setting(
                interaction.guild.id,
                "auto_bot_role",
                role.id
            )

            text = (
                "تم تحديد رتبة البوتات "
                "التلقائية: "
                f"{role.mention}"
            )

        await interaction.response.send_message(
            f"✅ {text}",
            ephemeral=True
        )


class AutoRoleView(
    discord.ui.View
):

    def __init__(
        self,
        role_type
    ):

        super().__init__(
            timeout=60
        )

        self.add_item(
            AutoRoleSelect(
                role_type
            )
        )


# =========================================================
# COMMANDS
# =========================================================

@bot.tree.command(
    name="تحديد_اللوق",
    description=
        "تحديد روم لقسم من أقسام اللوق"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def set_log(
    interaction
):

    await interaction.response.send_message(
        "اختر قسم اللوق الذي تريد تحديده:",
        view=LogTypeView(),
        ephemeral=True
    )


@bot.tree.command(
    name="رتبة_تلقائية_عضو",
    description=
        "تحديد الرتبة التلقائية للأعضاء"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def auto_member_role(
    interaction
):

    await interaction.response.send_message(
        "اختر الرتبة التي يأخذها العضو تلقائيًا:",
        view=AutoRoleView(
            "member"
        ),
        ephemeral=True
    )


@bot.tree.command(
    name="رتبة_تلقائية_بوت",
    description=
        "تحديد الرتبة التلقائية للبوتات"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def auto_bot_role(
    interaction
):

    await interaction.response.send_message(
        "اختر الرتبة التي يأخذها البوت تلقائيًا:",
        view=AutoRoleView(
            "bot"
        ),
        ephemeral=True
    )


@bot.tree.command(
    name="اعدادات_اللوق",
    description=
        "عرض إعدادات اللوقات"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def log_settings(
    interaction
):

    ensure_guild_settings(
        interaction.guild.id
    )

    con = db()

    row = con.execute(
        """
        SELECT *
        FROM log_settings
        WHERE guild_id = ?
        """,
        (
            interaction.guild.id,
        )
    ).fetchone()

    con.close()

    embed = discord.Embed(
        title="⚙️ إعدادات اللوقات",
        color=discord.Color.blurple()
    )

    for key, name in LOG_TYPES.items():

        channel_id = row[
            f"{key}_log"
        ]

        channel = (
            interaction.guild.get_channel(
                int(channel_id)
            )
            if channel_id
            else None
        )

        embed.add_field(
            name=name,
            value=(
                channel.mention
                if channel
                else "غير محدد"
            ),
            inline=False
        )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# WARNING WATCHER
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
        ] = (
            row["max_id"]
            or 0
        )


@tasks.loop(
    seconds=5
)
async def warning_watcher_task():

    try:

        con = db()

        minimum_id = (
            min(
                last_warning_id.values()
            )
            if last_warning_id
            else 0
        )

        rows = con.execute(
            """
            SELECT *
            FROM warnings
            WHERE id > ?
            ORDER BY id ASC
            """,
            (
                minimum_id,
            )
        ).fetchall()

        con.close()

        for row in rows:

            guild_id = (
                row["guild_id"]
            )

            warning_id = (
                row["id"]
            )

            old_id = (
                last_warning_id.get(
                    guild_id,
                    0
                )
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
                else
                f"`{row['user_id']}`"
            )

            moderator_text = (
                moderator.mention
                if moderator
                else
                f"`{row['moderator_id']}`"
            )

            await send_log(
                guild,
                "warning",
                "تحذير عضو",
                (
                    f"**العضو:** "
                    f"{user_text}\n"

                    f"**بواسطة:** "
                    f"{moderator_text}\n"

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

        if not filename.endswith(
            ".py"
        ):

            continue

        if filename == "__init__.py":

            continue

        module_name = filename[:-3]

        extension = (
            f"{systems_folder}."
            f"{module_name}"
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
# READY
# =========================================================

@bot.event
async def on_ready():

    print(
        "━━━━━━━━━━━━━━━━━━━━"
    )

    print(
        f"🤖 Bot: {bot.user}"
    )

    print(
        "🟢 CTRP System Online"
    )

    print(
        f"👥 Members Intent: "
        f"{bot.intents.members}"
    )

    print(
        "🔔 Notifications System Ready"
    )

    print(
        "🌐 API Ready"
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━"
    )

    try:

        synced = await bot.tree.sync()

        print(
            f"✅ Synced "
            f"{len(synced)} slash commands"
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

    await bot.start(
        TOKEN
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    web_thread = threading.Thread(
        target=start_web_server,
        daemon=True
    )

    web_thread.start()

    asyncio.run(
        main()
    )
