#!/usr/bin/env python3
"""Сборка статического зеркала downloads.quantumart.ru.

Использование:
    pip install jinja2
    python3 build.py            # собрать сайт в ./dist
    python3 build.py --serve    # собрать и запустить локальный сервер http://localhost:8000

Структура — по образцу проекта sidus: контент в src/data/*.json,
шаблоны в src/templates/, ассеты в src/static/. Спрайт иконок
(src/static/img/sprite.svg) инлайнится в <body> — от него зависят
<use xlink:href="#...">, поэтому подключать его файлом нельзя.

Продуктовые страницы (/QP8, /DPC, /Angular/ и т.д.) лежат в src/pages/
и копируются в dist/ дословно. Они почти не меняются, а в оригинале
у каждой своя разметка (блоки «Продукт / Сертификаты / Модули /
Демо-сайт / Документация», карта в блоке контактов, achievement-label).
Шаблонизировать их ради правки контента смысла нет, а дословная копия
гарантирует побайтовое совпадение с оригиналом. Главная и архив
остались на Jinja — их содержимое действительно редактируется.
"""
import datetime as dt
import json
import shutil
import sys
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Undefined

ROOT = Path(__file__).parent
SRC = ROOT / "src"
DIST = ROOT / "dist"


def load(name):
    return json.loads((SRC / "data" / name).read_text(encoding="utf-8"))


# slug, template, out path, <title>, meta description
# У главной на источнике <title> и description отсутствуют — так и оставляем
# (см. шаблон index.html: блок meta пуст), иначе копия будет отличаться.
PAGES = [
    ("index", "index.html", "index.html", None, None),
    ("archive", "archive.html", "archive/index.html", "archive", ""),
    ("404", "404.html", "404.html", "404", "404"),
]


def build():
    t0 = time.time()
    site = load("site.json")
    index = load("index.json")
    archive = load("archive.json")
    sprite = (SRC / "static/img/sprite.svg").read_text(encoding="utf-8").strip()

    env = Environment(loader=FileSystemLoader(SRC / "templates"), undefined=Undefined,
                      autoescape=True, trim_blocks=False, lstrip_blocks=False)

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(SRC / "static", DIST)
    # Спрайт нужен только как инлайн в HTML — отдельным файлом не отдаём.
    (DIST / "img/sprite.svg").unlink(missing_ok=True)

    today = dt.date.today()
    build_id = today.strftime("%Y%m%d") + str(int(t0) % 10000)
    common = dict(site=site, sprite=sprite, build_id=build_id, year=today.year)

    sitemap = []
    for slug, tpl, out, title, desc in PAGES:
        blocks = []
        if slug == "index":
            blocks = index["blocks"]
        elif slug == "archive":
            blocks = archive["blocks"]
        # Число пустых строк между зоной SiteHeaderZone и <header> на источнике
        # различается: у главной их две, у /archive/ — три. Пробелы CMS, не
        # разметка, но для побайтового совпадения передаём точное значение.
        zone_gap = "\n    \n\n\n" if slug == "archive" else "\n    \n\n"
        zone_gap += "<header"

        # Блок <head> между meta-format-detection и favicon-ссылками.
        # На источнике он есть только у /archive/ (description + keywords + title),
        # и после него идёт пустая строка. Точная строка — иначе Jinja схлопнет
        # пустой блок и каталог сдвинется на строку.
        head_extra = ""
        if desc is not None or title:
            head_extra = (f'    <meta name="description" content="{desc or ""}" />\n'
                          f'    <meta name="keywords" content="" />\n'
                          f'    <title>{title or ""}</title>\n\n')

        # 404 — та же разметка, что у главной, но без списка ссылок
        html = env.get_template(tpl).render(
            **common, blocks=blocks, page=slug, head_extra=head_extra, zone_gap=zone_gap,
            page_title=title if title else "", page_description=desc or "")
        target = DIST / out
        target.parent.mkdir(parents=True, exist_ok=True)
        # Jinja срезает финальный перевод строки, а комментарий в шапке шаблона
        # оставляет ведущую пустую строку — в источнике нет ни того, ни другого.
        target.write_text(html.strip("\n") + "\n", encoding="utf-8")
        if slug != "404":
            sitemap.append("" if slug == "index" else "archive/")

    # Продуктовые страницы копируются дословно из src/pages/.
    # Имена файлов повторяют структуру URL оригинала: /QP8 -> QP8.html,
    # /Angular/ -> Angular/index.html. Их отдаёт try_files в nginx.
    pages_dir = SRC / "pages"
    copied = 0
    if pages_dir.is_dir():
        for src in sorted(pages_dir.rglob("*.html")):
            rel = src.relative_to(pages_dir)
            dst = DIST / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            copied += 1
            if rel.stem == "index":
                # /Angular/ — с завершающим слэшем, как в оригинале
                sitemap.append(str(rel.parent).replace("\\", "/") + "/")
            else:
                sitemap.append(str(rel).replace("\\", "/")[:-len(".html")])

    robots = "User-agent: *\nAllow: /\n"
    if site["site_url"]:
        urls = "\n".join(
            f"  <url><loc>{site['site_url']}/{u}</loc><lastmod>{today.isoformat()}</lastmod></url>"
            for u in sitemap)
        (DIST / "sitemap.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n',
            encoding="utf-8")
        robots += f"\nSitemap: {site['site_url']}/sitemap.xml\n"
    (DIST / "robots.txt").write_text(robots, encoding="utf-8")

    print(f"Собрано {len(PAGES) - 1} шаблонных + {copied} дословных страниц "
          f"в {DIST} за {time.time() - t0:.2f} с")


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        import functools
        import http.server
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
        print("Локальный сервер: http://localhost:8000")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()
