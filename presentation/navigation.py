from dataclasses import dataclass, field
from typing import Any


MAIN_MENU_SCREEN = "main_menu"
ROUND_SCREEN = "round"
ROUND_SUMMARY_SCREEN = "round_summary"
GUIDED_SESSION_SUMMARY_SCREEN = "guided_session_summary"
PLAYER_DASHBOARD_OVERLAY = "player_dashboard"
LEADERBOARD_OVERLAY = "leaderboard"


@dataclass(frozen=True)
class NavigationEvent:
    layer: str
    route: str
    payload: dict[str, Any] = field(default_factory=dict)


class PresentationRouter:
    def __init__(self, *, screens, overlays):
        self._screens = dict(screens)
        self._overlays = dict(overlays)
        self.current_screen = None
        self.history = []

    def show_screen(self, route, **payload):
        renderer = self._screens[route]
        event = NavigationEvent(layer="screen", route=route, payload=dict(payload))
        self.current_screen = event
        self.history.append(event)
        return renderer(**payload)

    def open_overlay(self, route, **payload):
        renderer = self._overlays[route]
        event = NavigationEvent(layer="overlay", route=route, payload=dict(payload))
        self.history.append(event)
        return renderer(**payload)
