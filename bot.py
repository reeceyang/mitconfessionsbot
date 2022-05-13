# bot.py
import os
import sys
import discord
from discord.ext import tasks
from dotenv import load_dotenv
from facebook_scraper import get_posts
import json
import pymongo

load_dotenv()
channels = set()

client = pymongo.MongoClient(os.getenv('MONGODB_CONN_STR'), serverSelectionTimeoutMS=5000)
db = client.Cluster0
collection = db.confessions

def insert_confession(post, number):
    confession = {**post, 'number': number}
    print('inserted',number,'with id',collection.insert_one(confession).inserted_id)

try:
    print(client.server_info())
except Exception:
    print("Unable to connect to the server.")

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
# def get_post_text(text):
#    return text
#    FIXME: why is facebook-scraper like this
#    lines = text.split("\n")
#    like_index = lines.index("Like")
#    if "Comment" in lines[like_index - 1]:
#        post_index = like_index - 3
#    elif lines[like_index - 1].isdigit():   
#        post_index = like_index - 2
#    else:
#        post_index = like_index - 1
#    # print(lines[0:like_index])
#    return "\n".join(lines[0:post_index + 1])

def format_confession(post):
    """take in a post object and return a list of strings to be messaged in discord"""
    text = bold_number(post['post_text'])
    if post['post_id'] is not None:
        link = "https://www.facebook.com/" + post['post_id']
    elif post['w3_fb_url'] is not None:
        link = post['w3_fb_url']
    elif post['post_url'] is not None:
        link = post['post_url']
    else:
        link = ''
    text += '\n<' + link + '>'
    return split_confession(text)

def split_confession(text):
    if len(text) <= 2000:
        return [text]
    else:
        split_index = 1999
        punctuation = ' .\n:;,!?'
        if any([char in text for char in punctuation]):
            while text[split_index] not in punctuation:
                split_index -= 1
        return [text[:split_index + 1]] + split_confession(text[split_index + 1:])

def bold_number(text):
    first_space = text.index(" ")
    return "**" + text[0:first_space] + "**" + text[first_space:]

def get_number(text): 
    return int(text[1:text.index(" ")])

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

async def update_confessions(channel):
    global last_number
    max_number = last_number
    got_confessions = False
    posts = []
    lowest_number = last_number + 2
    pages = 16
    while lowest_number > last_number + 1:
        posts, lowest_number = get_confessions(pages, last_number)
        pages *= 2
    for post in posts:
        try:
            text = post['post_text']
            number = get_number(text)
            max_number = max(max_number, number)
            response_list = format_confession(post)
            for response in response_list:
                await channel.send(response)
            insert_confession(post, number)
            got_confessions = True
        except Exception as e:
            print(str(e))
    last_number = max_number
    dump_storage()
    return got_confessions

def get_confessions(num_pages, stop_number=None):
    """return a list of posts and the lowest confession number retrieved"""
    posts = []
    print("getting confessions")
    number = None
    for post in get_posts('beaverconfessions', cookies="cookies-facebook-com.txt", pages=num_pages):
        text = post['post_text']
        # ignore pinned post
        if text[0] != "#": 
            continue 
        number = get_number(text)
        if stop_number is not None and number <= stop_number:
            break
        print("got confession", number)
        posts.insert(0, post) 
    assert number is not None
    return posts, number + 1

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
#    if message.content == "getconfess":
#        await get_confessions(message.channel)
#    if message.content == "getconfess recent":
#        pass
#        # await get_recent_confessions(message.channel)
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
        if not await update_confessions(channel):
            await message.channel.send("no new confessions")

@my_background_task.before_loop
async def my_background_task_before_loop():
    await client.wait_until_ready()

my_background_task.start()
client.run(TOKEN)

