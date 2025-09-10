#!/usr/bin/env python3
import os
import ssl
import logging
import asyncio
import subprocess
import time
from urllib.parse import urlparse
# Set SSL environment variables
os.environ['SSL_CERT_FILE'] = '/etc/ssl/certs/ca-certificates.crt'
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'

# Try to use system certificates
try:
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass
# Bot configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN', "BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
RENDER = os.environ.get("RENDER", "").lower() == "true"

# Disable SSL verification for yt-dlp
os.environ['YTDLP_NO_SSL_VERIFY'] = '1'

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, 'downloads')

# Ensure temp directory exists
os.makedirs(TEMP_DIR, exist_ok=True)

# Simple logging setup
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TikTokDownloader:
    def __init__(self):
        self.temp_dir = TEMP_DIR
        logger.info(f"Temp directory: {self.temp_dir}")
    
    def check_ytdlp(self):
        """Check if yt-dlp is available"""
        try:
            result = subprocess.run(['yt-dlp', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"yt-dlp available: {version}")
                return True, version
            return False, None
        except Exception as e:
            logger.error(f"yt-dlp check failed: {e}")
            return False, None
    
    def is_tiktok_url(self, url):
        """Check if URL is from TikTok"""
        try:
            parsed = urlparse(url.lower())
            domain = parsed.netloc.lower()
            tiktok_domains = ['tiktok.com', 'www.tiktok.com', 'm.tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com']
            return any(d in domain for d in tiktok_domains)
        except:
            return False
    
    async def download_tiktok(self, url):
    """Download TikTok video using yt-dlp"""
    try:
        timestamp = int(time.time())
        output_template = os.path.join(self.temp_dir, f"tiktok_{timestamp}.%(ext)s")
        
        cmd = [
            'yt-dlp',
            '--format', 'best[filesize<50M]/worst',
            '--output', output_template,
            '--no-playlist',
            '--no-warnings',
            '--no-check-certificates',  # Disable SSL verification
            '--force-ipv4',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            url
        ]
        
        logger.info(f"Downloading: {url}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        except asyncio.TimeoutError:
            process.kill()
            return None, "Download timeout", 0
        
        if process.returncode == 0:
            # Find the downloaded file
            files = [f for f in os.listdir(self.temp_dir) 
                    if f.startswith(f"tiktok_{timestamp}")]
            
            if files:
                file_path = os.path.join(self.temp_dir, files[0])
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                    if file_size > 0.1:  # At least 100KB
                        logger.info(f"Downloaded: {file_size:.1f}MB")
                        return file_path, "TikTok Video", file_size
            
            return None, "No file generated", 0
        else:
            error = stderr.decode() if stderr else "Unknown error"
            logger.error(f"Download failed: {error}")
            
            if "unavailable" in error.lower():
                return None, "Video unavailable", 0
            elif "private" in error.lower():
                return None, "Private video", 0
            elif "not found" in error.lower() or "404" in error:
                return None, "Video not found", 0
            else:
                return None, "Download failed", 0
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None, f"Error: {str(e)[:50]}", 0
    
    def cleanup_old_files(self):
        """Remove files older than 30 minutes"""
        try:
            current_time = time.time()
            count = 0
            for filename in os.listdir(self.temp_dir):
                filepath = os.path.join(self.temp_dir, filename)
                if os.path.isfile(filepath):
                    if current_time - os.path.getmtime(filepath) > 1800:  # 30 min
                        os.remove(filepath)
                        count += 1
            if count > 0:
                logger.info(f"Cleaned {count} old files")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

# Global instance
downloader = TikTokDownloader()

async def start_command(update, context):
    """Start command handler"""
    has_ytdlp, version = downloader.check_ytdlp()
    
    if has_ytdlp:
        message = f"""🎵 **TikTok Video Downloader**

✅ Ready! yt-dlp v{version}

**How to use:**
Just send me any TikTok link!

**Examples:**
• tiktok.com/@user/video/...
• vm.tiktok.com/...
• vt.tiktok.com/...

**Features:**
🎥 High quality downloads
💾 50MB max file size
🧹 Auto cleanup

**Commands:**
/help - Show help
/status - Bot status

Send me a TikTok link to get started! 🚀"""
    else:
        message = """🎵 **TikTok Video Downloader**

❌ yt-dlp not available
Bot is currently unavailable."""
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)

async def help_command(update, context):
    """Help command handler"""
    help_text = """🤖 **TikTok Downloader Help**

**Usage:**
1. Copy a TikTok video link
2. Send it to this bot
3. Receive the video file

**Supported links:**
✅ tiktok.com/@username/video/...
✅ vm.tiktok.com/...
✅ vt.tiktok.com/...
✅ www.tiktok.com/...

**Limits:**
• TikTok videos only
• Max 50MB file size
• Public videos only

**Commands:**
/start - Welcome message
/help - This help
/status - Bot status"""
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)

async def status_command(update, context):
    """Status command handler"""
    has_ytdlp, version = downloader.check_ytdlp()
    
    # Count temp files
    file_count = 0
    try:
        file_count = len([f for f in os.listdir(TEMP_DIR) if os.path.isfile(os.path.join(TEMP_DIR, f))])
    except:
        pass
    
    status = f"""🤖 **Bot Status**

**System:**
✅ Bot running
{'✅' if has_ytdlp else '❌'} yt-dlp: {'v' + version if has_ytdlp else 'Missing'}

**Storage:**
📁 Temp files: {file_count}
📂 Directory: {TEMP_DIR}

**Limits:**
💾 Max file size: 50MB
🧹 Auto cleanup: 30 minutes

Ready for TikTok downloads!"""
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=status)

async def handle_url(update, context):
    """Handle TikTok URL messages"""
    url = update.message.text.strip()
    
    # Check if it's a TikTok URL
    if not downloader.is_tiktok_url(url):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ **Not a TikTok URL**\n\nPlease send a valid TikTok link like:\n• tiktok.com/@user/video/...\n• vm.tiktok.com/..."
        )
        return
    
    # Check if yt-dlp is available
    has_ytdlp, _ = downloader.check_ytdlp()
    if not has_ytdlp:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Service temporarily unavailable")
        return
    
    # Clean old files
    downloader.cleanup_old_files()
    
    # Show progress
    status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="⏳ **Downloading TikTok...**")
    
    try:
        # Download the video
        file_path, title, file_size = await downloader.download_tiktok(url)
        
        if file_path and os.path.exists(file_path):
            if 0.1 <= file_size <= 50:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text="📤 **Sending video...**"
                )
                
                try:
                    with open(file_path, 'rb') as video_file:
                        await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=video_file,
                            caption=f"🎵 **{title}**\n💾 {file_size:.1f}MB",
                            supports_streaming=True
                        )
                    
                    await context.bot.delete_message(
                        chat_id=update.effective_chat.id,
                        message_id=status_msg.message_id
                    )
                    logger.info(f"Video sent successfully: {file_size:.1f}MB")
                    
                except Exception as e:
                    logger.error(f"Send error: {e}")
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=status_msg.message_id,
                        text="❌ **Failed to send video**"
                    )
                
            elif file_size > 50:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text=f"❌ **File too large: {file_size:.1f}MB**\nTelegram limit: 50MB"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text="❌ **File too small or corrupted**"
                )
        else:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=f"❌ **Download failed**\n\n{title}"
            )
    
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text="❌ **An error occurred**\nPlease try again"
        )
    
    finally:
        # Cleanup
        try:
            if 'file_path' in locals() and file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

async def error_handler(update, context):
    """Global error handler"""
    logger.error("Update caused error", exc_info=context.error)

def main():
    """Main function"""
    try:
        if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            logger.error("Bot token not set!")
            return
        
        logger.info("Starting TikTok Bot...")
        logger.info(f"Temp directory: {TEMP_DIR}")
        logger.info(f"Render mode: {RENDER}")
        logger.info(f"Webhook URL: {WEBHOOK_URL}")
        
        # Check yt-dlp availability
        has_ytdlp, version = downloader.check_ytdlp()
        if has_ytdlp:
            logger.info(f"yt-dlp ready: {version}")
        else:
            logger.warning("yt-dlp not available!")
        
        # Create application
        from telegram.ext import Application, CommandHandler, MessageHandler, filters
        
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("status", status_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
        app.add_error_handler(error_handler)
        
        logger.info("Bot ready!")
        
        # Start bot - FIXED: Only use webhook on Render
        if RENDER and WEBHOOK_URL:
            logger.info(f"Starting webhook mode on port {PORT}")
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                webhook_url=WEBHOOK_URL,
                url_path=BOT_TOKEN,
                drop_pending_updates=True
            )
        else:
            logger.info("Starting polling mode")
            app.run_polling(
                drop_pending_updates=True,
                allowed_updates=['message', 'callback_query']
            )
    
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

if __name__ == "__main__":
    main()