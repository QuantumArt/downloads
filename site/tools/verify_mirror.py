#!/usr/bin/env python3
"""Побайтовая сверка статического зеркала с оригиналом.

Обходит оба сайта от стартового URL (только свой origin), сравнивает:
  * множество страниц,
  * содержимое каждой страницы по sha256,
  * каждый локальный ассет (css/js/png/webp/svg/шрифт) по sha256,
  * множество ссылок на каждой странице (внешние — по URL, внутренние — по
    нормализованному пути),
  * коды ответов для внутренних ссылок.

Зависимостей нет — только стандартная библиотека. Оригинал можно опросить
по IP с сохранением SNI и Host-заголовка, поэтому скрипт работает и после
того, как DNS зеркала уже переключён на новый сервер.

Использование:
    python3 verify_mirror.py \
        --live-url https://downloads.quantumart.ru \
        --original-url https://downloads.quantumart.ru \
        --original-host downloads.quantumart.ru \
        --original-ip 91.216.147.7

Код возврата: 0 — расхождений нет, 1 — есть расхождения, 2 — ошибка запуска.
"""

import argparse
import hashlib
import http.client
import json
import re
import socket
import ssl
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

# Расширения, которые считаем ассетами, а не страницами.
FORM_NOTICE = ""
FORM_ENDPOINT = ""

ASSET_RE = re.compile(
    r"\.(?:css|mjs|js|png|jpe?g|gif|webp|avif|svg|ico|woff2?|ttf|otf|eot|"
    r"pdf|zip|tar\.gz|tgz|webmanifest|txt|xml|map)$",
    re.I,
)

# Намеренные отличия зеркала: перенос ссылок на своё хранилище плюс
# переименования файлов. Описаны в src/data/link-migration.json рядом с
# содержимым сайта, чтобы ожидаемое и проверяемое лежало в одном месте.
MIGRATION_FILE = Path(__file__).resolve().parent.parent / "src/data/link-migration.json"

# Обработка формы — объявленное отступление, описанное кодом. Тот же модуль
# зовёт и сборка: пока правка живёт в одном месте, эталон sha256 точен.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import patches  # noqa: E402


def load_migration():
    if not MIGRATION_FILE.exists():
        raise SystemExit(f"НЕ НАЙДЕН {MIGRATION_FILE}")
    data = json.loads(MIGRATION_FILE.read_text(encoding="utf-8"))
    return data["old_prefix"], data["new_prefix"], data.get("renames", {})


def apply_migration(text, old_prefix, new_prefix, renames):
    """Приводит текст оригинала к тому, как выглядит зеркало."""
    for old_url, new_url in sorted(renames.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(old_url, new_url)
    return text.replace(old_prefix, new_prefix)

# Теги, которые самостоятельно тянут ресурсы.
RESOURCE_TAGS = ("img", "script", "source", "link", "iframe", "video", "audio")


CSS_URL_RE = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.I)


def css_asset_urls(css_text, base_path):
    """Ассеты, на которые ссылается CSS (url(...) в том числе).

    Без этого обход не видит шрифты: в разметке они упомянуты только
    preload'ом одного файла, а остальные живут в @font-face внутри CSS.
    Именно так в зеркале незаметно пропало 9 файлов шрифтов из 10.
    """
    out = set()
    for raw in CSS_URL_RE.findall(css_text):
        if raw.startswith(("data:", "http://", "https://", "//", "#")):
            continue
        # путь относительно каталога CSS-файла
        segs = [s for s in base_path.split("/") if s]
        segs = segs[:-1]  # убрать имя файла
        for part in raw.split("/"):
            if part == "..":
                if segs:
                    segs.pop()
            elif part not in (".", ""):
                segs.append(part)
        out.add("/" + "/".join(segs))
    return out


class LinkCollector(HTMLParser):
    """Собирает href (все, включая внешние) и src/srcset указанных тегов."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []
        self.resources = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "href" in a and a["href"]:
            self.hrefs.append(a["href"])
        if tag in RESOURCE_TAGS:
            for key in ("src", "srcset"):
                if a.get(key):
                    # srcset: "url 1x, url 2x" — берём только URL
                    for part in a[key].split(","):
                        url = part.strip().split()[0] if part.strip() else ""
                        if url:
                            self.resources.append(url)
        if tag == "meta" and a.get("content") and a.get("property") in ("og:image", "og:url"):
            self.resources.append(a["content"])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def build_ssl_context(insecure):
    """Контекст с рабочим хранилищем корней.

    У системного Python на macOS (framework build) путь из
    ssl.get_default_verify_paths() часто указывает на несуществующий
    cert.pem, и create_default_context() молча даёт 0 корней. Тогда любой
    https падает с CERTIFICATE_VERIFY_FAILED, а curl при этом работает
    (он берёт корни из системного keychain). Поэтому проверяем число
    корней и подгружаем certifi, если он есть.
    """
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx, "verification disabled (--insecure)"

    ctx = ssl.create_default_context()
    if ctx.get_ca_certs():
        return ctx, f"{len(ctx.get_ca_certs())} корневых сертификатов из системного хранилища"

    try:
        import certifi  # type: ignore
        ctx.load_verify_locations(cafile=certifi.where())
        n = len(ctx.get_ca_certs())
        if n:
            return ctx, f"{n} корневых сертификатов из certifi ({certifi.where()})"
    except ImportError:
        pass

    raise SystemExit(
        "ОШИБКА: в Python нет корневых сертификатов (create_default_context() дал 0).\n"
        "  Установи certifi:            pip install certifi\n"
        "  Или укажи файл вручную:      --ca-bundle /path/to/cacert.pem\n"
        "  Или отключите проверку:      --insecure (TLS не проверяется!)"
    )


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Соединение по фиксированному IP, но с SNI и проверкой по имени.

    Просто передать IP в HTTPSConnection нельзя: тогда server_hostname
    равен IP, и проверка сертификата падает с «certificate is not valid
    for '91.216.147.7'», хотя сам сертификат в порядке. Нужно подключаться
    к IP, а SNI и проверку имени оставить от домена — ровно то, что делает
    curl с --resolve.
    """

    def __init__(self, host, ip, port, timeout, context):
        super().__init__(host, port, timeout=timeout, context=context)
        self._pin_ip = ip

    def connect(self):
        sock = socket.create_connection((self._pin_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class Fetcher:
    """GET с фиксированным IP, схемой и портом, с сохранением SNI и Host.

    Схема и порт задаются явно: иначе нельзя сверить живой https-сайт с
    локальной http-копией (например, чтобы проверить, что инструмент вообще
    ловит расхождения).

    Accept-Encoding не отправляем намеренно: иначе ответ придёт gzip-ом и
    побайтовое сравнение будет бессмысленным.
    """

    def __init__(self, host, ctx, scheme="https", port=443, ip=None, timeout=20):
        self.host = host
        self.ip = ip
        self.scheme = scheme
        self.port = port
        self.timeout = timeout
        self.ctx = ctx

    @property
    def base(self):
        netloc = self.host if self.port in (80, 443) else f"{self.host}:{self.port}"
        return f"{self.scheme}://{netloc}"

    def get(self, path, extra_headers=None):
        if self.scheme == "https":
            if self.ip:
                conn = PinnedHTTPSConnection(self.host, self.ip, self.port, self.timeout, self.ctx)
            else:
                conn = http.client.HTTPSConnection(
                    self.host, self.port, timeout=self.timeout, context=self.ctx)
        else:
            target = self.ip or self.host
            if self.ip:
                conn = PinnedHTTPConnection(self.host, self.ip, self.port, self.timeout)
            else:
                conn = http.client.HTTPConnection(
                    target, self.port, timeout=self.timeout)
        headers = {
            "Host": self.host if self.port in (80, 443) else f"{self.host}:{self.port}",
            "User-Agent": "verify-mirror/1.0",
            "Accept": "*/*",
            "Connection": "close",
        }
        if extra_headers:
            headers.update(extra_headers)
        try:
            conn.request("GET", path or "/", headers=headers)
            resp = conn.getresponse()
            body = resp.read()
            return resp.status, dict(resp.getheaders()), body
        finally:
            conn.close()


class PinnedHTTPConnection(http.client.HTTPConnection):
    """HTTP-соединение по фиксированному IP, но с правильным Host."""

    def __init__(self, host, ip, port, timeout):
        super().__init__(host, port, timeout=timeout)
        self._pin_ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._pin_ip, self.port), self.timeout)


def norm_href(href, base):
    """Абсолютный URL без якоря и без query (query обычно это трекинг)."""
    u, _frag = urldefrag(urljoin(base, href.strip()))
    p = urlsplit(u)
    if p.scheme not in ("http", "https"):
        return None
    return urlunsplit((p.scheme, p.netloc, p.path or "/", "", ""))


def same_origin(url, origin):
    return urlsplit(url).netloc == urlsplit(origin).netloc


def crawl(fetcher, start_url, max_pages, max_depth, ignore, keep_bodies=False):
    """Обход своего origin.

    Возвращает (pages, assets, links_by_page, errors, ignored[, bodies]).
    Тела страниц сохраняются только при keep_bodies — они нужны, чтобы привести
    оригинал к новому хранилищу и сравнить остальное содержимое.
    """
    origin = "%s://%s" % (urlsplit(start_url).scheme, urlsplit(start_url).netloc)
    seen = set()
    queue = [(start_url, 0)]
    pages = {}
    assets = {}
    links_by_page = {}
    errors = []
    ignored = []
    bodies = {}

    while queue and len(seen) < max_pages:
        url, depth = queue.pop(0)
        key = urlsplit(url).path or "/"
        if key in seen:
            continue
        if any(re.search(pat, key) for pat in ignore):
            ignored.append(key)
            continue
        seen.add(key)

        path = urlsplit(url).path or "/"
        q = urlsplit(url).query
        full = path + ("?" + q if q else "")
        try:
            status, headers, body = fetcher.get(full)
        except Exception as exc:  # noqa: BLE001 — сеть может упасть как угодно
            errors.append(f"{key}: {type(exc).__name__}: {exc}")
            continue

        if status != 200:
            errors.append(f"{key}: HTTP {status}")
            continue

        ctype = ""
        for hk, hv in headers.items():
            if hk.lower() == "content-type":
                ctype = hv
                break
        rec = {"status": status, "sha256": hashlib.sha256(body).hexdigest(),
               "size": len(body), "ctype": ctype}

        is_html = "html" in ctype.lower() or not ASSET_RE.search(key)
        if not is_html:
            assets[key] = rec
            # CSS может ссылаться на другие ассеты (@font-face, background-image).
            # Без обхода этих ссылок обход не увидит шрифты.
            if key.lower().endswith(".css"):
                try:
                    # css_asset_urls отдаёт пути, а очередь ждёт абсолютные URL,
                    # и same_origin умеет сравнивать только URL — иначе сравнение
                    # всегда ложное и обход молча ничего не ставит в очередь.
                    for extra in css_asset_urls(body.decode("utf-8", errors="replace"), key):
                        absolute = origin.rstrip("/") + extra
                        if same_origin(absolute, origin):
                            queue.append((absolute, depth + 1))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{key}: CSS parse: {exc}")
            continue

        pages[key] = rec
        text = body.decode("utf-8", errors="replace")
        if keep_bodies:
            bodies[key] = text
        p = LinkCollector()
        try:
            p.feed(text)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{key}: HTML parse: {exc}")
        page_links = []
        for href in p.hrefs:
            nu = norm_href(href, url)
            if not nu:
                continue
            page_links.append(nu)
            if same_origin(nu, origin) and depth < max_depth:
                queue.append((nu, depth + 1))
        links_by_page[key] = Counter(page_links)
        for res in p.resources:
            nu = norm_href(res, url)
            if not nu:
                continue
            if same_origin(nu, origin):
                queue.append((nu, depth + 1))

    # Возврат всегда из 6 элементов: иначе распаковка ломается, когда тела
    # не запрашивались.
    return pages, assets, links_by_page, errors, ignored, bodies


def main():
    ap = argparse.ArgumentParser(description="Побайтовая сверка зеркала с оригиналом")
    ap.add_argument("--live-url", required=True, help="проверяемое зеркало")
    ap.add_argument("--original-url", help="оригинал; по умолчанию = --live-url")
    ap.add_argument("--original-host", help="Host/SNI для оригинала")
    ap.add_argument("--original-ip", help="IP оригинала (если DNS уже переключён)")
    ap.add_argument("--original-scheme", help="http/https для оригинала (по умолчанию — из URL)")
    ap.add_argument("--original-port", type=int, help="порт оригинала (для локальной копии)")
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--max-depth", type=int, default=4)
    ap.add_argument("--expect-link-prefix-rewrite", action="store_true",
                    help="зеркало намеренно перевело ссылки на новое хранилище "
                         "и переименовало три файла (src/data/link-migration.json); "
                         "такие расхождения считать ожидаемыми, остальное сверять как есть")
    ap.add_argument("--insecure", action="store_true", help="не проверять TLS-сертификаты")
    ap.add_argument("--ca-bundle", help="путь к файлу корневых сертификатов (PEM)")
    ap.add_argument("--min-pages", type=int, default=2,
                    help="минимум страниц, иначе считаем прогон неудачным (по умолчанию 2)")
    ap.add_argument("--ignore", nargs="*", default=[r"^/icons/", r"\.(?:php|jsp)$"],
                    help="регулярки путей, которые не обходить")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    migration = load_migration()
    _site = json.loads((Path(__file__).resolve().parent.parent
                        / "src/data/site.json").read_text(encoding="utf-8"))
    global FORM_NOTICE, FORM_ENDPOINT
    FORM_NOTICE = _site.get("form_notice", "")
    FORM_ENDPOINT = _site.get("form_endpoint", "")
    live = args.live_url.rstrip("/") or "/"
    # .hostname, а не .netloc: netloc включает порт («127.0.0.1:3090»),
    # и такое значение не резолвится — gaierror.
    live_host = urlsplit(live).hostname or urlsplit(live).netloc
    orig = (args.original_url or live).rstrip("/") or "/"
    orig_host = args.original_host or (urlsplit(orig).hostname or urlsplit(orig).netloc)

    if args.ca_bundle:
        ctx = ssl.create_default_context(cafile=args.ca_bundle)
        tls_note = f"CA-файл: {args.ca_bundle}"
    else:
        ctx, tls_note = build_ssl_context(args.insecure)

    live_p = urlsplit(live)
    orig_p = urlsplit(orig)
    live_f = Fetcher(live_host, ctx=ctx, scheme=live_p.scheme or "https",
                     port=live_p.port or (443 if live_p.scheme == "https" else 80), timeout=20)
    orig_port = args.original_port or orig_p.port or (443 if orig_p.scheme == "https" else 80)
    orig_f = Fetcher(orig_host, ctx=ctx, scheme=args.original_scheme or orig_p.scheme or "https",
                     port=orig_port, ip=args.original_ip, timeout=20)

    print("=" * 72)
    print("СВЕРКА ЗЕРКАЛА С ОРИГИНАЛОМ")
    print("=" * 72)
    print(f"  зеркало:    {live}")
    print(f"  оригинал:   {orig_f.base}" + (f"  (пин на {args.original_ip})" if args.original_ip else ""))
    print(f"  TLS:        {tls_note}")
    print()

    print("Обход зеркала…")
    live_start = live_f.base + "/"
    (live_pages, live_assets, live_links, live_err, live_ign,
     _live_bodies) = crawl(
        live_f, live_start, args.max_pages, args.max_depth, args.ignore)
    print(f"  страниц: {len(live_pages)}, ассетов: {len(live_assets)}, ошибок: {len(live_err)}")

    print("Обход оригинала…")
    orig_start = orig_f.base + "/"
    (orig_pages, orig_assets, orig_links, orig_err, orig_ign,
     orig_body_cache) = crawl(
        orig_f, orig_start, args.max_pages, args.max_depth, args.ignore,
        keep_bodies=args.expect_link_prefix_rewrite)
    print(f"  страниц: {len(orig_pages)}, ассетов: {len(orig_assets)}, ошибок: {len(orig_err)}")
    print()

    problems = []

    # 1. Множество страниц
    only_live = sorted(set(live_pages) - set(orig_pages))
    only_orig = sorted(set(orig_pages) - set(live_pages))
    print("1. СОСТАВ САЙТА")
    if only_live or only_orig:
        for p in only_live:
            print(f"   ⚠️  есть только в зеркале:   {p}")
        for p in only_orig:
            print(f"   ❌ есть только в оригинале: {p}")
        problems.append("состав страниц")
    else:
        print(f"   ✅ совпадает ({len(live_pages)} страниц)")
    print()

    # 2. Содержимое страниц
    print("2. СОДЕРЖИМОЕ СТРАНИЦ (sha256)")
    def norm_body(path_key, pages):
        """Тело страницы, опционально с приведёнными к новому хранилищу ссылками.

        При --expect-link-prefix-rewrite слепое сравнение sha256 бессмысленно:
        страницы намеренно разошлись. Тогда применяем то же преобразование к
        оригиналу, что и к зеркалу, и сравниваем остальное — так любая
        НАСТОЯЩАЯ ошибка (забытый файл, опечатка) всё равно всплывёт.
        """
        if not args.expect_link_prefix_rewrite:
            return pages[path_key]
        raw = orig_body_cache.get(path_key)
        if raw is None:
            return pages[path_key]
        fixed = apply_migration(raw, *migration)
        # Тот же патч формы, что и при сборке, иначе побайтовое равенство
        # недостижимо и проверка подтверждала бы сама себя.
        fixed = patches.apply(fixed, FORM_NOTICE, FORM_ENDPOINT).encode("utf-8")
        return {"status": 200, "ctype": "text/html", "size": len(fixed),
                "sha256": hashlib.sha256(fixed).hexdigest()}

    diff_pages = [p for p in sorted(orig_pages) if p in live_pages
                  and live_pages[p]["sha256"] != norm_body(p, orig_pages)["sha256"]]
    for p in diff_pages:
        print(f"   ❌ {p}")
        print(f"        оригинал: {orig_pages[p]['size']:>9,} B  {orig_pages[p]['sha256'][:16]}")
        print(f"        зеркало:   {live_pages[p]['size']:>9,} B  {live_pages[p]['sha256'][:16]}")
    compared = len([p for p in orig_pages if p in live_pages])
    if not diff_pages and compared == len(orig_pages):
        print(f"   ✅ все {compared} страниц совпадают побайтово")
    elif not diff_pages:
        # Сравнили меньше, чем нашли у оригинала: часть страниц не попала в
        # зеркало из-за ошибки обхода. Раньше здесь печаталось число страниц
        # оригинала, и отчёт утверждал «все 13 совпадают», хотя сравнивалось 10.
        print(f"   ⚠️  совпадают {compared} из {len(orig_pages)} — "
              f"{len(orig_pages) - compared} страниц не попали в зеркало (см. ошибки обхода)")
    else:
        problems.append("содержимое страниц")
    print()

    # 3. Ассеты
    print("3. АССЕТЫ (sha256)")
    only_a_live = sorted(set(live_assets) - set(orig_assets))
    only_a_orig = sorted(set(orig_assets) - set(live_assets))
    diff_assets = [a for a in sorted(orig_assets) if a in live_assets
                   and live_assets[a]["sha256"] != orig_assets[a]["sha256"]]
    for a in only_a_orig:
        print(f"   ❌ отсутствует ассет: {a}")
    for a in only_a_live:
        print(f"   ⚠️  лишний ассет:      {a}")
    for a in diff_assets:
        print(f"   ❌ отличается:         {a}")
    if not (only_a_live or only_a_orig or diff_assets):
        print(f"   ✅ все {len(orig_assets)} ассетов совпадают побайтово")
    else:
        problems.append("ассеты")
    print()

    # 4. Ссылки
    print("4. ССЫЛКИ")
    link_diffs = 0
    for path in sorted(set(orig_links) & set(live_links)):
        o = orig_links[path]
        m = live_links[path]
        if args.expect_link_prefix_rewrite:
            o = Counter({apply_migration(u, *migration): n for u, n in o.items()})
            o = Counter({u: n for u, n in o.items() if n})
        if o == m:
            continue
        link_diffs += 1
        print(f"   ❌ {path}")
        for u in sorted((o - m).elements()):
            print(f"        только в оригинале: {u}")
        for u in sorted((m - o).elements()):
            print(f"        только в зеркале:   {u}")
    if link_diffs == 0 and set(orig_links) == set(live_links):
        total = sum(len(v) for v in orig_links.values())
        print(f"   ✅ наборы ссылок совпадают на всех {len(orig_links)} страницах ({total} ссылок)")
    elif link_diffs == 0:
        print(f"   ⚠️  наборы ссылок совпадают на {len(set(orig_links) & set(live_links))} "
              f"страницах из {len(orig_links)}")
    else:
        print(f"   ❌ расхождения на {link_diffs} страницах")
        problems.append("ссылки")
    print()

    # 5. Коды ответов внутренних ссылок
    print("5. ВНУТРЕННИЕ ССЫЛКИ")
    bad = []
    checked = 0
    already = 0
    external = 0
    # same_origin ждёт URL, а не готовый netloc: разбирать «host» без схемы
    # нельзя, urlsplit вернёт пустой netloc и все ссылки попадут во внешние.
    origin_url = orig_f.base + "/"
    for path in sorted(set(orig_links)):
        for u in orig_links[path]:
            if not same_origin(u, origin_url):
                external += 1
                continue
            up = urlsplit(u).path or "/"
            if any(re.search(pat, up) for pat in args.ignore):
                continue
            if up in live_pages or ASSET_RE.search(up):
                # Уже проверено: страница или ассет сравнены по sha256 выше.
                already += 1
                continue
            try:
                st, _h, _b = live_f.get(up)
            except Exception as exc:  # noqa: BLE001
                bad.append(f"{up}: {type(exc).__name__}")
                continue
            checked += 1
            if st != 200:
                bad.append(f"{up}: HTTP {st}")
    for b in sorted(set(bad)):
        print(f"   ❌ {b}")
    if not bad:
        print(f"   ✅ битых ссылок нет")
        print(f"      сверено по sha256 (страницы/ассеты): {already}")
        print(f"      проверено отдельным запросом:           {checked}")
        print(f"      внешних ссылок (не запрашиваются):      {external}")
    else:
        problems.append("коды ответов")
    print()

    # Ошибки обхода
    if live_err or orig_err:
        print("6. ОШИБКИ ОБХОДА")
        for e in (live_err + orig_err)[:20]:
            print(f"   ⚠️  {e}")
        print()

    # Страховка от ложного «всё хорошо». Пустой обход даёт нулевые
    # расхождения и выглядит как успех, хотя ничего не проверил.
    print("7. САМОПРОВЕРКА ПРОГОНА")
    ok = True
    if len(live_pages) < args.min_pages:
        print(f"   ❌ зеркало: обойдено {len(live_pages)} страниц, ожидалось ≥ {args.min_pages} — "
              f"прогон ничего не проверил")
        ok = False
    if len(orig_pages) < args.min_pages:
        print(f"   ❌ оригинал: обойдено {len(orig_pages)} страниц, ожидалось ≥ {args.min_pages} — "
              f"прогон ничего не проверил")
        ok = False
    if live_err:
        print(f"   ❌ ошибок обхода зеркала: {len(live_err)}")
        ok = False
    if orig_err:
        print(f"   ❌ ошибок обхода оригинала: {len(orig_err)}")
        ok = False
    if ok:
        print("   ✅ прогон реальный: страницы обойдены, ошибок нет")
    else:
        problems.append("прогон неполный")
    print()

    print("=" * 72)
    if problems:
        print("РЕЗУЛЬТАТ: ЕСТЬ РАСХОЖДЕНИЯ → " + ", ".join(problems))
        print("=" * 72)
        return 1
    print(f"РЕЗУЛЬТАТ: ПОЛНОЕ СОВПАДЕНИЕ "
          f"({len(live_pages)} страниц, {len(live_assets)} ассетов, все ссылки 200)")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)
