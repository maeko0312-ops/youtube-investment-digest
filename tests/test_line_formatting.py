"""外部通信なしで実行できる、LINEメッセージ組み立て・分割ロジックのテスト。

実行方法:
    python tests/test_line_formatting.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.line import MAX_MESSAGE_LENGTH, build_video_message_text, split_text  # noqa: E402


def test_split_text_short_text_returns_single_chunk() -> None:
    text = "短いテキスト"
    result = split_text(text)
    assert result == [text], result


def test_split_text_splits_long_text_within_limit() -> None:
    text = "あ" * (MAX_MESSAGE_LENGTH * 2 + 100)
    chunks = split_text(text)
    assert len(chunks) >= 3, chunks
    for chunk in chunks:
        assert len(chunk) <= MAX_MESSAGE_LENGTH, len(chunk)
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_split_text_prefers_newline_boundaries() -> None:
    line = "0123456789\n"
    text = line * (MAX_MESSAGE_LENGTH // len(line) + 5)
    chunks = split_text(text)
    for chunk in chunks[:-1]:
        assert chunk.endswith("9"), repr(chunk[-5:])


def test_build_video_message_text_with_chapters() -> None:
    chapters = [
        {"start_time": "0:00", "heading": "導入", "summary": "今日のテーマの紹介。"},
        {"start_time": "3:20", "heading": "個別銘柄解説", "summary": "A社について業績が良いと紹介。"},
    ]
    text = build_video_message_text("テストチャンネル", "テスト動画", "https://example.com/v", chapters)
    assert "テストチャンネル" in text
    assert "テスト動画" in text
    assert "https://example.com/v" in text
    assert "導入" in text
    assert "個別銘柄解説" in text
    assert len(text) <= MAX_MESSAGE_LENGTH


def test_build_video_message_text_fallback_without_chapters() -> None:
    text = build_video_message_text("テストチャンネル", "テスト動画", "https://example.com/v", None)
    assert "自動解析に失敗" in text
    assert "テスト動画" in text


def main() -> None:
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"OK: {t.__name__}")
    print(f"\n{len(tests)}件すべて成功")


if __name__ == "__main__":
    main()
