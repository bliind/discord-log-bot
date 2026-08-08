from discord import (
    CategoryChannel,
    Interaction,
    Member,
    VoiceChannel,
    VoiceState,
    app_commands,
)
from discord.ext import commands

from utility import make_embed


class VoiceMakerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: Member, before: VoiceState, after: VoiceState
    ):
        created_voice_channels = self.bot.config[member.guild.id].created_voice_channels
        vc_creation_channel = self.bot.config[member.guild.id].vc_creation_channel
        vc_creation_category = self.bot.config[member.guild.id].vc_creation_category

        if created_voice_channels == None:
            self.bot.config[member.guild.id].created_voice_channels = []
            created_voice_channels = self.bot.config[member.guild.id].created_voice_channels

        if after.channel and after.channel.id == vc_creation_channel:
            if vc_creation_category:
                category = self.bot.get_channel(vc_creation_category)
            else:
                category = after.channel.category

            if category:
                new_channel = await category.create_voice_channel(
                    f"{member.display_name}'s channel", user_limit=4
                )
                await member.move_to(new_channel)

                created_voice_channels.append(new_channel.id)

                await self.bot.write_config_file(member.guild.id)

        if before.channel and before.channel.id in created_voice_channels:
            voice_channel = self.bot.get_channel(before.channel.id)
            if voice_channel and len(voice_channel.members) == 0:
                await voice_channel.delete(reason="Empty user-made voice channel")
                created_voice_channels.remove(before.channel.id)
                await self.bot.write_config_file(member.guild.id)

    @app_commands.command(name='set_vc_maker_channel', description='Set the channel for the Voice Chat Maker')
    async def set_vc_maker_channel_command(self, interaction: Interaction, channel: VoiceChannel):
        await interaction.response.defer(ephemeral=True)
        current_config = self.bot.config[interaction.guild_id]
        current_config['vc_creation_channel'] = channel.id

        await self.bot.write_config_file(interaction.guild_id)

        response = make_embed('green', self.bot.user, '', title=f'Voice Chat Maker Channel set: {channel.jump_url}')
        await interaction.followup.send(embed=response)

    @app_commands.command(name='set_vc_maker_category', description='Set the category for the Voice Chat Maker to make VCs in')
    async def set_vc_maker_category_command(self, interaction: Interaction, channel: CategoryChannel):
        await interaction.response.defer(ephemeral=True)
        current_config = self.bot.config[interaction.guild_id]
        current_config['vc_creation_category'] = channel.id

        await self.bot.write_config_file(interaction.guild_id)

        response = make_embed('green', self.bot.user, '', title=f'Voice Chat Maker Channel set: {channel.jump_url}')
        await interaction.followup.send(embed=response)
