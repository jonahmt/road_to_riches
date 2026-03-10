# 

# ---

# Road to Riches Design

# Intro

This is a project to create a game that is essentially a sequel in the Fortune Street/Itadaki Street series. The old games are personal favorites and I want to be able to customize them from the ground up, which essentially requires recreating it. Therefore, the goal is to create a Fortune Street game that is a web app. The name of the new game is “Road to Riches”.

No game engine will be used \- the whole thing will be written from scratch. Other libraries such as graphics, UI, audio, etc can and most likely will be used on the front end.

The game will likely not be released publicly so does not need to be 100% polished. However, the closer it can be to a finished product the better. Things like security and net code are not at all priorities (**yet**).

## Reading this doc

This doc is essentially the design doc for the project. This doc contains the external facing view. It describes how the game should be played and what features must be supported. “Technical Design” is another doc that gives advice on the technical implementation of some core features, such as what data structures and event systems to use. It does not need to be followed to a tee, but deviations must be justifiable and documented. Finally, “Tech Stack” outlines what technologies should be used in the development, for example what coding languages and frameworks to use. It should be followed precisely.

Items are marked with a priority: (P0), (P1), etc. P0 means a feature is critical for the minimum viable/playable product. P1 means a feature is necessary for the main game to be done but should be done after all P0 are completed. P2 are things that should be completed but are additional items to be reevaluated later before implementation. P3 and above are optional and will be selected later.

# Gameplay Basics

This section outlines the core gameplay in case you are not aware. This is **the** most critical section of the project.

**Fortune Street** is a turn-based economic strategy board game for N (usually 4\) players. It combines the accessibility of traditional "roll-and-move" mechanics (e.g. Monopoly) with more complex features that add in depth strategic elements.

1) (P0) Turn  
   1) Each player plays turns consecutively on a shared board.  
   2) All players begin at a starting square (the bank).  
   3) A players turn consistent of:  
      1) Possible pre-roll actions chosen by the player.  
      2) Rolling the dice.  
      3) Moving the same number of spaces as the dice rolled.  
         1) Some squares change the game state as they are passed \- though this is an exception, not the standard.  
      4) Landing on a square and taking some action based on the square.  
      5) Possible further automated game state adjustments based on the turn.  
2) Assets  
   1) (P0) In the base game there are three main types of assets  
      1) Ready Cash (gold / G): the most liquid type of asset  
         1) Players begin with a fixed amount of ready cash and that’s it  
         2) Used to buy property and stock, pay other players, etc  
         3) If ready cash is negative at the ***end*** of a player’s turn (**not immediately when their cash goes negative. Specifically at the end of their turn)**, they are forced to sell other assets until they have a positive ready cash.  
            1) Any properties they sell are only sold for 75% of the shop value. Then the property is auctioned off to the other players, with a starting bid of 100% the shop value. If no player bids, the shop returns to an unowned state.  
         4) Contributes to net worth at a 1:1 ratio.  
         5) Typical starting amount will be in the range of 1500-3000.  
      2) Property (more details later)  
         1) Players buy unowned property as they move around the board. They pay the “value” of the shop to the bank and receive the property.  
         2) If a player lands on a property owned by another player, they must pay the “price” of the property (different from the value) in G to the player that owns the property.  
         3) If a player lands on their own property, they may invest in any of their owned properties. Up to the “max capital” which is determined based on the property value and other factors described later. Investing x G increases the value of the shop by exactly x and decreases the max capital by exactly x. The shop price changes based on a separate formula, related to the value.  
         4) Property value contributes to net worth 1:1.  
      3) Stock (more details later)  
         1) Players occasionally may buy stock in "districts" (groups of shops)  
         2) Each district’s stock has a value which changes as the shops develop and stock is bought/sold.  
         3) The value stock adds to a player’s net worth is the sum over each district X of the number of district X stock they own times the price of district X stock.  
   2) (P3) Other game modes *may* introduce additional types of assets but the listed three are fundamental.  
3) (P0) Promotions  
   1) As players move around the board, they collect four suits \- spade, heart, diamond, club. To collect a suit the player must simply pass over the square that provides said suit  
   2) Once a player has all four suits, they should return to the bank to receive a promotion.  
   3) A promotion increases the player’s level and provides them with a large bonus, calculated based on what level they are becoming and the assets they currently own.  
   4) Players start the game at level 1\. Level does not matter for most things but many venture cards and minigame prizes will scale based on it.  
   5) The promotion bonus has 4 components. Each should be overridable based on the specific board settings, but defaults will be provided here:  
      1) Base salary \- default \= 250G  
      2) Level bonus \- scales based on the next level. If next level is L, bonus is X(L-1). default \= 150  
      3) Shop bonus \- X% of current shop value. default \= 10%  
      4) Comeback bonus \- If you are promoting to level 4+, X% of the diff in your net worth **after the above bonuses have been granted to you** and the net worth of the player in first place (highest net worth). default \= 10%  
         1) If you are in first, you don’t get this bonus.  
   6) Promotion bonus is paid by the bank.  
4) (P0) Victory Condition  
   1) Each board has a specific target net worth. Once a player reaches the target net worth, **they must return to the bank square to claim 1st place**. The player with the next highest net worth (may even be higher than the 1st place player’s net worth) is 2nd and so on.  
   2) The game then ends and should proceed to a victory ceremony/game recap.  
5) (P0) Bankruptcy  
   1) If a player’s net worth is ever negative, they immediately go bankrupt and out of the game.   
   2) The player whose shop was landed on (if applicable) **does** still get the full amount of the rent.  
   3) Depending on the settings of the board, the game may end immediately or the other players may continue playing.  
   4) If the game continues, all of their stock is sold, and all of their properties are auctioned off.   
   5) The player should be removed from the board and no longer takes turns or is involved in anything.  
6) (P0) Boards  
   1) The game has many boards. Boards have different layouts and interesting features to keep each round fresh.   
   2) They are not simple loops but have branching paths and can dynamically change their layouts. Promotions incentivise players to traverse all squares to collect suits. But they are not strictly required.   
   3) Board squares have unique IDs starting from 0 and increasing to N-1 where N is the number of squares on the board.   
   4) Movement  
      1) Players move around the board. The path system is simple:  
         1) Each square has “waypoints” that describe which squares the player can go to *based on the square they are coming from.*   
   5) The boards are not randomly generated and instead are predesigned in a special file format.  
   6) (P1) There should be a separate board editor app that allows for the creation of these board files.

# Property System Details

1) (P0) Districts  
   1) Properties are divided into districts. Usually each district has 3-6 (4 is by far the most common) shops.  
   2) Districts can have names but are mainly referenced by ID which starts from 0 and increases.  
   3) Shops have some fundamental stats. The ones that are visible to the player in game are value, rent, and max capital.  
   4) Independent:  
      1) Base Value: The initial purchase cost of the shop  
      2) Base Rent: The initial rent of the shop  
         1) The board may technically have any value here, but typically will fall into a range. Specifically, if X \= (Base value \* 0.22) \- 11, then rent should almost always be in the range \[X \- 3, X \+ 3\]. This doesn’t affect implementation of the game engine but may affect the board creation tool when that gets developed.  
      3) Current Value: The current value of this shop  
      4) Num shops in district, and num shops owned in district  
         1) These are not stats “of the shop” but rather of the district. Num shops owned refers to the number of shops owned by the owner of the specific shop being referenced.  
   5) Dependent:  
      1) Current rent: the rent that gets paid when a player lands on the shop  
      2) Max capital: the maximum amount of money that can still be invested in this shop  
   6) In whatever UI is used, each district should have a unique color based on its ID.  
2) (P0) Specific Formulas  
   1) These formulas determine the current rent and max capital. They are implemented with look up tables. There is a rent lookup table and a max cap lookup table, based fully on the number of shops owned and number of shops in the district. So LUT(...) in the formula means lookup the corresponding table with those two variables to get a multiplier.  
   2) Current Rent \= LUT \* Base Rent \* (2 \* Current value \- Base value) / Base value  
   3) Current max cap \= LUT \* Base value \- Current value  
   4) If max cap somehow becomes negative, like due to a player selling a shop, it should just be displayed as 0 in game and treated as such by the server. Therefore the player can no longer invest in that shop.  
   5) If an event causes a shop to grow or shrink by x%, that applies to the base val, current val, and base price.  
      1) Anytime a final value would be a float, it should be rounded DOWN to the nearest integer.  
3) (P1) Shop Exchanges   
   1) On their turn, a player (A) may initiate an attempted exchange of shops with another player (B). The options are as follows:  
      1) **Buy**: A selects one of B’s shops. They then specify how much G they want to buy the shop for. B can accept the offer, counteroffer a different price, or reject the offer. If successful, the property transfers to A and B receives from A the agreed on price.  
      2) **Sell**: A selects one of their shops and a player B. Then it is like a reverse buy.  
      3) **Auction**: A selects one of their shops. Then an auction immediately begins. The other players bid on how much they would like to pay for the shop. The highest bidder wins, and they pay the bid to player A in exchange for the shop. If no players bid, A receives the base value of the shop and the shop becomes unowned.  
      4) **Trade**: A selects 1 or 2 of their shops and 1 or 2 of B’s shops. They may add or request additional G. Then B can accept, counteroffer, or reject the exchange as with buy and sell.   
4) (P1) Forced Buyouts  
   1) When landing on another player’s shop, after paying the shop price, the player that landed on the shop may have the option to **forcibly** buy out the shop for 5x the property value.  
      1) The owner of the shop only receives 3x the value.  
      2) The other 2x goes to the bank (removed from the economy) as a transaction fee.  
   2) There is **no way** to explicitly “protect” your shops from forced buyouts.  
5) (P1) Vacant Plots  
   1) In addition to the basic property type described above (and from here on out referred to as “shops”), there are additional rarer property types. These can be built when a player lands on and purchases a “vacant plot” square.   
   2) Upon purchase they are immediately required to choose which special property type to develop on the vacant plot.  
   3) In the future, they can renovate it into one of the other types for a smaller fee (they receive 75% of the value of current shop back, then pay 100% of new shop price). So for example 200 \-\> 200 costs 50G.  
   4) Vacant plot types:  
      1) (P1) Checkpoint  
         1) The special effect is that it must be paid when *passed* and not only landed on. Initial toll value is 10\.   
         2) Owner pass: raise the toll of the checkpoint by 10  
         3) Owner land: raise the toll by 10 and owner may invest in any of their shops  
         4) Other player pass: pay the current toll and raise the toll by 10\.  
         5) Other player land: pay the current toll and raise the toll by 10\.  
      2) (P1) Tax Office  
         1) The special effect is that the rent price is not fixed. Instead, it is based on the person who lands on its net worth.  
         2) Owner land: receive 4% of their current net worth.  
         3) Other player land: Pay 4% of their current net worth to the owner.   
      3) (P2) TODO additional types

# Stock Market Details

1) (P0) Buying stock  
   1) A player may only buy stock at a few select opportunities:  
      1) When passing the bank  
      2) When landing on a special square (stockbroker)  
      3) When a venture card, sphere, or other misc event allows them to  
   2) A player may only buy stock in a single district (of their choice) per stock buying opportunity  
   3) A player may only buy up to the amount of stock that their **current** ready cash covers. A player may **not**, for example, buy 99 stock in district A, go negative in ready cash, and then sell their stock in a different district to go even. They would have had to have sold the stock in the other district first, or bought less stock in district A.  
2) (P0) Selling stock  
   1) A player may sell stock freely. To be specific:  
      1) At any time on their turn **before** rolling the dice  
      2) If after spending ready cash for any purpose, their ready cash is negative, they may be prompted to sell stock to go even  
      3) A venture card, sphere, or misc event allows them the change to sell stock  
   2) In scenario i/a above, the player may sell as much stock as they desire in as many districts as they choose. In scenario ii/b, they may only keep selling discrete amounts until their ready cash is even (\>= 0). In scenario iii/c, the amount of stock they can sell depends on the specific event.  
3) (P0) Stock prices  
   1) Stock prices may only be whole numbers. Typical starting prices are in the range of 5-15 and by the end of the game prices of 40 or more are common. Above 100 is rare but possible.  
   2) Stock prices have two components: property (value) and additional (fluctuation). The total stock price is the sum of these two. From the player’s perspective, they only ever see the total stock price. They should only be considered separate in the internal logic of the game.  
      1) The starting property stock price of a district is 4% of the total property value, rounded to nearest integer  
         1) Vacant plots are assumed to have a starting price of whatever the typical option price is (200-300, tbd)  
      2) The starting additional stock price of a district is 0\.  
      3) When buying 10 or more stock (binary \- it’s either less than 10, or \>=10. The price does not scale with number of stock) in a district in a single turn, that district’s additional stock price rises by (current total stock price // 16 \+ 1\)  
      4) When selling 10 or more stock (binary \- it’s either less than 10, or \>=10. The price does not scale with number of stock) in a district in a single turn, that district’s stock price lowers by (current total stock price // 16 \+ 1\)  
      5) If a venture card/misc. event directly affects the stock price, the delta is calculated from the total stock price but then added only to the additional stock price.  
      6) When a player invests in a shop in a district, the property stock price updates to reflect the new value and stays 4% rounded to nearest int.  
   3) Update times  
      1) If a property is invested in or grows, the property stock part updates immediately and so does the total stock price  
      2) If the additional stock part changes, that does not take place until the end of the current player’s turn.  
         1) An exception to this rule is that an event which directly affects the stock price will take place immediately and immediately update the total stock price.  
      3) (P1) When the stock price of a district changes, the camera should pan to that district (average of all property positions) and display a UI showing the change and the profit/loss it causes each player.  
4) (P1) Viewing stock info  
   1) A player should be able to view the stock holdings of all players at essentially any time during their turn (that they are allowed to make inputs)  
   2) In whatever UI is in place, the stock info should display as a table with the players across the top and each district / price along the left. Then each entry is the **number** of stocks the player owns in that district.   
      1) This same UI should be used any time stock is viewed, bought, or sold.  
5) (P1) Dividends  
   1) Whenever a transaction (rent paid) is made in a district, and 1 or more players has stock there, dividends are handed out. Dividends are worth 20% of the paid rent value and that 20% is split based on the weight of the players that own stock there.  
   2) Dividends are paid by the bank (so the money is added into the game)

# Square Types

This section summarizes each basic square type. There may be other more complex squares implemented on a per board basis. These are the ones that should be available in most or all boards. **Note that function pass also applies in all cases where the player lands on the square.** Both function pass and function land apply (pass then land). All of these are P1 unless otherwise noted

| Square Name | Blank if neutral | Function Land | Function Pass |
| :---- | :---- | :---- | :---- |
| Bank (P0) |  | Starting square of all players. You can choose which way to go if you land on the bank | \- Player may buy stock \- If player has all four suits, promote and then buy stock. Promotion happens **before** stock purchasing \- If player has reached target net worth, they win the game |
| Shop (P0) | Player Owned | If unowned and player can afford it: Player may buy shop Owner: may invest in any of their own shops Other player: Pays the rent, and then may buy it for 5x value if they can afford it |  |
| Vacant Plot | Player Owned | Varies | Varies |
| Suit (P0) |  | Player chooses a venture card | Player collects the suit if they do not yet have it |
| Change of Suit  |  | Player chooses a venture card | Player collects the current suit, then the suit rotates to the next suit (spade \-\> heart \-\> diamond \-\> club \-\> …) |
| Suit Yourself  |  | Player chooses a venture card | Player is granted a suit yourself card |
| Venture (P0) |  | Player chooses a venture card |  |
| Take a break (P0) |  | All the player’s shops close for a turn (gain status closed \- 0 rent paid when an opponent lands on it) |  |
| Boon (P0) |  | Player gains a commission (for the next cycle of turns, they earn a 20% bonus from all rent paid, between any two players. It’s essentially free passive income.) |  |
| Boom |  | Player gains a large commission (50%) |  |
| Arcade (P2) |  | A mini game starts |  |
| Roll On (P0) |  | Player rolls the dice again and continues moving |  |
| Backstreet |  | The player is forced to warp to the destination square. They do not do the land or pass effect of the destination (usually another backstreet) |  |
| Doorway |  |  | Player teleports to the other doorway and continues the rest of their roll. Note that doorway spaces do NOT take away from the remaining moves. |
| Cannon |  | Player selects another player and jumps to their location |  |
| Switch |  | Changes the board layout |  |
| Stockbroker |  | The player may buy stock |  |
| Additional custom events |  |  |  |

# Sample Venture Effects

To showcase the large variety of possible venture effects, here are some from the original fortune street game. These might not all make it into this game, but the technical framework should make it easy to create new venture cards so all of these *could* be added with minimal effort.

* You can choose which way to go on your next turn  
* Roll the dice again  
* All shop prices increase by 30% (for 1 turn)  
* All your shops grow by 7%  
* You can invest in one of your shops  
* Roll the die and get 11x the number rolled from each other player  
* You’re forced to sell a shop to the bank for only 200g more than its value  
* Continue 1 more space  
* Receive a sudden promotion (lose all your suits)  
* Roll 1/3/5 and everyone else warps to a random location. Roll 2/4/6 and you warp to a random location  
* Stock venture\! The stock price raises 10% in a district of your choice  
* Forced to choose a district that you don’t own stock in. The stock price rises by 10%.  
* Optionally pay 100g to warp to the bank  
* Spawn a cameo character. They last for X turns, and move around the board like a player. When they land on a square, a certain event happens.  
* Spawn a cameo character. They last for X turns, and move around the board like a player. Whenever a player passes them, a certain event happens.

etc. etc. 

# Statuses

Players, shops, and districts can all gain temporary status effects. This is a core part of the game. Each status has a modifier/level X, and can last up to N turns. Some statuses are directly granted by board squares (like boon and take a break) where others are only found in venture cards or rarer events. Here are some examples that must eventually be supported. Others should be simple to add too.

## Player statuses:

* (P0) Commission X  
  * Receive X% of all rent transaction value  
* (P2) Poison X  
  * Every step you take, lose XG

## Shop statuses:

* (P0) Closed  
  * If a player lands on this shop, no rent is paid  
* (P0) Discount/Price Hike X  
  * Shop rent temporarily increases (+) or decreases (-) X%  
* (P1) Fixed price X  
  * Shop rent is temporarily fixed to a price of X gold (i.e. independent of the shop’s value)

## District statuses:

* (P3) Electrified X  
  * All shops in this district have prices increased by X%, until rent is paid to any shop in the district. Then that single transaction is increased by X%, and after this status effect is lost.

