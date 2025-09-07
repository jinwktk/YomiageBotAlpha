"""TTS処理機能"""

import logging
import discord
from discord.ext import commands
import asyncio
import io
from typing import Optional

# ユーティリティのインポート
from bot.utils.tts_api import TTSAPIClient, TTSAPIError
from bot.utils.text_processor import TextProcessor
from bot.utils.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class TTSHandler(commands.Cog):
    """TTS処理Cog"""
    
    def __init__(self, bot):
        """
        TTSハンドラーを初期化
        
        Args:
            bot: Discord Bot インスタンス
        """
        self.bot = bot
        
        # TTS関連の初期化
        self.tts_client = TTSAPIClient(api_url=self.bot.tts_api_url)
        self.text_processor = TextProcessor()
        self.cache_manager = CacheManager(cache_dir=str(self.bot.cache_dir))
        
        # 音声再生キュー（ギルドごと）
        self.tts_queues = {}
        self.processing_flags = {}  # ギルドごとの処理中フラグ
        
        logger.info("TTSHandler cog initialized")
    
    async def cog_load(self):
        """Cog ロード時の処理"""
        logger.info("TTSHandler cog loaded")
        
        # 期限切れキャッシュをクリーンアップ
        try:
            await self.cache_manager.cleanup_expired_cache()
        except Exception as e:
            logger.warning(f"Cache cleanup failed: {e}")
    
    async def cog_unload(self):
        """Cog アンロード時の処理"""
        logger.info("TTSHandler cog unloading...")
        
        # TTS クライアントを閉じる
        await self.tts_client.close()
        
        # キューをクリア
        self.tts_queues.clear()
        self.processing_flags.clear()
        
        logger.info("TTSHandler cog unloaded")
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        メッセージ受信イベント処理
        
        Args:
            message: 受信したメッセージ
        """
        # デバッグ用：すべてのメッセージを記録
        logger.info(f"[DEBUG] Message received: '{message.content[:50]}...' from {message.author.display_name} (bot={message.author.bot}) in guild={message.guild.name if message.guild else 'DM'}")
        
        # サーバーメッセージ以外は無視
        if not message.guild:
            logger.debug("Message ignored: Not in guild (DM)")
            return
        logger.info(f"[DEBUG] Step 1: Guild check passed - {message.guild.name}")
        
        # Bot がボイスチャンネルに接続していない場合は無視
        voice_client = self.bot.get_voice_client_for_guild(message.guild.id)
        logger.info(f"[DEBUG] Step 2: Voice client check - voice_client={voice_client}, connected={voice_client.is_connected() if voice_client else 'None'}")
        if not voice_client or not voice_client.is_connected():
            logger.info(f"Message ignored: Bot not connected to voice channel in {message.guild.name}")
            return
        logger.info(f"[DEBUG] Step 3: Voice connection check passed")
        
        # メッセージ内容の処理
        text_to_process = ""
        
        # テキストコンテンツがある場合
        if message.content and message.content.strip():
            text_to_process = message.content
            logger.info(f"[DEBUG] Step 4: Text content found - '{message.content[:30]}...'")
        
        # ファイル添付がある場合
        if message.attachments:
            if text_to_process:
                text_to_process += " ファイル"
            else:
                text_to_process = "ファイル"
            logger.info(f"[DEBUG] Step 5: File attachment detected - {len(message.attachments)} files")
        
        # テキストもファイルもない場合は無視
        if not text_to_process:
            logger.info("Message ignored: No content or attachments")
            return
        
        logger.info(f"[DEBUG] Step 6: Final text to process - '{text_to_process[:50]}...'")
        
        # WebHookメッセージ（Bot扱い）も処理対象に含める
        logger.info(f"[TTS] Processing message: '{text_to_process[:50]}...' from {message.author.display_name}")
        
        # テキストを前処理
        logger.info(f"[DEBUG] Step 7: Starting text processing")
        processed_text = self.text_processor.process_message_text(text_to_process)
        if not processed_text:
            logger.info(f"Message text processing failed: {text_to_process[:50]}...")
            return
        logger.info(f"[DEBUG] Step 8: Text processing completed - '{processed_text[:30]}...'")
        
        # TTS キューに追加
        logger.info(f"[DEBUG] Step 9: Adding to TTS queue")
        await self._queue_tts_message(message.guild.id, processed_text, message.author.display_name)
        logger.info(f"[DEBUG] Step 10: TTS queue processing completed")
    
    async def _queue_tts_message(self, guild_id: int, text: str, author_name: str):
        """
        TTSメッセージをキューに追加
        
        Args:
            guild_id: サーバーID
            text: 読み上げテキスト
            author_name: 送信者の表示名
        """
        # キューの初期化
        if guild_id not in self.tts_queues:
            self.tts_queues[guild_id] = []
        
        # メッセージをキューに追加
        queue_item = {
            "text": text,
            "author": author_name,
            "timestamp": discord.utils.utcnow()
        }
        
        self.tts_queues[guild_id].append(queue_item)
        logger.info(f"[DEBUG] Queued TTS message: {text[:30]}... (queue size: {len(self.tts_queues[guild_id])})")
        
        # キュー処理を開始（既に処理中でない場合）
        if guild_id not in self.processing_flags or not self.processing_flags[guild_id]:
            asyncio.create_task(self._process_tts_queue(guild_id))
    
    async def _process_tts_queue(self, guild_id: int):
        """
        TTSキューを処理
        
        Args:
            guild_id: サーバーID
        """
        # 処理中フラグを設定
        self.processing_flags[guild_id] = True
        logger.info(f"[DEBUG] Starting TTS queue processing for guild {guild_id}")
        
        try:
            while guild_id in self.tts_queues and self.tts_queues[guild_id]:
                # キューから次のアイテムを取得
                queue_item = self.tts_queues[guild_id].pop(0)
                logger.info(f"[DEBUG] Processing queue item: {queue_item['text'][:30]}...")
                
                # ボイスクライアントの状態確認
                voice_client = self.bot.get_voice_client_for_guild(guild_id)
                if not voice_client or not voice_client.is_connected():
                    logger.info(f"Voice client disconnected, clearing TTS queue for guild {guild_id}")
                    self.tts_queues[guild_id].clear()
                    break
                
                # 音声合成・再生
                logger.info(f"[DEBUG] Starting synthesize and play for: {queue_item['text'][:30]}...")
                await self._synthesize_and_play_message(guild_id, queue_item)
                logger.info(f"[DEBUG] Completed synthesize and play for: {queue_item['text'][:30]}...")
                
                # 再生完了まで待機
                await self._wait_for_playback_completion(voice_client)
                
                # 次のメッセージとの間隔
                await asyncio.sleep(0.5)
        
        except Exception as e:
            logger.error(f"Error processing TTS queue for guild {guild_id}: {e}")
        
        finally:
            # 処理中フラグをクリア
            self.processing_flags[guild_id] = False
    
    async def _synthesize_and_play_message(self, guild_id: int, queue_item: dict):
        """
        メッセージを音声合成して再生
        
        Args:
            guild_id: サーバーID
            queue_item: キューアイテム
        """
        text = queue_item["text"]
        author = queue_item["author"]
        
        voice_client = self.bot.get_voice_client_for_guild(guild_id)
        if not voice_client:
            return
        
        try:
            # キャッシュをチェック
            logger.info(f"[DEBUG] Checking cache for: {text[:20]}... (by {author})")
            tts_settings = self.tts_client.default_settings.copy()
            cached_audio = await self.cache_manager.get_cached_audio(text, tts_settings)
            
            if cached_audio:
                logger.info(f"[DEBUG] Using cached audio for: {text[:20]}... (by {author})")
                audio_data = cached_audio
            else:
                # TTS API で音声合成
                logger.info(f"[DEBUG] Synthesizing audio via API for: {text[:20]}... (by {author})")
                audio_data = await self.tts_client.synthesize_speech(text)
                logger.info(f"[DEBUG] Audio synthesis completed: {len(audio_data)} bytes")
                
                # キャッシュに保存
                await self.cache_manager.save_audio_cache(text, tts_settings, audio_data)
                logger.info(f"[DEBUG] Audio saved to cache for: {text[:20]}...")
            
            # 音声ファイルから AudioSource を作成
            logger.info(f"[DEBUG] Creating FFmpegPCMAudio source...")
            audio_io = io.BytesIO(audio_data)
            audio_source = discord.FFmpegPCMAudio(audio_io, pipe=True)
            
            # 音声再生
            logger.info(f"[DEBUG] Starting voice playback for: {text[:30]}... (by {author})")
            voice_client.play(audio_source)
            logger.info(f"[DEBUG] Voice playback started successfully: {text[:30]}... (by {author})")
            
        except TTSAPIError as e:
            logger.error(f"TTS API error for message by {author}: {e}")
        except Exception as e:
            logger.error(f"Failed to synthesize and play message by {author}: {e}")
    
    async def _wait_for_playback_completion(self, voice_client: discord.VoiceClient, timeout: float = 30.0):
        """
        音声再生完了まで待機
        
        Args:
            voice_client: ボイスクライアント
            timeout: タイムアウト時間（秒）
        """
        start_time = asyncio.get_event_loop().time()
        
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
            
            # タイムアウトチェック
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.warning("TTS playback timeout, stopping...")
                voice_client.stop()
                break
    
    @commands.command(name="skip")
    async def skip_current_tts(self, ctx: commands.Context):
        """現在の読み上げをスキップ"""
        voice_client = self.bot.get_voice_client_for_guild(ctx.guild.id)
        
        if voice_client is None:
            await ctx.send("ボイスチャンネルに参加していません。")
            return
        
        if voice_client.is_playing():
            voice_client.stop()
            await ctx.send("現在の読み上げをスキップしました。")
            logger.info(f"TTS skipped in {ctx.guild.name}")
        else:
            await ctx.send("現在読み上げ中のメッセージはありません。")
    
    @commands.command(name="queue")
    async def show_tts_queue(self, ctx: commands.Context):
        """現在のTTSキューを表示"""
        guild_id = ctx.guild.id
        
        if guild_id not in self.tts_queues or not self.tts_queues[guild_id]:
            await ctx.send("読み上げキューは空です。")
            return
        
        queue_size = len(self.tts_queues[guild_id])
        queue_preview = []
        
        for i, item in enumerate(self.tts_queues[guild_id][:5]):  # 最大5件表示
            text_preview = item["text"][:30] + "..." if len(item["text"]) > 30 else item["text"]
            queue_preview.append(f"{i+1}. {item['author']}: {text_preview}")
        
        preview_text = "\n".join(queue_preview)
        
        if queue_size > 5:
            preview_text += f"\n... 他 {queue_size - 5} 件"
        
        embed = discord.Embed(
            title=f"読み上げキュー ({queue_size} 件)",
            description=preview_text,
            color=0x00ff00
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="clear")
    async def clear_tts_queue(self, ctx: commands.Context):
        """TTSキューをクリア"""
        guild_id = ctx.guild.id
        
        if guild_id in self.tts_queues:
            queue_size = len(self.tts_queues[guild_id])
            self.tts_queues[guild_id].clear()
            
            await ctx.send(f"読み上げキューをクリアしました ({queue_size} 件削除)")
            logger.info(f"TTS queue cleared in {ctx.guild.name} ({queue_size} items)")
        else:
            await ctx.send("読み上げキューは空です。")
    
    @commands.command(name="voice")
    async def change_voice_settings(self, ctx: commands.Context, model_id: Optional[int] = None):
        """音声設定を変更（将来的な機能拡張用）"""
        # 現在はデフォルト設定のみ対応
        current_settings = self.tts_client.default_settings
        
        embed = discord.Embed(
            title="現在の音声設定",
            color=0x0099ff
        )
        
        embed.add_field(name="Model ID", value=current_settings["model_id"], inline=True)
        embed.add_field(name="Speaker ID", value=current_settings["speaker_id"], inline=True)
        embed.add_field(name="Style", value=current_settings["style"], inline=True)
        embed.add_field(name="Speed", value=current_settings["length"], inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="cache")
    async def show_cache_stats(self, ctx: commands.Context):
        """キャッシュ統計を表示"""
        try:
            stats = self.cache_manager.get_cache_stats()
            
            embed = discord.Embed(
                title="音声キャッシュ統計",
                color=0xff9900
            )
            
            embed.add_field(name="ファイル数", value=f"{stats['file_count']} 件", inline=True)
            embed.add_field(name="使用容量", value=f"{stats['total_size_mb']} MB", inline=True)
            embed.add_field(name="最大容量", value=f"{stats['max_size_mb']} MB", inline=True)
            embed.add_field(name="有効期限", value=f"{stats['expiry_hours']} 時間", inline=True)
            
            usage_percent = (stats['total_size_mb'] / stats['max_size_mb']) * 100
            embed.add_field(name="使用率", value=f"{usage_percent:.1f}%", inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"キャッシュ統計の取得に失敗しました: {e}")
            logger.error(f"Failed to get cache stats: {e}")


async def setup(bot):
    """Cog セットアップ"""
    await bot.add_cog(TTSHandler(bot))