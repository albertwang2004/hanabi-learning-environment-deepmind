import random

import pytest

from hanabi_learning_environment import pyhanabi


def total_cards(game):
  return sum(
      game.num_cards(color, rank)
      for color in range(game.num_colors())
      for rank in range(game.num_ranks())
  )


def assert_card_inventory(state, game, expected_total):
  hand_cards = sum(len(hand) for hand in state.player_hands())
  discard_cards = len(state.discard_pile())
  fireworks_cards = sum(state.fireworks())
  assert hand_cards <= game.hand_size() * game.num_players()
  assert state.deck_size() >= 0
  assert discard_cards + fireworks_cards + hand_cards + state.deck_size() == expected_total


def pick_weighted_random_move(moves, rng):
  """Favor non-play moves to avoid premature deck exhaustion."""
  play_type = pyhanabi.HanabiMoveType.PLAY
  play_moves = [m for m in moves if m.type() == play_type]
  non_play_moves = [m for m in moves if m.type() != play_type]
  if non_play_moves and play_moves:
    pool = non_play_moves * 4 + play_moves  # plays are 4x less likely.
  else:
    pool = moves
  return rng.choice(pool)


def remaining_deck_cards(state, game):
  counts = {}
  for color in range(game.num_colors()):
    for rank in range(game.num_ranks()):
      counts[(color, rank)] = game.num_cards(color, rank)

  def consume(cards):
    for card in cards:
      counts[(card.color(), card.rank())] -= 1

  for hand in state.player_hands():
    consume(hand)
  consume(state.discard_pile())
  for color, top in enumerate(state.fireworks()):
    for rank in range(top):
      counts[(color, rank)] -= 1

  remaining = []
  for (color, rank), count in counts.items():
    assert count >= 0
    remaining.extend([(color, rank)] * count)
  assert len(remaining) == state.deck_size()
  # Deterministic ordering: color-major, then rank.
  remaining.sort()
  return remaining


def play_random_game(config, seed):
  game = pyhanabi.HanabiGame(config)
  state = game.new_initial_state()
  expected_total = total_cards(game)
  rng = random.Random(seed)

  steps = 0
  max_steps = expected_total * 5  # Plenty of slack for end-of-deck play out.
  while not state.is_terminal():
    if state.cur_player() == pyhanabi.CHANCE_PLAYER_ID:
      state.deal_random_card()
    else:
      moves = state.legal_moves()
      assert moves, "Non-terminal states must expose at least one legal move."
      state.apply_move(rng.choice(moves))
    assert_card_inventory(state, game, expected_total)
    steps += 1
    assert steps < max_steps

  assert_card_inventory(state, game, expected_total)
  return state


@pytest.mark.parametrize(
    "config,seeds",
    [
        (
            {"players": 2, "colors": 3, "ranks": 3, "hand_size": 3, "seed": 123},
            [0, 1, 2],
        ),
        (
            {"players": 3, "colors": 5, "ranks": 2, "hand_size": 4, "seed": 999},
            [4, 5],
        ),
    ],
)
def test_random_rollouts_end_in_terminal_state(config, seeds):
  for seed in seeds:
    final_state = play_random_game(config, seed)
    assert final_state.is_terminal()
    assert final_state.end_of_game_status() != pyhanabi.HanabiEndOfGameType.NOT_FINISHED


def run_many_games(num_games, random_start_player):
  base_config = {
      "players": 2,
      "colors": 2,
      "ranks": 2,
      "hand_size": 2,
      "random_start_player": random_start_player,
  }
  for i in range(num_games):
    config = dict(base_config)
    config["seed"] = 1_000 + i
    game = pyhanabi.HanabiGame(config)
    state = game.new_initial_state()
    expected_total = total_cards(game)
    rng = random.Random(42 + i)
    max_steps = expected_total * 8  # ample slack for post-deck turns.
    steps = 0
    while not state.is_terminal():
      if state.cur_player() == pyhanabi.CHANCE_PLAYER_ID:
        state.deal_random_card()
      else:
        moves = state.legal_moves()
        assert moves
        move = pick_weighted_random_move(moves, rng)
        state.apply_move(move)
      assert_card_inventory(state, game, expected_total)
      steps += 1
      assert steps < max_steps
    assert_card_inventory(state, game, expected_total)


def test_thousands_of_games_switch_random_to_deterministic_start_no_crash():
  # First half uses random starting player; second half fixes the start order.
  run_many_games(num_games=1000, random_start_player=True)
  run_many_games(num_games=1000, random_start_player=False)


def play_game_switching_to_deal_specific(config, seed, switch_threshold):
  game = pyhanabi.HanabiGame(config)
  state = game.new_initial_state()
  expected_total = total_cards(game)
  rng = random.Random(seed)
  deterministic = False
  remaining = []
  max_steps = expected_total * 8
  steps = 0

  while not state.is_terminal():
    if state.cur_player() == pyhanabi.CHANCE_PLAYER_ID:
      if not deterministic:
        state.deal_random_card()
        if state.deck_size() <= switch_threshold:
          deterministic = True
          remaining = remaining_deck_cards(state, game)
      else:
        if not remaining:
          remaining = remaining_deck_cards(state, game)
        color, rank = remaining.pop(0)
        target_player = next(
            pid for pid, hand in enumerate(state.player_hands())
            if len(hand) < game.hand_size()
        )
        state.deal_specific_card(target_player, color, rank)
    else:
      moves = state.legal_moves()
      assert moves
      move = pick_weighted_random_move(moves, rng)
      state.apply_move(move)

    assert_card_inventory(state, game, expected_total)
    steps += 1
    assert steps < max_steps

  assert_card_inventory(state, game, expected_total)


def test_switching_to_deterministic_deal_specific_midgame():
  # Use a small deck to force chance events and mid-game switching frequently.
  config = {
      "players": 3,
      "colors": 2,
      "ranks": 3,
      "hand_size": 3,
      "random_start_player": True,
  }
  # Switch once the deck is half exhausted.
  for seed in range(20):
    play_game_switching_to_deal_specific(config, seed=seed, switch_threshold=3)
