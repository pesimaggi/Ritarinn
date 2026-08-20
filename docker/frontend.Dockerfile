# Ritarinn frontend (development server).
#
# Serves the Vite dev server. A production deployment would instead run
# `npm run build` and serve `dist/` from any static file server.

FROM node:22-slim

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./

USER node

EXPOSE 5173
# --host 0.0.0.0 is required for the published port to reach the container;
# the host-side binding in docker-compose.yml keeps it on loopback.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
