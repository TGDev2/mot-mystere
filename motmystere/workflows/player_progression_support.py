from ..database import get_recent_players
from ..solo_game_service import get_progression_bundle, prepare_player
from .ports import NullDialogPort


class PlayerProgressionSupport:
    def __init__(self, app, *, dialog_port=None):
        self.app = app
        self.dialog_port = dialog_port or getattr(app, "dialog_port", None) or NullDialogPort()

    def get_progression_bundle(self):
        if self.app.player is None:
            return None, None

        bundle = get_progression_bundle(self.app.player, self.app.category_availability)
        if bundle is None:
            return None, None

        return self.apply_progression_bundle(bundle)

    def set_active_player(self, player):
        self.app.player = player
        self.app.player_name_var.set(player["name"])
        self.app.progress_var.set(self.build_player_summary(player))

    def apply_progression_bundle(self, bundle, *, sync_recent_selection=False):
        if bundle is None:
            return None, None

        self.set_active_player(bundle["player"])
        dashboard = bundle["dashboard"]
        snapshot = bundle["snapshot"]
        self.app.progression_snapshot = snapshot

        if sync_recent_selection:
            self.sync_selection_from_recent_game(self.get_latest_game(dashboard))

        return dashboard, snapshot

    def get_latest_game(self, dashboard):
        recent_games = (dashboard or {}).get("recent_games") or ()
        return recent_games[0] if recent_games else None

    def sync_selection_from_recent_game(self, recent_game):
        if not recent_game:
            return

        self.app._sync_selection_to(
            recent_game.get("category"),
            recent_game.get("difficulty"),
        )

    def load_recent_players(self):
        return get_recent_players()

    def select_recent_player(self, player_id):
        bundle = get_progression_bundle({"id": player_id}, self.app.category_availability)
        if bundle is None:
            self.dialog_port.show_error("Profil", "Le profil demande est introuvable.")
            return

        self.apply_progression_bundle(bundle, sync_recent_selection=True)
        self.app.show_main_menu(banner_message=f"Profil recharge : {self.app.player['name']}.")

    def clear_active_player_state(self):
        self.app.player = None
        self.app.player_name_var.set("")
        self.app.progress_var.set("")
        self.app.round_exploration_before = None

    def load_player_from_form(self, *, sync_recent_selection=False):
        try:
            player = prepare_player(self.app.player_name_var.get())
        except ValueError as exc:
            self.dialog_port.show_error("Pseudo invalide", str(exc))
            return None

        bundle = get_progression_bundle(player, self.app.category_availability)
        if bundle is None:
            self.set_active_player(player)
            return player

        self.apply_progression_bundle(bundle, sync_recent_selection=sync_recent_selection)
        return self.app.player

    def build_player_summary(self, player):
        return (
            f"Progression de {player['name']} : "
            f"{player['score_total']} pts au total, "
            f"meilleur score {player['best_score']}, "
            f"{player['games_won']} victoire(s) sur {player['games_played']} partie(s), "
            f"taux {player['win_rate']} %."
        )
