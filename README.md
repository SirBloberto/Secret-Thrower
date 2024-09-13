# Secret-Thrower
## Invite Link
https://discord.com/api/oauth2/authorize?client_id=1061748245581267174&permissions=2147493952&scope=bot%20applications.commands
## Usage

### /create
Syntax: `/create team1:VoiceChannel team2:VoiceChannel ?info:String`

Description: Create a secret thrower game

### /start
Syntax: `/start ?team1_count:Integer ?team2_count:Integer`

Description: Assign the secret throwers and start the game

### /end
Syntax: `/end winner:VoiceChannel`

Description: End the secret thrower game and assign a winner

### /add
Syntax: `/add team:VoiceChannel player:Member`

Description: Add a player to a secret thrower team

### /remove
Syntax: `/remove player:Member`

Description: Remove a player from a secret thrower game

### /settings
Syntax: `/settings ?voting_timer:Integer ?thrower_info:Boolean`

Description: Set secret-thrower setting(s) and display current settings

### /statistics
Syntax: `/statistics`

Description: Get statistics on Secret-Thrower player

## Docker
docker-compose up --build -d