"""Shared management UI timing and bounded-buffer configuration.

The values stay in the versioned YAML contract so service UIs and gateways do not hard-code
polling, stream lifetime, or browser-memory limits. Timer reference:
https://html.spec.whatwg.org/multipage/timers-and-user-prompts.html#timers
"""

from __future__ import annotations

from dataclasses import dataclass

from .configuration import ConfigurationError, LoadedConfiguration, require_mapping


@dataclass(frozen=True, slots=True)
class ManagementUiSettings:
    refresh_interval_seconds: float
    log_stream_poll_interval_seconds: float
    log_stream_timeout_seconds: float
    log_buffer_bytes: int

    @classmethod
    def from_configuration(cls, loaded: LoadedConfiguration) -> ManagementUiSettings:
        management = require_mapping(loaded.document, "management")
        console = require_mapping(management, "console")
        try:
            settings = cls(
                refresh_interval_seconds=float(console["refresh_interval_seconds"]),
                log_stream_poll_interval_seconds=float(console["log_stream_poll_interval_seconds"]),
                log_stream_timeout_seconds=float(console["log_stream_timeout_seconds"]),
                log_buffer_bytes=int(console["log_buffer_bytes"]),
            )
        except KeyError as error:
            raise ConfigurationError(
                f"management.console is missing required key: {error.args[0]}"
            ) from error
        if settings.refresh_interval_seconds < 0.5:
            raise ConfigurationError(
                "management.console.refresh_interval_seconds must be at least 0.5"
            )
        return settings

    def document(self) -> dict[str, float | int]:
        return {
            "refresh_interval_seconds": self.refresh_interval_seconds,
            "log_stream_poll_interval_seconds": self.log_stream_poll_interval_seconds,
            "log_stream_timeout_seconds": self.log_stream_timeout_seconds,
            "log_buffer_bytes": self.log_buffer_bytes,
        }
