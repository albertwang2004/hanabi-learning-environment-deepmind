# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Small script that intentionally triggers an illegal move."""

from __future__ import print_function

from hanabi_learning_environment import rl_env


def main():
  env = rl_env.make()
  observation = env.reset()
  print("Initial legal moves for player 0:", observation["player_observations"]
        [0]["legal_moves"])

  # At the start of a game all information tokens are available, so discarding
  # is illegal. This deliberately sends that action to show the verbose error.
  illegal_action = {"action_type": "DISCARD", "card_index": 0}
  try:
    env.step(illegal_action)
  except AssertionError as err:
    print("Caught AssertionError with verbose context:\n{}".format(err))
    print("\nState at failure:\n{}".format(env.state))


if __name__ == "__main__":
  main()
