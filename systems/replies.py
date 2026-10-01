import discord
from discord.ext import commands
import sqlite3

DB_FILE = "ctrp_system.db"


class Replies(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        con = sqlite3.connect(DB_FILE)
        row = con.execute(
            "SELECT response FROM replies WHERE guild_id = ? AND trigger = ?",
            (message.guild.id, message.content.lower())
        ).fetchone()
        con.close()

        if row:
            await message.channel.send(row[0])

        await self.bot.process_commands(message)


async def setup(bot):
    await bot.add_cog(Replies(bot))
