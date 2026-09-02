"""Page Object do portal simulado de fornecedores."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)


class FalhaPortalFornecedoresError(
    RuntimeError
):
    """Falha controlada na interação com o portal."""


@dataclass(frozen=True)
class LinhaPedidoPortal:
    """Representa uma linha extraída visualmente."""

    pedido_id: str
    lote_id: str
    fornecedor: str
    produto: str
    quantidade_pedida: int
    status_pedido: str
    previsao_entrega: str | None


class PortalFornecedoresPage:
    """Ações e seletores do portal de fornecedores."""

    SELETOR_TITULO = (
        '[data-testid="titulo-portal"]'
    )

    SELETOR_TABELA = (
        '[data-testid="tabela-pedidos"]'
    )

    SELETOR_LINHAS = (
        '[data-testid="pedido-row"]'
    )

    SELETOR_SEM_REGISTROS = (
        '[data-testid="sem-registros"]'
    )

    SELETOR_PROXIMA_PAGINA = (
        '[data-testid="proxima-pagina"]'
    )

    SELETOR_PAGINA_ANTERIOR = (
        '[data-testid="pagina-anterior"]'
    )

    SELETOR_INFORMACAO_PAGINA = (
        '[data-testid="informacao-pagina"]'
    )

    SELETOR_CAMPO_BUSCA = (
        '[data-testid="campo-busca"]'
    )

    SELETOR_FILTRO_STATUS = (
        '[data-testid="filtro-status"]'
    )

    SELETOR_BOTAO_BUSCAR = (
        '[data-testid="botao-buscar"]'
    )

    SELETOR_BOTAO_LIMPAR = (
        '[data-testid="botao-limpar"]'
    )

    def __init__(
        self,
        page: Page,
    ) -> None:
        self._page = page

    def abrir(
        self,
        url: str,
        timeout_ms: int,
    ) -> None:
        """Abre e valida o portal."""

        self._page.set_default_timeout(
            timeout_ms
        )

        try:
            resposta = self._page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError as erro:
            raise FalhaPortalFornecedoresError(
                "timeout ao abrir o portal "
                "de fornecedores"
            ) from erro

        if resposta is None:
            raise FalhaPortalFornecedoresError(
                "o portal não retornou "
                "uma resposta HTTP"
            )

        if resposta.status >= 400:
            raise FalhaPortalFornecedoresError(
                "o portal respondeu com "
                f"status HTTP {resposta.status}"
            )

        self.aguardar_carregamento(
            timeout_ms
        )

    def aguardar_carregamento(
        self,
        timeout_ms: int,
    ) -> None:
        """Espera os elementos essenciais."""

        try:
            self._page.locator(
                self.SELETOR_TITULO
            ).wait_for(
                state="visible",
                timeout=timeout_ms,
            )

            self._page.locator(
                self.SELETOR_TABELA
            ).wait_for(
                state="visible",
                timeout=timeout_ms,
            )

        except PlaywrightTimeoutError as erro:
            raise FalhaPortalFornecedoresError(
                "o portal abriu, mas seus "
                "elementos não ficaram disponíveis"
            ) from erro

    @staticmethod
    def _texto_coluna(
        linha,
        test_id: str,
        *,
        obrigatorio: bool = True,
    ) -> str:
        """Obtém o texto de uma coluna da linha."""

        seletor = (
            f'[data-testid="{test_id}"]'
        )

        coluna = linha.locator(seletor)

        if coluna.count() != 1:
            raise FalhaPortalFornecedoresError(
                "coluna não encontrada ou "
                f"duplicada: {test_id}"
            )

        valor = coluna.inner_text().strip()

        if obrigatorio and not valor:
            raise FalhaPortalFornecedoresError(
                "coluna obrigatória vazia: "
                f"{test_id}"
            )

        return valor

    def esta_sem_registros(self) -> bool:
        """Informa se o portal está no estado vazio."""

        elemento = self._page.locator(
            self.SELETOR_SEM_REGISTROS
        )

        return (
            elemento.count() > 0
            and elemento.is_visible()
        )

    def extrair_pedidos(
        self,
    ) -> tuple[LinhaPedidoPortal, ...]:
        """Extrai todos os pedidos da página visível."""

        linhas = self._page.locator(
            self.SELETOR_LINHAS
        )

        quantidade_linhas = linhas.count()

        if quantidade_linhas == 0:
            if self.esta_sem_registros():
                return ()

            raise FalhaPortalFornecedoresError(
                "a tabela não apresentou pedidos "
                "nem o estado sem registros"
            )

        pedidos: list[
            LinhaPedidoPortal
        ] = []

        for indice in range(
            quantidade_linhas
        ):
            linha = linhas.nth(indice)

            quantidade_texto = (
                self._texto_coluna(
                    linha,
                    "quantidade-pedida",
                )
            )

            try:
                quantidade = int(
                    quantidade_texto
                )
            except ValueError as erro:
                raise (
                    FalhaPortalFornecedoresError(
                        "quantidade inválida no "
                        "pedido da linha "
                        f"{indice + 1}: "
                        f"{quantidade_texto!r}"
                    )
                ) from erro

            previsao = self._texto_coluna(
                linha,
                "previsao-entrega",
                obrigatorio=False,
            )

            if previsao in {
                "",
                "—",
                "-",
            }:
                previsao = None

            status = self._texto_coluna(
                linha,
                "status-pedido",
            )

            status = (
                status
                .strip()
                .upper()
                .replace(" ", "_")
            )

            pedidos.append(
                LinhaPedidoPortal(
                    pedido_id=(
                        self._texto_coluna(
                            linha,
                            "pedido-id",
                        )
                    ),
                    lote_id=(
                        self._texto_coluna(
                            linha,
                            "lote-id",
                        )
                    ),
                    fornecedor=(
                        self._texto_coluna(
                            linha,
                            "fornecedor",
                        )
                    ),
                    produto=(
                        self._texto_coluna(
                            linha,
                            "produto",
                        )
                    ),
                    quantidade_pedida=(
                        quantidade
                    ),
                    status_pedido=status,
                    previsao_entrega=previsao,
                )
            )

        return tuple(pedidos)

    def possui_proxima_pagina(
        self,
    ) -> bool:
        """Verifica se o botão Próxima está disponível."""

        botao = self._page.locator(
            self.SELETOR_PROXIMA_PAGINA
        )

        return (
            botao.count() == 1
            and botao.is_visible()
        )

    def avancar_pagina(
        self,
        timeout_ms: int,
    ) -> bool:
        """Navega para a próxima página."""

        if not self.possui_proxima_pagina():
            return False

        botao = self._page.locator(
            self.SELETOR_PROXIMA_PAGINA
        )

        try:
            botao.click(
                timeout=timeout_ms
            )

            self._page.wait_for_load_state(
                "domcontentloaded",
                timeout=timeout_ms,
            )

            self.aguardar_carregamento(
                timeout_ms
            )

        except PlaywrightTimeoutError as erro:
            raise FalhaPortalFornecedoresError(
                "timeout ao navegar para "
                "a próxima página"
            ) from erro

        return True

    def informacao_pagina(self) -> str:
        """Retorna o texto da paginação."""

        elemento = self._page.locator(
            self.SELETOR_INFORMACAO_PAGINA
        )

        if elemento.count() != 1:
            raise FalhaPortalFornecedoresError(
                "informação da página "
                "não encontrada"
            )

        return elemento.inner_text().strip()

    def aplicar_filtros(
        self,
        *,
        termo: str = "",
        status: str = "",
        timeout_ms: int = 5_000,
    ) -> None:
        """Preenche e aplica os filtros do portal."""

        self._page.locator(
            self.SELETOR_CAMPO_BUSCA
        ).fill(termo)

        self._page.locator(
            self.SELETOR_FILTRO_STATUS
        ).select_option(
            status.strip().upper()
        )

        try:
            self._page.locator(
                self.SELETOR_BOTAO_BUSCAR
            ).click(
                timeout=timeout_ms
            )

            self._page.wait_for_load_state(
                "domcontentloaded",
                timeout=timeout_ms,
            )

            self.aguardar_carregamento(
                timeout_ms
            )

        except PlaywrightTimeoutError as erro:
            raise FalhaPortalFornecedoresError(
                "timeout ao aplicar filtros"
            ) from erro

    def limpar_filtros(
        self,
        timeout_ms: int = 5_000,
    ) -> None:
        """Limpa todos os filtros."""

        try:
            self._page.locator(
                self.SELETOR_BOTAO_LIMPAR
            ).click(
                timeout=timeout_ms
            )

            self._page.wait_for_load_state(
                "domcontentloaded",
                timeout=timeout_ms,
            )

            self.aguardar_carregamento(
                timeout_ms
            )

        except PlaywrightTimeoutError as erro:
            raise FalhaPortalFornecedoresError(
                "timeout ao limpar filtros"
            ) from erro

    def capturar_screenshot(
        self,
        caminho: Path,
    ) -> None:
        """Captura toda a página."""

        caminho = Path(caminho)

        caminho.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._page.screenshot(
            path=str(caminho),
            full_page=True,
        )

    def salvar_html(
        self,
        caminho: Path,
    ) -> None:
        """Salva o HTML atual para auditoria."""

        caminho = Path(caminho)

        caminho.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        caminho.write_text(
            self._page.content(),
            encoding="utf-8",
        )