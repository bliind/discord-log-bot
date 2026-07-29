import json
import os
from glob import glob

import aiofiles
import discord
from discord.ext import commands

from Cogs.LoggingCog import LoggingCog
from Cogs.VoiceMakerCog import VoiceMakerCog
from utility import dotdict


# extend bot class
class MyBot(commands.Bot):
    def __init__(self, use_cogs):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="¤", intents=intents)
        self.synced = False
        self.use_cogs = use_cogs
        self.config = {}

    async def load_config(self, guild: int | None = None):
        if guild:
            config_files = [f"./config/{guild}.json"]
        else:
            config_files = glob("./config/*.json")

        for config_file in config_files:
            guild_id = os.path.splitext(os.path.basename(config_file))[0]
            try:
                guild_id = int(guild_id)
            except ValueError as e:
                print(f"Failed to parse guild_id: {e}")
            async with aiofiles.open(config_file, mode="r", encoding="utf-8") as file:
                content = await file.read()
            config_data = json.loads(content)
            self.config[guild_id] = dotdict(config_data)

    async def write_config_file(self, guild_id: int):
        config = self.config[guild_id]
        if not config:
            return

        config_file = f"./config/{guild_id}.json"
        async with aiofiles.open(config_file, mode="w", encoding="utf-8") as file:
            await file.write(json.dumps(config, indent=4))

    async def setup_hook(self):
        await self.load_config()

        for use_cog in self.use_cogs:
            await self.add_cog(use_cog(self))

    async def on_ready(self):
        if self.synced:
            return

        await self.tree.sync()
        self.synced = True

        print("Bot ready to go!")


use_cogs = [LoggingCog, VoiceMakerCog]
bot = MyBot(use_cogs)
bot.run(os.getenv("BOT_TOKEN", ""))
