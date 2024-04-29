# Tutorial: Setting up OAuth with a Slack bot app on Python

There doesn't seem to be a good tutorial on how to use slack_bolt to do oauth for slack bot apps with Python. I think it might be possible without using slack_sdk directly since slack_bolt imports pieces of it. So i'll try to write a tutorial as I figure it out. This tutorial assumes you already know how to code - you can follow it exactly if you want but you would have to pay for the same things I'm paying for (OpenAI, Supabase). Because I'm lazy to write code that I'm not going to use, sorry.

I already have [a bot working on my personal Slack workspace](https://github.com/ruthgrace/check-in-bot/tree/1f6785efa19413c7022634814d4414c28d9983fd). When my bot is added to a channel, it responds with 4 emojis whenever someone leaves a message. (TODO - for the tutorial replace this code with just thumbs-up reacts on each message so people don't have to pay for OpenAI just to do the tutorial)

basically what we are setting up is that when the bot app is made installable by other workspaces, you need a way for workspaces to authenticate with your app. This means that

1. you need to add features to your app to keep track of tokens for all the workspaces that have authenticated with you
2. when you get a request, you need to figure out which workspace it came from, and your response has to include the appropriate token.

## Make your add to slack button

https://api.slack.com/authentication/oauth-v2

TODO - add image

I added my button to my index.html page.

## Set up data store

I'm using supabase.
