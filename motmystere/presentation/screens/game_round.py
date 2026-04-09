import tkinter as tk

from ...categories import format_category_name
from ..theme import (
    ACCENT_BORDER,
    ACCENT_COLOR,
    APP_BG,
    CARD_BG,
    HERO_BG,
    MUTED_BG,
    SUBTLE_TEXT,
    SUCCESS_COLOR,
    TEXT_COLOR,
)


class GameRoundScreen:
    def render(self, app):
        app.clear_screen()
        app.letter_buttons = {}
        _, progression = app._get_progression_bundle()
        ui = app.ui

        container = ui.frame(app.root, bg=APP_BG, padx=24, pady=24)
        container.pack(fill="both", expand=True)

        hero = ui.card(container, bg=HERO_BG, border=ACCENT_BORDER, padx=18, pady=16)
        hero.pack(fill="x")
        ui.label(
            hero,
            text=(
                f"{app.player['name']} | {format_category_name(app.session.category)} | "
                f"{app.session.difficulty}"
            ),
            bg=HERO_BG,
            fg=ACCENT_COLOR,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")

        app.round_hint_var.set(
            f"Mot de {app.session.word_profile.length} lettres, complexite "
            f"{app.session.word_complexity}, timer {app.session.time_limit} s."
        )
        ui.label(
            hero,
            textvariable=app.round_hint_var,
            bg=HERO_BG,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(4, 6))
        if app.guided_session is not None and app.guided_session.get("status") == "active":
            objective_state = app.guided_session.get("objective_state") or {}
            session_kind = str(app.guided_session.get("session_kind") or "")
            mode_label = app.guided_session.get("mode_label", "Session active")
            if session_kind.startswith("review_"):
                session_text = (
                    f"{mode_label} en cours : {objective_state.get('title', '')} "
                    f"({objective_state.get('progress_text', '')}). "
                    "Hors rotation normale."
                )
            else:
                session_text = (
                    f"{mode_label} en cours : {objective_state.get('title', '')} "
                    f"({objective_state.get('progress_text', '')})."
                )
            ui.label(
                hero,
                text=session_text,
                bg=HERO_BG,
                fg=ACCENT_COLOR,
                font=("Arial", 10, "bold"),
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(0, 4))
        if progression is not None and progression.get("primary_goal") is not None:
            primary_goal = progression["primary_goal"]
            is_aligned = (
                primary_goal.get("category") == app.session.category
                and primary_goal.get("difficulty") == app.session.difficulty
            )
            guidance = (
                "Cette manche suit l'objectif recommande."
                if is_aligned
                else (
                    "Objectif recommande en parallele : "
                    f"{primary_goal['title']} avec {format_category_name(primary_goal['category'])} "
                    f"en {primary_goal['difficulty']}."
                )
            )
            ui.label(
                hero,
                text=guidance,
                bg=HERO_BG,
                fg=SUCCESS_COLOR if is_aligned else ACCENT_COLOR,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x")
        if progression is not None and progression.get("featured_challenge") is not None:
            featured_challenge = progression["featured_challenge"]
            is_challenge_aligned = (
                featured_challenge.get("category") == app.session.category
                and featured_challenge.get("difficulty") == app.session.difficulty
            )
            challenge_text = (
                "Cette manche fait aussi avancer le defi du moment."
                if is_challenge_aligned
                else (
                    "Defi du moment : "
                    f"{featured_challenge['title']} sur "
                    f"{format_category_name(featured_challenge['category'])} "
                    f"en {featured_challenge['difficulty']}."
                )
                if featured_challenge.get("category") and featured_challenge.get("difficulty")
                else f"Defi du moment : {featured_challenge['title']}."
            )
            ui.label(
                hero,
                text=challenge_text,
                bg=HERO_BG,
                fg=SUCCESS_COLOR if is_challenge_aligned else SUBTLE_TEXT,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(4, 0))

        body = ui.frame(container, bg=APP_BG)
        body.pack(fill="x", pady=(16, 0))

        left = ui.card(body, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        left.pack(side="left", fill="both", expand=True)
        right = ui.card(body, bg=MUTED_BG, border="#d7d0c1", padx=18, pady=18)
        right.pack(side="left", fill="both", padx=(14, 0))

        ui.label(
            left,
            text="Clavier actif : tapez une lettre A-Z ou cliquez sur les boutons.",
            fg=ACCENT_COLOR,
            font=("Arial", 10, "bold"),
            wraplength=420,
            justify="left",
        ).pack(anchor="w", fill="x")
        ui.label(
            left,
            textvariable=app.word_var,
            font=("Courier New", 28, "bold"),
        ).pack(pady=(18, 14))

        metrics = ui.frame(left)
        metrics.pack(fill="x", pady=(0, 8))
        for index, (title, variable, bg, border, fg) in enumerate(
            [
                ("Essais restants", app.attempts_var, "#f7f9fc", "#d7deea", TEXT_COLOR),
                ("Temps", app.timer_var, "#fff7e8", "#ebd29a", TEXT_COLOR),
                ("Score si victoire", app.score_hint_var, "#eef6ff", "#c8d9f1", ACCENT_COLOR),
            ]
        ):
            card = ui.card(metrics, bg=bg, border=border, padx=12, pady=10)
            card.pack(side="left", fill="both", expand=True, padx=(0, 8 if index < 2 else 0))
            ui.label(
                card,
                text=title,
                bg=bg,
                fg=SUBTLE_TEXT,
                font=("Arial", 9, "bold"),
            ).pack(anchor="w")
            ui.label(
                card,
                textvariable=variable,
                bg=bg,
                fg=fg,
                font=("Arial", 14, "bold"),
            ).pack(anchor="w", pady=(2, 0))

        status_card = ui.card(left, bg="#f7f9fc", border="#d7deea", padx=12, pady=12)
        status_card.pack(fill="x", pady=(4, 12))
        ui.label(
            status_card,
            textvariable=app.tried_letters_var,
            bg="#f7f9fc",
            wraplength=420,
            justify="left",
        ).pack(anchor="w")
        ui.label(
            status_card,
            textvariable=app.status_var,
            bg="#f7f9fc",
            fg=SUBTLE_TEXT,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        keyboard = ui.frame(left, bg=CARD_BG)
        keyboard.pack()
        for index, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            button = tk.Button(
                keyboard,
                text=letter,
                width=4,
                command=lambda selected=letter: app.handle_letter(selected),
            )
            button.grid(row=index // 6, column=index % 6, padx=2, pady=2)
            app.letter_buttons[letter] = button

        actions = ui.frame(left, bg=CARD_BG)
        actions.pack(fill="x", pady=(14, 0))

        tk.Button(
            actions,
            text="Arreter la session" if app.guided_session is not None else "Changer de reglage",
            command=app.stop_guided_session_from_game if app.guided_session is not None else app.return_to_menu,
            width=18,
        ).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Profil", command=app.open_player_dashboard, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(actions, text="Classement", command=app.show_leaderboard, width=14).pack(
            side="left"
        )

        ui.section_title(right, "Pourquoi cette manche compte")
        ui.label(
            right,
            textvariable=app.progress_var,
            wraplength=320,
            justify="left",
        ).pack(anchor="w", fill="x")
        if progression is not None:
            ui.section_title(right, "Defis du moment")
            ui.render_challenge_cards(right, progression.get("challenges", ()), limit=2, compact=True)
            ui.section_title(right, "Objectifs actifs")
            ui.render_goal_cards(right, progression["goals"], limit=2, compact=True)

        app.status_var.set("Proposez une lettre.")
        app.refresh_game_view()
        app.root.bind("<Key>", app.on_game_keypress)
        app.schedule_timer()
