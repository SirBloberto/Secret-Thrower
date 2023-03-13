import discord
import json
from bot import tree

@tree.command(name="timer", description="Set the current secret-thrower voting timer OR show current timer")
@discord.app_commands.describe(length="The length of time in seconds for voting")
async def timer(interaction: discord.Interaction, length: int=0):
    global json
    guild = str(interaction.guild.id)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    if guild not in config:
        config[guild] = 60
    if length == 0:
        await interaction.response.send_message(f"Current secret thrower voting timer is {config[guild]} seconds", ephemeral=True, delete_after=60.0)
    config[guild] = length
    with open('config.json', 'w') as config_out:
        json.dump(config, config_out, indent=4)
    await interaction.response.send_message(f"Changed the secret thrower voting timer to {length} seconds", ephemeral=True, delete_after=60.0)