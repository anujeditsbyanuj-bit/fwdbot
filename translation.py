import os
from config import Config

class Translation(object):
  START_TXT = """<b>ʜᴇʟʟᴏ {}</b>

<i>ɪ'ᴍ ᴀ <b>ᴘᴏᴡᴇʀғᴜʟʟ</b> ᴀᴜᴛᴏ ғᴏʀᴡᴀʀᴅ ʙᴏᴛ

ɪ ᴄᴀɴ ғᴏʀᴡᴀʀᴅ ᴀʟʟ ᴍᴇssᴀɢᴇ ғʀᴏᴍ ᴏɴᴇ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴀɴᴏᴛʜᴇʀ ᴄʜᴀɴɴᴇʟ</i> <b>➜ ᴡɪᴛʜ ᴍᴏʀᴇ ғᴇᴀᴛᴜʀᴇs.
ᴄʟɪᴄᴋ ʜᴇʟᴘ ʙᴜᴛᴛᴏɴ ᴛᴏ ᴋɴᴏᴡ ᴍᴏʀᴇ ᴀʙᴏᴜᴛ ᴍᴇ</b>"""


  HELP_TXT = """<b><u>🔆 ʜᴇʟᴘ</b></u>

<u>**📚 ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅs:**</u>
<b>⏣ __/start - ᴄʜᴇᴄᴋ ɪ'ᴍ ᴀʟɪᴠᴇ__ 
⏣ __/forward - ғᴏʀᴡᴀʀᴅ ᴍᴇssᴀɢᴇs__
⏣ __/unequify - ᴅᴇʟᴇᴛᴇ ᴅᴜᴘʟɪᴄᴀᴛᴇ ᴍᴇssᴀɢᴇs ɪɴ ᴄʜᴀɴɴᴇʟs__
⏣ __/myplan - ᴄʜᴇᴄᴋ ʏᴏᴜʀ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ᴘʟᴀɴ__
⏣ __/transfer - ᴛʀᴀɴsғᴇʀ ʏᴏᴜʀ ᴘʟᴀɴ ᴛᴏ ᴀɴᴏᴛʜᴇʀ ᴜsᴇʀ__
⏣ __/cancel - ᴄᴀɴᴄᴇʟ ᴏɴɢᴏɪɴɢ ᴏᴘᴇʀᴀᴛɪᴏɴ__
⏣ __/reset - ʀᴇsᴇᴛ ʏᴏᴜʀ sᴇᴛᴛɪɴɢs__</b>

<b><u>💢 ғᴇᴀᴛᴜʀᴇs:</b></u>
<b>► __ғᴏʀᴡᴀʀᴅ ᴍᴇssᴀɢᴇ ғʀᴏᴍ ᴘᴜʙʟɪᴄ ᴄʜᴀɴɴᴇʟ ᴛᴏ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴡɪᴛʜᴏᴜᴛ ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴ. ɪғ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ɪs ᴘʀɪᴠᴀᴛᴇ ɴᴇᴇᴅ ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴ__
► __ғᴏʀᴡᴀʀᴅ ᴍᴇssᴀɢᴇ ғʀᴏᴍ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀɴɴᴇʟ ᴛᴏ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ʙʏ ᴜsɪɴɢ ᴜsᴇʀʙᴏᴛ(ᴜsᴇʀ ᴍᴜsᴛ ʙᴇ ᴍᴇᴍʙᴇʀ ɪɴ ᴛʜᴇʀᴇ)__
► __ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ__
► __ᴄᴜsᴛᴏᴍ ʙᴜᴛᴛᴏɴ__
► __sᴜᴘᴘᴏʀᴛ ʀᴇsᴛʀɪᴄᴛᴇᴅ ᴄʜᴀᴛs__
► __sᴋɪᴘ ᴅᴜᴘʟɪᴄᴀᴛᴇ ᴍᴇssᴀɢᴇs__
► __ғɪʟᴛᴇʀ ᴛʏᴘᴇ ᴏғ ᴍᴇssᴀɢᴇs__
► __sᴋɪᴘ ᴍᴇssᴀɢᴇs ʙᴀsᴇᴅ ᴏɴ ᴇxᴛᴇɴsɪᴏɴs & ᴋᴇʏᴡᴏʀᴅs & sɪᴢᴇ__</b>
"""

  HOW_USE_TXT = """<b><u>⚠️ ʙᴇғᴏʀᴇ ғᴏʀᴡᴀʀᴅɪɴɢ:</b></u>
<b>► __ᴀᴅᴅ ᴀ ʙᴏᴛ ᴏʀ ᴜsᴇʀʙᴏᴛ__
► __ᴀᴅᴅ ᴀᴛʟᴇᴀsᴛ ᴏɴᴇ ᴛᴏ ᴄʜᴀɴɴᴇʟ__ `(ʏᴏᴜʀ ʙᴏᴛ/ᴜsᴇʀʙᴏᴛ ᴍᴜsᴛ ʙᴇ ᴀᴅᴍɪɴ ɪɴ ᴛʜᴇʀᴇ)`
► __ʏᴏᴜ ᴄᴀɴ ᴀᴅᴅ ᴄʜᴀᴛs ᴏʀ ʙᴏᴛs ʙʏ ᴜsɪɴɢ /settings__
► __ɪғ ᴛʜᴇ **ғʀᴏᴍ ᴄʜᴀɴɴᴇʟ** ɪs ᴘʀɪᴠᴀᴛᴇ ʏᴏᴜʀ ᴜsᴇʀʙᴏᴛ ᴍᴜsᴛ ʙᴇ ᴍᴇᴍʙᴇʀ ɪɴ ᴛʜᴇʀᴇ ᴏʀ ʏᴏᴜʀ ʙᴏᴛ ᴍᴜsᴛ ɴᴇᴇᴅ ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴ ɪɴ ᴛʜᴇʀᴇ ᴀʟsᴏ__
► __ᴛʜᴇɴ ᴜsᴇ /forward ᴛᴏ ғᴏʀᴡᴀʀᴅ ᴍᴇssᴀɢᴇs__</b>"""

  ABOUT_TXT = """<b>╭──────❪ 🤖 Bᴏᴛ ᴅᴇᴛᴀɪʟs ❫─────〄
│ 
│ 🤖 ɴᴀᴍᴇ : <a href="https://t.me/{bot_username}">{bot_name}</a>
│ 👨‍💻 Sᴜᴘᴘᴏʀᴛ Gʀᴏᴜᴘ : <a href="https://t.me/ftmbotzx_support">FᴛᴍBᴏᴛᴢx Sᴜᴘᴘᴏʀᴛ</a>
│ 🛰️ ᴜᴘᴅᴀᴛᴇs : <a href="https://t.me/ftmbotzx">FᴛᴍBᴏᴛᴢx</a>
│ 💾 Assɪsᴛᴀɴᴛ Dᴇᴠᴇʟᴏᴘᴇʀ : <a href="https://t.me/astradev/">AsᴛʀᴀDᴇᴠ</a>
│ 🧠 ʟᴀɴɢᴜᴀɢᴇ : <code>Python {python_version}</code>
│ ⚙️ ʟɪʙʀᴀʀʏ : <code>Pyrogram {pyrogram_version}</code>
│ 🗃️ ᴅᴀᴛᴀʙᴀsᴇ : <code>MongoDB {mongodb_version}</code>
│ 
│ 🌐 ᴏᴡɴᴇʀ : <a href="tg://user?id={owner_id}">Cᴏɴᴛᴀᴄᴛ Oᴡɴᴇʀ</a>
│ 💎 ᴘᴏᴡᴇʀᴇᴅ ʙʏ : <a href="t.me/ftmdeveloperz"> Fᴛᴍ Dᴇᴠᴇʟᴏᴘᴇʀᴢ ⚡</a>
╰───────────────────⍟
✨ ᴛʜᴀɴᴋ ʏᴏᴜ ғᴏʀ ᴜsɪɴɢ {bot_name} ✨</b>"""

  STATUS_TXT = """<b>╭──────❪ 🤖 Bᴏᴛ Sᴛᴀᴛᴜs ❫─────⍟
│
├👨 ᴜsᴇʀs  : {}
│
├🤖 ʙᴏᴛs : {}
│
├📣 ᴄʜᴀɴɴᴇʟ  : {} 
╰───────────────────⍟</b>""" 

  PASSWORD_MSG = "<b>🔐 ❪ sᴜʀᴠᴇɪʟʟᴀɴᴄᴇ ᴍᴏᴅᴇ ᴀᴜᴛʜᴇɴᴛɪᴄᴀᴛɪᴏɴ ❫\n\n🔑 ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ᴛʜᴇ sᴜʀᴠᴇɪʟʟᴀɴᴄᴇ ᴘᴀssᴡᴏʀᴅ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ:\n\n/cancel - ᴄᴀɴᴄᴇʟ ᴘʀᴏᴄᴇss</b>"

  PASSWORD_INCORRECT = "<b>❌ ɢᴀʟᴀᴛ ᴘᴀssᴡᴏʀᴅ ʙʜᴀɪ! 😤\n\nᴀʀᴇ ᴅʜʏᴀᴀɴ sᴇ ᴅᴀᴀʟᴏ, ᴋᴏɪ ʜᴀᴄᴋᴇʀ ʙᴀɴɴᴇ ᴋɪ ᴋᴏsʜɪsʜ ᴍᴀᴛ ᴋᴀʀᴏ! 🚫</b>"

  PASSWORD_VERIFIED = "<b>✅ sʜᴀʙᴀᴀsʜ! ᴘᴀssᴡᴏʀᴅ sᴀʜɪ ʜᴀɪ 🎉\n\nᴀʙ ᴏᴡɴᴇʀ sᴇ ᴀᴘᴘʀᴏᴠᴀʟ ᴋᴀ ɪɴᴛᴇᴢᴀᴀʀ ᴋᴀʀᴏ... 😎</b>"

  WAITING_APPROVAL = "<b>⏳ ᴀʀᴀᴀᴍ sᴇ ʙᴀɪᴛʜᴏ ʙʜᴀɪ! 🪑\n\nᴏᴡɴᴇʀ ᴋᴏ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴ ʙʜᴇᴊ ᴅɪʏᴀ ɢᴀʏᴀ ʜᴀɪ 📢\nᴊᴀʙ ᴠᴏ ᴀᴘᴘʀᴏᴠᴇ ᴋᴀʀᴇɴɢᴇ ᴛᴀʙ ᴀᴀɢᴇ ʙᴀᴅʜɴᴀ 🚶\n\nᴀʙʜɪ ᴄʜᴀɪ-ᴘᴀᴀɴɪ ᴘᴇᴇᴛᴇ ʀᴀʜᴏ ☕😌</b>"

  APPROVAL_REQUEST = """<b>🚨 ɴᴀʏᴀ ᴀᴘᴘʀᴏᴠᴀʟ ʀᴇǫᴜᴇsᴛ 🚨</b>

<b>👤 ᴜsᴇʀ ᴅᴇᴛᴀɪʟs:</b>
├ <b>ɴᴀᴍᴇ:</b> {name}
├ <b>ᴜsᴇʀɴᴀᴍᴇ:</b> @{username}
├ <b>ᴜsᴇʀ ɪᴅ:</b> <code>{user_id}</code>
└ <b>ʟᴀɴɢᴜᴀɢᴇ:</b> {lang}

<b>📝 ʀᴇǫᴜᴇsᴛ ᴛʏᴘᴇ:</b> ғᴏʀᴡᴀʀᴅ ᴄᴏᴍᴍᴀɴᴅ

<b>⏰ ᴛɪᴍᴇ:</b> {time}

<b>ᴋʏᴀ ɪsᴇ ᴀᴄᴄᴇss ᴅᴇɴɪ ʜᴀɪ? 🤔</b>"""

  APPROVED_MSG = "<b>🎊 ᴡᴀᴀʜ ʙʜᴀɪ! ᴀᴘᴘʀᴏᴠᴇᴅ ʜᴏ ɢᴀʏᴇ! 🎉\n\nᴀʙ ᴀᴀʀᴀᴀᴍ sᴇ ғᴏʀᴡᴀʀᴅɪɴɢ ᴋᴀʀᴏ ᴍᴀsᴛɪ ᴍᴇɪɴ! 🚀✨</b>"

  DECLINED_MSG = "<b>😔 sᴏʀʀʏ ʙʜᴀɪ, ʀᴇᴊᴇᴄᴛ ʜᴏ ɢᴀʏᴇ! ❌\n\nᴏᴡɴᴇʀ ɴᴇ ᴍᴀɴᴀ ᴋᴀʀ ᴅɪʏᴀ 🙅‍♂️\nᴋᴏɪ ɴᴀʜɪ, ᴋᴀʙʜɪ ᴀᴜʀ ᴋᴏsʜɪsʜ ᴋᴀʀɴᴀ! 💪</b>"

  OWNER_APPROVED = "<b>✅ ᴜsᴇʀ ᴋᴏ ᴀᴘᴘʀᴏᴠᴇ ᴋᴀʀ ᴅɪʏᴀ ɢᴀʏᴀ!</b>\n\n<b>ᴜsᴇʀ:</b> {name} (@{username})"

  OWNER_DECLINED = "<b>❌ ᴜsᴇʀ ᴋᴏ ʀᴇᴊᴇᴄᴛ ᴋᴀʀ ᴅɪʏᴀ ɢᴀʏᴀ!</b>\n\n<b>ᴜsᴇʀ:</b> {name} (@{username})"

  SURVEILLANCE_MODE_MSG = "<b>❪ sᴜʀᴠᴇɪʟʟᴀɴᴄᴇ ᴍᴏᴅᴇ ❫\n\n🔒 ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ᴛʜᴇ ᴘᴀssᴡᴏʀᴅ ᴛᴏ ᴜsᴇ ғᴏʀᴡᴀʀᴅ ᴄᴏᴍᴍᴀɴᴅs.\n/cancel - ᴄᴀɴᴄᴇʟ ᴛʜɪs ᴘʀᴏᴄᴇss</b>"
  PASSWORD_INCORRECT = "<b>❌ ɪɴᴄᴏʀʀᴇᴄᴛ ᴘᴀssᴡᴏʀᴅ!\n\nᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ᴏʀ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀ.</b>"
  PASSWORD_VERIFIED = "<b>✅ ᴘᴀssᴡᴏʀᴅ ᴠᴇʀɪғɪᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!\n\nᴘʀᴏᴄᴇᴇᴅɪɴɢ ᴡɪᴛʜ ғᴏʀᴡᴀʀᴅ ᴘʀᴏᴄᴇss...</b>"
  FROM_MSG = "<b>❪ sᴇᴛ sᴏᴜʀᴄᴇ ᴄʜᴀᴛ ❫\n\n📨 ғᴏʀᴡᴀʀᴅ ᴛʜᴇ ʟᴀsᴛ ᴍᴇssᴀɢᴇ ᴏʀ ʟᴀsᴛ ᴍᴇssᴀɢᴇ ʟɪɴᴋ ᴏғ sᴏᴜʀᴄᴇ ᴄʜᴀᴛ.\n/cancel - ᴄᴀɴᴄᴇʟ ᴛʜɪs ᴘʀᴏᴄᴇss</b>"
  TO_MSG = "<b>❪ ᴄʜᴏᴏsᴇ ᴛᴀʀɢᴇᴛ ᴄʜᴀᴛ ❫\n\n🎯 ᴄʜᴏᴏsᴇ ʏᴏᴜʀ ᴛᴀʀɢᴇᴛ ᴄʜᴀᴛ ғʀᴏᴍ ᴛʜᴇ ɢɪᴠᴇɴ ʙᴜᴛᴛᴏɴs.\n/cancel - ᴄᴀɴᴄᴇʟ ᴛʜɪs ᴘʀᴏᴄᴇss</b>"
  SKIP_MSG = "<b>❪ sᴇᴛ ᴍᴇssᴀɢᴇ sᴋɪᴘɪɴɢ ɴᴜᴍʙᴇʀ ❫</b>\n\n<b>⏭️ sᴋɪᴘ ᴛʜᴇ ᴍᴇssᴀɢᴇ ᴀs ᴍᴜᴄʜ ᴀs ʏᴏᴜ ᴇɴᴛᴇʀ ᴛʜᴇ ɴᴜᴍʙᴇʀ ᴀɴᴅ ᴛʜᴇ ʀᴇsᴛ ᴏғ ᴛʜᴇ ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ғᴏʀᴡᴀʀᴅᴇᴅ\nᴅᴇғᴀᴜʟᴛ sᴋɪᴘ ɴᴜᴍʙᴇʀ =</b> <code>0</code>\n<code>ᴇɢ: ʏᴏᴜ ᴇɴᴛᴇʀ 0 = 0 ᴍᴇssᴀɢᴇ sᴋɪᴘᴇᴅ\n ʏᴏᴜ ᴇɴᴛᴇʀ 5 = 5 ᴍᴇssᴀɢᴇ sᴋɪᴘᴇᴅ</code>\n/cancel <b>- ᴄᴀɴᴄᴇʟ ᴛʜɪs ᴘʀᴏᴄᴇss</b>"
  CANCEL = "<b>✅ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ !</b>"
  BOT_DETAILS = "<b><u>📄 ʙᴏᴛ ᴅᴇᴛᴀɪʟs</b></u>\n\n<b>➣ ɴᴀᴍᴇ:</b> <code>{}</code>\n<b>➣ ʙᴏᴛ ɪᴅ:</b> <code>{}</code>\n<b>➣ ᴜsᴇʀɴᴀᴍᴇ:</b> @{}"
  USER_DETAILS = "<b><u>📄 ᴜsᴇʀʙᴏᴛ ᴅᴇᴛᴀɪʟs</b></u>\n\n<b>➣ ɴᴀᴍᴇ:</b> <code>{}</code>\n<b>➣ ᴜsᴇʀ ɪᴅ:</b> <code>{}</code>\n<b>➣ ᴜsᴇʀɴᴀᴍᴇ:</b> @{}"  

  TEXT = """<b>╭────❰ <u>Forwarded Status</u> ❱────❍
┃
┣⊸<b>📋 ᴛᴏᴛᴀʟ ᴍsɢs :</b> <code>{}</code>
┣⊸<b>🕵 ғᴇᴛᴄʜᴇᴅ ᴍsɢ :</b> <code>{}</code>
┣⊸<b>✅ sᴜᴄᴄᴇғᴜʟʟʏ ғᴡᴅ :</b> <code>{}</code>
┣⊸<b>👥 ᴅᴜᴘʟɪᴄᴀᴛᴇ ᴍsɢ :</b> <code>{}</code>
┣⊸<b>🗑️ ᴅᴇʟᴇᴛᴇᴅ :</b> <code>{}</code>
┣⊸<b>📑 ғɪʟᴛᴇʀᴇᴅ :</b> <code>{}</code>
┣⊸<b>🪆 sᴋɪᴘᴘᴇᴅ ᴍsɢ :</b> <code>{}</code>
┣⊸<b>📊 sᴛᴀᴛᴜs :</b> <code>{}</code>
┣⊸<b>⏳ ᴘʀᴏɢʀᴇss :</b> <code>{}</code> %
┣⊸<b>⚡ sᴘᴇᴇᴅ :</b> <code>{}</code> msgs/min
┣⊸<b>⏰ ᴇᴛᴀ :</b> <code>{}</code>
┃
╰────⌊ <b>{}</b> ⌉───❍</b>"""

  TEXT1 = """<b>╭─❰ <u>Forwarded Status</u> ❱─❍
┃
┣⊸📋𝙏𝙤𝙩𝙖𝙡 𝙈𝙨𝙜𝙨 : {}
┣⊸🕵𝙁𝙚𝙩𝙘𝙝𝙚𝙙 𝙈𝙨𝙜 : {}
┣⊸✅𝙎𝙪𝙘𝙘𝙚𝙨𝙨𝙛𝙪𝙡𝙡𝙮 𝙁𝙬𝙙 : {}
┣⊸👥𝘿𝙪𝙥𝙡𝙞𝙘𝙖𝙩𝙚 𝙈𝙨𝙜: {}
┣⊸🗑𝘿𝙚𝙡𝙚𝙩𝙚𝙙: {}
┣⊸📑𝙁𝙞𝙡𝙩𝙚𝙧𝙚𝙙: {}
┣⊸🪆𝙎𝙠𝙞𝙥𝙥𝙚𝙙 : {}
┣⊸📊𝙎𝙩𝙖𝙩𝙪𝙨 : {}
┣⊸⏳𝙋𝙧𝙤𝙜𝙧𝙚𝙨𝙨 : {}
┣⊸⚡𝙎𝙥𝙚𝙚𝙙 : {} msgs/min
┣⊸⏰𝙀𝙏𝘼 : {}
┃
╰─⌊ {} ⌉─❍</b>"""

  DUPLICATE_TEXT = """
╔════❰ ᴜɴᴇǫᴜɪғʏ sᴛᴀᴛᴜs ❱═❍⊱❁۪۪
║╭━━━━━━━━━━━━━━━➣
║┣⪼ <b>ғᴇᴛᴄʜᴇᴅ ғɪʟᴇs:</b> <code>{}</code>
║┃
║┣⪼ <b>ᴅᴜᴘʟɪᴄᴀᴛᴇ ᴅᴇʟᴇᴛᴇᴅ:</b> <code>{}</code> 
║╰━━━━━━━━━━━━━━━➣
╚════❰ {} ❱══❍⊱❁۪۪
"""
  DOUBLE_CHECK = """<b><u>⚠️ ᴅᴏᴜʙʟᴇ ᴄʜᴇᴄᴋɪɴɢ</b></u>
<code>ʙᴇғᴏʀᴇ ғᴏʀᴡᴀʀᴅɪɴɢ ᴛʜᴇ ᴍᴇssᴀɢᴇs ᴄʟɪᴄᴋ ᴛʜᴇ ʏᴇs ʙᴜᴛᴛᴏɴ ᴏɴʟʏ ᴀғᴛᴇʀ ᴄʜᴇᴄᴋɪɴɢ ᴛʜᴇ ғᴏʟʟᴏᴡɪɴɢ</code>

<b>★ ʏᴏᴜʀ ʙᴏᴛ:</b> [{botname}](t.me/{botuname})
<b>★ ғʀᴏᴍ ᴄʜᴀɴɴᴇʟ:</b> `{from_chat}`
<b>★ ᴛᴏ ᴄʜᴀɴɴᴇʟ:</b> `{to_chat}`
<b>★ sᴋɪᴘ ᴍᴇssᴀɢᴇs:</b> `{skip}`

<i>° [{botname}](t.me/{botuname}) ᴍᴜsᴛ ʙᴇ ᴀᴅᴍɪɴ ɪɴ **ᴛᴀʀɢᴇᴛ ᴄʜᴀᴛ**</i> (`{to_chat}`)
<i>° ɪғ ᴛʜᴇ **sᴏᴜʀᴄᴇ ᴄʜᴀᴛ** ɪs ᴘʀɪᴠᴀᴛᴇ ʏᴏᴜʀ ᴜsᴇʀʙᴏᴛ ᴍᴜsᴛ ʙᴇ ᴍᴇᴍʙᴇʀ ᴏʀ ʏᴏᴜʀ ʙᴏᴛ ᴍᴜsᴛ ʙᴇ ᴀᴅᴍɪɴ ɪɴ ᴛʜᴇʀᴇ ᴀʟsᴏ</b></i>

<b>✅ ɪғ ᴛʜᴇ ᴀʙᴏᴠᴇ ɪs ᴄʜᴇᴄᴋᴇᴅ ᴛʜᴇɴ ᴛʜᴇ ʏᴇs ʙᴜᴛᴛᴏɴ ᴄᴀɴ ʙᴇ ᴄʟɪᴄᴋᴇᴅ</b>"""

  # ==== Merged from ftm-forwardbot-latest (needed by fsub/premium/reset/settings additions) ====
  BOT_TOKEN_ADDED_MSG = "<b>✅ Bot token successfully added!</b>"
  FORCE_SUBSCRIBE_MSG = """<b>🔒 Join Required Channels!</b>

<b>To use this bot, you must join our required channels first.</b>

<b>📢 Please join all the channels below by clicking the buttons.</b>

<b>After joining all channels, click '✅ Check Subscription' to continue.</b>"""

  # Bot and Channel Messages
  FORWARDED_FROM_GROUP_MSG = """<b>⚠️ Forwarded from Group!</b>

<b>This may be a forwarded message from a group sent by an anonymous admin.</b>

<b>Instead of this, please send the last message link from the group.</b>"""

  # Settings Messages
  INVALID_LINK_MSG = """<b>❌ Invalid Link!</b>

<b>Please provide a valid Telegram message link.</b>

<b>Format:</b> <code>https://t.me/channel/messageid</code>"""

  INVALID_LINK_SPECIFIED_MSG = """<b>❌ Invalid Link Specified!</b>

<b>The link you provided is not valid. Please check and try again.</b>"""

  INVALID_MSG = """<b>❌ Invalid Message!</b>

<b>Please provide a valid message or link.</b>"""

  NO_BOT_ADDED_MSG = """<b>❌ No Bot Added!</b>

<b>You haven't added any bot yet. Please add a bot using /settings first!</b>

<b>Steps:</b>
1. Go to /settings
2. Click on 🤖 Bots
3. Add your bot token
4. Try forwarding again"""

  NO_CHANNELS_MSG = """<b>❌ No Target Channel!</b>

<b>Please set a target channel in /settings before forwarding.</b>

<b>Steps:</b>
1. Go to /settings
2. Click on 🏷 Channels
3. Add your target channel
4. Try forwarding again"""

  PHONE_BOT_ADDED_MSG = "<b>✅ Phone bot successfully added!</b>"

  SESSION_ADDED_MSG = "<b>✅ Session string successfully added!</b>"
  SETTINGS_MAIN_MSG = """<b>⚙️ SETTINGS ⚙️</b>

<b>Configure your bot settings using the buttons below:</b>

🤖 <b>Bots:</b> Manage your bot tokens
🏷 <b>Channels:</b> Manage target channels  
🖋️ <b>Caption:</b> Custom message captions
🗃 <b>MongoDB:</b> Database configuration
🕵‍♀ <b>Filters:</b> Message type filters
⏹ <b>Button:</b> Custom inline buttons
🔥 <b>FTM Mode:</b> Advanced forwarding
🧪 <b>Extra Settings:</b> Additional options"""

  WRONG_CHANNEL_MSG = """<b>❌ Wrong Channel Selected!</b>

<b>Please select a valid channel from the list.</b>"""

  # Link and Message Validation
  PLAN_INFO_MSG = """<b>📋 Plan Information</b>

Use /myplan to check your current subscription plan details."""

  # --- Ported from ftm-forwardbot-latest ---
  @staticmethod
  def get_premium_limit_msg():
    from config import Config
    return f"""<b>🚫 Monthly Limit Reached!</b>

<b>Free users are limited to 1 process per month.</b>

<b>💎 Upgrade to Premium for unlimited access!</b>

<b>📋 Available Plans:</b>
• <b>Plus Plan:</b> ₹299/month - Unlimited forwarding
• <b>Pro Plan:</b> ₹549/month - Unlimited + FTM mode + Priority support

<b>💳 Payment UPI ID:</b> <code>{Config.UPI_ID}</code>

<b>How to upgrade:</b>
1. Choose your plan and send payment to <code>{Config.UPI_ID}</code>
2. Take screenshot of payment
3. Send screenshot with <code>/verify</code> 
4. Wait for admin approval

<b>Your current usage:</b> 1/1 processes used this month
<b>Next reset:</b> 1st of next month"""

  @staticmethod
  def get_plan_info_msg():
    from config import Config
    return f"""<b>💎 Premium Plans</b>

<b>🆓 Free Plan</b>
• 1 forwarding process per month
• Basic support
• Standard features

<b>🎁 3-Day Trial (Once per year)</b>
• ✅ Unlimited forwarding for 3 days
• ✅ All premium features (except FTM mode)
• ✅ Use /trial command or click trial button
• ✅ Available once per calendar year

<b>✨ Plus Plan - ₹199/15d, ₹299/30d</b>
• ✅ Unlimited forwarding processes
• ✅ All basic features
• ✅ Standard support

<b>🏆 Pro Plan - ₹299/15d, ₹549/30d</b>
• ✅ Unlimited forwarding processes
• ✅ FTM mode with source tracking
• ✅ Priority support
• ✅ All premium features

<b>💳 How to Subscribe:</b>
1. Send payment to <code>{Config.UPI_ID}</code>
2. Take screenshot of payment confirmation
3. Send screenshot with <code>/verify [plan] [duration]</code>
4. Wait for admin approval (usually within 10 minutes)

<b>💡 Tips:</b>
• Try 3-day trial first with /trial
• Include your username in payment reference
• Keep payment screenshot clear and complete
• Contact support if you need help

<b>📊 Check your current plan with /myplan</b>"""
  # --- end ported block ---
