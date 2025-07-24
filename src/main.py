import sys
from bots.test_connection import ConnectionTester

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py [nameOfBot]")
        return

    bot_name = sys.argv[1]

    available_bots = {
        ConnectionTester.NAME: ConnectionTester,
    }
    if bot_name in available_bots:
        bot_class = available_bots[bot_name]
        bot_class().run()
    else:
        print(f"Unknown bot: {bot_name}")

if __name__ == "__main__":
    main()
