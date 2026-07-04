import os
import asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from plugins.timezone import get_current_ist_timestamp, display_expiry_date, display_subscription_date
from database import db
from config import Config
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
import logging

# Purchase plan callback handlers
@Client.on_callback_query(filters.regex(r'^buy_(plus|pro)_(15|30)$'))
async def buy_plan_callback(client, callback_query):
    user_id = callback_query.from_user.id
    data_parts = callback_query.data.split('_')
    plan_type = data_parts[1]  # plus or pro
    duration = int(data_parts[2])  # 15 or 30

    # Get pricing
    from config import Config
    amount = Config.PLAN_PRICING[plan_type][f'{duration}_days']

    purchase_text = (
        f"💳 <b>Purchase {plan_type.upper()} Plan</b>\n\n"
        f"📦 <b>Plan:</b> {plan_type.upper()}\n"
        f"⏰ <b>Duration:</b> {duration} days\n"
        f"💰 <b>Amount:</b> ₹{amount}\n\n"
        f"<b>💵 Payment Instructions:</b>\n"
        f"1. Send ₹{amount} to UPI: <code>{Config.UPI_ID}</code>\n"
        f"2. Take a screenshot of the payment\n"
        f"3. Send the screenshot to this bot\n"
        f"4. Reply to the screenshot with: <code>/verify {plan_type} {duration}</code>\n\n"
        f"<b>⚠️ Important:</b>\n"
        f"• Pay exact amount: ₹{amount}\n"
        f"• Include payment reference in screenshot\n"
        f"• Verification usually takes 5-10 minutes"
    )

    buttons = [
        [
            InlineKeyboardButton("📋 Copy UPI ID", callback_data="copy_upi"),
            InlineKeyboardButton("💬 Contact Support", callback_data="contact_admin")
        ],
        [
            InlineKeyboardButton("🔙 Back to Plans", callback_data="premium_plans")
        ]
    ]

    await callback_query.message.edit_text(
        text=purchase_text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Payment approval/rejection callbacks
@Client.on_callback_query(filters.regex(r'^approve_payment_'))
async def approve_payment_callback(client, callback_query):
    user_id = callback_query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await callback_query.answer("❌ You don't have permission!", show_alert=True)

    verification_id = ObjectId(callback_query.data.split("_")[2])

    try:
        # Get verification details
        verification = await db.get_verification_by_id(verification_id)
        if not verification:
            return await callback_query.answer("❌ Verification not found!", show_alert=True)

        if verification['status'] != 'pending':
            return await callback_query.answer(f"❌ Already {verification['status']}!", show_alert=True)

        # Approve payment
        success = await db.approve_payment(verification_id, user_id, "Payment approved by admin")

        if success:
            # Get verification details for plan info
            verification = await db.get_verification_by_id(verification_id)
            plan_type = verification.get('plan_type', 'pro').upper()
            duration = verification.get('duration_days', 30)
            amount = verification.get('amount', 0)

            # Update the admin message
            await callback_query.message.edit_caption(
                callback_query.message.caption + f"\n\n<b>✅ APPROVED by {callback_query.from_user.first_name}</b>",
                reply_markup=None
            )

            # Notify the user
            try:
                # Get plan features for display
                user_features = await db.get_user_plan_features(verification['user_id'])
                features_text = ""
                if user_features.get('unlimited_forwarding'):
                    features_text += "• Unlimited forwarding processes\n"
                if user_features.get('ftm_mode'):
                    features_text += "• FTM mode enabled\n"
                if user_features.get('priority_support'):
                    features_text += "• Priority support\n"

                await client.send_message(
                    verification['user_id'],
                    f"<b>🎉 Payment Approved!</b>\n\n"
                    f"<b>✅ Your payment has been verified and approved!</b>\n"
                    f"<b>💎 You now have {plan_type} plan for {duration} days.</b>\n"
                    f"<b>💰 Amount paid: ₹{amount}</b>\n\n"
                    f"<b>{plan_type} Plan Benefits:</b>\n"
                    f"{features_text}\n"
                    f"<b>Use /myplan to check your subscription details.</b>"
                )
            except Exception:
                pass

            await callback_query.answer("✅ Payment approved successfully!", show_alert=True)
        else:
            await callback_query.answer("❌ Failed to approve payment!", show_alert=True)

    except Exception as e:
        await callback_query.answer(f"❌ Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r'^reject_payment_'))
async def reject_payment_callback(client, callback_query):
    user_id = callback_query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await callback_query.answer("❌ You don't have permission!", show_alert=True)

    verification_id = ObjectId(callback_query.data.split("_")[2])

    try:
        # Get verification details
        verification = await db.get_verification_by_id(verification_id)
        if not verification:
            return await callback_query.answer("❌ Verification not found!", show_alert=True)

        if verification['status'] != 'pending':
            return await callback_query.answer(f"❌ Already {verification['status']}!", show_alert=True)

        # Reject payment
        success = await db.reject_payment(verification_id, user_id, "Payment rejected by admin")

        if success:
            # Update the admin message
            await callback_query.message.edit_caption(
                callback_query.message.caption + f"\n\n<b>❌ REJECTED by {callback_query.from_user.first_name}</b>",
                reply_markup=None
            )

            # Notify the user
            try:
                await client.send_message(
                    verification['user_id'],
                    "<b>❌ Payment Rejected</b>\n\n"
                    "<b>Your payment verification has been rejected.</b>\n\n"
                    "<b>Possible reasons:</b>\n"
                    "• Invalid payment screenshot\n"
                    "• Incorrect amount\n"
                    "• Payment not found\n"
                    "• Duplicate submission\n\n"
                    "<b>Please verify your payment and submit again with /verify</b>\n"
                    "<b>Or contact support for assistance.</b>"
                )
            except Exception:
                pass

            await callback_query.answer("❌ Payment rejected!", show_alert=True)
        else:
            await callback_query.answer("❌ Failed to reject payment!", show_alert=True)

    except Exception as e:
        await callback_query.answer(f"❌ Error: {str(e)}", show_alert=True)

# /chat command for admins to chat with users

# Handle messages in admin chat sessions
@Client.on_message(filters.private & ~filters.command(['start', 'help', 'forward', 'fwd', 'settings', 'verify', 'chat', 'contact', 'endchat', 'add_premium', 'remove_premium', 'pusers', 'plan', 'myplan', 'chatuser']))
async def handle_chat_messages(client, message):
    user_id = message.from_user.id

    # Check if admin has active chat session
    if Config.is_sudo_user(user_id):
        chat_session = await db.get_active_admin_chat(user_id)
        if chat_session:
            target_user_id = chat_session['target_user_id']

            # Forward admin message to user
            try:
                await client.send_message(
                    target_user_id,
                    f"<b>👨‍💼 Admin:</b> {message.text or '[Media/File]'}"
                )

                # Log the message
                await db.add_chat_message(chat_session['_id'], True, message.text or '[Media/File]')

                # Confirm to admin
                await message.reply_text("✅ Message sent to user!")

            except Exception as e:
                await message.reply_text(f"❌ Failed to send message: {str(e)}")
            return

    # Check if user has an active chat session with an admin (user replying to admin)
    else:
        active_chat = await db.get_active_chat_for_user(user_id)
        if active_chat:
            admin_id = active_chat['admin_id']

            # Forward user message to admin
            try:
                # Get user info for better display
                user_name = message.from_user.first_name
                user_username = f"@{message.from_user.username}" if message.from_user.username else ""

                await client.send_message(
                    admin_id,
                    f"<b>👤 {user_name} {user_username} (ID: {user_id}):</b>\n{message.text or '[Media/File]'}"
                )

                # Log the message
                await db.add_chat_message(active_chat['_id'], False, message.text or '[Media/File]')

                # Confirm to user that message was sent
                await message.reply_text("✅ Your message has been sent to admin!")

            except Exception as e:
                await message.reply_text(f"❌ Failed to send message to admin: {str(e)}")
            return

# /contact command for users to initiate chat with admin or owner
@Client.on_message(filters.private & filters.command(['contact']))
async def chat_request_command(client, message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    user_username = f"@{message.from_user.username}" if message.from_user.username else ""

    try:
        # Check if user already has a pending chat request
        existing_request = await db.get_pending_chat_request(user_id)
        if existing_request:
            return await message.reply_text(
                "<b>⏳ Chat Request Already Pending</b>\n\n"
                "<b>You already have a pending chat request.</b>\n"
                "<b>Please wait for admin approval.</b>\n\n"
                f"<b>Request ID:</b> <code>{existing_request['_id']}</code>\n"
                f"<b>Submitted:</b> {display_subscription_date(existing_request['created_at'])}"
            )

        # Check if user is already in an active chat
        active_chat = await db.get_active_chat_for_user(user_id)
        if active_chat:
            return await message.reply_text(
                "<b>💬 You already have an active chat session with admin!</b>\n\n"
                "<b>Just send your message and it will be forwarded to admin.</b>"
            )

        # Create chat request
        request_id = await db.create_chat_request(user_id)

        await message.reply_text(
            "<b>💬 Chat Request Submitted!</b>\n\n"
            "<b>Your request to chat with admin has been submitted.</b>\n"
            "<b>⏳ Please wait for admin approval.</b>\n\n"
            f"<b>Request ID:</b> <code>{request_id}</code>\n"
            "<b>💬 You will be notified once an admin accepts your request.</b>"
        )

        # Send notification to all sudo users (admin + owner) with accept/deny options
        sudo_users = Config.OWNER_ID + Config.ADMIN_ID
        notification_messages = []  # Store message IDs for cleanup

        for sudo_id in sudo_users:
            try:
                buttons = [
                    [
                        InlineKeyboardButton("✅ Accept Chat", callback_data=f"accept_chat_{request_id}"),
                        InlineKeyboardButton("❌ Deny", callback_data=f"deny_chat_{request_id}")
                    ]
                ]

                sent_msg = await client.send_message(
                    sudo_id,
                    f"<b>💬 New Chat Request</b>\n\n"
                    f"<b>User:</b> {user_name} {user_username}\n"
                    f"<b>User ID:</b> <code>{user_id}</code>\n"
                    f"<b>Request ID:</b> <code>{request_id}</code>\n"
                    f"<b>Time:</b> {get_current_ist_timestamp()}\n\n"
                    "<b>User wants to start a chat session.</b>\n\n"
                    "<b>✅ Accept to connect with this user</b>\n"
                    "<b>❌ Deny to reject this request</b>",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

                # Store notification message info for cleanup
                notification_messages.append({
                    'admin_id': sudo_id,
                    'message_id': sent_msg.id
                })

            except Exception as e:
                logging.error(f"Failed to notify admin {sudo_id}: {e}")
        # Store notification messages in the request for cleanup
        await db.store_chat_notifications(request_id, notification_messages)

        # Log the chat request for monitoring
        from utils.notifications import NotificationManager
        notify = NotificationManager(client)
        await notify.notify_contact_request(user_id, "premium support", "submitted")

    except Exception as e:
        await message.reply_text(
            "<b>❌ Chat Request Failed</b>\n\n"
            "<b>An error occurred while processing your chat request.</b>\n\n"
            "<b>Please try again later.</b>"
        )


# Chat request accept/deny callbacks
@Client.on_callback_query(filters.regex(r'^accept_chat_'))
async def accept_chat_callback(client, callback_query):
    user_id = callback_query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await callback_query.answer("❌ You don't have permission!", show_alert=True)

    request_id = ObjectId(callback_query.data.split("_")[2])

    try:
        # Get chat request details
        request = await db.get_chat_request_by_id(request_id)
        if not request:
            return await callback_query.answer("❌ Chat request not found!", show_alert=True)

        if request['status'] != 'pending':
            return await callback_query.answer(f"❌ Already {request['status']}!", show_alert=True)

        # Start chat session
        session_id = await db.start_admin_chat(user_id, request['user_id'])
        await db.update_chat_request_status(request_id, 'accepted', user_id)

        # Delete notifications from all other admins
        await db.cleanup_chat_notifications(request_id, client, user_id)

        # Update current admin message
        await callback_query.message.edit_text(
            f"<b>✅ CHAT ACCEPTED by {callback_query.from_user.first_name}</b>\n\n"
            f"<b>User:</b> {request.get('user_name', 'Unknown')} {request.get('user_username', '')}\n"
            f"<b>User ID:</b> <code>{request['user_id']}</code>\n"
            f"<b>Request ID:</b> <code>{request_id}</code>\n\n"
            f"<b>🔗 Chat session started!</b>\n"
            f"<b>Session ID:</b> <code>{session_id}</code>",
            reply_markup=None
        )

        # Notify the user
        try:
            await client.send_message(
                request['user_id'],
                f"<b>✅ Chat Request Accepted!</b>\n\n"
                f"<b>Admin {callback_query.from_user.first_name} has accepted your chat request!</b>\n\n"
                f"<b>💬 You can now chat directly with the admin.</b>\n"
                f"<b>Just send your message and it will be forwarded.</b>\n\n"
                f"<b>Session ID:</b> <code>{session_id}</code>"
            )
        except Exception:
            pass

        await callback_query.answer("✅ Chat request accepted and session started!", show_alert=True)

    except Exception as e:
        await callback_query.answer(f"❌ Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r'^deny_chat_'))
async def deny_chat_callback(client, callback_query):
    user_id = callback_query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await callback_query.answer("❌ You don't have permission!", show_alert=True)

    request_id = ObjectId(callback_query.data.split("_")[2])

    try:
        # Get chat request details
        request = await db.get_chat_request_by_id(request_id)
        if not request:
            return await callback_query.answer("❌ Chat request not found!", show_alert=True)

        if request['status'] != 'pending':
            return await callback_query.answer(f"❌ Already {request['status']}!", show_alert=True)

        # Deny chat request
        await db.update_chat_request_status(request_id, 'denied', user_id)

        # Delete notifications from all admins
        await db.cleanup_chat_notifications(request_id, client, user_id)

        # Update current admin message
        await callback_query.message.edit_text(
            f"<b>❌ CHAT DENIED by {callback_query.from_user.first_name}</b>\n\n"
            f"<b>User:</b> {request.get('user_name', 'Unknown')} {request.get('user_username', '')}\n"
            f"<b>User ID:</b> <code>{request['user_id']}</code>\n"
            f"<b>Request ID:</b> <code>{request_id}</code>\n\n"
            f"<b>🚫 Chat request has been denied.</b>",
            reply_markup=None
        )

        # Notify the user
        try:
            await client.send_message(
                request['user_id'],
                "<b>❌ Chat Request Denied</b>\n\n"
                "<b>Your chat request has been denied by admin.</b>\n"
                "<b>You can try again later if needed.</b>"
            )
        except Exception:
            pass

        await callback_query.answer("❌ Chat request denied!", show_alert=True)

    except Exception as e:
        await callback_query.answer(f"❌ Error: {str(e)}", show_alert=True)

# Admin-only chat command for direct user connection without permission
@Client.on_message(filters.private & filters.command(['chatuser']))
async def admin_chat_user_command(client, message):
    user_id = message.from_user.id

    # Check if user is admin/owner
    if not Config.is_sudo_user(user_id):
        return await message.reply_text("❌ You don't have permission to use this command!")

    try:
        # Get user ID from command
        command_parts = message.text.split()
        if len(command_parts) < 2:
            return await message.reply_text(
                "<b>📝 Usage:</b> <code>/chatuser USER_ID</code>\n\n"
                "<b>Example:</b> <code>/chatuser 123456789</code>\n\n"
                "<b>This command allows admins to directly start a chat with any user.</b>"
            )

        target_user_id = int(command_parts[1])

        # Check if admin already has an active chat
        existing_chat = await db.get_active_admin_chat(user_id)
        if existing_chat:
            await db.end_admin_chat(user_id)  # End existing chat

        # Start new chat session
        session_id = await db.start_admin_chat(user_id, target_user_id)

        # Get target user info
        try:
            target_user = await client.get_users(target_user_id)
            user_info = f"{target_user.first_name} (@{target_user.username})" if target_user.username else target_user.first_name
        except Exception:
            user_info = f"User ID {target_user_id}"

        await message.reply_text(
            f"<b>✅ Direct Chat Started!</b>\n\n"
            f"<b>Target User:</b> {user_info}\n"
            f"<b>User ID:</b> <code>{target_user_id}</code>\n"
            f"<b>Session ID:</b> <code>{session_id}</code>\n\n"
            f"<b>💬 You can now chat directly with this user.</b>\n"
            f"<b>Messages you send will be forwarded to them.</b>\n\n"
            f"<b>Use /endchat to end this session.</b>"
        )

        # Notify the target user
        try:
            admin_name = message.from_user.first_name
            await client.send_message(
                target_user_id,
                f"<b>📞 Admin Chat Started!</b>\n\n"
                f"<b>Admin {admin_name} has started a chat session with you!</b>\n\n"
                f"<b>💬 You can now chat directly with the admin.</b>\n"
                f"<b>Just send your message and it will be forwarded.</b>\n\n"
                f"<b>Session ID:</b> <code>{session_id}</code>"
            )
        except Exception as e:
            await message.reply_text(f"⚠️ Chat started but failed to notify user: {str(e)}")

    except ValueError:
        await message.reply_text(
            "<b>❌ Invalid User ID!</b>\n\n"
            "<b>Please provide a valid numeric user ID.</b>\n\n"
            "<b>Example:</b> <code>/chatuser 123456789</code>"
        )
    except Exception as e:
        await message.reply_text(f"❌ Error starting chat: {str(e)}")

# End chat command for admins
@Client.on_message(filters.private & filters.command(['endchat']))
async def end_chat_command(client, message):
    user_id = message.from_user.id

    # Check if user is admin/owner
    if not Config.is_sudo_user(user_id):
        return await message.reply_text("❌ You don't have permission to use this command!")

    try:
        # Check if admin has an active chat
        active_chat = await db.get_active_admin_chat(user_id)
        if not active_chat:
            return await message.reply_text(
                "<b>❌ No Active Chat!</b>\n\n"
                "<b>You don't have any active chat sessions.</b>\n\n"
                "<b>Use /chatuser USER_ID to start a new chat.</b>"
            )

        # End the chat session
        await db.end_admin_chat(user_id)

        # Get target user info
        target_user_id = active_chat['target_user_id']
        try:
            target_user = await client.get_users(target_user_id)
            user_info = f"{target_user.first_name} (@{target_user.username})" if target_user.username else target_user.first_name
        except Exception:
            user_info = f"User ID {target_user_id}"

        await message.reply_text(
            f"<b>✅ Chat Session Ended!</b>\n\n"
            f"<b>Target User:</b> {user_info}\n"
            f"<b>User ID:</b> <code>{target_user_id}</code>\n"
            f"<b>Session ID:</b> <code>{active_chat['_id']}</code>\n\n"
            f"<b>🔒 Chat session has been closed.</b>"
        )

        # Notify the target user
        try:
            admin_name = message.from_user.first_name
            await client.send_message(
                target_user_id,
                f"<b>🔒 Chat Session Ended!</b>\n\n"
                f"<b>Admin {admin_name} has ended the chat session.</b>\n\n"
                f"<b>💬 Use /chat to request a new chat session if needed.</b>"
            )
        except Exception:
            pass  # Ignore if we can't notify the user

    except Exception as e:
        await message.reply_text(f"❌ Error ending chat: {str(e)}")

# Chat with user callback from payment verification
@Client.on_callback_query(filters.regex(r'^chat_user_'))
async def chat_user_callback(client, callback_query):
    user_id = callback_query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await callback_query.answer("❌ You don't have permission!", show_alert=True)


# My plan callback handler
@Client.on_callback_query(filters.regex(r'^my_plan$'))
async def my_plan_callback(client, callback_query):
    """Handle my plan button"""
    user_id = callback_query.from_user.id

    try:
        # Check if user is premium
        is_premium = await db.is_premium_user(user_id)
        premium_details = await db.get_premium_user_details(user_id)
        usage = await db.get_daily_usage(user_id)

        if is_premium and premium_details:
            # Premium user
            plan_type = premium_details['plan_type']
            subscribed = display_subscription_date(premium_details['subscribed_at'])
            expires = display_expiry_date(premium_details['expires_at']) if premium_details['expires_at'] else 'Never'

            status_text = f"<b>💎 Your Premium Plan</b>\n\n"
            status_text += f"<b>Plan:</b> Premium ({plan_type})\n"
            status_text += f"<b>Status:</b> ✅ Active\n"
            status_text += f"<b>Subscribed:</b> {subscribed}\n"
            status_text += f"<b>Expires:</b> {expires}\n\n"
            status_text += f"<b>✅ Benefits:</b>\n"
            status_text += f"• Unlimited forwarding processes\n"
            status_text += f"• Priority support\n"
            status_text += f"• All premium features unlocked\n\n"

            if premium_details['expires_at']:
                days_left = (premium_details['expires_at'] - datetime.utcnow()).days
                status_text += f"<b>⏰ Days remaining:</b> {days_left} days\n"

        else:
            # Free user
            # Get monthly usage and check trial status
            monthly_usage = await db.get_monthly_usage(user_id)
            processes_used = monthly_usage.get('processes', 0)

            # Check trial status for proper limit calculation
            trial_status = await db.get_trial_status(user_id)
            processes_limit = 1  # Base free process
            if trial_status and trial_status.get('used', False):
                processes_limit = 2  # Base + trial

            status_text = f"<b>🆓 Your Free Plan</b>\n\n"
            status_text += f"<b>📊 Account Status:</b> Free User\n"
            status_text += f"<b>🗓️ Monthly Allocation:</b> {processes_limit} processes\n"

            if trial_status and trial_status.get('used', False):
                status_text += f"<b>🎁 Breakdown:</b> 1 base + 1 free trial bonus\n"
            else:
                status_text += f"<b>🎁 Free Trial:</b> Available (claim +1 extra process)\n"

            status_text += f"\n<b>📈 Monthly Usage:</b>\n"
            status_text += f"• <b>Used:</b> {processes_used}/{processes_limit} processes\n"
            status_text += f"• <b>Remaining:</b> {max(0, processes_limit - processes_used)} processes\n"
            status_text += f"• <b>Resets:</b> 1st of every month\n\n"

            if processes_used >= processes_limit:
                status_text += f"<b>🚫 Monthly limit reached!</b>\n"
                status_text += f"<b>💎 Upgrade to Premium for unlimited access!</b>\n\n"

            status_text += f"<b>💡 Upgrade to Premium:</b>\n"
            status_text += f"<b>✨ Plus Plan:</b> ₹199/15d, ₹299/30d\n"
            status_text += f"<b>🏆 Pro Plan:</b> ₹299/15d, ₹549/30d\n"
            status_text += f"• Use <code>/verify [plan] [duration]</code> with payment screenshot\n\n"

        status_text += f"<b>🔗 Earn FREE Premium with /referral</b>\n"
        status_text += f"<b>📋 See all plans with /plan</b>"

        # Add referral button
        buttons = [
            [
                InlineKeyboardButton('🔗 Referral System', callback_data='refresh_referral'),
                InlineKeyboardButton('💎 Premium Plans', callback_data='premium_plans')
            ],
            [
                InlineKeyboardButton('🔙 Back', callback_data='back')
            ]
        ]

        await callback_query.message.edit_text(
            text=status_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        await callback_query.answer(f"❌ Error fetching plan details: {str(e)}", show_alert=True)


    target_user_id = int(callback_query.data.split("_")[2])

    try:
        # Start chat session
        session_id = await db.start_admin_chat(user_id, target_user_id)

        # Get user info
        try:
            target_user = await client.get_users(target_user_id)
            user_info = f"{target_user.first_name} (@{target_user.username})" if target_user.username else target_user.first_name
        except Exception:
            user_info = f"User ID: {target_user_id}"

        await callback_query.message.reply_text(
            f"<b>💬 Chat Session Started</b>\n\n"
            f"<b>Target User:</b> {user_info}\n"
            f"<b>User ID:</b> <code>{target_user_id}</code>\n\n"
            "<b>💡 Now send any message and it will be forwarded to the user.</b>\n"
            "<b>🔚 Use /endchat to end the session.</b>"
        )

        await callback_query.answer("✅ Chat session started!")

        # Notify the target user
        try:
            await client.send_message(
                target_user_id,
                f"<b>💬 Admin Chat Session</b>\n\n"
                f"<b>An admin has started a chat session with you.</b>\n"
                f"<b>Admin:</b> {callback_query.from_user.first_name}\n\n"
                "<b>You can now chat directly with the admin!</b>"
            )
        except Exception:
            pass

    except Exception as e:
        await callback_query.answer(f"❌ Error: {str(e)}", show_alert=True)

# Copy UPI ID callback
@Client.on_callback_query(filters.regex(r'^copy_upi$'))
async def copy_upi_callback(client, callback_query):
    await callback_query.answer(f"📋 UPI ID: {Config.UPI_ID}", show_alert=True)

# Referral command handler - REMOVED: Duplicate of plugins/referral.py
# This was causing force subscription checks before referral access
# The enhanced referral system is now handled entirely in plugins/referral.py
# @Client.on_message(filters.private & filters.command(['referral']))
# async def referral_command(client, message):
#     user_id = message.from_user.id
#     user_name = message.from_user.first_name
# 
#     # Force subscribe check
#     try:
#         is_subscribed = await client.get_chat_member(Config.CHANNEL_ID, user_id)
#         if is_subscribed.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:
#             await message.reply_text(
#                 "<b>❌ You are not subscribed to our channel!</b>\n\n"
#                 "<b>Please join our channel to use the referral system.</b>\n\n"
#                 f"<b>Channel:</b> {Config.CHANNEL_LINK}"
#             )
#             return
#     except Exception as e:
#         print(f"Error checking channel subscription: {e}")
#         await message.reply_text(
#             "<b>❌ Error checking subscription status. Please try again later.</b>"
#         )
#         return
# 
#     # Generate referral link
#     referral_link = f"https://t.me/{Config.BOT_USERNAME}?start=ref_{user_id}"
# 
#     # Referral stats
#     referrals = await db.get_referral_count(user_id)
#     total_earned = await db.get_total_referral_earnings(user_id)
# 
#     referral_text = f"""
#     <b>✨ Welcome to the Referral Program, {user_name}! ✨</b>
# 
#     <b>🚀 Your Unique Referral Link:</b>
#     <code>{referral_link}</code>
# 
#     <b>🔗 Share this link with your friends and earn rewards!</b>
# 
#     <b>📊 Your Referral Stats:</b>
#     • <b>Total Referrals:</b> {referrals}
#     • <b>Total Earned:</b> ₹{total_earned:.2f}
# 
#     <b>🎁 Rewards:</b>
#     • Earn ₹{Config.REFERRAL_REWARD_PER_USER:.2f} for each successful referral!
#     • Get your referral to subscribe to any plan to get rewarded.
# 
#     <b>📜 Rules:</b>
#     • Fake referrals will be ignored.
#     • Only genuine users who subscribe to a plan will be counted.
# 
#     <b>💡 Tip:</b> Share your link in groups and with friends who might find our bot useful!
#     """
#     await message.reply_text(referral_text)

# Callback for refreshing referral stats - REMOVED: Duplicate of plugins/referral.py  
# This was causing force subscription checks before referral callback access
# The enhanced referral system callbacks are now handled entirely in plugins/referral.py
# @Client.on_callback_query(filters.regex(r'^refresh_referral$'))
# async def refresh_referral_callback(client, callback_query):
#     user_id = callback_query.from_user.id
#     user_name = callback_query.from_user.first_name
# 
#     # Force subscribe check
#     try:
#         is_subscribed = await client.get_chat_member(Config.CHANNEL_ID, user_id)
#         if is_subscribed.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:
#             await callback_query.answer(
#                 "❌ You are not subscribed to our channel! Please join to access referral features.",
#                 show_alert=True
#             )
#             return
#     except Exception as e:
#         print(f"Error checking channel subscription: {e}")
#         await callback_query.answer("❌ Error checking subscription status. Please try again later.", show_alert=True)
#         return
# 
#     # Generate referral link
#     referral_link = f"https://t.me/{Config.BOT_USERNAME}?start=ref_{user_id}"
# 
#     # Referral stats
#     referrals = await db.get_referral_count(user_id)
#     total_earned = await db.get_total_referral_earnings(user_id)
# 
#     referral_text = f"""
#     <b>✨ Welcome to the Referral Program, {user_name}! ✨</b>
# 
#     <b>🚀 Your Unique Referral Link:</b>
#     <code>{referral_link}</code>
# 
#     <b>🔗 Share this link with your friends and earn rewards!</b>
# 
#     <b>📊 Your Referral Stats:</b>
#     • <b>Total Referrals:</b> {referrals}
#     • <b>Total Earned:</b> ₹{total_earned:.2f}
# 
#     <b>🎁 Rewards:</b>
#     • Earn ₹{Config.REFERRAL_REWARD_PER_USER:.2f} for each successful referral!
#     • Get your referral to subscribe to any plan to get rewarded.
# 
#     <b>📜 Rules:</b>
#     • Fake referrals will be ignored.
#     • Only genuine users who subscribe to a plan will be counted.
# 
#     <b>💡 Tip:</b> Share your link in groups and with friends who might find our bot useful!
#     """
# 
#     # Edit the message to show updated referral stats
#     await callback_query.message.edit_text(referral_text)
#     await callback_query.answer("✅ Referral stats refreshed!")

# Callback for premium plans
@Client.on_callback_query(filters.regex(r'^premium_plans$'))
async def premium_plans_callback(client, callback_query):
    from config import Config
    plans_text = f"""
    <b>💎 Explore Our Premium Plans!</b>

    <b>✨ Plus Plan</b>
    • ♾️ Unlimited forwarding processes
    • 🔄 All basic features
    • 📱 Standard support
    • 💰 15 days: ₹{Config.PLAN_PRICING['plus']['15_days']}
    • 💰 30 days: ₹{Config.PLAN_PRICING['plus']['30_days']}

    <b>🏆 Pro Plan</b>
    • ♾️ Unlimited forwarding processes
    • 🔥 FTM mode with source tracking
    • 🛡️ Priority support
    • ⚡ Enhanced performance
    • 💰 15 days: ₹{Config.PLAN_PRICING['pro']['15_days']}
    • 💰 30 days: ₹{Config.PLAN_PRICING['pro']['30_days']}

    <b>💳 How to Subscribe:</b>
    1. Choose your desired plan and duration.
    2. Click on the corresponding button to get payment instructions.
    3. Complete the payment and follow the verification steps.

    <b>📊 Check your current plan with /myplan</b>
    """

    plans_buttons = [
        [
            InlineKeyboardButton("✨ Plus 15 Days (₹199)", callback_data="buy_plus_15"),
            InlineKeyboardButton("✨ Plus 30 Days (₹299)", callback_data="buy_plus_30")
        ],
        [
            InlineKeyboardButton("🏆 Pro 15 Days (₹299)", callback_data="buy_pro_15"),
            InlineKeyboardButton("🏆 Pro 30 Days (₹549)", callback_data="buy_pro_30")
        ],
        [
            InlineKeyboardButton("🔗 Referral System", callback_data="refresh_referral"),
            InlineKeyboardButton("📊 My Plan Details", callback_data="my_plan")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back")
        ]
    ]

    await callback_query.message.edit_text(
        text=plans_text,
        reply_markup=InlineKeyboardMarkup(plans_buttons)
    )
    await callback_query.answer("Premium plans loaded!")