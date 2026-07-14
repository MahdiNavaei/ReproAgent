"""Offline failure example that persists the case and re-raises the application error."""

from __future__ import annotations

import argparse
from pathlib import Path

from reproagent.capture import capture


class SyntheticLookupError(RuntimeError):
    pass


def failing_lookup(order_id: str) -> dict[str, str]:
    raise SyntheticLookupError(f"synthetic lookup failed for order {order_id}")


def main(output: Path) -> None:
    with capture(output=output, name="manual-failure-agent") as session:
        call_id = session.tool_call(name="lookup_order", arguments={"order_id": "404"})
        try:
            failing_lookup("404")
        except SyntheticLookupError as exc:
            session.tool_result(
                parent_event_id=call_id,
                name="lookup_order",
                status="failure",
                error={"exception_type": type(exc).__name__, "message": str(exc)},
            )
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    main(args.output)
