"""ボイスチャンネル管理機能"""

import logging
import discord
from discord.ext import commands
from typing import Optional
import asyncio
import io

# ユーティリティのインポート
from bot.utils.tts_api import TTSAPIClient
from bot.utils.text_processor import TextProcessor
from bot.utils.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class VoiceManager(commands.Cog):
    """ボイスチャンネル管理Cog"""
    
    def __init__(self, bot):
        """
        ボイスマネージャーを初期化
        
        Args:
            bot: Discord Bot インスタンス
        """
        self.bot = bot
        
        # TTS関連の初期化
        self.tts_client = TTSAPIClient(api_url=self.bot.tts_api_url)
        self.text_processor = TextProcessor()
        self.cache_manager = CacheManager(cache_dir=str(self.bot.cache_dir))
        
        logger.info("VoiceManager cog initialized")
    
    async def cog_load(self):
        """Cog ロード時の処理"""
        logger.info("VoiceManager cog loaded")
        
        # TTS API 接続テスト
        try:
            if await self.tts_client.test_connection():
                logger.info("TTS API connection test successful")
            else:
                logger.warning("TTS API connection test failed")
        except Exception as e:
            logger.error(f"TTS API connection test error: {e}")
    
    async def cog_unload(self):
        """Cog アンロード時の処理"""
        logger.info("VoiceManager cog unloading...")
        
        # TTS クライアントを閉じる
        await self.tts_client.close()
        
        logger.info("VoiceManager cog unloaded")
    
    @commands.Cog.listener()
    async def on_voice_state_update(
        self, 
        member: discord.Member, 
        before: discord.VoiceState, 
        after: discord.VoiceState
    ):
        """
        ボイス状態更新イベント処理
        
        Args:
            member: 状態変更したメンバー
            before: 変更前のボイス状態
            after: 変更後のボイス状態
        """
        # Bot自身の状態変更は無視
        if member.bot:
            return
        
        # ユーザーがボイスチャンネルに参加した場合
        if before.channel is None and after.channel is not None:
            await self._handle_user_join(member, after.channel)
        
        # ユーザーがボイスチャンネルから退出した場合
        elif before.channel is not None and after.channel is None:
            await self._handle_user_leave(member, before.channel)
        
        # ユーザーがボイスチャンネル間を移動した場合
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            await self._handle_user_move(member, before.channel, after.channel)
    
    async def _handle_user_join(self, member: discord.Member, channel: discord.VoiceChannel):
        """
        ユーザーのボイスチャンネル参加処理
        
        Args:
            member: 参加したメンバー
            channel: 参加先チャンネル
        """
        logger.debug(f"User joined voice channel: {member.display_name} -> #{channel.name}")
        
        # Bot がこのサーバーのどのボイスチャンネルにも接続していない場合のみ参加
        if not any(vc.guild.id == member.guild.id for vc in self.bot.voice_clients):
            try:
                voice_client = await channel.connect()
                self.bot.set_voice_client_for_guild(member.guild.id, voice_client)
                logger.info(f"Bot joined voice channel: #{channel.name} in {member.guild.name}")
                
                # 参加挨拶を再生
                await self._play_greeting(member, is_join=True)
                
            except discord.errors.ClientException as e:
                logger.error(f"Failed to connect to voice channel: {e}")
            except Exception as e:
                logger.error(f"Unexpected error joining voice channel: {e}")
        else:
            logger.debug(f"Bot already connected to voice in {member.guild.name}")
            
            # 既に接続中でも挨拶は再生
            await self._play_greeting(member, is_join=True)
    
    async def _handle_user_leave(self, member: discord.Member, channel: discord.VoiceChannel):
        """
        ユーザーのボイスチャンネル退出処理
        
        Args:
            member: 退出したメンバー
            channel: 退出元チャンネル
        """
        logger.debug(f"User left voice channel: {member.display_name} <- #{channel.name}")
        
        # 退出挨拶を再生
        await self._play_greeting(member, is_join=False)
        
        # チャンネルに人がいなくなったかチェック
        await self._check_and_leave_if_empty(channel)
    
    async def _handle_user_move(
        self, 
        member: discord.Member, 
        from_channel: discord.VoiceChannel, 
        to_channel: discord.VoiceChannel
    ):
        """
        ユーザーのボイスチャンネル移動処理
        
        Args:
            member: 移動したメンバー
            from_channel: 移動元チャンネル
            to_channel: 移動先チャンネル
        """
        logger.debug(f"User moved voice channel: {member.display_name} #{from_channel.name} -> #{to_channel.name}")
        
        # 移動元チャンネルが空になったかチェック
        await self._check_and_leave_if_empty(from_channel)
        
        # 移動先チャンネルでの参加処理（移動も参加として扱う）
        await self._handle_user_join(member, to_channel)
    
    async def _check_and_leave_if_empty(self, channel: discord.VoiceChannel):
        """
        チャンネルが空の場合、Botを退出させる
        
        Args:
            channel: チェック対象のチャンネル
        """
        # Bot以外のメンバーがいるかチェック
        human_members = [m for m in channel.members if not m.bot]
        
        if not human_members:
            # Bot がこのチャンネルに接続しているかチェック
            voice_client = self.bot.get_voice_client_for_guild(channel.guild.id)
            
            if voice_client and voice_client.channel.id == channel.id:
                try:
                    await voice_client.disconnect()
                    self.bot.set_voice_client_for_guild(channel.guild.id, None)
                    logger.info(f"Bot left empty voice channel: #{channel.name} in {channel.guild.name}")
                except Exception as e:
                    logger.error(f"Failed to disconnect from voice channel: {e}")
    
    async def _play_greeting(self, member: discord.Member, is_join: bool):
        """
        挨拶音声を再生
        
        Args:
            member: 対象メンバー
            is_join: 参加時の場合 True、退出時の場合 False
        """
        # Bot がボイスチャンネルに接続していない場合はスキップ
        voice_client = self.bot.get_voice_client_for_guild(member.guild.id)
        if not voice_client or not voice_client.is_connected():
            logger.debug(f"No voice client for greeting: {member.display_name}")
            return
        
        # 挨拶メッセージ生成
        if is_join:
            greeting_text = f"{member.display_name}さん、こんちゃ"
        else:
            greeting_text = f"{member.display_name}さん、またね"
        
        try:
            # 音声合成・再生
            await self._synthesize_and_play(member.guild.id, greeting_text, is_greeting=True)
            logger.debug(f"Played greeting: {greeting_text}")
            
        except Exception as e:
            logger.error(f"Failed to play greeting for {member.display_name}: {e}")
    
    async def _synthesize_and_play(self, guild_id: int, text: str, is_greeting: bool = False):
        """
        テキストを音声合成して再生
        
        Args:
            guild_id: サーバーID
            text: 合成するテキスト
            is_greeting: 挨拶音声の場合 True
        """
        voice_client = self.bot.get_voice_client_for_guild(guild_id)
        if not voice_client:
            return
        
        # 音声が再生中の場合は待機
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        
        try:
            # キャッシュをチェック
            tts_settings = self.tts_client.default_settings.copy()
            cached_audio = await self.cache_manager.get_cached_audio(text, tts_settings)
            
            if cached_audio:
                logger.debug(f"Using cached audio for: {text[:20]}...")
                audio_data = cached_audio
            else:
                # TTS API で音声合成
                logger.debug(f"Synthesizing audio for: {text[:20]}...")
                audio_data = await self.tts_client.synthesize_speech(text)
                
                # キャッシュに保存
                await self.cache_manager.save_audio_cache(text, tts_settings, audio_data)
            
            # 音声ファイルから AudioSource を作成
            audio_io = io.BytesIO(audio_data)
            audio_source = discord.FFmpegPCMAudio(audio_io, pipe=True)
            
            # 音声再生
            voice_client.play(audio_source)
            logger.debug(f"Started playing TTS audio: {text[:30]}...")
            
        except Exception as e:
            logger.error(f"Failed to synthesize and play audio: {e}")
    
    @commands.command(name="join")
    async def join_voice_channel(self, ctx: commands.Context, *, channel: Optional[discord.VoiceChannel] = None):
        """
        指定ボイスチャンネルまたはユーザーの現在のチャンネルに参加
        
        Args:
            channel: 参加先チャンネル（省略時はユーザーの現在位置）
        """
        if channel is None:
            if ctx.author.voice is None:
                await ctx.send("ボイスチャンネルに参加するか、チャンネルを指定してください。")
                return
            channel = ctx.author.voice.channel
        
        try:
            voice_client = await channel.connect()
            self.bot.set_voice_client_for_guild(ctx.guild.id, voice_client)
            await ctx.send(f"#{channel.name} に参加しました！")
            logger.info(f"Manual join: #{channel.name} in {ctx.guild.name}")
            
        except discord.errors.ClientException as e:
            await ctx.send(f"ボイスチャンネル参加に失敗しました: {e}")
            logger.error(f"Manual join failed: {e}")
    
    @commands.command(name="leave")
    async def leave_voice_channel(self, ctx: commands.Context):
        """現在のボイスチャンネルから退出"""
        voice_client = self.bot.get_voice_client_for_guild(ctx.guild.id)
        
        if voice_client is None:
            await ctx.send("ボイスチャンネルに参加していません。")
            return
        
        try:
            await voice_client.disconnect()
            self.bot.set_voice_client_for_guild(ctx.guild.id, None)
            await ctx.send("ボイスチャンネルから退出しました。")
            logger.info(f"Manual leave in {ctx.guild.name}")
            
        except Exception as e:
            await ctx.send(f"退出に失敗しました: {e}")
            logger.error(f"Manual leave failed: {e}")
    
    @commands.command(name="test")
    async def test_tts(self, ctx: commands.Context, *, text: str = "テスト音声合成です"):
        """TTS機能をテスト"""
        voice_client = self.bot.get_voice_client_for_guild(ctx.guild.id)
        
        if voice_client is None:
            await ctx.send("ボイスチャンネルに参加していません。`!yomiage join` で参加してください。")
            return
        
        await ctx.send(f"テスト音声を再生します: 「{text}」")
        
        try:
            await self._synthesize_and_play(ctx.guild.id, text)
            logger.info(f"TTS test played: {text}")
            
        except Exception as e:
            await ctx.send(f"音声再生に失敗しました: {e}")
            logger.error(f"TTS test failed: {e}")


async def setup(bot):
    """Cog セットアップ"""
    await bot.add_cog(VoiceManager(bot))