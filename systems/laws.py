import discord
from discord import app_commands
from discord.ext import commands
import sqlite3

DB_FILE = "ctrp_system.db"


class Laws(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="law", description="إضافة أو تعديل قانون")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def law(
        self,
        interaction: discord.Interaction,
        number: int,
        name: str,
        text: str
    ):
        if number < 1 or number > 30:
            return await interaction.response.send_message(
                "❌ رقم القانون يجب أن يكون من 1 إلى 30.",
                ephemeral=True
            )

        con = sqlite3.connect(DB_FILE)

        con.execute("""
            INSERT INTO laws (guild_id, number, name, text)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, number)
            DO UPDATE SET
                name = excluded.name,
                text = excluded.text
        """, (
            interaction.guild.id,
            number,
            name,
            text
        ))

        con.commit()
        con.close()

        await interaction.response.send_message(
            f"✅ تم حفظ القانون رقم **{number}**."
        )

    @app_commands.command(name="laws", description="عرض القوانين")
    async def laws(self, interaction: discord.Interaction):
        con = sqlite3.connect(DB_FILE)

        rows = con.execute("""
            SELECT number, name, text
            FROM laws
            WHERE guild_id = ?
            ORDER BY number
        """, (interaction.guild.id,)).fetchall()

        con.close()

        if not rows:
            return await interaction.response.send_message(
                "📋 لا توجد قوانين محفوظة."
            )

        embed = discord.Embed(
            title="📋 قوانين السيرفر",
            color=discord.Color.blue()
        )

        for number, name, text in rows:
            embed.add_field(
                name=f"⚖️ {number}・{name}",
                value=text[:1024],
                inline=False
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Laws(bot))
