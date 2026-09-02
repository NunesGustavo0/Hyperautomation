"""Testes de integração do Bot C com o portal real."""

from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
)
from contextlib import contextmanager
from pathlib import Path
import socket
from threading import Thread
import time
from typing import Iterator
import urllib.request

import uvicorn

from src.bots.bot_coleta_web import (
    ConfiguracaoColetaWeb,
    ResultadoColetaWeb,
    executar_bot_coleta_web,
)
from src.contratos_capstone import (
    ArtefatoPedidosFornecedor,
    EstadoExecucao,
)
from src.simuladores.portal_fornecedores import (
    ConfiguracaoPortal,
    criar_aplicacao,
)


def obter_porta_livre() -> int:
    """Obtém uma porta disponível para o teste."""

    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as servidor:
        servidor.bind(
            ("127.0.0.1", 0)
        )

        return int(
            servidor.getsockname()[1]
        )


@contextmanager
def executar_portal_teste(
    *,
    modo: str = "normal",
    atraso_segundos: float = 0.0,
) -> Iterator[str]:
    """Inicia o portal em uma thread isolada."""

    porta = obter_porta_livre()

    configuracao_portal = (
        ConfiguracaoPortal(
            modo=modo,
            atraso_segundos=(
                atraso_segundos
            ),
            tamanho_pagina=5,
            host="127.0.0.1",
            porta=porta,
        )
    )

    aplicacao = criar_aplicacao(
        configuracao_portal
    )

    configuracao_uvicorn = (
        uvicorn.Config(
            app=aplicacao,
            host="127.0.0.1",
            port=porta,
            log_level="critical",
        )
    )

    servidor = uvicorn.Server(
        configuracao_uvicorn
    )

    thread = Thread(
        target=servidor.run,
        daemon=True,
    )

    thread.start()

    url = (
        f"http://127.0.0.1:{porta}"
    )

    limite = time.monotonic() + 5

    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(
                f"{url}/health",
                timeout=0.5,
            ) as resposta:
                if resposta.status == 200:
                    break

        except Exception:
            time.sleep(0.05)

    else:
        servidor.should_exit = True

        thread.join(
            timeout=5
        )

        raise RuntimeError(
            "o portal de teste não iniciou"
        )

    try:
        yield url

    finally:
        servidor.should_exit = True

        thread.join(
            timeout=5
        )


def ler_artefato(
    caminho: Path,
) -> ArtefatoPedidosFornecedor:
    """Lê o resultado produzido pelo Bot C."""

    return (
        ArtefatoPedidosFornecedor
        .de_json(
            caminho.read_text(
                encoding="utf-8"
            )
        )
    )


def executar_bot_em_thread(
    **argumentos,
) -> ResultadoColetaWeb:
    """
    Executa o Playwright síncrono em uma
    thread sem loop asyncio ativo.
    """

    with ThreadPoolExecutor(
        max_workers=1
    ) as executor:
        futuro = executor.submit(
            executar_bot_coleta_web,
            **argumentos,
        )

        return futuro.result(
            timeout=30
        )


def test_bot_c_coleta_todas_as_paginas(
    tmp_path: Path,
):
    """Coleta os 12 registros usando Chromium real."""

    saida = (
        tmp_path
        / "pedidos_fornecedores.json"
    )

    evidencias = (
        tmp_path
        / "evidencias"
    )

    with executar_portal_teste(
        modo="normal"
    ) as url:
        resultado = (
            executar_bot_em_thread(
                execution_id=(
                    "exec-web-001"
                ),
                correlation_id=(
                    "corr-web-001"
                ),
                task_id=(
                    "task-web-001"
                ),
                configuracao=(
                    ConfiguracaoColetaWeb(
                        portal_url=url,
                        max_tentativas=1,
                        timeout_seconds=10,
                        backoff_seconds=0,
                        intervalo_paginas_seconds=0,
                        headless=True,
                        caminho_artefato=(
                            saida
                        ),
                        diretorio_evidencias=(
                            evidencias
                        ),
                    )
                ),
            )
        )

    assert resultado.sucesso is True

    assert (
        resultado.estado
        == EstadoExecucao.CONCLUIDO
    )

    assert resultado.tentativas == 1

    assert (
        resultado.total_registros
        == 12
    )

    assert saida.is_file()

    artefato = ler_artefato(
        saida
    )

    assert (
        artefato.total_registros
        == 12
    )

    assert (
        artefato.auditoria.execution_id
        == "exec-web-001"
    )

    assert (
        artefato
        .auditoria
        .correlation_id
        == "corr-web-001"
    )

    assert (
        artefato.auditoria.bot_id
        == "bot-c-coleta-web"
    )

    pedidos = {
        pedido.pedido_id: pedido
        for pedido
        in artefato.registros
    }

    assert len(pedidos) == 12

    assert (
        pedidos[
            "PED-2026-001"
        ].lote_id
        == "LOTE-001"
    )

    assert (
        pedidos[
            "PED-2026-012"
        ].lote_id
        == "LOTE-012"
    )


def test_bot_c_aceita_portal_sem_registros(
    tmp_path: Path,
):
    """O modo vazio conclui com uma lista vazia."""

    saida = (
        tmp_path
        / "pedidos_vazios.json"
    )

    with executar_portal_teste(
        modo="vazio"
    ) as url:
        resultado = (
            executar_bot_em_thread(
                execution_id=(
                    "exec-web-vazio"
                ),
                correlation_id=(
                    "corr-web-vazio"
                ),
                task_id=(
                    "task-web-vazio"
                ),
                configuracao=(
                    ConfiguracaoColetaWeb(
                        portal_url=url,
                        max_tentativas=1,
                        timeout_seconds=5,
                        backoff_seconds=0,
                        intervalo_paginas_seconds=0,
                        headless=True,
                        caminho_artefato=(
                            saida
                        ),
                        diretorio_evidencias=(
                            tmp_path
                            / "evidencias-vazio"
                        ),
                    )
                ),
            )
        )

    assert resultado.sucesso is True

    assert (
        resultado.total_registros
        == 0
    )

    artefato = ler_artefato(
        saida
    )

    assert artefato.registros == ()

    assert (
        artefato.auditoria.estado
        == EstadoExecucao.CONCLUIDO
    )


def test_bot_c_trata_portal_indisponivel(
    tmp_path: Path,
):
    """HTTP 503 gera falha controlada e evidência."""

    saida = (
        tmp_path
        / "pedidos_falha.json"
    )

    evidencias = (
        tmp_path
        / "evidencias-erro"
    )

    with executar_portal_teste(
        modo="erro"
    ) as url:
        resultado = (
            executar_bot_em_thread(
                execution_id=(
                    "exec-web-erro"
                ),
                correlation_id=(
                    "corr-web-erro"
                ),
                task_id=(
                    "task-web-erro"
                ),
                configuracao=(
                    ConfiguracaoColetaWeb(
                        portal_url=url,
                        max_tentativas=2,
                        timeout_seconds=5,
                        backoff_seconds=0,
                        intervalo_paginas_seconds=0,
                        headless=True,
                        caminho_artefato=(
                            saida
                        ),
                        diretorio_evidencias=(
                            evidencias
                        ),
                    )
                ),
                sleeper=lambda _: None,
            )
        )

    assert resultado.sucesso is False

    assert (
        resultado.estado
        == EstadoExecucao.FALHOU
    )

    assert resultado.tentativas == 2

    assert (
        resultado.total_registros
        == 0
    )

    assert resultado.erro is not None

    assert "503" in resultado.erro

    assert (
        resultado.caminho_screenshot
        is not None
    )

    assert (
        resultado
        .caminho_screenshot
        .is_file()
    )

    assert (
        resultado.caminho_html
        is not None
    )

    assert (
        resultado
        .caminho_html
        .is_file()
    )

    artefato = ler_artefato(
        saida
    )

    assert artefato.registros == ()

    assert (
        artefato.auditoria.estado
        == EstadoExecucao.FALHOU
    )


def test_bot_c_trata_portal_acima_timeout(
    tmp_path: Path,
):
    """Atraso maior que o timeout não bloqueia o bot."""

    saida = (
        tmp_path
        / "pedidos_timeout.json"
    )

    evidencias = (
        tmp_path
        / "evidencias-timeout"
    )

    with executar_portal_teste(
        modo="lento",
        atraso_segundos=1,
    ) as url:
        resultado = (
            executar_bot_em_thread(
                execution_id=(
                    "exec-web-timeout"
                ),
                correlation_id=(
                    "corr-web-timeout"
                ),
                task_id=(
                    "task-web-timeout"
                ),
                configuracao=(
                    ConfiguracaoColetaWeb(
                        portal_url=url,
                        max_tentativas=1,
                        timeout_seconds=0.2,
                        backoff_seconds=0,
                        intervalo_paginas_seconds=0,
                        headless=True,
                        caminho_artefato=(
                            saida
                        ),
                        diretorio_evidencias=(
                            evidencias
                        ),
                    )
                ),
            )
        )

    assert resultado.sucesso is False

    assert (
        resultado.estado
        == EstadoExecucao.FALHOU
    )

    assert resultado.tentativas == 1

    assert resultado.erro is not None

    assert (
        "timeout"
        in resultado.erro.lower()
    )

    artefato = ler_artefato(
        saida
    )

    assert (
        artefato.auditoria.estado
        == EstadoExecucao.FALHOU
    )