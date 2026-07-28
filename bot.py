import json
import os
from glob import glob

import aiofiles
import discord
from discord.ext import commands

from Cogs.ConfigCog import ConfigCog
from Cogs.LoggingCog import LoggingCog
from utility import dotdict


# extend bot class
class MyBot(commands.Bot):
    def __init__(self, use_cogs):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix='¤', intents=intents)
        self.synced = False
        self.use_cogs = use_cogs
        self.config = {}

    async def setup_hook(self):
        for config_file in glob('./config/*.json'):
            guild_id = os.path.splitext(os.path.basename(config_file))[0]
            try:
                guild_id = int(guild_id)
            except ValueError as e:
                print(f'Failed to parse guild_id: {e}')
            async with aiofiles.open(config_file, mode='r', encoding='utf-8') as file:
                content = await file.read()
            config_data = json.loads(content)
            self.config[guild_id] = dotdict(config_data)

        for use_cog in self.use_cogs:
            await self.add_cog(use_cog(self))

    async def on_ready(self):
        if self.synced:
            return

        await self.tree.sync()
        self.synced = True

        print('Bot ready to go!')

use_cogs = [
    ConfigCog,
    LoggingCog
]
bot = MyBot(use_cogs)
bot.run(os.getenv('BOT_TOKEN', ''))
