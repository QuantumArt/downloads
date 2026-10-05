# downloads.quantumart.ru — статическое зеркало

Клон портала загрузок QuantumArt (QP8 / QP7), собирается в статику и
раздаётся nginx в Docker-контейнере. Структура и паттерн деплоя — как у
проекта `sidus` на том же VPS.

## Что внутри

| Путь | Назначение |
|---|---|
| `build.py` | Сборка: Jinja2-шаблоны + `src/data/*.json` → `dist/` |
| `src/data/site.json` | Домен, контакты, id Яндекс.Метрики |
| `src/data/index.json` | Главная: 3 блока, 12 ссылок |
| `src/data/archive.json` | Архив: 4 блока, 26 ссылок |
| `src/templates/` | `base.html`, `index.html`, `archive.html`, `404.html`, `_macros.html` |
| `src/static/` | CSS, JS, шрифт, favicon-набор, webmanifest, SVG-спрайт |
| `nginx/default.conf` | Внутриконтейнерный nginx (отдаёт `dist/`) |
| `nginx/downloads` | Хостовый server block (TLS + reverse proxy) |
| `deploy.sh` | Деплой: pull → build → restart → smoke-тест |
| `DEPLOY.md` | Runbook для VPS |

## Локальная разработка

```bash
pip install jinja2
python3 build.py            # собрать в ./dist
python3 build.py --serve    # собрать и открыть http://localhost:8000
```

## Правка контента

Ссылки на документы лежат в JSON — правь их, а не HTML:

- `src/data/index.json` — главная (Продукты / Компоненты / Утилиты)
- `src/data/archive.json` — архив QP7
- `src/data/site.json` — телефон, домен, Метрика

Схема элемента:

```json
{
  "title": "QP8.CMS",
  "url": "/QP8",
  "target": "_blank",
  "tight_icon": false
}
```

`target` — `"_blank"` или пустая строка. `tight_icon: true` убирает пробел между
`</use>` и `</svg>` — так в оригинале сделано только для QP7.9 Framework.

Файлы дистрибутивов **не хранятся в репозитории**: ссылки ведут на внешний
`storage.qp.qsupport.ru`, как и на источнике.

## Тонкости, из-за которых шаблоны выглядят странно

Сайт — клон ASP.NET-страницы, и разметка повторяет её 1:1. Отсюда вещи,
которые иначе выглядят опечатками:

1. **Спрайт инлайнится в `<body>`**, а не подключается файлом: от него зависят
   все `<use xlink:href="#...">`. В `build.py` он вставляется с `| safe` —
   иначе `autoescape` разрушит SVG.
2. **Пустые строки и отступы вокруг зон CMS** (`<!--start zone ...-->`)
   различаются между главной и архивом. Они заданы в `build.py` переменными
   `zone_gap` и `head_extra` — Jinja схлопывает пустые блоки, а для побайтового
   совпадения это важно.
3. **На главной нет `<title>` и `description`** — так в источнике. Архив их
   имеет.
4. **Хвостовые пробелы в трёх подписях** на главной и отсутствие пробела в
   разметке QP7.9 Framework — часть исходного текста ссылок.

Проверить, что сборка не разъехалась с оригиналом:

```bash
python3 - <<'EOF'
import hashlib
for mine, orig in (("dist/index.html", "index.html"),
                   ("dist/archive/index.html", "archive/index.html")):
    print(mine, hashlib.sha256(open(mine,'rb').read()).hexdigest()[:16])
EOF
```

Эталонные значения: главная `2d3eb3e8b6e087d3`, архив `babbe87b71d7c1ab`.

## Деплой

Полный runbook — в [DEPLOY.md](DEPLOY.md). Коротко:

```bash
cd ~/downloads/site && ./deploy.sh
```

Домен обслуживается отдельным сертификатом (не покрывается `ts.sqlhub.pro`),
а его A-запись по умолчанию указывает на кластер QuantumArt — см. шаги 0–1
`DEPLOY.md`.
