"""
Cog do combate: /host (lobby) e rolagens com prefixo "!" durante a batalha.
"""
import discord
from discord import app_commands
from discord.ext import commands

from bot.combat import resolucao
from bot.combat.combate_embeds import embed_lobby
from bot.combat.combate_manager import CombateState, obter_combate, registrar_combate
from bot.combat.combate_views import LobbyView
from bot.combat.dados import PADRAO_DADO, rolar_expressao


def _normalizar(expr: str):
    """'!d20+3' e '!1D20+3' viram a mesma chave."""
    t = expr.strip().replace(" ", "")
    m = PADRAO_DADO.match(t if t.startswith("!") else "!" + t)
    if not m:
        return None
    qtd, tipo, lados, mod = m.groups()
    return (int(qtd or 1), tipo.upper(), int(lados or 20), int(mod or 0))


class CombateCog(commands.Cog, name="Combate"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="host", description="Inicia um lobby de combate neste canal")
    @app_commands.guild_only()
    async def host(self, interaction: discord.Interaction):
        if obter_combate(interaction.channel_id):
            await interaction.response.send_message(
                "❌ Já existe um lobby ou combate ativo neste canal.", ephemeral=True
            )
            return
        c = CombateState(
            canal_id=interaction.channel_id, guild_id=interaction.guild_id,
            host_id=interaction.user.id, host_nome=interaction.user.display_name,
        )
        registrar_combate(c)
        await interaction.response.send_message(embed=embed_lobby(c), view=LobbyView(c))
        msg = await interaction.original_response()
        c.mensagem_painel_id = msg.id

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content.startswith("!"):
            return
        c = obter_combate(message.channel.id)
        if not c or c.status != "EM_ANDAMENTO" or not c.acao_pendente:
            return

        pend = c.acao_pendente
        atacante = c.obter(pend.atacante_id)
        alvo = c.obter(pend.alvo_id)
        if not atacante or not alvo:
            return

        uid = str(message.author.id)
        if pend.aguardando == "DEFENSOR" and pend.defesa != "DESVIAR":
            if uid == alvo.owner_id:
                await message.reply("⚠️ Escolha **Desviar** ou **Bloquear** nos botões acima antes de rolar.",
                                    mention_author=False)
            return

        if pend.aguardando == "ATACANTE":
            dono, esperado = atacante.owner_id, pend.expr_atacante()
        else:
            dono, esperado = alvo.owner_id, pend.expr_defensor()
        if uid != dono:
            return

        if _normalizar(message.content) != _normalizar(esperado):
            await message.reply(f"⚠️ Você deve rolar exatamente `!{esperado}`.", mention_author=False)
            return
        r = rolar_expressao(message.content)
        if not r:
            return

        if pend.aguardando == "ATACANTE":
            await message.reply(f"🎲 **{atacante.nome}**: {r.formatar()}", mention_author=False)
            await resolucao.apos_rolagem_atacante(message.channel, c, r.valores_finais)
            return

        for k, v in enumerate(r.valores_finais):
            pend.cache_def[pend.idx + k] = v
        resumo = resolucao.resolver_golpe(c, pend, r.valores_finais[0])
        await message.reply(f"🛡️ **{alvo.nome}**: {r.formatar()}\n{resumo}", mention_author=False)
        await resolucao.apos_golpe(message.channel, c)


async def setup(bot: commands.Bot):
    await bot.add_cog(CombateCog(bot))
