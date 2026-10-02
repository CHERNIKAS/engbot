#!/usr/bin/env bash
# Отправляет рассылку v2 — но только если бот действительно живой.
#
# Проверка существует потому, что объявить о новой версии мёртвому боту хуже,
# чем не объявить вовсе. Поллинг поднимается и у бота, который падает на первой
# карточке, поэтому доказательством считается не старт, а факт отправки карточки.
set -euo pipefail

cd /opt/englshbot
LOG=/opt/englshbot/ops/broadcast-v2.log
exec >>"$LOG" 2>&1
echo "=== $(date '+%F %T %Z') запуск проверки ==="

state="$(docker compose -f docker-compose.prod.yml ps -a --format '{{.Service}} {{.State}}' | awk '$1=="bot"{print $2}')"
if [ "$state" != "running" ]; then
    echo "ОТМЕНА: контейнер бота в состоянии '$state', рассылка не отправлена"
    exit 1
fi

sent="$(docker compose -f docker-compose.prod.yml logs bot --since 12h 2>/dev/null | grep -c '"event":"push_sent"' || true)"
if [ "${sent:-0}" -lt 1 ]; then
    echo "ОТМЕНА: за 12 часов ни одной push_sent — путь до карточки не подтверждён"
    exit 1
fi
echo "проверка пройдена: бот running, push_sent за 12ч: $sent"

docker compose -f docker-compose.prod.yml run --rm --no-deps \
    -v /opt/englshbot/scripts:/app/scripts \
    -v /opt/englshbot/ops:/app/ops \
    --entrypoint python bot \
    scripts/broadcast.py --slug v2 --text-file /app/ops/v2.txt --send
echo "=== $(date '+%F %T %Z') готово ==="
