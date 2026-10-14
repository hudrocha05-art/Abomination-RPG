"""
Funções de acesso a dados (CRUD) para a tabela `skills`.

O campo `tipos` é guardado como uma lista JSON (ex: '["DANO", "DEBUFF"]"),
permitindo que uma skill combine mais de um tipo — diferente da versão
antiga em TypeScript, que só aceitava um tipo por skill.

O campo `dados` guarda detalhes extras em JSON (por enquanto só o custo
de HP; fórmulas de dano/efeitos específicos entram quando o combate for
implementado).
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from bot.db.database import get_connection

# Tipos de skill válidos (equivalente ao enum TipoSkill do projeto antigo)
TIPOS_VALIDOS = [
    "DANO", "CURA", "ESCUDO", "BUFF", "DEBUFF", "CAMPO", "INVOCACAO", "BLOQUEIO",
]


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_para_dict(row: sqlite3.Row) -> dict:
    """Converte uma linha do banco em dict, decodificando os campos JSON."""
    d = dict(row)
    d["tipos"] = json.loads(d["tipos"])
    d["dados"] = json.loads(d["dados"])
    return d


def criar_skill(
    personagem_id: str,
    nome: str,
    tipos: list[str],
    cooldown: int = 0,
    descricao: Optional[str] = None,
    nivel: Optional[int] = None,
    custo_vida: Optional[int] = None,
    efeitos: Optional[list[dict]] = None,
    dano: Optional[dict] = None,
    alcance: Optional[str] = None,
    roll: Optional[str] = None,
) -> dict:
    conn = get_connection()
    try:
        novo_id = str(uuid.uuid4())
        agora = _agora()
        dados = {
            "custo_vida": custo_vida,
            "alcance": alcance or "UNICO",
            "roll": roll or "d20",
            "efeitos": efeitos or [],
        }
        if dano:
            dados["dano"] = dano
        conn.execute(
            """
            INSERT INTO skills (
                id, personagem_id, nome, tipos, cooldown, descricao, nivel, dados, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                novo_id, personagem_id, nome, json.dumps(tipos), cooldown,
                descricao, nivel, json.dumps(dados), agora, agora,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM skills WHERE id = ?", (novo_id,)).fetchone()
        return _row_para_dict(row)
    finally:
        conn.close()


def listar_skills(personagem_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM skills WHERE personagem_id = ? ORDER BY created_at ASC",
            (personagem_id,),
        ).fetchall()
        return [_row_para_dict(r) for r in rows]
    finally:
        conn.close()


def buscar_skill_por_id(skill_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
        return _row_para_dict(row) if row else None
    finally:
        conn.close()


def buscar_skill_por_nome(personagem_id: str, nome: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM skills WHERE personagem_id = ? AND nome = ? COLLATE NOCASE",
            (personagem_id, nome),
        ).fetchone()
        return _row_para_dict(row) if row else None
    finally:
        conn.close()


def atualizar_skill(
    skill_id: str,
    nome: Optional[str] = None,
    tipos: Optional[list[str]] = None,
    cooldown: Optional[int] = None,
    descricao: Optional[str] = None,
    custo_vida: Optional[int] = None,
    efeitos: Optional[list[dict]] = None,
    nivel: Optional[int] = None,
    dano: Optional[dict] = None,
    alcance: Optional[str] = None,
    roll: Optional[str] = None,
) -> None:
    conn = get_connection()
    try:
        atual = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
        if not atual:
            return
        atual_dict = _row_para_dict(atual)

        novo_nome = nome if nome is not None else atual_dict["nome"]
        novos_tipos = tipos if tipos is not None else atual_dict["tipos"]
        novo_cooldown = cooldown if cooldown is not None else atual_dict["cooldown"]
        nova_descricao = descricao if descricao is not None else atual_dict["descricao"]
        dados = dict(atual_dict["dados"])
        if custo_vida is not None:
            dados["custo_vida"] = custo_vida
        if efeitos is not None:
            dados["efeitos"] = efeitos
        if dano is not None:
            dados["dano"] = dano
        if alcance is not None:
            dados["alcance"] = alcance
        if roll is not None:
            dados["roll"] = roll
        if "DANO" not in novos_tipos:
            dados.pop("dano", None)
        novo_nivel = nivel if nivel is not None else atual_dict["nivel"]

        conn.execute(
            """
            UPDATE skills SET nome = ?, tipos = ?, cooldown = ?, descricao = ?, nivel = ?, dados = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                novo_nome, json.dumps(novos_tipos), novo_cooldown, nova_descricao, novo_nivel,
                json.dumps(dados), _agora(), skill_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def excluir_skill(skill_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
        conn.commit()
    finally:
        conn.close()


def autocomplete_skills(personagem_id: str, texto_atual: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM skills
            WHERE personagem_id = ? AND nome LIKE ? COLLATE NOCASE
            ORDER BY nome ASC LIMIT 25
            """,
            (personagem_id, f"%{texto_atual}%"),
        ).fetchall()
        return [_row_para_dict(r) for r in rows]
    finally:
        conn.close()
