"""
View com menu de seleção múltipla para os tipos de uma skill.
Permite combinar mais de um tipo (ex: Dano + Debuff) — diferente da
versão antiga, que só aceitava um tipo por skill.
"""
import discord

from bot.db import skills as db_skills

OPCOES_TIPO = [
    discord.SelectOption(label="Dano", value="DANO", emoji="💥"),
    discord.SelectOption(label="Cura", value="CURA", emoji="💚"),
    discord.SelectOption(label="Escudo", value="ESCUDO", emoji="🛡️"),
    discord.SelectOption(label="Buff", value="BUFF", emoji="✨"),
    discord.SelectOption(label="Debuff", value="DEBUFF", emoji="💀"),
    discord.SelectOption(label="Campo", value="CAMPO", emoji="🌐"),
    discord.SelectOption(label="Invocação", value="INVOCACAO", emoji="👥"),
    discord.SelectOption(label="Bloqueio (Guardião)", value="BLOQUEIO", emoji="🛡️"),
]


class SkillTipoSelect(discord.ui.Select):
    def __init__(self, ao_selecionar, tipos_marcados: set[str] | None = None):
        tipos_marcados = tipos_marcados or set()
        # Cria cópias das opções (não reutiliza os objetos do módulo) para não
        # vazar o estado de "marcado" entre usuários diferentes usando o comando.
        opcoes = [
            discord.SelectOption(
                label=o.label, value=o.value, emoji=o.emoji, default=o.value in tipos_marcados
            )
            for o in OPCOES_TIPO
        ]
        super().__init__(
            placeholder="Escolha um ou mais tipos para a habilidade...",
            min_values=1,
            max_values=len(opcoes),
            options=opcoes,
        )
        self._ao_selecionar = ao_selecionar

    async def callback(self, interaction: discord.Interaction):
        await self._ao_selecionar(interaction, self.values)


class SkillTipoView(discord.ui.View):
    """View simples que só mostra o menu de seleção de tipos."""

    def __init__(
        self,
        ao_selecionar,
        autor_id: int,
        tipos_marcados: set[str] | None = None,
        *,
        timeout: float = 60,
    ):
        super().__init__(timeout=timeout)
        self._autor_id = autor_id
        self.add_item(SkillTipoSelect(ao_selecionar, tipos_marcados))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._autor_id:
            await interaction.response.send_message(
                "❌ Só quem pediu essa ação pode escolher os tipos.", ephemeral=True
            )
            return False
        return True
