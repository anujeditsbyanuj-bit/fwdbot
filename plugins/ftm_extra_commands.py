"""
Merged from ftm-forwardbot-latest.
Adds: /trial, /commands, /speedtest, /system
Kept in a separate file (instead of editing plugins/commands.py) because
SRC-fwdbot-ftm-4.5's own commands.py already defines its own /start, /help,
/about and /back handlers - duplicating those here would create conflicting
callback_query handlers. Only the standalone, non-conflicting commands were
ported.
"""
import logging
import psutil
import speedtest
import platform
from datetime import datetime
from database import db
from config import Config
from translation import Translation
from utils.notifications import NotificationManager
from plugins.fsub import get_force_sub_buttons
from pyrogram import Client, filters, __version__ as pyrogram_version
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


@Client.on_message(filters.private & filters.command(['help']))
async def help_command_msg(client, message):
    """Direct /help command (SRC only had this reachable via inline button before)"""
    await message.reply_text(
        text=Translation.HELP_TXT,
        reply_markup=InlineKeyboardMarkup(
            [[
            InlineKeyboardButton('ʜᴏᴡ ᴛᴏ ᴜsᴇ ᴍᴇ ❓', callback_data='how_to_use')
            ],[
            InlineKeyboardButton('⚙️ sᴇᴛᴛɪɴɢs ', callback_data='settings#main'),
            InlineKeyboardButton('📜 sᴛᴀᴛᴜs ', callback_data='status')
            ]]
        )
    )


def get_main_buttons():
    """Dynamically generate the main buttons for the bot's menu."""
    return [[
        InlineKeyboardButton('📜 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ ', url=Config.SUPPORT_GROUP),
        InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ  ', url=Config.UPDATE_CHANNEL)
        ],[
        InlineKeyboardButton('🎁 Get Free Trial', callback_data='get_free_trial'),
        InlineKeyboardButton('📊 My Plan', callback_data='my_plan')
        ],[
        InlineKeyboardButton('💎 Premium Plans', callback_data='premium_plans'),
        InlineKeyboardButton('🙋‍♂️ ʜᴇʟᴘ', callback_data='help')
        ],[
        InlineKeyboardButton('💁‍♂️ ᴀʙᴏᴜᴛ ', callback_data='about'),
        InlineKeyboardButton('⚙️ sᴇᴛᴛɪɴɢs ⚙️', callback_data='settings#main')
        ],[
        InlineKeyboardButton('📞 Contact Admin', callback_data='contact_admin')
        ]]


#===================Start Function===================#



@Client.on_message(filters.private & filters.command(['trial']))
async def trial_command(client, message):
    """Handle trial command"""
    user_id = message.from_user.id
    logger.info(f"Trial command from user {user_id}")

    try:
        # Check force subscribe for non-sudo users
        if not Config.is_sudo_user(user_id) and Config.MULTI_FSUB:
            subscription_status = await db.check_force_subscribe(user_id, client)
            if not subscription_status['all_subscribed']:
                force_buttons, joined_channels = await get_force_sub_buttons(client, user_id)
                if force_buttons:
                    force_sub_text = Translation.FORCE_SUBSCRIBE_MSG
                    if joined_channels:
                        force_sub_text += f"\n\n<b>✅ Already Joined:</b>\n"
                        for channel in joined_channels:
                            force_sub_text += f"• {channel} ✅\n"
                        force_sub_text += f"\n<b>📢 Please join the remaining channels below:</b>"

                    return await message.reply_text(
                        text=force_sub_text,
                        reply_markup=InlineKeyboardMarkup(force_buttons),
                        quote=True
                    )

        # Check if user can use trial
        can_trial = await db.can_use_trial(user_id)

        if not can_trial:
            await message.reply_text(
                text="<b>❌ Trial Already Used!</b>\n\n"
                     "<b>You have already used your free trial this year.</b>\n"
                     "<b>Trial is available once per calendar year.</b>\n\n"
                     "<b>💎 Check our premium plans with /plan</b>",
                quote=True
            )
            return

        # Check if user already has premium
        is_premium = await db.is_premium_user(user_id)
        if is_premium:
            await message.reply_text(
                text="<b>✅ You already have premium access!</b>\n\n"
                     "<b>Use /myplan to check your subscription details.</b>",
                quote=True
            )
            return

        # Grant trial
        success, result = await db.grant_trial(user_id)

        if success:
            from plugins.timezone import display_expiry_date
            expires_date = display_expiry_date(result)
            await message.reply_text(
                text=f"<b>🎉 3-Day Trial Activated!</b>\n\n"
                     f"<b>✅ You now have unlimited forwarding for 3 days!</b>\n\n"
                     f"<b>Trial Benefits:</b>\n"
                     f"• ✅ Unlimited forwarding processes\n"
                     f"• ✅ All premium features (except FTM mode)\n"
                     f"• ✅ Priority support\n\n"
                     f"<b>⏰ Expires:</b> {expires_date}\n\n"
                     f"<b>💡 Use /forward to start forwarding messages!</b>\n"
                     f"<b>📊 Check status anytime with /myplan</b>",
                quote=True,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton('📊 My Plan', callback_data='my_plan'),
                    InlineKeyboardButton('🚀 Start Forwarding', callback_data='start_forwarding')
                ]])
            )

            # Send notification
            notify = NotificationManager(client)
            await notify.notify_user_action(
                user_id,
                "Trial Activated",
                f"User activated 3-day free trial - expires {expires_date}"
            )

        else:
            await message.reply_text(
                text=f"<b>❌ Trial Activation Failed</b>\n\n"
                     f"<b>Reason:</b> {result}\n\n"
                     f"<b>💎 Check our premium plans with /plan</b>",
                quote=True
            )

    except Exception as e:
        logger.error(f"Error in trial command for user {user_id}: {e}", exc_info=True)
        await message.reply_text("❌ An error occurred. Please try again.", quote=True)



@Client.on_message(filters.private & filters.command(['commands']))
async def commands_list(client, message):
    """Show all available commands"""
    user_id = message.from_user.id
    logger.info(f"Commands list requested by user {user_id}")

    try:
        # Check force subscribe for non-sudo users
        if not Config.is_sudo_user(user_id) and Config.MULTI_FSUB:
            subscription_status = await db.check_force_subscribe(user_id, client)
            if not subscription_status['all_subscribed']:
                force_buttons, joined_channels = await get_force_sub_buttons(client, user_id)
                if force_buttons:
                    force_sub_text = Translation.FORCE_SUBSCRIBE_MSG
                    if joined_channels:
                        force_sub_text += f"\n\n<b>✅ Already Joined:</b>\n"
                        for channel in joined_channels:
                            force_sub_text += f"• {channel} ✅\n"
                        force_sub_text += f"\n<b>📢 Please join the remaining channels below:</b>"

                    return await message.reply_text(
                        text=force_sub_text,
                        reply_markup=InlineKeyboardMarkup(force_buttons),
                        quote=True
                    )

        is_admin = Config.is_sudo_user(user_id)
        is_premium = await db.is_premium_user(user_id)
        can_trial = await db.can_use_trial(user_id)

        commands_text = "<b>📋 Available Commands</b>\n\n"

        commands_text += "<b>🔥 Essential Commands:</b>\n"
        commands_text += "• <code>/start</code> - Start bot and show main menu\n"
        commands_text += "• <code>/help</code> - Get detailed help and instructions\n"
        commands_text += "• <code>/forward</code> - Start message forwarding process\n"
        commands_text += "• <code>/settings</code> - Configure your bot settings\n"
        commands_text += "• <code>/myplan</code> - Check your subscription status\n"
        commands_text += "• <code>/info</code> - Get your account information\n"
        commands_text += "• <code>/reset</code> - Reset your bot configurations\n\n"

        commands_text += "<b>💎 Premium Features:</b>\n"
        if not is_premium and can_trial:
            commands_text += "• <code>/trial</code> - Get 3-day free trial (⭐ Available!)\n"
        elif not is_premium:
            commands_text += "• <code>/trial</code> - Get 3-day free trial (❌ Used this year)\n"
        else:
            commands_text += "• <code>/trial</code> - Get 3-day free trial (✅ You have premium)\n"

        commands_text += "• <code>/verify</code> - Verify payment for premium plans\n"
        commands_text += "• <code>/plan</code> - View available premium plans\n\n"

        if is_admin:
            commands_text += "<b>👑 Admin Commands:</b>\n"
            commands_text += "• <code>/users</code> - List all registered users\n"
            commands_text += "• <code>/broadcast</code> - Send message to all users\n"
            commands_text += "• <code>/speedtest</code> - Network speed test\n"
            commands_text += "• <code>/system</code> - System information\n"
            commands_text += "• <code>/resetall</code> - Reset all users (DANGER)\n"
            commands_text += "• <code>/premium add</code> - Grant premium to user\n"
            commands_text += "• <code>/premium remove</code> - Remove premium from user\n\n"

        commands_text += "<b>🎯 Quick Status:</b>\n"
        commands_text += f"• <b>Plan:</b> {'Premium' if is_premium else 'Free'}\n"
        commands_text += f"• <b>Trial:</b> {'Available' if can_trial and not is_premium else 'Used/Premium'}\n"
        commands_text += f"• <b>Admin:</b> {'Yes' if is_admin else 'No'}\n\n"

        commands_text += "<b>💡 Pro Tip:</b> Use /trial for instant premium access!"

        await message.reply_text(
            text=commands_text,
            quote=True,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton('🎁 Free Trial', callback_data='get_free_trial'),
                    InlineKeyboardButton('📊 My Plan', callback_data='my_plan')
                ],
                [
                    InlineKeyboardButton('💎 Premium Plans', callback_data='premium_plans'),
                    InlineKeyboardButton('📋 Help', callback_data='help')
                ],
                [
                    InlineKeyboardButton('🏠 Main Menu', callback_data='back')
                ]
            ])
        )

    except Exception as e:
        logger.error(f"Error in commands list for user {user_id}: {e}", exc_info=True)
        await message.reply_text("❌ An error occurred. Please try again.", quote=True)



@Client.on_callback_query(filters.regex(r'^get_free_trial$'))
async def trial_callback(client, callback_query):
    """Handle get free trial button"""
    user_id = callback_query.from_user.id
    logger.info(f"Trial callback from user {user_id}")

    try:
        # Check force subscribe for non-sudo users
        if not Config.is_sudo_user(user_id) and Config.MULTI_FSUB:
            subscription_status = await db.check_force_subscribe(user_id, client)
            if not subscription_status['all_subscribed']:
                force_buttons, joined_channels = await get_force_sub_buttons(client, user_id)
                if force_buttons:
                    force_sub_text = Translation.FORCE_SUBSCRIBE_MSG
                    if joined_channels:
                        force_sub_text += f"\n\n<b>✅ Already Joined:</b>\n"
                        for channel in joined_channels:
                            force_sub_text += f"• {channel} ✅\n"
                        force_sub_text += f"\n<b>📢 Please join the remaining channels below:</b>"

                    return await callback_query.message.edit_text(
                        text=force_sub_text,
                        reply_markup=InlineKeyboardMarkup(force_buttons)
                    )


        # Check if user can use trial
        can_trial = await db.can_use_trial(user_id)

        if not can_trial:
            await callback_query.answer("❌ Trial already used this year!", show_alert=True)
            return

        # Check if user already has premium
        is_premium = await db.is_premium_user(user_id)
        if is_premium:
            await callback_query.answer("✅ You already have premium access!", show_alert=True)
            return

        # Show confirmation
        await callback_query.message.edit_text(
            text="<b>🎁 Activate Free Trial?</b>\n\n"
                 "<b>✅ 3 days unlimited forwarding</b>\n"
                 "<b>✅ All premium features (except FTM mode)</b>\n"
                 "<b>✅ Priority support</b>\n\n"
                 "<b>⚠️ Available once per year only!</b>\n\n"
                 "<b>Do you want to activate your free trial now?</b>",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton('✅ Yes, Activate Trial', callback_data='confirm_trial'),
                    InlineKeyboardButton('❌ Not Now', callback_data='back')
                ]
            ])
        )

    except Exception as e:
        logger.error(f"Error in trial callback for user {user_id}: {e}", exc_info=True)
        await callback_query.answer("❌ An error occurred. Please try again.", show_alert=True)



@Client.on_callback_query(filters.regex(r'^confirm_trial$'))
async def confirm_trial_callback(client, callback_query):
    """Handle trial confirmation"""
    user_id = callback_query.from_user.id

    try:
        # Grant trial
        success, result = await db.grant_trial(user_id)

        if success:
            from plugins.timezone import display_expiry_date
            expires_date = display_expiry_date(result)
            await callback_query.message.edit_text(
                text=f"<b>🎉 3-Day Trial Activated!</b>\n\n"
                     f"<b>✅ You now have unlimited forwarding for 3 days!</b>\n\n"
                     f"<b>Trial Benefits:</b>\n"
                     f"• ✅ Unlimited forwarding processes\n"
                     f"• ✅ All premium features (except FTM mode)\n"
                     f"• ✅ Priority support\n\n"
                     f"<b>⏰ Expires:</b> {expires_date}\n\n"
                     f"<b>💡 Use /forward to start forwarding messages!</b>",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton('📊 My Plan', callback_data='my_plan'),
                        InlineKeyboardButton('🚀 Start Forwarding', callback_data='start_forwarding')
                    ],
                    [
                        InlineKeyboardButton('🏠 Main Menu', callback_data='back')
                    ]
                ])
            )

            # Send notification
            notify = NotificationManager(client)
            await notify.notify_user_action(
                user_id,
                "Trial Activated",
                f"User activated 3-day free trial - expires {expires_date}"
            )

        else:
            await callback_query.message.edit_text(
                text=f"<b>❌ Trial Activation Failed</b>\n\n"
                     f"<b>Reason:</b> {result}\n\n"
                     f"<b>💎 Check our premium plans with /plan</b>",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton('🏠 Main Menu', callback_data='back')
                ]])
            )

    except Exception as e:
        logger.error(f"Error in confirm trial for user {user_id}: {e}", exc_info=True)
        await callback_query.answer("❌ An error occurred. Please try again.", show_alert=True)



@Client.on_callback_query(filters.regex(r'^start_forwarding$'))
async def start_forwarding_callback(client, callback_query):
    """Handle start forwarding button"""
    await callback_query.message.edit_text(
        text="<b>🚀 Ready to Forward!</b>\n\n"
             "<b>Use the /forward command to start forwarding messages.</b>\n\n"
             "<b>Before forwarding, make sure you have:</b>\n"
             "• ✅ Added your bot in /settings\n"
             "• ✅ Added target channels in /settings\n"
             "• ✅ Made your bot admin in target channels\n\n"
             "<b>💡 Need help? Use /help for detailed instructions.</b>",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton('⚙️ Settings', callback_data='settings#main'),
                InlineKeyboardButton('📋 Help', callback_data='help')
            ],
            [
                InlineKeyboardButton('🏠 Main Menu', callback_data='back')
            ]
        ])
    )



@Client.on_message(filters.private & filters.command(['speedtest', 'speed']))
async def speed_test_command(client, message):
    user_id = message.from_user.id
    logger.info(f"Speedtest command from user {user_id}")

    # Check if user is sudo (owner or admin)
    if not Config.is_sudo_user(user_id):
        return await message.reply_text("❌ This command is only available for administrators.")

    status_msg = await message.reply_text("🔄 <b>Running Network Speed Test...</b>\n⏳ Please wait, this may take a moment.")

    try:
        # Initialize speedtest
        st = speedtest.Speedtest()

        # Update status
        await status_msg.edit_text("🔄 <b>Finding best server...</b>\n⏳ Please wait.")

        # Get best server
        st.get_best_server()

        # Update status
        await status_msg.edit_text("🔄 <b>Testing download speed...</b>\n⏳ Please wait.")

        # Test download speed
        download_speed = st.download()

        # Update status
        await status_msg.edit_text("🔄 <b>Testing upload speed...</b>\n⏳ Please wait.")

        # Test upload speed
        upload_speed = st.upload()

        # Get ping
        ping = st.results.ping

        # Get server info
        server = st.get_best_server()

        # Convert bytes to Mbps
        download_mbps = download_speed / 1024 / 1024
        upload_mbps = upload_speed / 1024 / 1024

        # Format the result
        speed_text = f"""<b>🌐 Bot Server Network Speed Test</b>

<b>📡 Server Connection Info:</b>
├ <b>ISP:</b> <code>{server.get('sponsor', 'Unknown')}</code>
├ <b>Server Location:</b> <code>{server.get('name', 'Unknown')}, {server.get('country', 'Unknown')}</code>
├ <b>Distance:</b> <code>{server.get('d', 0):.1f} km</code>

<b>🚀 Bot Server Speed Results:</b>
├ <b>📥 Download:</b> <code>{download_mbps:.2f} Mbps</code>
├ <b>📤 Upload:</b> <code>{upload_mbps:.2f} Mbps</code>
├ <b>📶 Ping:</b> <code>{ping:.1f} ms</code>

<b>📊 Test Information:</b>
├ <b>Test Date:</b> <code>{st.results.timestamp}</code>
├ <b>Note:</b> <code>Shows bot server network, not your location</code>
└ <b>Share URL:</b> <a href="{st.results.share()}">View Results</a>"""

        await status_msg.edit_text(speed_text, disable_web_page_preview=True)
        logger.info(f"Speedtest completed for user {user_id}")

    except Exception as e:
        error_msg = f"❌ <b>Speed Test Failed</b>\n\n<b>Error:</b> <code>{str(e)}</code>"
        await status_msg.edit_text(error_msg)
        logger.error(f"Speedtest error for user {user_id}: {e}", exc_info=True)


#==================System Info Command==================#



@Client.on_message(filters.private & filters.command(['system', 'sys', 'sysinfo']))
async def system_info_command(client, message):
    user_id = message.from_user.id
    logger.info(f"System info command from user {user_id}")

    # Check if user is sudo (owner or admin)
    if not Config.is_sudo_user(user_id):
        return await message.reply_text("❌ This command is only available for administrators.")

    status_msg = await message.reply_text("🔄 <b>Gathering system information...</b>")

    try:
        # Get system info
        uname = platform.uname()

        # Get CPU info
        cpu_count = psutil.cpu_count()
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq()

        # Get memory info
        memory = psutil.virtual_memory()
        memory_total = memory.total / (1024**3)  # GB
        memory_used = memory.used / (1024**3)   # GB
        memory_percent = memory.percent

        # Get disk info
        disk = psutil.disk_usage('/')
        disk_total = disk.total / (1024**3)  # GB
        disk_used = disk.used / (1024**3)    # GB
        disk_percent = (disk.used / disk.total) * 100

        # Get network info
        net_io = psutil.net_io_counters()
        bytes_sent = net_io.bytes_sent / (1024**2)  # MB
        bytes_recv = net_io.bytes_recv / (1024**2)  # MB

        # Get boot time
        boot_time = psutil.boot_time()

        # Get process info
        process_count = len(psutil.pids())

        # Get Python info
        python_ver = python_version()

        # Format uptime
        import datetime
        uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(boot_time)
        uptime_str = str(uptime).split('.')[0]

        # Get load average (Unix-like systems)
        try:
            load_avg = os.getloadavg()
            load_str = f"{load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}"
        except Exception:
            load_str = "Not Available"

        system_text = f"""<b>🖥️ Bot Server System Information</b>

<b>💻 Server System Details:</b>
├ <b>OS:</b> <code>{uname.system} {uname.release}</code>
├ <b>Architecture:</b> <code>{uname.machine}</code>
├ <b>Hostname:</b> <code>{uname.node}</code>
├ <b>Kernel:</b> <code>{uname.version}</code>

<b>🔧 Server Hardware Info:</b>
├ <b>CPU Cores:</b> <code>{cpu_count} cores</code>
├ <b>CPU Usage:</b> <code>{cpu_percent}%</code>
├ <b>CPU Frequency:</b> <code>{cpu_freq.current:.0f} MHz</code> (Max: <code>{cpu_freq.max:.0f} MHz</code>)
├ <b>Load Average:</b> <code>{load_str}</code>

<b>💾 Server Memory Info:</b>
├ <b>Total RAM:</b> <code>{memory_total:.2f} GB</code>
├ <b>Used RAM:</b> <code>{memory_used:.2f} GB ({memory_percent}%)</code>
├ <b>Available RAM:</b> <code>{(memory_total - memory_used):.2f} GB</code>

<b>💿 Server Storage Info:</b>
├ <b>Total Disk:</b> <code>{disk_total:.2f} GB</code>
├ <b>Used Disk:</b> <code>{disk_used:.2f} GB ({disk_percent:.1f}%)</code>
├ <b>Free Disk:</b> <code>{(disk_total - disk_used):.2f} GB</code>

<b>🌐 Server Network Usage:</b>
├ <b>Data Sent:</b> <code>{bytes_sent:.2f} MB</code>
├ <b>Data Received:</b> <code>{bytes_recv:.2f} MB</code>

<b>⚡ Bot Runtime Info:</b>
├ <b>Python Version:</b> <code>v{python_ver}</code>
├ <b>Pyrogram Version:</b> <code>v{pyrogram_version}</code>
├ <b>Active Processes:</b> <code>{process_count}</code>
├ <b>Server Uptime:</b> <code>{uptime_str}</code>
├ <b>Note:</b> <code>Shows bot server stats, not your device</code>
└ <b>Bot Status:</b> <code>Running ✅</code>"""

        await status_msg.edit_text(system_text)
        logger.info(f"System info sent to user {user_id}")

    except Exception as e:
        error_msg = f"❌ <b>System Info Failed</b>\n\n<b>Error:</b> <code>{str(e)}</code>"
        await status_msg.edit_text(error_msg)
        logger.error(f"System info error for user {user_id}: {e}", exc_info=True)


#==================Admin Callback Functions==================#



