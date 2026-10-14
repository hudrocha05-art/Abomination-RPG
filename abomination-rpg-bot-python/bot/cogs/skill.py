"""
Comandos de habilidades (skills).

/skill criar e /skill editar usam comando de barra, pois precisam do menu
de seleção de tipos + um Modal (formulário popup).

.skill listar, .skill ver e .skill excluir usam o prefixo "." por serem
rápidos e não precisarem de nenhum componente interativo de entrada.
"""
import discord
from discord import app_commands
from discord.ext import commands

from bot.db import personagens as db_personagens
from bot.db import skills as db_skills
from bot.ui.skill_tipo_view import SkillTipoView
from bot.ui.skill_modals import SkillEditarModal
from bot.ui.skill_criador import SkillInfoModal
from bot.ui.skill_embeds import skill_lista_embed, skill_ficha_embed

MAX_SKILLS_POR_PERSONAGEM = 10  # Limite total de habilidades por personagem (Skill Tree)


def _tem_permissao(personagem, user) -> bool:
    is_owner = personagem["owner_id"] == str(user.id)
    is_admin = (
        user.guild_permissions.manage_guild or user.guild_permissions.administrator
    ) if isinstance(user, discord.Member) else False
    return is_owner or is_admin


class ExcluirSkillView(discord.ui.View):
    """View de confirmação para excluir uma skill (botões Excluir/Cancelar)."""

    def __init__(self, skill_id: str, skill_nome: str, autor_id: int, *, timeout: float = 30):
        super().__init__(timeout=timeout)
        self._skill_id = skill_id
        self._skill_nome = skill_nome
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
        db_skills.excluir_skill(self._skill_id)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"🗑️ Habilidade **{self._skill_nome}** foi excluída permanentemente.",
            view=self,
        )
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"↩️ Exclusão de **{self._skill_nome}** cancelada.", view=self
        )
        self.stop()


class SkillCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ══════════════════ Comandos de barra (com Select + Modal) ══════════════════

    grupo = app_commands.Group(name="skill", description="Gerencia as habilidades de um personagem")

    @grupo.command(name="criar", description="Cria uma nova habilidade para um personagem")
    @app_commands.describe(
        personagem="Nome do personagem que vai receber a habilidade",
        tipo="Tipo inicial da habilidade (você pode marcar mais tipos no painel)",
        nivel="Nível na Skill Tree (opcional)",
    )
    @app_commands.choices(
        tipo=[
            app_commands.Choice(name="💥 Dano", value="DANO"),
            app_commands.Choice(name="💚 Cura", value="CURA"),
            app_commands.Choice(name="🛡️ Escudo", value="ESCUDO"),
            app_commands.Choice(name="✨ Buff", value="BUFF"),
            app_commands.Choice(name="💀 Debuff", value="DEBUFF"),
            app_commands.Choice(name="🌐 Campo", value="CAMPO"),
            app_commands.Choice(name="👥 Invocação", value="INVOCACAO"),
            app_commands.Choice(name="🛡️ Bloqueio (Guardião)", value="BLOQUEIO"),
        ]
    )
    async def criar(
        self,
        interaction: discord.Interaction,
        personagem: str,
        tipo: app_commands.Choice[str] | None = None,
        nivel: app_commands.Range[int, 1, 3] | None = None,
    ):
        alvo = db_personagens.buscar_personagem_por_nome_qualquer_dono(personagem)
        if not alvo:
            await interaction.response.send_message(
                f"❌ Nenhum personagem encontrado com o nome **{personagem}**.", ephemeral=True
            )
            return

        if not _tem_permissao(alvo, interaction.user):
            await interaction.response.send_message(
                f"❌ Você não tem permissão para adicionar habilidades a **{alvo['nome']}**.",
                ephemeral=True,
            )
            return

        if len(db_skills.listar_skills(alvo["id"])) >= MAX_SKILLS_POR_PERSONAGEM:
            await interaction.response.send_message(
                f"❌ **{alvo['nome']}** já atingiu o limite de {MAX_SKILLS_POR_PERSONAGEM} habilidades.",
                ephemeral=True,
            )
            return

        if alvo["hp"] == 0 and alvo["atk"] == 0 and alvo["def"] == 0 and alvo["mst"] == 0 and alvo["vel"] == 0:
            await interaction.response.send_message(
                f"⚠️ **{alvo['nome']}** ainda não tem uma ficha de stats configurada!\n"
                "Use `/ficha preencher` primeiro para definir os atributos de combate antes de criar habilidades.",
                ephemeral=True,
            )
            return

        tipos_iniciais = [tipo.value] if tipo else ["DANO"]
        await interaction.response.send_modal(
            SkillInfoModal(alvo["id"], alvo["nome"], tipos_iniciais, nivel)
        )

    @criar.autocomplete("personagem")
    async def criar_autocomplete(self, interaction: discord.Interaction, atual: str):
        rows = db_personagens.autocomplete_personagens(str(interaction.user.id), atual)
        return [app_commands.Choice(name=r["nome"], value=r["nome"]) for r in rows]

    @grupo.command(name="editar", description="Edita uma habilidade existente")
    @app_commands.describe(
        personagem="Nome do personagem",
        habilidade="Nome da habilidade",
        tipo="Novo tipo (opcional, mantém o atual se vazio)",
        nivel="Novo nível na Skill Tree (opcional)",
    )
    @app_commands.choices(
        tipo=[
            app_commands.Choice(name="💥 Dano", value="DANO"),
            app_commands.Choice(name="💚 Cura", value="CURA"),
            app_commands.Choice(name="🛡️ Escudo", value="ESCUDO"),
            app_commands.Choice(name="✨ Buff", value="BUFF"),
            app_commands.Choice(name="💀 Debuff", value="DEBUFF"),
            app_commands.Choice(name="🌐 Campo", value="CAMPO"),
            app_commands.Choice(name="👥 Invocação", value="INVOCACAO"),
            app_commands.Choice(name="🛡️ Bloqueio (Guardião)", value="BLOQUEIO"),
        ]
    )
    async def editar(
        self,
        interaction: discord.Interaction,
        personagem: str,
        habilidade: str,
        tipo: app_commands.Choice[str] | None = None,
        nivel: app_commands.Range[int, 1, 3] | None = None,
    ):
        alvo = db_personagens.buscar_personagem_por_nome_qualquer_dono(personagem)
        if not alvo:
            await interaction.response.send_message(
                f"❌ Nenhum personagem encontrado com o nome **{personagem}**.", ephemeral=True
            )
            return

        if not _tem_permissao(alvo, interaction.user):
            await interaction.response.send_message(
                f"❌ Você não tem permissão para editar habilidades de **{alvo['nome']}**.",
                ephemeral=True,
            )
            return

        skill = db_skills.buscar_skill_por_nome(alvo["id"], habilidade)
        if not skill:
            await interaction.response.send_message(
                f"❌ **{alvo['nome']}** não possui a habilidade **{habilidade}**.", ephemeral=True
            )
            return

        tipos = [tipo.value] if tipo else skill["tipos"]
        await interaction.response.send_modal(
            SkillInfoModal(alvo["id"], alvo["nome"], tipos, nivel or skill["nivel"], skill=skill)
        )

    @editar.autocomplete("personagem")
    async def editar_personagem_autocomplete(self, interaction: discord.Interaction, atual: str):
        rows = db_personagens.autocomplete_personagens(str(interaction.user.id), atual)
        return [app_commands.Choice(name=r["nome"], value=r["nome"]) for r in rows]

    @editar.autocomplete("habilidade")
    async def editar_habilidade_autocomplete(self, interaction: discord.Interaction, atual: str):
        personagem_nome = interaction.namespace.personagem
        if not personagem_nome:
            return []
        alvo = db_personagens.buscar_personagem_por_nome_qualquer_dono(personagem_nome)
        if not alvo:
            return []
        skills = db_skills.autocomplete_skills(alvo["id"], atual)
        return [app_commands.Choice(name=s["nome"], value=s["nome"]) for s in skills]

    # ══════════════════ Comandos de prefixo "." ══════════════════

    @commands.group(name="skill", invoke_without_command=True)
    async def skill_prefixo(self, ctx: commands.Context):
        await ctx.send(
            "Use `.skill listar <personagem>`, `.skill ver <personagem> <habilidade>` ou "
            "`.skill excluir <personagem> <habilidade>`.\n"
            "Para criar ou editar, use `/skill criar` e `/skill editar`."
        )

    @skill_prefixo.command(name="listar")
    async def listar_prefixo(self, ctx: commands.Context, *, personagem: str):
        alvo = db_personagens.buscar_personagem(str(ctx.author.id), personagem)
        if not alvo:
            await ctx.send(f"❌ Você não possui nenhum personagem chamado **{personagem}**.")
            return

        skills = db_skills.listar_skills(alvo["id"])
        if not skills:
            await ctx.send(
                f"ℹ️ **{alvo['nome']}** ainda não possui habilidades.\nUse `/skill criar` para adicionar a primeira!"
            )
            return
        await ctx.send(embed=skill_lista_embed(alvo["nome"], skills))

    @skill_prefixo.command(name="ver")
    async def ver_prefixo(self, ctx: commands.Context, personagem: str, *, habilidade: str):
        alvo = db_personagens.buscar_personagem(str(ctx.author.id), personagem)
        if not alvo:
            await ctx.send(f"❌ Você não possui nenhum personagem chamado **{personagem}**.")
            return

        skill = db_skills.buscar_skill_por_nome(alvo["id"], habilidade)
        if not skill:
            await ctx.send(f"❌ **{alvo['nome']}** não possui a habilidade **{habilidade}**.")
            return

        await ctx.send(embed=skill_ficha_embed(alvo["nome"], skill))

    @skill_prefixo.command(name="excluir")
    async def excluir_prefixo(self, ctx: commands.Context, personagem: str, *, habilidade: str):
        alvo = db_personagens.buscar_personagem_por_nome_qualquer_dono(personagem)
        if not alvo:
            await ctx.send(f"❌ Nenhum personagem encontrado com o nome **{personagem}**.")
            return

        if not _tem_permissao(alvo, ctx.author):
            await ctx.send(f"❌ Você não tem permissão para excluir habilidades de **{alvo['nome']}**.")
            return

        skill = db_skills.buscar_skill_por_nome(alvo["id"], habilidade)
        if not skill:
            await ctx.send(f"❌ **{alvo['nome']}** não possui a habilidade **{habilidade}**.")
            return

        view = ExcluirSkillView(skill["id"], skill["nome"], ctx.author.id)
        await ctx.send(
            f"⚠️ Tem certeza que deseja excluir **{skill['nome']}** de **{alvo['nome']}**? "
            "Essa ação não pode ser desfeita.",
            view=view,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SkillCog(bot))
