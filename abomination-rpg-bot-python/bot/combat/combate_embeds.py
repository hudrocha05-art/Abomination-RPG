"""
Embeds do lobby e do painel de batalha.
"""
import discord

from bot.combat.combate_manager import DURACAO_PERMANENTE, CombateState, ParticipanteCombate


def barra(atual: int, maximo: int, blocos: int = 10) -> str:
    if atual <= 0 or maximo <= 0:
        return "░" * blocos
    cheios = max(0, min(blocos, round(atual / maximo * blocos)))
    return "█" * cheios + "░" * (blocos - cheios)


def cor_hp(p: ParticipanteCombate) -> discord.Color:
    pct = p.hp_atual / p.hp_max if p.hp_max else 0
    if pct > 0.5:
        return discord.Color.green()
    if pct >= 0.2:
        return discord.Color.gold()
    return discord.Color.red()


def _turnos(restante) -> str:
    return "" if restante == DURACAO_PERMANENTE else f" ({restante})"


def _condicoes(p: ParticipanteCombate) -> str:
    itens = []
    for d in p.dots:
        itens.append(f"☠️ {d['nome']}" + (f" x{d['stacks']}" if d["stacks"] > 1 else "") + _turnos(d["restante"]))
    for k in p.contras:
        itens.append(f"🔄 {k['nome']}" + _turnos(k["restante"]))
    if p.carregando:
        itens.append(f"🔋 {p.carregando['nome']} ({p.carregando['turnos']})")
    if p.extras_pend:
        itens.append("⚡ ataque extra armado")
    return ", ".join(itens)


def _bloco_personagem(p: ParticipanteCombate, eh_vez: bool = False) -> str:
    cond = _condicoes(p)
    nome = ("▶️ " if eh_vez else "") + p.nome[:150] + (f" - {cond[:300]}" if cond else "")
    defesa = f"🛡️ DEF quebrada ({p.def_regen})" if p.def_regen is not None else f"{p.def_atual} DEF 🛡️"
    return (f"**{nome}**\n"
            f"{p.hp_atual}/{p.hp_max} HP ❤️ | {defesa}\n"
            f"{p.atk} ATK ⚔️ | {p.mst} MST ✨ | {p.vel} VEL 👟")


def _campos_time(c: CombateState, time: str) -> list[tuple[str, str]]:
    membros = sorted(
        (p for p in c.participantes if p.time == time),
        key=lambda p: p.vel,
        reverse=True,
    )
    reservas = [p.nome for p in membros if not p.em_campo]
    blocos = []
    if reservas:
        # Keep the reserve list in manageable chunks as the roster grows.
        atual = []
        tamanho = len("Reservas: ")
        for nome in reservas:
            nome = nome[:100]
            extra = len(nome) + (2 if atual else 0)
            if tamanho + extra > 800 and atual:
                blocos.append("**Reservas:** " + ", ".join(atual))
                atual, tamanho = [], len("Reservas: ")
            atual.append(nome)
            tamanho += extra
        if atual:
            blocos.append("**Reservas:** " + ", ".join(atual))
    for p in (x for x in membros if x.em_campo):
        vez = c.atual
        blocos.append(_bloco_personagem(p, bool(vez and vez.personagem_id == p.personagem_id and not c.vencedor())))

    campos: list[str] = []
    parte = []
    tamanho = 0
    for bloco in blocos:
        separador = "\n\n──────────────\n\n" if parte else ""
        if parte and tamanho + len(separador) + len(bloco) > 930:
            campos.append("\n\n──────────────\n\n".join(parte))
            parte, tamanho, separador = [], 0, ""
        parte.append(bloco)
        tamanho += len(separador) + len(bloco)
    if parte:
        campos.append("\n\n──────────────\n\n".join(parte))

    rotulo = "🔵 Time A" if time == "A" else "🔴 Time B"
    # Mantém um espaço antes do conteúdo sem deixar linhas vazias no fim do painel.
    # Markdown de título (#) não funciona em nome de campo, então o rótulo vai no valor.
    return [
        ("\u200b", (f"# **{rotulo}**\n" if i == 0 else f"## **{rotulo} (continuação)**\n")
         + "\u200b\n" + campo.rstrip())
        for i, campo in enumerate(campos or ["*Vazio*"])
    ]


def embed_lobby(c: CombateState) -> discord.Embed:
    e = discord.Embed(
        title="⚔️ Lobby de Combate Iniciado!",
        description=f"*Organizado por **{c.host_nome}***\n\n"
        "Clique em **Participar** para selecionar seus personagens e entrar na batalha!",
        color=discord.Color.blurple(),
    )
    if not c.participantes:
        e.add_field(name="Times", value="*Nenhum personagem inscrito.*", inline=False)
    for t in ("A", "B"):
        blocos = []
        for dono in c.donos():
            linhas = []
            for p in (x for x in c.participantes if x.owner_id == dono and x.time == t):
                estado = "⚔️ Ativo" if p.em_campo else "🎒 Reserva"
                linhas.append(f"👤 **{p.nome}** — {estado}\n└ HP `{p.hp_max}` | ATK `{p.atk}` | VEL `{p.vel}`")
            if linhas:
                blocos.append(f"**Jogador:** <@{dono}>\n" + "\n".join(linhas))
        e.add_field(name=f"🔵 Time A" if t == "A" else "🔴 Time B",
                    value="\n\n".join(blocos) or "*Vazio*", inline=False)
    e.set_footer(text="Cada time precisa de pelo menos 1 personagem para o host iniciar a batalha.")
    return e


def embed_batalha(c: CombateState) -> discord.Embed:
    vez = c.atual
    venc = c.vencedor()
    e = discord.Embed(
        title=f"⚡ Rodada: {c.rodada}" if not venc else f"🏁 Combate encerrado — Rodada {c.rodada}",
        description=f"📝 **Último Evento:**\n\u200b\n{c.ultimo_log[:900]}" if c.ultimo_log else "📝 *Nenhum evento ainda.*",
        color=cor_hp(vez) if vez and not venc else discord.Color.gold(),
    )

    candidatos = [
        campo
        for t in ("A", "B")
        for campo in _campos_time(c, t)
    ]
    campos = []
    total = (
        len(e.title or "") + len(e.description or "")
        + sum(len(f.name) + len(f.value) for f in e.fields)
    )
    omitido = False
    for nome, valor in candidatos:
        custo = len(nome) + len(valor)
        if len(e.fields) + len(campos) >= 25 or len(valor) > 1024 or total + custo > 5800:
            omitido = True
            continue
        campos.append((nome, valor))
        total += custo

    if omitido:
        aviso = "⚠️ Lista encurtada para caber nos limites do Discord."
        if campos:
            nome, valor = campos[-1]
            campos[-1] = (nome, (valor[:1024 - len(aviso) - 2] + "\n\n" + aviso))
        else:
            campos.append(("Aviso", aviso))
    for nome, valor in campos:
        e.add_field(name=nome, value=valor, inline=False)
    return e
