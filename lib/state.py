"""state/ 以下のJSONファイルを読み書きするヘルパー。

状態はすべてリポジトリ内のJSONファイルとして保存し、ワークフローが
実行後にコミット&プッシュすることで永続化する（追加のDBを使わない）。

保存するのは動画ID・チャンネル名・タイトルなど、元々YouTube上で公開されている
情報のみ。Geminiが生成したチャプター要約の本文はここには保存しない
（LINEへ送信したら終わりで、日次ダイジェスト作成時は改めてGeminiに解析させる）。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state")

SEEN_PATH = os.path.join(STATE_DIR, "seen.json")
PENDING_LIVE_PATH = os.path.join(STATE_DIR, "pending_live.json")
RECENT_VIDEOS_PATH = os.path.join(STATE_DIR, "recent_videos.json")

RECENT_VIDEOS_RETENTION_DAYS = 2


def _load(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return default
        return json.loads(content)


def _save(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def load_seen() -> set[str]:
    """処理済み動画IDの集合を返す。"""
    return set(_load(SEEN_PATH, []))


def save_seen(seen_ids: set[str]) -> None:
    _save(SEEN_PATH, sorted(seen_ids))


def load_pending_live() -> dict[str, dict]:
    """配信中で未処理のライブ動画（video_id -> メタ情報）を返す。"""
    return _load(PENDING_LIVE_PATH, {})


def save_pending_live(pending: dict[str, dict]) -> None:
    _save(PENDING_LIVE_PATH, pending)


def load_recent_videos() -> list[dict]:
    """日次ダイジェスト用に、直近数日分の処理済み動画（メタ情報のみ）を返す。"""
    return _load(RECENT_VIDEOS_PATH, [])


def append_recent_video(entry: dict) -> None:
    """1動画分のメタ情報（video_id, channel_name, title, url, processed_at）を追記し、
    保持期間を過ぎた古いものは削除する。要約本文はここには含めないこと。
    """
    entries = load_recent_videos()
    entries.append(entry)

    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_VIDEOS_RETENTION_DAYS)
    kept = []
    for e in entries:
        try:
            ts = datetime.fromisoformat(e["processed_at"])
        except (KeyError, ValueError):
            continue
        if ts >= cutoff:
            kept.append(e)

    _save(RECENT_VIDEOS_PATH, kept)


def clear_recent_videos() -> None:
    _save(RECENT_VIDEOS_PATH, [])
