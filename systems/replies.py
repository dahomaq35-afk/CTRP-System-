import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
DB_FILE = "ctrp_system.db"
class Replies(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    # =========================================================
    # DATABASE
    # =========================================================
    def get_db(self):
        con = sqlite3.connect(DB_FILE)
        con.row_factory = sqlite3.Row
        return con
    # =========================================================
    # الرد التلقائي
    # =========================================================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if not message.guild:
            return
        content = message.content.strip().lower()
        if not content:
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
                content
            )
        ).fetchone()
        con.close()
        if row:
            try:
                await message.channel.send(
                    row["response"]
                )
            except discord.Forbidden:
                pass
        await self.bot.process_commands(message)
    # =========================================================
    # /اضافة_رد
    # =========================================================
    @app_commands.command(
        name="اضافة_رد",
        description="إضافة رد تلقائي لكلمة معينة"
    )
    @app_commands.describe(
        word="الكلمة التي تريد أن يرد عليها البوت",
        response="الرد الذي سيرسله البوت"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def add_reply(
        self,
        interaction: discord.Interaction,
        word: str,
        response: str
    ):
        word = word.strip().lower()
        if not word:
            return await interaction.response.send_message(
                "❌ اكتب كلمة صحيحة.",
                ephemeral=True
            )
        if not response.strip():
            return await interaction.response.send_message(
                "❌ اكتب الرد.",
                ephemeral=True
            )
        con = self.get_db()
        con.execute(
            """
            INSERT INTO replies
            (
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
                word,
                response
            )
        )
        con.commit()
        con.close()
        await interaction.response.send_message(
            "✅ تم حفظ الرد التلقائي.\n\n"
            f"**الكلمة:** `{word}`\n"
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
        word="الكلمة التي تريد حذف ردها"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def remove_reply(
        self,
        interaction: discord.Interaction,
        word: str
    ):
        word = word.strip().lower()
        con = self.get_db()
        cursor = con.execute(
            """
            DELETE FROM replies
            WHERE guild_id = ?
            AND trigger = ?
            """,
            (
                interaction.guild.id,
                word
            )
        )
        con.commit()
        con.close()
        if cursor.rowcount == 0:
            return await interaction.response.send_message(
                "❌ لا يوجد رد تلقائي بهذه الكلمة.",
                ephemeral=True
            )
        await interaction.response.send_message(
            f"✅ تم حذف الرد التلقائي للكلمة `{word}`."
        )
    # =========================================================
    # /الردود
    # =========================================================
    @app_commands.command(
        name="الردود",
        description="عرض الردود التلقائية"
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
                "📭 لا توجد ردود تلقائية.",
                ephemeral=True
            )
        embed = discord.Embed(
            title="💬 الردود التلقائية",
            color=discord.Color.blue()
        )
        text = ""
        for row in rows:
            line = (
                f"**الكلمة:** `{row['trigger']}`\n"
                f"**الرد:** {row['response']}\n\n"
            )
            if len(text) + len(line) > 3900:
                embed.add_field(
                    name="الردود",
                    value=text,
                    inline=False
                )
                text = ""
            text += line
        if text:
            embed.add_field(
                name="الردود",
                value=text,
                inline=False
            )
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )
async def setup(bot):
    await bot.add_cog(Replies(bot))
