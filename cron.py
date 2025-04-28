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

def is_last_day_of_month():
    """Check if today is the last day of the month"""
    today = get_pt_time()
    # Create a datetime for the first day of the next month
    if today.month == 12:
        next_month = datetime(today.year + 1, 1, 1)
    else:
        next_month = datetime(today.year, today.month + 1, 1)
    
    # Subtract one day to get the last day of the current month
    last_day = next_month - timedelta(days=1)
    
    # Return True if today is the last day of the month
    return today.day == last_day.day

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

def build_intro_message(users: list, month: str):
    """Build the intro message for the checkin channels"""
    users_text = " ".join([f"<@{user}>" for user in users])
    message = (
        f"Welcome to {month}! {MONTH_EMOJIS[month]} {users_text}\n\n"
        f"Let's do introductions here in thread. You can be as brief or long as you like. Share any of: who you might mention in your check ins, what's been on your mind lately, or what you'd like to build in the short or long term. (pasting your intro from a previous month is fine too!)\n\n"
        f"General info about this group:\n"
        f"* The aim is to create a supportive group of close-knit friends, not to make people feel bad about their productivity level\n"
        f"* We share our intentions for the day and how our previous day went, often along with a little journalling. The format is casual and flexible, and i'm happy for you to use this group in a way that feels most useful to you. Some people post daily and others weekly.\n"
        f"* If you don't end up posting anything by the 10th of the month I will bump you out of this month's group, just to make sure nobody feels weird about people reading without posting. I'll send out reminders to people who haven't posted around the 7th.\n"
        f"* If you want to get the text of all your checkins from a month, message me just the name of the channel, like `#2025-february-1` (but in plain text; the channel should turn into a blue link)\n"
        f"* If you read someone else's message, leave an emoji react! :slightly_smiling_face: I will leave some initial emoji reacts on each message to foster more human to human interaction."
    )
    return message

def dm_admins(client, workspace_info: dict, message: str):
    """DM admins about the new checkin groups"""
    admins = workspace_info.get("admins", [])
    for admin in admins:
        client.chat_postMessage(channel=admin, text=message)

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
        messages = client.conversations_history(channel=channel_id, limit=999)["messages"]
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
                if not msg.get("thread_ts") or msg.get("ts") == msg.get("thread_ts") or (msg.get("subtype") == "thread_broadcast"):
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
        logging.info(f"Sent reminder to user <@{user_id}> ({first_name}) for channel <#{channel_id}>")
        dm_admins(client, workspace_info, f"Sent reminder to user <@{user_id}> for channel <#{channel_id}>")
        
    except SlackApiError as e:
        logging.error(f"Error sending reminder: {e}")
        dm_admins(client, workspace_info, f"Error sending reminder: {e}")

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

                if first_name != "check-in-bot":
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
                    dm_admins(client, workspace_info, f"Kicked user <@{user_id}> from channel <#{channel_id}>")
                    logging.info(f"Kicked user {user_id} ({first_name}) from channel {channel_id}")
                
            except SlackApiError as e:
                logging.error(f"Error kicking user {user_id} ({first_name}) from channel {channel_id}: {e}")
                dm_admins(client, workspace_info, f"Error kicking user <@{user_id}> from channel <#{channel_id}>: {e}")
    except SlackApiError as e:
        logging.error(f"Error getting channel info: {e}")
        dm_admins(client, workspace_info, f"Error getting channel info for kicking users who haven't posted: {e}")

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
        dm_admins(client, workspace_info, f"Posted monthly signup message to channel <#{announcement_channel}>")
        logging.info(f"Posted monthly signup message to channel <#{announcement_channel}>")
        
    except SlackApiError as e:
        logging.error(f"Error posting monthly signup: {e}")
        dm_admins(client, workspace_info, f"Error posting monthly signup: {e}")

def get_active_users_from_previous_month(client, workspace_info: dict):
    """Get users who were active in the LAST WEEK of the previous month
    
    Args:
        client: Slack client
        workspace_info: Workspace info dictionary
        
    Returns:
        tuple: (daily_posters, weekly_posters) - Sets of user IDs classified by activity level
    """
    # Track user message counts
    user_message_counts = {}
    
    try:
        # Calculate previous month
        now = get_pt_time()
        if now.month == 1:  # January
            prev_month_year = now.year - 1
            prev_month = 12  # December
        else:
            prev_month_year = now.year
            prev_month = now.month - 1
            
        prev_month_name = datetime(prev_month_year, prev_month, 1).strftime("%B").lower()
        prev_month_number = datetime(prev_month_year, prev_month, 1).strftime("%m")  # 01-12 format
        
        # Calculate the last week of the previous month
        first_day_of_current_month = (datetime(now.year, now.month, 1))
        last_week_start_date = first_day_of_current_month - timedelta(days=7)
        
        logging.info(f"Looking for users active between {last_week_start_date.strftime('%Y-%m-%d')} and end of {prev_month_name}")
        
        # Get the channel format from workspace settings
        channel_format = workspace_info.get("channel_format", "check-ins-[year]-[month]")
        
        # Create channel name pattern for the previous month's base format (without numbers)
        base_pattern = channel_format.replace("[year]", str(prev_month_year))
        
        # Create two base patterns - one with month name, one with month number
        base_pattern_name = base_pattern.replace("[month]", prev_month_name)
        base_pattern_number = base_pattern.replace("[month]", prev_month_number)
        
        # If [number] is in the pattern, remove it for base matching
        if "[number]" in base_pattern_name:
            # The pattern up to the [number] part
            base_pattern_name = base_pattern_name.split("[number]")[0]
            base_pattern_number = base_pattern_number.split("[number]")[0]
            
        logging.info(f"Looking for previous month channels that start with: '{base_pattern_name}' or '{base_pattern_number}'")
        
        # List all non-archived channels (using exclude_archived=True)
        result = client.conversations_list(
            types="public_channel,private_channel",
            exclude_archived=True
        )
        matching_channels = []
        
        for channel in result["channels"]:
            channel_name = channel["name"]
            
            # Check if channel name starts with our base pattern
            if (channel_name.startswith(base_pattern_name) or 
                channel_name.startswith(base_pattern_number)):
                matching_channels.append(channel)
                logging.info(f"Found matching previous month channel: {channel_name}")
                
        logging.info(f"Found {len(matching_channels)} matching channels for previous month")
        
        # Process each matching channel
        for channel in matching_channels:
            try:
                # Get channel history
                history = client.conversations_history(channel=channel["id"])
                
                # Count of messages found in last week
                last_week_msg_count = 0
                
                for msg in history["messages"]:
                    # Skip system messages
                    if msg.get("subtype") in ["channel_join", "channel_leave", "channel_archive", "channel_unarchive"]:
                        continue
                        
                    # Get message timestamp
                    msg_ts = float(msg["ts"])
                    msg_date = datetime.fromtimestamp(msg_ts)
                    
                    # If message is from the last week of the month
                    if msg_date >= last_week_start_date:
                        last_week_msg_count += 1
                        user_id = msg.get("user")
                        if user_id:
                            # Increment user's message count
                            if user_id in user_message_counts:
                                user_message_counts[user_id] += 1
                            else:
                                user_message_counts[user_id] = 1
                            
                logging.info(f"Found {last_week_msg_count} messages from the last week in {channel['name']}")
                            
            except Exception as e:
                logging.error(f"Error getting history for channel {channel['name']}: {e}")
        
        # Classify users as daily or weekly posters based on message count
        daily_posters = set()
        weekly_posters = set()
        
        # Users with more than 2 messages are considered daily posters
        DAILY_THRESHOLD = 2
        
        for user_id, count in user_message_counts.items():
            if count > DAILY_THRESHOLD:
                daily_posters.add(user_id)
                logging.info(f"User {user_id} classified as daily poster with {count} messages")
            else:
                weekly_posters.add(user_id)
                logging.info(f"User {user_id} classified as weekly poster with {count} messages")
                
        logging.info(f"Found {len(daily_posters)} daily posters and {len(weekly_posters)} weekly posters from last week of {prev_month_name}")
        
        return daily_posters, weekly_posters
        
    except Exception as e:
        logging.error(f"Error finding active users from previous month: {e}")
        raise

def make_new_checkin_groups(client, workspace_info: dict):
    """Make new checkin groups for the current month"""
    # Get the announcement channel
    announcement_channel = workspace_info.get("announcement_channel")
    if not announcement_channel:
        logging.info("No announcement channel set for this workspace, skipping group creation")
        dm_admins(client, workspace_info, "No announcement channel set for this workspace, skipping group creation")
        return

    last_announcement_timestamp = workspace_info.get("announcement_timestamp")
    if not last_announcement_timestamp:
        logging.info("No last announcement set for this workspace, skipping group creation")
        dm_admins(client, workspace_info, "No last announcement set for this workspace, skipping group creation")
        return

    channel_id = last_announcement_timestamp["channel"]
    timestamp = last_announcement_timestamp["ts"]
    try:
        # Get all users who reacted to the announcement message
        result = client.reactions_get(channel=channel_id, timestamp=timestamp)
        reactions = result.data["message"].get("reactions", [])
    except SlackApiError as e:
        logging.error(f"Error getting user reactions to last announcement: {e}")
        dm_admins(client, workspace_info, f"Error getting user reactions to last announcement: {e}")
        return

    if len(reactions) == 0:
        logging.info("No reactions found for the announcement message, skipping group creation")
        dm_admins(client, workspace_info, "No reactions found for the announcement message, skipping group creation")
        return
    
    daily_posters = set()
    weekly_posters = set()
    for react in reactions:
        if react["name"] == "sun_with_face":
            daily_posters.update(react["users"])
        elif react["name"] == "star2":
            weekly_posters.update(react["users"])
    
    # Check if auto-add active users is enabled
    auto_add_enabled = workspace_info.get("auto_add_active_users", False)
    if auto_add_enabled:
        logging.info("Auto-add active users is enabled - getting active users from previous month")
        
        # Get users who were active in the previous month, classified by activity level
        auto_daily_posters, auto_weekly_posters = get_active_users_from_previous_month(client, workspace_info)
        
        # Add active users who didn't explicitly opt-in
        for user_id in auto_daily_posters:
            if user_id not in daily_posters and user_id not in weekly_posters:
                daily_posters.add(user_id)
                logging.info(f"Auto-adding user {user_id} as daily poster")
                
        for user_id in auto_weekly_posters:
            if user_id not in daily_posters and user_id not in weekly_posters:
                weekly_posters.add(user_id)
                logging.info(f"Auto-adding user {user_id} as weekly poster")
                
        logging.info(f"Auto-added {len(auto_daily_posters & (daily_posters | weekly_posters))} daily posters and {len(auto_weekly_posters & (daily_posters | weekly_posters))} weekly posters")
    
    # admin should be in all groups, will be added separately
    admins = set(workspace_info['admins'])
    daily_posters = daily_posters - admins
    weekly_posters = weekly_posters - admins
    # people who reacted for both daily and weekly should be considered weekly posters
    daily_posters = daily_posters - weekly_posters
    logging.info(f"Daily posters: {daily_posters}")
    logging.info(f"Weekly posters: {weekly_posters}")
    all_participants = set()
    all_participants.update(daily_posters)
    all_participants.update(weekly_posters)

    # check if there are any incompatible pairs in the workspace
    incompatible_pairs = workspace_info.get("incompatible_pairs", [])
    group_memberships = [[]]
    added_members = set()
    for pair in incompatible_pairs:
        if pair[0] in all_participants and pair[1] in all_participants:
            if len(group_memberships) == 1:
                group_memberships.append([])
            group_memberships[0].append(pair[0])
            group_memberships[1].append(pair[1])
            added_members.add(pair[0])
            added_members.add(pair[1])
    # Aiming for at least 12 people in each group including one admin 
    if len(all_participants) // 11 > len(group_memberships):
        for i in range(len(all_participants) // 11-len(group_memberships)):
            group_memberships.append([])
    current_group = len(added_members) % len(group_memberships)
    # users are added round-robin based on the order in which they reacted to the announcement
    for user in daily_posters:
        if user not in added_members:
            group_memberships[current_group].append(user)
            added_members.add(user)
            current_group = (current_group + 1) % len(group_memberships)
        else:
            continue
    for user in weekly_posters:
        if user not in added_members:
            group_memberships[current_group].append(user)
            added_members.add(user)
            current_group = (current_group + 1) % len(group_memberships)
        else:
            continue
    # admins are also added round-robin with the requirement that there be one admin in each group
    current_admin = 0
    admins = list(admins)
    for group in group_memberships:
        group.append(admins[current_admin])
        current_admin = (current_admin + 1) % len(admins)
    logging.info(f"Group memberships: {group_memberships}")

    # create checkin channels
    channel_format = workspace_info.get("channel_format", "")
    if not channel_format:
        logging.info("No channel format set for this workspace, skipping channel creation")
        dm_admins(client, workspace_info, "No channel format set for this workspace, skipping channel creation")
        return
    try:
        for i in range(len(group_memberships)):
            channel_name = channel_format
            month_name = get_pt_time().strftime('%B')
            month_two_digits = get_pt_time().strftime('%m')
            channel_name.replace("[month]", f"{month_two_digits}")
            channel_name.replace("[year]", f"{get_pt_time().year}")
            if len(group_memberships) > 1:
                channel_name += f"-{i+1}"
            result = client.conversations_create(name=channel_name, is_private=True)
            new_channel_id = result.data["channel_id"]
            # add members to the channel
            new_users = group_memberships[i].join(",")
            client.conversations_invite(channel=new_channel_id, users=new_users)
            # post intro thread
            client.chat_postMessage(channel=new_channel_id, text=build_intro_message(group_memberships[i], month_name))
    except SlackApiError as e:
        logging.error(f"Error creating checkin channels: {e}")
        dm_admins(client, workspace_info, f"Error creating checkin channels: {e}")
        return

if __name__ == "__main__":
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
            # Create new check-in groups on the last day of the month instead of the 1st of next month
            elif is_last_day_of_month():
                make_new_checkin_groups(client, workspace_info)
        except Exception as e:
            logging.error(f"Error processing workspace {workspace_id}: {e}")
