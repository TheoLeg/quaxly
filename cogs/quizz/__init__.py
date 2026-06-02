import asyncio
import itertools

import discord
from discord import app_commands
from discord.app_commands import Choice, Range
from discord.ext import commands

from cogs.quizz.session import QuizSession

# key -> (emoji, display name, internal question type)
_BASE_TYPES = {
    "flags": ("🚩", "Flags", "flag"),
    "capitals": ("🏛️", "Capitals", "capital"),
    "maps": ("🗺️", "Maps", "map"),
    "shapes": ("🧩", "Shapes", "shape"),
}


def _build_type_choices():
    """Build every non-empty combination of categories dynamically.

    Returns the slash-command choices plus lookup maps from a combination
    value (e.g. "flags+maps") to its internal question types and its label.
    """
    keys = list(_BASE_TYPES)
    choices: list[Choice] = []
    type_map: dict[str, list[str]] = {}
    label_map: dict[str, str] = {}

    for size in range(1, len(keys) + 1):
        for combo in itertools.combinations(keys, size):
            value = "+".join(combo)
            type_map[value] = [_BASE_TYPES[k][2] for k in combo]
            if len(combo) == len(keys):
                label = "🌐 All types"
            else:
                label = " ".join(
                    f"{_BASE_TYPES[k][0]} {_BASE_TYPES[k][1]}" for k in combo
                )
            label_map[value] = label
            choices.append(Choice(name=label, value=value))

    return choices, type_map, label_map


_TYPE_CHOICES, _TYPE_MAP, _TYPE_LABELS = _build_type_choices()
_DEFAULT_TYPE = "+".join(_BASE_TYPES)

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
        type="kind of questions (any combination of categories)",
        difficulty="how well-known the countries are",
        questions="number of questions (5-30)",
    )
    @app_commands.choices(
        type=_TYPE_CHOICES,
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

        type_value = type.value if type else _DEFAULT_TYPE
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

        session = QuizSession(channel, self.bot, q_types, difficulty_value, questions)
        self.sessions[channel.id] = session

        task = asyncio.create_task(session.start())
        session.task = task
        task.add_done_callback(lambda _: self.sessions.pop(channel.id, None))


async def setup(bot: commands.Bot):
    await bot.add_cog(Quizz(bot))
