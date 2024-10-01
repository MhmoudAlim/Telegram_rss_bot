import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import feedparser
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import time
import requests
import logging
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


bot = telebot.TeleBot(BOT_TOKEN)

# File to store user data
USER_DATA_FILE = 'user_data.json'


# Load user data from file
def load_user_data():
    try:
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


# Save user data to file
def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f)


# User data storage
user_data = load_user_data()


@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    if user_id not in user_data:
        user_data[user_id] = {'feeds': []}
        save_user_data(user_data)

    bot.reply_to(message, "Welcome to the RSS Feed Reader Bot! \n  Use /help to see available commands.")
    logging.info(f"User {user_id} started the bot")


@bot.message_handler(commands=['help'])
def help(message):
    help_text = """
Available commands:
/start - Start the bot and get a welcome message
/help - Show this help message
/add - Add a new RSS feed
/list - List all your current feeds
/remove - Remove a feed
/interval - Change update interval for a feed
    """
    bot.reply_to(message, help_text)


@bot.message_handler(commands=['add'])
def add_feed(message):
    bot.reply_to(message, "Please send the RSS feed URL you want to add.")
    bot.register_next_step_handler(message, process_feed_url)


def process_feed_url(message):
    url = message.text.strip()
    user_id = str(message.from_user.id)

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        parsed_feed = feedparser.parse(response.text)

        if not parsed_feed.entries:
            raise ValueError("No entries found in the feed")

        user_data[user_id]['feeds'].append({'url': url, 'interval': 60})  # Default interval: 60 minutes
        save_user_data(user_data)

        bot.reply_to(message,
                     f"Feed added successfully. Now, please specify the update interval in minutes (e.g., 30 for checking every 30 minutes).")
        bot.register_next_step_handler(message, set_interval, url)
    except Exception as e:
        bot.reply_to(message, f"Error adding feed: {str(e)}")
        logging.error(f"Error adding feed for user {user_id}: {str(e)}", exc_info=True)


def set_interval(message, url):
    try:
        interval = int(message.text.strip())
        if interval < 1:
            raise ValueError("Interval must be a positive integer.")

        user_id = str(message.from_user.id)
        for feed in user_data[user_id]['feeds']:
            if feed['url'] == url:
                feed['interval'] = interval
                save_user_data(user_data)
                bot.reply_to(message, f"Update interval set to {interval} minutes for the feed: {url}")
                return

        bot.reply_to(message, "Error: Feed not found. Please try adding the feed again.")
    except ValueError as e:
        bot.reply_to(message, f"Invalid interval. Please enter a positive integer. Error: {str(e)}")


@bot.message_handler(commands=['list'])
def list_feeds(message):
    user_id = str(message.from_user.id)
    if user_id not in user_data or not user_data[user_id]['feeds']:
        bot.reply_to(message, "You haven't added any feeds yet. Use /add to add a feed.")
    else:
        feed_list = "Your feeds:\n"
        for i, feed in enumerate(user_data[user_id]['feeds'], 1):
            feed_list += f"{i}. {feed['url']} (Update interval: {feed['interval']} minutes)\n"
        bot.reply_to(message, feed_list)


@bot.message_handler(commands=['remove'])
def remove_feed(message):
    user_id = str(message.from_user.id)
    if user_id not in user_data or not user_data[user_id]['feeds']:
        bot.reply_to(message, "You don't have any feeds to remove.")
        return

    keyboard = InlineKeyboardMarkup()
    for i, feed in enumerate(user_data[user_id]['feeds'], 1):
        keyboard.add(InlineKeyboardButton(f"{i}. {feed['url']}", callback_data=f"remove_{i - 1}"))

    bot.reply_to(message, "Select a feed to remove:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_'))
def callback_remove_feed(call):
    user_id = str(call.from_user.id)
    feed_index = int(call.data.split('_')[1])

    if 0 <= feed_index < len(user_data[user_id]['feeds']):
        removed_feed = user_data[user_id]['feeds'].pop(feed_index)
        save_user_data(user_data)
        bot.answer_callback_query(call.id, f"Removed feed: {removed_feed['url']}")
        bot.edit_message_text("Feed removed successfully.", call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Invalid feed selection.")


@bot.message_handler(commands=['interval'])
def change_interval(message):
    user_id = str(message.from_user.id)
    if user_id not in user_data or not user_data[user_id]['feeds']:
        bot.reply_to(message, "You don't have any feeds to modify.")
        return

    keyboard = InlineKeyboardMarkup()
    for i, feed in enumerate(user_data[user_id]['feeds'], 1):
        keyboard.add(InlineKeyboardButton(f"{i}. {feed['url']}", callback_data=f"interval_{i - 1}"))

    bot.reply_to(message, "Select a feed to change its interval:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('interval_'))
def callback_change_interval(call):
    user_id = str(call.from_user.id)
    feed_index = int(call.data.split('_')[1])

    if 0 <= feed_index < len(user_data[user_id]['feeds']):
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "Please enter the new interval in minutes:")
        bot.register_next_step_handler(call.message, process_new_interval, feed_index)
    else:
        bot.answer_callback_query(call.id, "Invalid feed selection.")


def process_new_interval(message, feed_index):
    try:
        new_interval = int(message.text.strip())
        if new_interval < 1:
            raise ValueError("Interval must be a positive integer.")

        user_id = str(message.from_user.id)
        user_data[user_id]['feeds'][feed_index]['interval'] = new_interval
        save_user_data(user_data)
        bot.reply_to(message, f"Interval updated to {new_interval} minutes for the selected feed.")
    except ValueError as e:
        bot.reply_to(message, f"Invalid interval. Please enter a positive integer. Error: {str(e)}")


def check_feed_updates():
    logging.info("Checking feed updates...")
    current_time = datetime.now()
    for user_id, user_info in user_data.items():
        for feed in user_info['feeds']:
            if 'last_checked' not in feed or current_time - datetime.fromisoformat(feed['last_checked']) >= timedelta(
                    minutes=feed['interval']):
                try:
                    logging.info(f"Fetching feed: {feed['url']}")
                    response = requests.get(feed['url'], timeout=10)
                    response.raise_for_status()

                    parsed_feed = feedparser.parse(response.text)

                    if not parsed_feed.entries:
                        logging.warning(f"No entries found for feed: {feed['url']}")
                        continue

                    latest_entry = parsed_feed.entries[0]

                    if 'last_entry' not in feed or feed['last_entry'] != latest_entry.get('id',
                                                                                          latest_entry.get('link')):
                        message = f"New post in {parsed_feed.feed.get('title', 'Unknown Feed')}:\n{latest_entry.get('title', 'No title')}\n{latest_entry.get('link', 'No link')}"
                        bot.send_message(user_id, message)
                        logging.info(f"Sent update to user {user_id}: {message}")
                        feed['last_entry'] = latest_entry.get('id', latest_entry.get('link'))

                    feed['last_checked'] = current_time.isoformat()
                    save_user_data(user_data)
                except requests.exceptions.RequestException as e:
                    logging.error(f"Error fetching feed {feed['url']}: {e}")
                except Exception as e:
                    logging.error(f"Error processing feed {feed['url']}: {e}", exc_info=True)


# Set up the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_feed_updates, 'interval', minutes=1)
scheduler.start()

# Start the bot
while True:
    try:
        logging.info("Starting bot polling...")
        bot.polling(none_stop=True)
    except Exception as e:
        logging.error(f"Bot polling error: {e}", exc_info=True)
        time.sleep(15)