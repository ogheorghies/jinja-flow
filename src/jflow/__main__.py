import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: jflow <config.yaml>", file=sys.stderr)
        sys.exit(1)
    print(f"jflow: would process {sys.argv[1]}")


if __name__ == "__main__":
    main()
