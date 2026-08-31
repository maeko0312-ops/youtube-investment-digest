"""YouTubeまわりのユーティリティ。

- 新着検知: 各チャンネルのRSSフィード（無料・APIキー不要）
- 動画メタ情報・ライブ配信状態: YouTube Data API v3 の videos.list（軽量なのでAPIキーが必要）
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

ATOM_NS = "{http://www.w3.org/2005/Atom}"
YT_NS = "{http://www.youtube.com/xml/schemas/2015}"

RSS_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
VIDEOS_API_URL = "https://www.googleapis.com/youtube/v3/videos"

REQUEST_TIMEOUT_SECONDS = 20


@dataclass
class FeedEntry:
    video_id: str
    title: str
    published: str


@dataclass
class VideoDetails:
    video_id: str
    title: str
    live_broadcast_content: str  # "live" | "upcoming" | "none"
    has_ended: bool  # liveStreamingDetails.actualEndTime が存在するか


def fetch_channel_feed(channel_id: str) -> list[FeedEntry]:
    """チャンネルのRSSフィードから直近の動画一覧を取得する（新しい順、通常15件程度）。"""
    url = RSS_URL_TEMPLATE.format(channel_id=channel_id)
    resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    entries: list[FeedEntry] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        video_id_el = entry.find(f"{YT_NS}videoId")
        title_el = entry.find(f"{ATOM_NS}title")
        published_el = entry.find(f"{ATOM_NS}published")
        if video_id_el is None or video_id_el.text is None:
            continue
        entries.append(
            FeedEntry(
                video_id=video_id_el.text,
                title=(title_el.text if title_el is not None else "").strip(),
                published=(published_el.text if published_el is not None else ""),
            )
        )
    return entries


def get_video_details(api_key: str, video_ids: list[str]) -> dict[str, VideoDetails]:
    """videos.list で複数動画のメタ情報を一括取得する（最大50件/リクエスト）。"""
    result: dict[str, VideoDetails] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        params = {
            "part": "snippet,liveStreamingDetails",
            "id": ",".join(chunk),
            "key": api_key,
        }
        resp = requests.get(VIDEOS_API_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            video_id = item["id"]
            snippet = item.get("snippet", {})
            live_details = item.get("liveStreamingDetails", {})
            result[video_id] = VideoDetails(
                video_id=video_id,
                title=snippet.get("title", ""),
                live_broadcast_content=snippet.get("liveBroadcastContent", "none"),
                has_ended="actualEndTime" in live_details,
            )
    return result


def is_pending_live(details: VideoDetails) -> bool:
    """まだ処理すべきでない（配信中 or 配信予定の）動画かどうか。"""
    return details.live_broadcast_content in ("live", "upcoming")


def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"
