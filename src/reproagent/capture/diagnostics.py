"""Safe, namespaced diagnostics for capture quality and degradation."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import JsonValue

CAPTURE_EXTENSION_NAMESPACE = "org.reproagent.capture/v1"


@dataclass
class CaptureDiagnostics:
    """Mutable internal diagnostics that never retain observed secret values."""

    warnings: list[str] = field(default_factory=list)
    unsupported_observations: list[str] = field(default_factory=list)
    redaction_failures: list[dict[str, str]] = field(default_factory=list)
    normalization_failures: list[dict[str, str]] = field(default_factory=list)
    serialization_warnings: list[str] = field(default_factory=list)
    dropped_event_count: int = 0
    degraded_reasons: list[str] = field(default_factory=list)

    def record_redaction_failure(self, event_type: str, error_type: str) -> None:
        self.redaction_failures.append({"event_type": event_type, "error_type": error_type})
        self.dropped_event_count += 1
        self.add_degraded_reason(
            "one or more observed events were dropped because redaction failed"
        )

    def record_normalization_failure(self, event_type: str, error_type: str) -> None:
        self.normalization_failures.append({"event_type": event_type, "error_type": error_type})
        self.dropped_event_count += 1
        self.add_degraded_reason("one or more observed events could not be normalized safely")

    def add_warning(self, warning: str) -> None:
        if warning not in self.warnings:
            self.warnings.append(warning)

    def add_unsupported(self, observation: str) -> None:
        if observation not in self.unsupported_observations:
            self.unsupported_observations.append(observation)

    def add_serialization_warning(self, warning: str) -> None:
        if warning not in self.serialization_warnings:
            self.serialization_warnings.append(warning)

    def add_degraded_reason(self, reason: str) -> None:
        if reason not in self.degraded_reasons:
            self.degraded_reasons.append(reason)

    def to_extension(self) -> dict[str, JsonValue]:
        return {
            "warnings": list(self.warnings),
            "unsupported_observations": list(self.unsupported_observations),
            "redaction_failures": [dict(item) for item in self.redaction_failures],
            "normalization_failures": [dict(item) for item in self.normalization_failures],
            "serialization_warnings": list(self.serialization_warnings),
            "dropped_event_count": self.dropped_event_count,
            "degraded_reasons": list(self.degraded_reasons),
        }
