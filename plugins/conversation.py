import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from typing import Optional, Dict, Callable

pending_conversations: Dict[int, dict] = {}

async def listen(
    client: Client,
    chat_id: int,
    filter_func: Optional[Callable[[Message], bool]] = None,
    timeout: int = 300
) -> Optional[Message]:
    """
    Wait for a message from a specific chat.
    
    Args:
        client: The Pyrogram client
        chat_id: The chat ID to listen for
        filter_func: Optional function to filter messages (e.g., lambda m: m.photo is not None)
        timeout: Timeout in seconds (default 300 = 5 minutes)
    
    Returns:
        The Message object or None if timeout
    """
    future = asyncio.Future()
    pending_conversations[chat_id] = {
        "future": future,
        "filter": filter_func
    }
    
    try:
        response = await asyncio.wait_for(future, timeout=timeout)
        return response
    except asyncio.TimeoutError:
        return None
    finally:
        pending_conversations.pop(chat_id, None)


def check_and_resolve_response(message: Message) -> bool:
    """
    Check if a message is a response to a pending conversation.
    Call this from a message handler.
    
    Returns:
        True if the message was handled as a conversation response
    """
    chat_id = message.chat.id
    conv = pending_conversations.get(chat_id)
    
    if conv and not conv["future"].done():
        filter_func = conv.get("filter")
        if filter_func:
            try:
                if not filter_func(message):
                    return False
            except Exception:
                return False
        conv["future"].set_result(message)
        return True
    return False


def is_photo_or_cancel(message: Message) -> bool:
    """Filter for photo messages or /cancel command"""
    if message.photo:
        return True
    if message.text and message.text.startswith("/cancel"):
        return True
    return False


def is_text_or_cancel(message: Message) -> bool:
    """Filter for text messages or /cancel command"""
    if message.text:
        return True
    return False


def is_forwarded_or_cancel(message: Message) -> bool:
    """Filter for forwarded messages or /cancel command"""
    if message.forward_date or message.forward_from or message.forward_from_chat:
        return True
    if message.text and message.text.startswith("/cancel"):
        return True
    return False


def is_any_message(message: Message) -> bool:
    """Accept any message"""
    return True


@Client.on_message(filters.private, group=-999)
async def conversation_handler(client: Client, message: Message):
    """
    Global handler to capture messages for pending conversations.
    Uses group=-999 to run before other handlers.
    """
    if check_and_resolve_response(message):
        message.stop_propagation()
