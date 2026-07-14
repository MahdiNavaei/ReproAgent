"""Allow ``python -m reproagent`` to behave like the CLI entry point."""

from reproagent.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
