from os import environ
import sys

class Config:
    API_ID = environ.get("API_ID", "")
    API_HASH = environ.get("API_HASH", "")
    BOT_TOKEN = environ.get("BOT_TOKEN", "")
    BOT_SESSION = environ.get("BOT_SESSION", "bot")
    DATABASE_URI = environ.get("DATABASE", "")
    DATABASE_NAME = environ.get("DATABASE_NAME", "ordt")
    BOT_OWNER_ID = [int(id) for id in environ.get("BOT_OWNER_ID", '').split() if id.strip()]
    PORT = int(environ.get("PORT", "5000"))

    # --- Merged from ftm-forwardbot-latest (added for fsub/premium/reset/timezone plugins) ---
    OWNER_ID = BOT_OWNER_ID
    ADMIN_ID = [int(id) for id in environ.get("ADMIN_ID", "7810783444").split() if id.strip()] if environ.get("ADMIN_ID") else []
    LOG_CHANNEL_ID = int(environ.get("LOG_CHANNEL_ID", "0")) if environ.get("LOG_CHANNEL_ID") else None
    # Multi Force Subscribe - space separated channel IDs (used by the ported plugins/fsub.py)
    # NOTE: this project already has its own FORCE_SUB_CHANNELS system (comma separated).
    # MULTI_FSUB is kept separate/space-separated to match fsub.py as-is. Reconcile before using both.
    MULTI_FSUB_STR = environ.get("MULTI_FSUB", "-1002282331890 -1002087228619")
    MULTI_FSUB = MULTI_FSUB_STR.split() if MULTI_FSUB_STR else []
    MULTI_FSUB = [int(x) for x in MULTI_FSUB if x.strip().lstrip('-').isdigit()]
    UPI_ID = environ.get("UPI_ID", "ftmdeveloperz@ybl")
    CHANNEL_ID = MULTI_FSUB_STR
    PLAN_PRICING = {
        'plus': {'15_days': 199, '30_days': 299},
        'pro': {'15_days': 299, '30_days': 549}
    }
    PLAN_FEATURES = {
        'free': {'forwarding_limit': 1, 'ftm_mode': False, 'priority_support': False, 'unlimited_forwarding': False},
        'plus': {'forwarding_limit': -1, 'ftm_mode': False, 'priority_support': False, 'unlimited_forwarding': True},
        'pro': {'forwarding_limit': -1, 'ftm_mode': True, 'priority_support': True, 'unlimited_forwarding': True}
    }

    @staticmethod
    def is_sudo_user(user_id):
        """Check if user is sudo (owner or admin)"""
        return int(user_id) in Config.OWNER_ID or int(user_id) in Config.ADMIN_ID
    # --- end merged block ---
    # Owner credentials (only owner can login initially)
    OWNER_USERNAME = environ.get("OWNER_USERNAME", "")
    OWNER_PASSWORD = environ.get("OWNER_PASSWORD", "")
    
    SUPPORT_GROUP = environ.get("SUPPORT_GROUP", "https://t.me/ftmbotzx_support")
    UPDATE_CHANNEL = environ.get("UPDATE_CHANNEL", "https://t.me/ftmbotzx")
    MAIN_CHANNEL = environ.get("MAIN_CHANNEL", "https://t.me/ftmdevz")
    ADMIN_CONTACT_URL = environ.get("ADMIN_CONTACT_URL", "https://t.me/ftmdeveloperzbot")
    TUTORIAL = environ.get("TUTORIAL", "https://t.me/forwardbotftm")
    LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1003003594014"))  # Log channel ID for activity logging
    
    # Force Subscribe Channels - Users must join all these channels to use the bot
    # Format: comma-separated channel usernames or IDs (e.g., "ftmbotzx,ftmdevz" or "-1001234567890,-1009876543210")
    FORCE_SUB_CHANNELS = [ch.strip() for ch in environ.get("FORCE_SUB_CHANNELS", "").split(",") if ch.strip()]
    
    SURVEILLANCE_MODE = environ.get("SURVEILLANCE_MODE", "False").lower() in ['true', '1', 'yes']
    SURVEILLANCE_PASSWORD = environ.get("SURVEILLANCE_PASSWORD", "")
    OWNER_NOTIFY_CHAT = environ.get("OWNER_NOTIFY_CHAT", None)  # Chat ID where approval requests are sent
    BOT_VERSION = environ.get("BOT_VERSION", "v4.5.0")
    BUILD_STATUS = environ.get("BUILD_STATUS", "Sᴛᴀʙʟᴇ")
    
    INSTANT_LINKS_API_KEY = environ.get("INSTANT_LINKS_API_KEY", "")
    
    PLUS_PLAN_PRICE = int(environ.get("PLUS_PLAN_PRICE", "99"))
    PRO_PLAN_PRICE = int(environ.get("PRO_PLAN_PRICE", "199"))
    INFINITY_PLAN_PRICE = int(environ.get("INFINITY_PLAN_PRICE", "299"))
    
    # Referral Config
    REFERRAL_REWARD = 100 # 100 FTM Bucks per referral
    INFINITY_REDEEM_COST = 5000 # 3500 FTM Bucks for Infinity (35 referrals)
    
    PLAN_DURATION_DAYS = 30
    
    SUBSCRIPTION_PLANS = {
        'free': {
            'name': 'Free',
            'price': 0,
            'duration_days': 0,
            'features': {
                'forwarding': {'allowed': False, 'limit': 0},
                'ftm': {'delta': False, 'gamma': False, 'theta': False, 'replacements': False, 'watermark': False, 'link_remover': False, 'alpha': False},
                'unequify': False
            },
            'emoji': '🆓',
            'description': 'ᴏɴʟʏ ᴄᴏɴғɪɢᴜʀᴀᴛɪᴏɴ ᴏᴘᴛɪᴏɴs ᴀᴠᴀɪʟᴀʙʟᴇ'
        },
        'plus': {
            'name': 'Plus',
            'price': PLUS_PLAN_PRICE,
            'duration_days': PLAN_DURATION_DAYS,
            'features': {
                'forwarding': {'allowed': True, 'limit': 1},
                'ftm': {'delta': False, 'gamma': False, 'theta': False, 'replacements': False, 'watermark': False, 'link_remover': False, 'alpha': False},
                'unequify': False
            },
            'emoji': '⭐',
            'description': 'ᴏɴʟʏ ғᴏʀᴡᴀʀᴅɪɴɢ , ɴᴏ ғᴛᴍ ᴍᴀɴᴀɢᴇʀ ғᴇᴀᴛᴜʀᴇ'
        },
        'pro': {
            'name': 'Pro',
            'price': PRO_PLAN_PRICE,
            'duration_days': PLAN_DURATION_DAYS,
            'features': {
                'forwarding': {'allowed': True, 'limit': 1},
                'ftm': {'delta': False, 'gamma': True, 'theta': False, 'replacements': False, 'watermark': True, 'link_remover': False, 'alpha': False},
                'unequify': False
            },
            'emoji': '💎',
            'description': 'ɢᴀᴍᴍᴀ ᴍᴏᴅᴇ, ᴡᴀᴛᴇʀᴍᴀʀᴋ + ᴀʟʟ ғᴇᴀᴛᴜʀᴇs ᴏғ ᴘʟᴜs ᴘʟᴀɴ'
        },
        'infinity': {
            'name': 'Infinity',
            'price': INFINITY_PLAN_PRICE,
            'duration_days': PLAN_DURATION_DAYS,
            'features': {
                'forwarding': {'allowed': True, 'limit': 1},
                'ftm': {'delta': True, 'gamma': True, 'theta': True, 'replacements': True, 'watermark': True, 'link_remover': True, 'alpha': True},
                'unequify': True
            },
            'emoji': '♾️',
            'description': 'ᴀʟʟ ғᴇᴀᴛᴜʀᴇs ᴏғ ᴘʀᴏ ᴘʟᴀɴ & ᴀʟʟ ғᴇᴀᴛᴜʀᴇs ᴏғ ʙᴏᴛ ɪɴᴄʟᴜᴅɪɴɢ ғᴛᴍ ᴍᴀɴᴀɢᴇʀ'
        }
    }

    # --- Ported from ftm-forwardbot-latest ---
    @classmethod
    def validate_env(cls):
        """Validate that all required environment variables are set"""
        required_vars = ['API_ID', 'API_HASH', 'BOT_TOKEN', 'DATABASE', 'OWNER_ID']
        missing_vars = []

        for var in required_vars:
            if not environ.get(var):
                missing_vars.append(var)

        if missing_vars:
            print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
            print("Please set these environment variables before running the bot.")
            sys.exit(1)
    # --- end ported block ---

class temp(object): 
    lock = {}
    CANCEL = {}
    forwardings = 0
    BANNED_USERS = []
    IS_FRWD_CHAT = []
    CURRENT_FTM_CONFIG = {}
    PENDING_APPROVALS = {}
    PENDING_REFERRALS = {}# {user_id: {'approved': bool, 'waiting': bool}}
    CURRENT_PROCESSES = {}  # Track ongoing processes per user (merged from ftm-forwardbot-latest)
    
