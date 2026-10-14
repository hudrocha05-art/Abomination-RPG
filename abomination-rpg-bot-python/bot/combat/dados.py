"""
Sistema de rolagem de dados para o Abomination RPG.

Suporta:
- d20 normal: !1d20, !d20, !d20+3, !1d20-2
- W20 (dado especial onde o valor mínimo do dado é 10): !W20, !1W20, !W20+3
- Múltiplos dados: !5d20, !3W20+2
- Dados genéricos: !2d6+1, !1d100
"""
import random
import re
from typing import Optional

PADRAO_DADO = re.compile(
    r"^!(\d+)?([dDwW])(\d+)?([+-]\d+)?$",
    re.IGNORECASE,
)


class ResultadoDadoIndividual:
    def __init__(self, bruto: int, tipo: str, lados: int, final: int):
        self.bruto = bruto
        self.tipo = tipo.upper()
        self.lados = lados
        self.final = final


class ResultadoRolagem:
    def __init__(
        self,
        quantidade: int,
        tipo_dado: str,
        lados: int,
        modificador: int,
        dados: list[ResultadoDadoIndividual],
        texto_original: str,
    ):
        self.quantidade = quantidade
        self.tipo_dado = tipo_dado.upper()
        self.lados = lados
        self.modificador = modificador
        self.dados = dados
        self.texto_original = texto_original

    @property
    def total(self) -> int:
        return sum(d.final for d in self.dados) + self.modificador

    @property
    def valores_finais(self) -> list[int]:
        """Lista com o valor final de cada dado + o modificador aplicado."""
        return [d.final + self.modificador for d in self.dados]

    def formatar(self) -> str:
        mod_txt = ""
        if self.modificador > 0:
            mod_txt = f"+{self.modificador}"
        elif self.modificador < 0:
            mod_txt = f"{self.modificador}"

        if self.quantidade == 1:
            d = self.dados[0]
            ajuste = f" *(ajustado de {d.bruto})*" if d.bruto != d.final else ""
            if self.modificador != 0:
                return f"🎲 **{self.total}** `[{d.final}{mod_txt}]`{ajuste}"
            return f"🎲 **{self.total}**{ajuste}"

        # Múltiplos dados (ex: !5d20)
        partes = [f"`{d.final}{mod_txt}`" if self.modificador else f"`{d.final}`" for d in self.dados]
        lista = ", ".join(partes)
        return f"🎲 **{self.quantidade}{self.tipo_dado}{self.lados}{mod_txt}** ➔ [{lista}] (Total: **{self.total}**)"


def rolar_expressao(texto: str) -> Optional[ResultadoRolagem]:
    """Interpreta comandos como !1d20, !d20+3, !W20, !5d20."""
    t = texto.strip()
    m = PADRAO_DADO.match(t)
    if not m:
        return None

    qtd_str, tipo, lados_str, mod_str = m.groups()
    qtd = int(qtd_str) if qtd_str else 1
    tipo = tipo.upper()

    if lados_str:
        lados = int(lados_str)
    else:
        lados = 20  # W20 ou d padrão é 20

    if qtd < 1 or qtd > 20:
        return None
    if lados < 2 or lados > 1000:
        return None

    mod = int(mod_str) if mod_str else 0

    dados = []
    for _ in range(qtd):
        bruto = random.randint(1, lados)
        final = bruto
        if tipo == "W":
            # W20: resultados abaixo de 10 viram 10
            if final < 10:
                final = 10
        dados.append(ResultadoDadoIndividual(bruto, tipo, lados, final))

    return ResultadoRolagem(qtd, tipo, lados, mod, dados, t)
