from os import environ 
from config import Config
import motor.motor_asyncio
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

async def mongodb_version():
    x = MongoClient(Config.DATABASE_URI)
    mongodb_version = x.server_info()['version']
    return mongodb_version

class Database:

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.bot = self.db.bots
        self.col = self.db.users
        self.nfy = self.db.notify
        self.chl = self.db.channels 

        # --- Merged from ftm-forwardbot-latest (needed by ported fsub/premium/reset/timezone plugins) ---
        self.queue_col = self.db.queue
        self.premium_col = self.db.premium_users
        self.payment_col = self.db.payment_verifications
        self.usage_col = self.db.usage_tracking
        self.admin_chat_col = self.db.admin_chats
        self.contact_requests_col = self.db.contact_requests
        self.chat_requests_col = self.db.chat_requests
        self.trial_col = self.db.trial_usage
        self.referral_col = self.db.referrals
        self.alpha_config_col = self.db.alpha_configs
        # --- end merged block ---

    async def generate_ftm_id(self):
        """Generate unique FTM ID counting down from 9999999999"""
        last_user = await self.col.find_one(
            {'ftm_id': {'$exists': True}},
            sort=[('ftm_id', 1)]
        )
        if last_user and 'ftm_id' in last_user:
            return last_user['ftm_id'] - 1
        return 9999999999

    async def generate_referral_code(self):
        """Generate unique referral code: ftmbotzx{random 12 URL-safe chars}"""
        import random
        import string

        while True:
            chars = string.ascii_letters + string.digits
            random_part = ''.join(random.choices(chars, k=12))
            referral_code = f"ftmbotzx{random_part}"

            existing = await self.col.find_one({'referral.code': referral_code})
            if not existing:
                return referral_code

    def new_user(self, id, name, ftm_id, referral_code):
        from datetime import datetime
        return dict(
            id = id,
            name = name,
            ftm_id = ftm_id,
            joined_at = datetime.utcnow(),
            ban_status=dict(
                is_banned=False,
                ban_reason="",
            ),
            subscription=dict(
                plan='free',
                status='active',
                expires_at=None,
                assigned_by='system',
                features=Config.SUBSCRIPTION_PLANS['free']['features']
            ),
            referral=dict(
                code=referral_code,
                referred_by=None,
                ftm_bucks=0,
                total_referrals=0,
                referred_users=[]
            ),
            active_tasks=dict(
                forwarding=0,
                last_activity_at=None
            ),
            last_process=dict(
                type=None,
                completed_at=None,
                status=None
            )
        )

    async def add_user(self, id, name, referred_by_code=None):
        ftm_id = await self.generate_ftm_id()
        referral_code = await self.generate_referral_code()
        user = self.new_user(id, name, ftm_id, referral_code)

        if referred_by_code:
            referrer = await self.col.find_one({'referral.code': referred_by_code})
            if referrer:
                user['referral']['referred_by'] = referrer['id']

        await self.col.insert_one(user)

    async def is_user_exist(self, id):
        user = await self.col.find_one({'id':int(id)})
        return bool(user)

    async def total_users_bots_count(self):
        bcount = await self.bot.count_documents({})
        count = await self.col.count_documents({})
        return count, bcount

    async def total_channels(self):
        count = await self.chl.count_documents({})
        return count

    async def remove_ban(self, id):
        ban_status = dict(
            is_banned=False,
            ban_reason=''
        )
        await self.col.update_one({'id': id}, {'$set': {'ban_status': ban_status}})

    async def ban_user(self, user_id, ban_reason="No Reason"):
        ban_status = dict(
            is_banned=True,
            ban_reason=ban_reason
        )
        await self.col.update_one({'id': user_id}, {'$set': {'ban_status': ban_status}})

    async def get_ban_status(self, id):
        default = dict(
            is_banned=False,
            ban_reason=''
        )
        user = await self.col.find_one({'id':int(id)})
        if not user:
            return default
        return user.get('ban_status', default)

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    async def remove_user_completely(self, user_id):
        """Remove user from all collections"""
        user_id = int(user_id)
        results = {
            'users': await self.col.delete_many({'id': user_id}),
            'bots': await self.bot.delete_many({'user_id': user_id}),
            'channels': await self.chl.delete_many({'user_id': user_id}),
            'notifications': await self.nfy.delete_many({'user_id': user_id}),
            'admins': await self.db.admins.delete_one({'user_id': user_id})
        }
        return results

    async def get_banned(self):
        users = self.col.find({'ban_status.is_banned': True})
        b_users = [user['id'] async for user in users]
        return b_users

    async def update_configs(self, id, configs):
        await self.col.update_one({'id': int(id)}, {'$set': {'configs': configs}})

    async def update_config_key(self, id, key, value):
        """Update a specific config key"""
        await self.col.update_one(
            {'id': int(id)}, 
            {'$set': {f'configs.{key}': value}},
            upsert=False
        )

    async def get_configs(self, id):
        default = {
            'caption': None,
            'duplicate': True,
            'forward_tag': False,
            'file_size': 0,
            'size_limit': None,
            'extension': None,
            'keywords': None,
            'protect': None,
            'button': None,
            'db_uri': None,
            'ftm_delta_mode': False,
            'ftm_gamma_mode': False,
            'ftm_theta_mode': False,
            'ftm_alpha_mode': False,
            'ftm_pi_mode': False,
            'ftm_gamma_sources': [],
            'ftm_gamma_targets': [],
            'ftm_replacer': [],
            'ftm_remover': [],
            'ftm_link_remover': False,
            'filters': {
               'poll': True,
               'text': True,
               'audio': True,
               'voice': True,
               'video': True,
               'photo': True,
               'document': True,
               'animation': True,
               'sticker': True
            }
        }
        user = await self.col.find_one({'id':int(id)})
        if user:
            return user.get('configs', default)
        return default 

    async def add_bot(self, datas):
       if not await self.is_bot_exist(datas['user_id']):
          await self.bot.insert_one(datas)

    async def remove_bot(self, user_id):
       await self.bot.delete_many({'user_id': int(user_id)})

    async def get_bot(self, user_id: int):
       bot = await self.bot.find_one({'user_id': user_id})
       return bot if bot else None

    async def is_bot_exist(self, user_id):
       bot = await self.bot.find_one({'user_id': user_id})
       return bool(bot)

    async def in_channel(self, user_id: int, chat_id: int) -> bool:
       channel = await self.chl.find_one({"user_id": int(user_id), "chat_id": int(chat_id)})
       return bool(channel)

    async def add_channel(self, user_id: int, chat_id: int, title, username, thread_id=None):
       channel = await self.in_channel(user_id, chat_id)
       if channel:
         return False
       return await self.chl.insert_one({
           "user_id": user_id,
           "chat_id": chat_id,
           "title": title,
           "username": username,
           "thread_id": thread_id
       })

    async def remove_channel(self, user_id: int, chat_id: int):
       channel = await self.in_channel(user_id, chat_id )
       if not channel:
         return False
       return await self.chl.delete_many({"user_id": int(user_id), "chat_id": int(chat_id)})

    async def get_channel_details(self, user_id: int, chat_id: int):
       return await self.chl.find_one({"user_id": int(user_id), "chat_id": int(chat_id)})

    async def get_user_channels(self, user_id: int):
       channels = self.chl.find({"user_id": int(user_id)})
       return [channel async for channel in channels]

    async def get_filters(self, user_id):
       filters = []
       filter = (await self.get_configs(user_id))['filters']
       for k, v in filter.items():
          if v == False:
            filters.append(str(k))
       return filters

    async def set_user_approval(self, user_id, approved=True, declined=False):
        """Set user approval status in database"""
        approval_status = {
            'approved': approved,
            'declined': declined,
            'waiting': False
        }
        await self.col.update_one(
            {'id': int(user_id)}, 
            {'$set': {'approval_status': approval_status}},
            upsert=True
        )

    async def get_user_approval(self, user_id):
        """Get user approval status from database"""
        default = {'approved': False, 'declined': False, 'waiting': False}
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return default
        return user.get('approval_status', default)

    async def add_frwd(self, user_id):
       return await self.nfy.insert_one({'user_id': int(user_id)})

    async def rmve_frwd(self, user_id=0, all=False):
       data = {} if all else {'user_id': int(user_id)}
       return await self.nfy.delete_many(data)

    async def get_all_frwd(self):
       return self.nfy.find({})

    async def ensure_user_document(self, user_id):
        """Ensure user document exists with subscription data"""
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return False

        if 'subscription' not in user:
            await self.col.update_one(
                {'id': int(user_id)},
                {'$set': {
                    'subscription': {
                        'plan': 'free',
                        'status': 'active',
                        'expires_at': None,
                        'assigned_by': 'system',
                        'features': Config.SUBSCRIPTION_PLANS['free']['features']
                    },
                    'active_tasks': {
                        'forwarding': 0,
                        'last_activity_at': None
                    }
                }}
            )
        return True

    async def get_subscription(self, user_id):
        """Get user subscription details"""
        await self.ensure_user_document(user_id)
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return None
        subscription = user.get('subscription', {
            'plan': 'free',
            'status': 'active',
            'expires_at': None,
            'assigned_by': 'system',
            'features': Config.SUBSCRIPTION_PLANS['free']['features']
        })
        
        # Merge features with config defaults to ensure new features are included
        plan = subscription.get('plan', 'free')
        default_features = Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free']).get('features', {})
        
        # Deep merge features
        if 'features' in subscription:
            for feature_category, feature_data in default_features.items():
                if feature_category not in subscription['features']:
                    subscription['features'][feature_category] = feature_data
                elif isinstance(feature_data, dict):
                    for key, value in feature_data.items():
                        if key not in subscription['features'][feature_category]:
                            subscription['features'][feature_category][key] = value
        else:
            subscription['features'] = default_features
        
        return subscription

    async def set_subscription(self, user_id, plan, expires_at=None, assigned_by='system', status='active'):
        """Set user subscription"""
        from datetime import datetime, timedelta

        if expires_at is None and plan != 'free':
            duration_days = Config.SUBSCRIPTION_PLANS.get(plan, {}).get('duration_days', 30)
            if duration_days > 0:
                expires_at = datetime.utcnow() + timedelta(days=duration_days)

        subscription_data = {
            'plan': plan,
            'status': status,
            'expires_at': expires_at,
            'purchased_at': datetime.utcnow() if plan != 'free' else None,
            'assigned_by': assigned_by,
            'features': Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])['features']
        }

        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {'subscription': subscription_data}},
            upsert=True
        )

    async def set_lifetime_plan(self, user_id, plan='infinity', assigned_by='system'):
        """Set lifetime subscription for admins/owners"""
        from datetime import datetime
        subscription_data = {
            'plan': plan,
            'status': 'lifetime',
            'expires_at': None,
            'purchased_at': datetime.utcnow(),
            'assigned_by': assigned_by,
            'features': Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['infinity'])['features']
        }

        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {'subscription': subscription_data}},
            upsert=True
        )

    async def increment_task(self, user_id, kind='forwarding'):
        """Increment active task count"""
        from datetime import datetime
        await self.col.update_one(
            {'id': int(user_id)},
            {
                '$inc': {f'active_tasks.{kind}': 1},
                '$set': {'active_tasks.last_activity_at': datetime.utcnow()}
            }
        )

    async def decrement_task(self, user_id, kind='forwarding'):
        """Decrement active task count (won't go below 0)"""
        # First get current value
        user = await self.col.find_one({'id': int(user_id)})
        if user:
            current = user.get('active_tasks', {}).get(kind, 0)
            if current > 0:
                await self.col.update_one(
                    {'id': int(user_id)},
                    {'$inc': {f'active_tasks.{kind}': -1}}
                )

    async def reset_task_counter(self, user_id, kind='forwarding'):
        """Reset active task count to 0 - use when counter is stuck"""
        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {f'active_tasks.{kind}': 0}}
        )

    async def get_active_tasks(self, user_id):
        """Get active tasks count"""
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return {'forwarding': 0, 'last_activity_at': None}
        return user.get('active_tasks', {'forwarding': 0, 'last_activity_at': None})

    async def update_last_process(self, user_id, process_type, status='completed'):
        """Update last process information"""
        from datetime import datetime
        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {
                'last_process.type': process_type,
                'last_process.completed_at': datetime.utcnow(),
                'last_process.status': status
            }}
        )

    async def expire_subscriptions(self):
        """Expire subscriptions that have passed their expiry date"""
        from datetime import datetime
        result = await self.col.update_many(
            {
                'subscription.expires_at': {'$lt': datetime.utcnow()},
                'subscription.status': 'active'
            },
            {
                '$set': {
                    'subscription.status': 'expired',
                    'subscription.plan': 'free',
                    'subscription.features': Config.SUBSCRIPTION_PLANS['free']['features']
                }
            }
        )
        return result.modified_count

    async def get_referral_info(self, user_id):
        """Get user referral information"""
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return None
        return user.get('referral', {
            'code': None,
            'referred_by': None,
            'ftm_bucks': 0,
            'total_referrals': 0,
            'referred_users': []
        })

    async def add_balance(self, user_id, amount):
        """Add balance to user's ftmbucks"""
        return await self.col.update_one(
            {'id': int(user_id)},
            {'$inc': {'referral.ftm_bucks': float(amount)}},
            upsert=True
        )

    async def get_balance(self, user_id):
        """Get user's ftmbucks balance"""
        user = await self.col.find_one({'id': int(user_id)})
        if not user: return 0.0
        return user.get('referral', {}).get('ftm_bucks', 0.0)

    async def deduct_ftm_bucks(self, user_id, amount):
        """Deduct FtmBucks from user account"""
        user = await self.col.find_one({'id': int(user_id)})
        if not user or user.get('referral', {}).get('ftm_bucks', 0) < amount:
            return False

        await self.col.update_one(
            {'id': int(user_id)},
            {'$inc': {'referral.ftm_bucks': -amount}}
        )
        return True

    async def record_referral(self, referrer_id, referred_user_id):
        """Record a successful referral"""
        await self.col.update_one(
            {'id': int(referrer_id)},
            {
                '$inc': {'referral.total_referrals': 1},
                '$push': {'referral.referred_users': int(referred_user_id)}
            }
        )

    async def get_user_by_referral_code(self, referral_code):
        """Get user by their referral code"""
        user = await self.col.find_one({'referral.code': referral_code})
        return user

    async def ensure_referral_data(self, user_id):
        """Ensure user has referral data (for existing users)"""
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return False

        if 'referral' not in user:
            ftm_id = await self.generate_ftm_id()
            referral_code = await self.generate_referral_code()

            await self.col.update_one(
                {'id': int(user_id)},
                {'$set': {
                    'ftm_id': ftm_id,
                    'referral': {
                        'code': referral_code,
                        'referred_by': None,
                        'ftm_bucks': 0,
                        'total_referrals': 0,
                        'referred_users': []
                    }
                }}
            )
        return True

    async def add_admin(self, user_id, username, password_hash, created_by):
        """Add a new admin"""
        from datetime import datetime
        admin_data = {
            'user_id': int(user_id),
            'username': username,
            'password_hash': password_hash,
            'role': 'admin',
            'created_at': datetime.utcnow(),
            'created_by': created_by,
            'is_active': True
        }

        # Check if admin already exists
        existing = await self.db.admins.find_one({'user_id': int(user_id)})
        if existing:
            return False

        await self.db.admins.insert_one(admin_data)

        # Grant infinity plan
        await self.set_lifetime_plan(user_id, 'infinity', assigned_by='system')

        return True

    async def remove_admin(self, user_id):
        """Remove admin privileges"""
        result = await self.db.admins.delete_one({'user_id': int(user_id)})
        return result.deleted_count > 0

    async def get_admin(self, username):
        """Get admin by username"""
        return await self.db.admins.find_one({'username': username})

    async def get_admin_by_id(self, user_id):
        """Get admin by user_id"""
        return await self.db.admins.find_one({'user_id': int(user_id)})

    async def get_all_admins(self):
        """Get all admins"""
        return self.db.admins.find({})

    async def is_admin(self, user_id):
        """Check if user is admin"""
        admin = await self.db.admins.find_one({'user_id': int(user_id), 'is_active': True})
        return bool(admin)

    async def toggle_admin_status(self, user_id):
        """Toggle admin active status"""
        admin = await self.db.admins.find_one({'user_id': int(user_id)})
        if not admin:
            return False

        new_status = not admin.get('is_active', True)
        await self.db.admins.update_one(
            {'user_id': int(user_id)},
            {'$set': {'is_active': new_status}}
        )
        return True

    async def update_admin_password(self, user_id, password_hash):
        """Update admin password"""
        result = await self.db.admins.update_one(
            {'user_id': int(user_id)},
            {'$set': {'password_hash': password_hash}}
        )
        return result.modified_count > 0

    async def create_verification_token(self, user_id, token, shortened_url):
        """Create a new verification token for user"""
        from datetime import datetime
        await self.db.verifications.delete_many({'user_id': int(user_id), 'used': False})

        verification_data = {
            'user_id': int(user_id),
            'token': token,
            'shortened_url': shortened_url,
            'created_at': datetime.utcnow(),
            'used': False,
            'used_at': None
        }

        await self.db.verifications.insert_one(verification_data)

    async def get_verification_by_token(self, token):
        """Get verification data by token"""
        return await self.db.verifications.find_one({'token': token})

    async def mark_verification_used(self, token):
        """Mark verification token as used"""
        from datetime import datetime
        await self.db.verifications.update_one(
            {'token': token},
            {'$set': {'used': True, 'used_at': datetime.utcnow()}}
        )

    async def get_pending_verification(self, user_id):
        """Get user's pending/active verification status"""
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return None
        return user.get('verification_bonus', {})

    async def update_verification_plan_status(self, user_id, is_verified=False, plan_expires_at=None):
        """Update user's verification plan status"""
        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {
                'verification_bonus': {
                    'is_verified': is_verified,
                    'plan_expires_at': plan_expires_at,
                    'verified_at': datetime.utcnow() if is_verified else None
                }
            }},
            upsert=True
        )

    async def get_active_verification_users(self):
        """Get all users with active verification bonus plans"""
        from datetime import datetime
        return self.col.find({
            'subscription.is_verification_plan': True,
            'subscription.expires_at': {'$lte': datetime.utcnow()},
            'subscription.status': 'active'
        })

    async def get_users_with_verification_plan(self):
        """Get users with verification plan for expiry checking"""
        from datetime import datetime
        return self.col.find({
            'subscription.is_verification_plan': True,
            'subscription.status': 'active'
        })

    async def pause_user_forwarding(self, user_id):
        """Pause active forwarding tasks for a user"""
        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {
                'forwarding_paused': True,
                'paused_at': datetime.utcnow(),
                'pause_reason': 'verification_expired'
            }}
        )

    async def get_forwarding_pause_status(self, user_id):
        """Check if user's forwarding is paused"""
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return False
        return user.get('forwarding_paused', False)

    async def resume_forwarding(self, user_id):
        """Resume user's forwarding"""
        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {'forwarding_paused': False, 'pause_reason': None}}
        )

    # ================ FTM Alpha Mode - Forwarding State Tracking ================
    
    async def save_forwarding_state(self, user_id, state_data, merge=False):
        """Save or update forwarding state for auto-resume
        
        Args:
            user_id: User ID
            state_data: State data to save
            merge: If True, only update provided fields without overwriting others
        """
        fwd_type = state_data.get('type')
        
        if merge and fwd_type:
            # Merge mode: Only update the specific fields provided
            # MongoDB $set only updates the fields specified, leaving others intact
            update_data = {'updated_at': datetime.utcnow()}
            for key, value in state_data.items():
                if key != 'type':  # Don't update the type field, use it for matching
                    update_data[key] = value
            
            await self.db.forwarding_states.update_one(
                {'user_id': int(user_id), 'type': fwd_type},
                {'$set': update_data}
            )
        else:
            # Replace mode: Set all fields (for initial state creation)
            state_data['user_id'] = int(user_id)
            state_data['updated_at'] = datetime.utcnow()
            
            await self.db.forwarding_states.update_one(
                {'user_id': int(user_id), 'type': state_data.get('type')},
                {'$set': state_data},
                upsert=True
            )
    
    async def get_forwarding_state(self, user_id, fwd_type=None):
        """Get active forwarding state for user"""
        query = {'user_id': int(user_id), 'status': {'$in': ['active', 'paused']}}
        if fwd_type:
            query['type'] = fwd_type
        return await self.db.forwarding_states.find_one(query)
    
    async def get_all_active_forwarding_states(self):
        """Get all active/paused forwarding states for auto-resume on restart"""
        return self.db.forwarding_states.find({'status': {'$in': ['active', 'paused']}})
    
    async def update_forwarding_progress(self, user_id, fwd_type, last_msg_id, processed, fetched):
        """Update forwarding progress (called after each message)"""
        await self.db.forwarding_states.update_one(
            {'user_id': int(user_id), 'type': fwd_type},
            {'$set': {
                'last_msg_id': last_msg_id,
                'processed': processed,
                'fetched': fetched,
                'updated_at': datetime.utcnow()
            }}
        )
    
    async def complete_forwarding_state(self, user_id, fwd_type):
        """Mark forwarding as completed"""
        await self.db.forwarding_states.update_one(
            {'user_id': int(user_id), 'type': fwd_type},
            {'$set': {
                'status': 'completed',
                'completed_at': datetime.utcnow()
            }}
        )
    
    async def cancel_forwarding_state(self, user_id, fwd_type=None):
        """Cancel/remove forwarding state"""
        query = {'user_id': int(user_id)}
        if fwd_type:
            query['type'] = fwd_type
        await self.db.forwarding_states.delete_many(query)
    
    async def get_completed_forwarding_states(self):
        """Get forwarding states that completed before restart (for notification)"""
        return self.db.forwarding_states.find({'status': 'completed', 'notified': {'$ne': True}})
    
    async def mark_state_notified(self, user_id, fwd_type):
        """Mark forwarding state as notified"""
        await self.db.forwarding_states.update_one(
            {'user_id': int(user_id), 'type': fwd_type},
            {'$set': {'notified': True}}
        )
    
    # ================ FTM Alpha - Gamma Last Message Tracking ================
    
    async def update_gamma_last_msg(self, user_id, source_chat_id, message_id):
        """Update last forwarded message ID for a gamma source channel"""
        await self.db.forwarding_states.update_one(
            {'user_id': int(user_id), 'type': 'gamma'},
            {
                '$set': {
                    f'last_msg_ids.{source_chat_id}': message_id,
                    'updated_at': datetime.utcnow()
                },
                '$inc': {'processed': 1}
            }
        )
    
    async def get_gamma_last_msgs(self, user_id):
        """Get all last message IDs for gamma sources"""
        state = await self.db.forwarding_states.find_one(
            {'user_id': int(user_id), 'type': 'gamma'}
        )
        if state:
            return state.get('last_msg_ids', {})
        return {}
    
    async def save_gamma_state(self, user_id, source_chat_ids, target_chat_ids, last_msg_ids=None):
        """Save gamma forwarding state with last message IDs per source"""
        state_data = {
            'user_id': int(user_id),
            'type': 'gamma',
            'source_chat_ids': source_chat_ids,
            'target_chat_ids': target_chat_ids,
            'status': 'active',
            'processed': 0,
            'updated_at': datetime.utcnow()
        }
        if last_msg_ids:
            state_data['last_msg_ids'] = last_msg_ids
        
        await self.db.forwarding_states.update_one(
            {'user_id': int(user_id), 'type': 'gamma'},
            {'$set': state_data},
            upsert=True
        )

    async def set_thumbnail(self, user_id, file_id, file_unique_id=None, file_path=None):
        """Save user's custom thumbnail for FTM Thumbnail Changer"""
        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {
                'ftm_thumbnail': {
                    'file_id': file_id,
                    'file_unique_id': file_unique_id,
                    'file_path': file_path,
                    'updated_at': datetime.utcnow()
                }
            }},
            upsert=True
        )
    
    async def get_thumbnail(self, user_id):
        """Get user's custom thumbnail file path for applying to videos"""
        user = await self.col.find_one({'id': int(user_id)})
        if user and 'ftm_thumbnail' in user:
            return user['ftm_thumbnail'].get('file_path')
        return None
    
    async def get_thumbnail_info(self, user_id):
        """Get full thumbnail info including file_id and metadata"""
        user = await self.col.find_one({'id': int(user_id)})
        if user and 'ftm_thumbnail' in user:
            return user['ftm_thumbnail']
        return None
    
    async def remove_thumbnail(self, user_id):
        """Remove user's custom thumbnail"""
        await self.col.update_one(
            {'id': int(user_id)},
            {'$unset': {'ftm_thumbnail': ''}}
        )
    
    async def set_thumbnail_enabled(self, user_id, enabled=True):
        """Enable or disable thumbnail changer mode"""
        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {'configs.ftm_thumbnail_enabled': enabled}},
            upsert=True
        )
    
    async def get_thumbnail_enabled(self, user_id):
        """Check if thumbnail changer is enabled for user"""
        config = await self.get_configs(user_id)
        return config.get('ftm_thumbnail_enabled', False)

    # ==== Merged methods from ftm-forwardbot-latest (fsub/premium/reset/timezone support) ====
    async def add_chat_message(self, session_id, from_admin, message_text):
        """Add message to admin chat session"""
        message_data = {
            'from_admin': from_admin,
            'message': message_text,
            'timestamp': datetime.utcnow()
        }
        return await self.admin_chat_col.update_one(
            {'_id': session_id},
            {'$push': {'messages': message_data}}
        )


    async def add_premium_user(self, user_id, plan_type="pro", duration_days=30, amount_paid=None):
        """Add a user to premium with three-tier support"""
        expires_at = datetime.utcnow() + timedelta(days=duration_days)

        premium_data = {
            'user_id': int(user_id),
            'plan_type': plan_type,  # 'free', 'plus', 'pro'
            'duration_days': duration_days,
            'amount_paid': amount_paid,
            'subscribed_at': datetime.utcnow(),
            'expires_at': expires_at,
            'is_active': True,
            'auto_renew': False,
            'features': self._get_plan_features(plan_type)
        }

        # Special handling for sudo lifetime subscriptions
        if amount_paid == "sudo_lifetime_subscription":
            premium_data['is_sudo_lifetime'] = True
            premium_data['expires_at'] = datetime.utcnow() + timedelta(days=365250)  # 999+ years
            
        # Remove existing premium record if any
        await self.premium_col.delete_many({'user_id': int(user_id)})
        return await self.premium_col.insert_one(premium_data)


    async def approve_payment(self, verification_id, admin_id, notes=None):
        """Approve payment verification"""
        result = await self.payment_col.update_one(
            {'_id': verification_id},
            {
                '$set': {
                    'status': 'approved',
                    'reviewed_by': int(admin_id),
                    'reviewed_at': datetime.utcnow(),
                    'review_notes': notes
                }
            }
        )

        # Get the verification to add premium subscription
        verification = await self.payment_col.find_one({'_id': verification_id})
        if verification and result.modified_count > 0:
            # Add premium subscription based on plan and duration
            await self.add_premium_user(
                verification['user_id'], 
                verification.get('plan_type', 'pro'),
                verification.get('duration_days', 30),
                verification.get('amount')
            )

        return result.modified_count > 0


    async def check_force_subscribe(self, user_id, client):
        """Check if user is subscribed to all required channels"""
        from config import Config

        try:
            if not Config.MULTI_FSUB:
                return {'all_subscribed': True, 'missing_channels': []}

            all_subscribed = True
            missing_channels = []

            for channel_id in Config.MULTI_FSUB:
                try:
                    # Convert to int if string
                    if isinstance(channel_id, str):
                        if channel_id.strip().lstrip('-').isdigit():
                            channel_id = int(channel_id)
                        else:
                            logger.warning(f"Skipping invalid channel ID: {channel_id}")
                            continue
                            
                    member = await client.get_chat_member(channel_id, user_id)
                    subscribed = member.status not in ['left', 'kicked']
                    
                    if not subscribed:
                        all_subscribed = False
                        try:
                            chat = await client.get_chat(channel_id)
                            missing_channels.append(chat.title or f"Channel {abs(channel_id)}")
                        except Exception:
                            missing_channels.append(f"Channel {abs(channel_id)}")
                            
                except Exception as e:
                    # Skip channels that cause USERNAME_INVALID or other errors
                    if "USERNAME_INVALID" not in str(e):
                        logger.error(f"Error checking channel {channel_id}: {e}")
                    all_subscribed = False
                    missing_channels.append(f"Channel {abs(int(channel_id)) if str(channel_id).lstrip('-').isdigit() else channel_id}")

                    if not subscribed:
                        all_subscribed = False
                        missing_channels.append(f"Channel {channel_id}")

                except Exception as e:
                    print(f"Error checking channel {channel_id}: {e}")
                    all_subscribed = False
                    missing_channels.append(f"Channel {channel_id}")

            result = {
                'all_subscribed': all_subscribed,
                'missing_channels': missing_channels
            }

            print(f"Subscription check result for user {user_id}: {result}")
            return result

        except Exception as e:
            print(f"Force subscribe check error: {e}")
            return {
                'all_subscribed': False,
                'missing_channels': ['Required channels']
            }

    # Admin chat sessions

    async def cleanup_chat_notifications(self, request_id, client, accepting_admin_id):
        """Delete notifications from all other admins when one admin accepts"""
        try:
            # Get the request to find notification messages
            request = await self.get_chat_request_by_id(request_id)
            if not request or 'notifications' not in request:
                return

            # Delete messages from all admins except the one who accepted
            for notification in request['notifications']:
                if notification['admin_id'] != accepting_admin_id:
                    try:
                        await client.delete_messages(
                            chat_id=notification['admin_id'],
                            message_ids=notification['message_id']
                        )
                    except Exception as e:
                        print(f"Failed to delete notification for admin {notification['admin_id']}: {e}")
        except Exception as e:
            print(f"Error cleaning up notifications: {e}")


    async def create_chat_request(self, user_id):
        """Create a new chat request"""
        chat_data = {
            'user_id': int(user_id),
            'status': 'pending',
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(hours=24),  # Auto-expire after 24 hours
            'reviewed_at': None,
            'reviewed_by': None,
            'notifications': []  # Store notification message IDs for cleanup
        }

        result = await self.chat_requests_col.insert_one(chat_data)
        return result.inserted_id


    async def end_admin_chat(self, admin_id):
        """End admin chat session"""
        return await self.admin_chat_col.update_many(
            {'admin_id': int(admin_id), 'is_active': True},
            {'$set': {'is_active': False, 'ended_at': datetime.utcnow()}}
        )


    async def get_active_admin_chat(self, admin_id):
        """Get active admin chat session for a specific admin"""
        return await self.admin_chat_col.find_one({
            'admin_id': int(admin_id),
            'is_active': True
        })

    # Contact requests methods

    async def get_active_chat_for_user(self, user_id):
        """Get active admin chat session for a specific user"""
        return await self.admin_chat_col.find_one({
            'target_user_id': int(user_id),
            'is_active': True
        })


    async def get_all_premium_users(self):
        """Get all premium users"""
        return await self.premium_col.find({'is_active': True}).to_list(length=1000)


    async def get_chat_request_by_id(self, request_id):
        """Get chat request by ID"""
        return await self.chat_requests_col.find_one({
            '_id': ObjectId(request_id)
        })


    async def get_daily_usage(self, user_id):
        """Get user's usage for current day"""
        start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        usage = await self.usage_col.find_one({
            'user_id': int(user_id),
            'date': start_of_day
        })
        return usage if usage else {'user_id': int(user_id), 'date': start_of_day, 'processes': 0}


    async def get_monthly_usage(self, user_id):
        """Get user's usage for current month"""
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = await self.usage_col.find_one({
            'user_id': int(user_id),
            'date': start_of_month
        })
        return usage if usage else {'user_id': int(user_id), 'date': start_of_month, 'processes': 0, 'trial_processes': 0}


    async def get_pending_chat_request(self, user_id):
        """Get pending chat request for user"""
        return await self.chat_requests_col.find_one({
            'user_id': int(user_id),
            'status': 'pending'
        })


    async def get_premium_user_details(self, user_id):
        """Get premium user details"""
        return await self.premium_col.find_one({'user_id': int(user_id)})


    async def get_trial_status(self, user_id):
        """Get user's trial status - whether they have used their free trial"""
        monthly_usage = await self.get_monthly_usage(user_id)
        return {
            'used': monthly_usage.get('trial_activated', False),
            'trial_processes': monthly_usage.get('trial_processes', 0),
            'granted_at': monthly_usage.get('trial_granted_at')
        }


    async def get_user(self, user_id):
        """Get user data by user ID"""
        return await self.col.find_one({'id': int(user_id)})


    async def get_user_plan_features(self, user_id):
        """Get user's plan features"""
        user = await self.premium_col.find_one({
            'user_id': int(user_id),
            'is_active': True,
            'expires_at': {'$gt': datetime.utcnow()}
        })
        if user:
            plan_type = user.get('plan_type', 'free')
            current_plan_features = self._get_plan_features(plan_type)
            stored_features = user.get('features', {})

            # Merge current plan features with stored features (current plan takes precedence for missing keys)
            merged_features = {**current_plan_features, **stored_features}

            # If features are missing/outdated, update them in database
            if stored_features != merged_features:
                await self.premium_col.update_one(
                    {'user_id': int(user_id)},
                    {'$set': {'features': merged_features}}
                )
                print(f"✅ Updated features for Pro user {user_id}: added missing keys")

            return merged_features
        return self._get_plan_features('free')


    async def get_verification_by_id(self, verification_id):
        """Get verification details by ID"""
        return await self.payment_col.find_one({'_id': verification_id})

    # Usage tracking for daily limits

    async def is_premium_user(self, user_id):
        """Check if user has active premium subscription"""
        user = await self.premium_col.find_one({
            'user_id': int(user_id),
            'is_active': True,
            'expires_at': {'$gt': datetime.utcnow()}
        })
        
        # Special check for sudo lifetime subscriptions
        if not user:
            sudo_user = await self.premium_col.find_one({
                'user_id': int(user_id),
                'is_active': True,
                'is_sudo_lifetime': True
            })
            return bool(sudo_user)
            
        return bool(user)


    async def is_user_subscribed_to_channel(self, user_id, channel_id, client):
        """
        Check if user is subscribed to a specific channel
        
        Args:
            user_id (int): User ID to check
            channel_id (int): Channel ID to check
            client: Pyrogram client instance
            
        Returns:
            bool: True if subscribed, False otherwise
        """
        try:
            # Convert string channel_id to int if needed
            if isinstance(channel_id, str):
                if channel_id.startswith('-'):
                    channel_id = int(channel_id)
                else:
                    # Skip invalid channel IDs
                    logger.warning(f"Skipping invalid channel ID format: {channel_id}")
                    return False
                    
            member = await client.get_chat_member(channel_id, user_id)
            return member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]
        except Exception as e:
            # Don't log USERNAME_INVALID errors as they're expected for some channels
            if "USERNAME_INVALID" not in str(e):
                logger.error(f"Error checking channel {channel_id}: {e}")
            return False


    async def mark_referral_channels_joined(self, user_id):
        """Mark that referred user has joined all required channels"""
        result = await self.referral_col.update_one(
            {'referred_user_id': int(user_id), 'completed': False},
            {'$set': {'channels_joined': True}}
        )
        
        # Check if referral should be completed
        if result.modified_count > 0:
            return await self._check_and_complete_referral(user_id)
        return False


    async def reject_payment(self, verification_id, admin_id, notes=None):
        """Reject payment verification"""
        result = await self.payment_col.update_one(
            {'_id': verification_id},
            {
                '$set': {
                    'status': 'rejected',
                    'reviewed_by': int(admin_id),
                    'reviewed_at': datetime.utcnow(),
                    'review_notes': notes or 'Payment verification rejected'
                }
            }
        )
        return result.modified_count > 0


    async def remove_premium_user(self, user_id):
        """Remove a user from premium"""
        return await self.premium_col.delete_many({'user_id': int(user_id)})


    async def start_admin_chat(self, admin_id, target_user_id):
        """Start admin chat session with user"""
        chat_data = {
            'admin_id': int(admin_id),
            'target_user_id': int(target_user_id),
            'started_at': datetime.utcnow(),
            'is_active': True,
            'messages': []
        }

        # End any existing chat session for this admin
        await self.admin_chat_col.update_many(
            {'admin_id': int(admin_id), 'is_active': True},
            {'$set': {'is_active': False, 'ended_at': datetime.utcnow()}}
        )

        result = await self.admin_chat_col.insert_one(chat_data)
        return result.inserted_id


    async def store_chat_notifications(self, request_id, notification_messages):
        """Store notification message IDs for cleanup"""
        return await self.chat_requests_col.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {'notifications': notification_messages}}
        )


    async def submit_payment_verification(self, user_id, screenshot_file_id, plan_type='pro', duration_days=30, amount=None):
        """Submit payment verification with plan support"""
        verification_data = {
            'user_id': int(user_id),
            'screenshot_file_id': screenshot_file_id,
            'plan_type': plan_type,
            'duration_days': duration_days,
            'amount': amount,
            'payment_method': '6354228145@axl',
            'submitted_at': datetime.utcnow(),
            'status': 'pending',  # pending, approved, rejected
            'reviewed_by': None,
            'reviewed_at': None,
            'review_notes': None
        }
        result = await self.payment_col.insert_one(verification_data)
        return result.inserted_id


    async def update_chat_request_status(self, request_id, status, admin_id=None):
        """Update chat request status"""
        update_data = {
            'status': status,
            'reviewed_at': datetime.utcnow()
        }
        if admin_id:
            update_data['reviewed_by'] = int(admin_id)

        return await self.chat_requests_col.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': update_data}
        )

    async def cleanup_expired_chat_requests(self):
        """Remove chat requests and data older than 24 hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        expired_requests = self.chat_requests_col.find({
            'created_at': {'$lt': cutoff_time}
        })

        async for request in expired_requests:
            if request.get('status') == 'accepted':
                await self.admin_chat_col.update_many(
                    {'target_user_id': request['user_id'], 'is_active': True},
                    {'$set': {'is_active': False, 'ended_at': datetime.utcnow()}}
                )

        result = await self.chat_requests_col.delete_many({
            'created_at': {'$lt': cutoff_time}
        })

        return result.deleted_count

    async def can_use_trial(self, user_id):
        """Check if user can use 3-day trial (once per year)"""
        current_year = datetime.utcnow().year

        existing_trial = await self.premium_col.find_one({
            'user_id': int(user_id),
            'plan_type': '3day_trial',
            'trial_year': current_year
        })

        return existing_trial is None

    async def grant_trial(self, user_id):
        """Grant 3-day trial to user"""
        try:
            current_year = datetime.utcnow().year

            if not await self.can_use_trial(user_id):
                return False, "Trial already used this year"

            if await self.is_premium_user(user_id):
                return False, "Already has premium access"

            await self.premium_col.delete_many({'user_id': int(user_id)})

            expires_at = datetime.utcnow() + timedelta(days=3)

            trial_data = {
                'user_id': int(user_id),
                'plan_type': '3day_trial',
                'duration_days': 3,
                'amount_paid': 0,
                'subscribed_at': datetime.utcnow(),
                'expires_at': expires_at,
                'is_active': True,
                'auto_renew': False,
                'trial_year': current_year,
                'features': {
                    'forwarding_limit': -1,
                    'ftm_mode': False,
                    'priority_support': True,
                    'unlimited_forwarding': True
                }
            }

            await self.premium_col.insert_one(trial_data)
            return True, expires_at

        except Exception as e:
            return False, str(e)


    # ============ Ported from ftm-forwardbot-latest (premium/plan/referral/queue system) ============
    async def update_user_config(self, user_id, key, value):
        """Update a specific configuration key for a user"""
        try:
            # Get current configs
            current_configs = await self.get_configs(user_id)
            
            # Update the specific key
            current_configs[key] = value
            
            # Save back the entire config
            await self.update_configs(user_id, current_configs)
            return True
        except Exception as e:
            print(f"Error updating user config for user {user_id}, key {key}: {e}")
            return False
    async def get_channel_info(self, channel_id):
        """Get channel information by ID"""
        try:
            # This would typically fetch from Telegram API
            # For now, return basic info
            return {'title': f'Channel {channel_id}', 'id': channel_id}
        except Exception:
            return None
    async def add_queue_item(self, user_id, process_data):
        """Add a forwarding process to the queue"""
        queue_item = {
            'user_id': user_id,
            'status': 'active',
            'created_at': datetime.utcnow(),
            'process_data': process_data
        }
        result = await self.queue_col.insert_one(queue_item)
        return result.inserted_id
    async def update_queue_status(self, user_id, status):
        """Update queue status (active, completed, cancelled)"""
        return await self.queue_col.update_one(
            {'user_id': user_id, 'status': 'active'},
            {'$set': {'status': status, 'updated_at': datetime.utcnow()}}
        )
    async def get_active_queues(self):
        """Get all active forwarding processes for crash recovery"""
        return await self.queue_col.find({'status': 'active'}).to_list(length=100)
    async def remove_completed_queues(self):
        """Clean up completed/cancelled queue items older than 1 day"""
        cutoff = datetime.utcnow() - timedelta(days=1)
        result = await self.queue_col.delete_many({
            'status': {'$in': ['completed', 'cancelled']},
            'updated_at': {'$lt': cutoff}
        })
        return result.deleted_count
    def _get_plan_features(self, plan_type):
        """Get features for a specific plan type"""
        from config import Config
        return Config.PLAN_FEATURES.get(plan_type, Config.PLAN_FEATURES['free'])
    async def get_user_plan(self, user_id):
        """Get user's current plan type"""
        user = await self.premium_col.find_one({
            'user_id': int(user_id),
            'is_active': True,
            'expires_at': {'$gt': datetime.utcnow()}
        })
        return user['plan_type'] if user else 'free'
    async def can_use_ftm_mode(self, user_id):
        """Check if user can use FTM Delta mode (Pro plan only)"""
        features = await self.get_user_plan_features(user_id)
        return features.get('ftm_mode', False)
    async def can_use_ftm_alpha_mode(self, user_id):
        """Check if user can use FTM Alpha mode (pro plan required)"""
        user_plan = await self.get_user_plan(user_id)
        return user_plan in ['pro', 'plus'] or await self.is_premium_user(user_id)
    async def get_alpha_config(self, user_id):
        """Get FTM Alpha mode configuration for user"""
        config = await self.alpha_config_col.find_one({'user_id': int(user_id)})
        if not config:
            # Return default configuration
            return {
                'user_id': int(user_id),
                'enabled': False,
                'source_chat': None,
                'target_chat': None,
                'auto_forward': False
            }
        return config
    async def set_alpha_config(self, user_id, enabled=None, source_chat=None, target_chat=None, auto_forward=None):
        """Set FTM Alpha mode configuration for user"""
        update_data = {}
        if enabled is not None:
            update_data['enabled'] = enabled
        if source_chat is not None:
            update_data['source_chat'] = source_chat
        if target_chat is not None:
            update_data['target_chat'] = target_chat
        if auto_forward is not None:
            update_data['auto_forward'] = auto_forward
        
        return await self.alpha_config_col.update_one(
            {'user_id': int(user_id)},
            {'$set': update_data},
            upsert=True
        )
    async def get_forwarding_limit(self, user_id):
        """Get user's daily forwarding limit"""
        features = await self.get_user_plan_features(user_id)
        return features.get('forwarding_limit', 5)
    async def has_priority_support(self, user_id):
        """Check if user has priority support"""
        features = await self.get_user_plan_features(user_id)
        return features.get('priority_support', False)
    async def get_premium_info(self, user_id):
        """Get premium user info (alias for get_premium_user_details)"""
        return await self.get_premium_user_details(user_id)
    async def get_user_usage(self, user_id):
        """Get user's total usage count"""
        daily_usage = await self.get_daily_usage(user_id)
        return daily_usage.get('processes', 0)
    async def get_days_remaining(self, user_id):
        """Get days remaining for premium subscription"""
        premium_info = await self.get_premium_user_details(user_id)
        if premium_info and premium_info.get('expires_at'):
            from datetime import datetime
            expires_at = premium_info['expires_at']
            if isinstance(expires_at, datetime):
                days_remaining = max(0, (expires_at - datetime.utcnow()).days)
                return days_remaining
        return 0
    async def add_trial_processes(self, user_id, additional_processes=1):
        """Add trial processes to user's monthly limit (legacy method)"""
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Check if trial already activated this month
        existing = await self.usage_col.find_one({
            'user_id': int(user_id), 
            'date': start_of_month,
            'trial_activated': True
        })

        if existing:
            return False  # Trial already claimed this month

        await self.usage_col.update_one(
            {'user_id': int(user_id), 'date': start_of_month},
            {
                '$set': {
                    'trial_processes': additional_processes, 
                    'trial_activated': True, 
                    'trial_granted_at': datetime.utcnow()
                },
                '$setOnInsert': {'processes': 0}
            },
            upsert=True
        )
        return True  # Trial successfully granted
    async def activate_3day_trial(self, user_id):
        """Activate 3-day premium trial (once per year)"""
        current_year = datetime.utcnow().year

        # Check if user already used trial this year
        existing_trial = await self.premium_col.find_one({
            'user_id': int(user_id),
            'plan_type': '3day_trial',
            'trial_year': current_year
        })

        if existing_trial:
            return False, "Trial already used this year"

        # Check if user currently has premium
        if await self.is_premium_user(user_id):
            return False, "Already has premium access"

        # Grant 3-day premium trial
        expires_at = datetime.utcnow() + timedelta(days=3)

        trial_data = {
            'user_id': int(user_id),
            'plan_type': '3day_trial',
            'duration_days': 3,
            'amount_paid': 0,
            'subscribed_at': datetime.utcnow(),
            'expires_at': expires_at,
            'is_active': True,
            'auto_renew': False,
            'trial_year': current_year,
            'features': {
                'forwarding_limit': -1,  # unlimited
                'ftm_mode': False,  # No FTM mode in trial
                'priority_support': False,
                'unlimited_forwarding': True
            }
        }

        result = await self.premium_col.insert_one(trial_data)
        return True, "3-day trial activated successfully"
    async def can_use_3day_trial(self, user_id):
        """Check if user can activate 3-day trial"""
        return await self.can_use_trial(user_id)
    async def get_user_process_limit(self, user_id):
        """Get user's total process limit including trials"""
        base_limit = await self.get_forwarding_limit(user_id)
        if base_limit == -1:  # Premium user
            return -1

        # Check for trial processes
        monthly_usage = await self.get_monthly_usage(user_id)
        trial_processes = monthly_usage.get('trial_processes', 0)
        return base_limit + trial_processes
    async def cleanup_expired_premium(self):
        """Remove expired premium subscriptions"""
        result = await self.premium_col.update_many(
            {'expires_at': {'$lt': datetime.utcnow()}},
            {'$set': {'is_active': False}}
        )
        return result.modified_count
    async def get_pending_verifications(self):
        """Get all pending payment verifications"""
        return await self.payment_col.find({'status': 'pending'}).to_list(length=100)
    async def increment_usage(self, user_id):
        """Increment user's monthly usage"""
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        await self.usage_col.update_one(
            {'user_id': int(user_id), 'date': start_of_month},
            {
                '$inc': {'processes': 1},
                '$set': {'last_used': datetime.utcnow()}
            },
            upsert=True
        )
    async def can_user_process(self, user_id):
        """Check if user can process based on their plan (including trial processes)"""
        # Get user's total forwarding limit (including trial processes)
        limit = await self.get_user_process_limit(user_id)

        # Unlimited for premium plans (Plus and Pro)
        if limit == -1:
            return True, "unlimited"

        # Check monthly usage for free users
        usage = await self.get_monthly_usage(user_id)
        if usage['processes'] >= limit:
            return False, "monthly_limit_reached"

        return True, "allowed"
    async def create_contact_request(self, user_id):
        """Create a new contact request"""
        contact_data = {
            'user_id': int(user_id),
            'status': 'pending',
            'created_at': datetime.utcnow(),
            'reviewed_at': None,
            'reviewed_by': None
        }

        result = await self.contact_requests_col.insert_one(contact_data)
        return result.inserted_id
    async def get_pending_contact_request(self, user_id):
        """Get pending contact request for user"""
        return await self.contact_requests_col.find_one({
            'user_id': int(user_id),
            'status': 'pending'
        })
    async def get_contact_request_by_id(self, request_id):
        """Get contact request by ID"""
        return await self.contact_requests_col.find_one({
            '_id': ObjectId(request_id)
        })
    async def update_contact_request_status(self, request_id, status):
        """Update contact request status"""
        return await self.contact_requests_col.update_one(
            {'_id': ObjectId(request_id)},
            {
                '$set': {
                    'status': status,
                    'reviewed_at': datetime.utcnow()
                }
            }
        )
    def _generate_referral_code(self, user_id):
        """Generate unique referral code: ftmbotzx + 4 random chars = 12 total"""
        import random
        import string
        
        # Generate 4 random alphanumeric characters (ftmbotzx = 8 chars + 4 = 12 total)
        random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        code = f"ftmbotzx{random_chars}"
        logger.info(f"Generated referral code {code} for user {user_id}")
        return code
    async def create_referral_code(self, user_id):
        """Create and assign referral code to user"""
        try:
            # Check if user already has referral code
            user = await self.get_user(user_id)
            if user and user.get('referral_code'):
                logger.info(f"User {user_id} already has referral code: {user['referral_code']}")
                return user['referral_code']
            
            # Generate unique referral code
            max_attempts = 10
            for attempt in range(max_attempts):
                referral_code = self._generate_referral_code(user_id)
                
                # Check if code already exists
                existing_user = await self.col.find_one({'referral_code': referral_code})
                if not existing_user:
                    # Assign code to user
                    result = await self.col.update_one(
                        {'id': int(user_id)},
                        {'$set': {'referral_code': referral_code}},
                        upsert=True
                    )
                    
                    if result.matched_count > 0 or result.upserted_id:
                        logger.info(f"Assigned referral code {referral_code} to user {user_id}")
                        return referral_code
                    else:
                        logger.warning(f"Failed to assign referral code on attempt {attempt + 1}")
            
            # Fallback: use user_id in code if all random attempts fail
            referral_code = f"ftmbotzx{str(user_id)[-4:].zfill(4)}"
            await self.col.update_one(
                {'id': int(user_id)},
                {'$set': {'referral_code': referral_code}},
                upsert=True
            )
            logger.info(f"Assigned fallback referral code {referral_code} to user {user_id}")
            return referral_code
            
        except Exception as e:
            logger.error(f"Error creating referral code for user {user_id}: {e}")
            # Emergency fallback
            fallback_code = f"ftmbotzx{str(user_id)[-4:].zfill(4)}"
            return fallback_code
    async def get_referral_code(self, user_id):
        """Get user's referral code, create if doesn't exist"""
        user = await self.get_user(user_id)
        if user and user.get('referral_code'):
            return user['referral_code']
        
        # Create new referral code
        return await self.create_referral_code(user_id)
    async def set_user_referred_by(self, user_id, referral_code):
        """Set who referred this user"""
        try:
            logger.info(f"Setting referral for user {user_id} with code {referral_code}")
            
            # First ensure the user has a referral code created if they don't have one
            await self.create_referral_code(user_id)
            
            # Find the referring user
            referring_user = await self.get_user_by_referral_code(referral_code)
            if not referring_user:
                logger.error(f"No user found with referral code: {referral_code}")
                return False
            
            referring_user_id = referring_user['id']
            logger.info(f"Found referring user: {referring_user_id}")
            
            # Don't allow self-referral
            if int(referring_user_id) == int(user_id):
                logger.warning(f"Self-referral attempt blocked for user {user_id}")
                return False
            
            # Check if this user already has any referral record
            existing_user_data = await self.get_user(user_id)
            if existing_user_data and existing_user_data.get('referred_by'):
                logger.warning(f"User {user_id} already has a referrer: {existing_user_data.get('referred_by')}")
                return False
            
            # Check if referral tracking record already exists
            existing_referral = await self.referral_col.find_one({
                'referred_user_id': int(user_id)
            })
            
            if existing_referral:
                logger.warning(f"User {user_id} already has a referral tracking record")
                return False
            
            # Update the referred user in the users collection
            update_result = await self.col.update_one(
                {'id': int(user_id)},
                {'$set': {
                    'referred_by': int(referring_user_id),
                    'referral_completed': False
                }},
                upsert=True
            )
            
            logger.info(f"✅ Updated user {user_id} referred_by field to {referring_user_id}")
            
            # Create referral tracking record
            referral_data = {
                'referrer_user_id': int(referring_user_id),
                'referred_user_id': int(user_id),
                'referral_code': referral_code,
                'created_at': datetime.utcnow(),
                'completed': False,
                'completed_at': None,
                'bot_started': False,
                'channels_joined': False,
                'tracking_notification_sent': False,
                'completion_notification_sent': False
            }
            
            try:
                insert_result = await self.referral_col.insert_one(referral_data)
                if insert_result.inserted_id:
                    logger.info(f"✅ Created referral tracking record: {insert_result.inserted_id} for referrer {referring_user_id} -> referred {user_id}")
                    return True
                else:
                    logger.error(f"Failed to create referral tracking record")
                    return False
            except Exception as insert_error:
                logger.error(f"Error inserting referral tracking record: {insert_error}")
                return False
            
        except Exception as e:
            logger.error(f"Error in set_user_referred_by for user {user_id} with code {referral_code}: {e}", exc_info=True)
            return False
    async def mark_referral_bot_started(self, user_id):
        """Mark that referred user has started the bot"""
        result = await self.referral_col.update_one(
            {'referred_user_id': int(user_id), 'completed': False},
            {'$set': {'bot_started': True}}
        )
        
        logger.info(f"Marked bot started for referred user {user_id}: {result.modified_count} record(s) updated")
        
        # Check if referral should be completed
        if result.modified_count > 0:
            await self._check_and_complete_referral(user_id)
    async def _check_and_complete_referral(self, user_id):
        """Check if referral is complete and mark it as such with auto-rewards"""
        referral = await self.referral_col.find_one({
            'referred_user_id': int(user_id),
            'completed': False,
            'bot_started': True,
            'channels_joined': True
        })
        
        if referral:
            logger.info(f"Completing referral for user {user_id} (referrer: {referral['referrer_user_id']})")
            
            # Complete the referral
            await self.referral_col.update_one(
                {'_id': referral['_id']},
                {'$set': {
                    'completed': True,
                    'completed_at': datetime.utcnow(),
                    'completion_notification_sent': True
                }}
            )
            
            # Update user record
            await self.col.update_one(
                {'id': int(user_id)},
                {'$set': {'referral_completed': True}}
            )
            
            # Auto-grant 1 day Plus plan to referred user
            await self.add_premium_user(
                user_id,
                plan_type="plus",
                duration_days=1,
                amount_paid="referral_welcome_bonus"
            )
            logger.info(f"Granted 1-day Plus plan to referred user {user_id}")
            
            # Check if referrer should get milestone rewards
            reward_granted, total_referrals = await self._check_auto_upgrade(referral['referrer_user_id'])
            
            return {
                'completed': True,
                'referrer_user_id': referral['referrer_user_id'],
                'referred_user_id': user_id,
                'reward_granted': reward_granted,
                'total_referrals': total_referrals
            }
        
        logger.warning(f"No valid referral found for user {user_id} to complete")
        return False
    async def _check_auto_upgrade(self, referrer_user_id):
        """Check if user should get auto-upgraded for reaching milestones"""
        # Count completed referrals
        completed_count = await self.referral_col.count_documents({
            'referrer_user_id': int(referrer_user_id),
            'completed': True
        })
        
        # Check if user should get upgrade
        reward_granted = False
        
        # 15 referrals = Plus plan (30 days)
        if completed_count == 15:
            # Check if user already has this reward
            existing_reward = await self.premium_col.find_one({
                'user_id': int(referrer_user_id),
                'referral_milestone': 15
            })
            
            if not existing_reward:
                # Auto-upgrade to Plus plan for 30 days
                result = await self.premium_col.insert_one({
                    'user_id': int(referrer_user_id),
                    'plan_type': 'plus',
                    'duration_days': 30,
                    'amount_paid': 'referral_15_milestone',
                    'subscribed_at': datetime.utcnow(),
                    'expires_at': datetime.utcnow() + timedelta(days=30),
                    'is_active': True,
                    'auto_renew': False,
                    'referral_milestone': 15,
                    'features': self._get_plan_features('plus')
                })
                reward_granted = True
                logger.info(f"Auto-granted Plus 30d to user {referrer_user_id} for 15 referrals")
        
        # 30 referrals = Pro plan (15 days)
        elif completed_count == 30:
            # Check if user already has this reward
            existing_reward = await self.premium_col.find_one({
                'user_id': int(referrer_user_id),
                'referral_milestone': 30
            })
            
            if not existing_reward:
                # Auto-upgrade to Pro plan for 15 days
                result = await self.premium_col.insert_one({
                    'user_id': int(referrer_user_id),
                    'plan_type': 'pro',
                    'duration_days': 15,
                    'amount_paid': 'referral_30_milestone',
                    'subscribed_at': datetime.utcnow(),
                    'expires_at': datetime.utcnow() + timedelta(days=15),
                    'is_active': True,
                    'auto_renew': False,
                    'referral_milestone': 30,
                    'features': self._get_plan_features('pro')
                })
                reward_granted = True
                logger.info(f"Auto-granted Pro 15d to user {referrer_user_id} for 30 referrals")
        
        return reward_granted, completed_count
    async def get_referral_stats(self, user_id):
        """Get comprehensive referral statistics for user"""
        # Get completed referrals
        completed_referrals = await self.referral_col.find({
            'referrer_user_id': int(user_id),
            'completed': True
        }).to_list(length=100)
        
        # Get pending referrals (started but not completed)
        pending_referrals = await self.referral_col.find({
            'referrer_user_id': int(user_id),
            'completed': False
        }).to_list(length=100)
        
        # Get user's referral code
        user_code = await self.get_referral_code(user_id)
        
        # Calculate stats
        total_completed = len(completed_referrals)
        total_pending = len(pending_referrals)
        remaining_for_reward = max(0, 15 - total_completed)
        
        # Check if already got reward
        has_received_reward = total_completed >= 15
        
        return {
            'referral_code': user_code,
            'total_completed': total_completed,
            'total_pending': total_pending,
            'remaining_for_reward': remaining_for_reward,
            'has_received_reward': has_received_reward,
            'completed_referrals': completed_referrals,
            'pending_referrals': pending_referrals
        }
    async def get_referral_leaderboard(self, limit=10):
        """Get top referrers leaderboard"""
        pipeline = [
            {
                '$match': {'completed': True}
            },
            {
                '$group': {
                    '_id': '$referrer_user_id',
                    'total_referrals': {'$sum': 1}
                }
            },
            {
                '$sort': {'total_referrals': -1}
            },
            {
                '$limit': limit
            }
        ]
        
        return await self.referral_col.aggregate(pipeline).to_list(length=limit)
    async def is_referral_completed(self, user_id):
        """Check if user's referral is completed"""
        user = await self.get_user(user_id)
        return user.get('referral_completed', False) if user else False
    async def has_incomplete_referral(self, user_id):
        """Check if user has an incomplete referral that needs completion"""
        # Check user record
        user = await self.get_user(user_id)
        if not user or not user.get('referred_by') or user.get('referral_completed'):
            return False
        
        # Check referral tracking record
        referral = await self.referral_col.find_one({
            'referred_user_id': int(user_id),
            'completed': False
        })
        
        return referral is not None
    async def get_referrer_of_user(self, user_id):
        """Get who referred this user"""
        user = await self.get_user(user_id)
        if user and user.get('referred_by'):
            return await self.get_user(user['referred_by'])
        return None
    async def get_all_referrals(self, user_id):
        """Get all referrals made by a specific user"""
        referrals = await self.referral_col.find({
            'referrer_user_id': int(user_id)
        }).to_list(length=100)
        return referrals
    # ============ end ported block ============

db = Database(Config.DATABASE_URI, Config.DATABASE_NAME)
