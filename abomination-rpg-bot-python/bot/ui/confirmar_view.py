"""
View de confirmação usada em ações destrutivas (ex: excluir personagem).
"""
import discord

from bot.db import personagens as db_personagens


class ConfirmarExclusaoView(discord.ui.View):
    def __init__(self, personagem_id: str, personagem_nome: str, autor_id: int, *, timeout: float = 30):
        super().__init__(timeout=timeout)
        self._personagem_id = personagem_id
        self._personagem_nome = personagem_nome
        self._autor_id = autor_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._autor_id:
            await interaction.response.send_message(
                "❌ Só quem pediu a exclusão pode confirmar.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Excluir", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        db_personagens.excluir_personagem(self._personagem_id)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"🗑️ Personagem **{self._personagem_nome}** foi excluído permanentemente.",
            view=self,
        )
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"↩️ Exclusão de **{self._personagem_nome}** cancelada.",
            view=self,
        )
        self.stop()

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
