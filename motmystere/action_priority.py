from .categories import format_category_name


def _format_selection(category, difficulty):
    if not category or not difficulty:
        return "le reglage conseille"
    return f"{format_category_name(category)} en {difficulty}"


def _get_latest_game(dashboard):
    recent_games = (dashboard or {}).get("recent_games") or ()
    return recent_games[0] if recent_games else None


def _build_action(
    kind,
    label,
    title,
    reason_line,
    callback_id,
    *,
    cta_text,
    category=None,
    difficulty=None,
    enabled=True,
):
    return {
        "kind": kind,
        "label": label,
        "title": title,
        "reason_line": reason_line,
        "callback_id": callback_id,
        "cta_text": cta_text,
        "category": category,
        "difficulty": difficulty,
        "enabled": enabled,
    }


def _build_start_game_action(*, has_player_context):
    if has_player_context:
        return _build_action(
            "start_game",
            "Lancement libre",
            "Lancer une nouvelle manche",
            "Le formulaire reste disponible pour repartir tout de suite sur le reglage affiche.",
            "start_game",
            cta_text="Lancer une partie",
        )
    return _build_action(
        "start_game",
        "Parcours principal",
        "Commencer une premiere manche",
        "Saisissez un pseudo puis lancez la premiere manche sur le reglage deja selectionne.",
        "start_game",
        cta_text="Lancer une partie",
    )


def _build_personalized_action(snapshot):
    recommendation = (snapshot or {}).get("personalized_recommendation")
    if (
        recommendation is None
        or not recommendation.get("category")
        or not recommendation.get("difficulty")
    ):
        return None

    return _build_action(
        "personalized_recommendation",
        "Manche recommandee",
        recommendation.get("title") or f"Reprendre {_format_selection(recommendation.get('category'), recommendation.get('difficulty'))}",
        recommendation.get("detail") or "Le moteur produit pointe ce reglage comme levier principal.",
        "start_personalized_recommendation",
        cta_text="Jouer la reco",
        category=recommendation.get("category"),
        difficulty=recommendation.get("difficulty"),
    )


def _build_last_selection_action(dashboard):
    latest_game = _get_latest_game(dashboard)
    if latest_game is None or not latest_game.get("category") or not latest_game.get("difficulty"):
        return None

    selection_text = _format_selection(latest_game.get("category"), latest_game.get("difficulty"))
    outcome = "victoire" if latest_game.get("won") else "defaite"
    return _build_action(
        "last_selection",
        "Reprise rapide",
        f"Reprendre {selection_text}",
        f"Dernier reglage rejouable : {selection_text} ({outcome}).",
        "start_last_selection",
        cta_text="Reprendre",
        category=latest_game.get("category"),
        difficulty=latest_game.get("difficulty"),
    )


def _build_replay_action(dashboard):
    latest_game = _get_latest_game(dashboard)
    if latest_game is None or not latest_game.get("category") or not latest_game.get("difficulty"):
        return None

    selection_text = _format_selection(latest_game.get("category"), latest_game.get("difficulty"))
    return _build_action(
        "replay_current_selection",
        "Rejouer",
        f"Rejouer {selection_text}",
        f"Le reglage qui vient d'etre joue reste disponible pour repartir sans friction.",
        "replay_current_selection",
        cta_text="Rejouer",
        category=latest_game.get("category"),
        difficulty=latest_game.get("difficulty"),
    )


def _build_review_actions(snapshot):
    review_options = (snapshot or {}).get("review_options") or {}
    actions = []

    failed_words = review_options.get("failed_words")
    if failed_words is not None:
        actions.append(
            _build_action(
                "review_failed_words",
                "Revision ciblee",
                failed_words.get("title", "Reviser mes mots rates"),
                failed_words.get("detail")
                or "Transformez les defaites recentes en revision hors rotation normale.",
                "start_review_failed_words",
                cta_text="Reviser",
                category=failed_words.get("category"),
                difficulty=failed_words.get("difficulty"),
            )
        )

    weak_pair = review_options.get("weak_pair")
    if weak_pair is not None:
        actions.append(
            _build_action(
                "review_weak_pair",
                "Revision ciblee",
                weak_pair.get("title", "Travailler mon reglage fragile"),
                weak_pair.get("detail")
                or "Travaillez la paire fragile hors rotation normale.",
                "start_review_weak_pair",
                cta_text="Travailler",
                category=weak_pair.get("category"),
                difficulty=weak_pair.get("difficulty"),
            )
        )

    return actions


def _build_primary_goal_action(snapshot):
    primary_goal = (snapshot or {}).get("primary_goal")
    if primary_goal is None:
        return None

    return _build_action(
        "primary_goal_session",
        "Session objectif",
        f"Session objectif : {primary_goal.get('title', 'Objectif actif')}",
        primary_goal.get("detail") or "Enchainement guide vers l'objectif principal.",
        "start_guided_primary_goal_session",
        cta_text="Session objectif",
        category=primary_goal.get("category"),
        difficulty=primary_goal.get("difficulty"),
    )


def _build_featured_challenge_action(snapshot):
    featured_challenge = (snapshot or {}).get("featured_challenge")
    if featured_challenge is None:
        return None

    return _build_action(
        "featured_challenge_session",
        "Session defi",
        f"Session defi : {featured_challenge.get('title', 'Defi actif')}",
        featured_challenge.get("detail") or "Le defi du moment reste disponible en session guidee.",
        "start_guided_featured_challenge_session",
        cta_text="Session defi",
        category=featured_challenge.get("category"),
        difficulty=featured_challenge.get("difficulty"),
    )


def _build_return_to_menu_action():
    return _build_action(
        "return_to_menu",
        "Navigation",
        "Retour accueil",
        "Revenez a l'accueil pour changer de reglage ou reprendre une autre suite.",
        "return_to_menu",
        cta_text="Retour accueil",
    )


def _build_utility_actions(*, has_player_context):
    return [
        _build_action(
            "player_dashboard",
            "Utilitaire",
            "Profil",
            "Consultez la progression detaillee du joueur actif.",
            "open_player_dashboard",
            cta_text="Profil",
            enabled=has_player_context,
        ),
        _build_action(
            "leaderboard",
            "Utilitaire",
            "Classement",
            "Ouvrez le classement solo local.",
            "show_leaderboard",
            cta_text="Classement",
        ),
        _build_action(
            "editorial",
            "Maintenance",
            "Cockpit editorial",
            "Consultez les priorites de maintenance du catalogue.",
            "show_editorial_cockpit_overlay",
            cta_text="Cockpit editorial",
        ),
        _build_action(
            "export_local_data",
            "Maintenance",
            "Sauvegarder mes donnees",
            "Exportez l'environnement local complet.",
            "export_local_data",
            cta_text="Sauvegarder",
        ),
        _build_action(
            "import_local_data",
            "Maintenance",
            "Restaurer une sauvegarde",
            "Rechargez une sauvegarde locale verifiee.",
            "import_local_data",
            cta_text="Restaurer",
        ),
    ]


def _dedupe_actions(actions):
    seen = set()
    deduped = []
    for action in actions:
        if action is None:
            continue
        key = (
            action.get("callback_id"),
            action.get("category"),
            action.get("difficulty"),
            action.get("kind"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped


def build_surface_action_plan(dashboard, snapshot, *, surface, round_result=None):
    has_player_context = dashboard is not None or snapshot is not None
    start_game_action = _build_start_game_action(has_player_context=has_player_context)
    personalized_action = _build_personalized_action(snapshot)
    review_actions = _build_review_actions(snapshot)
    primary_goal_action = _build_primary_goal_action(snapshot)
    featured_challenge_action = _build_featured_challenge_action(snapshot)

    if surface == "home":
        if not has_player_context:
            ordered_actions = [start_game_action]
        else:
            ordered_actions = [
                personalized_action,
                _build_last_selection_action(dashboard),
                *review_actions,
                primary_goal_action,
                featured_challenge_action,
                start_game_action,
            ]
    elif surface == "round_summary":
        replay_action = _build_replay_action(dashboard)
        return_to_menu_action = _build_return_to_menu_action()
        if round_result == "won":
            ordered_actions = [
                personalized_action,
                replay_action,
                primary_goal_action,
                return_to_menu_action,
            ]
        else:
            ordered_actions = [
                *review_actions,
                personalized_action,
                replay_action,
                primary_goal_action,
                return_to_menu_action,
            ]
    else:
        raise ValueError(f"Surface inconnue : {surface}")

    ordered_actions = _dedupe_actions(ordered_actions)
    primary_action = ordered_actions[0] if ordered_actions else None
    secondary_actions = ordered_actions[1:] if len(ordered_actions) > 1 else []

    if primary_action is None:
        fallback = start_game_action if surface == "home" else _build_return_to_menu_action()
        primary_action = fallback
        secondary_actions = []

    return {
        "surface": surface,
        "reason_line": primary_action.get("reason_line", ""),
        "primary_action": primary_action,
        "secondary_actions": secondary_actions,
        "utility_actions": _build_utility_actions(has_player_context=has_player_context),
    }
