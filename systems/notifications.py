# =========================================================
# CTRP SYSTEM
# systems/notifications.py
# NOTIFICATIONS SYSTEM
# =========================================================

import discord
from discord import app_commands
from discord.ext import commands, tasks

import sqlite3


# =========================================================
# DATABASE
# =========================================================

DB_FILE = "ctrp_system.db"


def get_db():

    con = sqlite3.connect(
        DB_FILE,
        timeout=30
    )

    con.row_factory = sqlite3.Row

    return con


# =========================================================
# DATABASE SETUP
# =========================================================

def setup_welcome_database():

    con = get_db()

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS welcome_settings
        (
            guild_id INTEGER PRIMARY KEY,

            enabled INTEGER NOT NULL DEFAULT 1,

            channel_id INTEGER,

            message TEXT NOT NULL
                DEFAULT 'Welcome To {server} {mention}\nInvited By {inviter}',

            image_url TEXT,

            footer TEXT DEFAULT '',

            color INTEGER NOT NULL DEFAULT 0x8B0000
        )
        """
    )

    # =====================================================
    # MIGRATION
    # =====================================================

    columns = con.execute(
        """
        PRAGMA table_info(welcome_settings)
        """
    ).fetchall()

    column_names = [
        column["name"]
        for column in columns
    ]

    if "image_url" not in column_names:

        con.execute(
            """
            ALTER TABLE welcome_settings
            ADD COLUMN image_url TEXT
            """
        )

    if "footer" not in column_names:

        con.execute(
            """
            ALTER TABLE welcome_settings
            ADD COLUMN footer TEXT DEFAULT ''
            """
        )

    if "color" not in column_names:

        con.execute(
            """
            ALTER TABLE welcome_settings
            ADD COLUMN color INTEGER NOT NULL DEFAULT 0x8B0000
            """
        )

    con.commit()
    con.close()


def setup_stream_database():

    con = get_db()

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS streamers
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            guild_id INTEGER NOT NULL,

            platform TEXT NOT NULL,

            username TEXT NOT NULL,

            channel_id INTEGER NOT NULL,

            message TEXT DEFAULT
                '{user} نشر محتوى جديد!\n{title}\n{url}',

            UNIQUE(
                guild_id,
                platform,
                username
            )
        )
        """
    )

    con.commit()
    con.close()


# =========================================================
# WELCOME VARIABLES
# =========================================================

WELCOME_VARIABLES = {

    "{mention}":
        "منشن العضو",

    "{user}":
        "اسم العضو",

    "{username}":
        "اسم المستخدم",

    "{display_name}":
        "الاسم الظاهر",

    "{server}":
        "اسم السيرفر",

    "{member_count}":
        "عدد أعضاء السيرفر",

    "{count}":
        "عدد أعضاء السيرفر",

    "{id}":
        "آيدي العضو",

    "{inviter}":
        "منشن الشخص الذي دعا العضو",

    "{inviter_name}":
        "اسم الشخص الذي دعا العضو",

    "{inviter_id}":
        "آيدي الشخص الذي دعا العضو",

    "{invites}":
        "عدد دعوات الشخص الذي دعا العضو"
}


# =========================================================
# HELPERS
# =========================================================

def get_welcome_settings(
    guild_id
):

    con = get_db()

    row = con.execute(
        """
        SELECT
            guild_id,
            enabled,
            channel_id,
            message,
            image_url,
            footer,
            color

        FROM welcome_settings

        WHERE guild_id = ?
        """,
        (
            guild_id,
        )
    ).fetchone()

    con.close()

    if not row:

        return None

    return {

        "guild_id":
            row["guild_id"],

        "enabled":
            bool(
                row["enabled"]
            ),

        "channel_id":
            row["channel_id"],

        "message":
            row["message"],

        "image_url":
            row["image_url"],

        "footer":
            row["footer"],

        "color":
            row["color"]
    }


# =========================================================
# GET INVITER
# =========================================================

async def get_inviter(
    member
):

    try:

        guild = member.guild

        invites = await guild.invites()

        # -------------------------------------------------
        # هذا يعتمد على كاش الدعوات الموجود عند Discord
        # -------------------------------------------------

        for invite in invites:

            if invite.uses is not None:

                continue

        return None

    except Exception:

        return None


# =========================================================
# REPLACE VARIABLES
# =========================================================

async def replace_welcome_variables(
    message,
    member
):

    guild = member.guild

    inviter = await get_inviter(
        member
    )

    if inviter:

        inviter_mention = (
            inviter.mention
        )

        inviter_name = (
            inviter.name
        )

        inviter_id = (
            str(inviter.id)
        )

        try:

            inviter_invites = (
                str(inviter.public_flags)
            )

        except Exception:

            inviter_invites = "0"

    else:

        inviter_mention = "غير معروف"

        inviter_name = "غير معروف"

        inviter_id = "غير معروف"

        inviter_invites = "0"

    replacements = {

        "{mention}":
            member.mention,

        "{user}":
            member.name,

        "{username}":
            member.name,

        "{display_name}":
            member.display_name,

        "{server}":
            "Crystal Town",

        "{member_count}":
            str(
                guild.member_count
                or 0
            ),

        "{count}":
            str(
                guild.member_count
                or 0
            ),

        "{id}":
            str(
                member.id
            ),

        "{inviter}":
            inviter_mention,

        "{inviter_name}":
            inviter_name,

        "{inviter_id}":
            inviter_id,

        "{invites}":
            inviter_invites
    }

    for key, value in replacements.items():

        message = message.replace(
            key,
            value
        )

    return message


# =========================================================
# NOTIFICATIONS
# =========================================================

class Notifications(
    commands.Cog
):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        setup_welcome_database()

        setup_stream_database()

        self.check_streams.start()


    # =====================================================
    # UNLOAD
    # =====================================================

    def cog_unload(
        self
    ):

        self.check_streams.cancel()


    # =====================================================
    # MEMBER JOIN
    # =====================================================

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member
    ):

        try:

            settings = get_welcome_settings(
                member.guild.id
            )

            if not settings:

                return

            if not settings["enabled"]:

                return

            if not settings["channel_id"]:

                return

            channel = (
                member.guild.get_channel(
                    settings["channel_id"]
                )
            )

            if channel is None:

                try:

                    channel = (
                        await self.bot.fetch_channel(
                            settings["channel_id"]
                        )
                    )

                except Exception as e:

                    print(
                        "❌ Welcome Channel Error: "
                        f"{e}"
                    )

                    return

            if not isinstance(
                channel,
                discord.TextChannel
            ):

                return

            # =============================================
            # MESSAGE
            # =============================================

            message = await replace_welcome_variables(
                settings["message"],
                member
            )

            # =============================================
            # SEND NORMAL MESSAGE
            # NO EMBED
            # =============================================

            await channel.send(

                message,

                allowed_mentions=
                    discord.AllowedMentions(
                        users=True,
                        roles=False,
                        everyone=False
                    )
            )

        except discord.Forbidden:

            print(
                "❌ Welcome Error: "
                "البوت لا يملك صلاحية الإرسال في روم الترحيب."
            )

        except Exception as e:

            print(
                f"❌ Welcome Error: {e}"
            )


    # =====================================================
    # STREAM NOTIFICATIONS
    # =====================================================

    @tasks.loop(
        minutes=2
    )
    async def check_streams(
        self
    ):

        try:

            con = get_db()

            rows = con.execute(
                """
                SELECT
                    id,
                    guild_id,
                    platform,
                    username,
                    channel_id,
                    message

                FROM streamers
                """
            ).fetchall()

            con.close()

            for row in rows:

                continue

        except Exception as e:

            print(
                "❌ Stream Notification Error: "
                f"{e}"
            )


    @check_streams.before_loop
    async def before_check(
        self
    ):

        await self.bot.wait_until_ready()


    # =====================================================
    # WELCOME SETUP
    # =====================================================

    @app_commands.command(
        name="welcome_setup",
        description="إعداد نظام الترحيب"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    @app_commands.describe(

        channel="روم الترحيب",

        message="رسالة الترحيب ويمكنك استخدام المتغيرات",

        image="متغير قديم - غير مستخدم",

        footer="متغير قديم - غير مستخدم"
    )
    async def welcome_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str =
            "Welcome To {server} {mention}\nInvited By {inviter}",
        image: str = None,
        footer: str = ""
    ):

        con = get_db()

        con.execute(
            """
            INSERT INTO welcome_settings
            (
                guild_id,
                enabled,
                channel_id,
                message,
                image_url,
                footer,
                color
            )

            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )

            ON CONFLICT(guild_id)

            DO UPDATE SET

                enabled =
                    excluded.enabled,

                channel_id =
                    excluded.channel_id,

                message =
                    excluded.message
            """,
            (
                interaction.guild.id,

                1,

                channel.id,

                message,

                image,

                footer,

                0x8B0000
            )
        )

        con.commit()
        con.close()

        await interaction.response.send_message(

            (
                "✅ تم إعداد نظام الترحيب.\n\n"
                f"📢 **الروم:** {channel.mention}\n"
                f"🟢 **الحالة:** مفعّل\n\n"
                f"**الرسالة:**\n{message}"
            ),

            ephemeral=True
        )


    # =====================================================
    # WELCOME ON
    # =====================================================

    @app_commands.command(
        name="welcome_on",
        description="تشغيل نظام الترحيب"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def welcome_on(
        self,
        interaction: discord.Interaction
    ):

        con = get_db()

        row = con.execute(
            """
            SELECT guild_id

            FROM welcome_settings

            WHERE guild_id = ?
            """,
            (
                interaction.guild.id,
            )
        ).fetchone()

        if not row:

            con.execute(
                """
                INSERT INTO welcome_settings
                (
                    guild_id,
                    enabled,
                    message
                )

                VALUES
                (
                    ?,
                    1,
                    ?
                )
                """,
                (
                    interaction.guild.id,

                    "Welcome To {server} {mention}\nInvited By {inviter}"
                )
            )

        else:

            con.execute(
                """
                UPDATE welcome_settings

                SET enabled = 1

                WHERE guild_id = ?
                """,
                (
                    interaction.guild.id,
                )
            )

        con.commit()
        con.close()

        await interaction.response.send_message(
            "🟢 تم تشغيل نظام الترحيب.",
            ephemeral=True
        )


    # =====================================================
    # WELCOME OFF
    # =====================================================

    @app_commands.command(
        name="welcome_off",
        description="إيقاف نظام الترحيب"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def welcome_off(
        self,
        interaction: discord.Interaction
    ):

        con = get_db()

        con.execute(
            """
            UPDATE welcome_settings

            SET enabled = 0

            WHERE guild_id = ?
            """,
            (
                interaction.guild.id,
            )
        )

        con.commit()
        con.close()

        await interaction.response.send_message(
            "🔴 تم إيقاف نظام الترحيب.",
            ephemeral=True
        )


    # =====================================================
    # WELCOME RESET
    # =====================================================

    @app_commands.command(
        name="welcome_reset",
        description="حذف إعدادات الترحيب"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def welcome_reset(
        self,
        interaction: discord.Interaction
    ):

        con = get_db()

        con.execute(
            """
            DELETE FROM welcome_settings

            WHERE guild_id = ?
            """,
            (
                interaction.guild.id,
            )
        )

        con.commit()
        con.close()

        await interaction.response.send_message(
            "🗑️ تم حذف إعدادات الترحيب.",
            ephemeral=True
        )


    # =====================================================
    # WELCOME TEST
    # =====================================================

    @app_commands.command(
        name="welcome_test",
        description="تجربة رسالة الترحيب"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def welcome_test(
        self,
        interaction: discord.Interaction
    ):

        settings = get_welcome_settings(
            interaction.guild.id
        )

        if not settings:

            return await interaction.response.send_message(
                "❌ لم يتم إعداد نظام الترحيب.",
                ephemeral=True
            )

        if not settings["channel_id"]:

            return await interaction.response.send_message(
                "❌ لم يتم تحديد روم الترحيب.",
                ephemeral=True
            )

        channel = (
            interaction.guild.get_channel(
                settings["channel_id"]
            )
        )

        if channel is None:

            try:

                channel = (
                    await self.bot.fetch_channel(
                        settings["channel_id"]
                    )
                )

            except Exception:

                return await interaction.response.send_message(
                    "❌ روم الترحيب غير موجود.",
                    ephemeral=True
                )

        if not isinstance(
            channel,
            discord.TextChannel
        ):

            return await interaction.response.send_message(
                "❌ الروم المحدد ليس رومًا نصيًا.",
                ephemeral=True
            )

        message = await replace_welcome_variables(
            settings["message"],
            interaction.user
        )

        try:

            await channel.send(

                message,

                allowed_mentions=
                    discord.AllowedMentions(
                        users=True,
                        roles=False,
                        everyone=False
                    )
            )

            await interaction.response.send_message(

                (
                    "✅ تم إرسال تجربة "
                    f"الترحيب في "
                    f"{channel.mention}."
                ),

                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.response.send_message(

                "❌ البوت لا يملك صلاحية إرسال الرسائل في الروم.",

                ephemeral=True
            )

        except Exception as e:

            print(
                f"❌ Welcome Test Error: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(

                    "❌ حدث خطأ أثناء إرسال تجربة الترحيب.",

                    ephemeral=True
                )


    # =====================================================
    # STREAM ADD
    # =====================================================

    @app_commands.command(
        name="notification_add",
        description="إضافة حساب للإشعارات"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def notification_add(
        self,
        interaction: discord.Interaction,
        platform: str,
        username: str,
        channel: discord.TextChannel
    ):

        platform = platform.lower().strip()

        if platform not in [
            "twitch",
            "kick",
            "youtube",
            "tiktok"
        ]:

            return await interaction.response.send_message(

                (
                    "❌ المنصات المتاحة:\n"
                    "Twitch / Kick / YouTube / TikTok"
                ),

                ephemeral=True
            )

        con = get_db()

        con.execute(
            """
            INSERT OR IGNORE INTO streamers
            (
                guild_id,
                platform,
                username,
                channel_id,
                message
            )

            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                interaction.guild.id,

                platform,

                username,

                channel.id,

                "{user} نشر محتوى جديد!\n{title}\n{url}"
            )
        )

        con.commit()
        con.close()

        await interaction.response.send_message(

            (
                f"✅ تمت إضافة **{username}** "
                f"من **{platform}** للإشعارات.\n"
                f"📢 الروم: {channel.mention}"
            ),

            ephemeral=True
        )


    # =====================================================
    # STREAM REMOVE
    # =====================================================

    @app_commands.command(
        name="notification_remove",
        description="حذف حساب من الإشعارات"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def notification_remove(
        self,
        interaction: discord.Interaction,
        platform: str,
        username: str
    ):

        platform = (
            platform
            .lower()
            .strip()
        )

        con = get_db()

        cursor = con.execute(
            """
            DELETE FROM streamers

            WHERE guild_id = ?

            AND platform = ?

            AND username = ?
            """,
            (
                interaction.guild.id,

                platform,

                username
            )
        )

        deleted = cursor.rowcount

        con.commit()
        con.close()

        if deleted:

            text = (
                f"🗑️ تم حذف "
                f"**{username}** "
                f"من الإشعارات."
            )

        else:

            text = (
                "❌ لم يتم العثور على "
                "هذا الحساب."
            )

        await interaction.response.send_message(

            text,

            ephemeral=True
        )


# =========================================================
# SETUP
# =========================================================

async def setup(
    bot
):

    await bot.add_cog(
        Notifications(bot)
    )
