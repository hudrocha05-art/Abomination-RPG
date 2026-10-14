"""
Painel de configuração do dano de uma skill (subtipos combináveis).

Fluxo: no painel do criador de habilidade, o botão "Configurar Dano" troca a
mensagem por este painel. Lá o criador marca os subtipos (Bruto, Múltiplos
Golpes, Ataque Extra, DoT, Contra-ataque, Ataque Carregado) e configura cada
um em um formulário próprio.
"""
import discord

from bot import dano as D


class _FormInvalido(Exception):
    pass


def _inteiro(txt: str, campo: str, minimo: int = 1) -> int:
    try:
        v = int(txt.strip())
    except ValueError:
        raise _FormInvalido(f"**{campo}** deve ser um número inteiro.")
    if v < minimo:
        raise _FormInvalido(f"**{campo}** deve ser no mínimo {minimo}.")
    return v


def _formula(txt: str) -> dict:
    try:
        return D.parse_formula(txt)
    except ValueError:
        raise _FormInvalido(
            "**Fórmula inválida.** Use `+50` para STAT + 50%, ou `75` para 75% do STAT."
        )


def _select_label(texto: str, opcoes: dict[str, str], atual: str | None, obrigatorio: bool = True) -> tuple[discord.ui.Label, discord.ui.Select]:
    select = discord.ui.Select(
        options=[
            discord.SelectOption(label=rotulo[:100], value=valor, default=(valor == atual))
            for valor, rotulo in opcoes.items()
        ],
        required=obrigatorio,
        min_values=1 if obrigatorio else 0,
    )
    return discord.ui.Label(text=texto[:45], component=select), select


def _texto(label: str, placeholder: str = "", default: str | None = None, required: bool = True,
           paragrafo: bool = False, max_length: int | None = None) -> discord.ui.TextInput:
    return discord.ui.TextInput(
        label=label[:45],
        placeholder=placeholder[:100],
        default=default,
        required=required,
        max_length=max_length,
        style=discord.TextStyle.paragraph if paragrafo else discord.TextStyle.short,
    )


def _fmt_formula(c: dict | None) -> str | None:
    if not c:
        return None
    f = c["formula"]
    return ("+" if f["modo"] == "SOMA" else "") + str(f["percentual"])


class _DanoModal(discord.ui.Modal):
    CHAVE = ""
    TITULO = ""

    def __init__(self, painel):
        super().__init__(title=self.TITULO)
        self.painel = painel
        self.atual = painel.dano["config"].get(self.CHAVE)

    def construir(self) -> dict:
        raise NotImplementedError

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            config = self.construir()
        except _FormInvalido as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
            return
        self.painel.dano["config"][self.CHAVE] = config
        view = DanoConfigView(self.painel)
        await interaction.response.edit_message(embed=view.montar_embed(), view=view)


FORMULA_PLACEHOLDER = "+50 = STAT + 50%  |  75 = 75% do STAT"


class BrutoModal(_DanoModal):
    CHAVE = "BRUTO"
    TITULO = "Dano Bruto"

    def __init__(self, painel):
        super().__init__(painel)
        self.formula = _texto("Fórmula de dano", FORMULA_PLACEHOLDER, _fmt_formula(self.atual))
        self.add_item(self.formula)

    def construir(self) -> dict:
        return {"formula": _formula(self.formula.value)}


class MultiplosModal(_DanoModal):
    CHAVE = "MULTIPLOS"
    TITULO = "Múltiplos Golpes"

    def __init__(self, painel):
        super().__init__(painel)
        a = self.atual
        self.golpes = _texto("Quantidade de golpes", "Ex: 5", str(a["golpes"]) if a else None)
        self.formula = _texto("Fórmula de cada golpe", FORMULA_PLACEHOLDER, _fmt_formula(a))
        self.add_item(self.golpes)
        self.add_item(self.formula)

    def construir(self) -> dict:
        return {"golpes": _inteiro(self.golpes.value, "Quantidade de golpes", 2), "formula": _formula(self.formula.value)}


class ExtraModal(_DanoModal):
    CHAVE = "EXTRA"
    TITULO = "Ataque Extra"

    def __init__(self, painel):
        super().__init__(painel)
        a = self.atual or {}
        lbl_cond, self.cond = _select_label("Condição do ataque extra", D.CONDICOES_EXTRA, a.get("condicao"))
        lbl_mom, self.momento = _select_label(
            "Se 'Permanece': quando dispara?", D.MOMENTOS_PERMANECE, a.get("momento"), obrigatorio=False
        )
        self.formula = _texto("Fórmula do ataque extra", FORMULA_PLACEHOLDER, _fmt_formula(self.atual))
        self.golpes = _texto("Quantidade de golpes extras", "Ex: 1 ou 3", str(a["golpes"]) if a.get("golpes") else "1", required=True)
        self.parametro = _texto(
            "Buff/Debuff (se Efeito) ou Mínimo (se Rolagem)", "Ex: Queimadura ou 15",
            str(a["parametro"]) if a.get("parametro") is not None else None, required=False,
        )
        for item in (lbl_cond, lbl_mom, self.formula, self.golpes, self.parametro):
            self.add_item(item)

    def construir(self) -> dict:
        cond = self.cond.values[0]
        momento = self.momento.values[0] if self.momento.values else None
        if cond == "PERMANECE" and not momento:
            raise _FormInvalido("Escolha **quando o ataque que permanece dispara**.")
        golpes = _inteiro(self.golpes.value, "Quantidade de golpes extras", 1)
        param = self.parametro.value.strip()
        if cond == "EFEITO" and not param:
            raise _FormInvalido("Informe o **nome do Buff ou Debuff** do alvo no último campo.")
        if cond == "ROLAGEM":
            param = _inteiro(param or "x", "Valor mínimo da rolagem", 1)
        return {
            "condicao": cond,
            "momento": momento,
            "formula": _formula(self.formula.value),
            "golpes": golpes,
            "parametro": param or None,
        }


class DotModal(_DanoModal):
    CHAVE = "DOT"
    TITULO = "Dano Contínuo (DoT)"

    def __init__(self, painel):
        super().__init__(painel)
        a = self.atual or {}
        lbl_base, self.base = _select_label("Base do cálculo", D.BASES_DOT, a.get("base"))
        lbl_emp, self.emp = _select_label(
            "Empilhável?", {"SIM": "Sim, empilha", "NAO": "Não empilha"},
            None if not a else ("SIM" if a["empilhavel"] else "NAO"),
        )
        self.formula = _texto("Fórmula por turno", FORMULA_PLACEHOLDER, _fmt_formula(self.atual))
        dur = a.get("duracao")
        self.duracao = _texto(
            "Duração (turnos ou 'permanente')", "Ex: 3",
            None if dur is None else ("permanente" if dur == D.DURACAO_PERMANENTE else str(dur)),
        )
        self.stacks = _texto(
            "Máx. de stacks (se empilhável)", "Ex: 5",
            str(a["max_stacks"]) if a.get("max_stacks") else None, required=False,
        )
        for item in (lbl_base, lbl_emp, self.formula, self.duracao, self.stacks):
            self.add_item(item)

    def construir(self) -> dict:
        txt = self.duracao.value.strip().lower()
        duracao = D.DURACAO_PERMANENTE if txt == "permanente" else _inteiro(txt, "Duração", 1)
        empilhavel = self.emp.values[0] == "SIM"
        max_stacks = None
        if empilhavel:
            if not self.stacks.value.strip():
                raise _FormInvalido("Informe o **máximo de stacks**, já que o DoT é empilhável.")
            max_stacks = _inteiro(self.stacks.value, "Máx. de stacks", 2)
        return {
            "base": self.base.values[0],
            "formula": _formula(self.formula.value),
            "duracao": duracao,
            "empilhavel": empilhavel,
            "max_stacks": max_stacks,
        }


class ContraModal(_DanoModal):
    CHAVE = "CONTRA"
    TITULO = "Contra-ataque"

    def __init__(self, painel):
        super().__init__(painel)
        a = self.atual or {}
        lbl_g, self.gatilho = _select_label("Gatilho", D.GATILHOS_CONTRA, a.get("gatilho"))
        lbl_t, self.trat = _select_label(
            "Se atacado: o dano recebido...", D.TRATAMENTO_CONTRA, a.get("tratamento"), obrigatorio=False
        )
        self.formula = _texto("Fórmula do revide", FORMULA_PLACEHOLDER, _fmt_formula(self.atual))
        self.duracao = _texto("Duração (em turnos)", "Ex: 2", str(a["duracao"]) if a else None)
        for item in (lbl_g, lbl_t, self.formula, self.duracao):
            self.add_item(item)

    def construir(self) -> dict:
        return {
            "gatilho": self.gatilho.values[0],
            "tratamento": self.trat.values[0] if self.trat.values else "SOFRE",
            "formula": _formula(self.formula.value),
            "duracao": _inteiro(self.duracao.value, "Duração", 1),
        }


class CarregadoModal(_DanoModal):
    CHAVE = "CARREGADO"
    TITULO = "Ataque Carregado"

    def __init__(self, painel):
        super().__init__(painel)
        a = self.atual or {}
        max_turnos_val = a.get("max_turnos")
        if max_turnos_val in (-1, 9999, "INFINITO", "infinito"):
            max_turnos_txt = "infinito"
        elif max_turnos_val is not None:
            max_turnos_txt = str(max_turnos_val)
        else:
            max_turnos_txt = None

        self.minimo = _texto("Mínimo de turnos carregando", "Ex: 1", str(a["min_turnos"]) if a else None)
        self.maximo = _texto("Máximo de turnos ('infinito' ou número)", "Ex: 3 ou infinito", max_turnos_txt)
        self.formula = _texto("Fórmula do ataque liberado", FORMULA_PLACEHOLDER, _fmt_formula(self.atual))
        self.bonus = _texto(
            "Bônus de dano por turno (%)", "Ex: 20",
            str(a["bonus_por_turno"]) if a.get("bonus_por_turno") else None, required=True,
        )
        for item in (self.minimo, self.maximo, self.formula, self.bonus):
            self.add_item(item)

    def construir(self) -> dict:
        minimo = _inteiro(self.minimo.value, "Mínimo de turnos", 1)
        max_txt = self.maximo.value.strip().lower()
        if max_txt in ("infinito", "infinita", "inf", "infinitas", "infinitas vezes"):
            maximo = -1
        else:
            maximo = _inteiro(self.maximo.value, "Máximo de turnos", 1)
            if maximo < minimo:
                raise _FormInvalido("O **máximo** de turnos não pode ser menor que o mínimo.")
        bonus = _inteiro(self.bonus.value, "Bônus por turno", 1)
        return {
            "min_turnos": minimo,
            "max_turnos": maximo,
            "formula": _formula(self.formula.value),
            "bonus_por_turno": bonus,
        }


MODAIS = {
    "BRUTO": BrutoModal,
    "MULTIPLOS": MultiplosModal,
    "EXTRA": ExtraModal,
    "DOT": DotModal,
    "CONTRA": ContraModal,
    "CARREGADO": CarregadoModal,
}


class DanoConfigView(discord.ui.View):
    """Substitui o painel da skill enquanto o dano está sendo configurado."""

    def __init__(self, painel):
        super().__init__(timeout=900)
        self.painel = painel
        self.montar_componentes()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.painel.interaction_check(interaction)

    @property
    def dano(self) -> dict:
        return self.painel.dano

    def montar_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"⚔️ Configurar Dano — {self.painel.nome}",
            description=(
                "Marque **um ou mais subtipos** (eles podem ser combinados) e configure cada um.\n"
                "A fórmula usa o **STAT principal** do personagem como base."
            ),
            color=discord.Color.red(),
        )
        embed.add_field(name="Configuração atual", value=D.resumo_dano(self.dano, mostrar_pendentes=True)[:1024], inline=False)
        return embed

    def montar_componentes(self) -> None:
        self.clear_items()
        select = discord.ui.Select(
            placeholder="Escolha os subtipos de dano",
            min_values=0,
            max_values=len(D.SUBTIPOS),
            options=[
                discord.SelectOption(
                    label=nome, value=chave, emoji=emoji, default=chave in self.dano["subtipos"]
                )
                for chave, nome, emoji in D.SUBTIPOS
            ],
            row=0,
        )
        select.callback = self._ao_escolher
        self.add_item(select)

        for i, (chave, nome, emoji) in enumerate(D.SUBTIPOS):
            selecionado = chave in self.dano["subtipos"]
            pronto = chave in self.dano["config"]
            b = discord.ui.Button(
                label=nome,
                emoji="✅" if pronto else emoji,
                style=discord.ButtonStyle.success if pronto else discord.ButtonStyle.primary,
                disabled=not selecionado,
                row=1 + i // 3,
            )
            b.callback = self._criar_callback_configurar(chave)
            self.add_item(b)

        voltar = discord.ui.Button(label="Voltar ao painel", emoji="↩️", style=discord.ButtonStyle.secondary, row=3)
        voltar.callback = self._ao_voltar
        self.add_item(voltar)

    def _criar_callback_configurar(self, chave: str):
        async def callback(interaction: discord.Interaction):
            await interaction.response.send_modal(MODAIS[chave](self.painel))
        return callback

    async def _ao_escolher(self, interaction: discord.Interaction) -> None:
        escolhidos = set(interaction.data["values"])
        self.dano["subtipos"] = [k for k, _, _ in D.SUBTIPOS if k in escolhidos]
        for chave in list(self.dano["config"]):
            if chave not in escolhidos:
                del self.dano["config"][chave]
        self.montar_componentes()
        await interaction.response.edit_message(embed=self.montar_embed(), view=self)

    async def _ao_voltar(self, interaction: discord.Interaction) -> None:
        self.stop()
        self.painel.montar_componentes()
        await interaction.response.edit_message(embed=self.painel.montar_embed(), view=self.painel)
