import os
import io
import asyncio
import threading
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

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
# SETTINGS
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
            ?, NULL, NULL, NULL, NULL, NULL,
            NULL, NULL, NULL, NULL, NULL,
            NULL, NULL, NULL
        )
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
# WELCOME DATABASE
# =========================================================

def init_welcome_db():

    con = db()

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS welcome_settings
        (
            guild_id INTEGER PRIMARY KEY,

            enabled INTEGER DEFAULT 0,

            channel_id INTEGER,

            background_url TEXT,

            show_avatar INTEGER DEFAULT 1,

            avatar_x REAL DEFAULT 50,
            avatar_y REAL DEFAULT 50,
            avatar_size REAL DEFAULT 180,

            avatar_shape TEXT DEFAULT 'circle',

            show_username INTEGER DEFAULT 1,

            username_x REAL DEFAULT 50,
            username_y REAL DEFAULT 78,

            username_size REAL DEFAULT 48,

            username_color TEXT DEFAULT '#FFFFFF',

            message TEXT DEFAULT
                'مرحباً {mention} في {server}',

            image_width INTEGER DEFAULT 1024,
            image_height INTEGER DEFAULT 400
        )
        """
    )

    con.commit()
    con.close()


init_welcome_db()


def ensure_welcome_settings(guild_id: int):

    con = db()

    con.execute(
        """
        INSERT OR IGNORE INTO welcome_settings
        (
            guild_id,
            enabled,
            channel_id,
            background_url,
            show_avatar,
            avatar_x,
            avatar_y,
            avatar_size,
            avatar_shape,
            show_username,
            username_x,
            username_y,
            username_size,
            username_color,
            message,
            image_width,
            image_height
        )
        VALUES
        (
            ?,
            0,
            NULL,
            NULL,
            1,
            50,
            50,
            180,
            'circle',
            1,
            50,
            78,
            48,
            '#FFFFFF',
            'مرحباً {mention} في {server}',
            1024,
            400
        )
        """,
        (guild_id,)
    )

    con.commit()
    con.close()


def get_welcome_settings(guild_id: int):

    ensure_welcome_settings(guild_id)

    con = db()

    row = con.execute(
        """
        SELECT *
        FROM welcome_settings
        WHERE guild_id = ?
        """,
        (guild_id,)
    ).fetchone()

    con.close()

    return row


# =========================================================
# WELCOME IMAGE HELPERS
# =========================================================

def download_image(url: str):

    try:

        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": "CTRP-Bot/1.0"
            }
        )

        response.raise_for_status()

        image = Image.open(
            io.BytesIO(response.content)
        )

        return image.convert("RGBA")

    except Exception as e:

        print(
            f"❌ Welcome Image Error: {e}"
        )

        return None


def get_font(size: int, bold: bool = False):

    fonts = []

    if bold:

        fonts.extend(
            [
                "DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            ]
        )

    else:

        fonts.extend(
            [
                "DejaVuSans.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            ]
        )

    for font_path in fonts:

        try:

            return ImageFont.truetype(
                font_path,
                size
            )

        except Exception:
            continue

    return ImageFont.load_default()


def create_circle_avatar(
    image: Image.Image,
    size: int
):

    image = ImageOps.fit(
        image.convert("RGBA"),
        (size, size),
        method=Image.Resampling.LANCZOS
    )

    mask = Image.new(
        "L",
        (size, size),
        0
    )

    mask_draw = ImageDraw.Draw(mask)

    mask_draw.ellipse(
        (0, 0, size - 1, size - 1),
        fill=255
    )

    image.putalpha(mask)

    return image


def create_rounded_avatar(
    image: Image.Image,
    size: int
):

    image = ImageOps.fit(
        image.convert("RGBA"),
        (size, size),
        method=Image.Resampling.LANCZOS
    )

    mask = Image.new(
        "L",
        (size, size),
        0
    )

    mask_draw = ImageDraw.Draw(mask)

    radius = max(
        10,
        int(size * 0.18)
    )

    mask_draw.rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=radius,
        fill=255
    )

    image.putalpha(mask)

    return image


def safe_color(value, fallback="#FFFFFF"):

    if not value:
        return fallback

    try:

        value = str(value).strip()

        if not value.startswith("#"):
            value = "#" + value

        if len(value) != 7:
            return fallback

        int(value[1:], 16)

        return value

    except Exception:

        return fallback


# =========================================================
# CREATE WELCOME IMAGE
# =========================================================

def make_welcome_image(
    member: discord.Member,
    settings
):

    width = int(
        settings["image_width"] or 1024
    )

    height = int(
        settings["image_height"] or 400
    )

    width = max(
        400,
        min(width, 3000)
    )

    height = max(
        200,
        min(height, 2000)
    )

    # -----------------------------------------------------
    # BACKGROUND
    # -----------------------------------------------------

    background = None

    background_url = settings["background_url"]

    if background_url:

        background = download_image(
            background_url
        )

    if background:

        background = ImageOps.fit(
            background,
            (width, height),
            method=Image.Resampling.LANCZOS
        )

    else:

        background = Image.new(
            "RGBA",
            (width, height),
            (12, 12, 12, 255)
        )

    canvas = background.convert("RGBA")

    draw = ImageDraw.Draw(canvas)

    # -----------------------------------------------------
    # AVATAR
    # -----------------------------------------------------

    if settings["show_avatar"]:

        try:

            avatar_url = str(
                member.display_avatar.replace(
                    size=512
                ).url
            )

            avatar = download_image(
                avatar_url
            )

            if avatar:

                avatar_size = int(
                    settings["avatar_size"] or 180
                )

                avatar_size = max(
                    40,
                    min(avatar_size, 1000)
                )

                shape = (
                    settings["avatar_shape"]
                    or "circle"
                )

                if shape == "rounded":

                    avatar = create_rounded_avatar(
                        avatar,
                        avatar_size
                    )

                elif shape == "square":

                    avatar = ImageOps.fit(
                        avatar,
                        (
                            avatar_size,
                            avatar_size
                        ),
                        method=Image.Resampling.LANCZOS
                    )

                else:

                    avatar = create_circle_avatar(
                        avatar,
                        avatar_size
                    )

                avatar_x = float(
                    settings["avatar_x"]
                    if settings["avatar_x"] is not None
                    else 50
                )

                avatar_y = float(
                    settings["avatar_y"]
                    if settings["avatar_y"] is not None
                    else 50
                )

                x = int(
                    width *
                    (avatar_x / 100)
                    -
                    avatar_size / 2
                )

                y = int(
                    height *
                    (avatar_y / 100)
                    -
                    avatar_size / 2
                )

                canvas.alpha_composite(
                    avatar,
                    (x, y)
                )

        except Exception as e:

            print(
                f"❌ Avatar Render Error: {e}"
            )

    # -----------------------------------------------------
    # USERNAME
    # -----------------------------------------------------

    if settings["show_username"]:

        username = member.display_name

        username_size = int(
            settings["username_size"] or 48
        )

        username_size = max(
            12,
            min(username_size, 300)
        )

        font = get_font(
            username_size,
            bold=True
        )

        username_color = safe_color(
            settings["username_color"],
            "#FFFFFF"
        )

        bbox = draw.textbbox(
            (0, 0),
            username,
            font=font
        )

        text_width = (
            bbox[2] - bbox[0]
        )

        text_height = (
            bbox[3] - bbox[1]
        )

        username_x = float(
            settings["username_x"]
            if settings["username_x"] is not None
            else 50
        )

        username_y = float(
            settings["username_y"]
            if settings["username_y"] is not None
            else 78
        )

        x = int(
            width *
            (username_x / 100)
            -
            text_width / 2
        )

        y = int(
            height *
            (username_y / 100)
            -
            text_height / 2
        )

        # Shadow
        draw.text(
            (
                x + 3,
                y + 3
            ),
            username,
            font=font,
            fill="#000000",
            stroke_width=2,
            stroke_fill="#000000"
        )

        draw.text(
            (x, y),
            username,
            font=font,
            fill=username_color
        )

    # -----------------------------------------------------
    # MESSAGE
    # -----------------------------------------------------

    message = (
        settings["message"]
        or "مرحباً {mention} في {server}"
    )

    message = message.replace(
        "{user}",
        member.display_name
    )

    message = message.replace(
        "{username}",
        member.display_name
    )

    message = message.replace(
        "{mention}",
        member.mention
    )

    message = message.replace(
        "{server}",
        member.guild.name
    )

    message = message.replace(
        "{count}",
        str(member.guild.member_count)
    )

    # -----------------------------------------------------
    # EXPORT
    # -----------------------------------------------------

    buffer = io.BytesIO()

    canvas.save(
        buffer,
        format="PNG",
        optimize=True
    )

    buffer.seek(0)

    return buffer, message


# =========================================================
# LOG SETTINGS
# =========================================================

LOG_TYPES = {
    "member": "لوق الأعضاء",
    "role": "لوق الرتب",
    "message": "لوق الرسائل",
    "channel": "لوق القنوات",
    "warning": "لوق التحذيرات",
    "ticket": "لوق التذاكر",
    "application": "لوق التقديمات",
    "moderation": "لوق الإدارة",
    "suggestion": "لوق الاقتراحات",
    "notification": "لوق الإشعارات",
    "voice": "لوق الفويس",
    "level": "لوق اللفلات",
    "points": "لوق النقاط"
}


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
        (guild.id,)
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


async def send_log(
    guild: discord.Guild,
    log_type: str,
    title: str,
    description: str,
    emoji: str = "📋",
    color: discord.Color = discord.Color.blurple()
):

    channel = await get_section_log_channel(
        guild,
        log_type
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
                and entry.target.id == target_id
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
            reason=f"CTRP Auto Role - {role_type}"
        )

    except Exception as e:

        print(
            f"❌ Auto Role Error: {e}"
        )


# =========================================================
# MEMBER JOIN
# =========================================================

@bot.event
async def on_member_join(member):

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
            f"**العضو:** {member.mention}\n"
            f"**الاسم:** `{member}`\n"
            f"**ID:** `{member.id}`"
        ),
        "📥",
        discord.Color.green()
    )

    # -----------------------------------------------------
    # WELCOME
    # -----------------------------------------------------

    try:

        welcome = get_welcome_settings(
            member.guild.id
        )

        if not welcome:
            return

        if not welcome["enabled"]:
            return

        channel_id = welcome["channel_id"]

        if not channel_id:
            return

        channel = member.guild.get_channel(
            int(channel_id)
        )

        if not channel:

            try:

                channel = await bot.fetch_channel(
                    int(channel_id)
                )

            except Exception:

                return

        image_buffer, message = (
            await asyncio.to_thread(
                make_welcome_image,
                member,
                welcome
            )
        )

        file = discord.File(
            image_buffer,
            filename="welcome.png"
        )

        await channel.send(
            content=message,
            file=file
        )

        print(
            f"👋 Welcome sent: "
            f"{member} -> "
            f"{member.guild.name}"
        )

    except Exception as e:

        print(
            f"❌ Welcome Error "
            f"[{member.guild.name}]: {e}"
        )


# =========================================================
# MEMBER LEAVE / KICK
# =========================================================

@bot.event
async def on_member_remove(member):

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        member.guild,
        discord.AuditLogAction.kick,
        member.id
    )

    if entry:

        executor = entry.user

        await send_log(
            member.guild,
            "member",
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
        "member",
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
async def on_member_ban(guild, user):

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
        "member",
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
async def on_message_delete(message):

    if not message.guild:
        return

    if message.author.bot:
        return

    content = (
        message.content
        or "لا يوجد محتوى نصي"
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
async def on_guild_channel_create(channel):

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        channel.guild,
        discord.AuditLogAction.channel_create,
        channel.id
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
async def on_guild_channel_delete(channel):

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        channel.guild,
        discord.AuditLogAction.channel_delete,
        channel.id
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
async def on_guild_role_create(role):

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        role.guild,
        discord.AuditLogAction.role_create,
        role.id
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
async def on_guild_role_delete(role):

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        role.guild,
        discord.AuditLogAction.role_delete,
        role.id
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
    before,
    after
):

    if before.name == after.name:
        return

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        after.guild,
        discord.AuditLogAction.role_update,
        after.id
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
        - before_roles
    )

    removed = (
        before_roles
        - after_roles
    )

    if not added and not removed:
        return

    await asyncio.sleep(1)

    entry = await get_recent_audit_entry(
        after.guild,
        discord.AuditLogAction.member_role_update,
        after.id
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
                f"**العضو:** {after.mention}\n"
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
            "role",
            "سحب رتبة",
            (
                f"**العضو:** {after.mention}\n"
                f"**الرتبة:** {role.mention}\n"
                f"**بواسطة:** {executor_text}"
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

    def __init__(self, log_type):

        self.log_type = log_type

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

    def __init__(self, log_type):

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
            placeholder="اختر نوع اللوق",
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
            placeholder="اختر الرتبة",
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
# WELCOME CHANNEL SELECT
# =========================================================

class WelcomeChannelSelect(
    discord.ui.ChannelSelect
):

    def __init__(self):

        super().__init__(
            placeholder="اختر روم الترحيب",
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

        ensure_welcome_settings(
            interaction.guild.id
        )

        con = db()

        con.execute(
            """
            UPDATE welcome_settings
            SET channel_id = ?
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
            f"✅ تم تحديد روم الترحيب: "
            f"{self.values[0].mention}",
            ephemeral=True
        )


class WelcomeChannelView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=60
        )

        self.add_item(
            WelcomeChannelSelect()
        )


# =========================================================
# COMMANDS
# =========================================================

@bot.tree.command(
    name="تحديد_اللوق",
    description="تحديد روم لقسم من أقسام اللوق"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def set_log(interaction):

    await interaction.response.send_message(
        "اختر قسم اللوق الذي تريد تحديده:",
        view=LogTypeView(),
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
    interaction
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
    interaction
):

    await interaction.response.send_message(
        "اختر الرتبة التي يأخذها البوت تلقائيًا:",
        view=AutoRoleView("bot"),
        ephemeral=True
    )


@bot.tree.command(
    name="اعدادات_اللوق",
    description="عرض إعدادات اللوقات"
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
        (interaction.guild.id,)
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
# WELCOME COMMAND
# =========================================================

@bot.tree.command(
    name="تحديد_روم_الترحيب",
    description="تحديد الروم الذي ترسل فيه الترحيبات"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def set_welcome_channel(
    interaction
):

    await interaction.response.send_message(
        "اختر روم الترحيب:",
        view=WelcomeChannelView(),
        ephemeral=True
    )


@bot.tree.command(
    name="الترحيب",
    description="تشغيل أو إيقاف نظام الترحيب"
)
@app_commands.describe(
    الحالة="تشغيل أو إيقاف الترحيب"
)
@app_commands.choices(
    الحالة=[
        app_commands.Choice(
            name="تشغيل",
            value="on"
        ),
        app_commands.Choice(
            name="إيقاف",
            value="off"
        )
    ]
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def welcome_toggle(
    interaction,
    الحالة: app_commands.Choice[str]
):

    ensure_welcome_settings(
        interaction.guild.id
    )

    enabled = (
        1
        if الحالة.value == "on"
        else 0
    )

    con = db()

    con.execute(
        """
        UPDATE welcome_settings
        SET enabled = ?
        WHERE guild_id = ?
        """,
        (
            enabled,
            interaction.guild.id
        )
    )

    con.commit()
    con.close()

    text = (
        "🟢 تم تشغيل نظام الترحيب."
        if enabled
        else
        "🔴 تم إيقاف نظام الترحيب."
    )

    await interaction.response.send_message(
        text,
        ephemeral=True
    )


@bot.tree.command(
    name="اعدادات_الترحيب",
    description="عرض إعدادات الترحيب الحالية"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def welcome_settings_command(
    interaction
):

    row = get_welcome_settings(
        interaction.guild.id
    )

    channel = None

    if row["channel_id"]:

        channel = (
            interaction.guild.get_channel(
                int(row["channel_id"])
            )
        )

    embed = discord.Embed(
        title="👋 إعدادات الترحيب",
        color=discord.Color.dark_red()
    )

    embed.add_field(
        name="الحالة",
        value=(
            "🟢 مفعّل"
            if row["enabled"]
            else "🔴 متوقف"
        ),
        inline=False
    )

    embed.add_field(
        name="روم الترحيب",
        value=(
            channel.mention
            if channel
            else "غير محدد"
        ),
        inline=False
    )

    embed.add_field(
        name="الخلفية",
        value=(
            "محددة"
            if row["background_url"]
            else "غير محددة"
        ),
        inline=True
    )

    embed.add_field(
        name="صورة العضو",
        value=(
            "مفعلة"
            if row["show_avatar"]
            else "متوقفة"
        ),
        inline=True
    )

    embed.add_field(
        name="اسم العضو",
        value=(
            "مفعل"
            if row["show_username"]
            else "متوقف"
        ),
        inline=True
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
        ] = row["max_id"] or 0


@tasks.loop(seconds=5)
async def warning_watcher_task():

    try:

        con = db()

        minimum_id = (
            min(last_warning_id.values())
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
            (minimum_id,)
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
                "warning",
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

    print("━━━━━━━━━━━━━━━━━━━━")

    print(
        f"🤖 Bot: {bot.user}"
    )

    print(
        "🟢 CTRP System Online"
    )

    print("━━━━━━━━━━━━━━━━━━━━")

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

    init_welcome_db()

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
