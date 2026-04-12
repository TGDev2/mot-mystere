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
)


class MainMenuScreen:
    def render(self, app, *, banner_message=""):
        app.clear_screen()
        app.banner_var.set(banner_message)

        recent_players = app._load_recent_players()
        dashboard, progression = app._get_progression_bundle() if app.player is not None else (None, None)
        exploration_snapshot = app._build_catalog_exploration_snapshot()
        action_plan = app._build_surface_action_plan(
            dashboard,
            progression,
            surface="home",
        )
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
        self._render_priority_panel(app, right, action_plan)

        if progression is not None:
            self._render_player_context(app, right, dashboard, progression, exploration_snapshot)
        else:
            self._render_onboarding_panel(app, right, exploration_snapshot)

        self._render_utility_zone(app, container, action_plan)

        footer = ui.frame(container, bg=APP_BG)
        footer.pack(fill="x", pady=(14, 0))
        tk.Button(footer, text="Quitter", command=app.close, width=12).pack(anchor="w")

        app.player_name_entry.focus_set()
        app.root.bind("<Return>", app.on_main_menu_return)
        app.update_category_hint()

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
        app.selected_exploration_mount = ui.frame(parent, bg=parent.cget("bg"))
        app.selected_exploration_mount.pack(fill="x")

    def _render_priority_panel(self, app, parent, action_plan):
        ui = app.ui
        ui.section_title(parent, "Action prioritaire")
        ui.render_surface_action_card(
            parent,
            action_plan.get("primary_action"),
            command=app._get_action_callback(action_plan["primary_action"]["callback_id"]),
            compact=True,
        )
        secondary_actions = action_plan.get("secondary_actions") or ()
        if secondary_actions:
            ui.section_title(parent, "Autres options")
            ui.render_action_list(
                parent,
                secondary_actions,
                command_resolver=app._get_action_callback,
                compact=True,
            )

    def _render_player_context(self, app, parent, dashboard, progression, exploration_snapshot):
        ui = app.ui
        ui.section_title(parent, "Reperes joueur")
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
                    "Derniere manche : "
                    f"{format_category_name(latest_game['category'])} en {latest_game['difficulty']} "
                    f"({format_played_at(latest_game['played_at'])}, "
                    f"{'victoire' if latest_game['won'] else 'defaite'})."
                ),
                fg=ACCENT_COLOR,
                wraplength=330,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))

        mastery = progression["mastery"]
        ui.section_title(parent, "Carte de maitrise")
        ui.label(
            parent,
            text=(
                f"Maitrise globale : {mastery['mastery_percent']} %. "
                f"{mastery['mastered_pairs']}/{mastery['total_pairs']} paires maitrisees, "
                f"{mastery['pairs_left_to_master']} restantes."
            ),
            fg=ACCENT_COLOR,
            wraplength=330,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(0, 8))
        ui.section_title(parent, "Exploration du catalogue")
        ui.render_catalog_exploration_grid(parent, exploration_snapshot["grid"], compact=True)
        ui.section_title(parent, "Defis actifs")
        ui.render_challenge_cards(parent, progression.get("challenges", ()), limit=2, compact=True)
        ui.section_title(parent, "Objectifs actifs")
        ui.render_goal_cards(parent, progression["goals"], limit=2, compact=True)

    def _render_onboarding_panel(self, app, parent, exploration_snapshot):
        ui = app.ui
        ui.section_title(parent, "Avant la premiere manche")
        ui.render_bullets(
            parent,
            [
                "Choisir un pseudo local ou recharger un profil recent.",
                "Verifier le reglage categorie / difficulte deja affiche dans le formulaire.",
                "Lancer la premiere manche puis laisser la priorisation guider la suite.",
            ],
            wraplength=320,
        )
        ui.section_title(parent, "Exploration du catalogue")
        ui.label(
            parent,
            text=exploration_snapshot["empty_message"],
            fg=ACCENT_COLOR,
            wraplength=320,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(0, 10))
        ui.label(
            parent,
            text=(
                "La maintenance et les outils experts restent accessibles plus bas, "
                "sans couper le parcours de jeu principal."
            ),
            fg=SUBTLE_TEXT,
            wraplength=320,
            justify="left",
        ).pack(anchor="w", fill="x")

    def _render_utility_zone(self, app, parent, action_plan):
        ui = app.ui
        utility = ui.card(parent, bg=MUTED_BG, border="#d7d0c1", padx=18, pady=18)
        utility.pack(fill="x", pady=(16, 0))
        ui.section_title(utility, "Utilitaires")
        ui.label(
            utility,
            text=(
                "Profil, classement et maintenance restent accessibles ici, hors de la boucle "
                "principale comprendre -> lancer -> progresser."
            ),
            fg=SUBTLE_TEXT,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(0, 8))
        ui.label(
            utility,
            text=app._build_catalog_summary(),
            fg=ACCENT_COLOR,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(0, 8))
        ui.render_utility_actions(
            utility,
            action_plan.get("utility_actions"),
            command_resolver=app._get_action_callback,
        )
