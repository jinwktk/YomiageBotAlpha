# YomiageBot Alpha 開発メモ

## プロジェクト概要
- Discord TTS Bot (Text-to-Speech)
- Style-Bert-VITS2 API使用
- Phase1: 基本機能実装完了

## 2025-09-07 ファイル添付機能実装・修正完了

### ✅ 実装内容
1. **ファイル添付検出機能**
   - `bot/cogs/tts_handler.py`の`on_message`メソッドを修正
   - `message.attachments`でファイル添付を検出
   - ファイル添付時に「ファイル」を読み上げテキストに追加

2. **英語発音対応検討**
   - Style-Bert-VITS2 APIの言語設定を調査
   - "AUTO"は未対応、"JP", "EN", "ZH"のみ対応確認
   - 現在は"JP"設定で動作

### ✅ 修正・デバッグ作業
1. **API言語設定エラー修正**
   - エラー: `Input should be 'JP', 'EN' or 'ZH', input:"AUTO"`
   - 修正: `tts_api.py`の`language`設定を"JP"に変更
   - Bot再起動で完全修正

2. **ファイル添付検出ロジック修正**
   - デバッグログのステップ番号を整理
   - Step 4: テキスト内容検出
   - Step 5: ファイル添付検出
   - ユーザーフィードバックに基づく問題特定・修正

### 🧪 テスト結果
**WebHookテスト実行 (test_file_attachment.py)**
- テスト1: 「ファイルをアップロードします」+ ファイル → 「ファイルをアップロードします ファイル」読み上げ ✅
- テスト2: ファイルのみ → 「ファイル」のみ読み上げ ✅  
- テスト3: 「3つ目のファイルです」+ ファイル → 「3つ目のファイルです ファイル」読み上げ ✅

**音声合成・再生確認**
- 音声ファイルサイズ: 225KB、61KB、204KB
- FFmpeg再生: 全て正常終了
- キャッシュ機能: 正常動作

### 📝 技術的詳細
**修正ファイル**:
- `bot/cogs/tts_handler.py`: ファイル添付検出ロジック追加
- `bot/utils/tts_api.py`: 言語設定"AUTO"→"JP"修正

**実装コード**:
```python
# ファイル添付がある場合
if message.attachments:
    if text_to_process:
        text_to_process += " ファイル"
    else:
        text_to_process = "ファイル"
    logger.info(f"[DEBUG] Step 5: File attachment detected - {len(message.attachments)} files")
```

### 🚀 現在の状態
- **Bot Status**: 正常動作中 (Session ID: 0dba0d690403615b82f8cb9c4d0f1da3)
- **ボイスチャンネル**: 自動参加機能正常
- **TTS機能**: 完全動作
- **ファイル添付**: 完全対応
- **英語発音**: API制限により未対応（将来的検討事項）

## 2025-09-07 英語発音対応テスト・調査結果

### ❌ EN言語設定の問題発見
1. **APIエラー500発生**
   - Style-Bert-VITS2 APIで言語設定「EN」にするとエラー500発生
   - 日本語混在テキスト: `Hello world 英語を読み上げる` → APIエラー500
   - 純粋英語テキスト: `Hello`, `Hello world`, `Thank you so much` → APIエラー500

2. **根本原因の特定**
   - **Omochiモデル（model_id: 7）がEN言語設定に非対応**
   - EN設定時に純粋英語テキストでもAPIエラー発生
   - Style-Bert-VITS2の特定モデルと言語設定の互換性問題

### 🔍 検証済み事実
- JP設定: 日本語・英語混在テキストで正常動作（日本語読み）
- EN設定: あらゆるテキストでAPIエラー500発生
- Omochiモデルは日本語専用モデルの可能性が高い

### 📝 技術的詳細
**実行テストファイル**:
- `tmp/test_english_messages.py`: 日本語混在英語テスト
- `tmp/test_pure_english_messages.py`: 純粋英語テスト

**エラーログ**:
```
[ERROR] bot.utils.tts_api: TTS API error 500: Internal Server Error
[ERROR] bot.cogs.tts_handler: TTS API error for message: Unexpected error: API error 500: Internal Server Error
```

### 🚀 現在の状態
- **Bot Status**: EN設定でAPIエラー発生中
- **言語設定**: "EN"（要JP復元）
- **必要な対応**: JP設定に戻して安定動作を確保
- **ユーザー要求**: 「ハローワールド」「せんきゅーそーまっち」英語発音希望

### 🔮 今後の検討事項
1. **英語対応モデルの調査**: jvnv-F1-jp等の他モデルでEN言語設定対応確認
2. **言語自動検出機能**: テキスト内容に応じて動的に言語設定を変更
3. **英語専用読み上げ機能**: 英語部分のみ抽出してEN設定で処理
4. **代替TTS API**: 英語発音に特化した別のTTS APIの検討
5. **現実的な対応**: JP設定での英語読み上げ品質向上検討