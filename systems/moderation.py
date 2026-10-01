import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kick", description="طرد عضو من السيرفر")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "بدون سبب"):
        await member.kick(reason=reason)

        embed = discord.Embed(
            title="👢 تم طرد العضو",
            description=f"**العضو:** {member.mention}\n**السبب:** {reason}\n**بواسطة:** {interaction.user.mention}",
            color=discord.Color.orange()
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ban", description="حظر عضو من السيرفر")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "بدون سبب"):
        await member.ban(reason=reason)

        embed = discord.Embed(
            title="🔨 تم حظر العضو",
            description=f"**العضو:** {member.mention}\n**السبب:** {reason}\n**بواسطة:** {interaction.user.mention}",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unban", description="فك حظر عضو")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)

            await interaction.response.send_message(
                f"✅ تم فك الحظر عن **{user}**."
            )

        except Exception:
            await interaction.response.send_message(
                "❌ لم أستطع فك الحظر. تأكد من الآيدي.",
                ephemeral=True
            )

    @app_commands.command(name="timeout", description="إعطاء تايم أوت لعضو")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: int,
        reason: str = "بدون سبب"
    ):
        if minutes < 1 or minutes > 40320:
            return await interaction.response.send_message(
                "❌ المدة يجب أن تكون بين دقيقة و 40320 دقيقة.",
                ephemeral=True
            )

        await member.timeout(
            timedelta(minutes=minutes),
            reason=reason
        )

        await interaction.response.send_message(
            f"🔇 تم إعطاء {member.mention} تايم أوت لمدة **{minutes} دقيقة**.\n"
            f"**السبب:** {reason}"
        )

    @app_commands.command(name="untimeout", description="إزالة التايم أوت")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)

        await interaction.response.send_message(
            f"🔊 تم إزالة التايم أوت عن {member.mention}."
        )

    @app_commands.command(name="clear", description="حذف عدد من الرسائل")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount < 1 or amount > 100:
            return await interaction.response.send_message(
                "❌ اختر رقمًا بين 1 و100.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        deleted = await interaction.channel.purge(limit=amount)

        await interaction.followup.send(
            f"🧹 تم حذف **{len(deleted)}** رسالة.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Moderation(bot))
