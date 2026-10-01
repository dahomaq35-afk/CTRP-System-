import discord
from discord import app_commands
from discord.ext import commands
import sqlite3

DB_FILE = "ctrp_system.db"


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="role_add", description="إعطاء رتبة لعضو")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role_add(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                "❌ لا أستطيع إعطاء هذه الرتبة.",
                ephemeral=True
            )

        await member.add_roles(role)

        await interaction.response.send_message(
            f"✅ تم إعطاء {member.mention} رتبة {role.mention}."
        )

    @app_commands.command(name="role_remove", description="إزالة رتبة من عضو")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role_remove(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        await member.remove_roles(role)

        await interaction.response.send_message(
            f"✅ تم إزالة رتبة {role.mention} من {member.mention}."
        )

    @app_commands.command(name="selfrole_add", description="إضافة رتبة إلى قائمة الرتب الذاتية")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def selfrole_add(self, interaction: discord.Interaction, role: discord.Role):
        con = sqlite3.connect(DB_FILE)

        con.execute(
            "INSERT OR IGNORE INTO self_roles (guild_id, role_id) VALUES (?, ?)",
            (interaction.guild.id, role.id)
        )

        con.commit()
        con.close()

        await interaction.response.send_message(
            f"✅ تمت إضافة {role.mention} للرتب الذاتية."
        )

    @app_commands.command(name="selfrole_remove", description="إزالة رتبة من قائمة الرتب الذاتية")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def selfrole_remove(self, interaction: discord.Interaction, role: discord.Role):
        con = sqlite3.connect(DB_FILE)

        con.execute(
            "DELETE FROM self_roles WHERE guild_id = ? AND role_id = ?",
            (interaction.guild.id, role.id)
        )

        con.commit()
        con.close()

        await interaction.response.send_message(
            f"🗑️ تمت إزالة {role.mention} من الرتب الذاتية."
        )


async def setup(bot):
    await bot.add_cog(Roles(bot))
