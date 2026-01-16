#!/usr/bin/env python3
"""
Telegram Bot for Video Generation.
Handles commands for video creation from YouTube URLs and news articles.
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from execution.job_queue import (
    queue_full_pipeline,
    queue_news_pipeline,
    get_job_status,
    cancel_job
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message."""
    await update.message.reply_text(
        "🎬 Video Generator Bot\n\n"
        "Commands:\n"
        "• /video <youtube_url> - Create video from reference\n"
        "• /news <news_url> <topic> - Create video from news\n"
        "• /status <job_id> - Check job status\n"
        "• /digest - Get today's top news\n\n"
        "Just send a YouTube link and I'll start generating!"
    )


async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /video command - create video from YouTube reference."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /video <youtube_url>\n"
            "Example: /video https://youtube.com/watch?v=xyz123"
        )
        return
    
    youtube_url = context.args[0]
    topic = ' '.join(context.args[1:]) if len(context.args) > 1 else None
    
    # Validate URL
    if 'youtube.com' not in youtube_url and 'youtu.be' not in youtube_url:
        await update.message.reply_text("❌ Invalid YouTube URL")
        return
    
    await update.message.reply_text("🔄 Queuing video generation...")
    
    try:
        job_id = queue_full_pipeline(
            youtube_url=youtube_url,
            topic=topic,
            telegram_chat_id=update.effective_chat.id
        )
        
        await update.message.reply_text(
            f"✅ Job queued!\n\n"
            f"📹 Job ID: {job_id}\n"
            f"🔗 URL: {youtube_url[:50]}...\n\n"
            f"I'll notify you when it's complete.\n"
            f"Use /status {job_id} to check progress."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /news command - create video from news article."""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /news <news_url> <topic>\n"
            "Example: /news https://reuters.com/article/xyz Silver Market Crash"
        )
        return
    
    news_url = context.args[0]
    topic = ' '.join(context.args[1:])
    
    await update.message.reply_text("🔄 Queuing news video generation...")
    
    try:
        job_id = queue_news_pipeline(
            news_url=news_url,
            topic=topic,
            telegram_chat_id=update.effective_chat.id
        )
        
        await update.message.reply_text(
            f"✅ News job queued!\n\n"
            f"📹 Job ID: {job_id}\n"
            f"📰 Topic: {topic}\n\n"
            f"I'll notify you when it's complete."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - check job progress."""
    if not context.args:
        await update.message.reply_text("Usage: /status <job_id>")
        return
    
    job_id = context.args[0]
    status = get_job_status(job_id)
    
    if not status:
        await update.message.reply_text(f"❌ Job not found: {job_id}")
        return
    
    status_emoji = {
        'pending': '⏳',
        'running': '🔄',
        'completed': '✅',
        'failed': '❌'
    }
    
    emoji = status_emoji.get(status['status'], '❓')
    
    message = (
        f"{emoji} Job Status\n\n"
        f"📹 ID: {job_id}\n"
        f"📊 Status: {status['status'].upper()}\n"
        f"📈 Progress: {status['progress']}%\n"
        f"💬 {status['message']}"
    )
    
    await update.message.reply_text(message)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command - cancel a running job."""
    if not context.args:
        await update.message.reply_text("Usage: /cancel <job_id>")
        return
    
    job_id = context.args[0]
    
    try:
        success = cancel_job(job_id)
        if success:
            await update.message.reply_text(f"✅ Job {job_id} cancelled successfully!")
        else:
            await update.message.reply_text(f"❌ Could not cancel job {job_id}. It may have already completed or doesn't exist.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error cancelling job: {str(e)}")


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /digest command - get daily news digest."""
    await update.message.reply_text("🔄 Fetching today's top stories...")
    
    try:
        from execution.search_news import search_news
        
        # Default topics for the channel
        topics = ["silver gold commodities", "federal reserve", "economic collapse"]
        
        all_news = []
        for topic in topics:
            result = search_news(topic, num_articles=3)
            if result and 'articles' in result:
                all_news.extend(result['articles'])
        
        if not all_news:
            await update.message.reply_text("No news found today.")
            return
        
        message = "📰 Today's Top Stories:\n\n"
        for i, article in enumerate(all_news[:10], 1):
            title = article.get('title', 'No title')[:60]
            message += f"{i}. {title}\n"
        
        message += "\nReply with:\n/news <url> <topic>\nto create a video from any story."
        
        await update.message.reply_text(message)
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching news: {str(e)}")


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain YouTube URLs sent without command."""
    text = update.message.text
    
    # Check if it's a YouTube URL
    if 'youtube.com' in text or 'youtu.be' in text:
        # Extract URL from message
        import re
        url_match = re.search(r'(https?://[^\s]+)', text)
        if url_match:
            youtube_url = url_match.group(1)
            
            await update.message.reply_text("🔄 Detected YouTube URL. Queuing video generation...")
            
            try:
                job_id = queue_full_pipeline(
                    youtube_url=youtube_url,
                    telegram_chat_id=update.effective_chat.id
                )
                
                await update.message.reply_text(
                    f"✅ Job queued!\n\n"
                    f"📹 Job ID: {job_id}\n"
                    f"I'll notify you when complete."
                )
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")


def main():
    """Run the bot."""
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set in environment!")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("video", video_command))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("digest", digest_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # Handle plain URLs
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_url
    ))
    
    print("🤖 Bot started! Listening for messages...")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
