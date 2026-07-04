
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import Config, temp
from translation import Translation
from database import db
import logging

# Approval callback handlers
@Client.on_callback_query(filters.regex(r'^approve_user_'))
async def approve_user_callback(bot, query):
    # Check if user is owner
    if query.from_user.id not in Config.BOT_OWNER_ID:
        return await query.answer("❌ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ!", show_alert=True)
    
    user_id = int(query.data.split('_')[-1])
    
    # Update approval status in database
    await db.set_user_approval(user_id, approved=True, declined=False)
    
    # Notify user
    try:
        user_info = await bot.get_users(user_id)
        await bot.send_message(user_id, Translation.APPROVED_MSG)
        
        # Update owner message
        owner_msg = Translation.OWNER_APPROVED.format(
            name=user_info.first_name,
            username=user_info.username or "ɴᴏɴᴇ"
        )
        await query.message.edit_text(owner_msg)
        await query.answer("✅ ᴀᴘᴘʀᴏᴠᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!", show_alert=True)
    except Exception as e:
        logging.error(f"Error approving user: {e}")
        await query.answer("❌ ᴇʀʀᴏʀ ᴀᴘᴘʀᴏᴠɪɴɢ ᴜsᴇʀ!", show_alert=True)

@Client.on_callback_query(filters.regex(r'^decline_user_'))
async def decline_user_callback(bot, query):
    # Check if user is owner
    if query.from_user.id not in Config.BOT_OWNER_ID:
        return await query.answer("❌ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ!", show_alert=True)
    
    user_id = int(query.data.split('_')[-1])
    
    # Update approval status in database
    await db.set_user_approval(user_id, approved=False, declined=True)
    
    # Notify user
    try:
        user_info = await bot.get_users(user_id)
        await bot.send_message(user_id, Translation.DECLINED_MSG)
        
        # Update owner message
        owner_msg = Translation.OWNER_DECLINED.format(
            name=user_info.first_name,
            username=user_info.username or "ɴᴏɴᴇ"
        )
        await query.message.edit_text(owner_msg)
        await query.answer("❌ ᴅᴇᴄʟɪɴᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!", show_alert=True)
    except Exception as e:
        logging.error(f"Error declining user: {e}")
        await query.answer("❌ ᴇʀʀᴏʀ ᴅᴇᴄʟɪɴɪɴɢ ᴜsᴇʀ!", show_alert=True)


import re
import asyncio 
from .utils import STS
from database import db
from config import temp, Config
from translation import Translation
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait 
from pyrogram.errors.exceptions.not_acceptable_406 import ChannelPrivate as PrivateChat
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified, ChannelPrivate
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
 
#===================Run Function===================#

@Client.on_message(filters.private & filters.command(["fwd", "forward"]))
async def run(bot, message):
    from datetime import datetime
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from .subscription import require_forwarding
    
    buttons = []
    btn_data = {}
    user_id = message.from_user.id
    
    # Check subscription permission
    has_permission, error_message = await require_forwarding(user_id)
    if not has_permission:
        return await message.reply(error_message)
    
    # Note: Task counter is incremented in regix.py when actual forwarding starts
    # Not here, to avoid stuck counters from early returns
    
    # Check surveillance mode
    if Config.SURVEILLANCE_MODE:
        # Check approval status from database
        approval_status = await db.get_user_approval(user_id)
        
        if approval_status.get('declined'):
            return await message.reply(Translation.DECLINED_MSG)
        
        if approval_status.get('waiting'):
            return await message.reply(Translation.WAITING_APPROVAL)
        
        if not approval_status.get('approved'):
            # Ask for password
            try:
                password_prompt = await bot.ask(message.chat.id, Translation.PASSWORD_MSG, timeout=60)
                if password_prompt.text and password_prompt.text.startswith('/'):
                    return await message.reply(Translation.CANCEL)
                
                if password_prompt.text != Config.SURVEILLANCE_PASSWORD:
                    return await message.reply(Translation.PASSWORD_INCORRECT)
                
                await message.reply(Translation.PASSWORD_VERIFIED)
            except Exception as e:
                return await message.reply(f"<b>❌ ᴛɪᴍᴇᴏᴜᴛ ʜᴏ ɢᴀʏᴀ ʙʜᴀɪ! 😅\n\nᴅᴏʙᴀᴀʀᴀ ᴛʀʏ ᴋᴀʀᴏ /fwd</b>")
            
            # Set waiting status in database
            await db.set_user_approval(user_id, approved=False, declined=False)
            await db.col.update_one(
                {'id': int(user_id)}, 
                {'$set': {'approval_status.waiting': True}},
                upsert=True
            )
            
            # Send approval request to owner
            user = message.from_user
            approval_text = Translation.APPROVAL_REQUEST.format(
                name=user.first_name + (" " + user.last_name if user.last_name else ""),
                username=user.username or "ɴᴏɴᴇ",
                user_id=user_id,
                lang=user.language_code or "ᴜɴᴋɴᴏᴡɴ",
                time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            approval_buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ ᴀᴘᴘʀᴏᴠᴇ", callback_data=f"approve_user_{user_id}"),
                    InlineKeyboardButton("❌ ᴅᴇᴄʟɪɴᴇ", callback_data=f"decline_user_{user_id}")
                ]
            ])
            
            # Send to owner notify chat or first owner
            notify_chat = Config.OWNER_NOTIFY_CHAT if Config.OWNER_NOTIFY_CHAT else Config.BOT_OWNER_ID[0]
            try:
                await bot.send_message(notify_chat, approval_text, reply_markup=approval_buttons)
            except Exception as e:
                logging.error(f"Failed to send approval request: {e}")
            
            return await message.reply(Translation.WAITING_APPROVAL)
    
    _bot = await db.get_bot(user_id)
    if not _bot:
      return await message.reply("<code>You didn't added any bot. Please add a bot using /settings !</code>")
    channels = await db.get_user_channels(user_id)
    if not channels:
       return await message.reply_text("please set a to channel in /settings before forwarding")
    config = await db.get_configs(user_id)
    pi_mode_enabled = config.get('ftm_pi_mode', False)
    selected_targets = []
    if len(channels) > 1:
       if pi_mode_enabled:
          channel_lines = []
          for idx, channel in enumerate(channels, start=1):
             topic_suffix = f" (topic {channel['thread_id']})" if channel.get('thread_id') else ""
             channel_lines.append(f"{idx}. {channel['title']}{topic_suffix}")
          prompt = (
             f"{Translation.TO_MSG.format(_bot['name'], _bot['username'])}\n\n"
             f"<i>Send target numbers separated by spaces/commas (e.g. 1 3) or type <code>all</code>.</i>\n\n"
             + "\n".join(channel_lines)
          )
          _toid = await bot.ask(message.chat.id, prompt, reply_markup=ReplyKeyboardRemove())
          if _toid.text.startswith(('/', 'cancel')):
             return await message.reply_text(Translation.CANCEL, reply_markup=ReplyKeyboardRemove())
          selection = _toid.text.strip().lower()
          if selection in {"all", "*"}:
             selected_targets = channels
          else:
             indexes = {int(i) for i in re.split(r"[,\s]+", selection) if i.isdigit()}
             if not indexes:
                return await message.reply_text("wrong channel choosen !", reply_markup=ReplyKeyboardRemove())
             invalid_indexes = [i for i in indexes if i < 1 or i > len(channels)]
             if invalid_indexes:
                return await message.reply_text("wrong channel choosen !", reply_markup=ReplyKeyboardRemove())
             selected_targets = [channels[i - 1] for i in sorted(indexes)]
       else:
          for channel in channels:
             topic_suffix = " (topic)" if channel.get('thread_id') else ""
             buttons.append([KeyboardButton(f"{channel['title']}{topic_suffix}")])
             btn_data[f"{channel['title']}{topic_suffix}"] = channel['chat_id']
          buttons.append([KeyboardButton("cancel")]) 
          _toid = await bot.ask(message.chat.id, Translation.TO_MSG.format(_bot['name'], _bot['username']), reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True))
          if _toid.text.startswith(('/', 'cancel')):
             return await message.reply_text(Translation.CANCEL, reply_markup=ReplyKeyboardRemove())
          to_title = _toid.text
          toid = btn_data.get(to_title)
          if not toid:
             return await message.reply_text("wrong channel choosen !", reply_markup=ReplyKeyboardRemove())
          selected_targets = [channel for channel in channels if channel['chat_id'] == toid]
    else:
       selected_targets = channels
    toid = selected_targets[0]['chat_id']
    to_title = selected_targets[0]['title']
    to_thread_id = selected_targets[0].get('thread_id')
    if to_thread_id:
       to_title = f"{to_title} (topic {to_thread_id})"
    to_list = [
       {
          "chat_id": channel['chat_id'],
          "thread_id": channel.get('thread_id'),
          "title": channel.get('title')
       }
       for channel in selected_targets
    ]
    if len(to_list) > 1:
       to_title = f"{to_title} + {len(to_list) - 1} more"
    fromid = await bot.ask(message.chat.id, Translation.FROM_MSG, reply_markup=ReplyKeyboardRemove())
    if fromid.text and fromid.text.startswith('/'):
        await message.reply(Translation.CANCEL)
        return 
    if fromid.text and not fromid.forward_date:
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(fromid.text.replace("?single", ""))
        if not match:
            return await message.reply('Invalid link')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id = int(("-100" + chat_id))
        # If chat_id is a username string, try to get the chat to convert it to ID
        else:
            try:
                chat = await bot.get_chat(chat_id)
                chat_id = chat.id
            except Exception:
                return await message.reply('Invalid chat username or ID')
    elif fromid.forward_from_chat.type in [enums.ChatType.CHANNEL]:
        last_msg_id = fromid.forward_from_message_id
        # Always use the ID, not the username
        chat_id = fromid.forward_from_chat.id
        if last_msg_id == None:
           return await message.reply_text("**This may be a forwarded message from a group and sended by anonymous admin. instead of this please send last message link from group**")
    else:
        await message.reply_text("**invalid !**")
        return 
    try:
        title = (await bot.get_chat(chat_id)).title
  #  except ChannelInvalid:
        #return await fromid.reply("**Given source chat is copyrighted channel/group. you can't forward messages from there**")
    except (PrivateChat, ChannelPrivate, ChannelInvalid):
        title = "private" if fromid.text else fromid.forward_from_chat.title
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        return await message.reply(f'Errors - {e}')
    skipno = await bot.ask(message.chat.id, Translation.SKIP_MSG)
    if skipno.text.startswith('/'):
        await message.reply(Translation.CANCEL)
        return
    forward_id = f"{user_id}-{skipno.id}"
    buttons = [[
        InlineKeyboardButton('Yes', callback_data=f"start_public_{forward_id}"),
        InlineKeyboardButton('No', callback_data="close_btn")
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply_text(
        text=Translation.DOUBLE_CHECK.format(botname=_bot['name'], botuname=_bot['username'], from_chat=title, to_chat=to_title, skip=skipno.text),
        disable_web_page_preview=True,
        reply_markup=reply_markup
    )
    STS(forward_id).store(chat_id, toid, int(skipno.text), int(last_msg_id), to_thread_id=to_thread_id, to_list=to_list)
