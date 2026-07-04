import os
import re 
import sys
import typing
import asyncio 
import logging 
from database import db 
from config import Config, temp
from pyrogram import Client, filters
from pyrogram.raw.all import layer
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message 
from pyrogram.errors.exceptions.bad_request_400 import AccessTokenExpired, AccessTokenInvalid
from pyrogram.errors import FloodWait
from config import Config
from translation import Translation

from typing import Union, Optional, AsyncGenerator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BTN_URL_REGEX = re.compile(r"(\[([^\[]+?)]\[buttonurl:/{0,2}(.+?)(:same)?])")
BOT_TOKEN_TEXT = "<b>1️⃣ ᴄʀᴇᴀᴛᴇ ᴀ ʙᴏᴛ ᴜsɪɴɢ @BotFather\n2️⃣ ᴛʜᴇɴ ʏᴏᴜ ᴡɪʟʟ ɢᴇᴛ ᴀ ᴍᴇssᴀɢᴇ ᴡɪᴛʜ ʙᴏᴛ ᴛᴏᴋᴇɴ\n3️⃣ ғᴏʀᴡᴀʀᴅ ᴛʜᴀᴛ ᴍᴇssᴀɢᴇ ᴛᴏ ᴍᴇ</b>"
SESSION_STRING_MIN_SIZE = 200

# --- Ported from ftm-forwardbot-latest (phone login support) ---
waiting_messages = {}
# --- end ported block ---


async def start_clone_bot(FwdBot, data=None):
   await FwdBot.start()
   #
   async def iter_messages(
      self, 
      chat_id: Union[int, str], 
      limit: int, 
      offset: int = 0,
      search: str = None,
      filter: "types.TypeMessagesFilter" = None,
      filters: list = None,
      keywords: list = None,
      extensions: list = None,
      media_size: list = None,
      skip_duplicate: list = None,
      ) -> Optional[AsyncGenerator["types.Message", None]]:
        """Iterate through a chat sequentially with filtering support.
        This convenience method does the same as repeatedly calling :meth:`~pyrogram.Client.get_messages` in a loop, thus saving
        you from the hassle of setting up boilerplate code. It is useful for getting the whole chat messages with a
        single call.
        Parameters:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.
                For your personal cloud (Saved Messages) you can simply use "me" or "self".
                For a contact that exists in your Telegram address book you can use his phone number (str).

            limit (``int``):
                Identifier of the last message to be returned.

            offset (``int``, *optional*):
                Identifier of the first message to be returned.
                Defaults to 0.

            filters (``list``, *optional*):
                List of message types to filter out (e.g., ['photo', 'video'])

            keywords (``list``, *optional*):
                List of keywords to filter messages by

            extensions (``list``, *optional*):
                List of file extensions to filter by

            media_size (``list``, *optional*):
                [size_in_mb, 'above'/'below'] to filter by file size

            skip_duplicate (``list``, *optional*):
                [db_uri, chat_id] to skip duplicate files
        Returns:
            ``Generator``: A generator yielding :obj:`~pyrogram.types.Message` objects or "FILTERED"/"DUPLICATE" strings.
        Example:
            .. code-block:: python
                for message in app.iter_messages("pyrogram", 1, 15000):
                    logging.info(message.text)
        """
        # Initialize duplicate checker if needed
        duplicate_ids = set()
        if skip_duplicate and len(skip_duplicate) == 2:
            try:
                from motor.motor_asyncio import AsyncIOMotorClient
                mongo_client = AsyncIOMotorClient(skip_duplicate[0])
                dup_db = mongo_client['autoforward']
                dup_collection = dup_db['duplicate']
                # Load existing duplicate IDs
                async for doc in dup_collection.find({'chat_id': skip_duplicate[1]}):
                    if 'file_unique_id' in doc:
                        duplicate_ids.add(doc['file_unique_id'])
            except Exception:
                skip_duplicate = None

        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            messages = await self.get_messages(chat_id, list(range(current, current+new_diff+1)))
            for message in messages:
                current += 1

                # Skip None messages
                if not message:
                    continue

                # Apply media type filters
                if filters:
                    if 'photo' in filters and message.photo:
                        yield "FILTERED"
                        continue
                    if 'video' in filters and message.video:
                        yield "FILTERED"
                        continue
                    if 'document' in filters and message.document:
                        yield "FILTERED"
                        continue
                    if 'audio' in filters and message.audio:
                        yield "FILTERED"
                        continue
                    if 'voice' in filters and message.voice:
                        yield "FILTERED"
                        continue
                    if 'animation' in filters and message.animation:
                        yield "FILTERED"
                        continue
                    if 'sticker' in filters and message.sticker:
                        yield "FILTERED"
                        continue
                    if 'text' in filters and message.text:
                        yield "FILTERED"
                        continue
                    if 'poll' in filters and message.poll:
                        yield "FILTERED"
                        continue

                # Apply keyword filter
                if keywords:
                    text_to_check = message.text or message.caption or ""
                    has_keyword = any(keyword.lower() in text_to_check.lower() for keyword in keywords)
                    if not has_keyword:
                        yield "FILTERED"
                        continue

                # Apply extension filter
                if extensions and message.document:
                    file_name = message.document.file_name or ""
                    file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ""
                    if file_ext not in [ext.lower().replace('.', '') for ext in extensions]:
                        yield "FILTERED"
                        continue

                # Apply file size filter
                if media_size and len(media_size) == 2:
                    file_size_mb = 0
                    if message.document:
                        file_size_mb = message.document.file_size / (1024 * 1024)
                    elif message.video:
                        file_size_mb = message.video.file_size / (1024 * 1024)
                    elif message.audio:
                        file_size_mb = message.audio.file_size / (1024 * 1024)
                    elif message.photo:
                        file_size_mb = message.photo.file_size / (1024 * 1024) if hasattr(message.photo, 'file_size') else 0

                    size_limit, size_type = media_size[0], media_size[1]
                    if size_type == 'above' and file_size_mb > size_limit:
                        yield "FILTERED"
                        continue
                    elif size_type == 'below' and file_size_mb < size_limit:
                        yield "FILTERED"
                        continue

                # Check for duplicates
                if skip_duplicate:
                    file_unique_id = None
                    if message.document:
                        file_unique_id = message.document.file_unique_id
                    elif message.video:
                        file_unique_id = message.video.file_unique_id
                    elif message.audio:
                        file_unique_id = message.audio.file_unique_id
                    elif message.photo:
                        file_unique_id = message.photo.file_unique_id

                    if file_unique_id:
                        if file_unique_id in duplicate_ids:
                            yield "DUPLICATE"
                            continue
                        else:
                            # Add to duplicate set
                            duplicate_ids.add(file_unique_id)
                            # Save to database
                            try:
                                await dup_collection.insert_one({
                                    'chat_id': skip_duplicate[1],
                                    'file_unique_id': file_unique_id
                                })
                            except Exception:
                                pass

                yield message
   #
   FwdBot.iter_messages = iter_messages
   return FwdBot

class CLIENT: 
  def __init__(self):
     self.api_id = Config.API_ID
     self.api_hash = Config.API_HASH

  def client(self, data, user=None):
     if user == None and data.get('is_bot') == False:
        return Client("USERBOT", self.api_id, self.api_hash, session_string=data.get('session'))
     elif user == True:
        return Client("USERBOT", self.api_id, self.api_hash, session_string=data)
     elif user != False:
        data = data.get('token')
     return Client("BOT", self.api_id, self.api_hash, bot_token=data, in_memory=True)

  async def add_bot(self, bot, message):
     user_id = int(message.from_user.id)
     msg = await bot.ask(chat_id=user_id, text="<b>📤 sᴇɴᴅ ᴍᴇ ʏᴏᴜʀ ʙᴏᴛ ᴛᴏᴋᴇɴ ғʀᴏᴍ @BotFather\n\n📝 ᴇxᴀᴍᴘʟᴇ: 1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ\n\n/cancel - ᴄᴀɴᴄᴇʟ ᴛʜɪs ᴘʀᴏᴄᴇss</b>")
     if msg.text=='/cancel':
        return await msg.reply('<b>❌ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ !</b>')

     bot_token = re.findall(r'\d[0-9]{8,10}:[0-9A-Za-z_-]{35}', msg.text, re.IGNORECASE)
     bot_token = bot_token[0] if bot_token else None
     if not bot_token:
       return await msg.reply_text("<b>❌ ɪɴᴠᴀʟɪᴅ ʙᴏᴛ ᴛᴏᴋᴇɴ! ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴀ ᴠᴀʟɪᴅ ᴛᴏᴋᴇɴ ғʀᴏᴍ @BotFather</b>")

     status_msg = await msg.reply('<b>⏳ ᴠᴇʀɪғʏɪɴɢ ʙᴏᴛ ᴛᴏᴋᴇɴ...</b>')
     try:
       await status_msg.edit('<b>🔄 ᴄᴏɴɴᴇᴄᴛɪɴɢ ᴛᴏ ʙᴏᴛ...</b>')
       _client = await start_clone_bot(self.client(bot_token, False), True)
       await status_msg.edit('<b>📡 ғᴇᴛᴄʜɪɴɢ ʙᴏᴛ ᴅᴇᴛᴀɪʟs...</b>')
     except Exception as e:
       await status_msg.edit(f"<b>⚠️ ʙᴏᴛ ᴇʀʀᴏʀ:</b> `{e}`")
       return

     _bot = _client.me
     details = {
       'id': _bot.id,
       'is_bot': True,
       'user_id': user_id,
       'name': _bot.first_name,
       'token': bot_token,
       'username': _bot.username 
     }
     await status_msg.edit('<b>💾 sᴀᴠɪɴɢ ʙᴏᴛ ᴛᴏ ᴅᴀᴛᴀʙᴀsᴇ...</b>')
     await db.add_bot(details)

     # Log bot addition
     from plugins.logger import BotLogger
     await BotLogger.log_bot_added(_client, user_id, message.from_user.first_name, 'bot')


     success_text = f"<b>✅ ʙᴏᴛ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
     success_text += f"<b>📝 ɴᴀᴍᴇ:</b> <code>{_bot.first_name}</code>\n"
     success_text += f"<b>🆔 ʙᴏᴛ ɪᴅ:</b> <code>{_bot.id}</code>\n"
     if _bot.username:
        success_text += f"<b>🤖 ᴜsᴇʀɴᴀᴍᴇ:</b> @{_bot.username}"
     back_button = InlineKeyboardMarkup([[InlineKeyboardButton('↩ ʙᴀᴄᴋ ᴛᴏ sᴇᴛᴛɪɴɢs', callback_data='settings#main')]])
     await status_msg.edit(success_text, reply_markup=back_button)
     return True

  async def add_session(self, bot, message):
     user_id = int(message.from_user.id)
     text = "<b>⚠️ ᴅɪsᴄʟᴀɪᴍᴇʀ ⚠️</b>\n\n<code>ʏᴏᴜ ᴄᴀɴ ᴜsᴇ ʏᴏᴜʀ sᴇssɪᴏɴ ғᴏʀ ғᴏʀᴡᴀʀᴅ ᴍᴇssᴀɢᴇ ғʀᴏᴍ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ ᴛᴏ ᴀɴᴏᴛʜᴇʀ ᴄʜᴀᴛ.\nᴘʟᴇᴀsᴇ ᴀᴅᴅ ʏᴏᴜʀ ᴘʏʀᴏɢʀᴀᴍ sᴇssɪᴏɴ ᴡɪᴛʜ ʏᴏᴜʀ ᴏᴡɴ ʀɪsᴋ. ᴛʜᴇʀᴇ ɪs ᴀ ᴄʜᴀɴᴄᴇ ᴛᴏ ʙᴀɴ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ. ᴍʏ ᴅᴇᴠᴇʟᴏᴘᴇʀ ɪs ɴᴏᴛ ʀᴇsᴘᴏɴsɪʙʟᴇ ɪғ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ᴍᴀʏ ɢᴇᴛ ʙᴀɴɴᴇᴅ.</code>"
     await bot.send_message(user_id, text=text)
     msg = await bot.ask(chat_id=user_id, text="<b>📝 sᴇɴᴅ ʏᴏᴜʀ ᴘʏʀᴏɢʀᴀᴍ sᴇssɪᴏɴ.\nɢᴇᴛ ɪᴛ ғʀᴏᴍ ᴛʀᴜsᴛᴇᴅ sᴏᴜʀᴄᴇs.\n\n/cancel - ᴄᴀɴᴄᴇʟ ᴛʜᴇ ᴘʀᴏᴄᴇss</b>")
     if msg.text=='/cancel':
        return await msg.reply('<b>❌ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ !</b>')
     elif len(msg.text) < SESSION_STRING_MIN_SIZE:
        return await msg.reply('<b>❌ ɪɴᴠᴀʟɪᴅ sᴇssɪᴏɴ sᴛʀɪɴɢ! ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴀ ᴠᴀʟɪᴅ ᴘʏʀᴏɢʀᴀᴍ sᴇssɪᴏɴ sᴛʀɪɴɢ.</b>')

     status_msg = await msg.reply('<b>⏳ ᴠᴇʀɪғʏɪɴɢ sᴇssɪᴏɴ sᴛʀɪɴɢ...</b>')
     try:
       await status_msg.edit('<b>🔄 ᴄᴏɴɴᴇᴄᴛɪɴɢ ᴛᴏ ᴜsᴇʀʙᴏᴛ...</b>')
       client = await start_clone_bot(self.client(msg.text, True), True)
       await status_msg.edit('<b>📡 ғᴇᴛᴄʜɪɴɢ ᴜsᴇʀ ᴅᴇᴛᴀɪʟs...</b>')
       user = client.me
       details = {
         'id': user.id,
         'is_bot': False,
         'user_id': user_id,
         'name': user.first_name,
         'session': msg.text,
         'username': user.username
       }
       await status_msg.edit('<b>💾 sᴀᴠɪɴɢ ᴜsᴇʀʙᴏᴛ ᴛᴏ ᴅᴀᴛᴀʙᴀsᴇ...</b>')
       await db.add_bot(details)

       # Log bot addition
       from plugins.logger import BotLogger
       await BotLogger.log_bot_added(client, user_id, message.from_user.first_name, 'userbot')

       success_text = f"<b>✅ ᴜsᴇʀʙᴏᴛ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
       success_text += f"<b>📝 ɴᴀᴍᴇ:</b> <code>{user.first_name}</code>\n"
       success_text += f"<b>🆔 ᴜsᴇʀ ɪᴅ:</b> <code>{user.id}</code>\n"
       if user.username:
          success_text += f"<b>👤 ᴜsᴇʀɴᴀᴍᴇ:</b> @{user.username}"
       back_button = InlineKeyboardMarkup([[InlineKeyboardButton('↩ ʙᴀᴄᴋ ᴛᴏ sᴇᴛᴛɪɴɢs', callback_data='settings#main')]])
       await status_msg.edit(success_text, reply_markup=back_button)
       return True
     except Exception as e:
       await status_msg.edit(f"<b>⚠️ ᴜsᴇʀ ʙᴏᴛ ᴇʀʀᴏʀ:</b> `{e}`")
       return

  async def add_phone_session(self, bot, message):
     user_id = int(message.from_user.id)
     text = "<b>⚠️ ᴅɪsᴄʟᴀɪᴍᴇʀ ⚠️</b>\n\n<code>ʏᴏᴜ ᴄᴀɴ ᴜsᴇ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ғᴏʀ ғᴏʀᴡᴀʀᴅɪɴɢ ᴍᴇssᴀɢᴇs ғʀᴏᴍ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛs ᴛᴏ ᴀɴᴏᴛʜᴇʀ ᴄʜᴀᴛ.\nᴘʟᴇᴀsᴇ ʟᴏɢɪɴ ᴡɪᴛʜ ʏᴏᴜʀ ᴏᴡɴ ʀɪsᴋ. ᴛʜᴇʀᴇ ɪs ᴀ ᴄʜᴀɴᴄᴇ ᴛᴏ ʙᴀɴ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ. ᴛʜᴇ ᴅᴇᴠᴇʟᴏᴘᴇʀ ɪs ɴᴏᴛ ʀᴇsᴘᴏɴsɪʙʟᴇ ɪғ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ɢᴇᴛs ʙᴀɴɴᴇᴅ.</code>"
     await bot.send_message(user_id, text=text)

     phone_msg = await bot.ask(chat_id=user_id, text="<b>📱 sᴇɴᴅ ʏᴏᴜʀ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ ᴡɪᴛʜ ᴄᴏᴜɴᴛʀʏ ᴄᴏᴅᴇ\n\n📝 ᴇxᴀᴍᴘʟᴇ: +1234567890\n\n/cancel - ᴄᴀɴᴄᴇʟ ᴛʜᴇ ᴘʀᴏᴄᴇss</b>")
     if phone_msg.text == '/cancel':
        return await phone_msg.reply('<b>❌ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ !</b>')

     phone_number = phone_msg.text.strip()
     if not phone_number.startswith('+'):
        return await phone_msg.reply('<b>❌ ɪɴᴠᴀʟɪᴅ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ! ᴘʟᴇᴀsᴇ ɪɴᴄʟᴜᴅᴇ ᴄᴏᴜɴᴛʀʏ ᴄᴏᴅᴇ sᴛᴀʀᴛɪɴɢ ᴡɪᴛʜ +</b>')

     status_msg = await phone_msg.reply('<b>📨 sᴇɴᴅɪɴɢ ᴏᴛᴘ ᴄᴏᴅᴇ.</b>')
     session_name = f"user_{user_id}"
     try:
        await status_msg.edit('<b>📨 sᴇɴᴅɪɴɢ ᴏᴛᴘ ᴄᴏᴅᴇ..</b>')
        temp_client = Client(
            session_name, 
            api_id=self.api_id, 
            api_hash=self.api_hash, 
            in_memory=True,
            device_model="FᴛᴍBᴏᴛᴢx",
            system_version="Fᴛᴍ Dᴇᴠᴢ",
            app_version="Fᴛᴍ Fᴏʀᴡᴀʀᴅ Bᴏᴛ v2.1"
        )
        await temp_client.connect()
        await status_msg.edit('<b>📨 sᴇɴᴅɪɴɢ ᴏᴛᴘ ᴄᴏᴅᴇ...</b>')
        sent_code = await temp_client.send_code(phone_number)
        await status_msg.edit('<b>✅ ᴏᴛᴘ ᴄᴏᴅᴇ sᴇɴᴛ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>')

        # OTP verification with retry logic
        otp_attempts = 0
        max_otp_attempts = 3
        signed_in = False

        while otp_attempts < max_otp_attempts and not signed_in:
            otp_attempts += 1
            attempt_text = f" (ᴀᴛᴛᴇᴍᴘᴛ {otp_attempts}/{max_otp_attempts})" if otp_attempts > 1 else ""

            code_msg = await bot.ask(chat_id=user_id, text=f"<b>🔐 sᴇɴᴅ ᴛʜᴇ ᴏᴛᴘ ᴄᴏᴅᴇ ʏᴏᴜ ʀᴇᴄᴇɪᴠᴇᴅ ғʀᴏᴍ ᴛᴇʟᴇɢʀᴀᴍ{attempt_text}\n\n⚠️ ɪᴍᴘᴏʀᴛᴀɴᴛ: ᴀᴅᴅ 'FTM' ʙᴇғᴏʀᴇ ʏᴏᴜʀ ᴄᴏᴅᴇ\n📝 ᴇxᴀᴍᴘʟᴇ: ɪғ ᴏᴛᴘ ɪs 12345, sᴇɴᴅ FTM12345\n\n/cancel - ᴄᴀɴᴄᴇʟ ᴛʜᴇ ᴘʀᴏᴄᴇss</b>", timeout=300)

            if code_msg.text == '/cancel':
               await temp_client.disconnect()
               return await code_msg.reply('<b>❌ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ !</b>')

            code_input = code_msg.text.strip().replace(' ', '')

            # Check if code starts with FTM prefix (case-insensitive)
            if not code_input.upper().startswith('FTM'):
               await temp_client.disconnect()
               return await code_msg.reply('<b>❌ ɪɴᴠᴀʟɪᴅ ғᴏʀᴍᴀᴛ! ᴘʟᴇᴀsᴇ ᴀᴅᴅ FTM ʙᴇғᴏʀᴇ ʏᴏᴜʀ ᴏᴛᴘ ᴄᴏᴅᴇ.\n\n📝 ᴇxᴀᴍᴘʟᴇ: FTM12345</b>')

            # Remove FTM prefix (first 3 characters) to get actual OTP code
            code = code_input[3:].strip()

            if not code:
               await temp_client.disconnect()
               return await code_msg.reply('<b>❌ ɴᴏ ᴏᴛᴘ ᴄᴏᴅᴇ ғᴏᴜɴᴅ ᴀғᴛᴇʀ FTM!\n\n📝 ᴇxᴀᴍᴘʟᴇ: FTM12345</b>')

            try:
               await temp_client.sign_in(phone_number, sent_code.phone_code_hash, code)
               signed_in = True
            except Exception as e:
               error_str = str(e)

               if "PHONE_CODE_INVALID" in error_str:
                  if otp_attempts < max_otp_attempts:
                     await code_msg.reply(f'<b>❌ ɪɴᴠᴀʟɪᴅ ᴏᴛᴘ ᴄᴏᴅᴇ! ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.\n\n🔄 ʀᴇᴍᴀɪɴɪɴɢ ᴀᴛᴛᴇᴍᴘᴛs: {max_otp_attempts - otp_attempts}</b>')
                     continue
                  else:
                     await temp_client.disconnect()
                     return await code_msg.reply('<b>❌ ᴍᴀxɪᴍᴜᴍ ᴀᴛᴛᴇᴍᴘᴛs ʀᴇᴀᴄʜᴇᴅ! ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ.\n\nᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>')

               elif "Two-steps verification" in error_str or "PASSWORD_HASH_INVALID" in error_str or "SessionPasswordNeeded" in error_str or "SESSION_PASSWORD_NEEDED" in error_str:
                  # 2FA password verification with retry logic
                  password_attempts = 0
                  max_password_attempts = 2
                  password_verified = False

                  while password_attempts < max_password_attempts and not password_verified:
                     password_attempts += 1
                     pwd_attempt_text = f" (ᴀᴛᴛᴇᴍᴘᴛ {password_attempts}/{max_password_attempts})" if password_attempts > 1 else ""

                     password_msg = await bot.ask(chat_id=user_id, text=f"<b>🔒 ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ʜᴀs 2ғᴀ ᴇɴᴀʙʟᴇᴅ. sᴇɴᴅ ʏᴏᴜʀ ᴘᴀssᴡᴏʀᴅ{pwd_attempt_text}\n\n/cancel - ᴄᴀɴᴄᴇʟ ᴛʜᴇ ᴘʀᴏᴄᴇss</b>", timeout=300)

                     if password_msg.text == '/cancel':
                        await temp_client.disconnect()
                        return await password_msg.reply('<b>❌ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ !</b>')

                     try:
                        await temp_client.check_password(password_msg.text)
                        password_verified = True
                        signed_in = True
                        break
                     except Exception as pwd_error:
                        pwd_error_str = str(pwd_error)
                        if "PASSWORD_HASH_INVALID" in pwd_error_str:
                           if password_attempts < max_password_attempts:
                              await password_msg.reply(f'<b>❌ ɪɴᴠᴀʟɪᴅ ᴘᴀssᴡᴏʀᴅ! ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.\n\n🔄 ʀᴇᴍᴀɪɴɪɴɢ ᴀᴛᴛᴇᴍᴘᴛs: {max_password_attempts - password_attempts}</b>')
                              continue
                           else:
                              await temp_client.disconnect()
                              return await password_msg.reply('<b>❌ ᴍᴀxɪᴍᴜᴍ ᴘᴀssᴡᴏʀᴅ ᴀᴛᴛᴇᴍᴘᴛs ʀᴇᴀᴄʜᴇᴅ! ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ.\n\nᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>')
                        else:
                           await temp_client.disconnect()
                           return await password_msg.reply(f'<b>❌ ᴜɴᴇxᴘᴇᴄᴛᴇᴅ ᴇʀʀᴏʀ:</b> `{pwd_error_str}`')

               else:
                  await temp_client.disconnect()
                  return await code_msg.reply(f'<b>❌ ʟᴏɢɪɴ ᴇʀʀᴏʀ:</b> `{error_str}`')

        if not signed_in:
           await temp_client.disconnect()
           return await status_msg.edit('<b>❌ ʟᴏɢɪɴ ғᴀɪʟᴇᴅ!</b>')

        # Save session string
        await status_msg.edit('<b>💾 sᴀᴠɪɴɢ sᴇssɪᴏɴ...</b>')
        session_string = await temp_client.export_session_string()
        await temp_client.disconnect()

        # Create new client with session string
        await status_msg.edit('<b>🔄 ᴠᴇʀɪғʏɪɴɢ sᴇssɪᴏɴ...</b>')
        client = await start_clone_bot(self.client(session_string, True), True)
        user = client.me
        details = {
          'id': user.id,
          'is_bot': False,
          'user_id': user_id,
          'name': user.first_name,
          'session': session_string,
          'username': user.username
        }
        await db.add_bot(details)

        # Log bot addition
        from plugins.logger import BotLogger
        await BotLogger.log_bot_added(client, user_id, message.from_user.first_name, 'userbot')

        success_text = f"<b>✅ ᴜsᴇʀʙᴏᴛ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
        success_text += f"<b>📝 ɴᴀᴍᴇ:</b> <code>{user.first_name}</code>\n"
        success_text += f"<b>🆔 ᴜsᴇʀ ɪᴅ:</b> <code>{user.id}</code>\n"
        if user.username:
           success_text += f"<b>👤 ᴜsᴇʀɴᴀᴍᴇ:</b> @{user.username}"

        back_button = InlineKeyboardMarkup([[InlineKeyboardButton('↩ ʙᴀᴄᴋ ᴛᴏ sᴇᴛᴛɪɴɢs', callback_data='settings#main')]])
        await bot.send_message(user_id, success_text, reply_markup=back_button)
        return True

     except asyncio.exceptions.TimeoutError:
        if 'temp_client' in locals():
           await temp_client.disconnect()
        return await status_msg.edit('<b>⏱️ ᴘʀᴏᴄᴇss ʜᴀs ʙᴇᴇɴ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴄᴀɴᴄᴇʟʟᴇᴅ</b>')
     except Exception as e:
        if 'temp_client' in locals():
           await temp_client.disconnect()
        return await status_msg.edit(f'<b>❌ ᴜsᴇʀ ʙᴏᴛ ᴇʀʀᴏʀ:</b> `{e}`')

# OLD RESET COMMAND - DISABLED
# Replaced with enhanced /reset command in plugins/commands.py
# @Client.on_message(filters.private & filters.command('reset'))
# async def forward_tag(bot, m):
#    default = await db.get_configs("01")
#    temp.CONFIGS[m.from_user.id] = default
#    await db.update_configs(m.from_user.id, default)
#    await m.reply("✅ sᴜᴄᴄᴇssғᴜʟʟʏ sᴇᴛᴛɪɴɢs ʀᴇsᴇᴛᴇᴅ ✔️")

@Client.on_message(filters.command('resetall'))
async def resetall(bot, message):
  from plugins.utils import to_small_caps
  if message.from_user.id not in Config.BOT_OWNER_ID:
      return await message.reply_text(
          f"🚫 <b>{to_small_caps('this command is not for you')}</b> 🚫\n\n"
          f"⚠️ {to_small_caps('only bot owner can use this command')}"
      )
  users = await db.get_all_users()
  sts = await message.reply("⚙️ **ᴘʀᴏᴄᴇssɪɴɢ**")
  TEXT = "total: {}\nsuccess: {}\nfailed: {}\nexcept: {}"
  total = success = failed = already = 0
  ERRORS = []
  async for user in users:
      user_id = user['id']
      default = await get_configs(user_id)
      default['db_uri'] = None
      total += 1
      if total %10 == 0:
         await sts.edit(TEXT.format(total, success, failed, already))
      try: 
         await db.update_configs(user_id, default)
         success += 1
      except Exception as e:
         ERRORS.append(e)
         failed += 1
  if ERRORS:
     await message.reply(ERRORS[:100])
  await sts.edit("✅ ᴄᴏᴍᴘʟᴇᴛᴇᴅ\n" + TEXT.format(total, success, failed, already))

async def get_configs(user_id):
  #configs = temp.CONFIGS.get(user_id)
  #if not configs:
  configs = await db.get_configs(user_id)
  #temp.CONFIGS[user_id] = configs 
  return configs

async def update_configs(user_id, key, value):
    config = await get_configs(user_id)

    # Handle nested keys like 'filters.text'
    if '.' in key:
        keys = key.split('.')
        nested_config = config
        for k in keys[:-1]:
            if k not in nested_config:
                nested_config[k] = {}
            nested_config = nested_config[k]
        nested_config[keys[-1]] = value
    else:
        config[key] = value

    # Use the new update_config_key method for atomic updates
    await db.update_config_key(user_id, key, value)
    # Also update the full config to ensure consistency
    await db.update_configs(user_id, config)

def parse_buttons(text, markup=True):
    buttons = []
    for match in BTN_URL_REGEX.finditer(text):
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        if n_escapes % 2 == 0:
            if bool(match.group(4)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(3).replace(" ", "")))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(3).replace(" ", ""))])
    if markup and buttons:
       buttons = InlineKeyboardMarkup(buttons)
    return buttons if buttons else None