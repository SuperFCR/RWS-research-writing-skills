# tests/test_compile_engine_flag.py
import pytest

from overleaf_sync.compile import engine_flag


@pytest.mark.parametrize(
    "engine,expected",
    [
        ("pdflatex", "-pdf"),
        ("xelatex", "-xelatex"),
        ("lualatex", "-lualatex"),
    ],
)
def test_engine_flag_maps_known_engines(engine, expected):
    assert engine_flag(engine) == expected


def test_engine_flag_rejects_unknown_engine():
    with pytest.raises(ValueError):
        engine_flag("dvipdf")
