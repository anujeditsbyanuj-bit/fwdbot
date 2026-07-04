import asyncio 
import time, datetime
import logging
from database import db 
from config import Config
from pyrogram import Client, filters 
from pyrogram.errors import InputUserDeactivated, FloodWait, UserIsBlocked
from plugins.utils import to_small_caps

logger = logging.getLogger(__name__)

@Client.on_message(filters.private & filters.command(["broadcast"]))
async def broadcast(bot, message):
    if message.from_user.id not in Config.BOT_OWNER_ID:
        return await message.reply_text(
            f"🚫 <b>{to_small_caps('this command is not for you')}</b> 🚫\n\n"
            f"⚠️ {to_small_caps('only bot owner can use this command')}"
        )
    
    if not message.reply_to_message:
        return await message.reply_text(
            f"⚠️ <b>{to_small_caps('please reply to a message to broadcast')}</b>"
        )
    logger.info(f"Broadcast command triggered by user {message.from_user.id}")
    users = await db.get_all_users()
    b_msg = message.reply_to_message
    sts = await message.reply_text(
        text='Broadcasting your messages...'
    )
    start_time = time.time()
    total_users, k = await db.total_users_bots_count()
    done = 0
    blocked = 0
    deleted = 0
    failed = 0 
    success = 0
    async for user in users:
        pti, sh = await broadcast_messages(int(user['id']), b_msg, logger)
        if pti:
            success += 1
            await asyncio.sleep(2)
        elif pti == False:
            if sh == "Blocked":
                blocked+=1
            elif sh == "Deleted":
                deleted += 1
            elif sh == "Error":
                failed += 1
        done += 1
        if not done % 20:
            await sts.edit(f"Broadcast in progress:\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nBlocked: {blocked}\nDeleted: {deleted}")    
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await sts.edit(f"Broadcast Completed:\nCompleted in {time_taken} seconds.\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nBlocked: {blocked}\nDeleted: {deleted}")
    
    # Log broadcast activity
    from plugins.logger import BotLogger
    await BotLogger.log_broadcast(bot, message.from_user.id, message.from_user.first_name, total_users, success, blocked + deleted + failed)

async def broadcast_messages(user_id, message, log):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value if hasattr(e, 'value') else getattr(e, 'x', 10))
        return await broadcast_messages(user_id, message, log)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        log.info(f"{user_id}-Removed from Database, since deleted account.")
        return False, "Deleted"
    except UserIsBlocked:
        log.info(f"{user_id} -Blocked the bot.")
        return False, "Blocked"
    except Exception as e:
        log.error(f"Broadcast error for {user_id}: {e}")
        return False, "Error"

    
