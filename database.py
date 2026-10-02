import sqlite3
import discord
from discord import app_commands
from discord.ext import commands

DB_FILE = "ctrp_system.db"


class Replies(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_db(self):
        con = sqlite3.connect(DB_FILE)
        con.row_factory = sqlite3.Row
        return con

    # =========================================================
    # /اضافة_رد
    # =========================================================

    @app_commands.command(
        name="اضافة_رد",
        description="إضافة رد تلقائي"
    )
    @app_commands.describe(
        الكلمة="الكلمة التي سيراقبها البوت",
        الرد="الرد الذي سيرسله البوت"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def add_reply(
        self,
        interaction: discord.Interaction,
        الكلمة: str,
        الرد: str
    ):
        trigger = الكلمة.strip().lower()
        response = الرد.strip()

        if not trigger:
            return await interaction.response.send_message(
                "❌ اكتب الكلمة.",
                ephemeral=True
            )

        if not response:
            return await interaction.response.send_message(
                "❌ اكتب الرد.",
                ephemeral=True
            )

        con = self.get_db()

        con.execute(
            """
            INSERT INTO replies (
                guild_id,
                trigger,
                response
            )
            VALUES (?, ?, ?)

            ON CONFLICT(guild_id, trigger)
            DO UPDATE SET
                response = excluded.response
            """,
            (
                interaction.guild.id,
                trigger,
                response
            )
        )

        con.commit()
        con.close()

        await interaction.response.send_message(
            f"✅ تم حفظ الرد التلقائي.\n\n"
            f"**الكلمة:** `{trigger}`\n"
            f"**الرد:** {response}"
        )

    # =========================================================
    # /حذف_رد
    # =========================================================

    @app_commands.command(
        name="حذف_رد",
        description="حذف رد تلقائي"
    )
    @app_commands.describe(
        الكلمة="الكلمة التي تريد حذف ردها"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def delete_reply(
        self,
        interaction: discord.Interaction,
        الكلمة: str
    ):
        trigger = الكلمة.strip().lower()

        con = self.get_db()

        cursor = con.execute(
            """
            DELETE FROM replies
            WHERE guild_id = ?
            AND trigger = ?
            """,
            (
                interaction.guild.id,
                trigger
            )
        )

        con.commit()
        con.close()

        if cursor.rowcount == 0:
            return await interaction.response.send_message(
                "❌ ما فيه رد تلقائي بهذه الكلمة.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"✅ تم حذف الرد التلقائي للكلمة `{trigger}`."
        )

    # =========================================================
    # /الردود
    # =========================================================

    @app_commands.command(
        name="الردود",
        description="عرض جميع الردود التلقائية"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def list_replies(
        self,
        interaction: discord.Interaction
    ):
        con = self.get_db()

        rows = con.execute(
            """
            SELECT trigger, response
            FROM replies
            WHERE guild_id = ?
            ORDER BY trigger
            """,
            (
                interaction.guild.id,
            )
        ).fetchall()

        con.close()

        if not rows:
            return await interaction.response.send_message(
                "📭 ما فيه ردود تلقائية محفوظة.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="💬 الردود التلقائية",
            color=discord.Color.blue()
        )

        for row in rows:
            response = row["response"]

            if len(response) > 1000:
                response = response[:997] + "..."

            embed.add_field(
                name=f"🔹 {row['trigger']}",
                value=response,
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =========================================================
    # الرد التلقائي
    # =========================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message
    ):
        if message.author.bot:
            return

        if not message.guild:
            return

        trigger = message.content.strip().lower()

        if not trigger:
            return

        con = self.get_db()

        row = con.execute(
            """
            SELECT response
            FROM replies
            WHERE guild_id = ?
            AND trigger = ?
            """,
            (
                message.guild.id,
                trigger
            )
        ).fetchone()

        con.close()

        if row:
            await message.channel.send(
                row["response"]
            )

        await self.bot.process_commands(message)


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(
        Replies(bot)
    )
