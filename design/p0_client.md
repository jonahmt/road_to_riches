  
---

# P0 Client \- Terminal UI

This section describes the P0 client, which will be a terminal UI.

# Tech Stack

The tui should be built in python. It should display colors and ascii blocks for segmenting UI sections. The terminal can be thought of as a grid canvas rather than just text. Each frame, the canvas gets displayed exactly as the client renders it. If the Textual library supports this method, it should be used.

# Features

We can assume that the terminal window will have a minimum dimension of 140x35. However, it may be more than that and should appropriately scale. The overall structure of the tui during a normal turn should be this:

## (P0) Command Line and Log (bottom)

This section is always present and takes the bottom portion of the screen, say the bottom 8-10 chars. It has a log of events that occur in the game. And when the player needs to make an input, it prompts them with an explanation of the choice and waits for them to type the correct input. The client should do some internal validation to make sure this is a valid choice before sending it to the server. For example, here is an event flow and how the log/command line would look. The exact spacing can change, but this is generally what I’d like it to look like. We can also use colors to make it more readable.

**`Scenario:`** `Player 0 starts their turn, checks their options, and decides to roll the dice. They roll a 3, and must choose an intersection.`

`Plaintext`  
`================================================================================`  
`| [LOG] Player 3 finishes their turn.                                          |`  
`| [LOG] ---------------------------------------------------------------------- |`  
`| [LOG] It is Player 0's turn!                                                 |`  
`| [LOG] You are on square 12 (Shop - owned by Player 1).                       |`  
`|                                                                              |`  
`| > Options: [R]oll, [S]ell Stock, [T]rade, [V]iew Board                       |`  
`| > Enter command:                                                             |`  
`================================================================================`

*`The user types S and hits Enter. The client intercepts this.`* `Client Validation: Is S a valid option right now? Yes. It sends an INIT_SELL_STOCK(0) request to the server. The server responds that the player actually has 0 stock in all districts.`

`Plaintext`  
`================================================================================`  
`| [LOG] It is Player 0's turn!                                                 |`  
`| [LOG] You are on square 12 (Shop - owned by Player 1).                       |`  
`| [LOG] You do not own any stock to sell.                                      |`  
`|                                                                              |`  
`| > Options: [R]oll, [S]ell Stock, [T]rade, [V]iew Board                       |`  
`| > Enter command: R                                                           |`  
`================================================================================`

`The user types R. The client sends the ROLL(0) request. The server resolves the roll and broadcasts the result. A dice icon (7x7 or 5x5) is temporarily added to the top left of the ui while the player rolls the dice and plays. During the “roll” it flashes a few random numbers before settling on the number the player rolled. Let’s say it's a 2.`  
`Plaintext`  
`================================================================================`  
`| [LOG] You do not own any stock to sell.                                      |`  
`| [LOG] Player 0 rolls a 2! 									 |`  
`| [LOG] Current square: 7                                                      |`                        
`|                                                                              |`  
`| > Select path: [A]Left (Square 15), [D]Right (Square 22), [V]iew Board       |`            
`| > Enter path:                                                                |`  
`================================================================================`

`The player chooses square 15 (A/left). It is another player’s checkpoint, so they have to pay. At the same time, the server sends the roll remaining event as 1. So the dice in the top left updates to display 1.`

`Plaintext`  
`================================================================================`                                     
`| [LOG] Player 0 rolls a 2! 									 |`  
`| [LOG] Player 0 moves to square 15!`  
`| [LOG] Player 0 passes Player 1’s checkpoint and pays 30G!`  
`| [LOG] Current square: 15`  
`| [LOG] 1 square remaining.                                                      |`                        
`|                                                                              |`  
`| > Select path: [A]Left (Square 16), [U]ndo (Square 7), [V]iew Board       |`            
`| > Enter path:                                                                |`  
`================================================================================`

`The player sends an invalid input (square 0). The client figures this out independently and lets the player input again.`

`================================================================================`                                     
`| [LOG] Player 0 rolls a 2! 									 |`  
`| [LOG] Player 0 moves to square 15!`  
`| [LOG] Player 0 passes Player 1’s checkpoint and pays 30G!`  
`| [LOG] Current square: 15`  
`| [LOG] 1 square remaining.`  
`[ERROR] Invalid input. Please select a valid path.`                                                               
`|                                                                              |`  
`| > Select path: [A]Left (Square 16), [U]ndo (Square 7), [V]iew Board       |`            
`| > Enter path:                                                                |`  
`================================================================================`

Throughout, the player should be able to scroll the log infinitely back to the start of the game, to see exactly what happened. Additionally, the viewing board should cause all UI elements to vanish except for the game view. In the screen the player can move squares with wasd to view the info of each square (in a separate UI box overlaid in the top right). Basically, moving the center of the board from (0,0) by 1 each key press. And whatever square is in the center will have its info displayed.

## (P0) Info

Any time a player is inputting a decision, they should also be able to type I/info/Info to get info about the game. They can request info player to see a player’s full stats, info square type to see the definition of that square (same as would appear in viewing board), etc. info game would return the victory condition for example. This is how the game can be remotely playable before the following UI components are implemented. This is also how agents should interact with the program while testing.

## (P0.5) Game View

The whole terminal will display the grid in close up. So each square is represented by an NxN square. We can assume that each character is twice as tall as it is wide. Therefore, we will actually have a 2NxN grid. Let’s use 8x4 to start with, and can change to something else later. 8x4 is a good choice because squares can have their positions set up tp ¼ of a square width. I.e. positions are integers and the width of a square edge is 4\.

These are always present in the game and everything else is drawn ON TOP of this. Here are some example squares assuming 5x10. Imagine a monospace font. The chars which are \~ represent the border and should actually use the ascii box drawing characters. Player ids are 0, 1, 2, 3\. The id of the square is in the bottom right and the id of the players currently at that square are in the bottom left. Each square has a main color and a highlight color. Some things are also guaranteed to be white. Specifically, the player ids and square ids should always be white.

### Example special (non shop) square \- bank with id 0

| \~ | \~ | \~ | \~ | \~ | \~ | \~ | \~ |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| \~ |  | B | A | N | K |  | \~ |
| \~ |  |  |  |  |  |  | \~ |
| 0 |  | 2 |  | \~ | \~ | 0 | 0 |

The main color is the Bank text. The highlight color is the outline.   
Main: Golden.    
Highlight: White

### Example shop square with id 35\. Value 1540, price 567, max capital 818

| \~ | \~ | \~ | \~ | \~ | \~ | \~ | \~ |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| \~ | V |  | 1 | 5 | 4 | 0 | \~ |
| \~ | $ |  |  | 5 | 6 | 7 | \~ |
|  |  |  |  | \~ | \~ | 3 | 5 |

Main color is the text inside the square. Highlight is the border.  
Main: Player’s designated color  
Highlight: District’s designated color

### Example change of suit square with id 20\.

| \~ | \~ | \~ | \~ | \~ | \~ | \~ | \~ |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| \~ | C | . | o | . | S | . | \~ |
| \~ |  | D | m | n | d |  | \~ |
|  | 1 |  |  | \~ | \~ | 3 | 5 |

Main is the CHANGE OF SUIT TEXT. Highlight is the border and (in this case) DIAMOND.  
Main: Rainbow ((p1) should be a color gradient from char to char)  
Highlight: Whatever color is associated with the suit. For diamond, this is yellow.

 Diamond is the only suit that needs to be abbreviated. The others will display their full name.

These examples just serve to highlight the idea. The others can be easily extrapolated.

## (P0.5) Player Info View (bottom right but above the log)

This section is also available at all times, but is drawn on top of the game view with its own border. It is just a stack of N player info boxes. The data available is: Player net worth, ready cash, current suits, status (displays one status with remaining turns. If more than one, say Multiple ?). The info should be side by side where possible to keep it as small as possible. For example,   
PX	Status		Suits  
Level 	Ready Cash	Net worth  
The border for each player’s box should be their color. 

## (P0.5) Stock market view

When a player inputs a command to buy, sell, or view stocks, an overlay table must appear, temporarily covering the Game View. As defined in the Gameplay Spec, this table must have Players across the top (columns) and Districts along the left (rows), with the current Stock Price next to the District name. The intersecting cells display the number of stocks that player owns in that district.

