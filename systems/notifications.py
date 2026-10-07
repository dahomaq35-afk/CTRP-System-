import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3


DB_FILE = "ctrp_system.db"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    return sqlite3.connect(DB_FILE)


def setup_welcome_database():
    con = get_db()

    con.execute("""
        CREATE TABLE IF NOT EXISTS welcome_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            channel_id INTEGER,
            message TEXT NOT NULL DEFAULT '{mention} نورت السيرفر! 🎉',
            image_url TEXT,
            footer TEXT DEFAULT 'أهلاً وسهلاً بك في {server}',
            color INTEGER NOT NULL DEFAULT 0x8B0000
        )
    """)

    con.commit()
    con.close()


# =========================================================
# HELPERS
# =========================================================

def get_welcome_settings(guild_id):
    con = get_db()

    row = con.execute("""
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
    """, (guild_id,)).fetchone()

    con.close()

    if not row:
        return None

    return {
        "guild_id": row[0],
        "enabled": bool(row[1]),
        "channel_id": row[2],
        "message": row[3],
        "image_url": row[4],
        "footer": row[5],
        "color": row[6]
    }


def replace_welcome_variables(message, member):
    guild = member.guild

    replacements = {
        "{mention}": member.mention,
        "{user}": member.name,
        "{username}": member.name,
        "{display_name}": member.display_name,
        "{server}": guild.name,
        "{member_count}": str(guild.member_count or 0),
        "{id}": str(member.id),
    }

    for key, value in replacements.items():
        message = message.replace(key, value)

    return message


# =========================================================
# NOTIFICATIONS
# =========================================================

class Notifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        setup_welcome_database()

        self.check_streams.start()

    def cog_unload(self):
        self.check_streams.cancel()

    # =====================================================
    # STREAM NOTIFICATIONS
    # =====================================================

    @tasks.loop(minutes=2)
    async def check_streams(self):
        # مكان ربط Twitch / Kick / YouTube / TikTok APIs
        # سيتم فحص الحسابات المحفوظة وإرسال إشعار عند وجود بث أو محتوى جديد.
        pass

    @check_streams.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # =====================================================
    # WELCOME EVENT
    # =====================================================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        settings = get_welcome_settings(member.guild.id)

        if not settings:
            return

        if not settings["enabled"]:
            return

        channel_id = settings["channel_id"]

        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)

        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                return

        if not isinstance(channel, discord.TextChannel):
            return

        # -------------------------------------------------
        # TEXT
        # -------------------------------------------------

        message = replace_welcome_variables(
            settings["message"],
            member
        )

        # -------------------------------------------------
        # EMBED
        # -------------------------------------------------

        embed = discord.Embed(
            description=message,
            color=settings["color"]
        )

        # -------------------------------------------------
        # MEMBER AVATAR
        # -------------------------------------------------

        try:
            avatar_url = member.display_avatar.url

            embed.set_thumbnail(
                url=avatar_url
            )
        except Exception:
            pass

        # -------------------------------------------------
        # FOOTER
        # -------------------------------------------------

        footer = settings["footer"]

        if footer:
            footer = replace_welcome_variables(
                footer,
                member
            )

            embed.set_footer(
                text=footer
            )

        # -------------------------------------------------
        # IMAGE
        # -------------------------------------------------

        image_url = settings["image_url"]

        if image_url:
            embed.set_image(
                url=image_url
            )

        # -------------------------------------------------
        # SEND
        # -------------------------------------------------

        try:
            await channel.send(
                content=member.mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(
                    users=True,
                    roles=False,
                    everyone=False
                )
            )

        except discord.Forbidden:
            print(
                f"[WELCOME] لا أملك صلاحية الإرسال في روم "
                f"{channel.id} في سيرفر {member.guild.id}"
            )

        except Exception as e:
            print(
                f"[WELCOME] Error: {e}"
            )

    # =====================================================
    # WELCOME SETUP
    # =====================================================

    @app_commands.command(
        name="welcome_setup",
        description="إعداد نظام الترحيب"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="روم الترحيب",
        message="نص الترحيب",
        image="رابط صورة الترحيب",
        footer="النص الموجود أسفل الترحيب"
    )
    async def welcome_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str = "{mention} نورت السيرفر! 🎉",
        image: str = None,
        footer: str = "أهلاً وسهلاً بك في {server}"
    ):

        con = get_db()

        con.execute("""
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
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(guild_id)
            DO UPDATE SET
                enabled = excluded.enabled,
                channel_id = excluded.channel_id,
                message = excluded.message,
                image_url = excluded.image_url,
                footer = excluded.footer
        """, (
            interaction.guild.id,
            1,
            channel.id,
            message,
            image,
            footer,
            0x8B0000
        ))

        con.commit()
        con.close()

        embed = discord.Embed(
            title="👋 تم إعداد الترحيب",
            description=(
                f"**الروم:** {channel.mention}\n"
                f"**الحالة:** 🟢 مفعّل\n\n"
                f"**النص:**\n{message}"
            ),
            color=0x8B0000
        )

        if image:
            embed.set_image(url=image)

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # WELCOME ON
    # =====================================================

    @app_commands.command(
        name="welcome_on",
        description="تشغيل نظام الترحيب"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_on(
        self,
        interaction: discord.Interaction
    ):

        con = get_db()

        row = con.execute("""
            SELECT guild_id
            FROM welcome_settings
            WHERE guild_id = ?
        """, (interaction.guild.id,)).fetchone()

        if not row:
            con.execute("""
                INSERT INTO welcome_settings
                (
                    guild_id,
                    enabled,
                    message,
                    color
                )
                VALUES (?, 1, ?, ?)
            """, (
                interaction.guild.id,
                "{mention} نورت السيرفر! 🎉",
                0x8B0000
            ))
        else:
            con.execute("""
                UPDATE welcome_settings
                SET enabled = 1
                WHERE guild_id = ?
            """, (interaction.guild.id,))

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
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_off(
        self,
        interaction: discord.Interaction
    ):

        con = get_db()

        con.execute("""
            UPDATE welcome_settings
            SET enabled = 0
            WHERE guild_id = ?
        """, (interaction.guild.id,))

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
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_reset(
        self,
        interaction: discord.Interaction
    ):

        con = get_db()

        con.execute("""
            DELETE FROM welcome_settings
            WHERE guild_id = ?
        """, (interaction.guild.id,))

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
    @app_commands.checks.has_permissions(manage_guild=True)
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

        channel = interaction.guild.get_channel(
            settings["channel_id"]
        )

        if channel is None:
            return await interaction.response.send_message(
                "❌ روم الترحيب غير موجود.",
                ephemeral=True
            )

        message = replace_welcome_variables(
            settings["message"],
            interaction.user
        )

        embed = discord.Embed(
            description=message,
            color=settings["color"]
        )

        try:
            embed.set_thumbnail(
                url=interaction.user.display_avatar.url
            )
        except Exception:
            pass

        footer = settings["footer"]

        if footer:
            footer = replace_welcome_variables(
                footer,
                interaction.user
            )

            embed.set_footer(
                text=footer
            )

        if settings["image_url"]:
            embed.set_image(
                url=settings["image_url"]
            )

        try:
            await channel.send(
                content=interaction.user.mention,
                embed=embed
            )

            await interaction.response.send_message(
                f"✅ تم إرسال تجربة الترحيب في {channel.mention}.",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ البوت لا يملك صلاحية إرسال الرسائل أو الـ Embeds في الروم.",
                ephemeral=True
            )

    # =====================================================
    # STREAM ADD
    # =====================================================

    @app_commands.command(
        name="notification_add",
        description="إضافة حساب للإشعارات"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def notification_add(
        self,
        interaction: discord.Interaction,
        platform: str,
        username: str,
        channel: discord.TextChannel
    ):

        platform = platform.lower()

        if platform not in [
            "twitch",
            "kick",
            "youtube",
            "tiktok"
        ]:
            return await interaction.response.send_message(
                "❌ المنصات المتاحة: Twitch / Kick / YouTube / TikTok",
                ephemeral=True
            )

        con = sqlite3.connect(DB_FILE)

        con.execute("""
            INSERT OR IGNORE INTO streamers
            (
                guild_id,
                platform,
                username,
                channel_id,
                message
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            interaction.guild.id,
            platform,
            username,
            channel.id,
            "{user} نشر محتوى جديد!\n{title}\n{url}"
        ))

        con.commit()
        con.close()

        await interaction.response.send_message(
            f"✅ تمت إضافة **{username}** من **{platform}** للإشعارات.\n"
            f"📢 الروم: {channel.mention}"
        )

    # =====================================================
    # STREAM REMOVE
    # =====================================================

    @app_commands.command(
        name="notification_remove",
        description="حذف حساب من الإشعارات"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def notification_remove(
        self,
        interaction: discord.Interaction,
        platform: str,
        username: str
    ):

        con = sqlite3.connect(DB_FILE)

        con.execute("""
            DELETE FROM streamers
            WHERE guild_id = ?
            AND platform = ?
            AND username = ?
        """, (
            interaction.guild.id,
            platform.lower(),
            username
        ))

        con.commit()
        con.close()

        await interaction.response.send_message(
            f"🗑️ تم حذف **{username}** من الإشعارات."
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(
        Notifications(bot)
    )
