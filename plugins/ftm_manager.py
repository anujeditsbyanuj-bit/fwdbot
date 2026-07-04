import asyncio
import re
from database import db
from config import Config
from pyrogram import Client, filters, enums
from plugins.test import get_configs, update_configs
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import FloodWait
import logging

def get_numbering_format(number, style='dot'):
    """Generate formatted number based on style"""
    emoji_numbers = {
        0: '0️⃣', 1: '1️⃣', 2: '2️⃣', 3: '3️⃣', 4: '4️⃣',
        5: '5️⃣', 6: '6️⃣', 7: '7️⃣', 8: '8️⃣', 9: '9️⃣'
    }
    
    if style == 'dot':
        return f"{number}. "
    elif style == 'bracket':
        return f"{number}) "
    elif style == 'emoji':
        # Convert each digit to emoji
        emoji_str = ''.join(emoji_numbers.get(int(d), d) for d in str(number))
        return f"{emoji_str} "
    elif style == 'asterisk':
        return f"* {number} "
    elif style == 'dash':
        return f"- {number} "
    else:
        return f"{number}. "

def get_bullet_format(bullet_style='style1'):
    """Generate bullet prefix based on style"""
    bullet_styles = {
        'style1': '🚀 ',
        'style2': '🔥 ',
        'style3': '📌 ',
        'style4': '⭐ ',
        'style5': '💫 ',
        'style6': '✨ '
    }
    return bullet_styles.get(bullet_style, '🚀 ')

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

async def apply_ftm_transformations(caption, user_id, source_chat_id=None, source_msg_id=None, numbering_counter=None):
    if not caption:
        caption = ""

    config = await get_configs(user_id)

    ftm_replacer = config.get('ftm_replacer') or []
    for pair in ftm_replacer:
        caption = caption.replace(pair['old'], pair['new'])

    ftm_remover = config.get('ftm_remover') or []
    
    import html
    
    # Unescape HTML entities first (e.g., &lt;b&gt; -> <b>)
    caption = html.unescape(caption)
    
    for text_to_remove in ftm_remover:
        # Simple approach: Strip tags, check if text exists, then remove from original
        plain_caption = re.sub(r'<[^>]+>', '', caption)  # Strip all HTML tags
        
        if text_to_remove in plain_caption:
            # Text found in plain version - now remove it from HTML version
            # Build pattern: each char with optional HTML tags between
            pattern_parts = []
            for char in text_to_remove:
                pattern_parts.append(re.escape(char))
            # Join with optional tags between each character
            pattern = r'(?:<[^>]*>)*'.join(pattern_parts)
            caption = re.sub(pattern, '', caption)
        
        # Clean up empty formatting tags
        caption = re.sub(r'<(b|i|u|s|code|pre|em|strong|spoiler|tg-spoiler)>\s*</\1>', '', caption, flags=re.IGNORECASE)
        caption = re.sub(r'\n\s*\n', '\n', caption).strip()

    # Deeplink replacer - replaces all hyperlinks with user's own deeplink (only if deeplink remover is disabled)
    if config.get('ftm_deeplink_replacer', False) and not config.get('ftm_deeplink_remover', False):
        user_deeplink = config.get('ftm_deeplink_url', '')
        if user_deeplink:
            # Replace href in <a> tags with user's deeplink
            caption = re.sub(r'<a\s+href="[^"]*">', f'<a href="{user_deeplink}">', caption, flags=re.IGNORECASE)
    
    # Deeplink remover - removes links hidden in text (hyperlinks) but keeps the text
    if config.get('ftm_deeplink_remover', False):
        # Remove <a> tags but keep the text inside them
        caption = re.sub(r'<a\s+href="[^"]*">(.*?)</a>', r'\1', caption, flags=re.IGNORECASE)
    
    # Plain link remover - removes visible plain URL links (NOT inside href attributes)
    if config.get('ftm_plain_link_remover', False):
        # Use a function to only remove URLs that are NOT inside href=""
        def remove_plain_urls(text):
            # First, temporarily replace URLs inside href="" with placeholders
            href_pattern = r'(<a\s+href=")([^"]*)(">)'
            hrefs = []
            def save_href(match):
                hrefs.append(match.group(2))
                return match.group(1) + f"__HREF_PLACEHOLDER_{len(hrefs)-1}__" + match.group(3)
            text = re.sub(href_pattern, save_href, text, flags=re.IGNORECASE)
            
            # Now remove plain URLs
            text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
            
            # Restore the href URLs
            for i, href in enumerate(hrefs):
                text = text.replace(f"__HREF_PLACEHOLDER_{i}__", href)
            return text
        caption = remove_plain_urls(caption)

    # Username remover - removes @usernames from caption
    if config.get('ftm_username_remover', False):
        caption = re.sub(r'@[a-zA-Z0-9_]+', '', caption)

    if config.get('ftm_delta_mode', False) and source_chat_id and source_msg_id:
        if source_chat_id < 0:
            chat_id_str = str(source_chat_id)[4:]
            source_link = f"https://t.me/c/{chat_id_str}/{source_msg_id}"
        else:
            source_link = f"https://t.me/c/{source_chat_id}/{source_msg_id}"

        delta_version = config.get('ftm_delta_version', 'v1')
        
        if delta_version == 'v2':
            # V2 format: plain text link, no watermark text
            delta_tag = f'\n\n{source_link}'
        else:
            # V1 format: original format with emoji and hyperlink
            delta_tag = f'\n\n🔥 <b>ғᴛᴍ ᴅᴇʟᴛᴀ ᴍᴏᴅᴇ</b> 🔥\n📤 sᴏᴜʀᴄᴇ : <a href="{source_link}">ᴄʟɪᴄᴋ ʜᴇʀᴇ</a>'
        
        caption = caption + delta_tag if caption else delta_tag

    ftm_prefix = config.get('ftm_prefix', '')
    if ftm_prefix:
        caption = ftm_prefix + '\n\n' + caption if caption else ftm_prefix

    ftm_suffix = config.get('ftm_suffix', '')
    if ftm_suffix:
        caption = caption + '\n\n' + ftm_suffix if caption else ftm_suffix

    # FTM Bullets - add bullet prefix to caption (applied before numbering)
    if config.get('ftm_bullets_enabled', False):
        bullet_style = config.get('ftm_bullet_style', 'style1')
        bullet_prefix = get_bullet_format(bullet_style)
        caption = bullet_prefix + caption if caption else bullet_prefix.strip()

    # Auto numbering - add numbering prefix to caption (only for manual forwarding, applied after bullets)
    if config.get('ftm_auto_numbering', False) and numbering_counter is not None:
        numbering_style = config.get('ftm_numbering_style', 'dot')
        number_prefix = get_numbering_format(numbering_counter, numbering_style)
        caption = number_prefix + caption if caption else number_prefix.strip()

    return caption.strip() if caption else None

async def check_message_filters(message, user_id):
    """Check if message passes user's filter settings - for gamma mode"""
    config = await get_configs(user_id)
    filters = config.get('filters', {})
    
    # If message is text - check text filter (default: allow)
    if message.text:
        if not filters.get('text', True):
            return False
    # If message has document - check document filter (default: allow)
    elif message.document:
        if not filters.get('document', True):
            return False
    # If message has video - check video filter (default: allow)
    elif message.video:
        if not filters.get('video', True):
            return False
    # If message has photo - check photo filter (default: allow)
    elif message.photo:
        if not filters.get('photo', True):
            return False
    # If message has audio - check audio filter (default: allow)
    elif message.audio:
        if not filters.get('audio', True):
            return False
    # If message has voice - check voice filter (default: allow)
    elif message.voice:
        if not filters.get('voice', True):
            return False
    # If message has animation - check animation filter (default: allow)
    elif message.animation:
        if not filters.get('animation', True):
            return False
    # If message has sticker - check sticker filter (default: allow)
    elif message.sticker:
        if not filters.get('sticker', True):
            return False
    # If message has poll - check poll filter (default: allow)
    elif message.poll:
        if not filters.get('poll', True):
            return False
    else:
        # Message type not recognized, allow it
        return True
    
    # Check forward tag filter only for text messages
    if message.text and not config.get('forward_tag', True):
        if 'ftm' in message.text.lower():
            return False
    
    return True

async def apply_filters_only(caption, user_id, source_chat_id=None, source_msg_id=None, numbering_counter=None):
    """Apply ONLY filters without ftm_transformations - for gamma mode"""
    if not caption:
        caption = ""

    config = await get_configs(user_id)
    
    import html
    caption = html.unescape(caption)

    # Apply link filters ONLY (without text replacements/removals)
    
    # Deeplink replacer - replaces all hyperlinks with user's own deeplink
    if config.get('ftm_deeplink_replacer', False) and not config.get('ftm_deeplink_remover', False):
        user_deeplink = config.get('ftm_deeplink_url', '')
        if user_deeplink:
            caption = re.sub(r'<a\s+href="[^"]*">', f'<a href="{user_deeplink}">', caption, flags=re.IGNORECASE)
    
    # Deeplink remover - removes links hidden in text (hyperlinks) but keeps the text
    if config.get('ftm_deeplink_remover', False):
        caption = re.sub(r'<a\s+href="[^"]*">(.*?)</a>', r'\1', caption, flags=re.IGNORECASE)
    
    # Plain link remover - removes visible plain URL links
    if config.get('ftm_plain_link_remover', False):
        def remove_plain_urls(text):
            href_pattern = r'(<a\s+href=")([^"]*)(">)'
            hrefs = []
            def save_href(match):
                hrefs.append(match.group(2))
                return match.group(1) + f"__HREF_PLACEHOLDER_{len(hrefs)-1}__" + match.group(3)
            text = re.sub(href_pattern, save_href, text, flags=re.IGNORECASE)
            text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
            for i, href in enumerate(hrefs):
                text = text.replace(f"__HREF_PLACEHOLDER_{i}__", href)
            return text
        caption = remove_plain_urls(caption)

    # Username remover - removes @usernames from caption
    if config.get('ftm_username_remover', False):
        caption = re.sub(r'@[a-zA-Z0-9_]+', '', caption)

    # Watermark - add delta source tracking
    if config.get('ftm_delta_mode', False) and source_chat_id and source_msg_id:
        if source_chat_id < 0:
            chat_id_str = str(source_chat_id)[4:]
            source_link = f"https://t.me/c/{chat_id_str}/{source_msg_id}"
        else:
            source_link = f"https://t.me/c/{source_chat_id}/{source_msg_id}"

        delta_version = config.get('ftm_delta_version', 'v1')
        if delta_version == 'v2':
            # V2 format: plain text link, no watermark text
            delta_tag = f'\n\n{source_link}'
        else:
            # V1 format: original format with emoji and hyperlink
            delta_tag = f'\n\n🔥 <b>ғᴛᴍ ᴅᴇʟᴛᴀ ᴍᴏᴅᴇ</b> 🔥\n📤 sᴏᴜʀᴄᴇ : <a href="{source_link}">ᴄʟɪᴄᴋ ʜᴇʀᴇ</a>'
        caption = caption + delta_tag if caption else delta_tag

    # Add prefix and suffix
    ftm_prefix = config.get('ftm_prefix', '')
    if ftm_prefix:
        caption = ftm_prefix + '\n\n' + caption if caption else ftm_prefix

    ftm_suffix = config.get('ftm_suffix', '')
    if ftm_suffix:
        caption = caption + '\n\n' + ftm_suffix if caption else ftm_suffix

    # Bullets - add bullet prefix
    if config.get('ftm_bullets_enabled', False):
        bullet_style = config.get('ftm_bullet_style', 'style1')
        bullet_prefix = get_bullet_format(bullet_style)
        caption = bullet_prefix + caption if caption else bullet_prefix.strip()

    # Auto numbering - add numbering prefix
    if config.get('ftm_auto_numbering', False) and numbering_counter is not None:
        numbering_style = config.get('ftm_numbering_style', 'dot')
        number_prefix = get_numbering_format(numbering_counter, numbering_style)
        caption = number_prefix + caption if caption else number_prefix.strip()

    return caption.strip() if caption else None

@Client.on_callback_query(filters.regex(r'^ftm'))
async def ftm_manager_query(bot, query):
    user_id = query.from_user.id
    callback_data = query.data
    buttons = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data="settings#main")]]

    await query.answer()

    if callback_data == "ftm#main":
        from .subscription import require_ftm
        
        subscription = await db.get_subscription(user_id)
        features = subscription.get('features', {}).get('ftm', {})
        plan = subscription.get('plan', 'free')
        
        buttons = []
        
        # Plan-based features mapping
        # Pro: Gamma, Watermark
        # Infinity: Delta, Theta, Replacements, Link Remover, Auto Numbering, Bullets, Alpha
        
        # FTM Delta Mode
        if features.get('delta'):
            buttons.append([InlineKeyboardButton('🔥 ' + to_small_caps('ftm delta mode'), callback_data='ftm#delta')])
        else:
            buttons.append([InlineKeyboardButton('🔒 ' + to_small_caps('ftm delta mode (infinity)'), callback_data='ftm#locked_delta')])
        
        # FTM Alpha Mode - Infinity only
        if features.get('alpha'):
            buttons.append([InlineKeyboardButton('🧬 ' + to_small_caps('ftm alpha mode'), callback_data='ftm#alpha')])
        else:
            buttons.append([InlineKeyboardButton('🔒 ' + to_small_caps('ftm alpha mode (infinity)'), callback_data='ftm#locked_alpha')])
        
        # FTM Gamma Mode
        if features.get('gamma'):
            buttons.append([InlineKeyboardButton('💫 ' + to_small_caps('ftm gamma mode'), callback_data='ftm#gamma')])
        else:
            buttons.append([InlineKeyboardButton('🔒 ' + to_small_caps('ftm gamma mode (pro+)'), callback_data='ftm#locked_gamma')])
        
        # FTM Theta Mode
        if features.get('theta'):
            buttons.append([InlineKeyboardButton('🎯 ' + to_small_caps('ftm theta mode'), callback_data='ftm#theta')])
        else:
            buttons.append([InlineKeyboardButton('🔒 ' + to_small_caps('ftm theta mode (infinity)'), callback_data='ftm#locked_theta')])
        
        # FTM Watermark
        if features.get('watermark'):
            buttons.append([InlineKeyboardButton('💧 ' + to_small_caps('ftm watermark'), callback_data='ftm#watermark')])
        else:
            buttons.append([InlineKeyboardButton('🔒 ' + to_small_caps('ftm watermark (pro+)'), callback_data='ftm#locked_watermark')])

        # FTM Pi Mode
        buttons.append([InlineKeyboardButton('🥧 ' + to_small_caps('ftm pi mode'), callback_data='ftm#pi_mode')])
        
        # FTM Replacer & Remover
        if features.get('replacements'):
            buttons.append([InlineKeyboardButton('🌀 ' + to_small_caps('ftm replacer'), callback_data='ftm#replacer')])
            buttons.append([InlineKeyboardButton('✂️ ' + to_small_caps('ftm remover'), callback_data='ftm#remover')])
        else:
            buttons.append([InlineKeyboardButton('🔒 ' + to_small_caps('ftm replacer (infinity)'), callback_data='ftm#locked_replacer')])
            buttons.append([InlineKeyboardButton('🔒 ' + to_small_caps('ftm remover (infinity)'), callback_data='ftm#locked_remover')])
        
        # Auto Numbering & Bullets
        if features.get('replacements'):
            buttons.append([InlineKeyboardButton('🔢 ' + to_small_caps('ftm auto numbering'), callback_data='ftm#auto_numbering')])
            buttons.append([InlineKeyboardButton('💬 ' + to_small_caps('ftm bullets'), callback_data='ftm#bullets')])
        else:
            buttons.append([InlineKeyboardButton('🔒 ' + to_small_caps('ftm auto numbering (infinity)'), callback_data='ftm#locked_auto_numbering')])
            buttons.append([InlineKeyboardButton('🔒 ' + to_small_caps('ftm bullets (infinity)'), callback_data='ftm#locked_bullets')])
        
        buttons.append([InlineKeyboardButton(to_small_caps('↩ back'), callback_data='settings#main')])
        
        plan_info = Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])
        
        await query.message.edit_text(
            f"<b>🚀 {to_small_caps('ftm manager')} 🚀</b>\n\n"
            f"<b>{to_small_caps('your plan')}: {plan_info['emoji']} {plan_info['name']}</b>\n\n"
            f"<b>{to_small_caps('manage your forwarding transformation modes')}</b>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data.startswith("ftm#locked_"):
        feature_name = callback_data.replace("ftm#locked_", "")
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, feature_name)
        return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
    
    elif callback_data == "ftm#delta":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'delta')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        config = await get_configs(user_id)
        delta_status = config.get('ftm_delta_mode', False)
        delta_version = config.get('ftm_delta_version', 'v1')
        status_emoji = '✅' if delta_status else '❌'
        status_text = to_small_caps('enabled') if delta_status else to_small_caps('disabled')
        
        # FTM Alpha Mode - Update forwarding count for gamma/manual when delta forwards
        if delta_status and config.get('ftm_alpha_mode', False):
            try:
                fwd_state = await db.get_forwarding_state(user_id)
                if fwd_state and fwd_state.get('status') == 'active':
                    await db.update_gamma_last_msg(user_id, fwd_state.get('source_chat_id'), delta_version)
            except Exception as e:
                logging.error(f"[DELTA] Failed to update alpha progress: {e}")
        v1_check = '✅' if delta_version == 'v1' else '⬜'
        v2_check = '✅' if delta_version == 'v2' else '⬜'

        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle delta mode'), callback_data='ftm#toggle_delta')],
            [InlineKeyboardButton(f'{v1_check} V1 - ' + to_small_caps('classic format'), callback_data='ftm#set_delta_v1')],
            [InlineKeyboardButton(f'{v2_check} V2 - ' + to_small_caps('plain text format'), callback_data='ftm#set_delta_v2')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        await query.message.edit_text(
            f"<b>🔥 {to_small_caps('ftm delta mode')} 🔥</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_text}</b>\n\n"
            f"<b>📝 {to_small_caps('what is ftm delta mode?')}</b>\n"
            f"<i>{to_small_caps('source tracking for forwarded messages. when enabled, adds source message link in caption.')}</i>\n\n"
            f"<b>🎯 {to_small_caps('select version')}:</b>\n\n"
            f"<b>V1 - {to_small_caps('classic format')}:</b>\n"
            f"<i>{to_small_caps('emoji watermark with hyperlinked source')}</i>\n"
            f"<code>🔥 ғᴛᴍ ᴅᴇʟᴛᴀ ᴍᴏᴅᴇ 🔥\n📤 sᴏᴜʀᴄᴇ : ᴄʟɪᴄᴋ ʜᴇʀᴇ</code>\n\n"
            f"<b>V2 - {to_small_caps('plain text format')}:</b>\n"
            f"<i>{to_small_caps('plain text link without watermark text')}</i>\n"
            f"<code>https://t.me/c/channel/message</code>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#toggle_delta":
        from .subscription import require_ftm
        
        has_permission, error_message = await require_ftm(user_id, 'delta')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        current_status = config.get('ftm_delta_mode', False)
        await update_configs(user_id, 'ftm_delta_mode', not current_status)

        new_status = not current_status
        status_emoji = '✅' if new_status else '❌'
        status_text = to_small_caps('enabled') if new_status else to_small_caps('disabled')
        
        # Log FTM delta mode toggle
        from plugins.logger import BotLogger
        await BotLogger.log_ftm_mode_toggled(bot, user_id, query.from_user.first_name, 'delta', new_status)

        delta_version = config.get('ftm_delta_version', 'v1')
        v1_check = '✅' if delta_version == 'v1' else '⬜'
        v2_check = '✅' if delta_version == 'v2' else '⬜'

        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle delta mode'), callback_data='ftm#toggle_delta')],
            [InlineKeyboardButton(f'{v1_check} V1 - ' + to_small_caps('classic format'), callback_data='ftm#set_delta_v1')],
            [InlineKeyboardButton(f'{v2_check} V2 - ' + to_small_caps('plain text format'), callback_data='ftm#set_delta_v2')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        await query.message.edit_text(
            f"<b>🔥 {to_small_caps('ftm delta mode')} 🔥</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_text}</b>\n\n"
            f"<b>📝 {to_small_caps('what is ftm delta mode?')}</b>\n"
            f"<i>{to_small_caps('source tracking for forwarded messages. when enabled, adds source message link in caption.')}</i>\n\n"
            f"<b>🎯 {to_small_caps('select version')}:</b>\n\n"
            f"<b>V1 - {to_small_caps('classic format')}:</b>\n"
            f"<i>{to_small_caps('emoji watermark with hyperlinked source')}</i>\n"
            f"<code>🔥 ғᴛᴍ ᴅᴇʟᴛᴀ ᴍᴏᴅᴇ 🔥\n📤 sᴏᴜʀᴄᴇ : ᴄʟɪᴄᴋ ʜᴇʀᴇ</code>\n\n"
            f"<b>V2 - {to_small_caps('plain text format')}:</b>\n"
            f"<i>{to_small_caps('plain text link without watermark text')}</i>\n"
            f"<code>https://t.me/c/channel/message</code>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif callback_data == "ftm#set_delta_v1":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'delta')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        await update_configs(user_id, 'ftm_delta_version', 'v1')
        await query.answer("✅ V1 " + to_small_caps('format selected - classic with emoji'), show_alert=True)
        
        # Refresh the delta menu
        config = await get_configs(user_id)
        delta_status = config.get('ftm_delta_mode', False)
        status_emoji = '✅' if delta_status else '❌'
        status_text = to_small_caps('enabled') if delta_status else to_small_caps('disabled')
        
        v1_check = '✅'
        v2_check = '⬜'

        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle delta mode'), callback_data='ftm#toggle_delta')],
            [InlineKeyboardButton(f'{v1_check} V1 - ' + to_small_caps('classic format'), callback_data='ftm#set_delta_v1')],
            [InlineKeyboardButton(f'{v2_check} V2 - ' + to_small_caps('plain text format'), callback_data='ftm#set_delta_v2')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        await query.message.edit_text(
            f"<b>🔥 {to_small_caps('ftm delta mode')} 🔥</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_text}</b>\n\n"
            f"<b>📝 {to_small_caps('what is ftm delta mode?')}</b>\n"
            f"<i>{to_small_caps('source tracking for forwarded messages. when enabled, adds source message link in caption.')}</i>\n\n"
            f"<b>🎯 {to_small_caps('select version')}:</b>\n\n"
            f"<b>V1 - {to_small_caps('classic format')}:</b>\n"
            f"<i>{to_small_caps('emoji watermark with hyperlinked source')}</i>\n"
            f"<code>🔥 ғᴛᴍ ᴅᴇʟᴛᴀ ᴍᴏᴅᴇ 🔥\n📤 sᴏᴜʀᴄᴇ : ᴄʟɪᴄᴋ ʜᴇʀᴇ</code>\n\n"
            f"<b>V2 - {to_small_caps('plain text format')}:</b>\n"
            f"<i>{to_small_caps('plain text link without watermark text')}</i>\n"
            f"<code>https://t.me/c/channel/message</code>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif callback_data == "ftm#set_delta_v2":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'delta')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        await update_configs(user_id, 'ftm_delta_version', 'v2')
        await query.answer("✅ V2 " + to_small_caps('format selected - plain text link only'), show_alert=True)
        
        # Refresh the delta menu
        config = await get_configs(user_id)
        delta_status = config.get('ftm_delta_mode', False)
        status_emoji = '✅' if delta_status else '❌'
        status_text = to_small_caps('enabled') if delta_status else to_small_caps('disabled')
        
        v1_check = '⬜'
        v2_check = '✅'

        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle delta mode'), callback_data='ftm#toggle_delta')],
            [InlineKeyboardButton(f'{v1_check} V1 - ' + to_small_caps('classic format'), callback_data='ftm#set_delta_v1')],
            [InlineKeyboardButton(f'{v2_check} V2 - ' + to_small_caps('plain text format'), callback_data='ftm#set_delta_v2')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        await query.message.edit_text(
            f"<b>🔥 {to_small_caps('ftm delta mode')} 🔥</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_text}</b>\n\n"
            f"<b>📝 {to_small_caps('what is ftm delta mode?')}</b>\n"
            f"<i>{to_small_caps('source tracking for forwarded messages. when enabled, adds source message link in caption.')}</i>\n\n"
            f"<b>🎯 {to_small_caps('select version')}:</b>\n\n"
            f"<b>V1 - {to_small_caps('classic format')}:</b>\n"
            f"<i>{to_small_caps('emoji watermark with hyperlinked source')}</i>\n"
            f"<code>🔥 ғᴛᴍ ᴅᴇʟᴛᴀ ᴍᴏᴅᴇ 🔥\n📤 sᴏᴜʀᴄᴇ : ᴄʟɪᴄᴋ ʜᴇʀᴇ</code>\n\n"
            f"<b>V2 - {to_small_caps('plain text format')}:</b>\n"
            f"<i>{to_small_caps('plain text link without watermark text')}</i>\n"
            f"<code>https://t.me/c/channel/message</code>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#watermark":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'watermark')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        try:
            config = await get_configs(user_id)
            prefix = config.get('ftm_prefix', '')
            suffix = config.get('ftm_suffix', '')

            buttons = [
                [
                    InlineKeyboardButton('📝 ' + to_small_caps('ftm prefix'), callback_data='ftm#prefix'),
                    InlineKeyboardButton('👁️ ' + to_small_caps('view'), callback_data='ftm#view_prefix')
                ],
                [
                    InlineKeyboardButton('📌 ' + to_small_caps('ftm suffix'), callback_data='ftm#suffix'),
                    InlineKeyboardButton('👁️ ' + to_small_caps('view'), callback_data='ftm#view_suffix')
                ],
                [
                    InlineKeyboardButton('🗑️ ' + to_small_caps('clear prefix'), callback_data='ftm#clear_prefix'),
                    InlineKeyboardButton('🗑️ ' + to_small_caps('clear suffix'), callback_data='ftm#clear_suffix')
                ],
                [InlineKeyboardButton('✏️ ' + to_small_caps('ftm captions'), callback_data='ftm#captions')],
                [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
            ]

            # Safely create preview by stripping HTML tags for display
            import re
            prefix_clean = re.sub(r'<[^>]+>', '', prefix) if prefix else ''
            suffix_clean = re.sub(r'<[^>]+>', '', suffix) if suffix else ''

            prefix_preview = (prefix_clean[:30] + '...') if len(prefix_clean) > 30 else (prefix_clean if prefix_clean else to_small_caps('not set'))
            suffix_preview = (suffix_clean[:30] + '...') if len(suffix_clean) > 30 else (suffix_clean if suffix_clean else to_small_caps('not set'))

            await query.message.edit_text(
                f"<b>💧 {to_small_caps('ftm watermark')} 💧</b>\n\n"
                f"<b>{to_small_caps('current settings')}:</b>\n"
                f"• <b>{to_small_caps('prefix')}: </b><code>{prefix_preview}</code>\n"
                f"• <b>{to_small_caps('suffix')}: </b><code>{suffix_preview}</code>\n\n"
                f"<b>📝 {to_small_caps('what is watermark?')}</b>\n"
                f"<i>{to_small_caps('add custom prefix and suffix text to all forwarded messages.')}</i>\n\n"
                f"<b>✨ {to_small_caps('features')}:</b>\n"
                f"• <b>{to_small_caps('prefix')}</b> - {to_small_caps('added before caption on new line')}\n"
                f"• <b>{to_small_caps('suffix')}</b> - {to_small_caps('added after caption on new line')}\n"
                f"• {to_small_caps('supports html formatting')}\n"
                f"• {to_small_caps('works with all media types')}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            logging.error(f"[FTM] Error in watermark callback: {e}")
            import traceback
            traceback.print_exc()
            await query.answer(to_small_caps('error loading watermark settings'), show_alert=True)

    elif callback_data == "ftm#pi_mode":
        config = await get_configs(user_id)
        pi_status = config.get('ftm_pi_mode', False)
        status_emoji = '✅' if pi_status else '❌'
        status_text = to_small_caps('enabled') if pi_status else to_small_caps('disabled')
        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle pi mode'), callback_data='ftm#toggle_pi_mode')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        await query.message.edit_text(
            f"<b>🥧 {to_small_caps('ftm pi mode')} 🥧</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_text}</b>\n\n"
            f"<b>📝 {to_small_caps('what is ftm pi mode?')}</b>\n"
            f"<i>{to_small_caps('when enabled, you can select multiple target channels during manual forwarding.')}</i>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#toggle_pi_mode":
        config = await get_configs(user_id)
        current_status = config.get('ftm_pi_mode', False)
        new_status = not current_status
        await update_configs(user_id, 'ftm_pi_mode', new_status)

        from plugins.logger import BotLogger
        await BotLogger.log_ftm_mode_toggled(bot, user_id, query.from_user.first_name, 'pi_mode', new_status)

        status_emoji = '✅' if new_status else '❌'
        status_text = to_small_caps('enabled') if new_status else to_small_caps('disabled')
        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle pi mode'), callback_data='ftm#toggle_pi_mode')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        await query.message.edit_text(
            f"<b>🥧 {to_small_caps('ftm pi mode')} 🥧</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_text}</b>\n\n"
            f"<b>📝 {to_small_caps('what is ftm pi mode?')}</b>\n"
            f"<i>{to_small_caps('when enabled, you can select multiple target channels during manual forwarding.')}</i>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#gamma":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'gamma')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        config = await get_configs(user_id)
        gamma_status = config.get('ftm_gamma_mode', False)
        status_emoji = '✅' if gamma_status else '❌'
        status_text = to_small_caps('enabled') if gamma_status else to_small_caps('disabled')

        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle gamma mode'), callback_data='ftm#toggle_gamma')],
            [InlineKeyboardButton(to_small_caps('gamma source'), callback_data='ftm#gamma_source')],
            [InlineKeyboardButton(to_small_caps('gamma target'), callback_data='ftm#gamma_target')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        await query.message.edit_text(
            f"<b>💫 {to_small_caps('ftm gamma mode')}</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_text}</b>\n\n"
            f"<i>{to_small_caps('multi-channel auto-forwarding with filters. automatically forwards new messages from source channels to target channels with all your configured filters.')}</i>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#toggle_gamma":
        from .subscription import require_ftm
        
        has_permission, error_message = await require_ftm(user_id, 'gamma')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        current_status = config.get('ftm_gamma_mode', False)

        # If trying to enable, verify permissions
        if not current_status:
            _bot = await db.get_bot(user_id)
            if not _bot:
                buttons = [
                    [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma')]
                ]
                return await query.message.edit_text(
                    f"<b>❌ {to_small_caps('no bot added')}</b>\n\n"
                    f"<i>{to_small_caps('please add a bot or userbot first from settings')}</i>",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            gamma_sources = config.get('ftm_gamma_sources', [])
            gamma_targets = config.get('ftm_gamma_targets', [])

            if not gamma_sources or not gamma_targets:
                buttons = [
                    [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma')]
                ]
                return await query.message.edit_text(
                    f"<b>⚠️ {to_small_caps('channels not configured')}</b>\n\n"
                    f"<i>{to_small_caps('please add at least one source and one target channel first')}</i>",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Start bot client for verification
            from plugins.test import start_clone_bot, CLIENT
            try:
                bot_client = await start_clone_bot(CLIENT().client(_bot))
            except Exception as e:
                buttons = [
                    [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma')]
                ]
                return await query.message.edit_text(
                    f"<b>❌ {to_small_caps('failed to start bot client')}</b>\n\n"
                    f"<i>{to_small_caps('error')}: {str(e)}\n\n"
                    f"{to_small_caps('please check your bot credentials and try again')}</i>",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )

            # Step 5: Checking permissions
            await query.message.edit_text(
                f"<b>🔍 {to_small_caps('verifying channel permissions')}</b>\n\n"
                f"{'▰' * 8}{'▱' * 2} 80%\n\n"
                f"📢 {to_small_caps('checking source channels')}\n"
                f"🎯 {to_small_caps('checking target channels')}\n"
                f"🔐 {to_small_caps('validating admin rights')}..."
            )
            await asyncio.sleep(0.7)

            # Check source channel permissions
            permission_errors = []
            for source in gamma_sources:
                try:
                    chat = await bot_client.get_chat(source['chat_id'])
                    # Check if bot is member
                    try:
                        member = await bot_client.get_chat_member(source['chat_id'], bot_client.me.id)
                    except Exception:
                        permission_errors.append(f"❌ {to_small_caps('not a member of')} {source['title']}")
                except Exception as e:
                    permission_errors.append(f"❌ {to_small_caps('cannot access')} {source['title']}: {str(e)}")

            # Check target channel permissions
            for target in gamma_targets:
                try:
                    chat = await bot_client.get_chat(target['chat_id'])
                    member = await bot_client.get_chat_member(target['chat_id'], bot_client.me.id)
                    # Check if bot has admin rights
                    if not (member.status in ['administrator', 'creator'] or member.privileges):
                        permission_errors.append(f"❌ {to_small_caps('not admin in')} {target['title']}")
                except Exception as e:
                    permission_errors.append(f"❌ {to_small_caps('cannot access')} {target['title']}: {str(e)}")

            # Step 6: Permission check complete
            await query.message.edit_text(
                f"<b>✅ {to_small_caps('permissions verified')}</b>\n\n"
                f"{'▰' * 9}{'▱' * 1} 90%\n\n"
                f"🎯 {to_small_caps('source channels')} ✓\n"
                f"📢 {to_small_caps('target channels')} ✓\n"
                f"🛡️ {to_small_caps('admin rights confirmed')}..."
            )
            await asyncio.sleep(0.5)


            if permission_errors:
                error_text = f"<b>🚫 {to_small_caps('permission check failed')}</b>\n\n"
                error_text += "\n".join(permission_errors[:10])  # Show max 10 errors
                error_text += f"\n\n<i>{to_small_caps('please ensure your bot/userbot has proper permissions:')}</i>\n"
                error_text += f"• {to_small_caps('member of source channels')}\n"
                error_text += f"• {to_small_caps('admin with post rights in target channels')}"

                buttons = [
                    [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma')]
                ]
                return await query.message.edit_text(error_text, reply_markup=InlineKeyboardMarkup(buttons))

        # All checks passed, toggle the mode
        await update_configs(user_id, 'ftm_gamma_mode', not current_status)

        new_status = not current_status

        # Start or stop monitoring based on new status
        if new_status:
            success = await start_gamma_monitoring(user_id)
            if not success:
                await update_configs(user_id, 'ftm_gamma_mode', False)
                buttons = [
                    [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma')]
                ]
                return await query.message.edit_text(
                    f"<b>❌ {to_small_caps('failed to start monitoring')}</b>\n\n"
                    f"<i>{to_small_caps('please check your bot credentials and try again')}</i>",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
        else:
            await stop_gamma_monitoring(user_id)
        
        # Log FTM gamma mode toggle
        from plugins.logger import BotLogger
        await BotLogger.log_ftm_mode_toggled(bot, user_id, query.from_user.first_name, 'gamma', new_status)

        status_emoji = '✅' if new_status else '❌'
        status_text = to_small_caps('enabled') if new_status else to_small_caps('disabled')

        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle gamma mode'), callback_data='ftm#toggle_gamma')],
            [InlineKeyboardButton(to_small_caps('gamma source'), callback_data='ftm#gamma_source')],
            [InlineKeyboardButton(to_small_caps('gamma target'), callback_data='ftm#gamma_target')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        await query.message.edit_text(
            f"<b>💫 {to_small_caps('ftm gamma mode')}</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_text}</b>\n\n"
            f"<i>{to_small_caps('multi-channel auto-forwarding with filters. automatically forwards new messages from source channels to target channels with all your configured filters.')}</i>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#theta":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'theta')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        config = await get_configs(user_id)
        theta_status = config.get('ftm_theta_mode', False)
        status_emoji = '✅' if theta_status else '❌'
        status_text = to_small_caps('enabled') if theta_status else to_small_caps('disabled')

        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle theta mode'), callback_data='ftm#toggle_theta')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        await query.message.edit_text(
            f"<b>🎯 {to_small_caps('ftm theta mode')} 🎯</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_text}</b>\n\n"
            f"<b>📝 {to_small_caps('what is ftm theta mode?')}</b>\n"
            f"<i>{to_small_caps('smart image filter for forwarding. when enabled, only forwards images/photos that have captions (text). messages without both image and caption will be skipped.')}</i>\n\n"
            f"<b>✨ {to_small_caps('features')}:</b>\n"
            f"• {to_small_caps('only forwards photos with captions')}\n"
            f"• {to_small_caps('skips images without text')}\n"
            f"• {to_small_caps('skips text-only messages')}\n"
            f"• {to_small_caps('works with gamma mode auto-forwarding')}\n"
            f"• {to_small_caps('works with manual forwarding')}\n\n"
            f"<b>📌 {to_small_caps('use case')}:</b>\n"
            f"<i>{to_small_caps('perfect for forwarding product posts, announcements, or any content that requires both visual and text information.')}</i>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#toggle_theta":
        from .subscription import require_ftm
        
        has_permission, error_message = await require_ftm(user_id, 'theta')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        current_status = config.get('ftm_theta_mode', False)
        await update_configs(user_id, 'ftm_theta_mode', not current_status)

        new_status = not current_status
        status_emoji = '✅' if new_status else '❌'
        status_text = to_small_caps('enabled') if new_status else to_small_caps('disabled')
        
        from plugins.logger import BotLogger
        await BotLogger.log_ftm_mode_toggled(bot, user_id, query.from_user.first_name, 'theta', new_status)

        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle theta mode'), callback_data='ftm#toggle_theta')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        await query.message.edit_text(
            f"<b>🎯 {to_small_caps('ftm theta mode')} 🎯</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_text}</b>\n\n"
            f"<b>📝 {to_small_caps('what is ftm theta mode?')}</b>\n"
            f"<i>{to_small_caps('smart image filter for forwarding. when enabled, only forwards images/photos that have captions (text). messages without both image and caption will be skipped.')}</i>\n\n"
            f"<b>✨ {to_small_caps('features')}:</b>\n"
            f"• {to_small_caps('only forwards photos with captions')}\n"
            f"• {to_small_caps('skips images without text')}\n"
            f"• {to_small_caps('skips text-only messages')}\n"
            f"• {to_small_caps('works with gamma mode auto-forwarding')}\n"
            f"• {to_small_caps('works with manual forwarding')}\n\n"
            f"<b>📌 {to_small_caps('use case')}:</b>\n"
            f"<i>{to_small_caps('perfect for forwarding product posts, announcements, or any content that requires both visual and text information.')}</i>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#alpha":
        # FTM Alpha Mode - Infinity only
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'alpha')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        config = await get_configs(user_id)
        alpha_status = config.get('ftm_alpha_mode', False)
        status_emoji = '✅' if alpha_status else '❌'
        status_text = to_small_caps('enabled') if alpha_status else to_small_caps('disabled')
        
        # Get current forwarding state if any
        fwd_state = await db.get_forwarding_state(user_id)
        state_info = ""
        if fwd_state:
            state_type = fwd_state.get('type', 'unknown')
            state_status = fwd_state.get('status', 'unknown')
            processed = fwd_state.get('processed', 0)
            total = fwd_state.get('total', 0)
            state_info = f"\n\n<b>📊 {to_small_caps('last saved state')}:</b>\n"
            state_info += f"• {to_small_caps('type')}: {state_type}\n"
            state_info += f"• {to_small_caps('status')}: {state_status}\n"
            state_info += f"• {to_small_caps('progress')}: {processed}/{total}"
        
        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle alpha mode'), callback_data='ftm#toggle_alpha')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        await query.message.edit_text(
            f"<b>🧬 {to_small_caps('ftm alpha mode')} 🧬</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_text}</b>\n\n"
            f"<b>📝 {to_small_caps('what is ftm alpha mode?')}</b>\n"
            f"<i>{to_small_caps('auto-resume for forwarding processes. when enabled, if the bot restarts during manual or gamma forwarding, it will automatically resume from where it left off.')}</i>\n\n"
            f"<b>✨ {to_small_caps('features')}:</b>\n"
            f"• {to_small_caps('saves forwarding progress to database')}\n"
            f"• {to_small_caps('auto-resumes after bot restart')}\n"
            f"• {to_small_caps('notifies you when process completes')}\n"
            f"• {to_small_caps('logs to admin panel and log channel')}\n"
            f"• {to_small_caps('works with manual and gamma forwarding')}\n\n"
            f"<b>📌 {to_small_caps('use case')}:</b>\n"
            f"<i>{to_small_caps('never lose forwarding progress due to bot restarts or crashes.')}</i>"
            f"{state_info}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#toggle_alpha":
        # Toggle FTM Alpha Mode - Infinity only
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'alpha')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        config = await get_configs(user_id)
        current_status = config.get('ftm_alpha_mode', False)
        await update_configs(user_id, 'ftm_alpha_mode', not current_status)
        
        new_status = not current_status
        status_emoji = '✅' if new_status else '❌'
        status_text = to_small_caps('enabled') if new_status else to_small_caps('disabled')
        
        from plugins.logger import BotLogger
        await BotLogger.log_ftm_mode_toggled(bot, user_id, query.from_user.first_name, 'alpha', new_status)
        
        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle alpha mode'), callback_data='ftm#toggle_alpha')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        await query.message.edit_text(
            f"<b>🧬 {to_small_caps('ftm alpha mode')} 🧬</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_text}</b>\n\n"
            f"<b>📝 {to_small_caps('what is ftm alpha mode?')}</b>\n"
            f"<i>{to_small_caps('auto-resume for forwarding processes. when enabled, if the bot restarts during manual or gamma forwarding, it will automatically resume from where it left off.')}</i>\n\n"
            f"<b>✨ {to_small_caps('features')}:</b>\n"
            f"• {to_small_caps('saves forwarding progress to database')}\n"
            f"• {to_small_caps('auto-resumes after bot restart')}\n"
            f"• {to_small_caps('notifies you when process completes')}\n"
            f"• {to_small_caps('logs to admin panel and log channel')}\n"
            f"• {to_small_caps('works with manual and gamma forwarding')}\n\n"
            f"<b>📌 {to_small_caps('use case')}:</b>\n"
            f"<i>{to_small_caps('never lose forwarding progress due to bot restarts or crashes.')}</i>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif callback_data == "ftm#locked_alpha":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'alpha')
        return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
    
    elif callback_data == "ftm#gamma_source":
        config = await get_configs(user_id)
        sources = config.get('ftm_gamma_sources', [])

        buttons = []
        for source in sources:
            buttons.append([InlineKeyboardButton(f"📢 {source['title']}", callback_data=f"ftm#view_source_{source['chat_id']}")])

        buttons.append([InlineKeyboardButton('✚ ' + to_small_caps('add source channel'), callback_data='ftm#add_gamma_source')])
        buttons.append([InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma')])

        await query.message.edit_text(
            f"<b>📢 {to_small_caps('gamma source channels')}</b>\n\n"
            f"<b>{to_small_caps('total sources')}: {len(sources)}</b>\n\n"
            f"<i>{to_small_caps('these channels will be monitored for auto-forwarding')}</i>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#add_gamma_source":
        await query.message.delete()
        try:
            text = await bot.send_message(user_id, f"<b>❪ {to_small_caps('add gamma source channel')} ❫\n\n📨 {to_small_caps('forward a message from your source channel')}\n\n/cancel - {to_small_caps('cancel this process')}</b>")
            from plugins.conversation import listen, is_forwarded_or_cancel
            chat_msg = await listen(bot, user_id, filter_func=is_forwarded_or_cancel, timeout=300)
            if chat_msg is None:
                back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma_source')]]
                return await text.edit_text(f'<b>⏱️ {to_small_caps("process has been automatically cancelled")}</b>', reply_markup=InlineKeyboardMarkup(back_btn))
            if chat_msg.text and chat_msg.text.startswith("/cancel"):
                await chat_msg.delete()
                back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma_source')]]
                return await text.edit_text(
                    f"<b>❌ {to_small_caps('process cancelled')}</b>",
                    reply_markup=InlineKeyboardMarkup(back_btn))
            elif not chat_msg.forward_date:
                await chat_msg.delete()
                return await text.edit_text(f"<b>❌ {to_small_caps('this is not a forward message')}</b>")
            else:
                chat_id = chat_msg.forward_from_chat.id
                title = chat_msg.forward_from_chat.title
                username = chat_msg.forward_from_chat.username if chat_msg.forward_from_chat.username else "private"

                config = await get_configs(user_id)
                sources = config.get('ftm_gamma_sources', [])

                if any(s['chat_id'] == chat_id for s in sources):
                    await chat_msg.delete()
                    return await text.edit_text(f"<b>⚠️ {to_small_caps('this channel already added as source')}</b>")

                # Create a completely new list to ensure MongoDB detects the change
                new_sources = [dict(s) for s in sources]
                new_sources.append({'chat_id': chat_id, 'title': title, 'username': username})
                await update_configs(user_id, 'ftm_gamma_sources', new_sources)
                
                # Log gamma source channel addition
                from plugins.logger import BotLogger
                await BotLogger.log_channel_added(bot, user_id, chat_msg.from_user.first_name, 'gamma_source', title, chat_id)
                
                await chat_msg.delete()
                back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma_source')]]
                await text.edit_text(
                    f"<b>✅ {to_small_caps('source channel added successfully!')}</b>\n\n"
                    f"<b>📝 {to_small_caps('name')}: <code>{title}</code>\n"
                    f"🆔 {to_small_caps('channel id')}: <code>{chat_id}</code></b>",
                    reply_markup=InlineKeyboardMarkup(back_btn))
        except asyncio.exceptions.TimeoutError:
            back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma_source')]]
            await text.edit_text(f'<b>⏱️ {to_small_caps("process has been automatically cancelled")}</b>', reply_markup=InlineKeyboardMarkup(back_btn))

    elif callback_data.startswith("ftm#view_source_"):
        chat_id = int(callback_data.split('_')[-1])
        config = await get_configs(user_id)
        sources = config.get('ftm_gamma_sources', [])
        source = next((s for s in sources if s['chat_id'] == chat_id), None)

        if source:
            buttons = [
                [InlineKeyboardButton('❌ ' + to_small_caps('remove source'), callback_data=f'ftm#remove_source_{chat_id}')],
                [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma_source')]
            ]
            await query.message.edit_text(
                f"<b>📢 {to_small_caps('source channel details')}</b>\n\n"
                f"<b>{to_small_caps('title')}: <code>{source['title']}</code>\n"
                f"{to_small_caps('channel id')}: <code>{source['chat_id']}</code>\n"
                f"{to_small_caps('username')}: @{source['username']}</b>",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    elif callback_data.startswith("ftm#remove_source_"):
        chat_id = int(callback_data.split('_')[-1])
        config = await get_configs(user_id)
        sources = config.get('ftm_gamma_sources', [])
        new_sources = [dict(s) for s in sources if s['chat_id'] != chat_id]
        await update_configs(user_id, 'ftm_gamma_sources', new_sources)

        back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma_source')]]
        await query.message.edit_text(
            f"<b>✅ {to_small_caps('source channel removed successfully')}</b>",
            reply_markup=InlineKeyboardMarkup(back_btn))

    elif callback_data == "ftm#gamma_target":
        config = await get_configs(user_id)
        targets = config.get('ftm_gamma_targets', [])

        buttons = []
        for target in targets:
            topic_suffix = " (topic)" if target.get('thread_id') else ""
            buttons.append([InlineKeyboardButton(f"🎯 {target['title']}{topic_suffix}", callback_data=f"ftm#view_target_{target['chat_id']}")])

        buttons.append([InlineKeyboardButton('✚ ' + to_small_caps('add target channel'), callback_data='ftm#add_gamma_target')])
        buttons.append([InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma')])

        await query.message.edit_text(
            f"<b>🎯 {to_small_caps('gamma target channels')}</b>\n\n"
            f"<b>{to_small_caps('total targets')}: {len(targets)}</b>\n\n"
            f"<i>{to_small_caps('messages will be auto-forwarded to these channels')}</i>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#add_gamma_target":
        await query.message.delete()
        try:
            text = await bot.send_message(user_id, f"<b>❪ {to_small_caps('add gamma target channel')} ❫\n\n📨 {to_small_caps('forward a message from your target channel')}\n\n/cancel - {to_small_caps('cancel this process')}</b>")
            from plugins.conversation import listen, is_forwarded_or_cancel
            chat_msg = await listen(bot, user_id, filter_func=is_forwarded_or_cancel, timeout=300)
            if chat_msg is None:
                back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma_target')]]
                return await text.edit_text(f'<b>⏱️ {to_small_caps("process has been automatically cancelled")}</b>', reply_markup=InlineKeyboardMarkup(back_btn))
            if chat_msg.text and chat_msg.text.startswith("/cancel"):
                await chat_msg.delete()
                back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma_target')]]
                return await text.edit_text(
                    f"<b>❌ {to_small_caps('process cancelled')}</b>",
                    reply_markup=InlineKeyboardMarkup(back_btn))
            elif not chat_msg.forward_date:
                await chat_msg.delete()
                return await text.edit_text(f"<b>❌ {to_small_caps('this is not a forward message')}</b>")
            else:
                chat_id = chat_msg.forward_from_chat.id
                title = chat_msg.forward_from_chat.title
                username = chat_msg.forward_from_chat.username if chat_msg.forward_from_chat.username else "private"

                config = await get_configs(user_id)
                targets = config.get('ftm_gamma_targets', [])

                if any(t['chat_id'] == chat_id for t in targets):
                    await chat_msg.delete()
                    return await text.edit_text(f"<b>⚠️ {to_small_caps('this channel already added as target')}</b>")

                # Create a completely new list to ensure MongoDB detects the change
                thread_id = chat_msg.message_thread_id if chat_msg.is_topic_message else None
                new_targets = [dict(t) for t in targets]
                new_targets.append({'chat_id': chat_id, 'title': title, 'username': username, 'thread_id': thread_id})
                await update_configs(user_id, 'ftm_gamma_targets', new_targets)
                
                # Log gamma target channel addition
                from plugins.logger import BotLogger
                await BotLogger.log_channel_added(bot, user_id, chat_msg.from_user.first_name, 'gamma_target', title, chat_id)
                
                await chat_msg.delete()
                back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma_target')]]
                topic_line = f"🧵 {to_small_caps('topic id')}: <code>{thread_id}</code>\n" if thread_id else ""
                await text.edit_text(
                    f"<b>✅ {to_small_caps('target channel added successfully!')}</b>\n\n"
                    f"<b>📝 {to_small_caps('name')}: <code>{title}</code>\n"
                    f"🆔 {to_small_caps('channel id')}: <code>{chat_id}</code>\n"
                    f"{topic_line}</b>",
                    reply_markup=InlineKeyboardMarkup(back_btn))
        except asyncio.exceptions.TimeoutError:
            back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma_target')]]
            await text.edit_text(f'<b>⏱️ {to_small_caps("process has been automatically cancelled")}</b>', reply_markup=InlineKeyboardMarkup(back_btn))

    elif callback_data.startswith("ftm#view_target_"):
        chat_id = int(callback_data.split('_')[-1])
        config = await get_configs(user_id)
        targets = config.get('ftm_gamma_targets', [])
        target = next((t for t in targets if t['chat_id'] == chat_id), None)

        if target:
            buttons = [
                [InlineKeyboardButton('❌ ' + to_small_caps('remove target'), callback_data=f'ftm#remove_target_{chat_id}')],
                [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma_target')]
            ]
            topic_line = f"{to_small_caps('topic id')}: <code>{target['thread_id']}</code>\n" if target.get('thread_id') else ''
            await query.message.edit_text(
                f"<b>🎯 {to_small_caps('target channel details')}</b>\n\n"
                f"<b>{to_small_caps('title')}: <code>{target['title']}</code>\n"
                f"{to_small_caps('channel id')}: <code>{target['chat_id']}</code>\n"
                f"{topic_line}"
                f"{to_small_caps('username')}: @{target['username']}</b>",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    elif callback_data.startswith("ftm#remove_target_"):
        chat_id = int(callback_data.split('_')[-1])
        config = await get_configs(user_id)
        targets = config.get('ftm_gamma_targets', [])
        new_targets = [dict(t) for t in targets if t['chat_id'] != chat_id]
        await update_configs(user_id, 'ftm_gamma_targets', new_targets)

        back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#gamma_target')]]
        await query.message.edit_text(
            f"<b>✅ {to_small_caps('target channel removed successfully')}</b>",
            reply_markup=InlineKeyboardMarkup(back_btn))

    elif callback_data == "ftm#replacer":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        config = await get_configs(user_id)
        replacer_list = config.get('ftm_replacer', [])
        deeplink_replacer_status = config.get('ftm_deeplink_replacer', False)
        deeplink_emoji = '✅' if deeplink_replacer_status else '❌'

        buttons = []
        
        # Add deeplink replacer button at top
        buttons.append([InlineKeyboardButton(f"{deeplink_emoji} 🔗 {to_small_caps('deeplink replacer')}", callback_data='ftm#deeplink_replacer_menu')])
        
        if replacer_list:
            for idx, pair in enumerate(replacer_list):
                buttons.append([InlineKeyboardButton(f"🔄 {pair['old']} → {pair['new']}", callback_data=f"ftm#remove_replacer_{idx}")])

        buttons.append([InlineKeyboardButton('✚ ' + to_small_caps('add word pair'), callback_data='ftm#add_replacer')])
        buttons.append([InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')])

        replacer_text = "\n".join([f"• <code>{p['old']}</code> → <code>{p['new']}</code>" for p in replacer_list]) if replacer_list else to_small_caps("no word pairs added yet")

        await query.message.edit_text(
            f"<b>🌀 {to_small_caps('ftm replacer')} 🌀</b>\n\n"
            f"<b>{to_small_caps('deeplink replacer')}: {deeplink_emoji}</b>\n\n"
            f"<b>{to_small_caps('current word pairs')}:</b>\n{replacer_text}\n\n"
            f"<b>📝 {to_small_caps('what is replacer?')}</b>\n"
            f"<i>{to_small_caps('automatically replace specific words or text in captions.')}</i>\n\n"
            f"<b>✨ {to_small_caps('how to use')}:</b>\n"
            f"• {to_small_caps('click add word pair button')}\n"
            f"• {to_small_caps('send in format')}: <code>old_text|new_text</code>\n"
            f"• {to_small_caps('all occurrences will be replaced')}\n"
            f"• {to_small_caps('click on word pair to remove it')}\n\n"
            f"<b>📌 {to_small_caps('example')}:</b> <code>2024|2025</code>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#add_replacer":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        await query.message.delete()
        try:
            text = await bot.send_message(user_id, f"<b>{to_small_caps('add word replacement pair')}\n\n{to_small_caps('send in format')}: old_word|new_word\n\n/cancel - {to_small_caps('cancel')}</b>")
            from plugins.conversation import listen, is_text_or_cancel
            msg = await listen(bot, user_id, filter_func=is_text_or_cancel, timeout=300)
            if msg is None:
                back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#replacer')]]
                return await text.edit_text(f'<b>⏱️ {to_small_caps("process cancelled")}</b>', reply_markup=InlineKeyboardMarkup(back_btn))
            if msg.text and msg.text.startswith("/cancel"):
                await msg.delete()
                return await text.edit_text(f"<b>❌ {to_small_caps('process cancelled')}</b>")

            if '|' not in msg.text:
                await msg.delete()
                return await text.edit_text(f"<b>❌ {to_small_caps('invalid format. use')}: old_word|new_word</b>")

            old_word, new_word = msg.text.split('|', 1)
            config = await get_configs(user_id)
            replacer_list = config.get('ftm_replacer', [])
            # Create a completely new list to ensure MongoDB detects the change
            new_replacer_list = [dict(item) for item in replacer_list]
            new_replacer_list.append({'old': old_word.strip(), 'new': new_word.strip()})
            await update_configs(user_id, 'ftm_replacer', new_replacer_list)

            await msg.delete()
            back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#replacer')]]
            await text.edit_text(
                f"<b>✅ {to_small_caps('word pair added successfully!')}\n\n"
                f"<code>{old_word.strip()}</code> → <code>{new_word.strip()}</code></b>",
                reply_markup=InlineKeyboardMarkup(back_btn))
        except asyncio.exceptions.TimeoutError:
            back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#replacer')]]
            await text.edit_text(f'<b>⏱️ {to_small_caps("process cancelled")}</b>', reply_markup=InlineKeyboardMarkup(back_btn))

    elif callback_data.startswith("ftm#remove_replacer_"):
        idx = int(callback_data.split('_')[-1])
        config = await get_configs(user_id)
        replacer_list = config.get('ftm_replacer', [])
        if 0 <= idx < len(replacer_list):
            new_replacer_list = [dict(item) for i, item in enumerate(replacer_list) if i != idx]
            await update_configs(user_id, 'ftm_replacer', new_replacer_list)

        back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#replacer')]]
        await query.message.edit_text(
            f"<b>✅ {to_small_caps('word pair removed')}</b>",
            reply_markup=InlineKeyboardMarkup(back_btn))

    elif callback_data == "ftm#deeplink_replacer_menu":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        deeplink_replacer_status = config.get('ftm_deeplink_replacer', False)
        deeplink_url = config.get('ftm_deeplink_url', '')
        deeplink_remover_status = config.get('ftm_deeplink_remover', False)
        
        status_emoji = '✅' if deeplink_replacer_status else '❌'
        url_preview = deeplink_url[:40] + '...' if len(deeplink_url) > 40 else deeplink_url if deeplink_url else to_small_caps('not set')
        
        buttons = [
            [InlineKeyboardButton(f"{status_emoji} {to_small_caps('toggle deeplink replacer')}", callback_data='ftm#toggle_deeplink_replacer')],
            [InlineKeyboardButton(f"🔗 {to_small_caps('set deeplink url')}", callback_data='ftm#set_deeplink_url')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#replacer')]
        ]
        
        warning_text = ""
        if deeplink_remover_status:
            warning_text = f"\n\n⚠️ <b>{to_small_caps('warning')}:</b> <i>{to_small_caps('deeplink remover is enabled! disable it first for deeplink replacer to work.')}</i>"

        await query.message.edit_text(
            f"<b>🔗 {to_small_caps('ftm deeplink replacer')} 🔗</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_emoji}</b>\n"
            f"<b>{to_small_caps('your deeplink')}: </b><code>{url_preview}</code>\n\n"
            f"<b>📝 {to_small_caps('what is deeplink replacer?')}</b>\n"
            f"<i>{to_small_caps('automatically replace all hyperlinks in forwarded messages with your own deeplink.')}</i>\n\n"
            f"<b>✨ {to_small_caps('how it works')}:</b>\n"
            f"• {to_small_caps('set your own deeplink url (e.g. your channel/bot link)')}\n"
            f"• {to_small_caps('enable the mode')}\n"
            f"• {to_small_caps('all clickable text links will point to your deeplink')}\n"
            f"• {to_small_caps('the visible text remains unchanged')}\n\n"
            f"<b>📌 {to_small_caps('example')}:</b>\n"
            f"<i>{to_small_caps('original')}: </i><code>&lt;a href=\"other_link\"&gt;click here&lt;/a&gt;</code>\n"
            f"<i>{to_small_caps('result')}: </i><code>&lt;a href=\"your_link\"&gt;click here&lt;/a&gt;</code>\n\n"
            f"<b>⚠️ {to_small_caps('note')}:</b> <i>{to_small_caps('deeplink remover must be disabled for this to work.')}</i>{warning_text}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#toggle_deeplink_replacer":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        deeplink_url = config.get('ftm_deeplink_url', '')
        
        if not deeplink_url:
            return await query.answer(f"❌ {to_small_caps('please set your deeplink url first!')}", show_alert=True)
        
        current_status = config.get('ftm_deeplink_replacer', False)
        await update_configs(user_id, 'ftm_deeplink_replacer', not current_status)
        
        new_status = not current_status
        
        from plugins.logger import BotLogger
        await BotLogger.log_ftm_mode_toggled(bot, user_id, query.from_user.first_name, 'deeplink_replacer', new_status)
        
        status_text = to_small_caps('enabled') if new_status else to_small_caps('disabled')
        await query.answer(f"🔗 {to_small_caps('deeplink replacer')} {status_text}", show_alert=True)
        
        # Refresh menu
        status_emoji = '✅' if new_status else '❌'
        url_preview = deeplink_url[:40] + '...' if len(deeplink_url) > 40 else deeplink_url
        deeplink_remover_status = config.get('ftm_deeplink_remover', False)
        
        buttons = [
            [InlineKeyboardButton(f"{status_emoji} {to_small_caps('toggle deeplink replacer')}", callback_data='ftm#toggle_deeplink_replacer')],
            [InlineKeyboardButton(f"🔗 {to_small_caps('set deeplink url')}", callback_data='ftm#set_deeplink_url')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#replacer')]
        ]
        
        warning_text = ""
        if deeplink_remover_status:
            warning_text = f"\n\n⚠️ <b>{to_small_caps('warning')}:</b> <i>{to_small_caps('deeplink remover is enabled! disable it first for deeplink replacer to work.')}</i>"

        await query.message.edit_text(
            f"<b>🔗 {to_small_caps('ftm deeplink replacer')} 🔗</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_emoji}</b>\n"
            f"<b>{to_small_caps('your deeplink')}: </b><code>{url_preview}</code>\n\n"
            f"<b>📝 {to_small_caps('what is deeplink replacer?')}</b>\n"
            f"<i>{to_small_caps('automatically replace all hyperlinks in forwarded messages with your own deeplink.')}</i>\n\n"
            f"<b>✨ {to_small_caps('how it works')}:</b>\n"
            f"• {to_small_caps('set your own deeplink url (e.g. your channel/bot link)')}\n"
            f"• {to_small_caps('enable the mode')}\n"
            f"• {to_small_caps('all clickable text links will point to your deeplink')}\n"
            f"• {to_small_caps('the visible text remains unchanged')}\n\n"
            f"<b>📌 {to_small_caps('example')}:</b>\n"
            f"<i>{to_small_caps('original')}: </i><code>&lt;a href=\"other_link\"&gt;click here&lt;/a&gt;</code>\n"
            f"<i>{to_small_caps('result')}: </i><code>&lt;a href=\"your_link\"&gt;click here&lt;/a&gt;</code>\n\n"
            f"<b>⚠️ {to_small_caps('note')}:</b> <i>{to_small_caps('deeplink remover must be disabled for this to work.')}</i>{warning_text}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#set_deeplink_url":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        await query.message.delete()
        try:
            config = await get_configs(user_id)
            current_url = config.get('ftm_deeplink_url', '')
            
            text = await bot.send_message(
                user_id,
                f"<b>🔗 {to_small_caps('set deeplink url')}</b>\n\n"
                f"<b>{to_small_caps('current')}: </b>{current_url if current_url else to_small_caps('not set')}\n\n"
                f"<b>{to_small_caps('send your deeplink url')}:</b>\n"
                f"<i>{to_small_caps('this can be your channel link, bot link, or any url.')}</i>\n\n"
                f"<b>{to_small_caps('examples')}:</b>\n"
                f"• <code>https://t.me/yourchannel</code>\n"
                f"• <code>https://t.me/yourbot?start=ref</code>\n"
                f"• <code>https://yourwebsite.com</code>\n\n"
                f"/cancel - {to_small_caps('cancel')}"
            )
            from plugins.conversation import listen, is_text_or_cancel
            msg = await listen(bot, user_id, filter_func=is_text_or_cancel, timeout=300)
            if msg is None:
                return await text.edit_text(
                    f"<b>⏱️ {to_small_caps('process cancelled')}</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#deeplink_replacer_menu')]])
                )
            if msg.text and msg.text.startswith("/cancel"):
                await msg.delete()
                return await text.edit_text(
                    f"<b>❌ {to_small_caps('cancelled')}</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#deeplink_replacer_menu')]])
                )
            
            new_url = msg.text.strip()
            await update_configs(user_id, 'ftm_deeplink_url', new_url)
            
            await msg.delete()
            await text.edit_text(
                f"<b>✅ {to_small_caps('deeplink url updated!')}</b>\n\n"
                f"<code>{new_url}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#deeplink_replacer_menu')]])
            )
        except asyncio.exceptions.TimeoutError:
            await text.edit_text(
                f"<b>⏱️ {to_small_caps('process cancelled')}</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#deeplink_replacer_menu')]])
            )

    elif callback_data == "ftm#auto_numbering":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        numbering_status = config.get('ftm_auto_numbering', False)
        numbering_style = config.get('ftm_numbering_style', 'dot')
        
        status_emoji = '✅' if numbering_status else '❌'
        
        style_names = {
            'dot': '1. 2. 3.',
            'bracket': '1) 2) 3)',
            'emoji': '1️⃣ 2️⃣ 3️⃣'
        }
        current_style = style_names.get(numbering_style, '1. 2. 3.')
        
        buttons = [
            [InlineKeyboardButton(f"{status_emoji} {to_small_caps('toggle auto numbering')}", callback_data='ftm#toggle_auto_numbering')],
            [InlineKeyboardButton(f"🎨 {to_small_caps('numbering style')}: {current_style}", callback_data='ftm#numbering_style_menu')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]

        await query.message.edit_text(
            f"<b>🔢 {to_small_caps('ftm auto numbering')} 🔢</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_emoji}</b>\n"
            f"<b>{to_small_caps('style')}: </b><code>{current_style}</code>\n\n"
            f"<b>📝 {to_small_caps('what is auto numbering?')}</b>\n"
            f"<i>{to_small_caps('automatically add numbering to every forwarded message.')}</i>\n\n"
            f"<b>✨ {to_small_caps('features')}:</b>\n"
            f"• {to_small_caps('works for text + media captions')}\n"
            f"• {to_small_caps('numbering increases automatically')}:\n"
            f"  <code>1. {to_small_caps('caption text of message')} 1</code>\n"
            f"  <code>2. {to_small_caps('caption text of message')} 2</code>\n"
            f"  <code>3. {to_small_caps('caption text of message')} 3</code>\n"
            f"• {to_small_caps('counter resets for every forwarding process')}\n"
            f"• {to_small_caps('works only for manual forwarding (not gamma mode)')}\n\n"
            f"<b>🎨 {to_small_caps('available styles')}:</b>\n"
            f"• <code>1. 2. 3.</code> - {to_small_caps('dot style')}\n"
            f"• <code>1) 2) 3)</code> - {to_small_caps('bracket style')}\n"
            f"• <code>1️⃣ 2️⃣ 3️⃣</code> - {to_small_caps('emoji style')}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#toggle_auto_numbering":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        current_status = config.get('ftm_auto_numbering', False)
        await update_configs(user_id, 'ftm_auto_numbering', not current_status)
        
        new_status = not current_status
        
        from plugins.logger import BotLogger
        await BotLogger.log_ftm_mode_toggled(bot, user_id, query.from_user.first_name, 'auto_numbering', new_status)
        
        status_text = to_small_caps('enabled') if new_status else to_small_caps('disabled')
        await query.answer(f"🔢 {to_small_caps('auto numbering')} {status_text}", show_alert=True)
        
        # Refresh menu
        status_emoji = '✅' if new_status else '❌'
        numbering_style = config.get('ftm_numbering_style', 'dot')
        
        style_names = {
            'dot': '1. 2. 3.',
            'bracket': '1) 2) 3)',
            'emoji': '1️⃣ 2️⃣ 3️⃣'
        }
        current_style = style_names.get(numbering_style, '1. 2. 3.')
        
        buttons = [
            [InlineKeyboardButton(f"{status_emoji} {to_small_caps('toggle auto numbering')}", callback_data='ftm#toggle_auto_numbering')],
            [InlineKeyboardButton(f"🎨 {to_small_caps('numbering style')}: {current_style}", callback_data='ftm#numbering_style_menu')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]

        await query.message.edit_text(
            f"<b>🔢 {to_small_caps('ftm auto numbering')} 🔢</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_emoji}</b>\n"
            f"<b>{to_small_caps('style')}: </b><code>{current_style}</code>\n\n"
            f"<b>📝 {to_small_caps('what is auto numbering?')}</b>\n"
            f"<i>{to_small_caps('automatically add numbering to every forwarded message.')}</i>\n\n"
            f"<b>✨ {to_small_caps('features')}:</b>\n"
            f"• {to_small_caps('works for text + media captions')}\n"
            f"• {to_small_caps('numbering increases automatically')}:\n"
            f"  <code>1. {to_small_caps('caption text of message')} 1</code>\n"
            f"  <code>2. {to_small_caps('caption text of message')} 2</code>\n"
            f"  <code>3. {to_small_caps('caption text of message')} 3</code>\n"
            f"• {to_small_caps('counter resets for every forwarding process')}\n"
            f"• {to_small_caps('works only for manual forwarding (not gamma mode)')}\n\n"
            f"<b>🎨 {to_small_caps('available styles')}:</b>\n"
            f"• <code>1. 2. 3.</code> - {to_small_caps('dot style')}\n"
            f"• <code>1) 2) 3)</code> - {to_small_caps('bracket style')}\n"
            f"• <code>1️⃣ 2️⃣ 3️⃣</code> - {to_small_caps('emoji style')}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#numbering_style_menu":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        current_style = config.get('ftm_numbering_style', 'dot')
        
        dot_check = '✅' if current_style == 'dot' else '⬜'
        bracket_check = '✅' if current_style == 'bracket' else '⬜'
        emoji_check = '✅' if current_style == 'emoji' else '⬜'
        asterisk_check = '✅' if current_style == 'asterisk' else '⬜'
        dash_check = '✅' if current_style == 'dash' else '⬜'
        
        buttons = [
            [InlineKeyboardButton(f"{dot_check} 1. 2. 3. ({to_small_caps('dot')})", callback_data='ftm#set_numbering_dot')],
            [InlineKeyboardButton(f"{bracket_check} 1) 2) 3) ({to_small_caps('bracket')})", callback_data='ftm#set_numbering_bracket')],
            [InlineKeyboardButton(f"{emoji_check} 1️⃣ 2️⃣ 3️⃣ ({to_small_caps('emoji')})", callback_data='ftm#set_numbering_emoji')],
            [InlineKeyboardButton(f"{asterisk_check} * 1 * 2 ({to_small_caps('asterisk')})", callback_data='ftm#set_numbering_asterisk')],
            [InlineKeyboardButton(f"{dash_check} - 1 - 2 ({to_small_caps('dash')})", callback_data='ftm#set_numbering_dash')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#auto_numbering')]
        ]

        await query.message.edit_text(
            f"<b>🎨 {to_small_caps('select numbering style')} 🎨</b>\n\n"
            f"<b>{to_small_caps('5 numbering styles available')}:</b>\n\n"
            f"<code>1. • 2. • 3.</code> | <code>1) • 2) • 3)</code> | <code>1️⃣ • 2️⃣ • 3️⃣</code> | <code>* 1 • * 2</code> | <code>- 1 • - 2</code>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data.startswith("ftm#set_numbering_"):
        style = callback_data.replace("ftm#set_numbering_", "")
        await update_configs(user_id, 'ftm_numbering_style', style)
        
        style_names = {
            'dot': '1. 2. 3.',
            'bracket': '1) 2) 3)',
            'emoji': '1️⃣ 2️⃣ 3️⃣',
            'asterisk': '* 1 * 2',
            'dash': '- 1 - 2'
        }
        
        await query.answer(f"✅ {to_small_caps('style set to')} {style_names.get(style, style)}", show_alert=True)
        
        # Refresh style menu
        dot_check = '✅' if style == 'dot' else '⬜'
        bracket_check = '✅' if style == 'bracket' else '⬜'
        emoji_check = '✅' if style == 'emoji' else '⬜'
        asterisk_check = '✅' if style == 'asterisk' else '⬜'
        dash_check = '✅' if style == 'dash' else '⬜'
        
        buttons = [
            [InlineKeyboardButton(f"{dot_check} 1. 2. 3. ({to_small_caps('dot')})", callback_data='ftm#set_numbering_dot')],
            [InlineKeyboardButton(f"{bracket_check} 1) 2) 3) ({to_small_caps('bracket')})", callback_data='ftm#set_numbering_bracket')],
            [InlineKeyboardButton(f"{emoji_check} 1️⃣ 2️⃣ 3️⃣ ({to_small_caps('emoji')})", callback_data='ftm#set_numbering_emoji')],
            [InlineKeyboardButton(f"{asterisk_check} * 1 * 2 ({to_small_caps('asterisk')})", callback_data='ftm#set_numbering_asterisk')],
            [InlineKeyboardButton(f"{dash_check} - 1 - 2 ({to_small_caps('dash')})", callback_data='ftm#set_numbering_dash')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#auto_numbering')]
        ]

        await query.message.edit_text(
            f"<b>🎨 {to_small_caps('select numbering style')} 🎨</b>\n\n"
            f"<b>{to_small_caps('5 numbering styles available')}:</b>\n\n"
            f"<code>1. • 2. • 3.</code> | <code>1) • 2) • 3)</code> | <code>1️⃣ • 2️⃣ • 3️⃣</code> | <code>* 1 • * 2</code> | <code>- 1 • - 2</code>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#remover":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        deeplink_status = config.get('ftm_deeplink_remover', False)
        plainlink_status = config.get('ftm_plain_link_remover', False)
        username_status = config.get('ftm_username_remover', False)
        text_count = len(config.get('ftm_remover', []))
        
        # Show link status based on either option being enabled
        link_active = deeplink_status or plainlink_status
        link_emoji = '✅' if link_active else '❌'
        username_emoji = '✅' if username_status else '❌'

        buttons = [
            [InlineKeyboardButton(f"📝 {to_small_caps('text remover')} ({text_count})", callback_data='ftm#text_remover')],
            [InlineKeyboardButton(f"{link_emoji} 🔗 {to_small_caps('link remover')}", callback_data='ftm#link_remover_menu')],
            [InlineKeyboardButton(f"{username_emoji} 👤 {to_small_caps('username remover')}", callback_data='ftm#toggle_username_remover')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]

        await query.message.edit_text(
            f"<b>✂️ {to_small_caps('ftm remover')} ✂️</b>\n\n"
            f"<b>📝 {to_small_caps('what is remover?')}</b>\n"
            f"<i>{to_small_caps('automatically remove unwanted content from captions and filenames.')}</i>\n\n"
            f"<b>✨ {to_small_caps('available options')}:</b>\n"
            f"• <b>{to_small_caps('text remover')}</b> - {to_small_caps('remove specific words/text')}\n"
            f"• <b>{to_small_caps('link remover')}</b> - {to_small_caps('remove deeplinks & plain links')}\n"
            f"• <b>{to_small_caps('username remover')}</b> - {to_small_caps('remove @usernames')}\n\n"
            f"<b>📊 {to_small_caps('current status')}:</b>\n"
            f"• {to_small_caps('text entries')}: <code>{text_count}</code>\n"
            f"• {to_small_caps('link remover')}: {link_emoji}\n"
            f"• {to_small_caps('username remover')}: {username_emoji}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#text_remover":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        config = await get_configs(user_id)
        remover_list = config.get('ftm_remover', [])

        buttons = []
        if remover_list:
            for idx, word in enumerate(remover_list):
                buttons.append([InlineKeyboardButton(f"✂️ {word}", callback_data=f"ftm#remove_remover_{idx}")])

        buttons.append([InlineKeyboardButton('✚ ' + to_small_caps('add text to remove'), callback_data='ftm#add_remover')])
        buttons.append([InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#remover')])

        remover_text = "\n".join([f"• <code>{w}</code>" for w in remover_list]) if remover_list else to_small_caps("no words added yet")

        await query.message.edit_text(
            f"<b>📝 {to_small_caps('ftm text remover')} 📝</b>\n\n"
            f"<b>{to_small_caps('current words to remove')}:</b>\n{remover_text}\n\n"
            f"<b>📝 {to_small_caps('what is text remover?')}</b>\n"
            f"<i>{to_small_caps('automatically remove specific text or words from captions.')}</i>\n\n"
            f"<b>✨ {to_small_caps('how to use')}:</b>\n"
            f"• {to_small_caps('click add text to remove button')}\n"
            f"• {to_small_caps('send the text you want to remove')}\n"
            f"• {to_small_caps('all occurrences will be deleted')}\n"
            f"• {to_small_caps('click on text to remove it from list')}\n\n"
            f"<b>💡 {to_small_caps('smart feature')}:</b>\n"
            f"<i>{to_small_caps('automatically removes text even if it is bold, italic, or any other format!')}</i>\n\n"
            f"<b>📌 {to_small_caps('example')}:</b> {to_small_caps('remove watermarks, ads, unwanted text')}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#add_remover":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        await query.message.delete()
        try:
            text = await bot.send_message(
                user_id, 
                f"<b>📝 {to_small_caps('add text to remove')}</b>\n\n"
                f"{to_small_caps('send the text you want to remove from captions.')}\n\n"
                f"<i>💡 {to_small_caps('just type plain text - it will automatically be removed even if formatted (bold, italic, etc) in the original caption!')}</i>\n\n"
                f"/cancel - {to_small_caps('cancel')}"
            )
            from plugins.conversation import listen, is_text_or_cancel
            msg = await listen(bot, user_id, filter_func=is_text_or_cancel, timeout=300)
            if msg is None:
                back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#text_remover')]]
                return await text.edit_text(f'<b>⏱️ {to_small_caps("process cancelled")}</b>', reply_markup=InlineKeyboardMarkup(back_btn))
            if msg.text and msg.text.startswith("/cancel"):
                await msg.delete()
                return await text.edit_text(f"<b>❌ {to_small_caps('process cancelled')}</b>")

            config = await get_configs(user_id)
            remover_list = config.get('ftm_remover', [])
            # Create a completely new list to ensure MongoDB detects the change
            new_remover_list = [str(item) for item in remover_list]
            new_remover_list.append(msg.text.strip())
            await update_configs(user_id, 'ftm_remover', new_remover_list)

            await msg.delete()
            back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#text_remover')]]
            await text.edit_text(
                f"<b>✅ {to_small_caps('text added to remover list!')}\n\n"
                f"<code>{msg.text.strip()}</code></b>",
                reply_markup=InlineKeyboardMarkup(back_btn))
        except asyncio.exceptions.TimeoutError:
            back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#text_remover')]]
            await text.edit_text(f'<b>⏱️ {to_small_caps("process cancelled")}</b>', reply_markup=InlineKeyboardMarkup(back_btn))

    elif callback_data.startswith("ftm#remove_remover_"):
        idx = int(callback_data.split('_')[-1])
        config = await get_configs(user_id)
        remover_list = config.get('ftm_remover', [])
        if 0 <= idx < len(remover_list):
            new_remover_list = [item for i, item in enumerate(remover_list) if i != idx]
            await update_configs(user_id, 'ftm_remover', new_remover_list)

        back_btn = [[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#text_remover')]]
        await query.message.edit_text(
            f"<b>✅ {to_small_caps('text removed from list')}</b>",
            reply_markup=InlineKeyboardMarkup(back_btn))

    elif callback_data == "ftm#link_remover_menu":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        deeplink_status = config.get('ftm_deeplink_remover', False)
        plainlink_status = config.get('ftm_plain_link_remover', False)
        
        deeplink_emoji = '✅' if deeplink_status else '❌'
        plainlink_emoji = '✅' if plainlink_status else '❌'

        buttons = [
            [InlineKeyboardButton(f"{deeplink_emoji} 🔗 {to_small_caps('deeplink remover')}", callback_data='ftm#toggle_deeplink_remover')],
            [InlineKeyboardButton(f"{plainlink_emoji} 🌐 {to_small_caps('plain link remover')}", callback_data='ftm#toggle_plainlink_remover')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#remover')]
        ]

        await query.message.edit_text(
            f"<b>🔗 {to_small_caps('ftm link remover')} 🔗</b>\n\n"
            f"<b>📝 {to_small_caps('what is link remover?')}</b>\n"
            f"<i>{to_small_caps('remove different types of links from captions.')}</i>\n\n"
            f"<b>✨ {to_small_caps('available options')}:</b>\n\n"
            f"<b>🔗 {to_small_caps('deeplink remover')}:</b>\n"
            f"<i>{to_small_caps('removes hyperlinks (hidden links in text) but keeps the visible text.')}</i>\n"
            f"• {to_small_caps('example')}: <code>&lt;a href=\"url\"&gt;click here&lt;/a&gt;</code> → <code>click here</code>\n"
            f"• {to_small_caps('the link is removed but text remains visible')}\n\n"
            f"<b>🌐 {to_small_caps('plain link remover')}:</b>\n"
            f"<i>{to_small_caps('removes visible plain urls from caption.')}</i>\n"
            f"• {to_small_caps('example')}: <code>https://example.com</code> → {to_small_caps('removed')}\n"
            f"• {to_small_caps('only removes links that are directly visible in text')}\n\n"
            f"<b>📊 {to_small_caps('current status')}:</b>\n"
            f"• {to_small_caps('deeplink remover')}: {deeplink_emoji}\n"
            f"• {to_small_caps('plain link remover')}: {plainlink_emoji}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#toggle_deeplink_remover":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        current_status = config.get('ftm_deeplink_remover', False)
        await update_configs(user_id, 'ftm_deeplink_remover', not current_status)

        new_status = not current_status
        
        # Log FTM deeplink remover toggle
        from plugins.logger import BotLogger
        await BotLogger.log_ftm_mode_toggled(bot, user_id, query.from_user.first_name, 'deeplink_remover', new_status)

        status_text = to_small_caps('enabled') if new_status else to_small_caps('disabled')
        await query.answer(f"🔗 {to_small_caps('deeplink remover')} {status_text}", show_alert=True)
        
        # Refresh the link remover menu
        deeplink_status = new_status
        plainlink_status = config.get('ftm_plain_link_remover', False)
        
        deeplink_emoji = '✅' if deeplink_status else '❌'
        plainlink_emoji = '✅' if plainlink_status else '❌'

        buttons = [
            [InlineKeyboardButton(f"{deeplink_emoji} 🔗 {to_small_caps('deeplink remover')}", callback_data='ftm#toggle_deeplink_remover')],
            [InlineKeyboardButton(f"{plainlink_emoji} 🌐 {to_small_caps('plain link remover')}", callback_data='ftm#toggle_plainlink_remover')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#remover')]
        ]

        await query.message.edit_text(
            f"<b>🔗 {to_small_caps('ftm link remover')} 🔗</b>\n\n"
            f"<b>📝 {to_small_caps('what is link remover?')}</b>\n"
            f"<i>{to_small_caps('remove different types of links from captions.')}</i>\n\n"
            f"<b>✨ {to_small_caps('available options')}:</b>\n\n"
            f"<b>🔗 {to_small_caps('deeplink remover')}:</b>\n"
            f"<i>{to_small_caps('removes hyperlinks (hidden links in text) but keeps the visible text.')}</i>\n"
            f"• {to_small_caps('example')}: <code>&lt;a href=\"url\"&gt;click here&lt;/a&gt;</code> → <code>click here</code>\n"
            f"• {to_small_caps('the link is removed but text remains visible')}\n\n"
            f"<b>🌐 {to_small_caps('plain link remover')}:</b>\n"
            f"<i>{to_small_caps('removes visible plain urls from caption.')}</i>\n"
            f"• {to_small_caps('example')}: <code>https://example.com</code> → {to_small_caps('removed')}\n"
            f"• {to_small_caps('only removes links that are directly visible in text')}\n\n"
            f"<b>📊 {to_small_caps('current status')}:</b>\n"
            f"• {to_small_caps('deeplink remover')}: {deeplink_emoji}\n"
            f"• {to_small_caps('plain link remover')}: {plainlink_emoji}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#toggle_plainlink_remover":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        current_status = config.get('ftm_plain_link_remover', False)
        await update_configs(user_id, 'ftm_plain_link_remover', not current_status)

        new_status = not current_status
        
        # Log FTM plain link remover toggle
        from plugins.logger import BotLogger
        await BotLogger.log_ftm_mode_toggled(bot, user_id, query.from_user.first_name, 'plain_link_remover', new_status)

        status_text = to_small_caps('enabled') if new_status else to_small_caps('disabled')
        await query.answer(f"🌐 {to_small_caps('plain link remover')} {status_text}", show_alert=True)
        
        # Refresh the link remover menu
        deeplink_status = config.get('ftm_deeplink_remover', False)
        plainlink_status = new_status
        
        deeplink_emoji = '✅' if deeplink_status else '❌'
        plainlink_emoji = '✅' if plainlink_status else '❌'

        buttons = [
            [InlineKeyboardButton(f"{deeplink_emoji} 🔗 {to_small_caps('deeplink remover')}", callback_data='ftm#toggle_deeplink_remover')],
            [InlineKeyboardButton(f"{plainlink_emoji} 🌐 {to_small_caps('plain link remover')}", callback_data='ftm#toggle_plainlink_remover')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#remover')]
        ]

        await query.message.edit_text(
            f"<b>🔗 {to_small_caps('ftm link remover')} 🔗</b>\n\n"
            f"<b>📝 {to_small_caps('what is link remover?')}</b>\n"
            f"<i>{to_small_caps('remove different types of links from captions.')}</i>\n\n"
            f"<b>✨ {to_small_caps('available options')}:</b>\n\n"
            f"<b>🔗 {to_small_caps('deeplink remover')}:</b>\n"
            f"<i>{to_small_caps('removes hyperlinks (hidden links in text) but keeps the visible text.')}</i>\n"
            f"• {to_small_caps('example')}: <code>&lt;a href=\"url\"&gt;click here&lt;/a&gt;</code> → <code>click here</code>\n"
            f"• {to_small_caps('the link is removed but text remains visible')}\n\n"
            f"<b>🌐 {to_small_caps('plain link remover')}:</b>\n"
            f"<i>{to_small_caps('removes visible plain urls from caption.')}</i>\n"
            f"• {to_small_caps('example')}: <code>https://example.com</code> → {to_small_caps('removed')}\n"
            f"• {to_small_caps('only removes links that are directly visible in text')}\n\n"
            f"<b>📊 {to_small_caps('current status')}:</b>\n"
            f"• {to_small_caps('deeplink remover')}: {deeplink_emoji}\n"
            f"• {to_small_caps('plain link remover')}: {plainlink_emoji}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#toggle_username_remover":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        current_status = config.get('ftm_username_remover', False)
        await update_configs(user_id, 'ftm_username_remover', not current_status)

        new_status = not current_status
        
        # Log FTM username remover toggle
        from plugins.logger import BotLogger
        await BotLogger.log_ftm_mode_toggled(bot, user_id, query.from_user.first_name, 'username_remover', new_status)

        status_text = to_small_caps('enabled') if new_status else to_small_caps('disabled')
        await query.answer(f"👤 {to_small_caps('username remover')} {status_text}", show_alert=True)
        
        # Refresh the remover menu
        deeplink_status = config.get('ftm_deeplink_remover', False)
        plainlink_status = config.get('ftm_plain_link_remover', False)
        username_status = new_status
        text_count = len(config.get('ftm_remover', []))
        
        link_active = deeplink_status or plainlink_status
        link_emoji = '✅' if link_active else '❌'
        username_emoji = '✅' if username_status else '❌'

        buttons = [
            [InlineKeyboardButton(f"📝 {to_small_caps('text remover')} ({text_count})", callback_data='ftm#text_remover')],
            [InlineKeyboardButton(f"{link_emoji} 🔗 {to_small_caps('link remover')}", callback_data='ftm#link_remover_menu')],
            [InlineKeyboardButton(f"{username_emoji} 👤 {to_small_caps('username remover')}", callback_data='ftm#toggle_username_remover')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]

        await query.message.edit_text(
            f"<b>✂️ {to_small_caps('ftm remover')} ✂️</b>\n\n"
            f"<b>📝 {to_small_caps('what is remover?')}</b>\n"
            f"<i>{to_small_caps('automatically remove unwanted content from captions and filenames.')}</i>\n\n"
            f"<b>✨ {to_small_caps('available options')}:</b>\n"
            f"• <b>{to_small_caps('text remover')}</b> - {to_small_caps('remove specific words/text')}\n"
            f"• <b>{to_small_caps('link remover')}</b> - {to_small_caps('remove deeplinks & plain links')}\n"
            f"• <b>{to_small_caps('username remover')}</b> - {to_small_caps('remove @usernames')}\n\n"
            f"<b>📊 {to_small_caps('current status')}:</b>\n"
            f"• {to_small_caps('text entries')}: <code>{text_count}</code>\n"
            f"• {to_small_caps('link remover')}: {link_emoji}\n"
            f"• {to_small_caps('username remover')}: {username_emoji}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#view_prefix":
        config = await get_configs(user_id)
        prefix = config.get('ftm_prefix', '')
        await query.message.edit_text(
            f"<b>📝 {to_small_caps('ftm prefix')}</b>\n\n"
            f"<code>{prefix if prefix else to_small_caps('not set')}</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]])
        )

    elif callback_data == "ftm#view_suffix":
        config = await get_configs(user_id)
        suffix = config.get('ftm_suffix', '')
        await query.message.edit_text(
            f"<b>📌 {to_small_caps('ftm suffix')}</b>\n\n"
            f"<code>{suffix if suffix else to_small_caps('not set')}</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]])
        )

    elif callback_data == "ftm#prefix":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'watermark')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        await query.message.delete()
        try:
            config = await get_configs(user_id)
            prefix = config.get('ftm_prefix', '')

            text = await bot.send_message(
                user_id,
                f"<b>📝 {to_small_caps('ftm prefix')}</b>\n\n"
                f"<b>{to_small_caps('current')}: </b>{prefix if prefix else to_small_caps('not set')}\n\n"
                f"<b>{to_small_caps('send the text to add at the start of all messages')}. {to_small_caps('supports html formatting')}.</b>\n\n"
                f"/cancel - {to_small_caps('cancel')}\n"
                f"/clear - {to_small_caps('remove prefix')}"
            )
            from plugins.conversation import listen, is_text_or_cancel
            msg = await listen(bot, user_id, filter_func=is_text_or_cancel, timeout=300)
            if msg is None:
                return await text.edit_text(f"<b>⏱️ {to_small_caps('cancelled')}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]]))
            if msg.text and msg.text.startswith("/cancel"):
                await msg.delete()
                return await text.edit_text(f"<b>❌ {to_small_caps('cancelled')}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]]))
            if msg.text and msg.text.strip().lower() in {"/clear", "clear", "/remove", "remove"}:
                await update_configs(user_id, 'ftm_prefix', '')
                await msg.delete()
                return await text.edit_text(
                    f"<b>✅ {to_small_caps('prefix cleared!')}</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]])
                )

            await update_configs(user_id, 'ftm_prefix', msg.text)
            await msg.delete()
            await text.edit_text(
                f"<b>✅ {to_small_caps('prefix updated!')}</b>\n\n{msg.text[:100]}...",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]])
            )
        except asyncio.exceptions.TimeoutError:
            await text.edit_text(f"<b>⏱️ {to_small_caps('cancelled')}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]]))

    elif callback_data == "ftm#suffix":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'watermark')
        if not has_permission:
            return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        await query.message.delete()
        try:
            config = await get_configs(user_id)
            suffix = config.get('ftm_suffix', '')

            text = await bot.send_message(
                user_id,
                f"<b>📌 {to_small_caps('ftm suffix')}</b>\n\n"
                f"<b>{to_small_caps('current')}: </b>{suffix if suffix else to_small_caps('not set')}\n\n"
                f"<b>{to_small_caps('send the text to add at the end of all messages')}. {to_small_caps('supports html formatting')}.</b>\n\n"
                f"/cancel - {to_small_caps('cancel')}\n"
                f"/clear - {to_small_caps('remove suffix')}"
            )
            from plugins.conversation import listen, is_text_or_cancel
            msg = await listen(bot, user_id, filter_func=is_text_or_cancel, timeout=300)
            if msg is None:
                return await text.edit_text(f"<b>⏱️ {to_small_caps('cancelled')}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]]))
            if msg.text and msg.text.startswith("/cancel"):
                await msg.delete()
                return await text.edit_text(f"<b>❌ {to_small_caps('cancelled')}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]]))
            if msg.text and msg.text.strip().lower() in {"/clear", "clear", "/remove", "remove"}:
                await update_configs(user_id, 'ftm_suffix', '')
                await msg.delete()
                return await text.edit_text(
                    f"<b>✅ {to_small_caps('suffix cleared!')}</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]])
                )

            await update_configs(user_id, 'ftm_suffix', msg.text)
            await msg.delete()
            await text.edit_text(
                f"<b>✅ {to_small_caps('suffix updated!')}</b>\n\n{msg.text[:100]}...",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]])
            )
        except asyncio.exceptions.TimeoutError:
            await text.edit_text(f"<b>⏱️ {to_small_caps('cancelled')}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]]))

    elif callback_data == "ftm#captions":
        await query.message.delete()
        try:
            config = await get_configs(user_id)
            custom_caption = config.get('caption', '')

            text = await bot.send_message(
                user_id,
                f"<b>✏️ {to_small_caps('custom caption')} ✏️</b>\n\n"
                f"<b>{to_small_caps('current caption')}: </b>\n<code>{custom_caption if custom_caption else to_small_caps('not set')}</code>\n\n"
                f"<b>📝 {to_small_caps('custom caption settings')}</b>\n"
                f"<i>{to_small_caps('you can set a custom caption template for videos, documents, audio files, and photos.')}</i>\n\n"
                f"<b>🎯 {to_small_caps('available variables')}:</b>\n"
                f"• <code>{{filename}}</code> - {to_small_caps('file name')}\n"
                f"• <code>{{size}}</code> - {to_small_caps('file size')}\n"
                f"• <code>{{caption}}</code> - {to_small_caps('original caption')}\n"
                f"• <code>{{year}}</code> - {to_small_caps('file year extracted from name')}\n"
                f"• <code>{{language}}</code> - {to_small_caps('audio languages detected')}\n"
                f"• <code>{{quality}}</code> - {to_small_caps('video quality')} (480p, 720p, 1080p, {to_small_caps('etc')})\n"
                f"• <code>{{type}}</code> - {to_small_caps('media type')} ({to_small_caps('video, audio, document, photo')})\n\n"
                f"<b>⚠️ {to_small_caps('note')}:</b> <i>{to_small_caps('variables work on videos, audio, documents, and photos. html tags are supported in the template.')}</i>\n\n"
                f"<b>🎨 {to_small_caps('html formatting')}:</b>\n"
                f"• <code>&lt;b&gt;{to_small_caps('bold')}&lt;/b&gt;</code>\n"
                f"• <code>&lt;i&gt;{to_small_caps('italic')}&lt;/i&gt;</code>\n"
                f"• <code>&lt;u&gt;{to_small_caps('underline')}&lt;/u&gt;</code>\n"
                f"• <code>&lt;s&gt;{to_small_caps('strike')}&lt;/s&gt;</code>\n"
                f"• <code>&lt;code&gt;{to_small_caps('monospace')}&lt;/code&gt;</code>\n"
                f"• <code>&lt;spoiler&gt;{to_small_caps('spoiler')}&lt;/spoiler&gt;</code>\n"
                f"• <code>&lt;a href='url'&gt;{to_small_caps('link text')}&lt;/a&gt;</code>\n\n"
                f"<b>📌 {to_small_caps('example caption')}:</b>\n"
                f"<code>&lt;b&gt;{{filename}}&lt;/b&gt;\n"
                f"📊 {to_small_caps('size')}: {{size}}\n"
                f"🎬 {to_small_caps('quality')}: {{quality}}\n"
                f"📅 {to_small_caps('year')}: {{year}}\n"
                f"🗣️ {to_small_caps('language')}: {{language}}</code>\n\n"
                f"<b>💬 {to_small_caps('send your custom caption template now')}:</b>\n"
                f"/cancel - {to_small_caps('cancel')}"
            )
            from plugins.conversation import listen, is_text_or_cancel
            msg = await listen(bot, user_id, filter_func=is_text_or_cancel, timeout=300)
            if msg is None:
                return await text.edit_text(f"<b>⏱️ {to_small_caps('cancelled')}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]]))
            if msg.text and msg.text.startswith("/cancel"):
                await msg.delete()
                return await text.edit_text(f"<b>❌ {to_small_caps('cancelled')}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]]))

            try:
                msg.text.format(filename='', size='', caption='', year='', language='', quality='', type='')
            except KeyError as e:
                await msg.delete()
                return await text.edit_text(f"<b>❌ {to_small_caps('invalid variable')}: {e}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#captions')]]))

            await update_configs(user_id, 'caption', msg.text)
            await msg.delete()
            await text.edit_text(
                f"<b>✅ {to_small_caps('caption updated!')}</b>\n\n{msg.text[:100]}...",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]])
            )
        except asyncio.exceptions.TimeoutError:
            await text.edit_text(f"<b>⏱️ {to_small_caps('cancelled')}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#watermark')]]))


    elif callback_data == "ftm#clear_prefix":
        await update_configs(user_id, 'ftm_prefix', '')
        await query.answer(to_small_caps('prefix cleared successfully!'), show_alert=True)

        buttons = [
            [
                InlineKeyboardButton('📝 ' + to_small_caps('ftm prefix'), callback_data='ftm#prefix'),
                InlineKeyboardButton('👁️ ' + to_small_caps('view'), callback_data='ftm#view_prefix')
            ],
            [
                InlineKeyboardButton('📌 ' + to_small_caps('ftm suffix'), callback_data='ftm#suffix'),
                InlineKeyboardButton('👁️ ' + to_small_caps('view'), callback_data='ftm#view_suffix')
            ],
            [
                InlineKeyboardButton('🗑️ ' + to_small_caps('clear prefix'), callback_data='ftm#clear_prefix'),
                InlineKeyboardButton('🗑️ ' + to_small_caps('clear suffix'), callback_data='ftm#clear_suffix')
            ],
            [InlineKeyboardButton('✏️ ' + to_small_caps('ftm captions'), callback_data='ftm#captions')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]

        await query.message.edit_text(
            f"<b>💧 {to_small_caps('ftm watermark')}</b>\n\n"
            f"<b>{to_small_caps('prefix')}: </b><code>{to_small_caps('not set')}</code>\n"
            f"<b>{to_small_caps('suffix')}: </b><code>{to_small_caps('not set')}</code>\n\n"
            f"<i>{to_small_caps('add custom prefix and suffix to all forwarded messages. prefix appears at the start and suffix at the end.')}</i>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#clear_suffix":
        await update_configs(user_id, 'ftm_suffix', '')
        await query.answer(to_small_caps('suffix cleared successfully!'), show_alert=True)

        buttons = [
            [
                InlineKeyboardButton('📝 ' + to_small_caps('ftm prefix'), callback_data='ftm#prefix'),
                InlineKeyboardButton('👁️ ' + to_small_caps('view'), callback_data='ftm#view_prefix')
            ],
            [
                InlineKeyboardButton('📌 ' + to_small_caps('ftm suffix'), callback_data='ftm#suffix'),
                InlineKeyboardButton('👁️ ' + to_small_caps('view'), callback_data='ftm#view_suffix')
            ],
            [
                InlineKeyboardButton('🗑️ ' + to_small_caps('clear prefix'), callback_data='ftm#clear_prefix'),
                InlineKeyboardButton('🗑️ ' + to_small_caps('clear suffix'), callback_data='ftm#clear_suffix')
            ],
            [InlineKeyboardButton('✏️ ' + to_small_caps('ftm captions'), callback_data='ftm#captions')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]

        config = await get_configs(user_id)
        prefix = config.get('ftm_prefix', '')
        prefix_preview = prefix[:30] + '...' if len(prefix) > 30 else prefix if prefix else to_small_caps('not set')

        await query.message.edit_text(
            f"<b>💧 {to_small_caps('ftm watermark')}</b>\n\n"
            f"<b>{to_small_caps('prefix')}: </b><code>{prefix_preview}</code>\n"
            f"<b>{to_small_caps('suffix')}: </b><code>{to_small_caps('not set')}</code>\n\n"
            f"<i>{to_small_caps('add custom prefix and suffix to all forwarded messages. prefix appears at the start and suffix at the end.')}</i>",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif callback_data == "ftm#bullets":
        from .subscription import require_ftm
        # Bullets fall under 'replacements' capability
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            # Check if it's just 'watermark' capability needed instead, 
            # as bullets are often considered part of watermark features in some plans
            has_permission, error_message = await require_ftm(user_id, 'watermark')
            if not has_permission:
                return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        bullets_status = config.get('ftm_bullets_enabled', False)
        bullet_style = config.get('ftm_bullet_style', 'style1')
        
        status_emoji = '✅' if bullets_status else '❌'
        
        style_emojis = {'style1': '🚀', 'style2': '🔥', 'style3': '📌', 'style4': '⭐', 'style5': '💫', 'style6': '✨'}
        current_emoji = style_emojis.get(bullet_style, '🚀')
        
        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle bullets'), callback_data='ftm#toggle_bullets')],
            [InlineKeyboardButton(f"🎨 {to_small_caps('bullet style')}: {current_emoji}", callback_data='ftm#bullet_style_menu')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        
        await query.message.edit_text(
            f"<b>💬 {to_small_caps('ftm bullets')} 💬</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_emoji}</b>\n\n"
            f"<b>📝 {to_small_caps('what is bullets?')}</b>\n"
            f"<i>{to_small_caps('add emoji bullet prefix to every forwarded message.')}</i>\n\n"
            f"<b>✨ {to_small_caps('6 bullet styles available')}:</b>\n"
            f"🚀 {to_small_caps('rocket')} | 🔥 {to_small_caps('fire')} | 📌 {to_small_caps('pin')} | ⭐ {to_small_caps('star')} | 💫 {to_small_caps('spark')} | ✨ {to_small_caps('shine')}\n\n"
            f"<b>💡 {to_small_caps('note')}:</b> {to_small_caps('bullets first, then numbering if both enabled')}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif callback_data == "ftm#bullet_style_menu":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            has_permission, error_message = await require_ftm(user_id, 'watermark')
            if not has_permission:
                return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        current_style = config.get('ftm_bullet_style', 'style1')
        
        style1_check = '✅' if current_style == 'style1' else '⬜'
        style2_check = '✅' if current_style == 'style2' else '⬜'
        style3_check = '✅' if current_style == 'style3' else '⬜'
        style4_check = '✅' if current_style == 'style4' else '⬜'
        style5_check = '✅' if current_style == 'style5' else '⬜'
        style6_check = '✅' if current_style == 'style6' else '⬜'
        
        buttons = [
            [InlineKeyboardButton(f"{style1_check} 🚀 {to_small_caps('rocket')}", callback_data='ftm#set_bullet_style1')],
            [InlineKeyboardButton(f"{style2_check} 🔥 {to_small_caps('fire')}", callback_data='ftm#set_bullet_style2')],
            [InlineKeyboardButton(f"{style3_check} 📌 {to_small_caps('pin')}", callback_data='ftm#set_bullet_style3')],
            [InlineKeyboardButton(f"{style4_check} ⭐ {to_small_caps('star')}", callback_data='ftm#set_bullet_style4')],
            [InlineKeyboardButton(f"{style5_check} 💫 {to_small_caps('spark')}", callback_data='ftm#set_bullet_style5')],
            [InlineKeyboardButton(f"{style6_check} ✨ {to_small_caps('shine')}", callback_data='ftm#set_bullet_style6')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#bullets')]
        ]

        await query.message.edit_text(
            f"<b>🎨 {to_small_caps('select bullet style')} 🎨</b>\n\n"
            f"<b>{to_small_caps('choose your bullet emoji')}:</b>\n\n"
            f"🚀 • 🔥 • 📌 • ⭐ • 💫 • ✨",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif callback_data == "ftm#toggle_bullets":
        from .subscription import require_ftm
        # Bullets fall under 'replacements' capability
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            # Check if it's just 'watermark' capability needed instead
            has_permission, error_message = await require_ftm(user_id, 'watermark')
            if not has_permission:
                return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        config = await get_configs(user_id)
        current_status = config.get('ftm_bullets_enabled', False)
        await update_configs(user_id, 'ftm_bullets_enabled', not current_status)
        new_status = not current_status
        status_text = to_small_caps('enabled') if new_status else to_small_caps('disabled')
        await query.answer(f"💬 {to_small_caps('bullets')} {status_text}", show_alert=True)
        
        # Refresh the bullets menu to show updated status
        bullet_style = config.get('ftm_bullet_style', 'style1')
        status_emoji = '✅' if new_status else '❌'
        style_emojis = {'style1': '🚀', 'style2': '🔥', 'style3': '📌', 'style4': '⭐', 'style5': '💫', 'style6': '✨'}
        current_emoji = style_emojis.get(bullet_style, '🚀')
        
        buttons = [
            [InlineKeyboardButton(f'{status_emoji} ' + to_small_caps('toggle bullets'), callback_data='ftm#toggle_bullets')],
            [InlineKeyboardButton(f"🎨 {to_small_caps('bullet style')}: {current_emoji}", callback_data='ftm#bullet_style_menu')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#main')]
        ]
        
        await query.message.edit_text(
            f"<b>💬 {to_small_caps('ftm bullets')} 💬</b>\n\n"
            f"<b>{to_small_caps('status')}: {status_emoji}</b>\n\n"
            f"<b>📝 {to_small_caps('what is bullets?')}</b>\n"
            f"<i>{to_small_caps('add emoji bullet prefix to every forwarded message.')}</i>\n\n"
            f"<b>✨ {to_small_caps('6 bullet styles available')}:</b>\n"
            f"🚀 {to_small_caps('rocket')} | 🔥 {to_small_caps('fire')} | 📌 {to_small_caps('pin')} | ⭐ {to_small_caps('star')} | 💫 {to_small_caps('spark')} | ✨ {to_small_caps('shine')}\n\n"
            f"<b>💡 {to_small_caps('note')}:</b> {to_small_caps('bullets first, then numbering if both enabled')}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif callback_data.startswith("ftm#set_bullet_style"):
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        if not has_permission:
            has_permission, error_message = await require_ftm(user_id, 'watermark')
            if not has_permission:
                return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)
        
        style = callback_data.replace("ftm#set_bullet_style", "")
        await update_configs(user_id, 'ftm_bullet_style', f'style{style}')
        
        style_emojis = {'1': '🚀', '2': '🔥', '3': '📌', '4': '⭐', '5': '💫', '6': '✨'}
        await query.answer(f"✅ {style_emojis.get(style, '🚀')} {to_small_caps('bullet selected')}", show_alert=True)
        
        # Refresh style menu
        current_style = f'style{style}'
        style1_check = '✅' if current_style == 'style1' else '⬜'
        style2_check = '✅' if current_style == 'style2' else '⬜'
        style3_check = '✅' if current_style == 'style3' else '⬜'
        style4_check = '✅' if current_style == 'style4' else '⬜'
        style5_check = '✅' if current_style == 'style5' else '⬜'
        style6_check = '✅' if current_style == 'style6' else '⬜'
        
        buttons = [
            [InlineKeyboardButton(f"{style1_check} 🚀 {to_small_caps('rocket')}", callback_data='ftm#set_bullet_style1')],
            [InlineKeyboardButton(f"{style2_check} 🔥 {to_small_caps('fire')}", callback_data='ftm#set_bullet_style2')],
            [InlineKeyboardButton(f"{style3_check} 📌 {to_small_caps('pin')}", callback_data='ftm#set_bullet_style3')],
            [InlineKeyboardButton(f"{style4_check} ⭐ {to_small_caps('star')}", callback_data='ftm#set_bullet_style4')],
            [InlineKeyboardButton(f"{style5_check} 💫 {to_small_caps('spark')}", callback_data='ftm#set_bullet_style5')],
            [InlineKeyboardButton(f"{style6_check} ✨ {to_small_caps('shine')}", callback_data='ftm#set_bullet_style6')],
            [InlineKeyboardButton(to_small_caps('↩ back'), callback_data='ftm#bullets')]
        ]

        await query.message.edit_text(
            f"<b>🎨 {to_small_caps('select bullet style')} 🎨</b>\n\n"
            f"<b>{to_small_caps('choose your bullet emoji')}:</b>\n\n"
            f"🚀 • 🔥 • 📌 • ⭐ • 💫 • ✨",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif callback_data == "ftm#locked_bullets":
        from .subscription import require_ftm
        has_permission, error_message = await require_ftm(user_id, 'replacements')
        return await query.answer(error_message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''), show_alert=True)

# Dictionary to store running gamma mode clients with session info
# Structure: {user_id: {'client': client_obj, 'session_hash': hash_of_session, 'handler_group': int}}
gamma_clients = {}

async def retry_gamma_monitoring(user_id, wait_time):
    """Retry gamma monitoring after flood wait period"""
    await asyncio.sleep(wait_time)
    await start_gamma_monitoring(user_id)

async def start_gamma_monitoring(user_id):
    """Start gamma mode monitoring for a user"""
    from plugins.test import start_clone_bot, CLIENT
    from pyrogram import filters
    from pyrogram.handlers import MessageHandler
    
    try:
        _bot = await db.get_bot(user_id)
        if not _bot:
            logging.info(f"[GAMMA] No bot found for user {user_id}")
            return False
            
        config = await get_configs(user_id)
        if not config.get('ftm_gamma_mode', False):
            logging.info(f"[GAMMA] Gamma mode not enabled for user {user_id}")
            return False
            
        gamma_sources = config.get('ftm_gamma_sources', [])
        gamma_targets = config.get('ftm_gamma_targets', [])
        
        if not gamma_sources:
            logging.info(f"[GAMMA] No gamma sources for user {user_id}")
            return False
            
        if not gamma_targets:
            logging.info(f"[GAMMA] No gamma targets for user {user_id}")
            return False
        
        # Stop existing client if any
        if user_id in gamma_clients:
            await stop_gamma_monitoring(user_id)
        
        # Create and start the client
        try:
            bot_client = await start_clone_bot(CLIENT().client(_bot))
        except Exception as e:
            logging.error(f"[GAMMA] Failed to start client for user {user_id}: {e}")
            return False
        
        # Get source channel IDs for filtering
        source_chat_ids = [source['chat_id'] for source in gamma_sources]
        
        # Create message handler for gamma forwarding
        async def gamma_message_handler(client, message):
            try:
                # Get fresh config for each message
                user_config = await get_configs(user_id)
                if not user_config.get('ftm_gamma_mode', False):
                    return
                
                targets = user_config.get('ftm_gamma_targets', [])
                if not targets:
                    return
                
                # Apply FTM filters if enabled
                processed_message = message
                
                # Check if FTM delta mode is enabled (caption/text modifications)
                if user_config.get('ftm_delta_mode', False):
                    # Apply text replacements if configured
                    replacements = user_config.get('ftm_replacements', [])
                    if replacements and (message.text or message.caption):
                        text = message.text or message.caption or ""
                        for rep in replacements:
                            if 'find' in rep and 'replace' in rep:
                                text = text.replace(rep['find'], rep['replace'])
                
                # Check message type filters (for gamma/auto mode)
                from plugins.ftm_manager import check_message_filters
                if not await check_message_filters(message, user_id):
                    # Update last msg id even if filtered to skip it on restart
                    if user_config.get('ftm_alpha_mode', False):
                        await db.update_gamma_last_msg(user_id, message.chat.id, message.id)
                    return

                # Apply Theta Mode filter if enabled
                if user_config.get('ftm_theta_mode', False):
                    has_image = message.photo is not None
                    has_caption = bool(message.caption)
                    if not (has_image and has_caption):
                        # Update last msg id even if filtered
                        if user_config.get('ftm_alpha_mode', False):
                            await db.update_gamma_last_msg(user_id, message.chat.id, message.id)
                        return

                # Forward to all target channels
                forwarded_successfully = False
                
                # Apply FTM transformations if enabled
                from .ftm_manager import apply_ftm_transformations
                caption = message.caption.html if message.caption else ""
                if message.text:
                    caption = message.text.html
                
                # We need a counter for numbering if enabled
                # For gamma mode, we use the processed count from DB
                gamma_state = await db.get_forwarding_state(user_id, 'gamma')
                numbering_counter = gamma_state.get('processed', 0) + 1 if gamma_state else 1
                
                new_caption = await apply_ftm_transformations(
                    caption, user_id, message.chat.id, message.id, numbering_counter
                )

                for target in targets:
                    try:
                        target_chat_id = target['chat_id']
                        
                        # Copy the message to target channel with new caption
                        await client.copy_message(
                            chat_id=target_chat_id,
                            from_chat_id=message.chat.id,
                            message_id=message.id,
                            caption=new_caption,
                            reply_markup=message.reply_markup, # Keep original buttons or use custom?
                            parse_mode=enums.ParseMode.HTML,
                            message_thread_id=target.get('thread_id')
                        )
                        forwarded_successfully = True
                        
                    except FloodWait as fw:
                        logging.info(f"[GAMMA] FloodWait {fw.value if hasattr(fw, 'value') else getattr(fw, 'x', 10)}s for user {user_id}")
                        await asyncio.sleep(fw.value if hasattr(fw, 'value') else getattr(fw, 'x', 10))
                        # Retry after flood wait
                        try:
                            await client.copy_message(
                                chat_id=target['chat_id'],
                                from_chat_id=message.chat.id,
                                message_id=message.id,
                                caption=new_caption,
                                reply_markup=message.reply_markup,
                                parse_mode=enums.ParseMode.HTML,
                                message_thread_id=target.get('thread_id')
                            )
                            forwarded_successfully = True
                        except Exception as retry_e:
                            logging.error(f"[GAMMA] Retry failed for user {user_id}: {retry_e}")
                    except Exception as target_e:
                        target_chat_id_log = target.get('chat_id')
                        logging.error(f"[GAMMA] Failed to forward to target {target.get('title', target_chat_id_log)} for user {user_id}: {target_e}")
                # FTM Alpha - Save last message ID per source after successful forward
                if forwarded_successfully and user_config.get('ftm_alpha_mode', False):
                    try:
                        await db.update_gamma_last_msg(user_id, message.chat.id, message.id)
                    except Exception as alpha_e:
                        logging.error(f"[GAMMA] Failed to save last msg id: {alpha_e}")
            except Exception as handler_e:
                logging.error(f"[GAMMA] Handler error for user {user_id}: {handler_e}")
        # Create filter for source channels
        source_filter = filters.chat(source_chat_ids) & ~filters.service
        
        # Generate unique handler group for this user
        handler_group = hash(f"gamma_{user_id}") % 100000
        
        # Add the handler
        bot_client.add_handler(
            MessageHandler(gamma_message_handler, source_filter),
            group=handler_group
        )
        
        # Store client info
        session_hash = hash(_bot.get('session', _bot.get('token', '')))
        gamma_clients[user_id] = {
            'client': bot_client,
            'session_hash': session_hash,
            'handler_group': handler_group
        }
        
        # FTM Alpha Mode - Save gamma running state and catch up missed messages
        user_config = await get_configs(user_id)
        if user_config.get('ftm_alpha_mode', False):
            # Get previously saved last message IDs
            last_msg_ids = await db.get_gamma_last_msgs(user_id)
            
            # Save current state
            await db.save_gamma_state(
                user_id,
                source_chat_ids,
                [t['chat_id'] for t in gamma_targets],
                last_msg_ids
            )
            
            # Catch up missed messages for each source
            if last_msg_ids:
                asyncio.create_task(
                    gamma_catchup_missed_messages(
                        bot_client, user_id, source_chat_ids, 
                        gamma_targets, last_msg_ids
                    )
                )
        
        logging.info(f"[GAMMA] Started monitoring for user {user_id} with {len(source_chat_ids)} sources and {len(gamma_targets)} targets")
        return True
        
    except Exception as e:
        logging.error(f"[GAMMA] Error starting monitoring for user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

async def stop_gamma_monitoring(user_id):
    """Stop gamma mode monitoring for a user"""
    if user_id in gamma_clients:
        try:
            client_data = gamma_clients[user_id]
            client = client_data.get('client') if isinstance(client_data, dict) else client_data
            if client:
                # Remove handler if we stored the group
                handler_group = client_data.get('handler_group') if isinstance(client_data, dict) else None
                if handler_group is not None:
                    try:
                        # Clear handlers from this group
                        if hasattr(client, 'dispatcher') and hasattr(client.dispatcher, 'groups'):
                            if handler_group in client.dispatcher.groups:
                                client.dispatcher.groups[handler_group].clear()
                    except Exception as handler_e:
                        logging.error(f"[GAMMA] Error removing handler: {handler_e}")
                # Stop the client
                if hasattr(client, 'stop'):
                    await client.stop()
            
            del gamma_clients[user_id]
            
            # FTM Alpha Mode - Cancel gamma state when stopped manually
            try:
                user_config = await get_configs(user_id)
                if user_config.get('ftm_alpha_mode', False):
                    await db.cancel_forwarding_state(user_id, 'gamma')
            except Exception as state_e:
                logging.error(f"[GAMMA] Error canceling alpha state: {state_e}")
            logging.info(f"[GAMMA] Stopped monitoring for user {user_id}")
        except Exception as e:
            logging.error(f"[GAMMA] Error stopping: {e}")
            if user_id in gamma_clients:
                del gamma_clients[user_id]

async def get_gamma_status(user_id):
    """Get gamma status for a user"""
    status = {
        'is_running': user_id in gamma_clients,
        'is_connected': False,
        'session_hash': None
    }
    if user_id in gamma_clients:
        client_data = gamma_clients[user_id]
        client = client_data.get('client') if isinstance(client_data, dict) else None
        if client:
            status['is_connected'] = client.is_connected if hasattr(client, 'is_connected') else False
            status['session_hash'] = client_data.get('session_hash') if isinstance(client_data, dict) else None
    return status


async def gamma_catchup_missed_messages(client, user_id, source_chat_ids, targets, last_msg_ids):
    """
    FTM Alpha Mode - Catch up missed messages in gamma mode after bot restart.
    Fetches and forwards all messages that arrived since last_msg_id for each source.
    """
    try:
        from database import db
        
        total_missed = 0
        total_forwarded = 0
        
        for source_id in source_chat_ids:
            source_key = str(source_id)
            last_msg_id = last_msg_ids.get(source_key, 0)
            
            if not last_msg_id:
                continue
            
            try:
                # Count and forward missed messages
                missed_count = 0
                
                # Get messages newer than last_msg_id
                async for message in client.get_chat_history(source_id, limit=500):
                    if message.id <= last_msg_id:
                        break
                    
                    if message.empty or message.service:
                        # Update last msg id even for service messages to skip them
                        await db.update_gamma_last_msg(user_id, source_id, message.id)
                        continue
                    
                    # Apply filters during catch-up
                    if not await check_message_filters(message, user_id):
                        await db.update_gamma_last_msg(user_id, source_id, message.id)
                        continue
                    
                    user_config = await get_configs(user_id)
                    if user_config.get('ftm_theta_mode', False):
                        if not (message.photo and message.caption):
                            await db.update_gamma_last_msg(user_id, source_id, message.id)
                            continue

                    missed_count += 1
                    total_missed += 1
                    
                    # Prepare caption
                    caption = message.caption.html if message.caption else ""
                    if message.text:
                        caption = message.text.html
                    
                    # numbering counter
                    gamma_state = await db.get_forwarding_state(user_id, 'gamma')
                    numbering_counter = gamma_state.get('processed', 0) + 1 if gamma_state else 1

                    new_caption = await apply_ftm_transformations(
                        caption, user_id, source_id, message.id, numbering_counter
                    )

                    # Forward to all targets
                    for target in targets:
                        try:
                            target_chat_id = target['chat_id']
                            await client.copy_message(
                                chat_id=target_chat_id,
                                from_chat_id=source_id,
                                message_id=message.id,
                                caption=new_caption,
                                parse_mode=enums.ParseMode.HTML,
                                message_thread_id=target.get('thread_id')
                            )
                            total_forwarded += 1
                        except FloodWait as fw:
                            await asyncio.sleep(fw.value if hasattr(fw, 'value') else getattr(fw, 'x', 10))
                            try:
                                await client.copy_message(
                                    chat_id=target['chat_id'],
                                    from_chat_id=source_id,
                                    message_id=message.id,
                                    caption=new_caption,
                                    parse_mode=enums.ParseMode.HTML,
                                    message_thread_id=target.get('thread_id')
                                )
                                total_forwarded += 1
                            except Exception:
                                pass
                        except Exception as target_e:
                            logging.error(f"[GAMMA CATCHUP] Failed to forward to target: {target_e}")
                    # Update last message ID
                    await db.update_gamma_last_msg(user_id, source_id, message.id)
                    
                    await asyncio.sleep(1)  # Rate limiting
                
                if missed_count > 0:
                    logging.info(f"[GAMMA CATCHUP] User {user_id}: Forwarded {missed_count} missed messages from source {source_id}")
            except Exception as source_e:
                logging.error(f"[GAMMA CATCHUP] Error processing source {source_id}: {source_e}")
        # Notify user about catch-up if any messages were forwarded
        if total_missed > 0:
            try:
                await client.send_message(
                    user_id,
                    f"<b>🧬 ғᴛᴍ ᴀʟᴘʜᴀ ᴍᴏᴅᴇ - ɢᴀᴍᴍᴀ ᴄᴀᴛᴄʜ-ᴜᴘ 🧬</b>\n\n"
                    f"✨ <b>ᴍɪssᴇᴅ ᴍᴇssᴀɢᴇs ᴅᴇᴛᴇᴄᴛᴇᴅ!</b>\n\n"
                    f"📊 <b>ᴛᴏᴛᴀʟ ᴍɪssᴇᴅ:</b> {total_missed}\n"
                    f"✅ <b>ᴀᴜᴛᴏ-ғᴏʀᴡᴀʀᴅᴇᴅ:</b> {total_forwarded}\n\n"
                    f"<i>🔄 ᴀʟʟ ᴍɪssᴇᴅ ᴍᴇssᴀɢᴇs ғʀᴏᴍ sᴏᴜʀᴄᴇ ᴄʜᴀɴɴᴇʟs ʜᴀᴠᴇ ʙᴇᴇɴ ғᴏʀᴡᴀʀᴅᴇᴅ!</i>\n\n"
                    f"<b>⚡ ᴘᴏᴡᴇʀᴇᴅ ʙʏ <a href=https://t.me/ftmbotzx>ғᴛᴍʙᴏᴛᴢx</a></b>"
                )
            except Exception as notify_e:
                logging.error(f"[GAMMA CATCHUP] Failed to notify user: {notify_e}")
    except Exception as e:
        logging.error(f"[GAMMA CATCHUP] Error for user {user_id}: {e}")
        import traceback
        traceback.print_exc()
