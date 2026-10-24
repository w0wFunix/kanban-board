#!/usr/bin/env bash
# Для преподавателя: сборка артефакта + запуск app + Prometheus + Grafana
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/build.sh
docker compose up --build
