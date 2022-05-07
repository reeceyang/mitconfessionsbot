# bot.py
import os

import discord
from discord.ext import tasks
from dotenv import load_dotenv
from facebook_scraper import get_posts
import json

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

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

LAST_NUMBER = 63836
with open('vars.json') as f:
	data = json.loads(f.read())
	LAST_NUMBER = data['last']

async def get_confessions(message):
	global LAST_NUMBER
	print("getting confessions")
	max_number = LAST_NUMBER
	for post in get_posts('beaverconfessions', cookies="cookies-facebook-com.txt", pages=10):
		text = get_post_text(post['post_text'])
		# ignore pinned post
		if text[0] != "#": 
			continue 
		number = get_number(text)
		if (number <= LAST_NUMBER):
			break
		max_number = max(max_number, number)
		response = bold_number(text)
		print("got confession",get_number(text))
		await message.channel.send(response)
	if max_number == LAST_NUMBER:
		await message.channel.send("no new confessions")
	LAST_NUMBER = max_number
	with open('vars.json', 'w') as f:
		f.write(json.dumps({'last':LAST_NUMBER}))

@client.event
async def on_message(message):
	if message.content == "getconfess":
		await get_confessions(message)

@tasks.loop(minutes=60)
async def my_background_task():
	"""A background task that gets invoked every 10 minutes."""
	channel = discord.utils.get(client.get_all_channels(), name="mit-confessions")
	await channel.send('getconfess')

@my_background_task.before_loop
async def my_background_task_before_loop():
	await client.wait_until_ready()

my_background_task.start()
client.run(TOKEN)

