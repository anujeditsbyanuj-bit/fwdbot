from database import db
from config import Config
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import logging

@Client.on_message(filters.private & filters.command(['referral']))
async def referral_command(client, message):
    """Show referral information and options"""
    user_id = message.from_user.id
    
    await db.ensure_referral_data(user_id)
    
    referral_info = await db.get_referral_info(user_id)
    
    if not referral_info or not referral_info.get('code'):
        return await message.reply("❌ ᴇʀʀᴏʀ ʟᴏᴀᴅɪɴɢ ʀᴇғᴇʀʀᴀʟ ɪɴғᴏʀᴍᴀᴛɪᴏɴ!")
    
    bot_username = client.username if client.username else "bot"
    referral_link = f"https://t.me/{bot_username}?start=refer_{referral_info['code']}"
    
    ftm_bucks = referral_info.get('ftm_bucks', 0)
    total_referrals = referral_info.get('total_referrals', 0)
    
    text = (
        f"🎁 <b>ʀᴇғᴇʀʀᴀʟ ᴘʀᴏɢʀᴀᴍ</b>\n\n"
        f"💰 <b>ғᴛᴍʙᴜᴄᴋs ʙᴀʟᴀɴᴄᴇ:</b> <code>{ftm_bucks}</code>\n"
        f"👥 <b>ᴛᴏᴛᴀʟ ʀᴇғᴇʀʀᴀʟs:</b> <code>{total_referrals}</code>\n\n"
        f"🔗 <b>ʏᴏᴜʀ ʀᴇғᴇʀʀᴀʟ ʟɪɴᴋ:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"<b>ʜᴏᴡ ɪᴛ ᴡᴏʀᴋs:</b>\n"
        f"• sʜᴀʀᴇ ʏᴏᴜʀ ʀᴇғᴇʀʀᴀʟ ʟɪɴᴋ\n"
        f"• ᴡʜᴇɴ sᴏᴍᴇᴏɴᴇ ᴊᴏɪɴs, ʏᴏᴜ ɢᴇᴛ <b>+{Config.REFERRAL_REWARD} ғᴛᴍʙᴜᴄᴋs</b>\n"
        f"• ᴛʜᴇʏ ɢᴇᴛ <b>1-ᴅᴀʏ ᴘʟᴜs ᴘʟᴀɴ</b> ᴛʀɪᴀʟ\n\n"
        f"<b>ʀᴇᴅᴇᴇᴍ ʀᴇᴡᴀʀᴅs:</b>\n"
        f"• 1000 ғᴛᴍʙᴜᴄᴋs → 30-ᴅᴀʏ ᴘʟᴜs ᴘʟᴀɴ\n"
        f"• 2000 ғᴛᴍʙᴜᴄᴋs → 30-ᴅᴀʏ ᴘʀᴏ ᴘʟᴀɴ\n"
        f"• 5000 ғᴛᴍʙᴜᴄᴋs → 30-ᴅᴀʏ ɪɴғɪɴɪᴛʏ ᴘʟᴀɴ"
    )
    
    buttons = [
        [InlineKeyboardButton('👥 ᴠɪᴇᴡ ʀᴇғᴇʀʀᴇᴅ ᴜsᴇʀs', callback_data='referral#view_referred')],
        [InlineKeyboardButton('💰 ʀᴇᴅᴇᴇᴍ ғᴛᴍʙᴜᴄᴋs', callback_data='referral#redeem_menu')],
        [InlineKeyboardButton('🔄 ʀᴇғʀᴇsʜ', callback_data='referral#refresh')],
        [InlineKeyboardButton('↩ ʙᴀᴄᴋ', callback_data='back')]
    ]
    
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_message(filters.command("referral_list") & filters.private)
async def referral_list_command(client, message):
    """
    Show referral list/leaderboard for bot owner, or referred users for a specific user
    Usage:
    - /referral_list - Show your referrals (all users)
    - /referral_list [user_id] - Show specific user's referrals (owner only)
    """
    try:
        requesting_user_id = message.from_user.id
        is_owner = requesting_user_id in Config.BOT_OWNER_ID
        args = message.command[1:] if len(message.command) > 1 else []
        
        # Owner only: View leaderboard with no args
        if is_owner and not args:
            await show_referral_list(client, message, 0)
            return
        
        # Parse target user ID if provided
        target_user_id = None
        if args and args[0].isdigit():
            target_user_id = int(args[0])
            # Only owner can view other users' referrals
            if not is_owner:
                return await message.reply("❌ ᴏɴʟʏ ʙᴏᴛ ᴀᴅᴍɪɴ ᴄᴀɴ ᴠɪᴇᴡ ᴜsᴇʀ ʀᴇғᴇʀʀᴀʟs!")
        else:
            # If no args, show own referrals
            target_user_id = requesting_user_id
        
        # Show referrals for target user
        await show_referred_users(client, message, target_user_id, 0)
        
    except Exception as e:
        logging.error(f"Error in referral_list_command: {e}")
        await message.reply(f"❌ ᴇʀʀᴏʀ: {str(e)}")

async def show_referral_list(client, message, page):
    users_per_page = 10
    skip = page * users_per_page
    
    # Get users with at least one referral
    cursor = db.col.find({'referral.total_referrals': {'$gt': 0}}).sort('referral.total_referrals', -1).skip(skip).limit(users_per_page)
    users = [u async for u in cursor]
    total_users = await db.col.count_documents({'referral.total_referrals': {'$gt': 0}})
    
    if not users:
        text = "❌ ɴᴏ ʀᴇғᴇʀʀᴀʟs ғᴏᴜɴᴅ ʏᴇᴛ!"
        if isinstance(message, CallbackQuery):
            return await message.answer(text, show_alert=True)
        return await message.reply(text)

    text = f"👥 <b>ʀᴇғᴇʀʀᴀʟ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ (ᴘᴀɢᴇ {page + 1})</b>\n\n"
    for i, user in enumerate(users, start=skip + 1):
        name = user.get('name', 'Unknown')
        uid = user.get('id')
        count = user.get('referral', {}).get('total_referrals', 0)
        bucks = user.get('referral', {}).get('ftm_bucks', 0)
        text += f"{i}. <b>{name}</b> (<code>{uid}</code>)\n   ┗ 👥 {count} ʀᴇғs | 💰 {bucks} ʙᴜᴄᴋs\n\n"
    
    buttons = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ ᴘʀᴇᴠ", callback_data=f"reflist#{page-1}"))
    if (page + 1) * users_per_page < total_users:
        nav_buttons.append(InlineKeyboardButton("ɴᴇxᴛ ➡️", callback_data=f"reflist#{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([InlineKeyboardButton("🔄 ʀᴇғʀᴇsʜ", callback_data=f"reflist#{page}")])
    buttons.append([InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="back")])
    
    markup = InlineKeyboardMarkup(buttons)
    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=markup)
    else:
        await message.reply(text, reply_markup=markup)

async def show_referred_users(client, message, user_id, page):
    """Show all users referred by a specific user with detailed information"""
    try:
        users_per_page = 8
        skip = page * users_per_page
        user_id = int(user_id)
        
        # Get the user's document to fetch their referred_users array
        user = await db.col.find_one({'id': user_id})
        if not user:
            text = f"❌ ᴜsᴇʀ <code>{user_id}</code> ɴᴏᴛ ғᴏᴜɴᴅ!"
            if isinstance(message, CallbackQuery):
                return await message.answer(text, show_alert=True)
            return await message.reply(text)
        
        # Convert user to dict if needed
        if not isinstance(user, dict):
            user = dict(user)
        
        # Safely get referral data
        referral_data = user.get('referral', {})
        
        # Handle Int64 and other non-dict types
        if not isinstance(referral_data, dict):
            referral_data = {}
        
        # Get referred users list
        referred_users_raw = referral_data.get('referred_users', [])
        
        # Ensure it's a list
        if not isinstance(referred_users_raw, list):
            referred_users_raw = []
        
        # Convert each item to user data
        referred_users = []
        for item in referred_users_raw:
            if isinstance(item, dict):
                referred_users.append(item)
            else:
                # Item is a user ID (int) - fetch user from database
                try:
                    referred_user_id = int(item)
                    referred_user = await db.col.find_one({'id': referred_user_id})
                    if referred_user:
                        referred_users.append({
                            'id': referred_user_id,
                            'name': referred_user.get('name', 'Unknown'),
                            'referred_at': 'Unknown'  # Legacy data doesn't have timestamp
                        })
                except Exception:
                    pass  # Skip malformed items
        
        total_referred = len(referred_users)
        
        if not referred_users:
            user_name = user.get('name', 'Unknown')
            text = f"❌ <b>{user_name}</b> ʜᴀs ɴᴏ ʀᴇғᴇʀʀᴇᴅ ᴜsᴇʀs ʏᴇᴛ!"
            if isinstance(message, CallbackQuery):
                return await message.answer(text, show_alert=True)
            return await message.reply(text)
        
        # Sort by referred date (newest first)
        referred_users_sorted = sorted(referred_users, key=lambda x: x.get('referred_at', '') if isinstance(x, dict) else '', reverse=True)
        page_users = referred_users_sorted[skip:skip + users_per_page]
        
        user_name = user.get('name', 'Unknown')
        text = f"👥 <b>ʀᴇғᴇʀʀᴇᴅ ʙʏ {user_name}</b> (ᴘᴀɢᴇ {page + 1})\n\n"
        text += f"<b>ᴛᴏᴛᴀʟ ʀᴇғᴇʀʀᴀʟs: {total_referred}</b>\n\n"
        
        for i, referred_user in enumerate(page_users, start=skip + 1):
            # Ensure referred_user is a dict
            if not isinstance(referred_user, dict):
                continue
            
            ref_name = str(referred_user.get('name', 'Unknown'))
            ref_id = referred_user.get('id', 'N/A')
            ref_date = referred_user.get('referred_at', 'Unknown')
            
            # Format the date nicely
            try:
                if isinstance(ref_date, str):
                    # Try parsing if it's a string
                    from datetime import datetime
                    dt = datetime.fromisoformat(ref_date.replace('Z', '+00:00'))
                    ref_date_str = dt.strftime('%d %b %Y, %H:%M UTC')
                else:
                    ref_date_str = str(ref_date)
            except Exception:
                ref_date_str = str(ref_date)
            
            # Create tg:// link for direct message
            try:
                user_id_int = int(ref_id)
                dm_link = f"<a href=\"tg://user?id={user_id_int}\">{ref_name}</a>"
            except Exception:
                dm_link = ref_name
            
            text += f"{i}. <b>{dm_link}</b> (<code>{ref_id}</code>)\n"
            text += f"   ⏰ ʀᴇғᴇʀʀᴇᴅ: <code>{ref_date_str}</code>\n\n"
        
        # Navigation buttons only
        buttons = []
        
        # Add navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ ᴘʀᴇᴠ", callback_data=f"refusers#{user_id}#{page-1}"))
        if (page + 1) * users_per_page < total_referred:
            nav_buttons.append(InlineKeyboardButton("ɴᴇxᴛ ➡️", callback_data=f"refusers#{user_id}#{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([InlineKeyboardButton("🔄 ʀᴇғʀᴇsʜ", callback_data=f"refusers#{user_id}#{page}")])
        buttons.append([InlineKeyboardButton("↩ ʙᴀᴄᴋ", callback_data="referral#refresh")])
        
        markup = InlineKeyboardMarkup(buttons)
        if isinstance(message, CallbackQuery):
            try:
                await message.message.edit_text(text, reply_markup=markup)
            except Exception as edit_error:
                # Handle MESSAGE_NOT_MODIFIED error
                if "MESSAGE_NOT_MODIFIED" in str(edit_error):
                    await message.answer("✅ ʀᴇғʀᴇsʜᴇᴅ!", show_alert=True)
                else:
                    raise
        else:
            await message.reply(text, reply_markup=markup)
    
    except Exception as e:
        import traceback
        logging.error(f"Error in show_referred_users: {e}")
        logging.error(traceback.format_exc())
        text = f"❌ ᴇʀʀᴏʀ ʟᴏᴀᴅɪɴɢ ʀᴇғᴇʀʀᴀʟs: {str(e)}"
        if isinstance(message, CallbackQuery):
            await message.answer(text, show_alert=True)
        else:
            await message.reply(text)

@Client.on_callback_query(filters.regex(r'^reflist'))
async def reflist_callback(client, query: CallbackQuery):
    page = int(query.data.split('#')[1])
    await show_referral_list(client, query, page)

@Client.on_callback_query(filters.regex(r'^refusers'))
async def refusers_callback(client, query: CallbackQuery):
    """Handle referred users pagination"""
    parts = query.data.split('#')
    user_id = int(parts[1])
    page = int(parts[2])
    await show_referred_users(client, query, user_id, page)

@Client.on_callback_query(filters.regex(r'^referral'))
async def referral_callback(client, query: CallbackQuery):
    """Handle referral callback queries"""
    user_id = query.from_user.id
    data = query.data.split('#')
    action = data[1] if len(data) > 1 else None
    
    await db.ensure_referral_data(user_id)
    
    if action == 'refresh':
        await query.answer("🔄 ʀᴇғʀᴇsʜɪɴɢ...")
        
        referral_info = await db.get_referral_info(user_id)
        
        if not referral_info or not referral_info.get('code'):
            return await query.answer("❌ ᴇʀʀᴏʀ ʟᴏᴀᴅɪɴɢ ʀᴇғᴇʀʀᴀʟ ɪɴғᴏʀᴍᴀᴛɪᴏɴ!", show_alert=True)
        
        bot_username = client.username if client.username else "bot"
        referral_link = f"https://t.me/{bot_username}?start=refer_{referral_info['code']}"
        
        ftm_bucks = referral_info.get('ftm_bucks', 0)
        total_referrals = referral_info.get('total_referrals', 0)
        
        text = (
            f"🎁 <b>ʀᴇғᴇʀʀᴀʟ ᴘʀᴏɢʀᴀᴍ</b>\n\n"
            f"💰 <b>ғᴛᴍʙᴜᴄᴋs ʙᴀʟᴀɴᴄᴇ:</b> <code>{ftm_bucks}</code>\n"
            f"👥 <b>ᴛᴏᴛᴀʟ ʀᴇғᴇʀʀᴀʟs:</b> <code>{total_referrals}</code>\n\n"
            f"🔗 <b>ʏᴏᴜʀ ʀᴇғᴇʀʀᴀʟ ʟɪɴᴋ:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            f"<b>ʜᴏᴡ ɪᴛ ᴡᴏʀᴋs:</b>\n"
            f"• sʜᴀʀᴇ ʏᴏᴜʀ ʀᴇғᴇʀʀᴀʟ ʟɪɴᴋ\n"
            f"• ᴡʜᴇɴ sᴏᴍᴇᴏɴᴇ ᴊᴏɪɴs, ʏᴏᴜ ɢᴇᴛ <b>+100 ғᴛᴍʙᴜᴄᴋs</b>\n"
            f"• ᴛʜᴇʏ ɢᴇᴛ <b>1-ᴅᴀʏ ᴘʟᴜs ᴘʟᴀɴ</b> ᴛʀɪᴀʟ\n\n"
            f"<b>ʀᴇᴅᴇᴇᴍ ʀᴇᴡᴀʀᴅs:</b>\n"
            f"• 1000 ғᴛᴍʙᴜᴄᴋs → 30-ᴅᴀʏ ᴘʟᴜs ᴘʟᴀɴ\n"
            f"• 2000 ғᴛᴍʙᴜᴄᴋs → 30-ᴅᴀʏ ᴘʀᴏ ᴘʟᴀɴ\n"
            f"• 5000 ғᴛᴍʙᴜᴄᴋs → 30-ᴅᴀʏ ɪɴғɪɴɪᴛʏ ᴘʟᴀɴ"
        )
        
        buttons = [
            [InlineKeyboardButton('👥 ᴠɪᴇᴡ ʀᴇғᴇʀʀᴇᴅ ᴜsᴇʀs', callback_data='referral#view_referred')],
            [InlineKeyboardButton('💰 ʀᴇᴅᴇᴇᴍ ғᴛᴍʙᴜᴄᴋs', callback_data='referral#redeem_menu')],
            [InlineKeyboardButton('🔄 ʀᴇғʀᴇsʜ', callback_data='referral#refresh')],
            [InlineKeyboardButton('↩ ʙᴀᴄᴋ', callback_data='back')]
        ]
        
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    
    elif action == 'view_referred':
        await show_referred_users(client, query, user_id, 0)
    
    elif action == 'redeem_menu':
        referral_info = await db.get_referral_info(user_id)
        ftm_bucks = referral_info.get('ftm_bucks', 0)
        
        text = (
            f"💰 <b>ʀᴇᴅᴇᴇᴍ ғᴛᴍʙᴜᴄᴋs</b>\n\n"
            f"ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ: <code>{ftm_bucks}</code> ғᴛᴍʙᴜᴄᴋs\n\n"
            f"sᴇʟᴇᴄᴛ ᴀ ᴘʟᴀɴ ᴛᴏ ʀᴇᴅᴇᴇᴍ:"
        )
        
        buttons = []
        
        plus_emoji = "✅" if ftm_bucks >= 1000 else "❌"
        pro_emoji = "✅" if ftm_bucks >= 2000 else "❌"
        infinity_emoji = "✅" if ftm_bucks >= Config.INFINITY_REDEEM_COST else "❌"
        
        buttons.append([
            InlineKeyboardButton(
                f'{plus_emoji} ᴘʟᴜs ᴘʟᴀɴ (1000 ғᴛᴍʙᴜᴄᴋs)',
                callback_data='referral#redeem_plus'
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                f'{pro_emoji} ᴘʀᴏ ᴘʟᴀɴ (2000 ғᴛᴍʙᴜᴄᴋs)',
                callback_data='referral#redeem_pro'
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                f'{infinity_emoji} ɪɴғɪɴɪᴛʏ ᴘʟᴀɴ ({Config.INFINITY_REDEEM_COST} ғᴛᴍʙᴜᴄᴋs)',
                callback_data='referral#redeem_infinity'
            )
        ])
        buttons.append([InlineKeyboardButton('↩ ʙᴀᴄᴋ', callback_data='referral#refresh')])
        
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    
    elif action.startswith('redeem_'):
        plan = action.replace('redeem_', '')
        
        costs = {
            'plus': 1000,
            'pro': 2000,
            'infinity': Config.INFINITY_REDEEM_COST
        }
        
        cost = costs.get(plan)
        if not cost:
            return await query.answer("❌ ɪɴᴠᴀʟɪᴅ ᴘʟᴀɴ!", show_alert=True)
        
        referral_info = await db.get_referral_info(user_id)
        ftm_bucks = referral_info.get('ftm_bucks', 0)
        
        if ftm_bucks < cost:
            return await query.answer(
                f"❌ ɪɴsᴜғғɪᴄɪᴇɴᴛ ғᴛᴍʙᴜᴄᴋs!\n\n"
                f"ʏᴏᴜ ɴᴇᴇᴅ {cost} ғᴛᴍʙᴜᴄᴋs, ʙᴜᴛ ʏᴏᴜ ʜᴀᴠᴇ {ftm_bucks}.",
                show_alert=True
            )
        
        success = await db.deduct_ftm_bucks(user_id, cost)
        if not success:
            return await query.answer("❌ ᴇʀʀᴏʀ ᴅᴇᴅᴜᴄᴛɪɴɢ ғᴛᴍʙᴜᴄᴋs!", show_alert=True)
        
        from datetime import datetime, timedelta
        expires_at = datetime.utcnow() + timedelta(days=30)
        await db.set_subscription(user_id, plan, expires_at=expires_at, assigned_by='ftmbucks_redemption')
        
        new_balance = ftm_bucks - cost
        
        plan_names = {
            'plus': 'ᴘʟᴜs',
            'pro': 'ᴘʀᴏ',
            'infinity': 'ɪɴғɪɴɪᴛʏ'
        }
        
        await query.message.edit_text(
            f"✅ <b>ʀᴇᴅᴇᴍᴘᴛɪᴏɴ sᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
            f"🎉 ʏᴏᴜ'ᴠᴇ ʀᴇᴅᴇᴇᴍᴇᴅ <b>30-ᴅᴀʏ {plan_names[plan]} ᴘʟᴀɴ</b>!\n\n"
            f"💰 ᴄᴏsᴛ: <code>{cost}</code> ғᴛᴍʙᴜᴄᴋs\n"
            f"💵 ɴᴇᴡ ʙᴀʟᴀɴᴄᴇ: <code>{new_balance}</code> ғᴛᴍʙᴜᴄᴋs\n"
            f"⏰ ᴇxᴘɪʀᴇs: {expires_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"ᴜsᴇ /myplan ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ ᴘʟᴀɴ ᴅᴇᴛᴀɪʟs!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('💳 ᴍʏ ᴘʟᴀɴ', callback_data='sub#my_plan')],
                [InlineKeyboardButton('🎁 ʀᴇғᴇʀʀᴀʟ', callback_data='referral#refresh')],
                [InlineKeyboardButton('↩ ʙᴀᴄᴋ', callback_data='back')]
            ])
        )
        
        try:
            from plugins.logger import BotLogger
            user_name = query.from_user.first_name or "User"
            await BotLogger.log_ftmbucks_redemption(
                client, user_id, user_name, plan, cost, new_balance
            )
        except Exception as e:
            logging.error(f"Error logging redemption: {e}")