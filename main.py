from database import setup_database
from game_logic import HangmanApp


def main():
    setup_database()
    app = HangmanApp()
    app.run()


if __name__ == "__main__":
    main()
