"""テキスト前処理機能"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TextProcessor:
    """テキスト前処理クラス"""
    
    # URL検出用の正規表現パターン
    URL_PATTERN = re.compile(
        r'https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?'
        r'|ftp://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*)?',
        re.IGNORECASE
    )
    
    # より簡単なURL検出パターン（念のため）
    SIMPLE_URL_PATTERN = re.compile(
        r'(?:https?|ftp)://[^\s]+',
        re.IGNORECASE
    )
    
    def __init__(self, max_length: int = 100):
        """
        テキストプロセッサを初期化
        
        Args:
            max_length: 最大文字数制限
        """
        self.max_length = max_length
    
    def replace_urls(self, text: str) -> str:
        """
        テキスト内のURLを「URL」に置換
        
        Args:
            text: 処理対象のテキスト
            
        Returns:
            URL置換後のテキスト
        """
        if not text:
            return text
        
        # メインパターンでURL置換
        processed_text = self.URL_PATTERN.sub('URL', text)
        
        # 念のため、シンプルなパターンでも置換
        processed_text = self.SIMPLE_URL_PATTERN.sub('URL', processed_text)
        
        # 置換が発生した場合はログ出力
        if processed_text != text:
            logger.debug(f"URL replaced: '{text}' -> '{processed_text}'")
        
        return processed_text
    
    def validate_text_length(self, text: str) -> bool:
        """
        テキスト長さを検証
        
        Args:
            text: 検証対象のテキスト
            
        Returns:
            有効な場合 True、無効な場合 False
        """
        if not isinstance(text, str):
            return False
        
        if not text or not text.strip():
            return False
        
        if len(text) > self.max_length:
            return False
        
        return True
    
    def truncate_text(self, text: str) -> str:
        """
        テキストを最大長に切り詰め
        
        Args:
            text: 切り詰め対象のテキスト
            
        Returns:
            切り詰め後のテキスト
        """
        if not text:
            return text
        
        if len(text) <= self.max_length:
            return text
        
        truncated = text[:self.max_length]
        logger.debug(f"Text truncated: {len(text)} -> {len(truncated)} chars")
        return truncated
    
    def clean_text(self, text: str) -> str:
        """
        テキストをクリーンアップ（絵文字・記号は保持）
        
        Args:
            text: クリーンアップ対象のテキスト
            
        Returns:
            クリーンアップ後のテキスト
        """
        if not text:
            return text
        
        # 現在は絵文字・記号をそのまま保持するため、
        # 特別な処理は行わない（APIに委任）
        return text.strip()
    
    def process_message_text(self, text: str) -> Optional[str]:
        """
        メッセージテキストの完全処理
        
        Args:
            text: 処理対象のメッセージテキスト
            
        Returns:
            処理後のテキスト。無効な場合は None
        """
        if not text:
            return None
        
        # 1. テキストクリーンアップ
        processed = self.clean_text(text)
        
        # 2. URL置換
        processed = self.replace_urls(processed)
        
        # 3. 長さ制限
        processed = self.truncate_text(processed)
        
        # 4. 最終検証
        if not self.validate_text_length(processed):
            logger.debug(f"Text validation failed: '{text}' -> '{processed}'")
            return None
        
        # 処理内容をログ出力（デバッグ時のみ）
        if processed != text:
            logger.debug(f"Text processed: '{text}' -> '{processed}'")
        
        return processed
    
    def extract_display_name_from_mention(self, text: str) -> str:
        """
        メンション文字列から表示名を抽出（将来的な機能拡張用）
        
        Args:
            text: メンション文字列 (<@!123456789> など)
            
        Returns:
            表示名（現在は元の文字列をそのまま返す）
        """
        # Discord のメンション形式: <@123456789> または <@!123456789>
        mention_pattern = re.compile(r'<@!?(\d+)>')
        
        # 現在はそのまま返すが、将来的には実際のユーザー名に
        # 変換する機能を実装予定
        return text
    
    def get_processing_stats(self) -> dict:
        """
        処理統計情報を取得（将来的な機能拡張用）
        
        Returns:
            統計情報辞書
        """
        return {
            "max_length": self.max_length,
            "url_pattern_count": 2,  # 使用している正規表現パターン数
        }