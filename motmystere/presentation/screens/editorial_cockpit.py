import tkinter as tk

from ..formatters import format_played_at
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


class EditorialCockpitScreen:
    def render(self, app, *, banner_message=""):
        if app.editorial_cockpit_window is not None and app.editorial_cockpit_window.winfo_exists():
            app.editorial_cockpit_window.destroy()

        bundle = app.get_editorial_cockpit_bundle()

        window = tk.Toplevel(app.root, bg=APP_BG)
        window.title("Cockpit editorial")
        window.resizable(True, True)
        window.minsize(1180, 820)
        window.protocol("WM_DELETE_WINDOW", lambda: self._close(app))
        app.editorial_cockpit_window = window

        ui = app.ui
        container = ui.frame(window, bg=APP_BG, padx=18, pady=18)
        container.pack(fill="both", expand=True)

        header = ui.card(container, bg=HERO_BG, border=ACCENT_BORDER, padx=18, pady=16)
        header.pack(fill="x")
        ui.label(
            header,
            text="Cockpit editorial",
            bg=HERO_BG,
            font=("Georgia", 20, "bold"),
        ).pack(anchor="w")
        ui.label(
            header,
            text=self._build_header_text(bundle["summary"]),
            bg=HERO_BG,
            fg=SUBTLE_TEXT,
            wraplength=1040,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(4, 0))

        actions = ui.frame(header, bg=HERO_BG)
        actions.pack(anchor="w", pady=(12, 0))
        tk.Button(actions, text="Actualiser", command=app.refresh_editorial_cockpit_overlay, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(actions, text="Catalogue", command=app.show_catalog_overlay, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(
            actions,
            text="Pilotage difficulte",
            command=app.show_difficulty_calibration_overlay,
            width=18,
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
                wraplength=1080,
                justify="left",
            ).pack(anchor="w", fill="x")

        if bundle.get("official_error"):
            error_card = ui.card(container, bg=ERROR_BG, border=ERROR_COLOR, padx=14, pady=12)
            error_card.pack(fill="x", pady=(14, 0))
            ui.label(
                error_card,
                text=bundle["official_error"],
                bg=ERROR_BG,
                fg=ERROR_COLOR,
                wraplength=1080,
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

        self._render_summary_cards(ui, content, bundle["summary"])
        self._render_priority_sections(ui, content, bundle["priority_sections"])
        self._render_pack_section(ui, app, content, "Packs installes", bundle["installed_packs"])
        self._render_pack_section(ui, app, content, "Packs officiels", bundle["official_packs"])

    def _close(self, app):
        if app.editorial_cockpit_window is not None and app.editorial_cockpit_window.winfo_exists():
            app.editorial_cockpit_window.destroy()
        app.editorial_cockpit_window = None

    def _build_header_text(self, summary):
        latest = format_played_at(summary.get("latest_observation_at"))
        return (
            f"{summary['priority_count']} categorie(s) prioritaire(s), "
            f"{summary['installed_pack_count']} pack(s) installe(s), "
            f"{summary['official_pack_count']} pack(s) officiel(s) encore hors installation. "
            f"{summary['active_pair_count']} paire(s) actives cote calibration. "
            f"Derniere observation: {latest}."
        )

    def _render_summary_cards(self, ui, parent, summary):
        row = ui.frame(parent, bg=APP_BG)
        row.pack(fill="x")

        for index, card_info in enumerate(summary["cards"]):
            bg, border, accent = self._get_action_style(card_info["key"])
            card = ui.card(row, bg=bg, border=border, padx=14, pady=14)
            card.pack(
                side="left",
                fill="both",
                expand=True,
                padx=(0, 8 if index < len(summary["cards"]) - 1 else 0),
            )
            ui.label(
                card,
                text=card_info["title"],
                bg=bg,
                fg=accent,
                font=("Arial", 10, "bold"),
            ).pack(anchor="w")
            ui.label(
                card,
                text=str(card_info["value"]),
                bg=bg,
                fg=TEXT_COLOR,
                font=("Arial", 18, "bold"),
            ).pack(anchor="w", pady=(4, 0))
            ui.label(
                card,
                text=card_info["detail"],
                bg=bg,
                fg=SUBTLE_TEXT,
                wraplength=250,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(6, 0))

    def _render_priority_sections(self, ui, parent, sections):
        for section in sections:
            if section["count"] == 0 and section["key"] != "keep":
                continue

            bg, border, accent = self._get_action_style(section["key"])
            card = ui.card(parent, bg=bg, border=border, padx=16, pady=16)
            card.pack(fill="x", pady=(14, 0))
            ui.label(
                card,
                text=f"Priorites · {section['title']}",
                bg=bg,
                fg=accent,
                font=("Arial", 12, "bold"),
            ).pack(anchor="w")
            ui.label(
                card,
                text=section["description"],
                bg=bg,
                fg=SUBTLE_TEXT,
                wraplength=1060,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(4, 0))

            if not section["items"]:
                ui.label(
                    card,
                    text="Aucune categorie dans cette classe de decision.",
                    bg=bg,
                    fg=SUBTLE_TEXT,
                    wraplength=1060,
                    justify="left",
                ).pack(anchor="w", fill="x", pady=(8, 0))
                continue

            for item in section["items"]:
                self._render_priority_item(ui, card, item, bg=bg)

    def _render_priority_item(self, ui, parent, item, *, bg):
        item_bg, item_border, accent = self._get_action_style(item["recommended_action"])
        card = ui.card(parent, bg=item_bg, border=item_border, padx=12, pady=12)
        card.pack(fill="x", pady=(10, 0))

        title_row = ui.frame(card, bg=item_bg)
        title_row.pack(fill="x")
        ui.label(
            title_row,
            text=item["label"],
            bg=item_bg,
            fg=accent,
            font=("Arial", 10, "bold"),
        ).pack(side="left")
        ui.label(
            title_row,
            text=item["recommended_action_label"],
            bg=item_bg,
            fg=accent,
            font=("Arial", 10, "bold"),
        ).pack(side="right")

        ui.label(
            card,
            text=(
                f"Pack : {item['pack_label']} | Couverture : {item['total_words']}/{item['target_total_words']} mots | "
                f"Calibration : {item['calibration_label']}"
            ),
            bg=item_bg,
            fg=TEXT_COLOR,
            wraplength=1020,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(4, 0))
        if item["reasons"]:
            ui.render_bullets(card, item["reasons"], fg=SUBTLE_TEXT, wraplength=1000)

    def _render_pack_section(self, ui, app, parent, title, packs):
        ui.label(
            parent,
            text=title,
            bg=APP_BG,
            fg=ACCENT_COLOR,
            font=("Arial", 12, "bold"),
        ).pack(anchor="w", pady=(18, 8))

        if not packs:
            ui.label(
                parent,
                text="Aucun element dans cette section.",
                bg=APP_BG,
                fg=SUBTLE_TEXT,
                wraplength=1080,
                justify="left",
            ).pack(anchor="w", fill="x")
            return

        for pack in packs:
            self._render_pack_card(ui, app, parent, pack)

    def _render_pack_card(self, ui, app, parent, pack):
        bg, border, accent = self._get_action_style(pack["recommended_action"])
        card = ui.card(parent, bg=bg, border=border, padx=16, pady=16)
        card.pack(fill="x", pady=(0, 12))

        title_row = ui.frame(card, bg=bg)
        title_row.pack(fill="x")
        ui.label(
            title_row,
            text=pack["label"],
            bg=bg,
            fg=TEXT_COLOR,
            font=("Arial", 12, "bold"),
        ).pack(side="left")
        ui.label(
            title_row,
            text=pack["recommended_action_label"],
            bg=bg,
            fg=accent,
            font=("Arial", 10, "bold"),
        ).pack(side="right")

        detail_lines = [
            (
                f"Origine : {self._format_origin(pack['origin'])} | "
                f"Lecture : {pack['playability_label']} | Couverture : {pack['coverage_label']} | "
                f"Calibration : {pack['calibration_label']}"
            ),
            (
                f"Categories : {pack['category_count']} declaree(s) | "
                f"jouables : {pack['playable_category_count']} | chargees : {pack['loaded_category_count']}"
            ),
        ]
        if pack.get("description"):
            detail_lines.append(pack["description"])
        if pack.get("source_path"):
            detail_lines.append(f"Source : {pack['source_path']}")

        for line in detail_lines:
            ui.label(
                card,
                text=line,
                bg=bg,
                fg=TEXT_COLOR,
                wraplength=1060,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(4, 0))

        if pack["reasons"]:
            ui.label(
                card,
                text="Lecture mainteneur",
                bg=bg,
                fg=accent,
                font=("Arial", 10, "bold"),
            ).pack(anchor="w", pady=(10, 0))
            ui.render_bullets(card, pack["reasons"], fg=TEXT_COLOR, wraplength=1040)

        actions = ui.frame(card, bg=bg)
        actions.pack(anchor="w", pady=(10, 0))
        if pack["installed"] and pack["origin"] == "local" and pack["status"] != "invalid":
            label = "Desactiver" if pack["effective_enabled"] else "Activer"
            tk.Button(
                actions,
                text=label,
                width=14,
                command=lambda pack_id=pack["pack_id"], enabled=not pack["effective_enabled"]: app.toggle_catalog_pack(
                    pack_id,
                    enabled,
                    reopen_overlay="editorial",
                ),
            ).pack(side="left", padx=(0, 8))
        elif not pack["installed"]:
            tk.Button(
                actions,
                text="Voir et installer",
                width=18,
                command=lambda archive_path=pack["archive_path"]: app.preview_official_catalog_pack(
                    archive_path,
                    reopen_overlay="editorial",
                ),
            ).pack(side="left", padx=(0, 8))

        self._render_category_grid(ui, card, pack["categories"], bg=bg)

    def _render_category_grid(self, ui, parent, categories, *, bg):
        ui.label(
            parent,
            text="Lecture par categorie",
            bg=bg,
            fg=ACCENT_COLOR,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", pady=(12, 6))

        if not categories:
            ui.label(
                parent,
                text="Aucune categorie exploitable pour ce pack.",
                bg=bg,
                fg=SUBTLE_TEXT,
                wraplength=1040,
                justify="left",
            ).pack(anchor="w", fill="x")
            return

        table = ui.frame(parent, bg=bg)
        table.pack(fill="x")

        headers = ["Categorie", "Decision", "F", "M", "D"]
        for column_index, header in enumerate(headers):
            ui.label(
                table,
                text=header,
                bg=bg,
                fg=SUBTLE_TEXT,
                font=("Arial", 9, "bold"),
            ).grid(row=0, column=column_index, padx=4, pady=4, sticky="nsew")

        for row_index, category in enumerate(categories, start=1):
            category_bg, category_border, accent = self._get_action_style(category["recommended_action"])
            label_card = tk.Frame(
                table,
                bg=category_bg,
                padx=8,
                pady=6,
                highlightthickness=1,
                highlightbackground=category_border,
                bd=0,
            )
            label_card.grid(row=row_index, column=0, padx=3, pady=3, sticky="nsew")
            ui.label(
                label_card,
                text=category["label"],
                bg=category_bg,
                fg=accent,
                font=("Arial", 9, "bold"),
                justify="left",
                wraplength=280,
            ).pack(anchor="w")
            ui.label(
                label_card,
                text=(
                    f"{category['total_words']}/{category['target_total_words']} mots | "
                    f"{category['calibration_label']}"
                ),
                bg=category_bg,
                fg=TEXT_COLOR,
                wraplength=280,
                justify="left",
            ).pack(anchor="w", pady=(2, 0))
            if category["reasons"]:
                ui.label(
                    label_card,
                    text=category["reasons"][0],
                    bg=category_bg,
                    fg=SUBTLE_TEXT,
                    wraplength=280,
                    justify="left",
                ).pack(anchor="w", pady=(4, 0))

            decision_bg, decision_border, decision_fg = self._get_action_style(category["recommended_action"])
            decision_card = tk.Frame(
                table,
                bg=decision_bg,
                padx=8,
                pady=6,
                highlightthickness=1,
                highlightbackground=decision_border,
                bd=0,
            )
            decision_card.grid(row=row_index, column=1, padx=3, pady=3, sticky="nsew")
            ui.label(
                decision_card,
                text=category["recommended_action_label"],
                bg=decision_bg,
                fg=decision_fg,
                font=("Arial", 9, "bold"),
                justify="center",
            ).pack()

            for column_index, cell in enumerate(category["difficulty_cells"], start=2):
                cell_bg, cell_border, cell_fg = self._get_calibration_style(cell["calibration_status"])
                cell_card = tk.Frame(
                    table,
                    bg=cell_bg,
                    padx=8,
                    pady=6,
                    highlightthickness=1,
                    highlightbackground=cell_border,
                    bd=0,
                )
                cell_card.grid(row=row_index, column=column_index, padx=3, pady=3, sticky="nsew")
                ui.label(
                    cell_card,
                    text=cell["coverage_text"],
                    bg=cell_bg,
                    fg=cell_fg,
                    font=("Arial", 9, "bold"),
                    justify="center",
                ).pack()
                ui.label(
                    cell_card,
                    text=cell["calibration_label"],
                    bg=cell_bg,
                    fg=TEXT_COLOR,
                    font=("Arial", 8),
                    justify="center",
                ).pack(pady=(2, 0))

        for column_index in range(len(headers)):
            table.grid_columnconfigure(column_index, weight=1)

    def _format_origin(self, origin):
        return {
            "builtin": "Catalogue integre",
            "local": "Pack local",
            "official": "Pack officiel",
        }.get(origin, origin)

    def _get_action_style(self, action):
        if action == "disable":
            return ERROR_BG, ERROR_COLOR, ERROR_COLOR
        if action == "enrich":
            return WARNING_BG, WARNING_COLOR, WARNING_COLOR
        if action == "recalibrate":
            return "#eef6ff", ACCENT_BORDER, ACCENT_COLOR
        return SUCCESS_BG, SUCCESS_COLOR, SUCCESS_COLOR

    def _get_calibration_style(self, status):
        if status == "review":
            return ERROR_BG, ERROR_COLOR, ERROR_COLOR
        if status == "watch":
            return WARNING_BG, WARNING_COLOR, WARNING_COLOR
        if status == "stable":
            return SUCCESS_BG, SUCCESS_COLOR, SUCCESS_COLOR
        if status == "not_installed":
            return "#eef6ff", ACCENT_BORDER, ACCENT_COLOR
        if status == "unavailable":
            return "#f6f4ef", "#d7d0c1", SUBTLE_TEXT
        return CARD_BG, ACCENT_BORDER, ACCENT_COLOR
