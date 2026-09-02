"""Massa determinística do sistema desktop simulado de estoque."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable


@dataclass(frozen=True)
class ItemEstoqueSimulado:
    """Linha exibida na aplicação desktop de estoque."""

    lote_id: str
    produto: str
    quantidade_disponivel: int
    localizacao: str
    status_estoque: str

    def __post_init__(self) -> None:
        campos_texto = {
            "lote_id": self.lote_id,
            "produto": self.produto,
            "localizacao": self.localizacao,
            "status_estoque": self.status_estoque,
        }
        vazios = [
            nome
            for nome, valor in campos_texto.items()
            if not valor.strip()
        ]

        if vazios:
            raise ValueError(
                "Campos obrigatórios vazios: "
                + ", ".join(vazios)
            )

        if self.quantidade_disponivel < 0:
            raise ValueError(
                "quantidade_disponivel não pode ser negativa"
            )


@dataclass(frozen=True)
class PaginaEstoque:
    """Recorte paginado apresentado ao operador."""

    registros: tuple[ItemEstoqueSimulado, ...]
    pagina_atual: int
    total_paginas: int
    total_registros: int


MASSA_ESTOQUE = (
    ItemEstoqueSimulado(
        "LOTE-001",
        "Sensor de temperatura",
        20,
        "A-01",
        "DISPONIVEL",
    ),
    ItemEstoqueSimulado(
        "LOTE-002",
        "Atuador pneumático",
        8,
        "A-02",
        "ESTOQUE_BAIXO",
    ),
    ItemEstoqueSimulado(
        "LOTE-003",
        "Válvula de controle",
        0,
        "A-03",
        "INDISPONIVEL",
    ),
    ItemEstoqueSimulado(
        "LOTE-004",
        "Controlador lógico",
        14,
        "B-01",
        "DISPONIVEL",
    ),
    ItemEstoqueSimulado(
        "LOTE-005",
        "Módulo de comunicação",
        5,
        "B-02",
        "ESTOQUE_BAIXO",
    ),
    ItemEstoqueSimulado(
        "LOTE-006",
        "Fonte industrial",
        32,
        "B-03",
        "DISPONIVEL",
    ),
    ItemEstoqueSimulado(
        "LOTE-007",
        "Inversor de frequência",
        3,
        "C-01",
        "ESTOQUE_BAIXO",
    ),
    ItemEstoqueSimulado(
        "LOTE-008",
        "Motor trifásico",
        9,
        "C-02",
        "DISPONIVEL",
    ),
    ItemEstoqueSimulado(
        "LOTE-009",
        "Relé de proteção",
        18,
        "C-03",
        "DISPONIVEL",
    ),
    ItemEstoqueSimulado(
        "LOTE-010",
        "Disjuntor industrial",
        0,
        "D-01",
        "BLOQUEADO",
    ),
    ItemEstoqueSimulado(
        "LOTE-011",
        "Transmissor de pressão",
        11,
        "D-02",
        "DISPONIVEL",
    ),
    ItemEstoqueSimulado(
        "LOTE-012",
        "Cabo de instrumentação",
        4,
        "D-03",
        "ESTOQUE_BAIXO",
    ),
)


def obter_massa_estoque() -> tuple[ItemEstoqueSimulado, ...]:
    """Retorna a massa fixa utilizada em todas as demonstrações."""

    return MASSA_ESTOQUE


def filtrar_registros(
    registros: Iterable[ItemEstoqueSimulado],
    termo: str,
) -> tuple[ItemEstoqueSimulado, ...]:
    """Filtra por lote, produto, localização ou status."""

    registros_normalizados = tuple(registros)
    consulta = termo.strip().casefold()

    if not consulta:
        return registros_normalizados

    return tuple(
        registro
        for registro in registros_normalizados
        if consulta
        in " ".join(
            (
                registro.lote_id,
                registro.produto,
                registro.localizacao,
                registro.status_estoque,
            )
        ).casefold()
    )


def paginar_registros(
    registros: Iterable[ItemEstoqueSimulado],
    *,
    pagina: int,
    tamanho_pagina: int,
) -> PaginaEstoque:
    """Produz uma página validada da lista informada."""

    if tamanho_pagina <= 0:
        raise ValueError("tamanho_pagina deve ser maior que zero")

    if pagina <= 0:
        raise ValueError("pagina deve ser maior que zero")

    todos = tuple(registros)
    total_paginas = max(1, ceil(len(todos) / tamanho_pagina))

    if pagina > total_paginas:
        raise ValueError(
            f"pagina {pagina} não existe; "
            f"total de páginas: {total_paginas}"
        )

    inicio = (pagina - 1) * tamanho_pagina
    fim = inicio + tamanho_pagina

    return PaginaEstoque(
        registros=todos[inicio:fim],
        pagina_atual=pagina,
        total_paginas=total_paginas,
        total_registros=len(todos),
    )

