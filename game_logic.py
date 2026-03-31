import tkinter as tk
from tkinter import messagebox

from categories import load_categories
from database import get_leaderboard_data, get_or_create_player, record_game_result
from game_session import GameSession
from scoring import DIFFICULTY_CONFIG, build_score_breakdown


def format_category_name(category_key):
    return category_key.replace("_", " ").title()


class HangmanApp:
    def __init__(self):
        self.categories = load_categories()
        if not self.categories:
            raise RuntimeError("Aucune catégorie n'est disponible.")

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

        container = tk.Frame(self.root, padx=20, pady=20)
        container.pack()

        tk.Label(container, text="MotMystere", font=("Arial", 22, "bold")).pack(pady=(0, 6))
        tk.Label(
            container,
            text="Version solo stabilisée du jeu du pendu.",
            font=("Arial", 11),
        ).pack(pady=(0, 16))

        if self.banner_var.get():
            tk.Label(
                container,
                textvariable=self.banner_var,
                fg="#1f5c2e",
                justify="left",
                wraplength=380,
            ).pack(fill="x", pady=(0, 12))

        form = tk.Frame(container)
        form.pack(fill="x")

        tk.Label(form, text="Pseudo").grid(row=0, column=0, sticky="w", pady=6)
        tk.Entry(form, textvariable=self.player_name_var, width=28).grid(row=0, column=1, pady=6)

        tk.Label(form, text="Catégorie").grid(row=1, column=0, sticky="w", pady=6)
        self.category_display_var.set(format_category_name(self.category_var.get()))
        tk.OptionMenu(form, self.category_display_var, *self.category_labels.keys()).grid(
            row=1,
            column=1,
            sticky="ew",
            pady=6,
        )

        tk.Label(form, text="Difficulté").grid(row=2, column=0, sticky="w", pady=6)
        tk.OptionMenu(form, self.difficulty_var, *DIFFICULTY_CONFIG.keys()).grid(
            row=2,
            column=1,
            sticky="ew",
            pady=6,
        )

        tk.Label(
            container,
            text="Le mode multijoueur reste expérimental dans server.py et n'est pas exposé dans cette version.",
            fg="#555555",
            justify="left",
            wraplength=380,
        ).pack(fill="x", pady=(14, 10))

        if self.player is not None:
            self.progress_var.set(self._build_player_summary(self.player))
            tk.Label(
                container,
                textvariable=self.progress_var,
                justify="left",
                wraplength=380,
            ).pack(fill="x", pady=(0, 12))

        buttons = tk.Frame(container)
        buttons.pack(fill="x")

        tk.Button(buttons, text="Lancer une partie", command=self.start_game, width=18).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(buttons, text="Classement", command=self.show_leaderboard, width=18).pack(
            side="left"
        )
        tk.Button(buttons, text="Quitter", command=self.close, width=12).pack(
            side="left",
            padx=(8, 0),
        )

    def start_game(self):
        try:
            player = get_or_create_player(self.player_name_var.get())
        except ValueError as exc:
            messagebox.showerror("Pseudo invalide", str(exc))
            return

        self.category_var.set(self.category_labels[self.category_display_var.get()])
        self.player = player
        self.player_name_var.set(player["name"])
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
            f"Catégorie : {format_category_name(self.session.category)}  |  "
            f"Difficulté : {self.session.difficulty}"
        )
        tk.Label(container, text=header_text, font=("Arial", 10, "bold")).pack(pady=(0, 14))

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

        tk.Button(actions, text="Retour au menu", command=self.return_to_menu, width=18).pack(
            side="left",
            padx=(0, 8),
        )
        tk.Button(actions, text="Classement", command=self.show_leaderboard, width=18).pack(
            side="left"
        )

        self.status_var.set("Proposez une lettre.")
        self.refresh_game_view()
        self.schedule_timer()

    def refresh_game_view(self):
        self.word_var.set(self.session.revealed_word)
        tried_letters = ", ".join(self.session.letters_tried) or "Aucune"
        self.tried_letters_var.set(f"Lettres proposées : {tried_letters}")
        self.attempts_var.set(f"Essais restants : {self.session.attempts_left}")
        self.timer_var.set(f"Temps restant : {self.session.time_remaining} s")

        potential_score = build_score_breakdown(
            self.session.difficulty,
            len(self.session.secret_word),
            self.session.attempts_left,
            self.session.time_remaining,
        )["total"]
        self.score_hint_var.set(f"Score potentiel si vous gagnez maintenant : {potential_score}")
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
            self.status_var.set(f"La lettre {result.letter} a déjà été proposée.")
        elif result.correct:
            self.status_var.set(f"Bonne réponse : {result.letter} est dans le mot.")
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
        score_summary = "Score gagné : 0"

        if won:
            breakdown = build_score_breakdown(
                self.session.difficulty,
                len(self.session.secret_word),
                self.session.attempts_left,
                self.session.time_remaining,
            )
            score_earned = breakdown["total"]
            score_summary = (
                "Score gagné : "
                f"{score_earned} (base {breakdown['base_points']}, mot {breakdown['word_bonus']}, "
                f"essais {breakdown['attempts_bonus']}, temps {breakdown['time_bonus']})"
            )

        self.player = record_game_result(self.player["id"], won=won, score_earned=score_earned)
        self.progress_var.set(self._build_player_summary(self.player))

        if reason == "won":
            title = "Victoire"
            result_message = f"Vous avez trouvé le mot : {self.session.secret_word}."
        elif reason == "time":
            title = "Temps écoulé"
            result_message = f"Le temps est terminé. Le mot était : {self.session.secret_word}."
        else:
            title = "Partie perdue"
            result_message = f"Vous n'avez plus d'essais. Le mot était : {self.session.secret_word}."

        message = (
            f"{result_message}\n\n"
            f"{score_summary}\n"
            f"{self._build_player_summary(self.player)}\n\n"
            "Rejouer avec le même profil ?"
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
            banner_message=f"Dernier résultat : {result_message} {score_summary}"
        )

    def return_to_menu(self):
        self.show_main_menu()

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

        headers = ["#", "Joueur", "Score total", "Meilleur", "Victoires", "Taux de victoire"]
        for index, header in enumerate(headers):
            tk.Label(container, text=header, font=("Arial", 10, "bold")).grid(
                row=2,
                column=index,
                padx=6,
                pady=4,
            )

        if not rows:
            tk.Label(container, text="Aucune donnée disponible.").grid(
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
            f"{player['games_won']} victoire(s) sur {player['games_played']} partie(s)."
        )
