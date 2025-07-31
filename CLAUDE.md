# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Slack bot that automatically creates and manages monthly check-in groups.
There are two components. One is a constantly running python app that handles emoji reacting to certain messages using GPT-4. The other is a timer that runs once a day to do administrative stuff like reminding people to post and adding and removing people from channels.

## Key Commands

### Development
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application (port 3000)
python3 app.py
```

### Production
```bash
# Main service
sudo systemctl start check-in-bot
sudo systemctl status check-in-bot
sudo systemctl restart check-in-bot

# Cron timer (runs daily at 15:00 UTC)
sudo systemctl start check-in-bot-cron.timer
sudo systemctl status check-in-bot-cron.timer

# View logs
journalctl -u check-in-bot -f
journalctl -u check-in-bot-cron.service -f
```

## Architecture

### Core Components
- **app.py**: Main Flask/Bolt server handling Slack events and interactions
- **cron.py**: Scheduled tasks for monthly group management workflow
- **workspace_store.py**: Data persistence layer using pickle files in /data/
- **home_tab.py**: Slack home tab UI for admin controls and user preferences

### Monthly Workflow
- Day 25: Post signup message (users react with ☀️ for daily or ⭐ for weekly)
- Last day: Create channels and assign users to groups (~12 people each)
- Days 1-2: Add late signups to existing groups
- Day 7: Send reminders to inactive users
- Day 11: Remove users who haven't posted

## Important Files

### Configuration
- **tokens.py**: Contains API keys (bot_token, bot_signing_secret, open_ai_key)
- **nginx/check-in-bot**: Production nginx config with SSL
- **check-in-bot.service**: systemd service configuration
- **check-in-bot-cron.timer**: Daily scheduler configuration

### Data Storage
- **/data/workspaces.pickle**: Main workspace configurations
- **/data/installations/**: Slack OAuth installation data
- **/data/states/**: OAuth state management

## Slack Permissions Required
- **Scopes**: groups:history, reactions:write, chat:write, groups:write
- **Event Subscriptions**: message.groups
- **Interactivity**: Must be enabled for home tab and buttons

## Notes
- Enterprise Slack installations are not supported (see cron.py comment)
- SSL certificates are managed by Let's Encrypt and auto-renew
