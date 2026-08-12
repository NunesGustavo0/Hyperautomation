import logging
from pathlib import Path

from _pytest.config import Config
from selenium.webdriver.chrome.webdriver import WebDriver

from src.config import obter_configuracao
from .config_selenium import iniciar_browser
from .pages.formulario_login_pages import SeleniumLoginPage
from .pages.formulario_lotes_page import SeleniumFormularioPage

#Definindo a configuração
CONFIG = obter_configuracao()
CONTA : dict = {
    "USER": "UsuarioMuitoSeguro",
    "PASSWORD": "SenhaSuperSegura"
}
PRODUTOS : dict = {
    'Nome_Produto' : "Produto A",
    'Tipo_Produto' : "1",
    'Status_Produto' : 'processamento'
}
CAMINHO_EVIDENCIA: str = obter_configuracao().caminho_evidencia

def formulario_login_executar(driver : WebDriver) -> None:
    """Função que é responsável por fazer a execução do formulario login"""
    url_login : str = f'{CONFIG.url_base}/login.html'
    print(url_login)
    formulario_login = SeleniumLoginPage(driver)
    formulario_login.navegar(url_login)
    formulario_login.realizar_login(CONTA)

def formulario_lote_executar(driver : WebDriver ) -> None:
    """Função que é responsável por fazer a execução de inserir o lote"""
    url_lote : str = f'{CONFIG.url_base}/lote-teste.html'
    formulario_lote = SeleniumFormularioPage(driver)
    formulario_lote.navegar(url_lote)
    formulario_lote.realizar_cadastro(PRODUTOS,CAMINHO_EVIDENCIA)



def executar_cadastro_web(logger: logging.Logger):
    """
    Fluxo principal de navegação e automação
    """
    logger.info("Iniciando a o navegador Chromium via Selenium")
    #Inicializando o browser
    driver = iniciar_browser()
    try:
        formulario_login_executar(driver)
        logger.info('Pagina de Login carregada com sucesso.')

        formulario_lote_executar(driver)

    except Exception as e:
        logger.error(f'Erro ao executar em web: {str(e)}')
        caminho_print_erro = CONFIG.caminho_evidencia
        Path(caminho_print_erro).parent.mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(caminho_print_erro)

        raise Exception("Falha de forma automatizada em  web com Selenium. ") from e

    #Mesmo que ocorra erro, ele sempre irá fechar o navegador
    finally:
        logger.info("Encerrando o navegador")
        driver.close()

