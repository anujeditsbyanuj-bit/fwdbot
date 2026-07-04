import os
import sys
import asyncio 
import logging
import psutil
import speedtest
import platform
from database import db, mongodb_version
from config import Config, temp
from platform import python_version
from translation import Translation
from pyrogram import Client, filters, enums, __version__ as pyrogram_version
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaDocument
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, ChannelPrivate

logger = logging.getLogger(__name__)



async def check_force_sub(client, user_id):
    """
    Check if user has joined all force subscribe channels.
    Returns (is_subscribed: bool, not_joined_channels: list)
    """
    from pyrogram.errors import FloodWait
    
    if not Config.FORCE_SUB_CHANNELS:
        return True, []
    
    # Skip check for bot owners
    if user_id in Config.BOT_OWNER_ID:
        return True, []
    
    not_joined = []
    
    for channel in Config.FORCE_SUB_CHANNELS:
        try:
            # Convert to int if it's a numeric ID
            chat_id = int(channel) if channel.lstrip('-').isdigit() else channel
            
            member = await client.get_chat_member(chat_id, user_id)
            # Use enum comparison for Pyrogram 2.x
            if member.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:
                not_joined.append(channel)
        except UserNotParticipant:
            not_joined.append(channel)
        except (ChatAdminRequired, ChannelPrivate):
            # Bot is not admin or channel is private, skip this channel check
            continue
        except FloodWait as e:
            # Handle flood wait - wait and retry
            await asyncio.sleep(e.value if hasattr(e, 'value') else getattr(e, 'x', 10))
            try:
                member = await client.get_chat_member(chat_id, user_id)
                if member.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:
                    not_joined.append(channel)
            except UserNotParticipant:
                not_joined.append(channel)
            except Exception:
                continue
        except Exception as e:
            logging.error(f"Error checking force sub for channel {channel}: {e}")
            continue
    
    return len(not_joined) == 0, not_joined


async def get_all_force_sub_buttons(client, not_joined_channels):
    """
    Generate join buttons for ALL force subscribe channels.
    Shows channel name and creates invite link using Pyrogram.
    Marks channels as joined or not joined.
    """
    from pyrogram.errors import FloodWait
    
    buttons = []
    
    for channel in Config.FORCE_SUB_CHANNELS:
        try:
            # Convert to int if it's a numeric ID
            chat_id = int(channel) if channel.lstrip('-').isdigit() else channel
            
            # Get chat info with FloodWait handling
            try:
                chat = await client.get_chat(chat_id)
            except FloodWait as e:
                await asyncio.sleep(e.value if hasattr(e, 'value') else getattr(e, 'x', 10))
                chat = await client.get_chat(chat_id)
            
            channel_name = chat.title or "Channel"
            
            # Create invite link using Pyrogram
            try:
                invite_link = await client.export_chat_invite_link(chat_id)
            except FloodWait as e:
                await asyncio.sleep(e.value if hasattr(e, 'value') else getattr(e, 'x', 10))
                try:
                    invite_link = await client.export_chat_invite_link(chat_id)
                except Exception:
                    invite_link = None
            except Exception:
                invite_link = None
            
            # Fallback to existing invite link or username
            if not invite_link:
                if chat.invite_link:
                    invite_link = chat.invite_link
                elif chat.username:
                    invite_link = f"https://t.me/{chat.username}"
                else:
                    continue
            
            # Check if user has joined this channel
            is_joined = channel not in not_joined_channels
            
            if is_joined:
                # User has joined - show checkmark
                buttons.append([InlineKeyboardButton(f"✅ {channel_name}", url=invite_link)])
            else:
                # User hasn't joined - show join button
                buttons.append([InlineKeyboardButton(f"📢 ᴊᴏɪɴ {channel_name}", url=invite_link)])
                
        except Exception as e:
            logging.error(f"Error getting info for channel {channel}: {e}")
            continue
    
    # Add a refresh button to check again
    buttons.append([InlineKeyboardButton("🔄 ᴄʜᴇᴄᴋ ᴀɢᴀɪɴ", callback_data="check_force_sub")])
    
    return buttons

main_buttons = [[
        InlineKeyboardButton('🙋‍♂️ ʜᴇʟᴘ', callback_data='help'),
        InlineKeyboardButton('💁‍♂️ ᴀʙᴏᴜᴛ', callback_data='about')
        ],[
        InlineKeyboardButton('⚙️ sᴇᴛᴛɪɴɢs', callback_data='settings#main'),
        InlineKeyboardButton('📋 ᴘʟᴀɴs', callback_data='sub#main')
        ],[
        InlineKeyboardButton('💳 ᴍʏ ᴘʟᴀɴ', callback_data='sub#my_plan'),
        InlineKeyboardButton('🎁 ʀᴇғᴇʀʀᴀʟ', callback_data='referral#refresh')
        ],[
        InlineKeyboardButton('🎓 ʜᴏᴡ ᴛᴏ ᴜsᴇ ᴍᴇ', url=Config.TUTORIAL)
        ],[
        InlineKeyboardButton('🎛️ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ', url='http://t.me/ftm_autoforward_bot/ftmbotzx')
        ],[
        InlineKeyboardButton('📢 ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ', url=Config.MAIN_CHANNEL),
        InlineKeyboardButton('📜 sᴜᴘᴘᴏʀᴛ', url=Config.SUPPORT_GROUP)
        ],[
        InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇs', url=Config.UPDATE_CHANNEL),
        InlineKeyboardButton('📞 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ', url=Config.ADMIN_CONTACT_URL)
        ]]
#===================Start Function===================#

@Client.on_message(filters.private & filters.command(['start']))
async def start(client, message):
    user = message.from_user
    from datetime import datetime, timedelta
    from plugins.logger import BotLogger
    from pyrogram.errors import FloodWait
    import logging
    import traceback
    
    try:
        # Check for l_verify callback first
        if len(message.command) > 1:
            param = message.command[1]
            if param.startswith('l_verify_'):
                token = param.replace('l_verify_', '')
                from plugins.link_verify import handle_l_verify_callback
                await handle_l_verify_callback(client, user.id, token, message)
                return
        
        # Check for referral code first (before force sub check)
        referred_by_code = None
        if len(message.command) > 1:
            param = message.command[1]
            if param.startswith('refer_'):
                referred_by_code = param.replace('refer_', '')
        
        # Force Subscribe Check - User must join all channels before using the bot
        is_subscribed, not_joined = await check_force_sub(client, user.id)
    
        if not is_subscribed:
            # If user came via referral link and is new, initiate referral tracking
            is_new_user = not await db.is_user_exist(user.id)
            
            if referred_by_code and is_new_user:
                # Check if referral code is valid
                referrer = await db.get_user_by_referral_code(referred_by_code)
                if referrer and user.id not in temp.PENDING_REFERRALS:
                    # Store pending referral
                    temp.PENDING_REFERRALS[user.id] = {
                        'referral_code': referred_by_code,
                        'referrer_id': referrer['id'],
                        'referrer_name': referrer.get('name', 'User'),
                        'initiated_at': datetime.utcnow()
                    }
                    
                    # Log referral initiation
                    await BotLogger.log_referral_initiated(
                        client, user.id, user.first_name,
                        referrer['id'], referrer.get('name', 'User'), referred_by_code
                    )
            
            buttons = await get_all_force_sub_buttons(client, not_joined)
            total_channels = len(Config.FORCE_SUB_CHANNELS)
            joined_count = total_channels - len(not_joined)
            
            # Show referral info if pending
            referral_info = ""
            if user.id in temp.PENDING_REFERRALS:
                referral_info = f"\n🎁 ʀᴇғᴇʀʀᴀʟ ʙᴏɴᴜs ᴘᴇɴᴅɪɴɢ! ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ᴛᴏ ᴄʟᴀɪᴍ.\n"
            
            await client.send_message(
                chat_id=message.chat.id,
                text=(
                    f"👋 ʜᴇʟʟᴏ <b>{user.first_name}</b>!\n\n"
                    f"⚠️ <b>ғᴏʀᴄᴇ sᴜʙsᴄʀɪʙᴇ ʀᴇǫᴜɪʀᴇᴅ</b>\n\n"
                    f"ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ, ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ <b>ᴀʟʟ</b> ᴛʜᴇ ᴄʜᴀɴɴᴇʟs ʙᴇʟᴏᴡ:\n\n"
                    f"📊 ᴘʀᴏɢʀᴇss: <b>{joined_count}/{total_channels}</b> ᴄʜᴀɴɴᴇʟs ᴊᴏɪɴᴇᴅ\n"
                    f"📢 ʀᴇᴍᴀɪɴɪɴɢ: <b>{len(not_joined)}</b> ᴄʜᴀɴɴᴇʟs\n\n"
                    f"✅ = ᴊᴏɪɴᴇᴅ | 📢 = ɴᴏᴛ ᴊᴏɪɴᴇᴅ{referral_info}\n\n"
                    f"ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ᴀɴᴅ ᴄʟɪᴄᴋ <b>\"ᴄʜᴇᴄᴋ ᴀɢᴀɪɴ\"</b> ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ."
                ),
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return
    
        is_new_user = not await db.is_user_exist(user.id)
        
        if is_new_user:
            await db.add_user(user.id, user.first_name, referred_by_code)
            await BotLogger.log_new_user(client, user.id, user.first_name)
            
            # Complete referral if user came via referral link
            if referred_by_code:
                referrer = await db.get_user_by_referral_code(referred_by_code)
                if referrer:
                    await db.add_ftm_bucks(referrer['id'], 100)
                    await db.record_referral(referrer['id'], user.id)
                    
                    trial_expires = datetime.utcnow() + timedelta(days=1)
                    await db.set_subscription(user.id, 'plus', expires_at=trial_expires, assigned_by='referral_trial')
                    
                    # Log referral completion
                    await BotLogger.log_referral_completed(
                        client, user.id, user.first_name,
                        referrer['id'], referrer.get('name', 'User'), referred_by_code,
                        100, 'Plus'
                    )
                    
                    await client.send_message(
                        user.id,
                        f"🎉 <b>ᴡᴇʟᴄᴏᴍᴇ ʙᴏɴᴜs!</b>\n\n"
                        f"ʏᴏᴜ ᴊᴏɪɴᴇᴅ ᴠɪᴀ ʀᴇғᴇʀʀᴀʟ ʟɪɴᴋ!\n"
                        f"✨ ʏᴏᴜ'ᴠᴇ ʀᴇᴄᴇɪᴠᴇᴅ <b>1-ᴅᴀʏ ᴘʟᴜs ᴘʟᴀɴ</b> ᴛʀɪᴀʟ!\n\n"
                        f"⏰ ᴇxᴘɪʀᴇs: {trial_expires.strftime('%Y-%m-%d %H:%M UTC')}"
                    )
                    
                    try:
                        referrer_name = referrer.get('name', 'User')
                        await client.send_message(
                            referrer['id'],
                            f"🎁 <b>ʀᴇғᴇʀʀᴀʟ ʀᴇᴡᴀʀᴅ!</b>\n\n"
                            f"ᴜsᴇʀ <b>{user.first_name}</b> ᴊᴏɪɴᴇᴅ ᴜsɪɴɢ ʏᴏᴜʀ ʀᴇғᴇʀʀᴀʟ ʟɪɴᴋ!\n"
                            f"💰 +100 ғᴛᴍʙᴜᴄᴋs ᴀᴅᴅᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ!\n\n"
                            f"ᴛᴏᴛᴀʟ ʀᴇғᴇʀʀᴀʟs: {referrer.get('referral', {}).get('total_referrals', 0) + 1}"
                        )
                    except Exception as e:
                        logging.error(f"Error notifying referrer: {e}")
        else:
            await db.ensure_referral_data(user.id)
        
        if user.id in Config.BOT_OWNER_ID:
            await db.set_lifetime_plan(user.id, plan='infinity', assigned_by='system')
        
        reply_markup = InlineKeyboardMarkup(main_buttons)
        await client.send_message(
            chat_id=message.chat.id,
            reply_markup=InlineKeyboardMarkup(main_buttons),
            text=Translation.START_TXT.format(message.from_user.first_name))
    
    except FloodWait as e:
        logging.error(f"FloodWait error in start command for user {user.id}: {e.value if hasattr(e, 'value') else getattr(e, 'x', 10)}s")
        await asyncio.sleep(e.value if hasattr(e, 'value') else getattr(e, 'x', 10))
        # Retry after waiting
        await message.reply("⏳ ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ɪɴ ᴀ ғᴇᴡ sᴇᴄᴏɴᴅs...")
    except Exception as e:
        logging.error(f"Error in start command for user {user.id}: {e}")
        logging.error(traceback.format_exc())
        await message.reply("❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ /start ᴀɢᴀɪɴ.")


@Client.on_callback_query(filters.regex(r'^check_force_sub'))
async def check_force_sub_callback(client, query):
    """Handle the 'Check Again' button for force subscribe"""
    user = query.from_user
    from datetime import datetime, timedelta
    from plugins.logger import BotLogger
    
    is_subscribed, not_joined = await check_force_sub(client, user.id)
    
    if is_subscribed:
        # User has joined all channels, show the main menu
        await query.message.edit_text(
            text=Translation.START_TXT.format(user.first_name),
            reply_markup=InlineKeyboardMarkup(main_buttons)
        )
        
        # Process user registration if needed
        is_new_user = not await db.is_user_exist(user.id)
        
        # Check for pending referral
        pending_referral = temp.PENDING_REFERRALS.pop(user.id, None)
        
        if is_new_user:
            # Add user with referral code if pending
            referral_code = pending_referral['referral_code'] if pending_referral else None
            await db.add_user(user.id, user.first_name, referral_code)
            await BotLogger.log_new_user(client, user.id, user.first_name)
            
            # Complete pending referral
            if pending_referral:
                referrer = await db.get_user_by_referral_code(pending_referral['referral_code'])
                if referrer:
                    await db.add_ftm_bucks(referrer['id'], 100)
                    await db.record_referral(referrer['id'], user.id)
                    
                    trial_expires = datetime.utcnow() + timedelta(days=1)
                    await db.set_subscription(user.id, 'plus', expires_at=trial_expires, assigned_by='referral_trial')
                    
                    # Log referral completion
                    await BotLogger.log_referral_completed(
                        client, user.id, user.first_name,
                        referrer['id'], referrer.get('name', 'User'), 
                        pending_referral['referral_code'], 100, 'Plus'
                    )
                    
                    # Notify user about referral bonus
                    await client.send_message(
                        user.id,
                        f"🎉 <b>ᴡᴇʟᴄᴏᴍᴇ ʙᴏɴᴜs!</b>\n\n"
                        f"ʏᴏᴜ ᴊᴏɪɴᴇᴅ ᴠɪᴀ ʀᴇғᴇʀʀᴀʟ ʟɪɴᴋ!\n"
                        f"✨ ʏᴏᴜ'ᴠᴇ ʀᴇᴄᴇɪᴠᴇᴅ <b>1-ᴅᴀʏ ᴘʟᴜs ᴘʟᴀɴ</b> ᴛʀɪᴀʟ!\n\n"
                        f"⏰ ᴇxᴘɪʀᴇs: {trial_expires.strftime('%Y-%m-%d %H:%M UTC')}"
                    )
                    
                    # Notify referrer
                    try:
                        await client.send_message(
                            referrer['id'],
                            f"🎁 <b>ʀᴇғᴇʀʀᴀʟ ʀᴇᴡᴀʀᴅ!</b>\n\n"
                            f"ᴜsᴇʀ <b>{user.first_name}</b> ᴊᴏɪɴᴇᴅ ᴜsɪɴɢ ʏᴏᴜʀ ʀᴇғᴇʀʀᴀʟ ʟɪɴᴋ!\n"
                            f"💰 +100 ғᴛᴍʙᴜᴄᴋs ᴀᴅᴅᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ!\n\n"
                            f"ᴛᴏᴛᴀʟ ʀᴇғᴇʀʀᴀʟs: {referrer.get('referral', {}).get('total_referrals', 0) + 1}"
                        )
                    except Exception as e:
                        logging.error(f"Error notifying referrer: {e}")
        if user.id in Config.BOT_OWNER_ID:
            await db.set_lifetime_plan(user.id, plan='infinity', assigned_by='system')
    else:
        # User still hasn't joined all channels
        buttons = await get_all_force_sub_buttons(client, not_joined)
        total_channels = len(Config.FORCE_SUB_CHANNELS)
        joined_count = total_channels - len(not_joined)
        
        # Show referral info if pending
        referral_info = ""
        if user.id in temp.PENDING_REFERRALS:
            referral_info = f"\n🎁 ʀᴇғᴇʀʀᴀʟ ʙᴏɴᴜs ᴘᴇɴᴅɪɴɢ! ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ᴛᴏ ᴄʟᴀɪᴍ.\n"
        
        await query.message.edit_text(
            text=(
                f"👋 ʜᴇʟʟᴏ <b>{user.first_name}</b>!\n\n"
                f"⚠️ <b>ғᴏʀᴄᴇ sᴜʙsᴄʀɪʙᴇ ʀᴇǫᴜɪʀᴇᴅ</b>\n\n"
                f"ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ, ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ <b>ᴀʟʟ</b> ᴛʜᴇ ᴄʜᴀɴɴᴇʟs ʙᴇʟᴏᴡ:\n\n"
                f"📊 ᴘʀᴏɢʀᴇss: <b>{joined_count}/{total_channels}</b> ᴄʜᴀɴɴᴇʟs ᴊᴏɪɴᴇᴅ\n"
                f"📢 ʀᴇᴍᴀɪɴɪɴɢ: <b>{len(not_joined)}</b> ᴄʜᴀɴɴᴇʟs\n\n"
                f"✅ = ᴊᴏɪɴᴇᴅ | 📢 = ɴᴏᴛ ᴊᴏɪɴᴇᴅ{referral_info}\n\n"
                f"ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ᴀɴᴅ ᴄʟɪᴄᴋ <b>\"ᴄʜᴇᴄᴋ ᴀɢᴀɪɴ\"</b> ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ."
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await query.answer("❌ ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ʏᴇᴛ!", show_alert=True)

#==================Restart Function==================#

from plugins.utils import to_small_caps as cmd_to_small_caps

@Client.on_message(filters.private & filters.command(['restart']))
async def restart(client, message):
    if message.from_user.id not in Config.BOT_OWNER_ID:
        return await message.reply_text(
            f"🚫 <b>{cmd_to_small_caps('this command is not for you')}</b> 🚫\n\n"
            f"⚠️ {cmd_to_small_caps('only bot owner can use this command')}"
        )
    msg = await message.reply_text(
        text="<i>Trying to restart.....</i>"
    )
    await db.add_frwd(message.from_user.id)
    await asyncio.sleep(2)
    await msg.edit("<i>Bot is restarting... ♻️</i>")
    os.execl(sys.executable, sys.executable, *sys.argv)

#==================Cancel Function==================#

@Client.on_message(filters.private & filters.command(['cancel']))
async def cancel_task(client, message):
    """Cancel any ongoing forwarding or unequify task"""
    user_id = message.from_user.id
    
    # Check if user has active task (handle both boolean and string values)
    lock_value = temp.lock.get(user_id)
    has_lock = lock_value and (lock_value == True or str(lock_value) == "True")
    
    # Also check database for active tasks
    active_tasks = await db.get_active_tasks(user_id)
    has_db_task = active_tasks.get('forwarding', 0) > 0
    
    has_active_task = has_lock or has_db_task
    
    if has_active_task:
        temp.CANCEL[user_id] = True
        temp.lock.pop(user_id, None)
        
        if temp.forwardings > 0:
            temp.forwardings -= 1
        
        # Decrement database task counter
        try:
            await db.decrement_task(user_id, 'forwarding')
        except Exception as e:
            logging.error(f"Error decrementing task counter: {e}")
        await message.reply("⚠️ ᴛᴀsᴋ ᴄᴀɴᴄᴇʟʟᴀᴛɪᴏɴ ʀᴇǫᴜᴇsᴛᴇᴅ!\n\n"
                          "ʏᴏᴜʀ ᴏɴɢᴏɪɴɢ ᴛᴀsᴋ ᴡɪʟʟ sᴛᴏᴘ sʜᴏʀᴛʟʏ...")
        
        try:
            from plugins.logger import BotLogger
            user_name = message.from_user.first_name or "User"
            await BotLogger.log_task_cancelled(client, user_id, user_name)
        except Exception as e:
            logging.error(f"Error logging task cancellation: {e}")
    else:
        await message.reply("ℹ️ ɴᴏ ᴀᴄᴛɪᴠᴇ ᴛᴀsᴋ ғᴏᴜɴᴅ!\n\n"
                          "ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ʀᴜɴɴɪɴɢ ᴛᴀsᴋs ᴛᴏ ᴄᴀɴᴄᴇʟ.")

#==================Clear Task Function==================#

@Client.on_message(filters.private & filters.command(['cleartask', 'resettask']))
async def clear_task(client, message):
    """Reset stuck task counter - use when getting 'task limit reached' error with no active tasks"""
    user_id = message.from_user.id
    
    # Reset the task counter in database
    await db.reset_task_counter(user_id, 'forwarding')
    
    # Also clear local locks
    temp.lock.pop(user_id, None)
    temp.CANCEL.pop(user_id, None)
    
    await message.reply("✅ <b>ᴛᴀsᴋ ᴄᴏᴜɴᴛᴇʀ ʀᴇsᴇᴛ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
                       "ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ sᴛᴀʀᴛ ᴀ ɴᴇᴡ ғᴏʀᴡᴀʀᴅɪɴɢ ᴛᴀsᴋ.")

#==================Reset Function==================#

@Client.on_message(filters.private & filters.command(['reset']))
async def reset_config(client, message):
    """Reset all user configurations with confirmation"""
    user_id = message.from_user.id
    
    confirm_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ ʏᴇs, ʀᴇsᴇᴛ", callback_data=f"confirm_reset#{user_id}"),
            InlineKeyboardButton("❌ ɴᴏ, ᴄᴀɴᴄᴇʟ", callback_data="cancel_reset")
        ]
    ])
    
    await message.reply(
        "⚠️ <b>ʀᴇsᴇᴛ ᴄᴏɴғɪʀᴍᴀᴛɪᴏɴ</b>\n\n"
        "ᴛʜɪs ᴡɪʟʟ ᴅᴇʟᴇᴛᴇ:\n"
        "• ᴀʟʟ ʏᴏᴜʀ ᴀᴅᴅᴇᴅ ʙᴏᴛs/ᴜsᴇʀʙᴏᴛs\n"
        "• ᴀʟʟ sᴀᴠᴇᴅ ᴄʜᴀɴɴᴇʟs\n"
        "• ᴀʟʟ ғᴛᴍ sᴇᴛᴛɪɴɢs (ʀᴇᴘʟᴀᴄᴇʀ, ʀᴇᴍᴏᴠᴇʀ, ᴡᴀᴛᴇʀᴍᴀʀᴋ, ᴇᴛᴄ.)\n"
        "• ᴀʟʟ ᴏᴛʜᴇʀ ᴄᴏɴғɪɢᴜʀᴀᴛɪᴏɴs\n\n"
        "ᴀʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ?",
        reply_markup=confirm_keyboard
    )

@Client.on_callback_query(filters.regex(r'^confirm_reset#'))
async def confirm_reset(client, query):
    """Execute the reset after confirmation"""
    user_id = int(query.data.split('#')[1])
    
    if query.from_user.id != user_id:
        return await query.answer("ᴛʜɪs ɪs ɴᴏᴛ ʏᴏᴜʀ ʀᴇsᴇᴛ ʀᴇǫᴜᴇsᴛ!", show_alert=True)
    
    status_msg = await query.message.edit("⚙️ ʀᴇsᴇᴛᴛɪɴɢ ʏᴏᴜʀ ᴄᴏɴғɪɢᴜʀᴀᴛɪᴏɴ...\n\nᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...")
    
    try:
        removed_bots = 0
        removed_channels = 0
        
        if await db.is_bot_exist(user_id):
            removed_bots = await db.bot.count_documents({'user_id': int(user_id)})
            await db.remove_bot(user_id)
        
        channels = await db.get_user_channels(user_id)
        for channel in channels:
            await db.remove_channel(user_id, channel['chat_id'])
            removed_channels += 1
        
        default = await db.get_configs("01")
        await db.update_configs(user_id, default)
        
        temp.lock.pop(user_id, None)
        temp.CANCEL.pop(user_id, None)
        
        try:
            from plugins.logger import BotLogger
            user_name = query.from_user.first_name or "User"
            await BotLogger.log_config_reset(client, user_id, user_name, removed_bots, removed_channels)
        except Exception as e:
            logging.error(f"Error logging config reset: {e}")
        await status_msg.edit(
            f"✅ <b>ʀᴇsᴇᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
            f"• ʙᴏᴛs ʀᴇᴍᴏᴠᴇᴅ: <code>{removed_bots}</code>\n"
            f"• ᴄʜᴀɴɴᴇʟs ʀᴇᴍᴏᴠᴇᴅ: <code>{removed_channels}</code>\n"
            f"• ᴀʟʟ sᴇᴛᴛɪɴɢs ʀᴇsᴇᴛ ᴛᴏ ᴅᴇғᴀᴜʟᴛ ✔️"
        )
        
    except Exception as e:
        await status_msg.edit(f"❌ <b>ᴇʀʀᴏʀ ᴅᴜʀɪɴɢ ʀᴇsᴇᴛ:</b>\n\n<code>{str(e)}</code>")

@Client.on_callback_query(filters.regex(r'^cancel_reset'))
async def cancel_reset(client, query):
    """Cancel the reset operation"""
    await query.message.edit("❌ ʀᴇsᴇᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ!\n\nʏᴏᴜʀ ᴄᴏɴғɪɢᴜʀᴀᴛɪᴏɴs ᴀʀᴇ sᴀғᴇ.")
    
#==================Callback Functions==================#

@Client.on_callback_query(filters.regex(r'^help'))
async def helpcb(bot, query):
    await query.message.edit_text(
        text=Translation.HELP_TXT,
        reply_markup=InlineKeyboardMarkup(
            [[
            InlineKeyboardButton('ʜᴏᴡ ᴛᴏ ᴜsᴇ ᴍᴇ ❓', callback_data='how_to_use')
            ],[
            InlineKeyboardButton('⚙️ sᴇᴛᴛɪɴɢs ', callback_data='settings#main'),
            InlineKeyboardButton('📜 sᴛᴀᴛᴜs ', callback_data='status')
            ],[
            InlineKeyboardButton('↩ ʙᴀᴄᴋ', callback_data='back')
            ]]
        ))

@Client.on_callback_query(filters.regex(r'^how_to_use'))
async def how_to_use(bot, query):
    await query.message.edit_text(
        text=Translation.HOW_USE_TXT,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('↩ Back', callback_data='help')]]),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex(r'^back'))
async def back(bot, query):
    reply_markup = InlineKeyboardMarkup(main_buttons)
    await query.message.edit_text(
       reply_markup=reply_markup,
       text=Translation.START_TXT.format(
                query.from_user.first_name))

@Client.on_callback_query(filters.regex(r'^about'))
async def about(bot, query):
    from .utils import to_small_caps
    
    # Get bot username for link
    bot_username = bot.username if bot.username else "bot"
    
    # Format ABOUT_TXT with dynamic values
    about_text = Translation.ABOUT_TXT.format(
        bot_name=bot.first_name,
        bot_username=bot_username,
        bot_id=bot.id,
        python_version=python_version(),
        pyrogram_version=pyrogram_version,
        mongodb_version=await mongodb_version(),
        support_group=Config.SUPPORT_GROUP,
        update_channel=Config.UPDATE_CHANNEL,
        main_channel=Config.MAIN_CHANNEL,
        owner_id=Config.BOT_OWNER_ID[0]
    )
    
    await query.message.edit_text(
        text=about_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⫷ ʙᴀᴄᴋ', callback_data='back')]]),
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.HTML,
    )

@Client.on_callback_query(filters.regex(r'^status'))
async def status(bot, query):
    users_count, bots_count = await db.total_users_bots_count()
    total_channels = await db.total_channels()
    await query.message.edit_text(
        text=Translation.STATUS_TXT.format(users_count, bots_count, temp.forwardings, total_channels, temp.BANNED_USERS ),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('↩ Back', callback_data='help')]]),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True,
    )

#==================FTM Alpha Mode Command==================#

@Client.on_message(filters.private & filters.command(['alpha']))
async def alpha_info(client, message):
    """Display FTM Alpha Mode feature information - Infinity only"""
    from .utils import to_small_caps
    from .subscription import require_ftm
    
    user_id = message.from_user.id
    
    # Check if user has Infinity plan for alpha mode
    has_permission, error_message = await require_ftm(user_id, 'alpha')
    if not has_permission:
        return await message.reply(error_message)
    
    subscription = await db.get_subscription(user_id)
    plan = subscription.get('plan', 'free')
    
    # Check if user has Infinity plan
    is_infinity = plan == 'infinity'
    config = await db.get_configs(user_id)
    alpha_enabled = config.get('ftm_alpha_mode', False)
    
    status_text = "✅ ᴇɴᴀʙʟᴇᴅ" if alpha_enabled else "❌ ᴅɪsᴀʙʟᴇᴅ"
    plan_text = "🔓 ᴜɴʟᴏᴄᴋᴇᴅ" if is_infinity else "🔒 ʟᴏᴄᴋᴇᴅ (ɪɴғɪɴɪᴛʏ ᴏɴʟʏ)"
    
    alpha_help_text = f"""<b>🧬 ғᴛᴍ ᴀʟᴘʜᴀ ᴍᴏᴅᴇ 🧬</b>

<b>📋 sᴛᴀᴛᴜs:</b> {status_text}
<b>📦 ᴘʟᴀɴ:</b> {plan_text}

<b>━━━━━━━━━━━━━━━━━━</b>

<b>✨ ᴡʜᴀᴛ ɪs ғᴛᴍ ᴀʟᴘʜᴀ ᴍᴏᴅᴇ?</b>

ғᴛᴍ ᴀʟᴘʜᴀ ᴍᴏᴅᴇ ɪs ᴀɴ ᴇxᴄʟᴜsɪᴠᴇ ғᴇᴀᴛᴜʀᴇ ғᴏʀ ɪɴғɪɴɪᴛʏ ᴜsᴇʀs ᴛʜᴀᴛ ᴘʀᴏᴠɪᴅᴇs ᴀᴜᴛᴏ-ʀᴇsᴜᴍᴇ ᴄᴀᴘᴀʙɪʟɪᴛɪᴇs ғᴏʀ ʏᴏᴜʀ ғᴏʀᴡᴀʀᴅɪɴɢ ᴘʀᴏᴄᴇssᴇs.

<b>━━━━━━━━━━━━━━━━━━</b>

<b>🔧 ғᴇᴀᴛᴜʀᴇs:</b>

<b>📤 ᴍᴀɴᴜᴀʟ ғᴏʀᴡᴀʀᴅɪɴɢ:</b>
• sᴀᴠᴇs ᴘʀᴏɢʀᴇss ᴀғᴛᴇʀ ᴇᴀᴄʜ ᴍᴇssᴀɢᴇ
• ᴀᴜᴛᴏ-ʀᴇsᴛᴀʀᴛs ғʀᴏᴍ ʟᴀsᴛ ᴍᴇssᴀɢᴇ ᴏɴ ʙᴏᴛ ʀᴇsᴛᴀʀᴛ
• ɴᴏᴛɪғɪᴇs ʏᴏᴜ ᴡʜᴇɴ ʀᴇsᴜᴍᴇᴅ

<b>💫 ɢᴀᴍᴍᴀ ᴍᴏᴅᴇ:</b>
• ᴛʀᴀᴄᴋs ʟᴀsᴛ ғᴏʀᴡᴀʀᴅᴇᴅ ᴍᴇssᴀɢᴇ ᴘᴇʀ sᴏᴜʀᴄᴇ
• ᴀᴜᴛᴏ-ᴅᴇᴛᴇᴄᴛs ᴍɪssᴇᴅ ᴍᴇssᴀɢᴇs ᴏɴ ʀᴇsᴛᴀʀᴛ
• ᴀᴜᴛᴏ-ғᴏʀᴡᴀʀᴅs ᴀʟʟ ᴍɪssᴇᴅ ᴍᴇssᴀɢᴇs
• ᴄᴏᴜɴᴛs ᴀɴᴅ ʀᴇᴘᴏʀᴛs ᴍɪssᴇᴅ ᴍᴇssᴀɢᴇs

<b>━━━━━━━━━━━━━━━━━━</b>

<b>📱 ʜᴏᴡ ᴛᴏ ᴜsᴇ:</b>

1️⃣ ɢᴏ ᴛᴏ <b>sᴇᴛᴛɪɴɢs</b> → <b>ғᴛᴍ ᴍᴀɴᴀɢᴇʀ</b>
2️⃣ ᴛᴀᴘ ᴏɴ <b>🧬 ғᴛᴍ ᴀʟᴘʜᴀ ᴍᴏᴅᴇ</b>
3️⃣ ᴛᴏɢɢʟᴇ ᴛᴏ ᴇɴᴀʙʟᴇ

<b>━━━━━━━━━━━━━━━━━━</b>

<b>⚡ ᴘᴏᴡᴇʀᴇᴅ ʙʏ <a href="https://t.me/ftmbotzx">ғᴛᴍʙᴏᴛᴢx</a></b>"""

    await message.reply(
        alpha_help_text,
        disable_web_page_preview=True
    )



# ============ Ported from ftm-forwardbot-latest (admin panel utilities) ============
# NOTE: The original admin_commands_callback also had "Add Premium / Remove Premium /
# Premium Users / Change Price" buttons wired to a separate premium_col based system.
# Since this bot (SRC merged) already manages premium via plugins/subscription.py using
# the embedded `subscription` field on the user document, those buttons were intentionally
# left out here to avoid two conflicting premium systems. Use /add_premium, /remove_premium,
# /premium_users (subscription.py) for premium management instead.

@Client.on_callback_query(filters.regex(r'^admin_commands$'))
async def admin_commands_callback(bot, query):
    user_id = query.from_user.id
    logger.info(f"Admin commands callback from user {user_id}")

    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission to access admin commands!", show_alert=True)

    try:
        admin_buttons = [[
            InlineKeyboardButton('💬 Start Chat', callback_data='admin_start_chat_info'),
            InlineKeyboardButton('📊 System Info', callback_data='admin_system')
        ],[
            InlineKeyboardButton('⚡ Speed Test', callback_data='admin_speedtest'),
            InlineKeyboardButton('🔄 Restart Bot', callback_data='admin_restart')
        ],[
            InlineKeyboardButton('🗑️ Reset All Users', callback_data='admin_resetall_info'),
            InlineKeyboardButton('🔙 Back to Help', callback_data='help')
        ]]

        await query.message.edit_text(
            text="<b>🔧 Admin Commands Panel</b>\n\n"
                 "<b>Premium Management:</b>\n"
                 "• <code>/add_premium [user_id] [plan] [days]</code>\n"
                 "• <code>/remove_premium [user_id]</code>\n"
                 "• <code>/premium_users</code> - list premium users\n\n"
                 "<b>User Management:</b>\n"
                 "• <code>/users</code> - List all registered users\n\n"
                 "<b>System Tools:</b> Monitor server performance\n"
                 "<b>User Support:</b> Direct chat with users\n"
                 "<b>Bot Control:</b> Restart and configuration\n\n"
                 "<i>These commands are only visible to admins and owners.</i>",
            reply_markup=InlineKeyboardMarkup(admin_buttons)
        )
        logger.debug(f"Admin commands panel sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error in admin commands callback for user {user_id}: {e}", exc_info=True)


@Client.on_callback_query(filters.regex(r'^admin_start_chat_info$'))
async def admin_start_chat_info_callback(bot, query):
    """Points admin to the existing admin panel / admin_reply based chat system."""
    user_id = query.from_user.id
    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission!", show_alert=True)
    await query.message.edit_text(
        text="<b>💬 User Support Chat</b>\n\n"
             "<b>Users can request a chat via 'Contact Admin' — you'll get an\n"
             "Accept/Deny prompt here in the bot. Once accepted, just reply\n"
             "normally to their forwarded messages to chat with them.</b>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton('🔙 Back to Admin', callback_data='admin_commands')
        ]])
    )


@Client.on_callback_query(filters.regex(r'^admin_system$'))
async def admin_system_callback(bot, query):
    user_id = query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission to use this command!", show_alert=True)

    status_msg = await query.message.edit_text("🔄 <b>Gathering system information...</b>")

    try:
        uname = platform.uname()
        cpu_count = psutil.cpu_count()
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq()

        memory = psutil.virtual_memory()
        memory_total = memory.total / (1024**3)
        memory_used = memory.used / (1024**3)
        memory_percent = memory.percent

        disk = psutil.disk_usage('/')
        disk_total = disk.total / (1024**3)
        disk_used = disk.used / (1024**3)
        disk_percent = (disk.used / disk.total) * 100

        net_io = psutil.net_io_counters()
        bytes_sent = net_io.bytes_sent / (1024**2)
        bytes_recv = net_io.bytes_recv / (1024**2)

        boot_time = psutil.boot_time()
        process_count = len(psutil.pids())
        python_ver = python_version()

        import datetime
        uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(boot_time)
        uptime_str = str(uptime).split('.')[0]

        try:
            load_avg = os.getloadavg()
            load_str = f"{load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}"
        except Exception:
            load_str = "Not Available"

        cpu_freq_current = f"{cpu_freq.current:.0f} MHz" if cpu_freq else "N/A"
        cpu_freq_max = f"{cpu_freq.max:.0f} MHz" if cpu_freq else "N/A"

        system_text = f"""<b>🖥️ Bot Server System Information</b>

<b>💻 Server System Details:</b>
├ <b>OS:</b> <code>{uname.system} {uname.release}</code>
├ <b>Architecture:</b> <code>{uname.machine}</code>
├ <b>Hostname:</b> <code>{uname.node}</code>

<b>🔧 Server Hardware Info:</b>
├ <b>CPU Cores:</b> <code>{cpu_count} cores</code>
├ <b>CPU Usage:</b> <code>{cpu_percent}%</code>
├ <b>CPU Frequency:</b> <code>{cpu_freq_current}</code> (Max: <code>{cpu_freq_max}</code>)
├ <b>Load Average:</b> <code>{load_str}</code>

<b>💾 Server Memory Info:</b>
├ <b>Total RAM:</b> <code>{memory_total:.2f} GB</code>
├ <b>Used RAM:</b> <code>{memory_used:.2f} GB ({memory_percent}%)</code>
├ <b>Available RAM:</b> <code>{(memory_total - memory_used):.2f} GB</code>

<b>💿 Server Storage Info:</b>
├ <b>Total Disk:</b> <code>{disk_total:.2f} GB</code>
├ <b>Used Disk:</b> <code>{disk_used:.2f} GB ({disk_percent:.1f}%)</code>
├ <b>Free Disk:</b> <code>{(disk_total - disk_used):.2f} GB</code>

<b>🌐 Server Network Usage:</b>
├ <b>Data Sent:</b> <code>{bytes_sent:.2f} MB</code>
├ <b>Data Received:</b> <code>{bytes_recv:.2f} MB</code>

<b>⚡ Bot Runtime Info:</b>
├ <b>Python Version:</b> <code>v{python_ver}</code>
├ <b>Pyrogram Version:</b> <code>v{pyrogram_version}</code>
├ <b>Active Processes:</b> <code>{process_count}</code>
├ <b>Server Uptime:</b> <code>{uptime_str}</code>
└ <b>Bot Status:</b> <code>Running ✅</code>"""

        await status_msg.edit_text(
            text=system_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('🔙 Back to Admin', callback_data='admin_commands')
            ]])
        )
        logger.info(f"System info sent to admin {user_id}")

    except Exception as e:
        error_msg = f"❌ <b>System Info Failed</b>\n\n<b>Error:</b> <code>{str(e)}</code>"
        await status_msg.edit_text(
            text=error_msg,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('🔙 Back to Admin', callback_data='admin_commands')
            ]])
        )
        logger.error(f"System info error for admin {user_id}: {e}", exc_info=True)


@Client.on_callback_query(filters.regex(r'^admin_speedtest$'))
async def admin_speedtest_callback(bot, query):
    user_id = query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission to use this command!", show_alert=True)

    status_msg = await query.message.edit_text("🔄 <b>Running Network Speed Test...</b>\n⏳ Please wait, this may take a moment.")

    try:
        st = speedtest.Speedtest()
        await status_msg.edit_text("🔄 <b>Finding best server...</b>\n⏳ Please wait.")
        st.get_best_server()

        await status_msg.edit_text("🔄 <b>Testing download speed...</b>\n⏳ Please wait.")
        download_speed = st.download()

        await status_msg.edit_text("🔄 <b>Testing upload speed...</b>\n⏳ Please wait.")
        upload_speed = st.upload()

        ping = st.results.ping
        server = st.get_best_server()

        download_mbps = download_speed / 1024 / 1024
        upload_mbps = upload_speed / 1024 / 1024

        speed_text = f"""<b>🌐 Bot Server Network Speed Test</b>

<b>📡 Server Connection Info:</b>
├ <b>ISP:</b> <code>{server.get('sponsor', 'Unknown')}</code>
├ <b>Server Location:</b> <code>{server.get('name', 'Unknown')}, {server.get('country', 'Unknown')}</code>
├ <b>Distance:</b> <code>{server.get('d', 0):.1f} km</code>

<b>🚀 Bot Server Speed Results:</b>
├ <b>📥 Download:</b> <code>{download_mbps:.2f} Mbps</code>
├ <b>📤 Upload:</b> <code>{upload_mbps:.2f} Mbps</code>
├ <b>📶 Ping:</b> <code>{ping:.1f} ms</code>

<b>📊 Test Information:</b>
└ <b>Note:</b> <code>Shows bot server network, not your location</code>"""

        await status_msg.edit_text(
            text=speed_text,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('🔙 Back to Admin', callback_data='admin_commands')
            ]])
        )
        logger.info(f"Speedtest completed for admin {user_id}")

    except Exception as e:
        error_msg = f"❌ <b>Speed Test Failed</b>\n\n<b>Error:</b> <code>{str(e)}</code>"
        await status_msg.edit_text(
            text=error_msg,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('🔙 Back to Admin', callback_data='admin_commands')
            ]])
        )
        logger.error(f"Speedtest error for admin {user_id}: {e}", exc_info=True)


@Client.on_callback_query(filters.regex(r'^admin_restart$'))
async def admin_restart_callback(bot, query):
    user_id = query.from_user.id

    if user_id not in Config.OWNER_ID:
        return await query.answer("❌ Only owners can restart the bot!", show_alert=True)

    try:
        await query.message.edit_text(
            text="<b>🔄 Bot Restart</b>\n\n"
                 "<b>⚠️ Are you sure you want to restart the bot?</b>\n\n"
                 "<i>This will stop all ongoing processes!</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('✅ Yes, Restart', callback_data='confirm_restart'),
                InlineKeyboardButton('❌ Cancel', callback_data='admin_commands')
            ]])
        )
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)


@Client.on_callback_query(filters.regex(r'^confirm_restart$'))
async def confirm_restart_callback(bot, query):
    user_id = query.from_user.id

    if user_id not in Config.OWNER_ID:
        return await query.answer("❌ Only owners can restart the bot!", show_alert=True)

    await query.message.edit_text("🔄 <b>Restarting bot...</b>\n\n<i>Please wait...</i>")
    await restart(bot, query.message)


@Client.on_callback_query(filters.regex(r'^admin_resetall_info$'))
async def admin_resetall_info_callback(bot, query):
    user_id = query.from_user.id

    if user_id not in Config.OWNER_ID:
        return await query.answer("❌ Only owners can reset all users!", show_alert=True)

    try:
        await query.message.edit_text(
            text="<b>🗑️ Reset Commands Information</b>\n\n"
                 "<b>Available Reset Commands:</b>\n\n"
                 "<b>1. Individual User Reset:</b>\n"
                 "• Command: <code>/reset</code>\n"
                 "• Resets your own data only\n\n"
                 "<b>2. Reset All Users (Owner Only):</b>\n"
                 "• Command: <code>/resetall</code>\n"
                 "• Resets ALL users' data\n\n"
                 "<b>❗ These actions cannot be undone!</b>\n\n"
                 "<i>Use these commands in chat for full functionality</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('🔙 Back to Admin', callback_data='admin_commands')
            ]])
        )
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)


@Client.on_callback_query(filters.regex(r'^contact_admin$'))
async def contact_admin_callback(bot, query):
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    user_username = f"@{query.from_user.username}" if query.from_user.username else ""
    logger.info(f"Contact admin callback from user {user_id} ({user_name})")

    try:
        existing_request = await db.get_pending_chat_request(user_id)
        if existing_request:
            await query.answer(
                "⏳ You already have a pending chat request.\n"
                "Please wait for admin approval.",
                show_alert=True
            )
            return

        active_chat = await db.get_active_chat_for_user(user_id)
        if active_chat:
            await query.answer(
                "💬 You already have an active chat session with admin!\n"
                "Just send your message and it will be forwarded.",
                show_alert=True
            )
            return

        request_id = await db.create_chat_request(user_id)

        await query.message.edit_text(
            text="<b>💬 Contact Request Submitted!</b>\n\n"
                 "<b>Your request to contact admin has been submitted.</b>\n"
                 "<b>⏳ Please wait for admin approval.</b>\n\n"
                 f"<b>Request ID:</b> <code>{request_id}</code>\n"
                 "<b>💬 You will be notified once an admin accepts your request.</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('🔙 Back to Menu', callback_data='back')]
            ])
        )

        from plugins.timezone import get_current_ist_timestamp
        sudo_users = Config.OWNER_ID + Config.ADMIN_ID

        for sudo_id in sudo_users:
            try:
                buttons = [
                    [
                        InlineKeyboardButton("✅ Accept Chat", callback_data=f"accept_chat_{request_id}"),
                        InlineKeyboardButton("❌ Deny", callback_data=f"deny_chat_{request_id}")
                    ]
                ]

                await bot.send_message(
                    sudo_id,
                    f"<b>💬 New Contact Request</b>\n\n"
                    f"<b>User:</b> {user_name} {user_username}\n"
                    f"<b>User ID:</b> <code>{user_id}</code>\n"
                    f"<b>Request ID:</b> <code>{request_id}</code>\n"
                    f"<b>Time:</b> {get_current_ist_timestamp()}\n\n"
                    f"<b>Choose an action:</b>",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except Exception as send_err:
                logger.error(f"Failed to send contact request to admin {sudo_id}: {send_err}")

        logger.info(f"Contact request created: {request_id} for user {user_id}")

    except Exception as e:
        logger.error(f"Error in contact admin callback for user {user_id}: {e}", exc_info=True)
        await query.answer("❌ An error occurred. Please try again.", show_alert=True)


@Client.on_callback_query(filters.regex(r'^premium_info$'))
async def premium_info_callback(bot, query):
    user_id = query.from_user.id
    logger.info(f"Premium info callback from user {user_id}")

    try:
        await query.message.edit_text(
            text=Translation.PLAN_INFO_MSG,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('📊 Check My Plan', callback_data='my_plan')],
                [InlineKeyboardButton('💬 Contact Admin', callback_data='contact_admin')],
                [InlineKeyboardButton('🔙 Back to Menu', callback_data='back')]
            ])
        )
    except Exception as e:
        logger.error(f"Error in premium info callback for user {user_id}: {e}", exc_info=True)
# ============ end ported block ============
