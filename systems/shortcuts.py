import sqlite3
import copy
import discord

from discord import app_commands
from discord.ext import commands


DB_FILE = "ctrp_system.db"


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

    # =====================================================
    # GET ORIGINAL COMMAND
    # =====================================================

    def get_original_command(self, name):

        name = name.strip().lstrip("/")

        for command in self.bot.tree.get_commands():

            if not isinstance(command, app_commands.Command):
                continue

            if command.name == name:
                return command

        return None

    # =====================================================
    # NORMALIZE SHORTCUT
    # =====================================================

    def normalize_shortcut(self, value):

        if value is None:
            return None

        value = value.strip()

        # يسمح للمستخدم يكتب:
        # تايم
        # أو
        # /تايم

        if value.startswith("/"):
            value = value[1:]

        return value.strip()

    # =====================================================
    # ARABIC ONLY
    # =====================================================

    def is_arabic_char(self, char):

        return (
            "\u0600" <= char <= "\u06FF"
            or "\u0750" <= char <= "\u077F"
            or "\u08A0" <= char <= "\u08FF"
        )

    # =====================================================
    # VALIDATE SHORTCUT
    # =====================================================

    def validate_shortcut(self, value):

        if not value:
            return False, "❌ اكتب اسم الاختصار."

        if len(value) > 32:
            return False, "❌ الاختصار يجب ألا يتجاوز 32 حرفًا."

        # بدون مسافات
        if " " in value:
            return False, "❌ الاختصار يجب أن يكون كلمة واحدة بدون مسافات."

        # عربي فقط
        for char in value:

            if not self.is_arabic_char(char):

                return False, (
                    "❌ الاختصار عربي فقط.\n\n"
                    "ممنوع:\n"
                    "• الأرقام\n"
                    "• الحروف الإنجليزية\n"
                    "• _\n"
                    "• -\n"
                    "• الرموز"
                )

        return True, None

    # =====================================================
    # REMOVE SHORTCUTS
    # =====================================================

    def remove_command_shortcuts(
        self,
        guild,
        command_name
    ):

        key = (
            guild.id,
            command_name
        )

        old_commands = self.dynamic_commands.get(
            key,
            []
        )

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
    # CREATE SHORTCUT
    # =====================================================

    def create_shortcut(
        self,
        original,
        shortcut_name
    ):

        shortcut = copy.copy(original)

        try:
            shortcut._params = original._params.copy()
        except Exception:
            pass

        shortcut.name = shortcut_name

        shortcut.description = (
            f"اختصار للأمر /{original.name}"
        )

        return shortcut

    # =====================================================
    # LOAD SAVED SHORTCUTS
    # =====================================================

    async def load_guild_shortcuts(self, guild):

        con = self.get_db()

        rows = con.execute(
            """
            SELECT
                command_name,
                shortcut1,
                shortcut2,
                shortcut3
            FROM command_shortcuts
            WHERE guild_id = ?
            """,
            (guild.id,)
        ).fetchall()

        con.close()

        for row in rows:

            original = self.get_original_command(
                row["command_name"]
            )

            if not original:
                continue

            self.remove_command_shortcuts(
                guild,
                original.name
            )

            created = []

            for shortcut_name in (
                row["shortcut1"],
                row["shortcut2"],
                row["shortcut3"]
            ):

                if not shortcut_name:
                    continue

                shortcut_name = self.normalize_shortcut(
                    shortcut_name
                )

                valid, error = self.validate_shortcut(
                    shortcut_name
                )

                if not valid:
                    continue

                if shortcut_name == original.name:
                    continue

                # التأكد أن الاسم غير مستخدم
                existing = self.bot.tree.get_command(
                    shortcut_name,
                    guild=guild
                )

                if existing:
                    continue

                try:

                    shortcut = self.create_shortcut(
                        original,
                        shortcut_name
                    )

                    self.bot.tree.add_command(
                        shortcut,
                        guild=guild,
                        override=True
                    )

                    created.append(shortcut)

                    print(
                        f"🔗 Loaded shortcut: "
                        f"/{shortcut_name} -> "
                        f"/{original.name}"
                    )

                except Exception as e:

                    print(
                        f"❌ Failed shortcut "
                        f"/{shortcut_name}: {e}"
                    )

            self.dynamic_commands[
                (guild.id, original.name)
            ] = created

        try:

            await self.bot.tree.sync(
                guild=guild
            )

        except Exception as e:

            print(
                f"❌ Shortcut sync error "
                f"{guild.name}: {e}"
            )

    # =====================================================
    # SET SHORTCUTS
    # =====================================================

    @app_commands.command(
        name="حدد_امر",
        description="تحديد اختصارات لأي أمر في البوت"
    )
    @app_commands.describe(
        command="الأمر الأساسي",
        shortcut1="الاختصار الأول",
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

        if not interaction.guild:

            return await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )

        # إزالة /
        command = (
            command
            .strip()
            .lstrip("/")
        )

        original = self.get_original_command(
            command
        )

        if not original:

            return await interaction.response.send_message(
                f"❌ الأمر `/{command}` غير موجود.",
                ephemeral=True
            )

        # =================================================
        # PREPARE SHORTCUTS
        # =================================================

        shortcuts = []

        for value in (
            shortcut1,
            shortcut2,
            shortcut3
        ):

            if not value:
                continue

            value = self.normalize_shortcut(
                value
            )

            valid, error = self.validate_shortcut(
                value
            )

            if not valid:

                return await interaction.response.send_message(
                    error,
                    ephemeral=True
                )

            if value == original.name:

                return await interaction.response.send_message(
                    "❌ لا يمكن أن يكون الاختصار نفس الأمر.",
                    ephemeral=True
                )

            if value in shortcuts:

                return await interaction.response.send_message(
                    f"❌ الاختصار `/{value}` مكرر.",
                    ephemeral=True
                )

            shortcuts.append(value)

        if not shortcuts:

            return await interaction.response.send_message(
                "❌ لازم تحط اختصار واحد على الأقل.",
                ephemeral=True
            )

        # =================================================
        # RESERVED COMMANDS
        # =================================================

        reserved = {
            "حدد_امر",
            "اختصارات",
            "حذف_اختصارات"
        }

        for shortcut_name in shortcuts:

            if shortcut_name in reserved:

                return await interaction.response.send_message(
                    f"❌ `/{shortcut_name}` محجوز.",
                    ephemeral=True
                )

        # =================================================
        # CHECK CONFLICTS
        # =================================================

        for shortcut_name in shortcuts:

            existing_global = (
                self.get_original_command(
                    shortcut_name
                )
            )

            if existing_global:

                return await interaction.response.send_message(
                    f"❌ `/{shortcut_name}` مستخدم كأمر موجود.",
                    ephemeral=True
                )

            existing_guild = (
                self.bot.tree.get_command(
                    shortcut_name,
                    guild=interaction.guild
                )
            )

            if existing_guild:

                return await interaction.response.send_message(
                    f"❌ `/{shortcut_name}` مستخدم مسبقًا.",
                    ephemeral=True
                )

        # =================================================
        # SAVE
        # =================================================

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
                shortcuts[0],
                shortcuts[1]
                if len(shortcuts) > 1
                else None,
                shortcuts[2]
                if len(shortcuts) > 2
                else None
            )
        )

        con.commit()
        con.close()

        # =================================================
        # REMOVE OLD
        # =================================================

        self.remove_command_shortcuts(
            interaction.guild,
            original.name
        )

        # =================================================
        # CREATE NEW
        # =================================================

        created = []

        for shortcut_name in shortcuts:

            try:

                shortcut = self.create_shortcut(
                    original,
                    shortcut_name
                )

                self.bot.tree.add_command(
                    shortcut,
                    guild=interaction.guild,
                    override=True
                )

                created.append(shortcut)

            except Exception as e:

                print(
                    f"❌ Failed creating "
                    f"/{shortcut_name}: {e}"
                )

        self.dynamic_commands[
            (
                interaction.guild.id,
                original.name
            )
        ] = created

        # =================================================
        # SYNC
        # =================================================

        try:

            await self.bot.tree.sync(
                guild=interaction.guild
            )

        except Exception as e:

            return await interaction.response.send_message(
                "❌ حصل خطأ أثناء تحديث أوامر Discord.\n\n"
                f"`{e}`",
                ephemeral=True
            )

        # =================================================
        # SUCCESS
        # =================================================

        result = "\n".join(
            f"• `/{name}`"
            for name in shortcuts
        )

        await interaction.response.send_message(
            "✅ تم إنشاء اختصارات الأمر.\n\n"
            f"**الأمر الأساسي:** `/{original.name}`\n\n"
            f"**الاختصارات:**\n"
            f"{result}"
        )

    # =====================================================
    # LIST SHORTCUTS
    # =====================================================

    @app_commands.command(
        name="اختصارات",
        description="عرض جميع اختصارات الأوامر"
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
            SELECT
                command_name,
                shortcut1,
                shortcut2,
                shortcut3
            FROM command_shortcuts
            WHERE guild_id = ?
            ORDER BY command_name
            """,
            (interaction.guild.id,)
        ).fetchall()

        con.close()

        if not rows:

            return await interaction.response.send_message(
                "📭 لا توجد اختصارات.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🔗 اختصارات الأوامر",
            color=discord.Color.blue()
        )

        text = ""

        for row in rows:

            names = []

            for value in (
                row["shortcut1"],
                row["shortcut2"],
                row["shortcut3"]
            ):

                if value:

                    names.append(
                        f"`/{value}`"
                    )

            line = (
                f"**/{row['command_name']}**\n"
                f"{' • '.join(names)}\n\n"
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
        command="الأمر الأساسي"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def delete_shortcuts(
        self,
        interaction: discord.Interaction,
        command: str
    ):

        command = (
            command
            .strip()
            .lstrip("/")
        )

        original = self.get_original_command(
            command
        )

        if not original:

            return await interaction.response.send_message(
                f"❌ الأمر `/{command}` غير موجود.",
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
                "❌ هذا الأمر لا توجد له اختصارات.",
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

                await self.load_guild_shortcuts(
                    guild
                )

            except Exception as e:

                print(
                    f"❌ Failed loading shortcuts "
                    f"for {guild.name}: {e}"
                )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Shortcuts(bot)
    )
