
from pyrogram import Client, enums
from database import db
from config import Config
from datetime import datetime, timedelta
import asyncio
import pytz
from plugins.utils import to_small_caps
import logging

class SubscriptionChecker:
    """Background task to check and expire subscriptions"""
    
    def __init__(self, client: Client):
        self.client = client
        self.running = False
    
    async def send_telegram_notification(self, user_id, message):
        """Send notification to specific user"""
        try:
            await self.client.send_message(user_id, message, parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            logging.error(f"Failed to send notification to user {user_id}: {e}")
    async def send_log_notification(self, message):
        """Send notification to log channel"""
        if not Config.LOG_CHANNEL:
            return
        
        try:
            await self.client.send_message(Config.LOG_CHANNEL, message, parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            logging.error(f"Failed to send log notification: {e}")
    async def save_admin_notification(self, message, log_type="warning"):
        """Save notification to admin panel"""
        try:
            from pymongo import MongoClient
            client = MongoClient(Config.DATABASE_URI)
            admin_db = client[Config.DATABASE_NAME]
            
            admin_db.admin_logs.insert_one({
                "message": message,
                "log_type": log_type,
                "timestamp": datetime.utcnow(),
                "admin": "sʏsᴛᴇᴍ",
                "read": False
            })
            
            # Also add to notifications collection
            admin_db.notifications.insert_one({
                "message": message,
                "type": "subscription_expiry",
                "timestamp": datetime.utcnow(),
                "read": False
            })
            
            client.close()
        except Exception as e:
            logging.error(f"Failed to save admin notification: {e}")
    async def check_expiring_soon(self):
        """Check for subscriptions expiring in 24 hours"""
        try:
            logging.info("🔍 Checking for expiring subscriptions...")
            now = datetime.utcnow()
            tomorrow = now + timedelta(hours=24)
            
            # Find users whose subscription expires in 24 hours
            users_expiring_soon = db.col.find({
                'subscription.expires_at': {
                    '$gte': now,
                    '$lte': tomorrow
                },
                'subscription.status': 'active',
                'subscription.plan': {'$ne': 'free'}
            })
            
            ist = pytz.timezone('Asia/Kolkata')
            
            async for user in users_expiring_soon:
                user_id = user['id']
                user_name = user.get('name', 'ᴜɴᴋɴᴏᴡɴ')
                subscription = user.get('subscription', {})
                plan = subscription.get('plan', 'free')
                expires_at = subscription.get('expires_at')
                
                if not expires_at:
                    continue
                
                # Check if we already sent warning (to avoid spam)
                if subscription.get('expiry_warning_sent'):
                    continue
                
                plan_info = Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])
                
                # Convert to IST
                if expires_at.tzinfo is None:
                    expires_at = pytz.utc.localize(expires_at)
                expires_ist = expires_at.astimezone(ist)
                expiry_date = expires_ist.strftime('%d-%m-%Y')
                expiry_time = expires_ist.strftime('%I:%M:%S %p')
                
                # Calculate time left
                time_diff = expires_at.replace(tzinfo=None) - now
                hours_left = int(time_diff.total_seconds() / 3600)
                minutes_left = int((time_diff.total_seconds() % 3600) / 60)
                
                # Notify user
                user_message = f"""<b>⚠️ {to_small_caps('subscription expiring soon')} ⚠️</b>

{to_small_caps('your')} <b>{plan_info['emoji']} {plan_info['name']}</b> {to_small_caps('plan will expire soon!')}

<b>⏰ {to_small_caps('time remaining')}:</b> {hours_left} {to_small_caps('hours')}, {minutes_left} {to_small_caps('minutes')}

<b>📅 {to_small_caps('expiry date')}:</b> {expiry_date}
<b>🕐 {to_small_caps('expiry time')}:</b> {expiry_time}

<b>💡 {to_small_caps('renew now to continue enjoying premium features!')}</b>

{to_small_caps('use')} /subscription {to_small_caps('to view plans')}
{to_small_caps('or contact admin to renew')}: {Config.SUPPORT_GROUP}"""

                await self.send_telegram_notification(user_id, user_message)
                
                # Log to channel
                log_message = f"""<b>#sᴜʙsᴄʀɪᴘᴛɪᴏɴ_ᴇxᴘɪʀɪɴɢ_sᴏᴏɴ ⚠️</b>

👤 <b>{to_small_caps('user')}:</b> <a href="tg://user?id={user_id}">{user_name}</a>
⚡ <b>{to_small_caps('user id')}:</b> <code>{user_id}</code>
💎 <b>{to_small_caps('plan')}:</b> {plan_info['emoji']} {plan_info['name']}

⏰ <b>{to_small_caps('time left')}:</b> {hours_left} {to_small_caps('hours')}, {minutes_left} {to_small_caps('minutes')}

📅 <b>{to_small_caps('expires on')}:</b> {expiry_date}
🕐 <b>{to_small_caps('expires at')}:</b> {expiry_time}"""

                await self.send_log_notification(log_message)
                
                # Save to admin panel
                await self.save_admin_notification(
                    f"⚠️ {user_name} ({user_id}) - {plan_info['name']} {to_small_caps('plan expiring in')} {hours_left}h",
                    "warning"
                )
                
                # Mark warning as sent
                await db.col.update_one(
                    {'id': user_id},
                    {'$set': {'subscription.expiry_warning_sent': True}}
                )
                
                logging.info(f"✅ Sent expiry warning to {user_name} ({user_id})")
        except Exception as e:
            logging.error(f"❌ Error checking expiring subscriptions: {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    async def expire_subscriptions(self):
        """Check and expire subscriptions"""
        try:
            now = datetime.utcnow()
            ist = pytz.timezone('Asia/Kolkata')
            
            # Find expired subscriptions
            expired_users = db.col.find({
                'subscription.expires_at': {'$lt': now},
                'subscription.status': 'active',
                'subscription.plan': {'$ne': 'free'}
            })
            
            async for user in expired_users:
                user_id = user['id']
                user_name = user.get('name', 'ᴜɴᴋɴᴏᴡɴ')
                subscription = user.get('subscription', {})
                old_plan = subscription.get('plan', 'free')
                expires_at = subscription.get('expires_at')
                
                if not expires_at:
                    continue
                
                plan_info = Config.SUBSCRIPTION_PLANS.get(old_plan, Config.SUBSCRIPTION_PLANS['free'])
                
                # Convert to IST
                if expires_at.tzinfo is None:
                    expires_at = pytz.utc.localize(expires_at)
                expires_ist = expires_at.astimezone(ist)
                expired_date = expires_ist.strftime('%d-%m-%Y')
                expired_time = expires_ist.strftime('%I:%M:%S %p')
                
                # Update to free plan (active, not expired status)
                await db.col.update_one(
                    {'id': user_id},
                    {'$set': {
                        'subscription': {
                            'plan': 'free',
                            'status': 'active',
                            'expires_at': None,
                            'purchased_at': None,
                            'assigned_by': 'system',
                            'features': Config.SUBSCRIPTION_PLANS['free']['features'],
                            'previous_plan': old_plan,
                            'expired_at': datetime.utcnow()
                        }
                    }}
                )
                
                # Notify user
                user_message = f"""<b>⏰ {to_small_caps('subscription expired')} ⏰</b>

{to_small_caps('your')} <b>{plan_info['emoji']} {plan_info['name']}</b> {to_small_caps('plan has expired.')}

<b>📅 {to_small_caps('expired on')}:</b> {expired_date}
<b>🕐 {to_small_caps('expired at')}:</b> {expired_time}

<b>🔻 {to_small_caps('current plan')}:</b> 🆓 {to_small_caps('free')}

<b>💡 {to_small_caps('renew your subscription to continue enjoying premium features!')}</b>

{to_small_caps('use')} /subscription {to_small_caps('to view plans')}
{to_small_caps('or contact admin')}: {Config.SUPPORT_GROUP}"""

                await self.send_telegram_notification(user_id, user_message)
                
                # Log to channel
                log_message = f"""<b>#sᴜʙsᴄʀɪᴘᴛɪᴏɴ_ᴇxᴘɪʀᴇᴅ ⏰</b>

👤 <b>{to_small_caps('user')}:</b> <a href="tg://user?id={user_id}">{user_name}</a>
⚡ <b>{to_small_caps('user id')}:</b> <code>{user_id}</code>
💎 <b>{to_small_caps('expired plan')}:</b> {plan_info['emoji']} {plan_info['name']}
🔻 <b>{to_small_caps('current plan')}:</b> 🆓 {to_small_caps('free')}

📅 <b>{to_small_caps('expired on')}:</b> {expired_date}
🕐 <b>{to_small_caps('expired at')}:</b> {expired_time}

⚙️ <b>{to_small_caps('auto-expired by system')}</b>"""

                await self.send_log_notification(log_message)
                
                # Save to admin panel with detailed notification
                await self.save_admin_notification(
                    f"⏰ {user_name} ({user_id}) - {plan_info['name']} {to_small_caps('plan expired and downgraded to free')}",
                    "warning"
                )
                
                # Also add to notifications collection for web panel
                try:
                    from pymongo import MongoClient
                    client_db = MongoClient(Config.DATABASE_URI)
                    admin_db = client_db[Config.DATABASE_NAME]
                    
                    admin_db.notifications.insert_one({
                        "message": f"⏰ Subscription Expired: {user_name} ({user_id}) - {plan_info['name']} plan has expired and user downgraded to Free plan",
                        "type": "subscription_expired",
                        "user_id": user_id,
                        "user_name": user_name,
                        "old_plan": old_plan,
                        "new_plan": "free",
                        "expired_date": expired_date,
                        "expired_time": expired_time,
                        "timestamp": datetime.utcnow(),
                        "read": False
                    })
                    
                    client_db.close()
                except Exception as e:
                    logging.error(f"Failed to save detailed notification: {e}")
                # Store in chat
                await db.db.chats.insert_one({
                    "user_id": user_id,
                    "sender_type": "system",
                    "sender_name": "sʏsᴛᴇᴍ",
                    "message": f"⏰ {to_small_caps('your')} {plan_info['name']} {to_small_caps('plan has expired. you are now on free plan.')}",
                    "timestamp": datetime.utcnow(),
                    "read": True,
                    "notification_type": "subscription_expired"
                })
                
                logging.info(f"✅ Expired subscription for {user_name} ({user_id})")
        except Exception as e:
            logging.error(f"❌ Error expiring subscriptions: {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    async def check_verification_plan_expiry(self):
        """Check for verification bonus plans that have expired and pause forwarding if active"""
        try:
            logging.info("🔍 Checking for verification plan expiry...")
            now = datetime.utcnow()
            from config import temp
            from plugins.logger import BotLogger
            
            expired_verification_users = db.col.find({
                'subscription.is_verification_plan': True,
                'subscription.expires_at': {'$lt': now},
                'subscription.status': 'active'
            })
            
            ist = pytz.timezone('Asia/Kolkata')
            
            async for user in expired_verification_users:
                user_id = user['id']
                user_name = user.get('name', 'ᴜɴᴋɴᴏᴡɴ')
                
                active_tasks = await db.get_active_tasks(user_id)
                has_active_forwarding = active_tasks.get('forwarding', 0) > 0
                
                if has_active_forwarding:
                    temp.CANCEL[user_id] = True
                    await db.pause_user_forwarding(user_id)
                
                await db.col.update_one(
                    {'id': user_id},
                    {'$set': {
                        'subscription.plan': 'free',
                        'subscription.status': 'active',
                        'subscription.expires_at': None,
                        'subscription.purchased_at': None,
                        'subscription.assigned_by': 'system',
                        'subscription.features': Config.SUBSCRIPTION_PLANS['free']['features'],
                        'subscription.previous_plan': 'plus',
                        'subscription.expired_at': datetime.utcnow(),
                        'subscription.is_verification_plan': False,
                        'verification_bonus.is_verified': False,
                        'verification_bonus.plan_expires_at': None
                    }}
                )
                
                if has_active_forwarding:
                    user_message = f"""<b>⏰ {to_small_caps('verification plan expired')} ⏰</b>

{to_small_caps('your')} <b>4-ʜᴏᴜʀ ᴘʟᴜs</b> {to_small_caps('verification bonus has expired!')}

<b>⏸️ {to_small_caps('forwarding paused')}</b>
{to_small_caps('your active forwarding task has been paused automatically.')}

<b>🔄 {to_small_caps('to resume forwarding:')}</b>
1️⃣ {to_small_caps('use')} /free {to_small_caps('for another 4-hour verification')}
2️⃣ {to_small_caps('or buy a plan from')} /subscription

<b>💡 {to_small_caps('tip')}: {to_small_caps('buy a plan for uninterrupted forwarding!')}</b>"""
                else:
                    user_message = f"""<b>⏰ {to_small_caps('verification plan expired')} ⏰</b>

{to_small_caps('your')} <b>4-ʜᴏᴜʀ ᴘʟᴜs</b> {to_small_caps('verification bonus has expired!')}

🔻 <b>{to_small_caps('current plan')}:</b> 🆓 {to_small_caps('free')}

<b>🔄 {to_small_caps('to get forwarding access again:')}</b>
1️⃣ {to_small_caps('use')} /free {to_small_caps('for another 4-hour verification')}
2️⃣ {to_small_caps('or buy a plan from')} /subscription"""

                await self.send_telegram_notification(user_id, user_message)
                await BotLogger.log_verification_expired(self.client, user_id, user_name, has_active_forwarding)
                
                logging.info(f"✅ Verification plan expired for {user_name} ({user_id}), forwarding_paused: {has_active_forwarding}")
        except Exception as e:
            logging.error(f"❌ Error checking verification plan expiry: {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    async def run(self):
        """Run the subscription checker continuously"""
        self.running = True
        logging.info("🔄 Subscription checker started")
        while self.running:
            try:
                # Check for expiring subscriptions (24h warning)
                await self.check_expiring_soon()
                
                # Expire subscriptions
                await self.expire_subscriptions()
                
                # Check verification plan expiry (runs every 5 minutes for faster response)
                await self.check_verification_plan_expiry()
                
                # Wait 5 minutes before next check (reduced for verification plans)
                await asyncio.sleep(300)
            
            except Exception as e:
                logging.error(f"Error in subscription checker: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    def stop(self):
        """Stop the subscription checker"""
        self.running = False
        logging.info("🛑 Subscription checker stopped")
# Global instance
subscription_checker = None

async def start_subscription_checker(client: Client):
    """Start the subscription checker"""
    global subscription_checker
    subscription_checker = SubscriptionChecker(client)
    asyncio.create_task(subscription_checker.run())

async def stop_subscription_checker():
    """Stop the subscription checker"""
    global subscription_checker
    if subscription_checker:
        subscription_checker.stop()
