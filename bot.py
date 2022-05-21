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

def read_config():
    """returns the json object stored in config.js"""
    with open('config.json') as f:
        return json.loads(f.read())

if read_config()['production']:
    collection = db.confessions
else:
    collection = db.testing

def insert_confession(post, number):
    confession = {**post, 'number': number}
    print('inserted',number,'with id',collection.insert_one(confession).inserted_id)

def insert_confessions(posts):
    for post in posts:
        text = post['post_text']
        try:
            number = get_number(text)
        except ValueError:
            continue
        insert_confession(post, text)

try:
    print(client.server_info())
except Exception:
    print("Unable to connect to the server.")


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
    # HACK: wtf mit confessions admin
    if "#64205I" in text:
        return 64205
    return int(text[1:text.index(" ")])

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

async def update_confessions():
    """gets new confessions, posts them to all connected channels, and inserts them into database"""
    global last_number
    posts, max_number = get_new_posts()
    if len(posts) == 0:
        # no new confessions
        return False
    last_number = max_number
    dump_storage()
    insert_confessions(posts)
    for channel_id in channels:
        channel = client.get_channel(channel_id)
        await post_confessions(posts, channel)
    return True

def get_new_posts():
    """attempts to get any new confessions"""
    posts = []
    lowest_number = last_number + 2
    pages = 16
    max_number = last_number
    while lowest_number > last_number + 1:
        posts, lowest_number, max_number = get_confessions(pages, last_number)
        pages *= 2
    return posts, max_number

async def post_confessions(posts, channel):
    """post all confessions in `posts` to `channel`"""
    for post in posts:
        try:
            response_list = format_confession(post)
            for response in response_list:
                await channel.send(response)
        except Exception as e:
            print(str(e))
 
def get_confessions(num_pages, stop_number=None):
    """return a list of posts, the lowest number retrieved, and the highest confession number retrieved"""
    posts = []
    print("getting confessions")
    number = None
    max_number = 0
    for post in get_posts('beaverconfessions', cookies="cookies-facebook-com.txt", pages=num_pages):
        text = post['post_text']
        # ignore pinned post
        if text[0] != "#": 
            continue 
        try:
            number = get_number(text)
        except ValueError:
            continue
        max_number = max(max_number, number)
        if stop_number is not None and number <= stop_number:
            break
        print("got confession", number)
        posts.insert(0, post) 
    assert number is not None
    assert max_number != 0
    return posts, number + 1, max_number

async def show_recent_confessions(channel):
    posts, _, _ = get_confessions(2)
    await post_confessions(posts, channel)

@client.event
async def on_message(message):
    if message.content == "getconfess":
        if not await update_confessions():
            await message.channel.send('no new confessions')
    if message.content == "getconfess recent":
        await show_recent_confessions(message.channel)
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
    if not await update_confessions():
        print('no new confessions')

@my_background_task.before_loop
async def my_background_task_before_loop():
    await client.wait_until_ready()

my_background_task.start()
client.run(TOKEN)

