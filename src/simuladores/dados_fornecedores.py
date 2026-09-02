"""Massa determinística do portal simulado de fornecedores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import ceil
from typing import Iterable


STATUS_PEDIDO_VALIDOS = frozenset(
    {
        "CONFIRMADO",
        "EM_TRANSITO",
        "ATRASADO",
        "CANCELADO",
        "ENTREGUE",
    }
)


@dataclass(frozen=True)
class PedidoFornecedorSimulado:
    """Pedido exibido no portal de fornecedores."""

    pedido_id: str
    lote_id: str
    fornecedor: str
    produto: str
    quantidade_pedida: int
    status_pedido: str
    previsao_entrega: date | None = None

    def __post_init__(self) -> None:
        campos_texto = {
            "pedido_id": self.pedido_id,
            "lote_id": self.lote_id,
            "fornecedor": self.fornecedor,
            "produto": self.produto,
            "status_pedido": self.status_pedido,
        }

        campos_vazios = [
            nome
            for nome, valor in campos_texto.items()
            if not valor.strip()
        ]

        if campos_vazios:
            raise ValueError(
                "Campos obrigatórios vazios: "
                + ", ".join(campos_vazios)
            )

        if self.quantidade_pedida < 0:
            raise ValueError(
                "quantidade_pedida não pode ser negativa"
            )

        if self.status_pedido not in STATUS_PEDIDO_VALIDOS:
            raise ValueError(
                "status_pedido inválido: "
                f"{self.status_pedido!r}"
            )


@dataclass(frozen=True)
class PaginaPedidos:
    """Recorte paginado apresentado no portal."""

    registros: tuple[PedidoFornecedorSimulado, ...]
    pagina_atual: int
    total_paginas: int
    total_registros: int


MASSA_PEDIDOS = (
    PedidoFornecedorSimulado(
        pedido_id="PED-2026-001",
        lote_id="LOTE-001",
        fornecedor="Amazon Sensors",
        produto="Sensor de temperatura",
        quantidade_pedida=10,
        status_pedido="CONFIRMADO",
        previsao_entrega=date(2026, 9, 5),
    ),
    PedidoFornecedorSimulado(
        pedido_id="PED-2026-002",
        lote_id="LOTE-002",
        fornecedor="PneumaTech",
        produto="Atuador pneumático",
        quantidade_pedida=12,
        status_pedido="EM_TRANSITO",
        previsao_entrega=date(2026, 9, 6),
    ),
    PedidoFornecedorSimulado(
        pedido_id="PED-2026-003",
        lote_id="LOTE-003",
        fornecedor="Controle Industrial",
        produto="Válvula de controle",
        quantidade_pedida=4,
        status_pedido="ATRASADO",
        previsao_entrega=date(2026, 8, 29),
    ),
    PedidoFornecedorSimulado(
        pedido_id="PED-2026-004",
        lote_id="LOTE-004",
        fornecedor="Logic Automação",
        produto="Controlador lógico",
        quantidade_pedida=14,
        status_pedido="CONFIRMADO",
        previsao_entrega=date(2026, 9, 7),
    ),
    PedidoFornecedorSimulado(
        pedido_id="PED-2026-005",
        lote_id="LOTE-005",
        fornecedor="Industrial Networks",
        produto="Módulo de comunicação",
        quantidade_pedida=3,
        status_pedido="ENTREGUE",
        previsao_entrega=date(2026, 8, 31),
    ),
    PedidoFornecedorSimulado(
        pedido_id="PED-2026-006",
        lote_id="LOTE-006",
        fornecedor="Power Manaus",
        produto="Fonte industrial",
        quantidade_pedida=40,
        status_pedido="CONFIRMADO",
        previsao_entrega=date(2026, 9, 8),
    ),
    PedidoFornecedorSimulado(
        pedido_id="PED-2026-007",
        lote_id="LOTE-007",
        fornecedor="Frequency Solutions",
        produto="Inversor de frequência",
        quantidade_pedida=3,
        status_pedido="ATRASADO",
        previsao_entrega=date(2026, 8, 30),
    ),
    PedidoFornecedorSimulado(
        pedido_id="PED-2026-008",
        lote_id="LOTE-008",
        fornecedor="Motores Norte",
        produto="Motor trifásico",
        quantidade_pedida=7,
        status_pedido="EM_TRANSITO",
        previsao_entrega=date(2026, 9, 9),
    ),
    PedidoFornecedorSimulado(
        pedido_id="PED-2026-009",
        lote_id="LOTE-009",
        fornecedor="Proteção Elétrica",
        produto="Relé de proteção",
        quantidade_pedida=18,
        status_pedido="CONFIRMADO",
        previsao_entrega=date(2026, 9, 10),
    ),
    PedidoFornecedorSimulado(
        pedido_id="PED-2026-010",
        lote_id="LOTE-010",
        fornecedor="Disjuntores Brasil",
        produto="Disjuntor industrial",
        quantidade_pedida=2,
        status_pedido="CANCELADO",
        previsao_entrega=None,
    ),
    PedidoFornecedorSimulado(
        pedido_id="PED-2026-011",
        lote_id="LOTE-011",
        fornecedor="Pressure Tech",
        produto="Transmissor de pressão",
        quantidade_pedida=6,
        status_pedido="ENTREGUE",
        previsao_entrega=date(2026, 8, 31),
    ),
    PedidoFornecedorSimulado(
        pedido_id="PED-2026-012",
        lote_id="LOTE-012",
        fornecedor="Cabos Amazônia",
        produto="Cabo de instrumentação",
        quantidade_pedida=8,
        status_pedido="ATRASADO",
        previsao_entrega=date(2026, 8, 28),
    ),
)


def obter_massa_pedidos(
) -> tuple[PedidoFornecedorSimulado, ...]:
    """Retorna a massa fixa utilizada nas demonstrações."""

    return MASSA_PEDIDOS


def filtrar_pedidos(
    registros: Iterable[PedidoFornecedorSimulado],
    *,
    termo: str = "",
    status: str = "",
) -> tuple[PedidoFornecedorSimulado, ...]:
    """Filtra pedidos pelo texto e pelo status informado."""

    consulta = termo.strip().casefold()
    status_normalizado = status.strip().upper()

    return tuple(
        registro
        for registro in registros
        if (
            not consulta
            or consulta
            in " ".join(
                (
                    registro.pedido_id,
                    registro.lote_id,
                    registro.fornecedor,
                    registro.produto,
                    registro.status_pedido,
                )
            ).casefold()
        )
        and (
            not status_normalizado
            or registro.status_pedido
            == status_normalizado
        )
    )


def paginar_pedidos(
    registros: Iterable[PedidoFornecedorSimulado],
    *,
    pagina: int,
    tamanho_pagina: int,
) -> PaginaPedidos:
    """Produz uma página validada da lista de pedidos."""

    if pagina <= 0:
        raise ValueError(
            "pagina deve ser maior que zero"
        )

    if tamanho_pagina <= 0:
        raise ValueError(
            "tamanho_pagina deve ser maior que zero"
        )

    todos = tuple(registros)

    total_paginas = max(
        1,
        ceil(
            len(todos)
            / tamanho_pagina
        ),
    )

    if pagina > total_paginas:
        raise ValueError(
            f"pagina {pagina} não existe; "
            f"total de páginas: {total_paginas}"
        )

    inicio = (
        pagina - 1
    ) * tamanho_pagina

    fim = inicio + tamanho_pagina

    return PaginaPedidos(
        registros=todos[inicio:fim],
        pagina_atual=pagina,
        total_paginas=total_paginas,
        total_registros=len(todos),
    )