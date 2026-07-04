import asyncio
from database import db
from translation import Translation
from pyrogram import Client, filters
from .test import get_configs, update_configs, CLIENT, parse_buttons
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CLIENT = CLIENT()

@Client.on_message(filters.command('settings'))
async def settings(client, message):
   await message.delete()
   await message.reply_text(
     "<b>change your settings as your wish</b>",
     reply_markup=main_buttons()
     )

@Client.on_callback_query(filters.regex(r'^settings'))
async def settings_query(bot, query):
  user_id = query.from_user.id
  
  # Answer the callback query immediately to remove loading state
  await query.answer()
  
  i, type = query.data.split("#")
  buttons = [[InlineKeyboardButton('↩ Back', callback_data="settings#main")]]

  if type=="main":
     await query.message.edit_text(
       "<b>change your settings as your wish</b>",
       reply_markup=main_buttons())

  elif type=="bots":
     buttons = []
     _bot = await db.get_bot(user_id)
     if _bot is not None:
        buttons.append([InlineKeyboardButton(_bot['name'],
                         callback_data=f"settings#editbot")])
     else:
        buttons.append([InlineKeyboardButton('✚ Add bot ✚',
                         callback_data="settings#addbot")])
        buttons.append([InlineKeyboardButton('✚ Add User bot ✚',
                         callback_data="settings#adduserbot")])
     buttons.append([InlineKeyboardButton('↩ Back',
                      callback_data="settings#main")])
     await query.message.edit_text(
       "<b><u>My Bots</b></u>\n\n<b>You can manage your bots in here</b>",
       reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="addbot":
     await query.message.delete()
     result = await CLIENT.add_bot(bot, query)
     if result != True: return
     
     # Log bot addition
     from plugins.logger import BotLogger
     bot_data = await db.get_bot(user_id)
     if bot_data:
         await BotLogger.log_bot_added(bot, user_id, query.from_user.first_name, 'bot')

  elif type=="adduserbot":
     buttons = [
        [InlineKeyboardButton('📱 ʟᴏɢɪɴ ᴜsɪɴɢ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ', callback_data="settings#userbot_phone")],
        [InlineKeyboardButton('🔐 ʟᴏɢɪɴ ᴜsɪɴɢ sᴛʀɪɴɢ sᴇssɪᴏɴ', callback_data="settings#userbot_session")],
        [InlineKeyboardButton('↩ ʙᴀᴄᴋ', callback_data="settings#bots")]
     ]
     await query.message.edit_text(
        "<b><u>ᴀᴅᴅ ᴜsᴇʀ ʙᴏᴛ</b></u>\n\n<b>ᴄʜᴏᴏsᴇ ʏᴏᴜʀ ʟᴏɢɪɴ ᴍᴇᴛʜᴏᴅ:</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="userbot_session":
     await query.message.delete()
     user = await CLIENT.add_session(bot, query)
     if user != True: return
     
     # Log userbot addition
     from plugins.logger import BotLogger
     bot_data = await db.get_bot(user_id)
     if bot_data:
         await BotLogger.log_bot_added(bot, user_id, query.from_user.first_name, 'userbot')

  elif type=="userbot_phone":
     await query.message.delete()
     user = await CLIENT.add_phone_session(bot, query)
     if user != True: return
     
     # Log userbot addition
     from plugins.logger import BotLogger
     bot_data = await db.get_bot(user_id)
     if bot_data:
         await BotLogger.log_bot_added(bot, user_id, query.from_user.first_name, 'userbot')

  elif type=="channels":
     buttons = []
     channels = await db.get_user_channels(user_id)
     for channel in channels:
        topic_suffix = " (topic)" if channel.get('thread_id') else ""
        buttons.append([InlineKeyboardButton(f"{channel['title']}{topic_suffix}",
                         callback_data=f"settings#editchannels_{channel['chat_id']}")])
     buttons.append([InlineKeyboardButton('✚ Add Channel ✚',
                      callback_data="settings#addchannel")])
     buttons.append([InlineKeyboardButton('↩ Back',
                      callback_data="settings#main")])
     await query.message.edit_text(
       "<b><u>My Channels</b></u>\n\n<b>you can manage your target chats in here</b>",
       reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="addchannel":
     await query.message.delete()
     try:
         text = await bot.send_message(user_id, "<b>❪ sᴇᴛ ᴛᴀʀɢᴇᴛ ᴄʜᴀᴛ ❫\n\n📨 ғᴏʀᴡᴀʀᴅ ᴀ ᴍᴇssᴀɢᴇ ғʀᴏᴍ ʏᴏᴜʀ ᴛᴀʀɢᴇᴛ ᴄʜᴀᴛ\n\n/cancel - ᴄᴀɴᴄᴇʟ ᴛʜɪs ᴘʀᴏᴄᴇss</b>")
         from plugins.conversation import listen, is_forwarded_or_cancel
         chat_ids = await listen(bot, user_id, filter_func=is_forwarded_or_cancel, timeout=300)
         if chat_ids is None:
            return await text.edit_text('<b>⏱️ ᴘʀᴏᴄᴇss ʜᴀs ʙᴇᴇɴ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴄᴀɴᴄᴇʟʟᴇᴅ</b>', reply_markup=InlineKeyboardMarkup(buttons))
         if chat_ids.text and chat_ids.text.startswith("/cancel"):
            await chat_ids.delete()
            return await text.edit_text(
                  "<b>❌ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟᴇᴅ</b>",
                  reply_markup=InlineKeyboardMarkup(buttons))
         elif not chat_ids.forward_date:
            await chat_ids.delete()
            return await text.edit_text("<b>❌ ᴛʜɪs ɪs ɴᴏᴛ ᴀ ғᴏʀᴡᴀʀᴅ ᴍᴇssᴀɢᴇ</b>")
         else:
            chat_id = chat_ids.forward_from_chat.id
            title = chat_ids.forward_from_chat.title
            username = chat_ids.forward_from_chat.username
            username_display = "@" + username if username else "private"
         thread_id = chat_ids.message_thread_id if chat_ids.is_topic_message else None
         chat = await db.add_channel(user_id, chat_id, title, username_display, thread_id=thread_id)
         await chat_ids.delete()
         if chat:
            # Log channel addition
            from plugins.logger import BotLogger
            await BotLogger.log_channel_added(bot, user_id, query.from_user.first_name, 'target', title, chat_id)
            
            success_text = f"<b>✅ ᴄʜᴀɴɴᴇʟ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
            success_text += f"<b>📝 ɴᴀᴍᴇ:</b> <code>{title}</code>\n"
            success_text += f"<b>🆔 ᴄʜᴀɴɴᴇʟ ɪᴅ:</b> <code>{chat_id}</code>\n"
            if thread_id:
               success_text += f"\n<b>🧵 ᴛᴏᴘɪᴄ ɪᴅ:</b> <code>{thread_id}</code>"
            if username:
               success_text += f"<b>📢 ᴜsᴇʀɴᴀᴍᴇ:</b> @{username}"
            await text.edit_text(success_text, reply_markup=InlineKeyboardMarkup(buttons))
         else:
            await text.edit_text("<b>⚠️ ᴛʜɪs ᴄʜᴀɴɴᴇʟ ᴀʟʀᴇᴀᴅʏ ᴀᴅᴅᴇᴅ</b>", reply_markup=InlineKeyboardMarkup(buttons))
     except asyncio.exceptions.TimeoutError:
         await text.edit_text('<b>⏱️ ᴘʀᴏᴄᴇss ʜᴀs ʙᴇᴇɴ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴄᴀɴᴄᴇʟʟᴇᴅ</b>', reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="editbot":
     bot = await db.get_bot(user_id)
     TEXT = Translation.BOT_DETAILS if bot['is_bot'] else Translation.USER_DETAILS
     buttons = [[InlineKeyboardButton('❌ Remove ❌', callback_data=f"settings#removebot")
               ],
               [InlineKeyboardButton('↩ Back', callback_data="settings#bots")]]
     await query.message.edit_text(
        TEXT.format(bot['name'], bot['id'], bot['username']),
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="removebot":
     # Log bot removal
     from plugins.logger import BotLogger
     await BotLogger.log_bot_removed(bot, user_id, query.from_user.first_name)
     
     await db.remove_bot(user_id)
     await query.message.edit_text(
        "<b>successfully updated</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type.startswith("editchannels"):
     chat_id = type.split('_')[1]
     chat = await db.get_channel_details(user_id, chat_id)
     topic_line = f"\n<b>- TOPIC ID: </b> <code>{chat['thread_id']}</code>" if chat.get('thread_id') else ""
     buttons = [[InlineKeyboardButton('❌ Remove ❌', callback_data=f"settings#removechannel_{chat_id}")
               ],
               [InlineKeyboardButton('↩ Back', callback_data="settings#channels")]]
     await query.message.edit_text(
        f"<b><u>📄 CHANNEL DETAILS</b></u>\n\n<b>- TITLE:</b> <code>{chat['title']}</code>\n<b>- CHANNEL ID: </b> <code>{chat['chat_id']}</code>{topic_line}\n<b>- USERNAME:</b> {chat['username']}",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type.startswith("removechannel"):
     chat_id = type.split('_')[1]
     chat = await db.get_channel_details(user_id, chat_id)
     await db.remove_channel(user_id, chat_id)
     
     # Log channel removal
     from plugins.logger import BotLogger
     await BotLogger.log_channel_removed(bot, user_id, query.from_user.first_name, 'target', chat['title'], int(chat_id))
     
     await query.message.edit_text(
        "<b>successfully updated</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="caption":
     buttons = []
     data = await get_configs(user_id)
     caption = data['caption']
     if caption is None:
        buttons.append([InlineKeyboardButton('✚ Add Caption ✚',
                      callback_data="settings#addcaption")])
     else:
        buttons.append([InlineKeyboardButton('See Caption',
                      callback_data="settings#seecaption")])
        buttons[-1].append(InlineKeyboardButton('🗑️ Delete Caption',
                      callback_data="settings#deletecaption"))
     buttons.append([InlineKeyboardButton('↩ Back',
                      callback_data="settings#main")])
     await query.message.edit_text(
        "<b>✏️ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ ✏️</b>\n\n"
        "<b>📝 ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ sᴇᴛᴛɪɴɢs</b>\n"
        "<i>ʏᴏᴜ ᴄᴀɴ sᴇᴛ ᴀ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ ᴛᴇᴍᴘʟᴀᴛᴇ ғᴏʀ ᴠɪᴅᴇᴏs, ᴅᴏᴄᴜᴍᴇɴᴛs ᴀɴᴅ ᴀᴜᴅɪᴏ ғɪʟᴇs.</i>\n\n"
        "<b>🎯 ᴀᴠᴀɪʟᴀʙʟᴇ ᴠᴀʀɪᴀʙʟᴇs:</b>\n"
        "• <code>{filename}</code> - ғɪʟᴇ ɴᴀᴍᴇ\n"
        "• <code>{size}</code> - ғɪʟᴇ sɪᴢᴇ\n"
        "• <code>{caption}</code> - ᴏʀɪɢɪɴᴀʟ ᴄᴀᴘᴛɪᴏɴ\n"
        "• <code>{year}</code> - ғɪʟᴇ ʏᴇᴀʀ ᴇxᴛʀᴀᴄᴛᴇᴅ ғʀᴏᴍ ɴᴀᴍᴇ\n"
        "• <code>{language}</code> - ᴀᴜᴅɪᴏ ʟᴀɴɢᴜᴀɢᴇs ᴅᴇᴛᴇᴄᴛᴇᴅ\n"
        "• <code>{quality}</code> - ᴠɪᴅᴇᴏ ǫᴜᴀʟɪᴛʏ (480p, 720p, 1080p, ᴇᴛᴄ)\n"
        "• <code>{type}</code> - ᴍᴇᴅɪᴀ ᴛʏᴘᴇ (ᴠɪᴅᴇᴏ, ᴀᴜᴅɪᴏ, ᴅᴏᴄᴜᴍᴇɴᴛ)\n\n"
        "<b>⚠️ ɴᴏᴛᴇ:</b> <i>ᴠᴀʀɪᴀʙʟᴇs ᴏɴʟʏ ᴡᴏʀᴋ ᴏɴ ᴠɪᴅᴇᴏs, ᴀᴜᴅɪᴏ ᴀɴᴅ ᴅᴏᴄᴜᴍᴇɴᴛs. ᴘʜᴏᴛᴏs ᴡɪʟʟ ᴋᴇᴇᴘ ᴏʀɪɢɪɴᴀʟ ᴄᴀᴘᴛɪᴏɴ.</i>\n\n"
        "<b>🎨 ʜᴛᴍʟ ғᴏʀᴍᴀᴛᴛɪɴɢ:</b>\n"
        "• <code>&lt;b&gt;ʙᴏʟᴅ&lt;/b&gt;</code>\n"
        "• <code>&lt;i&gt;ɪᴛᴀʟɪᴄ&lt;/i&gt;</code>\n"
        "• <code>&lt;u&gt;ᴜɴᴅᴇʀʟɪɴᴇ&lt;/u&gt;</code>\n"
        "• <code>&lt;s&gt;sᴛʀɪᴋᴇ&lt;/s&gt;</code>\n"
        "• <code>&lt;code&gt;ᴍᴏɴᴏsᴘᴀᴄᴇ&lt;/code&gt;</code>\n"
        "• <code>&lt;spoiler&gt;sᴘᴏɪʟᴇʀ&lt;/spoiler&gt;</code>\n"
        "• <code>&lt;a href='url'&gt;ʟɪɴᴋ ᴛᴇxᴛ&lt;/a&gt;</code>\n\n"
        "<b>📌 ᴇxᴀᴍᴘʟᴇ ᴄᴀᴘᴛɪᴏɴ:</b>\n"
        "<code>&lt;b&gt;{filename}&lt;/b&gt;\n"
        "📊 sɪᴢᴇ: {size}\n"
        "🎬 ǫᴜᴀʟɪᴛʏ: {quality}\n"
        "📅 ʏᴇᴀʀ: {year}\n"
        "🗣️ ʟᴀɴɢᴜᴀɢᴇ: {language}</code>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="seecaption":
     data = await get_configs(user_id)
     buttons = [[InlineKeyboardButton('🖋️ Edit Caption',
                  callback_data="settings#addcaption")
               ],[
               InlineKeyboardButton('↩ Back',
                 callback_data="settings#caption")]]
     await query.message.edit_text(
        f"<b><u>YOUR CUSTOM CAPTION</b></u>\n\n<code>{data['caption']}</code>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="deletecaption":
     await update_configs(user_id, 'caption', None)
     
     # Log config update
     from plugins.logger import BotLogger
     await BotLogger.log_config_updated(bot, user_id, query.from_user.first_name, 'custom_caption', 'deleted')
     
     await query.message.edit_text(
        "<b>successfully updated</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="addcaption":
     await query.message.delete()
     try:
         text = await bot.send_message(query.message.chat.id, 
            "<b>✏️ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ</b>\n\n"
            "<b>💬 sᴇɴᴅ ʏᴏᴜʀ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ ᴛᴇᴍᴘʟᴀᴛᴇ:</b>\n\n"
            "<b>🎯 ᴀᴠᴀɪʟᴀʙʟᴇ ᴠᴀʀɪᴀʙʟᴇs:</b>\n"
            "<code>{filename}</code>, <code>{size}</code>, <code>{caption}</code>, <code>{year}</code>, <code>{language}</code>, <code>{quality}</code>, <code>{type}</code>\n\n"
            "/cancel - <code>ᴄᴀɴᴄᴇʟ ᴛʜɪs ᴘʀᴏᴄᴇss</code>")
         from plugins.conversation import listen, is_text_or_cancel
         caption = await listen(bot, user_id, filter_func=is_text_or_cancel, timeout=300)
         if caption is None:
            return await text.edit_text('<b>⏱️ ᴘʀᴏᴄᴇss ʜᴀs ʙᴇᴇɴ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴄᴀɴᴄᴇʟʟᴇᴅ</b>', reply_markup=InlineKeyboardMarkup(buttons))
         if caption.text and caption.text.startswith("/cancel"):
            await caption.delete()
            return await text.edit_text(
                  "<b>process canceled !</b>",
                  reply_markup=InlineKeyboardMarkup(buttons))
         try:
            caption.text.format(filename='', size='', caption='', year='', language='', quality='', type='')
         except KeyError as e:
            await caption.delete()
            return await text.edit_text(
               f"<b>❌ ɪɴᴠᴀʟɪᴅ ᴠᴀʀɪᴀʙʟᴇ: {e}\n\nᴀʟʟᴏᴡᴇᴅ ᴠᴀʀɪᴀʙʟᴇs: {{filename}}, {{size}}, {{caption}}, {{year}}, {{language}}, {{quality}}, {{type}}</b>",
               reply_markup=InlineKeyboardMarkup(buttons))
         await update_configs(user_id, 'caption', caption.text)
         
         # Log config update
         from plugins.logger import BotLogger
         await BotLogger.log_config_updated(bot, user_id, query.from_user.first_name, 'custom_caption', caption.text[:100])
         
         await caption.delete()
         await text.edit_text(
            "<b>successfully updated</b>",
            reply_markup=InlineKeyboardMarkup(buttons))
     except asyncio.exceptions.TimeoutError:
         await text.edit_text('<b>⏱️ ᴘʀᴏᴄᴇss ʜᴀs ʙᴇᴇɴ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴄᴀɴᴄᴇʟʟᴇᴅ</b>', reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="button":
     buttons = []
     button = (await get_configs(user_id))['button']
     if button is None:
        buttons.append([InlineKeyboardButton('✚ Add Button ✚',
                      callback_data="settings#addbutton")])
     else:
        buttons.append([InlineKeyboardButton('👀 See Button',
                      callback_data="settings#seebutton")])
        buttons[-1].append(InlineKeyboardButton('🗑️ Remove Button ',
                      callback_data="settings#deletebutton"))
     buttons.append([InlineKeyboardButton('↩ Back',
                      callback_data="settings#main")])
     await query.message.edit_text(
        "<b><u>CUSTOM BUTTON</b></u>\n\n<b>You can set a inline button to messages.</b>\n\n<b><u>FORMAT:</b></u>\n`[FᴛᴍBᴏᴛᴢx][buttonurl:https://t.me/ftmbotzx]`\n",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="addbutton":
     await query.message.delete()
     try:
         txt = await bot.send_message(user_id, text="**Send your custom button.\n\nFORMAT:**\n`[FᴛᴍBᴏᴛᴢx][buttonurl:https://t.me/ftmbotzx]`\n\n/cancel - ᴄᴀɴᴄᴇʟ ᴛʜɪs ᴘʀᴏᴄᴇss")
         from plugins.conversation import listen, is_text_or_cancel
         ask = await listen(bot, user_id, filter_func=is_text_or_cancel, timeout=300)
         if ask is None:
            return await txt.edit_text('Process has been automatically cancelled', reply_markup=InlineKeyboardMarkup(buttons))
         if ask.text and ask.text.startswith("/cancel"):
            await ask.delete()
            return await txt.edit_text('Process cancelled', reply_markup=InlineKeyboardMarkup(buttons))
         button = parse_buttons(ask.text.html)
         if not button:
            await ask.delete()
            return await txt.edit_text("**INVALID BUTTON**")
         await update_configs(user_id, 'button', ask.text.html)
         
         # Log config update
         from plugins.logger import BotLogger
         await BotLogger.log_config_updated(bot, user_id, query.from_user.first_name, 'custom_button', ask.text.html[:100])
         
         await ask.delete()
         await txt.edit_text("**Successfully button added**",
            reply_markup=InlineKeyboardMarkup(buttons))
     except asyncio.exceptions.TimeoutError:
         await txt.edit_text('Process has been automatically cancelled', reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="seebutton":
      button = (await get_configs(user_id))['button']
      button = parse_buttons(button, markup=False)
      button.append([InlineKeyboardButton("↩ Back", "settings#button")])
      await query.message.edit_text(
         "**YOUR CUSTOM BUTTON**",
         reply_markup=InlineKeyboardMarkup(button))

  elif type=="deletebutton":
     await update_configs(user_id, 'button', None)
     
     # Log config update
     from plugins.logger import BotLogger
     await BotLogger.log_config_updated(bot, user_id, query.from_user.first_name, 'custom_button', 'deleted')
     
     await query.message.edit_text(
        "**Successfully button deleted**",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="database":
     buttons = []
     db_uri = (await get_configs(user_id))['db_uri']
     if db_uri is None:
        buttons.append([InlineKeyboardButton('✚ Add Url ✚',
                      callback_data="settings#addurl")])
     else:
        buttons.append([InlineKeyboardButton('👀 See Url',
                      callback_data="settings#seeurl")])
        buttons[-1].append(InlineKeyboardButton('🗑️ Remove Url ',
                      callback_data="settings#deleteurl"))
     buttons.append([InlineKeyboardButton('↩ Back',
                      callback_data="settings#main")])
     await query.message.edit_text(
        "<b><u>DATABASE</u>\n\nDatabase is required for store your duplicate messages permenant. other wise stored duplicate media may be disappeared when after bot restart.</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="addurl":
     await query.message.delete()
     uri = await bot.ask(user_id, "<b>please send your mongodb url.</b>\n\n<i>get your Mongodb url from [here](https://mongodb.com)</i>", disable_web_page_preview=True)
     if uri.text=="/cancel":
        return await uri.reply_text(
                  "<b>process canceled !</b>",
                  reply_markup=InlineKeyboardMarkup(buttons))
     if not uri.text.startswith("mongodb+srv://") and not uri.text.endswith("majority"):
        return await uri.reply("<b>Invalid Mongodb Url</b>",
                   reply_markup=InlineKeyboardMarkup(buttons))
     await update_configs(user_id, 'db_uri', uri.text)
     
     # Log config update
     from plugins.logger import BotLogger
     await BotLogger.log_config_updated(bot, user_id, uri.from_user.first_name, 'database_url', 'configured')
     
     await uri.reply("**Successfully database url added**",
             reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="seeurl":
     db_uri = (await get_configs(user_id))['db_uri']
     await query.answer(f"DATABASE URL: {db_uri}", show_alert=True)

  elif type=="deleteurl":
     await update_configs(user_id, 'db_uri', None)
     await query.message.edit_text(
        "**Successfully your database url deleted**",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="filters":
     await query.message.edit_text(
        "<b><u>💠 CUSTOM FILTERS 💠</b></u>\n\n**configure the type of messages which you want forward**",
        reply_markup=await filters_buttons(user_id))

  elif type=="nextfilters":
     await query.edit_message_reply_markup(
        reply_markup=await next_filters_buttons(user_id))

  elif type.startswith("updatefilter"):
     i, key, value = type.split('-')
     
     # Determine if this is a nested filter or top-level config
     nested_filters = ['text', 'document', 'video', 'photo', 'audio', 'voice', 'animation', 'sticker', 'poll']
     config_key = f'filters.{key}' if key in nested_filters else key
     
     if value=="True":
        await update_configs(user_id, config_key, False)
     else:
        await update_configs(user_id, config_key, True)
     if key in ['poll', 'protect']:
        return await query.edit_message_reply_markup(
           reply_markup=await next_filters_buttons(user_id))
     await query.edit_message_reply_markup(
        reply_markup=await filters_buttons(user_id))

  elif type.startswith("file_size"):
    settings = await get_configs(user_id)
    size = settings.get('file_size', 0)
    i, limit = size_limit(settings['size_limit'])
    await query.message.edit_text(
       f'<b><u>SIZE LIMIT</b></u><b>\n\nyou can set file size limit to forward\n\nStatus: files with {limit} `{size} MB` will forward</b>',
       reply_markup=size_button(size))

  elif type.startswith("update_size"):
    i, size = type.split('-')
    size = int(size)
    if size < 0:
      size = 0
    if size > 2000:
      return await query.answer("size limit exceeded", show_alert=True)
    await update_configs(user_id, 'file_size', size)
    i, limit = size_limit((await get_configs(user_id))['size_limit'])
    await query.message.edit_text(
       f'<b><u>SIZE LIMIT</b></u><b>\n\nyou can set file size limit to forward\n\nStatus: files with {limit} `{size} MB` will forward</b>',
       reply_markup=size_button(size))

  elif type.startswith('update_limit'):
    i, limit, size = type.split('-')
    limit, sts = size_limit(limit)
    await update_configs(user_id, 'size_limit', limit)
    await query.message.edit_text(
       f'<b><u>SIZE LIMIT</b></u><b>\n\nyou can set file size limit to forward\n\nStatus: files with {sts} `{size} MB` will forward</b>',
       reply_markup=size_button(int(size)))

  elif type == "add_extension":
    await query.message.delete()
    ext = await bot.ask(user_id, text="**please send your extensions (seperete by space)**")
    if ext.text == '/cancel':
       return await ext.reply_text(
                  "<b>process canceled</b>",
                  reply_markup=InlineKeyboardMarkup(buttons))
    extensions = ext.text.split(" ")
    extension = (await get_configs(user_id))['extension']
    if extension:
        for extn in extensions:
            extension.append(extn)
    else:
        extension = extensions
    await update_configs(user_id, 'extension', extension)
    await ext.reply_text(
        f"**successfully updated**",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type == "get_extension":
    extensions = (await get_configs(user_id))['extension']
    btn = extract_btn(extensions)
    btn.append([InlineKeyboardButton('✚ ADD ✚', 'settings#add_extension')])
    btn.append([InlineKeyboardButton('Remove all', 'settings#rmve_all_extension')])
    btn.append([InlineKeyboardButton('↩ Back', 'settings#main')])
    await query.message.edit_text(
        text='<b><u>EXTENSIONS</u></b>\n\n**Files with these extiontions will not forward**',
        reply_markup=InlineKeyboardMarkup(btn))

  elif type == "rmve_all_extension":
    await update_configs(user_id, 'extension', None)
    await query.message.edit_text(text="**successfully deleted**",
                                   reply_markup=InlineKeyboardMarkup(buttons))
  elif type == "add_keyword":
    await query.message.delete()
    ask = await bot.ask(user_id, text="**please send the keywords (seperete by space)**")
    if ask.text == '/cancel':
       return await ask.reply_text(
                  "<b>process canceled</b>",
                  reply_markup=InlineKeyboardMarkup(buttons))
    keywords = ask.text.split(" ")
    keyword = (await get_configs(user_id))['keywords']
    if keyword:
        for word in keywords:
            keyword.append(word)
    else:
        keyword = keywords
    await update_configs(user_id, 'keywords', keyword)
    await ask.reply_text(
        f"**successfully updated**",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type == "get_keyword":
    keywords = (await get_configs(user_id))['keywords']
    btn = extract_btn(keywords)
    btn.append([InlineKeyboardButton('✚ ADD ✚', 'settings#add_keyword')])
    btn.append([InlineKeyboardButton('Remove all', 'settings#rmve_all_keyword')])
    btn.append([InlineKeyboardButton('↩ Back', 'settings#main')])
    await query.message.edit_text(
        text='<b><u>KEYWORDS</u></b>\n\n**File with these keywords in file name will forwad**',
        reply_markup=InlineKeyboardMarkup(btn))

  elif type == "rmve_all_keyword":
    await update_configs(user_id, 'keywords', None)
    await query.message.edit_text(text="**successfully deleted**",
                                   reply_markup=InlineKeyboardMarkup(buttons))
  elif type.startswith("alert"):
    alert = type.split('_')[1]
    await query.answer(alert, show_alert=True)

def main_buttons():
  buttons = [[
       InlineKeyboardButton('🤖 Bᴏᴛs',
                    callback_data=f'settings#bots'),
       InlineKeyboardButton('🏷 Cʜᴀɴɴᴇʟs',
                    callback_data=f'settings#channels')
       ],[
       InlineKeyboardButton('🖋️ Cᴀᴘᴛɪᴏɴ',
                    callback_data=f'settings#caption'),
       InlineKeyboardButton('🗃 MᴏɴɢᴏDB',
                    callback_data=f'settings#database')
       ],[
       InlineKeyboardButton('🕵‍♀ Fɪʟᴛᴇʀs 🕵‍♀',
                    callback_data=f'settings#filters'),
       InlineKeyboardButton('⏹ Bᴜᴛᴛᴏɴ',
                    callback_data=f'settings#button')
       ],[
       InlineKeyboardButton('🚀 FTM Mᴀɴᴀɢᴇʀ 🚀',
                    callback_data='ftm#main')
       ],[
       InlineKeyboardButton('Exᴛʀᴀ Sᴇᴛᴛɪɴɢs 🧪',
                    callback_data='settings#nextfilters')
       ],[
       InlineKeyboardButton('⫷ Bᴀᴄᴋ', callback_data='back')
       ]]
  return InlineKeyboardMarkup(buttons)

def size_limit(limit):
   if str(limit) == "None":
      return None, ""
   elif str(limit) == "True":
      return True, "more than"
   else:
      return False, "less than"

def extract_btn(datas):
    i = 0
    btn = []
    if datas:
       for data in datas:
         if i >= 5:
            i = 0
         if i == 0:
            btn.append([InlineKeyboardButton(data, f'settings#alert_{data}')])
            i += 1
            continue
         elif i > 0:
            btn[-1].append(InlineKeyboardButton(data, f'settings#alert_{data}'))
            i += 1
    return btn

def size_button(size):
  buttons = [[
       InlineKeyboardButton('+',
                    callback_data=f'settings#update_limit-True-{size}'),
       InlineKeyboardButton('=',
                    callback_data=f'settings#update_limit-None-{size}'),
       InlineKeyboardButton('-',
                    callback_data=f'settings#update_limit-False-{size}')
       ],[
       InlineKeyboardButton('+1',
                    callback_data=f'settings#update_size-{size + 1}'),
       InlineKeyboardButton('-1',
                    callback_data=f'settings#update_size-{size - 1}')
       ],[
       InlineKeyboardButton('+5',
                    callback_data=f'settings#update_size-{size + 5}'),
       InlineKeyboardButton('-5',
                    callback_data=f'settings#update_size-{size - 5}')
       ],[
       InlineKeyboardButton('+10',
                    callback_data=f'settings#update_size-{size + 10}'),
       InlineKeyboardButton('-10',
                    callback_data=f'settings#update_size-{size - 10}')
       ],[
       InlineKeyboardButton('+50',
                    callback_data=f'settings#update_size-{size + 50}'),
       InlineKeyboardButton('-50',
                    callback_data=f'settings#update_size-{size - 50}')
       ],[
       InlineKeyboardButton('+100',
                    callback_data=f'settings#update_size-{size + 100}'),
       InlineKeyboardButton('-100',
                    callback_data=f'settings#update_size-{size - 100}')
       ],[
       InlineKeyboardButton('↩ Back',
                    callback_data="settings#main")
     ]]
  return InlineKeyboardMarkup(buttons)

async def filters_buttons(user_id):
  filter = await get_configs(user_id)
  filters = filter['filters']
  buttons = [[
       InlineKeyboardButton('🏷️ Forward tag',
                    callback_data=f'settings#updatefilter-forward_tag-{filter["forward_tag"]}'),
       InlineKeyboardButton('✅' if filter['forward_tag'] else '❌',
                    callback_data=f'settings#updatefilter-forward_tag-{filter["forward_tag"]}')
       ],[
       InlineKeyboardButton('🖍️ Texts',
                    callback_data=f'settings#updatefilter-text-{filters["text"]}'),
       InlineKeyboardButton('✅' if filters['text'] else '❌',
                    callback_data=f'settings#updatefilter-text-{filters["text"]}')
       ],[
       InlineKeyboardButton('📁 Documents',
                    callback_data=f'settings#updatefilter-document-{filters["document"]}'),
       InlineKeyboardButton('✅' if filters['document'] else '❌',
                    callback_data=f'settings#updatefilter-document-{filters["document"]}')
       ],[
       InlineKeyboardButton('🎞️ Videos',
                    callback_data=f'settings#updatefilter-video-{filters["video"]}'),
       InlineKeyboardButton('✅' if filters['video'] else '❌',
                    callback_data=f'settings#updatefilter-video-{filters["video"]}')
       ],[
       InlineKeyboardButton('📷 Photos',
                    callback_data=f'settings#updatefilter-photo-{filters["photo"]}'),
       InlineKeyboardButton('✅' if filters['photo'] else '❌',
                    callback_data=f'settings#updatefilter-photo-{filters["photo"]}')
       ],[
       InlineKeyboardButton('🎧 Audios',
                    callback_data=f'settings#updatefilter-audio-{filters["audio"]}'),
       InlineKeyboardButton('✅' if filters['audio'] else '❌',
                    callback_data=f'settings#updatefilter-audio-{filters["audio"]}')
       ],[
       InlineKeyboardButton('🎤 Voices',
                    callback_data=f'settings#updatefilter-voice-{filters["voice"]}'),
       InlineKeyboardButton('✅' if filters['voice'] else '❌',
                    callback_data=f'settings#updatefilter-voice-{filters["voice"]}')
       ],[
       InlineKeyboardButton('🎭 Animations',
                    callback_data=f'settings#updatefilter-animation-{filters["animation"]}'),
       InlineKeyboardButton('✅' if filters['animation'] else '❌',
                    callback_data=f'settings#updatefilter-animation-{filters["animation"]}')
       ],[
       InlineKeyboardButton('🃏 Stickers',
                    callback_data=f'settings#updatefilter-sticker-{filters["sticker"]}'),
       InlineKeyboardButton('✅' if filters['sticker'] else '❌',
                    callback_data=f'settings#updatefilter-sticker-{filters["sticker"]}')
       ],[
       InlineKeyboardButton('▶️ Skip duplicate',
                    callback_data=f'settings#updatefilter-duplicate-{filter["duplicate"]}'),
       InlineKeyboardButton('✅' if filter['duplicate'] else '❌',
                    callback_data=f'settings#updatefilter-duplicate-{filter["duplicate"]}')
       ],[
       InlineKeyboardButton('⫷ back',
                    callback_data="settings#main")
       ]]
  return InlineKeyboardMarkup(buttons)

async def next_filters_buttons(user_id):
  from .utils import to_small_caps
  filter = await get_configs(user_id)
  filters = filter['filters']
  buttons = [[
       InlineKeyboardButton('📊 ' + to_small_caps('poll'),
                    callback_data=f'settings#updatefilter-poll-{filters["poll"]}'),
       InlineKeyboardButton('✅' if filters['poll'] else '❌',
                    callback_data=f'settings#updatefilter-poll-{filters["poll"]}')
       ],[
       InlineKeyboardButton('🔒 ' + to_small_caps('secure message'),
                    callback_data=f'settings#updatefilter-protect-{filter["protect"]}'),
       InlineKeyboardButton('✅' if filter['protect'] else '❌',
                    callback_data=f'settings#updatefilter-protect-{filter["protect"]}')
       ],[
       InlineKeyboardButton('🛑 ' + to_small_caps('size limit'),
                    callback_data='settings#file_size')
       ],[
       InlineKeyboardButton('💾 ' + to_small_caps('extension'),
                    callback_data='settings#get_extension')
       ],[
       InlineKeyboardButton('♦️ ' + to_small_caps('keywords') + ' ♦️',
                    callback_data='settings#get_keyword')
       ],[
       InlineKeyboardButton('⫷ ' + to_small_caps('back'),
                    callback_data="settings#main")
       ]]
  return InlineKeyboardMarkup(buttons)
