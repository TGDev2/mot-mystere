import tkinter as tk

from ...categories import format_category_name
from ..formatters import format_played_at
from ..theme import (
    ACCENT_BORDER,
    ACCENT_COLOR,
    APP_BG,
    CARD_BG,
    HERO_BG,
    MUTED_BG,
    SUBTLE_TEXT,
    SUCCESS_BG,
    SUCCESS_COLOR,
    TEXT_COLOR,
    WARNING_BG,
    WARNING_COLOR,
)


class MainMenuScreen:
    def render(self, app, *, banner_message=""):
        app.clear_screen()
        app.banner_var.set(banner_message)

        recent_players = app._load_recent_players()
        dashboard, progression = app._get_progression_bundle() if app.player is not None else (None, None)
        ui = app.ui

        container = ui.frame(app.root, bg=APP_BG, padx=24, pady=24)
        container.pack(fill="both", expand=True)

        hero = ui.card(container, bg=HERO_BG, border=ACCENT_BORDER, padx=20, pady=18)
        hero.pack(fill="x")
        ui.label(
            hero,
            text="MotMystere",
            bg=HERO_BG,
            font=("Georgia", 24, "bold"),
        ).pack(anchor="w")
        ui.label(
            hero,
            text=(
                "Experience solo desktop concue pour rejouer souvent : rotation durable des mots, "
                "progression de maitrise et choix toujours lisibles."
            ),
            bg=HERO_BG,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(6, 10))

        badges = ui.frame(hero, bg=HERO_BG)
        badges.pack(fill="x")
        badge_texts = [
            f"{len(app.categories)} categories jouables",
            f"{len({value for values in app.category_availability.values() for value in values})} niveaux calibres",
            "score + profil + classement persistants",
        ]
        for index, text in enumerate(badge_texts):
            pill = ui.card(badges, bg="#f9fbff", border="#c7d5ef", padx=12, pady=8)
            pill.pack(side="left", padx=(0, 8 if index < len(badge_texts) - 1 else 0))
            ui.label(
                pill,
                text=text,
                bg="#f9fbff",
                fg=ACCENT_COLOR,
                font=("Arial", 9, "bold"),
            ).pack()

        body = ui.frame(container, bg=APP_BG)
        body.pack(fill="x", pady=(16, 0))

        left = ui.card(body, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        left.pack(side="left", fill="both", expand=True)
        right = ui.card(body, bg=MUTED_BG, border="#d7d0c1", padx=18, pady=18)
        right.pack(side="left", fill="both", padx=(14, 0))

        self._render_recent_players_section(app, left, recent_players)
        self._render_menu_form(app, left)

        if progression is not None:
            mastery = progression["mastery"]
            self._render_resume_panel(app, right, dashboard, progression)
            ui.section_title(right, "Carte de maitrise")
            ui.label(
                right,
                text=(
                    f"Maitrise globale : {mastery['mastery_percent']} %. "
                    f"{mastery['mastered_pairs']}/{mastery['total_pairs']} paires maitrisees, "
                    f"{mastery['pairs_left_to_master']} restantes."
                ),
                fg=ACCENT_COLOR,
                wraplength=330,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(0, 8))
            ui.render_mastery_grid(right, mastery, compact=True)
        else:
            self._render_onboarding_panel(app, right)

        self._render_main_menu_actions(app, container, dashboard, progression)

        app.player_name_entry.focus_set()
        app.root.bind("<Return>", app.on_main_menu_return)
        app.update_category_hint()

    def _render_catalog_card(self, app, parent):
        issue_lines = app._build_catalog_issue_lines()
        has_issue = bool(issue_lines)
        bg = WARNING_BG if has_issue else MUTED_BG
        border = WARNING_COLOR if has_issue else ACCENT_BORDER
        fg = WARNING_COLOR if has_issue else ACCENT_COLOR
        ui = app.ui

        card = ui.card(parent, bg=bg, border=border, padx=12, pady=12)
        card.pack(fill="x", pady=(14, 0))
        ui.label(
            card,
            text="Catalogue local",
            bg=bg,
            fg=fg,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")
        ui.label(
            card,
            text=app._build_catalog_summary(),
            bg=bg,
            fg=TEXT_COLOR,
            wraplength=340,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(6, 0))
        tk.Button(
            card,
            text="Gerer le catalogue",
            command=app.show_catalog_overlay,
            width=20,
        ).pack(anchor="w", pady=(10, 0))
        if issue_lines:
            ui.render_bullets(card, issue_lines, fg=fg, wraplength=320)

    def _render_recent_players_section(self, app, parent, recent_players):
        ui = app.ui
        ui.section_title(parent, "Profils recents")
        if not recent_players:
            ui.label(
                parent,
                text="Aucun profil recent. Creez un pseudo puis lancez une premiere manche.",
                fg=SUBTLE_TEXT,
                wraplength=360,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(0, 10))
            return

        ui.label(
            parent,
            text="Rechargez un joueur en un clic pour reprendre son contexte recent.",
            fg=SUBTLE_TEXT,
            wraplength=360,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(0, 10))

        buttons = ui.frame(parent, bg=parent.cget("bg"))
        buttons.pack(fill="x", pady=(0, 10))
        for index, recent_player in enumerate(recent_players[:6]):
            button = tk.Button(
                buttons,
                text=recent_player["name"],
                width=16,
                command=lambda player_id=recent_player["id"]: app._select_recent_player(player_id),
            )
            button.grid(
                row=index // 2,
                column=index % 2,
                padx=(0, 8 if index % 2 == 0 else 0),
                pady=4,
                sticky="ew",
            )

        buttons.grid_columnconfigure(0, weight=1)
        buttons.grid_columnconfigure(1, weight=1)

    def _render_menu_form(self, app, parent):
        ui = app.ui
        ui.section_title(parent, "Lancer une manche")
        ui.label(
            parent,
            text=(
                "Entrez un pseudo, choisissez une categorie et un niveau, puis lancez la manche. "
                "Un profil existant conserve deja historique, objectifs et dernieres parties."
            ),
            fg=SUBTLE_TEXT,
            wraplength=360,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(0, 12))

        if app.banner_var.get():
            banner = ui.card(parent, bg=SUCCESS_BG, border=SUCCESS_COLOR, padx=12, pady=10)
            banner.pack(fill="x", pady=(0, 12))
            ui.label(
                banner,
                textvariable=app.banner_var,
                bg=SUCCESS_BG,
                fg=SUCCESS_COLOR,
                wraplength=340,
                justify="left",
            ).pack(anchor="w")

        form = ui.frame(parent)
        form.pack(fill="x")
        ui.label(form, text="Pseudo").grid(row=0, column=0, sticky="w", pady=6)
        app.player_name_entry = tk.Entry(form, textvariable=app.player_name_var, width=28)
        app.player_name_entry.grid(row=0, column=1, sticky="ew", pady=6)
        ui.label(form, text="Categorie").grid(row=1, column=0, sticky="w", pady=6)
        app.category_display_var.set(app._get_category_display_name(app.category_var.get()))
        category_menu = tk.OptionMenu(
            form,
            app.category_display_var,
            *app.category_labels.keys(),
            command=app.on_category_selected,
        )
        category_menu.config(width=22)
        category_menu.grid(row=1, column=1, sticky="ew", pady=6)
        ui.label(form, text="Difficulte").grid(row=2, column=0, sticky="w", pady=6)
        app.difficulty_menu = tk.OptionMenu(
            form,
            app.difficulty_var,
            app.difficulty_var.get(),
            command=app.on_difficulty_selected,
        )
        app.difficulty_menu.config(width=22)
        app.difficulty_menu.grid(row=2, column=1, sticky="ew", pady=6)
        form.grid_columnconfigure(1, weight=1)
        app.refresh_difficulty_options()

        hint_card = ui.card(parent, bg="#f7f9fc", border="#d7deea", padx=12, pady=12)
        hint_card.pack(fill="x", pady=(14, 0))
        ui.label(
            hint_card,
            text="Ce que garantit ce reglage",
            bg="#f7f9fc",
            fg=ACCENT_COLOR,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")
        ui.label(
            hint_card,
            textvariable=app.category_hint_var,
            bg="#f7f9fc",
            wraplength=340,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(6, 0))
        self._render_catalog_card(app, parent)

    def _render_resume_panel(self, app, parent, dashboard, progression):
        ui = app.ui
        ui.section_title(parent, "Reprise rapide")
        ui.label(
            parent,
            text=app._build_player_summary(app.player),
            wraplength=330,
            justify="left",
        ).pack(anchor="w", fill="x")

        latest_game = app._get_latest_game(dashboard)
        if latest_game is not None:
            ui.label(
                parent,
                text=(
                    "Dernier reglage : "
                    f"{format_category_name(latest_game['category'])} en {latest_game['difficulty']} "
                    f"({format_played_at(latest_game['played_at'])}, "
                    f"{'victoire' if latest_game['won'] else 'defaite'})."
                ),
                fg=ACCENT_COLOR,
                wraplength=330,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))

        featured_challenge = progression.get("featured_challenge")
        if featured_challenge is not None:
            ui.label(
                parent,
                text=(
                    "Defi du moment : "
                    f"{featured_challenge['title']} sur "
                    f"{format_category_name(featured_challenge['category'])} en {featured_challenge['difficulty']}."
                    if featured_challenge.get("category") and featured_challenge.get("difficulty")
                    else f"Defi du moment : {featured_challenge['title']}."
                ),
                fg=ACCENT_COLOR,
                wraplength=330,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(10, 0))

        ui.section_title(parent, "Defis actifs")
        ui.render_challenge_cards(parent, progression.get("challenges", ()), limit=2, compact=True)
        ui.section_title(parent, "Objectifs actifs")
        ui.render_goal_cards(parent, progression["goals"], limit=2, compact=True)

    def _render_onboarding_panel(self, app, parent):
        ui = app.ui
        ui.section_title(parent, "Parcours solo")
        ui.render_bullets(
            parent,
            [
                "Choisir ou recharger un profil local.",
                "Lancer une manche avec un pool calibre par categorie et difficulte.",
                "Lire ensuite le score, les defis du moment et la progression globale.",
            ],
            wraplength=320,
        )
        ui.label(
            parent,
            text=(
                "Le produit reste centre sur le solo local, mais l'accueil met maintenant en avant "
                "la reprise, les recommandations et la profondeur deja calculee."
            ),
            fg=SUBTLE_TEXT,
            wraplength=320,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(12, 0))

    def _render_main_menu_actions(self, app, parent, dashboard, progression):
        buttons = app.ui.frame(parent, bg=APP_BG)
        buttons.pack(fill="x", pady=(16, 0))
        tk.Button(buttons, text="Lancer une partie", command=app.start_game, width=18).pack(
            side="left",
            padx=(0, 8),
        )
        if dashboard is not None and app._get_latest_game(dashboard) is not None:
            tk.Button(
                buttons,
                text="Reprendre dernier reglage",
                command=app.start_last_selection,
                width=24,
            ).pack(side="left", padx=(0, 8))
        if progression is not None and progression.get("featured_challenge") is not None:
            tk.Button(
                buttons,
                text="Session defi",
                command=app.start_guided_featured_challenge_session,
                width=16,
            ).pack(side="left", padx=(0, 8))
        if progression is not None and progression.get("primary_goal") is not None:
            tk.Button(
                buttons,
                text="Session objectif",
                command=app.start_guided_primary_goal_session,
                width=18,
            ).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="Profil", command=app.open_player_dashboard, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(buttons, text="Classement", command=app.show_leaderboard, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(buttons, text="Quitter", command=app.close, width=12).pack(side="left")
