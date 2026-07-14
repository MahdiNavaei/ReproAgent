"""Offline manual Capture Session example with synthetic model and tool behavior."""

from __future__ import annotations

import argparse
from pathlib import Path

from reproagent.capture import capture, capture_tool


@capture_tool(name="lookup_order")
def lookup_order(order_id: str) -> dict[str, str]:
    return {"order_id": order_id, "status": "shipped"}


def main(output: Path) -> None:
    with capture(output=output, name="manual-order-agent") as session:
        message_id = session.message(
            role="user",
            content="Find order 123",
        )
        request_id = session.model_request(
            parent_event_id=message_id,
            provider="synthetic-provider",
            model="synthetic-model-v1",
            input={
                "messages": [{"role": "user", "content": "Find order 123"}],
                "headers": {"authorization": "Bearer synthetic-demo-token-123456789"},
            },
            parameters={"temperature": 0},
        )
        response_id = session.model_response(
            parent_event_id=request_id,
            provider="synthetic-provider",
            model="synthetic-model-v1",
            output={
                "message": {
                    "role": "assistant",
                    "content": "I will look up the order.",
                }
            },
            finish_reason="tool_call",
            usage={"input_tokens": 10, "output_tokens": 12},
            latency_ms=12.5,
        )
        session.message(
            parent_event_id=response_id,
            role="assistant",
            content="Calling lookup_order",
        )
        result = lookup_order("123")
        session.message(role="assistant", content={"order": result})

    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    main(args.output)
