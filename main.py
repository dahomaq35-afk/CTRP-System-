import os
import asyncio
import importlib
import discord
from discord.ext import commands
from database import init_db

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN غير موجود في Environment Variables")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True
intents.presences = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


async def load_systems():
    systems_folder = "systems"

    if not os.path.exists(systems_folder):
        os.makedirs(systems_folder)

    for filename in os.listdir(systems_folder):

        if not filename.endswith(".py"):
            continue

        if filename == "__init__.py":
            continue

        module_name = filename[:-3]
        extension = f"{systems_folder}.{module_name}"

        try:
            await bot.load_extension(extension)
            print(f"✅ Loaded: {extension}")

        except Exception as e:
            print(f"❌ Failed: {extension}")
            print(f"   {e}")


@bot.event
async def on_ready():
    print("━━━━━━━━━━━━━━━━━━━━")
    print(f"🤖 Bot: {bot.user}")
    print("🟢 CTRP System Online")
    print("━━━━━━━━━━━━━━━━━━━━")

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")

    except Exception as e:
        print(f"❌ Sync Error: {e}")


async def main():
    init_db()

    await load_systems()

    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
