import random

from hanabi_learning_environment import pyhanabi


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
  remaining.sort()
  return remaining


def build_midgame_state(seed, switch_threshold=4):
  config = {
      "players": 3,
      "colors": 2,
      "ranks": 3,
      "hand_size": 3,
      "random_start_player": True,
  }
  game = pyhanabi.HanabiGame(config)
  state = game.new_initial_state()
  rng = random.Random(seed)
  deterministic = False
  remaining = []

  for _ in range(80):
    if state.is_terminal():
      break
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
      move = pick_weighted_random_move(moves, rng)
      state.apply_move(move)

    # Stop once we have switched to deterministic dealing and it's a player's turn.
    if deterministic and state.cur_player() != pyhanabi.CHANCE_PLAYER_ID:
      break

  # Ensure we exit on an acting player (not CHANCE) if possible.
  while state.cur_player() == pyhanabi.CHANCE_PLAYER_ID and not state.is_terminal():
    if deterministic:
      if not remaining:
        remaining = remaining_deck_cards(state, game)
      color, rank = remaining.pop(0)
      target_player = next(
          pid for pid, hand in enumerate(state.player_hands())
          if len(hand) < game.hand_size()
      )
      state.deal_specific_card(target_player, color, rank)
    else:
      state.deal_random_card()

  return game, state


def test_observations_after_switch_to_specific_dealing():
  for seed in range(5):
    game, state = build_midgame_state(seed, switch_threshold=4)
    assert not state.is_terminal()
    assert state.cur_player() != pyhanabi.CHANCE_PLAYER_ID

    actual_sizes = [len(hand) for hand in state.player_hands()]

    for pid in range(game.num_players()):
      obs = state.observation(pid)
      assert obs.num_players() == game.num_players()
      assert obs.deck_size() == state.deck_size()

      observed_hands = obs.observed_hands()
      assert len(observed_hands) == game.num_players()

      own_hand = observed_hands[0]
      assert all(not card.valid() for card in own_hand)

      other_hands = observed_hands[1:]
      assert all(card.valid() for hand in other_hands for card in hand)

      observed_sizes = [len(hand) for hand in observed_hands]
      assert sorted(observed_sizes) == sorted(actual_sizes)

      if obs.cur_player_offset() == 0:
        assert obs.legal_moves()
      else:
        assert obs.legal_moves() == []


def test_obs_fireworks_matches_state_with_specific_deals():
  game = pyhanabi.HanabiGame({
      "players": 2,
      "colors": 2,
      "ranks": 3,
      "hand_size": 2,
      "random_start_player": False,
  })
  state = game.new_initial_state()

  # Manually construct the hands using deal_specific_card.
  initial_hands = [
      [(0, 0), (0, 1)],  # Player 0
      [(1, 0), (1, 1)],  # Player 1
  ]
  for pid, cards in enumerate(initial_hands):
    for idx, (color, rank) in enumerate(cards):
      assert state.cur_player() == pyhanabi.CHANCE_PLAYER_ID
      state.deal_specific_card(pid, color, rank, card_index=idx)

  # Player 0 plays a 1, advancing the fireworks for color 0.
  assert state.cur_player() == 0
  state.apply_move(pyhanabi.HanabiMove.get_play_move(0))
  assert state.fireworks() == [1, 0]
  assert state.cur_player() == pyhanabi.CHANCE_PLAYER_ID

  # Replace the card with a specific draw.
  state.deal_specific_card(player_id=0, color=0, rank=2)
  assert state.cur_player() == 1

  # Player 1 plays a 1, advancing the fireworks for color 1.
  state.apply_move(pyhanabi.HanabiMove.get_play_move(0))
  assert state.fireworks() == [1, 1]
  assert state.cur_player() == pyhanabi.CHANCE_PLAYER_ID

  # Replace player 1's card with a specific draw.
  state.deal_specific_card(player_id=1, color=1, rank=2)
  assert state.cur_player() == 0

  for pid in range(game.num_players()):
    obs = state.observation(pid)
    # Fireworks should be identical in the observation and the true state.
    assert obs.fireworks() == state.fireworks() == [1, 1]
    # Observations should not crash and should have correct hand sizes.
    observed_hands = obs.observed_hands()
    assert len(observed_hands) == game.num_players()
    assert [len(hand) for hand in observed_hands] == [2, 2]
