FROM node:22-bookworm-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
COPY contracts /app/contracts
RUN npm run build

FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv libicu72 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY backend/requirements.txt backend/requirements.txt
RUN python3 -m venv .venv && .venv/bin/python -m pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY contracts contracts
COPY scripts scripts
COPY --from=web /app/frontend/dist frontend/dist
RUN useradd --uid 10001 --create-home prepcrew && mkdir /data /app/.artifacts && chown prepcrew:prepcrew /data /app/.artifacts
USER prepcrew
ENV PREPCREW_DATA_DIR=/data PREPCREW_PUBLIC=true PORT=8000
EXPOSE 8000
VOLUME ["/data"]
CMD ["node", "scripts/start.mjs"]
