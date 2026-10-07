# Steg 1: bygg frontenden.
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Steg 2: backend som också serverar den byggda frontenden från ./static.
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /frontend/dist ./static
# sh -c så att $PORT (satt av Railway) expanderas; exec gör uvicorn till PID 1 och får SIGTERM.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
