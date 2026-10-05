#!/bin/bash
# ─── downloads.quantumart.ru — production deploy ────────────────────────────
# Тянет последние изменения из git, пересобирает Docker-образ статического
# сайта, перезапускает контейнер, прогоняет smoke-test (loopback + домен).
# Паттерн — тот же, что у sidus на этом VPS.
#
# Запуск: ./deploy.sh [--force]
#   --force    Полная пересборка без кэша (пересоздаёт контейнер)
#   (по умолчанию) Инкрементальный деплой (пересборка образа, рестарт контейнера)

set -e

FORCE=false
for arg in "$@"; do
    case $arg in
        --force) FORCE=true; shift ;;
        *) echo "Usage: $0 [--force]"; exit 1 ;;
    esac
done

echo "🚀 Starting downloads.quantumart.ru deploy..."
if [ "$FORCE" = true ]; then
    echo "🔥 MODE: Full clean rebuild (--force)"
else
    echo "⚡ MODE: Incremental deploy (default)"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.production.yml"
DOMAIN="downloads.quantumart.ru"
PORT=3021
CONTAINER="downloads-web"

print_status() { echo "✅ $1"; }
print_error()  { echo "❌ ERROR: $1"; exit 1; }

cd "$SCRIPT_DIR"
echo "📁 Project root: $SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
    print_error "docker not found on PATH."
fi
print_status "Pre-flight checks passed"

echo ""
echo "📥 Step 1: Pulling latest changes..."

# Авторизация для git на этом VPS.
#
# Глобальный конфиг (/root/.gitconfig) содержит credential.helper=store, и его
# ~/.git-credentials отдаёт токен, созданный под другой репозиторий — на
# anisimovs/downloads GitHub отвечает 403. Helper'ы опрашиваются по очереди, и
# первый ответивший выигрывает, поэтому глобальный store перебивает локальный.
#
# Обходим это двумя средствами:
#   GIT_CONFIG_GLOBAL=/dev/null  — выбрасывает глобальный конфиг целиком,
#                                  store перестаёт участвовать (общий файл на
#                                  общем сервере не трогаем);
#   credential.helper через -c  — единственный оставшийся источник кредов.
# Значение токена при этом нигде не сохраняется: читается из .credentials.env.
if [ -z "${GH_TOKEN:-}" ]; then
    CREDS_FILE="$SCRIPT_DIR/../.credentials.env"
    if [ -f "$CREDS_FILE" ]; then
        set -a; . "$CREDS_FILE"; set +a
    fi
fi

GH_HELPER='!f() { echo username=x-access-token; echo password="$GH_TOKEN"; }; f'

# Первый деплой идёт в ещё пустой репозиторий: ветки upstream нет, и обычный
# `git pull` падает с "no tracking information". Не прерываем деплой из-за этого —
# кода на диске уже достаточно, чтобы собрать образ.
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    PRE_PULL_HASH=$(git rev-parse HEAD)
    GIT_CONFIG_GLOBAL=/dev/null git -c credential.helper="$GH_HELPER" pull
    POST_PULL_HASH=$(git rev-parse HEAD)
    if [ "$PRE_PULL_HASH" = "$POST_PULL_HASH" ]; then
        echo "ℹ️  Изменений нет — продолжаю пересборку (инкрементальный деплой)"
    else
        print_status "Получено обновление: $PRE_PULL_HASH → $POST_PULL_HASH"
    fi
else
    echo "ℹ️  No upstream branch configured — собираю из текущего состояния рабочей копии"
fi

echo ""
echo "🐳 Step 2: Docker compose..."
if [ "$FORCE" = true ]; then
    echo "🔥 FORCE MODE: Stopping container, cleaning build cache..."
    docker compose -f "$COMPOSE_FILE" down --remove-orphans
    docker builder prune -af
    echo "🔥 Building from scratch..."
    docker compose -f "$COMPOSE_FILE" build --no-cache --pull
    docker compose -f "$COMPOSE_FILE" up -d --force-recreate
else
    echo "⚡ NORMAL MODE: Rebuilding image (with cache)..."
    docker compose -f "$COMPOSE_FILE" build web
    docker compose -f "$COMPOSE_FILE" up -d --force-recreate web
fi
print_status "Container started"

echo ""
echo "🏥 Step 3: Health check..."
sleep 5
WEB_CONTAINER=$(docker ps --filter "name=$CONTAINER" --format "{{.Names}}" | head -1)
if [ -z "$WEB_CONTAINER" ]; then
    print_error "Container not running. Check: docker compose -f $COMPOSE_FILE ps"
fi
echo "📋 web: $WEB_CONTAINER"
docker logs "$WEB_CONTAINER" --tail 30

echo ""
echo "🌐 Step 4: HTTP smoke test..."
echo "  Loopback (Docker direct):"
# /archive/ — каталог, поэтому именно со слэшем: без него nginx ответит 301.
for path in / /index.html /archive/ /css/demosite.min.css /js/demosite.min.js /fonts/Raleway-Extrabold-800.woff2 /site.webmanifest /robots.txt /sitemap.xml; do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT$path")
    echo "    $path → HTTP $code"
    if [ "$code" != "200" ]; then
        print_error "Loopback: expected 200, got $code on $path"
    fi
done

echo "  404 (error_page):"
code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/definitely-missing-page")
echo "    /definitely-missing-page → HTTP $code (ожидается 404)"
if [ "$code" != "404" ]; then
    print_error "Expected 404 for missing page, got $code"
fi

echo "  External (через хостовый nginx, если уже настроен):"
for path in / /archive/; do
    code=$(curl -sk -o /dev/null -w '%{http_code}' "https://$DOMAIN$path" || echo "000")
    echo "    $path → HTTP $code"
    if [ "$code" != "200" ]; then
        echo "    ⚠️  ожидался 200, получили $code — нормально, если DNS/сертификат ещё не переключены"
    fi
done
print_status "HTTP smoke test done"

echo ""
echo "🎉 Deploy complete!"
docker compose -f "$COMPOSE_FILE" ps
echo ""
echo "💡 Полезные команды:"
echo "   Логи:           docker logs $WEB_CONTAINER -f"
echo "   Рестарт:        docker compose -f $COMPOSE_FILE restart web"
echo "   Reload nginx:   sudo systemctl reload nginx"
