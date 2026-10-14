"""
Modelo de dano das skills.

Uma skill do tipo DANO pode combinar vários subtipos (ex.: Ataque Extra + DoT).
Cada subtipo guarda sua própria configuração. Tudo é salvo em skills.dados["dano"]:

    {
      "subtipos": ["BRUTO", "DOT"],
      "config": {
        "BRUTO": {"formula": {"modo": "SOMA", "percentual": 50}},
        "DOT": {...}
      }
    }

Fórmula: {"modo": "SOMA", "percentual": 50}  -> STAT principal + 50%
         {"modo": "PERCENT", "percentual": 75} -> 75% do STAT principal
"""

SUBTIPOS = [
    ("BRUTO", "Dano Bruto", "💥"),
    ("MULTIPLOS", "Múltiplos Golpes", "🗡️"),
    ("EXTRA", "Ataque Extra", "⚡"),
    ("DOT", "Dano Contínuo (DoT)", "☠️"),
    ("CONTRA", "Contra-ataque", "🔄"),
    ("CARREGADO", "Ataque Carregado", "⏳"),
]
NOME_SUBTIPO = {k: n for k, n, _ in SUBTIPOS}
EMOJI_SUBTIPO = {k: e for k, _, e in SUBTIPOS}

CONDICOES_EXTRA = {
    "SEMPRE": "Sempre (junto do ataque principal)",
    "ACERTAR": "Se o ataque principal acertar",
    "ERRAR": "Se o ataque principal errar",
    "EFEITO": "Se o alvo tiver Buff/Debuff específico",
    "ROLAGEM": "Por rolagem (valor mínimo no dado)",
    "PERMANECE": "Permanece até o próximo turno",
}
MOMENTOS_PERMANECE = {
    "INICIO_ATACANTE": "Início do próximo turno do atacante",
    "FIM_ATACANTE": "Fim do próximo turno do atacante",
    "TURNO_ALVO": "Quando o alvo agir",
}
BASES_DOT = {
    "STAT_ATACANTE": "STAT principal do atacante",
    "STAT_ALVO": "STAT principal do alvo",
    "HP_MAX_ALVO": "HP máximo do alvo",
    "HP_ATUAL_ALVO": "HP atual do alvo",
}
GATILHOS_CONTRA = {
    "ATACADO": "Ao ser atacado",
    "DESVIO": "Ao desviar de um ataque",
}
TRATAMENTO_CONTRA = {
    "SOFRE": "Sofre o dano normalmente",
    "IGNORA": "Ignora o dano recebido",
    "REDUZ_25": "Dano recebido reduzido em 25%",
    "REDUZ_50": "Dano recebido reduzido em 50%",
    "REDUZ_75": "Dano recebido reduzido em 75%",
}
DURACAO_PERMANENTE = 9999


ALCANCES = [
    ("🎯 Alvo único", "UNICO"),
    ("🎯👥 Alvo principal + adjacentes", "ADJACENTES"),
    ("🌐 Ataque em área", "AREA"),
    ("👥💥 Todos (incluindo aliados)", "TODOS"),
]
ALCANCE_ROTULOS = {val: lbl for lbl, val in ALCANCES}


def parse_formula(texto: str) -> dict:
    """'+50' ou '+50%' -> STAT + 50%.  '75' ou '75%' -> 75% do STAT."""
    t = texto.strip().replace(" ", "").replace(",", ".").rstrip("%")
    modo = "PERCENT"
    if t.startswith("+"):
        modo = "SOMA"
        t = t[1:]
    try:
        valor = float(t)
    except ValueError:
        raise ValueError("fórmula inválida")
    if valor <= 0:
        raise ValueError("fórmula inválida")
    if valor == int(valor):
        valor = int(valor)
    return {"modo": modo, "percentual": valor}


def formatar_formula(f: dict, base: str = "STAT principal") -> str:
    if f["modo"] == "SOMA":
        return f"{base} + {f['percentual']}%"
    return f"{f['percentual']}% de {base}"


def _dur(d: int) -> str:
    return "Permanente" if d == DURACAO_PERMANENTE else f"{d} turno(s)"


def resumo_subtipo(chave: str, c: dict) -> str:
    if chave == "BRUTO":
        return f"Fórmula: {formatar_formula(c['formula'])}"
    if chave == "MULTIPLOS":
        return f"{c['golpes']} golpes de {formatar_formula(c['formula'])} cada"
    if chave == "EXTRA":
        cond = CONDICOES_EXTRA[c["condicao"]]
        extra = ""
        if c["condicao"] == "EFEITO":
            extra = f" (Buff/Debuff: {c['parametro']})"
        elif c["condicao"] == "ROLAGEM":
            extra = f" (mínimo {c['parametro']})"
        elif c["condicao"] == "PERMANECE":
            extra = f" ({MOMENTOS_PERMANECE[c['momento']]})"
        golpes = f"{c['golpes']} golpe(s) extra(s) de "
        return f"{cond}{extra}\nCausa {golpes}{formatar_formula(c['formula'])}"
    if chave == "DOT":
        base = BASES_DOT[c["base"]]
        stack = f"empilhável até {c['max_stacks']}x" if c["empilhavel"] else "não empilhável"
        return (
            f"Fórmula: {formatar_formula(c['formula'], base)} por turno\n"
            f"Duração: {_dur(c['duracao'])} · {stack}"
        )
    if chave == "CONTRA":
        return (
            f"{GATILHOS_CONTRA[c['gatilho']]} · {TRATAMENTO_CONTRA[c['tratamento']]}\n"
            f"Revide: {formatar_formula(c['formula'])} (acerto garantido) · {_dur(c['duracao'])}"
        )
    if chave == "CARREGADO":
        max_turnos = "Infinitos" if c["max_turnos"] in (-1, 9999, "INFINITO", "infinito") else f"{c['max_turnos']}"
        linhas = [
            f"Carrega de {c['min_turnos']} a {max_turnos} turno(s)",
            f"Fórmula: {formatar_formula(c['formula'])}",
            f"+{c['bonus_por_turno']}% de dano por turno carregado",
        ]
        return "\n".join(linhas)
    return ""


def resumo_dano(dano: dict | None, mostrar_pendentes: bool = False) -> str:
    if not dano or not dano.get("subtipos"):
        return "*Nenhum subtipo de dano selecionado.*"
    linhas = []
    for chave in dano["subtipos"]:
        titulo = f"{EMOJI_SUBTIPO[chave]} **{NOME_SUBTIPO[chave]}**"
        c = dano["config"].get(chave)
        if c:
            linhas.append(f"{titulo}\n{resumo_subtipo(chave, c)}")
        elif mostrar_pendentes:
            linhas.append(f"{titulo}\n⚠️ *Ainda não configurado*")
    return "\n\n".join(linhas) if linhas else "*Nenhum subtipo de dano selecionado.*"


def dano_pendentes(dano: dict | None) -> list[str]:
    """Subtipos selecionados que ainda não foram configurados (vazio = tudo certo)."""
    if not dano or not dano.get("subtipos"):
        return ["(nenhum subtipo selecionado)"]
    return [NOME_SUBTIPO[k] for k in dano["subtipos"] if k not in dano["config"]]
