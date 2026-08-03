from pathlib import Path
import pandas as pd

CAMINHO_ARQUIVO = Path(__file__).resolve().parents[1] / "data" / 'samples' / "inspecao_lotes_dia_teste.xlsx"

def abrir_arquivo(logger):
    cabecalho = 2
    df = pd.read_excel(io=CAMINHO_ARQUIVO, header=cabecalho, sheet_name="Inspecao")
    df = df.dropna(how='all')
    df = df.reset_index(drop=True)

    # Remove linhas de rodapé/legenda (ex: "Total de registros...", "LEGENDA...", "Exemplo")
    # que não são lotes de inspeção reais.
    linhas_invalidas = df['lote_id'].astype(str).str.contains(
        r'^(Total de registros|LEGENDA|Exemplo)', case=False, na=False
    )
    df = df[~linhas_invalidas].reset_index(drop=True)
    logger.info('Base de dados carregada')

    return df

def obter_base_referencia(logger):
    """Lê a aba de referência para aplicar a RN03."""
    try:
        df_base = pd.read_excel(io=CAMINHO_ARQUIVO, sheet_name="Base_Referencia", header=1)
        return df_base['lote_id'].dropna().astype(str).tolist()
    except Exception as e:
        logger.error(f"Erro ao carregar base de referência: {e}")
        return []
