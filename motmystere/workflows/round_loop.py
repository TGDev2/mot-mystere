import tkinter as tk

from ..scoring import build_score_breakdown
from ..solo_game_service import create_review_session, create_session_for_player, resolve_round
from .ports import NullDialogPort, NullTimerPort


class RoundLoopWorkflow:
    def __init__(self, app, *, dialog_port=None, timer_port=None):
        self.app = app
        self.dialog_port = dialog_port or getattr(app, "dialog_port", None) or NullDialogPort()
        self.timer_port = timer_port or getattr(app, "timer_port", None) or NullTimerPort()

    def create_session_for_current_selection(self):
        category = self.app.category_var.get()
        difficulty = self.app.difficulty_var.get()
        return create_session_for_player(
            self.app.player["id"],
            self.app.categories,
            category,
            difficulty,
        )

    def start_round(self, *, preserve_guided_session=False, review_mode=False):
        if not preserve_guided_session:
            self.app.guided_session = None

        player = self.app._load_player_from_form()
        if player is None:
            return

        selected_display_name = self.app.category_display_var.get()
        if selected_display_name in self.app.category_labels:
            self.app.category_var.set(self.app.category_labels[selected_display_name])

        self.app.round_exploration_before = (
            None if review_mode else self.app._build_catalog_exploration_snapshot()["selected_state"]
        )
        try:
            if review_mode:
                self.app.session = create_review_session(
                    self.app.guided_session,
                    self.app.categories,
                )
            else:
                self.app.session = self.create_session_for_current_selection()
        except ValueError as exc:
            self.app.round_exploration_before = None
            self.dialog_port.show_error("Partie indisponible", str(exc))
            self.app.refresh_difficulty_options()
            self.app.update_category_hint()
            return

        self.app.show_game_screen()

    def start_game(self):
        self.start_round()

    def replay_current_selection(self, *, preserve_guided_session=False):
        if self.app.player is None:
            self.app.show_main_menu()
            return

        if not preserve_guided_session:
            self.app.guided_session = None

        try:
            self.app.session = self.create_session_for_current_selection()
        except ValueError as exc:
            self.app.show_main_menu(banner_message=str(exc))
            return

        self.app.show_game_screen()

    def start_last_selection(self):
        player = self.app.player
        dashboard = None

        if player is None:
            player = self.app._load_player_from_form(sync_recent_selection=True)
            if player is None:
                return
        else:
            dashboard, _ = self.app._get_progression_bundle()
            self.app._sync_selection_from_recent_game(self.app._get_latest_game(dashboard))

        if dashboard is None:
            dashboard, _ = self.app._get_progression_bundle()
        if self.app._get_latest_game(dashboard) is None:
            self.app.start_game()
            return

        self.app.start_game()

    def on_game_keypress(self, event):
        if self.app.session is None or self.app.session.status != "in_progress":
            return

        focused_widget = self.app.root.focus_get()
        if focused_widget is not None and focused_widget.winfo_toplevel() is not self.app.root:
            return

        if event.keysym == "Escape":
            if self.app.guided_session is not None and self.app.guided_session.get("status") == "active":
                self.app.stop_guided_session_from_game()
            else:
                self.app.return_to_menu()
            return

        letter = str(event.char or "").strip().upper()
        if len(letter) == 1 and letter.isalpha():
            self.handle_letter(letter)

    def refresh_game_view(self):
        self.app.word_var.set(self.app.session.revealed_word)
        tried_letters = ", ".join(self.app.session.letters_tried) or "Aucune"
        self.app.tried_letters_var.set(f"Lettres proposees : {tried_letters}")
        self.app.attempts_var.set(str(self.app.session.attempts_left))
        self.app.timer_var.set(f"{self.app.session.time_remaining} s")

        potential_score = build_score_breakdown(
            self.app.session.difficulty,
            self.app.session.word_profile.length,
            self.app.session.attempts_left,
            self.app.session.time_remaining,
            word_complexity=self.app.session.word_complexity,
            time_limit=self.app.session.time_limit,
        )["total"]
        self.app.score_hint_var.set(f"{potential_score} pts")
        self.app.progress_var.set(self.app._build_player_summary(self.app.player))

    def schedule_timer(self):
        self.app.cancel_timer()
        self.app.timer_job = self.timer_port.schedule(1000, self.app.on_timer_tick)

    def on_timer_tick(self):
        status = self.app.session.tick()
        self.refresh_game_view()
        if status == "in_progress":
            self.schedule_timer()
            return

        self.finish_round("time")

    def handle_letter(self, letter):
        result = self.app.session.guess(letter)
        if not result.was_valid:
            self.app.status_var.set("Veuillez choisir une lettre valide.")
            return

        if result.letter in self.app.letter_buttons:
            self.app.letter_buttons[result.letter].config(state=tk.DISABLED)

        if result.already_guessed:
            self.app.status_var.set(f"La lettre {result.letter} a deja ete proposee.")
        elif result.correct:
            self.app.status_var.set(f"Bonne reponse : {result.letter} est dans le mot.")
        else:
            self.app.status_var.set(f"{result.letter} n'est pas dans le mot.")

        self.refresh_game_view()

        if result.status == "won":
            self.finish_round("won")
        elif result.status == "lost":
            self.finish_round("attempts")

    def finish_round(self, reason):
        self.app.cancel_timer()
        for button in self.app.letter_buttons.values():
            button.config(state=tk.DISABLED)

        outcome = resolve_round(
            self.app.player,
            self.app.session,
            reason,
            self.app.category_availability,
        )
        rotation_before = self.app.round_exploration_before
        rotation_after = None
        if rotation_before is not None:
            rotation_after = self.app._build_catalog_exploration_snapshot(
                selected_category=self.app.session.category,
                selected_difficulty=self.app.session.difficulty,
            )["selected_state"]
        self.app.round_exploration_before = None
        self.app.player = outcome["player"]
        self.app.progress_var.set(self.app._build_player_summary(self.app.player))
        if outcome["progression_snapshot"] is not None:
            self.app.progression_snapshot = outcome["progression_snapshot"]

        guided_payload = self.app._ensure_guided_session_workflow().handle_round_outcome(
            reason=reason,
            outcome=outcome,
        )
        if guided_payload["completed"]:
            return

        surface_action_plan = self.app._build_surface_action_plan(
            outcome["dashboard"],
            outcome["progression_snapshot"],
            surface="round_summary",
            round_result=reason,
        )

        self.app.show_round_summary(
            outcome["title"],
            outcome["result_message"],
            outcome["score_summary"],
            outcome["score_earned"],
            outcome["progression_snapshot"],
            outcome["completed_goals"],
            outcome["mastery_updates"],
            outcome["breakdown"],
            catalog_rotation=(
                {
                    "before": rotation_before,
                    "after": rotation_after,
                }
                if rotation_before is not None
                else None
            ),
            guided_progress=guided_payload["guided_progress"],
            guided_recommendation=guided_payload["guided_recommendation"],
            surface_action_plan=surface_action_plan,
        )

    def return_to_menu(self):
        banner_message = ""
        if self.app.guided_session is not None and self.app.guided_session.get("status") == "active":
            banner_message = f"{self.app.guided_session.get('mode_label', 'Session active')} arretee."
        self.app.guided_session = None
        self.app.session = None
        self.app.show_main_menu(banner_message=banner_message)
