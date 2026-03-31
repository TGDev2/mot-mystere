from datetime import datetime
import tkinter as tk
from tkinter import messagebox

from categories import get_category_difficulty_breakdown, load_categories
from database import (
    get_leaderboard_data,
    get_or_create_player,
    get_player_dashboard,
    record_game_result,
)
from game_session import GameSession
from scoring import DIFFICULTY_CONFIG, build_score_breakdown


def format_category_name(category_key):
    return category_key.replace("_", " ").title()


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
        self.categories = load_categories()
        if not self.categories:
            raise RuntimeError("Aucune categorie n'est disponible.")

        self.root = tk.Tk()
        self.root.title("MotMystere")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.player = None
        self.session = None
        self.timer_job = None
        self.letter_buttons = {}
        self.category_labels = {format_category_name(key): key for key in self.categories}

        self.player_name_var = tk.StringVar()
        self.category_var = tk.StringVar(value=next(iter(self.categories)))
        self.category_display_var = tk.StringVar(
            value=format_category_name(self.category_var.get())
        )
        self.difficulty_var = tk.StringVar(value="Facile")
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
        for widget in self.root.winfo_children():
            widget.destroy()

    def show_main_menu(self, banner_message=""):
        self.clear_screen()
        self.banner_var.set(banner_message)
        self.update_category_hint()

        container = tk.Frame(self.root, padx=20, pady=20)
        container.pack()

        tk.Label(container, text="MotMystere", font=("Arial", 22, "bold")).pack(pady=(0, 6))
        tk.Label(
            container,
            text="Jeu solo calibre avec categories, score persistant et suivi joueur.",
            font=("Arial", 11),
            wraplength=420,
            justify="center",
        ).pack(pady=(0, 16))

        if self.banner_var.get():
            tk.Label(
                container,
                textvariable=self.banner_var,
                fg="#1f5c2e",
                justify="left",
                wraplength=420,
            ).pack(fill="x", pady=(0, 12))

        form = tk.Frame(container)
        form.pack(fill="x")

        tk.Label(form, text="Pseudo").grid(row=0, column=0, sticky="w", pady=6)
        tk.Entry(form, textvariable=self.player_name_var, width=28).grid(row=0, column=1, pady=6)

        tk.Label(form, text="Categorie").grid(row=1, column=0, sticky="w", pady=6)
        self.category_display_var.set(format_category_name(self.category_var.get()))
        tk.OptionMenu(
            form,
            self.category_display_var,
            *self.category_labels.keys(),
            command=self.on_category_selected,
        ).grid(row=1, column=1, sticky="ew", pady=6)

        tk.Label(form, text="Difficulte").grid(row=2, column=0, sticky="w", pady=6)
        tk.OptionMenu(
            form,
            self.difficulty_var,
            *DIFFICULTY_CONFIG.keys(),
            command=self.on_difficulty_selected,
        ).grid(row=2, column=1, sticky="ew", pady=6)

        tk.Label(
            container,
            textvariable=self.category_hint_var,
            fg="#1f3a93",
            justify="left",
            wraplength=420,
        ).pack(fill="x", pady=(10, 10))

        tk.Label(
            container,
            text=(
                "Le mode multijoueur reste experimental dans server.py et n'est pas "
                "expose dans cette version."
            ),
            fg="#555555",
            justify="left",
            wraplength=420,
        ).pack(fill="x", pady=(0, 10))

        if self.player is not None:
            self.progress_var.set(self._build_player_summary(self.player))
            tk.Label(
                container,
                textvariable=self.progress_var,
                justify="left",
                wraplength=420,
            ).pack(fill="x", pady=(0, 12))

        buttons = tk.Frame(container)
        buttons.pack(fill="x")

        tk.Button(buttons, text="Lancer une partie", command=self.start_game, width=18).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(buttons, text="Profil", command=self.open_player_dashboard, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(buttons, text="Classement", command=self.show_leaderboard, width=14).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(buttons, text="Quitter", command=self.close, width=12).pack(side="left")

    def on_category_selected(self, selected_display_name):
        if selected_display_name in self.category_labels:
            self.category_var.set(self.category_labels[selected_display_name])
        self.update_category_hint()

    def on_difficulty_selected(self, _selected_difficulty):
        self.update_category_hint()

    def update_category_hint(self):
        if self.category_display_var.get() in self.category_labels:
            self.category_var.set(self.category_labels[self.category_display_var.get()])

        breakdown = get_category_difficulty_breakdown(self.categories[self.category_var.get()])
        selected_difficulty = self.difficulty_var.get()
        total_words = sum(breakdown.values())
        selected_pool = breakdown.get(selected_difficulty, 0)
        self.category_hint_var.set(
            f"{format_category_name(self.category_var.get())} : {total_words} mots "
            f"(Facile {breakdown['Facile']}, Moyen {breakdown['Moyen']}, "
            f"Difficile {breakdown['Difficile']}). Le niveau {selected_difficulty} "
            f"utilisera {selected_pool} mot(s) calibres."
        )

    def _load_player_from_form(self):
        try:
            player = get_or_create_player(self.player_name_var.get())
        except ValueError as exc:
            messagebox.showerror("Pseudo invalide", str(exc))
            return None

        self.player = player
        self.player_name_var.set(player["name"])
        return player

    def open_player_dashboard(self):
        if self.player_name_var.get().strip():
            player = self._load_player_from_form()
            if player is None:
                return
        elif self.player is None:
            messagebox.showinfo("Profil", "Saisissez un pseudo pour afficher un profil.")
            return
        else:
            player = self.player

        self.show_player_dashboard(player["id"])

    def start_game(self):
        player = self._load_player_from_form()
        if player is None:
            return

        self.category_var.set(self.category_labels[self.category_display_var.get()])
        self.session = GameSession.create(
            self.categories,
            self.category_var.get(),
            self.difficulty_var.get(),
        )
        self.show_game_screen()

    def show_game_screen(self):
        self.clear_screen()
        self.letter_buttons = {}

        container = tk.Frame(self.root, padx=20, pady=20)
        container.pack()

        header_text = (
            f"Joueur : {self.player['name']}  |  "
            f"Categorie : {format_category_name(self.session.category)}  |  "
            f"Difficulte : {self.session.difficulty}"
        )
        tk.Label(container, text=header_text, font=("Arial", 10, "bold")).pack(pady=(0, 6))

        self.round_hint_var.set(
            f"Calibration : {self.session.word_profile.length} lettres, "
            f"complexite {self.session.word_complexity}, "
            f"timer {self.session.time_limit} s."
        )
        tk.Label(
            container,
            textvariable=self.round_hint_var,
            fg="#555555",
        ).pack(pady=(0, 10))

        tk.Label(container, textvariable=self.word_var, font=("Courier New", 24, "bold")).pack(
            pady=(0, 12)
        )
        tk.Label(container, textvariable=self.tried_letters_var).pack(pady=4)
        tk.Label(container, textvariable=self.attempts_var).pack(pady=4)
        tk.Label(container, textvariable=self.timer_var).pack(pady=4)
        tk.Label(container, textvariable=self.score_hint_var, fg="#1f3a93").pack(pady=(4, 8))
        tk.Label(
            container,
            textvariable=self.progress_var,
            justify="left",
            wraplength=420,
        ).pack(pady=(0, 8))
        tk.Label(container, textvariable=self.status_var, fg="#444444").pack(pady=(0, 12))

        keyboard = tk.Frame(container)
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

        actions = tk.Frame(container)
        actions.pack(fill="x", pady=(14, 0))

        tk.Button(actions, text="Retour au menu", command=self.return_to_menu, width=16).pack(
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

        self.status_var.set("Proposez une lettre.")
        self.refresh_game_view()
        self.schedule_timer()

    def refresh_game_view(self):
        self.word_var.set(self.session.revealed_word)
        tried_letters = ", ".join(self.session.letters_tried) or "Aucune"
        self.tried_letters_var.set(f"Lettres proposees : {tried_letters}")
        self.attempts_var.set(f"Essais restants : {self.session.attempts_left}")
        self.timer_var.set(f"Temps restant : {self.session.time_remaining} s")

        potential_score = build_score_breakdown(
            self.session.difficulty,
            self.session.word_profile.length,
            self.session.attempts_left,
            self.session.time_remaining,
            word_complexity=self.session.word_complexity,
            time_limit=self.session.time_limit,
        )["total"]
        self.score_hint_var.set(
            f"Score potentiel : {potential_score} pts si vous gagnez maintenant."
        )
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

        won = reason == "won"
        score_earned = 0
        score_summary = "Score gagne : 0"

        if won:
            breakdown = build_score_breakdown(
                self.session.difficulty,
                self.session.word_profile.length,
                self.session.attempts_left,
                self.session.time_remaining,
                word_complexity=self.session.word_complexity,
                time_limit=self.session.time_limit,
            )
            score_earned = breakdown["total"]
            score_summary = (
                "Score gagne : "
                f"{score_earned} (base {breakdown['base_points']}, "
                f"mot {breakdown['word_bonus']}, "
                f"complexite {breakdown['complexity_bonus']}, "
                f"essais {breakdown['attempts_bonus']}, "
                f"temps {breakdown['time_bonus']})"
            )

        self.player = record_game_result(
            self.player["id"],
            won=won,
            score_earned=score_earned,
            category=self.session.category,
            difficulty=self.session.difficulty,
            secret_word=self.session.secret_word,
            end_reason=reason,
            attempts_left=self.session.attempts_left,
            time_remaining=self.session.time_remaining,
            word_complexity=self.session.word_complexity,
        )
        self.progress_var.set(self._build_player_summary(self.player))

        if reason == "won":
            title = "Victoire"
            result_message = f"Vous avez trouve le mot : {self.session.secret_word}."
        elif reason == "time":
            title = "Temps ecoule"
            result_message = f"Le temps est termine. Le mot etait : {self.session.secret_word}."
        else:
            title = "Partie perdue"
            result_message = f"Vous n'avez plus d'essais. Le mot etait : {self.session.secret_word}."

        message = (
            f"{result_message}\n\n"
            f"{score_summary}\n"
            f"{self._build_player_summary(self.player)}\n\n"
            "Rejouer avec le meme profil ?"
        )

        if messagebox.askyesno(title, message):
            self.session = GameSession.create(
                self.categories,
                self.category_var.get(),
                self.difficulty_var.get(),
            )
            self.show_game_screen()
            return

        self.show_main_menu(
            banner_message=f"Dernier resultat : {result_message} {score_summary}"
        )

    def return_to_menu(self):
        self.show_main_menu()

    def show_player_dashboard(self, player_id):
        dashboard = get_player_dashboard(player_id)
        if dashboard is None:
            messagebox.showerror("Profil", "Le profil demande est introuvable.")
            return

        self.player = dashboard["player"]
        self.player_name_var.set(self.player["name"])
        self.progress_var.set(self._build_player_summary(self.player))

        profile_window = tk.Toplevel(self.root)
        profile_window.title(f"Profil - {self.player['name']}")
        profile_window.resizable(False, False)

        container = tk.Frame(profile_window, padx=14, pady=14)
        container.pack()

        tk.Label(
            container,
            text=f"Profil de {self.player['name']}",
            font=("Arial", 18, "bold"),
        ).pack(pady=(0, 10))

        overview = dashboard["overview"]
        recent_form = dashboard["recent_form"]
        summary_lines = [
            self._build_player_summary(self.player),
            (
                f"Score moyen par manche : {overview['average_score']} pts. "
                f"Pic sur une manche : {overview['peak_round_score']} pts."
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

        for line in summary_lines:
            tk.Label(
                container,
                text=line,
                justify="left",
                wraplength=520,
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
            tk.Label(
                container,
                text="Points de progression",
                font=("Arial", 12, "bold"),
            ).pack(pady=(14, 6))
            for line in insight_lines:
                tk.Label(
                    container,
                    text=line,
                    justify="left",
                    wraplength=520,
                ).pack(fill="x", pady=2)

        tk.Label(
            container,
            text="Dernieres parties",
            font=("Arial", 12, "bold"),
        ).pack(pady=(14, 6))

        table = tk.Frame(container)
        table.pack()

        headers = ["#", "Resultat", "Categorie", "Niveau", "Score", "Fin", "Date"]
        for index, header in enumerate(headers):
            tk.Label(table, text=header, font=("Arial", 10, "bold")).grid(
                row=0,
                column=index,
                padx=6,
                pady=4,
            )

        if not dashboard["recent_games"]:
            tk.Label(table, text="Aucune partie enregistree.").grid(
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
                    tk.Label(table, text=value).grid(
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
        leaderboard = tk.Toplevel(self.root)
        leaderboard.title("Classement")
        leaderboard.resizable(False, False)

        container = tk.Frame(leaderboard, padx=14, pady=14)
        container.pack()

        tk.Label(container, text="Classement solo", font=("Arial", 18, "bold")).grid(
            row=0,
            column=0,
            columnspan=6,
            pady=(0, 8),
        )
        tk.Label(
            container,
            text="Tri par score total, puis meilleur score.",
            fg="#555555",
        ).grid(row=1, column=0, columnspan=6, pady=(0, 12))

        headers = ["#", "Joueur", "Score total", "Meilleur", "Victoires", "Taux"]
        for index, header in enumerate(headers):
            tk.Label(container, text=header, font=("Arial", 10, "bold")).grid(
                row=2,
                column=index,
                padx=6,
                pady=4,
            )

        if not rows:
            tk.Label(container, text="Aucune donnee disponible.").grid(
                row=3,
                column=0,
                columnspan=6,
                pady=8,
            )
        else:
            for row_index, player in enumerate(rows, start=3):
                values = [
                    row_index - 2,
                    player["name"],
                    player["score_total"],
                    player["best_score"],
                    player["games_won"],
                    f"{player['win_rate']} %",
                ]
                for column_index, value in enumerate(values):
                    tk.Label(container, text=value).grid(
                        row=row_index,
                        column=column_index,
                        padx=6,
                        pady=3,
                    )

        tk.Button(container, text="Fermer", command=leaderboard.destroy, width=14).grid(
            row=len(rows) + 4,
            column=0,
            columnspan=6,
            pady=(14, 0),
        )

    def _build_player_summary(self, player):
        return (
            f"Progression de {player['name']} : "
            f"{player['score_total']} pts au total, "
            f"meilleur score {player['best_score']}, "
            f"{player['games_won']} victoire(s) sur {player['games_played']} partie(s), "
            f"taux {player['win_rate']} %."
        )
