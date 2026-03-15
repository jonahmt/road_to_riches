"""Placeholder venture card script: gives the player 100G."""


def run(state, player_id):
    """Execute the script effect.

    Args:
        state: GameState instance
        player_id: ID of the player who triggered this script

    Returns:
        str: A message describing what happened
    """
    player = state.get_player(player_id)
    player.ready_cash += 100
    return f"Player {player_id} draws a venture card and receives 100G!"
