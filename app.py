import tokens
import os
# Use the package we installed
from slack_bolt import App

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
     app.client.reactions_add(
        channel=event["channel"],
        timestamp=event["ts"],
        name="thumbsup",
        token=tokens.bot_token,
    )
  except Exception as e:
    logger.error(f"Error publishing emoji reacts: {repr(e)}")

# Ready? Start your app!
if __name__ == "__main__":
    app.start(port=int(os.environ.get("PORT", 3000)))