from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

from kcal_tracker.services.barcode import _decode_first, normalize_barcode


def _install_fake_pyzbar(monkeypatch, decode):
    package = ModuleType("pyzbar")
    module = ModuleType("pyzbar.pyzbar")
    module.decode = decode
    package.pyzbar = module
    monkeypatch.setitem(sys.modules, "pyzbar", package)
    monkeypatch.setitem(sys.modules, "pyzbar.pyzbar", module)


def test_decode_first_returns_none_when_candidate_decode_fails(monkeypatch) -> None:
    def decode(_image):
        raise RuntimeError("Unsupported bits-per-pixel")

    _install_fake_pyzbar(monkeypatch, decode)

    assert _decode_first(object()) is None


def test_decode_first_returns_decoded_barcode(monkeypatch) -> None:
    def decode(_image):
        return [SimpleNamespace(data=b"4601234567893")]

    _install_fake_pyzbar(monkeypatch, decode)

    assert _decode_first(object()) == "4601234567893"


def test_decode_first_rejects_partial_number(monkeypatch) -> None:
    def decode(_image):
        return [SimpleNamespace(data=b"941921")]

    _install_fake_pyzbar(monkeypatch, decode)

    assert _decode_first(object()) is None


def test_normalize_barcode_accepts_digits_with_spaces() -> None:
    assert normalize_barcode("4 601234 567893") == "4601234567893"
