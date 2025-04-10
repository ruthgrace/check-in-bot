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

# Month-specific emojis for signup messages
MONTH_EMOJIS = {
    "January": ":snowflake:",  # Snowflake for winter
    "February": ":heart:",  # Hearts for Valentine's Day
    "March": ":four_leaf_clover:",  # Four leaf clover for St. Patrick's Day
    "April": ":cherry_blossom:",  # Cherry blossom for spring
    "May": ":tulip:",  # Tulip for spring flowers
    "June": ":sunny:",  # Sunny for summer
    "July": ":beach_with_umbrella:",  # Beach umbrella for summer vacation
    "August": ":palm_tree:",  # Palm tree for summer
    "September": ":fallen_leaf:",  # Fallen leaf for autumn
    "October": ":jack_o_lantern:",  # Jack o'lantern for Halloween
    "November": ":maple_leaf:",  # Maple leaf for fall
    "December": ":christmas_tree:"  # Christmas tree for holidays
}

def get_pt_time():
    """Get current time in PT (UTC-8, ignoring daylight savings)"""
    return datetime.utcnow() - timedelta(hours=8)

def build_announcement_message(workspace_info: dict):
    """Build the announcement message for the monthly signup"""
    
    # Get the next month
    now = get_pt_time()
    next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    next_month_name = next_month.strftime("%B")
    
    # Get the month-specific emoji
    month_emoji = MONTH_EMOJIS.get(next_month_name, ":calendar:")  # Default to calendar if month not found
    
    # Get the custom announcement text
    custom_text = workspace_info.get("custom_announcement_text", "")
    if not custom_text:
        custom_text = ""

    # Get the tag type
    tag_type = workspace_info.get("announcement_tag", "channel")
    if not tag_type:
        tag_type = "channel"
        update_announcement_tag(workspace_info["team_id"], tag_type)
    # Create the message
    message = f"It's almost {next_month_name}! {month_emoji} <!{tag_type}> Please react to this message if you want to opt in for {next_month_name}. {custom_text}\n\n:sun_with_face: If you would like to try daily checkins\n:star2: If you would like to do weekly checkins (in the same channel)"
    
    return message

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

def post_monthly_signup(client, workspace_info: dict):
    """Post the monthly signup message to the announcement channel"""
    try:
        # Get the announcement channel
        announcement_channel = workspace_info.get("announcement_channel")
        if not announcement_channel:
            logging.info("No announcement channel set for this workspace, skipping monthly signup")
            return
        message = build_announcement_message(workspace_info)
        
        # Post the message
        result = client.chat_postMessage(
            channel=announcement_channel,
            text=message,
            parse="none"
        )

        # Add initial emoji reacts to the message
        client.reactions_add(
            channel=announcement_channel,
            timestamp=result["ts"],
            name="sun_with_face"
        )
        client.reactions_add(
            channel=announcement_channel,
            timestamp=result["ts"],
            name="star2"
        )
        
        logging.info(f"Posted monthly signup message to channel {announcement_channel}")
        
    except SlackApiError as e:
        logging.error(f"Error posting monthly signup: {e}")

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
            
            # On the 25th, post the monthly signup message
            if current_day == 25:
                post_monthly_signup(client, workspace_info)
            elif current_day == 7 or current_day == 11:
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
