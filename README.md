# check-in-bot

automatically adds emoji reacts to each message in channel

## dev setup

1. add tokens.py with contents (fill in tokens)

```
bot_token = "fill-in-your-bot-token"
bot_signing_secret = "fill-in-your-bot-signing-secret"
open_ai_key = "fill-in-your-openai-key"
```

2. make venv `python3 -m venv .venv`
3. activate `source .venv/bin/activate`
4. install ngrok https://ngrok.com/download
5. `pip install -r requirements.txt`

reference tutorial: https://api.slack.com/start/building/bolt-python

This app needs group.history and reactions.write scope permissions, and the message.groups event subscription.

### setup debugging - [SSL: CERTIFICATE_VERIFY_FAILED]

Run this file on mac (click on it): `/Applications/Python\ 3.*/Install\ Certificates.command`

## dev process

1. activate venv `source .venv/bin/activate`
2. `ngrok http 3000`
3. update slack bot Event Subscriptions > Request URL setting with the ngrok URL, adding `/slack/events` on the end
4. `python3 app.py`

## production set up

1. clone this repo to /var/www/
2. add tokens.py with contents (fill in tokens)

```
bot_token = "fill-in-your-bot-token"
bot_signing_secret = "fill-in-your-bot-signing-secret"
open_ai_key = "fill-in-your-openai-key"
```

3. install python deps

```
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip3 install -r requirements.txt
```

3. make sure you have your domain. mine is check-in-bot.ruthgracewong.com (subdomain managed via digital ocean)
4. symlink `nginx/check-in-bot` file to nginx config

set up SELinux
```
sudo chcon -t httpd_config_t /var/www/check-in-bot/nginx/check-in-bot.bootstrap
sudo chcon -t httpd_config_t /var/www/check-in-bot/nginx/check-in-bot
sudo chcon -t httpd_sys_content_t /var/www/check-in-bot
```


```
sudo ln -fs /var/www/check-in-bot/nginx/check-in-bot.bootstrap /etc/nginx/conf.d/check-in-bot.conf
```

5. run `sudo service nginx reload`
6. make SSL certificates for HTTPS

```
sudo certbot certonly --force-renewal -a webroot -w /var/www/check-in-bot -d www.check-in-bot.ruthgracewong.com -w /var/www/check-in-bot -d check-in-bot.ruthgracewong.com
```

7. make sure that auto renewal of SSL cert is set up e.g. https://onepagezen.com/letsencrypt-auto-renew-certbot-apache/
8. now that the SSL certs are made, put up the production nginx config

```
sudo ln -fs /var/www/check-in-bot/nginx/check-in-bot /etc/nginx/conf.d/check-in-bot.conf
sudo service nginx reload
```

9. set up process manager by COPYING check-in-bot.service to `/etc/systemd/system/`

```
sudo cp /var/www/check-in-bot/check-in-bot.service /etc/systemd/system/check-in-bot.service
```

10. start the service

```
sudo systemctl daemon-reload
sudo service check-in-bot start
```

## production maintenance

### manually renew SSL

```
sudo certbot renew
```

## Setting up the Cron Service

After setting up the main service, set up the cron service that handles scheduled tasks:

1. Create the service and timer files:
```
sudo cp -f check-in-bot-cron.service /etc/systemd/system/check-in-bot-cron.service
sudo cp -f check-in-bot-cron.timer /etc/systemd/system/check-in-bot-cron.timer
```

2. Enable and start the timer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable check-in-bot-cron.timer
sudo systemctl start check-in-bot-cron.timer
```

3. Verify the timer is running:
```bash
journalctl -u check-in-bot-cron.service
```

The cron service will run daily at 15:00 UTC (8am Pacific) and perform these tasks:
- On the 25th: Announce signups for next month's check-in groups
- On the last day: Create channels and add participants
- On the 1st and 2nd: Add late signups to existing groups
- On the 7th: Send reminders to inactive members
- On the 11th: Remove inactive members

## notes

this doesn't work for enterprise installations (see code in cron.py)

## to do

* archive all channels with a specific year/string