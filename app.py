import importlib
import re
import string
from datetime import datetime, date, timedelta
from openai import OpenAI
from slack_bolt import App
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore
from slack_sdk.models.blocks import *
import logging

# Add this near the top of your file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

tokens = importlib.import_module("tokens")


ai_client = OpenAI(
    api_key=tokens.open_ai_key,
)

oauth_settings = OAuthSettings(
    client_id=tokens.client_id,
    client_secret=tokens.client_secret,
    scopes=[
        "channels:join",
        "channels:manage",
        "channels:read",
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
        "users:read"
    ],
    installation_store=FileInstallationStore(base_dir="./data/installations"),
    state_store=FileOAuthStateStore(expiration_seconds=600, base_dir="./data/states")
)

app = App(
    signing_secret=tokens.client_signing_secret,
    oauth_settings=oauth_settings,
    name="check-in-bot"
)


MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December"
]

NO_REACT_EVENTS = [
  "channel_leave",
  "channel_join",
  "channel_archive",
  "channel_unarchive"
]

def is_dm(event):
  if "channel_type" in event.keys() and event["channel_type"] == "im":
    return True

def extract_channel(message):
  if message.startswith("<#") and message.endswith("|>"):
    return message[2:-2]
  return ""

def get_check_ins(client, event, logger, channel_id):
  try:
    channel_info = client.conversations_info(
      channel=channel_id,
    )
    channel_name = channel_info.data['channel']['name']
    message_data = client.conversations_history(
      channel=channel_id,
      limit=10
    )
    check_in_entries = []
    parse_messages(check_in_entries, message_data, event['user'])
    while message_data["has_more"]:
      cursor = message_data["response_metadata"]["next_cursor"]
      message_data = client.conversations_history(
        channel=channel_id,
        limit=10,
        cursor=cursor,
      )
      parse_messages(check_in_entries, message_data, event['user'])
    # put entries in chronological order
    check_in_entries.reverse()
    check_ins_string = "\n\n".join(entry for entry in check_in_entries)
    client.files_upload_v2(
      channel=event["channel"],
      title=f"{channel_name} entries",
      filename=f"{channel_name}_check-ins.txt",
      content=check_ins_string,
      initial_comment=f"Here are all the entries you wrote in {channel_name}:",
    )
  except Exception as e:
    logger.error(f"Error getting entries from channel: {repr(e)}")
    try:
      client.chat_postMessage(
        channel=event["channel"],
        text="Sorry, I wasn't able to get your entries from that channel. I need to be added to a channel to be able to see it. Can you check to make sure I'm there, under Integrations?"
      )
    except Exception as e:
      logger.error(f"Error posting about inability to get entries from channel: {repr(e)}")

def parse_messages(check_in_entries, message_data, user):
  # threaded replies are not included in conversation history by default
  messages = message_data["messages"]
  for message in messages:
    if message["user"] == user:
      if "subtype" not in message.keys() or message["subtype"] != "channel_join":
        timestamp = int(message["ts"].split(".")[0])
        readable_date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        check_in_entries.append(message["text"])
        check_in_entries.append(readable_date)

def should_react(client, event, logger):
  if "text" not in event.keys():
    return False
  if "subtype" in event and event["subtype"] in NO_REACT_EVENTS:
    return False
  if "thread_ts" not in event.keys():
    return True
  if ("subtype" in event and event["subtype"] == "thread_broadcast"):
    return True
  # get parent message from thread_ts and check if it's the welcome message asking for intros in thread
  try:
    parent = client.conversations_replies(
      channel=event["channel"],
      ts=event["thread_ts"],
      limit=1,
    )
    parent_message = parent["messages"][0]["text"]
    # we want to emoji react to introduction messages in the welcome thread
    if parent_message.startswith("Welcome to"):
      words = parent_message.split()
      if len(words) > 3 and words[2].translate(str.maketrans('', '', string.punctuation)) in MONTHS:
        return True
  except Exception as e:
    logger.error(f"Error checking if threaded message is an intro: {repr(e)}")
  return False

def get_emojis(client, event, logger):
  try:
    chat_completion = ai_client.chat.completions.create(
        messages=[
          {
            "role": "system",
            "content": "You are a intelligent assistant. You respond to all of the following messages with a single line representing four unique emojis, formatted for Slack. The emojis should represent things mentioned in the messages, with only zero or one emojis representing sentiment. Note that text surrounded by ~ or where the line starts or ends with a negative emoji like :no_pedestrians: or :heavy_multiplication_x: means that the task mentioned there was not completed - please exclude these lines from your emoji output. If the messages express deep sadness or high stress or mention anything related to death of people or animals, please use :people_hugging: to express comfort instead of something more specific for that part of the text. For example if someone's relative died please react with a hug instead of with an emoji representing the relative or death. Also, please use ungendered emojis, for example, :cook: is preferred over :female-cook: or :male-cook:",
          }, 
          {
            "role": "user",
            "content": event["text"]
          }, 
        ],
        model="gpt-4",
    )
    reply = chat_completion.choices[0].message.content
    reply = reply.strip().strip(":")
    emojis = re.split(r':\s*:*', reply)
    return emojis
  except Exception as e:
    logger.error(f"Error getting emojis from OpenAI: {repr(e)}")

def post_emojis(client, event, logger, emojis):
  emoji_limit = 5
  for emoji in emojis:
    if emoji_limit == 0:
      break;
    try:
      client.reactions_add(
        channel=event["channel"],
        timestamp=event["ts"],
        name=f"{emoji}",
      )
      emoji_limit -= 1
    except Exception as e:
      logger.error(f"Error publishing {emoji} emoji react: {repr(e)}")

@app.event("message")
def respond_to_message(client, event, logger):
  # direct messages to the bot are only used for extracting check ins
  if is_dm(event):
    channel_id = extract_channel(event['text'])
    # need to get the channel name for the month
    if channel_id:
      get_check_ins(client, event, logger, channel_id)
    else:
      try:
        client.chat_postMessage(
          channel=event["channel"],
          text="Sorry, I don't understand. You can send me the name of a channel (starting with #) and I will respond with a text file that has all your check-in entries from that channel."
        )
      except Exception as e:
        logger.error(f"Error posting about inability to parse channel: {repr(e)}")
    return
  if should_react(client, event, logger):
    emojis = get_emojis(client, event, logger)
    if emojis is not None:
      post_emojis(client, event, logger, emojis)

def get_home_view(user_id: str):
    """Create the home tab view"""
    logging.info(f"Creating home view for user {user_id}")
    blocks = [
        SectionBlock(
            text=MarkdownText(
                text="*Welcome to Check-in Bot!* 👋\n\nI help manage monthly check-in groups and add emoji reactions to encourage interaction between members."
            )
        ),
        DividerBlock(),
        SectionBlock(
            text=MarkdownText(
                text="*Need help?*\nYou can DM me with a channel name (like #channel-name) and I'll send you all your check-ins from that channel!"
            )
        )
    ]
    
    view = {
        "type": "home",
        "blocks": blocks
    }
    logging.info(f"Generated home view: {view}")
    return view

@app.event("app_home_opened")
def update_home_tab(client, event, logger):
    """Handle app home opened events"""
    logger.info(f"App home opened event received: {event}")
    try:
        # Check the event type
        if event["tab"] != "home":
            logger.info("Ignoring non-home tab event")
            return
            
        logger.info(f"Publishing home view for user {event['user']}")
        result = client.views_publish(
            user_id=event["user"],
            view=get_home_view(event["user"])
        )
        logger.info(f"Successfully published home view: {result}")
    except Exception as e:
        logger.error(f"Error publishing home tab: {str(e)}")
        logger.error(f"Full error details: {repr(e)}")

# Ready? Start your app!
if __name__ == "__main__":
    app.start(port=3000)
