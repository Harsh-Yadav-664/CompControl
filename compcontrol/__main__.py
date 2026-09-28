"""Terminal entry point for the CompControl prototype."""

from .core import Assistant


def main() -> None:
    assistant = Assistant()
    print("CompControl prototype — type help; Ctrl+C to quit.")
    try:
        while True:
            try:
                request = input("You> ")
            except EOFError:
                print()
                break
            result = assistant.handle(request)
            print(f"CompControl> {result.message}")
    except KeyboardInterrupt:
        print("\nGoodbye.")


if __name__ == "__main__":
    main()
