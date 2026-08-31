"""毎朝5:00 JST(=20:00 UTC)に実行: 直近の新着動画の要約を横断して
「今後の投資戦略」ダイジェストを作りLINEグループへ送る。

必要な環境変数:
  GEMINI_API_KEY
  LINE_CHANNEL_ACCESS_TOKEN
  LINE_GROUP_ID
"""
from __future__ import annotations

import os
import sys

from lib import line, state, summarize

NO_UPDATE_MESSAGE = "【本日の投資戦略ダイジェスト】\n直近、監視対象チャンネルからの新着動画はありませんでした。"


def build_summaries_text(entries: list[dict]) -> str:
    parts = []
    for e in entries:
        parts.append(f"◆ {e['channel_name']} 『{e['title']}』")
        for ch in e.get("chapters") or []:
            heading = ch.get("heading", "")
            summary = ch.get("summary", "")
            parts.append(f"  - {heading}: {summary}")
        parts.append("")
    return "\n".join(parts)


def main() -> int:
    gemini_api_key = os.environ["GEMINI_API_KEY"]
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_group_id = os.environ["LINE_GROUP_ID"]

    entries = state.load_recent_summaries()

    if not entries:
        line.push_text(line_token, line_group_id, NO_UPDATE_MESSAGE)
        print("[daily] 新着なしのため簡易メッセージのみ送信")
        return 0

    summaries_text = build_summaries_text(entries)
    gemini_client = summarize.get_client(gemini_api_key)
    digest = summarize.build_daily_digest(gemini_client, summaries_text)

    if digest is None:
        digest = (
            "本日のダイジェスト生成に失敗しました。以下、直近動画の一覧のみお届けします。\n\n"
            + summaries_text
        )

    message = "【本日の投資戦略ダイジェスト】\n" + digest
    ok = line.push_text(line_token, line_group_id, message)
    if not ok:
        print("[daily] LINE送信に失敗（月間上限の可能性）")

    state.clear_recent_summaries()
    print(f"[daily] 完了: {len(entries)}件の動画を元にダイジェストを作成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
