# =========================================================
# CTRP SYSTEM
# main.py
# FULL VERSION
# =========================================================

import os
import io
import json
import asyncio
import threading
import sqlite3

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import requests

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageOps
)

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

            background_x REAL DEFAULT 50,
            background_y REAL DEFAULT 50,
            background_scale REAL DEFAULT 100,

            show_avatar INTEGER DEFAULT 1,

            avatar_x REAL DEFAULT 50,
            avatar_y REAL DEFAULT 50,
            avatar_size REAL DEFAULT 180,

            avatar_shape TEXT DEFAULT 'circle',

            avatar_rotation REAL DEFAULT 0,
            avatar_opacity REAL DEFAULT 100,

            avatar_border_enabled INTEGER DEFAULT 0,
            avatar_border_width REAL DEFAULT 0,
            avatar_border_color TEXT DEFAULT '#FFFFFF',

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

    # -----------------------------------------------------
    # MIGRATION
    # -----------------------------------------------------

    existing_columns = {
        row["name"]
        for row in con.execute(
            "PRAGMA table_info(welcome_settings)"
        ).fetchall()
    }

    columns_to_add = {

        "background_x":
            "REAL DEFAULT 50",

        "background_y":
            "REAL DEFAULT 50",

        "background_scale":
            "REAL DEFAULT 100",

        "avatar_rotation":
            "REAL DEFAULT 0",

        "avatar_opacity":
            "REAL DEFAULT 100",

        "avatar_border_enabled":
            "INTEGER DEFAULT 0",

        "avatar_border_width":
            "REAL DEFAULT 0",

        "avatar_border_color":
            "TEXT DEFAULT '#FFFFFF'"
    }

    for column, definition in columns_to_add.items():

        if column not in existing_columns:

            con.execute(
                f"""
                ALTER TABLE welcome_settings
                ADD COLUMN {column} {definition}
                """
            )

    con.commit()
    con.close()


init_welcome_db()


# =========================================================
# WELCOME SETTINGS
# =========================================================

def ensure_welcome_settings(
    guild_id: int
):

    con = db()

    con.execute(
        """
        INSERT OR IGNORE INTO welcome_settings
        (
            guild_id,
            enabled,
            channel_id,

            background_url,
            background_x,
            background_y,
            background_scale,

            show_avatar,

            avatar_x,
            avatar_y,
            avatar_size,
            avatar_shape,
            avatar_rotation,
            avatar_opacity,

            avatar_border_enabled,
            avatar_border_width,
            avatar_border_color,

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
            50,
            50,
            100,

            1,

            50,
            50,
            180,
            'circle',
            0,
            100,

            0,
            0,
            '#FFFFFF',

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


def get_welcome_settings(
    guild_id: int
):

    ensure_welcome_settings(
        guild_id
    )

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
# SAVE WELCOME SETTINGS
# =========================================================

def save_welcome_settings(
    guild_id: int,
    data: dict
):

    ensure_welcome_settings(
        guild_id
    )

    allowed = {

        "enabled",

        "channel_id",

        "background_url",
        "background_x",
        "background_y",
        "background_scale",

        "show_avatar",

        "avatar_x",
        "avatar_y",
        "avatar_size",
        "avatar_shape",
        "avatar_rotation",
        "avatar_opacity",

        "avatar_border_enabled",
        "avatar_border_width",
        "avatar_border_color",

        "show_username",

        "username_x",
        "username_y",
        "username_size",
        "username_color",

        "message",

        "image_width",
        "image_height"
    }

    updates = []

    values = []

    for key, value in data.items():

        if key not in allowed:
            continue

        updates.append(
            f"{key} = ?"
        )

        values.append(
            value
        )

    if not updates:
        return False

    values.append(
        guild_id
    )

    con = db()

    con.execute(
        f"""
        UPDATE welcome_settings
        SET {", ".join(updates)}
        WHERE guild_id = ?
        """,
        values
    )

    con.commit()
    con.close()

    return True


# =========================================================
# VALIDATE WELCOME SETTINGS
# =========================================================

def validate_welcome_data(
    data: dict
):

    clean = {}

    if "enabled" in data:

        clean["enabled"] = (
            1
            if bool(data["enabled"])
            else 0
        )

    if "channel_id" in data:

        value = data["channel_id"]

        if value in (
            None,
            "",
            0,
            "0"
        ):

            clean["channel_id"] = None

        else:

            clean["channel_id"] = int(
                value
            )

    if "background_url" in data:

        url = str(
            data["background_url"]
            or ""
        ).strip()

        if url:

            parsed = urlparse(url)

            if parsed.scheme not in (
                "http",
                "https"
            ):

                raise ValueError(
                    "رابط الخلفية يجب أن يكون HTTP أو HTTPS"
                )

        clean["background_url"] = (
            url or None
        )

    numeric_ranges = {

        "background_x":
            (-500, 1500),

        "background_y":
            (-500, 1500),

        "background_scale":
            (10, 500),

        "avatar_x":
            (-500, 1500),

        "avatar_y":
            (-500, 1500),

        "avatar_size":
            (20, 1500),

        "avatar_rotation":
            (-360, 360),

        "avatar_opacity":
            (0, 100),

        "avatar_border_width":
            (0, 100),

        "username_x":
            (-500, 1500),

        "username_y":
            (-500, 1500),

        "username_size":
            (10, 500),

        "image_width":
            (400, 3000),

        "image_height":
            (200, 2000)
    }

    for key, (
        minimum,
        maximum
    ) in numeric_ranges.items():

        if key not in data:
            continue

        value = float(
            data[key]
        )

        value = max(
            minimum,
            min(
                value,
                maximum
            )
        )

        if key in (
            "image_width",
            "image_height"
        ):

            value = int(value)

        clean[key] = value

    if "avatar_shape" in data:

        shape = str(
            data["avatar_shape"]
        ).lower()

        if shape not in (
            "circle",
            "square",
            "rounded"
        ):

            shape = "circle"

        clean[
            "avatar_shape"
        ] = shape

    boolean_fields = [

        "show_avatar",
        "avatar_border_enabled",
        "show_username"
    ]

    for key in boolean_fields:

        if key in data:

            clean[key] = (
                1
                if bool(data[key])
                else 0
            )

    color_fields = [

        "username_color",
        "avatar_border_color"
    ]

    for key in color_fields:

        if key in data:

            clean[key] = safe_color(
                data[key]
            )

    if "message" in data:

        message = str(
            data["message"]
            or ""
        )

        if len(message) > 2000:

            message = message[:2000]

        clean["message"] = message

    return clean


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

        # -------------------------------------------------
        # HEALTH
        # -------------------------------------------------

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

        # -------------------------------------------------
        # WELCOME GET
        # -------------------------------------------------

        if path.startswith(
            "/api/welcome/"
        ):

            try:

                guild_id = int(
                    path.split(
                        "/"
                    )[-1]
                )

                row = get_welcome_settings(
                    guild_id
                )

                data = dict(
                    row
                )

                self.send_json(
                    200,
                    {
                        "success": True,
                        "settings": data
                    }
                )

            except Exception as e:

                self.send_json(
                    400,
                    {
                        "success": False,
                        "error": str(e)
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

        parsed = urlparse(
            self.path
        )

        path = parsed.path

        # -------------------------------------------------
        # SECRET
        # -------------------------------------------------

        if not PANEL_SECRET:

            self.send_json(
                503,
                {
                    "success": False,
                    "error":
                        "CT_PANEL_SECRET غير موجود"
                }
            )

            return

        received_secret = self.headers.get(
            "X-CT-PANEL-SECRET",
            ""
        )

        if received_secret != PANEL_SECRET:

            self.send_json(
                403,
                {
                    "success": False,
                    "error": "Unauthorized"
                }
            )

            return

        # -------------------------------------------------
        # WELCOME API
        # -------------------------------------------------

        if path.startswith(
            "/api/welcome/"
        ):

            try:

                guild_id = int(
                    path.split(
                        "/"
                    )[-1]
                )

                content_length = int(
                    self.headers.get(
                        "Content-Length",
                        "0"
                    )
                )

                if content_length > 100000:

                    self.send_json(
                        413,
                        {
                            "success": False,
                            "error":
                                "الطلب كبير جدًا"
                        }
                    )

                    return

                raw = self.rfile.read(
                    content_length
                )

                data = json.loads(
                    raw.decode(
                        "utf-8"
                    )
                )

                clean = validate_welcome_data(
                    data
                )

                save_welcome_settings(
                    guild_id,
                    clean
                )

                self.send_json(
                    200,
                    {
                        "success": True,
                        "message":
                            "تم حفظ إعدادات الترحيب"
                    }
                )

            except Exception as e:

                self.send_json(
                    400,
                    {
                        "success": False,
                        "error": str(e)
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
# IMAGE HELPERS
# =========================================================

def download_image(
    url: str
):

    try:

        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent":
                    "CTRP-Bot/1.0"
            }
        )

        response.raise_for_status()

        image = Image.open(
            io.BytesIO(
                response.content
            )
        )

        return image.convert(
            "RGBA"
        )

    except Exception as e:

        print(
            f"❌ Welcome Image Error: {e}"
        )

        return None


def get_font(
    size: int,
    bold: bool = False
):

    if bold:

        fonts = [

            "DejaVuSans-Bold.ttf",

            "/usr/share/fonts/"
            "truetype/dejavu/"
            "DejaVuSans-Bold.ttf"
        ]

    else:

        fonts = [

            "DejaVuSans.ttf",

            "/usr/share/fonts/"
            "truetype/dejavu/"
            "DejaVuSans.ttf"
        ]

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
        (
            size,
            size
        ),
        method=Image.Resampling.LANCZOS
    )

    mask = Image.new(
        "L",
        (
            size,
            size
        ),
        0
    )

    draw = ImageDraw.Draw(
        mask
    )

    draw.ellipse(
        (
            0,
            0,
            size - 1,
            size - 1
        ),
        fill=255
    )

    image.putalpha(
        mask
    )

    return image


def create_rounded_avatar(
    image: Image.Image,
    size: int
):

    image = ImageOps.fit(
        image.convert("RGBA"),
        (
            size,
            size
        ),
        method=Image.Resampling.LANCZOS
    )

    mask = Image.new(
        "L",
        (
            size,
            size
        ),
        0
    )

    draw = ImageDraw.Draw(
        mask
    )

    radius = max(
        10,
        int(size * 0.18)
    )

    draw.rounded_rectangle(
        (
            0,
            0,
            size - 1,
            size - 1
        ),
        radius=radius,
        fill=255
    )

    image.putalpha(
        mask
    )

    return image


def safe_color(
    value,
    fallback="#FFFFFF"
):

    if not value:
        return fallback

    try:

        value = str(
            value
        ).strip()

        if not value.startswith(
            "#"
        ):

            value = "#" + value

        if len(value) != 7:

            return fallback

        int(
            value[1:],
            16
        )

        return value

    except Exception:

        return fallback


# =========================================================
# APPLY OPACITY
# =========================================================

def apply_opacity(
    image: Image.Image,
    opacity: float
):

    opacity = max(
        0,
        min(
            float(opacity),
            100
        )
    )

    alpha = image.getchannel(
        "A"
    )

    alpha = alpha.point(
        lambda value:
            int(
                value *
                (
                    opacity /
                    100
                )
            )
    )

    image.putalpha(
        alpha
    )

    return image


# =========================================================
# CREATE BORDER
# =========================================================

def add_avatar_border(
    avatar: Image.Image,
    shape: str,
    width: int,
    color: str
):

    if width <= 0:

        return avatar

    width = min(
        width,
        100
    )

    original_size = avatar.width

    total_size = (
        original_size
        + width * 2
    )

    layer = Image.new(
        "RGBA",
        (
            total_size,
            total_size
        ),
        (
            0,
            0,
            0,
            0
        )
    )

    draw = ImageDraw.Draw(
        layer
    )

    color = safe_color(
        color,
        "#FFFFFF"
    )

    if shape == "circle":

        draw.ellipse(
            (
                0,
                0,
                total_size - 1,
                total_size - 1
            ),
            fill=color
        )

    elif shape == "rounded":

        radius = int(
            total_size * 0.18
        )

        draw.rounded_rectangle(
            (
                0,
                0,
                total_size - 1,
                total_size - 1
            ),
            radius=radius,
            fill=color
        )

    else:

        draw.rectangle(
            (
                0,
                0,
                total_size - 1,
                total_size - 1
            ),
            fill=color
        )

    layer.alpha_composite(
        avatar,
        (
            width,
            width
        )
    )

    return layer


# =========================================================
# BACKGROUND
# =========================================================

def prepare_background(
    background,
    width,
    height,
    settings
):

    if not background:

        return Image.new(
            "RGBA",
            (
                width,
                height
            ),
            (
                12,
                12,
                12,
                255
            )
        )

    scale = float(
        settings["background_scale"]
        or 100
    )

    scale = max(
        10,
        min(
            scale,
            500
        )
    )

    base_scale = max(
        width / background.width,
        height / background.height
    )

    final_scale = (
        base_scale
        * (
            scale /
            100
        )
    )

    new_width = max(
        1,
        int(
            background.width
            * final_scale
        )
    )

    new_height = max(
        1,
        int(
            background.height
            * final_scale
        )
    )

    background = background.resize(
        (
            new_width,
            new_height
        ),
        Image.Resampling.LANCZOS
    )

    canvas = Image.new(
        "RGBA",
        (
            width,
            height
        ),
        (
            12,
            12,
            12,
            255
        )
    )

    x_percent = float(
        settings["background_x"]
        or 50
    )

    y_percent = float(
        settings["background_y"]
        or 50
    )

    x = int(
        (
            width
            -
            new_width
        )
        *
        (
            x_percent /
            100
        )
    )

    y = int(
        (
            height
            -
            new_height
        )
        *
        (
            y_percent /
            100
        )
    )

    canvas.alpha_composite(
        background,
        (
            x,
            y
        )
    )

    return canvas


# =========================================================
# CREATE WELCOME IMAGE
# =========================================================

def make_welcome_image(
    member: discord.Member,
    settings
):

    width = int(
        settings["image_width"]
        or 1024
    )

    height = int(
        settings["image_height"]
        or 400
    )

    width = max(
        400,
        min(
            width,
            3000
        )
    )

    height = max(
        200,
        min(
            height,
            2000
        )
    )

    # =====================================================
    # BACKGROUND
    # =====================================================

    background = None

    background_url = (
        settings["background_url"]
    )

    if background_url:

        background = download_image(
            background_url
        )

    canvas = prepare_background(
        background,
        width,
        height,
        settings
    )

    draw = ImageDraw.Draw(
        canvas
    )

    # =====================================================
    # AVATAR
    # =====================================================

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
                    settings["avatar_size"]
                    or 180
                )

                avatar_size = max(
                    20,
                    min(
                        avatar_size,
                        1500
                    )
                )

                shape = (
                    settings["avatar_shape"]
                    or "circle"
                )

                if shape == "rounded":

                    avatar = (
                        create_rounded_avatar(
                            avatar,
                            avatar_size
                        )
                    )

                elif shape == "square":

                    avatar = ImageOps.fit(
                        avatar,
                        (
                            avatar_size,
                            avatar_size
                        ),
                        method=
                            Image.Resampling.LANCZOS
                    )

                else:

                    avatar = (
                        create_circle_avatar(
                            avatar,
                            avatar_size
                        )
                    )

                # -------------------------------------------------
                # BORDER
                # -------------------------------------------------

                if settings[
                    "avatar_border_enabled"
                ]:

                    avatar = (
                        add_avatar_border(
                            avatar,
                            shape,
                            int(
                                settings[
                                    "avatar_border_width"
                                ]
                                or 0
                            ),
                            settings[
                                "avatar_border_color"
                            ]
                        )
                    )

                # -------------------------------------------------
                # ROTATION
                # -------------------------------------------------

                rotation = float(
                    settings[
                        "avatar_rotation"
                    ]
                    or 0
                )

                if rotation:

                    avatar = avatar.rotate(
                        rotation,
                        expand=True,
                        resample=
                            Image.Resampling.BICUBIC
                    )

                # -------------------------------------------------
                # OPACITY
                # -------------------------------------------------

                avatar = apply_opacity(
                    avatar,
                    float(
                        settings[
                            "avatar_opacity"
                        ]
                        or 100
                    )
                )

                # -------------------------------------------------
                # POSITION
                # -------------------------------------------------

                avatar_x = float(
                    settings["avatar_x"]
                    if settings[
                        "avatar_x"
                    ] is not None
                    else 50
                )

                avatar_y = float(
                    settings["avatar_y"]
                    if settings[
                        "avatar_y"
                    ] is not None
                    else 50
                )

                x = int(
                    width
                    *
                    (
                        avatar_x /
                        100
                    )
                    -
                    avatar.width /
                    2
                )

                y = int(
                    height
                    *
                    (
                        avatar_y /
                        100
                    )
                    -
                    avatar.height /
                    2
                )

                canvas.alpha_composite(
                    avatar,
                    (
                        x,
                        y
                    )
                )

        except Exception as e:

            print(
                "❌ Avatar Render Error: "
                f"{e}"
            )

    # =====================================================
    # USERNAME
    # =====================================================

    if settings["show_username"]:

        try:

            username = (
                member.display_name
            )

            username_size = int(
                settings[
                    "username_size"
                ]
                or 48
            )

            username_size = max(
                12,
                min(
                    username_size,
                    500
                )
            )

            font = get_font(
                username_size,
                bold=True
            )

            username_color = safe_color(
                settings[
                    "username_color"
                ],
                "#FFFFFF"
            )

            bbox = draw.textbbox(
                (
                    0,
                    0
                ),
                username,
                font=font
            )

            text_width = (
                bbox[2]
                -
                bbox[0]
            )

            text_height = (
                bbox[3]
                -
                bbox[1]
            )

            username_x = float(
                settings[
                    "username_x"
                ]
                if settings[
                    "username_x"
                ] is not None
                else 50
            )

            username_y = float(
                settings[
                    "username_y"
                ]
                if settings[
                    "username_y"
                ] is not None
                else 78
            )

            x = int(
                width
                *
                (
                    username_x /
                    100
                )
                -
                text_width /
                2
            )

            y = int(
                height
                *
                (
                    username_y /
                    100
                )
                -
                text_height /
                2
            )

            # -------------------------------------------------
            # SHADOW
            # -------------------------------------------------

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

            # -------------------------------------------------
            # TEXT
            # -------------------------------------------------

            draw.text(
                (
                    x,
                    y
                ),
                username,
                font=font,
                fill=username_color
            )

        except Exception as e:

            print(
                "❌ Username Render Error: "
                f"{e}"
            )

    # =====================================================
    # MESSAGE
    # =====================================================

    message = (
        settings["message"]
        or
        "مرحباً {mention} في {server}"
    )

    replacements = {

        "{user}":
            member.display_name,

        "{username}":
            member.display_name,

        "{mention}":
            member.mention,

        "{server}":
            member.guild.name,

        "{count}":
            str(
                member.guild.member_count
            ),

        "{id}":
            str(
                member.id
            )
    }

    for key, value in replacements.items():

        message = message.replace(
            key,
            value
        )

    # =====================================================
    # EXPORT
    # =====================================================

    buffer = io.BytesIO()

    canvas.save(
        buffer,
        format="PNG",
        optimize=True
    )

    buffer.seek(0)

    return (
        buffer,
        message
    )


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

    # -----------------------------------------------------
    # WELCOME
    # -----------------------------------------------------

    try:

        welcome = (
            get_welcome_settings(
                member.guild.id
            )
        )

        if not welcome:

            print(
                f"⚠️ Welcome: "
                f"لا توجد إعدادات "
                f"[{member.guild.name}]"
            )

            return

        if not welcome["enabled"]:

            print(
                f"⚠️ Welcome: "
                f"النظام متوقف "
                f"[{member.guild.name}]"
            )

            return

        channel_id = (
            welcome["channel_id"]
        )

        if not channel_id:

            print(
                f"⚠️ Welcome: "
                f"لم يتم تحديد روم "
                f"[{member.guild.name}]"
            )

            return

        channel = (
            member.guild.get_channel(
                int(channel_id)
            )
        )

        if not channel:

            try:

                channel = (
                    await bot.fetch_channel(
                        int(channel_id)
                    )
                )

            except Exception as e:

                print(
                    f"❌ Welcome Channel Error "
                    f"[{member.guild.name}]: {e}"
                )

                return

        if not isinstance(
            channel,
            discord.TextChannel
        ):

            print(
                f"❌ Welcome: "
                f"الروم المحدد ليس Text Channel "
                f"[{member.guild.name}]"
            )

            return

        me = member.guild.me

        if not me:

            print(
                f"❌ Welcome: "
                f"لم يتم العثور على البوت "
                f"[{member.guild.name}]"
            )

            return

        permissions = (
            channel.permissions_for(
                me
            )
        )

        if not permissions.send_messages:

            print(
                f"❌ Welcome: "
                f"البوت لا يستطيع إرسال رسائل "
                f"#{channel.name}"
            )

            return

        if not permissions.attach_files:

            print(
                f"❌ Welcome: "
                f"البوت لا يستطيع رفع الملفات "
                f"#{channel.name}"
            )

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
            file=file,
            allowed_mentions=discord.AllowedMentions(
                users=True,
                roles=False,
                everyone=False
            )
        )

        print(
            f"👋 Welcome sent: "
            f"{member} -> "
            f"{member.guild.name} -> "
            f"#{channel.name}"
        )

    except Exception as e:

        print(
            f"❌ Welcome Error "
            f"[{member.guild.name}]: {e}"
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
# WELCOME CHANNEL SELECT
# =========================================================

class WelcomeChannelSelect(
    discord.ui.ChannelSelect
):

    def __init__(self):

        super().__init__(
            placeholder=
                "اختر روم الترحيب",

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
# WELCOME CHANNEL
# =========================================================

@bot.tree.command(
    name="تحديد_روم_الترحيب",
    description=
        "تحديد الروم الذي ترسل فيه الترحيبات"
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


# =========================================================
# WELCOME TOGGLE
# =========================================================

@bot.tree.command(
    name="الترحيب",
    description=
        "تشغيل أو إيقاف نظام الترحيب"
)
@app_commands.describe(
    الحالة=
        "تشغيل أو إيقاف الترحيب"
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
    الحالة:
        app_commands.Choice[str]
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


# =========================================================
# WELCOME SETTINGS
# =========================================================

@bot.tree.command(
    name="اعدادات_الترحيب",
    description=
        "عرض إعدادات الترحيب الحالية"
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
                int(
                    row["channel_id"]
                )
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

    embed.add_field(
        name="حجم الصورة",
        value=(
            f"`{row['avatar_size']}`"
        ),
        inline=True
    )

    embed.add_field(
        name="شكل الصورة",
        value=(
            f"`{row['avatar_shape']}`"
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
        "👋 Welcome System Ready"
    )

    print(
        "🌐 Welcome API Ready"
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
