import discord
from bot import tree

@tree.command(name="help", description="Summarize Secret Thrower game loop and commands")
async def help(interaction: discord.Interaction):
    global tree

    commands = tree.get_commands()

    embed = discord.Embed(title="Secret Thrower")
    embed.add_field(name="Game Loop", value="1. create\n2. start\n3. end\n", inline=False)
    embed.add_field(name="Command", value='\n'.join([command.name for command in commands]))
    embed.add_field(name="Description", value='\n'.join([command.description for command in commands]))

    await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=300.0)
