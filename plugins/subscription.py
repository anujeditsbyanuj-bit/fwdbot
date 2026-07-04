from database import db
from config import Config
from .utils import to_small_caps
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import traceback

async def check_owner_sub(message):
    """Check if user is owner for subscription commands"""
    if message.from_user.id not in Config.BOT_OWNER_ID:
        await message.reply_text(
            f"🚫 <b>{to_small_caps('this command is not for you')}</b> 🚫\n\n"
            f"⚠️ {to_small_caps('only bot owner can use this command')}"
        )
        return False
    return True

class SubscriptionError(Exception):
    """Custom exception for subscription-related errors"""
    pass


async def require_forwarding(user_id):
    """
    Check if user has forwarding permission
    Returns: (bool, message)
    """
    try:
        subscription = await db.get_subscription(user_id)
        plan = subscription.get('plan', 'free')
        status = subscription.get('status', 'active')
        features = subscription.get('features', {})

        if status == 'expired':
            message = (
                f"<b>⏰ {to_small_caps('subscription expired')} ⏰</b>\n\n"
                f"{to_small_caps('your')} <b>{Config.SUBSCRIPTION_PLANS.get(plan, {}).get('name', plan)}</b> "
                f"{to_small_caps('plan has expired.')}\n\n"
                f"{to_small_caps('please renew to continue forwarding.')}"
            )
            return (False, message)

        forwarding_allowed = features.get('forwarding', {}).get('allowed', False)

        if not forwarding_allowed:
            plan_info = Config.SUBSCRIPTION_PLANS.get(plan, {})
            message = (
                f"<b>🚫 {to_small_caps('forwarding not allowed')} 🚫</b>\n\n"
                f"{to_small_caps('your current plan:')} <b>{plan_info.get('emoji', '')} {plan_info.get('name', plan)}</b>\n"
                f"{to_small_caps(plan_info.get('description', ''))}\n\n"
                f"<b>📢 {to_small_caps('upgrade to unlock forwarding!')}</b>\n\n"
                f"⭐ <b>{to_small_caps('plus plan')}</b> - {to_small_caps('unlimited forwarding')}\n"
                f"💎 <b>{to_small_caps('pro plan')}</b> - {to_small_caps('forwarding + ftm manager')}\n"
                f"♾️ <b>{to_small_caps('infinity plan')}</b> - {to_small_caps('all features unlocked')}\n\n"
                f"{to_small_caps('use /subscription to view plans')}"
            )
            return (False, message)

        task_limit = features.get('forwarding', {}).get('limit')
        if task_limit is not None:
            active_tasks = await db.get_active_tasks(user_id)
            current_tasks = active_tasks.get('forwarding', 0)

            if current_tasks >= task_limit:
                message = (
                    f"<b>⚠️ {to_small_caps('task limit reached')} ⚠️</b>\n\n"
                    f"{to_small_caps('your')} <b>{Config.SUBSCRIPTION_PLANS.get(plan, {}).get('name', plan)}</b> "
                    f"{to_small_caps('plan allows')} <b>{task_limit}</b> {to_small_caps('forwarding task at a time.')}\n\n"
                    f"{to_small_caps('please wait for current task to complete.')}\n\n"
                    f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>🔧 {to_small_caps('if no process is running:')}</b>\n\n"
                    f"• /cancel - {to_small_caps('cancel any running task')}\n"
                    f"• /cleartask - {to_small_caps('reset stuck task counter')}\n\n"
                    f"<i>{to_small_caps('use these commands if you see this message but no forwarding is active.')}</i>"
                )
                return (False, message)

        return (True, None)
    except Exception as e:
        logging.error(f"Error in require_forwarding: {e}")
        return (False, f"❌ Error checking subscription: {str(e)}")


async def require_ftm(user_id, capability='delta'):
    """
    Check if user has FTM capability access
    capability: 'delta', 'gamma', 'replacements', 'watermark', 'link_remover'
    Returns: (bool, message)
    """
    try:
        subscription = await db.get_subscription(user_id)
        plan = subscription.get('plan', 'free')
        status = subscription.get('status', 'active')
        features = subscription.get('features', {})

        if status == 'expired':
            message = (
                f"<b>⏰ {to_small_caps('subscription expired')} ⏰</b>\n\n"
                f"{to_small_caps('your subscription has expired. please renew to access ftm features.')}"
            )
            return (False, message)

        ftm_features = features.get('ftm', {})
        has_access = ftm_features.get(capability, False)

        if not has_access:
            plan_info = Config.SUBSCRIPTION_PLANS.get(plan, {})
            capability_names = {
                'delta': 'ғᴛᴍ ᴅᴇʟᴛᴀ ᴍᴏᴅᴇ',
                'gamma': 'ғᴛᴍ ɢᴀᴍᴍᴀ ᴍᴏᴅᴇ',
                'replacements': 'ғᴛᴍ ʀᴇᴘʟᴀᴄᴇʀ',
                'watermark': 'ғᴛᴍ ᴡᴀᴛᴇʀᴍᴀʀᴋ',
                'link_remover': 'ғᴛᴍ ʟɪɴᴋ ʀᴇᴍᴏᴠᴇʀ',
                'thumbnail_changer': 'ғᴛᴍ ᴛʜᴜᴍʙɴᴀɪʟ ᴄʜᴀɴɢᴇʀ',
                'alpha': 'ғᴛᴍ ᴀʟᴘʜᴀ ᴍᴏᴅᴇ'
            }

            required_plan = 'pro'
            if capability == 'gamma':
                required_plan = 'pro'
            elif capability == 'thumbnail_changer':
                required_plan = 'infinity'
            elif capability in ['delta', 'theta', 'replacements', 'link_remover', 'alpha']:
                required_plan = 'infinity'

            # Special message for Infinity-only features
            if required_plan == 'infinity' and capability in ['delta', 'theta', 'replacements', 'link_remover', 'alpha']:
                message = (
                    f"<b>🔒 {to_small_caps('premium feature')} 🔒</b>\n\n"
                    f"<b>{capability_names.get(capability, capability)}</b> {to_small_caps('is only available for')} "
                    f"<b>♾️ Infinity</b> {to_small_caps('plan users.')}\n\n"
                    f"<b>📢 {to_small_caps('upgrade to')} {Config.SUBSCRIPTION_PLANS['infinity']['emoji']} "
                    f"{Config.SUBSCRIPTION_PLANS['infinity']['name']} {to_small_caps('to unlock this feature!')}</b>\n\n"
                    f"{to_small_caps('use /subscription to view plans')}"
                )
            else:
                message = (
                    f"<b>🔒 {to_small_caps('premium feature')} 🔒</b>\n\n"
                    f"<b>{capability_names.get(capability, capability)}</b> {to_small_caps('is not available in your')} "
                    f"<b>{plan_info.get('emoji', '')} {plan_info.get('name', plan)}</b> {to_small_caps('plan.')}\n\n"
                    f"<b>📢 {to_small_caps('upgrade to')} {Config.SUBSCRIPTION_PLANS[required_plan]['emoji']} "
                    f"{Config.SUBSCRIPTION_PLANS[required_plan]['name']} {to_small_caps('or higher!')}</b>\n\n"
                    f"{to_small_caps('use /subscription to view plans')}"
                )
            return (False, message)

        return (True, None)
    except Exception as e:
        logging.error(f"Error in require_ftm: {e}")
        return (False, f"❌ Error checking subscription: {str(e)}")


async def require_unequify(user_id):
    """
    Check if user has unequify access
    Returns: (bool, message)
    """
    try:
        subscription = await db.get_subscription(user_id)
        plan = subscription.get('plan', 'free')
        status = subscription.get('status', 'active')
        features = subscription.get('features', {})

        if status == 'expired':
            message = (
                f"<b>⏰ {to_small_caps('subscription expired')} ⏰</b>\n\n"
                f"{to_small_caps('your subscription has expired. please renew to access unequify.')}"
            )
            return (False, message)

        has_access = features.get('unequify', False)

        if not has_access:
            plan_info = Config.SUBSCRIPTION_PLANS.get(plan, {})
            message = (
                f"<b>🔒 {to_small_caps('premium feature')} 🔒</b>\n\n"
                f"<b>✂️ {to_small_caps('unequify')}</b> {to_small_caps('is only available in')} "
                f"<b>♾️ {Config.SUBSCRIPTION_PLANS['infinity']['name']}</b> {to_small_caps('plan.')}\n\n"
                f"{to_small_caps('your current plan:')} <b>{plan_info.get('emoji', '')} {plan_info.get('name', plan)}</b>\n\n"
                f"<b>📢 {to_small_caps('upgrade to infinity to unlock unequify!')}</b>\n\n"
                f"{to_small_caps('use /subscription to view plans')}"
            )
            return (False, message)

        return (True, None)
    except Exception as e:
        logging.error(f"Error in require_unequify: {e}")
        return (False, f"❌ Error checking subscription: {str(e)}")


async def get_subscription_info_text(user_id):
    """Get formatted subscription information for a user"""
    from datetime import datetime
    import pytz

    try:
        subscription = await db.get_subscription(user_id)
        plan = subscription.get('plan', 'free')
        status = subscription.get('status', 'active')
        expires_at = subscription.get('expires_at')
        purchased_at = subscription.get('purchased_at')
        assigned_by = subscription.get('assigned_by', 'system')

        plan_info = Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])

        # Get user info
        user_doc = await db.col.find_one({'id': int(user_id)})
        joined_at = user_doc.get('joined_at') if user_doc else None
        user_name = user_doc.get('name', 'User') if user_doc else 'User'

        # Determine plan type
        plan_type = "Owner" if user_id in Config.BOT_OWNER_ID and status == 'lifetime' else plan_info['name']

        # IST timezone
        ist = pytz.timezone('Asia/Kolkata')

        text = f"⚜️💎 {to_small_caps('my plan')} 💎⚜️\n\n"
        text += f"👤 {to_small_caps('user')} : {user_name}\n"
        text += f"⚡ {to_small_caps('user id')} : <code>{user_id}</code>\n"
        text += f"💎 {to_small_caps('plan')} : {plan_info['emoji']} {plan_info['name']}\n"
        text += f"📊 {to_small_caps('plan type')} : {plan_type}\n"

        # Registration date and time (convert to IST)
        if joined_at:
            if joined_at.tzinfo is None:
                joined_at = pytz.utc.localize(joined_at)
            joined_ist = joined_at.astimezone(ist)
            registration_date = joined_ist.strftime('%d-%m-%Y')
            registration_time = joined_ist.strftime('%I:%M:%S %p')
            text += f"📅 {to_small_caps('registration date')} : {registration_date}\n"
            text += f"🕐 {to_small_caps('registration time')} : {registration_time}\n"

        # Purchased date and time (convert to IST)
        if purchased_at:
            if purchased_at.tzinfo is None:
                purchased_at = pytz.utc.localize(purchased_at)
            purchased_ist = purchased_at.astimezone(ist)
            purchased_date = purchased_ist.strftime('%d-%m-%Y')
            purchased_time = purchased_ist.strftime('%I:%M:%S %p')
            text += f"💳 {to_small_caps('purchased date')} : {purchased_date}\n"
            text += f"🕐 {to_small_caps('purchased time')} : {purchased_time}\n"

        # Expiry information (convert to IST)
        if status == 'lifetime':
            text += f"⏰ {to_small_caps('time left')} : ♾️ {to_small_caps('lifetime')}\n"
            text += f"⌛️ {to_small_caps('expiry date')} : N/A\n"
            text += f"⏱️ {to_small_caps('expiry time')} : N/A\n"
        elif expires_at:
            now_utc = datetime.utcnow()
            time_diff = expires_at - now_utc
            if time_diff.total_seconds() > 0:
                days_left = time_diff.days
                hours_left = time_diff.seconds // 3600
                minutes_left = (time_diff.seconds % 3600) // 60
                text += f"⏰ {to_small_caps('time left')} : {days_left} {to_small_caps('days')}, {hours_left} {to_small_caps('hours')}, {minutes_left} {to_small_caps('minutes')}\n"

                if expires_at.tzinfo is None:
                    expires_at = pytz.utc.localize(expires_at)
                expires_ist = expires_at.astimezone(ist)
                expiry_date = expires_ist.strftime('%d-%m-%Y')
                expiry_time = expires_ist.strftime('%I:%M:%S %p')
                text += f"⌛️ {to_small_caps('expiry date')} : {expiry_date}\n"
                text += f"⏱️ {to_small_caps('expiry time')} : {expiry_time}\n"
            else:
                text += f"⏰ {to_small_caps('status')} : {to_small_caps('expired')}\n"
        else:
            text += f"⏰ {to_small_caps('time left')} : N/A\n"

        # Features section
        features = subscription.get('features', {})
        forwarding = features.get('forwarding', {})
        ftm = features.get('ftm', {})

        text += f"\n✨ {to_small_caps('features unlocked')} :\n\n"

        if forwarding.get('allowed'):
            limit = forwarding.get('limit')
            if limit:
                text += f"✅ {to_small_caps('forwarding')} ({limit} {to_small_caps('concurrent')})\n"
            else:
                text += f"✅ {to_small_caps('unlimited forwarding')}\n"
        else:
            text += f"❌ {to_small_caps('forwarding')}\n"

        if ftm.get('delta'):
            text += f"✅ {to_small_caps('ftm delta mode')}\n"
        else:
            text += f"❌ {to_small_caps('ftm delta mode')}\n"

        if ftm.get('watermark'):
            text += f"✅ {to_small_caps('ftm watermark')}\n"
        else:
            text += f"❌ {to_small_caps('ftm watermark')}\n"

        if ftm.get('replacements'):
            text += f"✅ {to_small_caps('ftm replacer & remover')}\n"
        else:
            text += f"❌ {to_small_caps('ftm replacer & remover')}\n"

        if ftm.get('link_remover'):
            text += f"✅ {to_small_caps('ftm link remover')}\n"
        else:
            text += f"❌ {to_small_caps('ftm link remover')}\n"

        if ftm.get('gamma'):
            text += f"✅ {to_small_caps('ftm gamma mode')}\n"
        else:
            text += f"❌ {to_small_caps('ftm gamma mode')}\n"

        if features.get('unequify'):
            text += f"✅ {to_small_caps('unequify')}\n"
        else:
            text += f"❌ {to_small_caps('unequify')}\n"

        if plan == 'free':
            text += f"\n💡 <i>{to_small_caps('tip: upgrade to unlock premium features!')}</i>"

        return text
    except Exception as e:
        logging.error(f"Error in get_subscription_info_text: {e}")
        logging.error(traceback.format_exc())
        return f"❌ Error retrieving subscription info: {str(e)}"


@Client.on_message(filters.private & filters.command(['myplan']))
async def myplan_command(client, message):
    """Show user's current subscription details"""
    user_id = message.from_user.id

    # Log plan check
    from plugins.logger import BotLogger
    await BotLogger.log_plan_check(client, user_id, message.from_user.first_name)

    try:
        text = await get_subscription_info_text(user_id)

        buttons = [
            [InlineKeyboardButton(f"📋 {to_small_caps('view all plans')}", callback_data='sub#main')],
            [InlineKeyboardButton(f"📞 {to_small_caps('contact admin')}", url=Config.ADMIN_CONTACT_URL)],
            [InlineKeyboardButton(f"⫷ {to_small_caps('back')}", callback_data='back')]
        ]

        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logging.error(f"Error in myplan_command: {e}")
        logging.error(traceback.format_exc())
        await message.reply_text(f"❌ Error: {str(e)}")


@Client.on_message(filters.command("add_bal") & filters.private)
async def add_balance_command(client, message):
    if message.from_user.id not in Config.BOT_OWNER_ID:
        return
        
    try:
        args = message.text.split()
        if len(args) != 3:
            return await message.reply_text("<b>Usage:</b> /add_bal {userid} {amount}")
            
        user_id = int(args[1])
        amount = float(args[2])
        
        await db.add_balance(user_id, amount)
        new_bal = await db.get_balance(user_id)
        
        # Notify User
        try:
            await client.send_message(
                user_id,
                f"<b>💰 {to_small_caps('balance updated')}!</b>\n\n"
                f"🎁 {to_small_caps('admin added')} <b>{amount} ғᴛᴍ ʙᴜᴄᴋs</b> {to_small_caps('to your account.')}\n"
                f"🏦 {to_small_caps('new balance')}: <b>{new_bal} ғᴛᴍ ʙᴜᴄᴋs</b>"
            )
        except Exception as e:
            logging.error(f"Failed to notify user {user_id}: {e}")
        # Log to Channel
        log_text = (
            f"<b>💸 {to_small_caps('balance added')} 💸</b>\n\n"
            f"👤 {to_small_caps('user')}: <code>{user_id}</code>\n"
            f"💰 {to_small_caps('amount')}: <code>{amount} ғᴛᴍ ʙᴜᴄᴋs</code>\n"
            f"🏦 {to_small_caps('new balance')}: <code>{new_bal} ғᴛᴍ ʙᴜᴄᴋs</code>\n"
            f"👮‍♂️ {to_small_caps('by owner')}: {message.from_user.mention}"
        )
        await client.send_message(Config.LOG_CHANNEL, log_text)
        
        await message.reply_text(f"✅ {to_small_caps('added')} {amount} {to_small_caps('to')} {user_id}. {to_small_caps('new bal')}: {new_bal}")
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.command(['subscription', 'sub', 'plan']))
async def subscription_command(client, message):
    """Show subscription plans"""
    user_id = message.from_user.id

    # Log plan check
    from plugins.logger import BotLogger
    await BotLogger.log_plan_check(client, user_id, message.from_user.first_name)

    try:
        subscription = await db.get_subscription(user_id)
        current_plan = subscription.get('plan', 'free')

        text = (
            f"<b>💳 {to_small_caps('subscription plans')} 💳</b>\n\n"
            f"{to_small_caps('choose the perfect plan for your needs')}\n\n"
        )

        for plan_key in ['free', 'plus', 'pro', 'infinity']:
            plan = Config.SUBSCRIPTION_PLANS[plan_key]
            is_current = (plan_key == current_plan)

            text += f"{'🔹' if is_current else '▫️'} <b>{plan['emoji']} {plan['name']}</b>"
            if is_current:
                text += f" {to_small_caps('(current)')}"
            text += "\n"

            text += f"   {plan['description']}\n"

            if plan['price'] > 0:
                text += f"   💰 <b>{plan['price']}</b> {to_small_caps('for')} {plan['duration_days']} {to_small_caps('days')}\n"
            else:
                text += f"   💰 <b>{to_small_caps('free')}</b>\n"

            text += "\n"

        text += f"\n{to_small_caps('use the buttons below to view details or upgrade your plan')}"

        buttons = [
            [InlineKeyboardButton(f"📊 {to_small_caps('my subscription')}", callback_data='sub#my_plan')],
            [
                InlineKeyboardButton(f"{Config.SUBSCRIPTION_PLANS['plus']['emoji']} {to_small_caps('plus')}", callback_data='sub#plan_plus'),
                InlineKeyboardButton(f"{Config.SUBSCRIPTION_PLANS['pro']['emoji']} {to_small_caps('pro')}", callback_data='sub#plan_pro')
            ],
            [
                InlineKeyboardButton(f"{Config.SUBSCRIPTION_PLANS['infinity']['emoji']} {to_small_caps('infinity')}", callback_data='sub#plan_infinity')
            ],
            [InlineKeyboardButton(f"⫷ {to_small_caps('back')}", callback_data='back')]
        ]

        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logging.error(f"Error in subscription_command: {e}")
        logging.error(traceback.format_exc())
        await message.reply_text(f"❌ Error: {str(e)}")


@Client.on_callback_query(filters.regex(r'^sub#'))
async def subscription_callback(client, query):
    """Handle subscription callbacks"""
    user_id = query.from_user.id
    data = query.data

    await query.answer()

    # Log plan exploration
    from plugins.logger import BotLogger
    await BotLogger.log_plan_check(client, user_id, query.from_user.first_name)

    if data == 'sub#my_plan':
        try:
            text = await get_subscription_info_text(user_id)
            buttons = [[InlineKeyboardButton(f"⫷ {to_small_caps('back')}", callback_data='sub#main')]]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            logging.error(f"Error in subscription_callback (sub#my_plan): {e}")
            logging.error(traceback.format_exc())
            await query.answer(f"❌ Error: {str(e)}", show_alert=True)

    elif data.startswith('sub#plan_'):
        plan_key = data.replace('sub#plan_', '')
        plan = Config.SUBSCRIPTION_PLANS.get(plan_key)

        if not plan:
            return await query.answer(f"❌ {to_small_caps('invalid plan')}", show_alert=True)

        try:
            subscription = await db.get_subscription(user_id)
            current_plan = subscription.get('plan', 'free')

            text = (
                f"<b>{plan['emoji']} {plan['name']} {to_small_caps('plan')} {plan['emoji']}</b>\n\n"
                f"<b>📝 {to_small_caps('description')}:</b>\n{plan['description']}\n\n"
                f"<b>💰 {to_small_caps('price')}:</b> "
            )

            if plan['price'] > 0:
                text += f"<b>{plan['price']}</b> {to_small_caps('for')} {plan['duration_days']} {to_small_caps('days')}\n\n"
            else:
                text += f"<b>{to_small_caps('free')}</b>\n\n"

            text += f"<b>✨ {to_small_caps('features included')}:</b>\n"

            features = plan['features']
            forwarding = features.get('forwarding', {})
            ftm = features.get('ftm', {})

            if forwarding.get('allowed'):
                limit = forwarding.get('limit')
                if limit:
                    text += f"✅ {to_small_caps('forwarding')} ({limit} {to_small_caps('at a time')})\n"
                else:
                    text += f"✅ {to_small_caps('unlimited forwarding')}\n"
            else:
                text += f"❌ {to_small_caps('no forwarding')}\n"

            if ftm.get('delta'):
                text += f"✅ {to_small_caps('ftm delta mode')}\n"
            if ftm.get('watermark'):
                text += f"✅ {to_small_caps('ftm watermark (prefix/suffix)')}\n"
            if ftm.get('replacements'):
                text += f"✅ {to_small_caps('ftm replacer & remover')}\n"
            if ftm.get('link_remover'):
                text += f"✅ {to_small_caps('ftm link remover')}\n"
            if ftm.get('gamma'):
                text += f"✅ {to_small_caps('ftm gamma mode (auto-forward)')}\n"
            if ftm.get('thumbnail_changer'):
                text += f"✅ {to_small_caps('ftm thumbnail changer')} 🖼️\n"

            if features.get('unequify'):
                text += f"✅ {to_small_caps('unequify (remove duplicates)')}\n"

            buttons = []

            if plan_key != current_plan and plan['price'] > 0:
                text += f"\n<b>💡 {to_small_caps('want to upgrade?')}</b>\n"
                text += f"{to_small_caps('contact admin to purchase this plan')}\n"
                buttons.append([InlineKeyboardButton(f"📞 {to_small_caps('contact admin')}", url=Config.SUPPORT_GROUP)])
            elif plan_key == current_plan:
                text += f"\n<b>✅ {to_small_caps('this is your current plan')}</b>"

            buttons.append([InlineKeyboardButton(f"⫷ {to_small_caps('back')}", callback_data='sub#main')])
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            logging.error(f"Error in subscription_callback (sub#{plan_key}): {e}")
            logging.error(traceback.format_exc())
            await query.answer(f"❌ Error: {str(e)}", show_alert=True)

    elif data == 'sub#main':
        try:
            subscription = await db.get_subscription(user_id)
            current_plan = subscription.get('plan', 'free')

            text = (
                f"<b>💳 {to_small_caps('subscription plans')} 💳</b>\n\n"
                f"{to_small_caps('choose the perfect plan for your needs')}\n\n"
            )

            for plan_key in ['free', 'plus', 'pro', 'infinity']:
                plan = Config.SUBSCRIPTION_PLANS[plan_key]
                is_current = (plan_key == current_plan)

                text += f"{'🔹' if is_current else '▫️'} <b>{plan['emoji']} {plan['name']}</b>"
                if is_current:
                    text += f" {to_small_caps('(current)')}"
                text += "\n"

                text += f"   {plan['description']}\n"

                if plan['price'] > 0:
                    text += f"   💰 <b>{plan['price']}</b> {to_small_caps('for')} {plan['duration_days']} {to_small_caps('days')}\n"
                else:
                    text += f"   💰 <b>{to_small_caps('free')}</b>\n"

                text += "\n"

            text += f"\n{to_small_caps('use the buttons below to view details or upgrade your plan')}"

            buttons = [
                [InlineKeyboardButton(f"📊 {to_small_caps('my subscription')}", callback_data='sub#my_plan')],
                [
                    InlineKeyboardButton(f"{Config.SUBSCRIPTION_PLANS['plus']['emoji']} {to_small_caps('plus')}", callback_data='sub#plan_plus'),
                    InlineKeyboardButton(f"{Config.SUBSCRIPTION_PLANS['pro']['emoji']} {to_small_caps('pro')}", callback_data='sub#plan_pro')
                ],
                [
                    InlineKeyboardButton(f"{Config.SUBSCRIPTION_PLANS['infinity']['emoji']} {to_small_caps('infinity')}", callback_data='sub#plan_infinity')
                ],
                [InlineKeyboardButton(f"⫷ {to_small_caps('back')}", callback_data='back')]
            ]

            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            logging.error(f"Error in subscription_callback (sub#main): {e}")
            logging.error(traceback.format_exc())
            await query.answer(f"❌ Error: {str(e)}", show_alert=True)


@Client.on_message(filters.private & filters.command(['add_premium']))
async def add_premium_command(client, message):
    """Admin command to add premium plan to a user with custom duration"""
    if not await check_owner_sub(message):
        return
    from datetime import datetime, timedelta

    try:
        args = message.text.split()
        if len(args) < 4:
            return await message.reply(
                f"<b>❌ {to_small_caps('invalid format')}</b>\n\n"
                f"<b>{to_small_caps('usage')}:</b> <code>/add_premium user_id plan duration</code>\n\n"
                f"<b>{to_small_caps('plans')}:</b> <code>plus, pro, infinity</code>\n\n"
                f"<b>{to_small_caps('duration formats')}:</b>\n"
                f"  • <code>3d</code> = 3 {to_small_caps('days')}\n"
                f"  • <code>5h</code> = 5 {to_small_caps('hours')}\n"
                f"  • <code>30m</code> = 30 {to_small_caps('minutes')}\n"
                f"  • <code>2w</code> = 2 {to_small_caps('weeks')}\n"
                f"  • <code>1M</code> = 1 {to_small_caps('month')}\n"
                f"  • <code>1y</code> = 1 {to_small_caps('year')}\n"
                f"  • <code>infinity</code> = {to_small_caps('lifetime')}\n\n"
                f"<b>{to_small_caps('examples')}:</b>\n"
                f"  <code>/add_premium 123456789 plus 30d</code>\n"
                f"  <code>/add_premium 123456789 pro infinity</code>"
            )

        target_user_id = int(args[1])
        plan = args[2].lower()
        duration_str = args[3].lower()

        if plan not in ['plus', 'pro', 'infinity']:
            return await message.reply(
                f"<b>❌ {to_small_caps('invalid plan')}</b>\n\n"
                f"<b>{to_small_caps('available plans')}:</b> <code>plus, pro, infinity</code>"
            )

        if not await db.is_user_exist(target_user_id):
            return await message.reply(
                f"<b>❌ {to_small_caps('user not found')}</b>\n\n"
                f"{to_small_caps('user id')} <code>{target_user_id}</code> {to_small_caps('is not in the database')}"
            )

        # Parse duration
        expires_at = None
        status = 'active'
        duration_text = ""

        if duration_str == 'infinity' or duration_str == 'lifetime':
            status = 'lifetime'
            expires_at = None
            duration_text = f"♾️ {to_small_caps('lifetime')}"
        else:
            # Parse time unit
            import re
            match = re.match(r'^(\d+)([dhwMym])$', duration_str)
            if not match:
                return await message.reply(
                    f"<b>❌ {to_small_caps('invalid duration format')}</b>\n\n"
                    f"{to_small_caps('use')}: <code>3d, 5h, 30m, 2w, 1M, 1y, {to_small_caps('or')} infinity</code>"
                )

            amount = int(match.group(1))
            unit = match.group(2)

            now = datetime.utcnow()

            if unit == 'm':
                expires_at = now + timedelta(minutes=amount)
                duration_text = f"{amount} {to_small_caps('minutes' if amount > 1 else 'minute')}"
            elif unit == 'h':
                expires_at = now + timedelta(hours=amount)
                duration_text = f"{amount} {to_small_caps('hours' if amount > 1 else 'hour')}"
            elif unit == 'd':
                expires_at = now + timedelta(days=amount)
                duration_text = f"{amount} {to_small_caps('days' if amount > 1 else 'day')}"
            elif unit == 'w':
                expires_at = now + timedelta(weeks=amount)
                duration_text = f"{amount} {to_small_caps('weeks' if amount > 1 else 'week')}"
            elif unit == 'M':
                expires_at = now + timedelta(days=amount * 30)
                duration_text = f"{amount} {to_small_caps('months' if amount > 1 else 'month')}"
            elif unit == 'y':
                expires_at = now + timedelta(days=amount * 365)
                duration_text = f"{amount} {to_small_caps('years' if amount > 1 else 'year')}"

        # Set subscription with custom expiry
        subscription_data = {
            'plan': plan,
            'status': status,
            'expires_at': expires_at,
            'purchased_at': datetime.utcnow(),
            'assigned_by': message.from_user.id,
            'features': Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])['features']
        }

        await db.col.update_one(
            {'id': int(target_user_id)},
            {'$set': {'subscription': subscription_data}},
            upsert=True
        )

        plan_info = Config.SUBSCRIPTION_PLANS[plan]

        # Get user name
        user_doc = await db.col.find_one({'id': int(target_user_id)})
        user_name = user_doc.get('name', 'Unknown') if user_doc else 'Unknown'

        # Admin confirmation message
        admin_msg = (
            f"<b>✅ {to_small_caps('premium added successfully')}</b>\n\n"
            f"👤 <b>{to_small_caps('user')}:</b> {user_name}\n"
            f"⚡ <b>{to_small_caps('user id')}:</b> <code>{target_user_id}</code>\n"
            f"💎 <b>{to_small_caps('plan')}:</b> {plan_info['emoji']} <b>{plan_info['name']}</b>\n"
            f"⏰ <b>{to_small_caps('duration')}:</b> {duration_text}\n"
        )

        if expires_at:
            expiry_date = expires_at.strftime('%d-%m-%Y')
            expiry_time = expires_at.strftime('%I:%M:%S %p')
            admin_msg += f"📅 <b>{to_small_caps('expires on')}:</b> {expiry_date}\n"
            admin_msg += f"🕐 <b>{to_small_caps('expires at')}:</b> {expiry_time}\n"

        admin_msg += f"👨‍💼 <b>{to_small_caps('assigned by')}:</b> <code>{message.from_user.id}</code>"

        await message.reply(admin_msg)

        # Log to log channel
        from plugins.logger import BotLogger
        await BotLogger.log_premium_added(
            client, target_user_id, user_name, plan, duration_text,
            subscription_data['purchased_at'], expires_at,
            message.from_user.id, message.from_user.first_name
        )

        # Notify user
        try:
            user_msg = (
                f"<b>🎉 {to_small_caps('congratulations')} 🎉</b>\n\n"
                f"{to_small_caps('you have been upgraded to')} {plan_info['emoji']} <b>{plan_info['name']}</b> {to_small_caps('plan')}!\n\n"
                f"<b>⏰ {to_small_caps('duration')}:</b> {duration_text}\n"
            )

            if expires_at:
                expiry_date = expires_at.strftime('%d-%m-%Y')
                expiry_time = expires_at.strftime('%I:%M:%S %p')
                user_msg += f"<b>📅 {to_small_caps('expires on')}:</b> {expiry_date}\n"
                user_msg += f"<b>🕐 {to_small_caps('expires at')}:</b> {expiry_time}\n"

            user_msg += f"\n{to_small_caps('use')} /myplan {to_small_caps('to view your plan details')}"

            await client.send_message(target_user_id, user_msg)
        except Exception:
            pass

    except ValueError:
        await message.reply(
            f"<b>❌ {to_small_caps('invalid user id')}</b>\n\n"
            f"{to_small_caps('user id must be a number')}"
        )
    except Exception as e:
        logging.error(f"Error in add_premium_command: {e}")
        logging.error(traceback.format_exc())
        await message.reply(f"<b>❌ {to_small_caps('error')}:</b> <code>{str(e)}</code>")


@Client.on_message(filters.private & filters.command(['remove_premium']))
async def remove_premium_command(client, message):
    """Admin command to remove premium plan from a user"""
    if not await check_owner_sub(message):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.reply(
            f"<b>❌ {to_small_caps('invalid format')}</b>\n\n"
            f"<b>{to_small_caps('usage')}:</b> <code>/remove_premium user_id</code>\n\n"
            f"<b>{to_small_caps('example')}:</b> <code>/remove_premium 123456789</code>"
        )

    try:
        target_user_id = int(args[1])

        if not await db.is_user_exist(target_user_id):
            return await message.reply(
                f"<b>❌ {to_small_caps('user not found')}</b>\n\n"
                f"{to_small_caps('user id')} <code>{target_user_id}</code> {to_small_caps('is not in the database')}"
            )

        subscription = await db.get_subscription(target_user_id)
        old_plan = subscription.get('plan', 'free')

        if old_plan == 'free':
            return await message.reply(
                f"<b>ℹ️ {to_small_caps('user already on free plan')}</b>\n\n"
                f"{to_small_caps('user id')} <code>{target_user_id}</code> {to_small_caps('is already on free plan')}"
            )

        await db.set_subscription(target_user_id, 'free', assigned_by=message.from_user.id)

        # Get user name
        user_doc = await db.col.find_one({'id': int(target_user_id)})
        user_name = user_doc.get('name', 'Unknown') if user_doc else 'Unknown'

        old_plan_info = Config.SUBSCRIPTION_PLANS[old_plan]
        await message.reply(
            f"<b>✅ {to_small_caps('premium removed successfully')}</b>\n\n"
            f"<b>{to_small_caps('user id')}:</b> <code>{target_user_id}</code>\n"
            f"<b>{to_small_caps('old plan')}:</b> {old_plan_info['emoji']} <b>{old_plan_info['name']}</b>\n"
            f"<b>{to_small_caps('new plan')}:</b> 🆓 <b>{to_small_caps('free')}</b>"
        )

        # Log to log channel
        from plugins.logger import BotLogger
        await BotLogger.log_premium_removed(
            client, target_user_id, user_name, old_plan,
            message.from_user.id, message.from_user.first_name
        )

        try:
            await client.send_message(
                target_user_id,
                f"<b>⚠️ {to_small_caps('subscription downgraded')} ⚠️</b>\n\n"
                f"{to_small_caps('your')} {old_plan_info['emoji']} <b>{old_plan_info['name']}</b> {to_small_caps('plan has been downgraded to')} 🆓 <b>{to_small_caps('free')}</b>.\n\n"
                f"{to_small_caps('contact admin for more information')}"
            )
        except Exception:
            pass

    except ValueError:
        await message.reply(
            f"<b>❌ {to_small_caps('invalid user id')}</b>\n\n"
            f"{to_small_caps('user id must be a number')}"
        )
    except Exception as e:
        logging.error(f"Error in remove_premium_command: {e}")
        logging.error(traceback.format_exc())
        await message.reply(f"<b>❌ {to_small_caps('error')}:</b> <code>{str(e)}</code>")


@Client.on_message(filters.private & filters.command(['users']))
async def users_command(client, message):
    """Admin command to list all users with details"""
    if not await check_owner_sub(message):
        return
    from datetime import datetime

    try:
        args = message.text.split()
        page = 1
        if len(args) > 1:
            try:
                page = int(args[1])
            except Exception:
                page = 1

        per_page = 8
        skip = (page - 1) * per_page

        total_users = await db.col.count_documents({})
        total_pages = (total_users + per_page - 1) // per_page

        if page < 1:
            page = 1
        elif page > total_pages and total_pages > 0:
            page = total_pages

        all_users = db.col.find({}).skip(skip).limit(per_page)

        if total_users == 0:
            return await message.reply(
                f"<b>👥 {to_small_caps('users list (page')} {page}/{total_pages})</b>\n"
                f"{to_small_caps('total users')}: {total_users}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>ℹ️ {to_small_caps('no users found')}</b>"
            )

        text = f"<b>👥 {to_small_caps('users list (page')} {page}/{total_pages})</b>\n"
        text += f"{to_small_caps('total users')}: {total_users}\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        user_count = skip
        async for user in all_users:
            user_count += 1
            user_id = user.get('id')
            name = user.get('name', 'Unknown')
            joined_at = user.get('joined_at')
            subscription = user.get('subscription', {})
            plan = subscription.get('plan', 'free')
            status = subscription.get('status', 'active')
            expires_at = subscription.get('expires_at')
            purchased_at = subscription.get('purchased_at')
            assigned_by = subscription.get('assigned_by', 'system')
            ban_status = user.get('ban_status', {})
            is_banned = ban_status.get('is_banned', False)
            last_process = user.get('last_process', {})
            active_tasks = user.get('active_tasks', {})

            plan_info = Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])

            # Determine if user is owner/admin
            role = ""
            if user_id in Config.BOT_OWNER_ID:
                role = " (Owner)" if status == 'lifetime' else ""

            text += f"<b>{user_count}. {name}</b>\n"
            text += f"├─ 👤 {to_small_caps('user id')}: <code>{user_id}</code>\n"
            text += f"├─ 💎 {to_small_caps('plan')}: {plan_info['emoji']} {plan_info['name']}{role}\n"

            # Joined date (convert to IST)
            if joined_at:
                import pytz
                ist = pytz.timezone('Asia/Kolkata')
                if joined_at.tzinfo is None:
                    joined_at = pytz.utc.localize(joined_at)
                joined_ist = joined_at.astimezone(ist)
                joined_str = joined_ist.strftime('%d-%m-%Y')
                joined_time = joined_ist.strftime('%I:%M:%S %p')
                text += f"├─ 📅 {to_small_caps('joined date')}: {joined_str}\n"
                text += f"├─ ⏰ {to_small_caps('joined time')}: {joined_time}\n"

            # Purchased date (only if plan is not free) (convert to IST)
            if plan != 'free' and purchased_at:
                import pytz
                ist = pytz.timezone('Asia/Kolkata')
                if purchased_at.tzinfo is None:
                    purchased_at = pytz.utc.localize(purchased_at)
                purchased_ist = purchased_at.astimezone(ist)
                purchased_str = purchased_ist.strftime('%d-%m-%Y')
                purchased_time = purchased_ist.strftime('%I:%M:%S %p')
                text += f"├─ 💳 {to_small_caps('purchased date')}: {purchased_str}\n"
                text += f"├─ 🕐 {to_small_caps('purchased time')}: {purchased_time}\n"

            # Expiry information (convert to IST)
            if status == 'lifetime':
                text += f"├─ ⏳ {to_small_caps('expiry')}: N/A\n"
            elif expires_at and plan != 'free':
                try:
                    import pytz
                    ist = pytz.timezone('Asia/Kolkata')
                    if expires_at.tzinfo is None:
                        expires_at = pytz.utc.localize(expires_at)
                    expires_ist = expires_at.astimezone(ist)
                    expire_str = expires_ist.strftime('%d-%m-%Y')
                    expire_time = expires_ist.strftime('%I:%M:%S %p')
                    text += f"├─ ⏳ {to_small_caps('expiry date')}: {expire_str}\n"
                    text += f"├─ ⏱️ {to_small_caps('expiry time')}: {expire_time}\n"

                    # Calculate time left or show expired
                    time_diff = expires_at.replace(tzinfo=None) - datetime.utcnow()
                    if time_diff.total_seconds() > 0:
                        days_left = time_diff.days
                        hours_left = time_diff.seconds // 3600
                        minutes_left = (time_diff.seconds % 3600) // 60
                        text += f"├─ ⏰ {to_small_caps('time left')}: {days_left} days, {hours_left} hours, {minutes_left} minutes\n"
                    else:
                        text += f"├─ ⏰ {to_small_caps('status')}: {to_small_caps('expired')}\n"
                except Exception:
                    text += f"├─ ⏳ {to_small_caps('expiry')}: N/A\n"
            else:
                text += f"├─ ⏳ {to_small_caps('expiry')}: N/A\n"

            # Active tasks
            forwarding_count = active_tasks.get('forwarding', 0)
            plan_limit = plan_info.get('features', {}).get('forwarding', {}).get('limit', 1)
            if plan_limit is None:
                text += f"├─ 🔄 {to_small_caps('active')}: {forwarding_count}/∞\n"
            else:
                text += f"├─ 🔄 {to_small_caps('active')}: {forwarding_count}/{plan_limit}\n"

            # Last process
            if last_process.get('type'):
                process_type = last_process.get('type')
                process_time = last_process.get('completed_at')
                process_status = last_process.get('status', 'unknown')
                if process_time:
                    process_str = process_time.strftime('%d-%m-%Y %I:%M:%S %p')
                    text += f"├─ 🔄 {to_small_caps('last process')}: {process_type} ({process_status})\n"
                    text += f"└─ 🕐 {to_small_caps('completed at')}: {process_str}\n"
                else:
                    text += f"└─ 🔄 {to_small_caps('last process')}: {process_type} ({process_status})\n"
            else:
                text += f"└─ 🔄 {to_small_caps('last process')}: {to_small_caps('none')}\n"

            if is_banned:
                text += f"   🚫 <b>{to_small_caps('banned')}</b>\n"

            text += "\n"

        # Create pagination buttons
        buttons = []
        nav_buttons = []

        if page > 1:
            nav_buttons.append(InlineKeyboardButton(f"⏮ {to_small_caps('previous')}", callback_data=f'users_page#{page-1}'))

        nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data='users_page#current'))

        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(f"{to_small_caps('next')} ⏭", callback_data=f'users_page#{page+1}'))

        if nav_buttons:
            buttons.append(nav_buttons)

        await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

    except Exception as e:
        logging.error(f"Error in users_command: {e}")
        logging.error(traceback.format_exc())
        await message.reply(f"<b>❌ {to_small_caps('error')}:</b> <code>{str(e)}</code>")


@Client.on_message(filters.private & filters.command(['pusers']))
async def premium_users_command(client, message):
    """Admin command to list all premium users"""
    if not await check_owner_sub(message):
        return
    from datetime import datetime

    try:
        args = message.text.split()
        page = 1
        if len(args) > 1:
            try:
                page = int(args[1])
            except Exception:
                page = 1

        all_users = await db.get_all_users()

        premium_users_list = []
        total_premium = 0

        async for user in all_users:
            subscription = user.get('subscription', {})
            plan = subscription.get('plan', 'free')
            status = subscription.get('status', 'active')

            if plan != 'free' or status == 'lifetime':
                total_premium += 1
                expires_at = subscription.get('expires_at')
                purchased_at = subscription.get('purchased_at')
                joined_at = user.get('joined_at')
                assigned_by = subscription.get('assigned_by', 'system')
                active_tasks = user.get('active_tasks', {})

                user_info = {
                    'id': user.get('id'),
                    'name': user.get('name', 'Unknown'),
                    'plan': plan,
                    'status': status,
                    'expires_at': expires_at,
                    'purchased_at': purchased_at,
                    'joined_at': joined_at,
                    'assigned_by': assigned_by,
                    'active_tasks': active_tasks.get('forwarding', 0)
                }
                premium_users_list.append(user_info)

        if total_premium == 0:
            return await message.reply(
                f"{to_small_caps('premium users list')} :\n\n"
                f"{to_small_caps('no premium users found')}\n\n"
                f"{to_small_caps('total premium users')} : 0"
            )

        # Pagination
        per_page = 8
        total_pages = (total_premium + per_page - 1) // per_page

        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_users = premium_users_list[start_idx:end_idx]

        text = f"{to_small_caps('premium users list')} :\n"
        text += f"{to_small_caps('page')} {page}/{total_pages}\n\n"

        for idx, user in enumerate(page_users, start_idx + 1):
            plan_info = Config.SUBSCRIPTION_PLANS.get(user['plan'], Config.SUBSCRIPTION_PLANS['free'])

            # Determine role
            role = ""
            if user['id'] in Config.BOT_OWNER_ID and user['status'] == 'lifetime':
                role = " (Owner)"
            elif user['assigned_by'] != 'system' and user['status'] == 'lifetime':
                role = " (Admin)"

            text += f"<b>{idx}. {user['name']}</b>\n"
            text += f"👤 {to_small_caps('user id')} : <code>{user['id']}</code>\n"
            text += f"💎 {to_small_caps('plan')} : {plan_info['name']}{role}\n"

            # Joined date (convert to IST)
            if user['joined_at']:
                import pytz
                ist = pytz.timezone('Asia/Kolkata')
                joined_at = user['joined_at']
                if joined_at.tzinfo is None:
                    joined_at = pytz.utc.localize(joined_at)
                joined_ist = joined_at.astimezone(ist)
                joined_str = joined_ist.strftime('%d-%m-%Y')
                joined_time = joined_ist.strftime('%I:%M:%S %p')
                text += f"📅 {to_small_caps('joined date')} : {joined_str}\n"
                text += f"🕐 {to_small_caps('joined time')} : {joined_time}\n"

            # Purchased date (if applicable) (convert to IST)
            if user['purchased_at']:
                import pytz
                ist = pytz.timezone('Asia/Kolkata')
                purchased_at = user['purchased_at']
                if purchased_at.tzinfo is None:
                    purchased_at = pytz.utc.localize(purchased_at)
                purchased_ist = purchased_at.astimezone(ist)
                purchased_str = purchased_ist.strftime('%d-%m-%Y')
                purchased_time = purchased_ist.strftime('%I:%M:%S %p')
                text += f"💳 {to_small_caps('purchased date')} : {purchased_str}\n"
                text += f"🕐 {to_small_caps('purchased time')} : {purchased_time}\n"

            # Expiry information (convert to IST)
            if user['status'] == 'lifetime':
                text += f"⏳ {to_small_caps('expiry')} : N/A\n"
            elif user['expires_at']:
                try:
                    import pytz
                    ist = pytz.timezone('Asia/Kolkata')
                    expires_at = user['expires_at']
                    if expires_at.tzinfo is None:
                        expires_at = pytz.utc.localize(expires_at)
                    expires_ist = expires_at.astimezone(ist)
                    expire_str = expires_ist.strftime('%d-%m-%Y')
                    expire_time = expires_ist.strftime('%I:%M:%S %p')
                    text += f"⏳ {to_small_caps('expiry date')} : {expire_str}\n"
                    text += f"⏱️ {to_small_caps('expiry time')} : {expire_time}\n"

                    # Calculate time left or show expired
                    time_diff = user['expires_at'].replace(tzinfo=None) - datetime.utcnow()
                    if time_diff.total_seconds() > 0:
                        days_left = time_diff.days
                        hours_left = time_diff.seconds // 3600
                        minutes_left = (time_diff.seconds % 3600) // 60
                        text += f"⏰ {to_small_caps('time left')} : {days_left} days, {hours_left} hours, {minutes_left} minutes\n"
                    else:
                        text += f"⏰ {to_small_caps('status')} : {to_small_caps('expired')}\n"
                except Exception:
                    text += f"⏳ {to_small_caps('expiry')} : N/A\n"
            else:
                text += f"⏳ {to_small_caps('expiry')} : N/A\n"

            # Concurrent tasks - show actual active tasks
            text += f"🔄 {to_small_caps('concurrent')} : {user['active_tasks']}\n"

            text += "\n"

        text += f"{to_small_caps('total premium users')} : {total_premium}"

        # Create pagination buttons
        buttons = []
        nav_buttons = []

        if page > 1:
            nav_buttons.append(InlineKeyboardButton(f"⏮ {to_small_caps('previous')}", callback_data=f'pusers_page#{page-1}'))

        nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data='pusers_page#current'))

        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(f"{to_small_caps('next')} ⏭", callback_data=f'pusers_page#{page+1}'))

        if nav_buttons:
            buttons.append(nav_buttons)

        await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

    except Exception as e:
        logging.error(f"Error in premium_users_command: {e}")
        logging.error(traceback.format_exc())
        await message.reply(f"<b>❌ {to_small_caps('error')}:</b> <code>{str(e)}</code>")



@Client.on_callback_query(filters.regex(r'^users_page#'))
async def users_page_callback(client, query):
    """Handle users list pagination"""
    from datetime import datetime

    user_id = query.from_user.id
    if user_id not in Config.BOT_OWNER_ID:
        return await query.answer(f"❌ {to_small_caps('unauthorized')}", show_alert=True)

    data = query.data.split('#')[1]

    if data == 'current':
        return await query.answer()

    try:
        page = int(data)

        per_page = 8
        skip = (page - 1) * per_page

        total_users = await db.col.count_documents({})
        total_pages = (total_users + per_page - 1) // per_page

        if page < 1:
            page = 1
        elif page > total_pages and total_pages > 0:
            page = total_pages

        all_users = db.col.find({}).skip(skip).limit(per_page)

        if total_users == 0:
            return await query.message.edit_text(
                f"<b>👥 {to_small_caps('users list (page')} {page}/{total_pages})</b>\n"
                f"{to_small_caps('total users')}: {total_users}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>ℹ️ {to_small_caps('no users found')}</b>"
            )

        text = f"<b>👥 {to_small_caps('users list (page')} {page}/{total_pages})</b>\n"
        text += f"{to_small_caps('total users')}: {total_users}\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        user_count = skip
        async for user in all_users:
            user_count += 1
            user_id_item = user.get('id')
            name = user.get('name', 'Unknown')
            joined_at = user.get('joined_at')
            subscription = user.get('subscription', {})
            plan = subscription.get('plan', 'free')
            status = subscription.get('status', 'active')
            expires_at = subscription.get('expires_at')
            purchased_at = subscription.get('purchased_at')
            ban_status = user.get('ban_status', {})
            is_banned = ban_status.get('is_banned', False)
            last_process = user.get('last_process', {})
            active_tasks = user.get('active_tasks', {})

            plan_info = Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])

            role = ""
            if user_id_item in Config.BOT_OWNER_ID:
                role = " (Owner)" if status == 'lifetime' else ""

            text += f"<b>{user_count}. {name}</b>\n"
            text += f"├─ 👤 {to_small_caps('user id')}: <code>{user_id_item}</code>\n"
            text += f"├─ 💎 {to_small_caps('plan')}: {plan_info['emoji']} {plan_info['name']}{role}\n"

            if joined_at:
                import pytz
                ist = pytz.timezone('Asia/Kolkata')
                if joined_at.tzinfo is None:
                    joined_at = pytz.utc.localize(joined_at)
                joined_ist = joined_at.astimezone(ist)
                joined_str = joined_ist.strftime('%d-%m-%Y')
                joined_time = joined_ist.strftime('%I:%M:%S %p')
                text += f"├─ 📅 {to_small_caps('joined date')}: {joined_str}\n"
                text += f"├─ ⏰ {to_small_caps('joined time')}: {joined_time}\n"

            if plan != 'free' and purchased_at:
                import pytz
                ist = pytz.timezone('Asia/Kolkata')
                if purchased_at.tzinfo is None:
                    purchased_at = pytz.utc.localize(purchased_at)
                purchased_ist = purchased_at.astimezone(ist)
                purchased_str = purchased_ist.strftime('%d-%m-%Y')
                purchased_time = purchased_ist.strftime('%I:%M:%S %p')
                text += f"├─ 💳 {to_small_caps('purchased date')}: {purchased_str}\n"
                text += f"├─ 🕐 {to_small_caps('purchased time')}: {purchased_time}\n"

            if status == 'lifetime':
                text += f"├─ ⏳ {to_small_caps('expiry')}: N/A\n"
            elif expires_at and plan != 'free':
                try:
                    import pytz
                    ist = pytz.timezone('Asia/Kolkata')
                    if expires_at.tzinfo is None:
                        expires_at = pytz.utc.localize(expires_at)
                    expires_ist = expires_at.astimezone(ist)
                    expire_str = expires_ist.strftime('%d-%m-%Y')
                    expire_time = expires_ist.strftime('%I:%M:%S %p')
                    text += f"├─ ⏳ {to_small_caps('expiry date')}: {expire_str}\n"
                    text += f"├─ ⏱️ {to_small_caps('expiry time')}: {expire_time}\n"

                    time_diff = expires_at.replace(tzinfo=None) - datetime.utcnow()
                    if time_diff.total_seconds() > 0:
                        days_left = time_diff.days
                        hours_left = time_diff.seconds // 3600
                        minutes_left = (time_diff.seconds % 3600) // 60
                        text += f"├─ ⏰ {to_small_caps('time left')}: {days_left} days, {hours_left} hours, {minutes_left} minutes\n"
                    else:
                        text += f"├─ ⏰ {to_small_caps('status')}: {to_small_caps('expired')}\n"
                except Exception:
                    text += f"├─ ⏳ {to_small_caps('expiry')}: N/A\n"
            else:
                text += f"├─ ⏳ {to_small_caps('expiry')}: N/A\n"

            forwarding_count = active_tasks.get('forwarding', 0)
            plan_limit = plan_info.get('features', {}).get('forwarding', {}).get('limit', 1)
            if plan_limit is None:
                text += f"├─ 🔄 {to_small_caps('active')}: {forwarding_count}/∞\n"
            else:
                text += f"├─ 🔄 {to_small_caps('active')}: {forwarding_count}/{plan_limit}\n"

            if last_process.get('type'):
                process_type = last_process.get('type')
                process_time = last_process.get('completed_at')
                process_status = last_process.get('status', 'unknown')
                if process_time:
                    process_str = process_time.strftime('%d-%m-%Y %I:%M:%S %p')
                    text += f"├─ 🔄 {to_small_caps('last process')}: {process_type} ({process_status})\n"
                    text += f"└─ 🕐 {to_small_caps('completed at')}: {process_str}\n"
                else:
                    text += f"└─ 🔄 {to_small_caps('last process')}: {process_type} ({process_status})\n"
            else:
                text += f"└─ 🔄 {to_small_caps('last process')}: {to_small_caps('none')}\n"

            if is_banned:
                text += f"   🚫 <b>{to_small_caps('banned')}</b>\n"

            text += "\n"

        buttons = []
        nav_buttons = []

        if page > 1:
            nav_buttons.append(InlineKeyboardButton(f"⏮ {to_small_caps('previous')}", callback_data=f'users_page#{page-1}'))

        nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data='users_page#current'))

        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(f"{to_small_caps('next')} ⏭", callback_data=f'users_page#{page+1}'))

        if nav_buttons:
            buttons.append(nav_buttons)

        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)
        await query.answer()

    except Exception as e:
        logging.error(f"Error in users_page_callback: {e}")
        logging.error(traceback.format_exc())
        await query.answer(f"❌ Error: {str(e)}", show_alert=True)


@Client.on_callback_query(filters.regex(r'^pusers_page#'))
async def pusers_page_callback(client, query):
    """Handle premium users list pagination"""
    from datetime import datetime

    user_id = query.from_user.id
    if user_id not in Config.BOT_OWNER_ID:
        return await query.answer(f"❌ {to_small_caps('unauthorized')}", show_alert=True)

    data = query.data.split('#')[1]

    if data == 'current':
        return await query.answer()

    try:
        page = int(data)

        all_users = await db.get_all_users()

        premium_users_list = []
        total_premium = 0

        async for user in all_users:
            subscription = user.get('subscription', {})
            plan = subscription.get('plan', 'free')
            status = subscription.get('status', 'active')

            if plan != 'free' or status == 'lifetime':
                total_premium += 1
                expires_at = subscription.get('expires_at')
                purchased_at = subscription.get('purchased_at')
                joined_at = user.get('joined_at')
                assigned_by = user.get('assigned_by', 'system')
                active_tasks = user.get('active_tasks', {})

                user_info = {
                    'id': user.get('id'),
                    'name': user.get('name', 'Unknown'),
                    'plan': plan,
                    'status': status,
                    'expires_at': expires_at,
                    'purchased_at': purchased_at,
                    'joined_at': joined_at,
                    'assigned_by': assigned_by,
                    'active_tasks': active_tasks.get('forwarding', 0)
                }
                premium_users_list.append(user_info)

        if total_premium == 0:
            return await query.message.edit_text(
                f"{to_small_caps('premium users list')} :\n\n"
                f"{to_small_caps('no premium users found')}\n\n"
                f"{to_small_caps('total premium users')} : 0"
            )

        per_page = 8
        total_pages = (total_premium + per_page - 1) // per_page

        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_users = premium_users_list[start_idx:end_idx]

        text = f"{to_small_caps('premium users list')} :\n"
        text += f"{to_small_caps('page')} {page}/{total_pages}\n\n"

        for idx, user in enumerate(page_users, start_idx + 1):
            plan_info = Config.SUBSCRIPTION_PLANS.get(user['plan'], Config.SUBSCRIPTION_PLANS['free'])

            role = ""
            if user['id'] in Config.BOT_OWNER_ID and user['status'] == 'lifetime':
                role = " (Owner)"
            elif user['assigned_by'] != 'system' and user['status'] == 'lifetime':
                role = " (Admin)"

            text += f"<b>{idx}. {user['name']}</b>\n"
            text += f"👤 {to_small_caps('user id')} : <code>{user['id']}</code>\n"
            text += f"💎 {to_small_caps('plan')} : {plan_info['name']}{role}\n"

            if user['joined_at']:
                import pytz
                ist = pytz.timezone('Asia/Kolkata')
                joined_at = user['joined_at']
                if joined_at.tzinfo is None:
                    joined_at = pytz.utc.localize(joined_at)
                joined_ist = joined_at.astimezone(ist)
                joined_str = joined_ist.strftime('%d-%m-%Y')
                joined_time = joined_ist.strftime('%I:%M:%S %p')
                text += f"📅 {to_small_caps('joined date')} : {joined_str}\n"
                text += f"🕐 {to_small_caps('joined time')} : {joined_time}\n"

            if user['purchased_at']:
                import pytz
                ist = pytz.timezone('Asia/Kolkata')
                purchased_at = user['purchased_at']
                if purchased_at.tzinfo is None:
                    purchased_at = pytz.utc.localize(purchased_at)
                purchased_ist = purchased_at.astimezone(ist)
                purchased_str = purchased_ist.strftime('%d-%m-%Y')
                purchased_time = purchased_ist.strftime('%I:%M:%S %p')
                text += f"💳 {to_small_caps('purchased date')} : {purchased_str}\n"
                text += f"🕐 {to_small_caps('purchased time')} : {purchased_time}\n"

            if user['status'] == 'lifetime':
                text += f"⏳ {to_small_caps('expiry')} : N/A\n"
            elif user['expires_at']:
                try:
                    import pytz
                    ist = pytz.timezone('Asia/Kolkata')
                    expires_at = user['expires_at']
                    if expires_at.tzinfo is None:
                        expires_at = pytz.utc.localize(expires_at)
                    expires_ist = expires_at.astimezone(ist)
                    expire_str = expires_ist.strftime('%d-%m-%Y')
                    expire_time = expires_ist.strftime('%I:%M:%S %p')
                    text += f"⏳ {to_small_caps('expiry date')} : {expire_str}\n"
                    text += f"⏱️ {to_small_caps('expiry time')} : {expire_time}\n"

                    time_diff = user['expires_at'].replace(tzinfo=None) - datetime.utcnow()
                    if time_diff.total_seconds() > 0:
                        days_left = time_diff.days
                        hours_left = time_diff.seconds // 3600
                        minutes_left = (time_diff.seconds % 3600) // 60
                        text += f"⏰ {to_small_caps('time left')} : {days_left} days, {hours_left} hours, {minutes_left} minutes\n"
                    else:
                        text += f"⏰ {to_small_caps('status')} : {to_small_caps('expired')}\n"
                except Exception:
                    text += f"⏳ {to_small_caps('expiry')} : N/A\n"
            else:
                text += f"⏳ {to_small_caps('expiry')} : N/A\n"

            # Concurrent tasks - show actual active tasks
            text += f"🔄 {to_small_caps('concurrent')} : {user['active_tasks']}\n"

            text += "\n"

        text += f"{to_small_caps('total premium users')} : {total_premium}"

        buttons = []
        nav_buttons = []

        if page > 1:
            nav_buttons.append(InlineKeyboardButton(f"⏮ {to_small_caps('previous')}", callback_data=f'pusers_page#{page-1}'))

        nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data='pusers_page#current'))

        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(f"{to_small_caps('next')} ⏭", callback_data=f'pusers_page#{page+1}'))

        if nav_buttons:
            buttons.append(nav_buttons)

        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)
        await query.answer()

    except Exception as e:
        logging.error(f"Error in pusers_page_callback: {e}")
        logging.error(traceback.format_exc())
        await query.answer(f"❌ Error: {str(e)}", show_alert=True)