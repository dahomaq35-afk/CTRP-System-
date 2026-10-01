import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from datetime import datetime


DB_FILE = "ctrp_system.db"


class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="apply", description="تقديم طلب")
    async def apply(
        self,
        interaction: discord.Interaction,
        application_type: str,
        content: str
    ):
        con = sqlite3.connect(DB_FILE)

        con.execute("""
            INSERT INTO applications
            (guild_id, user_id, application_type, content, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            interaction.guild.id,
            interaction.user.id,
            application_type,
            content,
            "pending",
            datetime.utcnow().isoformat()
        ))

        con.commit()
        con.close()

        await interaction.response.send_message(
            "✅ تم إرسال طلبك بنجاح.",
            ephemeral=True
        )

    @app_commands.command(name="applications", description="عرض الطلبات")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def applications(self, interaction: discord.Interaction):
        con = sqlite3.connect(DB_FILE)

        rows = con.execute("""
            SELECT id, user_id, application_type, content, status
            FROM applications
            WHERE guild_id = ?
            ORDER BY id DESC
            LIMIT 10
        """, (interaction.guild.id,)).fetchall()

        con.close()

        if not rows:
            return await interaction.response.send_message(
                "📋 لا توجد طلبات."
            )

        embed = discord.Embed(
            title="📝 آخر الطلبات",
            color=discord.Color.blue()
        )

        for row in rows:
            app_id, user_id, app_type, content, status = row

            embed.add_field(
                name=f"#{app_id}・{app_type}",
                value=(
                    f"**العضو:** <@{user_id}>\n"
                    f"**الحالة:** {status}\n"
                    f"**الطلب:** {content[:500]}"
                ),
                inline=False
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Applications(bot))
