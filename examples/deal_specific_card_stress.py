"""Stress test for deal_specific_card using randomized decks and play."""

import random

from hanabi_learning_environment import pyhanabi
from hanabi_utils import advance_state


def _build_deck(game):
  deck = []
  for color in range(game.num_colors()):
    for rank in range(game.num_ranks()):
      deck.extend([(color, rank)] * game.num_cards(color, rank))
  return deck


def _deal_next_card(state, deck, deck_index, player_id):
  color, rank = deck[deck_index]
  state.deal_specific_card(player_id=player_id, color=color, rank=rank)
  return deck_index + 1


def _play_out_game(state, deck, start_index, rng, hand_size, num_players):
  deck_index = start_index
  while not state.is_terminal():
    if state.cur_player() == pyhanabi.CHANCE_PLAYER_ID:
      if deck_index >= len(deck):
        break
      target = None
      for pid, hand in enumerate(state.player_hands()):
        if len(hand) < hand_size:
          target = pid
          break
      if target is None:
        break
      advance_state(state, [(target, *deck[deck_index])])
      deck_index += 1
      continue

    legal = state.legal_moves()
    if not legal:
      break
    advance_state(state, [rng.choice(legal)])
  return deck_index


def run(num_games=100000, seed=1234):
  rng = random.Random(seed)
  config = {"players": 2, "colors": 5, "ranks": 5, "hand_size": 5, "seed": seed}
  game = pyhanabi.HanabiGame(config)
  base_deck = _build_deck(game)

  for game_index in range(num_games):
    #print(game_index)
    deck = list(base_deck)
    rng.shuffle(deck)
    state = game.new_initial_state()

    deck_index = 0

    _play_out_game(
        state=state,
        deck=deck,
        start_index=deck_index,
        rng=rng,
        hand_size=game.hand_size(),
        num_players=game.num_players(),
    )

    if (game_index + 1) % 10000 == 0:
      print(f"Completed {game_index + 1} / {num_games} games", flush=True)

  print("Stress test finished successfully.", flush=True)


if __name__ == "__main__":
  run()
