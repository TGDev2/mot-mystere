from tkinter import TclError

from database import setup_database
from game_logic import HangmanApp


def main():
    setup_database()
    try:
        app = HangmanApp()
    except TclError as exc:
        raise RuntimeError(
            "Tkinter/Tcl est indisponible. Utilisez un environnement Python avec Tcl/Tk "
            "ou un build Windows genere sur une machine compatible."
        ) from exc
    app.run()


if __name__ == "__main__":
    main()
