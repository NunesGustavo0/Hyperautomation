import logging
import sys

from src.config import ROOT_DIR
from selenium_web.web_automation import executar_cadastro_web
import os
from pythonjsonlogger import jsonlogger


CAMINHO_LOG = ROOT_DIR / 'logs' / 'botcity_permofer.log'
ATIVIDADE_LOG = 'AuditoriasLotes'

# Configurando o logger para web_automation
def configurar_logger() -> logging.Logger:
    #Criando a pasta
    CAMINHO_LOG.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('botcity_permorfer')
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Recuperamos o execution_id e bot_id das variáveis de ambiente
        # Caso não exista no .env, vamos colocar o valor padrão mesmo
        bot_id = os.getenv('BOT_ID','bot-auditoria-local')
        execution_id = os.getenv('EXECUCAO_ID','exec_dev_001')

        # Usamos o nossa classe python-json-logger para facilitar a injeção de contexto
        class ContextJsonFormatter(jsonlogger.JsonFormatter):
            def add_fields(self, log_record, record, message_dict):
                super(ContextJsonFormatter, self).add_fields(log_record, record, message_dict)
                # Injetando os campos em TODAS as mensagens automaticamente
                log_record['bot_id'] = bot_id
                log_record['execution_id'] = execution_id

        #Definimos o nosso formato base (O que o JSON terá que conter)
        formato = '%(asctime)s %(levelname)s %(filename)s %(message)s'
        formatter = ContextJsonFormatter(formato)

        # Handler para salvar no arquivo botcity_performer.log

        file_handler = logging.FileHandler(CAMINHO_LOG,encoding='utf8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Vamos também mostrar no nosso terminal
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger




def main() -> None:
    # Para mostrar o logger, é necessário utilizar uma função para instanciar
    logger = configurar_logger()

    executar_cadastro_web(logger)


if __name__ == "__main__":
    main()
