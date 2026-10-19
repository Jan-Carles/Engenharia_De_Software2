"""Modelos de entrada/saída e validações (campos obrigatórios, valores inválidos, etc.)."""
import unicodedata
from decimal import Decimal
from typing import Any, List

from pydantic import BaseModel, Field, field_validator, model_validator

CATEGORIAS = ["Camiseta", "Calça", "Camisa", "Vestido", "Saia", "Blazer", "Outra"]
GENEROS = ["Feminino", "Masculino", "Unissex"]
CORTES = ["Reto", "Ajustado", "Oversized", "Evasê", "Outro"]

MEDIDA_MAXIMA_CM = Decimal("500")


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    ).lower()


def _texto_obrigatorio(valor: Any) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError("Campo obrigatório.")
    return valor.strip()


def _escolha(valor: Any, opcoes: List[str]) -> str:
    """Valida contra uma lista fechada, ignorando maiúsculas/acentos, e devolve o valor oficial."""
    texto = _texto_obrigatorio(valor)
    for opcao in opcoes:
        if _sem_acento(opcao) == _sem_acento(texto):
            return opcao
    raise ValueError(f"Valor inválido. Opções: {', '.join(opcoes)}.")


class TamanhoIn(BaseModel):
    """Um tamanho (P, M, 38...) com as suas medidas em centímetros."""

    tamanho: str
    ombro: Decimal = Field(allow_inf_nan=False, decimal_places=2)
    cintura: Decimal = Field(allow_inf_nan=False, decimal_places=2)
    altura: Decimal = Field(allow_inf_nan=False, decimal_places=2)
    busto: Decimal = Field(allow_inf_nan=False, decimal_places=2)

    @field_validator("tamanho", mode="before")
    @classmethod
    def _tamanho(cls, v: Any) -> str:
        v = _texto_obrigatorio(v).upper()
        if len(v) > 10:
            raise ValueError("Use no máximo 10 caracteres.")
        return v

    @field_validator("ombro", "cintura", "altura", "busto", mode="before")
    @classmethod
    def _aceita_virgula(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not v.strip()):
            raise ValueError("Campo obrigatório.")
        if isinstance(v, bool):
            raise ValueError("Valor numérico inválido.")
        if isinstance(v, str):
            return v.strip().replace(",", ".")  # o front aceita "38,5"
        return v

    @field_validator("ombro", "cintura", "altura", "busto")
    @classmethod
    def _positivo(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Deve ser maior que zero.")
        if v > MEDIDA_MAXIMA_CM:
            raise ValueError(f"Deve ser no máximo {MEDIDA_MAXIMA_CM} cm.")
        return v


class PecaIn(BaseModel):
    modelo: str
    categoria: str
    genero: str
    corte: str
    tamanhos: List[TamanhoIn] = Field(min_length=1)

    @field_validator("modelo", mode="before")
    @classmethod
    def _modelo(cls, v: Any) -> str:
        v = _texto_obrigatorio(v)
        if len(v) > 100:
            raise ValueError("Use no máximo 100 caracteres.")
        return v

    @field_validator("categoria", mode="before")
    @classmethod
    def _categoria(cls, v: Any) -> str:
        return _escolha(v, CATEGORIAS)

    @field_validator("genero", mode="before")
    @classmethod
    def _genero(cls, v: Any) -> str:
        return _escolha(v, GENEROS)

    @field_validator("corte", mode="before")
    @classmethod
    def _corte(cls, v: Any) -> str:
        return _escolha(v, CORTES)

    @model_validator(mode="after")
    def _tamanhos_unicos(self) -> "PecaIn":
        vistos, repetidos = set(), set()
        for t in self.tamanhos:
            (repetidos if t.tamanho in vistos else vistos).add(t.tamanho)
        if repetidos:
            raise ValueError(f"Tamanhos repetidos: {', '.join(sorted(repetidos))}.")
        return self


# ---------- saída ----------
class TamanhoOut(BaseModel):
    id_tamanho: int
    id_medida: int | None
    tamanho: str
    ombro: float | None
    cintura: float | None
    altura: float | None
    busto: float | None


class PecaOut(BaseModel):
    id_peca: int
    modelo: str
    categoria: str
    genero: str
    corte: str
    tamanhos: List[TamanhoOut]


class RespostaPeca(BaseModel):
    mensagem: str
    peca: PecaOut


class RespostaLista(BaseModel):
    total: int
    pagina: int
    limite: int
    itens: List[PecaOut]


class RespostaMensagem(BaseModel):
    mensagem: str
