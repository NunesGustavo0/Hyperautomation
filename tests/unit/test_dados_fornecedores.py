import pytest

from src.simuladores.dados_estoque import (
    obter_massa_estoque,
)
from src.simuladores.dados_fornecedores import (
    filtrar_pedidos,
    obter_massa_pedidos,
    paginar_pedidos,
)


def test_massa_possui_doze_pedidos_unicos():
    pedidos = obter_massa_pedidos()

    ids = {
        pedido.pedido_id
        for pedido in pedidos
    }

    assert len(pedidos) == 12
    assert len(ids) == 12


def test_lotes_sao_compativeis_com_estoque():
    lotes_estoque = {
        registro.lote_id
        for registro in obter_massa_estoque()
    }

    lotes_pedidos = {
        pedido.lote_id
        for pedido in obter_massa_pedidos()
    }

    assert lotes_pedidos == lotes_estoque


def test_massa_possui_casos_divergentes():
    pedidos = obter_massa_pedidos()

    status = {
        pedido.status_pedido
        for pedido in pedidos
    }

    assert "ATRASADO" in status
    assert "CANCELADO" in status
    assert "ENTREGUE" in status


def test_filtra_por_fornecedor():
    resultados = filtrar_pedidos(
        obter_massa_pedidos(),
        termo="amazon sensors",
    )

    assert len(resultados) == 1
    assert resultados[0].pedido_id == (
        "PED-2026-001"
    )


def test_filtra_por_status():
    resultados = filtrar_pedidos(
        obter_massa_pedidos(),
        status="ATRASADO",
    )

    assert len(resultados) == 3

    assert all(
        pedido.status_pedido == "ATRASADO"
        for pedido in resultados
    )


def test_paginar_em_tres_paginas():
    pedidos = obter_massa_pedidos()

    pagina_1 = paginar_pedidos(
        pedidos,
        pagina=1,
        tamanho_pagina=5,
    )

    pagina_2 = paginar_pedidos(
        pedidos,
        pagina=2,
        tamanho_pagina=5,
    )

    pagina_3 = paginar_pedidos(
        pedidos,
        pagina=3,
        tamanho_pagina=5,
    )

    assert len(pagina_1.registros) == 5
    assert len(pagina_2.registros) == 5
    assert len(pagina_3.registros) == 2
    assert pagina_3.total_registros == 12


@pytest.mark.parametrize(
    ("pagina", "tamanho"),
    [
        (0, 5),
        (1, 0),
        (4, 5),
    ],
)
def test_rejeita_paginacao_invalida(
    pagina,
    tamanho,
):
    with pytest.raises(ValueError):
        paginar_pedidos(
            obter_massa_pedidos(),
            pagina=pagina,
            tamanho_pagina=tamanho,
        )