import discord
from discord.ext import commands
from discord import app_commands

class Game(commands.Cog):
    def __init__(self, bot):
        pass

    game = app_commands.Group(name="game", description="Match lifecycle management")

    @game.command(name="setup", description="Initialize a Secret Thrower game")
    async def setup(self, interation: discord.Interaction):
        pass

    @game.command(name="add", description="Add/move a player to a Secret Thrower team")
    async def add(self, interaction: discord.Interaction, user: discord.Member): #team, player
        #Find game
        
        if game.state != State.SETUP:
            pass#Should be a function that handles inccorect game state
        
        for game_team in game.get_teams():
            for player in game_team.players:
                if player.member.id == user.id:
                    game_team.players.remove(player)
        for game_team in game.get_teams():
            #If its not the team we selected continue
            game_team.players.append(Player(user, 0, [None, None], [[], []]))

        game.message = await = game.message.edit(embed=game.build_embed())
        return await interaction.response.send_message(
            f"Added: {user.name} to {team.name}", ephemeral=True, delete_after=60.0
        )

    @game.command(name="remove", description="")
    async def remove(self, interaction: discord.Interaction, user: discord.Member):
        #Find game

        if game.state != State.SETUP:
            pass#Should be a function that handles inccorect game state

        for team in game.get_teams():
            for player in team.players:
                if player.member.id == user.id:
                    team.players.remove(player)
                    game.message = await game.message.edit(embed=game.build_embed())
                    return await interaction.response.send_message(
                        f"Removed: {user.name}", ephemeral=True, delete_after=60.0
                    )

        return await interaction.response.send_message(
            f"Game does not have player: {user.name}", ephemeral=True, delete_after=60.0
        )
    
    @game.command(name="cancel", description="")
    async def cancel(self, interaction: discord.Interaction):
        pass #Need to find the game by the user that started it. Based on the server and the user

    @game.command(name="start", description="")
    async def start(self, interaction: discord.Interaction, team1_count: int = 1, team2_count: int = 1): #team 1 count, team 2 count
        #Find game

        if game.state != GameState.SETUP:
            pass #Use a method like above

        thrower_info = game.settings.thrower_info
        #Get the amount of games since the players have last thrown and determine probabilities
        
        team1_count = len(game.team1.players) if len(game.team1.players) < team1_count else team1_count
        team2_count = len(game.team2.players) if len(game.team2.players) < team2_count else team2_count
        #Assign throwers

        for team in game.get_teams():
            for player in team.players:
                message = "You are the secret thrower! Your goal is to lose the game without being discovered by others. "

                await player.member.send(message)
        
        game.state = GameState.PLAYING
        await interaction.response.send_message(
            f"Secret Thrower count -> Team1: {team1_count}, Team2: {team2_count}",
            ephemeral=not thrower_info,
            delete_after=60.0,
        )
        await interaction.channel.send("Secret Throwers have been assigned", delete_after=60.0)
        game_time = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
        #Update game time locally. DO not commit data

    @game.command(name="result", description="")
    async def result(self, interaction: discord.Interaction):
        pass

    
async def setup(bot):
    await bot.add_cog(Game(bot))