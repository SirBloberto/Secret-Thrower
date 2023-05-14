import discord
import json
from bot import tree

@tree.command(name="settings", description="Display or change a Secret Thrower setting")
@discord.app_commands.describe(timer="The length of time in seconds for voting")
async def settings(interaction: discord.Interaction, timer: int=0):
    global json
    guild = str(interaction.guild.id)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    if guild not in config:
        config[guild] = 60
    if timer == 0:
        await interaction.response.send_message(f"Current secret thrower voting timer is {config[guild]} seconds", ephemeral=True, delete_after=60.0)
    config[guild] = timer
    with open('config.json', 'w') as config_out:
        json.dump(config, config_out, indent=4)
    await interaction.response.send_message(f"Changed the secret thrower voting timer to {timer} seconds", ephemeral=True, delete_after=60.0)