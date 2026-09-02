from fastapi.testclient import TestClient

from src.simuladores.portal_fornecedores import (
    ConfiguracaoPortal,
    criar_aplicacao,
)


def criar_cliente(
    *,
    modo: str = "normal",
    tamanho_pagina: int = 5,
    atraso_segundos: float = 0,
) -> TestClient:
    aplicacao = criar_aplicacao(
        ConfiguracaoPortal(
            modo=modo,
            tamanho_pagina=tamanho_pagina,
            atraso_segundos=atraso_segundos,
        )
    )

    return TestClient(
        aplicacao
    )


def test_portal_exibe_primeira_pagina():
    cliente = criar_cliente()

    resposta = cliente.get("/")

    assert resposta.status_code == 200

    assert (
        resposta.text.count(
            'data-testid="pedido-row"'
        )
        == 5
    )

    assert "PED-2026-001" in resposta.text
    assert "LOTE-001" in resposta.text
    assert "Amazon Sensors" in resposta.text


def test_portal_exibe_terceira_pagina():
    cliente = criar_cliente()

    resposta = cliente.get(
        "/",
        params={
            "pagina": 3,
        },
    )

    assert resposta.status_code == 200

    assert (
        resposta.text.count(
            'data-testid="pedido-row"'
        )
        == 2
    )

    assert "PED-2026-011" in resposta.text
    assert "PED-2026-012" in resposta.text

    assert (
        'data-testid="fim-paginacao"'
        in resposta.text
    )


def test_portal_filtra_pedidos_atrasados():
    cliente = criar_cliente()

    resposta = cliente.get(
        "/",
        params={
            "status": "ATRASADO",
        },
    )

    assert resposta.status_code == 200

    assert (
        resposta.text.count(
            'data-testid="pedido-row"'
        )
        == 3
    )

    assert "PED-2026-003" in resposta.text
    assert "PED-2026-007" in resposta.text
    assert "PED-2026-012" in resposta.text


def test_portal_filtra_por_fornecedor():
    cliente = criar_cliente()

    resposta = cliente.get(
        "/",
        params={
            "q": "Pressure Tech",
        },
    )

    assert resposta.status_code == 200
    assert "PED-2026-011" in resposta.text

    assert (
        resposta.text.count(
            'data-testid="pedido-row"'
        )
        == 1
    )


def test_modo_vazio_nao_exibe_pedidos():
    cliente = criar_cliente(
        modo="vazio",
    )

    resposta = cliente.get("/")

    assert resposta.status_code == 200

    assert (
        'data-testid="sem-registros"'
        in resposta.text
    )

    assert (
        'data-testid="pedido-row"'
        not in resposta.text
    )


def test_modo_erro_retorna_503():
    cliente = criar_cliente(
        modo="erro",
    )

    resposta = cliente.get("/")

    assert resposta.status_code == 503

    assert resposta.json() == {
        "detail": (
            "Portal de fornecedores "
            "temporariamente indisponível"
        )
    }


def test_health_informa_modo_normal():
    cliente = criar_cliente()

    resposta = cliente.get(
        "/health"
    )

    assert resposta.status_code == 200

    assert resposta.json() == {
        "servico": "portal_fornecedores",
        "status": "ok",
        "modo": "normal",
        "portal_disponivel": True,
    }


def test_health_informa_modo_degradado():
    cliente = criar_cliente(
        modo="erro",
    )

    resposta = cliente.get(
        "/health"
    )

    assert resposta.status_code == 200

    assert resposta.json()[
        "portal_disponivel"
    ] is False

    assert resposta.json()[
        "status"
    ] == "degradado"