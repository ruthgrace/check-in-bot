#!/usr/bin/env python3
import logging
import sys
import json
from datetime import datetime
from slack_bolt import App
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.errors import SlackApiError
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore
import tokens

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("api_diagnostics_log.txt")
    ]
)

# Initialize the Bolt app with the same settings as in cron.py
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

def run_api_diagnostics(client, workspace_id):
    """
    Run comprehensive API diagnostics to debug permission issues
    
    Args:
        client: Slack client with token already set
        workspace_id: Workspace ID for logging
    """
    logging.info("======== RUNNING DETAILED API DIAGNOSTICS ========")
    logging.info("Workspace ID: {}".format(workspace_id))
    
    try:
        # 1. Check auth and bot identity
        auth_test = client.auth_test()
        logging.info("Auth test successful:")
        logging.info("  - Bot name: {}".format(auth_test.get('user')))
        logging.info("  - Bot user ID: {}".format(auth_test.get('user_id')))
        logging.info("  - Team name: {}".format(auth_test.get('team')))
        logging.info("  - Team ID: {}".format(auth_test.get('team_id')))
        logging.info("  - Bot ID: {}".format(auth_test.get('bot_id')))
        
        # 2. Check available scopes
        scopes = auth_test.get('scope', '').split(',')
        logging.info("Bot scopes ({}):".format(len(scopes)))
        for scope in sorted(scopes):
            if scope:  # Avoid empty strings
                logging.info("  - {}".format(scope))
                
        # 3. Check available methods
        logging.info("\nTesting API endpoints...")
        
        # 3.1 Test conversations.list
        try:
            logging.info("\nTesting conversations.list...")
            result = client.conversations_list(limit=1, types="private_channel")
            logging.info("conversations.list result: {}".format(result["ok"]))
            if result["channels"]:
                logging.info("  Found channels: {}".format(len(result["channels"])))
                for channel in result["channels"][:3]:  # Show up to 3 channels
                    logging.info("  - {} (ID: {})".format(channel["name"], channel["id"]))
        except Exception as e:
            logging.error("conversations.list failed: {}".format(e))
        
        # 3.2 Test users.list
        try:
            logging.info("\nTesting users.list...")
            result = client.users_list(limit=5)
            logging.info("users.list result: {}".format(result["ok"]))
            if result["members"]:
                logging.info("  Found users: {}".format(len(result["members"])))
                for user in result["members"][:3]:  # Show up to 3 users
                    logging.info("  - {} ({})".format(user["name"], user["id"]))
        except Exception as e:
            logging.error("users.list failed: {}".format(e))
            
        # 3.3 Test chat.postMessage to bot DM
        try:
            logging.info("\nTesting chat.postMessage...")
            result = client.chat_postMessage(
                channel=auth_test.get('user_id'),
                text="API diagnostic test message"
            )
            logging.info("chat.postMessage result: {}".format(result["ok"]))
        except Exception as e:
            logging.error("chat.postMessage failed: {}".format(e))
            
        # 3.4 Test various channel creation scenarios
        logging.info("\nTesting channel creation with various parameters...")
        
        # 3.4.1 Test with private channel
        test_channel_name = "test-diag-priv-{}".format(int(datetime.utcnow().timestamp()))
        try:
            logging.info("Creating private channel: {}".format(test_channel_name))
            result = client.conversations_create(
                name=test_channel_name,
                is_private=True
            )
            logging.info("Private channel creation result: {}".format(result["ok"]))
            
            # If successful, clean up by archiving the channel
            if result["ok"] and "channel" in result and "id" in result["channel"]:
                channel_id = result["channel"]["id"]
                logging.info("Created channel ID: {}".format(channel_id))
                
                # Try to invite a user
                try:
                    logging.info("Testing user invitation...")
                    # Get the first admin user
                    users = client.users_list()
                    admin_user = None
                    for user in users["members"]:
                        if user.get("is_admin", False) and not user.get("is_bot", False):
                            admin_user = user["id"]
                            break
                    
                    if admin_user:
                        invite_result = client.conversations_invite(
                            channel=channel_id,
                            users=[admin_user]
                        )
                        logging.info("User invitation result: {}".format(invite_result["ok"]))
                except Exception as invite_error:
                    logging.error("User invitation failed: {}".format(invite_error))
                
                # Now archive the channel
                archive_result = client.conversations_archive(channel=channel_id)
                logging.info("Channel archive result: {}".format(archive_result["ok"]))
                
        except Exception as e:
            logging.error("Private channel creation failed: {}".format(e))
            
            # Log the full error response
            if hasattr(e, 'response') and e.response is not None:
                logging.error("API response: {}".format(e.response))
                
                # If we're getting restricted_action, try to get more details
                if hasattr(e.response, 'data') and e.response.data and "error" in e.response.data and e.response.data["error"] == "restricted_action":
                    logging.error("RESTRICTED ACTION ERROR DETECTED")
                    logging.error("This usually means the workspace has restrictions on channel creation.")
                    logging.error("Checking workspace enterprise status...")
                    
                    try:
                        # Get team info
                        team_info = client.team_info()
                        logging.info("Team info:")
                        logging.info(json.dumps(team_info, indent=2))
                        
                        # Check if it's part of an Enterprise Grid
                        is_enterprise = team_info.get("team", {}).get("is_enterprise", False)
                        domain = team_info.get("team", {}).get("domain", "unknown")
                        
                        if is_enterprise:
                            logging.info("This workspace is part of an Enterprise Grid installation.")
                            logging.info("Enterprise Grid workspaces often have additional restrictions.")
                        else:
                            logging.info("This workspace is not part of an Enterprise Grid.")
                            
                        logging.info("Workspace domain: {}".format(domain))
                    except Exception as team_err:
                        logging.error("Could not get team info: {}".format(team_err))
            
        # 3.4.2 Test with public channel
        test_channel_name = "test-diag-pub-{}".format(int(datetime.utcnow().timestamp()))
        try:
            logging.info("\nCreating public channel: {}".format(test_channel_name))
            result = client.conversations_create(
                name=test_channel_name,
                is_private=False
            )
            logging.info("Public channel creation result: {}".format(result["ok"]))
            
            # If successful, clean up by archiving the channel
            if result["ok"] and "channel" in result and "id" in result["channel"]:
                channel_id = result["channel"]["id"]
                archive_result = client.conversations_archive(channel=channel_id)
                logging.info("Channel archive result: {}".format(archive_result["ok"]))
        except Exception as e:
            logging.error("Public channel creation failed: {}".format(e))
            
            # Log the full error response
            if hasattr(e, 'response') and e.response is not None:
                logging.error("API response: {}".format(e.response))
            
        # 4. Check workspace admins
        try:
            logging.info("\nChecking workspace admins...")
            admin_users = []
            users_list = client.users_list()
            for user in users_list["members"]:
                if user.get("is_admin", False):
                    admin_users.append(user.get("name", "unknown") + " (" + user.get("id", "unknown") + ")")
            
            logging.info("Workspace admins: {}".format(", ".join(admin_users)))
        except Exception as e:
            logging.error("Could not get workspace admins: {}".format(e))
            
    except Exception as e:
        logging.error("Auth test failed: {}".format(e))
        if hasattr(e, 'response') and e.response is not None:
            logging.error("API response: {}".format(e.response))
            
    logging.info("======== API DIAGNOSTICS COMPLETE ========")

def main():
    if len(sys.argv) < 2:
        # If no workspace ID is provided, show all available workspaces
        logging.info("No workspace ID provided. Available workspaces:")
        installations = app.installation_store.find_all(is_enterprise_install=False)
        for install in installations:
            team_id = install.team_id
            try:
                # Create client from installation's bot token
                client = app.client
                client.token = install.bot_token
                auth = client.auth_test()
                logging.info("  - {} ({}): Team Name: {}".format(team_id, auth.get("team_id"), auth.get("team")))
            except Exception as e:
                logging.info("  - {} (error retrieving info: {})".format(team_id, str(e)))
                
        logging.info("\nUsage: python api_diagnostics.py WORKSPACE_ID")
        return
    
    # Get the workspace ID from command line argument
    workspace_id = sys.argv[1]
    logging.info("Running diagnostics for workspace ID: {}".format(workspace_id))
    
    # Get installation for this workspace
    installation = app.installation_store.find_installation(
        team_id=workspace_id,
        enterprise_id=None,
        is_enterprise_install=False
    )
    
    if not installation:
        logging.error("No installation found for workspace {}".format(workspace_id))
        return
    
    # Create client from installation's bot token
    client = app.client
    client.token = installation.bot_token
    
    # Run API diagnostics for this workspace
    run_api_diagnostics(client, workspace_id)

if __name__ == "__main__":
    main()
