import re
import sqlite3
import discord

from discord import app_commands
from discord.ext import commands

DB_FILE = "ctrp_system.db"

# =========================================================
# HELPERS
# =========================================================

VALID_NAME = re.compile(r"^[a-z0-9_-]{1,32}$", re.IGNORECASE)


class Shortcuts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.dynamic_commands = {}
        self.loaded = False

    # =====================================================
    # DATABASE
    # =====================================================

    def get_db(self):
        con = sqlite3.connect(DB_FILE)
        con.row_factory = sqlite3.Row
        return con

    def get_saved(self, guild_id, command_name):
        con = self.get_db()

        row = con.execute(
            """
            SELECT shortcut1, shortcut2, shortcut3
            FROM command_shortcuts
            WHERE guild_id = ?
            AND command_name = ?
            """,
            (guild_id, command_name)
        ).fetchone()

        con.close()
        return row

    # =====================================================
    # COMMAND DISCOVERY
    # =====================================================

    def get_all_commands(self):
        commands_list = []

        # أوامر البوت العامة
        for command in self.bot.tree.get_commands():
            if isinstance(command, app_commands.Command):
                commands_list.append(command)

        # إزالة التكرار
        result = {}
        for command in commands_list:
            result[command.name] = command

        return list(result.values())

    def find_command(self, name):
        for command in self.get_all_commands():
            if command.name == name:
                return command

        return None

    # =====================================================
    # REMOVE ONLY ONE COMMAND'S SHORTCUTS
    # =====================================================

    def remove_command_shortcuts(self, guild, command_name):
        key = (guild.id, command_name)

        old_commands = self.dynamic_commands.get(key, [])

        for command in old_commands:
            try:
                self.bot.tree.remove_command(
                    command.name,
                    guild=guild
                )
            except Exception:
                pass

        self.dynamic_commands[key] = []

    # =====================================================
    # CHECK NAME
    # =====================================================

    def valid_shortcut(self, name):
        if not name:
            return False

        name = name.strip()

        if len(name) > 32:
            return False

        if " " in name:
            return False

        return True

    # =====================================================
    # CREATE SHORTCUT
    # =====================================================

    def create_shortcut(self, guild, original, shortcut_name):

        async def callback(interaction: discord.Interaction, **kwargs):

            try:
                # نستخدم الأمر الأصلي مباشرة
                namespace = app_commands.Namespace(
                    interaction,
                    **kwargs
                )

                await original._invoke_with_namespace(
                    interaction,
                    namespace
                )

            except Exception as e:
                print(
                    f"❌ Shortcut error "
                    f"{shortcut_name} -> {original.name}: {e}"
                )

                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ حدث خطأ أثناء تنفيذ الأمر.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ حدث خطأ أثناء تنفيذ الأمر.",
                        ephemeral=True
                    )

        # إنشاء أمر جديد
        command = app_commands.Command(
            name=shortcut_name,
            description=f"اختصار للأمر /{original.name}",
            callback=callback
        )

        # نسخ خيارات الأمر الأصلي
        try:
            command._params = original._params.copy()
        except Exception:
            pass

        # نسخ الإعدادات المهمة
        try:
            command._guild_ids = [guild.id]
        except Exception:
            pass

        return command

    # =====================================================
    # LOAD SHORTCUTS
    # =====================================================

    async def load_guild_shortcuts(self, guild):

        con = self.get_db()

        rows = con.execute(
            """
            SELECT command_name, shortcut1, shortcut2, shortcut3
            FROM command_shortcuts
            WHERE guild_id = ?
            """,
            (guild.id,)
        ).fetchall()

        con.close()

        for row in rows:

            original = self.find_command(row["command_name"])

            if not original:
                continue

            key = (guild.id, original.name)

            self.remove_command_shortcuts(
                guild,
                original.name
            )

            created = []

            for shortcut in (
                row["shortcut1"],
                row["shortcut2"],
                row["shortcut3"]
            ):

                if not shortcut:
                    continue

                shortcut = shortcut.strip()

                if not self.valid_shortcut(shortcut):
                    continue

                # لا تسمح باختصار بنفس اسم الأمر
                if shortcut == original.name:
                    continue

                # لا تضيف إذا الاسم مستخدم مسبقًا
                existing = self.bot.tree.get_command(
                    shortcut,
                    guild=guild
                )

                if existing:
                    continue

                try:
                    command = self.create_shortcut(
                        guild,
                        original,
                        shortcut
                    )

                    self.bot.tree.add_command(
                        command,
                        guild=guild,
                        override=True
                    )

                    created.append(command)

                    print(
                        f"🔗 Shortcut loaded: "
                        f"/{shortcut} -> /{original.name}"
                    )

                except Exception as e:
                    print(
                        f"❌ Failed shortcut "
                        f"/{shortcut}: {e}"
                    )

            self.dynamic_commands[key] = created

        try:
            await self.bot.tree.sync(guild=guild)
        except Exception as e:
            print(
                f"❌ Shortcut sync error "
                f"{guild.name}: {e}"
            )

    # =====================================================
    # SET COMMAND
    # =====================================================

    @app_commands.command(
        name="حدد_امر",
        description="تحديد اختصارات لأي أمر في البوت"
    )
    @app_commands.describe(
        command="الأمر الأساسي",
        shortcut1="الاختصار الأول - إجباري",
        shortcut2="الاختصار الثاني - اختياري",
        shortcut3="الاختصار الثالث - اختياري"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def set_shortcuts(
        self,
        interaction: discord.Interaction,
        command: str,
        shortcut1: str,
        shortcut2: str = None,
        shortcut3: str = None
    ):

        original = self.find_command(command)

        if not original:
            return await interaction.response.send_message(
                "❌ هذا الأمر غير موجود في البوت.",
                ephemeral=True
            )

        shortcuts = [
            shortcut1,
            shortcut2,
            shortcut3
        ]

        cleaned = []

        for shortcut in shortcuts:

            if not shortcut:
                continue

            shortcut = shortcut.strip()

            if not self.valid_shortcut(shortcut):
                return await interaction.response.send_message(
                    f"❌ الاختصار `{shortcut}` غير صالح.",
                    ephemeral=True
                )

            if shortcut == original.name:
                return await interaction.response.send_message(
                    "❌ لا يمكن أن يكون الاختصار نفس اسم الأمر.",
                    ephemeral=True
                )

            if shortcut in cleaned:
                return await interaction.response.send_message(
                    f"❌ الاختصار `{shortcut}` مكرر.",
                    ephemeral=True
                )

            cleaned.append(shortcut)

        # التأكد أن الاختصارات غير مستخدمة
        for shortcut in cleaned:

            existing = self.bot.tree.get_command(
                shortcut,
                guild=interaction.guild
            )

            if existing and existing.name != shortcut:
                return await interaction.response.send_message(
                    f"❌ الاختصار `{shortcut}` مستخدم مسبقًا.",
                    ephemeral=True
                )

            # حتى لو كان الأمر موجودًا بنفس الاسم
            if existing:
                return await interaction.response.send_message(
                    f"❌ الأمر `/{shortcut}` موجود مسبقًا.",
                    ephemeral=True
                )

        # حفظ قاعدة البيانات
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
                original.name,
                cleaned[0],
                cleaned[1] if len(cleaned) > 1 else None,
                cleaned[2] if len(cleaned) > 2 else None
            )
        )

        con.commit()
        con.close()

        # حذف اختصارات هذا الأمر فقط
        self.remove_command_shortcuts(
            interaction.guild,
            original.name
        )

        created = []

        for shortcut in cleaned:

            try:
                dynamic = self.create_shortcut(
                    interaction.guild,
                    original,
                    shortcut
                )

                self.bot.tree.add_command(
                    dynamic,
                    guild=interaction.guild,
                    override=True
                )

                created.append(dynamic)

            except Exception as e:
                print(
                    f"❌ Failed creating /{shortcut}: {e}"
                )

        self.dynamic_commands[
            (interaction.guild.id, original.name)
        ] = created

        try:
            await self.bot.tree.sync(
                guild=interaction.guild
            )
        except Exception as e:
            return await interaction.response.send_message(
                f"⚠️ تم الحفظ لكن حدث خطأ أثناء المزامنة:\n`{e}`",
                ephemeral=True
            )

        text = (
            f"**الأمر الأساسي:** `/{original.name}`\n"
            f"**الاختصارات:**\n"
        )

        for shortcut in cleaned:
            text += f"• `/{shortcut}`\n"

        await interaction.response.send_message(
            "✅ تم تحديد الاختصارات بنجاح.\n\n" + text
        )

    # =====================================================
    # SHOW SHORTCUTS
    # =====================================================

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
            SELECT command_name, shortcut1, shortcut2, shortcut3
            FROM command_shortcuts
            WHERE guild_id = ?
            ORDER BY command_name
            """,
            (interaction.guild.id,)
        ).fetchall()

        con.close()

        if not rows:
            return await interaction.response.send_message(
                "📭 لا توجد اختصارات محددة.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🔗 اختصارات الأوامر",
            color=discord.Color.blue()
        )

        text = ""

        for row in rows:

            shortcuts = []

            for value in (
                row["shortcut1"],
                row["shortcut2"],
                row["shortcut3"]
            ):
                if value:
                    shortcuts.append(f"`/{value}`")

            line = (
                f"**/{row['command_name']}**\n"
                f"{' • '.join(shortcuts)}\n\n"
            )

            if len(text) + len(line) > 3900:
                embed.add_field(
                    name="الأوامر",
                    value=text,
                    inline=False
                )
                text = ""

            text += line

        if text:
            embed.add_field(
                name="الأوامر",
                value=text,
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # DELETE SHORTCUTS
    # =====================================================

    @app_commands.command(
        name="حذف_اختصارات",
        description="حذف اختصارات أمر معين"
    )
    @app_commands.describe(
        command="الأمر الذي تريد حذف اختصاراته"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def delete_shortcuts(
        self,
        interaction: discord.Interaction,
        command: str
    ):

        original = self.find_command(command)

        if not original:
            return await interaction.response.send_message(
                "❌ هذا الأمر غير موجود.",
                ephemeral=True
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
                original.name
            )
        )

        con.commit()
        con.close()

        if cursor.rowcount == 0:
            return await interaction.response.send_message(
                "❌ هذا الأمر ليس لديه اختصارات.",
                ephemeral=True
            )

        self.remove_command_shortcuts(
            interaction.guild,
            original.name
        )

        try:
            await self.bot.tree.sync(
                guild=interaction.guild
            )
        except Exception:
            pass

        await interaction.response.send_message(
            f"✅ تم حذف اختصارات `/{original.name}`."
        )

    # =====================================================
    # READY
    # =====================================================

    @commands.Cog.listener()
    async def on_ready(self):

        if self.loaded:
            return

        self.loaded = True

        for guild in self.bot.guilds:

            try:
                await self.load_guild_shortcuts(guild)

            except Exception as e:
                print(
                    f"❌ Failed loading shortcuts "
                    f"for {guild.name}: {e}"
                )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(Shortcuts(bot))
