"""YomiageBot Alpha - メインエントリーポイント"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Bot クライアントのインポート
from bot.client import YomiageBotClient

# ログ設定
def setup_logging(log_level: str = "INFO"):
    """ログ設定をセットアップ"""
    # ログディレクトリを作成
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # ログフォーマット
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # ログレベル設定
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # ルートロガー設定
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            # コンソール出力
            logging.StreamHandler(sys.stdout),
            # ファイル出力
            logging.FileHandler(
                log_dir / "yomiage.log",
                encoding='utf-8'
            )
        ]
    )
    
    # Discord.py のログレベルを調整（INFOレベルのみ）
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.INFO)
    
    # HTTP リクエストログを制限
    http_logger = logging.getLogger('discord.http')
    http_logger.setLevel(logging.WARNING)
    
    logging.info("Logging setup completed")


def load_environment():
    """環境変数をロード"""
    # .env ファイルをロード
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(env_path)
        logging.info(f"Environment loaded from {env_path}")
    else:
        logging.warning(f".env file not found: {env_path}")
    
    # 必須環境変数をチェック
    required_vars = ['DISCORD_TOKEN']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logging.error(f"Missing required environment variables: {missing_vars}")
        sys.exit(1)
    
    logging.info("Environment variables validated")


async def main():
    """メイン関数"""
    try:
        # ロギング設定
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        setup_logging(log_level)
        
        logging.info("=" * 60)
        logging.info("YomiageBot Alpha v0.2.0 Starting...")
        logging.info("=" * 60)
        
        # 環境変数ロード
        load_environment()
        
        # 設定値の取得
        token = os.getenv('DISCORD_TOKEN')
        debug_guild_id = os.getenv('DEBUG_GUILD_ID')
        tts_api_url = os.getenv('TTS_API_URL', 'http://192.168.0.99:5000')
        cache_dir = os.getenv('CACHE_DIR', 'cache')
        
        # Bot インスタンス作成
        bot = YomiageBotClient(
            debug_guild_id=int(debug_guild_id) if debug_guild_id else None,
            tts_api_url=tts_api_url,
            cache_dir=cache_dir
        )
        
        logging.info(f"Bot configuration:")
        logging.info(f"  Debug Guild ID: {debug_guild_id}")
        logging.info(f"  TTS API URL: {tts_api_url}")
        logging.info(f"  Cache Directory: {cache_dir}")
        
        # Bot 起動
        async with bot:
            await bot.start(token)
    
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt, shutting down...")
    
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        logging.info("YomiageBot Alpha shutdown completed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Failed to start bot: {e}")
        sys.exit(1)