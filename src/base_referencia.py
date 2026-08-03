"""
Nesse modulo, terá a responsabilidade de fazer verificação na base de lotes, que será a regra de negócio de RN03
"""
import logging

def verificar_lotes_rn03(id_lote : str, base_referencia : list):
    """
    Regra de negócio 3: Validação de Existencia de Lotes
    Verifica se o lote existe na base de referencia
    """
    if not id_lote or id_lote not in base_referencia:
        msg : str = f'''Divergencia: Lote não existe:
        Lote de id: {id_lote} não foi encontrado na base de referência
        '''
        raise ValueError(msg)

    return True
