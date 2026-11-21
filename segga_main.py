# -*- coding: utf-8 -*-
"""
Created on Sat Nov 21 01:29:28 2026

@author: omarr
"""

import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading

# Import the two AI agents from their separate files
from minimax_agent import MinimaxAgent
from mcts_agent import MCTSAgent

# =====================================================================
# 1. GAME STATE & RULES ENGINE (5x5 SEGGA / SEEGA)
# =====================================================================

EMPTY = 0
P1 = 1  # Gold / Dark (Moves first in Phase 1, second in Phase 2)
P2 = 2  # Teal / Light (Moves second in Phase 1, first in Phase 2)
CENTER = (2, 2)


class SeggaState:
    """
    Represents the exact state of a 5x5 Segga game.
    Phase 1: Players place 2 pieces per turn until 24 pieces are on board.
    Phase 2: Orthogonal movement & custodial (sandwich) captures.
    """
    def __init__(self):
        self.board = [[EMPTY for _ in range(5)] for _ in range(5)]
        self.phase = 1
        self.current_player = P1
        self.p1_to_place = 12
        self.p2_to_place = 12
        self.drops_remaining_in_turn = 2
        self.p1_pieces = 0
        self.p2_pieces = 0
        self.chain_piece = None
        self.no_capture_moves = 0
        self.max_no_capture = 60

    def clone(self):
        new_state = SeggaState()
        new_state.board = [row[:] for row in self.board]
        new_state.phase = self.phase
        new_state.current_player = self.current_player
        new_state.p1_to_place = self.p1_to_place
        new_state.p2_to_place = self.p2_to_place
        new_state.drops_remaining_in_turn = self.drops_remaining_in_turn
        new_state.p1_pieces = self.p1_pieces
        new_state.p2_pieces = self.p2_pieces
        new_state.chain_piece = self.chain_piece
        new_state.no_capture_moves = self.no_capture_moves
        return new_state

    def get_opponent(self, player=None):
        if player is None:
            player = self.current_player
        return P2 if player == P1 else P1

    def get_legal_moves(self):
        if self.is_terminal():
            return []

        if self.phase == 1:
            moves = []
            for r in range(5):
                for c in range(5):
                    if (r, c) != CENTER and self.board[r][c] == EMPTY:
                        moves.append(('DROP', (r, c)))
            return moves

        # Phase 2
        if self.chain_piece is not None:
            r, c = self.chain_piece
            chain_moves = [('END_CHAIN', None, None)]
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < 5 and 0 <= nc < 5 and self.board[nr][nc] == EMPTY:
                    if self._would_capture(r, c, nr, nc, self.current_player):
                        chain_moves.append(('MOVE', (r, c), (nr, nc)))
            return chain_moves

        moves = []
        for r in range(5):
            for c in range(5):
                if self.board[r][c] == self.current_player:
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < 5 and 0 <= nc < 5 and self.board[nr][nc] == EMPTY:
                            moves.append(('MOVE', (r, c), (nr, nc)))
        return moves

    def _would_capture(self, r1, c1, r2, c2, player):
        opp = self.get_opponent(player)
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            mr, mc = r2 + dr, c2 + dc
            fr, fc = r2 + 2 * dr, c2 + 2 * dc
            if 0 <= mr < 5 and 0 <= mc < 5 and 0 <= fr < 5 and 0 <= fc < 5:
                if (mr, mc) == CENTER:
                    continue
                if (fr, fc) == (r1, c1):
                    continue
                if self.board[mr][mc] == opp and self.board[fr][fc] == player:
                    return True
        return False

    def apply_move(self, move):
        move_type = move[0]
        captured_coords = []

        if move_type == 'DROP':
            r, c = move[1]
            self.board[r][c] = self.current_player
            if self.current_player == P1:
                self.p1_to_place -= 1
                self.p1_pieces += 1
            else:
                self.p2_to_place -= 1
                self.p2_pieces += 1

            self.drops_remaining_in_turn -= 1

            if self.p1_to_place == 0 and self.p2_to_place == 0:
                self.phase = 2
                self.current_player = P2
                self.drops_remaining_in_turn = 0
                self._handle_blocked_opponent()
            elif self.drops_remaining_in_turn == 0:
                self.current_player = self.get_opponent()
                self.drops_remaining_in_turn = 2

        elif move_type == 'END_CHAIN':
            self.chain_piece = None
            self.current_player = self.get_opponent()
            self._handle_blocked_opponent()

        elif move_type == 'MOVE':
            (r1, c1), (r2, c2) = move[1], move[2]
            player = self.current_player
            opp = self.get_opponent(player)

            self.board[r1][c1] = EMPTY
            self.board[r2][c2] = player

            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                mr, mc = r2 + dr, c2 + dc
                fr, fc = r2 + 2 * dr, c2 + 2 * dc
                if 0 <= mr < 5 and 0 <= mc < 5 and 0 <= fr < 5 and 0 <= fc < 5:
                    if (mr, mc) != CENTER and self.board[mr][mc] == opp and self.board[fr][fc] == player:
                        self.board[mr][mc] = EMPTY
                        captured_coords.append((mr, mc))
                        if opp == P1:
                            self.p1_pieces -= 1
                        else:
                            self.p2_pieces -= 1

            if captured_coords:
                self.no_capture_moves = 0
                can_chain = False
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r2 + dr, c2 + dc
                    if 0 <= nr < 5 and 0 <= nc < 5 and self.board[nr][nc] == EMPTY:
                        if self._would_capture(r2, c2, nr, nc, player):
                            can_chain = True
                            break
                if can_chain and not self.is_terminal():
                    self.chain_piece = (r2, c2)
                else:
                    self.chain_piece = None
                    self.current_player = opp
                    self._handle_blocked_opponent()
            else:
                self.no_capture_moves += 1
                self.chain_piece = None
                self.current_player = opp
                self._handle_blocked_opponent()

        return captured_coords

    def _handle_blocked_opponent(self):
        if self.phase == 2 and not self.is_terminal():
            legal = self.get_legal_moves()
            if not legal:
                self.current_player = self.get_opponent()

    def is_terminal(self):
        if self.phase == 1:
            return False
        if self.p1_pieces <= 1 or self.p2_pieces <= 1:
            return True
        if self.no_capture_moves >= self.max_no_capture:
            return True
        p1_moves = self._has_any_move(P1)
        p2_moves = self._has_any_move(P2)
        if not p1_moves and not p2_moves:
            return True
        return False

    def _has_any_move(self, player):
        for r in range(5):
            for c in range(5):
                if self.board[r][c] == player:
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < 5 and 0 <= nc < 5 and self.board[nr][nc] == EMPTY:
                            return True
        return False

    def get_winner(self):
        if not self.is_terminal():
            return None
        if self.p1_pieces <= 1 and self.p2_pieces > 1:
            return P2
        if self.p2_pieces <= 1 and self.p1_pieces > 1:
            return P1
        if self.p1_pieces > self.p2_pieces:
            return P1
        elif self.p2_pieces > self.p1_pieces:
            return P2
        else:
            return 0


# =====================================================================
# 2. INTERACTIVE TKINTER GUI (SPYDER COMPATIBLE)
# =====================================================================

class SeggaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Segga: Ancient Tactical Board Game (Minimax α-β vs MCTS)")
        self.root.geometry("1040x720")
        self.root.configure(bg="#1E1B18")
        self.root.resizable(False, False)

        self.col_bg = "#1E1B18"
        self.col_panel = "#2A2521"
        self.col_board = "#D8C39E"
        self.col_sanctuary = "#B89B67"
        self.col_grid = "#5C4938"
        self.col_p1 = "#D99B26"
        self.col_p1_outline = "#FFF0C2"
        self.col_p2 = "#1F7A8C"
        self.col_p2_outline = "#B8F2FF"
        self.col_highlight = "#4CAF50"
        self.col_last_move = "#E65100"

        self.state = SeggaState()
        self.selected_square = None
        self.last_move_squares = []
        self.last_captured_squares = []

        self.is_running = False
        self.is_paused = False
        self.ai_thinking = False
        self.move_count = 0

        self._build_ui()
        self.reset_game()

    def _build_ui(self):
        left_frame = tk.Frame(self.root, bg=self.col_bg, padx=20, pady=20)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH)

        right_frame = tk.Frame(self.root, bg=self.col_panel, width=380, padx=18, pady=18)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.title_lbl = tk.Label(
            left_frame,
            text="SEGGA (5×5 CUSTODIAL ENGINE)",
            font=("Georgia", 18, "bold"),
            fg="#F2D091",
            bg=self.col_bg
        )
        self.title_lbl.pack(pady=(0, 6))

        self.phase_lbl = tk.Label(
            left_frame,
            text="PHASE 1: TACTICAL DROP PHASE",
            font=("Consolas", 12, "bold"),
            fg="#A3E635",
            bg=self.col_bg
        )
        self.phase_lbl.pack(pady=(0, 10))

        self.canvas_size = 550
        self.cell_size = self.canvas_size // 5
        self.canvas = tk.Canvas(
            left_frame,
            width=self.canvas_size,
            height=self.canvas_size,
            bg=self.col_board,
            highlightthickness=3,
            highlightbackground="#8C6D46"
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        self.status_lbl = tk.Label(
            left_frame,
            text="Select mode and press 'Start / Resume' or click board to play.",
            font=("Segoe UI", 11),
            fg="#E5E5E5",
            bg=self.col_bg,
            pady=8
        )
        self.status_lbl.pack()

        # ---------------- RIGHT CONTROL PANEL ----------------
        tk.Label(
            right_frame, text="MATCH CONFIGURATION",
            font=("Georgia", 13, "bold"), fg="#F2D091", bg=self.col_panel
        ).pack(anchor="w", pady=(0, 8))

        tk.Label(right_frame, text="Game Mode:", font=("Segoe UI", 10, "bold"), fg="#CCCCCC", bg=self.col_panel).pack(anchor="w")
        self.mode_var = tk.StringVar(value="AI_VS_AI")
        modes = [
            ("AI vs AI (Minimax α-β vs MCTS)", "AI_VS_AI"),
            ("AI vs AI (MCTS vs Minimax α-β)", "AI_VS_AI_SWAP"),
            ("Human (Gold) vs Minimax AI (Teal)", "HUMAN_VS_MINIMAX"),
            ("Human (Gold) vs MCTS AI (Teal)", "HUMAN_VS_MCTS"),
        ]
        for text, val in modes:
            rb = tk.Radiobutton(
                right_frame, text=text, variable=self.mode_var, value=val,
                command=self.on_mode_change,
                font=("Segoe UI", 9), fg="#FFFFFF", bg=self.col_panel,
                selectcolor="#443C36", activebackground=self.col_panel, activeforeground="#F2D091"
            )
            rb.pack(anchor="w", pady=1)

        param_frame = tk.Frame(right_frame, bg=self.col_panel, pady=8)
        param_frame.pack(fill=tk.X)

        tk.Label(param_frame, text="Minimax Depth:", font=("Segoe UI", 9), fg="#CCCCCC", bg=self.col_panel).grid(row=0, column=0, sticky="w")
        self.depth_var = tk.IntVar(value=3)
        depth_spin = tk.Spinbox(param_frame, from_=2, to=4, textvariable=self.depth_var, width=5, font=("Segoe UI", 9))
        depth_spin.grid(row=0, column=1, padx=8, pady=2, sticky="w")

        tk.Label(param_frame, text="MCTS Rollouts:", font=("Segoe UI", 9), fg="#CCCCCC", bg=self.col_panel).grid(row=1, column=0, sticky="w")
        self.mcts_iter_var = tk.IntVar(value=400)
        mcts_spin = tk.Spinbox(param_frame, from_=100, to=1200, increment=100, textvariable=self.mcts_iter_var, width=6, font=("Segoe UI", 9))
        mcts_spin.grid(row=1, column=1, padx=8, pady=2, sticky="w")

        tk.Label(param_frame, text="AI Delay (ms):", font=("Segoe UI", 9), fg="#CCCCCC", bg=self.col_panel).grid(row=2, column=0, sticky="w")
        self.delay_var = tk.IntVar(value=350)
        delay_spin = tk.Spinbox(param_frame, from_=50, to=1500, increment=100, textvariable=self.delay_var, width=6, font=("Segoe UI", 9))
        delay_spin.grid(row=2, column=1, padx=8, pady=2, sticky="w")

        btn_frame = tk.Frame(right_frame, bg=self.col_panel, pady=6)
        btn_frame.pack(fill=tk.X)

        self.start_btn = tk.Button(
            btn_frame, text="▶ Start / Resume", command=self.start_or_resume,
            font=("Segoe UI", 10, "bold"), bg="#388E3C", fg="white", width=15, relief=tk.FLAT, pady=4
        )
        self.start_btn.grid(row=0, column=0, padx=4, pady=3)

        self.pause_btn = tk.Button(
            btn_frame, text="⏸ Pause", command=self.pause_game,
            font=("Segoe UI", 10, "bold"), bg="#F57C00", fg="white", width=15, relief=tk.FLAT, pady=4
        )
        self.pause_btn.grid(row=0, column=1, padx=4, pady=3)

        self.step_btn = tk.Button(
            btn_frame, text="⏭ Step 1 AI Move", command=self.step_ai_move,
            font=("Segoe UI", 10, "bold"), bg="#0288D1", fg="white", width=15, relief=tk.FLAT, pady=4
        )
        self.step_btn.grid(row=1, column=0, padx=4, pady=3)

        self.reset_btn = tk.Button(
            btn_frame, text="↺ New Game", command=self.reset_game,
            font=("Segoe UI", 10, "bold"), bg="#C62828", fg="white", width=15, relief=tk.FLAT, pady=4
        )
        self.reset_btn.grid(row=1, column=1, padx=4, pady=3)

        score_frame = tk.Frame(right_frame, bg="#1E1B18", padx=12, pady=10, highlightbackground="#5C4938", highlightthickness=1)
        score_frame.pack(fill=tk.X, pady=8)

        self.p1_info_lbl = tk.Label(score_frame, text="P1 (Gold): 0 on board | 12 in hand", font=("Consolas", 10, "bold"), fg=self.col_p1, bg="#1E1B18")
        self.p1_info_lbl.pack(anchor="w")

        self.p2_info_lbl = tk.Label(score_frame, text="P2 (Teal): 0 on board | 12 in hand", font=("Consolas", 10, "bold"), fg="#4DD0E1", bg="#1E1B18")
        self.p2_info_lbl.pack(anchor="w", pady=(4, 0))

        self.end_chain_btn = tk.Button(
            score_frame, text="End Capture Chain Turn", command=self.human_end_chain,
            font=("Segoe UI", 9, "bold"), bg="#6A1B9A", fg="white", state=tk.DISABLED
        )
        self.end_chain_btn.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            right_frame, text="ENGINE TELEMETRY & LOG",
            font=("Georgia", 11, "bold"), fg="#F2D091", bg=self.col_panel
        ).pack(anchor="w", pady=(6, 4))

        log_container = tk.Frame(right_frame, bg="#141210")
        log_container.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(log_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(
            log_container, height=12, width=38, bg="#141210", fg="#D4D4D4",
            font=("Consolas", 9), yscrollcommand=scrollbar.set, state=tk.DISABLED, wrap=tk.WORD
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)

    # =================================================================
    # GAME FLOW & AI CONTROLLERS
    # =================================================================

    def configure_agents(self):
        mode = self.mode_var.get()
        depth = self.depth_var.get()
        iters = self.mcts_iter_var.get()

        if mode == "AI_VS_AI":
            self.agents = {
                P1: ("Minimax α-β", MinimaxAgent(P1, max_depth=depth)),
                P2: ("MCTS (UCT)", MCTSAgent(P2, iterations=iters))
            }
        elif mode == "AI_VS_AI_SWAP":
            self.agents = {
                P1: ("MCTS (UCT)", MCTSAgent(P1, iterations=iters)),
                P2: ("Minimax α-β", MinimaxAgent(P2, max_depth=depth))
            }
        elif mode == "HUMAN_VS_MINIMAX":
            self.agents = {
                P1: ("Human", None),
                P2: ("Minimax α-β", MinimaxAgent(P2, max_depth=depth))
            }
        elif mode == "HUMAN_VS_MCTS":
            self.agents = {
                P1: ("Human", None),
                P2: ("MCTS (UCT)", MCTSAgent(P2, iterations=iters))
            }

    def on_mode_change(self):
        self.reset_game()

    def reset_game(self):
        self.is_running = False
        self.is_paused = False
        self.ai_thinking = False
        self.state = SeggaState()
        self.selected_square = None
        self.last_move_squares = []
        self.last_captured_squares = []
        self.move_count = 0
        self.configure_agents()

        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

        p1_name = self.agents[P1][0]
        p2_name = self.agents[P2][0]
        self.log(f"=== NEW SEGGA MATCH ===")
        self.log(f"Gold (P1): {p1_name}")
        self.log(f"Teal (P2): {p2_name}")
        self.log("Phase 1: Place 2 pieces per turn outside the center sanctuary (2,2).\n")

        self.update_ui()

        if self.agents[P1][1] is None:
            self.is_running = True
            self.status_lbl.config(text="Your Turn (Gold): Click an empty square to drop a piece.")
        else:
            self.status_lbl.config(text="Press '▶ Start / Resume' to launch autonomous AI vs AI battle.")

    def start_or_resume(self):
        if self.state.is_terminal():
            self.reset_game()
        self.configure_agents()
        self.is_running = True
        self.is_paused = False
        self.trigger_next_turn()

    def pause_game(self):
        self.is_paused = True
        self.status_lbl.config(text="Game Paused. Press '▶ Start / Resume' or '⏭ Step 1 AI Move'.")

    def step_ai_move(self):
        if self.state.is_terminal() or self.ai_thinking:
            return
        self.configure_agents()
        self.is_paused = True
        self.is_running = True
        curr_p = self.state.current_player
        if self.agents[curr_p][1] is not None:
            self._run_ai_turn_async()
        else:
            self.status_lbl.config(text="Current turn belongs to Human player.")

    def trigger_next_turn(self):
        if not self.is_running or self.is_paused or self.ai_thinking:
            return

        if self.state.is_terminal():
            self.handle_game_over()
            return

        curr_p = self.state.current_player
        agent_name, agent_obj = self.agents[curr_p]

        if agent_obj is None and self.state.chain_piece is not None:
            self.end_chain_btn.config(state=tk.NORMAL)
        else:
            self.end_chain_btn.config(state=tk.DISABLED)

        if agent_obj is None:
            p_color = "Gold (P1)" if curr_p == P1 else "Teal (P2)"
            if self.state.phase == 1:
                self.status_lbl.config(
                    text=f"Your Turn [{p_color}]: Drop {self.state.drops_remaining_in_turn} more piece(s)."
                )
            elif self.state.chain_piece is not None:
                self.status_lbl.config(
                    text=f"Capture Chain! Move {self.state.chain_piece} for another capture or End Turn."
                )
            else:
                self.status_lbl.config(text=f"Your Turn [{p_color}]: Select a piece and move orthogonally.")
        else:
            self._run_ai_turn_async()

    def _run_ai_turn_async(self):
        if self.ai_thinking or self.state.is_terminal():
            return
        self.ai_thinking = True
        curr_p = self.state.current_player
        agent_name, agent_obj = self.agents[curr_p]
        p_tag = "P1 (Gold)" if curr_p == P1 else "P2 (Teal)"
        self.status_lbl.config(text=f"{p_tag} [{agent_name}] is computing move...")

        state_copy = self.state.clone()

        def worker():
            t0 = time.perf_counter()
            move = agent_obj.get_move(state_copy)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.root.after(0, lambda: self._apply_ai_move(move, agent_name, agent_obj, elapsed_ms))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_ai_move(self, move, agent_name, agent_obj, elapsed_ms):
        self.ai_thinking = False
        if move is None:
            self.update_ui()
            self.handle_game_over()
            return

        curr_p = self.state.current_player
        p_tag = "P1" if curr_p == P1 else "P2"
        prev_phase = self.state.phase

        captured = self.state.apply_move(move)
        self.move_count += 1

        if move[0] == 'DROP':
            self.last_move_squares = [move[1]]
            desc = f"Drop at {move[1]}"
        elif move[0] == 'MOVE':
            self.last_move_squares = [move[1], move[2]]
            desc = f"{move[1]} -> {move[2]}"
        else:
            self.last_move_squares = []
            desc = "End Chain"

        self.last_captured_squares = captured

        metric_str = ""
        if isinstance(agent_obj, MinimaxAgent):
            metric_str = f"Nodes:{agent_obj.nodes_evaluated}"
        elif isinstance(agent_obj, MCTSAgent):
            metric_str = f"Rollouts:{agent_obj.last_iterations_run}"

        cap_str = f" | CAPTURED {captured}!" if captured else ""
        self.log(f"#{self.move_count:02d} {p_tag}[{agent_name}]: {desc}{cap_str} ({elapsed_ms:.0f}ms, {metric_str})")

        if prev_phase == 1 and self.state.phase == 2:
            self.log("\n>>> PHASE 2 BEGINS: Orthogonal Moves & Custodial Captures! <<<\n")

        self.update_ui()

        if self.state.is_terminal():
            self.handle_game_over()
            return

        if not self.is_paused and self.is_running:
            delay = max(50, self.delay_var.get())
            self.root.after(delay, self.trigger_next_turn)

    # =================================================================
    # HUMAN INPUT HANDLERS
    # =================================================================

    def on_canvas_click(self, event):
        if self.ai_thinking or self.state.is_terminal():
            return

        curr_p = self.state.current_player
        agent_name, agent_obj = self.agents[curr_p]
        if agent_obj is not None:
            return

        c = event.x // self.cell_size
        r = event.y // self.cell_size
        if not (0 <= r < 5 and 0 <= c < 5):
            return

        prev_phase = self.state.phase

        if self.state.phase == 1:
            move = ('DROP', (r, c))
            if move in self.state.get_legal_moves():
                self.state.apply_move(move)
                self.move_count += 1
                self.last_move_squares = [(r, c)]
                self.last_captured_squares = []
                self.log(f"#{self.move_count:02d} P{curr_p}[Human]: Drop at {(r, c)}")
                if prev_phase == 1 and self.state.phase == 2:
                    self.log("\n>>> PHASE 2 BEGINS: Orthogonal Moves & Custodial Captures! <<<\n")
                self.update_ui()
                self.is_paused = False
                self.is_running = True
                self.root.after(150, self.trigger_next_turn)
            else:
                self.status_lbl.config(text="Invalid Drop! Center sanctuary (2,2) and occupied squares are forbidden.")
            return

        if self.state.chain_piece is not None:
            self.selected_square = self.state.chain_piece

        if self.selected_square is None:
            if self.state.board[r][c] == curr_p:
                self.selected_square = (r, c)
                self.update_ui()
        else:
            if (r, c) == self.selected_square and self.state.chain_piece is None:
                self.selected_square = None
                self.update_ui()
            elif self.state.board[r][c] == curr_p and self.state.chain_piece is None:
                self.selected_square = (r, c)
                self.update_ui()
            else:
                move = ('MOVE', self.selected_square, (r, c))
                if move in self.state.get_legal_moves():
                    captured = self.state.apply_move(move)
                    self.move_count += 1
                    self.last_move_squares = [self.selected_square, (r, c)]
                    self.last_captured_squares = captured
                    cap_str = f" | CAPTURED {captured}!" if captured else ""
                    self.log(f"#{self.move_count:02d} P{curr_p}[Human]: {self.selected_square} -> {(r, c)}{cap_str}")
                    self.selected_square = self.state.chain_piece
                    self.update_ui()
                    self.is_paused = False
                    self.is_running = True
                    self.root.after(150, self.trigger_next_turn)

    def human_end_chain(self):
        if self.state.chain_piece is not None:
            self.state.apply_move(('END_CHAIN', None, None))
            self.selected_square = None
            self.end_chain_btn.config(state=tk.DISABLED)
            self.log(f"--- Human ended capture chain ---")
            self.update_ui()
            self.root.after(150, self.trigger_next_turn)

    # =================================================================
    # BOARD RENDERING & UI TELEMETRY
    # =================================================================

    def update_ui(self):
        self.canvas.delete("all")

        if self.state.phase == 1:
            self.phase_lbl.config(
                text=f"PHASE 1: TACTICAL DROP PHASE ({self.state.p1_to_place + self.state.p2_to_place} pieces left to place)",
                fg="#A3E635"
            )
        else:
            self.phase_lbl.config(
                text=f"PHASE 2: CUSTODIAL COMBAT (Draw Clock: {self.state.no_capture_moves}/{self.state.max_no_capture})",
                fg="#FF8A65"
            )

        p1_name = self.agents[P1][0]
        p2_name = self.agents[P2][0]
        self.p1_info_lbl.config(
            text=f"P1 Gold [{p1_name}]: {self.state.p1_pieces:2d} active | {self.state.p1_to_place:2d} reserve"
        )
        self.p2_info_lbl.config(
            text=f"P2 Teal [{p2_name}]: {self.state.p2_pieces:2d} active | {self.state.p2_to_place:2d} reserve"
        )

        valid_destinations = set()
        if self.selected_square is not None and self.state.phase == 2:
            for m in self.state.get_legal_moves():
                if m[0] == 'MOVE' and m[1] == self.selected_square:
                    valid_destinations.add(m[2])

        for r in range(5):
            for c in range(5):
                x1 = c * self.cell_size
                y1 = r * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                fill_col = self.col_sanctuary if (r, c) == CENTER else self.col_board
                if (r, c) == self.selected_square:
                    fill_col = "#A5D6A7"
                elif (r, c) in self.last_move_squares:
                    fill_col = "#FFE082"

                self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=fill_col, outline=self.col_grid, width=2
                )

                self.canvas.create_text(
                    x1 + 18, y1 + 14,
                    text=f"({r},{c})", font=("Consolas", 8), fill="#6D5843"
                )

                if (r, c) == CENTER:
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    self.canvas.create_oval(
                        cx - 28, cy - 28, cx + 28, cy + 28,
                        outline="#5C4938", width=2, dash=(4, 3)
                    )
                    self.canvas.create_text(
                        cx, y2 - 14,
                        text="SANCTUARY", font=("Georgia", 7, "bold"), fill="#4E3B29"
                    )

                if (r, c) in self.last_captured_squares:
                    self.canvas.create_rectangle(
                        x1 + 4, y1 + 4, x2 - 4, y2 - 4,
                        outline="#D32F2F", width=3, dash=(4, 2)
                    )

                if (r, c) in valid_destinations:
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    self.canvas.create_oval(
                        cx - 12, cy - 12, cx + 12, cy + 12,
                        fill="#2E7D32", outline="white", width=2
                    )

                piece = self.state.board[r][c]
                if piece != EMPTY:
                    pad = 18
                    p_fill = self.col_p1 if piece == P1 else self.col_p2
                    p_out = self.col_p1_outline if piece == P1 else self.col_p2_outline
                    self.canvas.create_oval(
                        x1 + pad + 3, y1 + pad + 3, x2 - pad + 3, y2 - pad + 3,
                        fill="#3E3227", outline=""
                    )
                    self.canvas.create_oval(
                        x1 + pad, y1 + pad, x2 - pad, y2 - pad,
                        fill=p_fill, outline=p_out, width=3
                    )
                    self.canvas.create_oval(
                        x1 + pad + 10, y1 + pad + 10, x2 - pad - 10, y2 - pad - 10,
                        outline=p_out, width=1
                    )

    def handle_game_over(self):
        self.is_running = False
        winner = self.state.get_winner()
        if winner == P1:
            msg = f"VICTORY: Player 1 (Gold - {self.agents[P1][0]}) Wins! ({self.state.p1_pieces} vs {self.state.p2_pieces})"
        elif winner == P2:
            msg = f"VICTORY: Player 2 (Teal - {self.agents[P2][0]}) Wins! ({self.state.p2_pieces} vs {self.state.p1_pieces})"
        else:
            msg = f"DRAW: Match ended with equal pieces ({self.state.p1_pieces} each)!"

        self.status_lbl.config(text=msg, fg="#FFD54F")
        self.log(f"\n==============================\n{msg}\n==============================")

    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)


if __name__ == "__main__":
    root = tk.Tk()
    app = SeggaGUI(root)
    root.mainloop()