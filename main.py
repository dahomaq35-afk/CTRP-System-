import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import discord
from discord.ext import commands
from database import init_db


# =========================================================
# TOKEN
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN غير موجود في Environment Variables")


# =========================================================
# RENDER PORT
# =========================================================

PORT = int(os.getenv("PORT", "10000"))


class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )
        self.end_headers()

        self.wfile.write(
            b"CTRP Bot is Online!"
        )

    def log_message(self, format, *args):
        pass


def start_web_server():

    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler
    )

    print("━━━━━━━━━━━━━━━━━━━━")
    print(f"🌐 Render Port: {PORT}")
    print("🟢 Web Server Online")
    print("━━━━━━━━━━━━━━━━━━━━")

    server.serve_forever()


# =========================================================
# DISCORD
# =========================================================

intents = discord.Intents.default()

intents.members = True
intents.message_content = True
intents.voice_states = True
intents.presences = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# LOAD SYSTEMS
# =========================================================

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


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    print("━━━━━━━━━━━━━━━━━━━━")
    print(f"🤖 Bot: {bot.user}")
    print("🟢 CTRP System Online")
    print("━━━━━━━━━━━━━━━━━━━━")

    try:

        synced = await bot.tree.sync()

        print(
            f"✅ Synced {len(synced)} slash commands"
        )

    except Exception as e:

        print(f"❌ Sync Error: {e}")


# =========================================================
# MAIN
# =========================================================

async def main():

    init_db()

    await load_systems()

    await bot.start(TOKEN)


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    # تشغيل منفذ Render بدون التأثير على البوت
    web_thread = threading.Thread(
        target=start_web_server,
        daemon=True
    )

    web_thread.start()

    # تشغيل البوت بنفس طريقتك السابقة
    asyncio.run(main())
