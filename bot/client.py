"""YomiageBot Alpha - Discord Bot クライアント"""

import logging
import os
from typing import Optional
import discord
from discord.ext import commands
from pathlib import Path

logger = logging.getLogger(__name__)


class YomiageBotClient(commands.Bot):
    """YomiageBot Alpha の Discord Bot クライアント"""
    
    def __init__(
        self,
        *,
        debug_guild_id: Optional[int] = None,
        tts_api_url: str = "http://192.168.0.99:5000",
        cache_dir: str = "cache",
        **kwargs
    ):
        """
        Bot クライアントを初期化
        
        Args:
            debug_guild_id: デバッグ用サーバーID（開発時のスラッシュコマンド即座同期用）
            tts_api_url: Style-Bert-VITS2 API URL
            cache_dir: 音声キャッシュディレクトリ
            **kwargs: commands.Bot への追加引数
        """
        # デフォルトのインテント設定
        intents = discord.Intents.default()
        intents.message_content = True  # メッセージ内容読み取り権限
        intents.voice_states = True     # ボイス状態変更検知権限
        intents.guild_messages = True   # サーバーメッセージ権限
        
        # commands.Bot の設定
        super().__init__(
            command_prefix="!yomiage ",  # プレフィックスコマンド（念のため）
            intents=intents,
            help_command=None,  # デフォルトヘルプを無効化
            **kwargs
        )
        
        self.debug_guild_id = debug_guild_id
        self.tts_api_url = tts_api_url
        self.cache_dir = Path(cache_dir)
        
        # キャッシュディレクトリを作成
        self.cache_dir.mkdir(exist_ok=True)
        
        # ボイス再生用の設定
        self.voice_clients_dict = {}  # ギルドID -> VoiceClient のマッピング
        self.tts_queue = {}  # ギルドID -> 音声再生キューのマッピング
        
        logger.info(f"YomiageBotClient initialized: guild_id={debug_guild_id}, api_url={tts_api_url}")
    
    async def setup_hook(self):
        """Bot起動時のセットアップフック"""
        logger.info("Setting up YomiageBot...")
        
        # Cog をロード
        try:
            await self.load_extension("bot.cogs.voice_manager")
            logger.info("Loaded voice_manager cog")
        except Exception as e:
            logger.error(f"Failed to load voice_manager cog: {e}")
        
        try:
            await self.load_extension("bot.cogs.tts_handler")
            logger.info("Loaded tts_handler cog")
        except Exception as e:
            logger.error(f"Failed to load tts_handler cog: {e}")
        
        # デバッグサーバーでスラッシュコマンド同期（開発時のみ）
        if self.debug_guild_id:
            guild = discord.Object(id=self.debug_guild_id)
            try:
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Synced {len(synced)} commands to debug guild {self.debug_guild_id}")
            except Exception as e:
                logger.error(f"Failed to sync commands to debug guild: {e}")
        
        logger.info("YomiageBot setup completed")
    
    async def on_ready(self):
        """Bot準備完了時のイベント"""
        logger.info(f"YomiageBot logged in as {self.user} (ID: {self.user.id})")
        
        # ボイスチャンネル接続状況を確認
        connected_guilds = []
        for voice_client in self.voice_clients:
            connected_guilds.append(f"{voice_client.guild.name} (#{voice_client.channel.name})")
        
        if connected_guilds:
            logger.info(f"Connected voice channels: {', '.join(connected_guilds)}")
        else:
            logger.info("No voice channels connected")
            
            # 人がいるボイスチャンネルを自動スキャン・参加
            await self._scan_and_join_voice_channels()
        
        # アクティビティ設定
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name="テキストメッセージ 📢"
        )
        await self.change_presence(activity=activity)
        
        logger.info("YomiageBot is ready!")

    async def _scan_and_join_voice_channels(self):
        """
        全ボイスチャンネルをスキャンして、人がいる場合は自動参加
        """
        logger.info("Scanning voice channels for users...")
        
        # 全サーバーのボイスチャンネルをスキャン
        for guild in self.guilds:
            try:
                # 既にこのサーバーのボイスチャンネルに接続中の場合はスキップ
                if guild.voice_client:
                    logger.debug(f"Already connected to voice channel in {guild.name}, skipping scan")
                    continue
                
                # ボイスチャンネルで人がいるチャンネルを検索
                occupied_channels = []
                for channel in guild.voice_channels:
                    # Bot以外のユーザーがいるかチェック
                    human_members = [member for member in channel.members if not member.bot]
                    if human_members:
                        occupied_channels.append((channel, len(human_members)))
                        logger.debug(f"Found {len(human_members)} users in {channel.name} ({guild.name})")
                
                # 最も人数が多いチャンネルに参加
                if occupied_channels:
                    # 人数でソート（降順）
                    occupied_channels.sort(key=lambda x: x[1], reverse=True)
                    target_channel, user_count = occupied_channels[0]
                    
                    logger.info(f"Auto-joining voice channel: #{target_channel.name} in {guild.name} ({user_count} users)")
                    
                    try:
                        # ボイスチャンネルに参加
                        voice_client = await target_channel.connect()
                        logger.info(f"Successfully joined {target_channel.name}")
                        
                        # VoiceManagerのCogがあれば挨拶音声を再生（Bot による参加挨拶）
                        voice_manager = self.get_cog('VoiceManager')
                        if voice_manager:
                            # Bot自身の挨拶として簡単な音声合成・再生を実行
                            try:
                                await voice_manager._synthesize_and_play(guild.id, "参加しました", is_greeting=True)
                                logger.debug("Played bot join greeting")
                            except Exception as e:
                                logger.error(f"Failed to play bot join greeting: {e}", exc_info=True)
                        
                    except discord.errors.ClientException as e:
                        logger.error(f"Failed to join voice channel {target_channel.name}: {e}")
                    except Exception as e:
                        logger.error(f"Unexpected error joining {target_channel.name}: {e}", exc_info=True)
                else:
                    logger.debug(f"No occupied voice channels found in {guild.name}")
                    
            except Exception as e:
                logger.error(f"Error scanning voice channels in {guild.name}: {e}")
        
        logger.info("Voice channel scan completed")
    
    async def on_error(self, event: str, *args, **kwargs):
        """エラーハンドリング"""
        logger.error(f"Discord event error in {event}: {args} {kwargs}", exc_info=True)
    
    async def on_guild_join(self, guild: discord.Guild):
        """サーバー参加時のイベント"""
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")
    
    async def on_guild_remove(self, guild: discord.Guild):
        """サーバー退出時のイベント"""
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
        
        # ボイスクライアント情報をクリーンアップ
        if guild.id in self.voice_clients_dict:
            del self.voice_clients_dict[guild.id]
        
        if guild.id in self.tts_queue:
            del self.tts_queue[guild.id]
    
    async def close(self):
        """Bot終了処理"""
        logger.info("Shutting down YomiageBot...")
        
        # すべてのボイスクライアントを切断
        for voice_client in self.voice_clients:
            try:
                await voice_client.disconnect()
                logger.debug(f"Disconnected from {voice_client.guild.name}")
            except Exception as e:
                logger.error(f"Error disconnecting from voice: {e}")
        
        # 親クラスの終了処理
        await super().close()
        logger.info("YomiageBot shutdown complete")
    
    def get_voice_client_for_guild(self, guild_id: int) -> Optional[discord.VoiceClient]:
        """指定サーバーのボイスクライアントを取得"""
        # discord.pyの標準機能を使用してボイスクライアントを検索
        for voice_client in self.voice_clients:
            if voice_client.guild.id == guild_id:
                return voice_client
        return None
    
    def set_voice_client_for_guild(self, guild_id: int, voice_client: Optional[discord.VoiceClient]):
        """指定サーバーのボイスクライアントを設定"""
        if voice_client is None:
            self.voice_clients_dict.pop(guild_id, None)
        else:
            self.voice_clients_dict[guild_id] = voice_client
    
    async def play_audio_in_guild(self, guild_id: int, audio_source: discord.AudioSource):
        """指定サーバーで音声を再生"""
        voice_client = self.get_voice_client_for_guild(guild_id)
        
        if voice_client is None or not voice_client.is_connected():
            logger.warning(f"No voice client connected for guild {guild_id}")
            return False
        
        if voice_client.is_playing():
            logger.debug(f"Voice client busy in guild {guild_id}, audio will be queued")
            # TODO: キュー機能を実装
            return False
        
        try:
            voice_client.play(audio_source)
            logger.debug(f"Started playing audio in guild {guild_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to play audio in guild {guild_id}: {e}")
            return False