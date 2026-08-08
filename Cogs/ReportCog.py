import io

import discord
from discord.ext import commands

from utility import get_member_image, make_embed
from Views.ReportView import ReportView


def clean_name(name):
    return name.replace('`', '\\`').replace('_', '\\_').replace('*', '\\*')

async def get_attachments(message):
    files = []
    for file in message.attachments:
        with io.BytesIO() as image_binary:
            await file.save(image_binary)
            image_binary.seek(0)
            files.append(discord.File(
                image_binary,
                filename=file.filename,
                spoiler=file.is_spoiler()
            ))

    return files

class ReportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        if payload.guild_id:
            config = self.bot.config[payload.guild_id]

            if str(payload.emoji) == config.report_emoji and \
                payload.channel_id not in config.no_report_channels:
                    await self.emoji_report(payload)
            return

    async def emoji_report(self, payload: discord.RawReactionActionEvent):
        if not payload.member:
            return

        chan = self.bot.get_channel(payload.channel_id)
        message = await chan.fetch_message(payload.message_id)
        reporter = await self.bot.fetch_user(payload.user_id)

        # remove react
        await message.remove_reaction(payload.emoji.name, reporter)

        # send DM to reporter
        description = 'Your report has been sent to the moderators!\n\nWe appreciate your efforts towards keeping the server clean!'
        embed = make_embed('blurple', payload.member.guild, description=description)
        await reporter.send(embed=embed)

        # send report to report channel
        await self.send_report(reporter, message)

    async def send_report(self, reporter: discord.Member, message: discord.Message, reason: str|None = None):
        if not message.guild:
            return

        description = f'{reporter.mention} ({clean_name(reporter.name)}) '
        description += f'has reported [this message]({message.jump_url}) from '
        description += f'{message.author.mention} ({clean_name(message.author.name)})!'

        if isinstance(message.author, discord.Member) and message.author.joined_at:
            joined_at = f'<t:{round(message.author.joined_at.timestamp())}>'
        else:
            joined_at = 'No Longer On Server'

        description += f'''\n
            **Reported User's Info:**
            Discord Tag: `{clean_name(message.author.name)}`
            Discord ID: `{message.author.id}`
            Account Created: <t:{round(message.author.created_at.timestamp())}>
            Joined Server: {joined_at}
        '''.replace(' '*8, '')

        description += f'''
            **Reported Message's Info:**
            Message ID: `{message.id}`
            Channel: <#{message.channel.id}>
            Created: <t:{round(message.created_at.timestamp())}>
            Attachments: `{len(message.attachments)}`
            Reactions: `{len(message.reactions)}`
            Content: `{message.content}`
        '''.replace(' '*8, '')

        if reason:
            description += f'''
                **Report Reason:**
                `{reason}`
            '''.replace(' '*8, '')

        embed = make_embed('light_gray', message.author, description)
        embed.set_author(name='Message Report Received', icon_url=get_member_image(reporter))
        assert isinstance(embed.description, str)

        report_view = ReportView(button_label='Handle', url=message.jump_url, timeout=None)
        files = await get_attachments(message)

        config = self.bot.config[message.guild.id]
        report_chan = self.bot.get_channel(config.report_channel)
        msg_content = f'<@&{config.moderator_role}>'

        report_message = await report_chan.send(msg_content, embed=embed, view=report_view, files=files)
        await report_view.wait()
        if report_view.value:
            buttonpusher = report_view.buttonpusher
            assert isinstance(buttonpusher, discord.Member)
            embed.description += f'\n\n✅ {buttonpusher.mention} ({buttonpusher.name}) is handling this'
            embed.color = discord.Color.green()
        elif report_view.value == False:
            buttonpusher = report_view.buttonpusher
            assert isinstance(buttonpusher, discord.Member)
            embed.description += f'\n\n❌ {buttonpusher.mention} ({buttonpusher.name}) marked this a false report'
            embed.color = discord.Color.red()
        await report_message.edit(embed=embed, view=report_view)
