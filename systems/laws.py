import discord
from discord import app_commands
from discord.ext import commands
import sqlite3

DB_FILE = "ctrp_system.db"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


# =========================================================
# LAW NUMBER SELECT
# =========================================================

class LawNumberSelect(discord.ui.Select):

    def __init__(self, bot):
        self.bot = bot

        options = [
            discord.SelectOption(
                label=f"القانون رقم {i}",
                value=str(i),
                emoji="📜"
            )
            for i in range(1, 16)
        ]

        super().__init__(
            placeholder="اختر رقم القانون",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        number = int(self.values[0])

        await interaction.response.send_modal(
            LawModal(number)
        )


class LawNumberView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=60)
        self.add_item(
            LawNumberSelect(bot)
        )


# =========================================================
# LAW MODAL
# =========================================================

class LawModal(discord.ui.Modal):

    def __init__(self, number: int):

        self.number = number

        super().__init__(
            title=f"القانون رقم {number}"
        )

        self.name_input = discord.ui.TextInput(
            label="اسم القانون",
            placeholder="مثال: قانون استخدام المركبات",
            max_length=100,
            required=True
        )

        self.text_input = discord.ui.TextInput(
            label="نص القانون",
            placeholder="اكتب نص القانون هنا...",
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=True
        )

        self.add_item(self.name_input)
        self.add_item(self.text_input)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        con = get_db()

        con.execute(
            """
            INSERT INTO laws
            (
                guild_id,
                number,
                name,
                text
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(guild_id, number)
            DO UPDATE SET
                name = excluded.name,
                text = excluded.text
            """,
            (
                interaction.guild.id,
                self.number,
                self.name_input.value,
                self.text_input.value
            )
        )

        con.commit()
        con.close()

        await interaction.response.send_message(
            (
                f"✅ تم حفظ القانون رقم **{self.number}**\n"
                f"📜 **{self.name_input.value}**"
            ),
            ephemeral=True
        )


# =========================================================
# LAWS MENU
# =========================================================

class LawsSelect(discord.ui.Select):

    def __init__(self, rows):

        options = []

        for row in rows:

            name = row["name"]

            if len(name) > 100:
                name = name[:97] + "..."

            options.append(
                discord.SelectOption(
                    label=name,
                    value=str(row["number"]),
                    emoji="📜"
                )
            )

        super().__init__(
            placeholder="اختر القانون",
            min_values=1,
            max_values=1,
            options=options
        )

        self.rows = rows

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        number = int(self.values[0])

        law = None

        for row in self.rows:

            if row["number"] == number:
                law = row
                break

        if not law:
            return await interaction.response.send_message(
                "❌ القانون غير موجود.",
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"📜 {law['name']}",
            description=law["text"],
            color=discord.Color.blue()
        )

        embed.set_footer(
            text=f"القانون رقم {law['number']}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


class LawsView(discord.ui.View):

    def __init__(self, rows):

        super().__init__(
            timeout=None
        )

        self.add_item(
            LawsSelect(rows)
        )


# =========================================================
# LAWS COG
# =========================================================

class Laws(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # =====================================================
    # إعداد قانون
    # =====================================================

    @app_commands.command(
        name="law",
        description="إضافة أو تعديل قانون"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def law(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.send_message(
            "اختر رقم القانون الذي تريد إضافته أو تعديله:",
            view=LawNumberView(self.bot),
            ephemeral=True
        )


    # =====================================================
    # إرسال بانل القوانين
    # =====================================================

    @app_commands.command(
        name="laws",
        description="إرسال بانل القوانين"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def laws(
        self,
        interaction: discord.Interaction
    ):

        con = get_db()

        rows = con.execute(
            """
            SELECT number, name, text
            FROM laws
            WHERE guild_id = ?
            AND number BETWEEN 1 AND 15
            ORDER BY number ASC
            """,
            (
                interaction.guild.id,
            )
        ).fetchall()

        con.close()

        if not rows:

            return await interaction.response.send_message(
                "❌ ما فيه قوانين محفوظة من 1 إلى 15.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="📜 قوانين السيرفر",
            description=(
                "اختر القانون من القائمة بالأسفل "
                "لعرض تفاصيله."
            ),
            color=discord.Color.blue()
        )

        await interaction.response.send_message(
            embed=embed,
            view=LawsView(rows)
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Laws(bot)
    )
