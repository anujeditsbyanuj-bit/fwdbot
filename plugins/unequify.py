import asyncio
import time as time_module
from database import db
from config import temp, Config
from .test import CLIENT, start_clone_bot
from translation import Translation
from pyrogram import Client, filters 
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import hashlib
import logging

CLIENT = CLIENT()

def to_small_caps(text):
    small_caps_map = {
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ғ', 'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ',
        'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ',
        'S': 's', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ',
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ',
        'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ',
        's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ'
    }
    return ''.join(small_caps_map.get(char, char) for char in text)

COMPLETED_BTN = InlineKeyboardMarkup(
   [
      [InlineKeyboardButton('⚡ ' + to_small_caps('Support'), url=Config.SUPPORT_GROUP)],
      [InlineKeyboardButton('📢 ' + to_small_caps('Updates'), url=Config.UPDATE_CHANNEL)]
   ]
)

CANCEL_BTN = InlineKeyboardMarkup([[InlineKeyboardButton('⚠️ ' + to_small_caps('cancel'), 'terminate_frwd')]])

def get_message_hash(msg):
   """Generate a hash for a message to detect duplicates"""
   try:
      if msg.document:
         return ('doc', msg.document.file_unique_id)
      if msg.photo:
         return ('photo', msg.photo.file_unique_id)
      if msg.video:
         return ('video', msg.video.file_unique_id)
      if msg.audio:
         return ('audio', msg.audio.file_unique_id)
      if msg.sticker:
         return ('sticker', msg.sticker.file_unique_id)
      if msg.animation:
         return ('animation', msg.animation.file_unique_id)
      if msg.text:
         text_hash = hashlib.md5(msg.text.encode()).hexdigest()
         return ('text', text_hash)
      if msg.caption:
         caption_hash = hashlib.md5(msg.caption.encode()).hexdigest()
         return ('caption', caption_hash)
      return (None, None)
   except Exception:
      return (None, None)

def format_progress(total, fetched, deleted, start_time):
   """Format progress with speed and ETA"""
   elapsed = time_module.time() - start_time
   if elapsed > 0:
      speed = fetched / elapsed
   else:
      speed = 0
   
   # Calculate ETA (estimate remaining based on speed)
   remaining = total - fetched if total > 0 else 0
   if speed > 0:
      eta_seconds = int(remaining / speed)
   else:
      eta_seconds = 0
   
   # Format times
   eta_mins = eta_seconds // 60
   eta_secs = eta_seconds % 60
   
   elapsed_mins = int(elapsed) // 60
   elapsed_secs = int(elapsed) % 60
   
   speed_str = f"{speed:.1f}"
   
   progress_text = (
      f"╭─ 🔄 {to_small_caps('unequify status')} 🔄 ─╮\n"
      f"│\n"
      f"├ 📥 {to_small_caps('fetched files')}: <b>{fetched}</b> / {total}\n"
      f"├ 🗑️ {to_small_caps('duplicate deleted')}: <b>{deleted}</b>\n"
      f"├ ⚡ {to_small_caps('speed')}: <b>{speed_str}</b> {to_small_caps('msg/s')}\n"
      f"├ ⏱️ {to_small_caps('elapsed')}: <b>{elapsed_mins}m {elapsed_secs}s</b>\n"
      f"├ ⏳ {to_small_caps('eta')}: <b>{eta_mins}m {eta_secs}s</b>\n"
      f"│\n"
      f"╰─ {to_small_caps('processing')}... ─╯"
   )
   
   return progress_text

@Client.on_message(filters.command("unequify") & filters.private)
async def unequify(client, message):
   from .subscription import require_unequify

   user_id = message.from_user.id

   # Check subscription permission
   has_permission, error_message = await require_unequify(user_id)
   if not has_permission:
      return await message.reply(error_message)

   temp.CANCEL[user_id] = False
   if temp.lock.get(user_id) and str(temp.lock.get(user_id))=="True":
      return await message.reply(f"⚠️ {to_small_caps('please wait until previous task complete')}")
   
   _bot = await db.get_bot(user_id)
   if not _bot or _bot['is_bot']:
      return await message.reply(f"❌ {to_small_caps('need userbot to do this process. please add a userbot using /settings')}")
   
   # Initialize bot
   try:
      bot = await start_clone_bot(CLIENT.client(_bot))
   except Exception as e:
      return await message.reply(f"❌ {to_small_caps('failed to start userbot')}: `{str(e)}`")
   
   try:
      # Ask for target chat
      target = await client.ask(user_id, text=f"📨 {to_small_caps('forward the last message from target chat or send last message link.')}\n/cancel - {to_small_caps('cancel this process')}")
      if not target or target.text.startswith("/"):
         return await message.reply(f"❌ {to_small_caps('process cancelled!')}")
      
      chat_id = None
      
      # Try to get chat from forwarded message first
      if target.forward_from_chat:
         chat_id = target.forward_from_chat.id
      else:
         # Try to parse as link
         import re
         text = target.text.strip()
         
         # Extract channel username or ID from link
         pattern = r'(?:https?://)?(?:t\.me/|telegram\.me/)(?:c/)?([a-zA-Z0-9_-]+|\d+)'
         match = re.search(pattern, text)
         
         if not match:
            return await message.reply(f"❌ {to_small_caps('invalid link or forward. please forward a message from the chat or send a valid link.')}")
         
         chat_identifier = match.group(1)
         
         # Try to get chat by username or ID
         try:
            if chat_identifier.isdigit():
               chat_id = int('-100' + chat_identifier)
            else:
               chat_obj = await bot.get_chat(chat_identifier)
               chat_id = chat_obj.id
         except Exception as e:
            await bot.stop()
            return await message.reply(f"❌ {to_small_caps('could not access chat')}: `{str(e)}`")
      
      if not chat_id:
         await bot.stop()
         return await message.reply(f"❌ {to_small_caps('could not determine chat id')}")
      
      # Confirm action
      confirm = await client.ask(user_id, text=f"✅ {to_small_caps('send /yes to start the process and /no to cancel this process')}")
      if confirm.text.lower() != '/yes':
         await bot.stop()
         return await confirm.reply(f"❌ {to_small_caps('process cancelled!')}")
      
      sts = await confirm.reply(f"⏳ {to_small_caps('initializing...')}")
      
      # Test permissions
      try:
         k = await bot.send_message(chat_id, text="testing")
         await k.delete()
      except Exception as e:
         await sts.edit(f"❌ {to_small_caps('error: cannot post in target chat. make sure userbot is admin with full permissions.')}\n`{str(e)}`")
         await bot.stop()
         return
      
      temp.lock[user_id] = True
      
      # Get chat info for logging
      start_time = time_module.time()
      user_name = message.from_user.first_name or "User"
      bot_name = _bot.get('username', 'Unknown')
      
      try:
         chat_obj = await bot.get_chat(chat_id)
         channel_title = chat_obj.title or chat_obj.first_name or "Unknown"
      except Exception:
         channel_title = "Unknown"
      
      # Log start
      try:
         from plugins.logger import BotLogger
         await BotLogger.log_unequify_started(
             client, user_id, user_name, bot_name, channel_title
         )
      except Exception:
         pass
      
      # First pass: count total messages
      await sts.edit(f"🔍 {to_small_caps('counting total messages...')}")
      total_messages = 0
      try:
         async for _ in bot.get_chat_history(chat_id, limit=0):
            total_messages += 1
      except Exception:
         total_messages = 0
      
      # Scan for duplicates
      message_hashes = {}
      DUPLICATE = []
      total = 0
      deleted = 0
      last_update = time_module.time()
      
      # Iterate through all messages in chat from newest
      try:
         async for msg in bot.get_chat_history(chat_id):
            if temp.CANCEL.get(user_id):
               break
            
            total += 1
            
            # Get message hash
            msg_type, msg_hash = get_message_hash(msg)
            
            if msg_type and msg_hash:
               hash_key = f"{msg_type}:{msg_hash}"
               
               if hash_key in message_hashes:
                  DUPLICATE.append(msg.id)
               else:
                  message_hashes[hash_key] = msg.id
            
            # Update progress every 0.5 seconds or every 50 messages
            current_time = time_module.time()
            if (current_time - last_update) > 0.5 or total % 50 == 0:
               progress = format_progress(total_messages, total, deleted, start_time)
               try:
                  await sts.edit(progress, reply_markup=CANCEL_BTN)
               except Exception:
                  pass
               last_update = current_time
            
            # Delete in batches of 50
            if len(DUPLICATE) >= 50:
               try:
                  await bot.delete_messages(chat_id, DUPLICATE)
                  deleted += len(DUPLICATE)
                  DUPLICATE = []
               except Exception as e:
                  logging.error(f"Error deleting messages: {e}")
            await asyncio.sleep(0.01)
      
      except Exception as e:
         logging.error(f"Error scanning messages: {e}")
      # Delete remaining duplicates
      if DUPLICATE:
         try:
            await bot.delete_messages(chat_id, DUPLICATE)
            deleted += len(DUPLICATE)
         except Exception as e:
            logging.error(f"Error deleting remaining messages: {e}")
      # Final update
      temp.lock[user_id] = False
      completion_time = time_module.time() - start_time
      completion_mins = int(completion_time) // 60
      completion_secs = int(completion_time) % 60
      
      final_text = (
         f"╭─ ✅ {to_small_caps('unequify completed')} ✅ ─╮\n"
         f"│\n"
         f"├ 📥 {to_small_caps('total fetched')}: <b>{total}</b>\n"
         f"├ 🗑️ {to_small_caps('duplicate removed')}: <b>{deleted}</b>\n"
         f"├ 📊 {to_small_caps('removal rate')}: <b>{(deleted/total*100):.1f}%</b>\n"
         f"├ ⏱️ {to_small_caps('time taken')}: <b>{completion_mins}m {completion_secs}s</b>\n"
         f"├ 📁 {to_small_caps('channel')}: <b>{channel_title}</b>\n"
         f"│\n"
         f"╰─ ✨ {to_small_caps('done')} ✨ ─╯"
      )
      
      await sts.edit(final_text, reply_markup=COMPLETED_BTN)
      
      # Log completion
      try:
         from plugins.logger import BotLogger
         time_taken = f"{completion_mins}m {completion_secs}s"
         
         await BotLogger.log_unequify_completed(
             client, user_id, user_name, bot_name, channel_title,
             total, deleted, time_taken
         )
      except Exception:
         pass
      
      await db.update_last_process(user_id, 'unequify', 'completed')

   except Exception as e:
      logging.error(f"Unequify error: {e}")
      temp.lock[user_id] = False
      await message.reply(f"❌ {to_small_caps('error')}: `{str(e)}`")
   finally:
      temp.CANCEL[user_id] = False
      temp.lock[user_id] = False
      try:
         await bot.stop()
      except Exception:
         pass
