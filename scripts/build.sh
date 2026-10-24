#!/usr/bin/env bash
# Сборка: React -> static, backend -> build/, всё упаковывается в артефакт artifacts/kanban-<версия>.tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${VERSION:-dev}"

rm -rf build artifacts
mkdir -p build/static artifacts

echo ">> Сборка фронтенда"
(cd frontend && npm ci && npm run build)
cp -r frontend/dist/. build/static/

echo ">> Копирование backend"
cp -r backend/app build/app
cp backend/requirements.txt build/
find build -name "__pycache__" -type d -prune -exec rm -rf {} +

echo ">> Упаковка артефакта"
tar -czf "artifacts/kanban-${VERSION}.tar.gz" -C build .
ls -lh artifacts/
