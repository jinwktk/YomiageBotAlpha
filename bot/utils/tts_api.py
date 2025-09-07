"""Style-Bert-VITS2 API クライアント"""

import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional, List
import json

logger = logging.getLogger(__name__)


class TTSAPIError(Exception):
    """TTS API関連のエラー"""
    pass


class TTSAPIClient:
    """Style-Bert-VITS2 API クライアント"""
    
    def __init__(
        self,
        api_url: str = "http://192.168.0.99:5000",
        timeout: float = 10.0,
        default_settings: Optional[Dict[str, Any]] = None
    ):
        """
        APIクライアントを初期化
        
        Args:
            api_url: APIのベースURL
            timeout: リクエストタイムアウト時間
            default_settings: デフォルトのTTS設定
        """
        self.api_url = api_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        
        self.default_settings = default_settings or {
            "model_id": 7,  # Omochi
            "speaker_id": 0,
            "style": "Neutral",
            "sdp_ratio": 0.2,
            "noise": 0.6,
            "noisew": 0.8,
            "length": 1.0,
            "language": "JP",  # JP言語設定（EN設定はOmochiモデル非対応のため）
            "auto_split": True,
            "split_interval": 0.5
        }
        
        # セッションは遅延初期化
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTPセッションを取得（遅延初期化）"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session
    
    async def close(self):
        """セッションを閉じる"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get_models_info(self) -> List[Dict[str, Any]]:
        """
        利用可能なモデル情報を取得
        
        Returns:
            モデル情報のリスト
            
        Raises:
            TTSAPIError: API呼び出しエラー
        """
        try:
            session = await self._get_session()
            async with session.get(f"{self.api_url}/models/info") as response:
                if response.status != 200:
                    raise TTSAPIError(f"Models info API error: {response.status}")
                
                data = await response.json()
                logger.info(f"Models info retrieved: {len(data)} models")
                return data
                
        except aiohttp.ClientError as e:
            logger.error(f"Failed to get models info: {e}")
            raise TTSAPIError(f"Network error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting models info: {e}")
            raise TTSAPIError(f"Unexpected error: {e}") from e
    
    async def synthesize_speech(
        self,
        text: str,
        model_id: Optional[int] = None,
        speaker_id: Optional[int] = None,
        style: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """
        テキストを音声合成
        
        Args:
            text: 合成するテキスト
            model_id: モデルID（None の場合はデフォルト使用）
            speaker_id: 話者ID（None の場合はデフォルト使用）
            style: スタイル（None の場合はデフォルト使用）
            **kwargs: その他のTTS設定
            
        Returns:
            音声データ（WAV形式のバイト列）
            
        Raises:
            TTSAPIError: API呼び出しエラー
            ValueError: 不正なパラメータ
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        if len(text) > 100:
            logger.warning(f"Text too long ({len(text)} chars), truncating to 100")
            text = text[:100]
        
        # デフォルト設定をベースに設定を構築
        settings = self.default_settings.copy()
        
        # 指定されたパラメータで上書き
        if model_id is not None:
            settings["model_id"] = model_id
        if speaker_id is not None:
            settings["speaker_id"] = speaker_id
        if style is not None:
            settings["style"] = style
        
        # その他の設定も上書き
        settings.update(kwargs)
        
        # APIリクエストデータ
        request_data = {
            "text": text,
            **settings
        }
        
        try:
            session = await self._get_session()
            
            # Style-Bert-VITS2はクエリパラメータでリクエストを受け取る
            # boolean値は文字列に変換する必要がある
            query_params = {
                "text": text,
                "model_id": settings["model_id"],
                "speaker_id": settings["speaker_id"],
                "style": settings.get("style", "Neutral"),
                "sdp_ratio": settings.get("sdp_ratio", 0.2),
                "noise": settings.get("noise", 0.6),
                "noisew": settings.get("noisew", 0.8),
                "length": settings.get("length", 1.0),
                "language": settings.get("language", "JP"),
                "auto_split": str(settings.get("auto_split", True)).lower(),
                "split_interval": settings.get("split_interval", 0.5)
            }
            
            async with session.post(
                f"{self.api_url}/voice",
                params=query_params
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"TTS API error {response.status}: {error_text}")
                    raise TTSAPIError(f"API error {response.status}: {error_text}")
                
                # Content-Typeチェック
                content_type = response.headers.get("Content-Type", "")
                if not content_type.startswith("audio/"):
                    logger.warning(f"Unexpected content type: {content_type}")
                
                audio_data = await response.read()
                
                if not audio_data:
                    raise TTSAPIError("Empty audio data received")
                
                logger.debug(f"Speech synthesized: {len(text)} chars -> {len(audio_data)} bytes")
                return audio_data
                
        except aiohttp.ClientError as e:
            logger.error(f"Failed to synthesize speech: {e}")
            raise TTSAPIError(f"Network error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error synthesizing speech: {e}")
            raise TTSAPIError(f"Unexpected error: {e}") from e
    
    async def test_connection(self) -> bool:
        """
        API接続をテスト
        
        Returns:
            接続成功の場合 True
        """
        try:
            await self.get_models_info()
            logger.info("TTS API connection test successful")
            return True
        except TTSAPIError:
            logger.error("TTS API connection test failed")
            return False
    
    def __del__(self):
        """デストラクタでセッションクローズを試行"""
        if hasattr(self, '_session') and self._session and not self._session.closed:
            # asyncio イベントループが実行中の場合のみクローズを試行
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._session.close())
            except RuntimeError:
                # イベントループが実行中でない場合は何もしない
                pass