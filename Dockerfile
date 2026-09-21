FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY database database
COPY data data
ENV DATA_DIR=/app/data
CMD ["sh", "-c", "if [ -n \"$DATABASE_URL\" ]; then python -m backend.db.migrate || exit 1; if [ \"$SEED_ON_START\" = \"1\" ]; then python -m backend.db.ingest --activate --if-empty --by bootstrap || exit 1; fi; fi; exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
