import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import random
import time

DB_FILE = "ctrp_system.db"


def db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


def level_from_xp(xp, base):
    level = 0
    required = base

    while xp >= required:
        xp -= required
        level += 1
        required = base * (level + 1)

    return level, xp, required


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_xp.start()

    def cog_unload(self):
        self.voice_xp.cancel()

    def get_settings(self, guild_id):
        con = db()

        row = con.execute(
            "SELECT * FROM level_settings WHERE guild_id = ?",
            (guild_id,)
        ).fetchone()

        if not row:
            con.execute("""
                INSERT INTO level_settings
                (guild_id, text_xp, voice_xp, base_xp, levelup_message)
                VALUES (?, ?, ?, ?, ?)
            """, (
                guild_id,
                10,
                5,
                100,
                "مبروك {user} 🎉 وصلت للمستوى {level}!"
            ))

            con.commit()

            row = con.execute(
                "SELECT * FROM level_settings WHERE guild_id = ?",
                (guild_id,)
            ).fetchone()

        con.close()
        return row

    async def add_xp(self, guild, member, amount, xp_type):
        settings = self.get_settings(guild.id)

        con = db()

        row = con.execute("""
            SELECT * FROM levels
            WHERE guild_id = ? AND user_id = ?
        """, (
            guild.id,
            member.id
        )).fetchone()

        if not row:
            con.execute("""
                INSERT INTO levels
                (guild_id, user_id, text_xp, voice_xp, total_xp, level)
                VALUES (?, ?, 0, 0, 0, 0)
            """, (
                guild.id,
                member.id
            ))

            row = con.execute("""
                SELECT * FROM levels
                WHERE guild_id = ? AND user_id = ?
            """, (
                guild.id,
                member.id
            )).fetchone()

        old_level = row["level"]

        if xp_type == "text":
            con.execute("""
                UPDATE levels
                SET text_xp = text_xp + ?,
                    total_xp = total_xp + ?
                WHERE guild_id = ? AND user_id = ?
            """, (
                amount,
                amount,
                guild.id,
                member.id
            ))

        else:
            con.execute("""
                UPDATE levels
                SET voice_xp = voice_xp + ?,
                    total_xp = total_xp + ?
                WHERE guild_id = ? AND user_id = ?
            """, (
                amount,
                amount,
                guild.id,
                member.id
            ))

        new_row = con.execute("""
            SELECT * FROM levels
            WHERE guild_id = ? AND user_id = ?
        """, (
            guild.id,
            member.id
        )).fetchone()

        new_level, _, _ = level_from_xp(
            new_row["total_xp"],
            settings["base_xp"]
        )

        con.execute("""
            UPDATE levels
            SET level = ?
            WHERE guild_id = ? AND user_id = ?
        """, (
            new_level,
            guild.id,
            member.id
        ))

        con.commit()
        con.close()

        if new_level > old_level:
            await self.level_up_message(
                guild,
                member,
                new_level,
                new_row["total_xp"],
                settings["levelup_message"]
            )

    async def level_up_message(
        self,
        guild,
        member,
        level,
        xp,
        message
    ):
        text = message.replace(
            "{user}",
            member.mention
        ).replace(
            "{level}",
            str(level)
        ).replace(
            "{xp}",
            str(xp)
        )

        channel = guild.get_channel(
            member.guild.system_channel.id
        ) if guild.system_channel else None

        if channel:
            await channel.send(
                text,
                reference=discord.MessageReference(
                    message_id=0,
                    channel_id=channel.id,
                    guild_id=guild.id
                )
            )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        settings = self.get_settings(message.guild.id)

        xp = random.randint(
            max(1, settings["text_xp"] - 2),
            settings["text_xp"] + 2
        )

        await self.add_xp(
            message.guild,
            message.author,
            xp,
            "text"
        )

    @tasks.loop(minutes=1)
    async def voice_xp(self):
        for guild in self.bot.guilds:
            settings = self.get_settings(guild.id)

            for channel in guild.voice_channels:
                for member in channel.members:
                    if member.bot:
                        continue

                    if member.voice and member.voice.self_deaf:
                        continue

                    await self.add_xp(
                        guild,
                        member,
                        settings["voice_xp"],
                        "voice"
                    )

    @voice_xp.before_loop
    async def before_voice_xp(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="level",
        description="عرض مستواك وخبرتك"
    )
    async def level(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        member = member or interaction.user
        settings = self.get_settings(interaction.guild.id)

        con = db()

        row = con.execute("""
            SELECT * FROM levels
            WHERE guild_id = ? AND user_id = ?
        """, (
            interaction.guild.id,
            member.id
        )).fetchone()

        con.close()

        if not row:
            total_xp = 0
            text_xp = 0
            voice_xp = 0
        else:
            total_xp = row["total_xp"]
            text_xp = row["text_xp"]
            voice_xp = row["voice_xp"]

        level, current_xp, required_xp = level_from_xp(
            total_xp,
            settings["base_xp"]
        )

        embed = discord.Embed(
            title="🎖️ مستوى العضو",
            color=discord.Color.blue()
        )

        embed.set_author(
            name=member.display_name,
            icon_url=member.display_avatar.url
        )

        embed.add_field(
            name="🎖️ المستوى",
            value=f"**{level}**",
            inline=True
        )

        embed.add_field(
            name="⭐ الخبرة",
            value=f"**{current_xp} / {required_xp} XP**",
            inline=True
        )

        embed.add_field(
            name="💬 الكتابي",
            value=f"**{text_xp} XP**",
            inline=True
        )

        embed.add_field(
            name="🎙️ الصوتي",
            value=f"**{voice_xp} XP**",
            inline=True
        )

        embed.add_field(
            name="✨ مجموع الخبرة",
            value=f"**{total_xp} XP**",
            inline=True
        )

        await interaction.response.send_message(
            embed=embed
        )

    @app_commands.command(
        name="setlevelup",
        description="تحديد رسالة الارتقاء"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlevelup(
        self,
        interaction: discord.Interaction,
        message: str
    ):
        con = db()

        con.execute("""
            INSERT INTO level_settings
            (guild_id, text_xp, voice_xp, base_xp, levelup_message)
            VALUES (?, 10, 5, 100, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET levelup_message = excluded.levelup_message
        """, (
            interaction.guild.id,
            message
        ))

        con.commit()
        con.close()

        await interaction.response.send_message(
            "✅ تم تغيير رسالة الارتقاء."
        )

    @app_commands.command(
        name="settextxp",
        description="تحديد خبرة الرسائل"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def settextxp(
        self,
        interaction: discord.Interaction,
        amount: int
    ):
        if amount < 1:
            return await interaction.response.send_message(
                "❌ يجب أن يكون XP أكبر من 0.",
                ephemeral=True
            )

        self.get_settings(interaction.guild.id)

        con = db()

        con.execute("""
            UPDATE level_settings
            SET text_xp = ?
            WHERE guild_id = ?
        """, (
            amount,
            interaction.guild.id
        ))

        con.commit()
        con.close()

        await interaction.response.send_message(
            f"✅ خبرة الرسائل أصبحت **{amount} XP**."
        )

    @app_commands.command(
        name="setvoicexp",
        description="تحديد خبرة الصوتي"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setvoicexp(
        self,
        interaction: discord.Interaction,
        amount: int
    ):
        if amount < 1:
            return await interaction.response.send_message(
                "❌ يجب أن يكون XP أكبر من 0.",
                ephemeral=True
            )

        self.get_settings(interaction.guild.id)

        con = db()

        con.execute("""
            UPDATE level_settings
            SET voice_xp = ?
            WHERE guild_id = ?
        """, (
            amount,
            interaction.guild.id
        ))

        con.commit()
        con.close()

        await interaction.response.send_message(
            f"✅ خبرة الصوتي أصبحت **{amount} XP**."
        )

    @app_commands.command(
        name="setlevelxp",
        description="تحديد XP الأساسي للمستويات"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlevelxp(
        self,
        interaction: discord.Interaction,
        amount: int
    ):
        if amount < 1:
            return await interaction.response.send_message(
                "❌ يجب أن يكون الرقم أكبر من 0.",
                ephemeral=True
            )

        self.get_settings(interaction.guild.id)

        con = db()

        con.execute("""
            UPDATE level_settings
            SET base_xp = ?
            WHERE guild_id = ?
        """, (
            amount,
            interaction.guild.id
        ))

        con.commit()
        con.close()

        await interaction.response.send_message(
            f"✅ XP الأساسي أصبح **{amount} XP**."
        )


async def setup(bot):
    await bot.add_cog(Levels(bot))
