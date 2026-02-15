# Family Schedule Planner

子どもの習い事スケジュールを管理・比較するWebアプリです。

## 機能

- 習い事候補の一覧管理（人物・曜日フィルター、ソート、CSV出力）
- 3パターンの比較カレンダー（月謝合計、曜日別集計、重複検知）
- 家族情報・条件の管理
- Google Sheets 連携（オプション）

## デモ

サンプルデータで動作を確認できます。Render の無料プランではデータはリデプロイ時にリセットされます。

## ローカル開発

```bash
pip install -r requirements.txt
python schedule_app.py
# http://localhost:5001/ でアクセス
```

デバッグモードを有効にするには：

```bash
FLASK_DEBUG=true python schedule_app.py
```

## Render へのデプロイ

1. このリポジトリを Fork または Clone
2. [Render](https://render.com) で「New Web Service」を作成
3. リポジトリを接続（設定は `render.yaml` で自動検出されます）

## Google Sheets 連携（オプション）

1. Google Cloud Console でサービスアカウントを作成
2. `credentials.json` をプロジェクトルートに配置
3. 環境変数 `GOOGLE_SHEETS_ID` にスプレッドシートのIDを設定

```bash
# .env ファイルに記載
GOOGLE_SHEETS_ID=your_spreadsheet_id_here
```

## 技術スタック

- Python / Flask
- シングルファイル構成（HTML/CSS/JS 埋め込み）
- JSON ファイルベースのデータ保存
- gunicorn（本番用 WSGI サーバー）
