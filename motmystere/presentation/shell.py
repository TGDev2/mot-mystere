import tkinter as tk

from .theme import (
    ACCENT_BORDER,
    ACCENT_COLOR,
    CARD_BG,
    MUTED_BG,
    SUBTLE_TEXT,
    SUCCESS_BG,
    SUCCESS_COLOR,
    TEXT_COLOR,
    WARNING_COLOR,
)


class PresentationShell:
    def frame(self, parent, *, bg=None, **kwargs):
        return tk.Frame(parent, bg=bg or parent.cget("bg"), **kwargs)

    def label(
        self,
        parent,
        *,
        text=None,
        textvariable=None,
        bg=None,
        fg=TEXT_COLOR,
        **kwargs,
    ):
        return tk.Label(
            parent,
            text=text,
            textvariable=textvariable,
            bg=bg or parent.cget("bg"),
            fg=fg,
            **kwargs,
        )

    def card(self, parent, *, bg=CARD_BG, border=ACCENT_BORDER, padx=16, pady=16):
        return tk.Frame(
            parent,
            bg=bg,
            padx=padx,
            pady=pady,
            highlightthickness=1,
            highlightbackground=border,
            bd=0,
        )

    def section_title(self, parent, text):
        self.label(
            parent,
            text=text,
            font=("Arial", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

    def render_bullets(self, parent, lines, *, fg=TEXT_COLOR, wraplength=320):
        for line in lines:
            self.label(
                parent,
                text=f"- {line}",
                fg=fg,
                wraplength=wraplength,
                justify="left",
            ).pack(anchor="w", fill="x", pady=2)

    def render_progress_bar(self, parent, ratio, *, fill=ACCENT_COLOR):
        canvas = tk.Canvas(
            parent,
            width=220,
            height=10,
            bg=parent.cget("bg"),
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(anchor="w", pady=(6, 0))
        canvas.create_rectangle(0, 0, 220, 10, fill="#dbe3f2", outline="")
        canvas.create_rectangle(
            0,
            0,
            int(220 * max(0.0, min(1.0, ratio))),
            10,
            fill=fill,
            outline="",
        )

    def render_progress_cards(self, parent, items, *, limit=3, compact=False):
        for item in items[:limit]:
            bg = SUCCESS_BG if item["completed"] else CARD_BG
            border = SUCCESS_COLOR if item["completed"] else ACCENT_BORDER
            card = self.card(parent, bg=bg, border=border, padx=12, pady=12)
            card.pack(fill="x", pady=4)
            badge_text = item.get("badge_text") or (
                "Defi atteint"
                if item.get("kind") == "challenge" and item["completed"]
                else "Defi du moment"
                if item.get("kind") == "challenge"
                else "Objectif atteint"
                if item["completed"]
                else "Objectif actif"
            )
            self.label(
                card,
                text=badge_text,
                fg=SUCCESS_COLOR if item["completed"] else ACCENT_COLOR,
                font=("Arial", 9, "bold"),
            ).pack(anchor="w")
            self.label(
                card,
                text=item["title"],
                font=("Arial", 11, "bold"),
                wraplength=320 if compact else 420,
                justify="left",
            ).pack(anchor="w", pady=(2, 2))
            self.label(
                card,
                text=item["progress_text"],
                font=("Arial", 10, "bold"),
            ).pack(anchor="w")
            self.render_progress_bar(
                card,
                item["ratio"],
                fill=SUCCESS_COLOR if item["completed"] else ACCENT_COLOR,
            )
            self.label(
                card,
                text=item["detail"],
                fg=SUBTLE_TEXT,
                wraplength=320 if compact else 420,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(6, 0))

    def render_personalized_recommendation_card(
        self,
        parent,
        recommendation,
        *,
        compact=False,
        command=None,
    ):
        if recommendation is None:
            return None

        wraplength = 320 if compact else 760
        card = self.card(parent, bg="#eef6ff", border="#c8d9f1", padx=14, pady=14)
        card.pack(fill="x", pady=(6, 0))
        self.label(
            card,
            text=f"Diagnostic dominant : {recommendation['driver_label']}",
            bg="#eef6ff",
            fg=ACCENT_COLOR,
            font=("Arial", 9, "bold"),
        ).pack(anchor="w")
        self.label(
            card,
            text=recommendation["title"],
            bg="#eef6ff",
            font=("Arial", 11, "bold"),
            wraplength=wraplength,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(2, 2))
        self.label(
            card,
            text=recommendation["detail"],
            bg="#eef6ff",
            fg=SUBTLE_TEXT,
            wraplength=wraplength,
            justify="left",
        ).pack(anchor="w", fill="x")
        if command is not None and recommendation.get("cta_text"):
            tk.Button(
                card,
                text=recommendation["cta_text"],
                command=command,
                width=16,
            ).pack(anchor="w", pady=(10, 0))
        return card

    def render_review_option_card(
        self,
        parent,
        option,
        *,
        compact=False,
        command=None,
    ):
        if option is None:
            return None

        if option.get("kind") == "failed_words":
            bg = "#fff7e8"
            border = "#ebd29a"
            accent = WARNING_COLOR
            badge = f"Revision mots rates | {option.get('count', 0)} cible(s)"
        else:
            bg = "#eef6ff"
            border = "#c8d9f1"
            accent = ACCENT_COLOR
            badge = f"Revision paire fragile | {option.get('driver_label', 'Diagnostic')}"

        wraplength = 320 if compact else 760
        card = self.card(parent, bg=bg, border=border, padx=14, pady=14)
        card.pack(fill="x", pady=(6, 0))
        self.label(
            card,
            text=badge,
            bg=bg,
            fg=accent,
            font=("Arial", 9, "bold"),
        ).pack(anchor="w")
        self.label(
            card,
            text=option["title"],
            bg=bg,
            font=("Arial", 11, "bold"),
            wraplength=wraplength,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(2, 2))
        self.label(
            card,
            text=option["detail"],
            bg=bg,
            fg=SUBTLE_TEXT,
            wraplength=wraplength,
            justify="left",
        ).pack(anchor="w", fill="x")
        if command is not None and option.get("cta_text"):
            tk.Button(
                card,
                text=option["cta_text"],
                command=command,
                width=26 if compact else 28,
            ).pack(anchor="w", pady=(10, 0))
        return card

    def render_catalog_exploration_card(
        self,
        parent,
        exploration_state,
        *,
        title="Etat d'exploration",
        empty_message="",
        tracked=True,
        compact=False,
    ):
        bg, border, accent = self._get_exploration_style(exploration_state)
        wraplength = 320 if compact else 420
        card = self.card(parent, bg=bg, border=border, padx=12, pady=12)
        card.pack(fill="x", pady=(14, 0) if not compact else (6, 0))
        self.label(
            card,
            text=title,
            bg=bg,
            fg=accent,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")

        if exploration_state is None:
            self.label(
                card,
                text=empty_message,
                bg=bg,
                fg=TEXT_COLOR,
                wraplength=wraplength,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(6, 0))
            return card

        self.label(
            card,
            text=exploration_state["badge_text"],
            bg=bg,
            fg=accent,
            font=("Arial", 9, "bold"),
        ).pack(anchor="w", pady=(6, 0))
        self.label(
            card,
            text=exploration_state["label"],
            bg=bg,
            font=("Arial", 11, "bold"),
            wraplength=wraplength,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(2, 2))
        self.label(
            card,
            text=exploration_state["progress_text"],
            bg=bg,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")
        self.render_progress_bar(card, exploration_state["ratio"], fill=accent)
        detail_text = exploration_state["detail"] if tracked else empty_message
        self.label(
            card,
            text=detail_text,
            bg=bg,
            fg=SUBTLE_TEXT,
            wraplength=wraplength,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(6, 0))
        if exploration_state.get("note"):
            self.label(
                card,
                text=exploration_state["note"],
                bg=bg,
                fg=accent,
                wraplength=wraplength,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(6, 0))
        return card

    def render_goal_cards(self, parent, goals, *, limit=3, compact=False):
        items = [dict(goal, kind="goal") for goal in goals]
        self.render_progress_cards(parent, items, limit=limit, compact=compact)

    def render_challenge_cards(self, parent, challenges, *, limit=3, compact=False):
        items = [dict(challenge, kind="challenge") for challenge in challenges]
        self.render_progress_cards(parent, items, limit=limit, compact=compact)

    def render_metric_cards(self, parent, metrics):
        row = self.frame(parent)
        row.pack(fill="x", pady=(0, 8))
        for index, metric in enumerate(metrics):
            card = self.card(
                row,
                bg=metric.get("bg", CARD_BG),
                border=metric.get("border", ACCENT_BORDER),
                padx=12,
                pady=10,
            )
            card.pack(
                side="left",
                fill="both",
                expand=True,
                padx=(0, 8 if index < len(metrics) - 1 else 0),
            )
            self.label(
                card,
                text=metric["label"],
                fg=SUBTLE_TEXT,
                font=("Arial", 9, "bold"),
            ).pack(anchor="w")
            self.label(
                card,
                text=metric["value"],
                fg=metric.get("fg", TEXT_COLOR),
                font=("Arial", 14, "bold"),
            ).pack(anchor="w", pady=(2, 0))

    def render_mastery_grid(self, parent, mastery, *, compact=False):
        if mastery is None:
            return

        legend = self.card(
            parent,
            bg="#f7f9fc" if compact else CARD_BG,
            border="#d7deea" if compact else ACCENT_BORDER,
            padx=12,
            pady=10,
        )
        legend.pack(fill="x", pady=(6, 0))
        self.label(
            legend,
            text=(
                "Lecture rapide : 0/1 = premiere validation, 1-2/3 = valide, "
                "3/3 = maitrise."
            ),
            fg=SUBTLE_TEXT,
            wraplength=320 if compact else 760,
            justify="left",
        ).pack(anchor="w", fill="x")

        table_card = self.card(
            parent,
            bg=CARD_BG if compact else "#fcfbf7",
            border=ACCENT_BORDER if compact else "#d7d0c1",
            padx=12,
            pady=12,
        )
        table_card.pack(fill="x", pady=(8, 0))
        table = self.frame(table_card, bg=table_card.cget("bg"))
        table.pack(fill="x")

        headers = ["Categorie", "F", "M", "D"]
        for column_index, header in enumerate(headers):
            self.label(
                table,
                text=header,
                bg=table.cget("bg"),
                fg=SUBTLE_TEXT,
                font=("Arial", 9, "bold"),
            ).grid(row=0, column=column_index, padx=4, pady=4, sticky="nsew")

        for row_index, row in enumerate(mastery["rows"], start=1):
            self.label(
                table,
                text=row["label"],
                bg=table.cget("bg"),
                font=("Arial", 9, "bold"),
                justify="left",
                wraplength=110 if compact else 180,
            ).grid(row=row_index, column=0, padx=(0, 6), pady=4, sticky="w")

            for column_index, cell in enumerate(row["cells"], start=1):
                cell_bg, cell_fg, cell_border = self._get_mastery_cell_style(cell)
                cell_card = tk.Frame(
                    table,
                    bg=cell_bg,
                    padx=8,
                    pady=6,
                    highlightthickness=1,
                    highlightbackground=cell_border,
                    bd=0,
                )
                cell_card.grid(
                    row=row_index,
                    column=column_index,
                    padx=3,
                    pady=3,
                    sticky="nsew",
                )
                cell_text = (
                    cell["progress_text"]
                    if compact
                    else f"{cell['state_label']}\n{cell['progress_text']}"
                )
                self.label(
                    cell_card,
                    text=cell_text,
                    bg=cell_bg,
                    fg=cell_fg,
                    font=("Arial", 8, "bold") if compact else ("Arial", 9, "bold"),
                    justify="center",
                ).pack()

        for column_index in range(len(headers)):
            table.grid_columnconfigure(column_index, weight=1)

    def render_catalog_exploration_grid(self, parent, exploration_grid, *, compact=False):
        if exploration_grid is None:
            return

        legend = self.card(
            parent,
            bg="#f7f9fc" if compact else CARD_BG,
            border="#d7deea" if compact else ACCENT_BORDER,
            padx=12,
            pady=10,
        )
        legend.pack(fill="x", pady=(6, 0))
        self.label(
            legend,
            text=(
                "Lecture rapide : neuf = rotation tres fraiche, bientot epuise = pool entame, "
                "cycle imminent = prochaine relance proche."
            ),
            fg=SUBTLE_TEXT,
            wraplength=320 if compact else 760,
            justify="left",
        ).pack(anchor="w", fill="x")

        table_card = self.card(
            parent,
            bg=CARD_BG if compact else "#fcfbf7",
            border=ACCENT_BORDER if compact else "#d7d0c1",
            padx=12,
            pady=12,
        )
        table_card.pack(fill="x", pady=(8, 0))
        table = self.frame(table_card, bg=table_card.cget("bg"))
        table.pack(fill="x")

        headers = ["Categorie", "F", "M", "D"]
        for column_index, header in enumerate(headers):
            self.label(
                table,
                text=header,
                bg=table.cget("bg"),
                fg=SUBTLE_TEXT,
                font=("Arial", 9, "bold"),
            ).grid(row=0, column=column_index, padx=4, pady=4, sticky="nsew")

        for row_index, row in enumerate(exploration_grid["rows"], start=1):
            self.label(
                table,
                text=row["label"],
                bg=table.cget("bg"),
                font=("Arial", 9, "bold"),
                justify="left",
                wraplength=110 if compact else 180,
            ).grid(row=row_index, column=0, padx=(0, 6), pady=4, sticky="w")

            for column_index, cell in enumerate(row["cells"], start=1):
                cell_bg, cell_fg, cell_border = self._get_exploration_style(cell)
                cell_card = tk.Frame(
                    table,
                    bg=cell_bg,
                    padx=8,
                    pady=6,
                    highlightthickness=1,
                    highlightbackground=cell_border,
                    bd=0,
                )
                cell_card.grid(
                    row=row_index,
                    column=column_index,
                    padx=3,
                    pady=3,
                    sticky="nsew",
                )
                cell_text = cell["progress_text"] if compact else f"{cell['state_label']}\n{cell['progress_text']}"
                self.label(
                    cell_card,
                    text=cell_text,
                    bg=cell_bg,
                    fg=cell_fg,
                    font=("Arial", 8, "bold") if compact else ("Arial", 9, "bold"),
                    justify="center",
                ).pack()

        for column_index in range(len(headers)):
            table.grid_columnconfigure(column_index, weight=1)

    def _get_mastery_cell_style(self, cell):
        state = cell.get("state")
        if state == "mastered":
            return SUCCESS_BG, SUCCESS_COLOR, SUCCESS_COLOR
        if state == "validated":
            return "#eef6ff", ACCENT_COLOR, ACCENT_BORDER
        if state == "in_progress":
            return "#fff7e8", WARNING_COLOR, "#ebd29a"
        if state == "unavailable":
            return MUTED_BG, SUBTLE_TEXT, "#d7d0c1"
        return "#f7f9fc", SUBTLE_TEXT, "#d7deea"

    def _get_exploration_style(self, exploration_state):
        state = (exploration_state or {}).get("state")
        if state == "fresh":
            return SUCCESS_BG, SUCCESS_COLOR, SUCCESS_COLOR
        if state == "warning":
            return "#fff7e8", WARNING_COLOR, "#ebd29a"
        if state == "imminent":
            return "#fff3f1", WARNING_COLOR, "#e0b0a7"
        if state == "profile_required":
            return "#eef6ff", ACCENT_COLOR, ACCENT_BORDER
        if state == "unavailable":
            return MUTED_BG, SUBTLE_TEXT, "#d7d0c1"
        return CARD_BG, ACCENT_BORDER, ACCENT_COLOR
