import discord
from discord.ext import tasks, commands
import random
import time
from dotenv import dotenv_values

CONFIG = dotenv_values(".env")
OPTIONS = [{'regional_indicator_a':'🇦','regional_indicator_b':'🇧','regional_indicator_c':'🇨','regional_indicator_d':'🇩','regional_indicator_e':'🇪','regional_indicator_f':'🇫','regional_indicator_g':'🇬','regional_indicator_h':'🇭','regional_indicator_i':'🇮',},{'one':'1️⃣','two':'2️⃣','three':'3️⃣','four':'4️⃣','five':'5️⃣','six':'6️⃣','seven':'7️⃣','eight':'8️⃣','nine':'9️⃣'}]
VS = '🆚'
WINNER = '👑'
THROWER = '🕵️'

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
intents.members = True
intents.reactions = True
client = discord.Client(intents=intents)

teams = {}
blacklist=[]
throwers = []
timer=60
current_message=None

def players(state):
    keys = list(teams.keys())
    if len(keys) != 2:
        return
    player_list = []
    for i in range(0, len(teams)):
        string=""
        for j, key in enumerate(teams[keys[i]]):
            if state == 'voting':
                string += ":" + list(OPTIONS[i].keys())[j] + ": "
            if state == 'complete' and key in throwers:
                string += THROWER
            string += key
            if state == 'complete':
                string += " : " + str(teams[keys[i]][key])
            string += "\n"
        player_list.append(string)
    return player_list[0], player_list[1]

async def Create(message):
    parameters = message.content.split(" ")[1:]

    if len(parameters) != 2:
        await message.channel.send("Incorrect parameters.  Expected: Create Team1 Team2", delete_after=60.0)
        return
    global current_message
    if current_message != None:
        await message.channel.send("Already in a game", delete_after=60.0)
        return

    current_message=None
    teams.clear()
    throwers.clear()
    for channel in message.guild.channels:
        if channel.name in parameters:
            teams[channel.name] = {}
            for member in channel.members:
                if member.name in blacklist:
                    continue
                teams[channel.name][member.name] = 0

    if len(teams.keys()) != 2:
        string = ""
        for i in range(0, len(parameters)):
            if parameters[i] not in list(teams.keys()):
                string += parameters[i] + " "
        await message.channel.send(f"Could not find channel(s): {string}", delete_after=60.0)
        teams.clear()
        return
    elif len(teams[parameters[0]]) == 0:
        await message.channel.send(f"{parameters[0]} is empty", delete_after=60.0)
        teams.clear()
        return
    elif len(teams[parameters[1]]) == 0:
        await message.channel.send(f"{parameters[1]} is empty")
        teams.clear()
        return
    team1, team2 = players('')
    embed = discord.Embed(title="Secret Thrower")
    embed.add_field(name=parameters[0], value=team1)
    embed.add_field(name=parameters[1], value=team2)
    current_message = await message.channel.send(embed=embed)

async def Send(message):
    if current_message == None:
        await message.channel.send("Not currently in a game", delete_after=60.0)
        return

    keys = list(teams.keys())
    throwers.append(random.choice(list(teams[keys[0]])))
    throwers.append(random.choice(list(teams[keys[1]])))
    for name in throwers:
        user = client.get_user(discord.utils.get(message.guild.members, name=name).id)
        await user.send("You are the secret thrower! Your goal is to lose the game without being found", delete_after=60.0)
    await message.channel.send("Secret Throwers have been assigned", delete_after=60.0)

async def End(message):
    if current_message == None:
        await message.channel.send("Not currently in a game", delete_after=60.0)
        return

    parameters = message.content.split(" ")[1:]
    if len(parameters) != 1:
        await message.channel.send("Incorrect paramters. Expected: End Winner", delete_after=60.0)
        return
    keys = list(teams.keys())
    if parameters[0] not in keys:
        await message.channel.send(f"No team with name: {parameters[0]}", delete_after=60.0)
        return
    if len(throwers) == 0:
        await message.channel.send("No throwers assigned. Use 'Send' to assign throwers")
        return

    embed = current_message.embeds[0]
    team1, team2 = players('voting')
    team1_name = keys[0]
    if parameters[0] == keys[0]:
        team1_name += " " + WINNER
    team2_name = keys[1]
    if parameters[0] == keys[1]:
        team2_name += " " + WINNER
    embed.description = "Voting ends <t:" + str(int(time.time()) + timer) + ":R>"
    embed.set_field_at(0, name=team1_name, value=team1)
    embed.set_field_at(1, name=team2_name, value=team2)
    sent_message = await current_message.edit(embed=embed)
    for index in range(0, len(teams[keys[0]])):
        await sent_message.add_reaction(list(OPTIONS[0].values())[index])
    await sent_message.add_reaction(VS)
    for index in range(0, len(teams[keys[1]])):
        await sent_message.add_reaction(list(OPTIONS[1].values())[index])
    countdown.start(message.channel, sent_message.id)

async def Whitelist(message):
    parameters = message.content.split(" ")[1:]

    if len(parameters) == 0:
        await message.channel.send("Incorrect parameters.  Expected: Whitelisted Player", delete_after=60.0)
        return
    
    for player in parameters:
        if player in blacklist:
            blacklist.remove(player)
            await message.channel.send(f"Whitelisted: {player}", delete_after=60.0)
        else:
            await message.channel.send(f"Already whitelisted: {player}", delete_after=60.0)

async def Blacklist(message):
    parameters = message.content.split(" ")[1:]

    if len(parameters) == 0:
        await message.channel.send("Incorrect parameters.  Expected: Blacklisted Player", delete_after=60.0)
        return
    
    for player in parameters:
        if player not in blacklist:
            blacklist.append(player)
            await message.channel.send(f"Blacklisted: {player}", delete_after=60.0)
        else:
            message.channel.send(f"Already blacklisted: {player}", delete_after=60.0)

async def Help(message):
    string="Secret Thrower commands: \n"
    for key in commands:
        string += "- " + key + "\n"
    await message.channel.send(f"{string}", delete_after=60.0)

async def Show(message):
    string="Blacklisted players:\n"
    for i in range(0, len(blacklist)):
        string += "- " + blacklist[i] + "\n"
    await message.channel.send(string, delete_after=60.0)

async def Timer(message):
    parameters = message.content.split(" ")[1:]

    if(len(parameters) > 1 or len(parameters) == 0):
        await message.channel.send("Incorrect parameters expected: Timer time", delete_after=60.0)
        return

    if not parameters[0].isnumeric():
        await message.channel.send("Time should be a whole number", delete_after=60.0)
        return

    global timer
    timer = parameters[0]
    await message.channel.send(f"Timer updated to: {timer}s", delete_after=60.0)

commands = {
    'Create': Create,
    'Send': Send,
    'Whitelist': Whitelist,
    'Blacklist': Blacklist,
    'End': End,
    'Help': Help,
    'Show': Show,
    'Timer': Timer
}

@client.event
async def on_ready():
    print(f"{client.user} ready!")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    if message.channel.name != 'custom-games':
        return

    command = message.content.split(' ')[0]
    if command in commands:
        await commands[command](message)
    else:
        await message.channel.send("Command not found. Try 'Help' to see possible commands", delete_after=60.0)
    await message.delete()

@client.event
async def on_message_delete(message):
    if message.author == client.user:
        return
    
    if message.channel.name != 'custom-games':
        return

    global current_message
    if message == current_message:
        current_message = None

@client.event
async def on_reaction_add(reaction, user):
    if reaction.message != current_message:
        return

    keys = list(teams.keys())
    if user.name not in teams[keys[0]] and user.name not in teams[keys[1]]:
        return

    reactions = reaction.message.reactions
    for i in range(0, len(teams.keys())):
        option_values = list(OPTIONS[i].values())
        if reaction.emoji not in option_values:
            continue
        for j, key in enumerate(teams[keys[i]]):
            current_reaction = [emoji for emoji in reactions if emoji.emoji == option_values[j]]
            if current_reaction == None:
                continue
            current_reaction == current_reaction[0]
            if option_values[j] == reaction.emoji:
                teams[keys[i]][key] += 1
            elif user.name in [user.name async for user in current_reaction.users()]:
                await reaction.message.remove_reaction(current_reaction, user)

@client.event
async def on_reaction_remove(reaction, user):
    if reaction.message != current_message:
        return

    keys = list(teams.keys())
    user = user.name
    if user not in teams[keys[0]] and user not in teams[keys[1]]:
        return

    option_values_team1 = list(OPTIONS[0].values())
    for index, key in enumerate(teams[keys[0]]):
        if option_values_team1[index] == reaction.emoji:
            teams[keys[0]][key] -= 1

    option_values_team2 = list(OPTIONS[1].values())
    for index, key in enumerate(teams[keys[1]]):
        if option_values_team2[index] == reaction.emoji:
            teams[keys[1]][key] -= 1

@tasks.loop(seconds=1)
async def countdown(channel, id):
    try:
        message = await channel.fetch_message(id)
    except:
        return
    embed = message.embeds[0]
    timestamp = int(embed.description.split(":")[1])
    if time.time() >= timestamp:
        await message.clear_reactions()
        team1, team2 = players('complete')
        embed.description = None
        embed.set_field_at(0, name=embed.fields[0].name, value=team1)
        embed.set_field_at(1, name=embed.fields[1].name, value=team2)
        await message.edit(embed=embed)
        global current_message
        current_message = None
        countdown.stop()

client.run(CONFIG["TOKEN"])