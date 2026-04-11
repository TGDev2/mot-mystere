from pathlib import Path

from ..backup_service import BackupServiceError
from ..solo_game_service import get_progression_bundle
from .ports import NullDialogPort, NullFileDialogPort


class BackupWorkflow:
    def __init__(self, app, *, dialog_port=None, file_dialog_port=None):
        self.app = app
        self.dialog_port = dialog_port or getattr(app, "dialog_port", None) or NullDialogPort()
        self.file_dialog_port = file_dialog_port or getattr(app, "file_dialog_port", None) or NullFileDialogPort()

    def export_local_data(self):
        suggested_path = self.app.backup_service.build_backup_archive_path()
        selected_path = self.file_dialog_port.ask_save_as_filename(
            parent=self.app.root,
            title="Sauvegarder mes donnees",
            initialdir=str(suggested_path.parent),
            initialfile=suggested_path.name,
            defaultextension=".zip",
            filetypes=[("Archives ZIP", "*.zip")],
        )
        if not selected_path:
            return

        try:
            summary = self.app.backup_service.export_archive(selected_path)
        except BackupServiceError as exc:
            self.dialog_port.show_error("Sauvegarde", str(exc))
            return

        parts = [f"Sauvegarde exportee : {Path(summary['archive_path']).name}."]
        if summary["includes"].get("packs"):
            parts.append("Les packs locaux sont inclus.")
        if summary["includes"].get("catalog_state"):
            parts.append("L'etat du catalogue est inclus.")
        self.app.show_main_menu(banner_message=" ".join(parts))

    def import_local_data(self):
        selected_path = self.file_dialog_port.ask_open_filename(
            parent=self.app.root,
            title="Restaurer une sauvegarde",
            filetypes=[("Archives ZIP", "*.zip"), ("Tous les fichiers", "*.*")],
        )
        if not selected_path:
            return

        rescue_backup_path = None
        if self.app.backup_service.has_managed_data():
            rescue_backup_path = self.app.backup_service.build_backup_archive_path(
                prefix="motmystere_pre_restore"
            )
            confirmed = self.dialog_port.ask_yes_no(
                "Restaurer une sauvegarde",
                (
                    "Cette restauration remplacera completement la base locale, l'etat du catalogue "
                    "et les packs locaux actuels. "
                    f"Une sauvegarde de secours sera creee avant remplacement dans : {rescue_backup_path}"
                ),
            )
            if not confirmed:
                return

        try:
            summary = self.app.backup_service.import_archive(
                selected_path,
                backup_path=rescue_backup_path,
            )
        except BackupServiceError as exc:
            self.dialog_port.show_error("Restauration", str(exc))
            return

        self.apply_restored_environment(summary)

    def apply_restored_environment(self, summary):
        self.app.cancel_timer()
        self.app.session = None
        self.app.guided_session = None
        self.app.progression_snapshot = None
        self.app.round_exploration_before = None
        self.app.close_catalog_pack_preview()
        if self.app.catalog_window is not None and self.app.catalog_window.winfo_exists():
            self.app.catalog_window.destroy()
        self.app.catalog_window = None

        previous_category = self.app.category_var.get()
        previous_difficulty = self.app.difficulty_var.get()
        self.app._set_catalog(self.app.catalog_service.load_catalog())
        selection_message = self.app._sync_selection_after_catalog_reload(
            previous_category,
            previous_difficulty,
        )

        restored_player_name = None
        recent_players = self.app._load_recent_players()
        if recent_players:
            bundle = get_progression_bundle(
                {"id": recent_players[0]["id"]},
                self.app.category_availability,
            )
            if bundle is not None:
                self.app._apply_progression_bundle(bundle, sync_recent_selection=True)
                restored_player_name = bundle["player"]["name"]
            else:
                self.app._clear_active_player_state()
        else:
            self.app._clear_active_player_state()

        messages = ["Sauvegarde restauree."]
        if summary.get("backup_path"):
            messages.append(
                f"Sauvegarde de secours creee : {Path(summary['backup_path']).name}."
            )
        if restored_player_name:
            messages.append(f"Profil recharge : {restored_player_name}.")
        messages.append(selection_message)
        self.app.show_main_menu(
            banner_message=self.app._merge_banner_messages(*messages),
        )
