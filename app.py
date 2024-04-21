import os
# Use the package we installed
from slack_bolt import App

# Initialize your app with your bot token and signing secret
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# New functionality
@app.event("message")
def emoji_react(client, event, logger):
  try:
     app.client.reactions_add(
        channel=event.channels,
        timestamp=event.event_time,
        name="thumbsup",
        token=app.token
    )
  except Exception as e:
    logger.error(f"Error publishing emoji reacts: {e}")

# Ready? Start your app!
if __name__ == "__main__":
    app.start(port=int(os.environ.get("PORT", 3000)))