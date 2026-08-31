"""20〜30分おきに実行: 各チャンネルの新着動画・ライブ配信をチェックし、
チャプター要約をLINEグループへ送る。

必要な環境変数:
  YOUTUBE_API_KEY
  GEMINI_API_KEY
  LINE_CHANNEL_ACCESS_TOKEN
  LINE_GROUP_ID
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from lib import line, state, summarize, youtube

CHANNELS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "channels.json")


def load_channels() -> list[dict]:
    with open(CHANNELS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["channels"]


def main() -> int:
    youtube_api_key = os.environ["YOUTUBE_API_KEY"]
    gemini_api_key = os.environ["GEMINI_API_KEY"]
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_group_id = os.environ["LINE_GROUP_ID"]

    channels = load_channels()
    seen = state.load_seen()
    pending_live = state.load_pending_live()

    # チャンネルのRSSを見て、未処理の新着動画IDを集める。あわせて video_id -> channel名 の対応も作る。
    channel_name_by_video_id: dict[str, str] = {}
    new_ids_from_feed: list[str] = []

    for ch in channels:
        try:
            entries = youtube.fetch_channel_feed(ch["id"])
        except Exception as e:
            print(f"[check] RSS取得失敗 channel={ch['name']}: {e}")
            continue
        for entry in entries:
            channel_name_by_video_id[entry.video_id] = ch["name"]
            if entry.video_id not in seen and entry.video_id not in pending_live:
                new_ids_from_feed.append(entry.video_id)

    # 既に「配信中」として保留していた動画も、終了したか毎回確認する
    ids_to_check = list(dict.fromkeys(new_ids_from_feed + list(pending_live.keys())))
    for vid, meta in pending_live.items():
        channel_name_by_video_id.setdefault(vid, meta.get("channel_name", "不明なチャンネル"))

    if not ids_to_check:
        print("[check] 新着なし")
        return 0

    try:
        details_map = youtube.get_video_details(youtube_api_key, ids_to_check)
    except Exception as e:
        print(f"[check] videos.list呼び出し失敗: {e}")
        return 1

    gemini_client = summarize.get_client(gemini_api_key)

    to_process: list[str] = []
    for vid in ids_to_check:
        details = details_map.get(vid)
        if details is None:
            # APIから消えている（削除・非公開化など）場合は無視してseen扱いにする
            seen.add(vid)
            pending_live.pop(vid, None)
            continue

        if youtube.is_pending_live(details):
            pending_live[vid] = {
                "channel_name": channel_name_by_video_id.get(vid, "不明なチャンネル"),
                "title": details.title,
            }
            continue

        pending_live.pop(vid, None)
        to_process.append(vid)

    for vid in to_process:
        channel_name = channel_name_by_video_id.get(vid, "不明なチャンネル")
        details = details_map.get(vid)
        title = details.title if details else channel_name
        url = youtube.video_url(vid)

        print(f"[check] 処理中: {channel_name} - {title}")
        chapters = summarize.analyze_video_chapters(gemini_client, url)

        message_text = line.build_video_message_text(channel_name, title, url, chapters)
        ok = line.push_text(line_token, line_group_id, message_text)
        if not ok:
            print(f"[check] LINE送信に失敗: {vid}（月間上限の可能性）")

        state.append_recent_summary(
            {
                "video_id": vid,
                "channel_name": channel_name,
                "title": title,
                "url": url,
                "chapters": chapters,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        seen.add(vid)

    state.save_seen(seen)
    state.save_pending_live(pending_live)
    print(f"[check] 完了: {len(to_process)}件処理, {len(pending_live)}件がライブ配信中で保留")
    return 0


if __name__ == "__main__":
    sys.exit(main())
