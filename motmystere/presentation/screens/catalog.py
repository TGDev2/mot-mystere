import tkinter as tk

from ..theme import (
    ACCENT_BORDER,
    ACCENT_COLOR,
    APP_BG,
    CARD_BG,
    ERROR_BG,
    ERROR_COLOR,
    HERO_BG,
    SUBTLE_TEXT,
    SUCCESS_BG,
    SUCCESS_COLOR,
    TEXT_COLOR,
    WARNING_BG,
    WARNING_COLOR,
)


class CatalogScreen:
    def render(self, app, *, banner_message=""):
        if app.catalog_window is not None and app.catalog_window.winfo_exists():
            app.catalog_window.destroy()

        window = tk.Toplevel(app.root, bg=APP_BG)
        window.title("Catalogue")
        window.resizable(True, True)
        window.minsize(980, 680)
        window.protocol("WM_DELETE_WINDOW", lambda: self._close(app))
        app.catalog_window = window

        ui = app.ui
        container = ui.frame(window, bg=APP_BG, padx=18, pady=18)
        container.pack(fill="both", expand=True)

        header = ui.card(container, bg=HERO_BG, border=ACCENT_BORDER, padx=18, pady=16)
        header.pack(fill="x")
        ui.label(
            header,
            text="Catalogue de packs",
            bg=HERO_BG,
            font=("Georgia", 20, "bold"),
        ).pack(anchor="w")
        ui.label(
            header,
            text=self._build_header_summary(app),
            bg=HERO_BG,
            fg=SUBTLE_TEXT,
            wraplength=860,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(4, 0))
        ui.label(
            header,
            text=f"Dossier surveille : {app.catalog.local_pack_dir}",
            bg=HERO_BG,
            fg=ACCENT_COLOR,
            wraplength=860,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(8, 0))

        actions = ui.frame(header, bg=HERO_BG)
        actions.pack(anchor="w", pady=(12, 0))
        tk.Button(actions, text="Importer un pack .zip", command=app.preview_catalog_pack_zip, width=20).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(
            actions,
            text="Importer un dossier (expert)",
            command=app.preview_catalog_pack_directory,
            width=24,
        ).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Actualiser", command=app.refresh_catalog_overlay, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(
            actions,
            text="Pilotage difficulte",
            command=app.show_difficulty_calibration_overlay,
            width=20,
        ).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Fermer", command=lambda: self._close(app), width=12).pack(side="left")

        if banner_message:
            banner = ui.card(container, bg=SUCCESS_BG, border=SUCCESS_COLOR, padx=14, pady=12)
            banner.pack(fill="x", pady=(14, 0))
            ui.label(
                banner,
                text=banner_message,
                bg=SUCCESS_BG,
                fg=SUCCESS_COLOR,
                wraplength=900,
                justify="left",
            ).pack(anchor="w", fill="x")

        viewport = ui.frame(container, bg=APP_BG)
        viewport.pack(fill="both", expand=True, pady=(14, 0))

        canvas = tk.Canvas(viewport, bg=APP_BG, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        content = ui.frame(canvas, bg=APP_BG)
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(content_window, width=event.width))

        official_packs, official_error = app._get_official_pack_library()
        self._render_import_routes(ui, app, content, official_packs, official_error)

        ui.label(
            content,
            text="Packs installes",
            bg=APP_BG,
            fg=ACCENT_COLOR,
            font=("Arial", 12, "bold"),
        ).pack(anchor="w", pady=(18, 8))
        for pack_summary in app.catalog.pack_summaries:
            self._render_pack_card(app, content, pack_summary)

    def render_import_preview_dialog(self, app, preview):
        if app.catalog_import_preview_window is not None and app.catalog_import_preview_window.winfo_exists():
            app.catalog_import_preview_window.destroy()

        parent = app.catalog_window if app.catalog_window is not None and app.catalog_window.winfo_exists() else app.root
        window = tk.Toplevel(parent, bg=APP_BG)
        window.title("Verifier le pack")
        window.resizable(True, True)
        window.minsize(820, 620)
        window.transient(parent)
        window.grab_set()
        window.protocol("WM_DELETE_WINDOW", app.close_catalog_pack_preview)
        app.catalog_import_preview_window = window

        ui = app.ui
        container = ui.frame(window, bg=APP_BG, padx=18, pady=18)
        container.pack(fill="both", expand=True)

        header_bg, header_border, header_fg = self._get_preview_style(preview)
        header = ui.card(container, bg=header_bg, border=header_border, padx=16, pady=16)
        header.pack(fill="x")
        ui.label(
            header,
            text=preview.pack_label,
            bg=header_bg,
            fg=header_fg,
            font=("Georgia", 18, "bold"),
        ).pack(anchor="w")
        ui.label(
            header,
            text=(
                f"Source : {self._format_source_kind(preview.source_kind)} | "
                f"Pack id : {preview.pack_id} | "
                f"{'Pret a installer' if preview.installable else 'Installation bloquee'}"
            ),
            bg=header_bg,
            fg=header_fg,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(6, 0))
        ui.label(
            header,
            text=str(preview.source_path),
            bg=header_bg,
            fg=SUBTLE_TEXT,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(6, 0))

        viewport = ui.frame(container, bg=APP_BG)
        viewport.pack(fill="both", expand=True, pady=(14, 0))

        canvas = tk.Canvas(viewport, bg=APP_BG, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        content = ui.frame(canvas, bg=APP_BG)
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(content_window, width=event.width))

        if preview.blockers:
            blocker_card = ui.card(content, bg=ERROR_BG, border=ERROR_COLOR, padx=14, pady=14)
            blocker_card.pack(fill="x", pady=(0, 12))
            ui.label(
                blocker_card,
                text="Blocages",
                bg=ERROR_BG,
                fg=ERROR_COLOR,
                font=("Arial", 10, "bold"),
            ).pack(anchor="w")
            ui.render_bullets(blocker_card, preview.blockers, fg=ERROR_COLOR, wraplength=720)

        if preview.alerts:
            alert_card = ui.card(content, bg=WARNING_BG, border=WARNING_COLOR, padx=14, pady=14)
            alert_card.pack(fill="x", pady=(0, 12))
            ui.label(
                alert_card,
                text="Alertes",
                bg=WARNING_BG,
                fg=WARNING_COLOR,
                font=("Arial", 10, "bold"),
            ).pack(anchor="w")
            ui.render_bullets(alert_card, preview.alerts, fg=WARNING_COLOR, wraplength=720)

        category_card = ui.card(content, bg=CARD_BG, border=ACCENT_BORDER, padx=14, pady=14)
        category_card.pack(fill="x", pady=(0, 12))
        ui.label(
            category_card,
            text="Perimetre inspecte",
            bg=CARD_BG,
            fg=ACCENT_COLOR,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")
        self._render_preview_category_lines(ui, category_card, preview.categories_added, bg=CARD_BG)

        self._render_effect_card(
            ui,
            content,
            preview.effect_when_enabled,
            title="Apres installation et activation",
            note=(
                f"{len(preview.playable_after_activation)} categorie(s) seraient jouables tout de suite. "
                f"{len(preview.installed_non_playable_categories)} resteraient installees mais non jouables."
            ),
        )
        self._render_effect_card(
            ui,
            content,
            preview.effect_when_disabled,
            title="Apres installation sans activation",
            note=(
                "Le pack serait installe mais non charge tant qu'il reste desactive."
                if preview.effect_when_disabled.loaded_category_count == 0
                else "Le pack resterait partiellement charge selon son manifeste."
            ),
        )

        footer = ui.frame(container, bg=APP_BG)
        footer.pack(fill="x", pady=(16, 0))
        if preview.installable:
            tk.Button(
                footer,
                text="Installer et activer",
                command=lambda: app.confirm_catalog_pack_import(True),
                width=20,
            ).pack(side="left", padx=(0, 8))
            tk.Button(
                footer,
                text="Installer sans activer",
                command=lambda: app.confirm_catalog_pack_import(False),
                width=22,
            ).pack(side="left", padx=(0, 8))
        tk.Button(footer, text="Fermer", command=app.close_catalog_pack_preview, width=12).pack(side="left")

    def _close(self, app):
        app.close_catalog_pack_preview()
        if app.catalog_window is not None and app.catalog_window.winfo_exists():
            app.catalog_window.destroy()
        app.catalog_window = None

    def _build_header_summary(self, app):
        local_packs = [pack for pack in app.catalog.pack_summaries if pack.origin == "local"]
        active_count = sum(1 for pack in local_packs if pack.status == "active")
        disabled_count = sum(1 for pack in local_packs if pack.status == "disabled")
        invalid_count = sum(1 for pack in local_packs if pack.status == "invalid")
        local_pack_count = len(local_packs)
        return (
            f"{local_pack_count} pack(s) local(aux) detecte(s), "
            f"{active_count} actif(s), {disabled_count} desactive(s), {invalid_count} invalide(s). "
            f"{len(app.categories)} categorie(s) jouable(s) sont chargees."
        )

    def _render_import_routes(self, ui, app, parent, official_packs, official_error):
        card = ui.card(parent, bg="#f7f9fc", border="#d7deea", padx=16, pady=16)
        card.pack(fill="x")
        ui.label(
            card,
            text="Importer du contenu",
            bg="#f7f9fc",
            fg=ACCENT_COLOR,
            font=("Arial", 12, "bold"),
        ).pack(anchor="w")
        ui.label(
            card,
            text=(
                "Parcours nominal : importez une archive .zip, verifiez le perimetre du pack, "
                "puis choisissez de l'activer tout de suite ou de l'installer sans activation. "
                "Le dossier brut reste reserve aux usages experts."
            ),
            bg="#f7f9fc",
            fg=TEXT_COLOR,
            wraplength=900,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(6, 0))

        actions = ui.frame(card, bg="#f7f9fc")
        actions.pack(anchor="w", pady=(12, 0))
        tk.Button(actions, text="Importer un pack .zip", command=app.preview_catalog_pack_zip, width=20).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(
            actions,
            text="Importer un dossier (expert)",
            command=app.preview_catalog_pack_directory,
            width=24,
        ).pack(side="left")

        ui.label(
            card,
            text="Packs officiels inclus",
            bg="#f7f9fc",
            fg=ACCENT_COLOR,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", pady=(14, 4))

        if official_error:
            ui.label(
                card,
                text=official_error,
                bg="#f7f9fc",
                fg=ERROR_COLOR,
                wraplength=900,
                justify="left",
            ).pack(anchor="w", fill="x")
            return

        if not official_packs:
            ui.label(
                card,
                text="Aucun pack officiel embarque.",
                bg="#f7f9fc",
                fg=SUBTLE_TEXT,
                wraplength=900,
                justify="left",
            ).pack(anchor="w", fill="x")
            return

        for pack_info in official_packs:
            pack_card = ui.card(
                card,
                bg=SUCCESS_BG if not pack_info.installed else CARD_BG,
                border=SUCCESS_COLOR if not pack_info.installed else ACCENT_BORDER,
                padx=12,
                pady=12,
            )
            pack_card.pack(fill="x", pady=(6, 0))
            header = ui.frame(pack_card, bg=pack_card.cget("bg"))
            header.pack(fill="x")
            ui.label(
                header,
                text=pack_info.label,
                bg=pack_card.cget("bg"),
                fg=ACCENT_COLOR,
                font=("Arial", 11, "bold"),
            ).pack(side="left")
            ui.label(
                header,
                text="Deja installe" if pack_info.installed else "Pack fiable pret a installer",
                bg=pack_card.cget("bg"),
                fg=SUBTLE_TEXT if pack_info.installed else SUCCESS_COLOR,
                font=("Arial", 9, "bold"),
            ).pack(side="right")
            ui.label(
                pack_card,
                text=pack_info.description,
                bg=pack_card.cget("bg"),
                fg=TEXT_COLOR,
                wraplength=860,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(4, 0))
            ui.label(
                pack_card,
                text="Categories : " + ", ".join(pack_info.category_labels),
                bg=pack_card.cget("bg"),
                fg=SUBTLE_TEXT,
                wraplength=860,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(4, 0))
            if not pack_info.installed:
                tk.Button(
                    pack_card,
                    text="Voir et installer",
                    command=lambda archive_path=pack_info.archive_path: app.preview_official_catalog_pack(
                        archive_path
                    ),
                    width=18,
                ).pack(anchor="w", pady=(10, 0))

    def _render_pack_card(self, app, parent, pack_summary):
        ui = app.ui
        bg, border, fg = self._get_pack_style(pack_summary.status)
        card = ui.card(parent, bg=bg, border=border, padx=16, pady=16)
        card.pack(fill="x", pady=(0, 12))

        title_row = ui.frame(card, bg=bg)
        title_row.pack(fill="x")
        ui.label(
            title_row,
            text=pack_summary.label,
            bg=bg,
            font=("Arial", 12, "bold"),
        ).pack(side="left")
        ui.label(
            title_row,
            text=self._format_status_label(pack_summary.status),
            bg=bg,
            fg=fg,
            font=("Arial", 10, "bold"),
        ).pack(side="right")

        details = [
            f"Pack id : {pack_summary.pack_id}",
            f"Source : {pack_summary.source_path}",
            (
                f"Etat manifeste : {'actif' if pack_summary.declared_enabled else 'desactive'} | "
                f"etat applique : {'actif' if pack_summary.effective_enabled else 'desactive'}"
            ),
            (
                f"Categories declarees : {pack_summary.category_count} | "
                f"jouables : {pack_summary.playable_category_count} | "
                f"chargees : {pack_summary.loaded_category_count} | "
                f"alertes : {pack_summary.issue_count}"
            ),
        ]
        for line in details:
            ui.label(
                card,
                text=line,
                bg=bg,
                fg=TEXT_COLOR,
                wraplength=900,
                justify="left",
            ).pack(anchor="w", fill="x", pady=2)

        actions = ui.frame(card, bg=bg)
        actions.pack(anchor="w", pady=(10, 0))
        if pack_summary.origin == "local" and pack_summary.status != "invalid":
            action_label = "Desactiver" if pack_summary.effective_enabled else "Activer"
            tk.Button(
                actions,
                text=action_label,
                width=14,
                command=lambda pack_id=pack_summary.pack_id, enabled=not pack_summary.effective_enabled: app.toggle_catalog_pack(
                    pack_id,
                    enabled,
                ),
            ).pack(side="left")
        elif pack_summary.origin == "builtin":
            ui.label(
                actions,
                text="Catalogue integre en lecture seule.",
                bg=bg,
                fg=SUBTLE_TEXT,
            ).pack(side="left")
        else:
            ui.label(
                actions,
                text="Aucune action disponible tant que le pack reste invalide.",
                bg=bg,
                fg=fg,
            ).pack(side="left")

        self._render_category_section(ui, card, pack_summary, bg)
        self._render_issue_section(app, ui, card, pack_summary, bg, fg)

    def _render_category_section(self, ui, card, pack_summary, bg):
        ui.label(
            card,
            text="Categories",
            bg=bg,
            fg=ACCENT_COLOR,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", pady=(12, 4))

        if not pack_summary.categories:
            ui.label(
                card,
                text="Aucune categorie exploitable ou inspectable pour ce pack.",
                bg=bg,
                fg=SUBTLE_TEXT,
                wraplength=900,
                justify="left",
            ).pack(anchor="w", fill="x")
            return

        for category in pack_summary.categories:
            available_levels = ", ".join(category.available_difficulties) or "aucun niveau jouable"
            ui.label(
                card,
                text=(
                    f"- {category.label} | {self._format_status_label(category.status).lower()} | "
                    f"niveaux : {available_levels} | source : {category.source_path}"
                ),
                bg=bg,
                fg=TEXT_COLOR,
                wraplength=900,
                justify="left",
            ).pack(anchor="w", fill="x", pady=2)

    def _render_issue_section(self, app, ui, card, pack_summary, bg, fg):
        issues = app.catalog.issues_by_pack.get(pack_summary.pack_id, ())
        if not issues:
            return

        ui.label(
            card,
            text="Alertes",
            bg=bg,
            fg=fg,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", pady=(12, 4))
        ui.render_bullets(
            card,
            [issue.message for issue in issues],
            fg=fg,
            wraplength=880,
        )

    def _render_preview_category_lines(self, ui, parent, categories, *, bg):
        if not categories:
            ui.label(
                parent,
                text="Aucune categorie inspectable pour cette source.",
                bg=bg,
                fg=SUBTLE_TEXT,
                wraplength=720,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(6, 0))
            return

        for category in categories:
            levels = ", ".join(category.available_difficulties) or "aucun niveau jouable"
            ui.label(
                parent,
                text=(
                    f"- {category.label} | {self._format_status_label(category.status).lower()} | "
                    f"niveaux : {levels}"
                ),
                bg=bg,
                fg=TEXT_COLOR,
                wraplength=720,
                justify="left",
            ).pack(anchor="w", fill="x", pady=2)

    def _render_effect_card(self, ui, parent, pack_summary, *, title, note):
        bg, border, accent = self._get_pack_style(pack_summary.status)
        card = ui.card(parent, bg=bg, border=border, padx=14, pady=14)
        card.pack(fill="x", pady=(0, 12))
        ui.label(
            card,
            text=title,
            bg=bg,
            fg=accent,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")
        ui.label(
            card,
            text=note,
            bg=bg,
            fg=TEXT_COLOR,
            wraplength=720,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(6, 0))
        for line in (
            f"Statut applique : {self._format_status_label(pack_summary.status).lower()}",
            (
                f"Categories declarees : {pack_summary.category_count} | "
                f"jouables : {pack_summary.playable_category_count} | "
                f"chargees : {pack_summary.loaded_category_count}"
            ),
        ):
            ui.label(
                card,
                text=line,
                bg=bg,
                fg=TEXT_COLOR,
                wraplength=720,
                justify="left",
            ).pack(anchor="w", fill="x", pady=2)

    def _format_source_kind(self, source_kind):
        return {
            "zip": "archive ZIP",
            "directory": "dossier",
            "file": "fichier",
        }.get(source_kind, source_kind)

    def _format_status_label(self, status):
        labels = {
            "active": "Actif",
            "disabled": "Desactive",
            "invalid": "Invalide",
        }
        return labels.get(status, status.title())

    def _get_pack_style(self, status):
        if status == "active":
            return CARD_BG, ACCENT_BORDER, ACCENT_COLOR
        if status == "disabled":
            return WARNING_BG, WARNING_COLOR, WARNING_COLOR
        return ERROR_BG, ERROR_COLOR, ERROR_COLOR

    def _get_preview_style(self, preview):
        if preview.installable:
            return SUCCESS_BG, SUCCESS_COLOR, SUCCESS_COLOR
        return ERROR_BG, ERROR_COLOR, ERROR_COLOR
