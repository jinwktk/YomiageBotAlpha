"""統一エラーハンドリング"""

import logging
import traceback
from typing import Optional, Any, Dict
from enum import Enum
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """エラー重要度レベル"""
    LOW = "low"          # ログのみ記録
    MEDIUM = "medium"    # ログ + ユーザー通知
    HIGH = "high"        # ログ + ユーザー通知 + 管理者通知
    CRITICAL = "critical" # 上記 + システム停止検討


class ErrorCategory(Enum):
    """エラーカテゴリ"""
    NETWORK = "network"
    API = "api"
    VOICE = "voice"
    CACHE = "cache"
    PERMISSION = "permission"
    USER_INPUT = "user_input"
    SYSTEM = "system"


class YomiageError(Exception):
    """カスタムエラーベースクラス"""
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.severity = severity
        self.category = category
        self.context = context or {}
        self.original_error = original_error
        super().__init__(message)


class TTSAPIError(YomiageError):
    """TTS API関連エラー"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, **kwargs):
        self.status_code = status_code
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.API,
            **kwargs
        )


class VoiceConnectionError(YomiageError):
    """ボイス接続関連エラー"""
    
    def __init__(self, message: str, guild_id: Optional[int] = None, **kwargs):
        self.guild_id = guild_id
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VOICE,
            **kwargs
        )


class CacheError(YomiageError):
    """キャッシュ関連エラー"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.CACHE,
            **kwargs
        )


class ErrorHandler:
    """統一エラーハンドラー"""
    
    def __init__(self, bot: Optional[commands.Bot] = None):
        self.bot = bot
        self.error_stats: Dict[ErrorCategory, int] = {
            category: 0 for category in ErrorCategory
        }
    
    async def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        user_context: Optional[discord.abc.Messageable] = None
    ) -> bool:
        """
        エラーを統一的に処理
        
        Args:
            error: 処理するエラー
            context: エラーコンテキスト
            user_context: ユーザー通知用のチャンネル
            
        Returns:
            エラーが正常に処理された場合 True
        """
        try:
            # YomiageError の場合
            if isinstance(error, YomiageError):
                return await self._handle_yomiage_error(error, user_context)
            
            # Discord.py エラーの場合
            elif isinstance(error, discord.DiscordException):
                return await self._handle_discord_error(error, user_context)
            
            # その他の例外
            else:
                return await self._handle_generic_error(error, context, user_context)
                
        except Exception as handler_error:
            logger.critical(f"Error handler failed: {handler_error}", exc_info=True)
            return False
    
    async def _handle_yomiage_error(
        self,
        error: YomiageError,
        user_context: Optional[discord.abc.Messageable]
    ) -> bool:
        """YomiageError を処理"""
        # 統計更新
        self.error_stats[error.category] += 1
        
        # ログレベル決定
        if error.severity == ErrorSeverity.CRITICAL:
            log_level = logging.CRITICAL
        elif error.severity == ErrorSeverity.HIGH:
            log_level = logging.ERROR
        elif error.severity == ErrorSeverity.MEDIUM:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO
        
        # ログ出力
        context_info = f" | Context: {error.context}" if error.context else ""
        logger.log(
            log_level,
            f"[{error.category.value.upper()}] {error.message}{context_info}"
        )
        
        if error.original_error:
            logger.log(log_level, f"Original error: {error.original_error}")
        
        # ユーザー通知
        if error.severity in [ErrorSeverity.MEDIUM, ErrorSeverity.HIGH] and user_context:
            user_message = self._get_user_friendly_message(error)
            try:
                await user_context.send(user_message)
            except Exception as send_error:
                logger.warning(f"Failed to send user notification: {send_error}")
        
        return True
    
    async def _handle_discord_error(
        self,
        error: discord.DiscordException,
        user_context: Optional[discord.abc.Messageable]
    ) -> bool:
        """Discord.py エラーを処理"""
        self.error_stats[ErrorCategory.SYSTEM] += 1
        
        if isinstance(error, discord.Forbidden):
            logger.warning(f"Permission denied: {error}")
            if user_context:
                try:
                    await user_context.send("権限が不足しています。管理者にお問い合わせください。")
                except:
                    pass
        
        elif isinstance(error, discord.NotFound):
            logger.info(f"Resource not found: {error}")
            
        elif isinstance(error, discord.HTTPException):
            logger.error(f"Discord API error: {error}")
            if user_context:
                try:
                    await user_context.send("Discord APIエラーが発生しました。しばらくしてからお試しください。")
                except:
                    pass
        
        else:
            logger.error(f"Discord error: {error}", exc_info=True)
        
        return True
    
    async def _handle_generic_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]],
        user_context: Optional[discord.abc.Messageable]
    ) -> bool:
        """一般的なエラーを処理"""
        self.error_stats[ErrorCategory.SYSTEM] += 1
        
        context_info = f" | Context: {context}" if context else ""
        logger.error(f"Unhandled error: {error}{context_info}", exc_info=True)
        
        if user_context:
            try:
                await user_context.send("予期しないエラーが発生しました。開発者に報告されました。")
            except:
                pass
        
        return True
    
    def _get_user_friendly_message(self, error: YomiageError) -> str:
        """ユーザーフレンドリーなエラーメッセージを生成"""
        if error.category == ErrorCategory.API:
            return "音声合成サービスで問題が発生しました。しばらくしてからお試しください。"
        
        elif error.category == ErrorCategory.VOICE:
            return "音声機能で問題が発生しました。ボイスチャンネルの状態をご確認ください。"
        
        elif error.category == ErrorCategory.NETWORK:
            return "ネットワーク接続で問題が発生しました。しばらくしてからお試しください。"
        
        elif error.category == ErrorCategory.CACHE:
            return "キャッシュ処理でエラーが発生しましたが、動作に影響はありません。"
        
        elif error.category == ErrorCategory.PERMISSION:
            return "権限不足です。管理者に必要な権限の付与をお問い合わせください。"
        
        elif error.category == ErrorCategory.USER_INPUT:
            return f"入力エラー: {error.message}"
        
        else:
            return "システムエラーが発生しました。開発者に報告されました。"
    
    def get_error_stats(self) -> Dict[str, Any]:
        """エラー統計情報を取得"""
        total_errors = sum(self.error_stats.values())
        
        stats = {
            "total_errors": total_errors,
            "error_breakdown": {
                category.value: count 
                for category, count in self.error_stats.items()
            }
        }
        
        if total_errors > 0:
            stats["error_rates"] = {
                category.value: round((count / total_errors) * 100, 1)
                for category, count in self.error_stats.items()
                if count > 0
            }
        
        return stats
    
    def reset_error_stats(self):
        """エラー統計をリセット"""
        self.error_stats = {category: 0 for category in ErrorCategory}
        logger.info("Error statistics reset")


# グローバルエラーハンドラーインスタンス
global_error_handler = ErrorHandler()


def handle_error_sync(error: Exception, context: Optional[Dict[str, Any]] = None):
    """同期版エラーハンドラー（緊急用）"""
    try:
        if isinstance(error, YomiageError):
            logger.error(f"[{error.category.value.upper()}] {error.message}")
        else:
            context_info = f" | Context: {context}" if context else ""
            logger.error(f"Unhandled error: {error}{context_info}", exc_info=True)
    except Exception as handler_error:
        print(f"Critical: Error handler failed: {handler_error}")
        print(f"Original error: {error}")


# デコレーター関数
def handle_errors(
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    category: ErrorCategory = ErrorCategory.SYSTEM,
    user_notify: bool = True
):
    """
    エラーハンドリングデコレーター
    
    Args:
        severity: エラー重要度
        category: エラーカテゴリ
        user_notify: ユーザー通知の有無
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except YomiageError:
                raise  # YomiageError はそのまま再発生
            except Exception as e:
                # 一般例外を YomiageError に変換
                yomiage_error = YomiageError(
                    f"Error in {func.__name__}: {str(e)}",
                    severity=severity,
                    category=category,
                    original_error=e
                )
                raise yomiage_error
        return wrapper
    return decorator