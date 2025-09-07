# YomiageBot Alpha

Discord Text-to-Speech Bot powered by Style-Bert-VITS2 API

## 概要

YomiageBot Alphaは、Discord上のテキストメッセージを自動的に音声で読み上げるBotです。Style-Bert-VITS2 APIを使用して高品質な日本語音声合成を提供します。

## 機能

### ✅ Phase 1 実装済み機能

#### ボイスチャンネル管理
- **自動参加**: ユーザーがボイスチャンネルに参加すると自動的にBotも参加
- **自動退出**: 全ユーザーが退出するとBotも自動退出
- **音声通知**: 参加時「○○さん、こんちゃ」、退出時「○○さん、またね」

#### TTS機能
- **全チャンネル対応**: サーバー内の全テキストチャンネルのメッセージを読み上げ
- **Style-Bert-VITS2連携**: 高品質な日本語音声合成
- **テキスト前処理**: URL置換、文字数制限対応
- **ファイル添付対応**: ファイル添付時に「ファイル」を読み上げ

#### キャッシュシステム
- **音声キャッシュ**: 同一テキストの重複生成を防止
- **自動クリーンアップ**: 期限切れキャッシュを自動削除

## セットアップ

### 1. 必要な環境
- Python 3.13+
- Discord Bot Token
- Style-Bert-VITS2 API サーバー

### 2. インストール
```bash
git clone https://github.com/your-username/yomiageBotAlpha.git
cd yomiageBotAlpha
pip install -r requirements.txt
```

### 3. 環境変数設定
`.env` ファイルを作成し、以下を設定：
```env
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=your_guild_id
TTS_API_URL=http://192.168.0.99:5000
```

### 4. 実行
```bash
python main.py
```

## API設定

### Style-Bert-VITS2 デフォルト設定
- **Model**: Omochi (model_id: 7)
- **Speaker**: 0
- **Style**: Neutral
- **Language**: JP

## プロジェクト構成

```
yomiageBotAlpha/
├── main.py              # エントリーポイント
├── bot/
│   ├── client.py        # Discord Bot クライアント
│   ├── cogs/
│   │   ├── voice_manager.py    # ボイスチャンネル管理
│   │   └── tts_handler.py      # TTS処理
│   └── utils/
│       ├── tts_api.py          # Style-Bert-VITS2 API クライアント
│       ├── cache_manager.py    # キャッシュ管理
│       └── text_processor.py   # テキスト前処理
├── tmp/tests/          # テストファイル
├── cache/              # 音声キャッシュ（自動生成）
├── logs/               # ログファイル（自動生成）
├── requirements.txt    # 依存関係
├── .env               # 環境変数（要作成）
└── memo.md            # 開発メモ
```

## 技術仕様

### 対応モデル
- jvnv-F1-jp, jvnv-F2-jp, jvnv-M1-jp, jvnv-M2-jp
- 小春音アミ, あみたろ, miiyue, **Omochi（デフォルト）**

### 制約事項
- **英語発音**: 現在のOmochiモデルは英語発音に対応していません
- **文字数制限**: 1-100文字（API制限）
- **言語設定**: JP専用（EN設定でAPI エラー発生）

## 開発履歴

### Phase 1 (完了)
- ✅ 基本TTS機能実装
- ✅ ボイスチャンネル管理
- ✅ 音声通知機能
- ✅ キャッシュシステム
- ✅ ファイル添付対応

### Phase 2 (予定)
- 🔄 音声録音・リプレイ機能
- 🔄 `/replay` コマンド実装

### Phase 3 (予定)
- 🔄 サーバー間音声リレー機能

## ライセンス

MIT License

## 貢献

プルリクエストや Issue は歓迎です。

## トラブルシューティング

### よくある問題

#### 1. Bot が音声を読み上げない
- Style-Bert-VITS2 APIサーバーが起動しているか確認
- `.env` ファイルの `TTS_API_URL` が正しいか確認

#### 2. Bot がボイスチャンネルに参加しない
- Bot に適切な権限（ボイスチャンネルへの接続・発言）が付与されているか確認

#### 3. 英語が正しく発音されない
- 現在のOmochiモデルは英語発音に対応していません（日本語読み）
- 将来的な改善予定

## サポート

質問や問題がある場合は、Issue を作成してください。