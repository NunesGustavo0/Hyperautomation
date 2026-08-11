# Utilizando versão exata de acordo com .python-version
FROM python:3.12-slim

# Instalando as dependências corretas para o sistema, tendo Chromium e ChromeDriver
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    chromium \
    chromium-driver \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Configurando o fuso horário para Manaus
ENV TZ="America/Manaus"

# Definindo o diretório de trabalho
WORKDIR /app

#  Copiando a dependência nesse ponto e rodando o pip install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiando o restante do código do projeto
COPY . .

# Comando padrão de execução do bot
CMD ["python", "bot.py"]
