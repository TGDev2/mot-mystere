from datetime import datetime
import tkinter as tk
from tkinter import messagebox

from categories import (
    MIN_WORD_POOL_SIZE,
    format_category_name,
    get_category_difficulty_breakdown,
    load_runtime_category_catalog,
)
from database import get_recent_players
from presentation import (
    GUIDED_SESSION_SUMMARY_SCREEN,
    LEADERBOARD_OVERLAY,
    MAIN_MENU_SCREEN,
    PLAYER_DASHBOARD_OVERLAY,
    PresentationRouter,
    PresentationShell,
    ROUND_SCREEN,
    ROUND_SUMMARY_SCREEN,
)
from presentation.screens import (
    GameRoundScreen,
    LeaderboardScreen,
    MainMenuScreen,
    PlayerDashboardScreen,
    RoundSummaryScreen,
)
from presentation.theme import APP_BG
from scoring import build_score_breakdown
from solo_game_service import (
    build_guided_objective,
    build_guided_recommendation,
    create_session_for_player,
    evaluate_guided_objective,
    get_progression_bundle,
    prepare_player,
    resolve_round,
)


class HangmanApp:
    def __init__(self):
        self.catalog = load_runtime_category_catalog()
        self.categories = dict(self.catalog.categories)
        self.category_availability = dict(self.catalog.category_availability)
        if not self.categories:
            raise RuntimeError("Aucune categorie exploitable n'est disponible.")

        self.root = tk.Tk()
        self.root.title("MotMystere")
        self.root.resizable(False, False)
        self.root.configure(bg=APP_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.player = None
        self.session = None
        self.guided_session = None
        self.timer_job = None
        self.letter_buttons = {}
        self.category_display_names = dict(self.catalog.display_names)
        self.category_labels = self._build_category_label_map()

        first_category = next(iter(self.categories))
        first_difficulty = self.category_availability[first_category][0]

        self.player_name_var = tk.StringVar()
        self.category_var = tk.StringVar(value=first_category)
        self.category_display_var = tk.StringVar(value=self._get_category_display_name(first_category))
        self.difficulty_var = tk.StringVar(value=first_difficulty)
        self.banner_var = tk.StringVar()
        self.word_var = tk.StringVar()
        self.tried_letters_var = tk.StringVar()
        self.attempts_var = tk.StringVar()
        self.timer_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.progress_var = tk.StringVar()
        self.score_hint_var = tk.StringVar()
        self.category_hint_var = tk.StringVar()
        self.round_hint_var = tk.StringVar()

        self.player_name_entry = None
        self.difficulty_menu = None
        self.primary_goal_snapshot = None

        self.ui = PresentationShell()
        self.main_menu_screen = MainMenuScreen()
        self.game_round_screen = GameRoundScreen()
        self.round_summary_screen = RoundSummaryScreen()
        self.player_dashboard_screen = PlayerDashboardScreen()
        self.leaderboard_screen = LeaderboardScreen()
        self.presentation_router = self._build_presentation_router()

        self.show_main_menu()

    def run(self):
        self.root.mainloop()

    def close(self):
        self.cancel_timer()
        self.root.destroy()

    def cancel_timer(self):
        if self.timer_job is not None:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None

    def clear_screen(self):
        self.cancel_timer()
        self.root.unbind("<Return>")
        self.root.unbind("<Key>")
        for widget in self.root.winfo_children():
            widget.destroy()
        self.player_name_entry = None
        self.difficulty_menu = None

    def _build_presentation_router(self):
        return PresentationRouter(
            screens={
                MAIN_MENU_SCREEN: lambda banner_message="": self.main_menu_screen.render(
                    self,
                    banner_message=banner_message,
                ),
                ROUND_SCREEN: lambda: self.game_round_screen.render(self),
                ROUND_SUMMARY_SCREEN: lambda **payload: self.round_summary_screen.render_round_summary(
                    self,
                    **payload,
                ),
                GUIDED_SESSION_SUMMARY_SCREEN: lambda: self.round_summary_screen.render_guided_session_summary(
                    self
                ),
            },
            overlays={
                PLAYER_DASHBOARD_OVERLAY: lambda player_id: self.player_dashboard_screen.render(
                    self,
                    player_id=player_id,
                ),
                LEADERBOARD_OVERLAY: lambda: self.leaderboard_screen.render(self),
            },
        )

    def _get_category_display_name(self, category_key):
        return self.category_display_names.get(
            category_key,
            format_category_name(category_key),
        )

    def _build_category_label_map(self):
        counts = {}
        for key in self.categories:
            label = self._get_category_display_name(key)
            counts[label] = counts.get(label, 0) + 1

        labels = {}
        for key in self.categories:
            label = self._get_category_display_name(key)
            if counts[label] > 1:
                label = f"{label} [{key}]"
            labels[label] = key
        return labels

    def _build_catalog_summary(self):
        local_packs = [
            pack
            for pack in self.catalog.pack_summaries
            if pack.origin == "local"
        ]
        active_local = sum(1 for pack in local_packs if pack.status == "active")
        disabled_local = sum(1 for pack in local_packs if pack.status == "disabled")
        invalid_local = sum(1 for pack in local_packs if pack.status == "invalid")
        if self.catalog.local_pack_dir is not None:
            example_manifest = self.catalog.local_pack_dir / "<nom_du_pack>" / "pack.json"
        else:
            example_manifest = "packs/<nom_du_pack>/pack.json"
        return (
            f"{len(self.categories)} categorie(s) jouables chargees. "
            f"Packs locaux : {active_local} actif(s), {disabled_local} desactive(s), {invalid_local} invalide(s). "
            f"Ajoutez vos packs dans {example_manifest}."
        )

    def _build_catalog_issue_lines(self, limit=3):
        visible_issues = list(self.catalog.issues)
        lines = [issue.message for issue in visible_issues[:limit]]
        remaining = max(0, len(visible_issues) - len(lines))
        if remaining:
            lines.append(f"{remaining} autre(s) alerte(s) catalogue a verifier.")
        return lines

    def _get_progression_bundle(self):
        if self.player is None:
            return None, None

        bundle = get_progression_bundle(self.player, self.category_availability)
        if bundle is None:
            return None, None

        return self._apply_progression_bundle(bundle)

    def _set_active_player(self, player):
        self.player = player
        self.player_name_var.set(player["name"])
        self.progress_var.set(self._build_player_summary(player))

    def _apply_progression_bundle(self, bundle, *, sync_recent_selection=False):
        if bundle is None:
            return None, None

        self._set_active_player(bundle["player"])
        dashboard = bundle["dashboard"]
        snapshot = bundle["snapshot"]
        self.primary_goal_snapshot = snapshot

        if sync_recent_selection:
            self._sync_selection_from_recent_game(self._get_latest_game(dashboard))

        return dashboard, snapshot

    def _get_latest_game(self, dashboard):
        recent_games = (dashboard or {}).get("recent_games") or ()
        return recent_games[0] if recent_games else None

    def _sync_selection_from_recent_game(self, recent_game):
        if not recent_game:
            return

        self._sync_selection_to(
            recent_game.get("category"),
            recent_game.get("difficulty"),
        )

    def _load_recent_players(self):
        return get_recent_players()

    def _select_recent_player(self, player_id):
        bundle = get_progression_bundle({"id": player_id}, self.category_availability)
        if bundle is None:
            messagebox.showerror("Profil", "Le profil demande est introuvable.")
            return

        self._apply_progression_bundle(bundle, sync_recent_selection=True)
        self.show_main_menu(banner_message=f"Profil recharge : {self.player['name']}.")

    def _sync_selection_from_goal(self, goal):
        if not goal:
            return

        self._sync_selection_to(goal.get("category"), goal.get("difficulty"))

    def _sync_selection_to(self, category, difficulty):
        if category in self.categories:
            self.category_var.set(category)
            self.category_display_var.set(self._get_category_display_name(category))

        self.refresh_difficulty_options()
        available_difficulties = self.get_available_difficulties(self.category_var.get())
        if difficulty in available_difficulties:
            self.difficulty_var.set(difficulty)
        elif available_difficulties:
            self.difficulty_var.set(available_difficulties[0])
        self.update_category_hint()

    def _build_guided_session_state(self, objective, dashboard, snapshot):
        objective_state = evaluate_guided_objective(
            objective,
            self.player,
            dashboard,
            snapshot,
        )
        recommendation = build_guided_recommendation(
            objective,
            self.player,
            dashboard,
            snapshot,
        )
        return {
            "objective": objective,
            "objective_state": objective_state,
            "initial_progress_text": objective_state["progress_text"],
            "rounds": [],
            "recommendation": recommendation,
            "status": "active",
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }

    def _start_guided_session(self, source):
        player = self._load_player_from_form()
        if player is None:
            return

        dashboard, snapshot = self._get_progression_bundle()
        objective = build_guided_objective(snapshot, source=source)
        if objective is None:
            messagebox.showinfo(
                "Session guidee",
                "Aucun objectif concret n'est disponible pour lancer une session guidee.",
            )
            return

        guided_session = self._build_guided_session_state(objective, dashboard, snapshot)
        recommendation = guided_session.get("recommendation")
        if recommendation is None or not recommendation.get("category") or not recommendation.get("difficulty"):
            messagebox.showinfo(
                "Session guidee",
                "La recommandation suivante n'est pas exploitable pour le moment.",
            )
            return

        self.guided_session = guided_session
        self._sync_selection_to(
            recommendation.get("category"),
            recommendation.get("difficulty"),
        )
        self._start_round(preserve_guided_session=True)

    def _continue_guided_session(self):
        if self.guided_session is None or self.guided_session.get("status") != "active":
            self.show_main_menu()
            return

        recommendation = self.guided_session.get("recommendation")
        if recommendation is None or not recommendation.get("category") or not recommendation.get("difficulty"):
            self.show_guided_session_summary()
            return

        self._sync_selection_to(
            recommendation.get("category"),
            recommendation.get("difficulty"),
        )
        self.replay_current_selection(preserve_guided_session=True)

    def _stop_guided_session_after_round(self):
        if self.guided_session is None:
            self.show_main_menu()
            return

        self.guided_session["status"] = "stopped"
        self.show_guided_session_summary()

    def stop_guided_session_from_game(self):
        self.guided_session = None
        self.session = None
        self.show_main_menu(banner_message="Session guidee arretee avant la fin de la manche.")

    def start_primary_goal(self):
        if self.player is not None and self.primary_goal_snapshot is None:
            _, self.primary_goal_snapshot = self._get_progression_bundle()

        if self.primary_goal_snapshot and self.primary_goal_snapshot.get("primary_goal"):
            self._sync_selection_from_goal(self.primary_goal_snapshot["primary_goal"])

        self.start_game()

    def start_featured_challenge(self):
        if self.player is not None and self.primary_goal_snapshot is None:
            _, self.primary_goal_snapshot = self._get_progression_bundle()

        if self.primary_goal_snapshot and self.primary_goal_snapshot.get("featured_challenge"):
            self._sync_selection_from_goal(self.primary_goal_snapshot["featured_challenge"])

        self.start_game()

    def start_guided_primary_goal_session(self):
        self._start_guided_session("primary_goal")

    def start_guided_featured_challenge_session(self):
        self._start_guided_session("featured_challenge")

    def start_last_selection(self):
        player = self.player
        dashboard = None

        if player is None:
            player = self._load_player_from_form(sync_recent_selection=True)
            if player is None:
                return
        else:
            dashboard, _ = self._get_progression_bundle()
            self._sync_selection_from_recent_game(self._get_latest_game(dashboard))

        if dashboard is None:
            dashboard, _ = self._get_progression_bundle()
        if self._get_latest_game(dashboard) is None:
            self.start_game()
            return

        self.start_game()

    def show_main_menu(self, banner_message=""):
        self.presentation_router.show_screen(
            MAIN_MENU_SCREEN,
            banner_message=banner_message,
        )

    def on_main_menu_return(self, _event):
        self.start_game()

    def on_category_selected(self, selected_display_name):
        if selected_display_name in self.category_labels:
            self.category_var.set(self.category_labels[selected_display_name])
        self.refresh_difficulty_options()
        self.update_category_hint()

    def on_difficulty_selected(self, _selected_difficulty):
        self.update_category_hint()

    def get_available_difficulties(self, category_key=None):
        key = category_key or self.category_var.get()
        return self.category_availability.get(key, tuple())

    def refresh_difficulty_options(self):
        available_difficulties = self.get_available_difficulties(self.category_var.get())
        if not available_difficulties:
            raise RuntimeError("La categorie selectionnee ne propose aucun niveau exploitable.")

        if self.difficulty_var.get() not in available_difficulties:
            self.difficulty_var.set(available_difficulties[0])

        if self.difficulty_menu is None:
            return

        menu = self.difficulty_menu["menu"]
        menu.delete(0, "end")
        for difficulty in available_difficulties:
            menu.add_command(
                label=difficulty,
                command=tk._setit(self.difficulty_var, difficulty, self.on_difficulty_selected),
            )

    def update_category_hint(self):
        selected_display_name = self.category_display_var.get()
        if selected_display_name in self.category_labels:
            self.category_var.set(self.category_labels[selected_display_name])

        breakdown = get_category_difficulty_breakdown(self.categories[self.category_var.get()])
        available_difficulties = self.get_available_difficulties(self.category_var.get())
        selected_difficulty = self.difficulty_var.get()
        total_words = sum(breakdown.values())
        selected_pool = breakdown.get(selected_difficulty, 0)
        available_text = ", ".join(available_difficulties)
        self.category_hint_var.set(
            f"{self._get_category_display_name(self.category_var.get())} propose {total_words} mots au total. "
            f"Le niveau {selected_difficulty} active un pool calibre de {selected_pool} mot(s). "
            f"Niveaux jouables : {available_text} "
            f"(minimum garanti : {MIN_WORD_POOL_SIZE}, pool solide vise : 15 mots par niveau)."
        )

    def _load_player_from_form(self, *, sync_recent_selection=False):
        try:
            player = prepare_player(self.player_name_var.get())
        except ValueError as exc:
            messagebox.showerror("Pseudo invalide", str(exc))
            return None

        bundle = get_progression_bundle(player, self.category_availability)
        if bundle is None:
            self._set_active_player(player)
            return player

        self._apply_progression_bundle(bundle, sync_recent_selection=sync_recent_selection)
        return self.player

    def open_player_dashboard(self):
        if self.player_name_var.get().strip():
            player = self._load_player_from_form(sync_recent_selection=True)
            if player is None:
                return
        elif self.player is None:
            messagebox.showinfo("Profil", "Saisissez un pseudo pour afficher un profil.")
            return
        else:
            player = self.player

        self.show_player_dashboard(player["id"])

    def _create_session_for_current_selection(self):
        category = self.category_var.get()
        difficulty = self.difficulty_var.get()
        return create_session_for_player(
            self.player["id"],
            self.categories,
            category,
            difficulty,
        )

    def _start_round(self, *, preserve_guided_session=False):
        if not preserve_guided_session:
            self.guided_session = None

        player = self._load_player_from_form()
        if player is None:
            return

        selected_display_name = self.category_display_var.get()
        if selected_display_name in self.category_labels:
            self.category_var.set(self.category_labels[selected_display_name])

        try:
            self.session = self._create_session_for_current_selection()
        except ValueError as exc:
            messagebox.showerror("Partie indisponible", str(exc))
            self.refresh_difficulty_options()
            self.update_category_hint()
            return

        self.show_game_screen()

    def start_game(self):
        self._start_round()

    def replay_current_selection(self, *, preserve_guided_session=False):
        if self.player is None:
            self.show_main_menu()
            return

        if not preserve_guided_session:
            self.guided_session = None

        try:
            self.session = self._create_session_for_current_selection()
        except ValueError as exc:
            self.show_main_menu(banner_message=str(exc))
            return

        self.show_game_screen()

    def show_game_screen(self):
        self.presentation_router.show_screen(ROUND_SCREEN)

    def on_game_keypress(self, event):
        if self.session is None or self.session.status != "in_progress":
            return

        focused_widget = self.root.focus_get()
        if focused_widget is not None and focused_widget.winfo_toplevel() is not self.root:
            return

        if event.keysym == "Escape":
            if self.guided_session is not None and self.guided_session.get("status") == "active":
                self.stop_guided_session_from_game()
            else:
                self.return_to_menu()
            return

        letter = str(event.char or "").strip().upper()
        if len(letter) == 1 and letter.isalpha():
            self.handle_letter(letter)

    def refresh_game_view(self):
        self.word_var.set(self.session.revealed_word)
        tried_letters = ", ".join(self.session.letters_tried) or "Aucune"
        self.tried_letters_var.set(f"Lettres proposees : {tried_letters}")
        self.attempts_var.set(str(self.session.attempts_left))
        self.timer_var.set(f"{self.session.time_remaining} s")

        potential_score = build_score_breakdown(
            self.session.difficulty,
            self.session.word_profile.length,
            self.session.attempts_left,
            self.session.time_remaining,
            word_complexity=self.session.word_complexity,
            time_limit=self.session.time_limit,
        )["total"]
        self.score_hint_var.set(f"{potential_score} pts")
        self.progress_var.set(self._build_player_summary(self.player))

    def schedule_timer(self):
        self.cancel_timer()
        self.timer_job = self.root.after(1000, self.on_timer_tick)

    def on_timer_tick(self):
        status = self.session.tick()
        self.refresh_game_view()
        if status == "in_progress":
            self.schedule_timer()
            return

        self.finish_round("time")

    def handle_letter(self, letter):
        result = self.session.guess(letter)
        if not result.was_valid:
            self.status_var.set("Veuillez choisir une lettre valide.")
            return

        if result.letter in self.letter_buttons:
            self.letter_buttons[result.letter].config(state=tk.DISABLED)

        if result.already_guessed:
            self.status_var.set(f"La lettre {result.letter} a deja ete proposee.")
        elif result.correct:
            self.status_var.set(f"Bonne reponse : {result.letter} est dans le mot.")
        else:
            self.status_var.set(f"{result.letter} n'est pas dans le mot.")

        self.refresh_game_view()

        if result.status == "won":
            self.finish_round("won")
        elif result.status == "lost":
            self.finish_round("attempts")

    def finish_round(self, reason):
        self.cancel_timer()
        for button in self.letter_buttons.values():
            button.config(state=tk.DISABLED)

        outcome = resolve_round(
            self.player,
            self.session,
            reason,
            self.category_availability,
        )
        self.player = outcome["player"]
        self.progress_var.set(self._build_player_summary(self.player))
        if outcome["progression_snapshot"] is not None:
            self.primary_goal_snapshot = outcome["progression_snapshot"]

        guided_progress = None
        guided_recommendation = None
        if self.guided_session is not None and self.guided_session.get("status") == "active":
            round_record = {
                "title": outcome["title"],
                "result_message": outcome["result_message"],
                "category": self.session.category,
                "difficulty": self.session.difficulty,
                "won": reason == "won",
                "end_reason": reason,
                "score_earned": outcome["score_earned"],
                "completed_goals": outcome["completed_goals"],
                "mastery_updates": outcome["mastery_updates"],
            }
            self.guided_session["rounds"].append(round_record)
            guided_progress = evaluate_guided_objective(
                self.guided_session["objective"],
                outcome["player"],
                outcome["dashboard"],
                outcome["progression_snapshot"],
            )
            guided_recommendation = build_guided_recommendation(
                self.guided_session["objective"],
                outcome["player"],
                outcome["dashboard"],
                outcome["progression_snapshot"],
            )
            self.guided_session["objective_state"] = guided_progress
            self.guided_session["recommendation"] = guided_recommendation
            if guided_progress is not None and guided_progress.get("completed"):
                self.guided_session["status"] = "completed"
                self.show_guided_session_summary()
                return

        self.show_round_summary(
            outcome["title"],
            outcome["result_message"],
            outcome["score_summary"],
            outcome["score_earned"],
            outcome["progression_snapshot"],
            outcome["completed_goals"],
            outcome["mastery_updates"],
            outcome["breakdown"],
            guided_progress=guided_progress,
            guided_recommendation=guided_recommendation,
        )

    def show_round_summary(
        self,
        title,
        result_message,
        score_summary,
        score_earned,
        progression_snapshot,
        completed_goals,
        mastery_updates,
        breakdown,
        *,
        guided_progress=None,
        guided_recommendation=None,
    ):
        self.presentation_router.show_screen(
            ROUND_SUMMARY_SCREEN,
            title=title,
            result_message=result_message,
            score_summary=score_summary,
            score_earned=score_earned,
            progression_snapshot=progression_snapshot,
            completed_goals=completed_goals,
            mastery_updates=mastery_updates,
            breakdown=breakdown,
            guided_progress=guided_progress,
            guided_recommendation=guided_recommendation,
        )

    def show_guided_session_summary(self):
        self.presentation_router.show_screen(GUIDED_SESSION_SUMMARY_SCREEN)

    def return_to_menu(self):
        banner_message = ""
        if self.guided_session is not None and self.guided_session.get("status") == "active":
            banner_message = "Session guidee arretee."
        self.guided_session = None
        self.session = None
        self.show_main_menu(banner_message=banner_message)

    def show_player_dashboard(self, player_id):
        self.presentation_router.open_overlay(
            PLAYER_DASHBOARD_OVERLAY,
            player_id=player_id,
        )

    def show_leaderboard(self):
        self.presentation_router.open_overlay(LEADERBOARD_OVERLAY)

    def _build_player_summary(self, player):
        return (
            f"Progression de {player['name']} : "
            f"{player['score_total']} pts au total, "
            f"meilleur score {player['best_score']}, "
            f"{player['games_won']} victoire(s) sur {player['games_played']} partie(s), "
            f"taux {player['win_rate']} %."
        )
