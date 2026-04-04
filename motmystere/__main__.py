import sys

from .database import setup_database
from .release_smoke import run_release_smoke_test


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if "--smoke-test" in args:
        run_release_smoke_test()
        return

    setup_database()
    from tkinter import TclError

    from .game_logic import HangmanApp

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
