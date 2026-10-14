"""
Modal usado para criar/editar os dados textuais de uma skill
(Nome, Cooldown, Descrição, Custo de HP). Os tipos são escolhidos antes,
por um menu de seleção (SkillTipoView), pois um Modal só aceita 4-5 campos.
"""
import discord

from bot.db import skills as db_skills
from bot.ui.skill_embeds import skill_criada_embed


class SkillCriarModal(discord.ui.Modal):
    nome = discord.ui.TextInput(
        label="Nome da Habilidade",
        placeholder="Ex: Bola de Fogo",
        max_length=32,
        required=True,
    )
    cooldown = discord.ui.TextInput(
        label="Recarga (turnos)",
        placeholder="Número (padrão 0)",
        required=False,
    )
    descricao = discord.ui.TextInput(
        label="Descrição",
        style=discord.TextStyle.paragraph,
        placeholder="O que a habilidade faz...",
        max_length=200,
        required=False,
    )
    custo_vida = discord.ui.TextInput(
        label="Custo de HP",
        placeholder="Número (padrão 0)",
        required=False,
    )

    def __init__(self, personagem_id: str, personagem_nome: str, tipos: list[str]):
        super().__init__(title=f"Nova Skill: {personagem_nome[:25]}")
        self._personagem_id = personagem_id
        self._tipos = tipos

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cooldown_v = 0
        custo_v = 0
        try:
            if self.cooldown.value:
                cooldown_v = int(self.cooldown.value)
            if self.custo_vida.value:
                custo_v = int(self.custo_vida.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ Recarga e Custo de HP devem ser números inteiros.", ephemeral=True
            )
            return

        if cooldown_v < 0 or custo_v < 0:
            await interaction.response.send_message(
                "❌ Recarga e Custo de HP não podem ser negativos.", ephemeral=True
            )
            return

        skill = db_skills.criar_skill(
            personagem_id=self._personagem_id,
            nome=self.nome.value.strip(),
            tipos=self._tipos,
            cooldown=cooldown_v,
            descricao=self.descricao.value.strip() or None,
            custo_vida=custo_v,
        )
        await interaction.response.send_message(embed=skill_criada_embed(skill))


class SkillEditarModal(discord.ui.Modal):
    nome = discord.ui.TextInput(label="Nome da Habilidade", max_length=32, required=True)
    cooldown = discord.ui.TextInput(label="Recarga (turnos)", required=False)
    descricao = discord.ui.TextInput(
        label="Descrição", style=discord.TextStyle.paragraph, max_length=200, required=False
    )
    custo_vida = discord.ui.TextInput(label="Custo de HP", required=False)

    def __init__(self, skill_id: str, tipos: list[str], nome_atual: str, cooldown_atual: int,
                 descricao_atual: str | None, custo_vida_atual: int):
        super().__init__(title=f"Editando: {nome_atual[:25]}")
        self._skill_id = skill_id
        self._tipos = tipos
        self.nome.default = nome_atual
        self.cooldown.default = str(cooldown_atual)
        self.descricao.default = descricao_atual or ""
        self.custo_vida.default = str(custo_vida_atual)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cooldown_v = 0
        custo_v = 0
        try:
            if self.cooldown.value:
                cooldown_v = int(self.cooldown.value)
            if self.custo_vida.value:
                custo_v = int(self.custo_vida.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ Recarga e Custo de HP devem ser números inteiros.", ephemeral=True
            )
            return

        if cooldown_v < 0 or custo_v < 0:
            await interaction.response.send_message(
                "❌ Recarga e Custo de HP não podem ser negativos.", ephemeral=True
            )
            return

        db_skills.atualizar_skill(
            self._skill_id,
            nome=self.nome.value.strip(),
            tipos=self._tipos,
            cooldown=cooldown_v,
            descricao=self.descricao.value.strip() or None,
            custo_vida=custo_v,
        )
        await interaction.response.send_message(
            "✅ **Habilidade Atualizada**\nOs dados foram atualizados com sucesso.", ephemeral=True
        )
