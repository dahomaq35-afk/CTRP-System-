import os
import re
import sqlite3
from urllib.parse import urlparse

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks


DB_FILE = "ctrp_system.db"
CHECK_INTERVAL = 10


# =========================================================
# DATABASE
# =========================================================

def get_db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


def init_stream_db():
    con = get_db()

    con.execute("""
        CREATE TABLE IF NOT EXISTS stream_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            username TEXT NOT NULL,
            channel_id INTEGER NOT NULL,

            live_message TEXT,
            video_message TEXT,

            last_live_id TEXT,
            last_video_id TEXT,

            enabled INTEGER DEFAULT 1,

            UNIQUE(guild_id, platform, username, channel_id)
        )
    """)

    con.commit()
    con.close()


# =========================================================
# HELPERS
# =========================================================

def clean_account(value: str):
    value = value.strip()

    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]

    value = value.rstrip("/")

    # Twitch
    if "twitch.tv/" in value.lower():
        value = value.split("twitch.tv/", 1)[1]

    # Kick
    elif "kick.com/" in value.lower():
        value = value.split("kick.com/", 1)[1]

    # YouTube
    elif "youtube.com/" in value.lower():
        value = value.split("youtube.com/", 1)[1]

        if value.startswith("@"):
            value = value[1:]

        if value.startswith("channel/"):
            value = value.split("channel/", 1)[1]

    # TikTok
    elif "tiktok.com/" in value.lower():
        value = value.split("tiktok.com/", 1)[1]

        if value.startswith("@"):
            value = value[1:]

    value = value.split("?")[0]
    value = value.split("/")[0]

    if value.startswith("@"):
        value = value[1:]

    return value.strip()


def platform_name(platform):
    names = {
        "twitch": "🟣 Twitch",
        "kick": "🟢 Kick",
        "youtube": "🔴 YouTube",
        "tiktok": "⚫ TikTok"
    }

    return names.get(platform, platform)


# =========================================================
# STREAM ALERTS
# =========================================================

class StreamAlerts(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        init_stream_db()

        self.session = None

        self.check_streams.start()

    async def cog_load(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    def cog_unload(self):
        self.check_streams.cancel()

        if self.session and not self.session.closed:
            self.bot.loop.create_task(
                self.session.close()
            )

    # =====================================================
    # SESSION
    # =====================================================

    async def get_session(self):

        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

        return self.session

    # =====================================================
    # GET ALERTS
    # =====================================================

    def get_alerts(self):

        con = get_db()

        rows = con.execute("""
            SELECT *
            FROM stream_alerts
            WHERE enabled = 1
        """).fetchall()

        con.close()

        return rows

    # =====================================================
    # UPDATE LAST ID
    # =====================================================

    def update_last_live(self, alert_id, live_id):

        con = get_db()

        con.execute("""
            UPDATE stream_alerts
            SET last_live_id = ?
            WHERE id = ?
        """, (
            live_id,
            alert_id
        ))

        con.commit()
        con.close()

    def update_last_video(self, alert_id, video_id):

        con = get_db()

        con.execute("""
            UPDATE stream_alerts
            SET last_video_id = ?
            WHERE id = ?
        """, (
            video_id,
            alert_id
        ))

        con.commit()
        con.close()

    # =====================================================
    # TWITCH
    # =====================================================

    async def check_twitch(self, row):

        client_id = os.getenv("TWITCH_CLIENT_ID")
        access_token = os.getenv("TWITCH_ACCESS_TOKEN")

        if not client_id or not access_token:
            return None

        session = await self.get_session()

        headers = {
            "Client-Id": client_id,
            "Authorization": f"Bearer {access_token}"
        }

        url = "https://api.twitch.tv/helix/streams"

        params = {
            "user_login": row["username"]
        }

        try:

            async with session.get(
                url,
                headers=headers,
                params=params,
                timeout=8
            ) as response:

                if response.status != 200:
                    return None

                data = await response.json()

                streams = data.get("data", [])

                if not streams:
                    return None

                stream = streams[0]

                return {
                    "type": "live",
                    "id": stream["id"],
                    "url": f"https://twitch.tv/{row['username']}",
                    "title": stream.get("title", ""),
                    "game": stream.get("game_name", ""),
                    "viewers": stream.get("viewer_count", 0)
                }

        except Exception as e:

            print(
                f"[Twitch] Error {row['username']}: {e}"
            )

            return None

    # =====================================================
    # KICK
    # =====================================================

    async def check_kick(self, row):

        session = await self.get_session()

        username = row["username"]

        url = f"https://kick.com/api/v2/channels/{username}"

        try:

            async with session.get(
                url,
                timeout=8,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            ) as response:

                if response.status != 200:
                    return None

                data = await response.json()

                livestream = data.get("livestream")

                if not livestream:
                    return None

                live_id = str(
                    livestream.get("slug")
                    or livestream.get("id")
                    or livestream.get("session_title")
                )

                return {
                    "type": "live",
                    "id": live_id,
                    "url": f"https://kick.com/{username}",
                    "title": livestream.get(
                        "session_title",
                        ""
                    ),
                    "game": (
                        livestream.get("categories", [{}])[0]
                        .get("name", "")
                        if livestream.get("categories")
                        else ""
                    ),
                    "viewers": livestream.get(
                        "viewer_count",
                        0
                    )
                }

        except Exception as e:

            print(
                f"[Kick] Error {username}: {e}"
            )

            return None

    # =====================================================
    # YOUTUBE
    # =====================================================

    async def check_youtube(self, row):

        api_key = os.getenv("YOUTUBE_API_KEY")

        if not api_key:
            return None

        session = await self.get_session()

        username = row["username"]

        # ---------------------------------------------
        # تحديد Channel ID
        # ---------------------------------------------

        channel_id = None

        if username.startswith("UC"):
            channel_id = username

        else:

            search_url = (
                "https://www.googleapis.com/youtube/v3/search"
            )

            params = {
                "part": "snippet",
                "q": username,
                "type": "channel",
                "maxResults": 1,
                "key": api_key
            }

            try:

                async with session.get(
                    search_url,
                    params=params,
                    timeout=8
                ) as response:

                    if response.status != 200:
                        return None

                    data = await response.json()

                    items = data.get("items", [])

                    if not items:
                        return None

                    channel_id = items[0]["snippet"]["channelId"]

            except Exception as e:

                print(
                    f"[YouTube] Search Error {username}: {e}"
                )

                return None

        # ---------------------------------------------
        # فحص LIVE
        # ---------------------------------------------

        live_url = (
            "https://www.googleapis.com/youtube/v3/search"
        )

        live_params = {
            "part": "snippet",
            "channelId": channel_id,
            "eventType": "live",
            "type": "video",
            "maxResults": 1,
            "key": api_key
        }

        try:

            async with session.get(
                live_url,
                params=live_params,
                timeout=8
            ) as response:

                if response.status != 200:
                    return None

                data = await response.json()

                items = data.get("items", [])

                if items:

                    video = items[0]

                    return {
                        "type": "live",
                        "id": video["id"]["videoId"],
                        "url": (
                            "https://youtube.com/watch?v="
                            + video["id"]["videoId"]
                        ),
                        "title": video["snippet"]["title"],
                        "channel": video["snippet"].get(
                            "channelTitle",
                            ""
                        )
                    }

        except Exception as e:

            print(
                f"[YouTube LIVE] Error {username}: {e}"
            )

        # ---------------------------------------------
        # آخر فيديو
        # ---------------------------------------------

        video_params = {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "order": "date",
            "maxResults": 1,
            "key": api_key
        }

        try:

            async with session.get(
                live_url,
                params=video_params,
                timeout=8
            ) as response:

                if response.status != 200:
                    return None

                data = await response.json()

                items = data.get("items", [])

                if not items:
                    return None

                video = items[0]

                video_id = video["id"]["videoId"]

                return {
                    "type": "video",
                    "id": video_id,
                    "url": (
                        "https://youtube.com/watch?v="
                        + video_id
                    ),
                    "title": video["snippet"]["title"],
                    "channel": video["snippet"].get(
                        "channelTitle",
                        ""
                    )
                }

        except Exception as e:

            print(
                f"[YouTube VIDEO] Error {username}: {e}"
            )

            return None

    # =====================================================
    # TIKTOK
    # =====================================================

    async def check_tiktok(self, row):

        session = await self.get_session()

        username = row["username"]

        # ملاحظة:
        # TikTok لا يوفر API عامًا بسيطًا لفحص LIVE
        # لذلك هذا الجزء يستخدم صفحة الحساب العامة
        # كفحص مساعد وليس API رسميًا.

        url = f"https://www.tiktok.com/@{username}"

        try:

            async with session.get(
                url,
                timeout=8,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            ) as response:

                if response.status != 200:
                    return None

                html = await response.text()

                # محاولة معرفة LIVE
                live_match = re.search(
                    r'"liveRoomId":"([^"]+)"',
                    html
                )

                if live_match:

                    live_id = live_match.group(1)

                    return {
                        "type": "live",
                        "id": live_id,
                        "url": url,
                        "title": f"بث {username}"
                    }

                return None

        except Exception as e:

            print(
                f"[TikTok] Error {username}: {e}"
            )

            return None

    # =====================================================
    # CHECK ONE ALERT
    # =====================================================

    async def check_alert(self, row):

        platform = row["platform"]

        if platform == "twitch":
            result = await self.check_twitch(row)

        elif platform == "kick":
            result = await self.check_kick(row)

        elif platform == "youtube":
            result = await self.check_youtube(row)

        elif platform == "tiktok":
            result = await self.check_tiktok(row)

        else:
            return

        if not result:
            return

        alert_id = row["id"]

        # =================================================
        # LIVE
        # =================================================

        if result["type"] == "live":

            if result["id"] == row["last_live_id"]:
                return

            message = row["live_message"]

            if not message:
                message = (
                    "🔴 **LIVE الآن!**\n"
                    "{url}"
                )

            message = message.replace(
                "{url}",
                result["url"]
            )

            message = message.replace(
                "{user}",
                row["username"]
            )

            message = message.replace(
                "{title}",
                result.get("title", "")
            )

            channel = self.bot.get_channel(
                row["channel_id"]
            )

            if not channel:
                return

            try:

                await channel.send(message)

                self.update_last_live(
                    alert_id,
                    result["id"]
                )

            except Exception as e:

                print(
                    f"[Alert] Send Error: {e}"
                )

        # =================================================
        # VIDEO
        # =================================================

        elif result["type"] == "video":

            if result["id"] == row["last_video_id"]:
                return

            message = row["video_message"]

            if not message:
                message = (
                    "🎬 **مقطع جديد!**\n"
                    "{url}"
                )

            message = message.replace(
                "{url}",
                result["url"]
            )

            message = message.replace(
                "{user}",
                row["username"]
            )

            message = message.replace(
                "{title}",
                result.get("title", "")
            )

            channel = self.bot.get_channel(
                row["channel_id"]
            )

            if not channel:
                return

            try:

                await channel.send(message)

                self.update_last_video(
                    alert_id,
                    result["id"]
                )

            except Exception as e:

                print(
                    f"[Alert] Send Error: {e}"
                )

    # =====================================================
    # LOOP
    # =====================================================

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def check_streams(self):

        alerts = self.get_alerts()

        for row in alerts:

            try:

                await self.check_alert(row)

            except Exception as e:

                print(
                    f"[Stream Alert] {row['platform']} "
                    f"{row['username']}: {e}"
                )

    @check_streams.before_loop
    async def before_check_streams(self):

        await self.bot.wait_until_ready()

        await self.get_session()

    # =====================================================
    # /STREAMADD
    # =====================================================

    @app_commands.command(
        name="streamadd",
        description="إضافة تنبيه بث لمنصة"
    )
    @app_commands.choices(
        platform=[
            app_commands.Choice(
                name="Twitch",
                value="twitch"
            ),
            app_commands.Choice(
                name="Kick",
                value="kick"
            ),
            app_commands.Choice(
                name="YouTube",
                value="youtube"
            ),
            app_commands.Choice(
                name="TikTok",
                value="tiktok"
            )
        ]
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def streamadd(
        self,
        interaction: discord.Interaction,
        platform: app_commands.Choice[str],
        account: str,
        channel: discord.TextChannel,
        live_message: str,
        video_message: str = None
    ):

        platform_value = platform.value

        account = clean_account(account)

        if not account:
            return await interaction.response.send_message(
                "❌ رابط أو اسم الحساب غير صحيح.",
                ephemeral=True
            )

        if platform_value in ("twitch", "kick"):

            if video_message:
                video_message = None

        con = get_db()

        try:

            con.execute("""
                INSERT INTO stream_alerts
                (
                    guild_id,
                    platform,
                    username,
                    channel_id,
                    live_message,
                    video_message
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                interaction.guild.id,
                platform_value,
                account,
                channel.id,
                live_message,
                video_message
            ))

            con.commit()

        except sqlite3.IntegrityError:

            con.close()

            return await interaction.response.send_message(
                "❌ هذا الحساب مضاف مسبقًا في نفس الروم.",
                ephemeral=True
            )

        con.close()

        await interaction.response.send_message(
            "✅ تم إضافة تنبيه المنصة بنجاح.\n\n"
            f"**المنصة:** {platform_name(platform_value)}\n"
            f"**الحساب:** `{account}`\n"
            f"**الروم:** {channel.mention}\n"
            "⏱️ الفحص كل **10 ثوانٍ**."
        )

    # =====================================================
    # /STREAMREMOVE
    # =====================================================

    @app_commands.command(
        name="streamremove",
        description="حذف تنبيه منصة"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def streamremove(
        self,
        interaction: discord.Interaction,
        platform: str,
        account: str
    ):

        account = clean_account(account)

        con = get_db()

        cursor = con.execute("""
            DELETE FROM stream_alerts
            WHERE guild_id = ?
            AND platform = ?
            AND username = ?
        """, (
            interaction.guild.id,
            platform.lower(),
            account
        ))

        deleted = cursor.rowcount

        con.commit()
        con.close()

        if deleted == 0:

            return await interaction.response.send_message(
                "❌ ما لقيت هذا الحساب في التنبيهات.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"✅ تم حذف تنبيه `{account}`."
        )

    # =====================================================
    # /STREAMLIST
    # =====================================================

    @app_commands.command(
        name="streamlist",
        description="عرض تنبيهات المنصات"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def streamlist(
        self,
        interaction: discord.Interaction
    ):

        con = get_db()

        rows = con.execute("""
            SELECT *
            FROM stream_alerts
            WHERE guild_id = ?
            ORDER BY id ASC
        """, (
            interaction.guild.id,
        )).fetchall()

        con.close()

        if not rows:

            return await interaction.response.send_message(
                "📭 لا توجد حسابات مضافة."
            )

        lines = []

        for index, row in enumerate(rows, start=1):

            channel = self.bot.get_channel(
                row["channel_id"]
            )

            channel_text = (
                channel.mention
                if channel
                else f"`{row['channel_id']}`"
            )

            lines.append(
                f"**{index}.** "
                f"{platform_name(row['platform'])} "
                f"`{row['username']}` → "
                f"{channel_text}"
            )

        embed = discord.Embed(
            title="📡 تنبيهات المنصات",
            description="\n".join(lines),
            color=discord.Color.blue()
        )

        await interaction.response.send_message(
            embed=embed
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        StreamAlerts(bot)
    )
