from __future__ import annotations

from app.services.word_parser import parse_input


def test_parses_single_words():
    result = parse_input("hello\nworld\n")
    assert [w.english for w in result.words] == ["hello", "world"]
    assert all(w.translation is None for w in result.words)


def test_parses_with_translation_and_example():
    text = "persistent - настойчивый | He is very persistent.\nagile = шустрый"
    result = parse_input(text)
    assert len(result.words) == 2
    p0 = result.words[0]
    assert p0.english == "persistent"
    assert p0.translation == "настойчивый"
    assert p0.example == "He is very persistent."
    assert result.words[1].translation == "шустрый"


def test_deduplicates_case_insensitive():
    result = parse_input("Hello\nhello\nHELLO\n")
    assert len(result.words) == 1
    assert result.duplicates == 2


def test_skips_blanks_and_comments():
    result = parse_input("\n\n# a comment\nfoo\n  \n# another\nbar\n")
    assert [w.english for w in result.words] == ["foo", "bar"]


def test_strips_bom_and_mixed_line_endings():
    result = parse_input("﻿hello\r\nworld\r")
    assert [w.english for w in result.words] == ["hello", "world"]


def test_invalid_words_are_dropped():
    result = parse_input("foo\n123abc\n!!!\nbar\n")
    assert [w.english for w in result.words] == ["foo", "bar"]
    assert result.invalid == 2


def test_respects_max_words_cap():
    text = "\n".join(f"word{i}" for i in range(50))
    result = parse_input(text, max_words=10)
    assert len(result.words) == 10
