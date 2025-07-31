import logging
from datetime import datetime
from pathlib import Path
import pickle
import random
import re

def save_workspace_info(data):
    """Save workspace data to pickle file"""
    pickle_path = Path("data/workspaces.pickle")
    pickle_path.parent.mkdir(exist_ok=True)
    
    with open(pickle_path, 'wb') as f:
        pickle.dump(data, f)

def get_workspace_info(team_id: str = None):
    """Get info for one or all workspaces
    
    Args:
        team_id: Optional team ID. If provided, returns info for just that workspace.
                If None, returns info for all workspaces.
    
    Returns:
        If team_id provided: Dict with workspace info or None if not found
        If team_id None: Dict of all workspaces with team_ids as keys
    """
    pickle_path = Path("data/workspaces.pickle")
    if not pickle_path.exists():
        return {} if team_id else {}
        
    try:
        with open(pickle_path, 'rb') as f:
            data = pickle.load(f)
            if team_id:
                return data.get(team_id)
            return data
    except Exception as e:
        logging.error(f"Error reading workspace info: {repr(e)}")
        return {} if team_id else {}

def ensure_workspace_exists(team_id: str, client=None):
    """Ensure workspace exists in pickle, create if it doesn't"""
    data = get_workspace_info()
    
    if team_id not in data:
        team_name = team_id  # Default to team_id if we can't get the real name
        if client:
            try:
                team_info = client.team_info()
                team_name = team_info["team"]["name"]
            except Exception as e:
                logging.error(f"Error getting team info when ensuring workspace exists, setting team name to team id for now: {repr(e)}")
        logging.info(f"Saving team info for team id {team_id} and name {team_name}")
        data[team_id] = {
            "team_id": team_id,
            "team_name": team_name,
            "admins": [],
            "incompatible_pairs": [],
            "channel_format": "check-ins-[year]-[month]",  # Default format
            "announcement_channel": None,  # Default to None
            "installed_at": datetime.now().isoformat()
        }
        save_workspace_info(data)
        logging.info(f"Added workspace info for {team_name} ({team_id})")
    
    return data[team_id]

def update_workspace_admins(team_id: str, admin_ids: list):
    """Update the list of admin users for a workspace
    
    Args:
        team_id: The workspace team ID
        admin_ids: List of user IDs who should be admins
    """
    data = get_workspace_info()
    
    if team_id in data:
        data[team_id]["admins"] = admin_ids
        save_workspace_info(data)
        logging.info(f"Updated admins for workspace {team_id}: {admin_ids}")

def generate_admin_passcode(team_id: str, user_id: str):
    """Generate and store a passcode for admin verification
    
    Returns the generated passcode
    """
    # Generate a 6-digit passcode
    passcode = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    data = get_workspace_info()
    if team_id in data:
        # Add or update pending_admin field
        if "pending_admins" not in data[team_id]:
            data[team_id]["pending_admins"] = {}

        # Flush previous pending passcodes
        data[team_id]["pending_admins"] = {}
        
        data[team_id]["pending_admins"][user_id] = {
            "passcode": passcode,
            "timestamp": datetime.now().isoformat()
        }
        save_workspace_info(data)
        logging.info(f"Generated admin passcode for user {user_id} in workspace {team_id}")
        
    return passcode

def verify_admin_passcode(team_id: str, user_id: str, passcode: str) -> bool:
    """Verify a passcode and make user admin if correct"""
    data = get_workspace_info()
    if team_id in data and "pending_admins" in data[team_id]:
        pending = data[team_id]["pending_admins"].get(user_id)
        if pending and pending["passcode"] == passcode:
            # Remove from pending and add to admins
            del data[team_id]["pending_admins"][user_id]
            if user_id not in data[team_id]["admins"]:
                data[team_id]["admins"].append(user_id)
            save_workspace_info(data)
            logging.info(f"User {user_id} verified as admin in workspace {team_id}")
            return True
    return False

def add_incompatible_pair(team_id: str, user1: str, user2: str):
    """Add a pair of users that should be kept apart
    
    Args:
        team_id: The workspace team ID
        user1: First user ID (without the @ symbol)
        user2: Second user ID (without the @ symbol)
    """
    data = get_workspace_info()
    if team_id in data:
        if "incompatible_pairs" not in data[team_id]:
            data[team_id]["incompatible_pairs"] = []
            
        # Sort user IDs to ensure consistent storage
        pair = tuple(sorted([user1, user2]))
        if pair not in data[team_id]["incompatible_pairs"]:
            data[team_id]["incompatible_pairs"].append(pair)
            save_workspace_info(data)
            logging.info(f"Added incompatible pair in workspace {team_id}: {user1} and {user2}")

def validate_channel_format(format_str: str) -> tuple:
    """Validate channel format string
    
    Returns:
        (is_valid, error_message)
    """
    required_tokens = ['[year]', '[month]']
    optional_tokens = ['[number]']
    
    # Check for required tokens
    for token in required_tokens:
        if token not in format_str:
            return False, f"Format must include {token}"
            
    # Check for invalid characters
    invalid_chars = '<>&'
    for char in invalid_chars:
        if char in format_str:
            return False, f"Format cannot include {char}"
            
    # Check that all [] tokens are valid
    for token in re.findall(r'\[.*?\]', format_str):
        if token not in required_tokens + optional_tokens:
            return False, f"Invalid token: {token}"
            
    return True, ""

def update_channel_format(team_id: str, format_str: str) -> tuple:
    """Update the channel naming format for a workspace
    
    Args:
        team_id: The workspace team ID
        format_str: Format string for channel names
        
    Returns:
        (success, error_message)
    """
    is_valid, error = validate_channel_format(format_str)
    if not is_valid:
        return False, error
        
    data = get_workspace_info()
    if team_id in data:
        data[team_id]["channel_format"] = format_str
        save_workspace_info(data)
        logging.info(f"Updated channel format for workspace {team_id}: {format_str}")
        return True, ""
        
    return False, "Workspace not found"

def update_announcement_channel(team_id: str, channel_id: str) -> bool:
    """Update the announcement channel for a workspace
    
    Args:
        team_id: The workspace team ID
        channel_id: The channel ID to use for announcements
        
    Returns:
        bool: True if successful, False otherwise
    """
    data = get_workspace_info()
    if team_id in data:
        data[team_id]["announcement_channel"] = channel_id
        save_workspace_info(data)
        logging.info(f"Updated announcement channel for workspace {team_id}: {channel_id}")
        return True
    return False

def update_workspace_info(workspace_id: str, updates: dict):
    """Update workspace information"""
    workspaces = get_workspace_info()
    if workspace_id not in workspaces:
        workspaces[workspace_id] = {}
    logging.info(f"updates: {updates}")
    workspaces[workspace_id].update(updates)
    logging.info(f"workspace {workspace_id} after update: {workspaces[workspace_id]}")
    save_workspace_info(workspaces)

def update_custom_announcement(workspace_id: str, announcement_text: str):
    """Update the custom announcement text for a workspace"""
    update_workspace_info(workspace_id, {"custom_announcement_text": announcement_text})

def update_announcement_tag(workspace_id: str, tag_type: str):
    """Update the announcement tag type for a workspace (here or channel)"""
    if tag_type not in ["here", "channel"]:
        return (False, "Tag type must be either 'here' or 'channel'")
    update_workspace_info(workspace_id, {"announcement_tag": tag_type})
    return (True, "")

def update_announcement_timestamp(workspace_id: str, channel_id: str, timestamp: str):
    """Update the announcement message timestamp for a workspace"""
    update_workspace_info(workspace_id, {
        "announcement_timestamp": {
            "channel": channel_id,
            "ts": timestamp
        }
    })

def update_auto_add_setting(workspace_id: str, enabled: bool):
    """Update the setting for automatically adding active users from previous month
    
    Args:
        workspace_id: The workspace team ID
        enabled: Whether to auto-add active users
        
    Returns:
        tuple: (success, message)
    """
    update_workspace_info(workspace_id, {"auto_add_active_users": enabled})
    return (True, "")

def add_always_include_user(workspace_id: str, user_id: str):
    """Add a user to the 'always include' list for the next month's groups
    
    Args:
        workspace_id: The workspace team ID
        user_id: The user ID to always include
        
    Returns:
        tuple: (success, message)
    """
    data = get_workspace_info()
    if workspace_id in data:
        # Initialize always_include_users if it doesn't exist
        if "always_include_users" not in data[workspace_id]:
            data[workspace_id]["always_include_users"] = []
            
        # Add user to the list if not already there
        if user_id not in data[workspace_id]["always_include_users"]:
            data[workspace_id]["always_include_users"].append(user_id)
            save_workspace_info(data)
            logging.info(f"Added user {user_id} to always include list for workspace {workspace_id}")
            return (True, f"User <@{user_id}> added to the always include list")
        else:
            return (False, f"User <@{user_id}> is already in the always include list")
    return (False, "Workspace not found")

def remove_always_include_user(workspace_id: str, user_id: str):
    """Remove a user from the 'always include' list
    
    Args:
        workspace_id: The workspace team ID
        user_id: The user ID to remove
        
    Returns:
        tuple: (success, message)
    """
    data = get_workspace_info()
    if workspace_id in data and "always_include_users" in data[workspace_id]:
        if user_id in data[workspace_id]["always_include_users"]:
            data[workspace_id]["always_include_users"].remove(user_id)
            save_workspace_info(data)
            logging.info(f"Removed user {user_id} from always include list for workspace {workspace_id}")
            return (True, f"User <@{user_id}> removed from the always include list")
        else:
            return (False, f"User <@{user_id}> is not in the always include list")
    return (False, "Workspace not found or no always include list exists")

def get_always_include_users(workspace_id: str):
    """Get the list of users who should always be included in check-in groups
    
    Args:
        workspace_id: The workspace team ID
        
    Returns:
        list: List of user IDs who should always be included
    """
    data = get_workspace_info()
    if workspace_id in data:
        return data[workspace_id].get("always_include_users", [])
    return []