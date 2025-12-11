import pytest

from hanabi_learning_environment import pyhanabi


def total_cards(game):
  return sum(
      game.num_cards(color, rank)
      for color in range(game.num_colors())
      for rank in range(game.num_ranks())
  )


def test_deal_specific_card_appends_and_reduces_deck():
  game = pyhanabi.HanabiGame({
      "players": 2,
      "colors": 2,
      "ranks": 3,
      "hand_size": 3,
      "seed": 1,
  })
  state = game.new_initial_state()
  initial_deck = total_cards(game)

  state.deal_specific_card(player_id=0, color=0, rank=0)
  state.deal_specific_card(player_id=0, color=1, rank=1)

  hand = state.player_hands()[0]
  assert [(card.color(), card.rank()) for card in hand] == [(0, 0), (1, 1)]
  assert state.deck_size() == initial_deck - 2
  assert state.cur_player() == pyhanabi.CHANCE_PLAYER_ID


def test_deal_specific_card_inserts_at_given_index():
  game = pyhanabi.HanabiGame({
      "players": 2,
      "colors": 3,
      "ranks": 3,
      "hand_size": 3,
      "seed": 2,
  })
  state = game.new_initial_state()

  state.deal_specific_card(player_id=0, color=0, rank=0)
  state.deal_specific_card(player_id=0, color=0, rank=1)
  state.deal_specific_card(player_id=0, color=2, rank=0, card_index=1)

  hand = state.player_hands()[0]
  assert [(card.color(), card.rank()) for card in hand] == [
      (0, 0),  # original first card
      (2, 0),  # inserted in the middle
      (0, 1),  # original second card shifted right
  ]


def test_deal_specific_card_advances_once_hands_are_full():
  game = pyhanabi.HanabiGame({
      "players": 2,
      "colors": 2,
      "ranks": 3,
      "hand_size": 2,
      "seed": 3,
  })
  state = game.new_initial_state()
  initial_deck = total_cards(game)

  deals = [
      (0, 0, 0, None),
      (1, 1, 0, None),
      (0, 0, 1, None),
      (1, 1, 1, None),
  ]
  for player_id, color, rank, idx in deals:
    state.deal_specific_card(player_id=player_id, color=color, rank=rank, card_index=idx)

  assert state.cur_player() == 0  # First non-chance player acts next.
  assert state.deck_size() == initial_deck - len(deals)
  assert [len(hand) for hand in state.player_hands()] == [2, 2]

  with pytest.raises(AssertionError):
    state.deal_specific_card(player_id=0, color=0, rank=0)
