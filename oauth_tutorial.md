# Tutorial: Setting up OAuth with a Slack bot app on Python

There doesn't seem to be a good tutorial on how to use slack_bolt to do oauth for slack bot apps with Python. I think it might be possible without using slack_sdk directly since slack_bolt imports pieces of it. So i'll try to write a tutorial as I figure it out. This tutorial assumes you already know how to code - you can follow it exactly if you want but you would have to pay for the same things I'm paying for (OpenAI, Supabase). Because I'm lazy to write code that I'm not going to use, sorry.

I already have [a bot working on my personal Slack workspace](https://github.com/ruthgrace/check-in-bot/tree/1f6785efa19413c7022634814d4414c28d9983fd). When my bot is added to a channel, it responds with 4 emojis whenever someone leaves a message. (TODO - for the tutorial replace this code with just thumbs-up reacts on each message so people don't have to pay for OpenAI just to do the tutorial)

basically what we are setting up is that when the bot app is made installable by other workspaces, you need a way for workspaces to authenticate with your app. This means that

1. you need to add features to your app to keep track of tokens for all the workspaces that have authenticated with you
2. when you get a request, you need to figure out which workspace it came from, and your response has to include the appropriate token.

## Make your add to slack button

https://api.slack.com/authentication/oauth-v2

TODO - add image

I got

```
<a href="https://slack.com/oauth/v2/authorize?scope=groups%3Ahistory%2Cgroups%3Aread%2Cgroups%3Awrite%2Cgroups%3Awrite.invites%2Creactions%3Aread%2Creactions%3Awrite&amp;user_scope=&amp;redirect_uri=check-in-bot.ruthgracewong.com%2Fslack%2Foauth_redirect&amp;client_id=1560185583159.6993099351717" style="align-items:center;color:#000;background-color:#fff;border:1px solid #ddd;border-radius:4px;display:inline-flex;font-family:Lato, sans-serif;font-size:16px;font-weight:600;height:48px;justify-content:center;text-decoration:none;width:236px"><svg xmlns="http://www.w3.org/2000/svg" style="height:20px;width:20px;margin-right:12px" viewBox="0 0 122.8 122.8"><path d="M25.8 77.6c0 7.1-5.8 12.9-12.9 12.9S0 84.7 0 77.6s5.8-12.9 12.9-12.9h12.9v12.9zm6.5 0c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9v32.3c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9V77.6z" fill="#e01e5a"></path><path d="M45.2 25.8c-7.1 0-12.9-5.8-12.9-12.9S38.1 0 45.2 0s12.9 5.8 12.9 12.9v12.9H45.2zm0 6.5c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H12.9C5.8 58.1 0 52.3 0 45.2s5.8-12.9 12.9-12.9h32.3z" fill="#36c5f0"></path><path d="M97 45.2c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9-5.8 12.9-12.9 12.9H97V45.2zm-6.5 0c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9V12.9C64.7 5.8 70.5 0 77.6 0s12.9 5.8 12.9 12.9v32.3z" fill="#2eb67d"></path><path d="M77.6 97c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9-12.9-5.8-12.9-12.9V97h12.9zm0-6.5c-7.1 0-12.9-5.8-12.9-12.9s5.8-12.9 12.9-12.9h32.3c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H77.6z" fill="#ecb22e"></path></svg>Add to Slack</a>
```

## Set up data store

I'm using supabase.
