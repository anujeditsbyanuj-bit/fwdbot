# Advance Content Saver Bot

## Overview

This is a Telegram bot that forwards messages and files from restricted or non-restricted channels, groups, and bots. It supports saving content from private channels (with user session), batch operations up to 10K messages, and includes a subscription-based system with multiple tiers (Free, Plus, Pro, Infinity). The project includes both a Telegram bot and a Flask-based admin panel running concurrently.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Components

**Bot Framework**
- Built with Pyrogram (Telegram MTProto library) for bot functionality
- Uses pyrofork for extended Pyrogram features
- Multiprocessing design: bot and admin panel run as separate processes
- Plugin-based architecture with handlers organized in `/plugins` directory

**Database Layer**
- MongoDB as the primary database (via motor for async operations)
- Database class in `database.py` handles all data operations
- Collections: users, bots, channels, notifications, admin_logs
- Stores user data, subscription info, referral data, bot configurations

**Admin Panel**
- Flask web application with Flask-Login for authentication
- Flask-WTF for CSRF protection and form handling
- Owner-only initial login with configurable credentials
- Full user management, subscription control, broadcast features
- Located in `/admin_panel` directory with templates and static assets

### Key Design Patterns

**Subscription System**
- Tiered plans: Free, Plus, Pro, Infinity
- Feature flags control access to forwarding, FTM transformations, unequify
- Background subscription checker runs async to expire subscriptions
- Duration support: days, months, years, lifetime

**Force Subscribe**
- Multi-channel force subscription support
- Users must join all configured channels before using bot
- Channels configured via `MULITI_FSUB` environment variable

**Message Forwarding**
- Supports public and private channel forwarding
- Clone bot system for user-specific bot tokens
- FTM Manager for caption transformations, watermarks, link removal
- Duplicate detection and filtering capabilities

**FTM Alpha Mode** (Infinity Plan Exclusive)
- Auto-restart for interrupted manual forwarding from last processed message
- State persistence across bot restarts
- Supports both bot tokens and session strings (userbots)
- Graceful degradation with user guidance when credentials missing
- Unicode small caps notifications with emojis

**Gamma Mode Enhancements**
- Tracks last forwarded message ID per source per user
- Auto catch-up logic for missed messages after bot restart
- Database methods: update_gamma_last_msg, get_gamma_last_msgs, save_gamma_state

**Logging System**
- Centralized BotLogger class for activity tracking
- Logs to Telegram channel and MongoDB admin_logs collection
- IST timezone formatting for timestamps

### Configuration

All settings managed through environment variables in `config.py`:
- Telegram API credentials (API_ID, API_HASH, BOT_TOKEN)
- MongoDB connection string
- Owner credentials for admin panel
- Channel links and force subscribe channels
- Subscription plan pricing

## External Dependencies

**Telegram Integration**
- Telegram Bot API via Pyrogram
- TgCrypto for encryption
- User session strings for private channel access

**Database**
- MongoDB Atlas (cloud-hosted MongoDB)
- Motor (async MongoDB driver)
- PyMongo (sync operations for admin panel)

**URL Shortening**
- InstantLinks API for link verification system

**Web Framework**
- Flask with Jinja2 templates
- Werkzeug for password hashing
- Flask-Login for session management

**Media Processing**
- OpenCV (headless) for potential image/video processing
- aiohttp for async HTTP requests