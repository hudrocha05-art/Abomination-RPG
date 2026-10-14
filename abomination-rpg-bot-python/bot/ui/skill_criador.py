"""
Painel de criação e edição de habilidades.

Fluxo:
1. /skill criar abre o formulário inicial (Nome, Recarga, Descrição, Custo de HP, Roll de Acerto).
2. O bot responde com o painel interativo:
   - Menu multiselect para marcar os tipos da habilidade (ex: Dano + Debuff + Buff).
   - Menu para escolher o Alcance/Alvo (Único, Adjacentes, Área, Todos).
   - Botão para alterar o Roll de Acerto (ex: d20, d20+3, W20).
   - Botão para configurar os subtipos de Dano (se DANO estiver marcado).
   - Botões para Finalizar e Salvar ou Cancelar.
"""
import copy

import discord

from bot import dano as D
from bot.db import skills as db_skills
from bot.ui.dano_painel import DanoConfigView
from bot.ui.skill_embeds import skill_criada_embed, EMOJI_TIPO


class AlterarRollModal(discord.ui.Modal, title="Definir Roll de Acerto"):
    roll = discord.ui.TextInput(
        label="Dado de Acerto (Roll)",
        placeholder="Ex: d20, d20+3, W20",
        max_length=20,
        required=True,
    )

    def __init__(self, painel: "SkillCriadorView"):
        super().__init__()
        self._painel = painel
        self.roll.default = painel.roll

    async def on_submit(self, interaction: discord.Interaction) -> None:
        val = self.roll.value.strip()
        self._painel.roll = val or "d20"
        self._painel.montar_componentes()
        await interaction.response.edit_message(embed=self._painel.montar_embed(), view=self._painel)


class SkillInfoModal(discord.ui.Modal):
    nome = discord.ui.TextInput(
        label="Nome da Habilidade", placeholder="Ex: Bola de Fogo", max_length=32, required=True
    )
    cooldown = discord.ui.TextInput(
        label="Tempo de Recarga (Cooldown em turnos)", placeholder="Número (padrão é 0)", required=False
    )
    descricao = discord.ui.TextInput(
        label="Descrição da Habilidade (Flavor)",
        style=discord.TextStyle.paragraph,
        placeholder="O que a habilidade faz narrativamente...",
        max_length=200,
        required=True,
    )
    custo_vida = discord.ui.TextInput(label="Custo de HP (Vida)", required=False)
    roll = discord.ui.TextInput(
        label="Dado de Acerto (Roll)",
        placeholder="Ex: d20, d20+3, W20",
        default="d20",
        max_length=20,
        required=True,
    )

    def __init__(
        self,
        personagem_id: str,
        personagem_nome: str,
        tipos: list[str],
        nivel: int | None,
        skill: dict | None = None,
    ):
        prefixo = "Editar Skill" if skill else "Nova Skill"
        super().__init__(title=f"{prefixo} - {personagem_nome[:30]}")
        self._skill = skill
        if skill:
            self.nome.default = skill["nome"]
            self.cooldown.default = str(skill["cooldown"])
            self.descricao.default = skill["descricao"] or ""
            self.custo_vida.default = str(skill["dados"].get("custo_vida") or 0)
            self.roll.default = str(skill["dados"].get("roll") or "d20")
        self._personagem_id = personagem_id
        self._personagem_nome = personagem_nome
        self._tipos = list(tipos) if tipos else ["DANO"]
        self._nivel = nivel
        bloqueio = "BLOQUEIO" in self._tipos
        self.custo_vida.required = bloqueio
        self.custo_vida.placeholder = "Obrigatório para Bloqueio (ex: 5)" if bloqueio else "Opcional"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            cooldown_v = int(self.cooldown.value.strip()) if self.cooldown.value.strip() else 0
            if cooldown_v < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ **Cooldown Inválido**\nO tempo de recarga deve ser um número inteiro maior ou igual a zero.",
                ephemeral=True,
            )
            return

        try:
            custo_v = int(self.custo_vida.value.strip()) if self.custo_vida.value.strip() else 0
            if custo_v < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ **Custo de Vida Inválido**\nO custo de vida deve ser um número inteiro maior ou igual a zero.",
                ephemeral=True,
            )
            return

        roll_v = self.roll.value.strip() or "d20"
        view = SkillCriadorView(
            autor_id=interaction.user.id,
            personagem_id=self._personagem_id,
            personagem_nome=self._personagem_nome,
            nome=self.nome.value.strip(),
            tipos=self._tipos,
            cooldown=cooldown_v,
            descricao=self.descricao.value.strip(),
            custo_vida=custo_v,
            nivel=self._nivel,
            skill_id=self._skill["id"] if self._skill else None,
            dano=self._skill["dados"].get("dano") if self._skill else None,
            alcance=self._skill["dados"].get("alcance") if self._skill else "UNICO",
            roll=roll_v,
            efeitos=self._skill["dados"].get("efeitos") if self._skill else None,
        )
        await interaction.response.send_message(embed=view.montar_embed(), view=view)


class SkillCriadorView(discord.ui.View):
    def __init__(
        self,
        autor_id: int,
        personagem_id: str,
        personagem_nome: str,
        nome: str,
        tipos: list[str],
        cooldown: int,
        descricao: str,
        custo_vida: int,
        nivel: int | None,
        skill_id: str | None = None,
        dano: dict | None = None,
        alcance: str = "UNICO",
        roll: str = "d20",
        efeitos: list[dict] | None = None,
    ):
        super().__init__(timeout=900)
        self.autor_id = autor_id
        self.personagem_id = personagem_id
        self.personagem_nome = personagem_nome
        self.nome = nome
        self.tipos = list(tipos) if tipos else ["DANO"]
        self.cooldown = cooldown
        self.descricao = descricao
        self.custo_vida = custo_vida
        self.nivel = nivel
        self.skill_id = skill_id
        self.dano = copy.deepcopy(dano) if dano else {"subtipos": [], "config": {}}
        self.alcance = alcance or "UNICO"
        self.roll = roll or "d20"
        self.efeitos = [dict(e) for e in (efeitos or [])]
        self.montar_componentes()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "❌ Só quem iniciou a criação pode usar este painel.", ephemeral=True
            )
            return False
        return True

    def montar_embed(self) -> discord.Embed:
        nivel_txt = f" ({self.nivel}º Nível)" if self.nivel else " (Geral)"
        tipos_txt = " ".join(f"{EMOJI_TIPO.get(t, '')} `{t}`" for t in self.tipos)
        custo_txt = f"\n· **Custo de Vida:** {self.custo_vida} HP" if self.custo_vida else ""
        alcance_txt = D.ALCANCE_ROTULOS.get(self.alcance, self.alcance)

        descricao = (
            f"· **Dono:** {self.personagem_nome}\n"
            f"· **Tipo(s):** {tipos_txt}  ·  **Cooldown:** {self.cooldown} turnos{custo_txt}\n"
            f"· **Alcance:** {alcance_txt}  ·  **Roll:** `{self.roll}`\n"
            f"· **Descrição Narrativa:** *{self.descricao or 'Nenhuma'}*"
        )
        embed = discord.Embed(
            title=f"🔮 Criador de Habilidade — {self.nome}{nivel_txt}",
            description=descricao,
            color=discord.Color.blurple(),
        )
        if "DANO" in self.tipos:
            embed.add_field(
                name="⚔️ Dano",
                value=D.resumo_dano(self.dano, mostrar_pendentes=True)[:1024]
                if self.dano["subtipos"]
                else "⚠️ *Dano ainda não configurado. Clique em **Configurar Dano**.*",
                inline=False,
            )
        return embed

    def montar_componentes(self) -> None:
        self.clear_items()

        # Row 0: Seleção de Tipo(s) da Habilidade (múltiplos permitidos)
        select_tipos = discord.ui.Select(
            placeholder="Escolha o(s) tipo(s) da habilidade (pode marcar vários)",
            min_values=1,
            max_values=len(db_skills.TIPOS_VALIDOS),
            options=[
                discord.SelectOption(
                    label=t,
                    value=t,
                    emoji=EMOJI_TIPO.get(t),
                    default=(t in self.tipos),
                )
                for t in db_skills.TIPOS_VALIDOS
            ],
            row=0,
        )
        select_tipos.callback = self._ao_escolher_tipos
        self.add_item(select_tipos)

        # Row 1: Seleção de Alcance / Alvo
        select_alcance = discord.ui.Select(
            placeholder="Escolha o alcance / alvo da habilidade",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=lbl,
                    value=val,
                    default=(val == self.alcance),
                )
                for lbl, val in D.ALCANCES
            ],
            row=1,
        )
        select_alcance.callback = self._ao_escolher_alcance
        self.add_item(select_alcance)

        # Row 2: Ações e botões
        b_roll = discord.ui.Button(
            label=f"Roll: {self.roll}"[:80],
            emoji="🎲",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        b_roll.callback = self._ao_alterar_roll
        self.add_item(b_roll)

        if "DANO" in self.tipos:
            b_dano = discord.ui.Button(
                label="Configurar Dano",
                emoji="⚔️",
                style=discord.ButtonStyle.danger,
                row=2,
            )
            b_dano.callback = self._ao_configurar_dano
            self.add_item(b_dano)

        b_salvar = discord.ui.Button(
            label="Finalizar e Salvar",
            emoji="✅",
            style=discord.ButtonStyle.success,
            row=2,
        )
        b_salvar.callback = self._ao_salvar
        self.add_item(b_salvar)

        b_cancelar = discord.ui.Button(
            label="Cancelar",
            emoji="❌",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        b_cancelar.callback = self._ao_cancelar
        self.add_item(b_cancelar)

    async def _ao_escolher_tipos(self, interaction: discord.Interaction) -> None:
        self.tipos = list(interaction.data["values"])
        if "DANO" not in self.tipos:
            self.dano = {"subtipos": [], "config": {}}
        self.montar_componentes()
        await interaction.response.edit_message(embed=self.montar_embed(), view=self)

    async def _ao_escolher_alcance(self, interaction: discord.Interaction) -> None:
        self.alcance = interaction.data["values"][0]
        self.montar_componentes()
        await interaction.response.edit_message(embed=self.montar_embed(), view=self)

    async def _ao_alterar_roll(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(AlterarRollModal(self))

    async def _ao_configurar_dano(self, interaction: discord.Interaction) -> None:
        view = DanoConfigView(self)
        await interaction.response.edit_message(embed=view.montar_embed(), view=view)

    async def _ao_salvar(self, interaction: discord.Interaction) -> None:
        dano = None
        if "DANO" in self.tipos:
            pendentes = D.dano_pendentes(self.dano)
            if pendentes:
                await interaction.response.send_message(
                    "❌ **Dano incompleto.** Clique em **Configurar Dano** e configure: "
                    + ", ".join(pendentes),
                    ephemeral=True,
                )
                return
            dano = self.dano

        if "BLOQUEIO" in self.tipos and self.custo_vida <= 0:
            await interaction.response.send_message(
                "❌ Habilidades com o tipo **Bloqueio** exigem um custo de HP maior que zero.",
                ephemeral=True,
            )
            return

        if self.skill_id:
            db_skills.atualizar_skill(
                self.skill_id,
                nome=self.nome,
                tipos=self.tipos,
                cooldown=self.cooldown,
                descricao=self.descricao,
                custo_vida=self.custo_vida,
                nivel=self.nivel,
                alcance=self.alcance,
                roll=self.roll,
                dano=dano,
                efeitos=self.efeitos,
            )
            skill = db_skills.buscar_skill_por_id(self.skill_id)
            embed = skill_criada_embed(skill)
            embed.title = f"✅ Habilidade Atualizada: {skill['nome']}"
        else:
            skill = db_skills.criar_skill(
                personagem_id=self.personagem_id,
                nome=self.nome,
                tipos=self.tipos,
                cooldown=self.cooldown,
                descricao=self.descricao or None,
                nivel=self.nivel,
                custo_vida=self.custo_vida,
                alcance=self.alcance,
                roll=self.roll,
                dano=dano,
                efeitos=self.efeitos,
            )
            embed = skill_criada_embed(skill)
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)

    async def _ao_cancelar(self, interaction: discord.Interaction) -> None:
        self.stop()
        await interaction.response.edit_message(
            content="ℹ️ **Criação Cancelada**\nO processo de criação da habilidade foi cancelado.",
            embed=None,
            view=None,
        )

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
