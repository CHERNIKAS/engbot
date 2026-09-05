"""Text carrying HTML must be sent with parse_mode="HTML".

The bot's default parse mode is None, so a forgotten argument doesn't fail —
it renders the markup literally. A user saw a placement card reading
`<b>prove</b>` before any test noticed.

The check walks the handlers and flags a send whose text comes from one of the
HTML constants without that argument. It follows two hops, because the bug it
was written for used both: a local assigned from a constant, and a local
unpacked from a helper that returns one.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import app.bot.texts as texts

APP = Path(__file__).resolve().parent.parent / "app"
SEND_METHODS = {"answer", "edit_text", "reply", "send_message"}
_TAG = re.compile(r"<[a-z/][^>]*>")


def _html_text_names() -> set[str]:
    return {
        name
        for name in dir(texts)
        if name.isupper()
        and isinstance(getattr(texts, name), str)
        and _TAG.search(getattr(texts, name))
    }


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _html_returning_helpers(tree: ast.AST, html_names: set[str]) -> set[str]:
    """Functions in this module that hand back an HTML text."""
    helpers: set[str] = set()
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(func):
            if isinstance(node, ast.Return) and node.value is not None:
                if _names_in(node.value) & html_names:
                    helpers.add(func.name)
    return helpers


def scan(tree: ast.AST, html_names: set[str]) -> list[tuple[int, list[str]]]:
    """Sends of HTML text with no parse_mode, as (line, source names)."""
    producers = _html_returning_helpers(tree, html_names)
    found: list[tuple[int, list[str]]] = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # Locals holding HTML: assigned from a constant, or from a helper that
        # returns one. Tuple targets count — `text, kb = _render_card(card)` is
        # exactly how the text reached the send site in the case this caught.
        tainted: set[str] = set()
        for node in ast.walk(func):
            if not isinstance(node, ast.Assign):
                continue
            if not (_names_in(node.value) & (html_names | tainted | producers)):
                continue
            for target in node.targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name):
                        tainted.add(name.id)
        for node in ast.walk(func):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in SEND_METHODS
                and node.args
            ):
                continue
            if any(k.arg == "parse_mode" for k in node.keywords):
                continue
            used = _names_in(node.args[0]) & (html_names | tainted | producers)
            if used:
                found.append((node.lineno, sorted(used)))
    return found


def test_html_texts_are_never_sent_without_parse_mode():
    html_names = _html_text_names()
    offenders = [
        f"{path.relative_to(APP.parent)}:{line} sends {names} without parse_mode"
        for path in sorted(APP.rglob("*.py"))
        for line, names in scan(ast.parse(path.read_text(encoding="utf-8")), html_names)
    ]
    assert not offenders, "\n".join(offenders)


def test_the_check_catches_the_shape_that_got_past_it():
    """The real bug went through a helper and a tuple unpack, so a check that
    only spotted direct references would have slept through it. This is that
    exact shape, and it must be flagged."""
    source = ast.parse(
        "def _render_card(card):\n"
        "    return PLACEMENT_CARD.format(writing=card.writing), kb(card)\n"
        "\n"
        "async def handler(query, card):\n"
        "    text, keyboard = _render_card(card)\n"
        "    await query.message.edit_text(text, reply_markup=keyboard)\n"
    )
    found = scan(source, _html_text_names())
    assert found, "the indirect shape must be flagged"
    assert found[0][0] == 6


def test_the_check_accepts_a_correct_send():
    source = ast.parse(
        "async def handler(query):\n"
        "    await query.message.edit_text(PLACEMENT_CARD, parse_mode='HTML')\n"
    )
    assert scan(source, _html_text_names()) == []
