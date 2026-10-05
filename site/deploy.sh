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

# Список «сирот» compose-проекта. Не удаляем: на этом VPS из соседних
# каталогов крутятся чужие сервисы, и они не наши.
ORPHANS=$(docker compose -f "$COMPOSE_FILE" ps -a --filter status=exited --format '{{.Names}}' 2>/dev/null)
if [ -n "$ORPHANS" ]; then
    echo "ℹ️  Остановленные контейнеры этого compose-проекта (не трогаем):"
    echo "$ORPHANS" | sed 's/^/    /'
fi
print_status "Pre-flight checks passed"

echo ""
echo "📥 Step 1: Pulling latest changes..."

# Репозиторий публичный (https://github.com/QuantumArt/downloads), токен не
# нужен — код тянется анонимно. Но отбрасывать глобальный конфиг всё равно
# нужно: на этом VPS в /root/.gitconfig живёт credential.helper=store, и его
# ~/.git-credentials подставит чужой токен даже там, где анонимный доступ
# разрешён. GitHub на такой заголовок отвечает 401/403, и pull падает.
#
#   GIT_CONFIG_GLOBAL=/dev/null  — store выпадает из авторизации (общий файл
#                                  на общем сервере не трогаем);
#   GIT_CONFIG_SYSTEM=/dev/null  — то же для /etc/gitconfig;
#   GIT_TERMINAL_PROMPT=0        — pull никогда не встанет ждать пароль.
REPO_URL="https://github.com/QuantumArt/downloads.git"
ACTUAL_REMOTE=$(git remote get-url origin 2>/dev/null || echo "<не задан>")
if [ "$ACTUAL_REMOTE" != "$REPO_URL" ]; then
    echo "⚠️  origin указывает на $ACTUAL_REMOTE, ожидался $REPO_URL"
    echo "    Правится один раз вручную: git remote set-url origin $REPO_URL"
fi

# Спрашиваем УДАЛЁННЫЙ репозиторий, а не локальную ветку: после смены remote
# на пустой репозиторий локальный origin/main ещё остаётся (с прошлого
# remote), и проверка «есть ли upstream» дала бы неверный ответ. На пустом
# remote `git pull` падает с "no such ref was fetched", а set -e убил бы деплой.
REMOTE_MAIN=$(GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 \
              git ls-remote --heads origin main 2>/dev/null)

if [ -n "$REMOTE_MAIN" ] && git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    PRE_PULL_HASH=$(git rev-parse HEAD)
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 git pull
    POST_PULL_HASH=$(git rev-parse HEAD)
    if [ "$PRE_PULL_HASH" = "$POST_PULL_HASH" ]; then
        echo "ℹ️  Изменений нет — продолжаю пересборку (инкрементальный деплой)"
    else
        print_status "Получено обновление: $PRE_PULL_HASH → $POST_PULL_HASH"
    fi
else
    echo "ℹ️  На remote нет ветки main (репозиторий пуст или её ещё не залили)"
    echo "    Собираю из текущего состояния рабочей копии."
fi

echo ""
echo "🐳 Step 2: Docker compose..."
if [ "$FORCE" = true ]; then
    echo "🔥 FORCE MODE: Stopping container, cleaning build cache..."
    # ВНИМАНИЕ: никаких --remove-orphans. На этом VPS из этого же каталога
    # запущены контейнеры других проектов — например nuget-baget (BaGet,
    # приватный NuGet-фид на 127.0.0.1:3022, restart: unless-stopped).
    # docker compose считает «сиротами» контейнеры с тем же compose-проектом,
    # но не перечисленные в нашем файле, и --remove-orphans удалил бы их
    # вместе с их volume. Останавливаем только свой сервис.
    docker compose -f "$COMPOSE_FILE" down
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
# Слэш обязателен для каталоговых страниц: /archive, /Angular и т.д. без слэша
# nginx отдаёт 301 на канонический адрес. Все страницы — и файловые
# (/QP8, /DPC, /search), и каталоговые (/Angular/, /React/, /GraphQL/).
for path in / /index.html /archive/ /QP8 /QP8_PG /DPC /Widgets /search /QP79 \
            /GraphQL/ /DPC.Impact/ /DPC.PdfGenerator/ /Angular/ /React/ \
            /css/demosite.min.css /js/demosite.min.js /fonts/Raleway-Extrabold-800.woff2 \
            /site.webmanifest /images/icon-medals.png /robots.txt /sitemap.xml; do
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
