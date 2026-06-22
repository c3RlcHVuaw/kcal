from __future__ import annotations

import json
import logging

from kcal_tracker.logging import JsonLogFormatter


def test_json_log_formatter_outputs_structured_record() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="kcal.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "kcal.test"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload
