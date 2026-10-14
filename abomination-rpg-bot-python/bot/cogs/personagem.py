"""
Comandos de personagem.

/personagem criar e /personagem editar usam comando de barra (slash),
porque precisam abrir um Modal (formulário popup) para os números —
isso só existe em comandos de barra.

.personagem listar, .personagem ver e .personagem excluir usam o
prefixo "." por serem rápidos e não precisarem de formulário.
"""
import discord
from discord import app_commands
from discord.ext import commands

from bot.db import personagens as db_personagens
from bot.ui.personagem_modals import (
    PersonagemCriarNarrativoModal,
    FichaStatsModal,
)
from bot.ui.personagem_embeds import personagem_lista_embed, personagem_ficha_embed
from bot.ui.confirmar_view import ConfirmarExclusaoView

STATS_CHOICES = [
    app_commands.Choice(name="⚔️ ATK", value="ATK"),
    app_commands.Choice(name="🛡️ DEF", value="DEF"),
    app_commands.Choice(name="✨ MST", value="MST"),
    app_commands.Choice(name="👢 VEL", value="VEL"),
    app_commands.Choice(name="❤️ HP", value="HP"),
]


def _tem_permissao(personagem, user) -> bool:
    is_owner = personagem["owner_id"] == str(user.id)
    is_admin = (
        user.guild_permissions.manage_guild or user.guild_permissions.administrator
    ) if isinstance(user, discord.Member) else False
    return is_owner or is_admin


class PersonagemCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ══════════════════ Grupo /personagem ══════════════════

    grupo_personagem = app_commands.Group(
        name="personagem", description="Gerencia seus personagens"
    )

    @grupo_personagem.command(
        name="criar",
        description="Registra um novo personagem (Nome, Raça, Elemento, Classe obrigatórios)",
    )
    @app_commands.describe(
        stat_principal="STAT principal, base das fórmulas das skills (padrão: ATK)",
    )
    @app_commands.choices(stat_principal=STATS_CHOICES)
    async def personagem_criar(
        self,
        interaction: discord.Interaction,
        stat_principal: app_commands.Choice[str] | None = None,
    ):
        modal = PersonagemCriarNarrativoModal(
            stat_principal=stat_principal.value if stat_principal else "ATK"
        )
        await interaction.response.send_modal(modal)

    @grupo_personagem.command(
        name="editar",
        description="Edita os detalhes narrativos ou STAT principal de um personagem",
    )
    @app_commands.describe(
        nome="Nome do personagem",
        raca="Nova raça (opcional)",
        elemento="Novo elemento (opcional)",
        classe="Nova classe (opcional)",
        stat_principal="Novo STAT principal (opcional)",
    )
    @app_commands.choices(stat_principal=STATS_CHOICES)
    async def personagem_editar(
        self,
        interaction: discord.Interaction,
        nome: str,
        raca: str | None = None,
        elemento: str | None = None,
        classe: str | None = None,
        stat_principal: app_commands.Choice[str] | None = None,
    ):
        personagem = db_personagens.buscar_personagem_por_nome_qualquer_dono(nome)
        if not personagem:
            await interaction.response.send_message(
                f"❌ Nenhum personagem encontrado com o nome **{nome}**.", ephemeral=True
            )
            return

        if not _tem_permissao(personagem, interaction.user):
            await interaction.response.send_message(
                f"❌ Você não tem permissão para editar o personagem **{personagem['nome']}**.",
                ephemeral=True,
            )
            return

        if raca is None and elemento is None and classe is None and stat_principal is None:
            await interaction.response.send_message(
                "ℹ️ Nenhum detalhe informado para alterar. "
                "Para editar os atributos numéricos (HP, ATK...), use `/ficha preencher`.",
                ephemeral=True,
            )
            return

        db_personagens.atualizar_detalhes(
            personagem["id"],
            raca=raca,
            elemento=elemento,
            classe=classe,
            stat_principal=stat_principal.value if stat_principal else None,
        )
        p_atualizado = db_personagens.buscar_personagem_por_id(personagem["id"])
        avatar_url = interaction.user.display_avatar.url
        await interaction.response.send_message(
            f"✅ Detalhes de **{p_atualizado['nome']}** atualizados!",
            embed=personagem_ficha_embed(p_atualizado, avatar_url),
        )

    @personagem_editar.autocomplete("nome")
    async def personagem_editar_autocomplete(
        self, interaction: discord.Interaction, atual: str
    ):
        rows = db_personagens.autocomplete_personagens(str(interaction.user.id), atual)
        return [app_commands.Choice(name=r["nome"], value=r["nome"]) for r in rows]

    # ══════════════════ Grupo /ficha ══════════════════

    grupo_ficha = app_commands.Group(
        name="ficha", description="Gerencia a ficha de atributos (stats) dos personagens"
    )

    @grupo_ficha.command(
        name="preencher",
        description="Preenche ou edita os atributos de combate (HP, ATK, DEF, MST, VEL)",
    )
    @app_commands.describe(personagem="Nome do personagem")
    async def ficha_preencher(self, interaction: discord.Interaction, personagem: str):
        alvo = db_personagens.buscar_personagem_por_nome_qualquer_dono(personagem)
        if not alvo:
            await interaction.response.send_message(
                f"❌ Nenhum personagem encontrado com o nome **{personagem}**.\n"
                "Crie o personagem primeiro com `/personagem criar`.",
                ephemeral=True,
            )
            return

        if not _tem_permissao(alvo, interaction.user):
            await interaction.response.send_message(
                f"❌ Você não tem permissão para alterar a ficha de **{alvo['nome']}**.",
                ephemeral=True,
            )
            return

        modal = FichaStatsModal(
            personagem_id=alvo["id"],
            personagem_nome=alvo["nome"],
            hp_atual=alvo["hp"],
            atk_atual=alvo["atk"],
            def_atual=alvo["def"],
            mst_atual=alvo["mst"],
            vel_atual=alvo["vel"],
            titulo_prefixo="Ficha de Stats",
        )
        await interaction.response.send_modal(modal)

    @ficha_preencher.autocomplete("personagem")
    async def ficha_preencher_autocomplete(
        self, interaction: discord.Interaction, atual: str
    ):
        rows = db_personagens.autocomplete_personagens(str(interaction.user.id), atual)
        return [app_commands.Choice(name=r["nome"], value=r["nome"]) for r in rows]

    @grupo_ficha.command(
        name="ver",
        description="Mostra a ficha completa de um personagem",
    )
    @app_commands.describe(personagem="Nome do personagem")
    async def ficha_ver(self, interaction: discord.Interaction, personagem: str):
        alvo = db_personagens.buscar_personagem_por_nome_qualquer_dono(personagem)
        if not alvo:
            await interaction.response.send_message(
                f"❌ Nenhum personagem encontrado com o nome **{personagem}**.",
                ephemeral=True,
            )
            return

        avatar_url = interaction.user.display_avatar.url
        await interaction.response.send_message(
            embed=personagem_ficha_embed(alvo, avatar_url)
        )

    @ficha_ver.autocomplete("personagem")
    async def ficha_ver_autocomplete(
        self, interaction: discord.Interaction, atual: str
    ):
        rows = db_personagens.autocomplete_personagens(str(interaction.user.id), atual)
        return [app_commands.Choice(name=r["nome"], value=r["nome"]) for r in rows]

    # ══════════════════ Comandos de prefixo "." ══════════════════

    @commands.group(name="ficha", invoke_without_command=True)
    async def ficha_prefixo(self, ctx: commands.Context):
        await ctx.send(
            "Use `.ficha ver <personagem>` para consultar a ficha.\n"
            "Para definir os atributos de combate, use `/ficha preencher`."
        )

    @ficha_prefixo.command(name="ver")
    async def ficha_ver_prefixo(self, ctx: commands.Context, *, nome: str):
        personagem = db_personagens.buscar_personagem_por_nome_qualquer_dono(nome)
        if not personagem:
            await ctx.send(f"❌ Nenhum personagem encontrado com o nome **{nome}**.")
            return
        avatar_url = ctx.author.display_avatar.url
        await ctx.send(embed=personagem_ficha_embed(personagem, avatar_url))

    @commands.group(name="personagem", invoke_without_command=True)
    async def personagem_prefixo(self, ctx: commands.Context):
        await ctx.send(
            "Use `.personagem listar`, `.personagem ver <nome>` ou `.personagem excluir <nome>`.\n"
            "Para criar: `/personagem criar`. Para preencher os stats: `/ficha preencher`."
        )

    @personagem_prefixo.command(name="listar")
    async def listar_prefixo(self, ctx: commands.Context):
        rows = db_personagens.listar_personagens(str(ctx.author.id))
        if not rows:
            await ctx.send(
                "ℹ️ Você ainda não tem nenhum personagem.\nUse `/personagem criar` para registrar o primeiro!"
            )
            return
        await ctx.send(embed=personagem_lista_embed(rows))

    @personagem_prefixo.command(name="ver")
    async def ver_prefixo(self, ctx: commands.Context, *, nome: str):
        personagem = db_personagens.buscar_personagem(str(ctx.author.id), nome)
        if not personagem:
            await ctx.send(
                f"❌ Nenhum personagem seu com o nome **{nome}** foi encontrado.\nUse `.personagem listar` para ver seus personagens."
            )
            return

        avatar_url = ctx.author.display_avatar.url
        await ctx.send(embed=personagem_ficha_embed(personagem, avatar_url))

    @personagem_prefixo.command(name="excluir")
    async def excluir_prefixo(self, ctx: commands.Context, *, nome: str):
        personagem = db_personagens.buscar_personagem_por_nome_qualquer_dono(nome)
        if not personagem:
            await ctx.send(f"❌ Nenhum personagem encontrado com o nome **{nome}**.")
            return

        if not _tem_permissao(personagem, ctx.author):
            await ctx.send(f"❌ Você não tem permissão para excluir o personagem **{personagem['nome']}**.")
            return

        view = ConfirmarExclusaoView(
            personagem_id=personagem["id"],
            personagem_nome=personagem["nome"],
            autor_id=ctx.author.id,
        )
        await ctx.send(
            f"⚠️ Tem certeza que deseja excluir **{personagem['nome']}**? Essa ação não pode ser desfeita.",
            view=view,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(PersonagemCog(bot))
