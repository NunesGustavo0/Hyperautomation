"""Testes dos contratos independentes do orquestrador."""

from datetime import date, datetime, timezone
import json

import pytest
from pydantic import ValidationError

from src.contratos_capstone import (
    ArtefatoConsolidacao,
    ArtefatoEstoqueDesktop,
    ArtefatoPedidosFornecedor,
    ContratoInvalidoError,
    EnvelopeAuditoria,
    EstadoExecucao,
    FonteDados,
    PedidoFornecedor,
    RegistroConsolidado,
    RegistroEstoqueDesktop,
)


def criar_envelope(
    *,
    bot_id: str = "bot-b-coleta-desktop",
    task_id: str = "task-b-001",
) -> EnvelopeAuditoria:
    return EnvelopeAuditoria(
        execution_id="exec-001",
        correlation_id="corr-001",
        bot_id=bot_id,
        task_id=task_id,
        estado=EstadoExecucao.CONCLUIDO,
        predecessor="carlos_souza-entrada-v2",
        predecessor_task_id="task-a-001",
        resultado_predecessor="pronto_para_coleta",
        registrado_em=datetime(
            2026,
            9,
            1,
            14,
            0,
            tzinfo=timezone.utc,
        ),
    )


def test_estoque_serializa_e_desserializa_sem_perder_dados():
    artefato = ArtefatoEstoqueDesktop(
        auditoria=criar_envelope(),
        registros=(
            RegistroEstoqueDesktop(
                lote_id="LOTE-001",
                produto="Sensor",
                quantidade_disponivel=20,
                localizacao="A-01",
                status_estoque="DISPONIVEL",
                coletado_em=datetime(
                    2026,
                    9,
                    1,
                    14,
                    1,
                    tzinfo=timezone.utc,
                ),
            ),
        ),
    )

    restaurado = ArtefatoEstoqueDesktop.de_json(
        artefato.para_json()
    )

    assert restaurado == artefato
    assert restaurado.total_registros == 1
    assert restaurado.registros[0].quantidade_disponivel == 20


def test_pedidos_serializam_data_e_preservam_rastreabilidade():
    artefato = ArtefatoPedidosFornecedor(
        auditoria=criar_envelope(
            bot_id="bot-c-coleta-web",
            task_id="task-c-001",
        ),
        registros=(
            PedidoFornecedor(
                pedido_id="PED-001",
                lote_id="LOTE-001",
                fornecedor="Fornecedor Norte",
                produto="Sensor",
                quantidade_pedida=25,
                status_pedido="EM_TRANSITO",
                previsao_entrega=date(2026, 9, 5),
            ),
        ),
    )

    restaurado = ArtefatoPedidosFornecedor.de_json(
        artefato.para_json()
    )

    assert restaurado == artefato
    assert restaurado.auditoria.execution_id == "exec-001"
    assert restaurado.auditoria.correlation_id == "corr-001"
    assert restaurado.registros[0].previsao_entrega == date(
        2026,
        9,
        5,
    )


def test_consolidacao_normal_exige_desktop_e_web():
    registro = RegistroConsolidado(
        lote_id="LOTE-001",
        produto="Sensor",
        quantidade_estoque=20,
        quantidade_pedida=25,
        status_estoque="DISPONIVEL",
        status_pedido="EM_TRANSITO",
        classificacao_deterministica="Divergência",
        motivo="Quantidade disponível abaixo do pedido",
        regras_aplicadas=("RN05",),
        fontes_disponiveis=(
            FonteDados.DESKTOP,
            FonteDados.WEB,
        ),
    )

    artefato = ArtefatoConsolidacao(
        auditoria=criar_envelope(
            bot_id="bot-d-consolidacao",
            task_id="task-d-001",
        ),
        registros=(registro,),
    )

    restaurado = ArtefatoConsolidacao.de_json(
        artefato.para_json()
    )

    assert restaurado == artefato
    assert restaurado.registros[0].modo_degradado is False


def test_consolidacao_degradada_aceita_somente_desktop():
    registro = RegistroConsolidado(
        lote_id="LOTE-002",
        produto="Atuador",
        quantidade_estoque=8,
        status_estoque="BAIXO",
        classificacao_deterministica="Pendente de revisão",
        motivo="Portal de fornecedores indisponível",
        fontes_disponiveis=(FonteDados.DESKTOP,),
        modo_degradado=True,
    )

    assert registro.quantidade_pedida is None
    assert registro.modo_degradado is True


def test_schema_incompativel_e_rejeitado_com_mensagem_clara():
    payload = json.loads(
        ArtefatoEstoqueDesktop(
            auditoria=criar_envelope(),
        ).para_json()
    )
    payload["schema_version"] = "2.0"

    with pytest.raises(
        ContratoInvalidoError,
        match="schema_version não suportada",
    ):
        ArtefatoEstoqueDesktop.de_json(
            json.dumps(payload)
        )


def test_campo_desconhecido_e_rejeitado():
    payload = json.loads(
        ArtefatoEstoqueDesktop(
            auditoria=criar_envelope(),
        ).para_json()
    )
    payload["campo_nao_previsto"] = True

    with pytest.raises(
        ContratoInvalidoError,
        match="campo_nao_previsto",
    ):
        ArtefatoEstoqueDesktop.de_json(
            json.dumps(payload)
        )


def test_identificadores_vazios_sao_rejeitados():
    with pytest.raises(ValidationError, match="execution_id"):
        EnvelopeAuditoria(
            execution_id="   ",
            correlation_id="corr-001",
            bot_id="bot-a-entrada",
            task_id="task-a-001",
            estado=EstadoExecucao.CONCLUIDO,
        )


def test_predecessor_e_task_id_devem_ser_informados_juntos():
    with pytest.raises(
        ValidationError,
        match="devem ser informados em conjunto",
    ):
        EnvelopeAuditoria(
            execution_id="exec-001",
            correlation_id="corr-001",
            bot_id="bot-b-coleta-desktop",
            task_id="task-b-001",
            estado=EstadoExecucao.CONCLUIDO,
            predecessor="carlos_souza-entrada-v2",
        )


def test_data_sem_fuso_horario_e_rejeitada():
    with pytest.raises(
        ValidationError,
        match="deve possuir fuso horário",
    ):
        RegistroEstoqueDesktop(
            lote_id="LOTE-001",
            produto="Sensor",
            quantidade_disponivel=20,
            localizacao="A-01",
            status_estoque="DISPONIVEL",
            coletado_em=datetime(2026, 9, 1, 10, 0),
        )


def test_quantidade_negativa_e_rejeitada():
    with pytest.raises(
        ValidationError,
        match="quantidade_disponivel",
    ):
        RegistroEstoqueDesktop(
            lote_id="LOTE-001",
            produto="Sensor",
            quantidade_disponivel=-1,
            localizacao="A-01",
            status_estoque="DISPONIVEL",
        )

