
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from config import Config, temp
from database import db
from .utils import to_small_caps
from datetime import datetime
import logging

# Store pending verifications temporarily
PENDING_VERIFICATIONS = {}

@Client.on_message(filters.private & filters.command(['verify']))
async def verify_payment(client: Client, message: Message):
    """Handle payment verification requests"""
    user_id = message.from_user.id
    
    # Debug logging
    logging.info(f"Verify command received from {user_id}")
    logging.info(f"Has reply_to_message: {message.reply_to_message is not None}")
    if message.reply_to_message:
        logging.info(f"Reply has photo: {message.reply_to_message.photo is not None}")
        logging.info(f"Reply has document: {message.reply_to_message.document is not None}")
        logging.info(f"Reply message type: {message.reply_to_message.media}")
    
    # Check if message is a reply to a photo or an image document
    has_photo = message.reply_to_message and message.reply_to_message.photo
    has_image_document = (
        message.reply_to_message and 
        message.reply_to_message.document and 
        message.reply_to_message.document.mime_type and
        message.reply_to_message.document.mime_type.startswith('image/')
    )
    
    if not message.reply_to_message or (not has_photo and not has_image_document):
        return await message.reply(
            f"<b>❌ {to_small_caps('invalid format')} ❌</b>\n\n"
            f"<b>{to_small_caps('usage')}:</b>\n"
            f"1️⃣ {to_small_caps('send payment screenshot')}\n"
            f"2️⃣ {to_small_caps('reply to that photo with')}:\n"
            f"   <code>/verify plan_name duration</code>\n\n"
            f"<b>{to_small_caps('example')}:</b>\n"
            f"<code>/verify pro 30d</code>\n"
            f"<code>/verify infinity 1M</code>\n\n"
            f"<b>{to_small_caps('available plans')}:</b> <code>plus, pro, infinity</code>\n"
            f"<b>{to_small_caps('duration formats')}:</b> <code>7d, 1M, 3M, 6M, 1y, infinity</code>"
        )
    
    args = message.text.split()
    logging.info(f"Command args: {args}, length: {len(args)}")
    
    if len(args) < 3:
        await message.reply(
            f"<b>❌ {to_small_caps('invalid format')} ❌</b>\n\n"
            f"<b>{to_small_caps('usage')}:</b> <code>/verify plan_name duration</code>\n\n"
            f"<b>{to_small_caps('example')}:</b>\n"
            f"<code>/verify pro 30d</code>\n"
            f"<code>/verify infinity 1M</code>"
        )
        return
    
    plan = args[1].lower()
    duration = args[2].lower()
    
    # Validate plan
    logging.info(f"Plan: {plan}, Duration: {duration}")
    if plan not in ['plus', 'pro', 'infinity']:
        await message.reply(
            f"<b>❌ {to_small_caps('invalid plan')} ❌</b>\n\n"
            f"<b>{to_small_caps('available plans')}:</b> <code>plus, pro, infinity</code>"
        )
        return
    
    # Validate duration format - allow plain digits (default to days), 'd', 'M', 'y' suffixes
    import re
    # Check if duration is valid: plain digits OR digits with suffix
    if duration != 'infinity' and not re.match(r'^\d+[dMy]?$', duration):
        await message.reply(
            f"<b>❌ {to_small_caps('invalid duration format')} ❌</b>\n\n"
            f"<b>{to_small_caps('valid formats')}:</b>\n"
            f"• <code>30</code> = 30 {to_small_caps('days')} ({to_small_caps('default')})\n"
            f"• <code>7d</code> = 7 {to_small_caps('days')}\n"
            f"• <code>1M</code> = 1 {to_small_caps('month')}\n"
            f"• <code>3M</code> = 3 {to_small_caps('months')}\n"
            f"• <code>1y</code> = 1 {to_small_caps('year')}\n"
            f"• <code>3y</code> = 3 {to_small_caps('years')}\n"
            f"• <code>infinity</code> = {to_small_caps('lifetime')}"
        )
        return
    
    # Normalize duration - if only digits, default to days
    if duration != 'infinity' and re.match(r'^\d+$', duration):
        duration = f"{duration}d"
    
    try:
        # Get photo from either photo or document
        if message.reply_to_message.photo:
            photo = message.reply_to_message.photo
        else:
            # It's an image document
            photo = message.reply_to_message.document
        user_name = message.from_user.first_name
        username = message.from_user.username
        
        logging.info(f"Processing verification - User: {user_name}, Plan: {plan}, Duration: {duration}")
        
        # Generate unique verification ID
        verification_id = f"{user_id}_{int(datetime.utcnow().timestamp())}"
        
        # Store verification data
        PENDING_VERIFICATIONS[verification_id] = {
            'user_id': user_id,
            'user_name': user_name,
            'username': username,
            'plan': plan,
            'duration': duration,
            'photo_file_id': photo.file_id,
            'timestamp': datetime.utcnow()
        }
        
        logging.info(f"Verification ID created: {verification_id}")
        
        # Send to all admins
        plan_info = Config.SUBSCRIPTION_PLANS.get(plan)
        logging.info(f"Plan info retrieved: {plan_info['name']}")
    except Exception as e:
        logging.error(f"Error in initial setup: {e}")
        return await message.reply(f"<b>❌ {to_small_caps('error')}:</b> {str(e)}")
    
    try:
        admin_message = (
            f"#Payment_Verification 💳\n\n"
            f"<b>👤 {to_small_caps('user details')}:</b>\n"
            f"• {to_small_caps('name')}: {user_name}\n"
            f"• {to_small_caps('username')}: @{username or 'None'}\n"
            f"• {to_small_caps('user id')}: <code>{user_id}</code>\n\n"
            f"<b>💎 {to_small_caps('requested plan')}:</b>\n"
            f"• {to_small_caps('plan')}: {plan_info['emoji']} {plan_info['name']}\n"
            f"• {to_small_caps('duration')}: {duration}\n"
            f"• {to_small_caps('price')}: ₹{plan_info['price']}\n\n"
            f"<b>📅 {to_small_caps('submitted at')}:</b> {datetime.utcnow().strftime('%d-%m-%Y %I:%M:%S %p')} UTC"
        )
        
        logging.info("Admin message created successfully")
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"✅ {to_small_caps('approve')}", callback_data=f"verify_approve#{verification_id}"),
                InlineKeyboardButton(f"❌ {to_small_caps('reject')}", callback_data=f"verify_reject#{verification_id}")
            ]
        ])
        
        logging.info("Buttons created successfully")
        
        # Send to all admins
        admin_list = Config.BOT_OWNER_ID if isinstance(Config.BOT_OWNER_ID, list) else [Config.BOT_OWNER_ID]
        logging.info(f"Admin list: {admin_list}, Count: {len(admin_list)}")
        
        sent_count = 0
        for admin_id in admin_list:
            try:
                logging.info(f"Attempting to send to admin {admin_id}")
                await client.send_photo(
                    chat_id=admin_id,
                    photo=photo.file_id,
                    caption=admin_message,
                    reply_markup=buttons
                )
                sent_count += 1
                logging.info(f"✅ Verification sent successfully to admin {admin_id}")
            except Exception as e:
                logging.error(f"❌ Error sending verification to admin {admin_id}: {e}", exc_info=True)
        
        logging.info(f"Sent verification to {sent_count} admins out of {len(admin_list)}")
        
    except Exception as e:
        logging.error(f"Error in admin message creation/sending: {e}", exc_info=True)
        sent_count = 0
    
    # Always send confirmation to user
    try:
        logging.info("Preparing to send confirmation to user")
        if sent_count == 0:
            await message.reply(
                f"<b>❌ {to_small_caps('error')} ❌</b>\n\n"
                f"{to_small_caps('failed to send verification to admins.')}\n"
                f"{to_small_caps('please contact support')}: {Config.SUPPORT_GROUP}"
            )
        else:
            # Confirm to user with screenshot attached
            logging.info(f"Sending confirmation to user {user_id}")
            confirmation_msg = (
                f"<b>✅ {to_small_caps('verification submitted')} ✅</b>\n\n"
                f"<b>💎 {to_small_caps('plan')}:</b> {plan_info['emoji']} {plan_info['name']}\n"
                f"<b>⏰ {to_small_caps('duration')}:</b> {duration}\n"
                f"<b>💰 {to_small_caps('amount')}:</b> ₹{plan_info['price']}\n\n"
                f"{to_small_caps('your payment verification has been sent to admins.')}\n"
                f"{to_small_caps('you will be notified once it is reviewed.')}\n\n"
                f"⏳ {to_small_caps('please wait for approval...')}"
            )
            await client.send_photo(
                chat_id=user_id,
                photo=photo.file_id,
                caption=confirmation_msg
            )
            logging.info(f"Confirmation sent successfully to user {user_id}")
    except Exception as e:
        logging.error(f"Error sending confirmation to user {user_id}: {e}")
        # Try to send a basic error message
        try:
            await message.reply(f"❌ Error: {str(e)}")
        except Exception:
            pass


@Client.on_callback_query(filters.regex(r'^verify_approve#'))
async def approve_verification(client: Client, query):
    """Handle verification approval"""
    user_id = query.from_user.id
    
    # Check if user is admin
    if user_id not in Config.BOT_OWNER_ID:
        return await query.answer(f"❌ {to_small_caps('unauthorized')}", show_alert=True)
    
    verification_id = query.data.split('#')[1]
    
    # Get verification data
    if verification_id not in PENDING_VERIFICATIONS:
        return await query.answer(
            f"❌ {to_small_caps('verification request expired or already processed')}",
            show_alert=True
        )
    
    verification = PENDING_VERIFICATIONS.pop(verification_id)
    target_user_id = verification['user_id']
    plan = verification['plan']
    duration_str = verification['duration']
    
    try:
        # Parse duration and set subscription
        from datetime import timedelta
        
        expires_at = None
        status = 'active'
        duration_text = ""
        
        if duration_str == 'infinity' or duration_str == 'lifetime':
            status = 'lifetime'
            expires_at = None
            duration_text = f"♾️ {to_small_caps('lifetime')}"
        else:
            import re
            match = re.match(r'^(\d+)([dMy])$', duration_str)
            if not match:
                return await query.answer(f"❌ {to_small_caps('invalid duration format')}", show_alert=True)
            
            amount = int(match.group(1))
            unit = match.group(2)
            
            now = datetime.utcnow()
            
            if unit == 'd':
                expires_at = now + timedelta(days=amount)
                duration_text = f"{amount} {to_small_caps('days' if amount > 1 else 'day')}"
            elif unit == 'M':
                expires_at = now + timedelta(days=amount * 30)
                duration_text = f"{amount} {to_small_caps('months' if amount > 1 else 'month')}"
            elif unit == 'y':
                expires_at = now + timedelta(days=amount * 365)
                duration_text = f"{amount} {to_small_caps('years' if amount > 1 else 'year')}"
        
        # Update subscription in database
        subscription_data = {
            'plan': plan,
            'status': status,
            'expires_at': expires_at,
            'purchased_at': datetime.utcnow(),
            'assigned_by': user_id,
            'features': Config.SUBSCRIPTION_PLANS.get(plan)['features']
        }
        
        await db.col.update_one(
            {'id': int(target_user_id)},
            {'$set': {'subscription': subscription_data}},
            upsert=True
        )
        
        plan_info = Config.SUBSCRIPTION_PLANS[plan]
        
        # Notify user with screenshot attached
        user_message = (
            f"<b>🎉 {to_small_caps('payment verified')} 🎉</b>\n\n"
            f"{to_small_caps('congratulations! your payment has been approved.')}\n\n"
            f"<b>💎 {to_small_caps('plan')}:</b> {plan_info['emoji']} {plan_info['name']}\n"
            f"<b>⏰ {to_small_caps('duration')}:</b> {duration_text}\n"
        )
        
        if expires_at:
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            expires_ist = expires_at.replace(tzinfo=pytz.utc).astimezone(ist)
            expiry_date = expires_ist.strftime('%d-%m-%Y')
            expiry_time = expires_ist.strftime('%I:%M:%S %p')
            user_message += f"<b>📅 {to_small_caps('expires on')}:</b> {expiry_date}\n"
            user_message += f"<b>🕐 {to_small_caps('expires at')}:</b> {expiry_time}\n"
        
        user_message += f"\n{to_small_caps('use')} /myplan {to_small_caps('to view your plan details')}"
        
        # Send with screenshot attached
        await client.send_photo(
            chat_id=target_user_id,
            photo=verification['photo_file_id'],
            caption=user_message
        )
        
        # Update admin message
        await query.message.edit_caption(
            f"{query.message.caption}\n\n"
            f"<b>✅ {to_small_caps('approved by')} {query.from_user.first_name}</b>\n"
            f"📅 {to_small_caps('approved at')}: {datetime.utcnow().strftime('%d-%m-%Y %I:%M:%S %p')} UTC"
        )
        
        # Log to log channel
        from plugins.logger import BotLogger
        await BotLogger.log_premium_added(
            client, target_user_id, verification['user_name'], plan, duration_text,
            subscription_data['purchased_at'], expires_at,
            user_id, query.from_user.first_name
        )
        
        # Additional log for verification approval
        if Config.LOG_CHANNEL:
            log_message = (
                f"#Verification_Approved ✅\n\n"
                f"<b>👤 {to_small_caps('user')}:</b> {verification['user_name']} (<code>{target_user_id}</code>)\n"
                f"<b>💎 {to_small_caps('plan')}:</b> {plan_info['emoji']} {plan_info['name']}\n"
                f"<b>⏰ {to_small_caps('duration')}:</b> {duration_text}\n"
                f"<b>👨‍💼 {to_small_caps('approved by')}:</b> {query.from_user.first_name} (<code>{user_id}</code>)\n"
                f"<b>📅 {to_small_caps('approved at')}:</b> {datetime.utcnow().strftime('%d-%m-%Y %I:%M:%S %p')} UTC"
            )
            await client.send_message(Config.LOG_CHANNEL, log_message)
        
        await query.answer(f"✅ {to_small_caps('verification approved successfully')}", show_alert=True)
        
    except Exception as e:
        logging.error(f"Error approving verification: {e}")
        await query.answer(f"❌ {to_small_caps('error')}: {str(e)}", show_alert=True)


@Client.on_callback_query(filters.regex(r'^verify_reject#'))
async def reject_verification(client: Client, query):
    """Handle verification rejection"""
    user_id = query.from_user.id
    
    # Check if user is admin
    if user_id not in Config.BOT_OWNER_ID:
        return await query.answer(f"❌ {to_small_caps('unauthorized')}", show_alert=True)
    
    verification_id = query.data.split('#')[1]
    
    # Get verification data
    if verification_id not in PENDING_VERIFICATIONS:
        return await query.answer(
            f"❌ {to_small_caps('verification request expired or already processed')}",
            show_alert=True
        )
    
    verification = PENDING_VERIFICATIONS.pop(verification_id)
    target_user_id = verification['user_id']
    plan = verification['plan']
    
    plan_info = Config.SUBSCRIPTION_PLANS[plan]
    
    # Notify user with detailed rejection message
    user_message = (
        f"<b>❌ {to_small_caps('payment verification rejected')} ❌</b>\n\n"
        f"{to_small_caps('your payment verification for')} {plan_info['emoji']} <b>{plan_info['name']}</b> "
        f"{to_small_caps('plan has been rejected.')}\n\n"
        f"<b>📋 {to_small_caps('possible reasons')}:</b>\n"
        f"• {to_small_caps('the screenshot image is not clear or readable')}\n"
        f"• {to_small_caps('payment details are not fully visible')}\n"
        f"• {to_small_caps('transaction id or utr number is missing')}\n"
        f"• {to_small_caps('amount does not match the plan price')}\n"
        f"• {to_small_caps('screenshot appears to be edited or fake')}\n"
        f"• {to_small_caps('payment was already used for another verification')}\n\n"
        f"<b>💡 {to_small_caps('what to do')}:</b>\n"
        f"• {to_small_caps('take a clear full screenshot showing all payment details')}\n"
        f"• {to_small_caps('ensure transaction id, amount and date are visible')}\n"
        f"• {to_small_caps('submit again with')} <code>/verify {plan} {verification['duration']}</code>\n\n"
        f"<b>📞 {to_small_caps('need help?')}</b>\n"
        f"{to_small_caps('contact support')}: {Config.SUPPORT_GROUP}"
    )
    
    await client.send_message(target_user_id, user_message)
    
    # Update admin message
    await query.message.edit_caption(
        f"{query.message.caption}\n\n"
        f"<b>❌ {to_small_caps('rejected by')} {query.from_user.first_name}</b>\n"
        f"📅 {to_small_caps('rejected at')}: {datetime.utcnow().strftime('%d-%m-%Y %I:%M:%S %p')} UTC"
    )
    
    # Log to log channel
    if Config.LOG_CHANNEL:
        log_message = (
            f"#Verification_Rejected ❌\n\n"
            f"<b>👤 {to_small_caps('user')}:</b> {verification['user_name']} (<code>{target_user_id}</code>)\n"
            f"<b>💎 {to_small_caps('plan')}:</b> {plan_info['emoji']} {plan_info['name']}\n"
            f"<b>⏰ {to_small_caps('duration')}:</b> {verification['duration']}\n"
            f"<b>👨‍💼 {to_small_caps('rejected by')}:</b> {query.from_user.first_name} (<code>{user_id}</code>)\n"
            f"<b>📅 {to_small_caps('rejected at')}:</b> {datetime.utcnow().strftime('%d-%m-%Y %I:%M:%S %p')} UTC"
        )
        await client.send_message(Config.LOG_CHANNEL, log_message)
    
    await query.answer(f"❌ {to_small_caps('verification rejected')}", show_alert=True)
