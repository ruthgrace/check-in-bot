import logging
from datetime import datetime, timedelta
from slack_bolt import App
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore
from slack_sdk.errors import SlackApiError
import tokens
from workspace_store import get_workspace_info

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Initialize the Bolt app with the same settings as app.py
oauth_settings = OAuthSettings(
    client_id=tokens.client_id,
    client_secret=tokens.client_secret,
    scopes=[
        "channels:join",
        "channels:manage",
        "channels:read",
        "channels:history",
        "channels:write.invites",
        "chat:write",
        "files:write",
        "groups:history",
        "groups:read",
        "groups:write",
        "groups:write.invites",
        "im:history",
        "reactions:read",
        "reactions:write",
        "users:read",
        "team:read"
    ],
    installation_store=FileInstallationStore(base_dir="./data/installations"),
    state_store=FileOAuthStateStore(expiration_seconds=600, base_dir="./data/states")
)

app = App(
    signing_secret=tokens.client_signing_secret,
    oauth_settings=oauth_settings
)

def get_pt_time():
    """Get current time in PT (UTC-8, ignoring daylight savings)"""
    return datetime.utcnow() - timedelta(hours=8)

def get_current_month_channels(client, workspace_info: dict):
    """Get all check-in channels for the current month"""
    channels = []
    try:
        result = client.conversations_list(types="public_channel,private_channel")
        now = get_pt_time()
        current_month_text = now.strftime("%B").lower()
        current_month_number = now.strftime("%m")  # This will give "01" through "12"
        current_year = now.year
        
        for channel in result["channels"]:
            # Check if channel matches the workspace's format for current month
            if (str(current_year) in channel["name"] and current_month_text in channel["name"].lower()) or f"{current_year}-{current_month_number}" in channel["name"]:
                channels.append(channel)
                
    except SlackApiError as e:
        logging.error(f"Error getting channels: {e}")
    
    return channels

def get_users_without_posts(client, channel_id: str):
    """Get users who haven't posted and those who only posted intros
    
    Returns:
        (users_no_posts, users_only_intro)
    """
    try:
        # Get channel members
        members = client.conversations_members(channel=channel_id)["members"]
        
        # Get messages from the last month
        messages = client.conversations_history(channel=channel_id)["messages"]
        
        # Track who has posted what
        posted_users = set()  # Users who posted in main channel
        thread_only_users = set()  # Users who only posted in threads
        
        # First find the welcome message
        welcome_msg = None
        for msg in messages:
            if msg.get("text", "").startswith("Welcome to"):
                welcome_msg = msg
                break
        
        if welcome_msg:
            # Get all replies in the intro thread
            intro_thread = client.conversations_replies(
                channel=channel_id,
                ts=welcome_msg["ts"]
            )
            
            # Add users who posted in the intro thread
            for reply in intro_thread["messages"][1:]:  # Skip the welcome message
                user = reply.get("user")
                if user:
                    thread_only_users.add(user)
        
        # Now check main channel messages
        for msg in messages:
            if msg.get("subtype") in ["channel_join", "channel_leave"]:
                continue
                
            user = msg.get("user")
            if user:
                # If message is in main channel (not just a thread broadcast)
                if not msg.get("thread_ts") or msg.get("subtype") == "thread_broadcast":
                    posted_users.add(user)
                    # Remove from thread_only if they've posted in main channel
                    if user in thread_only_users:
                        thread_only_users.remove(user)
        
        # Find users who haven't posted at all
        no_posts = [m for m in members if m not in posted_users and m not in thread_only_users]
        only_intro = list(thread_only_users)
        
        return no_posts, only_intro
        
    except SlackApiError as e:
        logging.error(f"Error getting user posts: {e}")
        return [], []

def send_reminder(client, user_id: str, channel_id: str, is_intro_only: bool):
    """Send a reminder DM to a user"""
    try:
        channel_info = client.conversations_info(channel=channel_id)
        channel_name = f"<#{channel_id}>"
        
        # Get user's info
        user_info = client.users_info(user=user_id)
        first_name = user_info["user"]["profile"].get("first_name", "there")  # Use "there" as fallback
        
        if is_intro_only:
            message = f"Hi {first_name}, I noticed you've posted an intro in {channel_name} but haven't shared a check-in yet. Are you still planning to participate in check in groups this month? If so, post something (it can be short!) in the next couple days. If not, no worries - you're always welcome back in a future month. :)"
        else:
            message = f"Hi {first_name}, are you still planning on participating in {channel_name} this month? If so post something in the channel — anything, it can be short. If not, I will remove you in a couple days. I just don't want participants to feel weird about people potentially reading without posting. You're of course always welcome to join in a future month too 🙂"
            
        client.chat_postMessage(
            channel=user_id,  # DM the user
            text=message
        )
        logging.info(f"Sent reminder to user {user_id} ({first_name}) for channel {channel_id}")
        
    except SlackApiError as e:
        logging.error(f"Error sending reminder: {e}")

def kick_inactive_users(client, channel_id: str, no_posts: list):
    """Kick users who haven't posted from the channel"""
    try:
        channel_info = client.conversations_info(channel=channel_id)
        channel_name = channel_info["channel"]["name"]
        
        for user_id in no_posts:
            try:
                # Get user's info for the message
                user_info = client.users_info(user=user_id)
                first_name = user_info["user"]["profile"].get("first_name", "there")
                
                # Kick the user
                client.conversations_kick(
                    channel=channel_id,
                    user=user_id
                )
                
                # Send a DM to the user
                client.chat_postMessage(
                    channel=user_id,
                    text=f"Hi {first_name}, I've removed you from {channel_name} since you haven't posted a check-in this month. You're always welcome to join again in a future month! 🙂"
                )
                
                logging.info(f"Kicked user {user_id} ({first_name}) from channel {channel_id}")
                
            except SlackApiError as e:
                logging.error(f"Error kicking user {user_id}: {e}")
                
    except SlackApiError as e:
        logging.error(f"Error getting channel info: {e}")

def check_and_remind():
    """Check for users who need reminders and send them"""
    logging.info("Cron job started")
    current_day = get_pt_time().day
    logging.info(f"Current day: {current_day} (Pacific time)")
    
    # Get all workspaces
    workspaces = get_workspace_info()
    
    for workspace_id, workspace_info in workspaces.items():
        try:
            # Get installation for this workspace
            installation = app.installation_store.find_installation(
                team_id=workspace_id,
                enterprise_id=None,
                is_enterprise_install=False
            )
            if not installation:
                logging.error(f"No installation found for workspace {workspace_id}")
                continue
            
            # Create client from installation's bot token
            client = app.client
            client.token = installation.bot_token
            
            # Get current month's channels
            channels = get_current_month_channels(client, workspace_info)
            
            for channel in channels:
                no_posts, only_intro = get_users_without_posts(client, channel["id"])
                
                # On the 7th, send reminders
                if current_day == 7:
                    for user in no_posts:
                        send_reminder(client, user, channel["id"], False)
                        
                    for user in only_intro:
                        send_reminder(client, user, channel["id"], True)
                
                # On the 11th, kick inactive users
                elif current_day == 11:
                    kick_inactive_users(client, channel["id"], no_posts)
                    
        except Exception as e:
            logging.error(f"Error processing workspace {workspace_id}: {e}")

if __name__ == "__main__":
    check_and_remind()

# time-based check-in-bot tasks

# ***Need to make sure actions are logged so that they can be reviewed.***

# on the 25th of the previous month: announce signups for check in groups For the next month
#    Also create the groups and add the check-in bot. 

# on the last day of the previous month:
#    Determine how many channels there should be (number of people // 12)
#        Can adjust based on previous posting frequency information 
#    Post a welcome message / intro thread in the channels, tagging everyone who should be in that channel
#    Ensure that everybody is added.

# on the 7th of the month:
#    Message people who have not posted. 
#    Message people who have only posted an intro and not posted a check-in to remind. 

# on the 11th of the month: Remove people who have still not posted ever.
#    Could also remove people who replied to the message asking to be removed even if they've already posted an intro.