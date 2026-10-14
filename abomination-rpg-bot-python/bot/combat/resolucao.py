"""
Resolução das ações de combate: golpes, DoT, ataques extras, contra-ataques e cargas.
"""
import asyncio
import traceback

from bot.combat import calculo_dano as cd
from bot.combat.combate_manager import (
    DURACAO_PERMANENTE,
    AcaoPendente,
    CombateState,
    ParticipanteCombate,
    encerrar_combate,
    obter_combate,
)
from bot.combat.dados import rolar_expressao
from bot.combat.formulas import calcular_valor_formula

FATOR_TRATAMENTO = {"SOFRE": 1.0, "IGNORA": 0.0, "REDUZ_25": 0.75, "REDUZ_50": 0.5, "REDUZ_75": 0.25}
TEMPO_INATIVIDADE = 300  # segundos
FORMULA_BASICO_HP = {"modo": "PERCENT", "percentual": 5}


# ---------------------------------------------------------------- montagem
def alvos_da_skill(c: CombateState, atacante: ParticipanteCombate, skill: dict | None,
                   principal: ParticipanteCombate) -> list[ParticipanteCombate]:
    """Alvos atingidos conforme o alcance da skill (o principal vem primeiro)."""
    alcance = ((skill or {}).get("dados") or {}).get("alcance") or "UNICO"
    inimigos = c.alvos_possiveis(atacante)
    if alcance == "AREA":
        alvos = inimigos
    elif alcance == "TODOS":
        alvos = [p for p in c.participantes if p.em_campo and p.vivo and p is not atacante]
    elif alcance == "ADJACENTES" and principal in inimigos:
        i = inimigos.index(principal)
        alvos = inimigos[max(0, i - 1): i + 2]
    else:
        alvos = [principal]
    return [principal] + [a for a in alvos if a is not principal] if principal in alvos else alvos


def alcance_sem_alvo(skill: dict | None) -> bool:
    """Em área / todos: não precisa escolher alvo."""
    return ((skill or {}).get("dados") or {}).get("alcance") in ("AREA", "TODOS")


def montar_pendencia(atacante: ParticipanteCombate, alvo: ParticipanteCombate, skill: dict | None,
                     mult: float = 1.0, restantes: list[str] | None = None, cache: dict | None = None,
                     primeiro: bool = True) -> AcaoPendente:
    extra = dict(alvos_restantes=list(restantes or []), cache_atk=cache if cache is not None else {},
                 primeiro_alvo=primeiro, mult=mult)
    if skill is None:
        formula = FORMULA_BASICO_HP if atacante.stat_principal == "HP" else cd.FORMULA_PADRAO
        fila = [{"formula": formula, "extra": False, "mult": 1.0, "stat": None}]
        return AcaoPendente(atacante.personagem_id, alvo.personagem_id, None, fila=fila, n_main=1, **extra)
    plano = cd.plano_skill(skill)
    fila = [
        {"formula": plano["formula"], "extra": False, "mult": mult, "stat": None}
        for _ in range(plano["golpes"])
    ]
    return AcaoPendente(
        atacante.personagem_id, alvo.personagem_id, skill, fila=fila, n_main=len(fila),
        roll_atacante=skill["dados"].get("roll") or "d20", plano=plano, **extra,
    )


def _golpes_extra(ex: dict) -> list[dict]:
    return [
        {"formula": ex["formula"], "extra": True, "mult": 1.0, "stat": None}
        for _ in range(max(1, int(ex.get("golpes", 1))))
    ]


def montar_extra_pendente(owner: ParticipanteCombate, alvo: ParticipanteCombate, ex: dict, encerra: bool) -> AcaoPendente:
    fila = _golpes_extra(ex)
    return AcaoPendente(
        owner.personagem_id, alvo.personagem_id, ex["skill"], fila=fila, n_main=len(fila),
        roll_atacante=ex["roll"], pos_main_feito=True, encerra_turno=encerra, so_extra=True,
    )


def ativar_contra(p: ParticipanteCombate, skill: dict, cfg: dict) -> None:
    p.contras = [k for k in p.contras if k["nome"] != skill["nome"]]
    p.contras.append({
        "nome": skill["nome"], "gatilho": cfg["gatilho"], "tratamento": cfg.get("tratamento", "SOFRE"),
        "formula": cfg["formula"], "restante": cfg["duracao"],
    })


def _aplicar_dot(atacante: ParticipanteCombate, alvo: ParticipanteCombate, skill: dict, cfg: dict) -> str:
    existente = next((d for d in alvo.dots if d["nome"] == skill["nome"] and d["fonte_id"] == atacante.personagem_id), None)
    if existente:
        existente["restante"] = cfg["duracao"]
        if cfg.get("empilhavel"):
            existente["stacks"] = min(int(cfg.get("max_stacks") or 1), existente["stacks"] + 1)
        return f"☠️ **{skill['nome']}** em {alvo.nome} (x{existente['stacks']})"
    alvo.dots.append({
        "nome": skill["nome"], "fonte_id": atacante.personagem_id, "base": cfg["base"],
        "formula": cfg["formula"], "stat_atacante": atacante.stat(atacante.stat_principal),
        "restante": cfg["duracao"], "stacks": 1, "empilhavel": cfg.get("empilhavel", False),
        "max_stacks": int(cfg.get("max_stacks") or 1),
    })
    dur = "permanente" if cfg["duracao"] == DURACAO_PERMANENTE else f"{cfg['duracao']} turno(s)"
    return f"☠️ **{skill['nome']}** aplicado em {alvo.nome} ({dur})"


# ---------------------------------------------------------------- golpe
def resolver_golpe(c: CombateState, pend: AcaoPendente, total_def: int, bloqueio: bool = False) -> str:
    item = pend.fila[pend.idx]
    atacante, alvo = c.obter(pend.atacante_id), c.obter(pend.alvo_id)
    total_atk = pend.total_atacante
    pre = "⚡ " if item["extra"] else ""
    receptor, fator = alvo, 1.0
    if bloqueio:
        pend.bloqueou = True
        fator = 0.5
    if bloqueio or total_atk >= total_def:  # empate favorece o atacante
        if not item["extra"]:
            if bloqueio:
                pend.main_bloqueios += 1
            else:
                pend.main_acertos += 1
                pend.melhor_roll = max(pend.melhor_roll, total_atk)
        if bloqueio:
            cab = (f"🧱 Bloqueado por **{receptor.nome}**! " if receptor is not alvo
                   else "🧱 Bloqueado! (-50% de dano) ")
        else:
            cab = "💥 Acertou! "
        efeito = ""
        hp_def = (0, 0)
        if item["formula"]:
            ref = atacante.stat(item["stat"] or atacante.stat_principal)
            dano = int(calcular_valor_formula(item["formula"], ref) * item["mult"] * fator * pend.fator_adj)
            nota = ""
            contra = next((k for k in receptor.contras if k["gatilho"] == "ATACADO"), None)
            if contra:
                dano = int(dano * FATOR_TRATAMENTO.get(contra["tratamento"], 1.0))
                nota = f" *(reduzido por {contra['nome']})*" if dano else f" *(ignorado por {contra['nome']})*"
            d_def, d_hp = cd.aplicar_dano(receptor, dano)
            partes = ([f"🛡️ -{d_def} DEF"] if d_def else []) + ([f"💔 -{d_hp} HP"] if d_hp else [])
            efeito = (" e ".join(p.split(" ", 1)[1] for p in partes) or "sem dano efetivo") + nota
            hp_def = (d_def, d_hp)
            txt = f"{pre}{cab}" + (" e ".join(partes) or "sem dano efetivo") + nota
        else:
            txt = f"{pre}{cab}".rstrip()
        pend.golpes.append({"extra": item["extra"], "tipo": "bloqueio" if bloqueio else "acerto", "efeito": efeito,
                            "def": hp_def[0], "hp": hp_def[1]})
    else:
        pend.errou = True
        txt = f"{pre}💨 Errou!"
        pend.golpes.append({"extra": item["extra"], "tipo": "erro", "efeito": "", "def": 0, "hp": 0})
    return txt


_ORD = ["Primeiro", "Segundo", "Terceiro", "Quarto", "Quinto", "Sexto", "Sétimo", "Oitavo", "Nono", "Décimo"]


def _descrever(golpes: list[dict], prefixo: str = "") -> tuple[str, list[str]]:
    """Devolve (resultado do cabeçalho, linhas de detalhe) sem comparar rolagens."""
    n = len(golpes)
    if n == 1:
        g = golpes[0]
        cab = {"acerto": "Acertou!", "bloqueio": "Bloqueado!", "erro": "Errou!"}[g["tipo"]]
        return cab, ([g["efeito"]] if g["efeito"] else [])
    acertos = sum(1 for g in golpes if g["tipo"] != "erro")
    erros = n - acertos
    if erros == 0:
        cab = f"{acertos} Acertaram!"
    elif acertos == 0:
        cab = f"{erros} Erraram!"
    else:
        cab = f"{acertos} {'Acertou' if acertos == 1 else 'Acertaram'}, {erros} {'Errou' if erros == 1 else 'Erraram'}!"
    linhas = []
    if erros:
        td, th = sum(g.get("def", 0) for g in golpes), sum(g.get("hp", 0) for g in golpes)
        partes = ([f"-{td} DEF"] if td else []) + ([f"-{th} HP"] if th else [])
        return cab, ([f"Causando {' e '.join(partes)}"] if partes else [])
    for i, g in enumerate(golpes):
        nome = f"{_ORD[i] if i < len(_ORD) else str(i + 1) + 'º'} Ataque"
        if g["tipo"] == "erro":
            linhas.append(f"{nome} errou")
        else:
            bloq = " (bloqueado)" if g["tipo"] == "bloqueio" else ""
            linhas.append(f"{nome}{bloq} causou {g['efeito']}" if g["efeito"] else f"{nome}{bloq} acertou")
    return cab, linhas


def _pos_principal(c: CombateState, pend: AcaoPendente) -> None:
    plano, skill = pend.plano, pend.skill
    if not plano or not skill:
        return
    atacante, alvo = c.obter(pend.atacante_id), c.obter(pend.alvo_id)
    if plano["dot"] and alvo.vivo and (pend.main_acertos + pend.main_bloqueios) > 0:
        pend.resumo.append(_aplicar_dot(atacante, alvo, skill, plano["dot"]))
    if plano["contra"] and pend.primeiro_alvo:
        ativar_contra(atacante, skill, plano["contra"])
        pend.resumo.append(f"🔄 Postura **{skill['nome']}** ativada")

    ex = plano["extra"]
    if not ex or not alvo.vivo:
        return
    cond = ex["condicao"]
    if cond == "PERMANECE":
        atacante.extras_pend.append({
            "skill": skill, "roll": pend.roll_atacante, "formula": ex["formula"], "golpes": ex["golpes"],
            "alvo_id": alvo.personagem_id, "momento": ex.get("momento") or "INICIO_ATACANTE", "rodada": c.rodada,
        })
        pend.resumo.append("⚡ Ataque extra ficará armado para o próximo turno")
        return
    param = str(ex.get("parametro") or "").strip().lower()
    if cond == "SEMPRE":
        ok = True
    elif cond == "ACERTAR":
        ok = (pend.main_acertos + pend.main_bloqueios) > 0
    elif cond == "ERRAR":
        ok = pend.main_acertos == 0 and not pend.bloqueou
    elif cond == "EFEITO":
        ok = bool(param) and any(param in d["nome"].lower() for d in alvo.dots)
    elif cond == "ROLAGEM":
        ok = param.isdigit() and pend.melhor_roll >= int(param)
    else:
        ok = False
    if ok:
        pend.fila.extend(_golpes_extra(ex))
        pend.resumo.append("⚡ Ataque extra ativado!")


# ---------------------------------------------------------------- fluxo
async def _painel(canal, c):
    from bot.combat.combate_views import atualizar_painel
    await atualizar_painel(canal, c)
    reiniciar_timer(canal, c)


# ---------------------------------------------------------------- temporizador
def reiniciar_timer(canal, c: CombateState) -> None:
    """Reinicia o temporizador de inatividade (5 min) da batalha."""
    if c.timer:
        c.timer.cancel()
        c.timer = None
    if c.status != "EM_ANDAMENTO" or obter_combate(c.canal_id) is not c or c.vencedor():
        return
    c.timer = asyncio.create_task(_esperar(canal, c))


async def _esperar(canal, c: CombateState) -> None:
    try:
        await asyncio.sleep(TEMPO_INATIVIDADE)
    except asyncio.CancelledError:
        return
    c.timer = None
    try:
        await _expirou(canal, c)
    except Exception:
        traceback.print_exc()


async def _expirou(canal, c: CombateState) -> None:
    if obter_combate(c.canal_id) is not c or c.vencedor():
        return
    pend = c.acao_pendente
    if pend and pend.aguardando == "DEFENSOR":
        alvo = c.obter(pend.alvo_id)
        if pend.defesa is None:
            pend.defesa = "DESVIAR"
        r = rolar_expressao("!" + pend.expr_defensor())
        for k, v in enumerate(r.valores_finais):
            pend.cache_def[pend.idx + k] = v
        resumo = resolver_golpe(c, pend, r.valores_finais[0])
        await canal.send(f"⏳ <@{alvo.owner_id}> demorou a responder — **{alvo.nome}** rolou automaticamente:\n"
                         f"{r.formatar()}\n{resumo}")
        await apos_golpe(canal, c)
        return
    if pend and not pend.encerra_turno:
        c.acao_pendente = None
        c.log("⏳ O tempo esgotou! O ataque extra foi cancelado por inatividade.")
        await _painel(canal, c)
        return
    ator = c.obter(pend.atacante_id) if pend else c.atual
    c.acao_pendente = None
    c.log(f"⏳ O tempo esgotou! **{ator.nome if ator else 'Alguém'}** perdeu a vez por inatividade.")
    await avancar_turno(canal, c)


# ---------------------------------------------------------------- fluxo
async def pedir_rolagem(canal, c: CombateState) -> None:
    pend = c.acao_pendente
    atacante = c.obter(pend.atacante_id)
    alvo = c.obter(pend.alvo_id)
    item = pend.fila[pend.idx]
    if item["extra"]:
        rot = f"⚡ Golpe extra {sum(1 for i in pend.fila[:pend.idx + 1] if i['extra'])}"
    else:
        rot = f"⚔️ Golpe {pend.idx + 1}/{pend.n_main}"
    if pend.idx in pend.cache_atk:  # ataque em área: reaproveita a rolagem do atacante
        pend.total_atacante = pend.cache_atk[pend.idx]
        await _pedir_defesa(canal, c, f"{rot} em **{alvo.nome}** — rolagem de **{atacante.nome}**: "
                                      f"**{pend.total_atacante}**")
        return
    await _painel(canal, c)
    await canal.send(f"{rot} — <@{atacante.owner_id}>, role `!{pend.expr_atacante()}` para **{atacante.nome}**!"
                     + (f" (todos os {pend._tam_lote()} golpes de uma vez)" if pend._tam_lote() > 1 else ""))


async def apos_rolagem_atacante(canal, c: CombateState, valores: list[int]) -> None:
    pend = c.acao_pendente
    for k, v in enumerate(valores):
        pend.cache_atk[pend.idx + k] = v
    pend.total_atacante = valores[0]
    await _pedir_defesa(canal, c, "")


async def _pedir_defesa(canal, c: CombateState, prefixo: str) -> None:
    pend = c.acao_pendente
    alvo = c.obter(pend.alvo_id)
    pend.aguardando = "DEFENSOR"
    if pend.defesa == "BLOQUEAR_SI":
        await resolver_bloqueio(canal, c)
        return
    if pend.defesa == "DESVIAR" and pend.idx in pend.cache_def:  # rolagem em lote já feita
        resumo = resolver_golpe(c, pend, pend.cache_def[pend.idx])
        await canal.send(f"{prefixo}\n🛡️ **{alvo.nome}** ({pend.cache_def[pend.idx]}) — {resumo}".strip())
        await apos_golpe(canal, c)
        return
    await _painel(canal, c)
    if pend.defesa == "DESVIAR":
        lote = f" (todos os {pend._tam_lote()} golpes de uma vez)" if pend._tam_lote() > 1 else ""
        await canal.send(f"{prefixo}\n🛡️ <@{alvo.owner_id}>, role `!{pend.expr_defensor()}` para **{alvo.nome}** desviar!{lote}".strip())
        return
    from bot.combat.combate_views import DefesaView
    await canal.send(
        f"{prefixo}\n🛡️ <@{alvo.owner_id}>, **{alvo.nome}** está sendo atacado! Escolha como se defender:".strip(),
        view=DefesaView(c, pend),
    )


async def resolver_bloqueio(canal, c: CombateState) -> None:
    pend = c.acao_pendente
    resumo = resolver_golpe(c, pend, 0, bloqueio=True)
    await canal.send(resumo)
    await apos_golpe(canal, c)


async def iniciar_pendencia(canal, c: CombateState, pend: AcaoPendente) -> None:
    c.acao_pendente = pend
    await pedir_rolagem(canal, c)


async def apos_golpe(canal, c: CombateState) -> None:
    pend = c.acao_pendente
    alvo = c.obter(pend.alvo_id)
    pend.idx += 1
    pend.aguardando = "ATACANTE"
    pend.total_atacante = 0
    if alvo.vivo and pend.idx < pend.n_main:
        await pedir_rolagem(canal, c)
        return
    if not pend.pos_main_feito:
        pend.pos_main_feito = True
        _pos_principal(c, pend)
    if alvo.vivo and pend.idx < len(pend.fila):
        await pedir_rolagem(canal, c)
        return
    await concluir(canal, c)


async def _checar_fim(canal, c: CombateState) -> bool:
    for entrou in c.repor_reservas():
        c.log_extra(f"🔁 **{entrou.nome}** entrou em campo da reserva!")
    vencedor = c.vencedor()
    if vencedor:
        await _painel(canal, c)
        anuncio = "🏁 **Empate!**" if vencedor == "EMPATE" else f"🏆 **Time {vencedor} venceu a batalha!**"
        await canal.send(anuncio)
        encerrar_combate(c.canal_id)
        return True
    return False


async def concluir(canal, c: CombateState) -> None:
    pend = c.acao_pendente
    atacante, alvo = c.obter(pend.atacante_id), c.obter(pend.alvo_id)
    nome = pend.skill["nome"] if pend.skill else "Ataque Básico"
    pre = "⚡ Ataque extra de " if pend.so_extra else ""
    principais = [g for g in pend.golpes if pend.so_extra or not g["extra"]]
    extras = [] if pend.so_extra else [g for g in pend.golpes if g["extra"]]
    cab, linhas = _descrever(principais) if principais else ("", [])
    texto = f"{pre}**{atacante.nome}** usou **{nome}** em **{alvo.nome}** — {cab}"
    if linhas:
        texto += "\n\u200b\n" + "\n\u200b\n".join(linhas)
    notas = [r for r in pend.resumo if not r.startswith("⚡")]
    notas_extra = [r for r in pend.resumo if r.startswith("⚡")]
    if notas:
        texto += "\n" + "\n".join(notas)
    for r in notas_extra:
        texto += "\n" + r
    if extras:
        cab_e, linhas_e = _descrever(extras)
        texto += f"\n\u200b\n⚡ Golpe extra — {cab_e}"
        if linhas_e:
            texto += "\n\u200b\n" + "\n\u200b\n".join(linhas_e)
    if pend.primeiro_alvo and not pend.so_extra:
        c.log(texto)
    else:
        c.log_extra(texto)

    if alvo.vivo and atacante.vivo:
        for k in alvo.contras:
            if (k["gatilho"] == "ATACADO") or (k["gatilho"] == "DESVIO" and pend.errou):
                dano = calcular_valor_formula(k["formula"], alvo.stat(alvo.stat_principal))
                d_def, d_hp = cd.aplicar_dano(atacante, dano)
                partes = ([f"🛡️ -{d_def} DEF"] if d_def else []) + ([f"💔 -{d_hp} HP"] if d_hp else [])
                c.log_extra(f"🔄 **{alvo.nome}** contra-atacou com **{k['nome']}** (acerto garantido): "
                            + (" e ".join(partes) or "sem dano efetivo"))
                if not atacante.vivo:
                    break

    c.acao_pendente = None
    if await _checar_fim(canal, c):
        return
    restantes = list(pend.alvos_restantes)
    while restantes and atacante.vivo:
        t = c.obter(restantes.pop(0))
        if t and t.vivo and t.em_campo:
            nova = montar_pendencia(atacante, t, pend.skill, pend.mult, restantes, pend.cache_atk, False)
            if ((pend.skill or {}).get("dados") or {}).get("alcance") == "ADJACENTES":
                nova.fator_adj = 0.5
            nova.encerra_turno = pend.encerra_turno
            await iniciar_pendencia(canal, c, nova)
            return
    await _fechar(canal, c, atacante, pend.encerra_turno)


async def _fechar(canal, c: CombateState, atacante: ParticipanteCombate, encerra: bool) -> None:
    if encerra:
        if atacante.vivo and await _gatilhos_fim(canal, c, atacante):
            return
        await avancar_turno(canal, c)
    elif not await _gatilhos_inicio(canal, c, c.atual):
        await novo_painel(canal, c)


async def novo_painel(canal, c: CombateState) -> None:
    """Apaga o painel antigo e envia um novo, avisando o dono do personagem da vez."""
    from bot.combat.combate_views import enviar_novo_painel
    await enviar_novo_painel(canal, c)
    reiniciar_timer(canal, c)


async def fim_sem_rolagem(canal, c: CombateState, atacante: ParticipanteCombate, texto: str) -> None:
    c.log(texto)
    await _fechar(canal, c, atacante, True)


async def avancar_turno(canal, c: CombateState) -> None:
    proximo = c.passar_turno()
    if c.eventos:
        c.log_extra("\n".join(c.eventos))
        c.eventos = []
    if await _checar_fim(canal, c):
        return
    if not proximo:
        await _painel(canal, c)
        return
    if not await _gatilhos_inicio(canal, c, proximo):
        await novo_painel(canal, c)


async def _lancar(canal, c, owner, ex, encerra) -> bool:
    owner.extras_pend.remove(ex)
    alvo = c.obter(ex["alvo_id"])
    if not alvo or not alvo.vivo or not owner.vivo:
        return False
    c.log_extra(f"⚡ O ataque extra armado de **{owner.nome}** ({ex['skill']['nome']}) dispara!")
    await iniciar_pendencia(canal, c, montar_extra_pendente(owner, alvo, ex, encerra))
    return True


async def _gatilhos_inicio(canal, c: CombateState, proximo: ParticipanteCombate | None) -> bool:
    if not proximo:
        return False
    for ex in list(proximo.extras_pend):
        if ex["momento"] == "INICIO_ATACANTE" and c.rodada > ex["rodada"]:
            if await _lancar(canal, c, proximo, ex, False):
                return True
    for p in c.participantes:
        for ex in list(p.extras_pend):
            if ex["momento"] == "TURNO_ALVO" and ex["alvo_id"] == proximo.personagem_id:
                if await _lancar(canal, c, p, ex, False):
                    return True
    return False


async def _gatilhos_fim(canal, c: CombateState, atacante: ParticipanteCombate) -> bool:
    for ex in list(atacante.extras_pend):
        if ex["momento"] == "FIM_ATACANTE" and c.rodada > ex["rodada"]:
            if await _lancar(canal, c, atacante, ex, True):
                return True
    return False
