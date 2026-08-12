""""Nesse modulo é o Page object formulário de Login"""
from typing import Final

#Importando da biblioteca
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

#Definindo de forma constante os seletores
SELETOR_USUARIO : Final = "usuario"
SELETOR_SENHA : Final = "senha"
BOTAO_LOGIN : Final = "button[type='submit']"

class SeleniumLoginPage:
    def __init__(self,driver: WebDriver):
        self.__driver = driver
        self.__wait = WebDriverWait(self.__driver,10)

        self.__campo_usuario = (By.ID, SELETOR_USUARIO)
        self.__campo_senha = (By.ID, SELETOR_SENHA)
        self.__botao_login = (By.CSS_SELECTOR, BOTAO_LOGIN)

    def navegar(self,url : str):
        """Nesse método ele vai abrir a página de login"""
        self.__driver.get(url)

    def __inserir_usuario(self, usuario: str):
        campo_usuario_elemento = self.__wait.until(EC.visibility_of_element_located(self.__campo_usuario))
        campo_usuario_elemento.clear()
        campo_usuario_elemento.send_keys(usuario)

    def __inserir_senha(self, senha: str):
        campo_senha_elemento = self.__driver.find_element(*self.__campo_senha)
        campo_senha_elemento.clear()
        campo_senha_elemento.send_keys(senha)

    def realizar_login(self, conta: dict):
        self.__inserir_usuario(conta['USER'])
        self.__inserir_senha(conta['PASSWORD'])

        self.__driver.find_element(*self.__botao_login).click()

