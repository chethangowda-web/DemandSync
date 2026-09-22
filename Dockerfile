FROM node:20-slim AS web
WORKDIR /web
COPY frontend/officer-web/package.json frontend/officer-web/package-lock.json ./
RUN npm ci
COPY frontend/officer-web/ ./
RUN VITE_BASE=/officer/ npm run build

FROM ghcr.io/cirruslabs/flutter:3.35.5 AS beneficiary
WORKDIR /app
COPY frontend/beneficiary-mobile/pubspec.yaml frontend/beneficiary-mobile/pubspec.lock ./
RUN flutter pub get
COPY frontend/beneficiary-mobile/ ./
RUN flutter gen-l10n
RUN flutter build web --release

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY database database
COPY data data
COPY --from=web /web/dist static/officer
COPY --from=beneficiary /app/build/web static/beneficiary
ENV DATA_DIR=/app/data OFFICER_WEB_DIR=/app/static/officer BENEFICIARY_WEB_DIR=/app/static/beneficiary
CMD ["sh", "-c", "python -m backend.startup || exit 1; exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
