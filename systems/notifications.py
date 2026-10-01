import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3

DB_FILE = "ctrp_system.db"


class Notifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_streams.start()

    def cog_unload(self):
        self.check_streams.cancel()

    @tasks.loop(minutes=2)
    async def check_streams(self):
        # مكان ربط Twitch / Kick / YouTube / TikTok APIs
        # سيتم فحص الحسابات المحفوظة وإرسال إشعار عند وجود بث أو محتوى جديد.
        pass

    @check_streams.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

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

        if platform not in ["twitch", "kick", "youtube", "tiktok"]:
            return await interaction.response.send_message(
                "❌ المنصات المتاحة: Twitch / Kick / YouTube / TikTok",
                ephemeral=True
            )

        con = sqlite3.connect(DB_FILE)

        con.execute("""
            INSERT OR IGNORE INTO streamers
            (guild_id, platform, username, channel_id, message)
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
            WHERE guild_id = ? AND platform = ? AND username = ?
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


async def setup(bot):
    await bot.add_cog(Notifications(bot))
