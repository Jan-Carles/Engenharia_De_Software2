"""Testes de integração (precisam do PostgreSQL com o schema.sql aplicado).

Rodar:  pytest -v      (use um banco de teste: DB_NAME=engenharia2_teste pytest -v)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from database import get_conn
from main import app
import psycopg
from database import _dsn

client = TestClient(app)


@pytest.fixture(autouse=True)
def limpar_banco():
    with psycopg.connect(**_dsn(), autocommit=True) as c:
        c.execute("TRUNCATE medida, tamanho, peca_roupa RESTART IDENTITY CASCADE")
    yield


def peca(**extra):
    base = {
        "modelo": "Camisa de linho", "categoria": "Camisa", "genero": "Feminino", "corte": "Reto",
        "tamanhos": [{"tamanho": "M", "ombro": 38, "cintura": "72,5", "altura": 60, "busto": 90}],
    }
    return base | extra


def test_cadastro_ok():
    r = client.post("/pecas", json=peca())
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["mensagem"] == "Peça cadastrada com sucesso!"
    assert corpo["peca"]["tamanhos"][0]["cintura"] == 72.5  # vírgula aceita


def test_campos_obrigatorios_vazios():
    r = client.post("/pecas", json=peca(modelo="  ", categoria=""))
    assert r.status_code == 422
    campos = {d["campo"] for d in r.json()["detalhes"]}
    assert {"modelo", "categoria"} <= campos


@pytest.mark.parametrize("valor", [-1, 0, "abc", 501, 38.555])
def test_medida_invalida(valor):
    t = {"tamanho": "M", "ombro": valor, "cintura": 72, "altura": 60, "busto": 90}
    assert client.post("/pecas", json=peca(tamanhos=[t])).status_code == 422


def test_sem_tamanhos_e_tamanho_repetido():
    assert client.post("/pecas", json=peca(tamanhos=[])).status_code == 422
    t = peca()["tamanhos"][0]
    assert client.post("/pecas", json=peca(tamanhos=[t, t])).status_code == 422


def test_categoria_fora_da_lista():
    assert client.post("/pecas", json=peca(categoria="Chapéu")).status_code == 422


def test_duplicada():
    assert client.post("/pecas", json=peca()).status_code == 201
    r = client.post("/pecas", json=peca(modelo="CAMISA DE LINHO"))
    assert r.status_code == 409
    assert "erro" in r.json()


def test_consultar_editar_excluir():
    id_peca = client.post("/pecas", json=peca()).json()["peca"]["id_peca"]

    assert client.get(f"/pecas/{id_peca}").status_code == 200
    assert client.get("/pecas?busca=linho").json()["total"] == 1
    assert client.get("/pecas?busca=xyz").json()["total"] == 0

    novo = peca(modelo="Camisa de algodão", tamanhos=[
        {"tamanho": "P", "ombro": 36, "cintura": 68, "altura": 58, "busto": 86},
        {"tamanho": "G", "ombro": 40, "cintura": 76, "altura": 62, "busto": 96},
    ])
    r = client.put(f"/pecas/{id_peca}", json=novo)
    assert r.status_code == 200
    assert [t["tamanho"] for t in r.json()["peca"]["tamanhos"]] == ["P", "G"]

    assert client.delete(f"/pecas/{id_peca}").status_code == 200
    assert client.get(f"/pecas/{id_peca}").status_code == 404
    assert client.delete(f"/pecas/{id_peca}").status_code == 404
