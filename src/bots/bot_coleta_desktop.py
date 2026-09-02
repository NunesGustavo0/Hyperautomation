"""Bot B: coleta visual de estoque na aplicação desktop simulada."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import sys
import time
from typing import Callable, Protocol, Sequence

from src.contratos_capstone import (
    ArtefatoEstoqueDesktop,
    EnvelopeAuditoria,
    EstadoExecucao,
    RegistroEstoqueDesktop,
)


LOGGER = logging.getLogger("botcity_permorfer")
BOT_ID = "bot-b-coleta-desktop"


class FalhaColetaDesktopError(RuntimeError):
    """Indica falha controlada durante a automação visual."""


class PortaAutomacaoDesktop(Protocol):
    """Operações visuais necessárias, independentemente da biblioteca."""

    def localizar_aplicacao(self, timeout_ms: int) -> bool:
        """Localiza visualmente a aplicação de estoque."""

    def copiar_pagina_visivel(self) -> str:
        """Copia pela interface os registros apresentados na página atual."""

    def avancar_pagina(self, timeout_ms: int) -> bool:
        """Clica em Próxima; retorna falso quando não existe próxima página."""

    def capturar_screenshot(self, caminho: Path) -> None:
        """Salva uma evidência visual da tela atual."""


@dataclass(frozen=True)
class ConfiguracaoColetaDesktop:
    """Limites de resiliência e caminhos utilizados pelo Bot B."""

    max_tentativas: int = 3
    timeout_seconds: float = 15.0
    backoff_seconds: float = 1.0
    max_paginas: int = 20
    caminho_artefato: Path = Path(
        "data/output/estoque_desktop.json"
    )
    diretorio_screenshots: Path = Path("screenshots/bot_desktop")

    def __post_init__(self) -> None:
        if self.max_tentativas <= 0:
            raise ValueError("max_tentativas deve ser maior que zero")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds deve ser maior que zero")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds não pode ser negativo")
        if self.max_paginas <= 0:
            raise ValueError("max_paginas deve ser maior que zero")


@dataclass(frozen=True)
class ResultadoColetaDesktop:
    """Resultado controlado retornado ao orquestrador."""

    sucesso: bool
    estado: EstadoExecucao
    tentativas: int
    total_registros: int
    caminho_artefato: Path
    caminho_screenshot: Path | None = None
    erro: str | None = None


def interpretar_pagina_tsv(
    conteudo: str,
) -> tuple[RegistroEstoqueDesktop, ...]:
    """Converte o texto copiado da tela no contrato da Issue 03."""

    linhas = [
        linha.strip()
        for linha in conteudo.splitlines()
        if linha.strip()
    ]
    if not linhas:
        raise FalhaColetaDesktopError(
            "a página visível não forneceu registros"
        )

    cabecalho_esperado = (
        "lote_id",
        "produto",
        "quantidade_disponivel",
        "localizacao",
        "status_estoque",
    )
    cabecalho = tuple(
        coluna.strip() for coluna in linhas[0].split("\t")
    )
    if cabecalho != cabecalho_esperado:
        raise FalhaColetaDesktopError(
            "cabeçalho visual inválido; esperado: "
            + " | ".join(cabecalho_esperado)
        )

    registros: list[RegistroEstoqueDesktop] = []
    for numero_linha, linha in enumerate(linhas[1:], start=2):
        colunas = [coluna.strip() for coluna in linha.split("\t")]
        if len(colunas) != len(cabecalho_esperado):
            raise FalhaColetaDesktopError(
                f"linha visual {numero_linha} possui "
                f"{len(colunas)} coluna(s); esperadas 5"
            )

        try:
            quantidade = int(colunas[2])
        except ValueError as erro:
            raise FalhaColetaDesktopError(
                f"quantidade inválida na linha visual {numero_linha}: "
                f"{colunas[2]!r}"
            ) from erro

        registros.append(
            RegistroEstoqueDesktop(
                lote_id=colunas[0],
                produto=colunas[1],
                quantidade_disponivel=quantidade,
                localizacao=colunas[3],
                status_estoque=colunas[4],
            )
        )

    if not registros:
        raise FalhaColetaDesktopError(
            "a página visível contém somente o cabeçalho"
        )

    return tuple(registros)


def coletar_registros_visuais(
    automacao: PortaAutomacaoDesktop,
    configuracao: ConfiguracaoColetaDesktop,
    *,
    clock: Callable[[], float] = time.monotonic,
    logger: logging.Logger | None = None,
) -> tuple[RegistroEstoqueDesktop, ...]:
    """Percorre visualmente todas as páginas disponíveis."""

    logger = logger or LOGGER
    inicio = clock()
    timeout_ms = max(1, int(configuracao.timeout_seconds * 1_000))

    if not automacao.localizar_aplicacao(timeout_ms):
        raise FalhaColetaDesktopError(
            "aplicação desktop não encontrada dentro do timeout"
        )

    registros_por_lote: dict[str, RegistroEstoqueDesktop] = {}
    paginas_vistas: set[tuple[tuple[str, object], ...]] = set()

    for numero_pagina in range(1, configuracao.max_paginas + 1):
        if clock() - inicio > configuracao.timeout_seconds:
            raise FalhaColetaDesktopError(
                "timeout durante a navegação das páginas"
            )

        pagina = interpretar_pagina_tsv(
            automacao.copiar_pagina_visivel()
        )
        assinatura = tuple(
            (
                registro.lote_id,
                registro.quantidade_disponivel,
            )
            for registro in pagina
        )

        if assinatura in paginas_vistas:
            raise FalhaColetaDesktopError(
                "a navegação retornou uma página já coletada"
            )
        paginas_vistas.add(assinatura)

        for registro in pagina:
            anterior = registros_por_lote.get(registro.lote_id)
            if anterior is not None and anterior != registro:
                raise FalhaColetaDesktopError(
                    f"lote {registro.lote_id!r} apareceu com dados diferentes"
                )
            registros_por_lote[registro.lote_id] = registro

        logger.info(
            "Página %d coletada: %d registro(s); acumulado=%d",
            numero_pagina,
            len(pagina),
            len(registros_por_lote),
            extra={
                "evento": "coleta_desktop_pagina_coletada",
                "pagina": numero_pagina,
                "registros_pagina": len(pagina),
                "registros_acumulados": len(registros_por_lote),
            },
        )

        restante_ms = max(
            1,
            int(
                (
                    configuracao.timeout_seconds
                    - (clock() - inicio)
                )
                * 1_000
            ),
        )
        if not automacao.avancar_pagina(restante_ms):
            logger.info(
                "Navegação finalizada: %d página(s); %d registro(s)",
                numero_pagina,
                len(registros_por_lote),
                extra={
                    "evento": "coleta_desktop_navegacao_finalizada",
                    "total_paginas": numero_pagina,
                    "total_registros": len(registros_por_lote),
                },
            )
            return tuple(registros_por_lote.values())

    raise FalhaColetaDesktopError(
        "limite de páginas atingido antes do fim da coleta"
    )


def _criar_artefato(
    *,
    execution_id: str,
    correlation_id: str,
    task_id: str,
    estado: EstadoExecucao,
    registros: Sequence[RegistroEstoqueDesktop],
    predecessor: str | None,
    predecessor_task_id: str | None,
    resultado_predecessor: str | None,
) -> ArtefatoEstoqueDesktop:
    return ArtefatoEstoqueDesktop(
        auditoria=EnvelopeAuditoria(
            execution_id=execution_id,
            correlation_id=correlation_id,
            bot_id=BOT_ID,
            task_id=task_id,
            estado=estado,
            predecessor=predecessor,
            predecessor_task_id=predecessor_task_id,
            resultado_predecessor=resultado_predecessor,
        ),
        registros=tuple(registros),
    )


def salvar_artefato(
    artefato: ArtefatoEstoqueDesktop,
    caminho: Path,
) -> Path:
    """Persiste o JSON de forma atômica para evitar arquivo incompleto."""

    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(artefato.para_json(), encoding="utf-8")
    temporario.replace(caminho)
    return caminho


def _capturar_falha_segura(
    automacao: PortaAutomacaoDesktop,
    caminho: Path,
    logger: logging.Logger,
) -> Path | None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    try:
        automacao.capturar_screenshot(caminho)
    except Exception as erro:  # A evidência não pode derrubar o pipeline.
        logger.warning(
            "screenshot_coleta_desktop_falhou",
            extra={
                "evento": "screenshot_coleta_desktop_falhou",
                "erro": str(erro),
            },
        )
        return None
    return caminho


def executar_bot_coleta_desktop(
    automacao: PortaAutomacaoDesktop,
    *,
    execution_id: str,
    correlation_id: str,
    task_id: str,
    configuracao: ConfiguracaoColetaDesktop | None = None,
    predecessor: str | None = None,
    predecessor_task_id: str | None = None,
    resultado_predecessor: str | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    logger: logging.Logger | None = None,
) -> ResultadoColetaDesktop:
    """Executa a coleta com tentativas limitadas e falha controlada."""

    configuracao = configuracao or ConfiguracaoColetaDesktop()
    logger = logger or LOGGER
    ultimo_erro: str | None = None
    ultimo_screenshot: Path | None = None

    for tentativa in range(1, configuracao.max_tentativas + 1):
        logger.info(
            "coleta_desktop_tentativa_iniciada",
            extra={
                "evento": "coleta_desktop_tentativa_iniciada",
                "bot_id": BOT_ID,
                "execution_id": execution_id,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "tentativa": tentativa,
            },
        )

        try:
            registros = coletar_registros_visuais(
                automacao,
                configuracao,
                logger=logger,
            )
            artefato = _criar_artefato(
                execution_id=execution_id,
                correlation_id=correlation_id,
                task_id=task_id,
                estado=EstadoExecucao.CONCLUIDO,
                registros=registros,
                predecessor=predecessor,
                predecessor_task_id=predecessor_task_id,
                resultado_predecessor=resultado_predecessor,
            )
            caminho = salvar_artefato(
                artefato,
                configuracao.caminho_artefato,
            )

            logger.info(
                "coleta_desktop_concluida",
                extra={
                    "evento": "coleta_desktop_concluida",
                    "bot_id": BOT_ID,
                    "execution_id": execution_id,
                    "correlation_id": correlation_id,
                    "task_id": task_id,
                    "tentativas": tentativa,
                    "total_registros": len(registros),
                    "caminho_artefato": str(caminho),
                },
            )
            return ResultadoColetaDesktop(
                sucesso=True,
                estado=EstadoExecucao.CONCLUIDO,
                tentativas=tentativa,
                total_registros=len(registros),
                caminho_artefato=caminho,
            )

        except Exception as erro:
            ultimo_erro = str(erro)
            caminho_screenshot = (
                configuracao.diretorio_screenshots
                / f"falha_tentativa_{tentativa}.png"
            )
            ultimo_screenshot = _capturar_falha_segura(
                automacao,
                caminho_screenshot,
                logger,
            )

            logger.warning(
                "coleta_desktop_tentativa_falhou",
                extra={
                    "evento": "coleta_desktop_tentativa_falhou",
                    "bot_id": BOT_ID,
                    "execution_id": execution_id,
                    "correlation_id": correlation_id,
                    "task_id": task_id,
                    "tentativa": tentativa,
                    "erro": ultimo_erro,
                    "screenshot": (
                        str(ultimo_screenshot)
                        if ultimo_screenshot is not None
                        else None
                    ),
                },
            )

            if tentativa < configuracao.max_tentativas:
                sleeper(configuracao.backoff_seconds * tentativa)

    artefato_falha = _criar_artefato(
        execution_id=execution_id,
        correlation_id=correlation_id,
        task_id=task_id,
        estado=EstadoExecucao.FALHOU,
        registros=(),
        predecessor=predecessor,
        predecessor_task_id=predecessor_task_id,
        resultado_predecessor=resultado_predecessor,
    )
    caminho = salvar_artefato(
        artefato_falha,
        configuracao.caminho_artefato,
    )

    logger.error(
        "coleta_desktop_falhou",
        extra={
            "evento": "coleta_desktop_falhou",
            "bot_id": BOT_ID,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "tentativas": configuracao.max_tentativas,
            "erro": ultimo_erro,
            "caminho_artefato": str(caminho),
        },
    )
    return ResultadoColetaDesktop(
        sucesso=False,
        estado=EstadoExecucao.FALHOU,
        tentativas=configuracao.max_tentativas,
        total_registros=0,
        caminho_artefato=caminho,
        caminho_screenshot=ultimo_screenshot,
        erro=ultimo_erro,
    )


class AdaptadorBotCityDesktop:
    """Implementação real baseada no BotCity Framework Core."""

    def __init__(
        self,
        *,
        diretorio_recursos: Path = Path(
            "resources/capstone_desktop"
        ),
        matching: float = 0.90,
    ) -> None:
        if sys.platform.startswith("linux") and not os.getenv("DISPLAY"):
            raise RuntimeError(
                "Sessão gráfica indisponível: "
                "a variável DISPLAY não está definida. "
                "Execute o Bot B em um terminal aberto "
                "na sessão gráfica do usuário."
            )

        try:
            from botcity.core import DesktopBot
        except ModuleNotFoundError as erro:
            if erro.name and erro.name.startswith("botcity"):
                raise RuntimeError(
                    "botcity-framework-core não está instalado"
                ) from erro
            raise RuntimeError(
                "Uma dependência do BotCity Desktop "
                f"não foi encontrada: {erro}"
            ) from erro
        except ImportError as erro:
            raise RuntimeError(
                "BotCity Desktop está instalado, "
                "mas não conseguiu acessar a sessão gráfica. "
                "Confira DISPLAY e XAUTHORITY. "
                f"Detalhe: {erro}"
            ) from erro

        self._bot = DesktopBot()
        self._matching = matching
        self._registrar_imagem(
            "aplicacao_estoque",
            diretorio_recursos / "aplicacao_estoque.png",
        )
        self._registrar_imagem(
            "botao_proximo",
            diretorio_recursos / "botao_proximo.png",
        )

    def _registrar_imagem(self, rotulo: str, caminho: Path) -> None:
        if not caminho.is_file():
            raise FileNotFoundError(
                f"imagem de reconhecimento não encontrada: {caminho}"
            )
        self._bot.add_image(rotulo, str(caminho))

    def localizar_aplicacao(self, timeout_ms: int) -> bool:
        encontrada = self._bot.find(
            "aplicacao_estoque",
            matching=self._matching,
            waiting_time=timeout_ms,
        )

        if not encontrada:
            return False

        # Entrega o foco do teclado ao simulador antes do Ctrl+E.
        self._bot.click(wait_after=500)
        return True

    def copiar_pagina_visivel(self) -> str:
        marcador = "__BOT_B_AGUARDANDO_PAGINA__"
        self._bot.copy_to_clipboard(marcador)
        self._bot.control_key("e", wait=300)
        conteudo = self._bot.get_clipboard()
        if not conteudo or conteudo == marcador:
            raise FalhaColetaDesktopError(
                "a interface não copiou a página visível"
            )
        return conteudo

    def avancar_pagina(self, timeout_ms: int) -> bool:
        encontrado = self._bot.find(
            "botao_proximo",
            matching=self._matching,
            waiting_time=min(timeout_ms, 1_000),
        )
        if not encontrado:
            return False
        self._bot.click(wait_after=400)
        return True

    def capturar_screenshot(self, caminho: Path) -> None:
        self._bot.get_screenshot(filepath=str(caminho))


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-id", default="exec-local-desktop")
    parser.add_argument("--correlation-id", default="corr-local-desktop")
    parser.add_argument("--task-id", default="task-local-desktop")
    parser.add_argument(
        "--saida",
        type=Path,
        default=Path("data/output/estoque_desktop.json"),
    )
    parser.add_argument(
        "--recursos",
        type=Path,
        default=Path("resources/capstone_desktop"),
    )
    parser.add_argument("--tentativas", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--backoff", type=float, default=1.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    LOGGER.setLevel(logging.INFO)

    args = construir_parser().parse_args(argv)
    configuracao = ConfiguracaoColetaDesktop(
        max_tentativas=args.tentativas,
        timeout_seconds=args.timeout,
        backoff_seconds=args.backoff,
        caminho_artefato=args.saida,
    )
    automacao = AdaptadorBotCityDesktop(
        diretorio_recursos=args.recursos,
    )
    resultado = executar_bot_coleta_desktop(
        automacao,
        execution_id=args.execution_id,
        correlation_id=args.correlation_id,
        task_id=args.task_id,
        configuracao=configuracao,
    )
    print(
        f"estado={resultado.estado.value} "
        f"registros={resultado.total_registros} "
        f"artefato={resultado.caminho_artefato}"
    )
    if resultado.erro is not None:
        print(f"erro={resultado.erro}")
    if resultado.caminho_screenshot is not None:
        print(f"screenshot={resultado.caminho_screenshot}")
    return 0 if resultado.sucesso else 1


if __name__ == "__main__":
    raise SystemExit(main())
