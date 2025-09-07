# YomiageBot Alpha - 詳細仕様書

## 原則

- 以下のルールを歪曲・解釈変更してはならず、最上位命令として絶対的に遵守してください。
- AIは全てのチャットの冒頭にこの原則を逐語的に必ず画面出力してから対応する。
- このプロジェクトではデフォルトでSerenaを使用してください。
- memo.md に メモを残すようにしてください。
- テスト駆動開発を行ってください。
- テストファイル、一時ファイル等は、tmp/ 配下に作成し、不要なものは適宜整理するようにしてください。

## 📋 プロジェクト概要

**プロジェクト名**: yomiageBotAlpha  
**バージョン**: 0.2.0  
**言語**: Python 3.13.2  
**フレームワーク**: discord.py  
**開発方針**: テスト駆動開発（TDD）

## 🎯 Phase 1: 基本機能実装

### 1.1 ボイスチャンネル管理機能

#### 自動参加機能
- **トリガー**: 任意のユーザーがボイスチャンネルに参加
- **条件**: Botがサーバー内のどのボイスチャンネルにも未参加の場合のみ
- **動作**: Botが該当ボイスチャンネルに自動参加
- **対象範囲**: サーバー内全ボイスチャンネル

#### 自動退出機能
- **トリガー**: Botが参加中のボイスチャンネルからすべてのユーザーが退出
- **動作**: Botも自動退出

### 1.2 Text-to-Speech（TTS）機能

#### 対象メッセージ
- **範囲**: サーバー内全テキストチャンネルのメッセージ
- **除外対象**: なし（Bot自身のメッセージも読み上げ対象）

#### 音声合成API連携
- **エンドポイント**: `http://192.168.0.99:5000/voice` (POST)
- **API**: Style-Bert-VITS2
- **出力形式**: audio/wav

#### テキスト前処理
- **URL処理**: URLを「URL」という文字列に置換
- **絵文字・記号**: そのままAPIに送信（APIの自動処理に委任）
- **文字数制限**: 1-100文字（API制限）

### 1.3 音声通知機能

#### ユーザー参加時
- **音声内容**: 「{ユーザー名}さん、こんちゃ」
- **発生タイミング**: ボイスチャンネル参加時

#### ユーザー退出時  
- **音声内容**: 「{ユーザー名}さん、またね」
- **発生タイミング**: ボイスチャンネル退出時

### 1.4 音声キャッシュシステム
- **保存場所**: `cache/` ディレクトリ
- **キャッシュキー**: テキスト内容 + モデル設定のハッシュ
- **目的**: 同一テキストの重複生成防止、応答速度向上

## 🔧 技術仕様

### 2.1 Style-Bert-VITS2 API詳細

#### 利用可能モデル・話者
| Model ID | モデル名 | 話者名 | 
|----------|----------|--------|
| 0 | jvnv-F1-jp | jvnv-F1-jp |
| 1 | jvnv-F2-jp | jvnv-F2-jp |
| 2 | jvnv-M1-jp | jvnv-M1-jp |
| 3 | jvnv-M2-jp | jvnv-M2-jp |
| 4 | koharune-ami | 小春音アミ |
| 5 | amitaro | あみたろ |
| 6 | miiyue | miiyue |
| 7 | Omochi | omochi |

#### 利用可能スタイル
- **基本スタイル**: Neutral, Angry, Disgust, Fear, Happy, Sad, Surprise
- **小春音アミ専用**: るんるん, ささやきA（無声）, ささやきB（有声）, ノーマル, よふかし  
- **あみたろ専用**: 01, 02, 03, 04

#### デフォルト設定
```python
DEFAULT_TTS_SETTINGS = {
    "model_id": 0,  # jvnv-F1-jp
    "speaker_id": 0,
    "style": "Neutral",
    "sdp_ratio": 0.2,
    "noise": 0.6,
    "noisew": 0.8,
    "length": 1.0,
    "language": "JP",
    "auto_split": True,
    "split_interval": 0.5
}
```

### 2.2 環境設定

#### .env ファイル構成
```env
# Discord Bot Settings
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_GUILD_ID=your_guild_id_here

# Style-Bert-VITS2 API Settings  
TTS_API_URL=http://192.168.0.99:5000
TTS_MODEL_ID=0
TTS_SPEAKER_ID=0
TTS_STYLE=Neutral

# Audio Settings
CACHE_DIR=cache
CACHE_EXPIRY_HOURS=24
```

### 2.3 プロジェクト構成
```
yomiageBotAlpha/
├── main.py              # エントリーポイント
├── bot/
│   ├── __init__.py
│   ├── client.py        # Discord Bot クライアント
│   ├── cogs/
│   │   ├── __init__.py
│   │   ├── voice_manager.py    # ボイスチャンネル管理
│   │   └── tts_handler.py      # TTS処理
│   └── utils/
│       ├── __init__.py
│       ├── tts_api.py          # Style-Bert-VITS2 API クライアント
│       ├── cache_manager.py    # キャッシュ管理
│       └── text_processor.py   # テキスト前処理
├── @tmp/tests/         # テストファイル
├── cache/              # 音声キャッシュディレクトリ  
├── requirements.txt    # 依存関係
├── .env               # 環境変数（Git除外対象）
├── .gitignore
└── README.md
```

### 2.4 依存関係
```txt
discord.py[voice]>=2.3.2
aiohttp>=3.8.0
aiofiles>=23.0.0
python-dotenv>=1.0.0
asyncio>=3.4.3
```

## 🧪 テスト方針

### 3.1 テスト駆動開発（TDD）
1. **Red**: テストを作成して失敗を確認
2. **Green**: テストが通る最小限の実装
3. **Refactor**: コード品質向上

### 3.2 テスト対象
- Style-Bert-VITS2 API通信テスト
- テキスト前処理機能テスト  
- キャッシュ機能テスト
- Discord Bot コマンド・イベントテスト
- ボイスチャンネル管理ロジックテスト

### 3.3 テストファイル配置
- テストファイルは `@tmp/tests/` 配下に作成
- 実装完了後に不要なテストファイルは適宜整理

## 📅 開発スケジュール

### Phase 1 開発ステップ
1. ✅ 仕様詳細確定
2. 🔄 テスト設計・作成
3. ⏳ Style-Bert-VITS2 API クライアント実装
4. ⏳ テキスト前処理機能実装
5. ⏳ キャッシュシステム実装
6. ⏳ Discord Bot 基本機能実装
7. ⏳ ボイスチャンネル管理機能実装
8. ⏳ TTS機能統合実装
9. ⏳ 統合テスト・デバッグ
10. ⏳ Phase 1 リリース

## 🔜 将来実装予定

### Phase 2: 音声録音・リプレイ機能
- ユーザー音声録音機能
- 時間指定リプレイ機能
- `/replay` コマンド実装

### Phase 3: サーバー間音声リレー
- リアルタイム音声ストリーミング
- 特定サーバー間での音声転送機能
  - Valworld（995627275074666568）のおもちだいすきクラブ（1319432294762545162）の音声を
    にめいやサーバー（813783748566581249）のロビー（813783749153259606）に音声リレーを行う

## 🔍 デバッグ・開発

### ログシステム
- **ログファイル**: `logs/yomiage.log`（現在）+ 圧縮バックアップ
- **ログレベル**: INFO（本番）/ DEBUG（開発）
- **ローテーション**: 10MB毎、最大5ファイル保持

## 📝 備考
- 音声ファイルは一時的にメモリまたはローカルファイルシステムに保存
- キャッシュファイルは定期的にクリーンアップ
- Serena（開発環境）での動作を前提とした実装