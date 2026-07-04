import os
import secrets
import requests
import pytz
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Optional, NumberRange, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from pymongo import MongoClient
from datetime import datetime, timedelta
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('ADMIN_SECRET_KEY', secrets.token_hex(32))
app.config['WTF_CSRF_ENABLED'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

client = MongoClient(Config.DATABASE_URI)
db = client[Config.DATABASE_NAME]

# Owner credentials
OWNER_USERNAME = Config.OWNER_USERNAME
OWNER_PASSWORD_HASH = generate_password_hash(Config.OWNER_PASSWORD)

class AdminUser(UserMixin):
    def __init__(self, user_id, username, role='admin'):
        self.id = str(user_id)
        self.username = username
        self.role = role

    def is_owner(self):
        return self.role == 'owner'

@login_manager.user_loader
def load_user(user_id):
    if user_id == 'owner':
        return AdminUser('owner', OWNER_USERNAME, 'owner')

    # Load from database
    admin = db.admins.find_one({'user_id': int(user_id)})
    if admin and admin.get('is_active', True):
        return AdminUser(admin['user_id'], admin['username'], 'admin')
    return None

def owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_owner():
            flash('Owner access required', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def to_small_caps(text):
    """Convert text to unicode small caps"""
    normal = "abcdefghijklmnopqrstuvwxyz"
    small_caps = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal + normal.upper(), small_caps + small_caps)
    return text.translate(trans)

def send_telegram_notification(user_id, message):
    """Send notification to specific user"""
    try:
        bot_token = Config.BOT_TOKEN
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {"chat_id": user_id, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        logging.error(f"Failed to send notification to user {user_id}: {e}")
def send_telegram_log(message, log_type="info", skip_log_channel=False):
    """Send activity log to Telegram"""
    try:
        bot_token = Config.BOT_TOKEN
        log_channel = Config.LOG_CHANNEL

        emoji = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌", "action": "🔧"}
        icon = emoji.get(log_type, "📝")

        from datetime import datetime
        import pytz
        ist = pytz.timezone('Asia/Kolkata')
        ist_time = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(ist)
        date_str = ist_time.strftime('%d-%m-%Y')
        time_str = ist_time.strftime('%I:%M:%S %p')

        admin_name = current_user.username if current_user.is_authenticated else 'sʏsᴛᴇᴍ'

        text = f"""
{icon} <b>{to_small_caps('admin panel activity')}</b>

📋 <b>{to_small_caps('action')}:</b> {message}
📅 <b>{to_small_caps('date')}:</b> {date_str}
⏰ <b>{to_small_caps('time')}:</b> {time_str}
👤 <b>{to_small_caps('admin')}:</b> {admin_name}
        """.strip()

        if not skip_log_channel:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {"chat_id": log_channel, "text": text, "parse_mode": "HTML"}
            requests.post(url, data=data, timeout=5)

        db.admin_logs.insert_one({
            "message": message,
            "log_type": log_type,
            "timestamp": datetime.utcnow(),
            "admin": admin_name,
            "read": False
        })
    except Exception as e:
        db.admin_logs.insert_one({
            "message": message,
            "log_type": log_type,
            "timestamp": datetime.utcnow(),
            "admin": admin_name if current_user.is_authenticated else 'sʏsᴛᴇᴍ',
            "telegram_error": str(e),
            "read": False
        })

def log_activity(message, log_type="info"):
    send_telegram_log(message, log_type)

    # Also log system errors
    if log_type in ['error', 'warning']:
        try:
            db.admin_logs.update_one(
                {'message': message, 'timestamp': {'$exists': True}},
                {'$set': {'read': False}},
                upsert=False
            )
        except Exception:
            pass

def calculate_expiry(duration_value, duration_unit):
    now = datetime.utcnow()
    if duration_unit == "minutes":
        return now + timedelta(minutes=duration_value)
    elif duration_unit == "hours":
        return now + timedelta(hours=duration_value)
    elif duration_unit == "days":
        return now + timedelta(days=duration_value)
    elif duration_unit == "weeks":
        return now + timedelta(weeks=duration_value)
    elif duration_unit == "months":
        return now + timedelta(days=duration_value * 30)
    elif duration_unit == "years":
        return now + timedelta(days=duration_value * 365)
    else:
        return now + timedelta(days=duration_value)

def format_duration(value, unit):
    return f"{value} {unit}"

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class CreateAdminForm(FlaskForm):
    user_id = IntegerField('User ID', validators=[DataRequired()])
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Create Admin')

class SubscriptionForm(FlaskForm):
    user_id = IntegerField('User ID', validators=[DataRequired()])
    plan = SelectField('Plan', choices=[('free', 'Free'), ('plus', 'Plus'), ('pro', 'Pro'), ('infinity', 'Infinity')])
    duration_value = IntegerField('Duration Value', validators=[Optional(), NumberRange(min=1, max=999)], default=30)
    duration_unit = SelectField('Duration Unit', choices=[
        ('minutes', 'Minutes'), ('hours', 'Hours'), ('days', 'Days'),
        ('weeks', 'Weeks'), ('months', 'Months'), ('years', 'Years')
    ], default='days')
    lifetime = SelectField('Lifetime', choices=[('no', 'No'), ('yes', 'Yes')])
    submit = SubmitField('Update Plan')

class BanForm(FlaskForm):
    user_id = IntegerField('User ID', validators=[DataRequired()])
    reason = StringField('Ban Reason')
    submit = SubmitField('Ban User')

class RevokePlanForm(FlaskForm):
    user_id = IntegerField('User ID', validators=[DataRequired()])
    submit = SubmitField('Revoke Plan')

class FtmBucksForm(FlaskForm):
    user_id = IntegerField('User ID', validators=[DataRequired()])
    amount = IntegerField('Amount', validators=[DataRequired()])
    action = SelectField('Action', choices=[('add', 'Add'), ('deduct', 'Deduct'), ('set', 'Set')])
    submit = SubmitField('Update FTM Bucks')

def get_safe(obj, *keys, default=None):
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key, default)
        else:
            return default
    return obj if obj is not None else default

@app.context_processor
def utility_processor():
    """Inject common variables into all templates"""
    from platform import python_version

    # Get bot info
    try:
        bot_info = db.bot_info.find_one({})
        if not bot_info:
            bot_info = {'name': 'ғᴛᴍ ʙᴏᴛ', 'username': 'ftmbotzx'}
    except Exception:
        bot_info = {'name': 'ғᴛᴍ ʙᴏᴛ', 'username': 'ftmbotzx'}

    # Get Pyrogram version without importing it (to avoid asyncio conflict)
    try:
        import importlib.metadata
        pyrogram_ver = importlib.metadata.version('pyrogram')
    except Exception:
        pyrogram_ver = '2.0.93'

    # Get MongoDB version
    try:
        x = MongoClient(Config.DATABASE_URI)
        mongodb_ver = x.server_info()['version']
        x.close()
    except Exception:
        mongodb_ver = 'N/A'

    owner_id = Config.BOT_OWNER_ID[0] if Config.BOT_OWNER_ID else 0

    return dict(
        get_safe=get_safe,
        current_user=current_user,
        bot_info=bot_info,
        python_ver=python_version(),
        pyrogram_ver=pyrogram_ver,
        mongodb_ver=mongodb_ver,
        owner_id=owner_id,
        bot_version=Config.BOT_VERSION
    )

@app.route('/')
@login_required
def dashboard():
    users_count = db.users.count_documents({})
    bots_count = db.bots.count_documents({})
    channels_count = db.channels.count_documents({})
    banned_count = db.users.count_documents({'ban_status.is_banned': True})

    subscription_stats = {
        'free': db.users.count_documents({'$or': [{'subscription.plan': 'free'}, {'subscription': {'$exists': False}}]}),
        'plus': db.users.count_documents({'subscription.plan': 'plus'}),
        'pro': db.users.count_documents({'subscription.plan': 'pro'}),
        'infinity': db.users.count_documents({'subscription.plan': 'infinity'})
    }

    lifetime_count = db.users.count_documents({'subscription.status': 'lifetime'})
    expired_count = db.users.count_documents({'subscription.status': 'expired'})

    recent_users = list(db.users.find().sort('joined_at', -1).limit(10))
    recent_logs = list(db.admin_logs.find().sort('timestamp', -1).limit(5))

    # Unread notifications count
    unread_notifications = db.notifications.count_documents({'read': False})

    return render_template('dashboard.html',
                         users_count=users_count,
                         bots_count=bots_count,
                         channels_count=channels_count,
                         banned_count=banned_count,
                         subscription_stats=subscription_stats,
                         lifetime_count=lifetime_count,
                         expired_count=expired_count,
                         recent_users=recent_users,
                         recent_logs=recent_logs,
                         unread_notifications=unread_notifications)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        # Check if owner
        if username == OWNER_USERNAME and check_password_hash(OWNER_PASSWORD_HASH, password):
            user = AdminUser('owner', OWNER_USERNAME, 'owner')
            login_user(user, remember=True)
            session.permanent = True
            flash('Welcome Owner!', 'success')
            log_activity("Owner logged in", "success")
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('dashboard'))

        # Check admins
        admin = db.admins.find_one({'username': username, 'is_active': True})
        if admin and check_password_hash(admin['password_hash'], password):
            user = AdminUser(admin['user_id'], admin['username'], 'admin')
            login_user(user, remember=True)
            session.permanent = True
            flash(f'Welcome {username}!', 'success')
            log_activity(f"Admin {username} logged in", "success")
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('dashboard'))

        flash('Invalid credentials', 'danger')
        log_activity(f"Failed login attempt: {username}", "warning")

    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    log_activity(f"{current_user.username} logged out", "info")
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/admins')
@login_required
@owner_required
def manage_admins():
    admins = list(db.admins.find({}))
    form = CreateAdminForm()
    unread_notifications = db.notifications.count_documents({'read': False})
    return render_template('admins.html', admins=admins, form=form, unread_notifications=unread_notifications)

@app.route('/admins/create', methods=['POST'])
@login_required
@owner_required
def create_admin():
    form = CreateAdminForm()
    if form.validate_on_submit():
        user_id = form.user_id.data
        username = form.username.data
        password = form.password.data

        # Check if user exists
        user = db.users.find_one({'id': user_id})
        if not user:
            flash(f'User {user_id} not found in database', 'danger')
            return redirect(url_for('manage_admins'))

        # Check if admin already exists
        existing = db.admins.find_one({'$or': [{'user_id': user_id}, {'username': username}]})
        if existing:
            flash('Admin already exists with this user ID or username', 'danger')
            return redirect(url_for('manage_admins'))

        # Create admin
        password_hash = generate_password_hash(password)
        admin_data = {
            'user_id': user_id,
            'username': username,
            'password_hash': password_hash,
            'role': 'admin',
            'created_at': datetime.utcnow(),
            'created_by': current_user.username,
            'is_active': True
        }

        db.admins.insert_one(admin_data)

        # Grant infinity plan
        subscription_data = {
            'plan': 'infinity',
            'status': 'lifetime',
            'expires_at': None,
            'purchased_at': datetime.utcnow(),
            'assigned_by': 'system',
            'duration_info': 'lifetime',
            'features': Config.SUBSCRIPTION_PLANS['infinity']['features']
        }

        db.users.update_one(
            {'id': user_id},
            {'$set': {'subscription': subscription_data}}
        )

        flash(f'Admin {username} created successfully with Infinity plan', 'success')
        log_activity(f"Created admin: {username} (ID: {user_id})", "action")

        # Notify user
        try:
            import requests
            text = (
                f"<b>🎉 Admin Access Granted 🎉</b>\n\n"
                f"You have been granted admin access to the panel!\n\n"
                f"<b>Username:</b> <code>{username}</code>\n"
                f"<b>Plan:</b> ♾️ Infinity (Lifetime)\n\n"
                f"Login at: {request.host_url}"
            )
            url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": user_id, "text": text, "parse_mode": "HTML"}, timeout=5)
        except Exception:
            pass

    return redirect(url_for('manage_admins'))

@app.route('/admins/<int:user_id>/toggle', methods=['POST'])
@login_required
@owner_required
def toggle_admin(user_id):
    admin = db.admins.find_one({'user_id': user_id})
    if not admin:
        flash('Admin not found', 'danger')
    else:
        new_status = not admin.get('is_active', True)
        db.admins.update_one({'user_id': user_id}, {'$set': {'is_active': new_status}})
        status_text = "activated" if new_status else "deactivated"
        flash(f'Admin {admin["username"]} {status_text}', 'success')
        log_activity(f"Admin {admin['username']} {status_text}", "action")

    return redirect(url_for('manage_admins'))

@app.route('/admins/<int:user_id>/delete', methods=['POST'])
@login_required
@owner_required
def delete_admin(user_id):
    admin = db.admins.find_one({'user_id': user_id})
    if not admin:
        flash('Admin not found', 'danger')
    else:
        db.admins.delete_one({'user_id': user_id})
        flash(f'Admin {admin["username"]} deleted', 'success')
        log_activity(f"Deleted admin: {admin['username']} (ID: {user_id})", "action")

    return redirect(url_for('manage_admins'))

@app.route('/user/<int:user_id>/promote-admin', methods=['POST'])
@login_required
@owner_required
def promote_to_admin(user_id):
    user = db.users.find_one({'id': user_id})
    if not user:
        flash(f'User {user_id} not found', 'danger')
        return redirect(url_for('users'))

    # Check if already admin
    existing = db.admins.find_one({'user_id': user_id})
    if existing:
        flash('User is already an admin', 'warning')
        return redirect(url_for('user_detail', user_id=user_id))

    # Generate default password
    import secrets
    password = secrets.token_urlsafe(8)
    password_hash = generate_password_hash(password)
    username = user.get('name', f'admin_{user_id}').replace(' ', '_').lower()

    # Create admin
    admin_data = {
        'user_id': user_id,
        'username': username,
        'password_hash': password_hash,
        'role': 'admin',
        'created_at': datetime.utcnow(),
        'created_by': current_user.username,
        'is_active': True
    }

    db.admins.insert_one(admin_data)

    # Grant infinity plan
    subscription_data = {
        'plan': 'infinity',
        'status': 'lifetime',
        'expires_at': None,
        'purchased_at': datetime.utcnow(),
        'assigned_by': 'system',
        'duration_info': 'lifetime',
        'features': Config.SUBSCRIPTION_PLANS['infinity']['features']
    }

    db.users.update_one(
        {'id': user_id},
        {'$set': {'subscription': subscription_data}}
    )

    flash(f'User promoted to admin! Username: {username}, Password: {password} (save this!)', 'success')
    log_activity(f"Promoted user {user_id} to admin: {username}", "action")

    # Notify user
    try:
        import requests
        text = (
            f"<b>🎉 Admin Access Granted 🎉</b>\n\n"
            f"You have been promoted to admin!\n\n"
            f"<b>Username:</b> <code>{username}</code>\n"
            f"<b>Password:</b> <code>{password}</code>\n"
            f"<b>Plan:</b> ♾️ Infinity (Lifetime)\n\n"
            f"Login at: {request.host_url}\n\n"
            f"⚠️ Please change your password after first login."
        )
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": user_id, "text": text, "parse_mode": "HTML"}, timeout=5)
    except Exception:
        pass

    # Store in chat
    db.chats.insert_one({
        "user_id": user_id,
        "sender_type": "system",
        "sender_name": "sʏsᴛᴇᴍ",
        "message": f"🎉 {to_small_caps('promoted to admin')} - ᴜsᴇʀɴᴀᴍᴇ: {username}",
        "timestamp": datetime.utcnow(),
        "read": True,
        "notification_type": "admin_promotion"
    })

    return redirect(url_for('user_detail', user_id=user_id))

@app.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search', '')
    filter_type = request.args.get('filter', '')

    query = {}
    if search:
        query = {'$or': [
            {'message': {'$regex': search, '$options': 'i'}},
            {'admin': {'$regex': search, '$options': 'i'}}
        ]}

    if filter_type:
        query['log_type'] = filter_type

    total_notifications = db.admin_logs.count_documents(query)
    notifications_list = list(db.admin_logs.find(query).sort('timestamp', -1).skip((page - 1) * per_page).limit(per_page))
    total_pages = max(1, (total_notifications + per_page - 1) // per_page)

    unread_count = db.admin_logs.count_documents({'read': False})

    # Mark current page as read
    notification_ids = [n['_id'] for n in notifications_list]
    db.admin_logs.update_many(
        {'_id': {'$in': notification_ids}, 'read': False},
        {'$set': {'read': True}}
    )

    # Convert ObjectId to string for JSON serialization
    for notification in notifications_list:
        if '_id' in notification:
            notification['_id'] = str(notification['_id'])

    return render_template('notifications.html',
                         notifications=notifications_list,
                         page=page,
                         total_pages=total_pages,
                         search=search,
                         filter_type=filter_type,
                         unread_notifications=unread_count)

# Include all existing routes from original app.py
# (users, subscriptions, bans, ftm_bucks, etc.)

@app.route('/users')
@login_required
def users():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search', '')
    filter_type = request.args.get('filter', '')

    query = {}
    if search:
        try:
            search_id = int(search)
            query = {'$or': [{'id': search_id}, {'name': {'$regex': search, '$options': 'i'}}]}
        except ValueError:
            query = {'name': {'$regex': search, '$options': 'i'}}

    if filter_type == 'banned':
        query['ban_status.is_banned'] = True
    elif filter_type == 'subscribed':
        query['subscription.plan'] = {'$ne': 'free'}
    elif filter_type == 'lifetime':
        query['subscription.status'] = 'lifetime'
    elif filter_type == 'expired':
        query['subscription.status'] = 'expired'

    total_users = db.users.count_documents(query)
    users_list = list(db.users.find(query).skip((page - 1) * per_page).limit(per_page))
    total_pages = max(1, (total_users + per_page - 1) // per_page)

    unread_notifications = db.notifications.count_documents({'read': False})

    return render_template('users.html',
                         users=users_list,
                         page=page,
                         total_pages=total_pages,
                         search=search,
                         filter_type=filter_type,
                         unread_notifications=unread_notifications)

@app.route('/user/<int:user_id>')
@login_required
def user_detail(user_id):
    user = db.users.find_one({'id': user_id})
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('users'))

    user_channels = list(db.channels.find({'user_id': user_id}))
    user_bot = db.bots.find_one({'user_id': user_id})
    unread_notifications = db.notifications.count_documents({'read': False})

    return render_template('user_detail.html', user=user, channels=user_channels, bot=user_bot, unread_notifications=unread_notifications)

@app.route('/subscriptions', methods=['GET', 'POST'])
@login_required
def subscriptions():
    form = SubscriptionForm()
    revoke_form = RevokePlanForm()

    if form.validate_on_submit() and 'update_plan' in request.form:
        user_id = form.user_id.data
        plan = form.plan.data
        duration_value = form.duration_value.data or 30
        duration_unit = form.duration_unit.data or 'days'
        is_lifetime = form.lifetime.data == 'yes'

        user = db.users.find_one({'id': user_id})
        if not user:
            flash(f'User {user_id} not found', 'danger')
            log_activity(f"Failed to update plan: User {user_id} not found", "error")
        else:
            expires_at = None  # Initialize expires_at
            
            if plan == 'free':
                subscription_data = {
                    'plan': 'free',
                    'status': 'active',
                    'expires_at': None,
                    'purchased_at': None,
                    'assigned_by': 'admin_panel',
                    'duration_info': None,
                    'features': Config.SUBSCRIPTION_PLANS['free']['features']
                }
                duration_text = 'Free plan'
            elif is_lifetime:
                subscription_data = {
                    'plan': plan,
                    'status': 'lifetime',
                    'expires_at': None,
                    'purchased_at': datetime.utcnow(),
                    'assigned_by': 'admin_panel',
                    'duration_info': 'lifetime',
                    'features': Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])['features']
                }
                duration_text = 'lifetime'
            else:
                expires_at = calculate_expiry(duration_value, duration_unit)
                subscription_data = {
                    'plan': plan,
                    'status': 'active',
                    'expires_at': expires_at,
                    'purchased_at': datetime.utcnow(),
                    'assigned_by': 'admin_panel',
                    'duration_info': f"{duration_value} {duration_unit}",
                    'features': Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])['features']
                }
                duration_text = format_duration(duration_value, duration_unit)

            db.users.update_one({'id': user_id}, {'$set': {'subscription': subscription_data}})
            flash(f'Updated subscription for user {user_id} to {plan.upper()} ({duration_text})', 'success')
            log_activity(f"Updated user {user_id} subscription to {plan.upper()} ({duration_text})", "success")

            # Notify user
            plan_info = Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])
            user_notification = f"""<b>🎉 {to_small_caps('subscription updated')} 🎉</b>

{to_small_caps('your subscription plan has been updated!')}

<b>💎 {to_small_caps('new plan')}:</b> {plan_info['emoji']} {plan_info['name']}
<b>⏰ {to_small_caps('duration')}:</b> {duration_text}"""

            if expires_at and not is_lifetime:
                import pytz
                ist = pytz.timezone('Asia/Kolkata')
                if expires_at.tzinfo is None:
                    expires_at = pytz.utc.localize(expires_at)
                expiry_ist = expires_at.astimezone(ist)
                expiry_date = expiry_ist.strftime('%d-%m-%Y')
                expiry_time = expiry_ist.strftime('%I:%M:%S %p')
                user_notification += f"\n<b>⌛️ {to_small_caps('expires on')}:</b> {expiry_date} {to_small_caps('at')} {expiry_time}"
            elif is_lifetime:
                user_notification += f"\n<b>⌛️ {to_small_caps('expiry')}:</b> ♾️ {to_small_caps('lifetime')}"

            user_notification += f"\n\n<b>👨‍💼 {to_small_caps('updated by')}:</b> {current_user.username}\n\n<i>✨ {to_small_caps('enjoy your premium features!')} ✨</i>"

            send_telegram_notification(user_id, user_notification)

            # Store in chat
            db.chats.insert_one({
                "user_id": user_id,
                "sender_type": "system",
                "sender_name": "sʏsᴛᴇᴍ",
                "message": f"💎 {to_small_caps('plan updated to')} {plan_info['name']} ({duration_text})",
                "timestamp": datetime.utcnow(),
                "read": True,
                "notification_type": "plan_update"
            })

    subscribed_users = list(db.users.find({'subscription.plan': {'$ne': 'free'}}).limit(50))
    unread_notifications = db.notifications.count_documents({'read': False})

    return render_template('subscriptions.html', form=form, revoke_form=revoke_form, subscribed_users=subscribed_users, unread_notifications=unread_notifications)

@app.route('/revoke-plan', methods=['POST'])
@login_required
def revoke_plan():
    user_id = request.form.get('user_id', type=int)
    if not user_id:
        flash('User ID is required', 'danger')
        return redirect(url_for('subscriptions'))

    user = db.users.find_one({'id': user_id})
    if not user:
        flash(f'User {user_id} not found', 'danger')
        log_activity(f"Failed to revoke plan: User {user_id} not found", "error")
    else:
        old_plan = get_safe(user, 'subscription', 'plan', default='free')
        subscription_data = {
            'plan': 'free',
            'status': 'active',
            'expires_at': None,
            'purchased_at': None,
            'assigned_by': 'admin_panel',
            'duration_info': None,
            'features': Config.SUBSCRIPTION_PLANS['free']['features']
        }
        db.users.update_one({'id': user_id}, {'$set': {'subscription': subscription_data}})
        flash(f'Revoked subscription for user {user_id}. Now on FREE plan.', 'success')
        log_activity(f"Revoked user {user_id} subscription from {old_plan.upper()} to FREE", "action")

    return redirect(url_for('subscriptions'))

@app.route('/bans', methods=['GET', 'POST'])
@login_required
def bans():
    form = BanForm()

    if form.validate_on_submit():
        user_id = form.user_id.data
        reason = form.reason.data or "ɴᴏ ʀᴇᴀsᴏɴ ᴘʀᴏᴠɪᴅᴇᴅ"

        user = db.users.find_one({'id': user_id})
        if not user:
            flash(f'User {user_id} not found', 'danger')
            log_activity(f"Failed to ban: User {user_id} not found", "error")
        else:
            db.users.update_one(
                {'id': user_id},
                {'$set': {'ban_status': {'is_banned': True, 'ban_reason': reason}}}
            )
            flash(f'User {user_id} has been banned', 'success')

            user_name = user.get('name', 'Unknown')

            # Send to log channel with formatting
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            ist_time = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(ist)
            date_str = ist_time.strftime('%d-%m-%Y')
            time_str = ist_time.strftime('%I:%M:%S %p')

            log_message = f"""<b>#ᴜsᴇʀ_ʙᴀɴɴᴇᴅ 🚫</b>

👤 <b>{to_small_caps('user')}:</b> {user_name}
⚡ <b>{to_small_caps('user id')}:</b> <code>{user_id}</code>
📝 <b>{to_small_caps('reason')}:</b> {reason}

👨‍💼 <b>{to_small_caps('banned by')}:</b> {current_user.username}
📅 <b>{to_small_caps('date')}:</b> {date_str}
⏰ <b>{to_small_caps('time')}:</b> {time_str}"""

            try:
                url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
                requests.post(url, data={"chat_id": Config.LOG_CHANNEL, "text": log_message, "parse_mode": "HTML"}, timeout=5)
            except Exception:
                pass

            # Notify user
            ban_notification = f"""<b>🚫 {to_small_caps('account banned')} 🚫</b>

{to_small_caps('your account has been banned from using the bot.')}

<b>📝 {to_small_caps('reason')}:</b> {reason}

<b>👨‍💼 {to_small_caps('banned by')}:</b> {current_user.username}
<b>📅 {to_small_caps('date')}:</b> {date_str}
<b>⏰ {to_small_caps('time')}:</b> {time_str}

<i>💬 {to_small_caps('contact support if you believe this is a mistake')}:</i>
{Config.SUPPORT_GROUP}

<i>⚠️ {to_small_caps('you will not be able to use any bot features until unbanned.')}</i>"""

            send_telegram_notification(user_id, ban_notification)

            # Store in chat
            db.chats.insert_one({
                "user_id": user_id,
                "sender_type": "system",
                "sender_name": "sʏsᴛᴇᴍ",
                "message": f"🚫 {to_small_caps('banned')}: {reason}",
                "timestamp": datetime.utcnow(),
                "read": True,
                "notification_type": "ban"
            })

    banned_users = list(db.users.find({'ban_status.is_banned': True}))
    unread_notifications = db.admin_logs.count_documents({'read': False})

    return render_template('bans.html', form=form, banned_users=banned_users, unread_notifications=unread_notifications)

@app.route('/unban/<int:user_id>', methods=['POST'])
@login_required
def unban_user(user_id):
    user = db.users.find_one({'id': user_id})
    user_name = user.get('name', 'Unknown') if user else 'Unknown'

    db.users.update_one(
        {'id': user_id},
        {'$set': {'ban_status': {'is_banned': False, 'ban_reason': ''}}}
    )
    flash(f'User {user_id} has been unbanned', 'success')

    # Send to log channel
    import pytz
    ist = pytz.timezone('Asia/Kolkata')
    ist_time = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(ist)
    date_str = ist_time.strftime('%d-%m-%Y')
    time_str = ist_time.strftime('%I:%M:%S %p')

    log_message = f"""<b>#ᴜsᴇʀ_ᴜɴʙᴀɴɴᴇᴅ ✅</b>

👤 <b>{to_small_caps('user')}:</b> {user_name}
⚡ <b>{to_small_caps('user id')}:</b> <code>{user_id}</code>

👨‍💼 <b>{to_small_caps('unbanned by')}:</b> {current_user.username}
📅 <b>{to_small_caps('date')}:</b> {date_str}
⏰ <b>{to_small_caps('time')}:</b> {time_str}"""

    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": Config.LOG_CHANNEL, "text": log_message, "parse_mode": "HTML"}, timeout=5)
    except Exception:
        pass

    # Notify user
    unban_notification = f"""<b>✅ {to_small_caps('account unbanned')} ✅</b>

{to_small_caps('great news! your account has been unbanned.')}

<b>👨‍💼 {to_small_caps('unbanned by')}:</b> {current_user.username}
<b>📅 {to_small_caps('date')}:</b> {date_str}
<b>⏰ {to_small_caps('time')}:</b> {time_str}

<i>🎉 {to_small_caps('you can now use all bot features again!')}</i>"""

    send_telegram_notification(user_id, unban_notification)

    return redirect(url_for('bans'))

@app.route('/ftm-bucks', methods=['GET', 'POST'])
@login_required
def ftm_bucks():
    form = FtmBucksForm()

    if form.validate_on_submit():
        user_id = form.user_id.data
        amount = form.amount.data
        action = form.action.data

        user = db.users.find_one({'id': user_id})
        if not user:
            flash(f'User {user_id} not found', 'danger')
            log_activity(f"Failed to update FTM Bucks: User {user_id} not found", "error")
        else:
            current_bucks = get_safe(user, 'referral', 'ftm_bucks', default=0)

            if action == 'add':
                new_amount = current_bucks + amount
            elif action == 'deduct':
                new_amount = max(0, current_bucks - amount)
            else:
                new_amount = amount

            db.users.update_one({'id': user_id}, {'$set': {'referral.ftm_bucks': new_amount}})
            flash(f'Updated FTM Bucks for user {user_id}: {current_bucks} -> {new_amount}', 'success')
            log_activity(f"Updated FTM Bucks for user {user_id}: {current_bucks} -> {new_amount} ({action})", "action")

    top_users = list(db.users.find({'referral.ftm_bucks': {'$gt': 0}}).sort('referral.ftm_bucks', -1).limit(50))
    unread_notifications = db.notifications.count_documents({'read': False})

    return render_template('ftm_bucks.html', form=form, top_users=top_users, unread_notifications=unread_notifications)

@app.route('/referrals')
@login_required
def referrals():
    page = request.args.get('page', 1, type=int)
    per_page = 20

    query = {'referral.total_referrals': {'$gt': 0}}
    total_referrers = db.users.count_documents(query)
    referrers = list(db.users.find(query).sort('referral.total_referrals', -1).skip((page - 1) * per_page).limit(per_page))
    total_pages = max(1, (total_referrers + per_page - 1) // per_page)
    unread_notifications = db.notifications.count_documents({'read': False})

    return render_template('referrals.html', referrers=referrers, page=page, total_pages=total_pages, unread_notifications=unread_notifications)

@app.route('/channels')
@login_required
def channels():
    page = request.args.get('page', 1, type=int)
    per_page = 20

    total_channels = db.channels.count_documents({})
    channels_list = list(db.channels.find().skip((page - 1) * per_page).limit(per_page))
    total_pages = max(1, (total_channels + per_page - 1) // per_page)
    unread_notifications = db.notifications.count_documents({'read': False})

    return render_template('channels.html', channels=channels_list, page=page, total_pages=total_pages, unread_notifications=unread_notifications)

@app.route('/bots')
@login_required
def bots():
    page = request.args.get('page', 1, type=int)
    per_page = 20

    total_bots = db.bots.count_documents({})
    bots_list = list(db.bots.find().skip((page - 1) * per_page).limit(per_page))
    total_pages = max(1, (total_bots + per_page - 1) // per_page)
    unread_notifications = db.notifications.count_documents({'read': False})

    return render_template('bots.html', bots=bots_list, page=page, total_pages=total_pages, unread_notifications=unread_notifications)

@app.route('/activity-logs')
@login_required
def activity_logs():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    log_type_filter = request.args.get('type', '')

    query = {}
    if log_type_filter:
        query['log_type'] = log_type_filter

    total_logs = db.admin_logs.count_documents(query)
    logs = list(db.admin_logs.find(query).sort('timestamp', -1).skip((page - 1) * per_page).limit(per_page))
    total_pages = max(1, (total_logs + per_page - 1) // per_page)
    unread_notifications = db.notifications.count_documents({'read': False})

    return render_template('activity_logs.html', logs=logs, page=page, total_pages=total_pages, log_type_filter=log_type_filter, unread_notifications=unread_notifications)

@app.route('/settings')
@login_required
def settings():
    config_data = {
        'bot_version': Config.BOT_VERSION,
        'build_status': Config.BUILD_STATUS,
        'support_group': Config.SUPPORT_GROUP,
        'update_channel': Config.UPDATE_CHANNEL,
        'surveillance_mode': Config.SURVEILLANCE_MODE,
        'plus_price': Config.PLUS_PLAN_PRICE,
        'pro_price': Config.PRO_PLAN_PRICE,
        'infinity_price': Config.INFINITY_PLAN_PRICE,
        'plan_duration': Config.PLAN_DURATION_DAYS,
        'log_channel': Config.LOG_CHANNEL
    }
    unread_notifications = db.notifications.count_documents({'read': False})
    return render_template('settings.html', config=config_data, unread_notifications=unread_notifications)

@app.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    user = db.users.find_one({'id': user_id})
    user_name = user.get('name', 'Unknown') if user else 'Unknown'

    db.users.delete_many({'id': user_id})
    db.bots.delete_many({'user_id': user_id})
    db.channels.delete_many({'user_id': user_id})

    flash(f'User {user_id} and all related data deleted', 'success')
    log_activity(f"Deleted user {user_id} ({user_name}) and all related data", "action")
    return redirect(url_for('users'))

@app.route('/api/stats')
@login_required
def api_stats():
    stats = {
        'users': db.users.count_documents({}),
        'bots': db.bots.count_documents({}),
        'channels': db.channels.count_documents({}),
        'banned': db.users.count_documents({'ban_status.is_banned': True}),
        'subscriptions': {
            'free': db.users.count_documents({'$or': [{'subscription.plan': 'free'}, {'subscription': {'$exists': False}}]}),
            'plus': db.users.count_documents({'subscription.plan': 'plus'}),
            'pro': db.users.count_documents({'subscription.plan': 'pro'}),
            'infinity': db.users.count_documents({'subscription.plan': 'infinity'})
        }
    }
    return jsonify(stats)

@app.route('/api/user/<int:user_id>/update-plan', methods=['POST'])
@login_required
@csrf.exempt
def api_update_plan(user_id):
    data = request.json
    plan = data.get('plan', 'free')
    duration_value = data.get('duration_value', 30)
    duration_unit = data.get('duration_unit', 'days')
    is_lifetime = data.get('lifetime', False)

    user = db.users.find_one({'id': user_id})
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    user_name = user.get('name', 'Unknown')
    plan_info = Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])

    if plan == 'free':
        subscription_data = {
            'plan': 'free',
            'status': 'active',
            'expires_at': None,
            'purchased_at': None,
            'assigned_by': 'admin_panel',
            'duration_info': None,
            'features': Config.SUBSCRIPTION_PLANS['free']['features']
        }
        duration_text = 'ғʀᴇᴇ ᴘʟᴀɴ'
        expires_at = None
    elif is_lifetime:
        subscription_data = {
            'plan': plan,
            'status': 'lifetime',
            'expires_at': None,
            'purchased_at': datetime.utcnow(),
            'assigned_by': 'admin_panel',
            'duration_info': 'lifetime',
            'features': Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])['features']
        }
        duration_text = 'ʟɪғᴇᴛɪᴍᴇ'
        expires_at = None
    else:
        expires_at = calculate_expiry(duration_value, duration_unit)
        subscription_data = {
            'plan': plan,
            'status': 'active',
            'expires_at': expires_at,
            'purchased_at': datetime.utcnow(),
            'assigned_by': 'admin_panel',
            'duration_info': f"{duration_value} {duration_unit}",
            'features': Config.SUBSCRIPTION_PLANS.get(plan, Config.SUBSCRIPTION_PLANS['free'])['features']
        }
        duration_text = f"{duration_value} {duration_unit}"

    db.users.update_one({'id': user_id}, {'$set': {'subscription': subscription_data}})

    # Send formatted notification to log channel
    import pytz
    ist = pytz.timezone('Asia/Kolkata')
    purchased_ist = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(ist)
    joining_date = purchased_ist.strftime('%d-%m-%Y')
    joining_time = purchased_ist.strftime('%I:%M:%S %p')

    if expires_at:
        expiry_ist = expires_at.replace(tzinfo=pytz.utc).astimezone(ist)
        expiry_date = expiry_ist.strftime('%d-%m-%Y')
        expiry_time = expiry_ist.strftime('%I:%M:%S %p')
    else:
        expiry_date = "ɴᴇᴠᴇʀ"
        expiry_time = ""

    log_message = f"""<b>#ᴘʟᴀɴ_ᴜᴘᴅᴀᴛᴇᴅ</b>

👤 <b>{to_small_caps('user')}:</b> {user_name}
⚡ <b>{to_small_caps('user id')}:</b> <code>{user_id}</code>
💎 <b>{to_small_caps('plan')}:</b> {plan_info['emoji']} {plan_info['name']}
⏰ <b>{to_small_caps('duration')}:</b> {duration_text}

⏳ <b>{to_small_caps('assigned date')}:</b> {joining_date}
⏱️ <b>{to_small_caps('assigned time')}:</b> {joining_time}"""

    if expiry_time:
        log_message += f"\n\n⌛️ <b>{to_small_caps('expiry date')}:</b> {expiry_date}\n⏱️ <b>{to_small_caps('expiry time')}:</b> {expiry_time}"
    else:
        log_message += f"\n\n⌛️ <b>{to_small_caps('expiry')}:</b> {expiry_date}"

    log_message += f"\n\n👨‍💼 <b>{to_small_caps('updated by')}:</b> {current_user.username}"

    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": Config.LOG_CHANNEL, "text": log_message, "parse_mode": "HTML"}, timeout=5)
    except Exception:
        pass

    # Notify user
    user_notification = f"""<b>🎉 {to_small_caps('subscription updated')} 🎉</b>

{to_small_caps('your subscription plan has been updated!')}

<b>💎 {to_small_caps('new plan')}:</b> {plan_info['emoji']} {plan_info['name']}
<b>⏰ {to_small_caps('duration')}:</b> {duration_text}"""

    if expiry_time:
        user_notification += f"\n<b>⌛️ {to_small_caps('expires on')}:</b> {expiry_date} {to_small_caps('at')} {expiry_time}"
    else:
        user_notification += f"\n<b>⌛️ {to_small_caps('expiry')}:</b> {expiry_date}"

    user_notification += f"\n\n<b>👨‍💼 {to_small_caps('updated by')}:</b> {current_user.username}\n\n<i>✨ {to_small_caps('enjoy your premium features!')} ✨</i>"

    send_telegram_notification(user_id, user_notification)

    # Store in chat
    db.chats.insert_one({
        "user_id": user_id,
        "sender_type": "system",
        "sender_name": "sʏsᴛᴇᴍ",
        "message": f"💎 {to_small_caps('plan updated to')} {plan_info['name']} ({duration_text})",
        "timestamp": datetime.utcnow(),
        "read": True,
        "notification_type": "plan_update"
    })

    return jsonify({'success': True, 'message': f'Plan updated to {plan} ({duration_text})'})

@app.route('/api/user/<int:user_id>/toggle-ban', methods=['POST'])
@login_required
@csrf.exempt
def api_toggle_ban(user_id):
    user = db.users.find_one({'id': user_id})
    if not user:
        log_activity(f"API: Failed to toggle ban - User {user_id} not found", "error")
        return jsonify({'success': False, 'message': 'User not found'}), 404

    is_banned = get_safe(user, 'ban_status', 'is_banned', default=False)

    if is_banned:
        db.users.update_one(
            {'id': user_id},
            {'$set': {'ban_status': {'is_banned': False, 'ban_reason': ''}}}
        )
        log_activity(f"API: Unbanned user {user_id}", "success")

        # Store in chat
        db.chats.insert_one({
            "user_id": user_id,
            "sender_type": "system",
            "sender_name": "sʏsᴛᴇᴍ",
            "message": f"✅ {to_small_caps('unbanned')}",
            "timestamp": datetime.utcnow(),
            "read": True,
            "notification_type": "unban"
        })

        return jsonify({'success': True, 'message': 'User unbanned', 'banned': False})
    else:
        db.users.update_one(
            {'id': user_id},
            {'$set': {'ban_status': {'is_banned': True, 'ban_reason': 'Banned by admin'}}}
        )
        log_activity(f"API: Banned user {user_id}", "action")

        # Store in chat
        db.chats.insert_one({
            "user_id": user_id,
            "sender_type": "system",
            "sender_name": "sʏsᴛᴇᴍ",
            "message": f"🚫 {to_small_caps('banned')}",
            "timestamp": datetime.utcnow(),
            "read": True,
            "notification_type": "ban"
        })

        return jsonify({'success': True, 'message': 'User banned', 'banned': True})

@app.route('/api/user/<int:user_id>/set-lifetime', methods=['POST'])
@login_required
@csrf.exempt
def api_set_lifetime(user_id):
    user = db.users.find_one({'id': user_id})
    if not user:
        log_activity(f"API: Failed to set lifetime - User {user_id} not found", "error")
        return jsonify({'success': False, 'message': 'User not found'}), 404

    subscription_data = {
        'plan': 'infinity',
        'status': 'lifetime',
        'expires_at': None,
        'purchased_at': datetime.utcnow(),
        'assigned_by': 'admin_panel',
        'duration_info': 'lifetime',
        'features': Config.SUBSCRIPTION_PLANS['infinity']['features']
    }

    db.users.update_one({'id': user_id}, {'$set': {'subscription': subscription_data}})
    log_activity(f"API: Granted lifetime Infinity subscription to user {user_id}", "success")

    # Store in chat
    db.chats.insert_one({
        "user_id": user_id,
        "sender_type": "system",
        "sender_name": "sʏsᴛᴇᴍ",
        "message": f"♾️ {to_small_caps('lifetime subscription granted')}",
        "timestamp": datetime.utcnow(),
        "read": True,
        "notification_type": "lifetime_subscription"
    })

    return jsonify({'success': True, 'message': 'Lifetime subscription granted'})

@app.route('/api/user/<int:user_id>/revoke-plan', methods=['POST'])
@login_required
@csrf.exempt
def api_revoke_plan(user_id):
    user = db.users.find_one({'id': user_id})
    if not user:
        log_activity(f"API: Failed to revoke plan - User {user_id} not found", "error")
        return jsonify({'success': False, 'message': 'User not found'}), 404

    old_plan = get_safe(user, 'subscription', 'plan', default='free')

    subscription_data = {
        'plan': 'free',
        'status': 'active',
        'expires_at': None,
        'purchased_at': None,
        'assigned_by': 'admin_panel',
        'duration_info': None,
        'features': Config.SUBSCRIPTION_PLANS['free']['features']
    }

    db.users.update_one({'id': user_id}, {'$set': {'subscription': subscription_data}})
    log_activity(f"API: Revoked user {user_id} from {old_plan.upper()} to FREE", "action")

    # Store in chat
    db.chats.insert_one({
        "user_id": user_id,
        "sender_type": "system",
        "sender_name": "sʏsᴛᴇᴍ",
        "message": f"❌ {to_small_caps('plan revoked to free')}",
        "timestamp": datetime.utcnow(),
        "read": True,
        "notification_type": "plan_revoked"
    })

    return jsonify({'success': True, 'message': 'Plan revoked - now on FREE'})

@app.route('/api/user/<int:user_id>/update-ftm-bucks', methods=['POST'])
@login_required
@csrf.exempt
def api_update_ftm_bucks(user_id):
    data = request.json
    amount = data.get('amount', 0)
    action = data.get('action', 'set')

    user = db.users.find_one({'id': user_id})
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    user_name = user.get('name', 'Unknown')
    current_bucks = get_safe(user, 'referral', 'ftm_bucks', default=0)

    if action == 'add':
        new_amount = current_bucks + amount
        action_text = to_small_caps('added')
        emoji = "➕"
    elif action == 'deduct':
        new_amount = max(0, current_bucks - amount)
        action_text = to_small_caps('deducted')
        emoji = "➖"
    else:
        new_amount = amount
        action_text = to_small_caps('set to')
        emoji = "🔄"

    db.users.update_one({'id': user_id}, {'$set': {'referral.ftm_bucks': new_amount}})

    # Send to log channel
    import pytz
    ist = pytz.timezone('Asia/Kolkata')
    ist_time = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(ist)
    date_str = ist_time.strftime('%d-%m-%Y')
    time_str = ist_time.strftime('%I:%M:%S %p')

    log_message = f"""<b>#ғᴛᴍ_ʙᴜᴄᴋs_ᴜᴘᴅᴀᴛᴇᴅ {emoji}</b>

👤 <b>{to_small_caps('user')}:</b> {user_name}
⚡ <b>{to_small_caps('user id')}:</b> <code>{user_id}</code>

💰 <b>{to_small_caps('previous balance')}:</b> {current_bucks}
{emoji} <b>{to_small_caps('action')}:</b> {action_text} {amount}
💎 <b>{to_small_caps('new balance')}:</b> {new_amount}

👨‍💼 <b>{to_small_caps('updated by')}:</b> {current_user.username}
📅 <b>{to_small_caps('date')}:</b> {date_str}
⏰ <b>{to_small_caps('time')}:</b> {time_str}"""

    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": Config.LOG_CHANNEL, "text": log_message, "parse_mode": "HTML"}, timeout=5)
    except Exception:
        pass

    # Notify user
    user_notification = f"""<b>💰 {to_small_caps('ftm bucks updated')} 💰</b>

{to_small_caps('your ftm bucks balance has been updated!')}

<b>💰 {to_small_caps('previous balance')}:</b> {current_bucks}
<b>{emoji} {to_small_caps('change')}:</b> {action_text} {amount}
<b>💎 {to_small_caps('new balance')}:</b> {new_amount}

<b>👨‍💼 {to_small_caps('updated by')}:</b> {current_user.username}

<i>✨ {to_small_caps('use /referral to check your balance')} ✨</i>"""

    send_telegram_notification(user_id, user_notification)

    # Store in chat
    db.chats.insert_one({
        "user_id": user_id,
        "sender_type": "system",
        "sender_name": "sʏsᴛᴇᴍ",
        "message": f"{emoji} {to_small_caps('ftm bucks updated')}: {current_bucks} -> {new_amount}",
        "timestamp": datetime.utcnow(),
        "read": True,
        "notification_type": "ftm_bucks_update"
    })

    return jsonify({'success': True, 'message': f'FTM Bucks updated: {current_bucks} -> {new_amount}', 'new_amount': new_amount})

@app.route('/chats')
@login_required
def chats():
    """Chat management page"""
    user_id_param = request.args.get('user_id', type=int)
    
    # Get list of users with chats - improved query
    chat_users = list(db.chats.aggregate([
        {'$sort': {'timestamp': -1}},
        {'$group': {
            '_id': '$user_id',
            'last_message': {'$first': '$message'},
            'last_timestamp': {'$first': '$timestamp'},
            'messages': {'$push': '$$ROOT'}
        }},
        {'$sort': {'last_timestamp': -1}},
        {'$limit': 50}
    ]))
    
    # Get user details for each chat
    recent_chats = []
    for chat in chat_users:
        user = db.users.find_one({'id': chat['_id']})
        if user:
            # Count unread messages from user (sender_type = 'user')
            unread_count = sum(1 for msg in chat.get('messages', []) 
                             if not msg.get('read', False) and msg.get('sender_type') == 'user')
            
            recent_chats.append({
                'user_id': chat['_id'],
                'user_name': user.get('name', 'ᴜɴᴋɴᴏᴡɴ'),
                'last_message': chat.get('last_message', '')[:50],
                'unread_count': unread_count,
                'last_timestamp': chat.get('last_timestamp')
            })
    
    # If no chats exist, show all users (for easy access)
    if not recent_chats:
        all_users = list(db.users.find({}).sort('joined_at', -1).limit(20))
        for user in all_users:
            recent_chats.append({
                'user_id': user['id'],
                'user_name': user.get('name', 'ᴜɴᴋɴᴏᴡɴ'),
                'last_message': to_small_caps('no messages yet'),
                'unread_count': 0,
                'last_timestamp': None
            })
    
    # Get selected user details and messages
    selected_user = None
    messages = []
    
    if user_id_param:
        selected_user = db.users.find_one({'id': user_id_param})
        if selected_user:
            messages = list(db.chats.find({'user_id': user_id_param}).sort('timestamp', 1))
            # Mark messages from user as read
            db.chats.update_many(
                {'user_id': user_id_param, 'sender_type': 'user', 'read': False},
                {'$set': {'read': True}}
            )
    
    unread_notifications = db.admin_logs.count_documents({'read': False})
    
    return render_template('chats.html',
                         recent_chats=recent_chats,
                         selected_user=selected_user,
                         messages=messages,
                         unread_notifications=unread_notifications)

@app.route('/api/chat/messages/<int:user_id>')
@login_required
def api_chat_messages(user_id):
    """Get chat messages for a user with optional since filter"""
    since = request.args.get('since', '')
    
    query = {'user_id': user_id}
    if since:
        try:
            since_time = datetime.fromisoformat(since.replace('Z', '+00:00'))
            query['timestamp'] = {'$gt': since_time}
        except Exception:
            pass
    
    messages = list(db.chats.find(query).sort('timestamp', 1).limit(50))
    
    result = []
    for msg in messages:
        result.append({
            'sender_type': msg.get('sender_type', 'user'),
            'sender_name': msg.get('sender_name', 'ᴜsᴇʀ'),
            'message': msg.get('message', ''),
            'timestamp': msg.get('timestamp', datetime.utcnow()).isoformat()
        })
    
    return jsonify({'success': True, 'messages': result})

@app.route('/api/chat/send', methods=['POST'])
@login_required
@csrf.exempt
def api_chat_send():
    """Send chat message to user"""
    data = request.json
    user_id = data.get('user_id')
    message = data.get('message', '').strip()

    if not user_id or not message:
        return jsonify({'success': False, 'message': 'ᴜsᴇʀ ɪᴅ ᴀɴᴅ ᴍᴇssᴀɢᴇ ᴀʀᴇ ʀᴇǫᴜɪʀᴇᴅ'}), 400

    user = db.users.find_one({'id': int(user_id)})
    if not user:
        return jsonify({'success': False, 'message': 'ᴜsᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ'}), 404

    user_name = user.get('name', 'Unknown')

    # Format message with admin header
    formatted_message = f"""<b>📩 {to_small_caps('message from admin')} 📩</b>

<b>👨‍💼 {to_small_caps('from')}:</b> {current_user.username}

<b>💬 {to_small_caps('message')}:</b>
{message}

<i>💡 {to_small_caps('reply to this message to respond to the admin')}</i>"""

    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        response = requests.post(url, data={
            "chat_id": user_id,
            "text": formatted_message,
            "parse_mode": "HTML"
        }, timeout=5)

        if response.status_code == 200:
            # Store in chat
            db.chats.insert_one({
                "user_id": user_id,
                "sender_type": "admin",
                "sender_name": current_user.username,
                "message": message,
                "timestamp": datetime.utcnow(),
                "read": True
            })

            # Log to notification system
            log_activity(f"sᴇɴᴛ ᴄʜᴀᴛ ᴍᴇssᴀɢᴇ ᴛᴏ ᴜsᴇʀ {user_id} ({user_name})", "info")

            return jsonify({'success': True, 'message': 'ᴍᴇssᴀɢᴇ sᴇɴᴛ sᴜᴄᴄᴇssғᴜʟʟʏ'})
        else:
            return jsonify({'success': False, 'message': 'ғᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ᴍᴇssᴀɢᴇ'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'ᴇʀʀᴏʀ: {str(e)}'}), 500

@app.route('/api/send-message', methods=['POST'])
@login_required
@csrf.exempt
def api_send_message():
    data = request.json
    user_id = data.get('user_id')
    message = data.get('message', '').strip()

    if not user_id or not message:
        return jsonify({'success': False, 'message': 'User ID and message are required'}), 400

    user = db.users.find_one({'id': int(user_id)})
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    user_name = user.get('name', 'Unknown')

    # Format message with admin header
    formatted_message = f"""<b>📩 {to_small_caps('message from admin')} 📩</b>

<b>👨‍💼 {to_small_caps('from')}:</b> {current_user.username}

<b>💬 {to_small_caps('message')}:</b>
{message}

<i>💡 {to_small_caps('reply to this message to respond to the admin')}</i>"""

    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        response = requests.post(url, data={
            "chat_id": user_id,
            "text": formatted_message,
            "parse_mode": "HTML"
        }, timeout=5)

        if response.status_code == 200:
            # Log to admin panel
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            ist_time = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(ist)
            date_str = ist_time.strftime('%d-%m-%Y')
            time_str = ist_time.strftime('%I:%M:%S %p')

            log_message = f"""<b>#ᴀᴅᴍɪɴ_ᴍᴇssᴀɢᴇ_sᴇɴᴛ 📨</b>

👨‍💼 <b>{to_small_caps('admin')}:</b> {current_user.username}
👤 <b>{to_small_caps('to user')}:</b> {user_name} (<code>{user_id}</code>)

💬 <b>{to_small_caps('message')}:</b>
{message[:200]}{'...' if len(message) > 200 else ''}

📅 <b>{to_small_caps('date')}:</b> {date_str}
⏰ <b>{to_small_caps('time')}:</b> {time_str}"""

            try:
                requests.post(url, data={"chat_id": Config.LOG_CHANNEL, "text": log_message, "parse_mode": "HTML"}, timeout=5)
            except Exception:
                pass

            # Store in chat
            db.chats.insert_one({
                "user_id": user_id,
                "sender_type": "admin",
                "sender_name": current_user.username,
                "message": message,
                "timestamp": datetime.utcnow(),
                "read": False
            })

            return jsonify({'success': True, 'message': 'Message sent successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to send message'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/notification/<notification_id>')
@login_required
def notification_detail(notification_id):
    """View detailed notification"""
    from bson import ObjectId
    
    try:
        notification = db.admin_logs.find_one({'_id': ObjectId(notification_id)})
        
        if not notification:
            # Try notifications collection
            notification = db.notifications.find_one({'_id': ObjectId(notification_id)})
        
        if not notification:
            flash('Notification not found', 'danger')
            return redirect(url_for('notifications'))
        
        # Mark as read
        db.admin_logs.update_one({'_id': ObjectId(notification_id)}, {'$set': {'read': True}})
        db.notifications.update_one({'_id': ObjectId(notification_id)}, {'$set': {'read': True}})
        
        unread_notifications = db.admin_logs.count_documents({'read': False})
        
        return render_template('notification_detail.html', 
                             notification=notification,
                             unread_notifications=unread_notifications)
    except Exception as e:
        flash(f'Error loading notification: {str(e)}', 'danger')
        return redirect(url_for('notifications'))

@app.route('/api/clear-logs', methods=['POST'])
@login_required
@csrf.exempt
def api_clear_logs():
    result = db.admin_logs.delete_many({})
    log_activity(f"Cleared {result.deleted_count} activity logs", "action")
    return jsonify({'success': True, 'message': f'Cleared {result.deleted_count} logs'})

@app.route('/restart', methods=['GET', 'POST'])
@login_required
def restart_bot():
    """Restart the bot - available to both owners and admins"""
    if request.method == 'POST':
        try:
            log_activity(f"Bot restart initiated by {current_user.username}", "action")
            flash('Bot restart initiated! The bot will restart shortly.', 'success')
            
            import subprocess
            import threading
            
            def restart_process():
                import time
                time.sleep(2)
                try:
                    subprocess.Popen(['pkill', '-f', 'bot.py'])
                    time.sleep(1)
                    subprocess.Popen(['python', 'bot.py'], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                except Exception as e:
                    logging.error(f"Restart error: {e}")
            threading.Thread(target=restart_process, daemon=True).start()
            
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Error restarting bot: {str(e)}', 'danger')
            log_activity(f"Bot restart failed: {str(e)}", "error")
            return redirect(url_for('dashboard'))
    
    unread_notifications = db.admin_logs.count_documents({'read': False})
    return render_template('restart.html', unread_notifications=unread_notifications)

@app.route('/broadcast', methods=['GET', 'POST'])
@login_required
def broadcast():
    """Broadcast message to all users - available to both owners and admins"""
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        target = request.form.get('target', 'all')
        
        if not message:
            flash('Message cannot be empty', 'danger')
            return redirect(url_for('broadcast'))
        
        try:
            if target == 'all':
                users = list(db.users.find({'ban_status.is_banned': {'$ne': True}}))
            elif target == 'subscribed':
                users = list(db.users.find({
                    'subscription.plan': {'$ne': 'free'},
                    'ban_status.is_banned': {'$ne': True}
                }))
            elif target == 'free':
                users = list(db.users.find({
                    '$or': [{'subscription.plan': 'free'}, {'subscription': {'$exists': False}}],
                    'ban_status.is_banned': {'$ne': True}
                }))
            else:
                users = list(db.users.find({'ban_status.is_banned': {'$ne': True}}))
            
            success_count = 0
            fail_count = 0
            
            formatted_message = f"""<b>📢 {to_small_caps('broadcast message')} 📢</b>

<b>👨‍💼 {to_small_caps('from')}:</b> {current_user.username}

<b>💬 {to_small_caps('message')}:</b>
{message}"""
            
            for user in users:
                try:
                    url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
                    response = requests.post(url, data={
                        "chat_id": user['id'],
                        "text": formatted_message,
                        "parse_mode": "HTML"
                    }, timeout=5)
                    
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1
            
            log_activity(f"Broadcast sent to {success_count} users ({fail_count} failed) - Target: {target}", "action")
            flash(f'Broadcast sent! Success: {success_count}, Failed: {fail_count}', 'success')
            
            db.admin_logs.insert_one({
                "message": f"Broadcast to {target}: {message[:100]}...",
                "log_type": "action",
                "timestamp": datetime.utcnow(),
                "admin": current_user.username,
                "broadcast_stats": {"success": success_count, "failed": fail_count, "target": target},
                "read": False
            })
            
            return redirect(url_for('broadcast'))
        except Exception as e:
            flash(f'Error sending broadcast: {str(e)}', 'danger')
            log_activity(f"Broadcast failed: {str(e)}", "error")
            return redirect(url_for('broadcast'))
    
    users_count = db.users.count_documents({'ban_status.is_banned': {'$ne': True}})
    subscribed_count = db.users.count_documents({
        'subscription.plan': {'$ne': 'free'},
        'ban_status.is_banned': {'$ne': True}
    })
    free_count = db.users.count_documents({
        '$or': [{'subscription.plan': 'free'}, {'subscription': {'$exists': False}}],
        'ban_status.is_banned': {'$ne': True}
    })
    
    unread_notifications = db.admin_logs.count_documents({'read': False})
    return render_template('broadcast.html', 
                         users_count=users_count,
                         subscribed_count=subscribed_count,
                         free_count=free_count,
                         unread_notifications=unread_notifications)

if __name__ == '__main__':
    # Initialize owner in database if not exists
    owner_admin = db.admins.find_one({'username': OWNER_USERNAME})
    if not owner_admin:
        db.admins.insert_one({
            'user_id': 0,
            'username': OWNER_USERNAME,
            'password_hash': OWNER_PASSWORD_HASH,
            'role': 'owner',
            'created_at': datetime.utcnow(),
            'created_by': 'system',
            'is_active': True
        })

    # Grant owner infinity plan
    if Config.BOT_OWNER_ID:
        owner_user_id = Config.BOT_OWNER_ID[0]
        owner_user = db.users.find_one({'id': owner_user_id})

        if owner_user:
            current_plan = get_safe(owner_user, 'subscription', 'plan', default='free')
            if current_plan != 'infinity':
                subscription_data = {
                    'plan': 'infinity',
                    'status': 'lifetime',
                    'expires_at': None,
                    'purchased_at': datetime.utcnow(),
                    'assigned_by': 'system',
                    'duration_info': 'lifetime',
                    'features': Config.SUBSCRIPTION_PLANS['infinity']['features']
                }
                db.users.update_one(
                    {'id': owner_user_id},
                    {'$set': {'subscription': subscription_data}}
                )
                logging.info(f"✅ Granted Infinity plan to owner (ID: {owner_user_id})")
    app.run(host='0.0.0.0', port=5000, debug=True)