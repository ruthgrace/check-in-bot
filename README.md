# emojiBot

automatically adds emoji reacts to each message in channel

## dev setup

1. add bot_token with string value of oauth token to tokens.py
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
2. install python deps
```
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip3 install -r requirements.txt
sudo chown -R www-data:www-data .venv
```
3. make sure you have your domain. mine is emojibot.ruthgracewong.com (subdomain managed via digital ocean)
4. symlink `nginx/emojibot` file to nginx config

```
sudo ln -fs /var/www/emojiBot/nginx/emojibot.bootstrap /etc/nginx/sites-available/emojibot
sudo ln -fs /etc/nginx/sites-available/emojibot /etc/nginx/sites-enabled/emojibot
```

4. run `sudo service nginx reload`
5. make SSL certificates for HTTPS

```
certbot certonly --force-renewal -a webroot -w /var/www/emojiBot -d www.emojibot.ruthgracewong.com -w /var/www/emojiBot -d emojibot.ruthgracewong.com
```

5. make sure that auto renewal of SSL cert is set up e.g. https://onepagezen.com/letsencrypt-auto-renew-certbot-apache/
6. now that the SSL certs are made, put up the production nginx config

```
sudo ln -fs /var/www/emojiBot/nginx/emojibot /etc/nginx/sites-available/emojibot
sudo service nginx reload
```
7. set up process manager by symlinking emojibot.service to `/etc/systemd/system/`

```
sudo ln -fs /var/www/emojiBot/emojibot.service /etc/systemd/system/emojibot.service
```

8. start the service

```
sudo systemctl daemon-reload
sudo service emojibot start
```

## production maintenance

### manually renew SSL

```
sudo certbot renew
```

## Ruth to do

- set up python venv properly in production
