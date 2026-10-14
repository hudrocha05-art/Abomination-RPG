"""
Conexão com o banco de dados SQLite e criação das tabelas.

Cada tabela aqui corresponde a uma "entidade" do RPG (personagem, skill,
passiva, item). Usamos JSON em texto (campo TEXT) para guardar listas ou
estruturas flexíveis, como os tipos combinados de uma skill.
"""
import sqlite3
from bot.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS personagens (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    nome TEXT NOT NULL,
    hp INTEGER NOT NULL,
    hp_atual INTEGER NOT NULL,
    atk INTEGER NOT NULL,
    def INTEGER NOT NULL,
    mst INTEGER NOT NULL DEFAULT 0,
    vel INTEGER NOT NULL,
    raca TEXT,
    elemento TEXT,
    classe TEXT,
    stat_principal TEXT NOT NULL DEFAULT 'ATK',
    starbits INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (owner_id, nome)
);

CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    personagem_id TEXT NOT NULL REFERENCES personagens(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    tipos TEXT NOT NULL,          -- lista JSON, ex: '["DANO", "DEBUFF"]'
    cooldown INTEGER NOT NULL DEFAULT 0,
    descricao TEXT,
    nivel INTEGER,
    dados TEXT NOT NULL,          -- JSON com detalhes mecânicos (custo de vida, efeitos, fórmula de dano etc.)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS passivas (
    id TEXT PRIMARY KEY,
    personagem_id TEXT NOT NULL REFERENCES personagens(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    condicao TEXT NOT NULL,
    parametro INTEGER,
    efeito TEXT NOT NULL,         -- JSON
    permanente INTEGER NOT NULL DEFAULT 0,
    nivel INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS itens_catalogo (
    id TEXT PRIMARY KEY,
    guild_id TEXT NOT NULL,
    nome TEXT NOT NULL,
    estrutura TEXT NOT NULL,      -- JSON
    cooldown_turnos INTEGER NOT NULL DEFAULT 0,
    raridade TEXT NOT NULL DEFAULT 'COMUM',
    uso_extra INTEGER NOT NULL DEFAULT 0,
    personagem_id TEXT REFERENCES personagens(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (guild_id, nome)
);

CREATE TABLE IF NOT EXISTS inventario_itens (
    id TEXT PRIMARY KEY,
    personagem_id TEXT NOT NULL REFERENCES personagens(id) ON DELETE CASCADE,
    item_catalogo_id TEXT NOT NULL REFERENCES itens_catalogo(id) ON DELETE CASCADE,
    quantidade_estoque INTEGER NOT NULL DEFAULT 1,
    equipado INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (personagem_id, item_catalogo_id)
);

CREATE TABLE IF NOT EXISTS precos_raridade (
    id TEXT PRIMARY KEY,
    guild_id TEXT NOT NULL,
    raridade TEXT NOT NULL,
    valor_starbits INTEGER NOT NULL DEFAULT 0,
    UNIQUE (guild_id, raridade)
);
"""


def get_connection() -> sqlite3.Connection:
    """Abre uma conexão com o banco de dados (cria o arquivo se não existir)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permite acessar colunas pelo nome (ex: row["nome"])
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Cria as tabelas do banco de dados, caso ainda não existam."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        # Migração simples: bancos antigos não têm a coluna stat_principal.
        colunas = [r["name"] for r in conn.execute("PRAGMA table_info(personagens)")]
        if "stat_principal" not in colunas:
            conn.execute("ALTER TABLE personagens ADD COLUMN stat_principal TEXT NOT NULL DEFAULT 'ATK'")
        conn.commit()
    finally:
        conn.close()
