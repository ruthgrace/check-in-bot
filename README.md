# emojiBot

automatically add 3 emoji reacts to each message in channel

## dev setup

1. add bot_token with string value of oauth token to tokens.py
2. make venv `python3 -m venv .venv`
3. install ngrok https://ngrok.com/download
4. `pip install slack_bolt`

reference tutorial: https://api.slack.com/start/building/bolt-python

## dev process

1. activate venv `source .venv/bin/activate`
2. `export SLACK_BOT_TOKEN=xoxb-your-token`
3. `export SLACK_SIGNING_SECRET=your-signing-secret`
4. `ngrok http 3000`
5. `python3 app.py`
