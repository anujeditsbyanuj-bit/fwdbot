from bot import Bot
from config import Config
from pyrogram import utils as pyroutils
pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -100999999999999
import multiprocessing
import os
import sys

def run_bot():
    """Run the Telegram bot"""
    app = Bot()
    app.run()

def run_admin_panel():
    """Run the admin panel"""
    # Change to admin_panel directory
    admin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'admin_panel')
    sys.path.insert(0, admin_dir)

    # Import and run the admin panel app
    from admin_panel.app import app
    app.run(host='0.0.0.0', port=Config.PORT, debug=False)

if __name__ == '__main__':
    thumbs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'thumbnails')
    if not os.path.exists(thumbs_dir):
        os.makedirs(thumbs_dir)
    
    # Create processes for both bot and admin panel
    bot_process = multiprocessing.Process(target=run_bot, name="TelegramBot")
    admin_process = multiprocessing.Process(target=run_admin_panel, name="AdminPanel")

    # Start both processes
    bot_process.start()
    admin_process.start()

    print("✅ Started Telegram Bot and Admin Panel")
    print("🤖 Bot is running...")
    print("🌐 Admin Panel is running on http://0.0.0.0:5000")

    # Wait for both processes to finish
    bot_process.join()
    admin_process.join()
