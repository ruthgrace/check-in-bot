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

0. my old server is Ubuntu 16 and I'm too lazy to upgrade it,but I also want to be able to use fstrings; instructions to install python3.7 on Ubuntu 16 here https://stackoverflow.com/questions/77005109/how-do-i-install-python3-7-on-ubuntu-16 . Make sure to run `./configure --enable-loadable-sqlite-extensions --enable-optimizations` before running make as per https://stackoverflow.com/questions/1210664/no-module-named-sqlite3
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
sudo chown -R www-data:www-data .venv
```

3. make sure you have your domain. mine is check-in-bot.ruthgracewong.com (subdomain managed via digital ocean)
4. symlink `nginx/check-in-bot` file to nginx config

```
sudo ln -fs /var/www/check-in-bot/nginx/check-in-bot.bootstrap /etc/nginx/sites-available/check-in-bot
sudo ln -fs /etc/nginx/sites-available/check-in-bot /etc/nginx/sites-enabled/check-in-bot
```

4. run `sudo service nginx reload`
5. make SSL certificates for HTTPS

```
certbot certonly --force-renewal -a webroot -w /var/www/check-in-bot -d www.check-in-bot.ruthgracewong.com -w /var/www/check-in-bot -d check-in-bot.ruthgracewong.com
```

5. make sure that auto renewal of SSL cert is set up e.g. https://onepagezen.com/letsencrypt-auto-renew-certbot-apache/
6. now that the SSL certs are made, put up the production nginx config

```
sudo ln -fs /var/www/check-in-bot/nginx/check-in-bot /etc/nginx/sites-available/check-in-bot
sudo service nginx reload
```

7. set up process manager by symlinking check-in-bot.service to `/etc/systemd/system/`

```
sudo ln -fs /var/www/check-in-bot/check-in-bot.service /etc/systemd/system/check-in-bot.service
```

8. start the service

```
sudo systemctl daemon-reload
sudo service check-in-bot start
```

## production maintenance

### manually renew SSL

```
sudo certbot renew
```
