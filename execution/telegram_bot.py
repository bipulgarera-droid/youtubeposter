#!/usr/bin/env python3
"""
Telegram Bot for Video Generation.
Conversation-based UI with selection menus instead of typed commands.
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

from execution.job_queue import (
    queue_full_pipeline,
    queue_news_pipeline,
    get_job_status,
    cancel_job,
    get_redis_connection
)

# Import new pipeline
from execution.new_video_pipeline import (
    get_pipeline,
    create_pipeline,
    remove_pipeline
)

# Import viral video discovery
from execution.youtube_search import discover_videos

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# STARTUP CHECK
print("="*50)
print("🤖 TELEGRAM BOT STARTING - DEPLOYMENT VERSION: v2.1 (Serper Fix)")
print("="*50)

# Bot token
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Conversation states
CHOOSING_MODE, WAITING_URL, CHOOSING_LENGTH, WAITING_SEARCH_KEYWORD, CHOOSING_NEWS_ARTICLE, CHOOSING_JOB_TO_CANCEL, CHOOSING_PIPELINE_MODE, NEWVIDEO_FLOW, WAITING_VIRAL_TOPIC = range(9)

# Length options
LENGTH_OPTIONS = [
    ("5 minutes", 5),
    ("10 minutes", 10),
    ("15 minutes", 15),
    ("20 minutes", 20),
    ("30 minutes", 30)
]


def get_main_menu_keyboard():
    """Main menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("🎬 NEW VIDEO (Research-First)", callback_data="mode_newvideo")],
        [InlineKeyboardButton("🔥 Find Viral Videos", callback_data="mode_viral")],
        [InlineKeyboardButton("─────── Legacy Options ───────", callback_data="noop")],
        [InlineKeyboardButton("📺 Reference Video (YouTube URL)", callback_data="mode_video")],
        [InlineKeyboardButton("📰 News Article", callback_data="mode_news")],
        [InlineKeyboardButton("🔍 Search News First", callback_data="mode_search")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_pipeline_mode_keyboard():
    """Choose between full auto or step-by-step pipeline."""
    keyboard = [
        [InlineKeyboardButton("🚀 Full Pipeline (Auto)", callback_data="pipeline_full")],
        [InlineKeyboardButton("👁️ Step-by-Step (Review Each)", callback_data="pipeline_step")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_length_keyboard():
    """Video length selection keyboard."""
    keyboard = [
        [InlineKeyboardButton(f"⏱️ {label}", callback_data=f"length_{minutes}")]
        for label, minutes in LENGTH_OPTIONS
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard(jobs: list):
    """Keyboard for selecting job to cancel."""
    keyboard = []
    for job in jobs[:5]:  # Max 5 jobs
        job_id = job.get('job_id', 'unknown')
        status = job.get('status', 'unknown')
        progress = job.get('progress', 0)
        message = job.get('message', '')[:30]
        
        label = f"🎬 {job_id[-12:]} ({status} - {progress}%)"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"cancel_{job_id}")])
    
    keyboard.append([InlineKeyboardButton("❌ Nevermind", callback_data="cancel_abort")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Welcome message with main menu."""
    # Clear any previous conversation data
    context.user_data.clear()
    
    await update.message.reply_text(
        "🎬 *Video Generator Bot*\n\n"
        "What type of video do you want to create today?",
        parse_mode='Markdown',
        reply_markup=get_main_menu_keyboard()
    )
    return CHOOSING_MODE


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to main menu."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "🎬 *Video Generator Bot*\n\n"
            "What type of video do you want to create today?",
            parse_mode='Markdown',
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "🎬 *Video Generator Bot*\n\n"
            "What type of video do you want to create today?",
            parse_mode='Markdown',
            reply_markup=get_main_menu_keyboard()
        )
    return CHOOSING_MODE


async def newvideo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start new video pipeline directly."""
    # Clear any previous conversation data
    context.user_data.clear()
    
    chat_id = update.effective_chat.id
    
    async def send_message(text):
        try:
            await context.bot.send_message(chat_id, text, parse_mode='Markdown')
        except Exception:
            # Fallback to plain text if markdown fails
            await context.bot.send_message(chat_id, text)
    
    async def send_keyboard(text, options):
        keyboard = [[InlineKeyboardButton(label, callback_data=cb)] for label, cb in options]
        try:
            await context.bot.send_message(
                chat_id, text, parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            # Fallback to plain text
            await context.bot.send_message(
                chat_id, text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    pipeline = create_pipeline(chat_id, send_message, send_keyboard, bot=context.bot)
    context.user_data['pipeline'] = pipeline
    await pipeline.start()
    return NEWVIDEO_FLOW


async def mode_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle mode selection."""
    query = update.callback_query
    await query.answer()
    
    mode = query.data.replace("mode_", "")
    context.user_data['mode'] = mode
    
    if mode == "video":
        await query.edit_message_text(
            "📺 *Reference Video Mode*\n\n"
            "Send me the YouTube URL of the video you want to use as reference:",
            parse_mode='Markdown'
        )
        return WAITING_URL
    
    elif mode == "news":
        await query.edit_message_text(
            "📰 *News Article Mode*\n\n"
            "Send me the news article URL:",
            parse_mode='Markdown'
        )
        return WAITING_URL
    
    elif mode == "search":
        await query.edit_message_text(
            "🔍 *Search News Mode*\n\n"
            "What topic do you want to search for?\n"
            "Enter a keyword or phrase:",
            parse_mode='Markdown'
        )
        return WAITING_SEARCH_KEYWORD
    
    elif mode == "newvideo":
        # Start new research-first pipeline
        chat_id = update.effective_chat.id
        
        async def send_message(text):
            try:
                await context.bot.send_message(chat_id, text, parse_mode='Markdown')
            except Exception:
                await context.bot.send_message(chat_id, text)
        
        async def send_keyboard(text, options):
            keyboard = [[InlineKeyboardButton(label, callback_data=cb)] for label, cb in options]
            try:
                await context.bot.send_message(
                    chat_id, text, parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception:
                await context.bot.send_message(
                    chat_id, text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        
        pipeline = create_pipeline(chat_id, send_message, send_keyboard, bot=context.bot)
        context.user_data['pipeline'] = pipeline
        await pipeline.start()
        return NEWVIDEO_FLOW
    
    elif mode == "viral":
        await query.edit_message_text(
            "🔥 *Find Viral Videos*\n\n"
            "Enter a topic or keyword to find high-performing videos:\n"
            "_(Example: 'silver investing', 'AI future', 'economy collapse')_",
            parse_mode='Markdown'
        )
        return WAITING_VIRAL_TOPIC


async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle URL input."""
    url = update.message.text.strip()
    mode = context.user_data.get('mode', 'video')
    
    # Validate URL based on mode
    if mode == "video":
        if 'youtube.com' not in url and 'youtu.be' not in url:
            await update.message.reply_text(
                "❌ That doesn't look like a YouTube URL.\n\n"
                "Please send a valid YouTube URL (e.g., https://youtube.com/watch?v=xyz)"
            )
            return WAITING_URL
        context.user_data['youtube_url'] = url
    else:
        context.user_data['news_url'] = url
    
    # Ask for pipeline mode (full vs step-by-step)
    await update.message.reply_text(
        "🎬 *Pipeline Mode*\n\n"
        "How would you like to run the pipeline?",
        parse_mode='Markdown',
        reply_markup=get_pipeline_mode_keyboard()
    )
    return CHOOSING_PIPELINE_MODE


async def pipeline_mode_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle pipeline mode selection (full vs step-by-step)."""
    query = update.callback_query
    await query.answer()
    
    pipeline_mode = query.data.replace("pipeline_", "")
    context.user_data['pipeline_mode'] = pipeline_mode
    
    if pipeline_mode == "step":
        await query.edit_message_text(
            "👁️ *Step-by-Step Mode*\n\n"
            "I'll pause after each step and show you the output.\n"
            "You can approve, regenerate, or cancel at any point.\n\n"
            "⏱️ How long should the video be?",
            parse_mode='Markdown',
            reply_markup=get_length_keyboard()
        )
    else:
        await query.edit_message_text(
            "🚀 *Full Pipeline Mode*\n\n"
            "I'll run everything automatically and notify you when done.\n\n"
            "⏱️ How long should the video be?",
            parse_mode='Markdown',
            reply_markup=get_length_keyboard()
        )
    
    return CHOOSING_LENGTH




async def length_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle length selection and queue the job."""
    query = update.callback_query
    await query.answer()
    
    # Extract length
    length = int(query.data.replace("length_", ""))
    context.user_data['target_minutes'] = length
    
    mode = context.user_data.get('mode', 'video')
    pipeline_mode = context.user_data.get('pipeline_mode', 'full')
    chat_id = update.effective_chat.id
    
    await query.edit_message_text("🔄 *Queuing your video...*", parse_mode='Markdown')
    
    try:
        # Choose pipeline based on mode
        if pipeline_mode == "step":
            # Use step-by-step pipeline with approval at each step
            from execution.job_queue import queue_step_pipeline
            
            if mode == "video":
                youtube_url = context.user_data.get('youtube_url')
                job_id = queue_step_pipeline(
                    youtube_url=youtube_url,
                    topic=None,
                    telegram_chat_id=chat_id
                )
                source_info = f"📺 YouTube: {youtube_url[:40]}..."
            else:
                # News/search mode
                news_url = context.user_data.get('news_url', '')
                news_article = context.user_data.get('selected_article', {})
                if news_article:
                    news_url = news_article.get('url', news_url)
                    topic = news_article.get('title', '')
                else:
                    topic = None
                
                job_id = queue_step_pipeline(
                    youtube_url=news_url,  # We'll handle news URLs too
                    topic=topic,
                    telegram_chat_id=chat_id
                )
                source_info = f"📰 News: {news_url[:40]}..."
            
            await query.edit_message_text(
                f"👁️ *Step-by-Step Pipeline Started!*\n\n"
                f"📹 Job ID: `{job_id}`\n"
                f"{source_info}\n"
                f"⏱️ Length: {length} minutes\n\n"
                f"I'll send you each step for review.\n"
                f"Watch for approval requests!",
                parse_mode='Markdown'
            )
        else:
            # Full auto pipeline
            if mode == "video":
                youtube_url = context.user_data.get('youtube_url')
                job_id = queue_full_pipeline(
                    youtube_url=youtube_url,
                    topic=None,
                    telegram_chat_id=chat_id
                )
                source_info = f"📺 YouTube: {youtube_url[:40]}..."
                
            elif mode == "news":
                news_url = context.user_data.get('news_url')
                job_id = queue_news_pipeline(
                    news_url=news_url,
                    topic=None,
                    telegram_chat_id=chat_id
                )
                source_info = f"📰 News: {news_url[:40]}..."
                
            elif mode == "search":
                news_article = context.user_data.get('selected_article', {})
                news_url = news_article.get('url', '')
                topic = news_article.get('title', '')
                
                job_id = queue_news_pipeline(
                    news_url=news_url,
                    topic=topic,
                    telegram_chat_id=chat_id
                )
                source_info = f"🔍 {topic[:40]}..."
            
            await query.edit_message_text(
                f"✅ *Job Queued!*\n\n"
                f"📹 Job ID: `{job_id}`\n"
                f"{source_info}\n"
                f"⏱️ Length: {length} minutes\n\n"
                f"I'll notify you when it's complete.\n"
                f"Use /status to check progress.",
                parse_mode='Markdown'
            )
        
        # Clear conversation data
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error queuing job: {e}")
        await query.edit_message_text(
            f"❌ *Error queuing job:*\n{str(e)}\n\n"
            f"Use /start to try again.",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END


async def receive_viral_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle viral video topic search."""
    topic = update.message.text.strip()
    
    await update.message.reply_text(f"🔥 Searching for viral videos about '{topic}'...")
    
    try:
        result = discover_videos(
            query=topic,
            min_multiplier=1.0,
            days=3,  # Only recent videos (last 3 days)
            max_results=50,
            min_views=10000,
            min_duration_minutes=5,
            max_subs=50000  # Small channels only (under 50K subs)
        )
        
        videos = result.get('videos', [])
        
        if not videos:
            await update.message.reply_text(
                f"❌ No high-multiplier videos found for '{topic}'.\n\n"
                "Try a broader or different keyword, or use /start to go back.",
                reply_markup=get_main_menu_keyboard()
            )
            return CHOOSING_MODE
        
        # Format results
        response = f"🔥 *Top Viral Videos for '{topic}'*\n\n"
        
        for i, video in enumerate(videos[:5]):
            title = video.get('title', 'No title')[:50]
            views = video.get('view_count', 0)
            subs = video.get('subscriber_count', 0)
            multiplier = video.get('multiplier', 0)
            video_id = video.get('video_id', '')
            
            views_str = f"{views:,}" if views < 1000000 else f"{views/1000000:.1f}M"
            subs_str = f"{subs:,}" if subs < 1000000 else f"{subs/1000000:.1f}M"
            
            response += f"*{i+1}. {title}...*\n"
            response += f"   👀 {views_str} views | 👥 {subs_str} subs | 📈 {multiplier}x\n"
            response += f"   🔗 https://youtube.com/watch?v={video_id}\n\n"
        
        response += f"_Found {len(videos)} videos total. Showing top 5._"
        
        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=get_main_menu_keyboard())
        return CHOOSING_MODE
        
    except Exception as e:
        logger.error(f"Viral video search error: {e}")
        await update.message.reply_text(
            f"❌ Search failed: {str(e)}\n\nUse /start to try again.",
            reply_markup=get_main_menu_keyboard()
        )
        return CHOOSING_MODE


async def receive_search_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle search keyword and show results."""
    keyword = update.message.text.strip()
    
    await update.message.reply_text("🔍 Searching for news articles...")
    
    try:
        from execution.search_news import search_news
        
        result = search_news(keyword, num_articles=10, days_limit=3)
        articles = result.get('articles', []) if result else []
        
        if not articles:
            await update.message.reply_text(
                "❌ No news articles found for that topic.\n\n"
                "Try a different keyword, or use /start to go back."
            )
            return WAITING_SEARCH_KEYWORD
        
        # Store articles in context
        context.user_data['search_results'] = articles
        
        # Build keyboard with articles
        keyboard = []
        for i, article in enumerate(articles[:8]):  # Max 8 results
            title = article.get('title', 'No title')[:50]
            source = article.get('source', '')[:15]
            label = f"{i+1}. {title}... ({source})"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"article_{i}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_main")])
        
        await update.message.reply_text(
            f"📰 *Found {len(articles)} articles for \"{keyword}\"*\n\n"
            "Select one to create a video:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHOOSING_NEWS_ARTICLE
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text(f"❌ Search failed: {str(e)}")
        return WAITING_SEARCH_KEYWORD


async def article_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle article selection."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_main":
        return await main_menu(update, context)
    
    # Extract article index
    article_idx = int(query.data.replace("article_", ""))
    articles = context.user_data.get('search_results', [])
    
    if article_idx >= len(articles):
        await query.edit_message_text("❌ Invalid selection. Use /start to try again.")
        return ConversationHandler.END
    
    selected = articles[article_idx]
    context.user_data['selected_article'] = selected
    
    # Show article info and ask for length
    await query.edit_message_text(
        f"📰 *Selected Article:*\n\n"
        f"*{selected.get('title', 'No title')}*\n"
        f"Source: {selected.get('source', 'Unknown')}\n\n"
        "⏱️ How long should the video be?",
        parse_mode='Markdown',
        reply_markup=get_length_keyboard()
    )
    return CHOOSING_LENGTH


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show status of all recent jobs."""
    chat_id = update.effective_chat.id
    
    # Get recent jobs from Redis
    try:
        redis = get_redis_connection()
        keys = redis.keys("job_status:*")
        
        if not keys:
            await update.message.reply_text("No jobs found. Use /start to create a video.")
            return
        
        jobs = []
        for key in keys[:10]:  # Last 10 jobs
            data = redis.get(key)
            if data:
                import json
                job = json.loads(data)
                jobs.append(job)
        
        # Sort by updated_at (most recent first)
        jobs.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        
        if not jobs:
            await update.message.reply_text("No jobs found. Use /start to create a video.")
            return
        
        message = "📊 *Recent Jobs:*\n\n"
        for job in jobs[:5]:
            job_id = job.get('job_id', 'unknown')
            status = job.get('status', 'unknown')
            progress = job.get('progress', 0)
            msg = job.get('message', '')[:40]
            
            emoji = {
                'pending': '⏳',
                'running': '🔄',
                'completed': '✅',
                'failed': '❌'
            }.get(status, '❓')
            
            message += f"{emoji} `{job_id[-16:]}`\n"
            message += f"   Status: {status.upper()} ({progress}%)\n"
            message += f"   {msg}\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show jobs to cancel."""
    try:
        redis = get_redis_connection()
        keys = redis.keys("job_status:*")
        
        if not keys:
            await update.message.reply_text("No jobs to cancel.")
            return ConversationHandler.END
        
        jobs = []
        for key in keys:
            data = redis.get(key)
            if data:
                import json
                job = json.loads(data)
                if job.get('status') in ['pending', 'running']:
                    jobs.append(job)
        
        if not jobs:
            await update.message.reply_text("No active jobs to cancel.")
            return ConversationHandler.END
        
        context.user_data['cancelable_jobs'] = jobs
        
        await update.message.reply_text(
            "🛑 *Cancel Job*\n\n"
            "Select a job to cancel:",
            parse_mode='Markdown',
            reply_markup=get_cancel_keyboard(jobs)
        )
        return CHOOSING_JOB_TO_CANCEL
        
    except Exception as e:
        logger.error(f"Cancel error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return ConversationHandler.END


async def confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle cancel confirmation."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_abort":
        await query.edit_message_text("👍 Cancelled - no jobs affected.")
        return ConversationHandler.END
    
    job_id = query.data.replace("cancel_", "")
    
    success = cancel_job(job_id)
    
    if success:
        await query.edit_message_text(f"✅ Job `{job_id}` cancelled.", parse_mode='Markdown')
    else:
        await query.edit_message_text(f"❌ Could not cancel job `{job_id}`.", parse_mode='Markdown')
    
    return ConversationHandler.END


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's top stories."""
    await update.message.reply_text("🔄 Fetching today's top stories...")
    
    try:
        from execution.search_news import search_news
        
        # Default topics for the channel
        topics = ["silver gold commodities", "federal reserve", "economic collapse"]
        
        all_news = []
        for topic in topics:
            result = search_news(topic, num_articles=3, days_limit=3)
            if result and 'articles' in result:
                all_news.extend(result['articles'])
        
        if not all_news:
            await update.message.reply_text("No news found today.")
            return
        
        message = "📰 *Today's Top Stories:*\n\n"
        for i, article in enumerate(all_news[:10], 1):
            title = article.get('title', 'No title')[:55]
            source = article.get('source', '')[:15]
            message += f"{i}. {title}...\n   _({source})_\n\n"
        
        message += "\nUse /start → 🔍 Search News to create a video from any topic."
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Digest error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel current conversation."""
    context.user_data.clear()
    await update.message.reply_text("Cancelled. Use /start to begin again.")
    return ConversationHandler.END


async def handle_newvideo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle callbacks from new video pipeline."""
    query = update.callback_query
    await query.answer()
    
    pipeline = context.user_data.get('pipeline')
    if not pipeline:
        await query.edit_message_text("❌ Session expired. Use /start to begin again.")
        return ConversationHandler.END
    
    callback_data = query.data
    
    # Handle the callback
    try:
        should_continue = await pipeline.handle_callback(callback_data)
        if should_continue:
            return NEWVIDEO_FLOW
        else:
            # Pipeline complete
            remove_pipeline(update.effective_chat.id)
            context.user_data.clear()
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        await context.bot.send_message(
            update.effective_chat.id,
            f"❌ Error: {str(e)}\n\nUse /start to begin again."
        )
        return ConversationHandler.END


async def handle_newvideo_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text input during new video pipeline."""
    pipeline = context.user_data.get('pipeline')
    if not pipeline:
        await update.message.reply_text("❌ Session expired. Use /start to begin again.")
        return ConversationHandler.END
    
    user_input = update.message.text
    
    try:
        should_continue = await pipeline.handle_callback(None, user_input=user_input)
        if should_continue:
            return NEWVIDEO_FLOW
        else:
            remove_pipeline(update.effective_chat.id)
            context.user_data.clear()
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}\n\nUse /start to begin again.")
        return ConversationHandler.END


def main():
    """Run the bot."""
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set in environment!")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Main conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("newvideo", newvideo_command),
            CommandHandler("cancel", cancel_command),
        ],
        states={
            CHOOSING_MODE: [
                CallbackQueryHandler(mode_selected, pattern="^mode_"),
            ],
            WAITING_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url),
            ],
            CHOOSING_LENGTH: [
                CallbackQueryHandler(length_selected, pattern="^length_"),
            ],
            CHOOSING_PIPELINE_MODE: [
                CallbackQueryHandler(pipeline_mode_selected, pattern="^pipeline_"),
            ],
            WAITING_SEARCH_KEYWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_search_keyword),
            ],
            WAITING_VIRAL_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_viral_topic),
            ],
            CHOOSING_NEWS_ARTICLE: [
                CallbackQueryHandler(article_selected, pattern="^article_"),
                CallbackQueryHandler(main_menu, pattern="^back_main$"),
            ],
            CHOOSING_JOB_TO_CANCEL: [
                CallbackQueryHandler(confirm_cancel, pattern="^cancel_"),
            ],
            NEWVIDEO_FLOW: [
                CallbackQueryHandler(handle_newvideo_callback, pattern="^newvideo_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_newvideo_text),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.COMMAND, cancel_conversation),
        ],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    
    # Standalone commands (work outside conversation)
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("digest", digest_command))
    
    # Step approval callbacks (outside conversation)
    application.add_handler(CallbackQueryHandler(handle_step_approval, pattern="^approve_"))
    application.add_handler(CallbackQueryHandler(handle_step_regenerate, pattern="^regen_"))
    
    print("🤖 Bot started! Listening for messages...")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


async def handle_step_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle step approval callback from step-by-step pipeline."""
    query = update.callback_query
    await query.answer("✅ Approved!")
    
    # Parse callback data: approve_jobid_stepname
    parts = query.data.split("_", 2)
    if len(parts) < 3:
        return
    
    job_id = parts[1]
    step_name = parts[2]
    
    from execution.job_queue import approve_step
    success = approve_step(job_id, step_name)
    
    if success:
        await query.edit_message_text(
            f"✅ *Step Approved*\n\n"
            f"Continuing to next step...",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(f"⚠️ Could not approve step (already processed?)")


async def handle_step_regenerate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle step regeneration request."""
    query = update.callback_query
    await query.answer("🔄 Regeneration requested")
    
    # For now, just reject and let user restart
    parts = query.data.split("_", 2)
    if len(parts) < 3:
        return
    
    job_id = parts[1]
    step_name = parts[2]
    
    from execution.job_queue import reject_step
    reject_step(job_id, step_name)
    
    await query.edit_message_text(
        f"🔄 *Regeneration Requested*\n\n"
        f"This step will be regenerated.\n"
        f"(Note: Full regeneration coming soon - for now pipeline will restart)",
        parse_mode='Markdown'
    )


if __name__ == "__main__":
    main()

