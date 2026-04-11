import tkinter as tk

from ..categories import MIN_WORD_POOL_SIZE, format_category_name, get_category_difficulty_breakdown
from ..solo_game_service import build_catalog_exploration_snapshot as build_catalog_exploration_snapshot_bundle


class SelectionCatalogSupport:
    def __init__(self, app):
        self.app = app

    def set_catalog(self, catalog):
        self.app.catalog = catalog
        self.app.categories = dict(catalog.categories)
        self.app.category_availability = dict(catalog.category_availability)
        self.app.category_display_names = dict(catalog.display_names)
        self.app.category_labels = self.build_category_label_map()
        if not self.app.categories:
            raise RuntimeError("Aucune categorie exploitable n'est disponible.")

    def merge_banner_messages(self, *messages):
        return " ".join(message.strip() for message in messages if message and message.strip())

    def get_category_display_name(self, category_key):
        return self.app.category_display_names.get(
            category_key,
            format_category_name(category_key),
        )

    def build_category_label_map(self):
        counts = {}
        for key in self.app.categories:
            label = self.get_category_display_name(key)
            counts[label] = counts.get(label, 0) + 1

        labels = {}
        for key in self.app.categories:
            label = self.get_category_display_name(key)
            if counts[label] > 1:
                label = f"{label} [{key}]"
            labels[label] = key
        return labels

    def sync_selection_after_catalog_reload(self, previous_category, previous_difficulty):
        fallback_category = next(iter(self.app.categories))
        selected_category = previous_category if previous_category in self.app.categories else fallback_category
        available_difficulties = self.app.category_availability[selected_category]
        selected_difficulty = (
            previous_difficulty if previous_difficulty in available_difficulties else available_difficulties[0]
        )

        self.app.category_var.set(selected_category)
        self.app.category_display_var.set(self.get_category_display_name(selected_category))
        self.app.difficulty_var.set(selected_difficulty)

        messages = []
        if previous_category and previous_category not in self.app.categories:
            messages.append(
                "Le reglage precedent n'est plus disponible; une categorie de secours a ete selectionnee."
            )
        elif previous_category == selected_category and previous_difficulty not in available_difficulties:
            messages.append(
                "Le niveau precedent n'est plus disponible; le premier niveau jouable a ete selectionne."
            )

        return " ".join(messages)

    def sync_selection_from_goal(self, goal):
        if not goal:
            return

        self.sync_selection_to(goal.get("category"), goal.get("difficulty"))

    def sync_selection_to(self, category, difficulty):
        if category in self.app.categories:
            self.app.category_var.set(category)
            self.app.category_display_var.set(self.get_category_display_name(category))

        self.refresh_difficulty_options()
        available_difficulties = self.get_available_difficulties(self.app.category_var.get())
        if difficulty in available_difficulties:
            self.app.difficulty_var.set(difficulty)
        elif available_difficulties:
            self.app.difficulty_var.set(available_difficulties[0])
        self.update_category_hint()

    def build_catalog_exploration_snapshot(
        self,
        *,
        selected_category=None,
        selected_difficulty=None,
    ):
        player_id = self.app.player["id"] if self.app.player is not None else None
        return build_catalog_exploration_snapshot_bundle(
            player_id,
            self.app.categories,
            self.app.category_availability,
            self.app.category_display_names,
            selected_category=selected_category or self.app.category_var.get(),
            selected_difficulty=selected_difficulty or self.app.difficulty_var.get(),
        )

    def render_selected_exploration_state(self):
        if self.app.selected_exploration_mount is None:
            return

        for widget in self.app.selected_exploration_mount.winfo_children():
            widget.destroy()

        snapshot = self.build_catalog_exploration_snapshot()
        self.app.ui.render_catalog_exploration_card(
            self.app.selected_exploration_mount,
            snapshot["selected_state"],
            title="Etat d'exploration",
            empty_message=snapshot["empty_message"],
            tracked=snapshot["tracked"],
        )

    def get_available_difficulties(self, category_key=None):
        key = category_key or self.app.category_var.get()
        return self.app.category_availability.get(key, tuple())

    def refresh_difficulty_options(self):
        available_difficulties = self.get_available_difficulties(self.app.category_var.get())
        if not available_difficulties:
            raise RuntimeError("La categorie selectionnee ne propose aucun niveau exploitable.")

        if self.app.difficulty_var.get() not in available_difficulties:
            self.app.difficulty_var.set(available_difficulties[0])

        if self.app.difficulty_menu is None:
            return

        menu = self.app.difficulty_menu["menu"]
        menu.delete(0, "end")
        for difficulty in available_difficulties:
            menu.add_command(
                label=difficulty,
                command=tk._setit(self.app.difficulty_var, difficulty, self.app.on_difficulty_selected),
            )

    def update_category_hint(self):
        selected_display_name = self.app.category_display_var.get()
        if selected_display_name in self.app.category_labels:
            self.app.category_var.set(self.app.category_labels[selected_display_name])

        breakdown = get_category_difficulty_breakdown(self.app.categories[self.app.category_var.get()])
        available_difficulties = self.get_available_difficulties(self.app.category_var.get())
        selected_difficulty = self.app.difficulty_var.get()
        total_words = sum(breakdown.values())
        selected_pool = breakdown.get(selected_difficulty, 0)
        available_text = ", ".join(available_difficulties)
        self.app.category_hint_var.set(
            f"{self.get_category_display_name(self.app.category_var.get())} propose {total_words} mots au total. "
            f"Le niveau {selected_difficulty} active un pool calibre de {selected_pool} mot(s). "
            f"Niveaux jouables : {available_text} "
            f"(minimum garanti : {MIN_WORD_POOL_SIZE}, pool solide vise : 15 mots par niveau)."
        )
        self.render_selected_exploration_state()
