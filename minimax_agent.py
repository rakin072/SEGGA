# -*- coding: utf-8 -*-
"""
Created on Sat Nov 21 01:27:31 2026

@author: omarr
"""

import math
import random

EMPTY = 0
P1 = 1
P2 = 2
CENTER = (2, 2)


class MinimaxAgent:
    """
    Minimax AI with Alpha-Beta Pruning & Move Ordering.
    Evaluates:
      1. Piece Parity (Material difference)
      2. Orthogonal Mobility (Available legal step moves)
      3. Trapping / Custodial Threat Potential & Center Sanctuary Control
    """
    def __init__(self, player_id, max_depth=3):
        self.player_id = player_id
        self.max_depth = max_depth
        self.nodes_evaluated = 0

    def get_move(self, state):
        self.nodes_evaluated = 0
        legal_moves = state.get_legal_moves()
        if not legal_moves:
            return None
        if len(legal_moves) == 1:
            return legal_moves[0]

        # Order moves to improve alpha-beta pruning efficiency
        ordered_moves = self._order_moves(state, legal_moves)

        best_score = -math.inf
        best_moves = []
        alpha = -math.inf
        beta = math.inf

        # Adjust depth dynamically in Phase 1 (high branching factor: up to 24 empty cells)
        search_depth = self.max_depth if state.phase == 2 else min(self.max_depth, 3)

        for move in ordered_moves:
            next_state = state.clone()
            next_state.apply_move(move)
            score = self._alphabeta(next_state, search_depth - 1, alpha, beta)

            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

            alpha = max(alpha, best_score)

        return random.choice(best_moves)

    def _alphabeta(self, state, depth, alpha, beta):
        self.nodes_evaluated += 1

        if depth == 0 or state.is_terminal():
            return self.evaluate(state)

        legal_moves = self._order_moves(state, state.get_legal_moves())
        if not legal_moves:
            return self.evaluate(state)

        is_maximizing = (state.current_player == self.player_id)

        if is_maximizing:
            value = -math.inf
            for move in legal_moves:
                child = state.clone()
                child.apply_move(move)
                value = max(value, self._alphabeta(child, depth - 1, alpha, beta))
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value
        else:
            value = math.inf
            for move in legal_moves:
                child = state.clone()
                child.apply_move(move)
                value = min(value, self._alphabeta(child, depth - 1, alpha, beta))
                beta = min(beta, value)
                if alpha >= beta:
                    break
            return value

    def _order_moves(self, state, moves):
        """Prioritizes capturing moves and central drops for faster pruning."""
        if state.phase == 1:
            def drop_priority(m):
                r, c = m[1]
                dist_to_center = abs(r - 2) + abs(c - 2)
                return -dist_to_center
            return sorted(moves, key=drop_priority, reverse=True)
        else:
            scored = []
            for m in moves:
                if m[0] == 'END_CHAIN':
                    scored.append((0, m))
                else:
                    (r1, c1), (r2, c2) = m[1], m[2]
                    caps = 10 if state._would_capture(r1, c1, r2, c2, state.current_player) else 0
                    center_bonus = 2 if (r2, c2) == CENTER else 0
                    scored.append((caps + center_bonus, m))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [m for _, m in scored]

    def evaluate(self, state):
        opp = state.get_opponent(self.player_id)
        winner = state.get_winner()
        if winner == self.player_id:
            return 10000.0
        elif winner == opp:
            return -10000.0
        elif winner == 0:
            return 0.0

        my_pieces = state.p1_pieces if self.player_id == P1 else state.p2_pieces
        opp_pieces = state.p2_pieces if self.player_id == P1 else state.p1_pieces

        # 1. Piece Parity (strongest weight)
        parity_score = (my_pieces - opp_pieces) * 120.0

        # 2. Mobility & Positional Features
        my_mobility = 0
        opp_mobility = 0
        my_threats = 0
        opp_threats = 0
        positional_score = 0

        for r in range(5):
            for c in range(5):
                cell = state.board[r][c]
                if cell == EMPTY:
                    continue

                # Mobility count
                mob = 0
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 5 and 0 <= nc < 5 and state.board[nr][nc] == EMPTY:
                        mob += 1

                if cell == self.player_id:
                    my_mobility += mob
                    if (r, c) == CENTER:
                        positional_score += 25.0  # Safe sanctuary hub
                    elif abs(r - 2) + abs(c - 2) == 1:
                        positional_score += 10.0  # Inner ring control
                    if (r in (0, 4)) and (c in (0, 4)):
                        positional_score += 6.0   # Corners cannot be sandwiched easily
                else:
                    opp_mobility += mob
                    if (r, c) == CENTER:
                        positional_score -= 25.0
                    elif abs(r - 2) + abs(c - 2) == 1:
                        positional_score -= 10.0

                # 3. Trapping / Vulnerability Check (Custodial sandwich danger)
                if (r, c) != CENTER:
                    enemy = opp if cell == self.player_id else self.player_id
                    for dr, dc in [(0, 1), (1, 0)]:
                        r_a, c_a = r - dr, c - dc
                        r_b, c_b = r + dr, c + dc
                        if 0 <= r_a < 5 and 0 <= c_a < 5 and 0 <= r_b < 5 and 0 <= c_b < 5:
                            side_a = state.board[r_a][c_a]
                            side_b = state.board[r_b][c_b]
                            if (side_a == enemy and side_b == EMPTY) or (side_b == enemy and side_a == EMPTY):
                                empty_r, empty_c = (r_b, c_b) if side_a == enemy else (r_a, c_a)
                                can_close_trap = False
                                for tr, tc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                    er, ec = empty_r + tr, empty_c + tc
                                    if (er, ec) != (r_a, c_a) and (er, ec) != (r_b, c_b):
                                        if 0 <= er < 5 and 0 <= ec < 5 and state.board[er][ec] == enemy:
                                            can_close_trap = True
                                            break
                                if can_close_trap:
                                    if cell == self.player_id:
                                        opp_threats += 1
                                    else:
                                        my_threats += 1

        mobility_score = (my_mobility - opp_mobility) * 8.0
        threat_score = (my_threats - opp_threats) * 35.0

        return parity_score + mobility_score + threat_score + positional_score