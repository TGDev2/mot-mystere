import tkinter as tk
from tkinter import messagebox

from ...categories import format_category_name
from ...solo_game_service import get_progression_bundle
from ..formatters import format_end_reason, format_played_at
from ..theme import ACCENT_BORDER, ACCENT_COLOR, APP_BG, CARD_BG, HERO_BG, MUTED_BG


class PlayerDashboardScreen:
    def render(self, app, *, player_id):
        bundle = get_progression_bundle({"id": player_id}, app.category_availability)
        if bundle is None:
            messagebox.showerror("Profil", "Le profil demande est introuvable.")
            return

        dashboard, progression = app._apply_progression_bundle(
            bundle,
            sync_recent_selection=True,
        )
        ui = app.ui

        profile_window = tk.Toplevel(app.root, bg=APP_BG)
        profile_window.title(f"Profil - {app.player['name']}")
        profile_window.resizable(False, False)

        container = ui.frame(profile_window, bg=APP_BG, padx=18, pady=18)
        container.pack(fill="both", expand=True)

        header = ui.card(container, bg=HERO_BG, border=ACCENT_BORDER, padx=18, pady=16)
        header.pack(fill="x")
        ui.label(
            header,
            text=f"Profil de {app.player['name']}",
            bg=HERO_BG,
            font=("Georgia", 20, "bold"),
        ).pack(anchor="w")

        overview = dashboard["overview"]
        recent_form = dashboard["recent_form"]
        summary_lines = [
            app._build_player_summary(app.player),
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

        summary_card = ui.card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        summary_card.pack(fill="x", pady=(14, 0))
        ui.section_title(summary_card, "Vue d'ensemble")
        for line in summary_lines:
            ui.label(
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
            insight_card = ui.card(container, bg=MUTED_BG, border="#d7d0c1", padx=18, pady=18)
            insight_card.pack(fill="x", pady=(14, 0))
            ui.label(
                insight_card,
                text="Points de progression",
                font=("Arial", 12, "bold"),
            ).pack(anchor="w", pady=(0, 6))
            for line in insight_lines:
                ui.label(
                    insight_card,
                    text=line,
                    justify="left",
                    wraplength=760,
                ).pack(fill="x", pady=2)

        mastery_card = ui.card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        mastery_card.pack(fill="x", pady=(14, 0))
        ui.section_title(mastery_card, "Maitrise par categorie")
        ui.label(
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
        ui.render_mastery_grid(mastery_card, progression["mastery"])

        challenges_card = ui.card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        challenges_card.pack(fill="x", pady=(14, 0))
        ui.section_title(challenges_card, "Defis du moment")
        ui.render_challenge_cards(challenges_card, progression.get("challenges", ()), limit=3)

        goals_card = ui.card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        goals_card.pack(fill="x", pady=(14, 0))
        ui.section_title(goals_card, "Objectifs actifs")
        ui.render_goal_cards(goals_card, progression["goals"], limit=3)

        table_card = ui.card(container, bg=CARD_BG, border=ACCENT_BORDER, padx=18, pady=18)
        table_card.pack(fill="x", pady=(14, 0))
        ui.section_title(table_card, "Dernieres parties")

        table = ui.frame(table_card)
        table.pack()

        headers = ["#", "Resultat", "Categorie", "Niveau", "Score", "Fin", "Date"]
        for index, header in enumerate(headers):
            ui.label(table, text=header, font=("Arial", 10, "bold")).grid(
                row=0,
                column=index,
                padx=6,
                pady=4,
            )

        if not dashboard["recent_games"]:
            ui.label(table, text="Aucune partie enregistree.").grid(
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
                    ui.label(table, text=value).grid(
                        row=row_index,
                        column=column_index,
                        padx=6,
                        pady=3,
                    )

        tk.Button(container, text="Fermer", command=profile_window.destroy, width=14).pack(
            pady=(14, 0)
        )
