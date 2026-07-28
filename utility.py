import datetime
from typing import Union

from discord import Color, Embed, Guild, Member, User


class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

def timestamp():
    now = datetime.datetime.now(datetime.timezone.utc)
    return round(now.timestamp())

def get_member_name(member: Union[Member,User]) -> str:
    attributes = ['nick', 'display_name', 'global_name']
    for attr in attributes:
        value = getattr(member, attr, None)
        if value:
            return value

    return member.name

def get_member_image(member: Union[Member,User]) -> Union[str,None]:
    attributes = ['guild_avatar', 'display_avatar', 'avatar']
    for attr in attributes:
        value = getattr(member, attr, None)
        if value:
            return value.url

def make_embed(color: str, member: Union[Member,User,Guild], description: str = '', **kwargs) -> Embed:
    color_method = getattr(Color, color, Color.greyple)
    embed = Embed(
        color=color_method(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        description=description,
        **kwargs
    )

    if isinstance(member, (Member, User)):
        embed.set_author(name=get_member_name(member), icon_url=get_member_image(member))
        embed.set_thumbnail(url=get_member_image(member))
        embed.set_footer(text=f'User ID: {member.id}')
    elif isinstance(member, Guild):
        if member.icon:
            embed.set_author(name=member.name, icon_url=member.icon.url)
            embed.set_thumbnail(url=member.icon.url)

    return embed

def readable_timedelta(delta: datetime.timedelta) -> str:
    hours = round(delta.total_seconds() / 3600)
    days = int(hours/24)
    remain_hours = int(hours - (days*24))

    user_time = ''
    if days > 0:
        user_time = f'{days} day{"s" if days > 1 else ""} '
    if remain_hours > 0:
        user_time += f'{hours} hour{"s" if hours > 1 else ""}'

    return user_time
