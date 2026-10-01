import os
import discord
from discord.ext import commands
from database import init_db

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


@bot.event
async def on_ready():
    print(f"CTRP System Online: {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print("Sync error:", e)


async def load_systems():
    pass


async def main():
    init_db()

    await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
