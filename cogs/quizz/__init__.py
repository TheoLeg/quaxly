import asyncio

import discord
from discord import app_commands
from discord.app_commands import Choice, Range
from discord.ext import commands

from cogs.quizz.session import QuizSession

_TYPE_MAP = {
    "all": ["flag", "capital", "map"],
    "flags": ["flag"],
    "capitals": ["capital"],
    "maps": ["map"],
}

_TYPE_LABELS = {
    "all": "🌐 All types",
    "flags": "🚩 Flags",
    "capitals": "🏛️ Capitals",
    "maps": "🗺️ Maps",
}

_DIFF_LABELS = {
    "easy": "🟢 Easy",
    "medium": "🟡 Medium",
    "hard": "🔴 Hard",
    "all": "🌈 All levels",
}


class Quizz(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[int, QuizSession] = {}

    @app_commands.command(name="quiz")
    @app_commands.guild_only()
    @app_commands.describe(
        type="kind of questions",
        difficulty="how well-known the countries are",
        questions="number of questions (5-30)",
    )
    @app_commands.choices(
        type=[
            Choice(name="🌐 All types", value="all"),
            Choice(name="🚩 Flags only", value="flags"),
            Choice(name="🏛️ Capitals only", value="capitals"),
            Choice(name="🗺️ Maps only", value="maps"),
        ],
        difficulty=[
            Choice(name="🟢 Easy (well-known countries)", value="easy"),
            Choice(name="🟡 Medium (less common countries)", value="medium"),
            Choice(name="🔴 Hard (obscure countries)", value="hard"),
            Choice(name="🌈 All levels mixed", value="all"),
        ],
    )
    async def quiz(
        self,
        interaction: discord.Interaction,
        type: Choice[str] = None,
        difficulty: Choice[str] = None,
        questions: Range[int, 5, 30] = 10,
    ):
        """Start a geography quiz in this channel"""
        channel = interaction.channel

        if self.sessions.get(channel.id) and self.sessions[channel.id].is_active:
            return await interaction.response.send_message(
                "a quiz is already running here", ephemeral=True
            )

        if not channel.permissions_for(interaction.guild.me).send_messages:
            return await interaction.response.send_message(
                "missing send message permission in this channel", ephemeral=True
            )

        type_value = type.value if type else "all"
        difficulty_value = difficulty.value if difficulty else "easy"
        q_types = _TYPE_MAP[type_value]

        embed = discord.Embed(
            title="🌍 Geography Quiz",
            description=(
                f"**Type:** {_TYPE_LABELS[type_value]}\n"
                f"**Difficulty:** {_DIFF_LABELS[difficulty_value]}\n"
                f"**Questions:** {questions}\n\n"
                "Starting in **3s…**"
            ),
            color=0x3498DB,
        )
        await interaction.response.send_message(embed=embed)

        await asyncio.sleep(3)

        session = QuizSession(
            channel, self.bot, q_types, difficulty_value, questions
        )
        self.sessions[channel.id] = session

        task = asyncio.create_task(session.start())
        session.task = task
        task.add_done_callback(lambda _: self.sessions.pop(channel.id, None))


async def setup(bot: commands.Bot):
    await bot.add_cog(Quizz(bot))
