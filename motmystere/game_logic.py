import tkinter as tk

from .action_priority import build_surface_action_plan
from .backup_service import BackupService
from .catalog_service import CatalogService
from .presentation import (
    CATALOG_OVERLAY,
    EDITORIAL_COCKPIT_OVERLAY,
    DIFFICULTY_CALIBRATION_OVERLAY,
    GUIDED_SESSION_SUMMARY_SCREEN,
    LEADERBOARD_OVERLAY,
    MAIN_MENU_SCREEN,
    PLAYER_DASHBOARD_OVERLAY,
    PresentationRouter,
    PresentationShell,
    ROUND_SCREEN,
    ROUND_SUMMARY_SCREEN,
)
from .presentation.screens import (
    CatalogScreen,
    DifficultyCalibrationScreen,
    EditorialCockpitScreen,
    GameRoundScreen,
    LeaderboardScreen,
    MainMenuScreen,
    PlayerDashboardScreen,
    RoundSummaryScreen,
)
from .presentation.theme import APP_BG
from .workflows import (
    BackupWorkflow,
    CatalogWorkflow,
    GuidedSessionWorkflow,
    PlayerProgressionSupport,
    RoundLoopWorkflow,
    SelectionCatalogSupport,
    TkDialogPort,
    TkFileDialogPort,
    TkTimerPort,
)


class HangmanApp:
    def __init__(self):
        self.backup_service = BackupService()
        self.catalog_service = CatalogService()
        self.catalog_window = None
        self.catalog_import_preview_window = None
        self.catalog_import_preview = None
        self.catalog_import_preview_reopen_overlay = "catalog"
        self.catalog = None
        self.editorial_cockpit_window = None
        self.categories = {}
        self.category_availability = {}
        self.category_display_names = {}
        self.category_labels = {}

        self.root = tk.Tk()
        self.root.title("MotMystere")
        self.root.resizable(False, False)
        self.root.configure(bg=APP_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.dialog_port = TkDialogPort()
        self.file_dialog_port = TkFileDialogPort()
        self.timer_port = TkTimerPort(self.root)

        self.selection_support = SelectionCatalogSupport(self)
        self.player_progression_support = PlayerProgressionSupport(self, dialog_port=self.dialog_port)
        self.catalog_workflow = CatalogWorkflow(
            self,
            dialog_port=self.dialog_port,
            file_dialog_port=self.file_dialog_port,
        )
        self.backup_workflow = BackupWorkflow(
            self,
            dialog_port=self.dialog_port,
            file_dialog_port=self.file_dialog_port,
        )
        self.guided_session_workflow = GuidedSessionWorkflow(self, dialog_port=self.dialog_port)
        self.round_loop_workflow = RoundLoopWorkflow(
            self,
            dialog_port=self.dialog_port,
            timer_port=self.timer_port,
        )
        self._set_catalog(self.catalog_service.load_catalog())

        self.player = None
        self.session = None
        self.guided_session = None
        self.timer_job = None
        self.letter_buttons = {}

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
        self.progression_snapshot = None
        self.selected_exploration_mount = None
        self.round_exploration_before = None

        self.ui = PresentationShell()
        self.main_menu_screen = MainMenuScreen()
        self.game_round_screen = GameRoundScreen()
        self.round_summary_screen = RoundSummaryScreen()
        self.player_dashboard_screen = PlayerDashboardScreen()
        self.leaderboard_screen = LeaderboardScreen()
        self.catalog_screen = CatalogScreen()
        self.difficulty_calibration_screen = DifficultyCalibrationScreen()
        self.editorial_cockpit_screen = EditorialCockpitScreen()
        self.presentation_router = self._build_presentation_router()

        self.show_main_menu()

    def run(self):
        self.root.mainloop()

    def close(self):
        self.cancel_timer()
        self.close_catalog_pack_preview()
        self.root.destroy()

    def cancel_timer(self):
        if getattr(self, "timer_job", None) is not None:
            timer_port = getattr(self, "timer_port", None)
            if timer_port is not None:
                timer_port.cancel(self.timer_job)
            else:
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
        self.selected_exploration_mount = None

    def _ensure_selection_support(self):
        if getattr(self, "selection_support", None) is None:
            self.selection_support = SelectionCatalogSupport(self)
        return self.selection_support

    def _ensure_player_progression_support(self):
        if getattr(self, "player_progression_support", None) is None:
            self.player_progression_support = PlayerProgressionSupport(
                self,
                dialog_port=getattr(self, "dialog_port", None),
            )
        return self.player_progression_support

    def _ensure_catalog_workflow(self):
        if getattr(self, "catalog_workflow", None) is None:
            self.catalog_workflow = CatalogWorkflow(
                self,
                dialog_port=getattr(self, "dialog_port", None),
                file_dialog_port=getattr(self, "file_dialog_port", None),
            )
        return self.catalog_workflow

    def _ensure_backup_workflow(self):
        if getattr(self, "backup_workflow", None) is None:
            self.backup_workflow = BackupWorkflow(
                self,
                dialog_port=getattr(self, "dialog_port", None),
                file_dialog_port=getattr(self, "file_dialog_port", None),
            )
        return self.backup_workflow

    def _ensure_guided_session_workflow(self):
        if getattr(self, "guided_session_workflow", None) is None:
            self.guided_session_workflow = GuidedSessionWorkflow(
                self,
                dialog_port=getattr(self, "dialog_port", None),
            )
        return self.guided_session_workflow

    def _ensure_round_loop_workflow(self):
        if getattr(self, "round_loop_workflow", None) is None:
            self.round_loop_workflow = RoundLoopWorkflow(
                self,
                dialog_port=getattr(self, "dialog_port", None),
                timer_port=getattr(self, "timer_port", None),
            )
        return self.round_loop_workflow

    def _set_catalog(self, catalog):
        self._ensure_selection_support().set_catalog(catalog)

    def _merge_banner_messages(self, *messages):
        return self._ensure_selection_support().merge_banner_messages(*messages)

    def _sync_selection_after_catalog_reload(self, previous_category, previous_difficulty):
        return self._ensure_selection_support().sync_selection_after_catalog_reload(
            previous_category,
            previous_difficulty,
        )

    def _reload_catalog_state(
        self,
        catalog,
        *,
        banner_message="",
        reopen_catalog=False,
        reopen_editorial=False,
    ):
        return self._ensure_catalog_workflow().reload_catalog_state(
            catalog,
            banner_message=banner_message,
            reopen_catalog=reopen_catalog,
            reopen_editorial=reopen_editorial,
        )

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
                CATALOG_OVERLAY: lambda banner_message="": self.catalog_screen.render(
                    self,
                    banner_message=banner_message,
                ),
                EDITORIAL_COCKPIT_OVERLAY: lambda banner_message="": self.editorial_cockpit_screen.render(
                    self,
                    banner_message=banner_message,
                ),
                DIFFICULTY_CALIBRATION_OVERLAY: lambda: self.difficulty_calibration_screen.render(self),
            },
        )

    def _get_category_display_name(self, category_key):
        return self._ensure_selection_support().get_category_display_name(category_key)

    def _build_category_label_map(self):
        return self._ensure_selection_support().build_category_label_map()

    def _build_catalog_summary(self):
        return self._ensure_catalog_workflow().build_catalog_summary()

    def _build_catalog_issue_lines(self, limit=3):
        return self._ensure_catalog_workflow().build_catalog_issue_lines(limit=limit)

    def _build_surface_action_plan(self, dashboard, snapshot, *, surface, round_result=None):
        return build_surface_action_plan(
            dashboard,
            snapshot,
            surface=surface,
            round_result=round_result,
        )

    def _get_action_callback(self, callback_id):
        callback_map = {
            "start_game": self.start_game,
            "start_last_selection": self.start_last_selection,
            "start_personalized_recommendation": self.start_personalized_recommendation,
            "start_review_failed_words": self.start_review_failed_words,
            "start_review_weak_pair": self.start_review_weak_pair,
            "start_guided_primary_goal_session": self.start_guided_primary_goal_session,
            "start_guided_featured_challenge_session": self.start_guided_featured_challenge_session,
            "replay_current_selection": self.replay_current_selection,
            "return_to_menu": self.return_to_menu,
            "open_player_dashboard": self.open_player_dashboard,
            "show_leaderboard": self.show_leaderboard,
            "show_editorial_cockpit_overlay": self.show_editorial_cockpit_overlay,
            "export_local_data": self.export_local_data,
            "import_local_data": self.import_local_data,
            "continue_guided_session": self._continue_guided_session,
            "stop_guided_session_after_round": self._stop_guided_session_after_round,
        }
        return callback_map[callback_id]

    def show_catalog_overlay(self, banner_message=""):
        self.presentation_router.open_overlay(
            CATALOG_OVERLAY,
            banner_message=banner_message,
        )

    def get_editorial_cockpit_bundle(self):
        return self._ensure_catalog_workflow().get_editorial_cockpit_bundle()

    def show_editorial_cockpit_overlay(self, banner_message=""):
        self.presentation_router.open_overlay(
            EDITORIAL_COCKPIT_OVERLAY,
            banner_message=banner_message,
        )

    def get_difficulty_calibration_bundle(self):
        return self._ensure_catalog_workflow().get_difficulty_calibration_bundle()

    def show_difficulty_calibration_overlay(self):
        self.presentation_router.open_overlay(DIFFICULTY_CALIBRATION_OVERLAY)

    def refresh_catalog_overlay(self):
        self._ensure_catalog_workflow().refresh_catalog_overlay()

    def refresh_editorial_cockpit_overlay(self):
        self._ensure_catalog_workflow().refresh_editorial_cockpit_overlay()

    def toggle_catalog_pack(self, pack_id, enabled, *, reopen_overlay="catalog"):
        self._ensure_catalog_workflow().toggle_catalog_pack(
            pack_id,
            enabled,
            reopen_overlay=reopen_overlay,
        )

    def _get_official_pack_library(self):
        return self._ensure_catalog_workflow().get_official_pack_library()

    def preview_catalog_pack_zip(self):
        self._ensure_catalog_workflow().preview_catalog_pack_zip()

    def preview_catalog_pack_directory(self):
        self._ensure_catalog_workflow().preview_catalog_pack_directory()

    def preview_official_catalog_pack(self, archive_path, *, reopen_overlay="catalog"):
        self._ensure_catalog_workflow().preview_official_catalog_pack(
            archive_path,
            reopen_overlay=reopen_overlay,
        )

    def _preview_catalog_pack_source(self, source_path, *, reopen_overlay="catalog"):
        self._ensure_catalog_workflow().preview_catalog_pack_source(
            source_path,
            reopen_overlay=reopen_overlay,
        )

    def close_catalog_pack_preview(self):
        self._ensure_catalog_workflow().close_catalog_pack_preview()

    def _build_pack_import_status_message(self, preview, pack_summary):
        return self._ensure_catalog_workflow().build_pack_import_status_message(
            preview,
            pack_summary,
        )

    def confirm_catalog_pack_import(self, enabled):
        self._ensure_catalog_workflow().confirm_catalog_pack_import(enabled)

    def import_catalog_pack(self):
        self._ensure_catalog_workflow().import_catalog_pack()

    def export_local_data(self):
        self._ensure_backup_workflow().export_local_data()

    def import_local_data(self):
        self._ensure_backup_workflow().import_local_data()

    def _clear_active_player_state(self):
        self._ensure_player_progression_support().clear_active_player_state()

    def _apply_restored_environment(self, summary):
        self._ensure_backup_workflow().apply_restored_environment(summary)

    def _get_progression_bundle(self):
        return self._ensure_player_progression_support().get_progression_bundle()

    def _set_active_player(self, player):
        self._ensure_player_progression_support().set_active_player(player)

    def _apply_progression_bundle(self, bundle, *, sync_recent_selection=False):
        return self._ensure_player_progression_support().apply_progression_bundle(
            bundle,
            sync_recent_selection=sync_recent_selection,
        )

    def _get_latest_game(self, dashboard):
        return self._ensure_player_progression_support().get_latest_game(dashboard)

    def _sync_selection_from_recent_game(self, recent_game):
        self._ensure_player_progression_support().sync_selection_from_recent_game(recent_game)

    def _load_recent_players(self):
        return self._ensure_player_progression_support().load_recent_players()

    def _select_recent_player(self, player_id):
        self._ensure_player_progression_support().select_recent_player(player_id)

    def _sync_selection_from_goal(self, goal):
        self._ensure_selection_support().sync_selection_from_goal(goal)

    def _sync_selection_to(self, category, difficulty):
        self._ensure_selection_support().sync_selection_to(category, difficulty)

    def _build_catalog_exploration_snapshot(
        self,
        *,
        selected_category=None,
        selected_difficulty=None,
    ):
        return self._ensure_selection_support().build_catalog_exploration_snapshot(
            selected_category=selected_category,
            selected_difficulty=selected_difficulty,
        )

    def _render_selected_exploration_state(self):
        self._ensure_selection_support().render_selected_exploration_state()

    def _build_guided_session_state(self, objective, dashboard, snapshot, *, source):
        return self._ensure_guided_session_workflow().build_guided_session_state(
            objective,
            dashboard,
            snapshot,
            source=source,
        )

    def _start_guided_session(self, source):
        self._ensure_guided_session_workflow().start_guided_session(source)

    def _start_review_session(self, review_key):
        self._ensure_guided_session_workflow().start_review_session(review_key)

    def _continue_guided_session(self):
        self._ensure_guided_session_workflow().continue_guided_session()

    def _stop_guided_session_after_round(self):
        self._ensure_guided_session_workflow().stop_guided_session_after_round()

    def stop_guided_session_from_game(self):
        self._ensure_guided_session_workflow().stop_guided_session_from_game()

    def start_primary_goal(self):
        self._ensure_guided_session_workflow().start_primary_goal()

    def start_featured_challenge(self):
        self._ensure_guided_session_workflow().start_featured_challenge()

    def start_personalized_recommendation(self):
        self._ensure_guided_session_workflow().start_personalized_recommendation()

    def start_guided_primary_goal_session(self):
        self._start_guided_session("primary_goal")

    def start_guided_featured_challenge_session(self):
        self._start_guided_session("featured_challenge")

    def start_review_failed_words(self):
        self._start_review_session("failed_words")

    def start_review_weak_pair(self):
        self._start_review_session("weak_pair")

    def start_last_selection(self):
        self._ensure_round_loop_workflow().start_last_selection()

    def show_main_menu(self, banner_message=""):
        self.presentation_router.show_screen(
            MAIN_MENU_SCREEN,
            banner_message=banner_message,
        )

    def on_main_menu_return(self, _event):
        dashboard, snapshot = self._get_progression_bundle() if self.player is not None else (None, None)
        action_plan = self._build_surface_action_plan(
            dashboard,
            snapshot,
            surface="home",
        )
        primary_action = action_plan.get("primary_action") if action_plan is not None else None
        callback_id = primary_action.get("callback_id") if primary_action is not None else "start_game"
        self._get_action_callback(callback_id)()

    def on_category_selected(self, selected_display_name):
        if selected_display_name in self.category_labels:
            self.category_var.set(self.category_labels[selected_display_name])
        self.refresh_difficulty_options()
        self.update_category_hint()

    def on_difficulty_selected(self, _selected_difficulty):
        self.update_category_hint()

    def get_available_difficulties(self, category_key=None):
        return self._ensure_selection_support().get_available_difficulties(category_key)

    def refresh_difficulty_options(self):
        self._ensure_selection_support().refresh_difficulty_options()

    def update_category_hint(self):
        self._ensure_selection_support().update_category_hint()

    def _load_player_from_form(self, *, sync_recent_selection=False):
        return self._ensure_player_progression_support().load_player_from_form(
            sync_recent_selection=sync_recent_selection,
        )

    def open_player_dashboard(self):
        if self.player_name_var.get().strip():
            player = self._load_player_from_form(sync_recent_selection=True)
            if player is None:
                return
        elif self.player is None:
            self.dialog_port.show_info("Profil", "Saisissez un pseudo pour afficher un profil.")
            return
        else:
            player = self.player

        self.show_player_dashboard(player["id"])

    def _create_session_for_current_selection(self):
        return self._ensure_round_loop_workflow().create_session_for_current_selection()

    def _start_round(self, *, preserve_guided_session=False, review_mode=False):
        self._ensure_round_loop_workflow().start_round(
            preserve_guided_session=preserve_guided_session,
            review_mode=review_mode,
        )

    def start_game(self):
        self._ensure_round_loop_workflow().start_game()

    def replay_current_selection(self, *, preserve_guided_session=False):
        self._ensure_round_loop_workflow().replay_current_selection(
            preserve_guided_session=preserve_guided_session,
        )

    def show_game_screen(self):
        self.presentation_router.show_screen(ROUND_SCREEN)

    def on_game_keypress(self, event):
        self._ensure_round_loop_workflow().on_game_keypress(event)

    def refresh_game_view(self):
        self._ensure_round_loop_workflow().refresh_game_view()

    def schedule_timer(self):
        self._ensure_round_loop_workflow().schedule_timer()

    def on_timer_tick(self):
        self._ensure_round_loop_workflow().on_timer_tick()

    def handle_letter(self, letter):
        self._ensure_round_loop_workflow().handle_letter(letter)

    def finish_round(self, reason):
        self._ensure_round_loop_workflow().finish_round(reason)

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
        catalog_rotation=None,
        guided_progress=None,
        guided_recommendation=None,
        surface_action_plan=None,
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
            catalog_rotation=catalog_rotation,
            guided_progress=guided_progress,
            guided_recommendation=guided_recommendation,
            surface_action_plan=surface_action_plan,
        )

    def show_guided_session_summary(self):
        self.presentation_router.show_screen(GUIDED_SESSION_SUMMARY_SCREEN)

    def return_to_menu(self):
        self._ensure_round_loop_workflow().return_to_menu()

    def show_player_dashboard(self, player_id):
        self.presentation_router.open_overlay(
            PLAYER_DASHBOARD_OVERLAY,
            player_id=player_id,
        )

    def show_leaderboard(self):
        self.presentation_router.open_overlay(LEADERBOARD_OVERLAY)

    def _build_player_summary(self, player):
        return self._ensure_player_progression_support().build_player_summary(player)
