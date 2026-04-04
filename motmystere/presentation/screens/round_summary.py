import tkinter as tk

from ...categories import format_category_name
from ..theme import (
    ACCENT_BORDER,
    ACCENT_COLOR,
    APP_BG,
    CARD_BG,
    ERROR_BG,
    ERROR_COLOR,
    MUTED_BG,
    SUBTLE_TEXT,
    SUCCESS_BG,
    SUCCESS_COLOR,
    WARNING_BG,
    WARNING_COLOR,
)


class RoundSummaryScreen:
    def render_round_summary(
        self,
        app,
        *,
        title,
        result_message,
        score_summary,
        score_earned,
        progression_snapshot,
        completed_goals,
        mastery_updates,
        breakdown,
        guided_progress=None,
        guided_recommendation=None,
    ):
        app.clear_screen()
        tone_bg = SUCCESS_BG if title == "Victoire" else WARNING_BG if title == "Temps ecoule" else ERROR_BG
        tone_fg = SUCCESS_COLOR if title == "Victoire" else WARNING_COLOR if title == "Temps ecoule" else ERROR_COLOR
        ui = app.ui

        container = ui.frame(app.root, bg=APP_BG, padx=24, pady=24)
        container.pack(fill="both", expand=True)

        hero = ui.card(container, bg=tone_bg, border=tone_fg, padx=20, pady=18)
        hero.pack(fill="x")
        ui.label(
            hero,
            text=title,
            bg=tone_bg,
            fg=tone_fg,
            font=("Georgia", 24, "bold"),
        ).pack(anchor="w")
        ui.label(
            hero,
            text=(
                f"{format_category_name(app.session.category)} | "
                f"{app.session.difficulty} | mot {app.session.secret_word}"
            ),
            bg=tone_bg,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", pady=(4, 6))
        ui.label(
            hero,
            text=result_message,
            bg=tone_bg,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x")

        ui.render_metric_cards(
            container,
            [
                {
                    "label": "Score de la manche",
                    "value": f"{score_earned} pts",
                    "bg": "#eef6ff",
                    "border": "#c8d9f1",
                    "fg": ACCENT_COLOR,
                },
                {
                    "label": "Essais restants",
                    "value": str(app.session.attempts_left),
                    "bg": "#f7f9fc",
                    "border": "#d7deea",
                },
                {
                    "label": "Temps restant",
                    "value": f"{app.session.time_remaining} s",
                    "bg": "#fff7e8",
                    "border": "#ebd29a",
                },
            ],
        )

        details = ui.card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        details.pack(fill="x")
        ui.section_title(details, "Impact sur la progression")
        ui.label(
            details,
            text=score_summary,
            fg=ACCENT_COLOR if score_earned else SUBTLE_TEXT,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x")
        ui.label(
            details,
            text=app._build_player_summary(app.player),
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(8, 0))
        if completed_goals:
            ui.label(
                details,
                text="Nouvel objectif valide : " + ", ".join(goal["title"] for goal in completed_goals) + ".",
                fg=SUCCESS_COLOR,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))
        if mastery_updates:
            ui.label(
                details,
                text="Nouveau palier de maitrise : " + ", ".join(update["title"] for update in mastery_updates) + ".",
                fg=SUCCESS_COLOR,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))
        if breakdown is not None:
            ui.label(
                details,
                text=(
                    f"Lecture rapide : base {breakdown['base_points']}, mot {breakdown['word_bonus']}, "
                    f"complexite {breakdown['complexity_bonus']}, essais {breakdown['attempts_bonus']}, "
                    f"temps {breakdown['time_bonus']}."
                ),
                fg=SUBTLE_TEXT,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))

        if guided_progress is not None:
            session_area = ui.card(container, bg="#eef6ff", border="#c8d9f1", padx=18, pady=18)
            session_area.pack(fill="x", pady=(14, 0))
            ui.section_title(session_area, "Session guidee")
            ui.label(
                session_area,
                text=(
                    f"{guided_progress['title']} : {guided_progress['progress_text']}. "
                    f"{guided_progress['detail']}"
                ),
                fg=ACCENT_COLOR,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x")
            if guided_recommendation is not None:
                recommendation_text = (
                    f"{format_category_name(guided_recommendation['category'])} "
                    f"en {guided_recommendation['difficulty']}."
                    if guided_recommendation.get("category") and guided_recommendation.get("difficulty")
                    else "Reprendre le reglage conseille."
                )
                ui.section_title(session_area, "Prochaine manche recommandee")
                ui.label(
                    session_area,
                    text=recommendation_text,
                    font=("Arial", 11, "bold"),
                    wraplength=760,
                    justify="left",
                ).pack(anchor="w", fill="x")
                ui.label(
                    session_area,
                    text=guided_recommendation["detail"],
                    wraplength=760,
                    justify="left",
                ).pack(anchor="w", fill="x", pady=(4, 0))

        if progression_snapshot is not None:
            goal_area = ui.card(container, bg=MUTED_BG, border="#d7d0c1", padx=18, pady=18)
            goal_area.pack(fill="x", pady=(14, 0))
            ui.section_title(goal_area, "Prochaine action recommandee")
            primary_goal = progression_snapshot["primary_goal"]
            if primary_goal is not None:
                ui.label(
                    goal_area,
                    text=(
                        f"{primary_goal['title']} : {primary_goal['progress_text']}. "
                        f"{primary_goal['detail']}"
                    ),
                    wraplength=760,
                    justify="left",
                ).pack(anchor="w", fill="x", pady=(0, 8))
            mastery = progression_snapshot["mastery"]
            ui.label(
                goal_area,
                text=(
                    f"Maitrise globale : {mastery['mastery_percent']} %. "
                    f"{mastery['pairs_left_to_master']} paire(s) encore a maitriser."
                ),
                fg=ACCENT_COLOR,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(0, 8))
            featured_challenge = progression_snapshot.get("featured_challenge")
            if featured_challenge is not None:
                ui.label(
                    goal_area,
                    text=(
                        f"Defi du moment : {featured_challenge['title']} "
                        f"({featured_challenge['progress_text']})."
                    ),
                    fg=ACCENT_COLOR,
                    wraplength=760,
                    justify="left",
                ).pack(anchor="w", fill="x", pady=(0, 8))
            ui.render_mastery_grid(goal_area, mastery)
            ui.section_title(goal_area, "Defis actifs")
            ui.render_challenge_cards(
                goal_area,
                progression_snapshot.get("challenges", ()),
                limit=3,
            )
            ui.section_title(goal_area, "Objectifs actifs")
            ui.render_goal_cards(goal_area, progression_snapshot["goals"], limit=3)

        buttons = ui.frame(container, bg=APP_BG)
        buttons.pack(fill="x", pady=(16, 0))

        if guided_progress is not None:
            tk.Button(
                buttons,
                text="Continuer la session",
                command=app._continue_guided_session,
                width=24,
            ).pack(side="left", padx=(0, 8))
            tk.Button(
                buttons,
                text="Arreter la session",
                command=app._stop_guided_session_after_round,
                width=20,
            ).pack(side="left", padx=(0, 8))
        else:
            tk.Button(
                buttons,
                text="Rejouer meme reglage",
                command=app.replay_current_selection,
                width=20,
            ).pack(side="left", padx=(0, 8))
            if progression_snapshot is not None and progression_snapshot.get("primary_goal") is not None:
                app.primary_goal_snapshot = progression_snapshot
                tk.Button(
                    buttons,
                    text="Session objectif",
                    command=app.start_guided_primary_goal_session,
                    width=18,
                ).pack(side="left", padx=(0, 8))
            tk.Button(
                buttons,
                text="Changer categorie",
                command=app.return_to_menu,
                width=18,
            ).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="Profil", command=app.open_player_dashboard, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(buttons, text="Classement", command=app.show_leaderboard, width=14).pack(
            side="left"
        )

        footer = ui.frame(container, bg=APP_BG)
        footer.pack(fill="x", pady=(14, 0))
        tk.Button(footer, text="Quitter", command=app.close, width=12).pack()

        if guided_progress is not None:
            app.root.bind("<Return>", lambda _event: app._continue_guided_session())
        else:
            app.root.bind("<Return>", lambda _event: app.replay_current_selection())

    def render_guided_session_summary(self, app):
        if app.guided_session is None:
            app.show_main_menu()
            return

        objective_state = app.guided_session.get("objective_state") or app.guided_session["objective"]
        rounds = app.guided_session.get("rounds", ())
        completed = app.guided_session.get("status") == "completed"
        tone_bg = SUCCESS_BG if completed else WARNING_BG
        tone_fg = SUCCESS_COLOR if completed else WARNING_COLOR
        wins = sum(1 for round_data in rounds if round_data.get("won"))
        total_score = sum(int(round_data.get("score_earned") or 0) for round_data in rounds)
        goal_titles = []
        mastery_titles = []
        for round_data in rounds:
            for goal in round_data.get("completed_goals", ()):
                title = goal.get("title")
                if title and title not in goal_titles:
                    goal_titles.append(title)
            for update in round_data.get("mastery_updates", ()):
                title = update.get("title")
                if title and title not in mastery_titles:
                    mastery_titles.append(title)

        app.clear_screen()
        ui = app.ui
        container = ui.frame(app.root, bg=APP_BG, padx=24, pady=24)
        container.pack(fill="both", expand=True)

        hero = ui.card(container, bg=tone_bg, border=tone_fg, padx=20, pady=18)
        hero.pack(fill="x")
        ui.label(
            hero,
            text="Objectif atteint" if completed else "Session guidee interrompue",
            bg=tone_bg,
            fg=tone_fg,
            font=("Georgia", 24, "bold"),
        ).pack(anchor="w")
        ui.label(
            hero,
            text=objective_state["title"],
            bg=tone_bg,
            font=("Arial", 11, "bold"),
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(4, 6))
        ui.label(
            hero,
            text=(
                f"Progression session : {app.guided_session['initial_progress_text']} "
                f"-> {objective_state['progress_text']}."
            ),
            bg=tone_bg,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x")

        ui.render_metric_cards(
            container,
            [
                {
                    "label": "Manches jouees",
                    "value": str(len(rounds)),
                    "bg": "#f7f9fc",
                    "border": "#d7deea",
                },
                {
                    "label": "Victoires",
                    "value": str(wins),
                    "bg": SUCCESS_BG,
                    "border": SUCCESS_COLOR,
                    "fg": SUCCESS_COLOR,
                },
                {
                    "label": "Score session",
                    "value": f"{total_score} pts",
                    "bg": "#eef6ff",
                    "border": "#c8d9f1",
                    "fg": ACCENT_COLOR,
                },
            ],
        )

        details = ui.card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        details.pack(fill="x")
        ui.section_title(details, "Resultat")
        ui.label(
            details,
            text=objective_state["detail"],
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x")
        if rounds:
            last_round = rounds[-1]
            ui.label(
                details,
                text=(
                    f"Derniere manche : {last_round['title'].lower()} sur "
                    f"{format_category_name(last_round['category'])} en {last_round['difficulty']} "
                    f"({last_round['score_earned']} pts)."
                ),
                fg=ACCENT_COLOR,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))
        if goal_titles:
            ui.label(
                details,
                text="Objectifs valides pendant la session : " + ", ".join(goal_titles) + ".",
                fg=SUCCESS_COLOR,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))
        if mastery_titles:
            ui.label(
                details,
                text="Paliers de maitrise atteints : " + ", ".join(mastery_titles) + ".",
                fg=SUCCESS_COLOR,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))

        if rounds:
            rounds_card = ui.card(container, bg=MUTED_BG, border="#d7d0c1", padx=18, pady=18)
            rounds_card.pack(fill="x", pady=(14, 0))
            ui.section_title(rounds_card, "Trace de session")
            for round_index, round_data in enumerate(rounds, start=1):
                ui.label(
                    rounds_card,
                    text=(
                        f"Manche {round_index} : {format_category_name(round_data['category'])} / "
                        f"{round_data['difficulty']} / {round_data['title']} / "
                        f"{round_data['score_earned']} pts"
                    ),
                    wraplength=760,
                    justify="left",
                ).pack(anchor="w", fill="x", pady=2)

        buttons = ui.frame(container, bg=APP_BG)
        buttons.pack(fill="x", pady=(16, 0))
        if app.primary_goal_snapshot is not None and app.primary_goal_snapshot.get("primary_goal") is not None:
            tk.Button(
                buttons,
                text="Session objectif",
                command=app.start_guided_primary_goal_session,
                width=18,
            ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons,
            text="Retour accueil",
            command=app.return_to_menu,
            width=18,
        ).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="Profil", command=app.open_player_dashboard, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(buttons, text="Classement", command=app.show_leaderboard, width=14).pack(
            side="left"
        )

        app.root.bind("<Return>", lambda _event: app.return_to_menu())
