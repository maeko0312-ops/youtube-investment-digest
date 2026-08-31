"""LINE Messaging API へのメッセージ送信まわり。

無料プラン（コミュニケーションプラン）は月200通まで無料。超過分は送信が
失敗するだけで課金は発生しない。1テキストメッセージは5000文字まで、
1回のpushリクエストで送れるメッセージは5件まで、という制約に合わせて
本文を分割する。
"""
from __future__ import annotations

import requests

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

MAX_MESSAGE_LENGTH = 5000
MAX_MESSAGES_PER_PUSH = 5
REQUEST_TIMEOUT_SECONDS = 20


def split_text(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """textをlimit文字以内のチャンクに分割する。改行境界をできるだけ尊重する。"""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut].rstrip("\n"))
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


def build_video_message_text(channel_name: str, title: str, url: str, chapters: list[dict] | None) -> str:
    """1動画分のLINEメッセージ本文を組み立てる。chaptersがNoneなら簡易フォールバック文面にする。"""
    header = f"【新着】{channel_name}\n{title}\n{url}"

    if not chapters:
        return header + "\n\n(内容の自動解析に失敗したため、タイトルのみお届けします)"

    lines = [header, ""]
    for ch in chapters:
        start = ch.get("start_time", "")
        heading = ch.get("heading", "")
        summary = ch.get("summary", "")
        lines.append(f"■ {start} {heading}")
        if summary:
            lines.append(summary)
        lines.append("")

    return "\n".join(lines).rstrip()


def push_text(channel_access_token: str, to: str, text: str) -> bool:
    """テキストをLINEグループへpushする。必要なら複数メッセージ・複数リクエストに分割する。
    送信に失敗しても例外は送出せず、Falseを返す（1件の失敗で全体を止めないため）。
    """
    chunks = split_text(text)
    headers = {
        "Authorization": f"Bearer {channel_access_token}",
        "Content-Type": "application/json",
    }

    ok = True
    for i in range(0, len(chunks), MAX_MESSAGES_PER_PUSH):
        batch = chunks[i : i + MAX_MESSAGES_PER_PUSH]
        body = {
            "to": to,
            "messages": [{"type": "text", "text": c} for c in batch],
        }
        try:
            resp = requests.post(LINE_PUSH_URL, headers=headers, json=body, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code != 200:
                print(f"[line] push failed: status={resp.status_code} body={resp.text}")
                ok = False
        except requests.RequestException as e:
            print(f"[line] push error: {e}")
            ok = False

    return ok
