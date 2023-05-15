import discord
import json
import os
from dotenv import dotenv_values
from utils import *

ENV = dotenv_values(".env")

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
intents.members = True
intents.reactions = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)
games = []

include("commands/create.py")
include("commands/send.py")
include("commands/end.py")
include("commands/add.py")
include("commands/remove.py")
include("commands/settings.py")

include("events/on_reaction_add.py")
include("events/on_reaction_remove.py")

@client.event
async def on_ready():
    await tree.sync()
    if not os.path.exists("config.json"):
        with open("config.json", "w") as config:
            json.dump({}, config)
    print(f"{client.user} Ready!")

client.run(ENV["TOKEN"])