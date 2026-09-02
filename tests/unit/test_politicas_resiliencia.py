"""Testes dos contratos compartilhados de tolerância a falhas."""

import pytest

from src.politicas_resiliencia import (
    ErroDeInfraestrutura,
    PoliticaResiliencia,
    executar_com_retry,
    obter_politica,
    sanitizar_dados,
)


def test_retry_tem_limite_e_backoff_exponencial():
    chamadas = 0
    esperas = []

    def operacao():
        nonlocal chamadas
        chamadas += 1
        raise ErroDeInfraestrutura("serviço indisponível")

    with pytest.raises(ErroDeInfraestrutura):
        executar_com_retry(
            operacao,
            politica=PoliticaResiliencia(
                max_tentativas=3,
                backoff_seconds=0.5,
                timeout_seconds=2,
            ),
            sleeper=esperas.append,
        )

    assert chamadas == 3
    assert esperas == [0.5, 1.0]


@pytest.mark.parametrize(
    "integracao",
    [
        "item",
        "base_referencia",
        "ml",
        "desktop",
        "portal_web",
        "telegram",
        "email",
    ],
)
def test_integracoes_possuem_limites_backoff_e_timeout(integracao):
    politica = obter_politica(integracao)

    assert politica.max_tentativas >= 1
    assert politica.backoff_seconds >= 0
    assert politica.timeout_seconds > 0


def test_payload_e_mensagem_tem_segredos_removidos():
    payload = {
        "lote_id": "LOTE-001",
        "password": "senha-real",
        "detalhes": {
            "token": "token-real",
            "erro": "Falhou com api_key=chave-real",
        },
    }

    seguro = sanitizar_dados(payload)

    assert seguro["lote_id"] == "LOTE-001"
    assert seguro["password"] == "[REDACTED]"
    assert seguro["detalhes"]["token"] == "[REDACTED]"
    assert "chave-real" not in seguro["detalhes"]["erro"]


@pytest.mark.parametrize(
    ("argumentos", "mensagem"),
    [
        ({"max_tentativas": 0}, "max_tentativas"),
        ({"backoff_seconds": -1}, "backoff_seconds"),
        ({"timeout_seconds": 0}, "timeout_seconds"),
    ],
)
def test_politica_rejeita_limites_invalidos(argumentos, mensagem):
    valores = {
        "max_tentativas": 1,
        "backoff_seconds": 0,
        "timeout_seconds": 1,
        **argumentos,
    }

    with pytest.raises(ValueError, match=mensagem):
        PoliticaResiliencia(**valores)
