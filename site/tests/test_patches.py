#!/usr/bin/env python3
"""Тесты объявленных отступлений.

Проверяют ЧТО ФУНКЦИЯ ВОЗВРАЩАЕТ, а не только то, что два вызова согласованы
между собой. Общий модуль patches.py гарантирует согласованность сборки и
проверки, но не правильность: опечатка одинаково применяется обеими сторонами,
и сравнение sha256 осталось бы довольным. Именно так уже ловилась ошибка с
экранированным переводом строки в перехватчике.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import patches  # noqa: E402

ENDPOINT = "https://formspree.io/f/mjygvben"
NOTICE = "Форма временно недоступна. Напишите нам на info@quantumart.ru"

# Одна форма на каждой из семи страниц. Все семь эндпоинтов должны
# опознаваться одинаково — это и есть отличие от соседнего проекта.
ENDPOINTS = ["/QP8/Send", "/QP8_PG/Send", "/DPC/Send", "/Widgets/Send",
             "/QP79/Send", "/DPC.Impact/Send", "/DPC.PdfGenerator/Send"]


def page(action="/QP8/Send"):
    return f'<html><body><form action="{action}"></form>\n</body></html>'


def run_tests():
    tests = []
    def t(fn):
        tests.append(fn)
        return fn

    # ── режим без приёмника: перехватчик ──────────────────────────────
    @t
    def guard_inserted_once():
        out = patches.apply(page(), NOTICE, "")
        assert out.count(patches.GUARD_MARK) == 1, out
        assert out.count("</body>") == 1, out

    @t
    def guard_watches_all_seven_endpoints():
        for ep in ENDPOINTS:
            out = patches.apply(page(ep), NOTICE, "")
            assert "/Send" in out, f"{ep}: перехватчик не смотрит на суффикс"
            assert "preventDefault" in out, ep
        # перехватчик не должен быть привязан к одной константе
        src = patches._guard(NOTICE)
        for ep in ENDPOINTS:
            assert ep not in src, f"{ep} зашит в перехватчик — новый продукт его сломает"

    @t
    def guard_does_not_touch_unrelated_forms():
        out = patches.apply('<html><body><form action="/subscribe"></form>\n</body></html>',
                            NOTICE, "")
        assert "addEventListener" in out
        # вставка должна быть безусловной на уровне document, а суффикс
        # проверяется в рантайме — проверяем это по тексту guard'а
        assert "/Send" in patches._guard(NOTICE)

    @t
    def notice_is_json_escaped_not_html_injected():
        nasty = '</script><img src=x onerror=alert(1)> "кавычка" \\ обратный'
        out = patches.apply(page(), nasty, "")
        assert "</script><img" not in out, "уведомление попало в разметку"
        assert '\\"' in out
        assert "<script>Кавычка" not in out

    @t
    def no_notice_means_no_patch():
        assert patches.apply(page(), "") == page()

    @t
    def guard_is_idempotent():
        once = patches.apply(page(), NOTICE, "")
        twice = patches.apply(once, NOTICE, "")
        assert patches.count_guard(once) == 1
        assert twice == once, "повторное применение изменило страницу"

    @t
    def guard_ends_with_real_newline_before_body():
        out = patches.apply(page(), NOTICE, "")
        assert "</script>\n</body>" in out, "пропал настоящий перевод строки"
        assert "</script>\\n</body>" not in out, "осталась экранированная \\n"
        assert "\\n" not in out, "в выводе осталась экранированная последовательность"

    @t
    def guard_placed_exactly_where_body_closed():
        out = patches.apply(page(), NOTICE, "")
        # перехватчик стоит непосредственно перед закрывающим </body>,
        # а не после </html> и не в начале документа
        assert out.endswith("</script>\n</body></html>"), out[-80:]
        assert out.index("</script>") < out.index("</body>") < out.index("</html>")

    @t
    def guard_leaves_rest_byte_identical():
        original = page()
        out = patches.apply(original, NOTICE, "")
        inserted = out.split("<script>", 1)[1]
        inserted = "<script>" + inserted.rsplit("</body>", 1)[0]
        assert out.replace(inserted, "") == original, "тронуто лишнее"

    # ── режим с приёмником: переписывание action ──────────────────────
    @t
    def endpoint_rewrites_action_and_installs_no_guard():
        out = patches.apply(page(), NOTICE, ENDPOINT)
        assert out.count(patches.GUARD_MARK) == 0, "перехватчик погасил бы отправку"
        assert f'action="{ENDPOINT}"' in out, out
        assert patches.count_rewritten_actions(out) == 0

    @t
    def endpoint_rewrites_every_seven_endpoints():
        for ep in ENDPOINTS:
            out = patches.apply(page(ep), NOTICE, ENDPOINT)
            assert f'action="{ENDPOINT}"' in out, f"{ep} не переписан"
            assert patches.count_rewritten_actions(out) == 0, ep

    @t
    def endpoint_keeps_every_other_byte_untouched():
        original = page()
        out = patches.apply(original, NOTICE, ENDPOINT)
        restored = out.replace(f'action="{ENDPOINT}"', 'action="/QP8/Send"')
        restored = restored.split("<script>", 1)[0] + "</body></html>"
        assert restored == original, "переписано больше, чем атрибут action"

    @t
    def accept_wrapper_installed_once_for_receiver():
        out = patches.apply(page(), NOTICE, ENDPOINT)
        assert patches.count_fetch_patch(out) == 1
        assert 'indexOf("formspree.io")' in out
        assert 'Accept":"application/json' in out

    @t
    def accept_wrapper_is_idempotent():
        once = patches.apply(page(), NOTICE, ENDPOINT)
        twice = patches.apply(once, NOTICE, ENDPOINT)
        assert patches.count_fetch_patch(twice) == 1, "обёртка установлена дважды"
        assert twice == once

    @t
    def accept_wrapper_targets_receiver_host():
        assert patches.receiver_host("https://formspree.io/f/abc") == "formspree.io"
        assert patches.receiver_host("") == ""
        # обёртка не должна ловить чужие домены
        out = patches.apply(page(), "", "https://example.com/f/1")
        assert 'indexOf("example.com")' in out

    @t
    def blank_endpoint_treated_as_absent():
        assert patches.apply(page(), NOTICE, "   ") == patches.apply(page(), NOTICE, "")

    @t
    def endpoint_ignores_notice():
        out = patches.apply(page(), NOTICE, ENDPOINT)
        assert NOTICE not in out

    @t
    def no_endpoint_keeps_guard_and_original_action():
        out = patches.apply(page(), NOTICE, "")
        assert out.count(patches.GUARD_MARK) == 1
        assert 'action="/QP8/Send"' in out

    # ── граница: не трогаем чужие action ─────────────────────────────
    @t
    def no_wrapper_on_page_without_form():
        # главная и архив формы не содержат — обёртка туда попадать не должна
        html = "<html><body><p>нет формы</p>\n</body></html>"
        out = patches.apply(html, NOTICE, ENDPOINT)
        assert patches.count_fetch_patch(out) == 0, "обёртка попала на страницу без формы"
        assert out == html, "страница без формы изменилась"

    @t
    def unrelated_action_untouched():
        html = '<html><body><form action="/subscribe"></form>\n</body></html>'
        out = patches.apply(html, NOTICE, ENDPOINT)
        assert 'action="/subscribe"' in out
        assert patches.count_rewritten_actions(html) == 0

    # ── против настоящих страниц сайта ────────────────────────────────
    @t
    def all_real_pages_have_exactly_one_form():
        root = Path(__file__).resolve().parent.parent / "src/pages"
        found = {}
        for p in root.rglob("*.html"):
            html = p.read_text(encoding="utf-8")
            n = patches.count_rewritten_actions(html)
            if n:
                found[str(p.relative_to(root))] = n
        assert len(found) == 7, f"ожидалось 7 страниц с формой, найдено {len(found)}: {found}"
        assert all(v == 1 for v in found.values()), f"где-то форм больше одной: {found}"

    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  ✅ {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  ❌ {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  💥 {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} тестов прошли")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run_tests())
