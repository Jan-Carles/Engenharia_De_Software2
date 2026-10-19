"""API de peças de roupa (Backlog ID5) - FastAPI + PostgreSQL.

Rodar:  uvicorn main:app --reload      |  Documentação: http://localhost:8000/docs
"""
from typing import Optional

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import repository as repo
from database import get_conn
from schemas import (
    CATEGORIAS, CORTES, GENEROS,
    PecaIn, PecaOut, RespostaLista, RespostaMensagem, RespostaPeca,
)

app = FastAPI(title="Provador Virtual - Peças de roupa", version="1.0.0")

app.add_middleware(  # permite o front-end (outra porta) chamar a API em desenvolvimento
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ---------- mensagens de erro padronizadas: {"erro": "...", "detalhes": [...]} ----------
def _mensagem_campo(err: dict) -> str:
    tipo = err["type"]
    if tipo in ("missing", "string_type", "none_required"):
        return "Campo obrigatório."
    if tipo == "too_short":
        return "Informe ao menos um tamanho."
    if tipo == "decimal_max_places":
        return "Use no máximo 2 casas decimais."
    if tipo.startswith("decimal") or tipo in ("float_parsing", "finite_number"):
        return "Valor numérico inválido."
    if tipo == "json_invalid":
        return "JSON inválido."
    return err["msg"].removeprefix("Value error, ")


def _nome_campo(loc: tuple) -> str:
    nome = ""
    for parte in loc[1:]:  # loc[0] é "body"
        nome += f"[{parte}]" if isinstance(parte, int) else (f".{parte}" if nome else str(parte))
    return nome or "corpo"


@app.exception_handler(RequestValidationError)
async def erro_validacao(_: Request, exc: RequestValidationError):
    detalhes = [{"campo": _nome_campo(e["loc"]), "mensagem": _mensagem_campo(e)} for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"erro": "Não foi possível cadastrar: verifique os campos informados.", "detalhes": detalhes},
    )


@app.exception_handler(StarletteHTTPException)
async def erro_http(_: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"erro": exc.detail})


@app.exception_handler(psycopg.OperationalError)
async def erro_conexao(_: Request, exc: psycopg.OperationalError):
    return JSONResponse(status_code=503, content={"erro": "Banco de dados indisponível. Tente novamente."})


@app.exception_handler(psycopg.Error)
async def erro_banco(_: Request, exc: psycopg.Error):
    return JSONResponse(status_code=500, content={"erro": "Erro interno ao processar a operação."})


MSG_DUPLICADA = "Já existe uma peça com o mesmo modelo, categoria, gênero e corte."


def _peca_ou_404(conn, id_peca: int) -> dict:
    peca = repo.buscar_peca(conn, id_peca)
    if peca is None:
        raise HTTPException(404, "Peça não encontrada.")
    return peca


# ---------- endpoints ----------
@app.post("/pecas", status_code=201, response_model=RespostaPeca)
def cadastrar_peca(dados: PecaIn, conn=Depends(get_conn)):
    if repo.existe_duplicada(conn, dados):
        raise HTTPException(409, MSG_DUPLICADA)
    try:
        id_peca = repo.criar_peca(conn, dados)
    except psycopg.errors.UniqueViolation:  # índice único opcional do schema.sql
        raise HTTPException(409, MSG_DUPLICADA)
    return {"mensagem": "Peça cadastrada com sucesso!", "peca": repo.buscar_peca(conn, id_peca)}


@app.get("/pecas", response_model=RespostaLista)
def consultar_pecas(
    busca: Optional[str] = Query(None, description="Nome ou código (id) da peça"),
    categoria: Optional[str] = None,
    genero: Optional[str] = None,
    pagina: int = Query(1, ge=1),
    limite: int = Query(6, ge=1, le=100),
    conn=Depends(get_conn),
):
    total, itens = repo.listar_pecas(conn, busca, categoria, genero, limite, (pagina - 1) * limite)
    return {"total": total, "pagina": pagina, "limite": limite, "itens": itens}


@app.get("/pecas/opcoes")
def opcoes_formulario():
    """Valores aceitos nos campos de seleção do formulário (categoria, gênero e corte)."""
    return {"categorias": CATEGORIAS, "generos": GENEROS, "cortes": CORTES}


@app.get("/pecas/{id_peca}", response_model=PecaOut)
def consultar_peca(id_peca: int, conn=Depends(get_conn)):
    return _peca_ou_404(conn, id_peca)


@app.put("/pecas/{id_peca}", response_model=RespostaPeca)
def editar_peca(id_peca: int, dados: PecaIn, conn=Depends(get_conn)):
    _peca_ou_404(conn, id_peca)
    if repo.existe_duplicada(conn, dados, ignorar_id=id_peca):
        raise HTTPException(409, MSG_DUPLICADA)
    try:
        repo.atualizar_peca(conn, id_peca, dados)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, MSG_DUPLICADA)
    return {"mensagem": "Peça atualizada com sucesso!", "peca": repo.buscar_peca(conn, id_peca)}


@app.delete("/pecas/{id_peca}", response_model=RespostaMensagem)
def excluir_peca(id_peca: int, conn=Depends(get_conn)):
    if not repo.excluir_peca(conn, id_peca):
        raise HTTPException(404, "Peça não encontrada.")
    return {"mensagem": "Peça excluída com sucesso!"}
