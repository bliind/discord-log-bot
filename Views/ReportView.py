import discord


class ReportView(discord.ui.View):
    def __init__(self, button_label: str, timeout: float|None = None, url: str|None = None):
        super().__init__(timeout=timeout)
        self.value = None
        self.buttonpusher = None
        self.handle.label = button_label

        if url:
            jump_button = discord.ui.Button(label='Jump to Message', style=discord.ButtonStyle.gray, url=url)
            self.add_item(jump_button)

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.label != 'Jump to Message':
                item.disabled = True

    @discord.ui.button(style=discord.ButtonStyle.green)
    async def handle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = True
        self.buttonpusher = interaction.user
        await self.on_timeout()
        self.stop()

    @discord.ui.button(label='False Report', style=discord.ButtonStyle.red)
    async def falsereport(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = False
        self.buttonpusher = interaction.user
        await self.on_timeout()
        self.stop()
