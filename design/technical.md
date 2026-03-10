# 

# ---

# Road to Riches Technical Design

# Intro

This section describes technical design for the actual implementation of the road to riches game. It does not need to be followed exactly, but any deviation needs to be approved and documented. The designs in this section have had much thought put into them and are likely the most *scalable and flexible* way to implement things, even if not the easiest.

This section does not have a clear overarching structure and instead is a random list of how to handle specific parts of the game.

# Client-Server Model

The game **will** be implemented with a client server model. This cannot be changed. The server is the source of truth for the game state and all events and actions that occur. The client is simply the UI that players use to interact with the game. A server may connect to up to N clients, where N is the number of players. 

## Benefits of this design:

* Easy to switch to add support for (P3) online play  
* Easy to develop multiple clients in different styles while only having one server codebase.  
* Prevents cheating as the server validates the state and actions taken at each step.   
* If playing locally, the client and server can easily run as separate processes on the same machine

## Tradeoffs

* Some logic has to be implemented twice  
* Syncing game state between players needs to be continuous, so other players can see what another is thinking, not just the result at the end of their turn

# Game State

The state of the game is relatively easy to represent. It has these components:

* Current player id  
* Board state  
  * Current board layout (all square types, locations, and waypoints)  
  * Alt board layouts (when switches are pressed)  
  * Board metadata  
    * Venture cards available  
    * Max dice roll, promotion info, etc  
  * Property owners  
  * Property values  
  * Property and district statuses  
* Stock state  
  * Stock prices  
* Player state  
  * Player positions (id of squares) and directions (id of a “from” square)  
  * Player levels  
  * Player ready cash  
  * Player stock ownership  
  * Player statuses  
* Event Queue, History, and Rewind stack  
  * The event queue represents the current, actual event that is taking place and what needs to follow.   
  * History contains all events that took place from the start of the game. It can be used for replays and analysis. Doesn’t need to be sent to each client every turn.   
  * Rewind stack contains events that are undoable. Pretty much this is only movement actions before the player confirms the square they will land on.

# Event Queue

Events in the game will be managed by a central queue. Each turn, the player starts with a basic “TURN” event in the queue, and it gets added to from there. The benefit of this approach is that it’s simple to debug and develop, supports a history and undoing action by rewinding the queue, and makes AI agents easy to add as they can simulate the event queue to decide what actions are best. Whenever an event is popped off, it is sent to the clients so they can update the UI including playing any animations. Sometimes the client may work ahead for example in the case of player movement. But internally it will always stay synced with the server. 

All boards will have the basic player events, where they get a “TURN(player id)” added at the start of their turn. Some boards will add board specific events if for example something needs to happen every other turn. (P2) Also, cameo characters are easy to add as they just get added into the queue like a normal player, such as “CAMEO\_TURN(cameo\_id)”.

## Sample Turn

Here is a sample turn, and the event queue that will populate and contract. This showcases the server side of things, throughout, the non-current player clients will have the events broadcast to them from the server so they can follow along. Let the player id be 0\.

Turn starts  
\[TURN(0)\]

TURN(0) is popped from the queue and handled by the system. It represents the start of the player’s turn, and they can choose any actions to take. It first sets the state.curr\_player\_id to 0\.

Player selects sell stock  
\[INIT\_SELL\_STOCK(0), TURN(0)\]

Since selling stock is a pre dice roll action and can be done unlimited times, TURN(0) is readded to the end of the queue (after the sell stock option) so the player can take additional actions.

INIT\_SELL\_STOCK(0) is popped off the queue. It represents player 0 selling stock. The server will hold this event until the player client sends a valid stock selling response (request?). In this case, lets say the player chooses to sell 10 stock in district C. Therefore their response is something like (just hypothetically)  
{  
sell\_stock {  
  player\_id: 0,  
  district\_id: 2, // C  
  quantity: 10,  
}  
}

The server verifies that this is valid by checking that player 0 does indeed have at least 10 stocks in district C. It then adds the appropriate event to the event queue, which is handling the stock selling response

\[SELL\_STOCK(0, 2, 10), TURN(0)\]

The SELL\_STOCK(0,2,10) represents the stock selling action. It cannot be undone after it’s processed. The server updates its internal state by lowering player 0’s stock in C by 10 and increasing their ready cash by the corresponding amount. Then since \>=10 stocks in a single district were sold, that stock price lowers following the formula in Gameplay Spec.

\[TURN(0)\]

Player 0 now takes another action. Let’s say they choose to try and trade one of their shops with one of player 3’s shops.

\[INIT\_TRADE\_SHOP(0), TURN(0)\]

Again, the TURN(0) is added because the player can take additional actions after trying (or succeeding) to trade shops. INIT\_TRADE\_SHOP(0) represents that 0 will start a shop trade. The server will wait for the trade response. Let’s say player 0 is offering two of their shops (ids 10, 11\) for one of player 3’s shops (id 20\) and 500G. Then the response looks something like  
{  
propsed\_trade {  
  sender: 0,  
  recipient: 3,  
  sender\_shops: \[10, 11\],  
  sender\_gold: 0,  
  recipient\_shops: \[20\],  
  recipient\_gold: 500,  
}  
}

The server verifies that this is a possible trade, and adds it to the queue:

\[PROPOSED\_TRADE\_SHOP(0, 3, \[10, 11\], 0, \[20\], 500), TURN(0)\]

PROPOSED\_TRADE\_SHOP(...) is popped off. It represents player 3’s option to accept or modify the trade. The server sends the info to player 3 and waits for a response. Let’s say player 3 thinks 500G is too much but would be willing to do it for 200G. Note that player 3 is only allowed to accept, cancel, or modify the gold. They cannot change the shops involved. Their response would be a proposed\_trade object:  
{  
propsed\_trade {  
  sender: 3,  
  recipient: 0,  
  sender\_shops: \[20\],  
  sender\_gold: 200,  
  recipient\_shops: \[10, 11\],  
  recipient\_gold: 0,  
}  
}

Note that the sender and receiver have flipped, as if the trade was initiated by player 3\. But on their client, 3 would only have the options accept, reject, and change gold. Now this new proposed trade is added to the queue:

\[PROPOSED\_TRADE\_SHOP(3, 0, \[20\], 200, \[10, 11\], 0), TURN(0)\]

So the proposed trade is popped off and sent to player 0\. Let’s say they accept the trade:  
{  
accepted\_gold {  
  sender: 0,  
  recipient: 3,  
  sender\_shops: \[10, 11\],  
  sender\_gold: 0,  
  recipient\_shops: \[20\],  
  recipient\_gold: 200,  
}  
}

The sender and recipient have flipped back. Basically, the sender will be the player who is taking action on the trade. Now, the event queue contains the accepted trade.

\[TRADE\_SHOP(0, 3, \[10, 11\], 0, \[20\], 500), TURN(0)\]

The server pops off TRADE\_SHOP(...) and updates the game state accordingly. Then, the queue is just TURN(0) which gets popped off, allowing player 0 to input more actions. Let’s say they finally decide to roll the dice:

\[ROLL(0)\]

Note that TURN(0) is finally removed from the queue, since after rolling player 0 will not be able to take any more actions (voluntarily). At this point the server pops off the ROLL(0). The server generates a random number from 1-max roll (usually 6). Meanwhile, the client plays the dice roll animation which will land on the number returned from the server. A MOVE event is added to the queue representing that the player is now moving on the board. Let’s say the player rolls a 4\.

\[WILL\_MOVE(0, 4, 4)\]

Note that the WILL\_MOVE operation has 3 parameters: the player id, the total roll, and the number of squares left. The total roll is needed because the player can go backwards to undo a turn before finally stopping and committing to a path/final square. But to go backwards, we need to remember the starting square of the player, which we will do via the total roll. If total roll \= squares left, they cannot continue backwards. The server pops off the WILL\_MOVE which represents waiting for the player input. The player's response should be a valid square based on their “from” square and the waypoints of the current square. Let’s say they move from square 60 to square 61:  
{  
player\_move: {  
  from: 60  
  to: 61  
}  
}

Now, the server will add these events to the queue:

\[MOVE(0, 60, 61), PASS\_SQUARE\_ACTION(0, 61), WILL\_MOVE(0, 4, 3)\]

MOVE represents the player movement. The server pops it off and updates the player position. PASS\_SQUARE\_ACTION(0, 61\) represents the player passing square 61\. If the square has a pass action, it will add those events to the queue when popped off. Otherwise, it will get popped off and do nothing. In this case, let’s say square 61 was a normal square so nothing happens. If a player (or npc/cameo) had been on square 61, we would also add a PASS\_PLAYER\_ACTION(0, p\_id), which could have a variety of effects depending on the player statuses or what npc is passed. WILL\_MOVE(0, 4, 3\) is the next opportunity for the player. When the server pops it off, it again represents waiting for player input. Let’s say the player moves to square 62\.

\[MOVE(0, 61, 62), PASS\_ACTION(0, 62), WILL\_MOVE(0, 4, 2)\]

Square 62 was actually a checkpoint owned by player 1, which does have a pass action. Therefore, it resolves and is added to the event queue:

\[PAY\_RENT\_CKPT(0, 1, 62), WILL\_MOVE(0, 4, 2)\]

PAY\_RENT\_CKPT event is then popped off and resolved, which means the checkpoints current toll is paid from player 0 to player 1\. Vacant plots usually have special rent functions, which is why it uses PAY\_RENT\_CKPT instead of PAY\_RENT. (Though in the implementation, these may end up being the same it’s best to keep them separate for now). 

\[WILL\_MOVE(0, 4, 2)\]

Now, let’s say the player decides to undo the previous move, which is a valid option from this state as 4 \!= 2\.   
{  
player\_undo\_move: {  
  from: 61  
  to: 62   
}  
}

Every change to the game state should be saved in a log until an undoable move is reached. So in this case, we would have saved the previous state before the move and can directly roll back to that. State also includes the event queue, so that comes back for free:

\[MOVE(0, 61, 62), PASS\_ACTION(0, 62), WILL\_MOVE(0, 4, 2)\]

There are no special UNDO actions because there should never be a difference in game state vs if the move/undo never happened. The MOVE action and subsequent events are simply rolled back. 

Now the player moves to square 70 instead (from 61, this is a valid choice because boards have branching paths). The player finishes their turn in a similar manner until they run out of moves. The queue will look like

\[WILL\_MOVE(0, 4, 0)\]

When the server pops this event, the only valid responses are undo move and stop. Let’s say the player confirms that they want to stop on this square (72), which is a commitment:  
{  
player\_stop: {  
  on: 72  
}  
}

Now, the server adds the stop action to the queue. At the same time, the end of player 0’s turn and the start of the next player’s turn is added to prepare. 

\[STOP\_ACTION(0, 72), END\_TURN(0), TURN(1)\]

The STOP\_ACTION resolves by adding the square’s stop events to the queue. Let’s say this is a take a break square. It has a more complex event script, which will be written in python

\`\`\`  
shops \= \[square.id for square in state.board\_state.squares if square.is\_property() and square.owner \== state.curr\_player\_id\]  
state.event\_queue.appendleft(ADD\_STATUS\_TO\_ALL\_SHOPS(shops, CLOSED, 1));   
\`\`\`  
(not exactly, details like event syntax needs to be refined)

This adds the ADD\_STATUS\_TO\_ALL\_SHOPS event to the queue. Note that the current\_player.all\_shops() did not add an event to the queue, as it is a read only function that doesn’t require any animation to play. While executing the script the server will just replace this with the result 

\[ADD\_STATUS\_TO\_ALL\_SHOPS(\[...\], CLOSED, 1), END\_TURN(0), TURN(1)\]

The ADD\_STATUS\_TO\_ALL\_SHOPS event is popped off. The first parameter is a list of shops. In this case, it is a list of all the shop ids owned by player 0\. The second param is the status to add. The third parameter says how many turns to apply the status for. In this case it’s just a single turn. The shops close, and then END\_TURN(0) is popped off. This is read by the server which then analyzes the board state to add a variety of events. First, it would check if player 0’s ready cash is negative. In this case, it isn’t so nothing happens there (if it was, remember they are forced to sell assets. A corresponding event would have been added). Then, it checks to see if any stock prices need to update. In this case, since at the start of their turn player 0 sold 10 stock in district C, it does. The event is added:

\[STOCK\_BUY\_SELL\_ADJUSTMENT(2, \-10), TURN(1)\]

The parameters are the district and the number of stock that was added/sold (negative for sold). The server will pop it off and calculate the necessary change (technically this would have also been calculated earlier and displayed WHILE the player was choosing how much stock to sell. but it doesn’t take effect until this point, and it might as well be recalculated here, i.e. the computation doesn’t need to be saved). The change is applied to the game state.

At this point, if the board has any scheduled events, they would be added to the queue as well. In this case, there are none, so now it’s finally player 1’s turn.

## Event Scripts

More complex events such as the CLOSE\_ALL\_SHOPS event will be implemented as python scripts. Specifically they are generator functions. Any events that the script wants to execute should be in the form of a yielded event. Reads can be done directly, or in the form of a yielded event with a set value if an animation needs to play. The value required will be added by the caller as the return value of the yield (python magic). A requirement for this to work is that all Events should implement a get\_result function that returns the result that should be added back to the script execution. It only needs to function AFTER the event executed. For Events not designed to return values, they can just return None which can be added as the default behavior.

An event script is added as SCRIPT(“event.py”), where “event.py” is of course replaced with the path to the script. It resolves by reading and executing the generator function. Anytime the generator yields an event, the yielded event is added to the event queue. Additionally, the ScriptEvent that was in the middle of execution also re-adds itself to the event queue, so when the yielded event finishes it can continue. 

As a proof of concept, here are some of the sample venture cards from Gameplay Spec and the scripts they could be implemented as (WIP, ideally will add helper functions and such to simplify some of this logic. Also, need to figure out event syntax).

* You can choose which way to go next turn\!

\`\`\`  
state.player\_state\[state.curr\_player\_id\].from \= None \# None allows player to move any direction on their turn  
\`\`\`

* Roll the dice again\!

\`\`\`  
yield ROLL(state.curr\_player\_id) \# might need to also remove the END\_TURN that was already in the queue, or make sure this roll doesn’t add another one at least  
\`\`\`

* All your shop prices increase by 30% for one turn\!

\`\`\`  
shops \=  \[square.id for square in state.board\_state.squares if square.is\_property() and square.owner \== state.curr\_player\_id\]  
yield ADD\_STATUS\_TO\_ALL\_SHOPS(shops, PRICE(30), 1));   
\`\`\`

* You can invest in one of your shops\!

\`\`\`  
yield INVEST\_IN\_SHOP(state.curr\_player\_id))  
\`\`\`

* Roll the die and get 11x the number rolled from each player\!

\`\`\`  
roll \= yield ROLL\_FOR\_EVENT(state.curr\_player\_id)) \# ROLL\_FOR\_EVENT generates a random number, plays the roll animation, and sets the input to the result. It is NOT a roll for movement.  
amount \= 11 \* roll  
stolen \= 0  
transaction\_dict \= {}  
for p in len(state.player\_state):  
  if (p \!= state.curr\_player\_id and state.player\_state\[p\].is\_player()) and state.player\_state\[p\].net\_worth() \> 0:  
    transaction\_dict\[p\] \= \-amount  
    stolen \+= amount  
transaction\_dict\[state.curr\_player\_id\] \= stolen  
yield TRANSACTION(transaction\_dict) \# TRANSACTION takes an arbitrary transaction dict and applies it to each player simultaneously. Extremely useful for all sorts of events.  
\`\`\`

* You’re forced to sell a shop to the bank for only 200g more than its value

\`\`\`  
shops \= \[square.id for square in state.board\_state.squares if square.is\_property() and square.owner \== state.curr\_player\_id\]  
shop \= yield PLAYER\_CHOOSE\_SHOP(state.curr\_player\_id, shops)  
yield SELL\_SHOP\_WITH\_MOD(shop, lambda x: x \+ 200\) \# Sells the shop but the owner receives the functional parameter evaluated on the shop value, instead of the actual shop value.  
\`\`\`

* Optionally pay 100g to warp to the bank

\`\`\`  
if state.player\_state\[state.curr\_player\_id\].ready\_cash \< 100:  
  yield MESSAGE(“Sorry, you don’t have enough ready cash to cover the cost\!”) \# Simply displays a message to the player  
  return  
choices \= {}  
choices\[“Warp\! (100G)”\] \= True  
choices\[“Stay here” \= False  
choice \= yield MESSAGE\_WITH\_DECISION(“Warp to bank?”, choices) \# Displays messages, and options from choices. Returns with the value of the selected choice  
if choice:  
  yield TRANSACTION({state.current\_player\_id, \-100})  
  yield WARP(state.current\_player\_id, 0\) \# Bank always has id 0 \- probably should use a variable though instead of a magic number  
\`\`\`

The script will be wrapped in a ScriptRunner object that runs the yielded events and continues execution until the script reaches a StopIteration exception (returns).

# Execution Flow

This section describes how each component starts up, plays the game, and shuts down. Note that for P0,1,2 only local play needs to be supported (i.e. the server and clients are just different processes running on the same machine. Network play is P3. However, the architecture should still be built with eventual network play in mind to make that transition as seamless as possible. Therefore WebSocket must be the standard communication method between clients and servers, from the very beginning. 

## Start Up

A single server is capable of running multiple games. On startup, the server simply initializes itself with an empty dictionary of game instances, and waits for a client to send a start game request. Once a start game request is received, the server initializes a Game object with a random (unique) game id, adds it to the map, and returns the game id to the client. It adds the client that requested the game (from now on called the host) to the game and waits for the host to configure the game. Possible configurations are:

- How many players and how many NPCs  
- Public game (can be discovered by other clients without the id) or private (other clients must have the game id to join)  
- Gameplay options

Once the game is configured, a few things happen:

- If the game is with 1 player and the rest NPCs, the game immediately begins.  
- If it has multiple players  
  - And is a public game, it's marked as such and if a later client sends a “discover games” request, it will be returned in that response along with the rules summary.  
  - If it is a private game, will not be returned in discovery requests  
  - In either case, wait until the player slots fill up after “join game” requests. If it is taking too long, the host should be able to force start the game which will fill all empty player slots with NPC slots.  
- Once the game is starting, the NPCs will be chosen randomly or by the host’s choice.  
- Finally, the Game object takes over and begins with a BEGIN\_GAME() event that handles things like assigning turn order then adding all players to the board with initial positions and ready cash. From here on out, all gameplay logic is handled by that game object and the main server acts as a router for requests 

Note that a single client can support multiple players. Therefore, “connection id” is different from “player id”. The client will handle the logic of attaching the right player id to each message based on who is taking their turn.

## Gameplay

- The events must be designed so that after the initial BEGIN\_GAME() event, the event queue is never empty until the game is over.   
- When an event is popped off the queue, the event is handled by the server AND sent to all clients simultaneously.  
  - Each client that receives the event must play an animation (if the client supports animations) or otherwise communicate what happened to the player(s) on that client.  
  - If the event involves a player input, the server will be waiting until the relevant client responds with the player’s action.   
    - Upon receiving a player response, the server must validate that they made a valid option (in terms of game logic) every single time.  
    - (P2) Network traffic should be signed or encrypted so the server can verify that the response came from the expected client.  
  - If the event involves no player input, the server just continues execution of events and streams the events as they happen. Each client should build an internal event queue since they won’t be able to keep up with the server (due to network delay and playing animations). Thankfully the client queue can be “dumb” and simply reads the events exactly as they come, no logic necessary.   
    - The player input events will let the clients catch up since obviously the player won’t be able to input their action until the client reaches that point (explicitly, the client should PREVENT the player from inputting anything until they are actually supposed to be able to).

## AI Players and NPCs

“AI Players” and “NPCs” have different meanings in the context of the game. AI Players are competitors in the game playing against the player. NPCs on the other hand are features of the game that can appear even if all the players are human. For example cameo characters which spawn for a few turns, take unique actions, then leave.

### AI Players

All AI players for a game will be handled on a unique AI client, that is running on the same machine as the server. (P1) This client is responsible for handling the AI logic and eventually making them smart enough to compete with real players at a high level. (P0) During development, the AIs can just make random (but valid) moves. But still should run on their own AI client process. 

Note that the different AIs are supposed to have different personalities and skill levels. These will apply when that AI character is selected in an online or singleplayer (or even hypothetical AI only) match.

### NPC Players

In contrast, NPC players are controlled directly by the server, through events. They still have their own player ids though and take turns.

## Error Handling

- If a client disconnects or loses a message, it will not be able to recover. In that case, the client can send a sync request to the server. The server will respond with the complete game state, and the client can jump to that point and continue from there. This also takes place during the start of the game.  
- If a client somehow sends an invalid response to the server, the server should give the client another try by sending a “please try again” response.   
  - If the client fails again, the server should respond with a state sync for that client  
- In case of an unrecoverable error from a client, that client should be replaced with an AI that acts on behalf of the player.  
- If the server runs into some type of state corruption that is caught, the whole game should be aborted.

## (P2) Single Player Mode

- Eventually a single player mode should be added, where the player plays against only other AIs. There should be unlockable boards, AIs, and achievements. Therefore each player should have a “progress” save file which tracks what they have unlocked. This design can be more thought out later. Just mentioning it now so we keep it in mind in case it influences any current decisions.  
  - One note: plan for save data to be stored client side so no persistent database is needed on the server side.

# Code Representations of Data

Most data in the game on the server side will be represented with python dataclasses. The benefit of this   
is that converting to/from json is super easy with the standard python library. Here is how the core game state class will look:

`@dataclass`  
`class GameState:`  
	`current_player: int, # the id of the current player`  
	`board_state: BoardState,`  
	`stock_state: StockState,`  
	`player_state: [PlayerState],`  
	`events: EventState`

`@dataclass`  
`class BoardState:`  
	`max_dice_roll: int, # 4-9`  
	`promotion_info: PromotionInfo,`  
	`target_networth: int, # the goal networth of the game`  
	`max_bankruptcies, int # the number of players that can bankrupt before the game automatically ends`  
	`venture_board: VentureBoard, # todo. only applicable in a normal (not spheres) game`  
	`squares: [SquareInfo]`

`@dataclass`  
`class SquareInfo:`  
	`position: (int, int) # x, y position of the square (for display purposes only, doesn’t affect functionality)`  
	`waypoints: [Waypoint]`  
	`type: SquareType, # the type of the square`  
`statuses: [SquareStatus], # empty list if this square has no current status effects`  
	`### BEGIN SQUARE SPECIFIC FIELDS ###`  
	`### Property fields ###`  
	`owner: int | None, # the id of the player that owns this, or None if it is unowned/unownable`	  
	`value: int | None, # if this is a property, it’s current value`  
	`district: int | None, # if this is a property, the id of the district it belongs to`  
	  
	  
	

