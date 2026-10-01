import discord
from discord import app_commands
from discord.ext import commands
import sqlite3

DB_FILE = "ctrp_system.db"


class Points(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="points_add", description="إضافة نقاط لعضو")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def points_add(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int
    ):
        con = sqlite3.connect(DB_FILE)

        con.execute("""
            INSERT INTO points (guild_id, user_id, points)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET points = points + excluded.points
        """, (
            interaction.guild.id,
            member.id,
            amount
        ))

        con.commit()
        con.close()

        await interaction.response.send_message(
            f"✅ تمت إضافة **{amount}** نقطة إلى {member.mention}."
        )

    @app_commands.command(name="points_remove", description="خصم نقاط من عضو")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def points_remove(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int
    ):
        con = sqlite3.connect(DB_FILE)

        con.execute("""
            INSERT INTO points (guild_id, user_id, points)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET points = MAX(0, points - ?)
        """, (
            interaction.guild.id,
            member.id,
            0,
            amount
        ))

        con.commit()
        con.close()

        await interaction.response.send_message(
            f"✅ تم خصم **{amount}** نقطة من {member.mention}."
        )

    @app_commands.command(name="points", description="عرض نقاط عضو")
    async def points(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        member = member or interaction.user

        con = sqlite3.connect(DB_FILE)

        row = con.execute("""
            SELECT points
            FROM points
            WHERE guild_id = ? AND user_id = ?
        """, (
            interaction.guild.id,
            member.id
        )).fetchone()

        con.close()

        amount = row[0] if row else 0

        await interaction.response.send_message(
            f"🔢 نقاط {member.mention}: **{amount}**"
        )


async def setup(bot):
    await bot.add_cog(Points(bot))
