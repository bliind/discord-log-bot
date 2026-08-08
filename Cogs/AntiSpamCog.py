import asyncio
import datetime
import io
from collections import defaultdict

import discord
from discord import File, Forbidden, Guild, Member, NotFound
from discord.ext import commands

from utility import make_embed
from Views.ReportView import ReportView


class AntiSpamCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.spam_tracker = defaultdict(list)
        self.currently_flagged_users = set()

    async def clean_expired_signatures(self, guild_id: int, user_id: int):
        config = self.bot.config[guild_id]

        await asyncio.sleep(config.spam_time_window)
        if user_id in self.currently_flagged_users:
            return

        if user_id in self.spam_tracker:
            now = datetime.datetime.now(datetime.timezone.utc)
            valid_start = now - datetime.timedelta(seconds=config.spam_time_window)

            self.spam_tracker[user_id] = [
                item for item in self.spam_tracker[user_id] if item[1] > valid_start
            ]

            if not self.spam_tracker[user_id]:
                del self.spam_tracker[user_id]

    async def flag_and_mute(self, user_id: int, guild: Guild, target_signature: str):
        await asyncio.sleep(2)

        config = self.bot.config[guild.id]
        member = guild.get_member(user_id)
        if not member:
            self.currently_flagged_users.discard(user_id)
            self.spam_tracker.pop(user_id, None)
            return

        cached_msgs = self.spam_tracker.get(user_id, [])
        messages_to_delete = [
            msg for sig, _, msg in cached_msgs if sig == target_signature
        ]

        self.spam_tracker.pop(user_id, None)
        self.currently_flagged_users.discard(user_id)

        preserved_files = []
        if messages_to_delete:
            sample_msg = messages_to_delete[0]
            for img in [a for a in sample_msg.attachments if a.width is not None]:
                try:
                    img_bytes = await img.read()
                    preserved_files.append(
                        File(io.BytesIO(img_bytes), filename=img.filename)
                    )
                except Exception as e: # noqa: BLE001
                    print(f'Failed to preserve attachment byte sequence: {e}')

        try:
            await member.timeout(
                datetime.timedelta(minutes=10),
                reason='Automated Spam Detection'
            )
        except Forbidden:
            print(f'Bot cannot mute {member.name}')

        channels_hit = set()
        for msg in messages_to_delete:
            channels_hit.add(msg.channel.mention)
            try:
                await msg.delete()
            except (NotFound, Forbidden):
                pass
            except Exception as e: # noqa: BLE001
                print(f'Could not delete message: {e}')

        log_channel = discord.utils.get(guild.text_channels, id=config.report_channel)
        mod_role = discord.utils.get(guild.roles, id=config.moderator_role)

        report_view = ReportView(timeout=None)
        if log_channel:
            channels_str = ', '.join(channels_hit)
            title = 'Automated Spam Detection'
            description = f'**User**\n{member.mention} ({member.id})\n\n' \
                        f'**Channels cleaned**:\n{channels_str}\n\n' \
                        'Attached images were spammed. User is under 10m timeout.'
            embed = make_embed('yellow', member, description, title=title)
            assert isinstance(embed.description, str)

            report_message = await log_channel.send(content=f'{mod_role.mention if mod_role else ""}', embed=embed, files=preserved_files, view=report_view)
            await report_view.wait()
            if report_view.value:
                u = report_view.buttonpusher
                assert isinstance(u, Member)

                userDM = make_embed('red', guild, f'### You have been banned from the {guild.name} Discord')
                userDM.add_field(name='Reason', value='Your account has been compromised and is sending spam/scam messages.')
                try:
                    await member.send(embed=userDM)
                except Exception as e: # noqa: BLE001
                    print(e)
                await asyncio.sleep(0.5)
                await guild.ban(member, reason='Compromised account', delete_message_seconds=86400)

                embed.description += f'\n\n✅ Banned by {u.mention} ({u.name})'
                embed.color = discord.Color.green()

            elif report_view.value == False:
                u = report_view.buttonpusher
                assert isinstance(u, Member)

                await member.timeout(None)
                embed.description += f'\n\n❌ {u.mention} ({u.name}) marked this a false report'
                embed.color = discord.Color.red()
            await report_message.edit(embed=embed, view=report_view)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        valid_images = [a for a in message.attachments if a.width is not None]
        if len(valid_images) != 4:
            return

        meta_elements = [f'{img.filename}_{img.size}' for img in valid_images]
        meta_elements.sort()
        payload_signature = '|'.join(meta_elements)

        user_id = message.author.id
        now = datetime.datetime.now(datetime.timezone.utc)

        if user_id in self.currently_flagged_users:
            # if already flagged just log
            self.spam_tracker[user_id].append((payload_signature, now, message))
            return

        recent_signatures = [item[0] for item in self.spam_tracker[user_id]]
        if payload_signature in recent_signatures and len(recent_signatures) > 1:
            # same 4 images send to at least 3 channels, flag em
            self.currently_flagged_users.add(user_id)
            self.spam_tracker[user_id].append((payload_signature, now, message))

            asyncio.create_task(self.flag_and_mute(user_id, message.guild, payload_signature))
            return

        self.spam_tracker[user_id].append((payload_signature, now, message))
        asyncio.create_task(self.clean_expired_signatures(message.guild.id, user_id))
