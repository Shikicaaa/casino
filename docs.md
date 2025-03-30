## About the project
This is a online gambling project that implements **provably fair system** that ensures transparency and fairness of the game.
## Installation
To install all required dependencies and libraries use this command.
```bash
pip install -r requirements.txt 
```
To start the application use:
```bash
cd kockarnica
py manage.py runserver 8000
```
this ensures that application is run on localhost at port 8000
To make changes to database and apply them use:
```bash
py manage.py makemigrations
py manage.py migrate
```
## Technical implementation
### Crash Game
Server generates **server_seed** and its **nonce**, hashes it and sends out **hashed_server_seed**, after the game ends - game sends it's **server_seed** and **nonce (number used once)** so player can calculate the outcome. Player can calculate the outcome using this function:
```python
def calculate_crash_point(server_seed, client_seed="default_client_seed", nonce):
    hash_input = f"{server_seed}-{client_seed}-{nonce}".encode()
    hashed = hashlib.sha256(hash_input).hexdigest()
    number = int(hashed[:8],16)
    return max(1.0, (10000.0/(number % 10000 + 1)))
```

## API Documentation
### Crash Game
**POST** /api/new_game/
Returns
**200 OK**
```json
{
    "hashed_server_seed" : "hashed_seed"
}
```
**POST** /api/verify_game/
Request
```json
{
    "server_seed" : "server_seed",
    "client_seed" : "default_client_seed",
    "nonce" : nonce
}
```
Returns
**200 OK**
```json
{
    "crash_point" : expected_crash
}
```

**GET** /api/reveal_seed/
Returns
**200 OK**
```json
{
    "server_seed" : "server_seed"
}
```
### Login and authentification
**POST** /api/register/
Request
```json
{
    "username" : "username",
    "email" : "email@domain.com",
    "password" : "password",
    "confirm_password" : "confirmed_password"
}
```
**400 Bad Request**
Raises *ValidationError* if passwords do not match.
Returns
**200 OK**
```json
{
    "username" : "username",
    "email" : "email@domain.com"
}
```

**POST** /api/login/
Request
**200 OK**
```json
{
    "email" : "email@domain.com",
    "password" : "password"
}
```
Returns
**200 OK**
```json
{
    "token" : "a very big encoded string that is used to authenticate user"
}
```

**POST** /api/verify/
**200 OK**
Request
```json
{
    "token" : "a very big encoded string that is used to authenticate user"
}
```
Returns
If valid:
**200 Ok**
```json
{
    "valid" : True,
    "user_id" : id_of_user,
    "email" : "email@domain.com"
}
```
Else:
**401 Bad Request**
```json
{
    "valid" : False
}
```
**POST** /api/logout/
Request
```json
{
    "token" : "a very big encoded string that is used to authenticate user"
}
```

Returns:
On success
**200 OK**
```json
{
    "message" : "User logged out successfully"
}
```
If user already logged out:
**401 Unauthorized**
```json
{
    "error" : "Token is blacklisted"
}
```
If token is empty:
**400 Bad request**
```json
{
    "error" : "Token is required"
}
```
If token has expired:
**400 Bad Request**
```json
{
    "error" : "Token has expired"
}
```
If token is invalid:
**400 Bad Request**
```json
{
    "error" : "Invalid token"
}
```

### Socket communication
#### On connection
```json
{
    "status" : "connected"
}
```
If authentication failed

```json
{
    "error" : "Authentication failed"
}
```

#### Cashing out
If auto cashout <= 1.0

```json
{
    "status" : "error",
    "message" : "Auto cashout must be greater than 1.0!"
}
```
If auto cashout already set

```json
{
    "status" : "error",
    "message" : "Auto cashout is already set."
}
```
If cashed out

```json
{
    "status" : "cashout",
    "message" f"User {user_id} cashed out {cashout_amount} with multiplier {multiplier}"
}
```
If cashout failed

```json
{
    "status" : "error",
    "message" : "Cannot cashout, not in game or already cashed out"
}
```
#### Joining game
If bet amount is less than 0.1

```json
{
    "status" : "error",
    "message" : "Bet must be greater than 0.1!"
}
```
If betting more than you have

```json
{
    "status" : "error",
    "message" : "Insufficient funds."
}
```
If game is running:

```json
{
    "status" : "in_queue",
    "message" : "Game is running. You are in queue"
}
```

If join success

```json
{    
    "status" : "joined",
    "message" : f"User {user_id} joined the game with {bet_amount} bet. Cashing out at {auto_cashout_at if auto_cashout_at != 0 else 'Not set'}"
}
```
#### Game running
On start 
```json
{
    "hash_server_seed" : "hashed_server_seed"
}
```
On time step
```json
{
    "multiplier" : multiplier,
    "status" : "running"
}
```

On game end
```json
{
    "crash_point": round(new_game.crash_point,2),
    "server_seed": new_game.server_seed,
    "nonce" : new_game.nonce,
    "status": "game_end",
}
```

Next game beginning
```json
{
    "status" : "game_ended",
    "message" : "Game starting in x seconds"
}
```