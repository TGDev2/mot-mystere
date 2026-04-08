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


class DifficultyCalibrationScreen:
    def render(self, app):
        bundle = app.get_difficulty_calibration_bundle()
        ui = app.ui

        window = tk.Toplevel(app.root, bg=APP_BG)
        window.title("Pilotage difficulte")
        window.resizable(True, True)
        window.minsize(1060, 760)

        container = ui.frame(window, bg=APP_BG, padx=18, pady=18)
        container.pack(fill="both", expand=True)

        header = ui.card(container, bg=HERO_BG, border=ACCENT_BORDER, padx=18, pady=16)
        header.pack(fill="x")
        ui.label(
            header,
            text="Pilotage difficulte",
            bg=HERO_BG,
            font=("Georgia", 20, "bold"),
        ).pack(anchor="w")
        ui.label(
            header,
            text=self._build_header_text(bundle["summary"]),
            bg=HERO_BG,
            fg=SUBTLE_TEXT,
            wraplength=920,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(4, 0))

        actions = ui.frame(header, bg=HERO_BG)
        actions.pack(anchor="w", pady=(12, 0))
        tk.Button(actions, text="Fermer", command=window.destroy, width=12).pack(side="left")

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
        self._render_policy_card(ui, content, bundle["policy"])
        self._render_rollups(ui, content, bundle)
        for section in bundle["sections"]:
            self._render_section(ui, content, section)

    def _build_header_text(self, summary):
        latest = format_played_at(summary.get("latest_observation_at"))
        return (
            "Lecture agregee sur toutes les parties locales enregistrees. "
            f"{summary['signal_count']} paire(s) signee(s), "
            f"{summary['active_pair_count']} paire(s) active(s) au catalogue. "
            f"Derniere observation: {latest}."
        )

    def _render_summary_cards(self, ui, parent, summary):
        row = ui.frame(parent, bg=APP_BG)
        row.pack(fill="x")
        cards = [
            ("A revoir", summary["review_count"], ERROR_BG, ERROR_COLOR),
            ("A surveiller", summary["watch_count"], WARNING_BG, WARNING_COLOR),
            ("Stables", summary["stable_count"], SUCCESS_BG, SUCCESS_COLOR),
            ("Donnees faibles", summary["insufficient_data_count"], CARD_BG, ACCENT_COLOR),
        ]
        for index, (title, value, bg, accent) in enumerate(cards):
            card = ui.card(row, bg=bg, border=accent, padx=14, pady=14)
            card.pack(
                side="left",
                fill="both",
                expand=True,
                padx=(0, 8 if index < len(cards) - 1 else 0),
            )
            ui.label(
                card,
                text=title,
                bg=bg,
                fg=accent,
                font=("Arial", 10, "bold"),
            ).pack(anchor="w")
            ui.label(
                card,
                text=str(value),
                bg=bg,
                fg=TEXT_COLOR,
                font=("Arial", 18, "bold"),
            ).pack(anchor="w", pady=(4, 0))

    def _render_policy_card(self, ui, parent, policy):
        card = ui.card(parent, bg="#f7f9fc", border="#d7deea", padx=16, pady=16)
        card.pack(fill="x", pady=(14, 0))
        ui.label(
            card,
            text="Regles de lecture",
            bg="#f7f9fc",
            fg=ACCENT_COLOR,
            font=("Arial", 12, "bold"),
        ).pack(anchor="w")
        ui.render_bullets(
            card,
            policy["lines"],
            fg=TEXT_COLOR,
            wraplength=940,
        )

    def _render_rollups(self, ui, parent, bundle):
        row = ui.frame(parent, bg=APP_BG)
        row.pack(fill="x", pady=(14, 0))
        self._render_rollup_card(
            ui,
            row,
            "Rollup par pack",
            bundle["pack_rollups"],
            padx=(0, 8),
        )
        self._render_rollup_card(
            ui,
            row,
            "Rollup par categorie",
            bundle["category_rollups"],
            padx=(0, 0),
        )

    def _render_rollup_card(self, ui, parent, title, rollups, *, padx):
        card = ui.card(parent, bg=CARD_BG, border=ACCENT_BORDER, padx=16, pady=16)
        card.pack(side="left", fill="both", expand=True, padx=padx)
        ui.label(
            card,
            text=title,
            bg=CARD_BG,
            fg=ACCENT_COLOR,
            font=("Arial", 12, "bold"),
        ).pack(anchor="w")

        if not rollups:
            ui.label(
                card,
                text="Aucun element actif dans le catalogue.",
                bg=CARD_BG,
                fg=SUBTLE_TEXT,
                wraplength=440,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(6, 0))
            return

        for rollup in rollups:
            bg, border, accent = self._get_status_style(rollup["status"])
            item = ui.card(card, bg=bg, border=border, padx=12, pady=12)
            item.pack(fill="x", pady=(8, 0))
            ui.label(
                item,
                text=rollup["label"],
                bg=bg,
                fg=accent,
                font=("Arial", 10, "bold"),
            ).pack(anchor="w")
            ui.label(
                item,
                text=f"{rollup['status_label']} | {rollup['pairs']} paire(s) | {rollup['signal_count']} signee(s)",
                bg=bg,
                fg=TEXT_COLOR,
                wraplength=420,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(4, 0))
            ui.label(
                item,
                text=rollup["detail"],
                bg=bg,
                fg=SUBTLE_TEXT,
                wraplength=420,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(4, 0))

    def _render_section(self, ui, parent, section):
        card = ui.card(parent, bg=CARD_BG, border=ACCENT_BORDER, padx=16, pady=16)
        card.pack(fill="x", pady=(14, 0))
        ui.label(
            card,
            text=section["title"],
            bg=CARD_BG,
            fg=ACCENT_COLOR,
            font=("Arial", 12, "bold"),
        ).pack(anchor="w")
        ui.label(
            card,
            text=section["description"],
            bg=CARD_BG,
            fg=SUBTLE_TEXT,
            wraplength=940,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(4, 0))

        if not section["pairs"]:
            ui.label(
                card,
                text="Aucune paire dans cette section.",
                bg=CARD_BG,
                fg=SUBTLE_TEXT,
                wraplength=940,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))
            return

        for pair in section["pairs"]:
            self._render_pair_card(ui, card, pair)

    def _render_pair_card(self, ui, parent, pair):
        bg, border, accent = self._get_status_style(pair["status"])
        card = ui.card(parent, bg=bg, border=border, padx=14, pady=14)
        card.pack(fill="x", pady=(10, 0))

        title_row = ui.frame(card, bg=bg)
        title_row.pack(fill="x")
        ui.label(
            title_row,
            text=pair["label"],
            bg=bg,
            fg=accent,
            font=("Arial", 11, "bold"),
        ).pack(side="left")
        ui.label(
            title_row,
            text=pair["status_label"],
            bg=bg,
            fg=accent,
            font=("Arial", 10, "bold"),
        ).pack(side="right")

        details = [
            f"Pack : {pair['pack_label']} | Niveau : {pair['difficulty']} | Direction : {pair['direction']}",
            (
                f"Observe : {pair['observed_text']} | Lisse : {pair['smoothed_text']} | "
                f"Cible : {pair['target_text']}"
            ),
            (
                f"Volume : {pair['games_played']} partie(s) | Joueurs : {pair['distinct_players']} | "
                f"Joueur dominant : {self._format_metric(pair['dominant_player_share'])}"
            ),
            (
                f"Temps perdu : {self._format_metric(pair['timeout_rate'])} | "
                f"Essais perdus : {self._format_metric(pair['attempt_fail_rate'])} | "
                f"Marge temps victoire : {self._format_metric(pair['avg_time_margin_on_wins'])} | "
                f"Marge essais victoire : {self._format_metric(pair['avg_attempt_margin_on_wins'])}"
            ),
            (
                f"Score moyen : {pair['avg_score']:.1f} pts | "
                f"Complexite moyenne : {pair['avg_complexity']:.1f} | "
                f"Derniere partie : {format_played_at(pair['last_played_at'])}"
            ),
        ]
        for line in details:
            ui.label(
                card,
                text=line,
                bg=bg,
                fg=TEXT_COLOR,
                wraplength=920,
                justify="left",
            ).pack(anchor="w", fill="x", pady=2)

        ui.label(
            card,
            text="Raison principale",
            bg=bg,
            fg=accent,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", pady=(8, 0))
        ui.label(
            card,
            text=pair["reason"],
            bg=bg,
            fg=TEXT_COLOR,
            wraplength=920,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(4, 0))

        ui.label(
            card,
            text="Suggestion manuelle",
            bg=bg,
            fg=accent,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", pady=(8, 0))
        ui.label(
            card,
            text=pair["manual_suggestion"],
            bg=bg,
            fg=SUBTLE_TEXT,
            wraplength=920,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(4, 0))

    def _get_status_style(self, status):
        if status == "review":
            return ERROR_BG, ERROR_COLOR, ERROR_COLOR
        if status == "watch":
            return WARNING_BG, WARNING_COLOR, WARNING_COLOR
        if status == "stable":
            return SUCCESS_BG, SUCCESS_COLOR, SUCCESS_COLOR
        return CARD_BG, ACCENT_BORDER, ACCENT_COLOR

    def _format_metric(self, value):
        if value is None:
            return "-"
        return f"{round(float(value) * 100, 1):g}%"
