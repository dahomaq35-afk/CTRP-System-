import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from datetime import datetime, timezone

DB_FILE = "ctrp_system.db"


class Applications(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # DATABASE
    # =====================================================

    def get_db(self):
        con = sqlite3.connect(DB_FILE)
        con.row_factory = sqlite3.Row
        return con

    # =====================================================
    # /apply
    # =====================================================

    @app_commands.command(
        name="apply",
        description="تقديم طلب"
    )
    @app_commands.describe(
        application_type="نوع التقديم",
        content="محتوى التقديم"
    )
    async def apply(
        self,
        interaction: discord.Interaction,
        application_type: str,
        content: str
    ):

        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )

        application_type = application_type.strip()
        content = content.strip()

        if not application_type:
            return await interaction.response.send_message(
                "❌ اكتب نوع التقديم.",
                ephemeral=True
            )

        if not content:
            return await interaction.response.send_message(
                "❌ اكتب محتوى التقديم.",
                ephemeral=True
            )

        con = self.get_db()

        con.execute(
            """
            INSERT INTO applications
            (
                guild_id,
                user_id,
                application_type,
                content,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                interaction.guild.id,
                interaction.user.id,
                application_type,
                content,
                "pending",
                datetime.now(timezone.utc).isoformat()
            )
        )

        con.commit()
        con.close()

        await interaction.response.send_message(
            "✅ تم إرسال طلبك بنجاح.\n"
            "📋 حالة الطلب: **قيد المراجعة**",
            ephemeral=True
        )

    # =====================================================
    # /applications
    # =====================================================

    @app_commands.command(
        name="applications",
        description="عرض آخر الطلبات"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def applications(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )

        con = self.get_db()

        rows = con.execute(
            """
            SELECT
                id,
                user_id,
                application_type,
                content,
                status,
                created_at
            FROM applications
            WHERE guild_id = ?
            ORDER BY id DESC
            LIMIT 10
            """,
            (
                interaction.guild.id,
            )
        ).fetchall()

        con.close()

        if not rows:
            return await interaction.response.send_message(
                "📭 لا توجد طلبات محفوظة.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="📝 آخر الطلبات",
            description="آخر 10 طلبات تم تقديمها في السيرفر.",
            color=discord.Color.blue()
        )

        for row in rows:

            content = row["content"]

            if len(content) > 500:
                content = content[:497] + "..."

            status = row["status"]

            if status == "pending":
                status_text = "🟡 قيد المراجعة"

            elif status == "accepted":
                status_text = "🟢 مقبول"

            elif status == "rejected":
                status_text = "🔴 مرفوض"

            else:
                status_text = status

            embed.add_field(
                name=(
                    f"#{row['id']}・"
                    f"{row['application_type']}"
                ),
                value=(
                    f"**العضو:** <@{row['user_id']}>\n"
                    f"**الحالة:** {status_text}\n"
                    f"**الطلب:** {content}"
                ),
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # /application_status
    # =====================================================

    @app_commands.command(
        name="application_status",
        description="تغيير حالة طلب"
    )
    @app_commands.describe(
        application_id="رقم الطلب",
        status="الحالة الجديدة"
    )
    @app_commands.choices(
        status=[
            app_commands.Choice(
                name="قيد المراجعة",
                value="pending"
            ),
            app_commands.Choice(
                name="مقبول",
                value="accepted"
            ),
            app_commands.Choice(
                name="مرفوض",
                value="rejected"
            )
        ]
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def application_status(
        self,
        interaction: discord.Interaction,
        application_id: int,
        status: app_commands.Choice[str]
    ):

        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )

        con = self.get_db()

        row = con.execute(
            """
            SELECT user_id
            FROM applications
            WHERE id = ?
            AND guild_id = ?
            """,
            (
                application_id,
                interaction.guild.id
            )
        ).fetchone()

        if not row:
            con.close()

            return await interaction.response.send_message(
                "❌ لم يتم العثور على هذا الطلب.",
                ephemeral=True
            )

        con.execute(
            """
            UPDATE applications
            SET status = ?
            WHERE id = ?
            AND guild_id = ?
            """,
            (
                status.value,
                application_id,
                interaction.guild.id
            )
        )

        con.commit()
        con.close()

        status_names = {
            "pending": "🟡 قيد المراجعة",
            "accepted": "🟢 مقبول",
            "rejected": "🔴 مرفوض"
        }

        await interaction.response.send_message(
            f"✅ تم تحديث الطلب **#{application_id}**.\n"
            f"الحالة الجديدة: "
            f"**{status_names.get(status.value, status.value)}**"
        )

    # =====================================================
    # ERROR HANDLER
    # =====================================================

    @application_status.error
    async def application_status_error(
        self,
        interaction: discord.Interaction,
        error
    ):

        if isinstance(
            error,
            app_commands.errors.MissingPermissions
        ):
            return await interaction.response.send_message(
                "❌ ما عندك صلاحية لإدارة الطلبات.",
                ephemeral=True
            )

        if isinstance(
            error,
            app_commands.errors.TransformerError
        ):
            return await interaction.response.send_message(
                "❌ رقم الطلب غير صحيح.",
                ephemeral=True
            )

        raise error


# =====================================================
# SETUP
# =====================================================

async def setup(bot):

    await bot.add_cog(
        Applications(bot)
    )
