import logging
import os
import pickle
import time
from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from dotenv import load_dotenv
import feedparser
import requests
from telegram import Update, ReplyKeyboardRemove
from telegram.error import Conflict
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    CallbackContext,
    filters,
)

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.debug("Script started")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
BOT_USER_NAME = os.getenv('BOT_USER_NAME', 'صاحبي')
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

# Check if required environment variables are loaded
if not all([BOT_TOKEN, API_ID, API_HASH]):
    logger.error("BOT_TOKEN, API_ID, or API_HASH is not set. Please set them in your .env file.")
    exit(1)

# File path for storing user data persistently
DATA_FILE = 'user_data.pkl'

# Global dictionaries to store user data
user_feeds = {}
user_channels = {}  # New: Store channel data

# Global variable for the bot application
application = None

telethon_client = None

# Conversation states
ASK_URL, ASK_INTERVAL, ASK_CHANNEL = range(3)


def load_data():
    """
    Load user feed and channel data from a file to maintain persistence across restarts.
    """
    global user_feeds, user_channels
    try:
        if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
            with open(DATA_FILE, 'rb') as f:
                data = pickle.load(f)
                user_feeds = data.get('feeds', {})
                user_channels = data.get('channels', {})
            logger.info('User data loaded successfully.')
        else:
            user_feeds = {}
            user_channels = {}
            logger.info('No existing user data found or file is empty. Starting fresh.')
    except Exception as e:
        logger.error(f'Unexpected error loading user data: {e}. Starting fresh.')
        user_feeds = {}
        user_channels = {}


def save_data():
    """
    Save user feed and channel data to a file for persistence.
    """
    with open(DATA_FILE, 'wb') as f:
        pickle.dump({'feeds': user_feeds, 'channels': user_channels}, f)
    logger.info('User data saved.')


async def add_feed_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Initiate the conversation to add a new RSS feed.
    """
    await update.message.reply_text('ابعتلي لينك الـ RSS اللي عايز تضيفه.')
    return ASK_URL


async def add_feed_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receive the RSS feed URL from the user and check for duplicates.
    """
    chat_id = update.effective_chat.id
    rss_url = update.message.text.strip()

    # Ensure the URL starts with http:// or https://
    if not rss_url.startswith('http://') and not rss_url.startswith('https://'):
        rss_url = 'http://' + rss_url

    # Check if the feed is already in the user's list
    if chat_id in user_feeds and any(feed['url'] == rss_url for feed in user_feeds[chat_id]):
        await update.message.reply_text('طب ما الفيد ده موجود بالفعل في قائمتك يا صاحبي. جرب فيد آخر.')
        return ConversationHandler.END

    # Validate the RSS feed URL
    if not is_valid_feed(rss_url):
        await update.message.reply_text('اللينك ده مش شغال. تأكد منه وحاول تاني، أو جرب لينك تاني.')
        return ASK_URL  # Ask for the URL again

    # Save the URL in the user's context
    context.user_data['rss_url'] = rss_url

    await update.message.reply_text('دلوقتي قولي كل قد ايه عايز البوت يشيك على الفيد ده (بالدقايق) .'
                                    ' بس اكتب الرقم بس، يعني مثلا لو كتبت 30 \n'
                                    '\n يبقي البوت هيدور كل ٣٠ دقيقه لو في جديد في الفيد و يبعتهولك')
    return ASK_INTERVAL


def is_valid_feed(url):
    """
    Check if the provided URL is a valid RSS feed.
    """
    try:
        # First, try to get the content of the URL
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0 (compatible; RSS Reader Bot/1.0)'})
        response.raise_for_status()  # Raise an exception for bad status codes

        # Then, try to parse the content as a feed
        d = feedparser.parse(response.content)

        # Log some information about the parsed feed
        logger.info(f"Parsed feed for {url}:")
        logger.info(f"Feed type: {d.version}")
        logger.info(f"Feed title: {d.feed.get('title', 'No title')}")
        logger.info(f"Number of entries: {len(d.entries)}")

        # Check if it's a valid feed
        if d.bozo == 0 and ('title' in d.feed or len(d.entries) > 0):
            return True
        else:
            logger.warning(f"Invalid feed structure for {url}: {d.bozo_exception}")
            return False
    except requests.RequestException as e:
        logger.error(f"Error fetching feed {url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error parsing feed {url}: {e}")
        return False


async def add_feed_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receive the update interval from the user and complete the feed addition.
    """
    chat_id = update.effective_chat.id
    interval_str = update.message.text.strip()

    # Convert interval to integer and validate
    try:
        interval = int(interval_str)
        if interval <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text('لازم تكتب رقم صحيح وموجب. حاول تاني.')
        return ASK_INTERVAL  # Ask for the interval again

    rss_url = context.user_data['rss_url']

    # Initialize the user's feed list if it doesn't exist
    if chat_id not in user_feeds:
        user_feeds[chat_id] = []

    # Add the new feed to the user's list
    feed_info = {
        'url': rss_url,
        'interval': interval,
        'last_entry_id': None,
        'job': None  # Will hold the Job instance
    }
    user_feeds[chat_id].append(feed_info)

    # Save the updated data
    save_data()

    # Schedule the feed checking job
    job_queue = context.job_queue
    job = job_queue.run_repeating(
        check_feed_for_user_feed,
        interval=interval * 60,
        first=0,
        chat_id=chat_id,
        name=f"{chat_id}_{rss_url}",
        data={'chat_id': chat_id, 'feed': feed_info}
    )
    feed_info['job'] = job

    await update.message.reply_text('تمام، ضفنا الفيد بنجاح!', reply_markup=ReplyKeyboardRemove())
    logger.info(f"User {chat_id} added a new feed: {rss_url} with interval {interval} minutes.")

    # End the conversation
    return ConversationHandler.END


def parse_feed_with_user_agent(url):
    """
    Parse the RSS feed using a custom User-Agent to prevent HTTP 403 errors.
    """
    try:
        # First, try to get the content of the URL
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0 (compatible; RSS Reader Bot/1.0)'})
        response.raise_for_status()  # Raise an exception for bad status codes

        # Then, try to parse the content as a feed
        d = feedparser.parse(response.content)

        # Check for parsing errors
        if d.bozo and d.bozo_exception:
            logger.warning(f"Parsing warning for feed {url}: {d.bozo_exception}")

        return d
    except requests.RequestException as e:
        logger.error(f"Error fetching feed {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing feed {url}: {e}")
        return None


async def check_feed_for_user_feed(context: CallbackContext):
    """
    Check a specific RSS feed for new entries and send updates to the user.
    """
    job = context.job
    chat_id = job.chat_id
    data = job.data
    feed = data['feed']

    try:
        # Parse the feed with a custom User-Agent
        d = parse_feed_with_user_agent(feed['url'])
        if d is None or not d.entries:
            return  # No entries to process or parsing failed

        latest_entry = d.entries[0]

        # Check if there's a new entry since the last check
        if feed['last_entry_id'] != latest_entry.id:
            feed['last_entry_id'] = latest_entry.id  # Update the last seen entry ID

            # Build the message to send
            message = (
                f"*في جديد من {d.feed.title}:*\n\n"
                f"*{latest_entry.title}*\n{latest_entry.link}"
            )

            # Send the update to the user
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=False
            )

            # Save the updated feed data
            save_data()
            logger.info(f"Sent new entry to user {chat_id} from feed {feed['url']}")

    except Exception as e:
        logger.error(f"Error checking feed {feed['url']}: {e}")


async def add_feed_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cancel the feed addition process.
    """
    await update.message.reply_text('خلاص، ألغينا إضافة الفيد.', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ... (previous imports and global variables remain the same)

# Add this function
async def add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Initiate the conversation to add a new Telegram channel for monitoring.
    """
    await update.message.reply_text('ابعتلي لينك القناة اللي عايز تراقبها.')
    return ASK_CHANNEL


async def add_channel_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Process the Telegram channel URL provided by the user and start monitoring.
    """
    chat_id = update.effective_chat.id
    channel_url = update.message.text.strip()

    if chat_id not in user_channels:
        user_channels[chat_id] = []

    if any(channel['url'] == channel_url for channel in user_channels[chat_id]):
        await update.message.reply_text('القناة دي موجودة بالفعل في قائمتك.')
        return ConversationHandler.END

    user_channels[chat_id].append({'url': channel_url, 'last_message_id': None})
    save_data()

    await update.message.reply_text('تمام، ضفنا القناة بنجاح!')
    await start_monitoring_channel(context, chat_id, channel_url)
    return ConversationHandler.END


async def start_monitoring_channel(context: ContextTypes.DEFAULT_TYPE, chat_id: int, channel_url: str):
    """
    Start monitoring a Telegram channel for new messages.
    """
    global telethon_client

    if telethon_client is None:
        telethon_client = TelegramClient('bot_session', API_ID, API_HASH)
        await telethon_client.start(bot_token=BOT_TOKEN)

    try:
        channel = await telethon_client.get_entity(channel_url)

        @telethon_client.on(events.NewMessage(chats=channel))
        async def handler(event):
            for user_channel in user_channels[chat_id]:
                if user_channel['url'] == channel_url:
                    if user_channel['last_message_id'] != event.message.id:
                        user_channel['last_message_id'] = event.message.id
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"رسالة جديدة من {channel.title}:\n\n{event.message.text}"
                        )
                        save_data()
                    break

        logger.info(f"Started monitoring channel {channel_url} for user {chat_id}")
    except ValueError as e:
        error_message = f"Error: Invalid channel URL. Please check the URL and try again. Details: {str(e)}"
        logger.error(error_message)
        await context.bot.send_message(chat_id=chat_id, text=error_message)
    except TypeError as e:
        error_message = f"Error: Channel not found or bot doesn't have access. Details: {str(e)}"
        logger.error(error_message)
        await context.bot.send_message(chat_id=chat_id, text=error_message)
    except Exception as e:
        error_message = f"Unexpected error while trying to monitor the channel: {channel_url}. Details: {str(e)}"
        logger.error(error_message)
        await context.bot.send_message(chat_id=chat_id, text=error_message)


async def run_telethon_client():
    global telethon_client
    telethon_client = TelegramClient('bot_session', API_ID, API_HASH)
    await telethon_client.start(bot_token=BOT_TOKEN)
    await telethon_client.run_until_disconnected()


async def list_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    List all RSS feeds that the user has added.
    """
    chat_id = update.effective_chat.id

    # Check if the user has any feeds
    if chat_id not in user_feeds or not user_feeds[chat_id]:
        await update.message.reply_text('مفيش فيدات مضافة.')
        return

    # Build the message listing the user's feeds
    message = 'الفيدات بتاعتك:\n'
    for idx, feed in enumerate(user_feeds[chat_id], start=1):
        message += f"{idx}. {feed['url']} (كل {feed['interval']} دقيقة)\n"

    await update.message.reply_text(message)
    logger.info(f"User {chat_id} requested their feed list.")


async def remove_feed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Remove an RSS feed from the user's list based on its number.
    """
    chat_id = update.effective_chat.id

    # Ensure the correct number of arguments is provided
    if len(context.args) != 1:
        await update.message.reply_text('استخدم الأمر كده: /remove <رقم_الفيد>\n'
                                        'مثلا /remove 1 \n'
                                        )
        return

    # Validate the feed number
    try:
        feed_number = int(context.args[0]) - 1  # Adjust for zero-based indexing
        if chat_id in user_feeds and 0 <= feed_number < len(user_feeds[chat_id]):
            feed_info = user_feeds[chat_id].pop(feed_number)
            # Cancel the associated job
            if feed_info['job']:
                feed_info['job'].schedule_removal()
            save_data()
            await update.message.reply_text(f"شلنا الفيد ده: {feed_info['url']}")
            logger.info(f"User {chat_id} removed feed: {feed_info['url']}")
        else:
            await update.message.reply_text('رقم الفيد مش صح.')
    except ValueError:
        await update.message.reply_text('لازم تكتب رقم الفيد صح.')


async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    List all Telegram channels that the user is currently monitoring.
    """
    chat_id = update.effective_chat.id

    if chat_id not in user_channels or not user_channels[chat_id]:
        await update.message.reply_text('مفيش قنوات مضافة.')
        return

    message = 'القنوات اللي بتراقبها:\n'
    for idx, channel in enumerate(user_channels[chat_id], start=1):
        message += f"{idx}. {channel['url']}\n"

    await update.message.reply_text(message)
    logger.info(f"User {chat_id} requested their channel list.")


async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Remove a Telegram channel from the user's monitoring list.
    """
    chat_id = update.effective_chat.id

    if len(context.args) != 1:
        await update.message.reply_text('استخدم الأمر كده: /remove_channel <رقم_القناة>')
        return

    try:
        channel_number = int(context.args[0]) - 1
        if chat_id in user_channels and 0 <= channel_number < len(user_channels[chat_id]):
            channel_info = user_channels[chat_id].pop(channel_number)
            save_data()
            await update.message.reply_text(f"شلنا القناة دي: {channel_info['url']}")
            logger.info(f"User {chat_id} removed channel: {channel_info['url']}")
        else:
            await update.message.reply_text('رقم القناة مش صح.')
    except ValueError:
        await update.message.reply_text('لازم تكتب رقم القناة صح.')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /start command. Send a welcome message and usage instructions.
    """
    welcome_message = (
        f'مسا مسا يا {BOT_USER_NAME}\n\n'
        'دوس على /add عشان تضيف فيد RSS جديد\n'
        'دوس /list عشان تشوف الفيدات اللي ضفتها\n'
        'دوس /remove <رقم_الفيد> عشان تشيل فيد\n'
        'دوس /add_channel عشان تضيف قناة تليجرام للمراقبة\n'
        'دوس /list_channels عشان تشوف القنوات اللي بتراقبها\n'
        'دوس /remove_channel <رقم_القناة> عشان تشيل قناة من المراقبة\n'
        'لو عايز تشوف الكلام ده تاني، دوس على /help.'
    )
    await update.message.reply_text(welcome_message)
    logger.info(f"User {update.effective_chat.id} started the bot.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Provide a list of available commands and their usage.
    """
    help_text = (
        "بص يا صاحبي \n"
        "/start - ابدأ البوت وشوف التعليمات\n"
        "/add - ضيف فيد RSS جديد\n"
        "/list - شوف الفيدات اللي ضفتها\n"
        "/remove <رقم_الفيد> - شيل فيد\n"
        "/add_channel - ضيف قناة تليجرام للمراقبة\n"
        "/list_channels - شوف القنوات اللي بتراقبها\n"
        "/remove_channel <رقم_القناة> - شيل قناة من المراقبة\n"
        "/help - اعرض الرسالة دي تاني"
    )
    await update.message.reply_text(help_text)
    logger.info(f"User {update.effective_chat.id} requested help.")


def main():
    """
    Main function to start the bot and set up handlers.
    """
    global application

    # Initialize the Application
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # Load existing user data
    load_data()

    # Create the ConversationHandler for adding a feed
    feed_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add_feed_start)],
        states={
            ASK_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_feed_url)],
            ASK_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_feed_interval)],
        },
        fallbacks=[CommandHandler('cancel', add_feed_cancel)],
    )

    # Create the ConversationHandler for adding a channel
    channel_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add_channel', add_channel_start)],
        states={
            ASK_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_url)],
        },
        fallbacks=[CommandHandler('cancel', add_feed_cancel)],
    )

    # Register handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(feed_conv_handler)
    application.add_handler(channel_conv_handler)
    application.add_handler(CommandHandler('list', list_feeds))
    application.add_handler(CommandHandler('remove', remove_feed))
    application.add_handler(CommandHandler('list_channels', list_channels))
    application.add_handler(CommandHandler('remove_channel', remove_channel))
    application.add_handler(CommandHandler('help', help_command))

    # Schedule existing feed checker jobs
    job_queue = application.job_queue
    for chat_id, feeds in user_feeds.items():
        for feed in feeds:
            job = job_queue.run_repeating(
                check_feed_for_user_feed,
                interval=feed['interval'] * 60,
                first=0,
                chat_id=chat_id,
                name=f"{chat_id}_{feed['url']}",
                data={'chat_id': chat_id, 'feed': feed}
            )
            feed['job'] = job

    # Start monitoring existing channels
    for chat_id, channels in user_channels.items():
        for channel in channels:
            application.job_queue.run_once(
                lambda context: start_monitoring_channel(context, chat_id, channel['url']),
                when=0
            )

    # Run the bot
    logger.info('Bot is starting...')
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Conflict as e:
        logger.error(f"Conflict error: {e}")
        logger.info("Waiting for 10 seconds before retrying...")
        time.sleep(10)
        logger.info("Retrying to start the bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Error running the bot: {e}")
    finally:
        logger.info('Bot has stopped.')


if __name__ == '__main__':
    main()
