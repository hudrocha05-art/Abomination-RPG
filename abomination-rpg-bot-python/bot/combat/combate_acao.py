"""
Menu privado (efêmero) de ações do jogador da vez.
"""
import discord

from bot.combat import calculo_dano as cd
from bot.combat import resolucao
from bot.combat.combate_manager import CombateState, ParticipanteCombate
from bot.db import skills as db_skills


class AcaoView(discord.ui.View):
    def __init__(self, combate: CombateState, atacante: ParticipanteCombate):
        super().__init__(timeout=300)
        self.combate = combate
        self.atacante = atacante
        self.skills = {
            s["id"]: s for s in db_skills.listar_skills(atacante.personagem_id) if "DANO" in s["tipos"]
        }
        car = atacante.carregando
        if car and car["skill_id"] not in self.skills:
            atacante.carregando = None
        self.escolhida = "BASICO"
        if atacante.carregando:
            self.escolhida = "LIBERAR" if self._pode_liberar() else "CARREGAR"
        self._montar()

    # ---------- carga ----------
    def _cfg_carga(self) -> dict | None:
        car = self.atacante.carregando
        if not car:
            return None
        return cd.plano_skill(self.skills[car["skill_id"]])["carregado"]

    def _pode_liberar(self) -> bool:
        cfg = self._cfg_carga()
        return bool(cfg) and self.atacante.carregando["turnos"] >= int(cfg.get("min_turnos", 1))

    def _pode_continuar(self) -> bool:
        cfg = self._cfg_carga()
        if not cfg:
            return False
        return cd.carga_infinita(cfg) or self.atacante.carregando["turnos"] < int(cfg["max_turnos"])

    # ---------- interface ----------
    def texto(self) -> str:
        car = self.atacante.carregando
        if car:
            cfg = self._cfg_carga()
            bonus = int(cfg["bonus_por_turno"]) * car["turnos"]
            return (f"### 🔋 {self.atacante.nome} está carregando **{car['nome']}**\n"
                    f"Turnos carregados: **{car['turnos']}** (+{bonus}% de dano se liberar agora).")
        return f"### ⚡ Turno de {self.atacante.nome}\nEscolha a ação e depois o alvo."

    def _skill_escolhida(self) -> dict | None:
        e = self.escolhida
        if e == "LIBERAR":
            return self.skills[self.atacante.carregando["skill_id"]]
        if e in ("BASICO", "CARREGAR"):
            return None
        return self.skills[e]

    def _eh_aoe(self) -> bool:
        """Ataque em área / todos: dispensa escolher alvo, só confirma."""
        e = self.escolhida
        if e == "LIBERAR":
            return resolucao.alcance_sem_alvo(self._skill_escolhida())
        if e in ("BASICO", "CARREGAR"):
            return False
        plano = cd.plano_skill(self.skills[e])
        return not plano["carregado"] and plano["rola"] and resolucao.alcance_sem_alvo(self.skills[e])

    def _precisa_alvo(self) -> bool:
        e = self.escolhida
        if e == "BASICO":
            return True
        if e == "CARREGAR":
            return False
        if e == "LIBERAR":
            return not self._eh_aoe()
        plano = cd.plano_skill(self.skills[e])
        return not plano["carregado"] and plano["rola"] and not self._eh_aoe()

    def _montar(self):
        self.clear_items()
        a = self.atacante
        if a.carregando:
            nome = a.carregando["nome"]
            opcoes = []
            if self._pode_liberar():
                opcoes.append(discord.SelectOption(label=f"Liberar {nome}"[:100], value="LIBERAR", emoji="💥",
                                                   default=self.escolhida == "LIBERAR"))
            if self._pode_continuar():
                opcoes.append(discord.SelectOption(label="Continuar carregando", value="CARREGAR", emoji="🔋",
                                                   default=self.escolhida == "CARREGAR"))
        else:
            opcoes = [discord.SelectOption(
                label="Ataque Básico", value="BASICO", emoji="⚔️",
                description="Dano do seu STAT principal (HP: 5% do HP)", default=self.escolhida == "BASICO",
            )]
            for sid, s in list(self.skills.items())[:24]:
                cdn = a.cooldowns.get(sid, 0)
                opcoes.append(discord.SelectOption(
                    label=s["nome"][:100], value=sid, emoji="✨",
                    description=f"⌛ Recarga: {cdn} turno(s)" if cdn else "✅ Disponível",
                    default=self.escolhida == sid,
                ))
        sel = discord.ui.Select(placeholder="1. Escolha a ação", options=opcoes, row=0)
        sel.callback = self._acao
        self.add_item(sel)

        if self._precisa_alvo():
            alvos = self.combate.alvos_possiveis(a)[:25]
            if len(alvos) == 1:
                unico = alvos[0]
                b = discord.ui.Button(label=f"Confirmar ação em {unico.nome}"[:80], emoji="✅",
                                      style=discord.ButtonStyle.success, row=1)

                async def _auto(interaction: discord.Interaction, alvo=unico):
                    await self._disparar(interaction, alvo)

                b.callback = _auto
                self.add_item(b)
            elif alvos:
                sel2 = discord.ui.Select(
                    placeholder="2. Escolha o alvo",
                    options=[discord.SelectOption(
                        label=x.nome[:100], value=x.personagem_id,
                        description=f"HP {x.hp_atual}/{x.hp_max} · DEF {x.def_atual}",
                    ) for x in alvos],
                    row=1,
                )
                sel2.callback = self._alvo
                self.add_item(sel2)
        else:
            b = discord.ui.Button(label="Confirmar ação", emoji="✅", style=discord.ButtonStyle.success, row=1)
            b.callback = self._sem_alvo
            self.add_item(b)

    async def _acao(self, interaction: discord.Interaction):
        self.escolhida = interaction.data["values"][0]
        self._montar()
        await interaction.response.edit_message(view=self)

    def _valido(self) -> bool:
        c = self.combate
        return not c.acao_pendente and c.atual is self.atacante

    async def _pagar_skill(self, interaction, skill: dict) -> bool:
        """Valida recarga e custo de HP; só cobra se tudo estiver ok."""
        a = self.atacante
        if a.cooldowns.get(skill["id"], 0) > 0:
            await interaction.response.send_message("❌ Essa habilidade está em recarga.", ephemeral=True)
            return False
        custo = skill["dados"].get("custo_vida") or 0
        if custo and a.hp_atual <= custo:
            await interaction.response.send_message("❌ HP insuficiente para o custo da habilidade.", ephemeral=True)
            return False
        a.hp_atual -= custo
        return True

    # ---------- ações sem alvo ----------
    async def _sem_alvo(self, interaction: discord.Interaction):
        c, a = self.combate, self.atacante
        if not self._valido():
            await interaction.response.edit_message(content="⚠️ Este menu expirou.", view=None)
            return
        if self._eh_aoe():
            await self._disparar(interaction, None)
            return

        if self.escolhida == "CARREGAR":
            a.carregando["turnos"] += 1
            texto = f"🔋 **{a.nome}** continua carregando **{a.carregando['nome']}** ({a.carregando['turnos']} turno(s))."
        else:
            skill = self.skills[self.escolhida]
            plano = cd.plano_skill(skill)
            if not await self._pagar_skill(interaction, skill):
                return
            if plano["carregado"]:
                a.carregando = {"skill_id": skill["id"], "nome": skill["nome"], "turnos": 1}
                texto = f"🔋 **{a.nome}** começou a carregar **{skill['nome']}**!"
            else:
                if skill["cooldown"] > 0:
                    a.cooldowns[skill["id"]] = skill["cooldown"] + 1
                resolucao.ativar_contra(a, skill, plano["contra"])
                texto = f"🔄 **{a.nome}** assumiu a postura **{skill['nome']}**!"
        self.stop()
        await interaction.response.edit_message(content=f"✅ {texto}", view=None)
        await resolucao.fim_sem_rolagem(interaction.channel, c, a, texto)

    # ---------- ações com alvo ----------
    async def _alvo(self, interaction: discord.Interaction):
        alvo = self.combate.obter(interaction.data["values"][0])
        await self._disparar(interaction, alvo)

    async def _disparar(self, interaction: discord.Interaction, principal: ParticipanteCombate | None):
        c, a = self.combate, self.atacante
        if not self._valido():
            await interaction.response.edit_message(content="⚠️ Este menu expirou.", view=None)
            return
        if principal is None:  # em área / todos: o "principal" é só o primeiro inimigo
            inimigos = c.alvos_possiveis(a)
            principal = inimigos[0] if inimigos else None
        if not principal or not principal.vivo:
            await interaction.response.send_message("❌ Alvo inválido.", ephemeral=True)
            return

        skill, mult = None, 1.0
        if self.escolhida == "LIBERAR":
            car = a.carregando
            skill = self.skills[car["skill_id"]]
            mult = 1 + int(self._cfg_carga()["bonus_por_turno"]) * car["turnos"] / 100
            a.carregando = None
            if skill["cooldown"] > 0:
                a.cooldowns[skill["id"]] = skill["cooldown"] + 1
        elif self.escolhida != "BASICO":
            skill = self.skills[self.escolhida]
            if not await self._pagar_skill(interaction, skill):
                return
            if skill["cooldown"] > 0:
                a.cooldowns[skill["id"]] = skill["cooldown"] + 1

        alvos = resolucao.alvos_da_skill(c, a, skill, principal)
        pend = resolucao.montar_pendencia(a, alvos[0], skill, mult, [t.personagem_id for t in alvos[1:]])
        self.stop()
        nome = skill["nome"] if skill else "Ataque Básico"
        quem = alvos[0].nome if len(alvos) == 1 else f"{len(alvos)} alvos"
        await interaction.response.edit_message(
            content=f"✅ **{nome}** contra **{quem}**! Role `!{pend.expr_atacante()}` no chat.", view=None
        )
        await resolucao.iniciar_pendencia(interaction.channel, c, pend)
