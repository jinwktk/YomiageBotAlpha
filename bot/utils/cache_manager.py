"""音声キャッシュシステム"""

import hashlib
import json
import os
import time
import asyncio
import aiofiles
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheManager:
    """音声キャッシュマネージャー"""
    
    def __init__(
        self,
        cache_dir: str = "cache",
        expiry_hours: int = 24,
        max_cache_size_mb: int = 500
    ):
        """
        キャッシュマネージャーを初期化
        
        Args:
            cache_dir: キャッシュディレクトリパス
            expiry_hours: キャッシュ有効期限（時間）
            max_cache_size_mb: 最大キャッシュサイズ（MB）
        """
        self.cache_dir = Path(cache_dir)
        self.expiry_hours = expiry_hours
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        
        # キャッシュディレクトリを作成
        self.cache_dir.mkdir(exist_ok=True)
        
        # ファイルアクセス用のロック
        self._file_locks: Dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()
        
        logger.info(f"Cache manager initialized: dir={cache_dir}, expiry={expiry_hours}h, max_size={max_cache_size_mb}MB")
    
    def _generate_cache_key(self, text: str, tts_settings: Dict[str, Any]) -> str:
        """
        キャッシュキーを生成
        
        Args:
            text: テキスト内容
            tts_settings: TTS設定
            
        Returns:
            ハッシュベースのキャッシュキー
        """
        # テキストと設定を組み合わせて一意なキーを生成
        key_data = {
            "text": text,
            "settings": tts_settings
        }
        
        # 辞書をソート済みJSONにシリアライズしてハッシュ化
        key_string = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        hash_object = hashlib.sha256(key_string.encode('utf-8'))
        return hash_object.hexdigest()[:16]  # 16文字に短縮
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """キャッシュファイルのパスを取得"""
        return self.cache_dir / f"{cache_key}.wav"
    
    def _get_metadata_file_path(self, cache_key: str) -> Path:
        """メタデータファイルのパスを取得"""
        return self.cache_dir / f"{cache_key}.meta"
    
    async def _get_file_lock(self, cache_key: str) -> asyncio.Lock:
        """ファイル固有のロックを取得"""
        async with self._locks_lock:
            if cache_key not in self._file_locks:
                self._file_locks[cache_key] = asyncio.Lock()
            return self._file_locks[cache_key]
    
    async def _write_metadata(self, cache_key: str, text: str, tts_settings: Dict[str, Any]):
        """メタデータを書き込み"""
        metadata = {
            "text": text,
            "tts_settings": tts_settings,
            "created_at": time.time(),
            "access_count": 1,
            "last_accessed": time.time()
        }
        
        metadata_path = self._get_metadata_file_path(cache_key)
        async with aiofiles.open(metadata_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(metadata, ensure_ascii=False, indent=2))
    
    async def _read_metadata(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """メタデータを読み込み"""
        metadata_path = self._get_metadata_file_path(cache_key)
        
        if not metadata_path.exists():
            return None
        
        try:
            async with aiofiles.open(metadata_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read metadata {cache_key}: {e}")
            return None
    
    async def _update_access_metadata(self, cache_key: str):
        """アクセス情報を更新"""
        metadata = await self._read_metadata(cache_key)
        if metadata:
            metadata["access_count"] = metadata.get("access_count", 0) + 1
            metadata["last_accessed"] = time.time()
            
            metadata_path = self._get_metadata_file_path(cache_key)
            async with aiofiles.open(metadata_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(metadata, ensure_ascii=False, indent=2))
    
    async def cache_exists(self, text: str, tts_settings: Dict[str, Any]) -> bool:
        """
        キャッシュが存在するかチェック
        
        Args:
            text: テキスト内容
            tts_settings: TTS設定
            
        Returns:
            キャッシュが存在し有効な場合 True
        """
        cache_key = self._generate_cache_key(text, tts_settings)
        cache_file = self._get_cache_file_path(cache_key)
        
        if not cache_file.exists():
            return False
        
        # 有効期限チェック
        metadata = await self._read_metadata(cache_key)
        if metadata:
            created_at = metadata.get("created_at", 0)
            expiry_time = created_at + (self.expiry_hours * 3600)
            
            if time.time() > expiry_time:
                logger.debug(f"Cache expired: {cache_key}")
                # 期限切れキャッシュを削除
                await self._delete_cache_files(cache_key)
                return False
        
        return True
    
    async def get_cached_audio(self, text: str, tts_settings: Dict[str, Any]) -> Optional[bytes]:
        """
        キャッシュされた音声データを取得
        
        Args:
            text: テキスト内容
            tts_settings: TTS設定
            
        Returns:
            音声データ。キャッシュが存在しない場合は None
        """
        cache_key = self._generate_cache_key(text, tts_settings)
        
        # キャッシュ存在チェック
        if not await self.cache_exists(text, tts_settings):
            return None
        
        # ファイルロックを取得
        file_lock = await self._get_file_lock(cache_key)
        async with file_lock:
            cache_file = self._get_cache_file_path(cache_key)
            
            try:
                async with aiofiles.open(cache_file, 'rb') as f:
                    audio_data = await f.read()
                
                # アクセス情報を更新
                await self._update_access_metadata(cache_key)
                
                logger.debug(f"Cache hit: {cache_key} ({len(audio_data)} bytes)")
                return audio_data
                
            except IOError as e:
                logger.error(f"Failed to read cache file {cache_key}: {e}")
                return None
    
    async def save_audio_cache(self, text: str, tts_settings: Dict[str, Any], audio_data: bytes):
        """
        音声データをキャッシュに保存
        
        Args:
            text: テキスト内容
            tts_settings: TTS設定
            audio_data: 音声データ
        """
        if not audio_data:
            logger.warning("Cannot cache empty audio data")
            return
        
        cache_key = self._generate_cache_key(text, tts_settings)
        
        # ファイルロックを取得
        file_lock = await self._get_file_lock(cache_key)
        async with file_lock:
            cache_file = self._get_cache_file_path(cache_key)
            
            try:
                # 音声ファイルを保存
                async with aiofiles.open(cache_file, 'wb') as f:
                    await f.write(audio_data)
                
                # メタデータを保存
                await self._write_metadata(cache_key, text, tts_settings)
                
                logger.debug(f"Cache saved: {cache_key} ({len(audio_data)} bytes)")
                
                # キャッシュサイズチェック・クリーンアップ
                await self._cleanup_if_needed()
                
            except IOError as e:
                logger.error(f"Failed to save cache {cache_key}: {e}")
    
    async def _delete_cache_files(self, cache_key: str):
        """キャッシュファイルとメタデータを削除"""
        cache_file = self._get_cache_file_path(cache_key)
        metadata_file = self._get_metadata_file_path(cache_key)
        
        for file_path in [cache_file, metadata_file]:
            try:
                if file_path.exists():
                    file_path.unlink()
            except OSError as e:
                logger.warning(f"Failed to delete {file_path}: {e}")
    
    async def _get_cache_size(self) -> int:
        """現在のキャッシュサイズを取得（バイト）"""
        total_size = 0
        for file_path in self.cache_dir.iterdir():
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size
    
    async def _cleanup_if_needed(self):
        """必要に応じてキャッシュをクリーンアップ"""
        current_size = await self._get_cache_size()
        
        if current_size <= self.max_cache_size_bytes:
            return
        
        logger.info(f"Cache size ({current_size / 1024 / 1024:.1f}MB) exceeds limit, cleaning up...")
        
        # メタデータ付きキャッシュファイルを収集
        cache_files = []
        for wav_file in self.cache_dir.glob("*.wav"):
            cache_key = wav_file.stem
            metadata = await self._read_metadata(cache_key)
            if metadata:
                cache_files.append({
                    "key": cache_key,
                    "size": wav_file.stat().st_size,
                    "last_accessed": metadata.get("last_accessed", 0),
                    "access_count": metadata.get("access_count", 0)
                })
        
        # LRU (最近使用頻度の低い順) でソート
        cache_files.sort(key=lambda x: (x["last_accessed"], x["access_count"]))
        
        # サイズ制限内になるまで削除
        deleted_size = 0
        for cache_info in cache_files:
            await self._delete_cache_files(cache_info["key"])
            deleted_size += cache_info["size"]
            
            current_size -= cache_info["size"]
            if current_size <= self.max_cache_size_bytes * 0.8:  # 80%まで削減
                break
        
        logger.info(f"Cache cleanup completed: deleted {deleted_size / 1024 / 1024:.1f}MB")
    
    async def cleanup_expired_cache(self):
        """期限切れキャッシュを削除"""
        current_time = time.time()
        expired_count = 0
        
        for wav_file in self.cache_dir.glob("*.wav"):
            cache_key = wav_file.stem
            metadata = await self._read_metadata(cache_key)
            
            if metadata:
                created_at = metadata.get("created_at", 0)
                expiry_time = created_at + (self.expiry_hours * 3600)
                
                if current_time > expiry_time:
                    await self._delete_cache_files(cache_key)
                    expired_count += 1
        
        if expired_count > 0:
            logger.info(f"Expired cache cleanup: deleted {expired_count} files")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """キャッシュ統計情報を取得"""
        cache_files = list(self.cache_dir.glob("*.wav"))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            "cache_dir": str(self.cache_dir),
            "file_count": len(cache_files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "expiry_hours": self.expiry_hours,
            "max_size_mb": self.max_cache_size_bytes / 1024 / 1024
        }