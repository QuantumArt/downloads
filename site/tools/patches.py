#!/usr/bin/env python3
"""Объявленные отступления от байтов боевого сайта: обработка формы.

Импорт и build.py, и verify_mirror.py — намеренно. Пока отступление описано
в одном месте и применяется одним кодом, эталон sha256 остаётся точным. Как
только правка разъезжается между сборкой и проверкой, проверка начинает
подтверждать сама себя и перестаёт что-то доказывать.

ОДНАКО общий модуль гарантирует СОГЛАСОВАННОСТЬ, а не ПРАВИЛЬНОСТЬ. Опечатка
здесь одинаково применяется сборкой и проверкой, и сравнение хешей останется
довольным. Поэтому у каждой функции обязан быть тест, проверяющий ЧТО ОНА
ВОЗВРАЩАЕТ, а не только то, что два вызова сходятся между собой (см.
tests/test_patches.py).

Свойства этого сайта, отличающие его от соседнего проекта quantumart:

* эндпоинтов не один, а семь — по одному на страницу с формой:
  /QP8/Send, /QP8_PG/Send, /DPC/Send, /Widgets/Send, /QP79/Send,
  /DPC.Impact/Send, /DPC.PdfGenerator/Send. Поэтому и переписывание action,
  и перехватчик опознают форму по признаку «action кончается на /Send»,
  а не по сравнению с одной константой.

Два режима, переключаются в src/data/site.json:

1. `form_endpoint` ПУСТОЙ (по умолчанию) — в конец body добавляется скрипт,
   который гасит отправку и показывает посетителю notice. Разметка формы
   не трогается.
2. `form_endpoint` ЗАДАН — у формы меняется ТОЛЬКО атрибут action на внешний
   приёмник заявок, перехватчик НЕ вставляется. Иначе перехватчик погасил бы
   и рабочую отправку.

Второй режим меняет байты сильнее первого (переписан атрибут), поэтому это
тоже объявленное отступление: и сборка, и проверка применяют его одним кодом.
"""
from __future__ import annotations

import json
import re

# Признак эндпоинта CMS на этом сайте. Не перечисляем семь имён: форма
# опознаётся по суффиксу пути, и новый продукт не потребует правки кода.
ENDPOINT_SUFFIX = "/Send"
GUARD_MARK = "addEventListener"
FETCH_PATCH_FLAG = "__qaAcceptJson"       # проверка идемпотентности
FETCH_PATCH_MARK = "FETCH_PATCH"         # ровно одно вхождение: счётчик установки
SUFFIX_JS = r"\\/Send$"

# Переписывание action. Группы 1 и 3 — неизменяемые части тега,
# 2 — сам эндпоинт, он заменяется.
RE_FORM_ACTION = re.compile(
    r'(<form\b[^>]*?\saction=")(/[^"]*' + re.escape(ENDPOINT_SUFFIX) + r')(")', re.I)


def _js_string(value: str) -> str:
    """Строка для вставки внутрь <script>.

    json.dumps экранирует кавычки и обратные слэши, но НЕ экранирует прямой
    слэш. Из-за этого уведомление, содержащее «</script>», выскочило бы из
    JS-строки прямо в разметку и сломало бы страницу (и выполнило бы
    произвольный HTML). Поэтому слэш после «<» экранируем отдельно — это
    допустимая escape-последовательность в JS и в HTML.
    """
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _guard(notice: str) -> str:
    payload = _js_string(notice)
    return (
        '<script>(function(){var n=' + payload + ';'
        'document.addEventListener("submit",function(e){var f=e.target;'
        'if(!f||f.tagName!=="FORM")return;'
        'var a=f.getAttribute("action")||"";'
        f'if(a.slice(-{len(ENDPOINT_SUFFIX)})!=="{ENDPOINT_SUFFIX}")return;'
        "e.preventDefault();"
        "if(window.ym){window.ym(n.length,!0);}"
        "else{window.alert(n);}}});})();</script>\n</body>"
    )


def _accept_json_wrapper(receiver_host: str) -> str:
    """Добавить Accept: application/json к запросам на приёмник.

    Собственный JS сайта отправляет форму так: fetchUrl = form.action, затем
    fetch(url, {method:POST, body}) и resolveResponse(status) — 200 открывает
    родную модалку успеха, 500 — ошибки. Обёртка нужна ровно потому, что он
    шлёт БЕЗ заголовка Accept, а приёмник без него отвечает 302 на свою
    страницу-спасибо. fetch пойдёт по редиректу на чужой домен, у которого нет
    CORS-заголовков, запрос отклонится — и resolveResponse не вызовется вовсе:
    посетитель не увидит ничего, тихо. С Accept приёмник отвечает JSON прямо,
    200, и родная механика сайта отрабатывает как задумано.

    Порядок загрузки не важен: demosite.min.js зовёт глобальный fetch в момент
    отправки, а не захватывает ссылку при загрузке.
    """
    # Метку-флаг и МАРКЕР для счёта разводим: если бы маркер входил и в
    # условие, он встречался бы дважды и счётчик установки врал бы.
    return (
        "<script>(function(){var f=window.fetch;"
        "if(!f||window." + FETCH_PATCH_FLAG + ")return;"
        "window." + FETCH_PATCH_MARK + "=1;"
        "window.fetch=function(u,o){o=o||{};"
        f'if(String(u).indexOf({_js_string(receiver_host)})>-1){{'
        "o=Object.assign({},o);"
        'o.headers=Object.assign({"Accept":"application/json"},o.headers||{});}'
        "return f.call(this,u,o);};})();</script>\n</body>"
    )


def count_guard(html: str) -> int:
    return html.count(GUARD_MARK)


def count_fetch_patch(html: str) -> int:
    return html.count(FETCH_PATCH_MARK)


def count_rewritten_actions(html: str) -> int:
    """Сколько форм ещё указывает на эндпоинт CMS (то есть не переведено)."""
    return len(RE_FORM_ACTION.findall(html))


def receiver_host(endpoint: str) -> str:
    """Хост приёмника — по нему обёртка решает, куда добавлять Accept."""
    m = re.match(r"https?://([^/]+)", endpoint or "")
    return m.group(1) if m else ""


def apply(html: str, notice: str, endpoint: str = "") -> str:
    """Применить объявленные отступления к готовому HTML страницы.

    endpoint непустой -> форма шлёт на приёмник по родной механике сайта
    (fetch + его собственная модалка), перехватчика нет.
    endpoint пустой    -> перехватчик гасит отправку и показывает notice.
    """
    endpoint = (endpoint or "").strip()
    if endpoint:
        before = count_rewritten_actions(html)
        html = RE_FORM_ACTION.sub(
            lambda m: f'{m.group(1)}{endpoint}{m.group(3)}', html)
        # Обёртка нужна только там, где форма реально переведена. Без этого
        # условия она попадала и на страницы без формы (главная, архив,
        # GraphQL, Angular, React) — лишние ~8 КБ JS впустую и лишний байт,
        # которого на побайтовой сверке нет.
        if before and count_fetch_patch(html) == 0:
            html = html.replace(
                "</body>", _accept_json_wrapper(receiver_host(endpoint)), 1)
        return html
    if not notice or count_guard(html):
        return html
    return html.replace("</body>", _guard(notice), 1)
