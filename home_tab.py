import logging
import traceback
from datetime import datetime
from slack_sdk.models.blocks import SectionBlock, DividerBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from workspace_store import ensure_workspace_exists, update_channel_format
from cron import build_announcement_message

def get_home_view(user_id: str, team_id: str, team_name: str, client, get_workspace_info):
    """Create the home tab view"""    
    # Ensure workspace exists in storage
    ensure_workspace_exists(team_id)
    
    # Get workspace info from the event context
    workspace_info = get_workspace_info(team_id)
    
    admin_text = ""
    incompatible_text = ""
    announcement_text = ""
    
    if workspace_info and workspace_info["admins"] and len(workspace_info["admins"]) > 0:
        admin_usernames = []
        for admin_id in workspace_info["admins"]:
            try:
                # Get user info from Slack
                user_info = client.users_info(user=admin_id)
                admin_usernames.append(f"<@{admin_id}>")
            except Exception as e:
                logging.error(f"Error getting user info: {repr(e)}")
        admin_text = "\n\n*Administrators:*\n" + ", ".join(admin_usernames)
    else:
        admin_text = "\n\n*Administrators:*\nNo administrators found. You can become an administrator by messaging 'king me' to the check-in bot."
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Welcome to Check-in Bot!* 👋\n\nI help manage monthly check-in groups and add emoji reactions to encourage interaction between members. "
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Want to save your check-ins?*\nYou can DM me with a channel name (like #channel-name) and I'll send you all your check-ins from that channel! Note that threaded replies are not included unless they were also posted as top-level channel messages."
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": admin_text + "\n\nAdministrators can ask check-in-bot to keep certain users from being in the same check-in-group."
            }
        }
    ]
    
    view = {
        "type": "home",
        "blocks": blocks
    }
    # If user is an admin, show the admin home view
    if workspace_info and workspace_info.get("admins") and user_id in workspace_info["admins"]:
        return build_admin_home(workspace_info, blocks)
    return view

def register_home_tab_handlers(app):
    """Register all home tab related event handlers"""
    
    @app.event("app_home_opened")
    def update_home_tab(client, event, logger):
        """Handle app home opened events"""
        try:
            # Check the event type
            if event["tab"] != "home":
                return
            logger.info(f"Publishing home view for user {event['user']}")
            
            # Get team_id from the client's context
            team_info = client.team_info()
            team_id = team_info["team"]["id"]
            team_name = team_info["team"]["name"]
                
            result = client.views_publish(
                user_id=event["user"],
                view=get_home_view(event["user"], team_id, team_name, client, app.get_workspace_info)
            )
        except Exception as e:
            logger.error(f"Error publishing home tab: {str(e)}")
            logger.error(f"Full error details:\n{traceback.format_exc()}")
            logger.error(f"Event object: {event}")

def build_admin_home(workspace_info: dict, blocks: list) -> dict:
    """Build the admin home tab view"""
    blocks.extend([
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Admin Settings",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Configure your workspace settings below:"
            }
        }
    ])


    if workspace_info["incompatible_pairs"]:
        pair_texts = []
        for user1, user2 in workspace_info["incompatible_pairs"]:
            pair_texts.append(f"<@{user1}> and <@{user2}>")
        incompatible_text = "\n\n*Users kept apart:*\n" + "\n".join(pair_texts)
    else:
        incompatible_text = "\n\n*Users kept apart:*\nNo users are currently being kept apart."
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": incompatible_text
        }
    })
    
    channel_format = workspace_info.get("channel_format")
    if not channel_format:
        update_channel_format(team_id, "check-ins-[year]-[month]")
        channel_format = workspace_info.get("channel_format")
    channel_format_text = f"\n\n*Channel naming format:*\n{channel_format}\n(Administrators can change this with `set channel format [new format]`)"
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": channel_format_text
        }
    })
    
    # Add announcement channel info
    announcement_channel = workspace_info.get("announcement_channel")
    if announcement_channel:
        announcement_text = f"\n\n*Announcement channel:*\n<#{announcement_channel}>\n(Administrators can change this with `set announcement channel #channel`)"
    else:
        announcement_text = "\n\n*Announcement channel:*\nNo announcement channel set. Administrators can set one with `set announcement channel #channel`"
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": announcement_text
        }
    })

    # Add custom announcement text section
    custom_announcement = workspace_info.get("custom_announcement_text", "")
    if custom_announcement:
        custom_announcement_text = f"*Custom Announcement Text:*\nUse `set announcement text [Your text here]` to set or `set announcement tag [here|channel]` to set the tag type.\n\nThis is what your monthly signup message will look like:\n\n{build_announcement_message(workspace_info)}"
    else:
        custom_announcement_text = f"*Custom Announcement Text:*\nNo custom announcement text set.\nUse `set announcement text [Your text here]` to set or `set announcement tag [here|channel]` to set the tag type.\n\nThis is what your monthly signup message will look like. Your custom text will apear after the 2nd sentence:\n\n{build_announcement_message(workspace_info)}"
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": custom_announcement_text
        }
    })

    # Add last announcement message link section if it exists
    last_announcement = workspace_info.get("announcement_timestamp")
    if last_announcement and "channel" in last_announcement and "ts" in last_announcement:
        channel_id = last_announcement["channel"]
        timestamp = last_announcement["ts"]
        # Format the permalink URL
        workspace_domain = workspace_info.get("domain", "slack")
        permalink = f"https://{workspace_domain}.slack.com/archives/{channel_id}/p{timestamp.replace('.', '')}"
        last_announcement_text = f"*Last Announcement:*\n<{permalink}|View last announcement message>\n(Administrators can update this with `set announcement link [message link]`)"
    else:
        last_announcement_text = "*Last Announcement:*\nNo last announcement message set.\nAdministrators can set one with `set announcement link [message link]`"
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": last_announcement_text
        }
    })

    # Add auto-add active users setting
    auto_add_enabled = workspace_info.get("auto_add_active_users", False)
    auto_add_status = "✅ Enabled" if auto_add_enabled else "❌ Disabled (default)"
    auto_add_text = f"*Auto-add Active Users:* {auto_add_status}\n" + \
                   "When enabled, users who posted in the previous month will automatically be added to new channels.\n" + \
                   "Use `set auto-add on` or `set auto-add off` to change this setting."
    
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": auto_add_text
        }
    })

    return {
        "type": "home",
        "blocks": blocks
    } 