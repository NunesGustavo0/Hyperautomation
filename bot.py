"""Performer: consome a fila configurada e reporta a execução ao Maestro."""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time

from botcity.maestro.datapool.entry import ErrorType
from botcity.maestro.model import AutomationTaskFinishStatus, Column

from src.config import ROOT_DIR, obter_configuracao
from src.maestro_client import criar_cliente
from src.vault_client import obter_credencial_erp
from src.auditoria_planilha import main as executar_local


CAMINHO_LOG = ROOT_DIR / "logs" / "botcity_performer.log"
PASTA_RESULTADOS = ROOT_DIR / "resultados"
ATIVIDADE_LOG = "AuditoriaLotes"


def configurar_logger() -> logging.Logger:
    CAMINHO_LOG.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("botcity.performer")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.FileHandler(CAMINHO_LOG, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)

    return logger


def criar_log_portal(maestro, logger: logging.Logger) -> None:
    """Cria a visualização de logs do bot no portal, se ainda não existir."""

    colunas = [
        Column(name="Lote", label="lote_id", width=160),
        Column(name="CPF", label="cpf", width=140),
        Column(name="Resultado", label="resultado", width=120),
        Column(name="Mensagem", label="mensagem", width=400),
    ]

    try:
        maestro.new_log(ATIVIDADE_LOG, colunas)
    except Exception as erro:
        logger.info("Log de atividade já existente ou não criado: %s", erro)


def registrar_log_portal(
    maestro,
    lote_id: str,
    cpf: str,
    resultado: str,
    mensagem: str,
) -> None:
    maestro.new_log_entry(
        ATIVIDADE_LOG,
        {
            "lote_id": lote_id,
            "cpf": cpf,
            "resultado": resultado,
            "mensagem": mensagem,
        },
    )


def gerar_resultado(resumo: dict) -> Path:
    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)

    instante = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    caminho = PASTA_RESULTADOS / f"resultado_auditoria_{instante}.json"

    caminho.write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return caminho


def executar_performer() -> dict:
    logger = configurar_logger()

    config = obter_configuracao()

    # Agora o cliente é criado utilizando os argumentos do Runner
    maestro = criar_cliente()

    logger.info("Maestro online: %s", maestro.is_online)
    logger.info("Task ID: %s", maestro.task_id)

    task_id = str(maestro.task_id) if maestro.task_id else None

    datapool = maestro.get_datapool(config.datapool_label)

    resumo = {
        "fila": config.datapool_label,
        "inicio_utc": datetime.now(timezone.utc).isoformat(),
        "processados": 0,
        "sucessos": 0,
        "falhas": 0,
        "credencial_vault": "não utilizada",
        "itens_com_erro": [],
    }

    try:
        credencial = obter_credencial_erp(maestro, config)

        if credencial is not None:
            resumo["credencial_vault"] = "obtida com sucesso"
            logger.info("Credencial do ERP obtida do Credentials Vault.")

        criar_log_portal(maestro, logger)

        while datapool.has_next():
            entrada = datapool.next(task_id)

            if entrada is None:
                break

            lote_id = str(entrada.get_value("lote_id", ""))
            cpf = str(entrada.get_value("cpf", "")).strip()

            resumo["processados"] += 1

            try:
                if not cpf:
                    raise ValueError("CPF não informado.")

                # Simulação do processamento
                time.sleep(1)

                entrada.report_done("Lote validado com sucesso.")

                resumo["sucessos"] += 1

                registrar_log_portal(
                    maestro,
                    lote_id,
                    cpf,
                    "SUCESSO",
                    "Lote validado.",
                )

                logger.info("Lote %s processado com sucesso.", lote_id)

            except Exception as erro:
                mensagem = str(erro)

                entrada.report_error(ErrorType.BUSINESS, mensagem)

                resumo["falhas"] += 1

                resumo["itens_com_erro"].append(
                    {
                        "lote_id": lote_id,
                        "cpf": cpf,
                        "erro": mensagem,
                    }
                )

                registrar_log_portal(
                    maestro,
                    lote_id,
                    cpf,
                    "ERRO",
                    mensagem,
                )

                logger.warning(
                    "Lote %s finalizado com erro: %s",
                    lote_id,
                    mensagem,
                )

    except Exception as erro:
        logger.exception("Falha não recuperável no performer: %s", erro)

        if task_id:
            maestro.error(task_id, erro, attachments=[str(CAMINHO_LOG)])

        raise

    finally:
        resumo["fim_utc"] = datetime.now(timezone.utc).isoformat()

        caminho_resultado = gerar_resultado(resumo)

        logger.info("Resultado final salvo em %s", caminho_resultado)

        if task_id:
            maestro.post_artifact(
                task_id,
                caminho_resultado.name,
                str(caminho_resultado),
            )

            maestro.post_artifact(
                task_id,
                CAMINHO_LOG.name,
                str(CAMINHO_LOG),
            )

            status = (
                AutomationTaskFinishStatus.SUCCESS
                if resumo["falhas"] == 0
                else AutomationTaskFinishStatus.PARTIALLY_COMPLETED
            )

            maestro.finish_task(
                task_id,
                status,
                message="Processamento da fila concluído.",
                total_items=resumo["processados"],
                processed_items=resumo["sucessos"],
                failed_items=resumo["falhas"],
            )

        else:
            logger.warning(
                "Execução local sem task_id: artefatos não foram enviados ao portal."
            )

    return resumo


def main() -> None:
    # Carregando a nossa configuração
    config = obter_configuracao()

    if config.maestro_enabled:
        print("Iniciando o maestro atráves pelo Bot City")
        executar_performer()
        return
    print("Executando o modo offline")
    executar_local()






if __name__ == "__main__":
    main()