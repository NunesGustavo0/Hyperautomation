"""Integração do Bot B com uma porta visual controlada."""

from pathlib import Path

import pytest

from src.bots.bot_coleta_desktop import (
    ConfiguracaoColetaDesktop,
    FalhaColetaDesktopError,
    coletar_registros_visuais,
    executar_bot_coleta_desktop,
    interpretar_pagina_tsv,
)
from src.contratos_capstone import (
    ArtefatoEstoqueDesktop,
    EstadoExecucao,
)


CABECALHO = (
    "lote_id\tproduto\tquantidade_disponivel\t"
    "localizacao\tstatus_estoque"
)

PAGINA_1 = "\n".join(
    (
        CABECALHO,
        "LOTE-001\tSensor de temperatura\t20\tA-01\tDISPONIVEL",
        "LOTE-002\tAtuador pneumático\t8\tA-02\tESTOQUE_BAIXO",
    )
)

PAGINA_2 = "\n".join(
    (
        CABECALHO,
        "LOTE-003\tVálvula de controle\t0\tA-03\tINDISPONIVEL",
    )
)


class AutomacaoVisualControlada:
    """Dublê que representa somente as interações disponíveis na tela."""

    def __init__(
        self,
        paginas=(),
        *,
        falhas_localizacao: int = 0,
    ) -> None:
        self.paginas = tuple(paginas)
        self.falhas_localizacao = falhas_localizacao
        self.indice = 0
        self.localizacoes = 0
        self.screenshots: list[Path] = []

    def localizar_aplicacao(self, timeout_ms: int) -> bool:
        assert timeout_ms > 0
        self.localizacoes += 1
        if self.localizacoes <= self.falhas_localizacao:
            return False
        self.indice = 0
        return True

    def copiar_pagina_visivel(self) -> str:
        if not self.paginas:
            raise RuntimeError("desktop indisponível")
        return self.paginas[self.indice]

    def avancar_pagina(self, timeout_ms: int) -> bool:
        assert timeout_ms > 0
        if self.indice + 1 >= len(self.paginas):
            return False
        self.indice += 1
        return True

    def capturar_screenshot(self, caminho: Path) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(b"evidencia-controlada")
        self.screenshots.append(caminho)


def criar_configuracao(tmp_path, **alteracoes):
    valores = {
        "max_tentativas": 3,
        "timeout_seconds": 2,
        "backoff_seconds": 0.25,
        "max_paginas": 10,
        "caminho_artefato": tmp_path / "estoque_desktop.json",
        "diretorio_screenshots": tmp_path / "screenshots",
    }
    valores.update(alteracoes)
    return ConfiguracaoColetaDesktop(**valores)


def test_bot_b_coleta_paginas_e_gera_artefato_contratual(tmp_path):
    automacao = AutomacaoVisualControlada((PAGINA_1, PAGINA_2))
    configuracao = criar_configuracao(tmp_path)

    resultado = executar_bot_coleta_desktop(
        automacao,
        execution_id="exec-001",
        correlation_id="corr-001",
        task_id="task-b-001",
        predecessor="bot-a-entrada",
        predecessor_task_id="task-a-001",
        resultado_predecessor="fontes_liberadas",
        configuracao=configuracao,
    )

    assert resultado.sucesso is True
    assert resultado.estado is EstadoExecucao.CONCLUIDO
    assert resultado.tentativas == 1
    assert resultado.total_registros == 3
    assert resultado.caminho_artefato.is_file()

    artefato = ArtefatoEstoqueDesktop.de_json(
        resultado.caminho_artefato.read_text(encoding="utf-8")
    )
    assert artefato.total_registros == 3
    assert artefato.auditoria.execution_id == "exec-001"
    assert artefato.auditoria.correlation_id == "corr-001"
    assert artefato.auditoria.bot_id == "bot-b-coleta-desktop"
    assert artefato.auditoria.predecessor_task_id == "task-a-001"
    assert artefato.registros[2].lote_id == "LOTE-003"


def test_falha_transitoria_aciona_retry_backoff_e_screenshot(tmp_path):
    automacao = AutomacaoVisualControlada(
        (PAGINA_1,),
        falhas_localizacao=1,
    )
    pausas: list[float] = []

    resultado = executar_bot_coleta_desktop(
        automacao,
        execution_id="exec-002",
        correlation_id="corr-002",
        task_id="task-b-002",
        configuracao=criar_configuracao(tmp_path),
        sleeper=pausas.append,
    )

    assert resultado.sucesso is True
    assert resultado.tentativas == 2
    assert pausas == [0.25]
    assert len(automacao.screenshots) == 1
    assert automacao.screenshots[0].is_file()


def test_desktop_indisponivel_falha_sem_deixar_lote_bloqueado(tmp_path):
    automacao = AutomacaoVisualControlada(
        falhas_localizacao=10,
    )
    pausas: list[float] = []

    resultado = executar_bot_coleta_desktop(
        automacao,
        execution_id="exec-003",
        correlation_id="corr-003",
        task_id="task-b-003",
        configuracao=criar_configuracao(tmp_path),
        sleeper=pausas.append,
    )

    assert resultado.sucesso is False
    assert resultado.estado is EstadoExecucao.FALHOU
    assert resultado.tentativas == 3
    assert resultado.total_registros == 0
    assert "não encontrada" in resultado.erro
    assert pausas == [0.25, 0.5]
    assert len(automacao.screenshots) == 3

    artefato = ArtefatoEstoqueDesktop.de_json(
        resultado.caminho_artefato.read_text(encoding="utf-8")
    )
    assert artefato.auditoria.estado is EstadoExecucao.FALHOU
    assert artefato.registros == ()


def test_parser_rejeita_conteudo_que_nao_veio_no_formato_visual():
    with pytest.raises(
        FalhaColetaDesktopError,
        match="cabeçalho visual inválido",
    ):
        interpretar_pagina_tsv(
            "lote;produto;quantidade\nLOTE-001;Sensor;2"
        )


def test_navegacao_rejeita_repeticao_da_mesma_pagina(tmp_path):
    automacao = AutomacaoVisualControlada((PAGINA_1, PAGINA_1))

    with pytest.raises(
        FalhaColetaDesktopError,
        match="página já coletada",
    ):
        coletar_registros_visuais(
            automacao,
            criar_configuracao(tmp_path),
        )

