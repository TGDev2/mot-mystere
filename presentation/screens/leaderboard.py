import tkinter as tk

from database import get_leaderboard_data
from presentation.theme import ACCENT_BORDER, APP_BG, CARD_BG, HERO_BG, SUBTLE_TEXT


class LeaderboardScreen:
    def render(self, app):
        rows = get_leaderboard_data()
        ui = app.ui

        leaderboard = tk.Toplevel(app.root, bg=APP_BG)
        leaderboard.title("Classement")
        leaderboard.resizable(False, False)

        container = ui.frame(leaderboard, bg=APP_BG, padx=18, pady=18)
        container.pack(fill="both", expand=True)

        header = ui.card(container, bg=HERO_BG, border=ACCENT_BORDER, padx=18, pady=16)
        header.pack(fill="x")
        ui.label(
            header,
            text="Classement solo",
            bg=HERO_BG,
            font=("Georgia", 20, "bold"),
        ).pack(anchor="w")
        ui.label(
            header,
            text="Tri par score total, puis meilleur score et nombre de victoires.",
            bg=HERO_BG,
            fg=SUBTLE_TEXT,
        ).pack(anchor="w", pady=(4, 0))

        table_card = ui.card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        table_card.pack(fill="x", pady=(14, 0))
        table = ui.frame(table_card)
        table.pack()
        headers = ["#", "Joueur", "Score total", "Meilleur", "Victoires", "Taux"]
        for index, header in enumerate(headers):
            ui.label(table, text=header, font=("Arial", 10, "bold")).grid(
                row=0,
                column=index,
                padx=6,
                pady=4,
            )

        if not rows:
            ui.label(table, text="Aucune donnee disponible.").grid(
                row=1,
                column=0,
                columnspan=6,
                pady=8,
            )
        else:
            for row_index, player in enumerate(rows, start=1):
                row_bg = "#eef6ff" if app.player and player["id"] == app.player["id"] else CARD_BG
                values = [
                    row_index,
                    player["name"],
                    player["score_total"],
                    player["best_score"],
                    player["games_won"],
                    f"{player['win_rate']} %",
                ]
                for column_index, value in enumerate(values):
                    ui.label(table, text=value, bg=row_bg).grid(
                        row=row_index,
                        column=column_index,
                        padx=6,
                        pady=3,
                    )

        tk.Button(container, text="Fermer", command=leaderboard.destroy, width=14).pack(
            pady=(14, 0)
        )
