import logging

import pandas as pd

from .validacao import (
    verificar_observacao_reprovado_rn07,
    verificar_status_rn04,
)
from .base_referencia import verificar_lotes_rn03

def aplicar_validacoes_por_linha(df: pd.DataFrame, base_referencia: list, logger: logging.Logger, divergencias: list):
    """
    Itera sobre as linhas do DataFrame aplicando as regras específicas (RN03, RN04, RN07).
    """
    for index, linha in df.iterrows():
        lote_id = linha.get('lote_id')
        status = linha.get('status')
        observacao = linha.get('observacao')

        # RN03: Validação de Existência na Base
        try:
            verificar_lotes_rn03(lote_id, base_referencia)
        except ValueError as erro_rn03:
            logger.warning(f"Linha {index} - Lote {lote_id}: Falha RN03")
            divergencias.append({
                "lote_id": str(lote_id),
                "status": str(status),
                "observacao": str(observacao) if pd.notna(observacao) else "",
                "motivo_divergencia": str(erro_rn03).strip()
            })

        # RN04 e RN05: Validação e Normalização de Status
        try:
            novo_status = verificar_status_rn04(status, logger)
            df.at[index, 'status'] = novo_status  # Atualiza in-place para as próximas regras
            status = novo_status # Atualiza a variável local
        except ValueError as erro_rn04:
            logger.warning(f"Linha {index} - Lote {lote_id}: Falha RN04")
            divergencias.append({
                "lote_id": str(lote_id),
                "status": str(status),
                "observacao": str(observacao) if pd.notna(observacao) else "",
                "motivo_divergencia": str(erro_rn04).strip()
            })

        # RN07: Validação de Observação para Reprovados
        try:
            verificar_observacao_reprovado_rn07(status, observacao,logger)
        except ValueError as erro_rn07:
            logger.warning(f"Linha {index} - Lote {lote_id}: Falha RN07")
            divergencias.append({
                "lote_id": str(lote_id),
                "status": str(status),
                "observacao": str(observacao) if pd.notna(observacao) else "",
                "motivo_divergencia": str(erro_rn07).strip()
            })
