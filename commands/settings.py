import discord
import json
import typing
from bot import tree
from utils import *

@tree.command(name="settings", description="Display or change a Secret Thrower setting")
@discord.app_commands.describe(voting_timer="The length of time in seconds for voting")
@discord.app_commands.describe(thrower_info="Show the number of throwers on each team and tell the throwers who their counterpart(s) are (if they exist)")
async def settings(interaction: discord.Interaction, voting_timer: typing.Optional[int], thrower_info: typing.Optional[bool]):
    global json
    guild = str(interaction.guild.id)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    if guild not in config:
        config[guild] = game_config()
    if voting_timer:
        config[guild]['voting_timer'] = voting_timer
        await interaction.channel.send(f"Changed the Secret-Thrower voting_timer setting to {voting_timer} seconds", delete_after=60.0)
    if thrower_info != None:
        config[guild]['thrower_info'] = thrower_info
        await interaction.channel.send(f"Changed the Secret-Thrower thrower_info setting to {thrower_info}", delete_after=60.0)
    with open('config.json', 'w') as config_out:
        json.dump(config, config_out, indent=4)
    embed=discord.Embed()
    embed.add_field(name="Setting", value=''.join(str(i) + '\n' for i in config[guild].keys()))
    embed.add_field(name="Value", value=''.join(str(i) + '\n' for i in config[guild].values()))
    await interaction.response.send_message(embed=embed)
