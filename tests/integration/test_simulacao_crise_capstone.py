"""Seis cenários de crise do capstone, sem dependências externas reais."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from src.bots.bot_coleta_desktop import (
    ConfiguracaoColetaDesktop,
    executar_bot_coleta_desktop,
)
from src.classificador_divergencia import ClassificadorDivergencia
from src.dead_letter import RepositorioDeadLetter, processar_lote_com_dead_letter
from src.decisao_hibrida import MotivoFallback
from src.ml_client import MLClient
from src.orchestrator import criar_tarefa_sucessora
from src.politicas_resiliencia import ErroDeItem
from src.sistema_alertas import Alerta, ResultadoAlerta, Severidade, SistemaAlertas
from src.wait_for_predecessor import TimeoutDependenciaError, wait_for_predecessor


pytestmark = pytest.mark.integration

EXECUTION_ID = "exec-crise-capstone-001"
CORRELATION_ID = "corr-crise-capstone-001"


def _eventos(logger: Mock) -> list[str]:
    return [
        chamada.kwargs["extra"]["evento"]
        for metodo in (logger.info, logger.warning, logger.error)
        for chamada in metodo.call_args_list
    ]


def _salvar_evidencia(tmp_path: Path, cenario: str, **resultado) -> dict:
    evidencia = {
        "cenario": cenario,
        "execution_id": EXECUTION_ID,
        "correlation_id": CORRELATION_ID,
        **resultado,
    }
    caminho = tmp_path / f"evidencia_{cenario}.json"
    caminho.write_text(
        json.dumps(evidencia, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return json.loads(caminho.read_text(encoding="utf-8"))


class DesktopIndisponivel:
    def localizar_aplicacao(self, timeout_ms: int) -> bool:
        return False

    def copiar_pagina_visivel(self) -> str:
        raise AssertionError("não deve copiar uma aplicação indisponível")

    def avancar_pagina(self, timeout_ms: int) -> bool:
        return False

    def capturar_screenshot(self, caminho: Path) -> None:
        caminho.write_bytes(b"evidencia-desktop-simulada")


class CanalFake:
    def __init__(self, nome: str, sucesso: bool, erro: str | None = None):
        self.nome = nome
        self.sucesso = sucesso
        self.erro = erro
        self.recebidos: list[Alerta] = []

    def enviar(self, alerta: Alerta) -> ResultadoAlerta:
        self.recebidos.append(alerta)
        return ResultadoAlerta(
            sucesso=self.sucesso,
            canal=self.nome,
            erro=self.erro,
        )


def test_cenario_1_bot_desktop_indisponivel_falha_controlada(tmp_path):
    logger = Mock()
    resultado = executar_bot_coleta_desktop(
        DesktopIndisponivel(),
        execution_id=EXECUTION_ID,
        correlation_id=CORRELATION_ID,
        task_id="task-desktop-crise",
        configuracao=ConfiguracaoColetaDesktop(
            max_tentativas=2,
            timeout_seconds=0.01,
            backoff_seconds=0,
            caminho_artefato=tmp_path / "desktop.json",
            diretorio_screenshots=tmp_path / "screenshots",
        ),
        sleeper=Mock(),
        logger=logger,
    )

    assert resultado.sucesso is False
    assert resultado.tentativas == 2
    assert resultado.caminho_artefato.is_file()
    assert resultado.caminho_screenshot.is_file()
    assert "coleta_desktop_falhou" in _eventos(logger)
    evidencia = _salvar_evidencia(
        tmp_path,
        "desktop_indisponivel",
        fallback="falha_controlada_com_artefato",
        lote_interrompido=False,
        tentativas=resultado.tentativas,
    )
    assert evidencia["fallback"] == "falha_controlada_com_artefato"


def test_cenario_2_dependencia_acima_timeout_encerra_espera(tmp_path):
    maestro = Mock()
    maestro.get_task.return_value = SimpleNamespace(status="RUNNING")
    logger = Mock()
    tempos = iter((0.0, 2.0))

    with pytest.raises(TimeoutDependenciaError):
        wait_for_predecessor(
            maestro,
            "task-predecessora-crise",
            timeout_seconds=1,
            poll_interval_seconds=0.1,
            clock=lambda: next(tempos),
            sleeper=Mock(),
            logger=logger,
        )

    assert maestro.get_task.call_count == 1
    assert "dependencia_timeout" in _eventos(logger)
    evidencia = _salvar_evidencia(
        tmp_path,
        "dependencia_timeout",
        fallback="timeout_controlado",
        alerta="dependencia_timeout",
    )
    assert evidencia["fallback"] == "timeout_controlado"


def test_cenario_3_servico_ml_fora_ar_processa_todo_lote_com_fallback(tmp_path):
    session = Mock()
    session.post.side_effect = requests.ConnectionError("ML offline")
    classificador = ClassificadorDivergencia(
        MLClient(session=session, timeout=0.01, limite_falhas=10),
        ml_enabled=True,
    )
    observacoes = ("Código incorreto", "Peça ausente", "Registro duplicado")

    decisoes = [classificador.classificar(item) for item in observacoes]

    assert len(decisoes) == len(observacoes)
    assert all(
        decisao.motivo_fallback is MotivoFallback.SERVICO_INDISPONIVEL
        for decisao in decisoes
    )
    evidencia = _salvar_evidencia(
        tmp_path,
        "ml_fora_ar",
        fallback="servico_indisponivel",
        lote_interrompido=False,
        itens_processados=len(decisoes),
    )
    assert evidencia["itens_processados"] == 3


def test_cenario_4_telegram_indisponivel_entrega_alerta_por_email(tmp_path):
    telegram = CanalFake("telegram", False, "canal_indisponivel")
    email = CanalFake("email", True)
    logger = Mock()
    resultado = SistemaAlertas(telegram, email, logger=logger).enviar(
        Alerta(
            Severidade.CRITICO,
            "Crise simulada",
            contexto={
                "execution_id": EXECUTION_ID,
                "correlation_id": CORRELATION_ID,
            },
        )
    )

    assert resultado.sucesso is True
    assert resultado.canal == "email"
    assert resultado.fallback_acionado is True
    assert len(telegram.recebidos) == len(email.recebidos) == 1
    evidencia = _salvar_evidencia(
        tmp_path,
        "telegram_indisponivel",
        fallback="email",
        alerta_entregue=resultado.sucesso,
        eventos=_eventos(logger),
    )
    assert evidencia["alerta_entregue"] is True


def test_cenario_5_dois_orquestradores_coexistem_em_simulacao(tmp_path):
    maestro = Mock(name="maestro_fake")
    smart_office = Mock(name="smart_office_fake")
    maestro.create_task.return_value = SimpleNamespace(task_id="task-maestro")
    smart_office.create_task.return_value = SimpleNamespace(
        task_id="task-smart-office"
    )

    for orquestrador, destino in (
        (maestro, "bot-maestro"),
        (smart_office, "bot-smart-office-simulado"),
    ):
        criar_tarefa_sucessora(
            orquestrador,
            activity_label=destino,
            predecessor="bot-entrada",
            predecessor_task_id="task-entrada",
            resultado_predecessor="concluido",
            execution_id=EXECUTION_ID,
            correlation_id=CORRELATION_ID,
        )

    payloads = [
        orquestrador.create_task.call_args.kwargs["parameters"]
        for orquestrador in (maestro, smart_office)
    ]
    assert {payload["execution_id"] for payload in payloads} == {EXECUTION_ID}
    assert {payload["correlation_id"] for payload in payloads} == {
        CORRELATION_ID
    }
    evidencia = _salvar_evidencia(
        tmp_path,
        "coexistencia_orquestradores",
        fallback="orquestradores_fakes_locais",
        smart_office_real="PENDENTE_PLATAFORMA",
        evidencia_real=False,
    )
    assert evidencia["smart_office_real"] == "PENDENTE_PLATAFORMA"
    assert evidencia["evidencia_real"] is False


def test_cenario_6_item_irrecuperavel_vai_dead_letter_e_lote_continua(tmp_path):
    repositorio = RepositorioDeadLetter(tmp_path / "dead_letter.jsonl")

    def processar(item):
        if item["lote_id"] == "LOTE-IRRECUPERAVEL":
            raise ErroDeItem("estrutura inválida")
        return item["lote_id"]

    resultado = processar_lote_com_dead_letter(
        [
            {"lote_id": "LOTE-001"},
            {"lote_id": "LOTE-IRRECUPERAVEL"},
            {"lote_id": "LOTE-002"},
        ],
        processar,
        repositorio=repositorio,
        execution_id=EXECUTION_ID,
        correlation_id=CORRELATION_ID,
        max_tentativas_dado=2,
        backoff_seconds=0,
    )

    assert resultado.processados == ("LOTE-001", "LOTE-002")
    assert len(resultado.dead_letters) == 1
    dead_letter = resultado.dead_letters[0]
    assert dead_letter.execution_id == EXECUTION_ID
    assert dead_letter.correlation_id == CORRELATION_ID
    assert repositorio.listar_pendentes() == (dead_letter,)
    evidencia = _salvar_evidencia(
        tmp_path,
        "item_dead_letter",
        fallback="dead_letter",
        lote_interrompido=False,
        dead_letter_id=dead_letter.dead_letter_id,
        itens_processados=len(resultado.processados),
    )
    assert evidencia["itens_processados"] == 2
