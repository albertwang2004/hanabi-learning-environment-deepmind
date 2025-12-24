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

#include "hanabi_hand.h"

#include <algorithm>
#include <cassert>

#include "util.h"

namespace hanabi_learning_env {

HanabiHand::ValueKnowledge::ValueKnowledge(int value_range)
    : value_(-1), value_plausible_(std::max(value_range, 0), true) {
  assert(value_range > 0);
}

void HanabiHand::ValueKnowledge::ApplyIsValueHint(int value) {
  assert(value >= 0 && value < value_plausible_.size());
  assert(value_ < 0 || value_ == value);
  assert(value_plausible_[value] == true);
  value_ = value;
  std::fill(value_plausible_.begin(), value_plausible_.end(), false);
  value_plausible_[value] = true;
}

void HanabiHand::ValueKnowledge::ApplyIsNotValueHint(int value) {
  assert(value >= 0 && value < value_plausible_.size());
  assert(value_ < 0 || value_ != value);
  value_plausible_[value] = false;
}

// ===== New joint (color,rank) plausibility CardKnowledge =====

HanabiHand::CardKnowledge::CardKnowledge(int num_colors, int num_ranks)
    : num_colors_(num_colors),
      num_ranks_(num_ranks),
      hinted_color_(-1),
      hinted_rank_(-1),
      plausible_(std::max(num_colors, 0) * std::max(num_ranks, 0), true) {
  assert(num_colors_ > 0);
  assert(num_ranks_ > 0);
  assert(static_cast<int>(plausible_.size()) == num_colors_ * num_ranks_);
}

bool HanabiHand::CardKnowledge::ColorPlausible(int color) const {
  assert(color >= 0 && color < num_colors_);
  for (int r = 0; r < num_ranks_; ++r) {
    if (plausible_[Index(color, r)]) return true;
  }
  return false;
}

bool HanabiHand::CardKnowledge::RankPlausible(int rank) const {
  assert(rank >= 0 && rank < num_ranks_);
  for (int c = 0; c < num_colors_; ++c) {
    if (plausible_[Index(c, rank)]) return true;
  }
  return false;
}

bool HanabiHand::CardKnowledge::CardPlausible(int color, int rank) const {
  assert(color >= 0 && color < num_colors_);
  assert(rank >= 0 && rank < num_ranks_);
  return plausible_[Index(color, rank)];
}

void HanabiHand::CardKnowledge::ApplyIsColorHint(int color) {
  assert(color >= 0 && color < num_colors_);
  assert(hinted_color_ < 0 || hinted_color_ == color);

  // Must be compatible with existing plausibility.
  bool any = false;
  for (int r = 0; r < num_ranks_; ++r) any = any || plausible_[Index(color, r)];
  assert(any);

  hinted_color_ = color;
  for (int c = 0; c < num_colors_; ++c) {
    if (c == color) continue;
    for (int r = 0; r < num_ranks_; ++r) plausible_[Index(c, r)] = false;
  }

  // Should not eliminate everything.
  bool any_after = false;
  for (bool b : plausible_) any_after = any_after || b;
  assert(any_after);
}

void HanabiHand::CardKnowledge::ApplyIsNotColorHint(int color) {
  assert(color >= 0 && color < num_colors_);
  assert(hinted_color_ < 0 || hinted_color_ != color);

  for (int r = 0; r < num_ranks_; ++r) plausible_[Index(color, r)] = false;

  bool any_after = false;
  for (bool b : plausible_) any_after = any_after || b;
  assert(any_after);
}

void HanabiHand::CardKnowledge::ApplyIsRankHint(int rank) {
  assert(rank >= 0 && rank < num_ranks_);
  assert(hinted_rank_ < 0 || hinted_rank_ == rank);

  bool any = false;
  for (int c = 0; c < num_colors_; ++c) any = any || plausible_[Index(c, rank)];
  assert(any);

  hinted_rank_ = rank;
  for (int r = 0; r < num_ranks_; ++r) {
    if (r == rank) continue;
    for (int c = 0; c < num_colors_; ++c) plausible_[Index(c, r)] = false;
  }

  bool any_after = false;
  for (bool b : plausible_) any_after = any_after || b;
  assert(any_after);
}

void HanabiHand::CardKnowledge::ApplyIsNotRankHint(int rank) {
  assert(rank >= 0 && rank < num_ranks_);
  assert(hinted_rank_ < 0 || hinted_rank_ != rank);

  for (int c = 0; c < num_colors_; ++c) plausible_[Index(c, rank)] = false;

  bool any_after = false;
  for (bool b : plausible_) any_after = any_after || b;
  assert(any_after);
}

void HanabiHand::CardKnowledge::ApplyIsNotCard(int color, int rank) {
  assert(color >= 0 && color < num_colors_);
  assert(rank >= 0 && rank < num_ranks_);

  // If both were directly hinted, banning that exact pair is a contradiction.
  assert(!(hinted_color_ == color && hinted_rank_ == rank));

  plausible_[Index(color, rank)] = false;

  bool any_after = false;
  for (bool b : plausible_) any_after = any_after || b;
  assert(any_after);
}

std::string HanabiHand::CardKnowledge::ToString() const {
  std::string result;
  result = result + (ColorHinted() ? ColorIndexToChar(Color()) : 'X') +
           (RankHinted() ? RankIndexToChar(Rank()) : 'X') + '|';

  // Preserve old-style summary: list plausible colors, then plausible ranks.
  for (int c = 0; c < num_colors_; ++c) {
    if (ColorPlausible(c)) result += ColorIndexToChar(c);
  }
  for (int r = 0; r < num_ranks_; ++r) {
    if (RankPlausible(r)) result += RankIndexToChar(r);
  }
  return result;
}

HanabiHand::HanabiHand(const HanabiHand& hand, bool hide_cards,
                       bool hide_knowledge) {
  if (hide_cards) {
    cards_.resize(hand.cards_.size(), HanabiCard());
  } else {
    cards_ = hand.cards_;
  }
  if (hide_knowledge && !hand.cards_.empty()) {
    card_knowledge_.resize(hand.cards_.size(),
                           CardKnowledge(hand.card_knowledge_[0].NumColors(),
                                         hand.card_knowledge_[0].NumRanks()));
  } else {
    card_knowledge_ = hand.card_knowledge_;
  }
}

void HanabiHand::AddCard(HanabiCard card,
                         const CardKnowledge& initial_knowledge) {
  REQUIRE(card.IsValid());
  cards_.push_back(card);
  card_knowledge_.push_back(initial_knowledge);
}

void HanabiHand::InsertCard(HanabiCard card,
                            const CardKnowledge& initial_knowledge,
                            int card_index) {
  REQUIRE(card.IsValid());

  // Treat -1 as "append to end" (Python uses this convention).
  if (card_index < 0) {
    card_index = static_cast<int>(cards_.size());
  }
  REQUIRE(card_index >= 0 && card_index <= static_cast<int>(cards_.size()));

  cards_.insert(cards_.begin() + card_index, card);
  card_knowledge_.insert(card_knowledge_.begin() + card_index,
                         initial_knowledge);
}

void HanabiHand::RemoveFromHand(int card_index,
                                std::vector<HanabiCard>* discard_pile) {
  if (discard_pile != nullptr) {
    discard_pile->push_back(cards_[card_index]);
  }
  cards_.erase(cards_.begin() + card_index);
  card_knowledge_.erase(card_knowledge_.begin() + card_index);
}

void HanabiHand::ReturnFromHand(int card_index) {
  // Adding to deck is handled by ApplyMove in hanabi_state
  cards_.erase(cards_.begin() + card_index);
}

uint8_t HanabiHand::RevealColor(const int color) {
  uint8_t mask = 0;
  assert(cards_.size() <= 8);  // More than 8 cards is currently not supported.
  for (int i = 0; i < cards_.size(); ++i) {
    if (cards_[i].Color() == color) {
      if (!card_knowledge_[i].ColorHinted()) {
        mask |= static_cast<uint8_t>(1) << i;
      }
      card_knowledge_[i].ApplyIsColorHint(color);
    } else {
      card_knowledge_[i].ApplyIsNotColorHint(color);
    }
  }
  return mask;
}

uint8_t HanabiHand::RevealRank(const int rank) {
  uint8_t mask = 0;
  assert(cards_.size() <= 8);  // More than 8 cards is currently not supported.
  for (int i = 0; i < cards_.size(); ++i) {
    if (cards_[i].Rank() == rank) {
      if (!card_knowledge_[i].RankHinted()) {
        mask |= static_cast<uint8_t>(1) << i;
      }
      card_knowledge_[i].ApplyIsRankHint(rank);
    } else {
      card_knowledge_[i].ApplyIsNotRankHint(rank);
    }
  }
  return mask;
}

std::string HanabiHand::ToString() const {
  std::string result;
  assert(cards_.size() == card_knowledge_.size());
  for (int i = 0; i < cards_.size(); ++i) {
    result +=
        cards_[i].ToString() + " || " + card_knowledge_[i].ToString() + '\n';
  }
  return result;
}

}  // namespace hanabi_learning_env
