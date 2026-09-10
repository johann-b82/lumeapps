# Zwei Ziele aus einer Datei (Befund 20):
#
#   produktion   — nur Laufzeit-Abhängigkeiten, ohne Testsuite
#   entwicklung  — zusätzlich pytest, ruff und Freunde; letztes Ziel und
#                  damit die Vorgabe, wenn `docker compose build` ohne
#                  `target:` läuft (Entwicklung und CI hängen daran)
#
# Das Produktionsbild lädt die Testsuite nicht mehr mit — sie enthält unter
# anderem den Helfer, der Directus-Token ausstellt. Im Betrieb bindet das
# Overlay den Quellbaum auch nicht ein, das Bild ist dort also alles, was da
# ist. Was die Suite ausschließt, steht in backend/.dockerignore.

FROM python:3.11-slim AS basis

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libreoffice-impress \
        libreoffice-calc \
        libreoffice-writer \
        libreoffice-core \
        python3-uno \
        poppler-utils \
        libzbar0 \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
        fonts-noto-core \
        fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/media/slides

# --- Produktion --------------------------------------------------------------
FROM basis AS produktion

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--log-level", "warning"]

# --- Entwicklung und CI ------------------------------------------------------
# Muss das letzte Ziel bleiben: ohne `target:` baut Docker das letzte.
FROM basis AS entwicklung

COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--no-access-log", "--log-level", "warning"]
