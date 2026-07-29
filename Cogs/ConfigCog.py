import json

from discord import CategoryChannel, ForumChannel, Interaction, TextChannel, app_commands
from discord.ext import commands

from utility import make_embed


class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logging_types = {
            "user_logs_channel": "User Logs",
            "mod_logs_channel": "Moderation Logs",
            "server_logs_channel": "Server Logs",
            "message_deletes_channel": "Message Deletes",
            "message_edits_channel": "Message Edits",
            "role_updates_channel": "Role Changes",
            "voice_logs_channel": "Voice Logs",
        }

    @app_commands.command(name='set_log_channel', description='Set the channel for a type of logs')
    async def set_log_channel_command(self, interaction: Interaction, log_type: str, channel: TextChannel):
        await interaction.response.defer(ephemeral=True)
        current_config = self.bot.config[interaction.guild_id]
        current_config[log_type] = channel.id

        await self.bot.write_config_file(interaction.guild_id)

        response = make_embed('green', self.bot.user, '', title='Log channel updated')
        response.add_field(name=log_type, value=channel.mention, inline=False)
        await interaction.followup.send(embed=response)

    @set_log_channel_command.autocomplete('log_type')
    async def auto_complete_log_type(self, interaction: Interaction, current: str):
        out = []
        for type, label in self.logging_types.items():
            if current.lower() in label.lower():
                out.append(app_commands.Choice(name=label, value=type))
        return out

    @app_commands.command(name='add_nolog_channel', description='Add a channel to not be logged')
    async def add_nolog_channel_command(self, interaction: Interaction, channel: CategoryChannel|ForumChannel|TextChannel):
        await interaction.response.defer(ephemeral=True)
        current_config = self.bot.config[interaction.guild_id]
        current_config['no_log_channels'].append(channel.id)

        await self.bot.write_config_file(interaction.guild_id)

        response = make_embed('green', self.bot.user, '', title='No log channel added')
        response.add_field(name='Channel added', value=channel.mention, inline=False)
        await interaction.followup.send(embed=response)

    @app_commands.command(name='remove_nolog_channel', description='Remove a channel from logging exemption')
    async def remove_nolog_channel_command(self, interaction: Interaction, channel: str):
        await interaction.response.defer(ephemeral=True)
        current_config = self.bot.config[interaction.guild_id]
        current_config['no_log_channels'].append(channel)

        await self.bot.write_config_file(interaction.guild_id)

        response = make_embed('green', self.bot.user, '', title='No log channel added')
        response.add_field(name='Channel added', value=channel, inline=False)
        await interaction.followup.send(embed=response)

    @remove_nolog_channel_command.autocomplete('channel')
    async def auto_complete_nolog_channel(self, interaction: Interaction, current: str):
        current_config = self.bot.config[interaction.guild_id]
        out = []

        for nolog_channel in current_config['no_log_channels']:
            if interaction.guild:
                channel = interaction.guild.get_channel(nolog_channel)
                if channel and current.lower() in channel.name.lower():
                    out.append(app_commands.Choice(name=f'#{channel.name}', value=str(channel.id)))
        return out
