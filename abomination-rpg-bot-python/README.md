# Abomination RPG Bot (Python)

Este é o bot Abomination RPG reconstruído do zero em **Python**, usando a
biblioteca `discord.py`. Ele substitui a versão antiga (TypeScript) e vai
sendo construído aos poucos, uma parte por vez.

## O que já funciona

- `/personagem criar [stat_principal]` — abre um formulário popup obrigatório
  para registrar os dados narrativos do personagem: **Nome**, **Raça**,
  **Elemento** e **Classe**. O `stat_principal` (base das fórmulas das
  skills) pode ser ATK, DEF, MST, VEL ou HP (padrão: ATK). Com HP, o ataque
  básico causa 5% do HP.
- `/personagem editar <nome>` — edita os dados narrativos ou o STAT principal
  de um personagem seu.
- `/ficha preencher <personagem>` — abre o formulário popup com os 5 atributos
  numéricos de combate: **HP**, **ATK**, **DEF**, **MST** e **VEL** (todos
  obrigatórios; HP maior que zero, os demais aceitam 0).
- `/ficha ver <personagem>` ou `.ficha ver <personagem>` — exibe a ficha
  completa com atributos e detalhes do personagem.
- `.personagem listar` — lista todos os seus personagens (comando com
  prefixo ".").
- `.personagem ver <nome>` — mostra a ficha completa de um personagem seu.
- `.personagem excluir <nome>` — apaga um personagem, com confirmação por
  botões (dono ou administrador do servidor).
- `/skill criar personagem:<nome> [tipo] [nivel]` — abre o formulário
  (Nome, Recarga, Descrição, Custo de HP, Dado de Acerto) e depois o painel
  interativo, onde é possível marcar múltiplos tipos (Dano, Cura, Buff,
  Debuff etc.), definir o Alcance (Único, Adjacentes, Área, Todos) e alterar
  o Roll de Acerto. Para o tipo Dano, o botão "Configurar Dano" permite
  combinar os subtipos: Bruto, Múltiplos Golpes, Ataque Extra, DoT,
  Contra-ataque e Ataque Carregado. As fórmulas usam o STAT principal do
  personagem (`+50` = STAT + 50%; `75` = 75% do STAT).
- `/skill editar personagem:<nome> habilidade:<nome>` — mesmo painel, já
  preenchido com os dados atuais.
- `.skill listar <personagem>` — lista as habilidades de um personagem.
- `.skill ver <personagem> <habilidade>` — mostra os detalhes de uma
  habilidade específica.
- `.skill excluir <personagem> <habilidade>` — apaga uma habilidade, com
  confirmação por botões.
- `/host` — abre um **lobby de combate** no canal (igual ao bot antigo).
  Cada jogador clica em **Participar** e escolhe seus personagens (só os que
  têm ficha preenchida): os 4 primeiros entram em campo, o resto fica na
  **reserva**. O host usa **Gerenciar (Host)** para iniciar (mínimo 2
  jogadores) ou cancelar. A batalha é **todos contra todos**, com a ordem
  definida por **VEL**.
- Na batalha, o jogador da vez clica em **Abrir Painel de Ações** (menu
  privado, só ele vê), escolhe Ataque Básico ou uma skill de dano e o alvo.
  Depois o atacante e o dono do alvo rolam no chat o dado pedido pelo bot
  (`!d20`, `!d20+3`, `!W20`...). Atacante acerta se rolar >= defensor. O dano
  vai primeiro na **DEF** e o excedente no **HP**. Quando um personagem cai,
  a reserva do mesmo jogador entra em campo. O host também pode pular turno
  ou encerrar a batalha.
  O combate é **Time A x Time B**. Ao clicar em Participar, cada jogador
  escolhe o time e seus personagens; um mesmo dono pode ter personagens
  diferentes nos dois times. Cada time precisa de pelo menos 1 personagem.
  **Defesa:** quem é atacado escolhe por botão entre **Desviar** (rola o dado
  e o bot só responde "Errou" se desviar) ou **Bloquear** (sem rolagem, recebe
  50% do dano). Não é possível bloquear por um aliado; golpes bloqueados ainda
  aplicam Dano Contínuo.
  **Alcance:** Alvo único, Principal + adjacentes, Em área (todos os
  inimigos) e Todos (inclui aliados). O atacante rola uma vez por golpe e
  cada alvo faz sua própria defesa.
  **Tempo:** 5 minutos sem ação = o jogador perde a vez; se o alvo não
  responder, o bot rola a defesa por ele.
  **DEF:** o painel mostra um único valor. Quando a DEF chega a 0, ela
  regenera 50% da DEF total após 5 turnos do próprio personagem. As condições
  mostram os turnos restantes entre parênteses (sem número = sem fim).
  **Bloqueio:** o alvo pode bloquear a si mesmo, recebendo metade do dano;
  golpes bloqueados também aplicam DoT. Não é possível bloquear por um aliado.
  **Rolagem em lote:** skills com vários golpes (múltiplos golpes ou ataques
  extras) exigem todos os dados de uma vez, ex.: 5 golpes = `!5d20` (ou
  `!5d20+3`; o modificador vale para cada dado), tanto do atacante quanto do
  alvo que escolher Desviar. Cada dado vale um golpe, em ordem.
  **Painel:** reenviado (apagando o anterior) a cada turno, com a rodada e o
  último evento no topo. Os personagens aparecem separados por time, reservas
  listadas à parte, e personagens em campo ordenados por VEL decrescente.
  Condições e stats aparecem junto ao personagem; os stats têm emojis e ficam
  numa linha. **Pular turno:** o dono
  do personagem da vez ou o host. **Encerrar:** o host abre uma votação entre
  os jogadores; maioria ou empate a favor encerra. Em skills de **Principal +
  adjacentes**, os adjacentes recebem metade do dano.
  O combate resolve **todos os subtipos de dano**: Bruto, Múltiplos Golpes,
  Ataque Extra (condições e momentos), Dano Contínuo (empilhável, ignora DEF,
  aplicado no início da rodada), Contra-ataque (automático, acerto garantido)
  e Ataque Carregado (continuar/liberar, bônus por turno).
  *Ainda não funcionam em combate: buffs, debuffs, cura, escudo, itens,
  passivas e troca. A condição "se efeito" do Ataque Extra só
  enxerga Danos Contínuos.*

Comandos que precisam de um formulário popup (criar/editar) usam "/" porque
esse recurso só existe em comandos de barra do Discord. Os demais usam o
prefixo "." por serem mais rápidos.

O banco de dados é um único arquivo `abomination.db` (SQLite), criado
automaticamente na primeira vez que o bot roda. Não precisa instalar
nenhum servidor de banco de dados.

## Passo a passo para rodar

### 1. Instalar as dependências

Abra um terminal dentro desta pasta e rode:

```powershell
python -m pip install -r requirements.txt
```

### 2. Configurar o token do bot

1. Copie o arquivo `.env.example` e renomeie a cópia para `.env`.
2. Abra o `.env` e preencha:
   - `DISCORD_TOKEN`: o token do seu bot (Discord Developer Portal → sua
     aplicação → Bot → Reset Token).
   - `CLIENT_ID`: o "Application ID" da sua aplicação (aba General
     Information).
   - `GUILD_ID`: o ID do servidor do Discord onde você vai testar (clique
     direito no nome do servidor com o "Modo Desenvolvedor" ativado →
     Copiar ID do Servidor). Isso faz os comandos aparecerem
     instantaneamente nesse servidor, em vez de esperar até 1 hora.

### 3. Rodar o bot

```powershell
python -m bot.main
```

Se tudo estiver certo, vai aparecer no terminal:

```
✅ Bot online como SeuBot#0000
✅ N comando(s) sincronizado(s) no servidor de testes.
```

Agora é só ir no Discord e testar `/personagem criar`.

## Estrutura do projeto

```
bot/
  config.py          # carrega o .env (token, IDs, caminho do banco)
  main.py             # ponto de entrada do bot
  db/
    database.py       # schema do banco de dados (tabelas)
    personagens.py     # funções de acesso à tabela de personagens
  cogs/
    personagem.py      # comandos /personagem
  ui/
    personagem_modals.py  # formulários popup de criar/editar
    personagem_embeds.py  # mensagens visuais (fichas, listas)
```

Conforme formos avançando, novos arquivos vão entrar em `db/`, `cogs/` e
`ui/` para skills, passivas, itens, loja e o sistema de combate.
