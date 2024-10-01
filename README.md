# Telegram RSS Feed Reader Bot

## Description

This Telegram bot allows users to subscribe to RSS feeds and receive updates directly in their Telegram chats. Users can
add multiple feeds, set custom update intervals, and manage their subscriptions easily.

## Features

- Add and remove RSS feeds
- Set custom update intervals for each feed
- Receive notifications for new posts
- Multi-user support
- Secure token management


## Try This Bot

You can start using this RSS Feed Reader Bot right now on Telegram!

- **Bot Username:** @a_feed_bot
- **Direct Link:** [t.me/a_feed_bot](https://t.me/a_feed_bot)

Or scan this QR code with your mobile device to open the bot in Telegram:

<img src="https://github.com/MhmoudAlim/telegram-rss-bot/blob/@a_feed_bot" alt="QR Code for @a_feed_bot" />


To use the bot:
1. Open Telegram
2. Search for @a_feed_bot or click the direct link above
3. Start a chat and follow the instructions provided by the bot

Feel free to explore the bot's features and start adding your favorite RSS feeds!

## How to Use This Bot on Telegram

(This section remains the same as in the previous update)

... (rest of the README continues)

## Prerequisites

- Python 3.7+
- pip (Python package installer)

...

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/MhmoudAlim/telegram-rss-bot.git
   cd telegram-rss-bot
   ```

2. Create a virtual environment (optional but recommended):

    - On macOS and Linux:
      ```
      python3 -m venv venv
      source venv/bin/activate
      ```

    - On Windows:
      ```
      python -m venv venv
      venv\Scripts\activate
      ```

3. Set up your bot token:
    - Create a `.env` file in the project root
    - Add your bot token: `BOT_TOKEN=your_bot_token_here`

...

## Usage

1. Start the bot:
   ```
   python bot.py
   ```

2. In Telegram, start a chat with your bot and use these commands:
    - `/start`: Initialize the bot
    - `/help`: Show available commands
    - `/add`: Add a new RSS feed
    - `/list`: List all current feeds
    - `/remove`: Remove a feed
    - `/interval`: Change update interval for a feed

# Telegram RSS Feed Reader Bot

... (previous sections remain the same)

## How to Use This Bot on Telegram

Once the bot is set up and running, you can interact with it on Telegram. Here's a step-by-step guide:

1. **Start the Bot**
   - Open Telegram and search for your bot's username.
   - Start a chat with the bot by clicking on it.
   - Send the `/start` command or click the "Start" button.
   - The bot will greet you and provide initial instructions.

2. **Add an RSS Feed**
   - Send the `/add` command to the bot.
   - The bot will ask you to enter the URL of the RSS feed you want to add.
   - Send the URL of the RSS feed (e.g., `https://example.com/feed.xml`).
   - The bot will then ask you to set an update interval in minutes.
   - Send a number representing how often you want the feed to be checked (e.g., `60` for hourly updates).

3. **List Your Subscribed Feeds**
   - Send the `/list` command.
   - The bot will display all the RSS feeds you've subscribed to, along with their update intervals.

4. **Remove a Feed**
   - Send the `/remove` command.
   - The bot will show you a list of your subscribed feeds.
   - Select the feed you want to remove by clicking on it or sending its number.

5. **Change Update Interval for a Feed**
   - Send the `/interval` command.
   - Select the feed you want to modify.
   - Enter the new update interval in minutes.

6. **Receive Updates**
   - Once you've added feeds, the bot will automatically send you messages when new content is available.
   - Each update will typically include the feed title, post title, and a link to the full article.

7. **Get Help**
   - If you ever need a reminder of available commands, send the `/help` command.
   - The bot will respond with a list of all available commands and their descriptions.

Remember:
- The bot needs to be running on a server to send updates. If you stop the bot on your local machine, it won't be able to check for updates or send notifications.
- Make sure to interact with the bot in a private chat, not in a group, for security reasons.
- If you encounter any issues or have questions, refer to the bot's help command or contact the bot administrator.

... (rest of the README continues)

## Configuration

- Update intervals and other settings can be adjusted in the `config.py` file.

## Security

- The bot token is stored in a `.env` file, which is not tracked by git.
- Ensure you never commit or share your actual bot token.

## Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/AmazingFeature`
3. Commit your changes: `git commit -m 'Add some AmazingFeature'`
4. Push to the branch: `git push origin feature/AmazingFeature`
5. Open a pull request

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) library
- [feedparser](https://feedparser.readthedocs.io/en/latest/) library
