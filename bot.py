import asyncio
import logging 
import logging.config
from database import db 
from config import Config  
from pyrogram import Client, __version__
from pyrogram.raw.all import layer 
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait 
from pyrogram import utils as pyroutils
pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -100999999999999
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

class Bot(Client): 
    def __init__(self):
        super().__init__(
            Config.BOT_SESSION,
            api_hash=Config.API_HASH,
            api_id=Config.API_ID,
            plugins={
                "root": "plugins"
            },
            workers=50,
            bot_token=Config.BOT_TOKEN
        )
        self.log = logging
        self._scheduler_task = None

    async def start(self):
        await super().start()
        me = await self.get_me()
        logging.info(f"{me.first_name} with for pyrogram v{__version__} (Layer {layer}) started on @{me.username}.")
        self.id = me.id
        self.username = me.username
        self.first_name = me.first_name
        self.set_parse_mode(ParseMode.DEFAULT)
        text = "**๏[-ิ_•ิ]๏ bot restarted !**"
        logging.info(text)

        # Start subscription checker
        from plugins.subscription_checker import start_subscription_checker
        await start_subscription_checker(self)

        # Start background cleanup task for expired chat requests (merged from ftm-forwardbot-latest)
        try:
            from utils.cleanup import periodic_cleanup
            asyncio.create_task(periodic_cleanup())
            logging.info("Background cleanup task started")
        except Exception as e:
            logging.error(f"Failed to start cleanup task: {e}")

        logging.info(f"{me.first_name} started ⚡️⚡️⚡️")

        # Log bot restart to log channel
        from plugins.logger import BotLogger
        await BotLogger.log_bot_restart(self)
        success = failed = 0
        users = await db.get_all_frwd()
        async for user in users:
           chat_id = user['user_id']
           try:
              await self.send_message(chat_id, text)
              success += 1
           except FloodWait as e:
              await asyncio.sleep(e.value if hasattr(e, 'value') else getattr(e, 'x', 10))
              await self.send_message(chat_id, text)
              success += 1
           except Exception:
              failed += 1 
    #    await self.send_message("venombotsupport", text)
        if (success + failed) != 0:
           await db.rmve_frwd(all=True)
           logging.info(f"Restart message status - success: {success}, failed: {failed}")

        # Restore gamma mode monitoring for users who had it enabled
        from plugins.ftm_manager import start_gamma_monitoring
        from plugins.test import get_configs

        all_users = await db.get_all_users()
        gamma_restored = 0
        async for user_doc in all_users:
            try:
                user_id = user_doc['id']
                config = await get_configs(user_id)
                if config and config.get('ftm_gamma_mode', False):
                    if await start_gamma_monitoring(user_id):
                        gamma_restored += 1
            except Exception as e:
                logging.error(f"Failed to restore gamma mode for user {user_doc.get('id')}: {e}")

        if gamma_restored > 0:
            logging.info(f"Gamma mode monitoring restored for {gamma_restored} users")

        # FTM Alpha Mode - Auto-resume interrupted forwarding processes
        try:
            active_states = await db.get_all_active_forwarding_states()
            alpha_resumed = 0
            alpha_completed = 0
            async for state in active_states:
                try:
                    user_id = state.get('user_id')
                    fwd_type = state.get('type')
                    status = state.get('status')
                    
                    # Check if user still has alpha mode enabled
                    user_config = await get_configs(user_id)
                    if not user_config.get('ftm_alpha_mode', False):
                        # Alpha mode disabled, cancel the state
                        await db.cancel_forwarding_state(user_id, fwd_type)
                        continue
                    
                    if fwd_type == 'manual':
                        # Manual forwarding was interrupted - auto-restart from last message
                        processed = state.get('processed', 0)
                        total = state.get('total', 0)
                        source_id = state.get('source_chat_id')
                        target_id = state.get('target_chat_id')
                        last_msg_id = state.get('last_msg_id', 0)
                        
                        # Check if already completed
                        if processed >= total and total > 0:
                            await db.complete_forwarding_state(user_id, fwd_type)
                            continue

                        # Auto-restart forwarding from last message
                        try:
                            from plugins.regix import resume_alpha_forwarding
                            resume_success = await resume_alpha_forwarding(
                                self, user_id, state
                            )
                            
                            if resume_success:
                                # Notify user about auto-restart
                                await self.send_message(
                                    user_id,
                                    f"<b>🧬 ғᴛᴍ ᴀʟᴘʜᴀ ᴍᴏᴅᴇ 🧬</b>\n\n"
                                    f"✨ <b>ᴀᴜᴛᴏ-ʀᴇsᴛᴀʀᴛ ᴀᴄᴛɪᴠᴀᴛᴇᴅ</b>\n\n"
                                    f"📊 <b>ᴘʀᴏɢʀᴇss:</b> {processed}/{total} ᴍᴇssᴀɢᴇs\n"
                                    f"📤 <b>sᴏᴜʀᴄᴇ:</b> <code>{source_id}</code>\n"
                                    f"📥 <b>ᴛᴀʀɢᴇᴛ:</b> <code>{target_id}</code>\n\n"
                                    f"<i>🔄 ʀᴇsᴜᴍɪɴɢ ғʀᴏᴍ ʟᴀsᴛ ᴍᴇssᴀɢᴇ...</i>\n\n"
                                    f"<b>⚡ ᴘᴏᴡᴇʀᴇᴅ ʙʏ <a href=https://t.me/ftmbotzx>ғᴛᴍʙᴏᴛᴢx</a></b>"
                                )
                                alpha_resumed += 1
                            else:
                                # Fallback to notification if resume fails (no valid bot credentials)
                                await self.send_message(
                                    user_id,
                                    f"<b>🧬 ғᴛᴍ ᴀʟᴘʜᴀ ᴍᴏᴅᴇ 🧬</b>\n\n"
                                    f"⚠️ <b>ɪɴᴛᴇʀʀᴜᴘᴛᴇᴅ ғᴏʀᴡᴀʀᴅɪɴɢ ᴅᴇᴛᴇᴄᴛᴇᴅ</b>\n\n"
                                    f"📊 <b>ᴘʀᴏɢʀᴇss:</b> {processed}/{total} ᴍᴇssᴀɢᴇs\n"
                                    f"📤 <b>sᴏᴜʀᴄᴇ:</b> <code>{source_id}</code>\n"
                                    f"📥 <b>ᴛᴀʀɢᴇᴛ:</b> <code>{target_id}</code>\n\n"
                                    f"<i>❌ ᴀᴜᴛᴏ-ʀᴇsᴛᴀʀᴛ ғᴀɪʟᴇᴅ - ɴᴏ ᴠᴀʟɪᴅ ʙᴏᴛ/sᴇssɪᴏɴ ғᴏᴜɴᴅ.</i>\n"
                                    f"<i>ᴘʟᴇᴀsᴇ ᴀᴅᴅ ᴀ ʙᴏᴛ ᴏʀ sᴇssɪᴏɴ ᴠɪᴀ /settings ᴀɴᴅ ᴜsᴇ /forward ᴛᴏ ʀᴇsᴛᴀʀᴛ.</i>\n\n"
                                    f"<b>⚡ ᴘᴏᴡᴇʀᴇᴅ ʙʏ <a href=https://t.me/ftmbotzx>ғᴛᴍʙᴏᴛᴢx</a></b>"
                                )
                                alpha_completed += 1
                                # Mark state as paused
                                await db.save_forwarding_state(user_id, {
                                    'type': fwd_type,
                                    'status': 'paused',
                                    'paused_reason': 'no_credentials'
                                }, merge=True)
                        except Exception as resume_e:
                            logging.error(f"Failed to auto-restart forwarding for user {user_id}: {resume_e}")
                            # Notify user about failure
                            try:
                                await self.send_message(
                                    user_id,
                                    f"<b>🧬 ғᴛᴍ ᴀʟᴘʜᴀ ᴍᴏᴅᴇ 🧬</b>\n\n"
                                    f"⚠️ <b>ɪɴᴛᴇʀʀᴜᴘᴛᴇᴅ ғᴏʀᴡᴀʀᴅɪɴɢ ᴅᴇᴛᴇᴄᴛᴇᴅ</b>\n\n"
                                    f"📊 <b>ᴘʀᴏɢʀᴇss:</b> {processed}/{total} ᴍᴇssᴀɢᴇs\n\n"
                                    f"<i>❌ ᴀᴜᴛᴏ-ʀᴇsᴛᴀʀᴛ ғᴀɪʟᴇᴅ. ᴘʟᴇᴀsᴇ ᴜsᴇ /forward ᴛᴏ ʀᴇsᴛᴀʀᴛ ᴍᴀɴᴜᴀʟʟʏ.</i>\n\n"
                                    f"<b>⚡ ᴘᴏᴡᴇʀᴇᴅ ʙʏ <a href=https://t.me/ftmbotzx>ғᴛᴍʙᴏᴛᴢx</a></b>"
                                )
                            except Exception:
                                pass
                            alpha_completed += 1
                        
                        # Log to log channel
                        if Config.LOG_CHANNEL:
                            try:
                                await self.send_message(
                                    Config.LOG_CHANNEL,
                                    f"#ᴀʟᴘʜᴀ_ʀᴇsᴜᴍᴇ\n\n"
                                    f"<b>ᴜsᴇʀ ɪᴅ:</b> <code>{user_id}</code>\n"
                                    f"<b>ᴛʏᴘᴇ:</b> {fwd_type}\n"
                                    f"<b>ᴘʀᴏɢʀᴇss:</b> {processed}/{total}\n"
                                    f"<i>🧬 ғᴛᴍ ᴀʟᴘʜᴀ ᴀᴜᴛᴏ-ʀᴇsᴛᴀʀᴛ ɪɴɪᴛɪᴀᴛᴇᴅ</i>"
                                )
                            except Exception as log_e:
                                logging.error(f"Failed to log alpha resume: {log_e}")
                        
                except Exception as state_e:
                    logging.error(f"Error processing alpha state for user {state.get('user_id')}: {state_e}")
            
            if alpha_resumed > 0 or alpha_completed > 0:
                logging.info(f"FTM Alpha Mode: Resumed {alpha_resumed} gamma, Notified {alpha_completed} interrupted manual processes")
        except Exception as alpha_e:
            logging.error(f"Error in FTM Alpha Mode auto-resume: {alpha_e}")

        # Clear all user approval statuses on restart
        try:
            result = await db.col.update_many(
                {},
                {'$unset': {'approval_status': ''}}
            )
            if result.modified_count > 0:
                logging.info(f"Cleared approval status for {result.modified_count} users on restart")
        except Exception as e:
            logging.error(f"Failed to clear approval statuses: {e}")

    async def subscription_expiration_scheduler(self):
        """Background task to periodically check and expire subscriptions"""
        logging.info("Subscription expiration scheduler started")
        while True:
            try:
                # Check every 60 seconds for expired subscriptions
                await asyncio.sleep(60)

                # Expire subscriptions that have passed their expiry date
                expired_count = await db.expire_subscriptions()

                if expired_count > 0:
                    logging.info(f"Expired {expired_count} subscription(s) - users moved to free plan")

            except asyncio.CancelledError:
                logging.info("Subscription expiration scheduler stopped")
                break
            except Exception as e:
                logging.error(f"Error in subscription expiration scheduler: {e}")
                await asyncio.sleep(60)  # Wait and retry on error

    async def stop(self, *args):
        # Stop subscription checker
        from plugins.subscription_checker import stop_subscription_checker
        await stop_subscription_checker()

        # Cancel the subscription scheduler task
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        msg = f"@{self.username} stopped. Bye."
        await super().stop()
        logging.info(msg)

    # ============ Ported from ftm-forwardbot-latest ============
    async def grant_sudo_lifetime_subscriptions(self):
        """Grant lifetime Pro subscriptions to all sudo users if not already given"""
        try:
            # Get all sudo users (owners + admins)
            sudo_users = Config.OWNER_ID + Config.ADMIN_ID
            granted_count = 0
            
            for sudo_user_id in sudo_users:
                try:
                    # Check if user already has an active premium subscription
                    existing_premium = await db.get_premium_user_details(sudo_user_id)
                    
                    if existing_premium and existing_premium.get('is_active', False):
                        # Check if it's already a lifetime subscription
                        if existing_premium.get('amount_paid') == 'sudo_lifetime_subscription':
                            logging.info(f"Sudo user {sudo_user_id} already has lifetime subscription, skipping")
                            continue
                        else:
                            # User has some other subscription, remove it first
                            await db.remove_premium_user(sudo_user_id)
                            logging.info(f"Removed existing subscription for sudo user {sudo_user_id}")
                    
                    # Grant lifetime Pro subscription (999 years)
                    await db.add_premium_user(
                        user_id=sudo_user_id,
                        plan_type="pro",
                        duration_days=365250,  # 999+ years (lifetime)
                        amount_paid="sudo_lifetime_subscription"
                    )
                    
                    granted_count += 1
                    logging.info(f"✅ Granted lifetime Pro subscription to sudo user {sudo_user_id}")
                    
                    # Send notification to the sudo user
                    try:
                        await self.send_message(
                            sudo_user_id,
                            "<b>🎉 Lifetime Pro Access Granted!</b>\n\n"
                            "<b>✅ You have been automatically granted lifetime Pro access as a sudo user!</b>\n\n"
                            "<b>🏆 Pro Plan Benefits:</b>\n"
                            "• ♾️ Unlimited forwarding processes\n"
                            "• 🔥 FTM mode with source tracking\n"
                            "• 🛡️ Priority support\n"
                            "• ⚡ Enhanced performance\n"
                            "• 📈 All premium features unlocked\n\n"
                            "<b>⏰ Duration:</b> Lifetime (999+ years)\n"
                            "<b>🔑 Access Level:</b> Sudo User\n\n"
                            "<b>Use /myplan to check your subscription details.</b>"
                        )
                    except Exception as notify_error:
                        logging.error(f"Failed to notify sudo user {sudo_user_id}: {notify_error}")
                        
                except Exception as user_error:
                    logging.error(f"Failed to grant subscription to sudo user {sudo_user_id}: {user_error}")
                    
            if granted_count > 0:
                logging.info(f"✅ Granted lifetime Pro subscriptions to {granted_count} sudo users")
                
                # Send notification to log channel (only if notification_manager exists)
                try:
                    if hasattr(self, 'notification_manager'):
                        await self.notification_manager.send_log_notification(
                            f"<b>🏆 Sudo Lifetime Subscriptions Granted!</b>\n\n"
                            f"<b>Count:</b> {granted_count} users\n"
                            f"<b>Plan:</b> Pro (Lifetime)\n"
                            f"<b>Access Level:</b> Sudo Users\n"
                            f"<b>Duration:</b> 999+ years\n\n"
                            f"<b>✅ All sudo users now have lifetime Pro access!</b>"
                        )
                except Exception as log_error:
                    logging.error(f"Failed to send sudo subscription log: {log_error}")
            else:
                logging.info("ℹ️ No new sudo lifetime subscriptions needed - all already have access")
                
        except Exception as e:
            logging.error(f"Error granting sudo lifetime subscriptions: {e}")
    # ============ end ported block ============
