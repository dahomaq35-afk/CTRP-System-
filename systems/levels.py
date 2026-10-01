import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import random
import time


DB_FILE = "ctrp_system.db"

TEXT_COOLDOWN = 30
VOICE_INTERVAL = 60


def get_db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


def calculate_level(total_xp: int, base_xp: int):
    level = 0
    used_xp = 0

    while True:
        required = base_xp * (level + 1)

        if total_xp < used_xp + required:
            current_xp = total_xp - used_xp
            return level, current_xp, required

        used_xp += required
        level += 1


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.text_cooldowns = {}

        self.voice_xp_loop.start()

    def cog_unload(self):
        self.voice_xp_loop.cancel()

    # =========================================================
    # DATABASE
    # =========================================================

    def get_settings(self, guild_id):
        con = get_db()

        row = con.execute("""
            SELECT *
            FROM level_settings
            WHERE guild_id = ?
        """, (guild_id,)).fetchone()

        if not row:
            con.execute("""
                INSERT INTO level_settings
                (
                    guild_id,
                    text_xp,
                    voice_xp,
                    base_xp,
                    levelup_message
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                guild_id,
                10,
                5,
                100,
                "مبروك {user} 🎉 وصلت للمستوى {level}!"
            ))

            con.commit()

            row = con.execute("""
                SELECT *
                FROM level_settings
                WHERE guild_id = ?
            """, (guild_id,)).fetchone()

        con.close()

        return row

    def get_user(self, guild_id, user_id):
        con = get_db()

        row = con.execute("""
            SELECT *
            FROM levels
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id
        )).fetchone()

        if not row:
            con.execute("""
                INSERT INTO levels
                (
                    guild_id,
                    user_id,
                    text_xp,
                    voice_xp,
                    total_xp,
                    level
                )
                VALUES (?, ?, 0, 0, 0, 0)
            """, (
                guild_id,
                user_id
            ))

            con.commit()

            row = con.execute("""
                SELECT *
                FROM levels
                WHERE guild_id = ?
                AND user_id = ?
            """, (
                guild_id,
                user_id
            )).fetchone()

        con.close()

        return row

    # =========================================================
    # ADD XP
    # =========================================================

    async def add_xp(
        self,
        guild: discord.Guild,
        member: discord.Member,
        amount: int,
        xp_type: str,
        reply_message=None
    ):
        if member.bot:
            return

        settings = self.get_settings(guild.id)
        old_data = self.get_user(guild.id, member.id)

        old_level = old_data["level"]

        con = get_db()

        if xp_type == "text":
            con.execute("""
                UPDATE levels
                SET
                    text_xp = text_xp + ?,
                    total_xp = total_xp + ?
                WHERE guild_id = ?
                AND user_id = ?
            """, (
                amount,
                amount,
                guild.id,
                member.id
            ))

        elif xp_type == "voice":
            con.execute("""
                UPDATE levels
                SET
                    voice_xp = voice_xp + ?,
                    total_xp = total_xp + ?
                WHERE guild_id = ?
                AND user_id = ?
            """, (
                amount,
                amount,
                guild.id,
                member.id
            ))

        new_data = con.execute("""
            SELECT *
            FROM levels
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild.id,
            member.id
        )).fetchone()

        new_level, _, _ = calculate_level(
            new_data["total_xp"],
            settings["base_xp"]
        )

        con.execute("""
            UPDATE levels
            SET level = ?
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            new_level,
            guild.id,
            member.id
        ))

        con.commit()
        con.close()

        # ارتقاء مستوى
        if new_level > old_level:
            await self.send_level_up(
                member=member,
                level=new_level,
                total_xp=new_data["total_xp"],
                message=settings["levelup_message"],
                reply_message=reply_message
            )

    # =========================================================
    # LEVEL UP MESSAGE
    # =========================================================

    async def send_level_up(
        self,
        member,
        level,
        total_xp,
        message,
        reply_message=None
    ):
        text = message

        text = text.replace(
            "{user}",
            member.mention
        )

        text = text.replace(
            "{level}",
            str(level)
        )

        text = text.replace(
            "{xp}",
            str(total_xp)
        )

        # إذا عندنا رسالة العضو، نرد عليها مباشرة
        if reply_message:
            try:
                await reply_message.reply(
                    text,
                    mention_author=False
                )
                return
            except Exception:
                pass

        # احتياط إذا تعذر الرد
        if member.guild.system_channel:
            try:
                await member.guild.system_channel.send(text)
            except Exception:
                pass

    # =========================================================
    # TEXT XP
    # =========================================================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not message.guild:
            return

        if not message.content.strip():
            return

        key = (
            message.guild.id,
            message.author.id
        )

        now = time.time()

        last_time = self.text_cooldowns.get(key, 0)

        if now - last_time < TEXT_COOLDOWN:
            return

        self.text_cooldowns[key] = now

        settings = self.get_settings(message.guild.id)

        amount = random.randint(
            max(1, settings["text_xp"] - 2),
            settings["text_xp"] + 2
        )

        await self.add_xp(
            guild=message.guild,
            member=message.author,
            amount=amount,
            xp_type="text",
            reply_message=message
        )

    # =========================================================
    # VOICE XP
    # =========================================================

    @tasks.loop(seconds=VOICE_INTERVAL)
    async def voice_xp_loop(self):
        for guild in self.bot.guilds:

            settings = self.get_settings(guild.id)

            for channel in guild.voice_channels:

                if channel.category is None:
                    pass

                for member in channel.members:

                    if member.bot:
                        continue

                    if not member.voice:
                        continue

                    # لا يحسب للشخص إذا كان مكتومًا من نفسه
                    if member.voice.self_deaf:
                        continue

                    amount = random.randint(
                        max(1, settings["voice_xp"] - 1),
                        settings["voice_xp"] + 1
                    )

                    await self.add_xp(
                        guild=guild,
                        member=member,
                        amount=amount,
                        xp_type="voice"
                    )

    @voice_xp_loop.before_loop
    async def before_voice_xp(self):
        await self.bot.wait_until_ready()

    # =========================================================
    # /LEVEL
    # =========================================================

    @app_commands.command(
        name="level",
        description="عرض اللفل والخبرة"
    )
    async def level(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        member = member or interaction.user

        settings = self.get_settings(
            interaction.guild.id
        )

        data = self.get_user(
            interaction.guild.id,
            member.id
        )

        level, current_xp, required_xp = calculate_level(
            data["total_xp"],
            settings["base_xp"]
        )

        embed = discord.Embed(
            title="🎖️ مستوى العضو",
            color=discord.Color.blue()
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.add_field(
            name="👤 العضو",
            value=member.mention,
            inline=False
        )

        embed.add_field(
            name="🎖️ اللفل",
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
            value=f"**{data['text_xp']} XP**",
            inline=True
        )

        embed.add_field(
            name="🎙️ الصوتي",
            value=f"**{data['voice_xp']} XP**",
            inline=True
        )

        embed.add_field(
            name="✨ مجموع الخبرة",
            value=f"**{data['total_xp']} XP**",
            inline=True
        )

        await interaction.response.send_message(
            embed=embed
        )

    # =========================================================
    # /TOP
    # =========================================================

    @app_commands.command(
        name="top",
        description="عرض أفضل الأعضاء في اللفلات"
    )
    @app_commands.choices(
        period=[
            app_commands.Choice(
                name="أسبوعي",
                value="weekly"
            ),
            app_commands.Choice(
                name="شهري",
                value="monthly"
            ),
            app_commands.Choice(
                name="سنوي",
                value="yearly"
            ),
            app_commands.Choice(
                name="الكل",
                value="all"
            )
        ]
    )
    async def top(
        self,
        interaction: discord.Interaction,
        period: app_commands.Choice[str]
    ):
        con = get_db()

        rows = con.execute("""
            SELECT *
            FROM levels
            WHERE guild_id = ?
            ORDER BY total_xp DESC
            LIMIT 100
        """, (
            interaction.guild.id,
        )).fetchall()

        con.close()

        settings = self.get_settings(
            interaction.guild.id
        )

        # =====================================================
        # الكتابي
        # =====================================================

        text_rows = sorted(
            rows,
            key=lambda x: x["text_xp"],
            reverse=True
        )

        # =====================================================
        # الصوتي
        # =====================================================

        voice_rows = sorted(
            rows,
            key=lambda x: x["voice_xp"],
            reverse=True
        )

        # =====================================================
        # Embed
        # =====================================================

        embed = discord.Embed(
            title="🏆 TOP اللفلات",
            description=f"الفترة: **{period.name}**",
            color=discord.Color.blue()
        )

        # =====================================================
        # TOP الكتابي
        # =====================================================

        text_lines = []

        for index, row in enumerate(text_rows[:5], start=1):

            level, _, _ = calculate_level(
                row["total_xp"],
                settings["base_xp"]
            )

            text_lines.append(
                f"🟠 **{index}・** <@{row['user_id']}>"
                f" — لفل **{level}**"
                f" — **{row['text_xp']} XP**"
            )

        # ترتيب صاحب الأمر
        my_data = self.get_user(
            interaction.guild.id,
            interaction.user.id
        )

        my_text_rank = 1

        for index, row in enumerate(text_rows, start=1):
            if row["user_id"] == interaction.user.id:
                my_text_rank = index
                break

        if interaction.user.id not in [
            row["user_id"] for row in text_rows[:5]
        ]:
            my_level, _, _ = calculate_level(
                my_data["total_xp"],
                settings["base_xp"]
            )

            text_lines.append(
                f"\n🔵 **{my_text_rank}・** "
                f"{interaction.user.mention}"
                f" — لفل **{my_level}**"
                f" — **{my_data['text_xp']} XP**"
            )

        embed.add_field(
            name="💬 TOP الكتابي",
            value="\n".join(text_lines)
            if text_lines else "لا توجد بيانات.",
            inline=False
        )

        # =====================================================
        # TOP الصوتي
        # =====================================================

        voice_lines = []

        for index, row in enumerate(voice_rows[:5], start=1):

            level, _, _ = calculate_level(
                row["total_xp"],
                settings["base_xp"]
            )

            voice_lines.append(
                f"🟠 **{index}・** <@{row['user_id']}>"
                f" — لفل **{level}**"
                f" — **{row['voice_xp']} XP**"
            )

        my_voice_rank = 1

        for index, row in enumerate(voice_rows, start=1):
            if row["user_id"] == interaction.user.id:
                my_voice_rank = index
                break

        if interaction.user.id not in [
            row["user_id"] for row in voice_rows[:5]
        ]:
            my_level, _, _ = calculate_level(
                my_data["total_xp"],
                settings["base_xp"]
            )

            voice_lines.append(
                f"\n🔵 **{my_voice_rank}・** "
                f"{interaction.user.mention}"
                f" — لفل **{my_level}**"
                f" — **{my_data['voice_xp']} XP**"
            )

        embed.add_field(
            name="🎙️ TOP الصوتي",
            value="\n".join(voice_lines)
            if voice_lines else "لا توجد بيانات.",
            inline=False
        )

        embed.set_footer(
            text="🟠 أفضل 5 • 🔵 ترتيبك"
        )

        await interaction.response.send_message(
            embed=embed
        )

    # =========================================================
    # /SETLEVELUP
    # =========================================================

    @app_commands.command(
        name="setlevelup",
        description="تحديد رسالة الارتقاء"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def setlevelup(
        self,
        interaction: discord.Interaction,
        message: str
    ):
        self.get_settings(
            interaction.guild.id
        )

        con = get_db()

        con.execute("""
            UPDATE level_settings
            SET levelup_message = ?
            WHERE guild_id = ?
        """, (
            message,
            interaction.guild.id
        ))

        con.commit()
        con.close()

        await interaction.response.send_message(
            "✅ تم تغيير رسالة الارتقاء بنجاح.\n\n"
            "**المتغيرات:**\n"
            "`{user}` = منشن العضو\n"
            "`{level}` = اللفل الجديد\n"
            "`{xp}` = مجموع الخبرة"
        )

    # =========================================================
    # /SETTEXTXP
    # =========================================================

    @app_commands.command(
        name="settextxp",
        description="تحديد XP الكتابي"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
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

        self.get_settings(
            interaction.guild.id
        )

        con = get_db()

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
            f"✅ XP الكتابي أصبح **{amount} XP**."
        )

    # =========================================================
    # /SETVOICEXP
    # =========================================================

    @app_commands.command(
        name="setvoicexp",
        description="تحديد XP الصوتي"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
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

        self.get_settings(
            interaction.guild.id
        )

        con = get_db()

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
            f"✅ XP الصوتي أصبح **{amount} XP** لكل دقيقة."
        )

    # =========================================================
    # /SETLEVELXP
    # =========================================================

    @app_commands.command(
        name="setlevelxp",
        description="تحديد XP الأساسي للمستويات"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
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

        self.get_settings(
            interaction.guild.id
        )

        con = get_db()

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
            f"✅ XP بداية المستويات أصبح **{amount} XP**."
        )


async def setup(bot):
    await bot.add_cog(Levels(bot))
