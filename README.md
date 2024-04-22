# emojiBot

automatically adds emoji reacts to each message in channel

## dev setup

1. add bot_token with string value of oauth token to tokens.py
2. make venv `python3 -m venv .venv`
3. install ngrok https://ngrok.com/download
4. `pip install -r requirements.txt`

reference tutorial: https://api.slack.com/start/building/bolt-python

This app needs group.history and reactions.write scope permissions, and the message.groups event subscription.

### setup debugging - [SSL: CERTIFICATE_VERIFY_FAILED]

Run this file on mac (click on it): `/Applications/Python\ 3.*/Install\ Certificates.command`

## dev process

1. activate venv `source .venv/bin/activate`
2. `ngrok http 3000`
3. update slack bot Event Subscriptions > Request URL setting with the ngrok URL, adding `/slack/events` on the end
4. `python3 app.py`

## Ruth to do

- productionize
