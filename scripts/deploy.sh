#!/usr/bin/env bash
# Деплой на Render: дёргаем Deploy Hook, затем ждём, пока /health ответит 200.
# Использование: RENDER_DEPLOY_HOOK=... APP_URL=https://... [IMAGE=ghcr.io/user/repo:sha] ./scripts/deploy.sh
set -euo pipefail
: "${RENDER_DEPLOY_HOOK:?Не задан RENDER_DEPLOY_HOOK}"
: "${APP_URL:?Не задан APP_URL}"

HOOK="$RENDER_DEPLOY_HOOK"
if [ -n "${IMAGE:-}" ]; then HOOK="${HOOK}&imgURL=${IMAGE}"; fi

echo ">> Запуск деплоя"
curl -fsS -X POST "$HOOK"
echo

echo ">> Ожидание /health (до ~5 минут)"
for i in $(seq 1 30); do
  if curl -fsS --max-time 20 "$APP_URL/health" >/dev/null; then
    echo "OK: приложение отвечает"; exit 0
  fi
  echo "попытка $i: пока не готово"; sleep 10
done
echo "Приложение не поднялось" >&2; exit 1
