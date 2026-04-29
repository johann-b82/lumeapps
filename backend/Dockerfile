FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt && \
    apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libreoffice-impress \
        libreoffice-core \
        poppler-utils \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
        fonts-noto-core \
        fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/media/slides

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
