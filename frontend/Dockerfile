FROM node:22-bookworm-slim

WORKDIR /workspace/frontend
COPY --chown=node:node package.json package-lock.json ./
RUN --mount=type=secret,id=build_proxy \
    if [ -f /run/secrets/build_proxy ]; then export npm_config_https_proxy="$(cat /run/secrets/build_proxy)"; fi; \
    npm ci && chown -R node:node /workspace/frontend
COPY --chown=node:node . .

USER node
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]
