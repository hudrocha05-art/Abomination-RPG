"""
Embeds (mensagens visuais) usados para exibir habilidades no Discord.
"""
import discord

EMOJI_TIPO = {
    "DANO": "💥",
    "CURA": "💚",
    "ESCUDO": "🛡️",
    "BUFF": "✨",
    "DEBUFF": "💀",
    "CAMPO": "🌐",
    "INVOCACAO": "👥",
    "BLOQUEIO": "🛡️",
}


def _tipos_formatados(tipos: list[str]) -> str:
    return " ".join(f"{EMOJI_TIPO.get(t, '')} {t}" for t in tipos)


def _corpo_skill(s: dict) -> str:
    linhas = [f"**Tipo(s):** {_tipos_formatados(s['tipos'])}"]
    linhas.append(f"**Recarga:** {s['cooldown']} turno(s)")
    custo_vida = s["dados"].get("custo_vida") or 0
    if custo_vida:
        linhas.append(f"**Custo de HP:** {custo_vida}")
    alcance = s["dados"].get("alcance")
    if alcance:
        from bot.dano import ALCANCE_ROTULOS
        linhas.append(f"**Alcance:** {ALCANCE_ROTULOS.get(alcance, alcance)}")
    roll = s["dados"].get("roll")
    if roll:
        linhas.append(f"**Roll de Acerto:** `{roll}`")
    efeitos = s["dados"].get("efeitos") or []
    if efeitos:
        from bot.ui.skill_criador import formatar_efeitos
        linhas.append(f"\n**Efeitos Extras:**\n{formatar_efeitos(efeitos)}")
    dano = s["dados"].get("dano")
    if dano and dano.get("subtipos"):
        from bot.dano import resumo_dano
        linhas.append(f"\n**⚔️ Dano:**\n{resumo_dano(dano)}")
    if s.get("descricao"):
        linhas.append(f"\n{s['descricao']}")
    return "\n".join(linhas)


def skill_criada_embed(s: dict) -> discord.Embed:
    return discord.Embed(
        title=f"✅ Habilidade Criada: {s['nome']}",
        description=_corpo_skill(s),
        color=discord.Color.green(),
    )


def skill_lista_embed(personagem_nome: str, skills: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title=f"📖 Habilidades de {personagem_nome}", color=discord.Color.blurple()
    )
    for s in skills:
        embed.add_field(name=s["nome"], value=_corpo_skill(s)[:1024], inline=False)
    return embed


def skill_ficha_embed(personagem_nome: str, s: dict) -> discord.Embed:
    return discord.Embed(
        title=f"📜 {s['nome']} ({personagem_nome})",
        description=_corpo_skill(s),
        color=discord.Color.gold(),
    )
