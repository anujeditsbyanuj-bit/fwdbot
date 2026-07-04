from pyrogram import Client
from pymongo import MongoClient
from config import Config
from datetime import datetime
import pytz
from plugins.utils import to_small_caps
import logging

db_client = MongoClient(Config.DATABASE_URI)
db = db_client[Config.DATABASE_NAME]

class BotLogger:
    """Centralized logging system for bot activities"""

    @staticmethod
    def get_ist_time():
        """Get current time in Asia/Kolkata timezone"""
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        return now

    @staticmethod
    def format_datetime(dt):
        """Format datetime to DD-MM-YYYY and HH:MM:SS AM/PM"""
        date_str = dt.strftime('%d-%m-%Y')
        time_str = dt.strftime('%I:%M:%S %p')
        return date_str, time_str

    @staticmethod
    def get_user_link(user_id, name):
        """Create user DM link with name and monospace user ID"""
        return f'<a href="tg://user?id={user_id}">{name}</a> (<code>{user_id}</code>)'

    @staticmethod
    def save_to_admin_logs(message, log_type="info", admin_name="ʙᴏᴛ"):
        """Save activity log to admin panel notifications"""
        try:
            db.admin_logs.insert_one({
                "message": message,
                "log_type": log_type,
                "timestamp": datetime.utcnow(),
                "admin": admin_name,
                "read": False
            })
        except Exception as e:
            logging.error(f"Error saving to admin logs: {e}")
    @staticmethod
    async def log_new_user(client: Client, user_id: int, name: str):
        """Log when a new user registers"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ɴᴇᴡ_ᴜsᴇʀ 🔻\n\n"
                f"👤 {to_small_caps('name')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"🔻 {to_small_caps('new user')}: {name} ({user_id})", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging new user: {e}")
    @staticmethod
    async def log_plan_check(client: Client, user_id: int, name: str):
        """Log when a user checks their plan"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ᴘʟᴀɴ_ᴄʜᴇᴄᴋ 🚫\n\n"
                f"👤 {to_small_caps('name')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"🚫 {to_small_caps('plan check')}: {name} ({user_id})", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging plan check: {e}")
    @staticmethod
    async def log_bot_restart(client: Client):
        """Log when bot restarts"""
        if not Config.LOG_CHANNEL:
            return

        try:
            me = await client.get_me()
            bot_link = f"https://t.me/{me.username}"

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ʙᴏᴛ_ʀᴇsᴛᴀʀᴛ 🔄\n\n"
                f"🤖 {to_small_caps('bot')}: <a href='{bot_link}'>{me.first_name}</a>\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}\n"
                f"🌐 {to_small_caps('timezone')}: Asia/Kolkata\n"
                f"🛠️ {to_small_caps('build status')}: {Config.BOT_VERSION} [ {Config.BUILD_STATUS} ]"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"🔄 {to_small_caps('bot restarted')} - {me.first_name}", "success", "sʏsᴛᴇᴍ")
        except Exception as e:
            logging.error(f"Error logging bot restart: {e}")
    @staticmethod
    async def log_premium_added(client: Client, user_id: int, name: str, plan: str, 
                                duration_text: str, purchased_at: datetime, 
                                expires_at: datetime, assigned_by_id: int, assigned_by_name: str):
        """Log when premium is added to a user"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)
            admin_link = BotLogger.get_user_link(assigned_by_id, assigned_by_name)

            plan_info = Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])

            # Convert UTC to IST
            ist = pytz.timezone('Asia/Kolkata')

            if purchased_at:
                purchased_ist = purchased_at.replace(tzinfo=pytz.utc).astimezone(ist)
                joining_date, joining_time = BotLogger.format_datetime(purchased_ist)
            else:
                joining_date = "N/A"
                joining_time = "N/A"

            message = (
                f"#Added_Premium\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"💎 {to_small_caps('plan')}: {plan_info['emoji']} {plan_info['name']}\n"
                f"⏰ {to_small_caps('premium access')}: {duration_text}\n\n"
                f"⏳ {to_small_caps('joining date')}: {joining_date}\n"
                f"⏱️ {to_small_caps('joining time')}: {joining_time}\n\n"
            )

            if expires_at:
                expires_ist = expires_at.replace(tzinfo=pytz.utc).astimezone(ist)
                expiry_date, expiry_time = BotLogger.format_datetime(expires_ist)
                message += (
                    f"⌛️ {to_small_caps('expiry date')}: {expiry_date}\n"
                    f"⏱️ {to_small_caps('expiry time')}: {expiry_time}\n\n"
                )
            else:
                message += f"⌛️ {to_small_caps('expiry')}: ♾️ {to_small_caps('lifetime')}\n\n"

            message += f"👨‍💼 {to_small_caps('added by')}: {admin_link} ({assigned_by_id})"

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"💎 {to_small_caps('premium added')}: {name} ({user_id}) - {plan_info['name']}", "success", assigned_by_name)
        except Exception as e:
            logging.error(f"Error logging premium added: {e}")
    @staticmethod
    async def log_premium_removed(client: Client, user_id: int, name: str, 
                                  old_plan: str, removed_by_id: int, removed_by_name: str):
        """Log when premium is removed from a user"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)
            admin_link = BotLogger.get_user_link(removed_by_id, removed_by_name)

            plan_info = Config.SUBSCRIPTION_PLANS.get(old_plan, Config.SUBSCRIPTION_PLANS['free'])

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ʀᴇᴍᴏᴠᴇᴅ_ᴘʀᴇᴍɪᴜᴍ\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"💎 {to_small_caps('old plan')}: {plan_info['emoji']} {plan_info['name']}\n"
                f"🔻 {to_small_caps('new plan')}: 🆓 Free\n\n"
                f"📅 {to_small_caps('removal date')}: {date_str}\n"
                f"⏰ {to_small_caps('removal time')}: {time_str}\n\n"
                f"👨‍💼 {to_small_caps('removed by')}: {admin_link} (<code>{removed_by_id}</code>)"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"🔻 {to_small_caps('premium removed')}: {name} ({user_id})", "warning", removed_by_name)
        except Exception as e:
            logging.error(f"Error logging premium removed: {e}")
    @staticmethod
    async def log_subscription_expired(client: Client, user_id: int, name: str, plan: str):
        """Log when a subscription expires"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)
            plan_info = Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#Subscription_Expired ⚠️\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"💎 {to_small_caps('expired plan')}: {plan_info['emoji']} {plan_info['name']}\n"
                f"🔻 {to_small_caps('current plan')}: 🆓 Free\n\n"
                f"📅 {to_small_caps('expired on')}: {date_str}\n"
                f"⏰ {to_small_caps('expired at')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"⚠️ {to_small_caps('subscription expired')}: {name} ({user_id}) - {plan_info['name']}", "warning", "sʏsᴛᴇᴍ")
        except Exception as e:
            logging.error(f"Error logging subscription expiry: {e}")
    @staticmethod
    async def log_command_usage(client: Client, user_id: int, name: str, command: str):
        """Log when a user uses a specific command"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ᴄᴏᴍᴍᴀɴᴅ_ᴜsᴇᴅ 📝\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"⚙️ {to_small_caps('command')}: /{command}\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"📝 /{command} {to_small_caps('used by')}: {name} ({user_id})", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging command usage: {e}")
    @staticmethod
    async def log_ftm_mode_activated(client: Client, user_id: int, name: str, mode: str):
        """Log when a user activates an FTM mode"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            mode_emoji = {
                'delta': '🔷',
                'gamma': '🔶',
                'replacements': '🔄',
                'watermark': '💧',
                'link_remover': '🔗'
            }

            message = (
                f"#ғᴛᴍ_ᴀᴄᴛɪᴠᴀᴛᴇᴅ {mode_emoji.get(mode, '⚙️')}\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🎯 {to_small_caps('mode')}: {to_small_caps(mode)}\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"{mode_emoji.get(mode, '⚙️')} FTM {to_small_caps(mode)} {to_small_caps('activated')}: {name} ({user_id})", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging FTM activation: {e}")
    @staticmethod
    async def log_broadcast(client: Client, admin_id: int, admin_name: str, 
                           total_users: int, success: int, failed: int):
        """Log broadcast activity"""
        if not Config.LOG_CHANNEL:
            return

        try:
            admin_link = BotLogger.get_user_link(admin_id, admin_name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ʙʀᴏᴀᴅᴄᴀsᴛ_sᴇɴᴛ 📢\n\n"
                f"👨‍💼 {to_small_caps('sent by')}: {admin_link} (<code>{admin_id}</code>)\n\n"
                f"👥 {to_small_caps('total users')}: {total_users}\n"
                f"✅ {to_small_caps('success')}: {success}\n"
                f"❌ {to_small_caps('failed')}: {failed}\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"📢 {to_small_caps('broadcast sent')}: {total_users} {to_small_caps('users')} (✅{success} ❌{failed})", "success", admin_name)
        except Exception as e:
            logging.error(f"Error logging broadcast: {e}")
    @staticmethod
    async def log_ftm_mode_toggled(client: Client, user_id: int, name: str, mode: str, enabled: bool):
        """Log when FTM mode is toggled"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            mode_emoji = {
                'delta': '🔥',
                'gamma': '💫',
                'replacements': '🌀',
                'watermark': '💧',
                'link_remover': '🔗',
                'pi_mode': '🥧'
            }

            status = to_small_caps('enabled') if enabled else to_small_caps('disabled')
            status_emoji = '✅' if enabled else '❌'

            message = (
                f"#ғᴛᴍ_ᴍᴏᴅᴇ_ᴛᴏɢɢʟᴇᴅ {mode_emoji.get(mode, '⚙️')}\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🎯 {to_small_caps('mode')}: {to_small_caps(mode.replace('_', ' '))}\n"
                f"📊 {to_small_caps('status')}: {status_emoji} {status}\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"{mode_emoji.get(mode, '⚙️')} FTM {to_small_caps(mode.replace('_', ' '))} {status_emoji} {status}: {name} ({user_id})", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging FTM mode toggle: {e}")
    @staticmethod
    async def log_bot_added(client: Client, user_id: int, name: str, bot_type: str):
        """Log when user adds a bot/userbot"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            bot_emoji = '🤖' if bot_type == 'bot' else '👤'

            message = (
                f"#ʙᴏᴛ_ᴀᴅᴅᴇᴅ {bot_emoji}\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🔧 {to_small_caps('type')}: {to_small_caps(bot_type)}\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"{bot_emoji} {to_small_caps(bot_type)} {to_small_caps('added by')}: {name} ({user_id})", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging bot addition: {e}")
    @staticmethod
    async def log_bot_removed(client: Client, user_id: int, name: str):
        """Log when user removes their bot"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ʙᴏᴛ_ʀᴇᴍᴏᴠᴇᴅ 🗑️\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"🗑️ {to_small_caps('bot removed by')}: {name} ({user_id})", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging bot removal: {e}")
    @staticmethod
    async def log_channel_added(client: Client, user_id: int, name: str, channel_type: str, channel_title: str, channel_id: int):
        """Log when user adds a channel (source/target/gamma)"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            type_emoji = {
                'source': '📢',
                'target': '🎯',
                'gamma_source': '📡',
                'gamma_target': '🎯'
            }

            message = (
                f"#ᴄʜᴀɴɴᴇʟ_ᴀᴅᴅᴇᴅ {type_emoji.get(channel_type, '📺')}\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🔖 {to_small_caps('type')}: {to_small_caps(channel_type.replace('_', ' '))}\n"
                f"📝 {to_small_caps('channel')}: <code>{channel_title}</code>\n"
                f"🆔 {to_small_caps('channel id')}: <code>{channel_id}</code>\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"{type_emoji.get(channel_type, '📺')} {to_small_caps(channel_type.replace('_', ' '))} {to_small_caps('added')}: {channel_title} {to_small_caps('by')} {name}", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging channel addition: {e}")
    @staticmethod
    async def log_channel_removed(client: Client, user_id: int, name: str, channel_type: str, channel_title: str, channel_id: int):
        """Log when user removes a channel"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ᴄʜᴀɴɴᴇʟ_ʀᴇᴍᴏᴠᴇᴅ 🗑️\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🔖 {to_small_caps('type')}: {to_small_caps(channel_type.replace('_', ' '))}\n"
                f"📝 {to_small_caps('channel')}: <code>{channel_title}</code>\n"
                f"🆔 {to_small_caps('channel id')}: <code>{channel_id}</code>\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"🗑️ {to_small_caps(channel_type.replace('_', ' '))} {to_small_caps('removed')}: {channel_title} {to_small_caps('by')} {name}", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging channel removal: {e}")
    @staticmethod
    async def log_forwarding_started(client: Client, user_id: int, name: str, bot_name: str, source_title: str, target_title: str, skip_duplicate: bool, source_id: int = None, target_id: int = None):
        """Log when forwarding process starts"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ғᴏʀᴡᴀʀᴅɪɴɢ_sᴛᴀʀᴛᴇᴅ 🚀\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🤖 {to_small_caps('bot')}: @{bot_name}\n"
                f"📢 {to_small_caps('source')}: {source_title}\n"
                f"🆔 {to_small_caps('source id')}: <code>{source_id}</code>\n"
                f"🎯 {to_small_caps('target')}: {target_title}\n"
                f"🆔 {to_small_caps('target id')}: <code>{target_id}</code>\n"
                f"♻️ {to_small_caps('skip duplicates')}: {'✅' if skip_duplicate else '❌'}\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"🚀 {to_small_caps('forwarding started')}: {name} ({user_id}) - {source_title} → {target_title}", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging forwarding start: {e}")
    @staticmethod
    async def log_forwarding_completed(client: Client, user_id: int, name: str, bot_name: str, total: int, success: int, failed: int, skipped: int, duplicate: int, time_taken: str):
        """Log when forwarding process completes"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ғᴏʀᴡᴀʀᴅɪɴɢ_ᴄᴏᴍᴘʟᴇᴛᴇᴅ ✅\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🤖 {to_small_caps('bot')}: @{bot_name}\n\n"
                f"📊 {to_small_caps('statistics')}:\n"
                f"📝 {to_small_caps('total messages')}: {total}\n"
                f"✅ {to_small_caps('success')}: {success}\n"
                f"❌ {to_small_caps('failed')}: {failed}\n"
                f"👥 {to_small_caps('duplicate')}: {duplicate}\n"
                f"⏭️ {to_small_caps('skipped')}: {skipped}\n"
                f"⏱️ {to_small_caps('time taken')}: {time_taken}\n\n"
                f"📅 {to_small_caps('completed on')}: {date_str}\n"
                f"⏰ {to_small_caps('completed at')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"✅ {to_small_caps('forwarding completed')}: {name} ({user_id}) - {total} {to_small_caps('msgs')} (✅{success} ❌{failed})", "success", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging forwarding completion: {e}")
    @staticmethod
    async def log_config_updated(client: Client, user_id: int, name: str, config_name: str, config_value: str):
        """Log when user updates configuration"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            # Truncate long values
            if len(str(config_value)) > 100:
                config_value = str(config_value)[:97] + "..."

            message = (
                f"#ᴄᴏɴғɪɢ_ᴜᴘᴅᴀᴛᴇᴅ ⚙️\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🔧 {to_small_caps('setting')}: {to_small_caps(config_name.replace('_', ' '))}\n"
                f"📝 {to_small_caps('value')}: <code>{config_value}</code>\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"⚙️ {to_small_caps('config updated')}: {name} ({user_id}) - {to_small_caps(config_name.replace('_', ' '))}", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging config update: {e}")
    @staticmethod
    async def log_ftm_setting_changed(client: Client, user_id: int, name: str, setting_name: str, setting_value: str):
        """Log when user changes FTM settings"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            if len(str(setting_value)) > 100:
                setting_value = str(setting_value)[:97] + "..."

            message = (
                f"#ғᴛᴍ_sᴇᴛᴛɪɴɢ ⚙️\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🔧 {to_small_caps('setting')}: {to_small_caps(setting_name.replace('_', ' '))}\n"
                f"📝 {to_small_caps('value')}: <code>{setting_value}</code>\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"⚙️ {to_small_caps('ftm setting')}: {name} ({user_id}) - {to_small_caps(setting_name.replace('_', ' '))}", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging FTM setting change: {e}")
    @staticmethod
    async def log_unequify_started(client: Client, user_id: int, name: str, bot_name: str, channel_title: str):
        """Log when unequify process starts"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ᴜɴᴇǫᴜɪғʏ_sᴛᴀʀᴛᴇᴅ 🔄\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🤖 {to_small_caps('bot')}: @{bot_name}\n"
                f"📢 {to_small_caps('channel')}: {channel_title}\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"🔄 {to_small_caps('unequify started')}: {name} ({user_id}) - {channel_title}", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging unequify start: {e}")
    @staticmethod
    async def log_unequify_completed(client: Client, user_id: int, name: str, bot_name: str, channel_title: str, total_scanned: int, duplicates_removed: int, time_taken: str):
        """Log when unequify process completes"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ᴜɴᴇǫᴜɪғʏ_ᴄᴏᴍᴘʟᴇᴛᴇᴅ ✅\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🤖 {to_small_caps('bot')}: @{bot_name}\n"
                f"📢 {to_small_caps('channel')}: {channel_title}\n\n"
                f"📊 {to_small_caps('statistics')}:\n"
                f"📝 {to_small_caps('total scanned')}: {total_scanned}\n"
                f"🗑️ {to_small_caps('duplicates removed')}: {duplicates_removed}\n"
                f"⏱️ {to_small_caps('time taken')}: {time_taken}\n\n"
                f"📅 {to_small_caps('completed on')}: {date_str}\n"
                f"⏰ {to_small_caps('completed at')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"✅ {to_small_caps('unequify completed')}: {name} ({user_id}) - 🗑️{duplicates_removed} {to_small_caps('removed')}", "success", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging unequify completion: {e}")
    @staticmethod
    async def log_task_cancelled(client: Client, user_id: int, name: str):
        """Log when a user cancels an ongoing task"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ᴛᴀsᴋ_ᴄᴀɴᴄᴇʟʟᴇᴅ ⚠️\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"⛔ {to_small_caps('action')}: {to_small_caps('task cancellation requested')}\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"⛔ {to_small_caps('task cancelled')}: {name} ({user_id})", "warning", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging task cancellation: {e}")
    @staticmethod
    async def log_config_reset(client: Client, user_id: int, name: str, removed_bots: int, removed_channels: int):
        """Log when a user resets their configuration"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ᴄᴏɴғɪɢ_ʀᴇsᴇᴛ 🔄\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n\n"
                f"📊 {to_small_caps('reset summary')}:\n"
                f"🤖 {to_small_caps('bots removed')}: {removed_bots}\n"
                f"📢 {to_small_caps('channels removed')}: {removed_channels}\n"
                f"⚙️ {to_small_caps('settings')}: {to_small_caps('reset to default')}\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"🔄 {to_small_caps('config reset')}: {name} ({user_id}) - 🤖{removed_bots} 📢{removed_channels}", "warning", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging config reset: {e}")
    @staticmethod
    async def log_ftmbucks_redemption(client: Client, user_id: int, name: str, 
                                      plan: str, cost: int, new_balance: int):
        """Log when a user redeems FtmBucks for a plan"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            plan_info = Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#FtmBucks_Redemption 💰\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"💎 {to_small_caps('plan redeemed')}: {plan_info['emoji']} {plan_info['name']}\n"
                f"💸 {to_small_caps('cost')}: {cost} FtmBucks\n"
                f"💵 {to_small_caps('new balance')}: {new_balance} FtmBucks\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"💰 {to_small_caps('ftmbucks redemption')}: {name} ({user_id}) - {plan_info['name']}", "success", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging FtmBucks redemption: {e}")
    @staticmethod
    async def log_admin_created(client: Client, user_id: int, user_name: str, 
                                username: str, created_by_id: int, created_by_name: str):
        """Log when a new admin is created"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, user_name)
            admin_link = BotLogger.get_user_link(created_by_id, created_by_name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ᴀᴅᴍɪɴ_ᴄʀᴇᴀᴛᴇᴅ 👨‍💼\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🔑 {to_small_caps('username')}: <code>{username}</code>\n"
                f"💎 {to_small_caps('plan')}: ♾️ {to_small_caps('infinity')} ({to_small_caps('lifetime')})\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}\n\n"
                f"👨‍💼 {to_small_caps('created by')}: {admin_link}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"👨‍💼 {to_small_caps('admin created')}: {user_name} ({user_id})", "success", created_by_name)
        except Exception as e:
            logging.error(f"Error logging admin creation: {e}")
    @staticmethod
    async def log_admin_removed(client: Client, user_id: int, user_name: str, 
                                removed_by_id: int, removed_by_name: str):
        """Log when an admin is removed"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, user_name)
            admin_link = BotLogger.get_user_link(removed_by_id, removed_by_name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ᴀᴅᴍɪɴ_ʀᴇᴍᴏᴠᴇᴅ ⚠️\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}\n\n"
                f"👨‍💼 {to_small_caps('removed by')}: {admin_link}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"⚠️ {to_small_caps('admin removed')}: {user_name} ({user_id})", "warning", removed_by_name)
        except Exception as e:
            logging.error(f"Error logging admin removal: {e}")
    @staticmethod
    async def log_user_removed(client: Client, user_id: int, user_name: str,
                               removed_by_id: int, removed_by_name: str):
        """Log when a user is completely removed from database"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, user_name)
            admin_link = BotLogger.get_user_link(removed_by_id, removed_by_name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ᴜsᴇʀ_ʀᴇᴍᴏᴠᴇᴅ 🗑️\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n\n"
                f"📅 {to_small_caps('removal date')}: {date_str}\n"
                f"⏰ {to_small_caps('removal time')}: {time_str}\n\n"
                f"👨‍💼 {to_small_caps('removed by')}: {admin_link}\n\n"
                f"⚠️ <i>{to_small_caps('user completely removed from all collections')}</i>"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"🗑️ {to_small_caps('user removed')}: {user_name} ({user_id})", "critical", removed_by_name)
        except Exception as e:
            logging.error(f"Error logging user removal: {e}")
    @staticmethod
    async def log_referral_initiated(client: Client, new_user_id: int, new_user_name: str, 
                                     referrer_id: int, referrer_name: str, referral_code: str):
        """Log when a referral is initiated (user clicked referral link but hasn't completed force sub)"""
        if not Config.LOG_CHANNEL:
            return

        try:
            new_user_link = BotLogger.get_user_link(new_user_id, new_user_name)
            referrer_link = BotLogger.get_user_link(referrer_id, referrer_name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ʀᴇғᴇʀʀᴀʟ_ɪɴɪᴛɪᴀᴛᴇᴅ 🔗\n\n"
                f"👤 {to_small_caps('new user')}: {new_user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{new_user_id}</code>\n\n"
                f"👨‍💼 {to_small_caps('referred by')}: {referrer_link}\n"
                f"🔑 {to_small_caps('referral code')}: <code>{referral_code}</code>\n\n"
                f"⏳ {to_small_caps('status')}: ᴘᴇɴᴅɪɴɢ ғᴏʀᴄᴇ sᴜʙsᴄʀɪʙᴇ\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"🔗 {to_small_caps('referral initiated')}: {new_user_name} ({new_user_id}) {to_small_caps('from')} {referrer_name}", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging referral initiation: {e}")
    @staticmethod
    async def log_referral_completed(client: Client, new_user_id: int, new_user_name: str, 
                                     referrer_id: int, referrer_name: str, referral_code: str,
                                     ftm_bucks_earned: int, trial_plan: str):
        """Log when a referral is completed (user completed force sub)"""
        if not Config.LOG_CHANNEL:
            return

        try:
            new_user_link = BotLogger.get_user_link(new_user_id, new_user_name)
            referrer_link = BotLogger.get_user_link(referrer_id, referrer_name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ʀᴇғᴇʀʀᴀʟ_ᴄᴏᴍᴘʟᴇᴛᴇᴅ ✅\n\n"
                f"👤 {to_small_caps('new user')}: {new_user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{new_user_id}</code>\n\n"
                f"👨‍💼 {to_small_caps('referred by')}: {referrer_link}\n"
                f"🔑 {to_small_caps('referral code')}: <code>{referral_code}</code>\n\n"
                f"🎁 {to_small_caps('rewards')}:\n"
                f"  💰 {to_small_caps('referrer earned')}: +{ftm_bucks_earned} ғᴛᴍʙᴜᴄᴋs\n"
                f"  ⭐ {to_small_caps('new user got')}: 1-ᴅᴀʏ {trial_plan} ᴛʀɪᴀʟ\n\n"
                f"✅ {to_small_caps('status')}: ᴄᴏᴍᴘʟᴇᴛᴇᴅ\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"✅ {to_small_caps('referral completed')}: {new_user_name} ({new_user_id}) {to_small_caps('from')} {referrer_name} (+{ftm_bucks_earned} ғᴛᴍʙᴜᴄᴋs)", "success", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging referral completion: {e}")
    @staticmethod
    async def log_verification_generated(client: Client, user_id: int, name: str, shortened_url: str):
        """Log when verification link is generated"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ_ɢᴇɴᴇʀᴀᴛᴇᴅ 🔗\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"🔗 {to_small_caps('link')}: <code>{shortened_url}</code>\n\n"
                f"📅 {to_small_caps('date')}: {date_str}\n"
                f"⏰ {to_small_caps('time')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"🔗 {to_small_caps('verification link generated')}: {name} ({user_id})", "info", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging verification generated: {e}")
    @staticmethod
    async def log_verification_completed(client: Client, user_id: int, name: str, expires_at):
        """Log when verification is completed successfully"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist = pytz.timezone('Asia/Kolkata')
            if expires_at.tzinfo is None:
                expires_at = pytz.utc.localize(expires_at)
            expires_ist = expires_at.astimezone(ist)
            expiry_date, expiry_time = BotLogger.format_datetime(expires_ist)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            message = (
                f"#ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ_ᴄᴏᴍᴘʟᴇᴛᴇᴅ ✅\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"⭐ {to_small_caps('plan granted')}: ᴘʟᴜs (4 ʜᴏᴜʀs)\n"
                f"⏰ {to_small_caps('expires')}: {expiry_date} {expiry_time}\n\n"
                f"📅 {to_small_caps('verified on')}: {date_str}\n"
                f"⏰ {to_small_caps('verified at')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"✅ {to_small_caps('verification completed')}: {name} ({user_id}) - 4ʜ ᴘʟᴜs", "success", "ʙᴏᴛ")
        except Exception as e:
            logging.error(f"Error logging verification completed: {e}")
    @staticmethod
    async def log_verification_expired(client: Client, user_id: int, name: str, had_active_forwarding: bool):
        """Log when verification plan expires"""
        if not Config.LOG_CHANNEL:
            return

        try:
            user_link = BotLogger.get_user_link(user_id, name)

            ist_time = BotLogger.get_ist_time()
            date_str, time_str = BotLogger.format_datetime(ist_time)

            forwarding_status = "⏸️ ᴘᴀᴜsᴇᴅ" if had_active_forwarding else "ɴᴏ ᴀᴄᴛɪᴠᴇ ᴛᴀsᴋ"

            message = (
                f"#ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ_ᴇxᴘɪʀᴇᴅ ⏰\n\n"
                f"👤 {to_small_caps('user')}: {user_link}\n"
                f"⚡ {to_small_caps('user id')}: <code>{user_id}</code>\n"
                f"⭐ {to_small_caps('expired plan')}: ᴘʟᴜs (ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ)\n"
                f"🔻 {to_small_caps('current plan')}: 🆓 ғʀᴇᴇ\n"
                f"📊 {to_small_caps('forwarding')}: {forwarding_status}\n\n"
                f"📅 {to_small_caps('expired on')}: {date_str}\n"
                f"⏰ {to_small_caps('expired at')}: {time_str}"
            )

            await client.send_message(Config.LOG_CHANNEL, message)
            BotLogger.save_to_admin_logs(f"⏰ {to_small_caps('verification expired')}: {name} ({user_id})", "warning", "sʏsᴛᴇᴍ")
        except Exception as e:
            logging.error(f"Error logging verification expired: {e}")