"""Bot C: coleta de pedidos no portal web de fornecedores."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
import time
from typing import Callable, Protocol, Sequence
from urllib.parse import urlparse

from src.contratos_capstone import (
    ArtefatoPedidosFornecedor,
    EnvelopeAuditoria,
    EstadoExecucao,
    PedidoFornecedor,
)

from src.pages.portal_fornecedores_page import (
    PortalFornecedoresPage,
)

LOGGER = logging.getLogger(
    "botcity_permorfer"
)

BOT_ID = "bot-c-coleta-web"


class FalhaColetaWebError(RuntimeError):
    """Representa uma falha controlada na automação web."""


class PortaAutomacaoWeb(Protocol):
    """Operações necessárias para automatizar o portal."""

    def abrir_portal(
        self,
        url: str,
        timeout_ms: int,
    ) -> None:
        """Abre o portal no navegador."""

    def coletar_pagina_atual(
        self,
    ) -> tuple[PedidoFornecedor, ...]:
        """Extrai os pedidos visíveis."""

    def avancar_pagina(
        self,
        timeout_ms: int,
    ) -> bool:
        """Avança e informa se existe outra página."""

    def capturar_screenshot(
        self,
        caminho: Path,
    ) -> None:
        """Captura evidência visual."""

    def salvar_html(
        self,
        caminho: Path,
    ) -> None:
        """Salva o HTML atual como evidência."""

    def fechar(self) -> None:
        """Encerra navegador e recursos."""


@dataclass(frozen=True)
class ConfiguracaoColetaWeb:
    """Configura a coleta e seus limites de segurança."""


    portal_url: str = (
        "http://127.0.0.1:8010"
    )

    max_tentativas: int = 3
    timeout_seconds: float = 10.0
    backoff_seconds: float = 1.0
    max_paginas: int = 20
    headless: bool = True
    intervalo_paginas_seconds: float = 0.0

    caminho_artefato: Path = Path(
        "data/output/pedidos_fornecedores.json"
    )

    diretorio_evidencias: Path = Path(
        "screenshots/bot_web"
    )

    def __post_init__(self) -> None:
        endereco = urlparse(self.portal_url)

        if endereco.scheme not in {
            "http",
            "https",
        }:
            raise ValueError(
                "portal_url deve utilizar "
                "http ou https"
            )

        if not endereco.netloc:
            raise ValueError(
                "portal_url deve possuir host"
            )

        if self.max_tentativas <= 0:
            raise ValueError(
                "max_tentativas deve ser "
                "maior que zero"
            )

        if self.timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds deve ser "
                "maior que zero"
            )

        if self.backoff_seconds < 0:
            raise ValueError(
                "backoff_seconds não pode "
                "ser negativo"
            )

        if self.max_paginas <= 0:
            raise ValueError(
                "max_paginas deve ser "
                "maior que zero"
            )
        if self.intervalo_paginas_seconds < 0:
            raise ValueError(
                "intervalo_paginas_seconds "
                "não pode ser negativo"
            )


@dataclass(frozen=True)
class ResultadoColetaWeb:
    """Resultado devolvido pelo Bot C."""

    sucesso: bool
    estado: EstadoExecucao
    tentativas: int
    total_registros: int
    caminho_artefato: Path
    caminho_screenshot: Path | None = None
    caminho_html: Path | None = None
    erro: str | None = None


def _assinatura_pedido(
    pedido: PedidoFornecedor,
) -> tuple[object, ...]:
    """Compara pedidos ignorando o horário da coleta."""

    return (
        pedido.pedido_id,
        pedido.lote_id,
        pedido.fornecedor,
        pedido.produto,
        pedido.quantidade_pedida,
        pedido.status_pedido,
        pedido.previsao_entrega,
    )


def coletar_todas_paginas(
    automacao: PortaAutomacaoWeb,
    configuracao: ConfiguracaoColetaWeb,
    *,
    clock: Callable[[], float] = (
        time.monotonic
    ),
    sleeper: Callable[
        [float],
        None,
    ] = time.sleep,
    logger: logging.Logger | None = None,
) -> tuple[PedidoFornecedor, ...]:
    """Percorre todas as páginas do portal."""

    logger = logger or LOGGER
    inicio = clock()

    timeout_ms = max(
        1,
        int(
            configuracao.timeout_seconds
            * 1_000
        ),
    )

    automacao.abrir_portal(
        configuracao.portal_url,
        timeout_ms,
    )

    registros: dict[
        str,
        PedidoFornecedor,
    ] = {}

    paginas_vistas: set[
        tuple[str, ...]
    ] = set()

    for numero_pagina in range(
        1,
        configuracao.max_paginas + 1,
    ):
        tempo_decorrido = (
            clock() - inicio
        )

        if (
            tempo_decorrido
            > configuracao.timeout_seconds
        ):
            raise FalhaColetaWebError(
                "timeout durante a coleta "
                "das páginas do portal"
            )

        pedidos_pagina = (
            automacao.coletar_pagina_atual()
        )

        assinatura_pagina = tuple(
            pedido.pedido_id
            for pedido in pedidos_pagina
        )

        if (
            assinatura_pagina
            and assinatura_pagina
            in paginas_vistas
        ):
            raise FalhaColetaWebError(
                "o portal retornou uma página "
                "já coletada"
            )

        paginas_vistas.add(
            assinatura_pagina
        )

        for pedido in pedidos_pagina:
            pedido_anterior = registros.get(
                pedido.pedido_id
            )

            if (
                pedido_anterior is not None
                and _assinatura_pedido(
                    pedido_anterior
                )
                != _assinatura_pedido(pedido)
            ):
                raise FalhaColetaWebError(
                    "pedido duplicado com dados "
                    "diferentes: "
                    f"{pedido.pedido_id}"
                )

            registros[pedido.pedido_id] = (
                pedido
            )

        logger.info(
            (
                "Página %d coletada: "
                "%d registro(s); acumulado=%d"
            ),
            numero_pagina,
            len(pedidos_pagina),
            len(registros),
            extra={
                "evento": (
                    "coleta_web_pagina_coletada"
                ),
                "bot_id": BOT_ID,
                "pagina": numero_pagina,
                "registros_pagina": (
                    len(pedidos_pagina)
                ),
                "registros_acumulados": (
                    len(registros)
                ),
            },
        )

        tempo_restante = (
            configuracao.timeout_seconds
            - (clock() - inicio)
        )

        if tempo_restante <= 0:
            raise FalhaColetaWebError(
                "timeout antes do fim "
                "da paginação"
            )

        possui_proxima = (
            automacao.avancar_pagina(
                max(
                    1,
                    int(
                        tempo_restante
                        * 1_000
                    ),
                )
            )
        )

        if not possui_proxima:
            logger.info(
                (
                    "Navegação finalizada: "
                    "%d página(s); "
                    "%d registro(s)"
                ),
                numero_pagina,
                len(registros),
                extra={
                    "evento": (
                        "coleta_web_navegacao_"
                        "finalizada"
                    ),
                    "bot_id": BOT_ID,
                    "total_paginas": (
                        numero_pagina
                    ),
                    "total_registros": (
                        len(registros)
                    ),
                },
            )

            return tuple(
                registros.values()
            )
        if (
                configuracao
                        .intervalo_paginas_seconds
                > 0
        ):

            logger.info(
                (
                    "Aguardando %.1f segundo(s) "
                    "antes de coletar "
                    "a próxima página"
                ),
                (
                    configuracao
                    .intervalo_paginas_seconds
                ),
                extra={
                    "evento": (
                        "coleta_web_aguardando_"
                        "proxima_pagina"
                    ),
                    "bot_id": BOT_ID,
                    "pagina_atual": (
                        numero_pagina
                    ),
                    "intervalo_seconds": (
                        configuracao
                        .intervalo_paginas_seconds
                    ),
                },

            )

            sleeper(
                configuracao
                .intervalo_paginas_seconds
            )

    raise FalhaColetaWebError(
        "limite de páginas atingido "
        "antes do fim da coleta"
    )


def _criar_artefato(
    *,
    execution_id: str,
    correlation_id: str,
    task_id: str,
    estado: EstadoExecucao,
    registros: Sequence[
        PedidoFornecedor
    ],
    predecessor: str | None,
    predecessor_task_id: str | None,
    resultado_predecessor: str | None,
) -> ArtefatoPedidosFornecedor:
    """Cria o contrato produzido pelo Bot C."""

    return ArtefatoPedidosFornecedor(
        auditoria=EnvelopeAuditoria(
            execution_id=execution_id,
            correlation_id=correlation_id,
            bot_id=BOT_ID,
            task_id=task_id,
            estado=estado,
            predecessor=predecessor,
            predecessor_task_id=(
                predecessor_task_id
            ),
            resultado_predecessor=(
                resultado_predecessor
            ),
        ),
        registros=tuple(registros),
    )


def salvar_artefato(
    artefato: ArtefatoPedidosFornecedor,
    caminho: Path,
) -> Path:
    """Salva o JSON de maneira atômica."""

    caminho = Path(caminho)

    caminho.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporario = caminho.with_suffix(
        caminho.suffix + ".tmp"
    )

    temporario.write_text(
        artefato.para_json(),
        encoding="utf-8",
    )

    temporario.replace(caminho)

    return caminho

class AdaptadorPlaywright:
    """Automação real usando Playwright e POM."""

    def __init__(
        self,
        *,
        headless: bool = True,
    ) -> None:
        try:
            from playwright.sync_api import (
                sync_playwright,
            )
        except ImportError as erro:
            raise RuntimeError(
                "Playwright não está instalado. "
                "Execute: uv add playwright"
            ) from erro

        self._gerenciador = (
            sync_playwright().start()
        )

        try:
            self._browser = (
                self._gerenciador
                .chromium
                .launch(
                    headless=headless,
                )
            )

            self._contexto = (
                self._browser.new_context(
                    locale="pt-BR",
                )
            )

            page = (
                self._contexto.new_page()
            )

        except Exception:
            self._gerenciador.stop()
            raise

        self._portal = (
            PortalFornecedoresPage(page)
        )

    def abrir_portal(
        self,
        url: str,
        timeout_ms: int,
    ) -> None:
        self._portal.abrir(
            url,
            timeout_ms,
        )

    def coletar_pagina_atual(
        self,
    ) -> tuple[PedidoFornecedor, ...]:
        linhas = (
            self._portal.extrair_pedidos()
        )

        pedidos: list[
            PedidoFornecedor
        ] = []

        for linha in linhas:
            previsao = None

            if (
                linha.previsao_entrega
                is not None
            ):
                try:
                    previsao = (
                        datetime.strptime(
                            linha.previsao_entrega,
                            "%d/%m/%Y",
                        ).date()
                    )
                except ValueError as erro:
                    raise FalhaColetaWebError(
                        "previsão de entrega "
                        "inválida no pedido "
                        f"{linha.pedido_id}: "
                        f"{linha.previsao_entrega!r}"
                    ) from erro

            pedidos.append(
                PedidoFornecedor(
                    pedido_id=(
                        linha.pedido_id
                    ),
                    lote_id=linha.lote_id,
                    fornecedor=(
                        linha.fornecedor
                    ),
                    produto=linha.produto,
                    quantidade_pedida=(
                        linha.quantidade_pedida
                    ),
                    status_pedido=(
                        linha.status_pedido
                    ),
                    previsao_entrega=(
                        previsao
                    ),
                )
            )

        return tuple(pedidos)

    def avancar_pagina(
        self,
        timeout_ms: int,
    ) -> bool:
        return (
            self._portal
            .avancar_pagina(
                timeout_ms
            )
        )

    def capturar_screenshot(
        self,
        caminho: Path,
    ) -> None:
        self._portal.capturar_screenshot(
            caminho
        )

    def salvar_html(
        self,
        caminho: Path,
    ) -> None:
        self._portal.salvar_html(
            caminho
        )

    def fechar(self) -> None:
        """Encerra os recursos na ordem inversa."""

        try:
            self._contexto.close()
        finally:
            try:
                self._browser.close()
            finally:
                self._gerenciador.stop()

def _capturar_evidencias_seguras(
    automacao: PortaAutomacaoWeb,
    configuracao: ConfiguracaoColetaWeb,
    tentativa: int,
    logger: logging.Logger,
) -> tuple[Path | None, Path | None]:
    """Captura screenshot e HTML sem derrubar o bot."""

    diretorio = (
        configuracao.diretorio_evidencias
    )

    diretorio.mkdir(
        parents=True,
        exist_ok=True,
    )

    caminho_screenshot = (
        diretorio
        / f"falha_tentativa_{tentativa}.png"
    )

    caminho_html = (
        diretorio
        / f"falha_tentativa_{tentativa}.html"
    )

    screenshot_salvo: Path | None = None
    html_salvo: Path | None = None

    try:
        automacao.capturar_screenshot(
            caminho_screenshot
        )

        screenshot_salvo = (
            caminho_screenshot
        )

    except Exception as erro:
        logger.warning(
            "screenshot_coleta_web_falhou",
            extra={
                "evento": (
                    "screenshot_coleta_web_"
                    "falhou"
                ),
                "bot_id": BOT_ID,
                "tentativa": tentativa,
                "erro": str(erro),
            },
        )

    try:
        automacao.salvar_html(
            caminho_html
        )

        html_salvo = caminho_html

    except Exception as erro:
        logger.warning(
            "html_coleta_web_falhou",
            extra={
                "evento": (
                    "html_coleta_web_falhou"
                ),
                "bot_id": BOT_ID,
                "tentativa": tentativa,
                "erro": str(erro),
            },
        )

    return (
        screenshot_salvo,
        html_salvo,
    )


def _fechar_automacao_segura(
    automacao: PortaAutomacaoWeb,
    logger: logging.Logger,
) -> None:
    """Fecha o navegador sem esconder o resultado do bot."""

    try:
        automacao.fechar()

    except Exception as erro:
        logger.warning(
            "fechamento_navegador_falhou",
            extra={
                "evento": (
                    "fechamento_navegador_"
                    "falhou"
                ),
                "bot_id": BOT_ID,
                "erro": str(erro),
            },
        )


def executar_bot_coleta_web(
    *,
    execution_id: str,
    correlation_id: str,
    task_id: str,
    configuracao: (
        ConfiguracaoColetaWeb | None
    ) = None,
    predecessor: str | None = None,
    predecessor_task_id: str | None = None,
    resultado_predecessor: str | None = None,
    fabrica_automacao: (
        Callable[
            [],
            PortaAutomacaoWeb,
        ]
        | None
    ) = None,
    sleeper: Callable[
        [float],
        None,
    ] = time.sleep,
    logger: logging.Logger | None = None,
) -> ResultadoColetaWeb:
    """Executa o Bot C com tentativas limitadas."""

    configuracao = (
        configuracao
        or ConfiguracaoColetaWeb()
    )


    logger = logger or LOGGER

    if fabrica_automacao is None:

        def fabrica_padrao(
        ) -> PortaAutomacaoWeb:
            return AdaptadorPlaywright(
                headless=(
                    configuracao.headless
                )
            )

        fabrica_automacao = (
            fabrica_padrao
        )

    ultimo_erro: str | None = None
    ultimo_screenshot: Path | None = None
    ultimo_html: Path | None = None

    for tentativa in range(
        1,
        configuracao.max_tentativas + 1,
    ):
        automacao: (
            PortaAutomacaoWeb | None
        ) = None

        logger.info(
            "coleta_web_tentativa_iniciada",
            extra={
                "evento": (
                    "coleta_web_tentativa_"
                    "iniciada"
                ),
                "bot_id": BOT_ID,
                "execution_id": execution_id,
                "correlation_id": (
                    correlation_id
                ),
                "task_id": task_id,
                "tentativa": tentativa,
                "portal_url": (
                    configuracao.portal_url
                ),
            },
        )

        try:
            automacao = (
                fabrica_automacao()
            )

            registros = coletar_todas_paginas(
                automacao,
                configuracao,
                sleeper=sleeper,
                logger=logger,
            )

            artefato = _criar_artefato(
                execution_id=execution_id,
                correlation_id=(
                    correlation_id
                ),
                task_id=task_id,
                estado=(
                    EstadoExecucao.CONCLUIDO
                ),
                registros=registros,
                predecessor=predecessor,
                predecessor_task_id=(
                    predecessor_task_id
                ),
                resultado_predecessor=(
                    resultado_predecessor
                ),
            )

            caminho = salvar_artefato(
                artefato,
                configuracao.caminho_artefato,
            )

            logger.info(
                "coleta_web_concluida",
                extra={
                    "evento": (
                        "coleta_web_concluida"
                    ),
                    "bot_id": BOT_ID,
                    "execution_id": (
                        execution_id
                    ),
                    "correlation_id": (
                        correlation_id
                    ),
                    "task_id": task_id,
                    "tentativas": tentativa,
                    "total_registros": (
                        len(registros)
                    ),
                    "caminho_artefato": (
                        str(caminho)
                    ),
                },
            )

            return ResultadoColetaWeb(
                sucesso=True,
                estado=(
                    EstadoExecucao.CONCLUIDO
                ),
                tentativas=tentativa,
                total_registros=(
                    len(registros)
                ),
                caminho_artefato=caminho,
            )

        except Exception as erro:
            ultimo_erro = str(erro)

            if automacao is not None:
                (
                    ultimo_screenshot,
                    ultimo_html,
                ) = (
                    _capturar_evidencias_seguras(
                        automacao,
                        configuracao,
                        tentativa,
                        logger,
                    )
                )

            logger.warning(
                "coleta_web_tentativa_falhou",
                extra={
                    "evento": (
                        "coleta_web_tentativa_"
                        "falhou"
                    ),
                    "bot_id": BOT_ID,
                    "execution_id": (
                        execution_id
                    ),
                    "correlation_id": (
                        correlation_id
                    ),
                    "task_id": task_id,
                    "tentativa": tentativa,
                    "erro": ultimo_erro,
                    "screenshot": (
                        str(
                            ultimo_screenshot
                        )
                        if ultimo_screenshot
                        is not None
                        else None
                    ),
                    "html": (
                        str(ultimo_html)
                        if ultimo_html
                        is not None
                        else None
                    ),
                },
            )

            if (
                tentativa
                < configuracao.max_tentativas
            ):
                tempo_backoff = (
                    configuracao
                    .backoff_seconds
                    * tentativa
                )

                logger.info(
                    "coleta_web_aguardando_retry",
                    extra={
                        "evento": (
                            "coleta_web_aguardando_"
                            "retry"
                        ),
                        "bot_id": BOT_ID,
                        "tentativa": tentativa,
                        "backoff_seconds": (
                            tempo_backoff
                        ),
                    },
                )

                sleeper(tempo_backoff)

        finally:
            if automacao is not None:
                _fechar_automacao_segura(
                    automacao,
                    logger,
                )

    artefato_falha = _criar_artefato(
        execution_id=execution_id,
        correlation_id=correlation_id,
        task_id=task_id,
        estado=EstadoExecucao.FALHOU,
        registros=(),
        predecessor=predecessor,
        predecessor_task_id=(
            predecessor_task_id
        ),
        resultado_predecessor=(
            resultado_predecessor
        ),
    )

    caminho = salvar_artefato(
        artefato_falha,
        configuracao.caminho_artefato,
    )

    logger.error(
        "coleta_web_falhou",
        extra={
            "evento": (
                "coleta_web_falhou"
            ),
            "bot_id": BOT_ID,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "tentativas": (
                configuracao.max_tentativas
            ),
            "erro": ultimo_erro,
            "caminho_artefato": (
                str(caminho)
            ),
            "screenshot": (
                str(ultimo_screenshot)
                if ultimo_screenshot
                is not None
                else None
            ),
            "html": (
                str(ultimo_html)
                if ultimo_html is not None
                else None
            ),
        },
    )

    return ResultadoColetaWeb(
        sucesso=False,
        estado=EstadoExecucao.FALHOU,
        tentativas=(
            configuracao.max_tentativas
        ),
        total_registros=0,
        caminho_artefato=caminho,
        caminho_screenshot=(
            ultimo_screenshot
        ),
        caminho_html=ultimo_html,
        erro=ultimo_erro,
    )


def construir_parser(
) -> argparse.ArgumentParser:
    """Cria os argumentos da execução local."""

    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "--url",
        default=(
            "http://127.0.0.1:8010"
        ),
    )

    parser.add_argument(
        "--execution-id",
        default="exec-local-web",
    )

    parser.add_argument(
        "--correlation-id",
        default="corr-local-web",
    )

    parser.add_argument(
        "--task-id",
        default="task-local-web",
    )

    parser.add_argument(
        "--saida",
        type=Path,
        default=Path(
            "data/output/"
            "pedidos_fornecedores.json"
        ),
    )

    parser.add_argument(
        "--evidencias",
        type=Path,
        default=Path(
            "screenshots/bot_web"
        ),
    )

    parser.add_argument(
        "--tentativas",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
    )

    parser.add_argument(
        "--backoff",
        type=float,
        default=1.0,
    )

    parser.add_argument(
        "--com-interface",
        action="store_true",
        help=(
            "Exibe o Chromium durante "
            "a automação."
        ),
    )

    parser.add_argument(
        "--intervalo-paginas",
        type=float,
        default=0.0,
        help=(
            "Tempo de espera entre a coleta "
            "de cada página."
        ),
    )

    return parser


def main(
    argv: list[str] | None = None,
) -> int:
    """Executa o Bot C pelo terminal."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    LOGGER.setLevel(logging.INFO)

    argumentos = (
        construir_parser()
        .parse_args(argv)
    )

    configuracao = (
        ConfiguracaoColetaWeb(
            portal_url=argumentos.url,
            max_tentativas=(
                argumentos.tentativas
            ),
            timeout_seconds=(
                argumentos.timeout
            ),
            backoff_seconds=(
                argumentos.backoff
            ),
            headless=(
                not argumentos.com_interface
            ),
            caminho_artefato=(
                argumentos.saida
            ),
            diretorio_evidencias=(
                argumentos.evidencias
            ),
            intervalo_paginas_seconds=(
                argumentos.intervalo_paginas
            ),
        )
    )

    resultado = (
        executar_bot_coleta_web(
            execution_id=(
                argumentos.execution_id
            ),
            correlation_id=(
                argumentos.correlation_id
            ),
            task_id=argumentos.task_id,
            configuracao=configuracao,
        )
    )

    print(
        f"estado={resultado.estado.value} "
        f"registros="
        f"{resultado.total_registros} "
        f"tentativas="
        f"{resultado.tentativas} "
        f"artefato="
        f"{resultado.caminho_artefato}"
    )

    if resultado.erro is not None:
        print(
            f"erro={resultado.erro}"
        )

    if (
        resultado.caminho_screenshot
        is not None
    ):
        print(
            "screenshot="
            f"{resultado.caminho_screenshot}"
        )

    if resultado.caminho_html is not None:
        print(
            f"html={resultado.caminho_html}"
        )


    return (
        0
        if resultado.sucesso
        else 1
    )



if __name__ == "__main__":
    raise SystemExit(main())