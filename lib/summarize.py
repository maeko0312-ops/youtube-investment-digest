"""Gemini APIによる動画のチャプター要約・日次ダイジェスト生成。

Gemini APIは動画URL（YouTubeのURL）を直接渡して内容を解析できるため、
別途の文字起こし取得は行わない。解析に失敗した場合は呼び出し側で
タイトルのみの簡易メッセージにフォールバックすること。
"""
from __future__ import annotations

import json
import os

from google import genai
from google.genai import types

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

CHAPTER_PROMPT = """あなたは投資解説YouTube動画の内容を要約するアシスタントです。
渡された動画を確認し、内容のまとまりごとにチャプターへ分割してください。
（動画の概要欄に著者自身のチャプター表記があればそれを優先して構いません）

出力は必ず以下のJSON形式のみで、説明文は付けないでください。
{
  "chapters": [
    {"start_time": "0:00", "heading": "チャプターの見出し（15文字程度）", "summary": "このチャプターの要点を日本語2〜3文で。銘柄名・数値・結論などの具体情報を優先すること"}
  ]
}

チャプター数は動画の長さに応じて適切な数（目安3〜10個）にしてください。
投資判断に関わる具体的な情報（銘柄名、価格水準、時期、根拠）を優先的に拾ってください。
"""

DAILY_DIGEST_PROMPT_TEMPLATE = """あなたは複数の投資解説YouTubeチャンネルの内容を横断して読み、
今後の投資戦略の参考になる形にまとめるアシスタントです。

以下は直近に配信・投稿された動画のチャンネル別・チャプター別の要約です。

{summaries_text}

これらを踏まえて、次の構成で日本語のダイジェストを作成してください。
1. 各チャンネルで語られていた注目トピック・銘柄・相場観の共通点や相違点
2. 今日以降、注目すべきポイント（イベント・指標・銘柄など）
3. 簡単な総括（3〜5行程度）

前提として、これは各チャンネルの発言内容の要約であり、あなた自身の投資助言ではないことが
伝わる書き方にしてください。断定的な「買い」「売り」の推奨ではなく、「〇〇氏は〜と述べていた」
という紹介の形式を基本とします。全体で2000文字程度に収めてください。
"""


def get_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def analyze_video_chapters(client: genai.Client, video_url: str, model: str = DEFAULT_MODEL) -> list[dict] | None:
    """動画をGeminiに解析させ、チャプターのリストを返す。失敗時はNone。"""
    try:
        response = client.models.generate_content(
            model=model,
            contents=types.Content(
                parts=[
                    types.Part(file_data=types.FileData(file_uri=video_url)),
                    types.Part(text=CHAPTER_PROMPT),
                ]
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        data = json.loads(response.text)
        chapters = data.get("chapters")
        if not isinstance(chapters, list) or not chapters:
            return None
        return chapters
    except Exception:
        return None


def build_daily_digest(client: genai.Client, summaries_text: str, model: str = DEFAULT_MODEL) -> str | None:
    """直近の要約テキストを渡し、横断的な投資戦略ダイジェストを生成する。失敗時はNone。"""
    try:
        prompt = DAILY_DIGEST_PROMPT_TEMPLATE.format(summaries_text=summaries_text)
        response = client.models.generate_content(model=model, contents=prompt)
        text = (response.text or "").strip()
        return text or None
    except Exception:
        return None
