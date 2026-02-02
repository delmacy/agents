# Usa uma imagem Python leve
FROM python:3.11-slim

# Define o diretório de trabalho
WORKDIR /app

# Instala dependências do sistema necessárias para compilar alguns pacotes de IA
RUN apt-get update && apt-get install -y build-essential curl

# Copia os requisitos
COPY requirements.txt .

# Instala as dependências Python
# --no-cache-dir ajuda a manter a imagem menor
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código
COPY . .

# Expõe a porta que o Railway vai usar (variável $PORT)
ENV PORT=8000
EXPOSE 8000

# Comando para iniciar o servidor
CMD uvicorn main:app --host 0.0.0.0 --port $PORT