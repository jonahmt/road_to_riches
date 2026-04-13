"""Venture Card 001: Choose your direction next turn."""


def run(state, player_id):
    player = state.get_player(player_id)
    player.from_square = None
