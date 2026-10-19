"""Acesso ao banco: todo o SQL fica aqui (peca_roupa, tamanho, medida)."""
from typing import Optional

import psycopg

from schemas import PecaIn

_SELECT_PECAS = """
    SELECT p.id_peca, p.modelo, p.categoria, p.genero, p.corte,
           t.id_tamanho, t.tamanho,
           m.id_medida, m.ombro, m.cintura, m.altura, m.busto
    FROM peca_roupa p
    LEFT JOIN tamanho t ON t.id_peca = p.id_peca
    LEFT JOIN medida  m ON m.id_tamanho = t.id_tamanho
    WHERE p.id_peca = ANY(%s)
    ORDER BY p.id_peca DESC, t.id_tamanho
"""


def _montar(rows: list[dict]) -> list[dict]:
    """Agrupa as linhas do JOIN em peças com a lista de tamanhos."""
    pecas: dict[int, dict] = {}
    for r in rows:
        peca = pecas.setdefault(
            r["id_peca"],
            {k: r[k] for k in ("id_peca", "modelo", "categoria", "genero", "corte")} | {"tamanhos": []},
        )
        if r["id_tamanho"] is not None:
            peca["tamanhos"].append(
                {k: r[k] for k in ("id_tamanho", "tamanho", "id_medida", "ombro", "cintura", "altura", "busto")}
            )
    return list(pecas.values())


def _inserir_tamanhos(cur, id_peca: int, dados: PecaIn) -> None:
    for t in dados.tamanhos:
        cur.execute(
            "INSERT INTO tamanho (id_peca, tamanho) VALUES (%s, %s) RETURNING id_tamanho",
            (id_peca, t.tamanho),
        )
        id_tamanho = cur.fetchone()["id_tamanho"]
        cur.execute(
            "INSERT INTO medida (id_tamanho, ombro, cintura, altura, busto) VALUES (%s, %s, %s, %s, %s)",
            (id_tamanho, t.ombro, t.cintura, t.altura, t.busto),
        )


def existe_duplicada(conn: psycopg.Connection, dados: PecaIn, ignorar_id: Optional[int] = None) -> bool:
    """Regra de duplicidade: mesmo modelo (sem diferenciar maiúsculas) + categoria + gênero + corte."""
    sql = """SELECT 1 FROM peca_roupa
             WHERE lower(modelo) = lower(%s) AND categoria = %s AND genero = %s AND corte = %s"""
    params = [dados.modelo, dados.categoria, dados.genero, dados.corte]
    if ignorar_id is not None:
        sql += " AND id_peca <> %s"
        params.append(ignorar_id)
    return conn.execute(sql, params).fetchone() is not None


def buscar_pecas(conn: psycopg.Connection, ids: list[int]) -> list[dict]:
    return _montar(conn.execute(_SELECT_PECAS, (ids,)).fetchall())


def buscar_peca(conn: psycopg.Connection, id_peca: int) -> Optional[dict]:
    pecas = buscar_pecas(conn, [id_peca])
    return pecas[0] if pecas else None


def criar_peca(conn: psycopg.Connection, dados: PecaIn) -> int:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "INSERT INTO peca_roupa (modelo, categoria, genero, corte) VALUES (%s, %s, %s, %s) RETURNING id_peca",
            (dados.modelo, dados.categoria, dados.genero, dados.corte),
        )
        id_peca = cur.fetchone()["id_peca"]
        _inserir_tamanhos(cur, id_peca, dados)
    return id_peca


def listar_pecas(
    conn: psycopg.Connection,
    busca: Optional[str],
    categoria: Optional[str],
    genero: Optional[str],
    limite: int,
    offset: int,
) -> tuple[int, list[dict]]:
    where, params = ["TRUE"], []
    if busca:
        where.append("(p.modelo ILIKE %s OR CAST(p.id_peca AS TEXT) = %s)")
        params += [f"%{busca}%", busca]
    if categoria:
        where.append("p.categoria = %s")
        params.append(categoria)
    if genero:
        where.append("p.genero = %s")
        params.append(genero)
    filtro = " AND ".join(where)

    total = conn.execute(f"SELECT count(*) AS n FROM peca_roupa p WHERE {filtro}", params).fetchone()["n"]
    ids = [
        r["id_peca"]
        for r in conn.execute(
            f"SELECT p.id_peca FROM peca_roupa p WHERE {filtro} ORDER BY p.id_peca DESC LIMIT %s OFFSET %s",
            params + [limite, offset],
        ).fetchall()
    ]
    return total, (buscar_pecas(conn, ids) if ids else [])


def _apagar_tamanhos(cur, id_peca: int) -> None:
    cur.execute(
        "DELETE FROM medida WHERE id_tamanho IN (SELECT id_tamanho FROM tamanho WHERE id_peca = %s)",
        (id_peca,),
    )
    cur.execute("DELETE FROM tamanho WHERE id_peca = %s", (id_peca,))


def atualizar_peca(conn: psycopg.Connection, id_peca: int, dados: PecaIn) -> bool:
    """Substitui os dados da peça e seus tamanhos/medidas (semântica de PUT)."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "UPDATE peca_roupa SET modelo=%s, categoria=%s, genero=%s, corte=%s WHERE id_peca=%s",
            (dados.modelo, dados.categoria, dados.genero, dados.corte, id_peca),
        )
        if cur.rowcount == 0:
            return False
        _apagar_tamanhos(cur, id_peca)
        _inserir_tamanhos(cur, id_peca, dados)
    return True


def excluir_peca(conn: psycopg.Connection, id_peca: int) -> bool:
    """Exclusão definitiva (o banco não tem coluna 'ativo'): apaga medida -> tamanho -> peça."""
    with conn.transaction(), conn.cursor() as cur:
        _apagar_tamanhos(cur, id_peca)
        cur.execute("DELETE FROM peca_roupa WHERE id_peca = %s", (id_peca,))
        return cur.rowcount > 0
