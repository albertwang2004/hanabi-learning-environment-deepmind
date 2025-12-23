cd ~/src/hanabi-learning-environment-deepmind/hanabi_learning_environment

# Recompile the shared library from sources
c++ -O3 -shared -fPIC -std=c++17 \
  -I. -I./hanabi_lib \
  -o libpyhanabi.so \
  pyhanabi.cc \
  hanabi_lib/canonical_encoders.cc \
  hanabi_lib/hanabi_card.cc \
  hanabi_lib/hanabi_game.cc \
  hanabi_lib/hanabi_hand.cc \
  hanabi_lib/hanabi_history_item.cc \
  hanabi_lib/hanabi_move.cc \
  hanabi_lib/hanabi_observation.cc \
  hanabi_lib/hanabi_state.cc \
  hanabi_lib/util.cc
