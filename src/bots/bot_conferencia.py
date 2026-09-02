"""Bot B: aplica as regras RN01-RN12 e o enriquecimento híbrido."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from pathlib import Path
from typing import Any

from gerar_relatorio import ler_e_validar
from src.auditoria_hibrida import AuditoriaPipelineHibrido
from src.classificador_divergencia import ClassificadorDivergencia
from src.validacao_lotes import RegistroValidado

from src.dead_letter import RepositorioDeadLetter
from src.politicas_resiliencia import mensagem_erro_segura

LOGGER = logging.getLogger("botcity_permorfer")
BOT_ID = "bot-b-conferencia"


class StatusBotConferencia(str, Enum):
    """Estados controlados produzidos pelo Bot B."""

    CONCLUIDO = "conferencia_concluida"
    ENTRADA_INVALIDA = "entrada_invalida"
    ERRO_PROCESSAMENTO = "erro_ao_processar_conferencia"


@dataclass(frozen=True)
class ResultadoBotConferencia:
    """Resultado do Bot B entregue ao Bot C."""

    sucesso: bool
    status: StatusBotConferencia
    mensagem: str
    execution_id: str
    correlation_id: str
    caminho_entrada: str
    registros: tuple[RegistroValidado, ...] = ()
    classificacoes: dict[str, int] = field(default_factory=dict)
    origens_decisao: dict[str, int] = field(default_factory=dict)
    decisoes_auditadas: int = 0
    erro: str | None = None

    @property
    def total_registros(self) -> int:
        return len(self.registros)

    def to_dict(self) -> dict[str, Any]:
        """Cria um resumo serializável sem duplicar todos os registros."""

        return {
            "sucesso": self.sucesso,
            "status": self.status.value,
            "mensagem": self.mensagem,
            "execution_id": self.execution_id,
            "correlation_id": self.correlation_id,
            "caminho_entrada": self.caminho_entrada,
            "total_registros": self.total_registros,
            "classificacoes": dict(self.classificacoes),
            "origens_decisao": dict(self.origens_decisao),
            "decisoes_auditadas": self.decisoes_auditadas,
            "erro": self.erro,
        }


def executar_bot_conferencia(
    caminho_entrada: str | Path,
    *,
    execution_id: str,
    correlation_id: str,
    classificador: ClassificadorDivergencia | None = None,
    auditoria_ml: AuditoriaPipelineHibrido | None = None,
    logger: logging.Logger | None = None,
    repositorio_dead_letter: RepositorioDeadLetter | None = None,
) -> ResultadoBotConferencia:
    """Lê a planilha e processa todos os registros uma única vez."""

    logger = logger or LOGGER
    caminho = Path(caminho_entrada)

    if not execution_id.strip() or not correlation_id.strip():
        return ResultadoBotConferencia(
            sucesso=False,
            status=StatusBotConferencia.ENTRADA_INVALIDA,
            mensagem="execution_id e correlation_id são obrigatórios",
            execution_id=execution_id,
            correlation_id=correlation_id,
            caminho_entrada=str(caminho),
            erro="identificadores_obrigatorios_ausentes",
        )

    if not caminho.is_file():
        return ResultadoBotConferencia(
            sucesso=False,
            status=StatusBotConferencia.ENTRADA_INVALIDA,
            mensagem=f"Planilha não encontrada: {caminho}",
            execution_id=execution_id,
            correlation_id=correlation_id,
            caminho_entrada=str(caminho),
            erro="planilha_nao_encontrada",
        )

    auditoria = auditoria_ml or AuditoriaPipelineHibrido(
        execution_id=execution_id,
        logger=logger,
    )

    logger.info(
        "bot_conferencia_iniciado",
        extra={
            "evento": "bot_conferencia_iniciado",
            "bot_id": BOT_ID,
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "caminho_entrada": str(caminho.resolve()),
        },
    )

    try:
        registros = ler_e_validar(
            caminho,
            auditoria_ml=auditoria,
            classificador=classificador,
            repositorio_dead_letter=repositorio_dead_letter,
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
    except Exception as erro:
        erro_seguro = mensagem_erro_segura(erro)
        resultado = ResultadoBotConferencia(
            sucesso=False,
            status=StatusBotConferencia.ERRO_PROCESSAMENTO,
            mensagem=f"Falha ao processar a planilha: {erro_seguro}",
            execution_id=execution_id,
            correlation_id=correlation_id,
            caminho_entrada=str(caminho.resolve()),
            erro=erro_seguro,
        )
        # Não anexar ``exc_info``: o traceback pode carregar tokens presentes
        # em argumentos de exceções de bibliotecas externas.
        logger.error(
            "bot_conferencia_falhou",
            extra={
                "evento": "bot_conferencia_falhou",
                "bot_id": BOT_ID,
                **resultado.to_dict(),
            },
        )
        return resultado

    if not registros:
        resultado = ResultadoBotConferencia(
            sucesso=False,
            status=StatusBotConferencia.ENTRADA_INVALIDA,
            mensagem="A planilha não possui registros para processar",
            execution_id=execution_id,
            correlation_id=correlation_id,
            caminho_entrada=str(caminho.resolve()),
            erro="planilha_sem_registros",
        )
        logger.warning(
            "bot_conferencia_sem_registros",
            extra={
                "evento": "bot_conferencia_sem_registros",
                "bot_id": BOT_ID,
                **resultado.to_dict(),
            },
        )
        return resultado

    classificacoes = Counter(
        registro.classificacao
        for registro in registros
    )
    origens_decisao = Counter(
        (registro.origem_decisao or "sem_origem").strip().lower()
        for registro in registros
    )

    resultado = ResultadoBotConferencia(
        sucesso=True,
        status=StatusBotConferencia.CONCLUIDO,
        mensagem="Regras e enriquecimento híbrido aplicados com sucesso",
        execution_id=execution_id,
        correlation_id=correlation_id,
        caminho_entrada=str(caminho.resolve()),
        registros=tuple(registros),
        classificacoes=dict(classificacoes),
        origens_decisao=dict(origens_decisao),
        decisoes_auditadas=len(auditoria.decisoes),
    )

    logger.info(
        "bot_conferencia_concluido",
        extra={
            "evento": "bot_conferencia_concluido",
            "bot_id": BOT_ID,
            **resultado.to_dict(),
        },
    )
    return resultado


def main(argv: list[str] | None = None) -> int:
    """Permite executar somente o Bot B pelo terminal."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entrada", help="Caminho da planilha .xlsx")
    parser.add_argument(
        "--execution-id",
        default="exec-bot-b-local",
    )
    parser.add_argument(
        "--correlation-id",
        default="corr-bot-b-local",
    )
    args = parser.parse_args(argv)

    resultado = executar_bot_conferencia(
        args.entrada,
        execution_id=args.execution_id,
        correlation_id=args.correlation_id,
    )
    print(
        json.dumps(
            resultado.to_dict(),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if resultado.sucesso else 2


if __name__ == "__main__":
    raise SystemExit(main())
