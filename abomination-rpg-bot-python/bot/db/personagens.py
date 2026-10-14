"""
Funções de acesso a dados (CRUD) para a tabela `personagens`.

Cada função abre e fecha sua própria conexão — simples e suficiente para
o volume de uso de um grupo pequeno de amigos.
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from bot.db.database import get_connection


class NomeDuplicadoError(Exception):
    """Levantado quando o usuário já tem um personagem com esse nome."""
    pass


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def criar_personagem(
    owner_id: str,
    nome: str,
    raca: str,
    elemento: str,
    classe: str,
    stat_principal: str = "ATK",
    hp: int = 0,
    atk: int = 0,
    defesa: int = 0,
    mst: int = 0,
    vel: int = 0,
) -> sqlite3.Row:
    """Cria um novo personagem com seus dados narrativos obrigatórios.
    Stats começam em 0 até a ficha ser preenchida via /ficha preencher."""
    conn = get_connection()
    try:
        novo_id = str(uuid.uuid4())
        agora = _agora()
        try:
            conn.execute(
                """
                INSERT INTO personagens (
                    id, owner_id, nome, hp, hp_atual, atk, def, mst, vel,
                    raca, elemento, classe, stat_principal, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    novo_id, owner_id, nome, hp, hp, atk, defesa, mst, vel,
                    raca, elemento, classe, stat_principal, agora, agora,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise NomeDuplicadoError(f"Você já tem um personagem chamado '{nome}'.")

        return conn.execute("SELECT * FROM personagens WHERE id = ?", (novo_id,)).fetchone()
    finally:
        conn.close()


def listar_personagens(owner_id: str) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM personagens WHERE owner_id = ? ORDER BY created_at ASC",
            (owner_id,),
        ).fetchall()
    finally:
        conn.close()


def buscar_personagem(owner_id: str, nome: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM personagens WHERE owner_id = ? AND nome = ?",
            (owner_id, nome),
        ).fetchone()
    finally:
        conn.close()


def buscar_personagem_por_id(personagem_id: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM personagens WHERE id = ?", (personagem_id,)
        ).fetchone()
    finally:
        conn.close()


def buscar_personagem_por_nome_qualquer_dono(nome: str) -> Optional[sqlite3.Row]:
    """Busca por nome sem filtrar pelo dono — usado na edição (dono ou admin)."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM personagens WHERE nome = ? COLLATE NOCASE",
            (nome,),
        ).fetchone()
    finally:
        conn.close()


def atualizar_atributos(personagem_id: str, hp: int, atk: int, defesa: int, mst: int, vel: int) -> None:
    """Atualiza os atributos principais. O HP atual é restaurado para o novo máximo
    (uma edição de ficha é tratada como um ajuste completo, não como dano)."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE personagens SET hp = ?, hp_atual = ?, atk = ?, def = ?, mst = ?, vel = ?, updated_at = ? WHERE id = ?",
            (hp, hp, atk, defesa, mst, vel, _agora(), personagem_id),
        )
        conn.commit()
    finally:
        conn.close()


def atualizar_detalhes(
    personagem_id: str,
    raca: Optional[str] = None,
    elemento: Optional[str] = None,
    classe: Optional[str] = None,
    stat_principal: Optional[str] = None,
) -> None:
    """Atualiza os campos opcionais (Raça, Elemento, Classe, STAT principal). Só altera os campos informados."""
    campos = []
    valores = []
    if stat_principal is not None:
        campos.append("stat_principal = ?")
        valores.append(stat_principal)
    if raca is not None:
        campos.append("raca = ?")
        valores.append(raca)
    if elemento is not None:
        campos.append("elemento = ?")
        valores.append(elemento)
    if classe is not None:
        campos.append("classe = ?")
        valores.append(classe)

    if not campos:
        return

    campos.append("updated_at = ?")
    valores.append(_agora())
    valores.append(personagem_id)

    conn = get_connection()
    try:
        conn.execute(f"UPDATE personagens SET {', '.join(campos)} WHERE id = ?", valores)
        conn.commit()
    finally:
        conn.close()


def excluir_personagem(personagem_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM personagens WHERE id = ?", (personagem_id,))
        conn.commit()
    finally:
        conn.close()


def autocomplete_personagens(owner_id: str, texto_atual: str) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT * FROM personagens
            WHERE owner_id = ? AND nome LIKE ? COLLATE NOCASE
            ORDER BY nome ASC LIMIT 25
            """,
            (owner_id, f"%{texto_atual}%"),
        ).fetchall()
    finally:
        conn.close()
