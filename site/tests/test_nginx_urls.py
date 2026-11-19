#!/usr/bin/env python3
r"""Тесты правил nginx для URL продукта.

Оригинал (ASP.NET) отвечает 200 на обоих вариантах каждого URL:
/QP8 и /QP8/, /archive и /archive/, /DPC и /DPC/ — все 200. Статика так
не умеет: каталог без слэша nginx уводит редиректом 301, а файл с
каталоговым URL (/DPC/) вообще не находится — 404. Поэтому в nginx
введено отдельное правило, и набор страниц в нём должен совпадать с
фактическими страницами сборки.

Тест проверяет именно ВОЗВРАЩАЕМЫЕ значения разбора конфига, а не то,
что две стороны согласованы между собой: сверка конфига с исходниками
страниц иначе осталась бы довольной опечаткой в самом списке.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONF = ROOT / "nginx" / "default.conf"
PAGES_DIR = ROOT / "src" / "pages"

# Правило со страницами: список имён в (?<page>...).
PAGE_RULE = re.compile(
    r"location\s+~\s+\^/\(\?<page>(?P<pages>[^)]+)\)/\?\$",
    re.DOTALL,
)

# Страницы, которых нет в src/pages: главная и 404 — не продуктовые,
# archive собирается шаблоном Jinja.
EXTRA_PAGES = {"archive"}

UNESCAPE = re.compile(r"\\(.)")


def parse_pages(conf_text):
    """Список страниц из правила nginx.

    Имена в конфиге экранированы (DPC.Impact с экранированной точкой),
    поэтому снимаем экранирование: сравнивать надо с именами каталогов
    сборки, а не с их regex-видом.
    """
    m = PAGE_RULE.search(conf_text)
    assert m, "в конфиге нет правила для страниц (location ~ ^/(?<page>...)/?$)"
    names = {UNESCAPE.sub(r"\1", p.strip()) for p in m.group("pages").split("|")}
    return names, m


# Блок, где живут сами .html. Ищем именно «location ... .html$ {»,
# а не первое вхождение «.html$»: в комментариях оно тоже встречается.
HTML_RULE = re.compile(r"location[^{]*\.html\$\s*\{(?P<body>[^}]*)\}", re.DOTALL)


def html_rule_span(conf_text):
    """Границы блока, где живут сами .html."""
    m = HTML_RULE.search(conf_text)
    assert m, "в конфиге нет блока location ... .html$ { }"
    return m.start(), m.start(), m.end(), m.group("body")


def expected_pages():
    """Страницы, которые реально собираются."""
    pages = set(EXTRA_PAGES)
    for item in PAGES_DIR.iterdir():
        if item.is_file() and item.suffix == ".html":
            pages.add(item.stem)
        elif item.is_dir():
            pages.add(item.name)
    return pages


def test_page_rule_matches_build():
    """Список страниц в правиле == страницы, которые есть в сборке."""
    conf = CONF.read_text(encoding="utf-8")
    in_conf, _ = parse_pages(conf)
    expected = expected_pages()
    missing = expected - in_conf
    extra = in_conf - expected
    assert not missing, f"страницы есть в сборке, но нет в правиле nginx: {sorted(missing)}"
    assert not extra, f"в правиле nginx есть несуществующие страницы: {sorted(extra)}"
    assert len(in_conf) == 12, f"ожидалось 12 продуктовых страниц, в правиле {len(in_conf)}"


def test_page_rule_before_html_rule():
    """Правило страниц идёт раньше правила .html, иначе перехватит кеширование."""
    conf = CONF.read_text(encoding="utf-8")
    _, page_m = parse_pages(conf)
    idx, _, _, _ = html_rule_span(conf)
    assert page_m.start() < idx, (
        "правило страниц должно идти раньше блока .html, "
        "иначе внутренний редирект на /DPC.html перехватит кеширование"
    )


def test_html_rule_is_internal():
    """Прямые /QP8.html закрыты: на оригинале они дают 404."""
    conf = CONF.read_text(encoding="utf-8")
    _, _, _, body = html_rule_span(conf)
    assert "internal;" in body, (
        "блок .html должен быть internal — иначе /QP8.html отдаст 200, "
        "хотя на оригинале там 404"
    )
    assert "no-cache" in body, "в блоке .html должен остаться Cache-Control no-cache"


def test_rule_does_not_catch_assets():
    """Правило страниц не перехватывает каталоги ассетов."""
    conf = CONF.read_text(encoding="utf-8")
    in_conf, _ = parse_pages(conf)
    for asset_dir in ("css", "js", "fonts", "img", "images"):
        assert asset_dir not in in_conf, (
            f"в правиле страниц не должно быть {asset_dir!r} — "
            "иначе ассеты перестанут отдаваться"
        )


def test_all_variants_in_container():
    """Живая проверка в контейнере: оба варианта URL дают 200.

    Требует docker. Если его нет — тест честно помечается как пропущенным,
    а не как пройденным.
    """
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        return "SKIP: docker недоступен"
    subprocess.run(["docker", "rm", "-f", "dl-urltest"], capture_output=True, timeout=60)
    build = subprocess.run(
        ["docker", "build", "-t", "dl-urltest:latest", str(ROOT)],
        capture_output=True, text=True, timeout=1800,
    )
    if build.returncode != 0:
        return "SKIP: образ не собрался (" + build.stderr.strip()[-200:] + ")"
    subprocess.run(
        ["docker", "run", "-d", "--name", "dl-urltest", "-p", "8097:80", "dl-urltest:latest"],
        capture_output=True, timeout=120,
    )
    try:
        import time
        import urllib.error
        import urllib.request

        time.sleep(2)
        pages = sorted(expected_pages())
        bad = []
        for page in pages:
            for path in (f"/{page}", f"/{page}/"):
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:8097{path}", timeout=15
                    ) as resp:
                        code = resp.status
                except urllib.error.HTTPError as e:
                    code = e.code
                except Exception:  # noqa: BLE001
                    code = 0
                if code != 200:
                    bad.append(f"{path} -> {code}")
        assert not bad, "не 200: " + ", ".join(bad)

        # Каталоги ассетов (/css/, /js/) на оригинале дают 404 — ASP.NET их
        # не знает. В статике без явного правила nginx отвечал бы 403.
        asset_bad = []
        for directory in ("css", "js", "fonts", "img", "images"):
            path = "/" + directory + "/"
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:8097" + path, timeout=15
                ) as resp:
                    code = resp.status
            except urllib.error.HTTPError as e:
                code = e.code
            except Exception:  # noqa: BLE001
                code = 0
            if code != 404:
                asset_bad.append(path + " -> " + str(code))
        assert not asset_bad, "каталоги ассетов должны давать 404: " + ", ".join(asset_bad)
    finally:
        subprocess.run(["docker", "rm", "-f", "dl-urltest"], capture_output=True, timeout=60)
    return None


def run_tests():
    tests = [
        test_page_rule_matches_build,
        test_page_rule_before_html_rule,
        test_html_rule_is_internal,
        test_rule_does_not_catch_assets,
        test_all_variants_in_container,
    ]
    failed = 0
    skipped = 0
    for fn in tests:
        try:
            note = fn()
            if note:
                skipped += 1
                print(f"  ⏭  {fn.__name__}: {note}")
            else:
                print(f"  ✅ {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  ❌ {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  💥 {fn.__name__}: {type(e).__name__}: {e}")
    passed = len(tests) - failed - skipped
    print(f"\n{passed}/{len(tests)} тестов прошли, пропущено: {skipped}")
    if skipped:
        print("⚠️  часть проверок пропущена — прогон неполный")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run_tests())
