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
        window.minsize(920, 640)
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
            wraplength=820,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(4, 0))
        ui.label(
            header,
            text=f"Dossier surveille : {app.catalog.local_pack_dir}",
            bg=HERO_BG,
            fg=ACCENT_COLOR,
            wraplength=820,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(8, 0))

        actions = ui.frame(header, bg=HERO_BG)
        actions.pack(anchor="w", pady=(12, 0))
        tk.Button(actions, text="Ajouter un pack", command=app.import_catalog_pack, width=18).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(actions, text="Actualiser", command=app.refresh_catalog_overlay, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(actions, text="Fermer", command=lambda: self._close(app), width=12).pack(side="left")

        if banner_message:
            banner = ui.card(container, bg=SUCCESS_BG, border=SUCCESS_COLOR, padx=14, pady=12)
            banner.pack(fill="x", pady=(14, 0))
            ui.label(
                banner,
                text=banner_message,
                bg=SUCCESS_BG,
                fg=SUCCESS_COLOR,
                wraplength=860,
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

        content.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(content_window, width=event.width),
        )

        for pack_summary in app.catalog.pack_summaries:
            self._render_pack_card(app, content, pack_summary)

    def _close(self, app):
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
                wraplength=860,
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
                wraplength=860,
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
                wraplength=860,
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
            wraplength=840,
        )

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
