def _move_to_action_dict(move: pyhanabi.HanabiMove) -> Dict[str, Any]:
    move_type = move.type()
    payload: Dict[str, Any] = {"action_type": move_type.name}
    if move_type in (pyhanabi.HanabiMoveType.PLAY, pyhanabi.HanabiMoveType.DISCARD):
        payload["card_index"] = move.card_index()
    elif move_type == pyhanabi.HanabiMoveType.REVEAL_COLOR:
        payload["target_offset"] = move.target_offset()
        payload["color"] = pyhanabi.COLOR_CHAR[move.color()]
    elif move_type == pyhanabi.HanabiMoveType.REVEAL_RANK:
        payload["target_offset"] = move.target_offset()
        payload["rank"] = move.rank()
    elif move_type == pyhanabi.HanabiMoveType.DEAL:
        payload["target_offset"] = move.target_offset()
        payload["color"] = pyhanabi.COLOR_CHAR[move.color()]
        payload["rank"] = move.rank()
    return payload


def _action_dict_to_move(data: Dict[str, Any]) -> pyhanabi.HanabiMove:
    try:
        move_type = pyhanabi.HanabiMoveType[data["action_type"].upper()]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unknown action type: {data}") from exc

    if move_type == pyhanabi.HanabiMoveType.PLAY:
        return pyhanabi.HanabiMove.get_play_move(int(data["card_index"]))
    if move_type == pyhanabi.HanabiMoveType.DISCARD:
        return pyhanabi.HanabiMove.get_discard_move(int(data["card_index"]))
    if move_type == pyhanabi.HanabiMoveType.REVEAL_COLOR:
        color = data["color"]
        if isinstance(color, str):
            color_idx = pyhanabi.color_char_to_idx(color)
        else:
            color_idx = int(color)
        if color_idx < 0 or color_idx >= HANABI_GAME_CONFIG["colors"]:
            raise ValueError(f"Reveal color out of range: {color_idx}")
        return pyhanabi.HanabiMove.get_reveal_color_move(
            int(data["target_offset"]), color_idx
        )
    if move_type == pyhanabi.HanabiMoveType.REVEAL_RANK:
        rank = int(data["rank"])
        if rank < 0 or rank >= HANABI_GAME_CONFIG["ranks"]:
            raise ValueError(f"Reveal rank out of range: {rank}")
        return pyhanabi.HanabiMove.get_reveal_rank_move(
            int(data["target_offset"]), rank
        )
    raise ValueError(f"Unsupported move payload: {data}")


def _clone_move_for_state(move: Any) -> pyhanabi.HanabiMove:
    """
    Build a fresh HanabiMove detached from any original state.

    Accepts an existing HanabiMove or an action dict. Raises on unsupported inputs.
    """
    if isinstance(move, pyhanabi.HanabiMove):
        move = _move_to_action_dict(move)
    print(move)
    if isinstance(move, dict):
        return _action_dict_to_move(move)
    print(move)
    raise ValueError(f"Unsupported move type for cloning: {move!r}")


def apply_move_safe(state: pyhanabi.HanabiState, move: Any) -> None:
    """
    Apply a move to state, cloning/validating to avoid cross-state corruption.

    Supports:
      - pyhanabi.HanabiMove or action dict (applied via _clone_move_for_state)
      - (player, color, rank) tuples/lists for DEAL events (applied via deal_specific_card)
    """
    if isinstance(move, (list, tuple)) and len(move) == 3 and not isinstance(move, pyhanabi.HanabiMove):
        state.deal_specific_card(*move)
        return
    cloned = _clone_move_for_state(move)
    state.apply_move(cloned)
