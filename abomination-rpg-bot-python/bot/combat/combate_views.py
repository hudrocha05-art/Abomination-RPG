"""
Views (botões e menus) do lobby e da batalha.
"""
import discord

from bot.combat.combate_embeds import embed_batalha, embed_lobby
from bot.combat.combate_manager import (
    MAX_EM_CAMPO,
    CombateState,
    ParticipanteCombate,
    encerrar_combate,
)
from bot.db import personagens as db_pers


async def _buscar_msg(canal, msg_id):
    try:
        return await canal.fetch_message(msg_id)
    except discord.HTTPException:
        return None


async def atualizar_lobby(canal, c: CombateState) -> None:
    if not c.mensagem_painel_id:
        return
    msg = await _buscar_msg(canal, c.mensagem_painel_id)
    if msg:
        await msg.edit(embed=embed_lobby(c), view=LobbyView(c))


async def enviar_novo_painel(canal, c: CombateState) -> None:
    """Apaga o painel anterior e manda um novo, mencionando o dono do personagem da vez."""
    if c.mensagem_painel_id:
        antiga = await _buscar_msg(canal, c.mensagem_painel_id)
        if antiga:
            try:
                await antiga.delete()
            except discord.HTTPException:
                pass
    vez = c.atual
    view = None if c.vencedor() else PainelView(c)
    aviso = f"⚡ <@{vez.owner_id}>, é a vez de **{vez.nome}**!" if vez and view else None
    msg = await canal.send(content=aviso, embed=embed_batalha(c), view=view)
    c.mensagem_painel_id = msg.id


async def atualizar_painel(canal, c: CombateState) -> None:
    if not c.mensagem_painel_id:
        return
    msg = await _buscar_msg(canal, c.mensagem_painel_id)
    if msg:
        view = None if c.vencedor() else PainelView(c)
        await msg.edit(embed=embed_batalha(c), view=view)


# ======================================================================
# LOBBY
# ======================================================================
class LobbyView(discord.ui.View):
    def __init__(self, combate: CombateState):
        super().__init__(timeout=None)
        self.combate = combate

    @discord.ui.button(label="Participar", emoji="⚔️", style=discord.ButtonStyle.success)
    async def participar(self, interaction: discord.Interaction, _: discord.ui.Button):
        c = self.combate
        if c.status != "LOBBY":
            await interaction.response.send_message("❌ A batalha já começou.", ephemeral=True)
            return
        uid = str(interaction.user.id)
        todos = db_pers.listar_personagens(uid)
        prontos = [p for p in todos if p["hp"] > 0][:20]
        if not prontos:
            await interaction.response.send_message(
                "❌ Você não tem personagens com a ficha preenchida. Use `/personagem criar` e `/ficha preencher`.",
                ephemeral=True,
            )
            return
        atuais = [p.personagem_id for p in c.participantes if p.owner_id == uid]
        view = EscolhaTimeView(c, uid, prontos)
        await interaction.response.send_message(view.texto(), view=view, ephemeral=True)

    @discord.ui.button(label="Gerenciar (Host)", emoji="⚙️", style=discord.ButtonStyle.secondary)
    async def gerenciar(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.combate.host_id:
            await interaction.response.send_message("❌ Só o host pode gerenciar o lobby.", ephemeral=True)
            return
        await interaction.response.send_message(
            "⚙️ **Gerenciar lobby**", view=GerenciarView(self.combate), ephemeral=True
        )


class EscolhaTimeView(discord.ui.View):
    def __init__(self, combate: CombateState, owner_id: str, personagens):
        super().__init__(timeout=300)
        self.combate = combate
        self.owner_id = owner_id
        self.personagens = personagens

    def texto(self) -> str:
        return ("### 🏳️ Escolha o seu Time\nVocê pode participar dos **dois times** "
                "(com personagens diferentes) — escolha qual time editar agora.")

    async def _abrir(self, interaction: discord.Interaction, time: str):
        c = self.combate
        if c.status != "LOBBY":
            await interaction.response.edit_message(content="❌ A batalha já começou.", view=None)
            return
        outro = "B" if time == "A" else "A"
        ocupados = {p.personagem_id for p in c.participantes if p.owner_id == self.owner_id and p.time == outro}
        disponiveis = [p for p in self.personagens if p["id"] not in ocupados]
        if not disponiveis:
            await interaction.response.edit_message(
                content=f"❌ Todos os seus personagens já estão no Time {outro}.", view=None)
            return
        atuais = [p.personagem_id for p in c.participantes if p.owner_id == self.owner_id and p.time == time]
        view = SelecaoView(c, self.owner_id, disponiveis, atuais, time)
        await interaction.response.edit_message(content=view.texto(), view=view)

    @discord.ui.button(label="Time A", emoji="🔵", style=discord.ButtonStyle.primary)
    async def time_a(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._abrir(interaction, "A")

    @discord.ui.button(label="Time B", emoji="🔴", style=discord.ButtonStyle.danger)
    async def time_b(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._abrir(interaction, "B")


class SelecaoView(discord.ui.View):
    def __init__(self, combate: CombateState, owner_id: str, personagens, selecionados: list[str], time: str = "A"):
        super().__init__(timeout=300)
        self.combate = combate
        self.owner_id = owner_id
        self.time = time
        self.personagens = {p["id"]: p for p in personagens}
        self.selecionados = list(selecionados)
        self._montar()

    def texto(self) -> str:
        cab = f"### ⚔️ Escolha seus Personagens — Time {self.time}\n"
        if not self.selecionados:
            return (
                cab + "Clique nos botões para selecionar.\n\n"
                f"⚠️ Só os **{MAX_EM_CAMPO} primeiros** entram em campo; os demais ficam na **reserva**."
            )
        linhas = []
        for i, pid in enumerate(self.selecionados):
            tag = "⚔️ Ativo" if i < MAX_EM_CAMPO else "🎒 Reserva"
            linhas.append(f"· **{self.personagens[pid]['nome']}** — {tag}")
        return cab + "\n".join(linhas) + "\n\nClique em **Confirmar Equipe** quando terminar."

    def _montar(self):
        self.clear_items()
        for p in self.personagens.values():
            sel = p["id"] in self.selecionados
            b = discord.ui.Button(
                label=f"{'🟢' if sel else '⚫'} {p['nome']}"[:80],
                style=discord.ButtonStyle.primary if sel else discord.ButtonStyle.secondary,
            )
            b.callback = self._toggle(p["id"])
            self.add_item(b)
        ok = discord.ui.Button(label="✅ Confirmar Equipe", style=discord.ButtonStyle.success, row=4)
        ok.callback = self._confirmar
        cancel = discord.ui.Button(label="❌ Cancelar", style=discord.ButtonStyle.secondary, row=4)
        cancel.callback = self._cancelar
        self.add_item(ok)
        self.add_item(cancel)

    def _toggle(self, pid: str):
        async def cb(interaction: discord.Interaction):
            if pid in self.selecionados:
                self.selecionados.remove(pid)
            else:
                self.selecionados.append(pid)
            self._montar()
            await interaction.response.edit_message(content=self.texto(), view=self)
        return cb

    async def _confirmar(self, interaction: discord.Interaction):
        c = self.combate
        if c.status != "LOBBY":
            await interaction.response.edit_message(content="❌ A batalha já começou.", view=None)
            return
        c.participantes = [
            p for p in c.participantes if not (p.owner_id == self.owner_id and p.time == self.time)
        ]
        for i, pid in enumerate(self.selecionados):
            r = self.personagens[pid]
            c.participantes.append(ParticipanteCombate(
                personagem_id=r["id"], owner_id=self.owner_id, nome=r["nome"],
                hp_max=r["hp"], hp_atual=r["hp"], atk=r["atk"],
                def_base=r["def"], def_atual=r["def"], mst=r["mst"], vel=r["vel"],
                stat_principal=r["stat_principal"], em_campo=i < MAX_EM_CAMPO, time=self.time,
            ))
        self.stop()
        txt = f"✅ Equipe do Time {self.time} confirmada!" if self.selecionados else f"✅ Você saiu do Time {self.time}."
        await interaction.response.edit_message(content=txt, view=None)
        await atualizar_lobby(interaction.channel, c)

    async def _cancelar(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(content="Seleção cancelada.", view=None)


class GerenciarView(discord.ui.View):
    def __init__(self, combate: CombateState):
        super().__init__(timeout=120)
        self.combate = combate

    @discord.ui.button(label="Iniciar Batalha", emoji="▶️", style=discord.ButtonStyle.success)
    async def iniciar(self, interaction: discord.Interaction, _: discord.ui.Button):
        c = self.combate
        if c.status != "LOBBY":
            await interaction.response.edit_message(content="❌ A batalha já começou.", view=None)
            return
        if not {p.time for p in c.participantes} >= {"A", "B"}:
            await interaction.response.send_message("❌ Cada time precisa de pelo menos 1 personagem.", ephemeral=True)
            return
        c.iniciar()
        await interaction.response.edit_message(content="▶️ Batalha iniciada!", view=None)
        from bot.combat import resolucao
        await resolucao.novo_painel(interaction.channel, c)

    @discord.ui.button(label="Cancelar Lobby", emoji="🛑", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, _: discord.ui.Button):
        c = self.combate
        encerrar_combate(c.canal_id)
        msg = await _buscar_msg(interaction.channel, c.mensagem_painel_id) if c.mensagem_painel_id else None
        if msg:
            await msg.edit(content="🛑 **Lobby cancelado pelo host.**", embed=None, view=None)
        await interaction.response.edit_message(content="Lobby cancelado.", view=None)


# ======================================================================
# BATALHA
# ======================================================================
class PainelView(discord.ui.View):
    def __init__(self, combate: CombateState):
        super().__init__(timeout=None)
        self.combate = combate

    @discord.ui.button(label="Abrir Painel de Ações", emoji="⚔️", style=discord.ButtonStyle.primary)
    async def abrir(self, interaction: discord.Interaction, _: discord.ui.Button):
        c = self.combate
        vez = c.atual
        if not vez or c.vencedor():
            await interaction.response.send_message("❌ Não há turno ativo.", ephemeral=True)
            return
        if str(interaction.user.id) != vez.owner_id:
            await interaction.response.send_message(
                f"❌ Agora é a vez de **{vez.nome}** (<@{vez.owner_id}>).", ephemeral=True
            )
            return
        if c.acao_pendente:
            await interaction.response.send_message("⚠️ Há uma ação aguardando rolagens no chat.", ephemeral=True)
            return
        from bot.combat.combate_acao import AcaoView
        view = AcaoView(c, vez)
        await interaction.response.send_message(view.texto(), view=view, ephemeral=True)

    @discord.ui.button(label="Pular Turno", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def pular(self, interaction: discord.Interaction, _: discord.ui.Button):
        c = self.combate
        vez = c.atual
        if not vez or c.vencedor():
            await interaction.response.send_message("❌ Não há turno ativo.", ephemeral=True)
            return
        if interaction.user.id != c.host_id and str(interaction.user.id) != vez.owner_id:
            await interaction.response.send_message(
                "❌ Só o dono do personagem da vez ou o host pode pular o turno.", ephemeral=True
            )
            return
        c.acao_pendente = None
        c.log(f"⏭️ O turno de **{vez.nome}** foi pulado por {interaction.user.display_name}.")
        await interaction.response.defer()
        from bot.combat import resolucao
        await resolucao.avancar_turno(interaction.channel, c)

    @discord.ui.button(label="Encerrar (Host)", emoji="🛑", style=discord.ButtonStyle.danger)
    async def encerrar(self, interaction: discord.Interaction, _: discord.ui.Button):
        c = self.combate
        if interaction.user.id != c.host_id:
            await interaction.response.send_message("❌ Só o host pode pedir o encerramento.", ephemeral=True)
            return
        if c.votacao_ativa:
            await interaction.response.send_message("⚠️ Já existe uma votação em andamento.", ephemeral=True)
            return
        c.votacao_ativa = True
        votantes = c.donos()
        view = VotacaoView(c, votantes, str(interaction.user.id))
        if view._contagem()[0] * 2 >= len(votantes):  # o voto do host já basta (ex.: 2 jogadores = empate)
            encerrar_combate(c.canal_id)
            await interaction.response.send_message("🛑 **Batalha encerrada** (o host pediu e o voto dele já é maioria/empate).")
            await _remover_painel(interaction.channel, c)
            return
        await interaction.response.send_message(view.texto(), view=view)


class VotacaoView(discord.ui.View):
    """Votação para encerrar: vota quem controla personagens; maioria ou empate encerra."""

    def __init__(self, combate: CombateState, votantes: list[str], host_uid: str):
        super().__init__(timeout=300)
        self.combate = combate
        self.votantes = votantes
        self.votos: dict[str, bool] = {host_uid: True}
        self.encerrada = False

    def _contagem(self) -> tuple[int, int]:
        sim = sum(1 for v in self.votos.values() if v)
        return sim, len(self.votos) - sim

    def texto(self) -> str:
        sim, nao = self._contagem()
        pend = len(self.votantes) - len(self.votos)
        return (f"🗳️ **O host pediu para encerrar a batalha.**\n"
                f"✅ Sim: **{sim}** · ❌ Não: **{nao}** · ⏳ Faltam: **{pend}**\n"
                "Maioria (ou empate) a favor encerra o combate.")

    async def _votar(self, interaction: discord.Interaction, voto: bool):
        uid = str(interaction.user.id)
        if uid not in self.votantes:
            await interaction.response.send_message("❌ Só quem controla personagens na batalha vota.", ephemeral=True)
            return
        if self.encerrada:
            await interaction.response.edit_message(view=None)
            return
        self.votos[uid] = voto
        sim, nao = self._contagem()
        total = len(self.votantes)
        if sim * 2 >= total:
            self.encerrada = True
            self.stop()
            encerrar_combate(self.combate.canal_id)
            await interaction.response.edit_message(
                content=f"🛑 **Batalha encerrada por votação** (✅ {sim} · ❌ {nao}).", view=None)
            await _remover_painel(interaction.channel, self.combate)
        elif nao * 2 > total:
            self.encerrada = True
            self.stop()
            self.combate.votacao_ativa = False
            await interaction.response.edit_message(
                content=f"❌ **Votação recusada** (✅ {sim} · ❌ {nao}). A batalha continua.", view=None)
        else:
            await interaction.response.edit_message(content=self.texto(), view=self)

    @discord.ui.button(label="Concordo", emoji="✅", style=discord.ButtonStyle.success)
    async def sim(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._votar(interaction, True)

    @discord.ui.button(label="Discordo", emoji="❌", style=discord.ButtonStyle.danger)
    async def nao(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._votar(interaction, False)

    async def on_timeout(self) -> None:
        if not self.encerrada:
            self.combate.votacao_ativa = False


async def _remover_painel(canal, c: CombateState) -> None:
    msg = await _buscar_msg(canal, c.mensagem_painel_id) if c.mensagem_painel_id else None
    if msg:
        try:
            await msg.edit(view=None)
        except discord.HTTPException:
            pass


class DefesaView(discord.ui.View):
    """Botões públicos: só o dono do personagem atacado pode escolher como se defender."""

    def __init__(self, combate: CombateState, pend):
        super().__init__(timeout=None)
        self.combate = combate
        self.pend = pend

    def _alvo(self):
        return self.combate.obter(self.pend.alvo_id)

    async def _valido(self, interaction: discord.Interaction) -> bool:
        c, pend = self.combate, self.pend
        if c.acao_pendente is not pend or pend.aguardando != "DEFENSOR" or pend.defesa is not None:
            await interaction.response.edit_message(view=None)
            return False
        if str(interaction.user.id) != self._alvo().owner_id:
            await interaction.response.send_message(
                f"❌ Só <@{self._alvo().owner_id}> pode escolher a defesa de **{self._alvo().nome}**.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Desviar", emoji="🎲", style=discord.ButtonStyle.primary)
    async def desviar(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._valido(interaction):
            return
        self.pend.defesa = "DESVIAR"
        alvo = self._alvo()
        await interaction.response.edit_message(
            content=f"🎲 **{alvo.nome}** tenta desviar! <@{alvo.owner_id}>, role `!{self.pend.expr_defensor()}`.", view=None
        )
        await atualizar_painel(interaction.channel, self.combate)

    @discord.ui.button(label="Bloquear (-50% de dano)", emoji="🧱", style=discord.ButtonStyle.secondary)
    async def bloquear_si(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._valido(interaction):
            return
        self.pend.defesa = "BLOQUEAR_SI"
        await interaction.response.edit_message(content=f"🧱 **{self._alvo().nome}** se prepara para bloquear!", view=None)
        from bot.combat import resolucao
        await resolucao.resolver_bloqueio(interaction.channel, self.combate)
