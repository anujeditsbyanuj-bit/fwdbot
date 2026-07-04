import logging
import asyncio
from datetime import datetime
from pyrogram.errors import FloodWait, ChatWriteForbidden, UserIsBlocked
from pyrogram import enums
from config import Config
# Import timezone conversion utilities
try:
    from plugins.timezone import get_current_ist_timestamp
except ImportError:
    # Fallback if timezone module is not available
    def get_current_ist_timestamp():
        # Manual IST calculation: UTC + 5:30
        from datetime import timedelta
        ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
        return ist_time.strftime('%Y-%m-%d %H:%M:%S IST')

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = Config.LOG_CHANNEL_ID

    async def _get_user_info(self, user_id):
        """Get formatted user information"""
        try:
            user = await self.bot.get_users(user_id)
            username = f"@{user.username}" if user.username else "No Username"
            return {
                'display': f"{user.first_name} ({username})",
                'name': user.first_name,
                'username': username,
                'id': user.id
            }
        except Exception:
            return {
                'display': f"User ID: {user_id}",
                'name': "Unknown User",
                'username': "No Username",
                'id': user_id
            }

    def _get_timestamp(self):
        """Get formatted timestamp in IST"""
        return get_current_ist_timestamp()

    def _format_header(self, icon, title, priority="INFO"):
        """Format professional notification header"""
        priority_icons = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨"
        }
        return f"<b>{icon} {title}</b>\n<b>📊 Priority:</b> {priority_icons.get(priority, 'ℹ️')} {priority}\n<b>🕒 Timestamp:</b> {self._get_timestamp()}\n{'-' * 50}"

    async def send_log_notification(self, message):
        """Send notification to log channel"""
        try:
            # Use the default log channel if none specified
            log_channel = self.log_channel_id or -1003003594014
            await self.bot.send_message(
                chat_id=log_channel,
                text=message,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send log notification: {e}")

    async def notify_process_start(self, user_id, process_type, from_chat, to_chat, additional_info=None):
        """Enhanced notification when a forwarding process starts"""
        try:
            user_info = await self._get_user_info(user_id)
            header = self._format_header("🚀", "FORWARDING PROCESS INITIATED", "INFO")

            notification = f"""{header}

<b>👤 User Information:</b>
├ <b>Name:</b> {user_info['name']}
├ <b>Username:</b> {user_info['username']}
├ <b>User ID:</b> <code>{user_info['id']}</code>
└ <b>Display:</b> {user_info['display']}

<b>🔄 Process Details:</b>
├ <b>Type:</b> {process_type}
├ <b>Source Chat:</b> <code>{from_chat}</code>
├ <b>Target Chat:</b> <code>{to_chat}</code>
└ <b>Status:</b> ✅ Process Started Successfully"""

            if additional_info:
                notification += f"\n\n<b>📋 Additional Information:</b>\n{additional_info}"

            notification += f"\n\n<b>🔍 System Status:</b> Process queue updated | Channel locks applied"

            await self.send_log_notification(notification)

        except Exception as e:
            logger.error(f"Failed to notify process start: {e}")

    async def notify_limit_exhausted(self, user_id, usage_count, next_reset_date=None):
        """Enhanced notification when user exhausts free limit"""
        try:
            user_info = await self._get_user_info(user_id)
            header = self._format_header("🚫", "FREE USAGE LIMIT REACHED", "WARNING")

            notification = f"""{header}

<b>👤 User Information:</b>
├ <b>Name:</b> {user_info['name']}
├ <b>Username:</b> {user_info['username']}
├ <b>User ID:</b> <code>{user_info['id']}</code>
└ <b>Display:</b> {user_info['display']}

<b>📊 Usage Statistics:</b>
├ <b>Current Usage:</b> {usage_count}/1 processes
├ <b>Limit Type:</b> Free Plan Monthly Limit
├ <b>Status:</b> ❌ Limit Exceeded
└ <b>Recommendation:</b> Premium Upgrade Required"""

            if next_reset_date:
                notification += f"\n\n<b>📅 Next Reset:</b> {next_reset_date}"

            notification += f"\n\n<b>💡 Action Required:</b> User should be prompted for premium upgrade"

            await self.send_log_notification(notification)

            # Also send to user
            try:
                from translation import Translation
                await self.bot.send_message(
                    chat_id=user_id,
                    text=Translation.get_premium_limit_msg()
                )
            except (ChatWriteForbidden, UserIsBlocked):
                logger.warning(f"Cannot send limit notification to user {user_id}")

        except Exception as e:
            logger.error(f"Failed to notify limit exhausted: {e}")

    async def notify_process_completed(self, user_id, process_type, from_chat, to_chat, stats, duration=None):
        """Enhanced notification when a process is completed"""
        try:
            user_info = await self._get_user_info(user_id)
            header = self._format_header("🎉", "FORWARDING PROCESS COMPLETED", "SUCCESS")

            total_processed = int(stats.get('fetched') or 0)
            forwarded = int(stats.get('forwarded') or 0)
            filtered = int(stats.get('filtered') or 0)
            duplicate = int(stats.get('duplicate') or 0)
            deleted = int(stats.get('deleted') or 0)
            success_rate = round((forwarded / total_processed * 100), 2) if total_processed > 0 else 0

            notification = f"""{header}

<b>👤 User Information:</b>
├ <b>Name:</b> {user_info['name']}
├ <b>Username:</b> {user_info['username']}
└ <b>User ID:</b> <code>{user_info['id']}</code>

<b>🔄 Process Details:</b>
├ <b>Type:</b> {process_type}
├ <b>Source Chat:</b> <code>{from_chat}</code>
├ <b>Target Chat:</b> <code>{to_chat}</code>
└ <b>Status:</b> ✅ Completed Successfully

<b>📊 Performance Statistics:</b>
├ <b>Total Fetched:</b> {total_processed} messages
├ <b>Successfully Forwarded:</b> {forwarded} messages
├ <b>Filtered Out:</b> {filtered} messages
├ <b>Duplicates Skipped:</b> {duplicate} messages
├ <b>Deleted/Errors:</b> {deleted} messages
└ <b>Success Rate:</b> {success_rate}%"""

            if duration:
                notification += f"\n\n<b>⏱️ Processing Time:</b> {duration}"

            notification += f"\n\n<b>🔍 System Status:</b> Channel locks released | Resources freed"

            await self.send_log_notification(notification)

        except Exception as e:
            logger.error(f"Failed to notify process completed: {e}")

    async def notify_user_action(self, user_id, action, details=None, category="General"):
        """Enhanced notification for user actions like settings changes, bot additions, etc."""
        try:
            user_info = await self._get_user_info(user_id)

            # Determine priority based on action type
            priority = "INFO"
            if "error" in action.lower() or "failed" in action.lower():
                priority = "WARNING"
            elif "success" in action.lower() or "completed" in action.lower():
                priority = "SUCCESS"

            header = self._format_header("👤", f"USER ACTION - {category.upper()}", priority)

            notification = f"""{header}

<b>👤 User Information:</b>
├ <b>Name:</b> {user_info['name']}
├ <b>Username:</b> {user_info['username']}
├ <b>User ID:</b> <code>{user_info['id']}</code>
└ <b>Display:</b> {user_info['display']}

<b>⚡ Action Details:</b>
├ <b>Category:</b> {category}
├ <b>Action:</b> {action}
└ <b>Status:</b> Logged Successfully"""

            if details:
                notification += f"\n\n<b>📋 Additional Details:</b>\n{details}"

            await self.send_log_notification(notification)

        except Exception as e:
            logger.error(f"Failed to notify user action: {e}")

    async def notify_premium_activity(self, user_id, activity, details=None, financial_impact=None):
        """Enhanced notification for premium activities like payments, upgrades, etc."""
        try:
            user_info = await self._get_user_info(user_id)

            # Determine priority based on activity
            priority = "INFO"
            if "payment" in activity.lower() or "upgrade" in activity.lower():
                priority = "SUCCESS"
            elif "expired" in activity.lower() or "cancelled" in activity.lower():
                priority = "WARNING"

            header = self._format_header("💎", "PREMIUM SUBSCRIPTION ACTIVITY", priority)

            notification = f"""{header}

<b>👤 User Information:</b>
├ <b>Name:</b> {user_info['name']}
├ <b>Username:</b> {user_info['username']}
├ <b>User ID:</b> <code>{user_info['id']}</code>
└ <b>Display:</b> {user_info['display']}

<b>💎 Premium Activity:</b>
├ <b>Activity Type:</b> {activity}
├ <b>Status:</b> Processed Successfully
└ <b>Impact:</b> User account updated"""

            if details:
                notification += f"\n\n<b>📋 Activity Details:</b>\n{details}"

            if financial_impact:
                notification += f"\n\n<b>💰 Financial Impact:</b> {financial_impact}"

            await self.send_log_notification(notification)

        except Exception as e:
            logger.error(f"Failed to notify premium activity: {e}")

    async def notify_admin_action(self, admin_id, action, target_user=None, details=None, impact_level="medium"):
        """Enhanced notification for admin actions with detailed tracking"""
        try:
            admin_info = await self._get_user_info(admin_id)

            priority = "INFO"
            if "ban" in action.lower() or "delete" in action.lower() or "remove" in action.lower():
                priority = "WARNING"
            elif "grant" in action.lower() or "approve" in action.lower():
                priority = "SUCCESS"

            header = self._format_header("👑", "ADMINISTRATIVE ACTION", priority)

            notification = f"""{header}

<b>👑 Administrator:</b>
├ <b>Name:</b> {admin_info['name']}
├ <b>Username:</b> {admin_info['username']}
├ <b>Admin ID:</b> <code>{admin_info['id']}</code>
└ <b>Authority Level:</b> {'Owner' if admin_id in getattr(Config, 'OWNER_ID', []) else 'Admin'}

<b>⚙️ Action Details:</b>
├ <b>Action Type:</b> {action}
├ <b>Impact Level:</b> {impact_level.upper()}
├ <b>Execution Status:</b> Completed
└ <b>Authorization:</b> Verified"""

            if target_user:
                try:
                    target_info = await self._get_user_info(target_user)
                    notification += f"\n\n<b>🎯 Target User:</b>\n├ <b>Name:</b> {target_info['name']}\n├ <b>Username:</b> {target_info['username']}\n└ <b>User ID:</b> <code>{target_info['id']}</code>"
                except Exception:
                    notification += f"\n\n<b>🎯 Target User ID:</b> <code>{target_user}</code>"

            if details:
                notification += f"\n\n<b>📋 Administrative Details:</b>\n{details}"

            notification += f"\n\n<b>📈 Administrative Audit:</b> Action logged for compliance and review"

            await self.send_log_notification(notification)

        except Exception as e:
            logger.error(f"Failed to notify admin action: {e}")

    async def notify_error(self, user_id, error_type, error_details, severity="medium", context=None):
        """Enhanced error notification with detailed troubleshooting information"""
        try:
            user_info = await self._get_user_info(user_id)

            priority = "ERROR"
            if severity.lower() == "critical":
                priority = "CRITICAL"
            elif severity.lower() == "low":
                priority = "WARNING"

            header = self._format_header("❌", f"SYSTEM ERROR - {error_type.upper()}", priority)

            notification = f"""{header}

<b>👤 Affected User:</b>
├ <b>Name:</b> {user_info['name']}
├ <b>Username:</b> {user_info['username']}
├ <b>User ID:</b> <code>{user_info['id']}</code>
└ <b>Display:</b> {user_info['display']}

<b>❌ Error Information:</b>
├ <b>Error Type:</b> {error_type}
├ <b>Severity Level:</b> {severity.upper()}
├ <b>Detection Method:</b> Automatic
└ <b>Error State:</b> Logged and Tracked

<b>📝 Technical Details:</b>
<code>{error_details}</code>"""

            if context:
                notification += f"\n\n<b>🔍 Error Context:</b>\n{context}"

            # Add troubleshooting recommendations
            troubleshooting = self._get_troubleshooting_steps(error_type)
            if troubleshooting:
                notification += f"\n\n<b>🔧 Troubleshooting Steps:</b>\n{troubleshooting}"

            notification += f"\n\n<b>🚨 Required Action:</b> {'Immediate investigation required' if severity == 'critical' else 'Review and resolve when possible'}"

            await self.send_log_notification(notification)

        except Exception as e:
            logger.error(f"Failed to notify error: {e}")

    def _get_troubleshooting_steps(self, error_type):
        """Get troubleshooting steps based on error type"""
        troubleshooting_map = {
            "database": "• Check database connection\n• Verify MongoDB service status\n• Review connection string",
            "forwarding": "• Verify bot permissions\n• Check source/target chat access\n• Review message content",
            "authentication": "• Verify bot token\n• Check user session\n• Review API permissions",
            "rate_limit": "• Implement rate limiting\n• Add delays between requests\n• Review API usage",
            "permission": "• Check bot admin status\n• Verify chat permissions\n• Review user access rights"
        }

        for key, steps in troubleshooting_map.items():
            if key.lower() in error_type.lower():
                return steps

        return "• Review error logs\n• Check system resources\n• Verify configuration settings"

    async def notify_forwarding_issue(self, user_id, issue_type, details, severity="medium"):
        """Enhanced notification for forwarding issues like forward tag detection"""
        try:
            user_info = await self._get_user_info(user_id)

            priority = "WARNING"
            if severity.lower() == "critical":
                priority = "CRITICAL"
            elif severity.lower() == "low":
                priority = "INFO"

            header = self._format_header("⚠️", "FORWARDING SYSTEM ISSUE", priority)

            notification = f"""{header}

<b>👤 User Information:</b>
├ <b>Name:</b> {user_info['name']}
├ <b>Username:</b> {user_info['username']}
├ <b>User ID:</b> <code>{user_info['id']}</code>
└ <b>Display:</b> {user_info['display']}

<b>🚨 Issue Details:</b>
├ <b>Issue Type:</b> {issue_type}
├ <b>Severity Level:</b> {severity.upper()}
├ <b>Status:</b> Detected and Logged
└ <b>Impact:</b> Process may be affected

<b>📝 Technical Details:</b>
{details}

<b>🔧 Action Required:</b> Review issue and implement fix if necessary"""

            await self.send_log_notification(notification)

        except Exception as e:
            logger.error(f"Failed to notify forwarding issue: {e}")

    async def notify_plan_exploration(self, user_id, plan_type, action="viewed", source="unknown"):
        """Notify when users explore premium plans and pricing"""
        try:
            user_info = await self._get_user_info(user_id)
            header = self._format_header("👀", "PREMIUM PLAN EXPLORATION", "INFO")

            notification = f"""{header}

<b>👤 User Information:</b>
├ <b>Name:</b> {user_info['name']}
├ <b>Username:</b> {user_info['username']}
├ <b>User ID:</b> <code>{user_info['id']}</code>
└ <b>Display:</b> {user_info['display']}

<b>💰 Plan Interest Details:</b>
├ <b>Plan Type:</b> {plan_type}
├ <b>Action:</b> {action}
├ <b>Source:</b> {source}
└ <b>Intent:</b> Potential subscription interest

<b>📊 Business Intelligence:</b>
├ <b>Lead Quality:</b> High (actively exploring pricing)
├ <b>Conversion Opportunity:</b> Available
└ <b>Recommended Action:</b> Monitor for follow-up engagement

<b>💡 Sales Insight:</b> User is evaluating premium features - consider targeted engagement"""

            await self.send_log_notification(notification)

        except Exception as e:
            logger.error(f"Failed to notify plan exploration: {e}")

    async def notify_free_trial_activity(self, user_id, action, remaining_usage=None):
        """Notify about free trial usage and activities"""
        try:
            user_info = await self._get_user_info(user_id)

            priority = "INFO"
            if "exhausted" in action.lower() or "limit" in action.lower():
                priority = "WARNING"
            elif "activated" in action.lower():
                priority = "SUCCESS"

            header = self._format_header("🎁", "FREE TRIAL ACTIVITY", priority)

            notification = f"""{header}

<b>👤 User Information:</b>
├ <b>Name:</b> {user_info['name']}
├ <b>Username:</b> {user_info['username']}
├ <b>User ID:</b> <code>{user_info['id']}</code>
└ <b>Display:</b> {user_info['display']}

<b>🎁 Trial Activity:</b>
├ <b>Action:</b> {action}
├ <b>Status:</b> Processed Successfully
└ <b>Impact:</b> User trial usage updated"""

            if remaining_usage is not None:
                notification += f"\n\n<b>📊 Usage Statistics:</b>\n├ <b>Remaining Usage:</b> {remaining_usage}\n└ <b>Conversion Potential:</b> {'High' if remaining_usage == 0 else 'Medium'}"

            notification += f"\n\n<b>💡 Conversion Insight:</b> {'User ready for premium upgrade' if remaining_usage == 0 else 'Monitor for premium interest'}"

            await self.send_log_notification(notification)

        except Exception as e:
            logger.error(f"Failed to notify free trial activity: {e}")

    async def notify_contact_request(self, user_id, request_type="general", status="submitted", admin_response=None):
        """Notify about user contact requests to admin"""
        try:
            user_info = await self._get_user_info(user_id)

            priority = "INFO"
            if status == "urgent":
                priority = "WARNING"
            elif status == "resolved":
                priority = "SUCCESS"

            header = self._format_header("📞", "USER CONTACT REQUEST", priority)

            notification = f"""{header}

<b>👤 User Information:</b>
├ <b>Name:</b> {user_info['name']}
├ <b>Username:</b> {user_info['username']}
├ <b>User ID:</b> <code>{user_info['id']}</code>
└ <b>Display:</b> {user_info['display']}

<b>📞 Contact Details:</b>
├ <b>Request Type:</b> {request_type}
├ <b>Status:</b> {status}
├ <b>Priority:</b> {priority}
└ <b>Response Required:</b> {'Yes' if status == 'submitted' else 'No'}"""

            if admin_response:
                notification += f"\n\n<b>👑 Admin Response:</b>\n{admin_response}"

            notification += f"\n\n<b>🎯 Action Required:</b> {'Admin should respond to user query' if status == 'submitted' else 'Contact request handled'}"

            await self.send_log_notification(notification)

        except Exception as e:
            logger.error(f"Failed to notify contact request: {e}")

    async def notify_system_health(self, component, status, details=None, performance_metrics=None):
        """Notify about system health and performance"""
        try:
            priority = "SUCCESS" if status == "healthy" else "WARNING" if status == "degraded" else "CRITICAL"
            header = self._format_header("🔧", f"SYSTEM HEALTH - {component.upper()}", priority)

            notification = f"""{header}

<b>🖥️ System Component:</b>
├ <b>Component:</b> {component}
├ <b>Status:</b> {status.upper()}
├ <b>Health Check:</b> Completed
└ <b>Alert Level:</b> {priority}"""

            if details:
                notification += f"\n\n<b>📋 Component Details:</b>\n{details}"

            if performance_metrics:
                notification += f"\n\n<b>📊 Performance Metrics:</b>\n{performance_metrics}"

            notification += f"\n\n<b>🔍 Monitoring Status:</b> Active | Continuous health monitoring enabled"

            await self.send_log_notification(notification)

        except Exception as e:
            logger.error(f"Failed to notify system health: {e}")

    async def notify_security_event(self, event_type, user_id=None, details=None, severity="medium"):
        """Notify about security events and potential threats"""
        try:
            priority = "CRITICAL" if severity == "high" else "WARNING" if severity == "medium" else "INFO"
            header = self._format_header("🛡️", f"SECURITY EVENT - {event_type.upper()}", priority)

            notification = f"""{header}

<b>🛡️ Security Event:</b>
├ <b>Event Type:</b> {event_type}
├ <b>Severity:</b> {severity.upper()}
├ <b>Detection Time:</b> {self._get_timestamp()}
└ <b>Status:</b> Detected and Logged"""

            if user_id:
                user_info = await self._get_user_info(user_id)
                notification += f"\n\n<b>👤 Associated User:</b>\n├ <b>Name:</b> {user_info['name']}\n├ <b>User ID:</b> <code>{user_info['id']}</code>\n└ <b>Username:</b> {user_info['username']}"

            if details:
                notification += f"\n\n<b>🔍 Event Details:</b>\n{details}"

            notification += f"\n\n<b>🚨 Security Response:</b> {'Immediate action required' if severity == 'high' else 'Monitor and investigate'}"

            await self.send_log_notification(notification)

        except Exception as e:
            logger.error(f"Failed to notify security event: {e}")