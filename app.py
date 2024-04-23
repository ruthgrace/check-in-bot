import tokens

from openai import OpenAI
import os
import re
# Use the package we installed
from slack_bolt import App
ai_client = OpenAI(
    api_key=tokens.open_ai_key,
)

# Initialize your app with your bot token and signing secret
app = App(
    token=tokens.bot_token,
    signing_secret=tokens.bot_signing_secret
)

# New functionality
@app.event("message")
def emoji_react(client, event, logger):
  try:
    print(event["text"])
    chat_completion = ai_client.chat.completions.create(
        messages=[
          {
            "role": "system",
            "content": "You are a intelligent assistant. You respond to all of the following messages with a single line representing five unique emojis, formatted for Slack. The emojis should represent things mentioned in the messages, with only zero or one emojis representing sentiment. Note that text surrounded by ~ or where the line starts with a negative emoji like :no_pedestrians: means that the task mentioned there was not completed - please exclude these lines from your emoji output. If the messages express deep sadness or high stress, please use :people_hugging: to express comfort instead of something more specific for that part of the text. For example if someone's relative died please react with a hug instead of with an emoji representing the relative or death. Also, please use ungendered emojis, for example, :cook: is preferred over :female-cook: or :male-cook:",
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
    print(f"{emojis}")
  except Exception as e:
    logger.error(f"Error getting emojis from OpenAI: {repr(e)}")
  for emoji in emojis:
    try:
      app.client.reactions_add(
        channel=event["channel"],
        timestamp=event["ts"],
        name=f"{emoji}",
        token=tokens.bot_token,
      )
    except Exception as e:
      logger.error(f"Error publishing {emoji} emoji react: {repr(e)}")

# Ready? Start your app!
if __name__ == "__main__":
    app.start(port=3000)