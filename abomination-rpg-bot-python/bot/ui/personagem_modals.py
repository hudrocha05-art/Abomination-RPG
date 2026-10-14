"""
Modais (formulários popup) usados na criação e edição de personagens e fichas.

/personagem criar: abre o modal PersonagemCriarNarrativoModal com os 4 campos
obrigatórios de lore (Nome, Raça, Elemento, Classe).

/ficha preencher e /personagem editar: abrem o modal FichaStatsModal com os 5
números de combate (HP, ATK, DEF, MST, VEL).
"""
import discord

from bot.db import personagens as db_personagens
from bot.ui.personagem_embeds import personagem_criado_embed, personagem_ficha_embed


class PersonagemCriarNarrativoModal(discord.ui.Modal, title="Novo Personagem"):
    nome = discord.ui.TextInput(
        label="Nome do Personagem",
        placeholder="Ex: Infinity",
        max_length=40,
        required=True,
    )
    raca = discord.ui.TextInput(
        label="Raça",
        placeholder="Ex: Humano, Elfo, Demônio...",
        max_length=40,
        required=True,
    )
    elemento = discord.ui.TextInput(
        label="Elemento",
        placeholder="Ex: Fogo, Trevas, Luz, Vento...",
        max_length=40,
        required=True,
    )
    classe = discord.ui.TextInput(
        label="Classe",
        placeholder="Ex: Guerreiro, Mago, Assassino...",
        max_length=40,
        required=True,
    )

    def __init__(self, stat_principal: str = "ATK"):
        super().__init__()
        self._stat_principal = stat_principal

    async def on_submit(self, interaction: discord.Interaction) -> None:
        nome_v = self.nome.value.strip()
        raca_v = self.raca.value.strip()
        elem_v = self.elemento.value.strip()
        classe_v = self.classe.value.strip()

        if not (nome_v and raca_v and elem_v and classe_v):
            await interaction.response.send_message(
                "❌ Todos os campos (Nome, Raça, Elemento e Classe) são obrigatórios.",
                ephemeral=True,
            )
            return

        try:
            personagem = db_personagens.criar_personagem(
                owner_id=str(interaction.user.id),
                nome=nome_v,
                raca=raca_v,
                elemento=elem_v,
                classe=classe_v,
                stat_principal=self._stat_principal,
            )
        except db_personagens.NomeDuplicadoError as e:
            await interaction.response.send_message(f"❌ **Nome Duplicado**\n{e}", ephemeral=True)
            return

        await interaction.response.send_message(embed=personagem_criado_embed(personagem))


class FichaStatsModal(discord.ui.Modal):
    hp = discord.ui.TextInput(
        label="Pontos de Vida (HP)",
        placeholder="Número inteiro maior que zero",
        required=True,
    )
    atk = discord.ui.TextInput(
        label="Ataque (ATK)",
        placeholder="Número inteiro (0 ou mais)",
        required=True,
    )
    defesa = discord.ui.TextInput(
        label="Defesa (DEF)",
        placeholder="Número inteiro (0 ou mais)",
        required=True,
    )
    mst = discord.ui.TextInput(
        label="Maestria (MST)",
        placeholder="Número inteiro (0 ou mais)",
        required=True,
    )
    vel = discord.ui.TextInput(
        label="Velocidade (VEL)",
        placeholder="Número inteiro (0 ou mais)",
        required=True,
    )

    def __init__(
        self,
        personagem_id: str,
        personagem_nome: str,
        hp_atual: int = 0,
        atk_atual: int = 0,
        def_atual: int = 0,
        mst_atual: int = 0,
        vel_atual: int = 0,
        titulo_prefixo: str = "Ficha de Stats",
    ):
        super().__init__(title=f"{titulo_prefixo}: {personagem_nome[:25]}")
        self._personagem_id = personagem_id
        self._personagem_nome = personagem_nome
        if hp_atual > 0:
            self.hp.default = str(hp_atual)
            self.atk.default = str(atk_atual)
            self.defesa.default = str(def_atual)
            self.mst.default = str(mst_atual)
            self.vel.default = str(vel_atual)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            hp_v = int(self.hp.value)
            atk_v = int(self.atk.value)
            def_v = int(self.defesa.value)
            mst_v = int(self.mst.value)
            vel_v = int(self.vel.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ **Stats Inválidos**\nHP, ATK, DEF, MST e VEL devem ser números inteiros.",
                ephemeral=True,
            )
            return

        if hp_v <= 0 or min(atk_v, def_v, mst_v, vel_v) < 0:
            await interaction.response.send_message(
                "❌ **Stats Inválidos**\nO HP deve ser maior que zero e os demais atributos não podem ser negativos.",
                ephemeral=True,
            )
            return

        db_personagens.atualizar_atributos(self._personagem_id, hp_v, atk_v, def_v, mst_v, vel_v)
        personagem = db_personagens.buscar_personagem_por_id(self._personagem_id)
        avatar_url = interaction.user.display_avatar.url
        await interaction.response.send_message(
            f"✅ **Ficha de {self._personagem_nome} configurada com sucesso!**",
            embed=personagem_ficha_embed(personagem, avatar_url),
        )


# Compatibilidade retroativa
PersonagemCriarModal = PersonagemCriarNarrativoModal
PersonagemEditarModal = FichaStatsModal

