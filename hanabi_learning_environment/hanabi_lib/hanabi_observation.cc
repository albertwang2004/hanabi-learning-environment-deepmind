// Copyright 2018 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//    https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include "hanabi_observation.h"

#include <algorithm>
#include <cassert>

#include "util.h"

namespace hanabi_learning_env {

namespace {
// Returns the offset of player ID pid relative to player ID observer_pid,
// or pid for negative values. That is, offset such that for a non-negative
// player id pid, we have (observer_pid + offset) % num_players == pid.
int PlayerToOffset(int pid, int observer_pid, int num_players) {
  return pid >= 0 ? (pid - observer_pid + num_players) % num_players : pid;
}

// Switch members from absolute player indices to observer-relative offsets,
// including player indices within the contained HanabiMove.
void ChangeHistoryItemToObserverRelative(int observer_pid, int num_players,
                                         bool show_cards,
                                         HanabiHistoryItem* item) {
  auto move_type = item->move.MoveType();
  if (move_type == HanabiMove::kDeal ||
      move_type == HanabiMove::kDealSpecific) {
    assert(item->player < 0 && item->deal_to_player >= 0);
    item->deal_to_player =
        (item->deal_to_player - observer_pid + num_players) % num_players;
    if (item->deal_to_player == 0 && !show_cards) {
      // Hide cards dealt to observer if they shouldn't be able to see them.
      item->move = HanabiMove(HanabiMove::kDeal, -1, -1, -1, -1);
    }
  } else {
    assert(item->player >= 0);
    item->player = (item->player - observer_pid + num_players) % num_players;
  }
}
}  // namespace

HanabiObservation::HanabiObservation(const HanabiState& state,
                                     int observing_player)
    : cur_player_offset_(PlayerToOffset(state.CurPlayer(), observing_player,
                                        state.ParentGame()->NumPlayers())),
      discard_pile_(state.DiscardPile()),
      fireworks_(state.Fireworks()),
      deck_size_(state.Deck().Size()),
      information_tokens_(state.InformationTokens()),
      life_tokens_(state.LifeTokens()),
      legal_moves_(state.LegalMoves(observing_player)),
      parent_game_(state.ParentGame()) {
  REQUIRE(observing_player >= 0 &&
          observing_player < state.ParentGame()->NumPlayers());
  hands_.reserve(state.Hands().size());
  const bool hide_knowledge =
      state.ParentGame()->ObservationType() == HanabiGame::kMinimal;
  const bool show_cards =
      state.ParentGame()->ObservationType() == HanabiGame::kSeer;

  hands_.push_back(
      HanabiHand(state.Hands()[observing_player], !show_cards, hide_knowledge));
  for (int offset = 1; offset < state.ParentGame()->NumPlayers(); ++offset) {
    hands_.push_back(HanabiHand(state.Hands()[(observing_player + offset) %
                                              state.ParentGame()->NumPlayers()],
                                false, hide_knowledge));
  }

  // ===== Per-observer exact-card count masking (NO LEAKAGE) =====
  //
  // Apply ONLY to the observing player's own hand knowledge (hands_[0]) and
  // ONLY for non-minimal, non-seer observations.
  //
  // Rule: if a specific (color,rank) has zero remaining copies in (deck + my
  // hidden hand), then none of my cards can be that exact (color,rank).
  if (!hide_knowledge && !show_cards &&
      state.ParentGame()->ObservationType() == HanabiGame::kCardKnowledge) {
    const int num_colors = state.ParentGame()->NumColors();
    const int num_ranks = state.ParentGame()->NumRanks();

    auto idx = [num_ranks](int c, int r) { return c * num_ranks + r; };

    std::vector<int> seen(num_colors * num_ranks, 0);

    // Seen in other players' hands (hands_[1..]).
    for (int p = 1; p < state.ParentGame()->NumPlayers(); ++p) {
      for (const HanabiCard& card : hands_[p].Cards()) {
        assert(card.IsValid());
        seen[idx(card.Color(), card.Rank())] += 1;
      }
    }

    // Seen in discard pile.
    for (const HanabiCard& card : discard_pile_) {
      assert(card.IsValid());
      seen[idx(card.Color(), card.Rank())] += 1;
    }

    // Seen on fireworks: for each color c, ranks [0..fireworks[c)-1] are played.
    for (int c = 0; c < num_colors; ++c) {
      int k = fireworks_[c];
      for (int r = 0; r < k; ++r) {
        seen[idx(c, r)] += 1;
      }
    }

    // Compute hiddenCount(color,rank) = totalInstances - seenElsewhere.
    std::vector<int> hidden(num_colors * num_ranks, 0);
    for (int c = 0; c < num_colors; ++c) {
      for (int r = 0; r < num_ranks; ++r) {
        int total = state.ParentGame()->NumberCardInstances(c, r);
        int h = total - seen[idx(c, r)];
        // If this fails, something is inconsistent (e.g., illegal deck edits).
        assert(h >= 0);
        hidden[idx(c, r)] = h;
      }
    }

    // Apply exact bans to every card slot in the observing player's hand.
    auto& my_knowledge = hands_[0].MutableKnowledge();
    for (auto& ck : my_knowledge) {
      for (int c = 0; c < num_colors; ++c) {
        for (int r = 0; r < num_ranks; ++r) {
          if (hidden[idx(c, r)] == 0) {
            ck.ApplyIsNotCard(c, r);
          }
        }
      }
    }
  }
  // ===== End per-observer exact-card count masking =====

  const auto& history = state.MoveHistory();
  auto start = std::find_if(history.begin(), history.end(),
                            [](const HanabiHistoryItem& item) {
                              return item.player != kChancePlayerId;
                            });
  std::reverse_iterator<decltype(start)> rend(start);
  for (auto it = history.rbegin(); it != rend; ++it) {
    last_moves_.push_back(*it);
    ChangeHistoryItemToObserverRelative(observing_player,
                                        state.ParentGame()->NumPlayers(),
                                        show_cards,
                                        &last_moves_.back());
    if (it->player == observing_player) {
      break;
    }
  }
}

std::string HanabiObservation::ToString() const {
  std::string result;
  result += "Life tokens: " + std::to_string(LifeTokens()) + "\n";
  result += "Info tokens: " + std::to_string(InformationTokens()) + "\n";
  result += "Fireworks: ";
  for (int i = 0; i < ParentGame()->NumColors(); ++i) {
    result += ColorIndexToChar(i);
    result += std::to_string(fireworks_[i]) + " ";
  }
  result += "\nHands:\n";
  for (int i = 0; i < hands_.size(); ++i) {
    if (i > 0) {
      result += "-----\n";
    }
    if (i == CurPlayerOffset()) {
      result += "Cur player\n";
    }
    result += hands_[i].ToString();
  }
  result += "Deck size: " + std::to_string(DeckSize()) + "\n";
  result += "Discards:";
  for (int i = 0; i < discard_pile_.size(); ++i) {
    result += " " + discard_pile_[i].ToString();
  }
  return result;
}

bool HanabiObservation::CardPlayableOnFireworks(int color, int rank) const {
  if (color < 0 || color >= ParentGame()->NumColors()) {
    return false;
  }
  return rank == fireworks_[color];
}

}  // namespace hanabi_learning_env
