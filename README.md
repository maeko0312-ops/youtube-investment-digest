# YouTube投資チャンネル要約 → LINEグループ通知ツール

指定した投資解説YouTubeチャンネルの新着動画・ライブ配信を検知し、Geminiでチャプターごとに
要約した資料をLINEグループへ自動投稿します。さらに毎朝5:00(JST)に、直近の内容を横断した
「今後の投資戦略ダイジェスト」も投稿します。GitHub Actionsで動くため、自分のPCを起動して
おく必要はありません。すべて無料枠の範囲で動く前提で作られています。

> **免責**: このツールが送る内容は、各チャンネルの発言・解説を要約したものであり、
> 個人向けの投資助言ではありません。投資判断はご自身の責任で行ってください。

## できること / できないこと

- できること: 新着・ライブ終了の検知（RSSポーリング、20分間隔）、Geminiによる動画のチャプター
  分割・要約（文字起こしの別取得は不要）、LINEグループへのpush配信、日次ダイジェスト
- できないこと・注意点:
  - リアルタイム通知ではありません（ポーリング間隔分の遅延があります）
  - Geminiの動画解析はプレビュー機能のため、失敗時はタイトルのみの簡易メッセージにフォールバックします
  - LINEの無料プランは月200通までです。超過すると送信は失敗しますが、課金はされません
  - ライブ配信は「配信終了後」にまとめて処理されます（配信中はスキップされ、終了を検知してから要約します）

## 公開範囲について（public リポジトリでの運用）

GitHub Actionsの実行時間を無制限にするため、このリポジトリは **public**（誰でも閲覧可能）で
運用する前提です。以下を踏まえた設計にしています。

- **コード・ワークフロー定義**は公開されますが、中身にAPIキー等は一切含まれません（すべて
  GitHub Secretsから環境変数として読み込みます）
- **Gemini が生成したチャプター要約・日次ダイジェストの本文は、どこにも保存しません。**
  `state/`以下にgitコミットされるのは、動画ID・チャンネル名・タイトルなど元々YouTube上で
  公開されている情報のみです。日次ダイジェスト（`daily_digest.py`）を作る際は、保存しておいた
  情報から改めてGeminiに動画を解析させて要約を作り直します（生成した要約はLINEへ送信したら
  破棄され、git履歴にもファイルにも残りません）
- Actions の実行ログ（誰でも閲覧可）には、処理した動画のチャンネル名・タイトルが出力されます。
  これらは元々YouTube上で公開されている情報です
- `channels.json` に監視対象チャンネルの一覧が含まれます。どのチャンネルをフォローしているかは
  リポジトリを見れば分かる状態になります

## 事前準備（あなた自身が行う必要がある手順）

セキュリティ上の理由から、アカウント作成やAPIキー・パスワードの入力はご自身で行ってください。
私（Claude）にAPIキーなどの値を共有する必要はありません。

### 1. YouTube Data API v3 のAPIキーを取得

1. [Google Cloud Console](https://console.cloud.google.com/) で新しいプロジェクトを作成
2. 「APIとサービス」→「ライブラリ」で **YouTube Data API v3** を検索して有効化
3. 「認証情報」→「認証情報を作成」→「APIキー」でキーを発行
   - 必要であれば「APIの制限」で YouTube Data API v3 のみに絞ると安全です

### 2. Gemini APIキーを取得（無料）

1. [Google AI Studio](https://aistudio.google.com/) にアクセスし、Googleアカウントでログイン
2. 「Get API key」からAPIキーを発行
   - **注意**: このプロジェクトに課金を有効化すると無料枠が失われ、最初の呼び出しから課金対象になります。課金を有効化しない状態のまま使ってください

### 3. LINE Messaging API のチャンネルを作成

1. [LINE Developers](https://developers.line.biz/) にログイン（LINEアカウントでログイン可）
2. 新規プロバイダーを作成 → 「Messaging API」チャンネルを作成（無料のコミュニケーションプランでOK）
3. チャンネル基本設定の「Messaging API設定」タブで **チャンネルアクセストークン（長期）** を発行
4. 同タブで「応答メッセージ」をオフ、「Webhookの利用」は後述の手順のときだけオンにする

### 4. Botを通知先のLINEグループに招待

1. LINE Developersのチャンネル画面にあるQRコード／Bot Basic IDで、作成したBotを友だち追加
2. 通知したいLINEグループにそのBotを招待する

### 5. グループIDを取得する（初回のみ・少し手間がかかります）

Messaging APIでグループにpushするには `groupId` が必要です。これはBotがグループ内の
メッセージを一度受信（Webhook）しないと分かりません。

1. [webhook.site](https://webhook.site) を開き、表示された固有URLをコピー
2. LINE Developersの「Messaging API設定」→「Webhook URL」に、そのURLを貼り付けて保存し、
   「Webhookの利用」をオンにする
3. LINEアプリで、Botを招待したグループ内で何かひとこと発言する
4. webhook.siteの画面に届いたリクエストのJSON本文を確認し、`"source":{"type":"group","groupId":"C..."}`
   の `groupId` の値をメモする
5. 確認できたら、LINE Developersの「Webhookの利用」は再びオフに戻してよい（このツールは
   push専用で、受信は使わないため）

### 6. GitHubリポジトリを用意する

1. GitHubで新しい **public** リポジトリを作成する（Actionsの実行時間が無制限になるため）
   - コードのみを公開し、APIキー等は次のSecretsに保存するので中身が漏れることはありません
2. このフォルダの中身をそのリポジトリにpushする
3. リポジトリの Settings → Secrets and variables → Actions → "New repository secret" で、
   以下の4つを登録する（値はGitHubの画面上で直接入力してください）
   - `YOUTUBE_API_KEY`
   - `GEMINI_API_KEY`
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `LINE_GROUP_ID`（手順5でメモした `C` から始まる文字列）

## 動作確認

Secretsを登録したら、GitHubの「Actions」タブから以下をそれぞれ手動実行（`Run workflow`）して
確認してください。

- **Check new videos**: 新着があればLINEにメッセージが届く。新着が無ければログに「新着なし」と出る
- **Daily investment digest**: 直近の要約が無ければ「新着はありませんでした」という短いメッセージが届く。
  一度 Check new videos を成功させてから試すと、実際のダイジェスト生成まで確認できる

その後は、`check.yml` が20分おき、`daily.yml` が毎朝5:00(JST)頃に自動実行されます
（GitHub Actionsの仕様上、実際の実行時刻は数分〜数十分ずれることがあります）。

## 監視チャンネルの追加・変更

`channels.json` の `channels` 配列に `{ "id": "チャンネルID", "name": "表示名" }` を
追加・削除するだけです。チャンネルIDは `https://www.youtube.com/channel/UCxxxxx` の
`UCxxxxx` の部分、またはチャンネルのRSSフィード (`view-source:` でチャンネルページを開き
`"channelId":"UC..."` を探す) から確認できます。

現在の設定（9チャンネル）:

- NOBU塾
- Sho's投資情報局
- 株の買い時を考えるチャンネル
- Dan Takahashi (Japanese)
- 馬渕磨理子の株式クラブ
- オレ的ゲーム速報JIN FX・株投資部
- おーちゃん【元外銀マン】
- FX龍王【ドル円予想】
- 上岡正明【MBA保有・累計31冊ビジネス作家】

9チャンネルはやや多めなので、投稿・配信の頻度によってはLINEの月200通枠やGeminiの
1日8時間分の動画解析枠に近づく可能性があります。枠を使い切った場合、その回の送信・解析は
スキップされるだけで、次の期間になれば自動的に復帰します。

## ローカルでのテスト

外部通信を伴わないロジック（LINEメッセージの組み立て・文字数分割）だけは、この
リポジトリ単体でテストできます。

```bash
pip install -r requirements.txt
python tests/test_line_formatting.py
```

## トラブルシューティング

- **動画解析が毎回失敗する**: Gemini APIキーが正しいか、対象動画が非公開・年齢制限などで
  Geminiからアクセスできない動画でないかを確認してください。失敗してもタイトルのみの
  メッセージは届くようになっています。
- **LINEにメッセージが届かない**: チャンネルアクセストークンの有効期限切れ、`LINE_GROUP_ID`
  の誤り、月200通の上限超過のいずれかが多いです。Actionsのログに `[line] push failed` や
  `[line] push error` が出ていないか確認してください。
- **Actionsが動かない/遅い**: publicリポジトリでもGitHub全体が混雑していると、schedule実行が
  数十分遅れることがあります（GitHub側の既知の挙動です）。`workflow_dispatch` で手動実行すれば
  即座に動作確認できます。
