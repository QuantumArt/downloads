# Внешние ссылки портала downloads.quantumart.ru
Полный перечень внешних ссылок зеркала: **170 ссылок на 140 уникальных
адресов, 7 доменов**. Снято скриптом `site/tools/verify_mirror.py` с живого
сайта 2026-10-05 и сверено с оригиналом: **наборы URL и адресов страниц, где
они встречаются, совпадают полностью**.

Зеркало эти файлы не хранит. Оно воспроизводит только страницы и ссылки;
сами дистрибутивы лежат на внешних хостингах, как и на оригинале.

---

## 1. Сводка по доменам

| Домен | Ссылок | Уникальных URL | Доля | Доступность | Оригинал |
|---|---:|---:|---:|---|---:|
| `storage.quantumart.ru` | 108 | 98 | 64% | 98/98 → 302 | 108 |
| `github.com` | 34 | 27 | 20% | 27/27 → 200 | 34 |
| `quantumart.ru` | 13 | 1 | 8% | 1/1 → 200 | 13 |
| `reestr.digital.gov.ru` | 7 | 7 | 4% | 7 → 000 | 7 |
| `www.npmjs.com` | 5 | 5 | 3% | 1×301, 4×403 | 5 |
| `wiki.qpublishing.ru` | 2 | 1 | 1% | 1 → 000 | 2 |
| `nuget.qsupport.ru` | 1 | 1 | 1% | 1/1 → 200 | 1 |
| **Всего** | **170** | **140** | 100% | | **170** |

### Что за домены

- **`storage.quantumart.ru`** — Хранилище файлов QP: дистрибутивы, базы данных, руководства, архивы. Отдаёт `302` на ассеты GitHub Release `QuantumArt/storage@v1`. До переноса 2026-10-05 эти ссылки вели на внешний `storage.qp.qsupport.ru`.
- **`github.com`** — Лицензии (MPL-2.0), репозитории исходников, монорепозитории модулей.
- **`quantumart.ru`** — Ссылка на главную в логотипе. Повторяется в шапке всех 13 страниц, поэтому 13 вхождений на 1 уникальный URL.
- **`reestr.digital.gov.ru`** — Реестр российского ПО — achievement-label «Зарегистрированы в Росреестре».
- **`www.npmjs.com`** — npm-пакеты модулей QP8.
- **`wiki.qpublishing.ru`** — Старая онлайн-документация QP7. Одна из двух ссылок — та самая битая: путь GitHub без префикса `github.com`, 404 и на оригинале.
- **`nuget.qsupport.ru`** — nuget-источник пакетов QP.

---

## 2. Операционное следствие

### До переноса (2026-10-05, история)

108 из 170 ссылок (64%) вели на `storage.qp.qsupport.ru` — внешний хост, который
зеркало не хранило. Страница жила на нашем VPS, а кнопки «Скачать» — на чужом
хостинге. Отказ того хостинга оставил бы портал живым с мёртвыми ссылками.

### После переноса (сейчас)

**Внешнего зависимого хостинга для файлов больше нет.** 98 уникальных ссылок
ведут на `storage.quantumart.ru` — наш же VPS, который отдаёт `302` на ассеты
GitHub Release `QuantumArt/storage@v1`.

Цепочка для пользователя:

```
браузер → storage.quantumart.ru/downloads/QP8.zip → 302 →
github.com/QuantumArt/storage/releases/download/v1/QP8.zip → 302 → файл
```

Остаточный риск теперь другой и меньший: файлы лежат в **публичном** GitHub
Release, а не на нашем VPS. Отвал нашего nginx не убьёт ссылки — хранилище
продолжит отдавать файлы и по прямым адресам GitHub. При этом место на диске
VPS не занимается: 1,47 ГБ лежат в GitHub, а не в контейнере.

Проверено 2026-10-05: все 98 уникальных ссылок отдают `302`.

Три файла пришлось переименовать (кириллическая «с», двойная точка, двойной
слэш) — причины в `site/src/data/link-migration.json`.

---

## 3. Доступность целей

HEAD-запросы к 140 уникальным адресам, с приведением редиректов:

| Домен | Результат | Комментарий |
|---|---|---|
| `storage.quantumart.ru` | 98/98 → 302 | все файлы ведут на ассеты GitHub Release |
| `github.com` | 27/27 → 200 |  |
| `quantumart.ru` | 1/1 → 200 |  |
| `reestr.digital.gov.ru` | 7 → 000 | хост не отвечает с этой машины, даже с браузерным UA; вероятно ограничение по гео/IP |
| `www.npmjs.com` | 1×301, 4×403 | npmjs отдаёт 403 и на браузерный User-Agent — режет автоматические запросы, пакеты при этом живые |
| `wiki.qpublishing.ru` | 1 → 000 | хост не отвечает, даже с браузерным UA |
| `nuget.qsupport.ru` | 1/1 → 200 |  |

**`000` и `403` — не битые ссылки, а поведение внешних хостов.** Проверено с
браузерным User-Agent: `reestr.digital.gov.ru` и `wiki.qpublishing.ru` не
отвечают и на него, `npmjs.com` отдаёт 403 и на него.

На перенос это не влияет: наборы внешних ссылок побайтово совпадают с
оригиналом, значит ведут себя одинаково. Проверять их полезно, чтобы понимать,
что будет, если внешний ресурс исчезнет, — но к корректности зеркала
отношения не имеет.

---

## 4. Полный перечень по доменам

Вхождения — страницы, на которых встречается ссылка.

### `storage.quantumart.ru` — 108 ссылок, 98 уникальных

- `https://storage.quantumart.ru/downloads/QP7_Active_Directory.pdf`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/API_ASP.NET_ENG.pdf`
  - на: `/QP79`, `/archive/`
- `https://storage.quantumart.ru/downloads/Components.zip`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/Database.Pg.zip`
  - на: `/`, `/QP8_PG`
- `https://storage.quantumart.ru/downloads/Database.zip`
  - на: `/`, `/QP8_PG`
- `https://storage.quantumart.ru/downloads/Developer_Guide_ASP.NET_ENG.pdf`
  - на: `/QP79`, `/archive/`
- `https://storage.quantumart.ru/downloads/Editor_Guide_RUS.pdf`
  - на: `/QP79`, `/archive/`
- `https://storage.quantumart.ru/downloads/Help_to_QP7_Backend_Explorer_ENG.pdf`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/Help_to_QP7_Backend_Explorer_RUS.pdf`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/Multisite_Object_Loading.pdf`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/QA_LicenceInfo.zip`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/QP7_Installation_Guide_RUS.pdf`
  - на: `/QP79`, `/archive/`
- `https://storage.quantumart.ru/downloads/QP7_Notifications.pdf`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/QP7_OnScreen.pdf`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/QP7_Security_Model.pdf`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/QP7_Workflow.pdf`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/QP8.ConsoleDbUpdate.zip`
  - на: `/`
- `https://storage.quantumart.ru/downloads/QP8.ProductCatalog.Impact.zip`
  - на: `/DPC.Impact/`
- `https://storage.quantumart.ru/downloads/QP8.ProductCatalog.PdfGenerator.zip`
  - на: `/DPC.PdfGenerator/`
- `https://storage.quantumart.ru/downloads/QP8.ProductCatalog.Pg.zip`
  - на: `/DPC`
- `https://storage.quantumart.ru/downloads/QP8.ProductCatalog.zip`
  - на: `/DPC`
- `https://storage.quantumart.ru/downloads/QP8.Widgets.Pg.zip`
  - на: `/Widgets`
- `https://storage.quantumart.ru/downloads/QP8.Widgets.zip`
  - на: `/Widgets`
- `https://storage.quantumart.ru/downloads/QP8.zip`
  - на: `/QP8`
- `https://storage.quantumart.ru/downloads/QP8_CMS_Postgres_Pro.pdf`
  - на: `/QP8_PG`
- `https://storage.quantumart.ru/downloads/QP8_PG.zip`
  - на: `/QP8_PG`
- `https://storage.quantumart.ru/downloads/QP8_ProductCatalog_Postgres_Pro.pdf`
  - на: `/DPC`
- `https://storage.quantumart.ru/downloads/QPCodeClean.zip`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/QPDatabaseSqlRunner.zip`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/QPWebService.zip`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/QP_Setup_7.9.7.0.zip`
  - на: `/QP79`
- `https://storage.quantumart.ru/downloads/Quantumart.zip`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/Release_Notes_RUS.pdf`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/SQL_injection.pdf`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/configuration_file.pdf`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/demo_qp.zip`
  - на: `/`
- `https://storage.quantumart.ru/downloads/demosite_rus.tar.gz`
  - на: `/`
- `https://storage.quantumart.ru/downloads/demosite_rus_db.tar.gz`
  - на: `/`, `/Widgets`
- `https://storage.quantumart.ru/downloads/functional_char_angular.pdf`
  - на: `/Angular/`
- `https://storage.quantumart.ru/downloads/functional_char_graphql.pdf`
  - на: `/GraphQL/`
- `https://storage.quantumart.ru/downloads/functional_char_react.pdf`
  - на: `/React/`
- `https://storage.quantumart.ru/downloads/graphql-config.tar`
  - на: `/GraphQL/`
- `https://storage.quantumart.ru/downloads/graphql.tar.gz`
  - на: `/GraphQL/`
- `https://storage.quantumart.ru/downloads/install_angular.pdf`
  - на: `/Angular/`
- `https://storage.quantumart.ru/downloads/install_graphql.pdf`
  - на: `/GraphQL/`
- `https://storage.quantumart.ru/downloads/install_react.pdf`
  - на: `/React/`
- `https://storage.quantumart.ru/downloads/mapping.zip`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/process_angular.pdf`
  - на: `/Angular/`
- `https://storage.quantumart.ru/downloads/process_graphql.pdf`
  - на: `/GraphQL/`
- `https://storage.quantumart.ru/downloads/process_react.pdf`
  - на: `/React/`
- `https://storage.quantumart.ru/downloads/publishing.zip`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/qp-search-install-manifests.tar.gz`
  - на: `/search`
- `https://storage.quantumart.ru/downloads/qp-search.tar.gz`
  - на: `/search`
- `https://storage.quantumart.ru/downloads/qp.tar.gz`
  - на: `/QP8_PG`
- `https://storage.quantumart.ru/downloads/qp8-admin-man.pdf`
  - на: `/QP8`
- `https://storage.quantumart.ru/downloads/qp8-dev-man.pdf`
  - на: `/QP8`, `/QP8_PG`
- `https://storage.quantumart.ru/downloads/qp8-dpc-functional-requirements.pdf`
  - на: `/DPC`
- `https://storage.quantumart.ru/downloads/qp8-dpc-impact-functional-requirements.pdf`
  - на: `/DPC.Impact/`
- `https://storage.quantumart.ru/downloads/qp8-dpc-impact-user-man.pdf`
  - на: `/DPC.Impact/`
- `https://storage.quantumart.ru/downloads/qp8-dpc-pdf-functional-requirements.pdf`
  - на: `/DPC.PdfGenerator/`
- `https://storage.quantumart.ru/downloads/qp8-dpc-pdf-user-man.pdf`
  - на: `/DPC.PdfGenerator/`
- `https://storage.quantumart.ru/downloads/qp8-dpc-user-man.pdf`
  - на: `/DPC`
- `https://storage.quantumart.ru/downloads/qp8-editor-man.pdf`
  - на: `/QP8`, `/QP8_PG`
- `https://storage.quantumart.ru/downloads/qp8-functional-characteristics.pdf`
  - на: `/QP8`
- `https://storage.quantumart.ru/downloads/qp8-graphql-user-man.pdf`
  - на: `/GraphQL/`
- `https://storage.quantumart.ru/downloads/qp8-pg-admin-man.pdf`
  - на: `/QP8_PG`
- `https://storage.quantumart.ru/downloads/qp8-pg-functional-characteristics.pdf`
  - на: `/QP8_PG`
- `https://storage.quantumart.ru/downloads/qp8-product-catalog-database.tar.gz`
  - на: `/`, `/DPC`
- `https://storage.quantumart.ru/downloads/qp8-product-catalog-demo-manifests.tar.gz`
  - на: `/DPC`
- `https://storage.quantumart.ru/downloads/qp8-product-catalog-demo.tar.gz`
  - на: `/DPC`
- `https://storage.quantumart.ru/downloads/qp8-product-catalog-impact-linux.tar.gz`
  - на: `/DPC.Impact/`
- `https://storage.quantumart.ru/downloads/qp8-product-catalog-impact-manifests.tar.gz`
  - на: `/DPC.Impact/`
- `https://storage.quantumart.ru/downloads/qp8-product-catalog-linux.tar.gz`
  - на: `/DPC`
- `https://storage.quantumart.ru/downloads/qp8-product-catalog-manifests.tar.gz`
  - на: `/DPC`
- `https://storage.quantumart.ru/downloads/qp8-product-catalog-pdf-manifests.tar.gz`
  - на: `/DPC.PdfGenerator/`
- `https://storage.quantumart.ru/downloads/qp8-product-catalog-pdf.tar.gz`
  - на: `/DPC.PdfGenerator/`
- `https://storage.quantumart.ru/downloads/qp8-search-admin-user-man.pdf`
  - на: `/search`
- `https://storage.quantumart.ru/downloads/qp8-search-api-developer-man.pdf`
  - на: `/search`
- `https://storage.quantumart.ru/downloads/qp8-search-architecture.pdf`
  - на: `/search`
- `https://storage.quantumart.ru/downloads/qp8-search-functions.pdf`
  - на: `/search`
- `https://storage.quantumart.ru/downloads/qp8-search-installation-manual.pdf`
  - на: `/search`
- `https://storage.quantumart.ru/downloads/qp8-search-integration-developer-man.pdf`
  - на: `/search`
- `https://storage.quantumart.ru/downloads/qp8-search-processes.pdf`
  - на: `/search`
- `https://storage.quantumart.ru/downloads/qp8-widgets-admin-man.pdf`
  - на: `/Widgets`
- `https://storage.quantumart.ru/downloads/qp8-widgets-angular-user-man.pdf`
  - на: `/Angular/`
- `https://storage.quantumart.ru/downloads/qp8-widgets-dev-man.pdf`
  - на: `/Widgets`
- `https://storage.quantumart.ru/downloads/qp8-widgets-editor-man.pdf`
  - на: `/Widgets`
- `https://storage.quantumart.ru/downloads/qp8-widgets-functional-requirements.pdf`
  - на: `/Widgets`
- `https://storage.quantumart.ru/downloads/qp8-widgets-react_user_man.pdf`
  - на: `/React/`
- `https://storage.quantumart.ru/downloads/qpconfig.tar`
  - на: `/QP8_PG`
- `https://storage.quantumart.ru/downloads/source.zip`
  - на: `/archive/`
- `https://storage.quantumart.ru/downloads/template.zip`
  - на: `/search`
- `https://storage.quantumart.ru/downloads/widget-angular-config.tar`
  - на: `/Angular/`
- `https://storage.quantumart.ru/downloads/widget-angular.tar.gz`
  - на: `/Angular/`
- `https://storage.quantumart.ru/downloads/widget-config.tar`
  - на: `/Widgets`
- `https://storage.quantumart.ru/downloads/widget-react-config.tar`
  - на: `/React/`
- `https://storage.quantumart.ru/downloads/widget-react.tar.gz`
  - на: `/React/`
- `https://storage.quantumart.ru/downloads/widget.tar.gz`
  - на: `/Widgets`

### `github.com` — 34 ссылок, 27 уникальных

- `https://github.com/QuantumArt/QA.Core.Engine/blob/master/LICENSE`
  - на: `/Widgets`
- `https://github.com/QuantumArt/QA.DPC.PdfLayout/`
  - на: `/DPC.PdfGenerator/`
- `https://github.com/QuantumArt/QA.DPC.PdfServer/`
  - на: `/DPC.PdfGenerator/`
- `https://github.com/QuantumArt/QA.DPC/`
  - на: `/DPC`
- `https://github.com/QuantumArt/QA.DPC/tree/master/ImpactService`
  - на: `/DPC.Impact/`
- `https://github.com/QuantumArt/QA.Engine`
  - на: `/Widgets`
- `https://github.com/QuantumArt/QA.Engine.Administration.Core`
  - на: `/Widgets`
- `https://github.com/QuantumArt/QA.Engine.Administration.Core/blob/master/LICENSE`
  - на: `/Widgets`
- `https://github.com/QuantumArt/QA.Engine.DemositeRus`
  - на: `/Widgets`
- `https://github.com/QuantumArt/QA.Engine.DemositeRus.Angular`
  - на: `/Angular/`
- `https://github.com/QuantumArt/QA.Engine.DemositeRus.React`
  - на: `/React/`
- `https://github.com/QuantumArt/QA.Engine.OnScreenAdmin`
  - на: `/Widgets`
- `https://github.com/QuantumArt/QA.Search/`
  - на: `/search`
- `https://github.com/QuantumArt/QA.Search/blob/master/LICENSE`
  - на: `/search`
- `https://github.com/QuantumArt/QA.WidgetPlatform.API`
  - на: `/Angular/`, `/React/`
- `https://github.com/QuantumArt/QA.WidgetPlatform.API/blob/master/LICENCE`
  - на: `/Angular/`, `/React/`
- `https://github.com/QuantumArt/QA.WidgetPlatform.Bridge`
  - на: `/React/`
- `https://github.com/QuantumArt/QA.WidgetPlatform.Module`
  - на: `/React/`
- `https://github.com/QuantumArt/QA.WidgetPlatform.PageStructure.Angular`
  - на: `/Angular/`
- `https://github.com/QuantumArt/QA.WidgetPlatform.PageStructure.Angular/blob/master/LICENSE.txt`
  - на: `/Angular/`
- `https://github.com/QuantumArt/QA.WidgetPlatform.Shell`
  - на: `/React/`
- `https://github.com/QuantumArt/QA.WidgetPlatform.Shell.Core`
  - на: `/React/`
- `https://github.com/QuantumArt/QA.WidgetPlatform.Shell.Core/blob/master/LICENSE.txt`
  - на: `/React/`
- `https://github.com/QuantumArt/QP.GraphQL`
  - на: `/GraphQL/`
- `https://github.com/QuantumArt/QP.GraphQL/blob/master/LICENCE`
  - на: `/GraphQL/`
- `https://github.com/QuantumArt/QP/`
  - на: `/QP79`, `/QP8`, `/QP8_PG`
- `https://github.com/QuantumArt/QP/blob/master/LICENSE`
  - на: `/DPC`, `/QP79`, `/QP8`, `/QP8_PG`

### `quantumart.ru` — 13 ссылок, 1 уникальных

- `https://quantumart.ru/`
  - на: `/`, `/Angular/`, `/DPC`, `/DPC.Impact/`, `/DPC.PdfGenerator/`, `/GraphQL/`, `/QP79`, `/QP8`, `/QP8_PG`, `/React/`, `/Widgets`, `/archive/`, `/search`

### `reestr.digital.gov.ru` — 7 ссылок, 7 уникальных

- `https://reestr.digital.gov.ru/reestr/1806996/`
  - на: `/search`
- `https://reestr.digital.gov.ru/reestr/306200/`
  - на: `/QP8`
- `https://reestr.digital.gov.ru/reestr/310017/`
  - на: `/DPC`
- `https://reestr.digital.gov.ru/reestr/310018/`
  - на: `/Widgets`
- `https://reestr.digital.gov.ru/reestr/339448/`
  - на: `/QP8_PG`
- `https://reestr.digital.gov.ru/reestr/399398/`
  - на: `/DPC.Impact/`
- `https://reestr.digital.gov.ru/reestr/399402/`
  - на: `/DPC.PdfGenerator/`

### `www.npmjs.com` — 5 ссылок, 5 уникальных

- `http://www.npmjs.com/package/@quantumart/qa-engine-page-structure-angular`
  - на: `/Angular/`
- `https://www.npmjs.com/package/@quantumart/qp8-widget-platform-bridge`
  - на: `/React/`
- `https://www.npmjs.com/package/@quantumart/qp8-widget-platform-module`
  - на: `/React/`
- `https://www.npmjs.com/package/@quantumart/qp8-widget-platform-shell`
  - на: `/React/`
- `https://www.npmjs.com/package/@quantumart/qp8-widget-platform-shell-core`
  - на: `/React/`

### `wiki.qpublishing.ru` — 2 ссылок, 1 уникальных

- `http://wiki.qpublishing.ru/`
  - на: `/QP79`, `/archive/`

### `nuget.qsupport.ru` — 1 ссылок, 1 уникальных

- `http://nuget.qsupport.ru/nuget`
  - на: `/Widgets`

---

## 5. Как пересобрать этот перечень

```bash
cd site
python3 tools/verify_mirror.py \
    --live-url https://downloads.quantumart.ru \
    --original-url https://downloads.quantumart.ru \
    --original-host downloads.quantumart.ru \
    --original-ip 91.216.147.7
```

Скрипт выводит общее число внешних ссылок и сверенных внутренних, но полную
разбивку по доменам печатает вручную. Если список внешних целей нужно держать
в репозитории, стоит добавить в скрипт флаг `--dump-external`, который
выгружает перечень в markdown — тогда перечень не расходится с проверкой.

## 6. Связанные документы

- [`VERIFICATION.md`](VERIFICATION.md) — полный результат сверки: страницы,
  ассеты, ссылки, отличия от оригинала
- [`DEPLOY-SPEC.md`](DEPLOY-SPEC.md) — переиспользуемый runbook деплоя
