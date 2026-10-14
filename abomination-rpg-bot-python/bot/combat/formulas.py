"""Fórmulas de dano (sem dependências, para evitar importações circulares)."""


def calcular_valor_formula(formula: dict, stat_valor: int) -> int:
    perc = formula.get("percentual", 100)
    if formula.get("modo") == "SOMA":
        return max(1, int(stat_valor * (1 + perc / 100)))
    return max(1, int(stat_valor * perc / 100))
