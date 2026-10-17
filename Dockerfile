# Hasret Zeytincilik — React + Flask/Waitress tek konteyner.
# 1. aşama: React derlemesi (dist/)
FROM node:22-alpine AS build
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html admin.html vite.config.js ./
COPY src ./src
COPY public ./public
RUN npm run build

# 2. aşama: Python çalışma ortamı
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=7030 \
    DATA_DIR=/data \
    ADMIN_FILE=/data/admin.txt
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app.py backend/seed.json ./backend/
COPY --from=build /build/dist ./dist
RUN useradd --system --uid 10001 --create-home app \
 && mkdir -p /data \
 && chown -R app:app /app /data
USER app
EXPOSE 7030
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python","-c","import os,urllib.request,sys; p=os.environ.get('PORT','7030'); sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+p+'/api/health',timeout=4).status==200 else 1)"]
CMD ["python","backend/app.py"]
