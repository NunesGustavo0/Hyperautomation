import pandas as pd
import logging

"""
Regra de negócio de RN01:
"""

def verificar_estrutura_rn01(lista: list, loggers) -> None:
    # Colunas de Referência
    colunas_referencia = {"lote_id", "produto", "linha",
                          "turno", "status", "responsavel",
                          "data", "observacao"
                          }
    # Colunas da planilha recebida
    colunas_recebidas = set(lista)

    colunas_invalidas = colunas_referencia - colunas_recebidas

    if colunas_invalidas:
        msg = f"Falha na RN01: Identificou-se {colunas_invalidas} fora do padrão estipulado"
        logging.error(msg)
        raise ValueError(msg)

""" Regra de negócio de RN02: """

def validar_campos_obrigatorios_rn02(df,logger) -> None:
    #1. Ignoramos a coluna 'observação", pois ela pode ser que esteja vazia(ex: Lotes Aprovados)
    verificar_coluna = df.drop(columns=["observacao"], errors="ignore")

    #2. Aplicamos a máscara de nulos apenas nas colunas essenciais
    mascara_nulos = verificar_coluna.isna()

    if mascara_nulos.any().any():
        nulos_empilhados = mascara_nulos.stack()
        coordenadas = nulos_empilhados[nulos_empilhados].index.tolist()

        primeiro_erro = coordenadas[0]
        linha_erro, coluna_erro = primeiro_erro

        mensagem = f"Falha na RN02: Valor ausente ou nulo encontrado na linha {linha_erro}, coluna '{coluna_erro}."
        logging.error(mensagem)
        raise ValueError(mensagem)

"""
Regra de negócio de RN04:
"""

def verificar_status_rn04(status: str, logging) -> str:
    """
    Verifica se o status pertence ao escopo de regras de negócio.
    Aciona a normalização caso identifique entradas 'OK' ou 'NOK'.
    """
    # Tratamento defensivo da entrada
    status_tratado = str(status).strip().upper()

    # Validação e acionamento da normalização
    if status_tratado in {"OK", "NOK"}:
        status_tratado = normalizar_status_rn05(status_tratado)

    # Conjunto de referência (Operação O(1))
    status_permitidos = {"APROVADO", "REPROVADO", "PENDENTE"}

    if status_tratado not in status_permitidos:
        msg = f"Erro de validação: Status '{status}' não reconhecido."
        logging.error(msg)
        raise ValueError(msg)

    return status_tratado

def normalizar_status_rn05(status: str) -> str:
    """
    Normaliza os status específicos 'OK' e 'NOK' para o padrão do sistema.
    """
    mapeamento = {
        "OK": "APROVADO",
        "NOK": "REPROVADO"
    }
    # Retorna o valor mapeado; se não existir no dicionário, retorna o próprio status
    return mapeamento.get(status, status)

def verificar_observacao_reprovado_rn07(status: str, observacao: str, logging):
    # Vamos padronizar o texto para evitar erros de CamelSensitive
    status_normalizado = str(status).strip().upper if status else ""

    if status_normalizado == 'REPROVADO':
        if not observacao or str(observacao).strip() == "" or str(observacao).lower() == 'nan':
            msg = "Divergência: Falta de Justificativa no campo de observação em lote em REPROVADO"
            logging.error(msg)
            raise ValueError(msg)
    return True