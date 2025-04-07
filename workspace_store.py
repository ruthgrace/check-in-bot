import logging
from datetime import datetime
from pathlib import Path
import pickle

def save_workspace_data(data):
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

def ensure_workspace_exists(team_id: str, team_name: str):
    """Ensure workspace exists in pickle, create if it doesn't"""
    data = get_workspace_info()
    
    if team_id not in data:
        logging.info(f"Saving team info for team id {team_id} and name {team_name}")
        data[team_id] = {
            "team_id": team_id,
            "team_name": team_name,
            "admins": [],
            "incompatible_pairs": [],
            "installed_at": datetime.now().isoformat()
        }
        save_workspace_data(data)
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
        save_workspace_data(data)
        logging.info(f"Updated admins for workspace {team_id}: {admin_ids}") 