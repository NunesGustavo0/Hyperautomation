"""Nesse módulo, será responsável pela configuraçao e inicialização do Selenium WebDriver"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from src.config import obter_configuracao

def iniciar_browser() -> webdriver.Chrome:
    """Iniciamos o nosso Chromium com as flags necessárias para rodar no Docker e localmente"""

    config = obter_configuracao()
    chromium_options = Options()

    # Nesse headless, é um modo que não terá nacessidade de ter interface gráfica
    if config.interface_navegador:
        chromium_options.add_argument('--headless')


    chromium_options.add_argument('--no-sandbox')
    chromium_options.add_argument('--disable-dev-shm-usage')
    chromium_options.add_argument('--disable-gpu')
    chromium_options.add_argument('--window-size=1920,1080')

    driver = webdriver.Chrome(options=chromium_options)

    #Definindo um tempo máximo de espera implícita para encontrar os elementos na tela
    driver.implicitly_wait(10)
    return driver