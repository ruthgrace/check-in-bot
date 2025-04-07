import logging
from datetime import datetime
from slack_sdk.models.blocks import SectionBlock, DividerBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from workspace_store import ensure_workspace_exists

def get_home_view(user_id: str, team_id: str, client, get_workspace_info):
    """Create the home tab view"""    
    # Check if we need to create/update workspace info
    team_info = client.team_info()
    team_name = team_info["team"]["name"]
    
    # Ensure workspace exists in storage
    ensure_workspace_exists(team_id, team_name)
    
    # Get workspace info from the event context
    workspace = get_workspace_info(team_id)
    admin_text = ""
    if workspace and workspace["admins"] and len(workspace["admins"]) > 0:
        admin_usernames = []
        for admin_id in workspace["admins"]:
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
            result = client.views_publish(
                user_id=event["user"],
                view=get_home_view(event["user"], event["view"]["team_id"], client, app.get_workspace_info)
            )
        except Exception as e:
            logger.error(f"Error publishing home tab: {str(e)}")
            logger.error(f"Full error details: {repr(e)}") 