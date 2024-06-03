import importlib
import json
import re
import string

from datetime import datetime
from openai import OpenAI
from slack_bolt import App
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore
tokens = importlib.import_module("tokens")

ai_client = OpenAI(
    api_key=tokens.open_ai_key,
)

oauth_settings = OAuthSettings(
    client_id=tokens.client_id,
    client_secret=tokens.client_secret,
    scopes=["groups:history", "groups:read", "groups:write", "groups:write.invites", "reactions:read", "reactions:write"],
    installation_store=FileInstallationStore(base_dir="./data/installations"),
    state_store=FileOAuthStateStore(expiration_seconds=600, base_dir="./data/states")
)

app = App(
    signing_secret=tokens.client_signing_secret,
    oauth_settings=oauth_settings
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

def is_dm(event):
  if "channel_type" in event.keys() and event["channel_type"] == "im":
    return True

def extract_channel(message):
  if message.startswith("<#") and message.endswith("|>"):
    return message[2:-2]
  return ""

def should_react(client, event, logger):
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

@app.event("message")
def emoji_react(client, event, logger):
  # direct messages to the bot are only used for extracting check ins
  if is_dm(event):
    logger.error(f"user: {event['user']}")
    channel_id = extract_channel(event['text'])
    # need to get the channel name for the month
    if channel_id:
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
        # threaded replies are not included in conversation history by default
        messages = message_data["messages"]
        for message in messages:
          if message["user"] == event['user']:
            timestamp = int(message["ts"].split(".")[0])
            readable_date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            check_in_entries.append(readable_date)
            check_in_entries.append(message["text"])
        logger.error(f"messages parsed: {check_in_entries}")
        # get additional pages of results using cursor
        # convert check in entries from array to string
        client.files_upload_v2(
          channel=event["channel"],
          title=f"{channel_name} entries",
          filename=f"{channel_name}_check-ins.txt",
          content="Hi there! This is a text file!",
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
    try:
      chat_completion = ai_client.chat.completions.create(
          messages=[
            {
              "role": "system",
              "content": "You are a intelligent assistant. You respond to all of the following messages with a single line representing four unique emojis, formatted for Slack. The emojis should represent things mentioned in the messages, with only zero or one emojis representing sentiment. Note that text surrounded by ~ or where the line starts with a negative emoji like :no_pedestrians: means that the task mentioned there was not completed - please exclude these lines from your emoji output. If the messages express deep sadness or high stress, please use :people_hugging: to express comfort instead of something more specific for that part of the text. For example if someone's relative died please react with a hug instead of with an emoji representing the relative or death. Also, please use ungendered emojis, for example, :cook: is preferred over :female-cook: or :male-cook:",
            }, 
            {
              "role": "user",
              "content": event["text"]
            }, 
          ],
          model="gpt-4",
      )
      reply = chat_completion.choices[0].message.content
      print(f"{reply}")
      reply = reply.strip().strip(":")
      emojis = re.split(r':\s*:*', reply)
      for emoji in emojis:
        try:
          client.reactions_add(
            channel=event["channel"],
            timestamp=event["ts"],
            name=f"{emoji}",
          )
        except Exception as e:
          logger.error(f"Error publishing {emoji} emoji react: {repr(e)}")
    except Exception as e:
      logger.error(f"Error getting emojis from OpenAI: {repr(e)}")

# Ready? Start your app!
if __name__ == "__main__":
    app.start(port=3000)
