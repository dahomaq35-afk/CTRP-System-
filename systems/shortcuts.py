import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from datetime import timedelta
DB_FILE = "ctrp_system.db"
class Shortcuts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.dynamic_commands = {}
    # =========================================================
    # DATABASE
    # =========================================================
    def get_db(self):
        con = sqlite3.connect(DB_FILE)
        con.row_factory = sqlite3.Row
        return con
    # =========================================================
    # الأوامر المدعومة
    # =========================================================
    COMMANDS = {
        "kick": "طرد عضو",
        "ban": "حظر عضو",
        "unban": "فك حظر عضو",
        "timeout": "إعطاء تايم أوت لعضو",
        "untimeout": "إزالة التايم أوت",
        "clear": "حذف عدد من الرسائل"
    }
    # =========================================================
    # إنشاء أمر kick
    # =========================================================
    def create_kick_command(self, name):
        async def callback(
            interaction: discord.Interaction,
            member: discord.Member,
            reason: str = "بدون سبب"
        ):
            if not interaction.user.guild_permissions.kick_members:
                return await interaction.response.send_message(
                    "❌ ما عندك صلاحية طرد الأعضاء.",
                    ephemeral=True
                )
            try:
                await member.kick(
                    reason=reason
                )
                embed = discord.Embed(
                    title="👢 تم طرد العضو",
                    description=(
                        f"**العضو:** {member.mention}\n"
                        f"**السبب:** {reason}\n"
                        f"**بواسطة:** {interaction.user.mention}"
                    ),
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(
                    embed=embed
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ البوت لا يملك صلاحية طرد هذا العضو.",
                    ephemeral=True
                )
        callback.__name__ = name
        command = app_commands.Command(
            name=name,
            description="اختصار لأمر طرد عضو",
            callback=callback
        )
        return command
    # =========================================================
    # إنشاء أمر ban
    # =========================================================
    def create_ban_command(self, name):
        async def callback(
            interaction: discord.Interaction,
            member: discord.Member,
            reason: str = "بدون سبب"
        ):
            if not interaction.user.guild_permissions.ban_members:
                return await interaction.response.send_message(
                    "❌ ما عندك صلاحية حظر الأعضاء.",
                    ephemeral=True
                )
            try:
                await member.ban(
                    reason=reason
                )
                embed = discord.Embed(
                    title="🔨 تم حظر العضو",
                    description=(
                        f"**العضو:** {member.mention}\n"
                        f"**السبب:** {reason}\n"
                        f"**بواسطة:** {interaction.user.mention}"
                    ),
                    color=discord.Color.red()
                )
                await interaction.response.send_message(
                    embed=embed
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ البوت لا يملك صلاحية حظر هذا العضو.",
                    ephemeral=True
                )
        callback.__name__ = name
        return app_commands.Command(
            name=name,
            description="اختصار لأمر حظر عضو",
            callback=callback
        )
    # =========================================================
    # إنشاء أمر unban
    # =========================================================
    def create_unban_command(self, name):
        async def callback(
            interaction: discord.Interaction,
            user_id: str
        ):
            if not interaction.user.guild_permissions.ban_members:
                return await interaction.response.send_message(
                    "❌ ما عندك صلاحية فك الحظر.",
                    ephemeral=True
                )
            try:
                user = await self.bot.fetch_user(
                    int(user_id)
                )
                await interaction.guild.unban(
                    user
                )
                await interaction.response.send_message(
                    f"✅ تم فك الحظر عن **{user}**."
                )
            except Exception:
                await interaction.response.send_message(
                    "❌ لم أستطع فك الحظر. تأكد من الآيدي.",
                    ephemeral=True
                )
        callback.__name__ = name
        return app_commands.Command(
            name=name,
            description="اختصار لأمر فك الحظر",
            callback=callback
        )
    # =========================================================
    # إنشاء أمر timeout
    # =========================================================
    def create_timeout_command(self, name):
        async def callback(
            interaction: discord.Interaction,
            member: discord.Member,
            minutes: int,
            reason: str = "بدون سبب"
        ):
            if not interaction.user.guild_permissions.moderate_members:
                return await interaction.response.send_message(
                    "❌ ما عندك صلاحية إعطاء تايم أوت.",
                    ephemeral=True
                )
            if minutes < 1 or minutes > 40320:
                return await interaction.response.send_message(
                    "❌ المدة يجب أن تكون بين دقيقة و40320 دقيقة.",
                    ephemeral=True
                )
            try:
                await member.timeout(
                    timedelta(minutes=minutes),
                    reason=reason
                )
                await interaction.response.send_message(
                    f"🔇 تم إعطاء {member.mention} تايم أوت لمدة "
                    f"**{minutes} دقيقة**.\n"
                    f"**السبب:** {reason}"
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ البوت لا يملك صلاحية إعطاء تايم لهذا العضو.",
                    ephemeral=True
                )
        callback.__name__ = name
        return app_commands.Command(
            name=name,
            description="اختصار لأمر التايم",
            callback=callback
        )
    # =========================================================
    # إنشاء أمر untimeout
    # =========================================================
    def create_untimeout_command(self, name):
        async def callback(
            interaction: discord.Interaction,
            member: discord.Member
        ):
            if not interaction.user.guild_permissions.moderate_members:
                return await interaction.response.send_message(
                    "❌ ما عندك صلاحية إزالة التايم.",
                    ephemeral=True
                )
            try:
                await member.timeout(
                    None
                )
                await interaction.response.send_message(
                    f"🔊 تم إزالة التايم أوت عن {member.mention}."
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ البوت لا يملك الصلاحية.",
                    ephemeral=True
                )
        callback.__name__ = name
        return app_commands.Command(
            name=name,
            description="اختصار لأمر فك التايم",
            callback=callback
        )
    # =========================================================
    # إنشاء أمر clear
    # =========================================================
    def create_clear_command(self, name):
        async def callback(
            interaction: discord.Interaction,
            amount: int
        ):
            if not interaction.user.guild_permissions.manage_messages:
                return await interaction.response.send_message(
                    "❌ ما عندك صلاحية حذف الرسائل.",
                    ephemeral=True
                )
            if amount < 1 or amount > 100:
                return await interaction.response.send_message(
                    "❌ اختر رقمًا بين 1 و100.",
                    ephemeral=True
                )
            await interaction.response.defer(
                ephemeral=True
            )
            try:
                deleted = await interaction.channel.purge(
                    limit=amount
                )
                await interaction.followup.send(
                    f"🧹 تم حذف **{len(deleted)}** رسالة.",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ البوت لا يملك صلاحية حذف الرسائل.",
                    ephemeral=True
                )
        callback.__name__ = name
        return app_commands.Command(
            name=name,
            description="اختصار لأمر حذف الرسائل",
            callback=callback
        )
    # =========================================================
    # إنشاء الاختصار حسب الأمر
    # =========================================================
    def build_command(self, command_name, shortcut):
        if command_name == "kick":
            return self.create_kick_command(
                shortcut
            )
        if command_name == "ban":
            return self.create_ban_command(
                shortcut
            )
        if command_name == "unban":
            return self.create_unban_command(
                shortcut
            )
        if command_name == "timeout":
            return self.create_timeout_command(
                shortcut
            )
        if command_name == "untimeout":
            return self.create_untimeout_command(
                shortcut
            )
        if command_name == "clear":
            return self.create_clear_command(
                shortcut
            )
        return None
    # =========================================================
    # تحميل الاختصارات
    # =========================================================
    async def load_shortcuts(self, guild):
        con = self.get_db()
        rows = con.execute(
            """
            SELECT *
            FROM command_shortcuts
            WHERE guild_id = ?
            """,
            (
                guild.id,
            )
        ).fetchall()
        con.close()
        for row in rows:
            command_name = row["command_name"]
            for shortcut in [
                row["shortcut1"],
                row["shortcut2"],
                row["shortcut3"]
            ]:
                if not shortcut:
                    continue
                command = self.build_command(
                    command_name,
                    shortcut
                )
                if command is None:
                    continue
                try:
                    self.bot.tree.add_command(
                        command,
                        guild=guild,
                        override=True
                    )
                    self.dynamic_commands[
                        (guild.id, shortcut)
                    ] = command
                except Exception as e:
                    print(
                        f"❌ Shortcut Error: {shortcut}"
                    )
                    print(e)
    # =========================================================
    # حذف الاختصارات القديمة
    # =========================================================
    async def remove_guild_shortcuts(
        self,
        guild
    ):
        keys = [
            key
            for key in self.dynamic_commands
            if key[0] == guild.id
        ]
        for key in keys:
            command = self.dynamic_commands.pop(
                key
            )
            try:
                self.bot.tree.remove_command(
                    command.name,
                    guild=guild
                )
            except Exception:
                pass
    # =========================================================
    # /حدد_امر
    # =========================================================
    @app_commands.command(
        name="حدد_امر",
        description="تحديد اختصارات لأحد أوامر الإدارة"
    )
    @app_commands.describe(
        command="الأمر الأساسي",
        shortcut1="الاختصار الأول - إجباري",
        shortcut2="الاختصار الثاني - اختياري",
        shortcut3="الاختصار الثالث - اختياري"
    )
    @app_commands.choices(
        command=[
            app_commands.Choice(
                name="Kick - طرد",
                value="kick"
            ),
            app_commands.Choice(
                name="Ban - حظر",
                value="ban"
            ),
            app_commands.Choice(
                name="Unban - فك حظر",
                value="unban"
            ),
            app_commands.Choice(
                name="Timeout - تايم",
                value="timeout"
            ),
            app_commands.Choice(
                name="Untimeout - فك تايم",
                value="untimeout"
            ),
            app_commands.Choice(
                name="Clear - مسح",
                value="clear"
            )
        ]
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def set_shortcuts(
        self,
        interaction: discord.Interaction,
        command: app_commands.Choice[str],
        shortcut1: str,
        shortcut2: str = None,
        shortcut3: str = None
    ):
        shortcut1 = shortcut1.strip().lower()
        shortcut2 = (
            shortcut2.strip().lower()
            if shortcut2
            else None
        )
        shortcut3 = (
            shortcut3.strip().lower()
            if shortcut3
            else None
        )
        if not shortcut1:
            return await interaction.response.send_message(
                "❌ الاختصار الأول إجباري.",
                ephemeral=True
            )
        shortcuts = [
            shortcut1,
            shortcut2,
            shortcut3
        ]
        shortcuts = [
            x for x in shortcuts
            if x
        ]
        if len(set(shortcuts)) != len(shortcuts):
            return await interaction.response.send_message(
                "❌ لا يمكن تكرار نفس الاختصار.",
                ephemeral=True
            )
        # منع استخدام اسم أمر موجود
        for shortcut in shortcuts:
            if self.bot.tree.get_command(
                shortcut
            ):
                return await interaction.response.send_message(
                    f"❌ `{shortcut}` مستخدم مسبقًا كأمر.",
                    ephemeral=True
                )
        # حذف الاختصارات القديمة لهذا السيرفر
        await self.remove_guild_shortcuts(
            interaction.guild
        )
        con = self.get_db()
        con.execute(
            """
            INSERT INTO command_shortcuts
            (
                guild_id,
                command_name,
                shortcut1,
                shortcut2,
                shortcut3
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, command_name)
            DO UPDATE SET
                shortcut1 = excluded.shortcut1,
                shortcut2 = excluded.shortcut2,
                shortcut3 = excluded.shortcut3
            """,
            (
                interaction.guild.id,
                command.value,
                shortcut1,
                shortcut2,
                shortcut3
            )
        )
        con.commit()
        con.close()
        # إنشاء الاختصارات الجديدة
        for shortcut in shortcuts:
            dynamic_command = self.build_command(
                command.value,
                shortcut
            )
            if dynamic_command:
                self.bot.tree.add_command(
                    dynamic_command,
                    guild=interaction.guild,
                    override=True
                )
                self.dynamic_commands[
                    (
                        interaction.guild.id,
                        shortcut
                    )
                ] = dynamic_command
        # مزامنة أوامر السيرفر
        try:
            await self.bot.tree.sync(
                guild=interaction.guild
            )
        except Exception as e:
            print(
                f"❌ Shortcut Sync Error: {e}"
            )
        result = (
            f"**الأمر الأساسي:** `/{command.value}`\n\n"
            f"**الاختصار الأول:** `/{shortcut1}`\n"
            f"**الاختصار الثاني:** "
            f"`/{shortcut2}`\n"
            f"**الاختصار الثالث:** "
            f"`/{shortcut3}`"
        )
        await interaction.response.send_message(
            "✅ تم إعداد اختصارات الأمر بنجاح.\n\n"
            + result
        )
    # =========================================================
    # /اختصارات
    # =========================================================
    @app_commands.command(
        name="اختصارات",
        description="عرض اختصارات الأوامر"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def list_shortcuts(
        self,
        interaction: discord.Interaction
    ):
        con = self.get_db()
        rows = con.execute(
            """
            SELECT *
            FROM command_shortcuts
            WHERE guild_id = ?
            ORDER BY command_name
            """,
            (
                interaction.guild.id,
            )
        ).fetchall()
        con.close()
        if not rows:
            return await interaction.response.send_message(
                "📭 لا توجد اختصارات.",
                ephemeral=True
            )
        embed = discord.Embed(
            title="⚡ اختصارات الأوامر",
            color=discord.Color.blue()
        )
        for row in rows:
            shortcuts = [
                f"`/{row['shortcut1']}`"
            ]
            if row["shortcut2"]:
                shortcuts.append(
                    f"`/{row['shortcut2']}`"
                )
            if row["shortcut3"]:
                shortcuts.append(
                    f"`/{row['shortcut3']}`"
                )
            embed.add_field(
                name=f"/{row['command_name']}",
                value=" • ".join(shortcuts),
                inline=False
            )
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )
    # =========================================================
    # /حذف_اختصارات
    # =========================================================
    @app_commands.command(
        name="حذف_اختصارات",
        description="حذف اختصارات أمر معين"
    )
    @app_commands.describe(
        command="الأمر الذي تريد حذف اختصاراته"
    )
    @app_commands.choices(
        command=[
            app_commands.Choice(
                name="Kick - طرد",
                value="kick"
            ),
            app_commands.Choice(
                name="Ban - حظر",
                value="ban"
            ),
            app_commands.Choice(
                name="Unban - فك حظر",
                value="unban"
            ),
            app_commands.Choice(
                name="Timeout - تايم",
                value="timeout"
            ),
            app_commands.Choice(
                name="Untimeout - فك تايم",
                value="untimeout"
            ),
            app_commands.Choice(
                name="Clear - مسح",
                value="clear"
            )
        ]
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def delete_shortcuts(
        self,
        interaction: discord.Interaction,
        command: app_commands.Choice[str]
    ):
        await self.remove_guild_shortcuts(
            interaction.guild
        )
        con = self.get_db()
        cursor = con.execute(
            """
            DELETE FROM command_shortcuts
            WHERE guild_id = ?
            AND command_name = ?
            """,
            (
                interaction.guild.id,
                command.value
            )
        )
        con.commit()
        con.close()
        try:
            await self.bot.tree.sync(
                guild=interaction.guild
            )
        except Exception:
            pass
        if cursor.rowcount == 0:
            return await interaction.response.send_message(
                "❌ لا توجد اختصارات لهذا الأمر.",
                ephemeral=True
            )
        await interaction.response.send_message(
            f"✅ تم حذف اختصارات `/{command.value}`."
        )
    # =========================================================
    # عند تشغيل البوت
    # =========================================================
    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            try:
                await self.load_shortcuts(
                    guild
                )
                await self.bot.tree.sync(
                    guild=guild
                )
            except Exception as e:
                print(
                    f"❌ Failed loading shortcuts "
                    f"for {guild.name}: {e}"
                )
async def setup(bot):
    await bot.add_cog(
        Shortcuts(bot)
    )
