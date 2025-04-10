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
    incompatible_text = ""
    announcement_text = ""
    
    if workspace and workspace["admins"] and len(workspace["admins"]) > 0:
        admin_usernames = []
        channel_format = workspace.get("channel_format", "[year]-[month]-[number]")
        for admin_id in workspace["admins"]:
            try:
                # Get user info from Slack
                user_info = client.users_info(user=admin_id)
                admin_usernames.append(f"<@{admin_id}>")
            except Exception as e:
                logging.error(f"Error getting user info: {repr(e)}")
        admin_text = "\n\n*Administrators:*\n" + ", ".join(admin_usernames)
        
        # If current user is an admin, show incompatible pairs and announcement channel
        if user_id in workspace["admins"]:
            if workspace["incompatible_pairs"]:
                pair_texts = []
                for user1, user2 in workspace["incompatible_pairs"]:
                    pair_texts.append(f"<@{user1}> and <@{user2}>")
                incompatible_text = "\n\n*Users kept apart:*\n" + "\n".join(pair_texts)
            else:
                incompatible_text = "\n\n*Users kept apart:*\nNo users are currently being kept apart."
            
            incompatible_text += f"\n\n*Channel naming format:*\n{channel_format}\n_(Administrators can change this with 'set format [new format]')_"
            
            # Add announcement channel info
            announcement_channel = workspace.get("announcement_channel")
            if announcement_channel:
                announcement_text = f"\n\n*Announcement channel:*\n<#{announcement_channel}>\n_(Administrators can change this with 'set announcement #channel')_"
            else:
                announcement_text = "\n\n*Announcement channel:*\nNo announcement channel set. Administrators can set one with 'set announcement #channel'"
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
                "text": admin_text + "\n\nAdministrators can ask check-in-bot to keep certain users from being in the same check-in-group." + incompatible_text + announcement_text
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