# bot.py
import os
import sys
import discord
from discord.ext import tasks
from dotenv import load_dotenv
from facebook_scraper import get_posts
import json

load_dotenv()
channels = set()

def read_config():
    """returns the json object stored in config.js"""
    with open('config.json') as f:
        return json.loads(f.read())

def read_storage():
    with open('storage.json') as f:
        return json.loads(f.read())

def dump_storage():
    with open('storage.json', 'w') as f:
        f.write(json.dumps({'last': last_number, 'channels': list(channels)}))
          
if read_config()['production']:
    TOKEN = os.getenv('DISCORD_TOKEN')
else:
    TOKEN = os.getenv('DISCORD_TOKEN_DEV')

last_number = 63836
channels = set()
try:
    storage = read_storage()
    if 'last' in storage:
        last_number = storage['last']
    if 'channels' in storage:
        channels = set(storage['channels'])
except FileNotFoundError:
    dump_storage()

client = discord.Client()
def get_post_text(text):
    lines = text.split("\n")
    like_index = lines.index("Like")
    if "Comment" in lines[like_index - 1]:
        post_index = like_index - 3
    elif lines[like_index - 1].isdigit():   
        post_index = like_index - 2
    else:
        post_index = like_index - 1
    # print(lines[0:like_index])
    return "\n".join(lines[0:post_index + 1])

def bold_number(text):
    first_space = text.index(" ")
    return "**" + text[0:first_space] + "**" + text[first_space:]

def get_number(text):
    return int(text[1:text.index(" ")])

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

with open('vars.json') as f:
    data = json.loads(f.read())
    last_number = data['last']

async def get_confessions(channel):
    global last_number
    print("getting confessions")
    max_number = last_number
    got_confessions = False
    for post in get_posts('beaverconfessions', cookies="cookies-facebook-com.txt", pages=10):
        text = get_post_text(post['post_text'])
        # ignore pinned post
        if text[0] != "#": 
            continue 
        number = get_number(text)
        if (number <= last_number):
            break
        max_number = max(max_number, number)
        response = bold_number(text)
        print("got confession",get_number(text))
        await channel.send(response)
        got_confessions = True
    last_number = max_number
    dump_storage()
    return got_confessions

async def get_recent_confessions(channel):
    for post in get_posts('beaverconfessions', cookies="cookies-facebook-com.txt", pages=3):
        text = get_post_text(post['post_text'])
        # ignore pinned post
        if text[0] != "#": 
            continue 
        response = bold_number(text)
        print("got confession",get_number(text))
        await channel.send(response)

@client.event
async def on_message(message):
    if message.content == "getconfess":
        await get_confessions(message.channel)
    if message.content == "getconfess recent":
        await get_recent_confessions(message.channel)
    if client.user.mentioned_in(message):
        if 'channel' in message.content:
            if 'set' in message.content:
                channels.add(message.channel.id)
                await message.channel.send('new confessions will be posted in #' + message.channel.name)
            if 'remove' in message.content:
                channels.discard(message.channel.id)
                await message.channel.send('new confessions will not be posted in #' + message.channel.name) 
            dump_storage()
            
@tasks.loop(minutes=60)
async def my_background_task():
    for channel_id in channels:
        channel = client.get_channel(channel_id)
        if not await get_confessions(channel):
            await message.channel.send("no new confessions")

@my_background_task.before_loop
async def my_background_task_before_loop():
    await client.wait_until_ready()

my_background_task.start()
client.run(TOKEN)

