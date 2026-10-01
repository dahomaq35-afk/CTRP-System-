import discord
from discord import app_commands
from discord.ext import commands
import sqlite3


DB_FILE = "ctrp_system.db"


class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="suggest", description="إرسال اقتراح")
    async def suggest(
        self,
        interaction: discord.Interaction,
        suggestion: str
    ):
        con = sqlite3.connect(DB_FILE)

        row = con.execute(
            "SELECT suggestion_channel FROM settings WHERE guild_id = ?",
            (interaction.guild.id,)
        ).fetchone()

        con.close()

        if not row or not row[0]:
            return await interaction.response.send_message(
                "❌ لم يتم تحديد روم الاقتراحات.",
                ephemeral=True
            )

        channel = interaction.guild.get_channel(row[0])

        if not channel:
            return await interaction.response.send_message(
                "❌ روم الاقتراحات غير موجود.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="💡 اقتراح جديد",
            description=suggestion,
            color=discord.Color.blue()
        )

        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )

        embed.set_footer(
            text=f"اقتراح بواسطة {interaction.user}"
        )

        message = await channel.send(embed=embed)

        await message.add_reaction("👍")
        await message.add_reaction("👎")

        await interaction.response.send_message(
            "✅ تم إرسال اقتراحك.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Suggestions(bot))
