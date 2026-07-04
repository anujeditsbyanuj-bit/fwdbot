
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database import db
from config import Config
from plugins.utils import to_small_caps
from werkzeug.security import generate_password_hash
from datetime import datetime

async def check_owner(message):
    """Check if user is owner, if not send error message"""
    if message.from_user.id not in Config.BOT_OWNER_ID:
        await message.reply_text(
            f"🚫 <b>{to_small_caps('this command is not for you')}</b> 🚫\n\n"
            f"⚠️ {to_small_caps('only bot owner can use this command')}"
        )
        return False
    return True

@Client.on_message(filters.private & filters.command(['makeadmin']))
async def make_admin_command(client, message):
    """Owner command to make a user an admin"""
    if not await check_owner(message):
        return
    args = message.text.split()
    if len(args) < 3:
        return await message.reply(
            f"<b>❌ {to_small_caps('invalid format')}</b>\n\n"
            f"<b>{to_small_caps('usage')}:</b> <code>/makeadmin user_id username password</code>\n\n"
            f"<b>{to_small_caps('example')}:</b> <code>/makeadmin 123456789 admin123 SecurePass@123</code>"
        )

    try:
        user_id = int(args[1])
        username = args[2]
        password = args[3] if len(args) > 3 else 'admin@123'

        # Check if user exists
        user = await db.col.find_one({'id': user_id})
        if not user:
            return await message.reply(
                f"<b>❌ {to_small_caps('user not found')}</b>\n\n"
                f"{to_small_caps('user id')} <code>{user_id}</code> {to_small_caps('is not in the database')}"
            )

        # Check if already admin
        existing_admin = await db.get_admin_by_id(user_id)
        if existing_admin:
            return await message.reply(
                f"<b>⚠️ {to_small_caps('already admin')}</b>\n\n"
                f"{to_small_caps('user')} <code>{user_id}</code> {to_small_caps('is already an admin')}"
            )

        # Create admin
        success = await db.add_admin(user_id, username, generate_password_hash(password), message.from_user.id)

        if success:
            user_name = user.get('name', 'Unknown')

            await message.reply(
                f"<b>✅ {to_small_caps('admin created successfully')}</b>\n\n"
                f"<b>👤 {to_small_caps('user')}:</b> {user_name}\n"
                f"<b>⚡ {to_small_caps('user id')}:</b> <code>{user_id}</code>\n"
                f"<b>🔑 {to_small_caps('username')}:</b> <code>{username}</code>\n"
                f"<b>🔐 {to_small_caps('password')}:</b> <code>{password}</code>\n"
                f"<b>💎 {to_small_caps('plan')}:</b> ♾️ {to_small_caps('infinity')} ({to_small_caps('lifetime')})\n\n"
                f"<i>{to_small_caps('admin can now login to web panel')}</i>",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"🌐 {to_small_caps('open admin panel')}", callback_data=f"send_panel_link_{user_id}")
                ]])
            )

            # Notify the new admin
            try:
                await client.send_message(
                    user_id,
                    f"<b>🎉 {to_small_caps('admin access granted')} 🎉</b>\n\n"
                    f"{to_small_caps('you have been granted admin access!')}\n\n"
                    f"<b>{to_small_caps('login credentials')}:</b>\n"
                    f"• {to_small_caps('username')}: <code>{username}</code>\n"
                    f"• {to_small_caps('password')}: <code>{password}</code>\n\n"
                    f"<b>💎 {to_small_caps('plan')}:</b> ♾️ {to_small_caps('infinity')} ({to_small_caps('lifetime')})\n\n"
                    f"<i>{to_small_caps('please change your password after first login')}</i>",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(f"🌐 {to_small_caps('open admin panel')}", callback_data="open_admin_panel")
                    ]])
                )
            except Exception:
                pass

            # Log activity
            from plugins.logger import BotLogger
            await BotLogger.log_admin_created(client, user_id, user_name, username, message.from_user.id, message.from_user.first_name)
        else:
            await message.reply(f"<b>❌ {to_small_caps('failed to create admin')}</b>")

    except ValueError:
        await message.reply(
            f"<b>❌ {to_small_caps('invalid user id')}</b>\n\n"
            f"{to_small_caps('user id must be a number')}"
        )
    except Exception as e:
        await message.reply(f"<b>❌ {to_small_caps('error')}:</b> <code>{str(e)}</code>")

@Client.on_message(filters.private & filters.command(['removeadmin']))
async def remove_admin_command(client, message):
    """Owner command to remove admin"""
    if not await check_owner(message):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.reply(
            f"<b>❌ {to_small_caps('invalid format')}</b>\n\n"
            f"<b>{to_small_caps('usage')}:</b> <code>/removeadmin user_id</code>\n\n"
            f"<b>{to_small_caps('example')}:</b> <code>/removeadmin 123456789</code>"
        )

    try:
        user_id = int(args[1])

        admin = await db.get_admin_by_id(user_id)
        if not admin:
            return await message.reply(
                f"<b>❌ {to_small_caps('not an admin')}</b>\n\n"
                f"{to_small_caps('user')} <code>{user_id}</code> {to_small_caps('is not an admin')}"
            )

        success = await db.remove_admin(user_id)

        if success:
            await message.reply(
                f"<b>✅ {to_small_caps('admin removed')}</b>\n\n"
                f"<b>{to_small_caps('username')}:</b> <code>{admin['username']}</code>\n"
                f"<b>{to_small_caps('user id')}:</b> <code>{user_id}</code>"
            )

            # Notify user
            try:
                await client.send_message(
                    user_id,
                    f"<b>⚠️ {to_small_caps('admin access revoked')} ⚠️</b>\n\n"
                    f"{to_small_caps('your admin access has been revoked by the owner')}\n\n"
                    f"{to_small_caps('you can no longer access the admin panel')}"
                )
            except Exception:
                pass
        else:
            await message.reply(f"<b>❌ {to_small_caps('failed to remove admin')}</b>")

    except ValueError:
        await message.reply(f"<b>❌ {to_small_caps('invalid user id')}</b>")
    except Exception as e:
        await message.reply(f"<b>❌ {to_small_caps('error')}:</b> <code>{str(e)}</code>")

@Client.on_message(filters.private & filters.command(['listadmins']))
async def list_admins_command(client, message):
    """Owner command to list all admins"""
    if not await check_owner(message):
        return
    admins = await db.get_all_admins()
    admin_list = []

    async for admin in admins:
        if admin.get('role') == 'owner':
            continue

        status = "✅ Active" if admin.get('is_active', True) else "❌ Inactive"
        admin_list.append(
            f"• <b>{admin['username']}</b>\n"
            f"  ID: <code>{admin['user_id']}</code>\n"
            f"  Status: {status}\n"
            f"  Created: {admin['created_at'].strftime('%Y-%m-%d') if admin.get('created_at') else 'N/A'}"
        )

    if not admin_list:
        return await message.reply(
            f"<b>👥 {to_small_caps('admin list')}</b>\n\n"
            f"<i>{to_small_caps('no admins created yet')}</i>"
        )

    text = f"<b>👥 {to_small_caps('admin list')}</b>\n\n" + "\n\n".join(admin_list)
    await message.reply(text)


@Client.on_message(filters.private & filters.command(['remove']))
async def remove_user_command(client, message):
    """Owner command to remove user completely from database"""
    if not await check_owner(message):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.reply(
            f"<b>❌ {to_small_caps('invalid format')}</b>\n\n"
            f"<b>{to_small_caps('usage')}:</b> <code>/remove user_id</code>\n\n"
            f"<b>{to_small_caps('example')}:</b> <code>/remove 123456789</code>"
        )

    try:
        user_id = int(args[1])

        # Check if user exists
        user = await db.col.find_one({'id': user_id})
        if not user:
            return await message.reply(
                f"<b>❌ {to_small_caps('user not found')}</b>\n\n"
                f"{to_small_caps('user id')} <code>{user_id}</code> {to_small_caps('is not in the database')}"
            )

        user_name = user.get('name', 'Unknown')

        # Remove user from all collections
        results = await db.remove_user_completely(user_id)

        await message.reply(
            f"<b>✅ {to_small_caps('user removed completely')}</b>\n\n"
            f"<b>👤 {to_small_caps('user')}:</b> {user_name}\n"
            f"<b>⚡ {to_small_caps('user id')}:</b> <code>{user_id}</code>\n\n"
            f"<b>{to_small_caps('removed from collections')}:</b>\n"
            f"• {to_small_caps('users')}: {results['users'].deleted_count}\n"
            f"• {to_small_caps('bots')}: {results['bots'].deleted_count}\n"
            f"• {to_small_caps('channels')}: {results['channels'].deleted_count}\n"
            f"• {to_small_caps('notifications')}: {results['notifications'].deleted_count}\n"
            f"• {to_small_caps('admin access')}: {results['admins'].deleted_count}"
        )

        # Log activity
        from plugins.logger import BotLogger
        await BotLogger.log_user_removed(client, user_id, user_name, message.from_user.id, message.from_user.first_name)

    except ValueError:
        await message.reply(
            f"<b>❌ {to_small_caps('invalid user id')}</b>\n\n"
            f"{to_small_caps('user id must be a number')}"
        )
    except Exception as e:
        await message.reply(f"<b>❌ {to_small_caps('error')}:</b> <code>{str(e)}</code>")





