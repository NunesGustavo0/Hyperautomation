"""Nesse modulo é o POM formulario de lotes"""
from pathlib import Path
from typing import Final

#Importando da biblioteca Selenium
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


SELETOR_LOTE : Final = 'lote'
SELETOR_PRODUTO : Final = 'produto'
BOTAO_CONFIRMAR : Final = 'button[type="submit"]'
SELETOR_STATUS : Final = "input[name='status']"
MENSAGEM_SUCESSO : Final = 'MensagemSucesso'

class SeleniumFormularioPage:
    def __init__(self,driver: WebDriver):
        self.__driver = driver
        self.__wait = WebDriverWait(self.__driver,10)

        self.__campo_lote = (By.ID,SELETOR_LOTE)
        self.__campo_produto = (By.ID,SELETOR_PRODUTO)
        self.__campo_tipo = SELETOR_STATUS
        self.__mensagem_sucesso = (By.ID,MENSAGEM_SUCESSO)
        self.__botao_confirmar = (By.CSS_SELECTOR,BOTAO_CONFIRMAR)

    def navegar(self,url: str):
        self.__driver.get(url)

    def __inserir_campo_lote(self,nome_lote : str):
        campo_lote_elemento = self.__wait.until(EC.visibility_of_element_located(self.__campo_lote))
        campo_lote_elemento.clear()
        campo_lote_elemento.send_keys(nome_lote)

    def __inserir_produto(self,valor : str):
        campo_produto = self.__driver.find_element(*self.__campo_produto)
        select = Select(campo_produto)
        select.select_by_value(valor)

    def __selecionar_status(self,valor : str):
        radio = self.__driver.find_element(By.CSS_SELECTOR, f"{self.__campo_tipo}[value='{valor}']")
        radio.click()

    def __submeter(self):
        self.__driver.find_element(*self.__botao_confirmar).click()

    def __mensagem_sucesso_visivel(self) -> bool:
        try:
            #Isso deve aguarda até que a classe CSS mude e a caixa apareça na tela
            elemento = self.__wait.until(EC.visibility_of_element_located(self.__mensagem_sucesso))
            return elemento.is_displayed()
        except Exception as e:
            print(f"Erro: {e}")
            return False

    def __capturar_evidencia(self,caminho: str):
        Path(caminho).parent.mkdir(parents=True,exist_ok=True)
        self.__driver.save_screenshot(caminho)

    def realizar_cadastro(self,produto : dict,caminho_evidencia :str):
        """Parte que executa o fluxo completo em única chamada"""
        self.__inserir_campo_lote(produto['Nome_Produto'])
        self.__inserir_produto(produto['Tipo_Produto'])
        self.__selecionar_status(produto['Status_Produto'])
        self.__submeter()

        if self.__mensagem_sucesso_visivel() and caminho_evidencia:
            self.__capturar_evidencia(caminho_evidencia)



