"""
Estado em memória dos combates (lobby + batalha todos contra todos).
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from bot.combat.formulas import calcular_valor_formula

DURACAO_PERMANENTE = 9999
MAX_EM_CAMPO = 4
TURNOS_REGEN_DEF = 5  # turnos do personagem até a DEF quebrada regenerar 50%


@dataclass
class ParticipanteCombate:
    personagem_id: str
    owner_id: str
    nome: str
    hp_max: int
    hp_atual: int
    atk: int
    def_base: int
    def_atual: int
    mst: int
    vel: int
    stat_principal: str = "ATK"
    em_campo: bool = True
    time: str = "A"
    cooldowns: dict[str, int] = field(default_factory=dict)  # skill_id -> turnos restantes
    dots: list[dict] = field(default_factory=list)
    contras: list[dict] = field(default_factory=list)
    carregando: Optional[dict] = None  # {"skill_id", "nome", "turnos"}
    extras_pend: list[dict] = field(default_factory=list)  # ataques extras "permanece"
    def_regen: Optional[int] = None  # turnos restantes para regenerar a DEF quebrada

    @property
    def vivo(self) -> bool:
        return self.hp_atual > 0

    def stat(self, nome: str) -> int:
        return {"ATK": self.atk, "DEF": self.def_base, "MST": self.mst, "VEL": self.vel,
                "HP": self.hp_max}.get(nome.upper(), self.atk)


@dataclass
class AcaoPendente:
    atacante_id: str
    alvo_id: str
    skill: Optional[dict]  # None = ataque básico
    fila: list[dict] = field(default_factory=list)  # golpes: {"formula", "extra", "mult", "stat"}
    n_main: int = 1
    idx: int = 0
    aguardando: str = "ATACANTE"  # "ATACANTE" ou "DEFENSOR"
    roll_atacante: str = "d20"
    roll_defensor: str = "d20"
    total_atacante: int = 0
    resumo: list[str] = field(default_factory=list)
    golpes: list[dict] = field(default_factory=list)
    plano: Optional[dict] = None
    main_acertos: int = 0
    melhor_roll: int = 0
    errou: bool = False
    pos_main_feito: bool = False
    encerra_turno: bool = True
    so_extra: bool = False
    mult: float = 1.0
    bloqueou: bool = False
    # alvos de ataques em área ainda por atacar (a rolagem do atacante é reaproveitada)
    alvos_restantes: list[str] = field(default_factory=list)
    cache_atk: dict = field(default_factory=dict)
    primeiro_alvo: bool = True
    fator_adj: float = 1.0  # adjacentes recebem metade do dano
    # defesa escolhida pelo alvo: None (aguardando escolha), DESVIAR ou BLOQUEAR_SI
    defesa: Optional[str] = None
    main_bloqueios: int = 0
    cache_def: dict = field(default_factory=dict)  # rolagens do defensor por golpe (lote)

    def _tam_lote(self) -> int:
        """Golpes consecutivos de mesma fase (principal/extra) a partir do atual (máx. 20 dados)."""
        extra = self.fila[self.idx]["extra"]
        n = 0
        for it in self.fila[self.idx:]:
            if it["extra"] != extra:
                break
            n += 1
        return min(n, 20)

    def _expr(self, roll: str) -> str:
        n = self._tam_lote()
        base = roll.lstrip("!").lstrip("0123456789")
        return (str(n) if n > 1 else "") + base

    def expr_atacante(self) -> str:
        return self._expr(self.roll_atacante)

    def expr_defensor(self) -> str:
        return self._expr(self.roll_defensor)


@dataclass
class CombateState:
    canal_id: int
    guild_id: int
    host_id: int
    host_nome: str = ""
    status: str = "LOBBY"  # LOBBY | EM_ANDAMENTO
    participantes: list[ParticipanteCombate] = field(default_factory=list)
    ordem_turnos: list[str] = field(default_factory=list)
    indice_turno: int = 0
    rodada: int = 1
    acao_pendente: Optional[AcaoPendente] = None
    mensagem_painel_id: Optional[int] = None
    ultimo_log: str = ""
    log_completo: list[str] = field(default_factory=list)
    eventos: list[str] = field(default_factory=list)  # eventos de início de rodada (DoT)
    timer: Optional[asyncio.Task] = None  # temporizador de inatividade
    votacao_ativa: bool = False

    # ---------- consultas ----------
    def obter(self, personagem_id: str) -> Optional[ParticipanteCombate]:
        for p in self.participantes:
            if p.personagem_id == personagem_id:
                return p
        return None

    def donos(self) -> list[str]:
        vistos: list[str] = []
        for p in self.participantes:
            if p.owner_id not in vistos:
                vistos.append(p.owner_id)
        return vistos

    @property
    def atual(self) -> Optional[ParticipanteCombate]:
        if not self.ordem_turnos:
            return None
        return self.obter(self.ordem_turnos[self.indice_turno % len(self.ordem_turnos)])

    def alvos_possiveis(self, atacante: ParticipanteCombate) -> list[ParticipanteCombate]:
        return [
            p for p in self.participantes
            if p.time != atacante.time and p.em_campo and p.vivo
        ]

    def vencedor(self) -> Optional[str]:
        """Retorna o time vencedor ('A'/'B'), 'EMPATE' ou None se a luta continua."""
        times_vivos = {p.time for p in self.participantes if p.vivo}
        if len(times_vivos) == 1:
            return next(iter(times_vivos))
        if not times_vivos:
            return "EMPATE"
        return None

    # ---------- ações ----------
    def log(self, texto: str) -> None:
        self.ultimo_log = texto
        self.log_completo.append(texto)
        self.log_completo = self.log_completo[-30:]

    def log_extra(self, texto: str) -> None:
        self.ultimo_log = (self.ultimo_log + "\n" + texto).strip()
        self.log_completo.append(texto)
        self.log_completo = self.log_completo[-30:]

    def iniciar(self) -> None:
        self.status = "EM_ANDAMENTO"
        ativos = sorted((p for p in self.participantes if p.em_campo), key=lambda p: p.vel, reverse=True)
        self.ordem_turnos = [p.personagem_id for p in ativos]
        self.indice_turno = 0
        self.rodada = 1

    def repor_reservas(self) -> list[ParticipanteCombate]:
        """Quando alguém em campo cai, a primeira reserva viva do mesmo dono entra."""
        entraram = []
        for p in list(self.participantes):
            if p.em_campo and not p.vivo:
                p.em_campo = False
                p.dots.clear()
                p.contras.clear()
                p.carregando = None
                p.extras_pend.clear()
                reserva = next(
                    (r for r in self.participantes if r.owner_id == p.owner_id and r.time == p.time and not r.em_campo and r.vivo),
                    None,
                )
                if reserva:
                    reserva.em_campo = True
                    self.ordem_turnos.append(reserva.personagem_id)
                    entraram.append(reserva)
        return entraram

    def _valor_dot(self, p: ParticipanteCombate, d: dict) -> int:
        base = d["base"]
        if base == "STAT_ATACANTE":
            ref = d["stat_atacante"]
        elif base == "STAT_ALVO":
            ref = p.stat(p.stat_principal)
        elif base == "HP_MAX_ALVO":
            ref = p.hp_max
        else:
            ref = p.hp_atual
        return calcular_valor_formula(d["formula"], ref) * d["stacks"]

    def _tick_dots(self) -> None:
        """Início de rodada: DoT ignora DEF e vai direto no HP."""
        for p in self.participantes:
            if not p.vivo or not p.em_campo:
                continue
            for d in list(p.dots):
                dano = min(p.hp_atual, self._valor_dot(p, d))
                p.hp_atual -= dano
                stacks = f" x{d['stacks']}" if d["stacks"] > 1 else ""
                self.eventos.append(f"☠️ **{p.nome}** sofreu **{dano}** de **{d['nome']}**{stacks}")
                if d["restante"] != DURACAO_PERMANENTE:
                    d["restante"] -= 1
                    if d["restante"] <= 0:
                        p.dots.remove(d)
                if not p.vivo:
                    break

    def passar_turno(self) -> Optional[ParticipanteCombate]:
        n = len(self.ordem_turnos)
        if n == 0:
            return None
        for _ in range(n + 1):
            self.indice_turno += 1
            if self.indice_turno >= n:
                self.indice_turno = 0
                self.rodada += 1
                self._tick_dots()
            p = self.atual
            if p and p.em_campo and p.vivo:
                if p.def_regen is not None:
                    p.def_regen -= 1
                    if p.def_regen <= 0:
                        p.def_regen = None
                        p.def_atual = p.def_base // 2
                        self.eventos.append(f"🛡️ A DEF de **{p.nome}** regenerou para **{p.def_atual}**")
                for k in list(p.cooldowns):
                    p.cooldowns[k] = max(0, p.cooldowns[k] - 1)
                for k in list(p.contras):
                    if k["restante"] != DURACAO_PERMANENTE:
                        k["restante"] -= 1
                        if k["restante"] <= 0:
                            p.contras.remove(k)
                return p
        return None


combates_ativos: dict[int, CombateState] = {}


def obter_combate(canal_id: int) -> Optional[CombateState]:
    return combates_ativos.get(canal_id)


def registrar_combate(c: CombateState) -> None:
    combates_ativos[c.canal_id] = c


def encerrar_combate(canal_id: int) -> None:
    c = combates_ativos.pop(canal_id, None)
    if c and c.timer:
        c.timer.cancel()
        c.timer = None
