# Single image: builds the PWA, then serves it and the API from FastAPI.
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_FIREBASE_API_KEY= VITE_FIREBASE_AUTH_DOMAIN= VITE_FIREBASE_PROJECT_ID= \
    VITE_FIREBASE_MESSAGING_SENDER_ID= VITE_FIREBASE_APP_ID= VITE_FIREBASE_VAPID_KEY=
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=web /web/dist /app/frontend/dist
RUN useradd -m vayu && mkdir -p /data && chown -R vayu /data /app
USER vayu
ENV VAYU_DATABASE_URL=sqlite:////data/vayu.db
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["sh", "-c", "python -m scripts.seed --no-demo && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
