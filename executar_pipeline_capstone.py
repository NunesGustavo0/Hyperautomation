"""Executa localmente os seis bots do capstone com simuladores reais.

Uso: ``python executar_pipeline_capstone.py --alertas console``.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Any
from urllib.request import urlopen
from uuid import uuid4

import requests
from openpyxl import Workbook

from executar_pipeline_bots import FormatadorJSON
from src.bots.bot_coleta_desktop import (
    ConfiguracaoColetaDesktop,
    executar_bot_coleta_desktop,
)
from src.bots.bot_coleta_web import ConfiguracaoColetaWeb, executar_bot_coleta_web
from src.contratos_capstone import PedidoFornecedor
from src.simuladores.dados_estoque import obter_massa_estoque, paginar_registros
from src.simuladores.dados_fornecedores import obter_massa_pedidos, paginar_pedidos


BOTS = (
    "bot-a-entrada",
    "bot-b-coleta-desktop",
    "bot-c-coleta-web",
    "bot-d-regras",
    "bot-e-ml",
    "bot-f-relatorio-alertas",
)


class AutomacaoDesktopSimulada:
    """Porta visual determinística apoiada pela massa do simulador desktop."""

    def __init__(self, tamanho_pagina: int = 5) -> None:
        self.pagina = 1
        self.tamanho_pagina = tamanho_pagina

    def localizar_aplicacao(self, timeout_ms: int) -> bool:
        return timeout_ms > 0

    def copiar_pagina_visivel(self) -> str:
        pagina = paginar_registros(
            obter_massa_estoque(),
            pagina=self.pagina,
            tamanho_pagina=self.tamanho_pagina,
        )
        linhas = [
            "lote_id\tproduto\tquantidade_disponivel\tlocalizacao\tstatus_estoque"
        ]
        linhas.extend(
            "\t".join(
                (
                    item.lote_id,
                    item.produto,
                    str(item.quantidade_disponivel),
                    item.localizacao,
                    item.status_estoque,
                )
            )
            for item in pagina.registros
        )
        return "\n".join(linhas)

    def avancar_pagina(self, timeout_ms: int) -> bool:
        pagina = paginar_registros(
            obter_massa_estoque(),
            pagina=self.pagina,
            tamanho_pagina=self.tamanho_pagina,
        )
        if self.pagina >= pagina.total_paginas:
            return False
        self.pagina += 1
        return True

    def capturar_screenshot(self, caminho: Path) -> None:
        caminho.write_bytes(b"simulador-desktop")


class AutomacaoWebSimulada:
    """Navegador local determinístico sobre a mesma massa servida pelo portal."""

    def __init__(self, tamanho_pagina: int = 5) -> None:
        self.pagina = 1
        self.tamanho_pagina = tamanho_pagina

    def abrir_portal(self, url: str, timeout_ms: int) -> None:
        with urlopen(f"{url}/health", timeout=timeout_ms / 1000) as resposta:
            if resposta.status != 200:
                raise RuntimeError("portal local indisponível")

    def coletar_pagina_atual(self) -> tuple[PedidoFornecedor, ...]:
        pagina = paginar_pedidos(
            obter_massa_pedidos(),
            pagina=self.pagina,
            tamanho_pagina=self.tamanho_pagina,
        )
        return tuple(PedidoFornecedor(**asdict(item)) for item in pagina.registros)

    def avancar_pagina(self, timeout_ms: int) -> bool:
        pagina = paginar_pedidos(
            obter_massa_pedidos(),
            pagina=self.pagina,
            tamanho_pagina=self.tamanho_pagina,
        )
        if self.pagina >= pagina.total_paginas:
            return False
        self.pagina += 1
        return True

    def capturar_screenshot(self, caminho: Path) -> None:
        caminho.write_bytes(b"simulador-web")

    def salvar_html(self, caminho: Path) -> None:
        caminho.write_text("<html>simulador web</html>", encoding="utf-8")

    def fechar(self) -> None:
        return None


@dataclass(frozen=True)
class ResultadoPipelineCapstone:
    sucesso: bool
    execution_id: str
    correlation_id: str
    total_desktop: int
    total_web: int
    total_consolidado: int
    caminho_relatorio: str
    caminho_logs: str
    processos_encerrados: bool


def _porta_livre() -> int:
    with socket.socket() as servidor:
        servidor.bind(("127.0.0.1", 0))
        return int(servidor.getsockname()[1])


def _encerrar(processo: subprocess.Popen[Any]) -> None:
    if processo.poll() is not None:
        return
    processo.terminate()
    try:
        processo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        processo.kill()
        processo.wait(timeout=5)


def _aguardar(url: str, processo: subprocess.Popen[Any]) -> None:
    for _ in range(50):
        if processo.poll() is not None:
            raise RuntimeError(f"processo auxiliar encerrou com código {processo.returncode}")
        try:
            with urlopen(url, timeout=0.2) as resposta:
                if resposta.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"serviço local não iniciou: {url}")


def _logger(caminho: Path) -> logging.Logger:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"capstone-e2e-{caminho}")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(caminho, encoding="utf-8")
    handler.setFormatter(FormatadorJSON())
    logger.addHandler(handler)
    return logger


def _registrar(logger: logging.Logger, bot_id: str, execution_id: str, correlation_id: str, **extra: Any) -> None:
    logger.info(
        f"{bot_id}_concluido",
        extra={
            "evento": f"{bot_id}_concluido",
            "bot_id": bot_id,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            **extra,
        },
    )


def executar_pipeline_capstone(
    *,
    diretorio_saida: Path = Path("data/output/capstone_e2e"),
    alertas: str = "console",
) -> ResultadoPipelineCapstone:
    diretorio_saida.mkdir(parents=True, exist_ok=True)
    execution_id = f"exec-{uuid4()}"
    correlation_id = f"corr-{uuid4()}"
    caminho_logs = diretorio_saida / "pipeline_capstone.jsonl"
    logger = _logger(caminho_logs)
    processos: list[subprocess.Popen[Any]] = []

    portal_porta = _porta_livre()
    ml_porta = _porta_livre()
    try:
        comandos = (
            [sys.executable, "-m", "src.simuladores.estoque_desktop", "--headless"],
            [sys.executable, "-m", "src.simuladores.portal_fornecedores", "--porta", str(portal_porta)],
            [sys.executable, "-m", "uvicorn", "api_ml.main:app", "--host", "127.0.0.1", "--port", str(ml_porta)],
        )
        for comando in comandos:
            processos.append(
                subprocess.Popen(
                    comando,
                    cwd=Path(__file__).resolve().parent,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
        _aguardar(f"http://127.0.0.1:{portal_porta}/health", processos[1])
        _aguardar(f"http://127.0.0.1:{ml_porta}/health", processos[2])

        _registrar(logger, BOTS[0], execution_id, correlation_id)

        desktop = executar_bot_coleta_desktop(
            AutomacaoDesktopSimulada(),
            execution_id=execution_id,
            correlation_id=correlation_id,
            task_id="task-b-e2e",
            configuracao=ConfiguracaoColetaDesktop(
                caminho_artefato=diretorio_saida / "estoque_desktop.json",
                diretorio_screenshots=diretorio_saida / "screenshots-desktop",
            ),
            logger=logger,
        )
        web = executar_bot_coleta_web(
            execution_id=execution_id,
            correlation_id=correlation_id,
            task_id="task-c-e2e",
            configuracao=ConfiguracaoColetaWeb(
                portal_url=f"http://127.0.0.1:{portal_porta}",
                caminho_artefato=diretorio_saida / "pedidos_fornecedores.json",
                diretorio_evidencias=diretorio_saida / "evidencias-web",
            ),
            fabrica_automacao=AutomacaoWebSimulada,
            logger=logger,
        )
        if not desktop.sucesso or not web.sucesso:
            raise RuntimeError("uma coleta local não produziu artefato")

        estoque = json.loads(desktop.caminho_artefato.read_text(encoding="utf-8"))["registros"]
        pedidos = json.loads(web.caminho_artefato.read_text(encoding="utf-8"))["registros"]
        pedidos_lote = {item["lote_id"]: item for item in pedidos}
        consolidados = [
            {
                **item,
                "quantidade_pedida": pedidos_lote[item["lote_id"]]["quantidade_pedida"],
                "status_pedido": pedidos_lote[item["lote_id"]]["status_pedido"],
                "execution_id": execution_id,
                "correlation_id": correlation_id,
            }
            for item in estoque
        ]
        caminho_consolidado = diretorio_saida / "registros_consolidados.json"
        caminho_consolidado.write_text(json.dumps(consolidados, ensure_ascii=False, indent=2), encoding="utf-8")
        _registrar(logger, BOTS[3], execution_id, correlation_id, total_registros=len(consolidados))

        classificados = []
        for item in consolidados:
            resposta = requests.post(
                f"http://127.0.0.1:{ml_porta}/predict",
                json={"observacao": f"Estoque {item['status_estoque']} e pedido {item['status_pedido']}"},
                timeout=5,
            )
            resposta.raise_for_status()
            classificados.append({**item, **resposta.json()})
        (diretorio_saida / "registros_classificados.json").write_text(
            json.dumps(classificados, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _registrar(logger, BOTS[4], execution_id, correlation_id, total_registros=len(classificados))

        relatorio = diretorio_saida / "relatorio_final.xlsx"
        workbook = Workbook()
        planilha = workbook.active
        planilha.title = "Consolidado"
        campos = ("lote_id", "produto", "quantidade_disponivel", "quantidade_pedida", "status_estoque", "status_pedido", "causa_provavel", "confianca_ml")
        planilha.append(campos)
        for item in classificados:
            planilha.append([item.get(campo) for campo in campos])
        workbook.save(relatorio)
        resumo = {
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "total_registros": len(classificados),
            "alerta": alertas,
            "relatorio": str(relatorio.resolve()),
        }
        (diretorio_saida / "resumo_execucao.json").write_text(
            json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if alertas == "console":
            print(json.dumps({"alerta_simulado": "pipeline_concluido", **resumo}, ensure_ascii=False))
        _registrar(logger, BOTS[5], execution_id, correlation_id, total_registros=len(classificados))
    finally:
        for processo in reversed(processos):
            _encerrar(processo)
        for handler in tuple(logger.handlers):
            handler.close()
            logger.removeHandler(handler)

    return ResultadoPipelineCapstone(
        sucesso=True,
        execution_id=execution_id,
        correlation_id=correlation_id,
        total_desktop=desktop.total_registros,
        total_web=web.total_registros,
        total_consolidado=len(classificados),
        caminho_relatorio=str(relatorio.resolve()),
        caminho_logs=str(caminho_logs.resolve()),
        processos_encerrados=all(processo.poll() is not None for processo in processos),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alertas", choices=("console", "nenhum"), default="console")
    parser.add_argument("--saida", type=Path, default=Path("data/output/capstone_e2e"))
    args = parser.parse_args(argv)
    try:
        resultado = executar_pipeline_capstone(diretorio_saida=args.saida, alertas=args.alertas)
    except Exception as erro:
        print(f"Pipeline capstone falhou: {erro}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(resultado), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
