import logging

import pandas as pd

from .validacao import (
    verificar_lote,
    verificar_observacao_reprovado,
    verificar_status_rn04,
)

def aplicar_validacao_status(df: pd.DataFrame, logger):
    """
    Aplica a regra de validação e normalização à coluna 'status'.
    Itera sobre a série e atualiza os valores in-place no DataFrame.
    """
    for index, valor in df['status'].items():
        try:
            # O método at[] atualiza o valor na célula específica com o retorno normalizado
            df.at[index, 'status'] = verificar_status_rn04(valor, logger)
        except ValueError as erro_status:
            msg = f"Falha na validação na linha {index}: {erro_status}"
            logger.error(msg)
            raise ValueError(msg)

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
            verificar_lote(lote_id, base_referencia)
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
            verificar_observacao_reprovado(status, observacao)
        except ValueError as erro_rn07:
            logger.warning(f"Linha {index} - Lote {lote_id}: Falha RN07")
            divergencias.append({
                "lote_id": str(lote_id),
                "status": str(status),
                "observacao": str(observacao) if pd.notna(observacao) else "",
                "motivo_divergencia": str(erro_rn07).strip()
            })
