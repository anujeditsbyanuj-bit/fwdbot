import os
import sys 
import math
import time
import asyncio 
import logging
from .utils import STS
from database import db 
from .test import CLIENT , start_clone_bot
from .ftm_manager import apply_ftm_transformations
from config import Config, temp
from translation import Translation
from pyrogram import Client, filters, enums 
#from pyropatch.utils import unpack_new_file_id
from pyrogram.errors import FloodWait, MessageNotModified, RPCError
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message 

CLIENT = CLIENT()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
TEXT = Translation.TEXT

def get_target_payloads(sts):
    targets = sts.get('TO_LIST') or []
    if targets:
        return targets
    return [{
        "chat_id": sts.get('TO'),
        "thread_id": sts.get('TO_THREAD_ID')
    }]

@Client.on_callback_query(filters.regex(r'^start_public'))
async def pub_(bot, message):
    # Save callback query message to avoid variable shadowing in the loop
    callback_query = message
    
    user = message.from_user.id
    temp.CANCEL[user] = False
    frwd_id = message.data.split("_")[2]
    if temp.lock.get(user) and str(temp.lock.get(user))=="True":
      return await message.answer("please wait until previous task complete", show_alert=True)
    sts = STS(frwd_id)
    if not sts.verify():
      await message.answer("your are clicking on my old button", show_alert=True)
      return await message.message.delete()
    i = sts.get(full=True)
    target_payloads = get_target_payloads(sts)
    target_chat_ids = [target["chat_id"] for target in target_payloads if target.get("chat_id") is not None]
    if any(chat_id in temp.IS_FRWD_CHAT for chat_id in target_chat_ids):
      return await message.answer("In Target chat a task is progressing. please wait until task complete", show_alert=True)
    m = await msg_edit(message.message, "<code>verifying your data's, please wait.</code>")
    _bot, caption, forward_tag, data, protect, button = await sts.get_data(user)
    if not _bot:
      return await msg_edit(m, "<code>You didn't added any bot. Please add a bot using /settings !</code>", wait=True)
    try:
      client = await start_clone_bot(CLIENT.client(_bot))
    except Exception as e:  
      return await m.edit(e)
    await msg_edit(m, "<code>processing..</code>")
    try: 
       await client.get_messages(sts.get("FROM"), 1)
    except Exception:
       await msg_edit(m, f"**Source chat may be a private channel / group. Use userbot (user must be member over there) or  if Make Your [Bot](t.me/{_bot['username']}) an admin over there**", retry_btn(frwd_id), True)
       return await stop(client, user)
    try:
       for target in target_payloads:
          k = await client.send_message(
              target["chat_id"],
              "Testing",
              message_thread_id=target.get("thread_id")
          )
          await k.delete()
    except Exception:
       await msg_edit(m, f"**Please Make Your [UserBot / Bot](t.me/{_bot['username']}) Admin In Target Channel With Full Permissions**", retry_btn(frwd_id), True)
       return await stop(client, user)
    temp.forwardings += 1
    await db.add_frwd(user)
    # Increment task counter only when forwarding actually starts
    await db.increment_task(user, 'forwarding')
    await send(client, user, "<b>✨ ғᴏʀᴡᴀʀᴅɪɴɢ ᴘʀᴏᴄᴇss sᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!\n\n⚡ ᴘᴏᴡᴇʀᴇᴅ ʙʏ <a href=https://t.me/ftmbotzx>FᴛᴍBᴏᴛᴢx</a></b>")
    
    # Log forwarding started
    try:
        from plugins.logger import BotLogger
        source_chat = await client.get_chat(sts.get('FROM'))
        target_chat = await client.get_chat(sts.get('TO'))
        source_title = source_chat.title or source_chat.first_name or "Unknown"
        target_title = target_chat.title or target_chat.first_name or "Unknown"
        if len(target_chat_ids) > 1:
            target_title = f"{target_title} + {len(target_chat_ids) - 1} more"
        source_id = sts.get('FROM')
        target_id = sts.get('TO')
        user_name = callback_query.from_user.first_name or "User"
        bot_name = _bot.get('username', 'Unknown')
        skip_dup = data.get('skip_duplicate', False)
        
        await BotLogger.log_forwarding_started(
            bot, user, user_name, bot_name, 
            source_title, target_title, skip_dup,
            source_id, target_id
        )
    except Exception as e:
        logging.error(f"Error logging forwarding start: {e}")
    sts.add(time=True)
    sleep = 1 if _bot['is_bot'] else 3
    await msg_edit(m, "<code>Processing...</code>") 
    temp.IS_FRWD_CHAT.extend(target_chat_ids)
    temp.lock[user] = locked = True
    
    # FTM Alpha Mode - Save initial forwarding state
    configs = await db.get_configs(user)
    alpha_mode = configs.get('ftm_alpha_mode', False)
    if alpha_mode:
        await db.save_forwarding_state(user, {
            'type': 'manual',
            'source_chat_id': sts.get('FROM'),
            'target_chat_id': sts.get('TO'),
            'total': data['limit'],
            'offset': data['offset'],
            'processed': 0,
            'fetched': 0,
            'last_msg_id': 0,
            'status': 'active',
            'started_at': sts.get(full=True).start
        })
    
    if locked:
        try:
          MSG = []
          pling=0
          numbering_counter = 0  # Counter for auto numbering feature (manual forwarding only)
          await edit(m, 'Progressing', 10, sts)
          logging.info(f"Starting Forwarding Process... From :{sts.get('FROM')} To: {target_chat_ids} Totel: {sts.get('limit')} stats : {sts.get('skip')})")
          # Track update timing
          last_update = time.time()
          update_interval = 10  # seconds
          
          async for message in client.iter_messages(
            client,
            chat_id=data['chat_id'], 
            limit=data['limit'], 
            offset=data['offset'],
            filters=data.get('filters'),
            keywords=data.get('keywords'),
            extensions=data.get('extensions'),
            media_size=data.get('media_size'),
            skip_duplicate=data.get('skip_duplicate')
            ):
                if await is_cancelled(client, user, m, sts):
                   return
                
                # Auto-update progress every 10 seconds
                current_time = time.time()
                if current_time - last_update >= update_interval:
                   await edit(m, 'Progressing', 10, sts)
                   last_update = current_time
                
                # FTM Alpha Mode - Update progress after each message (including skipped/filtered)
                if alpha_mode:
                    current_msg_id = message.id if not isinstance(message, str) and not (message.empty or message.service) else sts.get('last_msg_id') or 0
                    await db.update_forwarding_progress(
                        user, 'manual', 
                        current_msg_id, 
                        sts.get('total_files'), 
                        sts.get('fetched')
                    )
                
                if message == "DUPLICATE":
                   sts.add('duplicate')
                   continue 
                elif message == "FILTERED":
                   sts.add('filtered')
                   continue 
                if message.empty or message.service:
                   sts.add('deleted')
                   continue
                
                # Update last_msg_id in sts for tracking
                sts.add(last_msg_id=message.id)
                
                # Apply Theta Mode filter - only forward images with captions
                configs = await db.get_configs(user)
                if configs.get('ftm_theta_mode', False):
                   has_image = message.photo is not None
                   has_caption = bool(message.caption)
                   if not (has_image and has_caption):
                      sts.add('filtered')
                      continue
                
                # Check message type filters (for gamma/auto mode)
                from plugins.ftm_manager import check_message_filters
                if not await check_message_filters(message, user):
                   sts.add('filtered')
                   continue
                
                if forward_tag:
                   MSG.append(message.id)
                   notcompleted = len(MSG)
                   completed = sts.get('total') - sts.get('fetched')
                   if ( notcompleted >= 100 
                        or completed <= 100): 
                      await forward(client, MSG, m, sts, protect, user)
                      sts.add('total_files', notcompleted)
                      await asyncio.sleep(3)
                      MSG = []
                else:
                   if message.text:
                       # Increment numbering counter only for messages with captions
                       numbering_counter += 1
                       message_text = message.text.html
                       new_caption = await apply_ftm_transformations(message_text, user, sts.get('FROM'), message.id, numbering_counter)
                       if new_caption:
                           details = {"msg_id": message.id, "media": None, "caption": new_caption, 'button': button, "protect": protect, "is_text": True, "parse_mode": enums.ParseMode.HTML}
                       else:
                           details = {"msg_id": message.id, "media": None, "caption": None, 'button': button, "protect": protect}
                   elif message.sticker:
                       # Stickers don't get numbered - no counter increment
                       details = {"msg_id": message.id, "media": None, "caption": None, 'button': button, "protect": protect}
                   elif message.video:
                       # Video message
                       numbering_counter += 1
                       new_caption = await custom_caption_with_config(message, caption, user)
                       new_caption = await apply_ftm_transformations(new_caption, user, sts.get('FROM'), message.id, numbering_counter)
                       details = {"msg_id": message.id, "media": media(message), "video_file_id": message.video.file_id, "caption": new_caption, 'button': button, "protect": protect, "is_video": True, "parse_mode": enums.ParseMode.HTML}
                   else:
                       # Increment numbering counter only for messages with captions
                       numbering_counter += 1
                       new_caption = await custom_caption_with_config(message, caption, user)
                       new_caption = await apply_ftm_transformations(new_caption, user, sts.get('FROM'), message.id, numbering_counter)
                       details = {"msg_id": message.id, "media": media(message), "caption": new_caption, 'button': button, "protect": protect, "parse_mode": enums.ParseMode.HTML}
                   await copy(client, details, m, sts, user)
                   sts.add('total_files')
                   
                   # FTM Alpha Mode - Update progress after each message
                   if alpha_mode:
                       await db.update_forwarding_progress(
                           user, 'manual', 
                           message.id, 
                           sts.get('total_files'), 
                           sts.get('fetched')
                       )
                   
                   await asyncio.sleep(sleep)
        except Exception as e:
            await msg_edit(m, f'<b>ERROR:</b>\n<code>{e}</code>', wait=True)
            for chat_id in target_chat_ids:
                if chat_id in temp.IS_FRWD_CHAT:
                    temp.IS_FRWD_CHAT.remove(chat_id)
            # FTM Alpha Mode - Cancel state on error
            if alpha_mode:
                await db.cancel_forwarding_state(user, 'manual')
            return await stop(client, user)
        for chat_id in target_chat_ids:
            if chat_id in temp.IS_FRWD_CHAT:
                temp.IS_FRWD_CHAT.remove(chat_id)
        await send(client, user, "<b>🎉 ғᴏʀᴡᴀʀᴅɪɴɢ ᴄᴏᴍᴘʟᴇᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!\n\n⚡ ᴘᴏᴡᴇʀᴇᴅ ʙʏ <a href=https://t.me/ftmbotzx>FᴛᴍBᴏᴛᴢx</a></b>")
        
        # Log forwarding completed
        try:
            from plugins.logger import BotLogger
            i = sts.get(full=True)
            
            # Calculate time taken
            end_time = time.time()
            time_taken_seconds = int(end_time - i.start)
            time_taken = TimeFormatter(time_taken_seconds * 1000)
            
            # Use callback_query saved at function start (before loop shadowed message variable)
            user_name = callback_query.from_user.first_name or "User"
            bot_name = _bot.get('username', 'Unknown')
            
            await BotLogger.log_forwarding_completed(
                bot, user, user_name, bot_name,
                i.total, i.total_files, i.deleted, i.skip, i.duplicate,
                time_taken
            )
        except Exception as e:
            logging.error(f"Error logging forwarding completion: {e}")
        await edit(m, 'Completed', "completed", sts)
        await db.update_last_process(user, 'forwarding', 'completed')
        
        # FTM Alpha Mode - Mark as completed and remove state
        if alpha_mode:
            await db.complete_forwarding_state(user, 'manual')
        
        await stop(client, user)
            
async def copy(bot, msg, m, sts, user_id=None):
   try:
     targets = get_target_payloads(sts)
     for target in targets:
        if msg.get("is_text") and msg.get("caption"):
           await bot.send_message(
                 chat_id=target["chat_id"],
                 text=msg.get("caption"),
                 parse_mode=msg.get("parse_mode"),
                 reply_markup=msg.get('button'),
                 protect_content=msg.get("protect"),
                 message_thread_id=target.get("thread_id"))
        elif msg.get("media") and msg.get("caption"):
           await bot.send_cached_media(
                 chat_id=target["chat_id"],
                 file_id=msg.get("media"),
                 caption=msg.get("caption"),
                 parse_mode=msg.get("parse_mode"),
                 reply_markup=msg.get('button'),
                 protect_content=msg.get("protect"),
                 message_thread_id=target.get("thread_id"))
        else:
           await bot.copy_message(
                 chat_id=target["chat_id"],
                 from_chat_id=sts.get('FROM'),
                 caption=msg.get("caption"),
                 message_id=msg.get("msg_id"),
                 reply_markup=msg.get('button'),
                 protect_content=msg.get("protect"),
                 message_thread_id=target.get("thread_id"))
   except FloodWait as e:
     await edit(m, 'Progressing', e.value if hasattr(e, 'value') else getattr(e, 'x', 10), sts)
     await asyncio.sleep(e.value if hasattr(e, 'value') else getattr(e, 'x', 10))
     await edit(m, 'Progressing', 10, sts)
     await copy(bot, msg, m, sts, user_id)
   except Exception as e:
     logging.info(e)
     sts.add('deleted')
        
async def forward(bot, msg, m, sts, protect, user):
   try:                             
     targets = get_target_payloads(sts)
     for target in targets:
        await bot.forward_messages(
              chat_id=target["chat_id"],
              from_chat_id=sts.get('FROM'),
              protect_content=protect,
              message_thread_id=target.get("thread_id"),
              message_ids=msg)
   except FloodWait as e:
     await edit(m, 'Progressing', e.value if hasattr(e, 'value') else getattr(e, 'x', 10), sts)
     await asyncio.sleep(e.value if hasattr(e, 'value') else getattr(e, 'x', 10))
     await edit(m, 'Progressing', 10, sts)
     await forward(bot, msg, m, sts, protect, user)

PROGRESS = """
╭────❰ Forwarded Status ❱────❍
┃
┣⊸📋 ᴛᴏᴛᴀʟ ᴍsɢs : {0}
┣⊸🕵 ғᴇᴛᴄʜᴇᴅ ᴍsɢ : {1}
┣⊸✅ sᴜᴄᴄᴇғᴜʟʟʏ ғᴡᴅ : {2}
┣⊸👥 ᴅᴜᴘʟɪᴄᴀᴛᴇ ᴍsɢ : {3}
┣⊸🗑️ ᴅᴇʟᴇᴛᴇᴅ : {4}
┣⊸📑 ғɪʟᴛᴇʀᴇᴅ : {5}
┣⊸🪆 sᴋɪᴘᴘᴇᴅ ᴍsɢ : {6}
┣⊸📊 sᴛᴀᴛᴜs : {7}
┣⊸⏳ ᴘʀᴏɢʀᴇss : {8}%
┣⊸⚡ sᴘᴇᴇᴅ : {9} msgs/min
┣⊸⏰ ᴇᴛᴀ : {10}
┃
╰────❍
"""

async def msg_edit(msg, text, button=None, wait=None):
    try:
        return await msg.edit(text, reply_markup=button)
    except MessageNotModified:
        pass 
    except FloodWait as e:
        if wait:
           sleep_time = getattr(e, 'value', getattr(e, 'x', 10))
           await asyncio.sleep(sleep_time)
           return await msg_edit(msg, text, button, wait)
        
def format_eta(seconds):
   """Format ETA as days, hours, minutes, seconds"""
   if seconds <= 0:
      return "0s"
   
   days = int(seconds // 86400)
   hours = int((seconds % 86400) // 3600)
   minutes = int((seconds % 3600) // 60)
   secs = int(seconds % 60)
   
   parts = []
   if days > 0:
      parts.append(f"{days}d")
   if hours > 0:
      parts.append(f"{hours}h")
   if minutes > 0:
      parts.append(f"{minutes}m")
   if secs > 0 or not parts:
      parts.append(f"{secs}s")
   
   return ", ".join(parts)

async def edit(msg, title, status, sts):
   i = sts.get(full=True)
   status = 'Forwarding' if status == 10 else f"Sleeping {status} s" if str(status).isnumeric() else status
   
   # Calculate percentage based on fetched vs total with decimal precision
   # Don't show 100% until actually complete
   if i.fetched >= i.total:
      percentage = "100.0"
   else:
      percentage = "{:.1f}".format(float(i.fetched)*100/float(i.total)) if i.total > 0 else "0.0"
   
   # Calculate speed based on FORWARDED files, not fetched messages
   now = time.time()
   diff = max(1, int(now - i.start))  # Ensure diff is at least 1 second to avoid division issues
   
   # Speed is based on successfully forwarded files only
   speed = sts.divide(i.total_files, diff)  # Files forwarded per second
   speed_per_min = int(speed * 60) if speed > 0 else 0
   
   # Calculate ETA based on remaining files to forward
   remaining_files = i.total - i.fetched
   eta_seconds = sts.divide(remaining_files, speed) if speed > 0 else 0
   
   elapsed_time = round(diff) * 1000
   time_to_completion = round(eta_seconds) * 1000
   estimated_total_time = elapsed_time + time_to_completion  
   
   # Calculate progress bar
   progress_filled = math.floor(float(percentage) / 10)
   progress = "◉{0}{1}".format(
       ''.join(["◉" for _ in range(progress_filled)]),
       ''.join(["◎" for _ in range(10 - progress_filled)]))
   
   # Use consistent callback data format without special characters in status
   callback_status = status.replace(' ', '_')
   button =  [[InlineKeyboardButton(title, callback_data=f'fwrdstatus#{callback_status}#{estimated_total_time}#{percentage}#{i.id}')]]
   
   remaining = i.total - i.fetched
   eta_seconds = sts.divide(remaining, speed) if speed > 0 else 0
   eta_formatted = format_eta(eta_seconds)

   text = TEXT.format(i.total, i.fetched, i.total_files, i.duplicate, i.deleted, i.filtered, i.skip, status, percentage, speed_per_min, eta_formatted, progress)
   if status in ["cancelled", "completed"]:
      button.append(
         [InlineKeyboardButton('💬 Sᴜᴘᴘᴏʀᴛ Gʀᴏᴜᴘ', url='https://t.me/ftmbotzx_support'),
         InlineKeyboardButton('📢Uᴘᴅᴀᴛᴇs Cʜᴀɴɴᴇʟ', url='https://t.me/ftmbotzx')]
         )
   else:
      button.append([InlineKeyboardButton('• ᴄᴀɴᴄᴇʟ', 'terminate_frwd')])
   
   try:
      await msg_edit(msg, text, InlineKeyboardMarkup(button))
   except MessageNotModified:
      pass
   except Exception as e:
      logger.error(f"Error editing message: {e}")
   
async def is_cancelled(client, user, msg, sts):
   if temp.CANCEL.get(user)==True:
      target_payloads = get_target_payloads(sts)
      for target in target_payloads:
          chat_id = target.get("chat_id")
          if chat_id in temp.IS_FRWD_CHAT:
              temp.IS_FRWD_CHAT.remove(chat_id)
      await edit(msg, "Cancelled", "completed", sts)
      await send(client, user, "<b>❌ Forwarding Process Cancelled</b>")
      await stop(client, user)
      return True 
   return False 

async def stop(client, user):
   try:
     await client.stop()
   except Exception:
     pass 
   await db.rmve_frwd(user)
   await db.decrement_task(user, 'forwarding')
   temp.forwardings -= 1
   temp.lock[user] = False 
    
async def send(bot, user, text):
   try:
      await bot.send_message(user, text=text)
   except Exception:
      pass 
     
def extract_metadata(file_name):
    import re
    
    year = 'N/A'
    language = 'N/A'
    quality = 'N/A'
    
    if file_name:
        year_match = re.search(r'\b(19|20)\d{2}\b', file_name)
        if year_match:
            year = year_match.group()
        
        quality_match = re.search(r'\b(144|240|360|480|720|1080|1440|2160|4320)p?\b', file_name, re.IGNORECASE)
        if quality_match:
            quality = quality_match.group()
            if not quality.lower().endswith('p'):
                quality += 'p'
        
        lang_patterns = {
            'Hindi': r'\b(Hindi|HIN|हिंदी)\b',
            'English': r'\b(English|ENG)\b',
            'Tamil': r'\b(Tamil|TAM)\b',
            'Telugu': r'\b(Telugu|TEL)\b',
            'Malayalam': r'\b(Malayalam|MAL)\b',
            'Kannada': r'\b(Kannada|KAN)\b',
            'Bengali': r'\b(Bengali|BEN)\b',
            'Marathi': r'\b(Marathi|MAR)\b',
            'Punjabi': r'\b(Punjabi|PUN)\b',
            'Multi Audio': r'\b(Multi[- ]?Audio|Dual[- ]?Audio)\b',
        }
        
        found_langs = []
        for lang, pattern in lang_patterns.items():
            if re.search(pattern, file_name, re.IGNORECASE):
                found_langs.append(lang)
        
        if found_langs:
            language = ' + '.join(found_langs)
    
    return year, language, quality

def remove_usernames_from_text(text):
    """Remove @usernames from text"""
    import re
    if text:
        return re.sub(r'@[a-zA-Z0-9_]+', '', text)
    return text

def custom_caption(msg, caption, user_id=None):
  if msg.media:
    if (msg.video or msg.document or msg.audio or msg.photo):
      media_type = msg.media.value if hasattr(msg.media, 'value') else str(msg.media).split('.')[-1].lower()
      media = getattr(msg, media_type, None)
      if media:
        file_name = getattr(media, 'file_name', '')
        file_size = getattr(media, 'file_size', '')
        fcaption = getattr(msg, 'caption', '')
        if fcaption:
          fcaption = fcaption.html
        
        media_type = 'Unknown'
        if msg.video:
            media_type = 'Video'
        elif msg.audio:
            media_type = 'Audio'
        elif msg.document:
            media_type = 'Document'
        elif msg.photo:
            media_type = 'Photo'
        
        year, language, quality = extract_metadata(file_name)
        
        if caption:
          try:
              return caption.format(
                  filename=file_name, 
                  size=get_size(file_size), 
                  caption=fcaption,
                  year=year,
                  language=language,
                  quality=quality,
                  type=media_type
              )
          except KeyError:
              return caption.format(filename=file_name, size=get_size(file_size), caption=fcaption)
        return fcaption
  return None

async def custom_caption_with_config(msg, caption, user_id):
    """Custom caption with username removal support based on user config"""
    import re
    from plugins.test import get_configs
    
    if msg.media:
        if (msg.video or msg.document or msg.audio or msg.photo):
            media_type = msg.media.value if hasattr(msg.media, 'value') else str(msg.media).split('.')[-1].lower()
            media = getattr(msg, media_type, None)
            if media:
                file_name = getattr(media, 'file_name', '') or ''
                file_size = getattr(media, 'file_size', '')
                fcaption = getattr(msg, 'caption', '')
                if fcaption:
                    fcaption = fcaption.html
                
                # Get user config for username remover
                config = await get_configs(user_id)
                username_remover_enabled = config.get('ftm_username_remover', False)
                
                # Apply username removal to filename and caption if enabled
                # Note: Caption removal for images is skipped - only applies to video/audio/document
                if username_remover_enabled:
                    file_name = re.sub(r'@[a-zA-Z0-9_]+', '', file_name)
                    # Only remove usernames from caption for video, audio, document (not photos)
                    if fcaption and (msg.video or msg.audio or msg.document):
                        fcaption = re.sub(r'@[a-zA-Z0-9_]+', '', fcaption)
                
                media_type = 'Unknown'
                if msg.video:
                    media_type = 'Video'
                elif msg.audio:
                    media_type = 'Audio'
                elif msg.document:
                    media_type = 'Document'
                elif msg.photo:
                    media_type = 'Photo'
                
                year, language, quality = extract_metadata(file_name)
                
                if caption:
                    try:
                        return caption.format(
                            filename=file_name, 
                            size=get_size(file_size), 
                            caption=fcaption,
                            year=year,
                            language=language,
                            quality=quality,
                            type=media_type
                        )
                    except KeyError:
                        return caption.format(filename=file_name, size=get_size(file_size), caption=fcaption)
                return fcaption
    return None

def get_size(size):
  units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
  size = float(size)
  i = 0
  while size >= 1024.0 and i < len(units):
     i += 1
     size /= 1024.0
  return "%.2f %s" % (size, units[i]) 

def media(msg):
  if msg.media:
     try:
        media_type = msg.media.value if hasattr(msg.media, 'value') else str(msg.media).split('.')[-1].lower()
        media = getattr(msg, media_type, None)
        if media:
           return getattr(media, 'file_id', None)
     except Exception:
        pass
  return None 

def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "") + \
        ((str(milliseconds) + "ms, ") if milliseconds else "")
    return tmp[:-2]

def retry_btn(id):
    return InlineKeyboardMarkup([[InlineKeyboardButton('♻️ RETRY ♻️', f"start_public_{id}")]])

@Client.on_callback_query(filters.regex(r'^terminate_frwd$'))
async def terminate_frwding(bot, m):
    user_id = m.from_user.id 
    temp.lock[user_id] = False
    temp.CANCEL[user_id] = True 
    await m.answer("Forwarding cancelled !", show_alert=True)
          
@Client.on_callback_query(filters.regex(r'^fwrdstatus'))
async def status_msg(bot, msg):
    _, status, est_time, percentage, frwd_id = msg.data.split("#")
    # Replace underscores back to spaces for display
    status = status.replace('_', ' ')
    
    sts = STS(frwd_id)
    if not sts.verify():
       total, fetched, forwarded, duplicate, deleted, filtered, skipped = 0, 0, 0, 0, 0, 0, 0
       speed_per_min = 0
       speed = 0
       eta_formatted = "N/A"
    else:
       i = sts.get(full=True)
       total = i.total
       fetched = i.fetched
       forwarded = i.total_files
       duplicate = i.duplicate
       deleted = i.deleted
       filtered = i.filtered
       skipped = i.skip
       
       now = time.time()
       diff = max(1, int(now - i.start))  # Ensure diff is at least 1 second
       speed = sts.divide(i.total_files, diff)  # Speed based on forwarded files
       speed_per_min = int(speed * 60) if speed > 0 else 0
       
       # Limit speed display to reasonable values
       if speed_per_min > 10000:
          speed_per_min = 0
       
       # Calculate ETA
       eta_seconds = sts.divide(total - fetched, speed) if speed > 0 else 0
       eta_formatted = format_eta(eta_seconds)
    
    # Import small caps function
    from .utils import to_small_caps
    
    # Create enhanced alert with more fields, small caps, and emojis
    alert_text = (
        f"╭─❰ {to_small_caps('forwarding status')} ❱─╮\n"
        f"┃\n"
        f"┣⊱ 📊 {to_small_caps('progress')}: {percentage}%\n"
        f"┣⊱ 📋 {to_small_caps('total')}: {total}\n"
        f"┣⊱ 🕵️ {to_small_caps('fetched')}: {fetched}\n"
        f"┣⊱ ✅ {to_small_caps('forwarded')}: {forwarded}\n"
        f"┣⊱ 👥 {to_small_caps('duplicate')}: {duplicate}\n"
        f"┣⊱ 🗑️ {to_small_caps('deleted')}: {deleted}\n"
        f"┣⊱ 📑 {to_small_caps('filtered')}: {filtered}\n"
        f"┣⊱ 🪆 {to_small_caps('skipped')}: {skipped}\n"
        f"┣⊱ ⚡ {to_small_caps('speed')}: {speed_per_min} msgs/min\n"
        f"┣⊱ ⏰ {to_small_caps('eta')}: {eta_formatted}\n"
        f"┣⊱ 📌 {to_small_caps('status')}: {to_small_caps(status)}\n"
        f"┃\n"
        f"╰───────────────╯"
    )
    
    # Answer callback query with enhanced alert
    try:
        await msg.answer(alert_text, show_alert=True)
    except Exception as e:
        logger.error(f"Error answering callback query: {e}")
        # If still too long, use shorter version
        short_alert = f"📊 {percentage}% | ✅ {forwarded}/{total}\n⚡ {speed_per_min} msgs/min | ⏰ {eta_formatted}\n📌 {to_small_caps(status)}"
        try:
            await msg.answer(short_alert, show_alert=True)
        except Exception:
            try:
                await msg.answer()
            except Exception:
                pass
                  
@Client.on_callback_query(filters.regex(r'^close_btn$'))
async def close(bot, update):
    await update.answer()
    await update.message.delete()


async def resume_alpha_forwarding(bot, user_id, state):
    """
    Resume manual forwarding from saved state (FTM Alpha Mode).
    Called on bot restart to continue from last processed message.
    
    Args:
        bot: The Pyrogram client
        user_id: User ID
        state: Saved forwarding state from database
    
    Returns:
        True if resume initiated successfully, False otherwise
    """
    try:
        from database import db
        from .ftm_manager import apply_ftm_transformations
        from .test import parse_buttons
        from config import Config, temp
        import asyncio
        import time
        
        source_id = state.get('source_chat_id')
        target_id = state.get('target_chat_id')
        last_msg_id = state.get('last_msg_id', 0)
        total = state.get('total', 0)
        processed = state.get('processed', 0)
        fetched = state.get('fetched', 0)
        
        if not source_id or not target_id:
            return False
        
        # Check if user is already running a task
        if temp.lock.get(user_id):
            return False
        
        # Get user's clone bot for forwarding
        _bot = await db.get_bot(user_id)
        if not _bot:
            logging.info(f"[ALPHA RESUME] No bot found for user {user_id}")
            return False
        
        # Check if it's a userbot (session) or bot (token)
        # is_bot can be True, False, or None (not set)
        is_userbot = _bot.get('is_bot') is False
        session_string = _bot.get('session')
        bot_token = _bot.get('token') or _bot.get('bot_token')
        
        # Validate credentials are actual non-empty strings
        has_valid_session = is_userbot and session_string and isinstance(session_string, str) and len(session_string) > 10
        has_valid_token = bot_token and isinstance(bot_token, str) and len(bot_token) > 10
        
        if not has_valid_session and not has_valid_token:
            logging.info(f"[ALPHA RESUME] No valid credentials (token or session) found for user {user_id}. is_bot={_bot.get('is_bot')}, has_session={bool(session_string)}, has_token={bool(bot_token)}")
            return False
        
        try:
            from pyrogram import Client
            
            if has_valid_session:
                # Use session string for userbot
                logging.info(f"[ALPHA RESUME] Using session string for user {user_id}")
                client = Client(
                    f"userbot_{user_id}",
                    api_id=Config.API_ID,
                    api_hash=Config.API_HASH,
                    session_string=session_string
                )
            else:
                # Use bot token for regular bot
                logging.info(f"[ALPHA RESUME] Using bot token for user {user_id}")
                client = Client(
                    f"clone_{user_id}",
                    api_id=Config.API_ID,
                    api_hash=Config.API_HASH,
                    bot_token=bot_token,
                    in_memory=True
                )
            
            await client.start()
            logging.info(f"[ALPHA RESUME] Client started successfully for user {user_id}")
        except Exception as e:
            logging.error(f"Failed to start clone client for alpha resume: {e}")
            return False
        
        # Get configurations
        configs = await db.get_configs(user_id) or {}
        caption = configs.get('caption')
        forward_tag = configs.get('forward_tag', False)
        protect = configs.get('protect', False)
        button_text = configs.get('button') or ''
        button = parse_buttons(button_text) if button_text else None
        
        # Calculate remaining messages
        remaining = total - fetched
        if remaining <= 0:
            await client.stop()
            await db.complete_forwarding_state(user_id, 'manual')
            return True
        
        # Lock the task
        temp.lock[user_id] = True
        temp.IS_FRWD_CHAT.append(target_id)
        
        # Start the resume forwarding in background
        asyncio.create_task(
            _resume_forwarding_task(
                client, bot, user_id, source_id, target_id,
                last_msg_id, remaining, processed, fetched, total,
                caption, forward_tag, protect, button, configs
            )
        )
        
        return True
        
    except Exception as e:
        logging.error(f"Error in resume_alpha_forwarding: {e}")
        return False


async def _update_alpha_progress(progress_msg, total, fetched, processed, duplicate, deleted, filtered, skipped, start_time, status):
    """Helper to update alpha mode progress bar"""
    try:
        elapsed = time.time() - start_time
        diff = max(1, int(elapsed))
        speed = int((processed / diff) * 60) if diff > 0 and processed > 0 else 0
        remaining_msgs = total - fetched
        eta_seconds = (remaining_msgs / (fetched / elapsed)) if fetched > 0 and elapsed > 0 else 0
        eta = format_eta(eta_seconds)
        
        percent = "{:.1f}".format(float(fetched)*100/float(total)) if total > 0 else "0.0"
        progress_filled = math.floor(float(percent) / 10)
        progress_bar = "◉{0}{1}".format(
            ''.join(["◉" for _ in range(progress_filled)]),
            ''.join(["◎" for _ in range(10 - progress_filled)]))
        
        text = TEXT.format(total, fetched, processed, duplicate, deleted, filtered, skipped, status, percent, speed, eta, progress_bar)
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton(status, callback_data=f'alpha_status#progress')],
            [InlineKeyboardButton('• ᴄᴀɴᴄᴇʟ', 'terminate_frwd')]
        ])
        await progress_msg.edit_text(text, reply_markup=btn)
    except Exception:
        pass


async def _resume_forwarding_task(client, main_bot, user_id, source_id, target_id,
                                   last_msg_id, remaining, processed, fetched, total,
                                   caption, forward_tag, protect, button, configs):
    """Background task to continue forwarding from saved state"""
    try:
        from database import db
        from .ftm_manager import apply_ftm_transformations
        from config import temp
        from pyrogram import enums
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        import asyncio
        import time
        import math
        
        numbering_counter = processed  # Continue numbering from where we left
        sleep = 3
        progress_msg = None
        last_progress_update = 0
        progress_update_interval = 10  # Update progress every 10 messages
        start_time = time.time()
        duplicate = 0
        deleted = 0
        filtered = 0
        skipped = 0
        
        # Calculate initial progress
        percent = "{:.1f}".format(float(fetched)*100/float(total)) if total > 0 else "0.0"
        progress_filled = math.floor(float(percent) / 10)
        progress_bar = "◉{0}{1}".format(
            ''.join(["◉" for _ in range(progress_filled)]),
            ''.join(["◎" for _ in range(10 - progress_filled)]))
        
        # Send initial progress message using same format as manual forwarding
        try:
            text = TEXT.format(total, fetched, processed, duplicate, deleted, filtered, skipped, "🔄 ᴀᴜᴛᴏ-ʀᴇsᴜᴍɪɴɢ", percent, 0, "Calculating...", progress_bar)
            button = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 ᴀᴜᴛᴏ-ʀᴇsᴜᴍɪɴɢ", callback_data=f'alpha_status#resuming')],
                [InlineKeyboardButton('• ᴄᴀɴᴄᴇʟ', 'terminate_frwd')]
            ])
            progress_msg = await main_bot.send_message(user_id, text, reply_markup=button)
        except Exception as e:
            logging.error(f"Failed to send initial progress message: {e}")
        # Iterate from last_msg_id onwards
        last_fetched_update = 0
        async for message in client.get_chat_history(source_id, limit=remaining, offset_id=last_msg_id):
            try:
                if temp.CANCEL.get(user_id):
                    break
                
                fetched += 1
                
                if message.empty or message.service:
                    skipped += 1
                    # Update progress every 20 fetched messages (for skipped messages too)
                    if progress_msg and (fetched - last_fetched_update) >= 20:
                        await _update_alpha_progress(progress_msg, total, fetched, processed, duplicate, deleted, filtered, skipped, start_time, "🔄 ᴀᴜᴛᴏ-ʀᴇsᴜᴍɪɴɢ")
                        last_fetched_update = fetched
                    continue
                
                # Apply Theta Mode filter
                if configs.get('ftm_theta_mode', False):
                    has_image = message.photo is not None
                    has_caption = bool(message.caption)
                    if not (has_image and has_caption):
                        filtered += 1
                        if progress_msg and (fetched - last_fetched_update) >= 20:
                            await _update_alpha_progress(progress_msg, total, fetched, processed, duplicate, deleted, filtered, skipped, start_time, "🔄 ᴀᴜᴛᴏ-ʀᴇsᴜᴍɪɴɢ")
                            last_fetched_update = fetched
                        continue
                
                # Update alpha state
                await db.update_forwarding_progress(user_id, 'manual', message.id, processed, fetched)
                
                # Check message type filters (for gamma/auto mode)
                from plugins.ftm_manager import check_message_filters
                if not await check_message_filters(message, user_id):
                    filtered += 1
                    if progress_msg and (fetched - last_fetched_update) >= 20:
                        await _update_alpha_progress(progress_msg, total, fetched, processed, duplicate, deleted, filtered, skipped, start_time, "🔄 ᴀᴜᴛᴏ-ʀᴇsᴜᴍɪɴɢ")
                        last_fetched_update = fetched
                    continue
                
                # Process message
                try:
                    if message.text:
                        numbering_counter += 1
                        message_text = message.text.html
                        new_caption = await apply_ftm_transformations(message_text, user_id, source_id, message.id, numbering_counter)
                        if new_caption:
                            await client.send_message(
                                chat_id=target_id,
                                text=new_caption,
                                parse_mode=enums.ParseMode.HTML,
                                reply_markup=button,
                                disable_web_page_preview=True
                            )
                            processed += 1
                        else:
                            skipped += 1
                    elif message.sticker:
                        await client.copy_message(
                            chat_id=target_id,
                            from_chat_id=source_id,
                            message_id=message.id,
                            protect_content=protect
                        )
                        processed += 1
                    elif message.video:
                        numbering_counter += 1
                        new_caption = await apply_ftm_transformations(message.caption.html if message.caption else '', user_id, source_id, message.id, numbering_counter)
                        await client.copy_message(
                            chat_id=target_id,
                            from_chat_id=source_id,
                            message_id=message.id,
                            caption=new_caption,
                            reply_markup=button,
                            protect_content=protect
                        )
                        processed += 1
                    else:
                        numbering_counter += 1
                        new_caption = await apply_ftm_transformations(message.caption.html if message.caption else '', user_id, source_id, message.id, numbering_counter)
                        await client.copy_message(
                            chat_id=target_id,
                            from_chat_id=source_id,
                            message_id=message.id,
                            caption=new_caption,
                            reply_markup=button,
                            protect_content=protect
                        )
                        processed += 1
                except Exception as fwd_e:
                    deleted += 1
                    logging.error(f"Error forwarding message: {fwd_e}")
                # Update alpha state
                await db.update_forwarding_progress(user_id, 'manual', message.id, processed, fetched)
                
                # Update progress bar every 20 fetched messages
                if progress_msg and (fetched - last_fetched_update) >= 20:
                    await _update_alpha_progress(progress_msg, total, fetched, processed, duplicate, deleted, filtered, skipped, start_time, "🔄 ᴀᴜᴛᴏ-ʀᴇsᴜᴍɪɴɢ")
                    last_fetched_update = fetched
                
                await asyncio.sleep(sleep)
                
            except Exception as msg_e:
                logging.error(f"Error processing message in alpha resume: {msg_e}")
                deleted += 1
                continue
        
        # Mark as completed
        await db.complete_forwarding_state(user_id, 'manual')
        
        # Update progress bar to show completion
        elapsed = time.time() - start_time
        diff = max(1, int(elapsed))
        speed = int((processed / diff) * 60) if diff > 0 else 0
        
        progress_bar = "◉◉◉◉◉◉◉◉◉◉◉"
        text = TEXT.format(total, fetched, processed, duplicate, deleted, filtered, skipped, "✅ ᴄᴏᴍᴘʟᴇᴛᴇᴅ", "100.0", speed, "0s", progress_bar)
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ ᴄᴏᴍᴘʟᴇᴛᴇᴅ", callback_data=f'alpha_status#completed')],
            [InlineKeyboardButton('💬 Sᴜᴘᴘᴏʀᴛ Gʀᴏᴜᴘ', url='https://t.me/ftmbotzx_support'),
             InlineKeyboardButton('📢Uᴘᴅᴀᴛᴇs Cʜᴀɴɴᴇʟ', url='https://t.me/ftmbotzx')]
        ])
        
        try:
            if progress_msg:
                await progress_msg.edit_text(text, reply_markup=btn)
            else:
                await main_bot.send_message(user_id, text, reply_markup=btn)
        except Exception:
            pass
        
    except Exception as e:
        logging.error(f"Error in _resume_forwarding_task: {e}")
        await db.save_forwarding_state(user_id, {
            'type': 'manual',
            'status': 'paused',
            'paused_reason': 'resume_error'
        }, merge=True)
    finally:
        # Cleanup
        temp.lock[user_id] = False
        if target_id in temp.IS_FRWD_CHAT:
            temp.IS_FRWD_CHAT.remove(target_id)
        try:
            await client.stop()
        except Exception:
            pass


# ============ Ported from ftm-forwardbot-latest ============
def safe_decode_caption(caption_data):
    """
    Safely decode caption data that might be in various encodings including UTF-16-LE.
    
    Args:
        caption_data: The caption data from Pyrogram (could be string, bytes, or None)
        
    Returns:
        str: Properly decoded UTF-8 string, or empty string if decoding fails
    """
    if not caption_data:
        return ""
    
    # If it's already a string, ensure it's clean UTF-8
    if isinstance(caption_data, str):
        try:
            # Encode and decode to ensure clean UTF-8
            return caption_data.encode('utf-8', errors='ignore').decode('utf-8')
        except Exception:
            return ""
    
    # If it's bytes, try multiple encoding methods
    if isinstance(caption_data, bytes):
        # List of encodings to try, in order of preference
        encodings_to_try = [
            'utf-8',
            'utf-16-le',  # Handle the specific UTF-16-LE encoding issue
            'utf-16-be',
            'utf-16',
            'latin-1',
            'cp1252'
        ]
        
        for encoding in encodings_to_try:
            try:
                decoded = caption_data.decode(encoding, errors='strict')
                # Additional validation: ensure the decoded string is reasonable
                if decoded and len(decoded) > 0:
                    # Clean up any potential null bytes or control characters
                    cleaned = decoded.replace('\x00', '').strip()
                    if cleaned:
                        return cleaned
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        # If all encodings fail, try with error handling
        try:
            return caption_data.decode('utf-8', errors='replace').replace('\ufffd', '').strip()
        except Exception:
            return ""
    
    # Fallback for any other type
    try:
        return str(caption_data).encode('utf-8', errors='ignore').decode('utf-8')
    except Exception:
        return ""


async def should_forward_message(message, user_id):
    """Check if message should be forwarded based on user filters"""
    try:
        configs = await db.get_configs(user_id)
        filters_cfg = configs.get('filters', {})

        # Check if any filters are actually enabled (not default True values)
        # If no filters are explicitly set to True, allow all messages (backward compatibility)
        any_filter_enabled = any(filters_cfg.get(filter_type, False) for filter_type in 
                               ['text', 'photo', 'video', 'document', 'audio', 'voice', 'animation', 'sticker', 'poll', 'image_text'])
        
        if not any_filter_enabled:
            message_allowed = True
        else:
            # At least one filter is enabled, so check individual message type filters
            message_allowed = False
            
            # Check image+text filter first (special case - requires both image AND text/caption)
            if filters_cfg.get('image_text', False):
                has_image = bool(message.photo)
                has_text_or_caption = bool(message.caption and message.caption.strip()) or bool(message.text and message.text.strip())
                if has_image and has_text_or_caption:
                    message_allowed = True
            
            # Check individual message type filters (using if instead of elif so multiple can match)
            if message.text and filters_cfg.get('text', False):
                message_allowed = True
            if message.photo and filters_cfg.get('photo', False):
                message_allowed = True
            if message.video and filters_cfg.get('video', False):
                message_allowed = True
            if message.document and filters_cfg.get('document', False):
                message_allowed = True
            if message.audio and filters_cfg.get('audio', False):
                message_allowed = True
            if message.voice and filters_cfg.get('voice', False):
                message_allowed = True
            if message.animation and filters_cfg.get('animation', False):
                message_allowed = True
            if message.sticker and filters_cfg.get('sticker', False):
                message_allowed = True
            if message.poll and filters_cfg.get('poll', False):
                message_allowed = True
                
            if not message_allowed:
                return False

        # Check file size limit
        file_size_limit = configs.get('file_size', 0)
        size_limit_type = configs.get('size_limit')

        if file_size_limit > 0 and message.media:
            media = getattr(message, message.media.value, None)
            if media and hasattr(media, 'file_size'):
                file_size_mb = media.file_size / (1024 * 1024)  # Convert to MB

                if size_limit_type is True:  # More than
                    if file_size_mb <= file_size_limit:
                        return False
                elif size_limit_type is False:  # Less than
                    if file_size_mb >= file_size_limit:
                        return False

        # Check extension filters
        extensions = configs.get('extension')
        if extensions and message.document:
            file_name = getattr(message.document, 'file_name', '')
            if file_name:
                file_ext = file_name.split('.')[-1].lower()
                if file_ext in [ext.lower().strip('.') for ext in extensions]:
                    return False

        # Check keyword filters
        keywords = configs.get('keywords', [])
        if keywords and len(keywords) > 0:
            message_text = ""
            if message.text:
                message_text = message.text.lower()
            elif message.caption:
                message_text = message.caption.lower()
            elif message.document and hasattr(message.document, 'file_name'):
                message_text = message.document.file_name.lower()

            if message_text:
                # If keywords are set, message must contain at least one keyword
                keyword_found = any(keyword.lower().strip() in message_text for keyword in keywords if keyword.strip())
                if not keyword_found:
                    return False
            else:
                return False

        return True
    
    except Exception as e:
        logger.error(f"Error in should_forward_message: {e}")
        return True  # Default to allow forwarding if there's an error


async def is_duplicate_message(message, user_id):
    """Check if message is duplicate based on user settings"""
    configs = await db.get_configs(user_id)

    if not configs.get('duplicate', True):
        return False  # Duplicate checking is disabled

    # Simple duplicate check based on file_id for media messages
    if message.media:
        media = getattr(message, message.media.value, None)
        if media and hasattr(media, 'file_unique_id'):
            # Placeholder for future duplicate tracking via DB
            pass

    return False
# ============ end ported block ============
