# -*- coding: utf-8 -*-
"""
Created on Sat Nov 21 01:28:42 2026

@author: omarr
"""

import math
import random

P1 = 1
P2 = 2


class MCTSNode:
    def __init__(self, state, parent=None, move=None):
        self.state = state
        self.parent = parent
        self.move = move
        self.children = []
        self.untried_moves = state.get_legal_moves()
        random.shuffle(self.untried_moves)
        self.visits = 0
        self.wins = 0.0  # From the perspective of parent's current_player

    def is_fully_expanded(self):
        return len(self.untried_moves) == 0

    def best_uct_child(self, c_param=1.414):
        best_score = -math.inf
        best_child = None
        for child in self.children:
            if child.visits == 0:
                score = math.inf
            else:
                exploitation = child.wins / child.visits
                exploration = c_param * math.sqrt(math.log(self.visits) / child.visits)
                score = exploitation + exploration
            if score > best_score:
                best_score = score
                best_child = child
        return best_child


class MCTSAgent:
    """
    Monte Carlo Tree Search (MCTS) using UCT selection and Capture-Driven Rollouts.
    """
    def __init__(self, player_id, iterations=450, rollout_depth=35):
        self.player_id = player_id
        self.iterations = iterations
        self.rollout_depth = rollout_depth
        self.last_iterations_run = 0

    def get_move(self, root_state):
        legal_moves = root_state.get_legal_moves()
        if not legal_moves:
            return None
        if len(legal_moves) == 1:
            return legal_moves[0]

        root_node = MCTSNode(root_state.clone())

        for _ in range(self.iterations):
            node = root_node
            state = root_state.clone()

            # 1. SELECTION
            while not state.is_terminal() and node.is_fully_expanded() and node.children:
                node = node.best_uct_child()
                state.apply_move(node.move)

            # 2. EXPANSION
            if not state.is_terminal() and not node.is_fully_expanded():
                move = node.untried_moves.pop()
                acting_player = state.current_player
                state.apply_move(move)
                child_node = MCTSNode(state.clone(), parent=node, move=move)
                child_node.actor = acting_player
                node.children.append(child_node)
                node = child_node

            # 3. SIMULATION (Tactical Capture-Biased Rollout)
            reward_for_p1 = self._tactical_rollout(state)

            # 4. BACKPROPAGATION
            curr = node
            while curr is not None:
                curr.visits += 1
                if hasattr(curr, 'actor'):
                    if curr.actor == P1:
                        curr.wins += reward_for_p1
                    else:
                        curr.wins += (1.0 - reward_for_p1)
                curr = curr.parent

        self.last_iterations_run = self.iterations
        if not root_node.children:
            return random.choice(legal_moves)

        # Return move with highest visit count (robust child)
        best_child = max(root_node.children, key=lambda c: c.visits)
        return best_child.move

    def _tactical_rollout(self, state):
        """
        Simulates a game up to `rollout_depth` steps using capture-biased heuristics,
        returning a normalized reward in [0.0, 1.0] from P1's perspective.
        """
        steps = 0
        while not state.is_terminal() and steps < self.rollout_depth:
            moves = state.get_legal_moves()
            if not moves:
                break

            chosen_move = None
            if state.phase == 2:
                # 80% chance to greedily pick a capturing move if one exists
                capture_moves = [
                    m for m in moves
                    if m[0] == 'MOVE' and state._would_capture(
                        m[1][0], m[1][1], m[2][0], m[2][1], state.current_player
                    )
                ]
                if capture_moves and random.random() < 0.80:
                    chosen_move = random.choice(capture_moves)

            if chosen_move is None:
                chosen_move = random.choice(moves)

            state.apply_move(chosen_move)
            steps += 1

        winner = state.get_winner()
        if winner == P1:
            return 1.0
        elif winner == P2:
            return 0.0
        elif winner == 0:
            return 0.5

        # Depth cutoff evaluation based on piece advantage
        diff = state.p1_pieces - state.p2_pieces
        return max(0.05, min(0.95, 0.5 + (diff * 0.06)))