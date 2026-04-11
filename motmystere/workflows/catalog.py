from ..catalog_service import CatalogServiceError
from ..difficulty_calibration import get_difficulty_calibration_bundle
from ..editorial_cockpit import get_editorial_cockpit_bundle
from .ports import NullDialogPort, NullFileDialogPort


class CatalogWorkflow:
    def __init__(self, app, *, dialog_port=None, file_dialog_port=None):
        self.app = app
        self.dialog_port = dialog_port or getattr(app, "dialog_port", None) or NullDialogPort()
        self.file_dialog_port = file_dialog_port or getattr(app, "file_dialog_port", None) or NullFileDialogPort()

    def reload_catalog_state(
        self,
        catalog,
        *,
        banner_message="",
        reopen_catalog=False,
        reopen_editorial=False,
    ):
        previous_category = self.app.category_var.get()
        previous_difficulty = self.app.difficulty_var.get()

        self.app._set_catalog(catalog)
        selection_message = self.app._sync_selection_after_catalog_reload(
            previous_category,
            previous_difficulty,
        )
        combined_message = self.app._merge_banner_messages(banner_message, selection_message)

        self.app.show_main_menu(banner_message=combined_message)
        if reopen_catalog:
            self.app.show_catalog_overlay(banner_message=combined_message)
        if reopen_editorial:
            self.app.show_editorial_cockpit_overlay(banner_message=combined_message)

        return combined_message

    def build_catalog_summary(self):
        local_packs = [
            pack
            for pack in self.app.catalog.pack_summaries
            if pack.origin == "local"
        ]
        active_local = sum(1 for pack in local_packs if pack.status == "active")
        disabled_local = sum(1 for pack in local_packs if pack.status == "disabled")
        invalid_local = sum(1 for pack in local_packs if pack.status == "invalid")
        if self.app.catalog.local_pack_dir is not None:
            example_manifest = self.app.catalog.local_pack_dir / "<nom_du_pack>" / "pack.json"
        else:
            example_manifest = "packs/<nom_du_pack>/pack.json"
        return (
            f"{len(self.app.categories)} categorie(s) jouables chargees. "
            f"Packs locaux : {active_local} actif(s), {disabled_local} desactive(s), {invalid_local} invalide(s). "
            "Ouvrez le cockpit editorial pour prioriser enrichissements, recalibrages et activations, puis "
            f"utilisez au besoin le dossier expert {example_manifest}."
        )

    def build_catalog_issue_lines(self, limit=3):
        visible_issues = list(self.app.catalog.issues)
        lines = [issue.message for issue in visible_issues[:limit]]
        remaining = max(0, len(visible_issues) - len(lines))
        if remaining:
            lines.append(f"{remaining} autre(s) alerte(s) catalogue a verifier.")
        return lines

    def get_editorial_cockpit_bundle(self):
        return get_editorial_cockpit_bundle(
            self.app.catalog,
            catalog_service=self.app.catalog_service,
        )

    def get_difficulty_calibration_bundle(self):
        return get_difficulty_calibration_bundle(self.app.catalog)

    def refresh_catalog_overlay(self):
        self.reload_catalog_state(
            self.app.catalog_service.load_catalog(),
            banner_message="Catalogue actualise.",
            reopen_catalog=True,
        )

    def refresh_editorial_cockpit_overlay(self):
        self.reload_catalog_state(
            self.app.catalog_service.load_catalog(),
            banner_message="Cockpit editorial actualise.",
            reopen_editorial=True,
        )

    def toggle_catalog_pack(self, pack_id, enabled, *, reopen_overlay="catalog"):
        try:
            catalog, updated_pack = self.app.catalog_service.set_pack_enabled(pack_id, enabled)
        except CatalogServiceError as exc:
            self.dialog_port.show_error("Catalogue", str(exc))
            return

        status_message = (
            f"Pack active : {updated_pack.label}."
            if updated_pack.effective_enabled
            else f"Pack desactive : {updated_pack.label}."
        )
        self.reload_catalog_state(
            catalog,
            banner_message=status_message,
            reopen_catalog=reopen_overlay == "catalog",
            reopen_editorial=reopen_overlay == "editorial",
        )

    def get_official_pack_library(self):
        try:
            return self.app.catalog_service.list_official_packs(), ""
        except CatalogServiceError as exc:
            return (), str(exc)

    def preview_catalog_pack_zip(self):
        selected_path = self.file_dialog_port.ask_open_filename(
            parent=self.app.catalog_window if self.app.catalog_window is not None else self.app.root,
            title="Choisir une archive de pack",
            filetypes=[("Archives ZIP", "*.zip"), ("Tous les fichiers", "*.*")],
        )
        if not selected_path:
            return
        self.preview_catalog_pack_source(selected_path)

    def preview_catalog_pack_directory(self):
        selected_dir = self.file_dialog_port.ask_directory(
            parent=self.app.catalog_window if self.app.catalog_window is not None else self.app.root,
            title="Choisir un dossier de pack",
        )
        if not selected_dir:
            return
        self.preview_catalog_pack_source(selected_dir)

    def preview_official_catalog_pack(self, archive_path, *, reopen_overlay="catalog"):
        self.preview_catalog_pack_source(archive_path, reopen_overlay=reopen_overlay)

    def preview_catalog_pack_source(self, source_path, *, reopen_overlay="catalog"):
        try:
            preview = self.app.catalog_service.inspect_pack_source(source_path)
        except CatalogServiceError as exc:
            self.dialog_port.show_error("Catalogue", str(exc))
            return

        self.app.catalog_import_preview = preview
        self.app.catalog_import_preview_reopen_overlay = reopen_overlay
        self.app.catalog_screen.render_import_preview_dialog(self.app, preview)

    def close_catalog_pack_preview(self):
        preview_window = getattr(self.app, "catalog_import_preview_window", None)
        if preview_window is not None and preview_window.winfo_exists():
            preview_window.destroy()
        self.app.catalog_import_preview_window = None
        self.app.catalog_import_preview = None
        self.app.catalog_import_preview_reopen_overlay = "catalog"

    def build_pack_import_status_message(self, preview, pack_summary):
        parts = [f"Pack ajoute : {pack_summary.label}."]
        parts.append(
            f"{len(preview.categories_added)} categorie(s) inspectee(s), "
            f"{len(preview.playable_after_activation)} jouable(s) apres activation."
        )
        if pack_summary.effective_enabled:
            parts.append(
                f"Statut final : actif, {pack_summary.loaded_category_count} categorie(s) chargee(s) maintenant."
            )
        else:
            parts.append("Statut final : installe mais desactive jusqu'a activation manuelle.")

        if preview.installed_non_playable_categories:
            sample_labels = ", ".join(
                category.label for category in preview.installed_non_playable_categories[:3]
            )
            parts.append(
                f"{len(preview.installed_non_playable_categories)} categorie(s) restent installees mais non jouables: {sample_labels}."
            )
        elif preview.alerts:
            parts.append(f"{len(preview.alerts)} alerte(s) restent visibles dans le catalogue.")

        return " ".join(parts)

    def confirm_catalog_pack_import(self, enabled):
        if self.app.catalog_import_preview is None:
            return

        source_path = self.app.catalog_import_preview.source_path
        try:
            catalog, pack_summary = self.app.catalog_service.import_pack_from_source(
                source_path,
                enabled=enabled,
            )
        except CatalogServiceError as exc:
            self.dialog_port.show_error("Importer un pack", str(exc))
            return

        preview = self.app.catalog_import_preview
        reopen_overlay = self.app.catalog_import_preview_reopen_overlay
        self.close_catalog_pack_preview()
        self.reload_catalog_state(
            catalog,
            banner_message=self.build_pack_import_status_message(preview, pack_summary),
            reopen_catalog=reopen_overlay == "catalog",
            reopen_editorial=reopen_overlay == "editorial",
        )

    def import_catalog_pack(self):
        self.preview_catalog_pack_directory()
