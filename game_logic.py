from datetime import datetime
import tkinter as tk
from tkinter import messagebox

from categories import (
    MIN_WORD_POOL_SIZE,
    format_category_name,
    get_category_difficulty_breakdown,
    load_runtime_category_catalog,
)
from database import get_leaderboard_data, get_recent_players
from scoring import build_score_breakdown
from solo_game_service import (
    build_guided_objective,
    build_guided_recommendation,
    create_session_for_player,
    evaluate_guided_objective,
    get_progression_bundle,
    prepare_player,
    resolve_round,
)

APP_BG = "#f3efe6"
CARD_BG = "#fffdf9"
HERO_BG = "#e8f0ff"
MUTED_BG = "#f6f4ef"
ACCENT_COLOR = "#204d9b"
ACCENT_BORDER = "#9ab4e5"
SUCCESS_COLOR = "#1f6b4f"
SUCCESS_BG = "#e9f7f0"
WARNING_COLOR = "#9a6a13"
WARNING_BG = "#fff4da"
ERROR_COLOR = "#8b2f2f"
ERROR_BG = "#fdecec"
TEXT_COLOR = "#1f2430"
SUBTLE_TEXT = "#5b6270"


def format_end_reason(reason):
    mapping = {
        "won": "mot trouve",
        "attempts": "plus d'essais",
        "time": "temps ecoule",
    }
    return mapping.get(reason, str(reason))


def format_played_at(value):
    if not value:
        return "-"

    try:
        parsed = datetime.fromisoformat(str(value).replace(" ", "T"))
    except ValueError:
        return str(value)
    return parsed.strftime("%d/%m %H:%M")


class HangmanApp:
    def __init__(self):
        self.catalog = load_runtime_category_catalog()
        self.categories = dict(self.catalog.categories)
        self.category_availability = dict(self.catalog.category_availability)
        if not self.categories:
            raise RuntimeError("Aucune categorie exploitable n'est disponible.")

        self.root = tk.Tk()
        self.root.title("MotMystere")
        self.root.resizable(False, False)
        self.root.configure(bg=APP_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.player = None
        self.session = None
        self.guided_session = None
        self.timer_job = None
        self.letter_buttons = {}
        self.category_display_names = dict(self.catalog.display_names)
        self.category_labels = self._build_category_label_map()

        first_category = next(iter(self.categories))
        first_difficulty = self.category_availability[first_category][0]

        self.player_name_var = tk.StringVar()
        self.category_var = tk.StringVar(value=first_category)
        self.category_display_var = tk.StringVar(value=self._get_category_display_name(first_category))
        self.difficulty_var = tk.StringVar(value=first_difficulty)
        self.banner_var = tk.StringVar()
        self.word_var = tk.StringVar()
        self.tried_letters_var = tk.StringVar()
        self.attempts_var = tk.StringVar()
        self.timer_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.progress_var = tk.StringVar()
        self.score_hint_var = tk.StringVar()
        self.category_hint_var = tk.StringVar()
        self.round_hint_var = tk.StringVar()

        self.player_name_entry = None
        self.difficulty_menu = None
        self.primary_goal_snapshot = None

        self.show_main_menu()

    def run(self):
        self.root.mainloop()

    def close(self):
        self.cancel_timer()
        self.root.destroy()

    def cancel_timer(self):
        if self.timer_job is not None:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None

    def clear_screen(self):
        self.cancel_timer()
        self.root.unbind("<Return>")
        self.root.unbind("<Key>")
        for widget in self.root.winfo_children():
            widget.destroy()

    def _get_category_display_name(self, category_key):
        return self.category_display_names.get(
            category_key,
            format_category_name(category_key),
        )

    def _build_category_label_map(self):
        counts = {}
        for key in self.categories:
            label = self._get_category_display_name(key)
            counts[label] = counts.get(label, 0) + 1

        labels = {}
        for key in self.categories:
            label = self._get_category_display_name(key)
            if counts[label] > 1:
                label = f"{label} [{key}]"
            labels[label] = key
        return labels

    def _build_catalog_summary(self):
        local_packs = [
            pack
            for pack in self.catalog.pack_summaries
            if pack.origin == "local"
        ]
        active_local = sum(1 for pack in local_packs if pack.status == "active")
        disabled_local = sum(1 for pack in local_packs if pack.status == "disabled")
        invalid_local = sum(1 for pack in local_packs if pack.status == "invalid")
        if self.catalog.local_pack_dir is not None:
            example_manifest = self.catalog.local_pack_dir / "<nom_du_pack>" / "pack.json"
        else:
            example_manifest = "packs/<nom_du_pack>/pack.json"
        return (
            f"{len(self.categories)} categorie(s) jouables chargees. "
            f"Packs locaux : {active_local} actif(s), {disabled_local} desactive(s), {invalid_local} invalide(s). "
            f"Ajoutez vos packs dans {example_manifest}."
        )

    def _build_catalog_issue_lines(self, limit=3):
        visible_issues = list(self.catalog.issues)
        lines = [issue.message for issue in visible_issues[:limit]]
        remaining = max(0, len(visible_issues) - len(lines))
        if remaining:
            lines.append(f"{remaining} autre(s) alerte(s) catalogue a verifier.")
        return lines

    def _render_catalog_card(self, parent):
        issue_lines = self._build_catalog_issue_lines()
        has_issue = bool(issue_lines)
        bg = WARNING_BG if has_issue else MUTED_BG
        border = WARNING_COLOR if has_issue else ACCENT_BORDER
        fg = WARNING_COLOR if has_issue else ACCENT_COLOR

        card = self._card(parent, bg=bg, border=border, padx=12, pady=12)
        card.pack(fill="x", pady=(14, 0))
        self._label(
            card,
            text="Catalogue local",
            bg=bg,
            fg=fg,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")
        self._label(
            card,
            text=self._build_catalog_summary(),
            bg=bg,
            fg=TEXT_COLOR,
            wraplength=340,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(6, 0))
        if issue_lines:
            self._render_bullets(card, issue_lines, fg=fg, wraplength=320)

    def _frame(self, parent, *, bg=None, **kwargs):
        return tk.Frame(parent, bg=bg or parent.cget("bg"), **kwargs)

    def _label(self, parent, *, text=None, textvariable=None, bg=None, fg=TEXT_COLOR, **kwargs):
        return tk.Label(
            parent,
            text=text,
            textvariable=textvariable,
            bg=bg or parent.cget("bg"),
            fg=fg,
            **kwargs,
        )

    def _card(self, parent, *, bg=CARD_BG, border=ACCENT_BORDER, padx=16, pady=16):
        return tk.Frame(
            parent,
            bg=bg,
            padx=padx,
            pady=pady,
            highlightthickness=1,
            highlightbackground=border,
            bd=0,
        )

    def _section_title(self, parent, text):
        self._label(
            parent,
            text=text,
            font=("Arial", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

    def _render_bullets(self, parent, lines, *, fg=TEXT_COLOR, wraplength=320):
        for line in lines:
            self._label(
                parent,
                text=f"- {line}",
                fg=fg,
                wraplength=wraplength,
                justify="left",
            ).pack(anchor="w", fill="x", pady=2)

    def _render_progress_bar(self, parent, ratio, *, fill=ACCENT_COLOR):
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

    def _render_progress_cards(self, parent, items, *, limit=3, compact=False):
        for item in items[:limit]:
            bg = SUCCESS_BG if item["completed"] else CARD_BG
            border = SUCCESS_COLOR if item["completed"] else ACCENT_BORDER
            card = self._card(parent, bg=bg, border=border, padx=12, pady=12)
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
            self._label(
                card,
                text=badge_text,
                fg=SUCCESS_COLOR if item["completed"] else ACCENT_COLOR,
                font=("Arial", 9, "bold"),
            ).pack(anchor="w")
            self._label(
                card,
                text=item["title"],
                font=("Arial", 11, "bold"),
                wraplength=320 if compact else 420,
                justify="left",
            ).pack(anchor="w", pady=(2, 2))
            self._label(
                card,
                text=item["progress_text"],
                font=("Arial", 10, "bold"),
            ).pack(anchor="w")
            self._render_progress_bar(
                card,
                item["ratio"],
                fill=SUCCESS_COLOR if item["completed"] else ACCENT_COLOR,
            )
            self._label(
                card,
                text=item["detail"],
                fg=SUBTLE_TEXT,
                wraplength=320 if compact else 420,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(6, 0))

    def _render_goal_cards(self, parent, goals, *, limit=3, compact=False):
        items = [dict(goal, kind="goal") for goal in goals]
        self._render_progress_cards(parent, items, limit=limit, compact=compact)

    def _render_challenge_cards(self, parent, challenges, *, limit=3, compact=False):
        items = [dict(challenge, kind="challenge") for challenge in challenges]
        self._render_progress_cards(parent, items, limit=limit, compact=compact)

    def _render_metric_cards(self, parent, metrics):
        row = self._frame(parent)
        row.pack(fill="x", pady=(0, 8))
        for index, metric in enumerate(metrics):
            card = self._card(
                row,
                bg=metric.get("bg", CARD_BG),
                border=metric.get("border", ACCENT_BORDER),
                padx=12,
                pady=10,
            )
            card.pack(side="left", fill="both", expand=True, padx=(0, 8 if index < len(metrics) - 1 else 0))
            self._label(
                card,
                text=metric["label"],
                fg=SUBTLE_TEXT,
                font=("Arial", 9, "bold"),
            ).pack(anchor="w")
            self._label(
                card,
                text=metric["value"],
                fg=metric.get("fg", TEXT_COLOR),
                font=("Arial", 14, "bold"),
            ).pack(anchor="w", pady=(2, 0))

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

    def _render_mastery_grid(self, parent, mastery, *, compact=False):
        if mastery is None:
            return

        legend = self._card(
            parent,
            bg="#f7f9fc" if compact else CARD_BG,
            border="#d7deea" if compact else ACCENT_BORDER,
            padx=12,
            pady=10,
        )
        legend.pack(fill="x", pady=(6, 0))
        self._label(
            legend,
            text=(
                "Lecture rapide : 0/1 = premiere validation, 1-2/3 = valide, "
                "3/3 = maitrise."
            ),
            fg=SUBTLE_TEXT,
            wraplength=320 if compact else 760,
            justify="left",
        ).pack(anchor="w", fill="x")

        table_card = self._card(
            parent,
            bg=CARD_BG if compact else "#fcfbf7",
            border=ACCENT_BORDER if compact else "#d7d0c1",
            padx=12,
            pady=12,
        )
        table_card.pack(fill="x", pady=(8, 0))
        table = self._frame(table_card, bg=table_card.cget("bg"))
        table.pack(fill="x")

        headers = ["Categorie", "F", "M", "D"]
        for column_index, header in enumerate(headers):
            self._label(
                table,
                text=header,
                bg=table.cget("bg"),
                fg=SUBTLE_TEXT,
                font=("Arial", 9, "bold"),
            ).grid(row=0, column=column_index, padx=4, pady=4, sticky="nsew")

        for row_index, row in enumerate(mastery["rows"], start=1):
            self._label(
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
                cell_card.grid(row=row_index, column=column_index, padx=3, pady=3, sticky="nsew")
                cell_text = cell["progress_text"] if compact else f"{cell['state_label']}\n{cell['progress_text']}"
                self._label(
                    cell_card,
                    text=cell_text,
                    bg=cell_bg,
                    fg=cell_fg,
                    font=("Arial", 8, "bold") if compact else ("Arial", 9, "bold"),
                    justify="center",
                ).pack()

        for column_index in range(len(headers)):
            table.grid_columnconfigure(column_index, weight=1)

    def _get_progression_bundle(self):
        if self.player is None:
            return None, None

        bundle = get_progression_bundle(self.player, self.category_availability)
        if bundle is None:
            return None, None

        return self._apply_progression_bundle(bundle)

    def _set_active_player(self, player):
        self.player = player
        self.player_name_var.set(player["name"])
        self.progress_var.set(self._build_player_summary(player))

    def _apply_progression_bundle(self, bundle, *, sync_recent_selection=False):
        if bundle is None:
            return None, None

        self._set_active_player(bundle["player"])
        dashboard = bundle["dashboard"]
        snapshot = bundle["snapshot"]
        self.primary_goal_snapshot = snapshot

        if sync_recent_selection:
            self._sync_selection_from_recent_game(self._get_latest_game(dashboard))

        return dashboard, snapshot

    def _get_latest_game(self, dashboard):
        recent_games = (dashboard or {}).get("recent_games") or ()
        return recent_games[0] if recent_games else None

    def _sync_selection_from_recent_game(self, recent_game):
        if not recent_game:
            return

        self._sync_selection_to(
            recent_game.get("category"),
            recent_game.get("difficulty"),
        )

    def _load_recent_players(self):
        return get_recent_players()

    def _select_recent_player(self, player_id):
        bundle = get_progression_bundle({"id": player_id}, self.category_availability)
        if bundle is None:
            messagebox.showerror("Profil", "Le profil demande est introuvable.")
            return

        self._apply_progression_bundle(bundle, sync_recent_selection=True)
        self.show_main_menu(banner_message=f"Profil recharge : {self.player['name']}.")

    def _sync_selection_from_goal(self, goal):
        if not goal:
            return

        self._sync_selection_to(goal.get("category"), goal.get("difficulty"))

    def _sync_selection_to(self, category, difficulty):
        if category in self.categories:
            self.category_var.set(category)
            self.category_display_var.set(self._get_category_display_name(category))

        self.refresh_difficulty_options()
        available_difficulties = self.get_available_difficulties(self.category_var.get())
        if difficulty in available_difficulties:
            self.difficulty_var.set(difficulty)
        elif available_difficulties:
            self.difficulty_var.set(available_difficulties[0])
        self.update_category_hint()

    def _build_guided_session_state(self, objective, dashboard, snapshot):
        objective_state = evaluate_guided_objective(
            objective,
            self.player,
            dashboard,
            snapshot,
        )
        recommendation = build_guided_recommendation(
            objective,
            self.player,
            dashboard,
            snapshot,
        )
        return {
            "objective": objective,
            "objective_state": objective_state,
            "initial_progress_text": objective_state["progress_text"],
            "rounds": [],
            "recommendation": recommendation,
            "status": "active",
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }

    def _start_guided_session(self, source):
        player = self._load_player_from_form()
        if player is None:
            return

        dashboard, snapshot = self._get_progression_bundle()
        objective = build_guided_objective(snapshot, source=source)
        if objective is None:
            messagebox.showinfo(
                "Session guidee",
                "Aucun objectif concret n'est disponible pour lancer une session guidee.",
            )
            return

        guided_session = self._build_guided_session_state(objective, dashboard, snapshot)
        recommendation = guided_session.get("recommendation")
        if recommendation is None or not recommendation.get("category") or not recommendation.get("difficulty"):
            messagebox.showinfo(
                "Session guidee",
                "La recommandation suivante n'est pas exploitable pour le moment.",
            )
            return

        self.guided_session = guided_session
        self._sync_selection_to(
            recommendation.get("category"),
            recommendation.get("difficulty"),
        )
        self._start_round(preserve_guided_session=True)

    def _continue_guided_session(self):
        if self.guided_session is None or self.guided_session.get("status") != "active":
            self.show_main_menu()
            return

        recommendation = self.guided_session.get("recommendation")
        if recommendation is None or not recommendation.get("category") or not recommendation.get("difficulty"):
            self.show_guided_session_summary()
            return

        self._sync_selection_to(
            recommendation.get("category"),
            recommendation.get("difficulty"),
        )
        self.replay_current_selection(preserve_guided_session=True)

    def _stop_guided_session_after_round(self):
        if self.guided_session is None:
            self.show_main_menu()
            return

        self.guided_session["status"] = "stopped"
        self.show_guided_session_summary()

    def stop_guided_session_from_game(self):
        self.guided_session = None
        self.session = None
        self.show_main_menu(banner_message="Session guidee arretee avant la fin de la manche.")

    def start_primary_goal(self):
        if self.player is not None and self.primary_goal_snapshot is None:
            _, self.primary_goal_snapshot = self._get_progression_bundle()

        if self.primary_goal_snapshot and self.primary_goal_snapshot.get("primary_goal"):
            self._sync_selection_from_goal(self.primary_goal_snapshot["primary_goal"])

        self.start_game()

    def start_featured_challenge(self):
        if self.player is not None and self.primary_goal_snapshot is None:
            _, self.primary_goal_snapshot = self._get_progression_bundle()

        if self.primary_goal_snapshot and self.primary_goal_snapshot.get("featured_challenge"):
            self._sync_selection_from_goal(self.primary_goal_snapshot["featured_challenge"])

        self.start_game()

    def start_guided_primary_goal_session(self):
        self._start_guided_session("primary_goal")

    def start_guided_featured_challenge_session(self):
        self._start_guided_session("featured_challenge")

    def start_last_selection(self):
        player = self.player
        dashboard = None

        if player is None:
            player = self._load_player_from_form(sync_recent_selection=True)
            if player is None:
                return
        else:
            dashboard, _ = self._get_progression_bundle()
            self._sync_selection_from_recent_game(self._get_latest_game(dashboard))

        if dashboard is None:
            dashboard, _ = self._get_progression_bundle()
        if self._get_latest_game(dashboard) is None:
            self.start_game()
            return

        self.start_game()

    def _render_recent_players_section(self, parent, recent_players):
        self._section_title(parent, "Profils recents")
        if not recent_players:
            self._label(
                parent,
                text="Aucun profil recent. Creez un pseudo puis lancez une premiere manche.",
                fg=SUBTLE_TEXT,
                wraplength=360,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(0, 10))
            return

        self._label(
            parent,
            text="Rechargez un joueur en un clic pour reprendre son contexte recent.",
            fg=SUBTLE_TEXT,
            wraplength=360,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(0, 10))

        buttons = self._frame(parent, bg=parent.cget("bg"))
        buttons.pack(fill="x", pady=(0, 10))
        for index, recent_player in enumerate(recent_players[:6]):
            button = tk.Button(
                buttons,
                text=recent_player["name"],
                width=16,
                command=lambda player_id=recent_player["id"]: self._select_recent_player(player_id),
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

    def _render_menu_form(self, parent):
        self._section_title(parent, "Lancer une manche")
        self._label(
            parent,
            text=(
                "Entrez un pseudo, choisissez une categorie et un niveau, puis lancez la manche. "
                "Un profil existant conserve deja historique, objectifs et dernieres parties."
            ),
            fg=SUBTLE_TEXT,
            wraplength=360,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(0, 12))

        if self.banner_var.get():
            banner = self._card(parent, bg=SUCCESS_BG, border=SUCCESS_COLOR, padx=12, pady=10)
            banner.pack(fill="x", pady=(0, 12))
            self._label(
                banner,
                textvariable=self.banner_var,
                bg=SUCCESS_BG,
                fg=SUCCESS_COLOR,
                wraplength=340,
                justify="left",
            ).pack(anchor="w")

        form = self._frame(parent)
        form.pack(fill="x")
        self._label(form, text="Pseudo").grid(row=0, column=0, sticky="w", pady=6)
        self.player_name_entry = tk.Entry(form, textvariable=self.player_name_var, width=28)
        self.player_name_entry.grid(row=0, column=1, sticky="ew", pady=6)
        self._label(form, text="Categorie").grid(row=1, column=0, sticky="w", pady=6)
        self.category_display_var.set(self._get_category_display_name(self.category_var.get()))
        category_menu = tk.OptionMenu(
            form,
            self.category_display_var,
            *self.category_labels.keys(),
            command=self.on_category_selected,
        )
        category_menu.config(width=22)
        category_menu.grid(row=1, column=1, sticky="ew", pady=6)
        self._label(form, text="Difficulte").grid(row=2, column=0, sticky="w", pady=6)
        self.difficulty_menu = tk.OptionMenu(
            form,
            self.difficulty_var,
            self.difficulty_var.get(),
            command=self.on_difficulty_selected,
        )
        self.difficulty_menu.config(width=22)
        self.difficulty_menu.grid(row=2, column=1, sticky="ew", pady=6)
        form.grid_columnconfigure(1, weight=1)
        self.refresh_difficulty_options()

        hint_card = self._card(parent, bg="#f7f9fc", border="#d7deea", padx=12, pady=12)
        hint_card.pack(fill="x", pady=(14, 0))
        self._label(
            hint_card,
            text="Ce que garantit ce reglage",
            bg="#f7f9fc",
            fg=ACCENT_COLOR,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")
        self._label(
            hint_card,
            textvariable=self.category_hint_var,
            bg="#f7f9fc",
            wraplength=340,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(6, 0))
        self._render_catalog_card(parent)

    def _render_resume_panel(self, parent, dashboard, progression):
        self._section_title(parent, "Reprise rapide")
        self._label(
            parent,
            text=self._build_player_summary(self.player),
            wraplength=330,
            justify="left",
        ).pack(anchor="w", fill="x")

        latest_game = self._get_latest_game(dashboard)
        if latest_game is not None:
            self._label(
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
            self._label(
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

        self._section_title(parent, "Defis actifs")
        self._render_challenge_cards(parent, progression.get("challenges", ()), limit=2, compact=True)
        self._section_title(parent, "Objectifs actifs")
        self._render_goal_cards(parent, progression["goals"], limit=2, compact=True)

    def _render_onboarding_panel(self, parent):
        self._section_title(parent, "Parcours solo")
        self._render_bullets(
            parent,
            [
                "Choisir ou recharger un profil local.",
                "Lancer une manche avec un pool calibre par categorie et difficulte.",
                "Lire ensuite le score, les defis du moment et la progression globale.",
            ],
            wraplength=320,
        )
        self._label(
            parent,
            text=(
                "Le produit reste centre sur le solo local, mais l'accueil met maintenant en avant "
                "la reprise, les recommandations et la profondeur deja calculee."
            ),
            fg=SUBTLE_TEXT,
            wraplength=320,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(12, 0))

    def _render_main_menu_actions(self, parent, dashboard, progression):
        buttons = self._frame(parent, bg=APP_BG)
        buttons.pack(fill="x", pady=(16, 0))
        tk.Button(buttons, text="Lancer une partie", command=self.start_game, width=18).pack(
            side="left",
            padx=(0, 8),
        )
        if dashboard is not None and self._get_latest_game(dashboard) is not None:
            tk.Button(
                buttons,
                text="Reprendre dernier reglage",
                command=self.start_last_selection,
                width=24,
            ).pack(side="left", padx=(0, 8))
        if progression is not None and progression.get("featured_challenge") is not None:
            tk.Button(
                buttons,
                text="Session defi",
                command=self.start_guided_featured_challenge_session,
                width=16,
            ).pack(side="left", padx=(0, 8))
        if progression is not None and progression.get("primary_goal") is not None:
            tk.Button(
                buttons,
                text="Session objectif",
                command=self.start_guided_primary_goal_session,
                width=18,
            ).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="Profil", command=self.open_player_dashboard, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(buttons, text="Classement", command=self.show_leaderboard, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(buttons, text="Quitter", command=self.close, width=12).pack(side="left")

    def show_main_menu(self, banner_message=""):
        self.clear_screen()
        self.banner_var.set(banner_message)

        recent_players = self._load_recent_players()
        dashboard, progression = self._get_progression_bundle() if self.player is not None else (None, None)
        container = self._frame(self.root, bg=APP_BG, padx=24, pady=24)
        container.pack(fill="both", expand=True)

        hero = self._card(container, bg=HERO_BG, border=ACCENT_BORDER, padx=20, pady=18)
        hero.pack(fill="x")
        self._label(
            hero,
            text="MotMystere",
            bg=HERO_BG,
            font=("Georgia", 24, "bold"),
        ).pack(anchor="w")
        self._label(
            hero,
            text=(
                "Experience solo desktop concue pour rejouer souvent : rotation durable des mots, "
                "progression de maitrise et choix toujours lisibles."
            ),
            bg=HERO_BG,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(6, 10))

        badges = self._frame(hero, bg=HERO_BG)
        badges.pack(fill="x")
        badge_texts = [
            f"{len(self.categories)} categories jouables",
            f"{len({value for values in self.category_availability.values() for value in values})} niveaux calibres",
            "score + profil + classement persistants",
        ]
        for index, text in enumerate(badge_texts):
            pill = self._card(badges, bg="#f9fbff", border="#c7d5ef", padx=12, pady=8)
            pill.pack(side="left", padx=(0, 8 if index < len(badge_texts) - 1 else 0))
            self._label(
                pill,
                text=text,
                bg="#f9fbff",
                fg=ACCENT_COLOR,
                font=("Arial", 9, "bold"),
            ).pack()

        body = self._frame(container, bg=APP_BG)
        body.pack(fill="x", pady=(16, 0))

        left = self._card(body, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        left.pack(side="left", fill="both", expand=True)
        right = self._card(body, bg=MUTED_BG, border="#d7d0c1", padx=18, pady=18)
        right.pack(side="left", fill="both", padx=(14, 0))
        self._render_recent_players_section(left, recent_players)
        self._render_menu_form(left)

        if progression is not None:
            mastery = progression["mastery"]
            self._render_resume_panel(right, dashboard, progression)
            self._section_title(right, "Carte de maitrise")
            self._label(
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
            self._render_mastery_grid(right, mastery, compact=True)
        else:
            self._render_onboarding_panel(right)

        self._render_main_menu_actions(container, dashboard, progression)

        self.player_name_entry.focus_set()
        self.root.bind("<Return>", self.on_main_menu_return)
        self.update_category_hint()

    def on_main_menu_return(self, _event):
        self.start_game()

    def on_category_selected(self, selected_display_name):
        if selected_display_name in self.category_labels:
            self.category_var.set(self.category_labels[selected_display_name])
        self.refresh_difficulty_options()
        self.update_category_hint()

    def on_difficulty_selected(self, _selected_difficulty):
        self.update_category_hint()

    def get_available_difficulties(self, category_key=None):
        key = category_key or self.category_var.get()
        return self.category_availability.get(key, tuple())

    def refresh_difficulty_options(self):
        available_difficulties = self.get_available_difficulties(self.category_var.get())
        if not available_difficulties:
            raise RuntimeError("La categorie selectionnee ne propose aucun niveau exploitable.")

        if self.difficulty_var.get() not in available_difficulties:
            self.difficulty_var.set(available_difficulties[0])

        menu = self.difficulty_menu["menu"]
        menu.delete(0, "end")
        for difficulty in available_difficulties:
            menu.add_command(
                label=difficulty,
                command=tk._setit(self.difficulty_var, difficulty, self.on_difficulty_selected),
            )

    def update_category_hint(self):
        selected_display_name = self.category_display_var.get()
        if selected_display_name in self.category_labels:
            self.category_var.set(self.category_labels[selected_display_name])

        breakdown = get_category_difficulty_breakdown(self.categories[self.category_var.get()])
        available_difficulties = self.get_available_difficulties(self.category_var.get())
        selected_difficulty = self.difficulty_var.get()
        total_words = sum(breakdown.values())
        selected_pool = breakdown.get(selected_difficulty, 0)
        available_text = ", ".join(available_difficulties)
        self.category_hint_var.set(
            f"{self._get_category_display_name(self.category_var.get())} propose {total_words} mots au total. "
            f"Le niveau {selected_difficulty} active un pool calibre de {selected_pool} mot(s). "
            f"Niveaux jouables : {available_text} "
            f"(minimum garanti : {MIN_WORD_POOL_SIZE}, pool solide vise : 15 mots par niveau)."
        )

    def _load_player_from_form(self, *, sync_recent_selection=False):
        try:
            player = prepare_player(self.player_name_var.get())
        except ValueError as exc:
            messagebox.showerror("Pseudo invalide", str(exc))
            return None

        bundle = get_progression_bundle(player, self.category_availability)
        if bundle is None:
            self._set_active_player(player)
            return player

        self._apply_progression_bundle(bundle, sync_recent_selection=sync_recent_selection)
        return self.player

    def open_player_dashboard(self):
        if self.player_name_var.get().strip():
            player = self._load_player_from_form(sync_recent_selection=True)
            if player is None:
                return
        elif self.player is None:
            messagebox.showinfo("Profil", "Saisissez un pseudo pour afficher un profil.")
            return
        else:
            player = self.player

        self.show_player_dashboard(player["id"])

    def _create_session_for_current_selection(self):
        category = self.category_var.get()
        difficulty = self.difficulty_var.get()
        return create_session_for_player(
            self.player["id"],
            self.categories,
            category,
            difficulty,
        )

    def _start_round(self, *, preserve_guided_session=False):
        if not preserve_guided_session:
            self.guided_session = None

        player = self._load_player_from_form()
        if player is None:
            return

        selected_display_name = self.category_display_var.get()
        if selected_display_name in self.category_labels:
            self.category_var.set(self.category_labels[selected_display_name])

        try:
            self.session = self._create_session_for_current_selection()
        except ValueError as exc:
            messagebox.showerror("Partie indisponible", str(exc))
            self.refresh_difficulty_options()
            self.update_category_hint()
            return

        self.show_game_screen()

    def start_game(self):
        self._start_round()

    def replay_current_selection(self, *, preserve_guided_session=False):
        if self.player is None:
            self.show_main_menu()
            return

        if not preserve_guided_session:
            self.guided_session = None

        try:
            self.session = self._create_session_for_current_selection()
        except ValueError as exc:
            self.show_main_menu(banner_message=str(exc))
            return

        self.show_game_screen()

    def show_game_screen(self):
        self.clear_screen()
        self.letter_buttons = {}
        _, progression = self._get_progression_bundle()

        container = self._frame(self.root, bg=APP_BG, padx=24, pady=24)
        container.pack(fill="both", expand=True)

        hero = self._card(container, bg=HERO_BG, border=ACCENT_BORDER, padx=18, pady=16)
        hero.pack(fill="x")
        self._label(
            hero,
            text=(
                f"{self.player['name']} | {format_category_name(self.session.category)} | "
                f"{self.session.difficulty}"
            ),
            bg=HERO_BG,
            fg=ACCENT_COLOR,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w")

        self.round_hint_var.set(
            f"Mot de {self.session.word_profile.length} lettres, complexite "
            f"{self.session.word_complexity}, timer {self.session.time_limit} s."
        )
        self._label(
            hero,
            textvariable=self.round_hint_var,
            bg=HERO_BG,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(4, 6))
        if self.guided_session is not None and self.guided_session.get("status") == "active":
            objective_state = self.guided_session.get("objective_state") or {}
            self._label(
                hero,
                text=(
                    f"Session guidee en cours : {objective_state.get('title', '')} "
                    f"({objective_state.get('progress_text', '')})."
                ),
                bg=HERO_BG,
                fg=ACCENT_COLOR,
                font=("Arial", 10, "bold"),
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(0, 4))
        if progression is not None and progression.get("primary_goal") is not None:
            primary_goal = progression["primary_goal"]
            is_aligned = (
                primary_goal.get("category") == self.session.category
                and primary_goal.get("difficulty") == self.session.difficulty
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
            self._label(
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
                featured_challenge.get("category") == self.session.category
                and featured_challenge.get("difficulty") == self.session.difficulty
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
            self._label(
                hero,
                text=challenge_text,
                bg=HERO_BG,
                fg=SUCCESS_COLOR if is_challenge_aligned else SUBTLE_TEXT,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(4, 0))

        body = self._frame(container, bg=APP_BG)
        body.pack(fill="x", pady=(16, 0))

        left = self._card(body, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        left.pack(side="left", fill="both", expand=True)
        right = self._card(body, bg=MUTED_BG, border="#d7d0c1", padx=18, pady=18)
        right.pack(side="left", fill="both", padx=(14, 0))

        self._label(
            left,
            text="Clavier actif : tapez une lettre A-Z ou cliquez sur les boutons.",
            fg=ACCENT_COLOR,
            font=("Arial", 10, "bold"),
            wraplength=420,
            justify="left",
        ).pack(anchor="w", fill="x")
        self._label(
            left,
            textvariable=self.word_var,
            font=("Courier New", 28, "bold"),
        ).pack(pady=(18, 14))

        metrics = self._frame(left)
        metrics.pack(fill="x", pady=(0, 8))
        for index, (title, variable, bg, border, fg) in enumerate(
            [
                ("Essais restants", self.attempts_var, "#f7f9fc", "#d7deea", TEXT_COLOR),
                ("Temps", self.timer_var, "#fff7e8", "#ebd29a", TEXT_COLOR),
                ("Score si victoire", self.score_hint_var, "#eef6ff", "#c8d9f1", ACCENT_COLOR),
            ]
        ):
            card = self._card(metrics, bg=bg, border=border, padx=12, pady=10)
            card.pack(side="left", fill="both", expand=True, padx=(0, 8 if index < 2 else 0))
            self._label(
                card,
                text=title,
                bg=bg,
                fg=SUBTLE_TEXT,
                font=("Arial", 9, "bold"),
            ).pack(anchor="w")
            self._label(
                card,
                textvariable=variable,
                bg=bg,
                fg=fg,
                font=("Arial", 14, "bold"),
            ).pack(anchor="w", pady=(2, 0))

        status_card = self._card(left, bg="#f7f9fc", border="#d7deea", padx=12, pady=12)
        status_card.pack(fill="x", pady=(4, 12))
        self._label(
            status_card,
            textvariable=self.tried_letters_var,
            bg="#f7f9fc",
            wraplength=420,
            justify="left",
        ).pack(anchor="w")
        self._label(
            status_card,
            textvariable=self.status_var,
            bg="#f7f9fc",
            fg=SUBTLE_TEXT,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        keyboard = self._frame(left, bg=CARD_BG)
        keyboard.pack()
        for index, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            button = tk.Button(
                keyboard,
                text=letter,
                width=4,
                command=lambda selected=letter: self.handle_letter(selected),
            )
            button.grid(row=index // 6, column=index % 6, padx=2, pady=2)
            self.letter_buttons[letter] = button

        actions = self._frame(left, bg=CARD_BG)
        actions.pack(fill="x", pady=(14, 0))

        tk.Button(
            actions,
            text="Arreter la session" if self.guided_session is not None else "Changer de reglage",
            command=self.stop_guided_session_from_game if self.guided_session is not None else self.return_to_menu,
            width=18,
        ).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(actions, text="Profil", command=self.open_player_dashboard, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(actions, text="Classement", command=self.show_leaderboard, width=14).pack(
            side="left"
        )

        self._section_title(right, "Pourquoi cette manche compte")
        self._label(
            right,
            textvariable=self.progress_var,
            wraplength=320,
            justify="left",
        ).pack(anchor="w", fill="x")
        if progression is not None:
            self._section_title(right, "Defis du moment")
            self._render_challenge_cards(right, progression.get("challenges", ()), limit=2, compact=True)
            self._section_title(right, "Objectifs actifs")
            self._render_goal_cards(right, progression["goals"], limit=2, compact=True)

        self.status_var.set("Proposez une lettre.")
        self.refresh_game_view()
        self.root.bind("<Key>", self.on_game_keypress)
        self.schedule_timer()

    def on_game_keypress(self, event):
        if self.session is None or self.session.status != "in_progress":
            return

        focused_widget = self.root.focus_get()
        if focused_widget is not None and focused_widget.winfo_toplevel() is not self.root:
            return

        if event.keysym == "Escape":
            if self.guided_session is not None and self.guided_session.get("status") == "active":
                self.stop_guided_session_from_game()
            else:
                self.return_to_menu()
            return

        letter = str(event.char or "").strip().upper()
        if len(letter) == 1 and letter.isalpha():
            self.handle_letter(letter)

    def refresh_game_view(self):
        self.word_var.set(self.session.revealed_word)
        tried_letters = ", ".join(self.session.letters_tried) or "Aucune"
        self.tried_letters_var.set(f"Lettres proposees : {tried_letters}")
        self.attempts_var.set(str(self.session.attempts_left))
        self.timer_var.set(f"{self.session.time_remaining} s")

        potential_score = build_score_breakdown(
            self.session.difficulty,
            self.session.word_profile.length,
            self.session.attempts_left,
            self.session.time_remaining,
            word_complexity=self.session.word_complexity,
            time_limit=self.session.time_limit,
        )["total"]
        self.score_hint_var.set(f"{potential_score} pts")
        self.progress_var.set(self._build_player_summary(self.player))

    def schedule_timer(self):
        self.cancel_timer()
        self.timer_job = self.root.after(1000, self.on_timer_tick)

    def on_timer_tick(self):
        status = self.session.tick()
        self.refresh_game_view()
        if status == "in_progress":
            self.schedule_timer()
            return

        self.finish_round("time")

    def handle_letter(self, letter):
        result = self.session.guess(letter)
        if not result.was_valid:
            self.status_var.set("Veuillez choisir une lettre valide.")
            return

        if result.letter in self.letter_buttons:
            self.letter_buttons[result.letter].config(state=tk.DISABLED)

        if result.already_guessed:
            self.status_var.set(f"La lettre {result.letter} a deja ete proposee.")
        elif result.correct:
            self.status_var.set(f"Bonne reponse : {result.letter} est dans le mot.")
        else:
            self.status_var.set(f"{result.letter} n'est pas dans le mot.")

        self.refresh_game_view()

        if result.status == "won":
            self.finish_round("won")
        elif result.status == "lost":
            self.finish_round("attempts")

    def finish_round(self, reason):
        self.cancel_timer()
        for button in self.letter_buttons.values():
            button.config(state=tk.DISABLED)

        outcome = resolve_round(
            self.player,
            self.session,
            reason,
            self.category_availability,
        )
        self.player = outcome["player"]
        self.progress_var.set(self._build_player_summary(self.player))
        if outcome["progression_snapshot"] is not None:
            self.primary_goal_snapshot = outcome["progression_snapshot"]

        guided_progress = None
        guided_recommendation = None
        if self.guided_session is not None and self.guided_session.get("status") == "active":
            round_record = {
                "title": outcome["title"],
                "result_message": outcome["result_message"],
                "category": self.session.category,
                "difficulty": self.session.difficulty,
                "won": reason == "won",
                "end_reason": reason,
                "score_earned": outcome["score_earned"],
                "completed_goals": outcome["completed_goals"],
                "mastery_updates": outcome["mastery_updates"],
            }
            self.guided_session["rounds"].append(round_record)
            guided_progress = evaluate_guided_objective(
                self.guided_session["objective"],
                outcome["player"],
                outcome["dashboard"],
                outcome["progression_snapshot"],
            )
            guided_recommendation = build_guided_recommendation(
                self.guided_session["objective"],
                outcome["player"],
                outcome["dashboard"],
                outcome["progression_snapshot"],
            )
            self.guided_session["objective_state"] = guided_progress
            self.guided_session["recommendation"] = guided_recommendation
            if guided_progress is not None and guided_progress.get("completed"):
                self.guided_session["status"] = "completed"
                self.show_guided_session_summary()
                return

        self.show_round_summary(
            outcome["title"],
            outcome["result_message"],
            outcome["score_summary"],
            outcome["score_earned"],
            outcome["progression_snapshot"],
            outcome["completed_goals"],
            outcome["mastery_updates"],
            outcome["breakdown"],
            guided_progress=guided_progress,
            guided_recommendation=guided_recommendation,
        )

    def show_round_summary(
        self,
        title,
        result_message,
        score_summary,
        score_earned,
        progression_snapshot,
        completed_goals,
        mastery_updates,
        breakdown,
        *,
        guided_progress=None,
        guided_recommendation=None,
    ):
        self.clear_screen()
        tone_bg = SUCCESS_BG if title == "Victoire" else WARNING_BG if title == "Temps ecoule" else ERROR_BG
        tone_fg = SUCCESS_COLOR if title == "Victoire" else WARNING_COLOR if title == "Temps ecoule" else ERROR_COLOR

        container = self._frame(self.root, bg=APP_BG, padx=24, pady=24)
        container.pack(fill="both", expand=True)

        hero = self._card(container, bg=tone_bg, border=tone_fg, padx=20, pady=18)
        hero.pack(fill="x")
        self._label(
            hero,
            text=title,
            bg=tone_bg,
            fg=tone_fg,
            font=("Georgia", 24, "bold"),
        ).pack(anchor="w")
        self._label(
            hero,
            text=(
                f"{format_category_name(self.session.category)} | "
                f"{self.session.difficulty} | mot {self.session.secret_word}"
            ),
            bg=tone_bg,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", pady=(4, 6))
        self._label(
            hero,
            text=result_message,
            bg=tone_bg,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x")

        self._render_metric_cards(
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
                    "value": str(self.session.attempts_left),
                    "bg": "#f7f9fc",
                    "border": "#d7deea",
                },
                {
                    "label": "Temps restant",
                    "value": f"{self.session.time_remaining} s",
                    "bg": "#fff7e8",
                    "border": "#ebd29a",
                },
            ],
        )

        details = self._card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        details.pack(fill="x")
        self._section_title(details, "Impact sur la progression")
        self._label(
            details,
            text=score_summary,
            fg=ACCENT_COLOR if score_earned else SUBTLE_TEXT,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x")
        self._label(
            details,
            text=self._build_player_summary(self.player),
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(8, 0))
        if completed_goals:
            self._label(
                details,
                text="Nouvel objectif valide : " + ", ".join(goal["title"] for goal in completed_goals) + ".",
                fg=SUCCESS_COLOR,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))
        if mastery_updates:
            self._label(
                details,
                text="Nouveau palier de maitrise : " + ", ".join(update["title"] for update in mastery_updates) + ".",
                fg=SUCCESS_COLOR,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))
        if breakdown is not None:
            self._label(
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
            session_area = self._card(container, bg="#eef6ff", border="#c8d9f1", padx=18, pady=18)
            session_area.pack(fill="x", pady=(14, 0))
            self._section_title(session_area, "Session guidee")
            self._label(
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
                self._section_title(session_area, "Prochaine manche recommandee")
                self._label(
                    session_area,
                    text=recommendation_text,
                    font=("Arial", 11, "bold"),
                    wraplength=760,
                    justify="left",
                ).pack(anchor="w", fill="x")
                self._label(
                    session_area,
                    text=guided_recommendation["detail"],
                    wraplength=760,
                    justify="left",
                ).pack(anchor="w", fill="x", pady=(4, 0))

        if progression_snapshot is not None:
            goal_area = self._card(container, bg=MUTED_BG, border="#d7d0c1", padx=18, pady=18)
            goal_area.pack(fill="x", pady=(14, 0))
            self._section_title(goal_area, "Prochaine action recommandee")
            primary_goal = progression_snapshot["primary_goal"]
            if primary_goal is not None:
                self._label(
                    goal_area,
                    text=(
                        f"{primary_goal['title']} : {primary_goal['progress_text']}. "
                        f"{primary_goal['detail']}"
                    ),
                    wraplength=760,
                    justify="left",
                ).pack(anchor="w", fill="x", pady=(0, 8))
            mastery = progression_snapshot["mastery"]
            self._label(
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
                self._label(
                    goal_area,
                    text=(
                        f"Defi du moment : {featured_challenge['title']} "
                        f"({featured_challenge['progress_text']})."
                    ),
                    fg=ACCENT_COLOR,
                    wraplength=760,
                    justify="left",
                ).pack(anchor="w", fill="x", pady=(0, 8))
            self._render_mastery_grid(goal_area, mastery)
            self._section_title(goal_area, "Defis actifs")
            self._render_challenge_cards(
                goal_area,
                progression_snapshot.get("challenges", ()),
                limit=3,
            )
            self._section_title(goal_area, "Objectifs actifs")
            self._render_goal_cards(goal_area, progression_snapshot["goals"], limit=3)

        buttons = self._frame(container, bg=APP_BG)
        buttons.pack(fill="x", pady=(16, 0))

        if guided_progress is not None:
            tk.Button(
                buttons,
                text="Continuer la session",
                command=self._continue_guided_session,
                width=24,
            ).pack(side="left", padx=(0, 8))
            tk.Button(
                buttons,
                text="Arreter la session",
                command=self._stop_guided_session_after_round,
                width=20,
            ).pack(side="left", padx=(0, 8))
        else:
            tk.Button(
                buttons,
                text="Rejouer meme reglage",
                command=self.replay_current_selection,
                width=20,
            ).pack(side="left", padx=(0, 8))
            if progression_snapshot is not None and progression_snapshot.get("primary_goal") is not None:
                self.primary_goal_snapshot = progression_snapshot
                tk.Button(
                    buttons,
                    text="Session objectif",
                    command=self.start_guided_primary_goal_session,
                    width=18,
                ).pack(side="left", padx=(0, 8))
            tk.Button(
                buttons,
                text="Changer categorie",
                command=self.return_to_menu,
                width=18,
            ).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="Profil", command=self.open_player_dashboard, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(buttons, text="Classement", command=self.show_leaderboard, width=14).pack(
            side="left"
        )

        footer = self._frame(container, bg=APP_BG)
        footer.pack(fill="x", pady=(14, 0))
        tk.Button(footer, text="Quitter", command=self.close, width=12).pack()

        if guided_progress is not None:
            self.root.bind("<Return>", lambda _event: self._continue_guided_session())
        else:
            self.root.bind("<Return>", lambda _event: self.replay_current_selection())

    def show_guided_session_summary(self):
        if self.guided_session is None:
            self.show_main_menu()
            return

        self.clear_screen()
        objective_state = self.guided_session.get("objective_state") or self.guided_session["objective"]
        rounds = self.guided_session.get("rounds", ())
        completed = self.guided_session.get("status") == "completed"
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

        container = self._frame(self.root, bg=APP_BG, padx=24, pady=24)
        container.pack(fill="both", expand=True)

        hero = self._card(container, bg=tone_bg, border=tone_fg, padx=20, pady=18)
        hero.pack(fill="x")
        self._label(
            hero,
            text="Objectif atteint" if completed else "Session guidee interrompue",
            bg=tone_bg,
            fg=tone_fg,
            font=("Georgia", 24, "bold"),
        ).pack(anchor="w")
        self._label(
            hero,
            text=objective_state["title"],
            bg=tone_bg,
            font=("Arial", 11, "bold"),
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(4, 6))
        self._label(
            hero,
            text=(
                f"Progression session : {self.guided_session['initial_progress_text']} "
                f"-> {objective_state['progress_text']}."
            ),
            bg=tone_bg,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x")

        self._render_metric_cards(
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

        details = self._card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        details.pack(fill="x")
        self._section_title(details, "Resultat")
        self._label(
            details,
            text=objective_state["detail"],
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x")
        if rounds:
            last_round = rounds[-1]
            self._label(
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
            self._label(
                details,
                text="Objectifs valides pendant la session : " + ", ".join(goal_titles) + ".",
                fg=SUCCESS_COLOR,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))
        if mastery_titles:
            self._label(
                details,
                text="Paliers de maitrise atteints : " + ", ".join(mastery_titles) + ".",
                fg=SUCCESS_COLOR,
                wraplength=760,
                justify="left",
            ).pack(anchor="w", fill="x", pady=(8, 0))

        if rounds:
            rounds_card = self._card(container, bg=MUTED_BG, border="#d7d0c1", padx=18, pady=18)
            rounds_card.pack(fill="x", pady=(14, 0))
            self._section_title(rounds_card, "Trace de session")
            for round_index, round_data in enumerate(rounds, start=1):
                self._label(
                    rounds_card,
                    text=(
                        f"Manche {round_index} : {format_category_name(round_data['category'])} / "
                        f"{round_data['difficulty']} / {round_data['title']} / "
                        f"{round_data['score_earned']} pts"
                    ),
                    wraplength=760,
                    justify="left",
                ).pack(anchor="w", fill="x", pady=2)

        buttons = self._frame(container, bg=APP_BG)
        buttons.pack(fill="x", pady=(16, 0))
        if self.primary_goal_snapshot is not None and self.primary_goal_snapshot.get("primary_goal") is not None:
            tk.Button(
                buttons,
                text="Session objectif",
                command=self.start_guided_primary_goal_session,
                width=18,
            ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons,
            text="Retour accueil",
            command=self.return_to_menu,
            width=18,
        ).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="Profil", command=self.open_player_dashboard, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(buttons, text="Classement", command=self.show_leaderboard, width=14).pack(
            side="left"
        )

        self.root.bind("<Return>", lambda _event: self.return_to_menu())

    def return_to_menu(self):
        banner_message = ""
        if self.guided_session is not None and self.guided_session.get("status") == "active":
            banner_message = "Session guidee arretee."
        self.guided_session = None
        self.session = None
        self.show_main_menu(banner_message=banner_message)

    def show_player_dashboard(self, player_id):
        bundle = get_progression_bundle({"id": player_id}, self.category_availability)
        if bundle is None:
            messagebox.showerror("Profil", "Le profil demande est introuvable.")
            return

        dashboard, progression = self._apply_progression_bundle(
            bundle,
            sync_recent_selection=True,
        )

        profile_window = tk.Toplevel(self.root, bg=APP_BG)
        profile_window.title(f"Profil - {self.player['name']}")
        profile_window.resizable(False, False)

        container = self._frame(profile_window, bg=APP_BG, padx=18, pady=18)
        container.pack(fill="both", expand=True)

        header = self._card(container, bg=HERO_BG, border=ACCENT_BORDER, padx=18, pady=16)
        header.pack(fill="x")
        self._label(
            header,
            text=f"Profil de {self.player['name']}",
            bg=HERO_BG,
            font=("Georgia", 20, "bold"),
        ).pack(anchor="w")

        overview = dashboard["overview"]
        recent_form = dashboard["recent_form"]
        summary_lines = [
            self._build_player_summary(self.player),
            (
                f"Score moyen par manche : {overview['average_score']} pts. "
                f"Pic sur une manche : {overview['peak_round_score']} pts."
            ),
            (
                f"Maitrise globale : {progression['mastery']['mastery_percent']} %. "
                f"{progression['mastery']['mastered_pairs']}/{progression['mastery']['total_pairs']} "
                "paires maitrisees."
            ),
        ]
        if recent_form["recent_games"]:
            summary_lines.append(
                "Forme recente : "
                f"{recent_form['recent_wins']} victoire(s) sur les "
                f"{recent_form['recent_games']} dernieres parties."
            )
        else:
            summary_lines.append("Aucune manche enregistree pour l'instant.")

        summary_card = self._card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        summary_card.pack(fill="x", pady=(14, 0))
        self._section_title(summary_card, "Vue d'ensemble")
        for line in summary_lines:
            self._label(
                summary_card,
                text=line,
                justify="left",
                wraplength=760,
            ).pack(fill="x", pady=2)

        insight_lines = []
        if dashboard["best_difficulty"] is not None:
            best_difficulty = dashboard["best_difficulty"]
            insight_lines.append(
                "Niveau le plus rentable : "
                f"{best_difficulty['difficulty']} "
                f"({best_difficulty['average_score']} pts de moyenne, "
                f"{best_difficulty['win_rate']} % de victoires)."
            )
        if dashboard["favorite_category"] is not None:
            favorite_category = dashboard["favorite_category"]
            insight_lines.append(
                "Categorie la plus jouee : "
                f"{format_category_name(favorite_category['category'])} "
                f"({favorite_category['games_played']} partie(s), "
                f"{favorite_category['win_rate']} % de victoires)."
            )
        if dashboard["weakest_category"] is not None:
            weakest_category = dashboard["weakest_category"]
            insight_lines.append(
                "Categorie a travailler : "
                f"{format_category_name(weakest_category['category'])} "
                f"({weakest_category['win_rate']} % de victoires, "
                f"{weakest_category['average_score']} pts de moyenne)."
            )

        if insight_lines:
            insight_card = self._card(container, bg=MUTED_BG, border="#d7d0c1", padx=18, pady=18)
            insight_card.pack(fill="x", pady=(14, 0))
            self._label(
                insight_card,
                text="Points de progression",
                font=("Arial", 12, "bold"),
            ).pack(anchor="w", pady=(0, 6))
            for line in insight_lines:
                self._label(
                    insight_card,
                    text=line,
                    justify="left",
                    wraplength=760,
                ).pack(fill="x", pady=2)

        mastery_card = self._card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        mastery_card.pack(fill="x", pady=(14, 0))
        self._section_title(mastery_card, "Maitrise par categorie")
        self._label(
            mastery_card,
            text=(
                f"{progression['mastery']['validated_pairs']}/{progression['mastery']['total_pairs']} "
                "paires validees, "
                f"{progression['mastery']['pairs_left_to_validate']} a valider et "
                f"{progression['mastery']['pairs_left_to_master']} a maitriser."
            ),
            fg=ACCENT_COLOR,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", fill="x")
        self._render_mastery_grid(mastery_card, progression["mastery"])

        challenges_card = self._card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        challenges_card.pack(fill="x", pady=(14, 0))
        self._section_title(challenges_card, "Defis du moment")
        self._render_challenge_cards(challenges_card, progression.get("challenges", ()), limit=3)

        goals_card = self._card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        goals_card.pack(fill="x", pady=(14, 0))
        self._section_title(goals_card, "Objectifs actifs")
        self._render_goal_cards(goals_card, progression["goals"], limit=3)

        table_card = self._card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        table_card.pack(fill="x", pady=(14, 0))
        self._section_title(table_card, "Dernieres parties")

        table = self._frame(table_card)
        table.pack()

        headers = ["#", "Resultat", "Categorie", "Niveau", "Score", "Fin", "Date"]
        for index, header in enumerate(headers):
            self._label(table, text=header, font=("Arial", 10, "bold")).grid(
                row=0,
                column=index,
                padx=6,
                pady=4,
            )

        if not dashboard["recent_games"]:
            self._label(table, text="Aucune partie enregistree.").grid(
                row=1,
                column=0,
                columnspan=len(headers),
                pady=8,
            )
        else:
            for row_index, game in enumerate(dashboard["recent_games"], start=1):
                values = [
                    row_index,
                    "Victoire" if game["won"] else "Defaite",
                    format_category_name(game["category"]),
                    game["difficulty"],
                    game["score_earned"],
                    format_end_reason(game["end_reason"]),
                    format_played_at(game["played_at"]),
                ]
                for column_index, value in enumerate(values):
                    self._label(table, text=value).grid(
                        row=row_index,
                        column=column_index,
                        padx=6,
                        pady=3,
                    )

        tk.Button(container, text="Fermer", command=profile_window.destroy, width=14).pack(
            pady=(14, 0)
        )

    def show_leaderboard(self):
        rows = get_leaderboard_data()
        leaderboard = tk.Toplevel(self.root, bg=APP_BG)
        leaderboard.title("Classement")
        leaderboard.resizable(False, False)

        container = self._frame(leaderboard, bg=APP_BG, padx=18, pady=18)
        container.pack(fill="both", expand=True)

        header = self._card(container, bg=HERO_BG, border=ACCENT_BORDER, padx=18, pady=16)
        header.pack(fill="x")
        self._label(
            header,
            text="Classement solo",
            bg=HERO_BG,
            font=("Georgia", 20, "bold"),
        ).pack(anchor="w")
        self._label(
            header,
            text="Tri par score total, puis meilleur score et nombre de victoires.",
            bg=HERO_BG,
            fg=SUBTLE_TEXT,
        ).pack(anchor="w", pady=(4, 0))

        table_card = self._card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        table_card.pack(fill="x", pady=(14, 0))
        table = self._frame(table_card)
        table.pack()
        headers = ["#", "Joueur", "Score total", "Meilleur", "Victoires", "Taux"]
        for index, header in enumerate(headers):
            self._label(table, text=header, font=("Arial", 10, "bold")).grid(
                row=0,
                column=index,
                padx=6,
                pady=4,
            )

        if not rows:
            self._label(table, text="Aucune donnee disponible.").grid(
                row=1,
                column=0,
                columnspan=6,
                pady=8,
            )
        else:
            for row_index, player in enumerate(rows, start=1):
                row_bg = "#eef6ff" if self.player and player["id"] == self.player["id"] else CARD_BG
                values = [
                    row_index,
                    player["name"],
                    player["score_total"],
                    player["best_score"],
                    player["games_won"],
                    f"{player['win_rate']} %",
                ]
                for column_index, value in enumerate(values):
                    self._label(table, text=value, bg=row_bg).grid(
                        row=row_index,
                        column=column_index,
                        padx=6,
                        pady=3,
                    )

        tk.Button(container, text="Fermer", command=leaderboard.destroy, width=14).pack(
            pady=(14, 0)
        )

    def _build_player_summary(self, player):
        return (
            f"Progression de {player['name']} : "
            f"{player['score_total']} pts au total, "
            f"meilleur score {player['best_score']}, "
            f"{player['games_won']} victoire(s) sur {player['games_played']} partie(s), "
            f"taux {player['win_rate']} %."
        )
