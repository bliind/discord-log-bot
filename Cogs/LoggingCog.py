import io

import aiohttp
import discord
from discord import (
    CategoryChannel,
    File,
    ForumChannel,
    Guild,
    Interaction,
    Member,
    Message,
    RawMemberRemoveEvent,
    TextChannel,
    Thread,
    User,
    app_commands,
)
from discord.ext import commands

from utility import make_embed


class LoggingCog(commands.Cog):
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

    def check_no_log(self, channel):
        no_log = self.bot.config[channel.guild.id].no_log_channels
        if channel.id in no_log:
            return True
        if getattr(channel, 'category_id', None) in no_log:
            return True
        if getattr(channel, 'parent_id', None) in no_log:
            return True

    def get_channel_type(self, channel: discord.abc.GuildChannel, symbol: bool = False):
        if isinstance(channel, discord.TextChannel):
            return '📄' if symbol else 'Text'
        if isinstance(channel, discord.VoiceChannel):
            return '🎤' if symbol else 'Voice'
        if isinstance(channel, discord.CategoryChannel):
            return '📁' if symbol else 'Category'
        if isinstance(channel, discord.ForumChannel):
            return '💬' if symbol else 'Forum'
        if isinstance(channel, discord.StageChannel):
            return '🎭' if symbol else 'Stage'

    def get_log_channel(self, guild_id: int, log_type: str):
        try:
            log_channel_id = self.bot.config[guild_id][log_type]
            log_channel = self.bot.get_channel(log_channel_id)
            assert log_channel
        except Exception:
            return False

        return log_channel

    @commands.Cog.listener()
    async def on_raw_member_remove(self, event: RawMemberRemoveEvent):
        log_channel = self.get_log_channel(event.guild_id, "user_logs_channel")
        if not log_channel:
            return

        embed = make_embed('red', event.user, f'{event.user.mention} left.')
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        log_channel = self.get_log_channel(member.guild.id, "user_logs_channel")
        if not log_channel:
            return

        created = round(int(member.created_at.timestamp()))
        description = f'{member.mention} joined.' \
                    f'\n\nAccount created <t:{created}:f>' \
                    f'\n(Roughly <t:{created}:R>)'

        embed = make_embed('green', member, description)
        await log_channel.send(embed=embed)

    # handles on_message_delete, on_thread_delete, and on_bulk_message_delete
    async def log_delete(self, message: Message, thread: bool = False, bulk: bool = False):
        if not message.guild:
            return

        log_channel = self.get_log_channel(message.guild.id, "message_deletes_channel")
        if not log_channel:
            return

        # skip bot messages
        if message.author.bot:
            return

        # ensure we're not in a no log channel
        if self.check_no_log(message.channel):
            return

        # start logging
        created = round(int(message.created_at.timestamp()))
        title = 'Messages bulk deleted' if bulk else 'Message deleted'
        description = f'in {message.channel.jump_url} by {message.author.mention}'

        if thread:
            title = 'Thread deleted'
            if isinstance(message.channel, Thread) and message.channel.parent is not None:
                description = f'"{message.channel.name}" in {message.channel.parent.jump_url}'

        embed = make_embed('red', message.author, description, title=title)
        embed.set_footer(text=f'Message ID: {message.id}')
        assert isinstance(embed.description, str)
        content = message.content

        # capture poll information, if relevant
        if message.poll:
            content += f'\n**poll**\n_Question:_ {message.poll.question}'
            for answer in message.poll.answers:
                content += f'\n_Answer:_ {answer.emoji} {answer.text}'

        # final pieces on the embed
        embed.description += f'\n\n**deleted message**\n{content}'
        embed.description += f'\n\n**originally posted**\n<t:{created}:f>'
        if message.reference:
            embed.description += f'\n\n**reply to**\n{message.reference.jump_url}'

        # now to (try to) log images attached
        files = []
        try:
            for file in message.attachments:
                async with (
                    aiohttp.ClientSession() as session,
                    session.get(file.url) as resp
                ):
                    if resp.status != 200:
                        raise Exception
                    data = io.BytesIO(await resp.read())
                    files.append(File(data, file.filename))
        except Exception:
            embed.description += f'\n_(There were {len(message.attachments)} images attached but discord deleted them already)_'

        if files:
            embed.description += '\n_(Above images were attached)_'

        # and now stickers, just in case
        if message.stickers:
            async with aiohttp.ClientSession() as session:
                async with session.get(message.stickers[0].url) as resp:
                    if resp.status == 200:
                        data = io.BytesIO(await resp.read())
                        files.append(File(data, f'{message.stickers[0].name}.png'))
                embed.description += '\n_(Above sticker was attached)_'

        await log_channel.send(embed=embed, files=files)

    @commands.Cog.listener()
    async def on_message_delete(self, message: Message):
        await self.log_delete(message)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: Thread):
        if thread.starter_message:
            await self.log_delete(thread.starter_message, thread=True)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[Message]):
        for message in messages:
            await self.log_delete(message, bulk=True)

    @commands.Cog.listener()
    async def on_message_edit(self, before: Message, after: Message):
        if not after.guild:
            return

        log_channel = self.get_log_channel(after.guild.id, "message_edits_channel")
        if not log_channel:
            return

        # skip bot messages
        if after.author.bot:
            return

        # ensure we're not in a no log channel
        if self.check_no_log(after.channel):
            return

        # make sure there's actually changes
        if before.content.strip() == after.content.strip():
            return

        description = f'in {after.channel.jump_url} by {after.author.mention}' \
                      f'\n\n**before**\n{before.content}' \
                      f'\n\n**after**\n{after.content}'
        embed = make_embed(
            color='yellow',
            member=after.author,
            description=description,
            title='Message edited',
            url=after.jump_url
        )

        await log_channel.send(embed=embed)

    async def log_member_changes(self, before: Member, after: Member):
        log_channel = self.get_log_channel(after.guild.id, "user_logs_channel")
        if not log_channel:
            return

        description = f'{after.mention} has been updated.\n'
        send = False

        # capture nick changes
        if before.nick != after.nick:
            description += f'\n🕵️‍♂️ changed nickname from **{before.nick}** to **{after.nick}**'
            send = True

        # capture timeout states
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until is not None:
                timed_out_until = round(int(after.timed_out_until.timestamp()))
                description += f'\n⏰ timed out until **<t:{timed_out_until}:f>**'
            if after.timed_out_until is None:
                description += '\n⏰ **timeout removed**'
            send = True

        # capture server-specific avatar changes
        if before.guild_avatar != after.guild_avatar:
            description += '\n🖼 updated server avatar\n'
            send = True

        # only send an update if something we cared about changed
        if send:
            change_embed = make_embed('blue', after, description)
            await log_channel.send(embed=change_embed)

    async def log_role_updates(self, before: Member, after: Member):
        log_channel = self.get_log_channel(after.guild.id, "user_logs_channel")
        if not log_channel:
            return

        description = f'{after.mention} has been updated.\n'

        b_roles = [r.name for r in before.roles]
        a_roles = [r.name for r in after.roles]
        added = [r for r in a_roles if r not in b_roles]
        removed = [r for r in b_roles if r not in a_roles]

        if added:
            description += '\nRoles added:'
            for role_name in added:
                description += f'\n✅ {role_name}'

        if removed:
            description += '\nRoles removed:'
            for role_name in removed:
                description += f'\n⛔ {role_name}'

        role_embed = make_embed('blue', after, description)
        await log_channel.send(embed=role_embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: Member, after: Member):
        # log changes to the actual account
        await self.log_member_changes(before, after)

        # log role updates
        await self.log_role_updates(before, after)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: Guild, user: User|Member):
        log_channel = self.get_log_channel(guild.id, "mod_logs_channel")
        if not log_channel:
            return

        embed = make_embed('red', user, f'{user.mention} has been banned.')
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: Guild, user: User|Member):
        log_channel = self.get_log_channel(guild.id, "mod_logs_channel")
        if not log_channel:
            return

        embed = make_embed('green', user, f'{user.mention} has been unbanned.')
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        log_channel = self.get_log_channel(channel.guild.id, "server_logs_channel")
        if not log_channel:
            return

        channel_type = self.get_channel_type(channel)
        description = f'### {channel_type} Channel created: {channel.jump_url}'
        description += f'\n\n- **Name**: {channel.name}'
        if channel.category:
            description += f'\n- **Category**: {channel.category.name}'
        description += f'\n- **ID**: {channel.id}'
        embed = make_embed('green', channel.guild, description)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        log_channel = self.get_log_channel(channel.guild.id, "server_logs_channel")
        if not log_channel:
            return

        channel_type = self.get_channel_type(channel)
        description = f'### {channel_type} Channel deleted: {channel.name}'
        if channel.category:
            description += f'\n- **Category**: {channel.category.name}'
        description += f'\n- **ID**: {channel.id}'
        embed = make_embed('red', channel.guild, description)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        log_channel = self.get_log_channel(after.guild.id, "server_logs_channel")
        if not log_channel:
            return

        overwrites = {}
        befores = {}
        for role in after.changed_roles:
            for ao in after.overwrites_for(role):
                if role.name not in overwrites: overwrites[role.name] = {}
                overwrites[role.name][ao[0]] = ao[1]
            for bo in before.overwrites_for(role):
                if role.name not in befores: befores[role.name] = {}
                befores[role.name][bo[0]] = bo[1]

        final = {}
        channel_type = self.get_channel_type(after)
        description = f'### {channel_type} Channel {after.jump_url} updated:'

        if before.name != after.name:
            description += f'\n\nName changed from `{before.name}` to `{after.name}`'

        for role, perms in overwrites.items():
            for perm, access in perms.items():
                try: old = befores[role][perm]
                except: old = None
                if old != access:
                    final[role] = {}
                    final[role][perm] = access

        if len(final.items()):
            description += '\n\n### Permissions Updated:'
        for r, ps in final.items():
            description += f'\n\n:arrow_right: **{r}**'
            for p, a in ps.items():
                emojis = {True: ':white_check_mark:', False: ':no_entry:', None: ':white_large_square:'}
                pr = p.replace('_', ' ').capitalize()
                description += f'\n{emojis[a]} {pr}'

        if getattr(after, 'slowmode_delay', None) and before.slowmode_delay != after.slowmode_delay:
            description += f'\n\n### Slowmode updated:\n{before.slowmode_delay} seconds -> {after.slowmode_delay} seconds'

        if (getattr(after, 'user_limit', None) or getattr(before, 'user_limit', None)) and before.user_limit != after.user_limit:
            if after.user_limit == 0:
                description += f'\n\nUser limit removed (was {before.user_limit})'
            elif before.user_limit == 0:
                description += f'\n\nUser limit set to {after.user_limit}'
            else:
                change = 'increased' if before.user_limit < after.user_limit else 'decreased'
                description += f'\n\nUser limit {change} from {before.user_limit} to {after.user_limit}'

        if '\n' in description:
            embed = make_embed('blurple', after.guild, description)
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        log_channel = self.get_log_channel(role.guild.id, "role_updates_channel")
        if not log_channel:
            return

        embed = make_embed('green', role.guild, f'Role created: {role.mention}')
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        log_channel = self.get_log_channel(role.guild.id, "role_updates_channel")
        if not log_channel:
            return

        embed = make_embed('red', role.guild, f'Role deleted: {role.name} ({role.id})')
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        log_channel = self.get_log_channel(after.guild.id, "role_updates_channel")
        if not log_channel:
            return

        description = f'**Role updated: {after.mention}**\n'
        thumb = None
        send = False

        if before.name != after.name:
            description += f'\n- Name changed from `{before.name}` to `{after.name}`'
            send = True
        if before.icon != after.icon:
            description += '\n- Role icon changed'
            send = True
        if after.icon and after.icon.url:
            thumb = after.icon.url
            send = True
        if before.color != after.color:
            bc = '#%02x%02x%02x' % before.color.to_rgb()
            ac = '#%02x%02x%02x' % after.color.to_rgb()
            description += f'\n- Color changed from `{bc}` to `{ac}`'
            send = True

        bp = {}
        changes = {}
        for b in before.permissions:
            bp[b[0]] = b[1]
        for a in after.permissions:
            if bp[a[0]] != a[1]:
                changes[a[0]] = a[1]

        emojis = {True: ':white_check_mark:', False: ':no_entry:', None: ':white_large_square:'}
        if len(changes) > 0:
            send = True
            description += '\n- Permissions updated:'
            for perm, access in changes.items():
                p = perm.replace('_', ' ').capitalize()
                description += f'\n{emojis[access]} {p}'

        if send:
            embed = make_embed('blurple', after.guild, description)
            if thumb:
                embed.set_thumbnail(url=thumb)

            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: Member, before, after):
        if before.channel == after.channel:
            return

        log_channel = self.get_log_channel(member.guild.id, "voice_logs_channel")
        if not log_channel:
            return

        if (after.channel and self.check_no_log(after.channel)) or (before.channel and self.check_no_log(before.channel)):
            return

        if not before.channel:
            embed = make_embed('blue', member, f'{member.mention} has joined <#{after.channel.id}>')
        elif not after.channel:
            embed = make_embed('dark_red', member, f'{member.mention} has left <#{before.channel.id}>')
        else:
            embed = make_embed('blurple', member, f'{member.mention} switched from <#{before.channel.id}> to <#{after.channel.id}>')

        await log_channel.send(embed=embed)

    ### Config commands
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
