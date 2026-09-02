"""Portal web simulado de fornecedores do Capstone."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlencode

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from src.simuladores.dados_fornecedores import (
    STATUS_PEDIDO_VALIDOS,
    PedidoFornecedorSimulado,
    filtrar_pedidos,
    obter_massa_pedidos,
    paginar_pedidos,
)


MODOS_VALIDOS = (
    "normal",
    "lento",
    "erro",
    "vazio",
)

DIRETORIO_ATUAL = Path(
    __file__
).resolve().parent

DIRETORIO_TEMPLATES = (
    DIRETORIO_ATUAL
    / "front/templates"
)

DIRETORIO_STATIC = (
    DIRETORIO_ATUAL
    / "front/static"
)


@dataclass(frozen=True)
class ConfiguracaoPortal:
    """Configuração do portal e dos cenários de sabotagem."""

    modo: str = "normal"
    atraso_segundos: float = 3.0
    tamanho_pagina: int = 5
    host: str = "127.0.0.1"
    porta: int = 8010

    def __post_init__(self) -> None:
        if self.modo not in MODOS_VALIDOS:
            raise ValueError(
                "modo deve ser um de: "
                + ", ".join(MODOS_VALIDOS)
            )

        if self.atraso_segundos < 0:
            raise ValueError(
                "atraso_segundos não pode ser negativo"
            )

        if self.tamanho_pagina <= 0:
            raise ValueError(
                "tamanho_pagina deve ser maior que zero"
            )

        if not self.host.strip():
            raise ValueError(
                "host não pode ser vazio"
            )

        if not 1 <= self.porta <= 65535:
            raise ValueError(
                "porta deve estar entre 1 e 65535"
            )


def configuracao_de_ambiente(
) -> ConfiguracaoPortal:
    """Carrega a configuração por variáveis de ambiente."""

    return ConfiguracaoPortal(
        modo=os.getenv(
            "PORTAL_FORNECEDORES_MODO",
            "normal",
        ),
        atraso_segundos=float(
            os.getenv(
                "PORTAL_FORNECEDORES_ATRASO_SECONDS",
                "3",
            )
        ),
        tamanho_pagina=int(
            os.getenv(
                "PORTAL_FORNECEDORES_TAMANHO_PAGINA",
                "5",
            )
        ),
        host=os.getenv(
            "PORTAL_FORNECEDORES_HOST",
            "127.0.0.1",
        ),
        porta=int(
            os.getenv(
                "PORTAL_FORNECEDORES_PORT",
                "8010",
            )
        ),
    )


def calcular_indicadores(
    pedidos: tuple[
        PedidoFornecedorSimulado,
        ...,
    ],
) -> dict[str, int]:
    """Calcula os indicadores exibidos no portal."""

    return {
        "total": len(pedidos),
        "confirmados": sum(
            pedido.status_pedido
            == "CONFIRMADO"
            for pedido in pedidos
        ),
        "em_transito": sum(
            pedido.status_pedido
            == "EM_TRANSITO"
            for pedido in pedidos
        ),
        "com_atencao": sum(
            pedido.status_pedido
            in {
                "ATRASADO",
                "CANCELADO",
            }
            for pedido in pedidos
        ),
    }


def construir_url_pagina(
    *,
    pagina: int,
    termo: str,
    status: str,
) -> str:
    """Preserva os filtros durante a paginação."""

    parametros: dict[str, str | int] = {
        "pagina": pagina,
    }

    if termo:
        parametros["q"] = termo

    if status:
        parametros["status"] = status

    return "/?" + urlencode(parametros)


def criar_aplicacao(
    configuracao: ConfiguracaoPortal | None = None,
) -> FastAPI:
    """Cria o portal com configuração isolável para os testes."""

    configuracao = (
        configuracao
        or configuracao_de_ambiente()
    )

    aplicacao = FastAPI(
        title="Portal de Fornecedores",
        description=(
            "Aplicação web simulada utilizada "
            "pelo Bot C do Capstone."
        ),
        version="1.0.0",
    )

    aplicacao.mount(
        "/static",
        StaticFiles(
            directory=DIRETORIO_STATIC,
        ),
        name="static",
    )

    templates = Jinja2Templates(
        directory=DIRETORIO_TEMPLATES,
    )

    @aplicacao.get(
        "/health",
        name="health",
    )
    async def health() -> dict[str, object]:
        """Informa se o processo do portal está disponível."""

        portal_disponivel = (
            configuracao.modo != "erro"
        )

        return {
            "servico": "portal_fornecedores",
            "status": (
                "ok"
                if portal_disponivel
                else "degradado"
            ),
            "modo": configuracao.modo,
            "portal_disponivel": (
                portal_disponivel
            ),
        }

    @aplicacao.get(
        "/",
        response_class=HTMLResponse,
        name="listar_pedidos",
    )
    async def listar_pedidos(
        request: Request,
        q: str = Query(
            default="",
            max_length=120,
        ),
        status: str = Query(
            default="",
            max_length=30,
        ),
        pagina: int = Query(
            default=1,
            ge=1,
        ),
    ):
        """Renderiza a consulta visual de pedidos."""

        if configuracao.modo == "erro":
            raise HTTPException(
                status_code=503,
                detail=(
                    "Portal de fornecedores "
                    "temporariamente indisponível"
                ),
            )

        if configuracao.modo == "lento":
            await asyncio.sleep(
                configuracao.atraso_segundos
            )

        status_normalizado = (
            status.strip().upper()
        )

        if (
            status_normalizado
            and status_normalizado
            not in STATUS_PEDIDO_VALIDOS
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Status de pedido inválido: "
                    f"{status_normalizado}"
                ),
            )

        if configuracao.modo == "vazio":
            todos_os_pedidos = ()
        else:
            todos_os_pedidos = (
                obter_massa_pedidos()
            )

        pedidos_filtrados = filtrar_pedidos(
            todos_os_pedidos,
            termo=q,
            status=status_normalizado,
        )

        try:
            pagina_pedidos = paginar_pedidos(
                pedidos_filtrados,
                pagina=pagina,
                tamanho_pagina=(
                    configuracao.tamanho_pagina
                ),
            )
        except ValueError as erro:
            raise HTTPException(
                status_code=404,
                detail=str(erro),
            ) from erro

        url_anterior = construir_url_pagina(
            pagina=max(
                1,
                pagina_pedidos.pagina_atual
                - 1,
            ),
            termo=q,
            status=status_normalizado,
        )

        url_proxima = construir_url_pagina(
            pagina=min(
                pagina_pedidos.total_paginas,
                pagina_pedidos.pagina_atual
                + 1,
            ),
            termo=q,
            status=status_normalizado,
        )

        return templates.TemplateResponse(
            request=request,
            name="portal_fornecedores.html",
            context={
                "pagina": pagina_pedidos,
                "indicadores": (
                    calcular_indicadores(
                        pedidos_filtrados
                    )
                ),
                "termo": q,
                "status_selecionado": (
                    status_normalizado
                ),
                "status_validos": sorted(
                    STATUS_PEDIDO_VALIDOS
                ),
                "modo": configuracao.modo,
                "url_anterior": url_anterior,
                "url_proxima": url_proxima,
            },
        )

    return aplicacao


app = criar_aplicacao()


def construir_parser() -> argparse.ArgumentParser:
    """Cria os argumentos para execução local."""

    configuracao_padrao = (
        configuracao_de_ambiente()
    )

    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "--modo",
        choices=MODOS_VALIDOS,
        default=configuracao_padrao.modo,
    )

    parser.add_argument(
        "--atraso-segundos",
        type=float,
        default=(
            configuracao_padrao
            .atraso_segundos
        ),
    )

    parser.add_argument(
        "--tamanho-pagina",
        type=int,
        default=(
            configuracao_padrao
            .tamanho_pagina
        ),
    )

    parser.add_argument(
        "--host",
        default=configuracao_padrao.host,
    )

    parser.add_argument(
        "--porta",
        type=int,
        default=configuracao_padrao.porta,
    )

    return parser


def main(
    argv: list[str] | None = None,
) -> int:
    """Inicia o portal localmente."""

    argumentos = (
        construir_parser()
        .parse_args(argv)
    )

    configuracao = ConfiguracaoPortal(
        modo=argumentos.modo,
        atraso_segundos=(
            argumentos.atraso_segundos
        ),
        tamanho_pagina=(
            argumentos.tamanho_pagina
        ),
        host=argumentos.host,
        porta=argumentos.porta,
    )

    aplicacao = criar_aplicacao(
        configuracao
    )

    uvicorn.run(
        aplicacao,
        host=configuracao.host,
        port=configuracao.porta,
        log_level="info",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())