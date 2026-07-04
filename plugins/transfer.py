
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database import db
from config import Config
from plugins.utils import to_small_caps
from plugins.logger import BotLogger
import logging

# Store pending transfers
pending_transfers = {}

@Client.on_message(filters.private & filters.command(['transfer']))
async def transfer_command(client, message):
    """Initiate plan transfer to another user"""
    user_id = message.from_user.id
    
    # Check if user has a premium plan
    subscription = await db.get_subscription(user_id)
    plan = subscription.get('plan', 'free')
    
    if plan == 'free':
        return await message.reply(
            f"<b>❌ {to_small_caps('no plan to transfer')}</b>\n\n"
            f"{to_small_caps('you are currently on the free plan. only premium plans can be transferred.')}"
        )
    
    # Ask for recipient details
    await message.reply(
        f"<b>📤 {to_small_caps('plan transfer')}</b>\n\n"
        f"{to_small_caps('please provide the recipient user details')}:\n\n"
        f"• {to_small_caps('send user id')} (<code>1234567890</code>)\n"
        f"• {to_small_caps('send username')} (<code>@username</code>)\n"
        f"• {to_small_caps('or forward a message from the user')}\n\n"
        f"{to_small_caps('send')} /cancel {to_small_caps('to cancel the transfer')}"
    )
    
    # Store user state
    pending_transfers[user_id] = {'state': 'waiting_recipient'}

@Client.on_message(filters.private & ~filters.command(['cancel', 'start', 'help']), group=99)
async def handle_transfer_input(client, message):
    """Handle recipient input for transfer"""
    user_id = message.from_user.id
    
    if user_id not in pending_transfers:
        return message.continue_propagation()
    
    transfer_data = pending_transfers[user_id]
    
    if transfer_data.get('state') != 'waiting_recipient':
        return message.continue_propagation()
    
    recipient_user = None
    recipient_id = None
    
    try:
        # Case 1: Forwarded message
        if message.forward_from:
            recipient_user = message.forward_from
            recipient_id = message.forward_from.id
        
        # Case 2: User ID (numeric)
        elif message.text and message.text.isdigit():
            recipient_id = int(message.text)
            try:
                recipient_user = await client.get_users(recipient_id)
            except Exception as e:
                logging.error(f"Error fetching user by ID: {e}")
                return await message.reply(
                    f"<b>❌ {to_small_caps('user not found')}</b>\n\n"
                    f"{to_small_caps('unable to find user with id')}: <code>{recipient_id}</code>"
                )
        
        # Case 3: Username
        elif message.text and message.text.startswith('@'):
            username = message.text[1:]
            try:
                recipient_user = await client.get_users(username)
                recipient_id = recipient_user.id
            except Exception as e:
                logging.error(f"Error fetching user by username: {e}")
                return await message.reply(
                    f"<b>❌ {to_small_caps('user not found')}</b>\n\n"
                    f"{to_small_caps('unable to find user with username')}: @{username}"
                )
        
        else:
            return await message.reply(
                f"<b>❌ {to_small_caps('invalid input')}</b>\n\n"
                f"{to_small_caps('please send a valid user id, username, or forward a message')}"
            )
        
        # Validate recipient
        if not recipient_user:
            return await message.reply(
                f"<b>❌ {to_small_caps('unable to identify recipient')}</b>\n\n"
                f"{to_small_caps('please try again or send')} /cancel"
            )
        
        # Check if recipient exists in database
        if not await db.is_user_exist(recipient_id):
            return await message.reply(
                f"<b>❌ {to_small_caps('recipient not registered')}</b>\n\n"
                f"{to_small_caps('the recipient must start the bot first')}.\n"
                f"{to_small_caps('user')}: {recipient_user.first_name} (<code>{recipient_id}</code>)"
            )
        
        # Can't transfer to self
        if recipient_id == user_id:
            return await message.reply(
                f"<b>❌ {to_small_caps('invalid transfer')}</b>\n\n"
                f"{to_small_caps('you cannot transfer your plan to yourself')}"
            )
        
        # Get both users' subscription details
        sender_subscription = await db.get_subscription(user_id)
        recipient_subscription = await db.get_subscription(recipient_id)
        
        sender_plan = sender_subscription.get('plan', 'free')
        recipient_plan = recipient_subscription.get('plan', 'free')
        
        sender_plan_info = Config.SUBSCRIPTION_PLANS.get(sender_plan)
        recipient_plan_info = Config.SUBSCRIPTION_PLANS.get(recipient_plan)
        
        # Get user details
        sender_doc = await db.col.find_one({'id': int(user_id)})
        recipient_doc = await db.col.find_one({'id': int(recipient_id)})
        
        sender_name = sender_doc.get('name', 'Unknown') if sender_doc else message.from_user.first_name
        recipient_name = recipient_doc.get('name', 'Unknown') if recipient_doc else recipient_user.first_name
        
        # Show confirmation
        confirmation_text = (
            f"<b>🔄 {to_small_caps('plan transfer confirmation')}</b>\n\n"
            f"<b>📤 {to_small_caps('sender')}:</b>\n"
            f"├─ {to_small_caps('name')}: {sender_name}\n"
            f"├─ {to_small_caps('user id')}: <code>{user_id}</code>\n"
            f"└─ {to_small_caps('current plan')}: {sender_plan_info['emoji']} {sender_plan_info['name']}\n\n"
            f"<b>📥 {to_small_caps('recipient')}:</b>\n"
            f"├─ {to_small_caps('name')}: {recipient_name}\n"
            f"├─ {to_small_caps('user id')}: <code>{recipient_id}</code>\n"
            f"└─ {to_small_caps('current plan')}: {recipient_plan_info['emoji']} {recipient_plan_info['name']}\n\n"
        )
        
        # Add expiry info if applicable
        expires_at = sender_subscription.get('expires_at')
        status = sender_subscription.get('status', 'active')
        
        if status == 'lifetime':
            confirmation_text += f"<b>⏰ {to_small_caps('plan duration')}: ♾️ {to_small_caps('lifetime')}</b>\n\n"
        elif expires_at:
            from datetime import datetime
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            if expires_at.tzinfo is None:
                expires_at = pytz.utc.localize(expires_at)
            expires_ist = expires_at.astimezone(ist)
            
            time_diff = expires_at.replace(tzinfo=None) - datetime.utcnow()
            if time_diff.total_seconds() > 0:
                days_left = time_diff.days
                hours_left = time_diff.seconds // 3600
                minutes_left = (time_diff.seconds % 3600) // 60
                confirmation_text += (
                    f"<b>⏰ {to_small_caps('remaining time')}: {days_left} {to_small_caps('days')}, "
                    f"{hours_left} {to_small_caps('hours')}, {minutes_left} {to_small_caps('minutes')}</b>\n"
                    f"<b>📅 {to_small_caps('expires on')}: {expires_ist.strftime('%d-%m-%Y %I:%M:%S %p')}</b>\n\n"
                )
        
        confirmation_text += (
            f"⚠️ <b>{to_small_caps('warning')}:</b>\n"
            f"• {to_small_caps('your plan will be transferred to the recipient')}\n"
            f"• {to_small_caps('you will be downgraded to free plan')}\n"
            f"• {to_small_caps('this action cannot be undone')}\n\n"
            f"{to_small_caps('are you sure you want to continue?')}"
        )
        
        # Store transfer details
        pending_transfers[user_id] = {
            'state': 'awaiting_confirmation',
            'recipient_id': recipient_id,
            'recipient_name': recipient_name,
            'sender_plan': sender_plan,
            'recipient_plan': recipient_plan,
            'subscription_data': sender_subscription
        }
        
        # Create confirmation buttons
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"✅ {to_small_caps('confirm transfer')}", callback_data=f"confirm_transfer#{user_id}"),
                InlineKeyboardButton(f"❌ {to_small_caps('cancel')}", callback_data=f"cancel_transfer#{user_id}")
            ]
        ])
        
        await message.reply(confirmation_text, reply_markup=buttons)
        
    except Exception as e:
        logging.error(f"Error in transfer input handling: {e}", exc_info=True)
        await message.reply(
            f"<b>❌ {to_small_caps('error')}</b>\n\n"
            f"{to_small_caps('an error occurred')}: <code>{str(e)}</code>"
        )
        pending_transfers.pop(user_id, None)

@Client.on_callback_query(filters.regex(r'^confirm_transfer#'))
async def confirm_transfer_callback(client, query):
    """Confirm and execute the plan transfer"""
    sender_id = int(query.data.split('#')[1])
    
    if query.from_user.id != sender_id:
        return await query.answer(f"❌ {to_small_caps('this is not your transfer request')}", show_alert=True)
    
    if sender_id not in pending_transfers:
        return await query.answer(f"❌ {to_small_caps('transfer session expired')}", show_alert=True)
    
    transfer_data = pending_transfers.get(sender_id)
    
    if transfer_data.get('state') != 'awaiting_confirmation':
        return await query.answer(f"❌ {to_small_caps('invalid transfer state')}", show_alert=True)
    
    try:
        status_msg = await query.message.edit_text(
            f"⚙️ {to_small_caps('processing transfer')}...\n\n{to_small_caps('please wait')}"
        )
        
        recipient_id = transfer_data['recipient_id']
        recipient_name = transfer_data['recipient_name']
        sender_plan = transfer_data['sender_plan']
        subscription_data = transfer_data['subscription_data']
        
        # Get sender name
        sender_doc = await db.col.find_one({'id': int(sender_id)})
        sender_name = sender_doc.get('name', 'Unknown') if sender_doc else query.from_user.first_name
        
        # Transfer the plan to recipient
        await db.col.update_one(
            {'id': int(recipient_id)},
            {'$set': {'subscription': subscription_data}},
            upsert=True
        )
        
        # Downgrade sender to free plan
        await db.set_subscription(sender_id, 'free', assigned_by='transfer')
        
        # Log the transfer
        from datetime import datetime
        import pytz
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(ist)
        date_str = now_ist.strftime('%d-%m-%Y')
        time_str = now_ist.strftime('%I:%M:%S %p')
        
        sender_plan_info = Config.SUBSCRIPTION_PLANS.get(sender_plan)
        
        log_text = (
            f"#Plan_Transfer 🔄\n\n"
            f"<b>📤 {to_small_caps('sender')}:</b>\n"
            f"├─ {to_small_caps('name')}: {sender_name}\n"
            f"├─ {to_small_caps('user id')}: <code>{sender_id}</code>\n"
            f"└─ {to_small_caps('transferred plan')}: {sender_plan_info['emoji']} {sender_plan_info['name']}\n\n"
            f"<b>📥 {to_small_caps('recipient')}:</b>\n"
            f"├─ {to_small_caps('name')}: {recipient_name}\n"
            f"└─ {to_small_caps('user id')}: <code>{recipient_id}</code>\n\n"
            f"<b>📅 {to_small_caps('transfer date')}: {date_str}</b>\n"
            f"<b>⏰ {to_small_caps('transfer time')}: {time_str}</b>"
        )
        
        # Send to log channel
        if Config.LOG_CHANNEL:
            try:
                await client.send_message(Config.LOG_CHANNEL, log_text)
            except Exception as e:
                logging.error(f"Error sending transfer log: {e}")
        
        # Notify sender
        await status_msg.edit_text(
            f"<b>✅ {to_small_caps('transfer completed successfully')}</b>\n\n"
            f"{to_small_caps('your')} {sender_plan_info['emoji']} <b>{sender_plan_info['name']}</b> "
            f"{to_small_caps('plan has been transferred to')}:\n\n"
            f"👤 {recipient_name}\n"
            f"🆔 <code>{recipient_id}</code>\n\n"
            f"{to_small_caps('you have been downgraded to free plan')}"
        )
        
        # Notify recipient
        try:
            recipient_msg = (
                f"<b>🎉 {to_small_caps('plan received')} 🎉</b>\n\n"
                f"{to_small_caps('you have received a')} {sender_plan_info['emoji']} <b>{sender_plan_info['name']}</b> "
                f"{to_small_caps('plan from')}:\n\n"
                f"👤 {sender_name}\n"
                f"🆔 <code>{sender_id}</code>\n\n"
                f"{to_small_caps('use')} /myplan {to_small_caps('to view your plan details')}"
            )
            await client.send_message(recipient_id, recipient_msg)
        except Exception as e:
            logging.error(f"Error notifying recipient: {e}")
        
        # Clean up
        pending_transfers.pop(sender_id, None)
        
    except Exception as e:
        logging.error(f"Error executing transfer: {e}", exc_info=True)
        await query.message.edit_text(
            f"<b>❌ {to_small_caps('transfer failed')}</b>\n\n"
            f"{to_small_caps('an error occurred')}: <code>{str(e)}</code>"
        )
        pending_transfers.pop(sender_id, None)

@Client.on_callback_query(filters.regex(r'^cancel_transfer#'))
async def cancel_transfer_callback(client, query):
    """Cancel the plan transfer"""
    sender_id = int(query.data.split('#')[1])
    
    if query.from_user.id != sender_id:
        return await query.answer(f"❌ {to_small_caps('this is not your transfer request')}", show_alert=True)
    
    pending_transfers.pop(sender_id, None)
    
    await query.message.edit_text(
        f"<b>❌ {to_small_caps('transfer cancelled')}</b>\n\n"
        f"{to_small_caps('your plan transfer has been cancelled')}"
    )
    await query.answer(f"✅ {to_small_caps('transfer cancelled')}")

@Client.on_message(filters.private & filters.command(['cancel']))
async def cancel_transfer_command(client, message):
    """Cancel ongoing transfer via command"""
    user_id = message.from_user.id
    
    if user_id in pending_transfers:
        pending_transfers.pop(user_id, None)
        await message.reply(
            f"<b>❌ {to_small_caps('transfer cancelled')}</b>\n\n"
            f"{to_small_caps('your plan transfer has been cancelled')}"
        )
