"""
Cálculo de dano em combate.
"""
from bot.combat.combate_manager import TURNOS_REGEN_DEF, ParticipanteCombate
from bot.combat.formulas import calcular_valor_formula  # noqa: F401 (reexport)

FORMULA_PADRAO = {"modo": "PERCENT", "percentual": 100}


def carga_infinita(cfg: dict) -> bool:
    return cfg.get("max_turnos") in (-1, 9999, "INFINITO", "infinito")


def plano_skill(skill: dict) -> dict:
    """Resume o que a skill faz em combate a partir do dano configurado."""
    dano = (skill.get("dados") or {}).get("dano") or {}
    cfg = dano.get("config") or {}
    subs = dano.get("subtipos") or []
    plano = {
        "formula": None,
        "golpes": 1,
        "carregado": cfg.get("CARREGADO") if "CARREGADO" in subs else None,
        "extra": cfg.get("EXTRA") if "EXTRA" in subs else None,
        "dot": cfg.get("DOT") if "DOT" in subs else None,
        "contra": cfg.get("CONTRA") if "CONTRA" in subs else None,
    }
    if "MULTIPLOS" in subs and cfg.get("MULTIPLOS"):
        plano["formula"] = cfg["MULTIPLOS"]["formula"]
        plano["golpes"] = max(1, int(cfg["MULTIPLOS"].get("golpes", 1)))
    elif "BRUTO" in subs and cfg.get("BRUTO"):
        plano["formula"] = cfg["BRUTO"]["formula"]
    if plano["carregado"]:
        plano["formula"] = plano["carregado"]["formula"]
    if not subs:
        plano["formula"] = FORMULA_PADRAO
    # só precisa de rolagem de acerto se causa dano, aplica DoT ou tem ataque extra
    plano["rola"] = bool(plano["formula"] or plano["dot"] or plano["extra"])
    return plano


def aplicar_dano(alvo: ParticipanteCombate, dano: int) -> tuple[int, int]:
    """O dano vai primeiro na DEF; o excedente vai no HP. Retorna (dano_def, dano_hp)."""
    dano_def = min(alvo.def_atual, dano)
    alvo.def_atual -= dano_def
    if dano_def and alvo.def_atual == 0 and alvo.def_regen is None:
        alvo.def_regen = TURNOS_REGEN_DEF
    dano_hp = min(alvo.hp_atual, dano - dano_def)
    alvo.hp_atual -= dano_hp
    return dano_def, dano_hp
