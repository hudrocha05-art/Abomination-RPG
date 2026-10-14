"""
Embeds (mensagens visuais) usados para exibir personagens no Discord.
"""
import sqlite3
import discord


def _corpo_ficha(p: sqlite3.Row) -> str:
    """Monta o corpo da ficha no formato usado pelo grupo:
    X HP
    [X] ATK
    [X] DEF
    [X] MST
    [X] VEL
    """
    if p["hp"] == 0 and p["atk"] == 0 and p["def"] == 0 and p["mst"] == 0 and p["vel"] == 0:
        return "⚠️ *Ficha de stats ainda não preenchida. Use `/ficha preencher`.*"
    return (
        f"**{p['hp']} HP**\n"
        f"[{p['atk']}] ATK ⚔️\n"
        f"[{p['def']}] DEF 🛡️\n"
        f"[{p['mst']}] MST ✨\n"
        f"[{p['vel']}] VEL 👢"
    )


def personagem_criado_embed(p: sqlite3.Row) -> discord.Embed:
    embed = discord.Embed(
        title=f"✅ Personagem Criado: {p['nome']}",
        description=(
            f"**Raça:** {p['raca']}\n"
            f"**Elemento:** {p['elemento']}\n"
            f"**Classe:** {p['classe']}\n"
            f"**STAT principal:** {p['stat_principal']}\n\n"
            "📝 *Agora use `/ficha preencher` para definir os stats (HP, ATK, DEF, MST, VEL).*"
        ),
        color=discord.Color.green(),
    )
    return embed


def personagem_lista_embed(rows: list[sqlite3.Row]) -> discord.Embed:
    embed = discord.Embed(title="📋 Seus Personagens", color=discord.Color.blurple())
    for p in rows:
        embed.add_field(name=p["nome"], value=_corpo_ficha(p), inline=False)
    return embed


def personagem_ficha_embed(p: sqlite3.Row, avatar_url: str | None = None) -> discord.Embed:
    corpo = (
        f"**{p['hp_atual']}/{p['hp']} HP**\n"
        f"[{p['atk']}] ATK ⚔️\n"
        f"[{p['def']}] DEF 🛡️\n"
        f"[{p['mst']}] MST ✨\n"
        f"[{p['vel']}] VEL 👢\n"
        f"🪙 Starbits: {p['starbits']}"
    )
    embed = discord.Embed(title=f"📜 Ficha de {p['nome']}", description=corpo, color=discord.Color.gold())
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    extras = []
    if p["raca"]:
        extras.append(f"Raça: {p['raca']}")
    if p["classe"]:
        extras.append(f"Classe: {p['classe']}")
    if p["elemento"]:
        extras.append(f"Elemento: {p['elemento']}")
    extras.append(f"STAT principal: {p['stat_principal']}")
    if extras:
        embed.add_field(name="Detalhes", value="\n".join(extras), inline=False)
    return embed
