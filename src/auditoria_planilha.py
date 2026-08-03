"""Execução local da auditoria de planilha existente no projeto."""

import logging
from pathlib import Path

from .regras_negocio import aplicar_validacoes_por_linha
from .relatorio import CAMINHO_SAIDA, gerar_relatorio_divergencias
from .util import abrir_arquivo, obter_base_referencia
from .validacao import validar_campos_obrigatorios_rn02, validar_estrutura_rn01


CAMINHO_LOG = Path(__file__).resolve().parents[1] / "log" / "execucao.log"
CAMINHO_LOG.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    logging.basicConfig(
        filename=CAMINHO_LOG,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    try:
        df = abrir_arquivo(logger)
        base_referencia = obter_base_referencia(logger)
        divergencias: list = []
        validar_estrutura_rn01(list(df.columns), logger)
        validar_campos_obrigatorios_rn02(df, logger)
        aplicar_validacoes_por_linha(df, base_referencia, logger, divergencias)
        if divergencias:
            gerar_relatorio_divergencias(divergencias, CAMINHO_SAIDA)
            print(f"[{len(divergencias)} divergências] Relatório salvo em: {CAMINHO_SAIDA}")
        else:
            print("[Sucesso] Inspeção concluída sem divergências.")
    except Exception as erro:
        logger.exception("Execução abortada: %s", erro)
        print(f"Erro crítico que interrompeu a execução: {erro}")


if __name__ == "__main__":
    main()
