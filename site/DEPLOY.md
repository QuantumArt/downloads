# Деплой downloads.quantumart.ru на VPS

Инструкция для ручного выполнения на VPS (`root@timeweb`, 217.198.6.66) — том
же, где уже развёрнут sidus. Паттерн тот же: Docker-контейнер со статикой +
хостовый nginx как reverse proxy.

Репозиторий: https://github.com/anisimovs/downloads (приватный, папка `site/`).

> **Ключевое отличие от sidus.** Домен `downloads.quantumart.ru` — не поддомен
> `sqlhub.pro`, а отдельная зона. Общий SAN-сертификат `ts.sqlhub.pro` покрывает
> только `*.sqlhub.pro`, поэтому **нужен отдельный сертификат** (шаг 2). И
> A-запись домена указывает на кластер QuantumArt `91.216.147.7` — её нужно
> переключить на `217.198.6.66` (шаг 0). Пока это не сделано, сайт продолжит
> отдаваться со старого кластера.

## 0. DNS — переключить A-запись (до всего остального)

Сейчас:

```
downloads.quantumart.ru. → cluster.quantumart.ru. → 91.216.147.7
```

Нужно, чтобы домен смотрел на этот VPS:

```
downloads.quantumart.ru. → 217.198.6.66
```

Если зона обслуживается через Cloudflare — A-запись в панели Cloudflare, затем
дождаться распространения (`dig +short downloads.quantumart.ru` должен вернуть
`217.198.6.66`).

> Порядок именно такой: сначала сертификат (шаг 2), потом nginx, и только потом
> переключение DNS. Иначе домен начнёт отдавать сертификат `ts.sqlhub.pro`,
> который для него невалиден, и посетители увидят предупреждение TLS.

Порт **3021** свободен (соседний с sidus на 3020). Заняты: 3001, 3010, 3020,
5000, 7700, 8090, 9117. Проверь перед стартом:

```bash
docker ps --format '{{.Names}}\t{{.Ports}}'
ss -ltnp | grep 3021
```

## 1. Выпустить сертификат для домена

Cloudflare DNS-01. Credentials лежат в проекте на VPS:

```
~/downloads/.secrets/cloudflare.ini
```

```bash
sudo certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials ~/downloads/.secrets/cloudflare.ini \
  -d downloads.quantumart.ru \
  --cert-name downloads.quantumart.ru
```

Проверить:

```bash
sudo certbot certificates
# Certificate Name: downloads.quantumart.ru
#   Domains: downloads.quantumart.ru
```

Автопродление уже настроено через `certbot.timer`.

## 2. Клонировать репозиторий

> **Внимание: репозиторий `anisimovs/downloads` пока пуст** — `git clone`
> скачает репозиторий без единого файла, и `site/` на сервере не появится.
> Проверь: `git -C ~/downloads log --oneline` — если вывод пустой, сначала
> нужен первый коммит (см. ниже), и только потом клон или `rsync`.

Проект живёт в `~/downloads` (там же `.secrets/cloudflare.ini` из шага 1):

```bash
cd ~/downloads
git clone https://github.com/anisimovs/downloads.git   # только если ещё не клонирован
cd downloads/site
```

Если каталог `~/downloads` уже существует (как сейчас) — репозиторий там уже
инициализирован, нужен только код проекта:

```bash
cd ~/downloads
ls site/ 2>/dev/null || echo "кода проекта ещё нет — нужен git pull после первого коммита"
```

### Первый коммит (если репозиторий пуст)

С локальной машины, где проект уже собран:

```bash
cd /Users/anisimovs/Projects/downloads
git init
git add -A
git status              # убедись, что .credentials.env НЕ в списке
git commit -m "Static mirror of downloads.quantumart.ru: Jinja2 build, Docker/nginx, deploy runbook"
git remote add origin https://github.com/anisimovs/downloads.git
git push -u origin main
```

`.credentials.env` и `.secrets/` должны остаться вне индекса — проверь по
`.gitignore` перед `git add`.

Для приватного репозитория нужен PAT (`GH_TOKEN` в `.credentials.env` в корне
проекта). Чтобы `git pull` в `deploy.sh` не зависал на запрос пароля, настрой
credential-helper один раз:

```bash
set -a && . .credentials.env && set +a
git config credential.helper '!f() { echo username=x-access-token; echo password="$GH_TOKEN"; }; f'
```

Значение токена при этом нигде не сохраняется — оно читается из
`.credentials.env` (файл в `.gitignore`).

Если репозиторий уже клонирован — просто `cd` туда, `deploy.sh` сам сделает
`git pull`.

## 3. Поднять контейнер

```bash
cd ~/downloads/site
./deploy.sh
```

Скрипт: `git pull` → сборка образа (`python:3.12-slim` → `build.py` → `dist/`,
затем `nginx:1.27-alpine` отдаёт статику) → контейнер `downloads-web` на
`127.0.0.1:3021` → health-check → smoke-тест по HTTP.

## 4. Подключить хостовый nginx

```bash
sudo cp nginx/downloads /etc/nginx/sites-available/downloads
sudo ln -s /etc/nginx/sites-available/downloads /etc/nginx/sites-enabled/downloads
sudo nginx -t
sudo systemctl reload nginx
```

## 5. Проверка

```bash
# локально, минуя DNS — контейнер и прокси
curl -I http://127.0.0.1:3021/
curl -I http://127.0.0.1:3021/archive/

# через хостовый nginx, ещё до переключения DNS (резолвим вручную)
curl -I --resolve downloads.quantumart.ru:443:127.0.0.1 \
  https://downloads.quantumart.ru/

# после переключения DNS
curl -I https://downloads.quantumart.ru/
curl -I https://downloads.quantumart.ru/archive/
```

Все должны вернуть `HTTP/2 200`. Для `/archive/` важно наличие слэша — без него
nginx отвечает `301` на канонический адрес.

Проверить, что отдаётся наш контейнер, а не старый кластер:

```bash
curl -s https://downloads.quantumart.ru/ | sha256sum
# ожидается 2d3eb3e8b6e087d3... (первые 16 символов sha256 главной страницы)
```

## Обновление сайта в будущем

```bash
cd ~/downloads/site
./deploy.sh            # инкрементально
./deploy.sh --force    # полная пересборка без кэша
```

## Откат

Если что-то пошло не так:

```bash
cd ~/downloads/site
docker compose -f docker-compose.production.yml down
sudo rm /etc/nginx/sites-enabled/downloads
sudo nginx -t && sudo systemctl reload nginx
# и вернуть A-запись на 91.216.147.7
```
