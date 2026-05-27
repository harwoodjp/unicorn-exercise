import pytest

from service.match.deterministic import _normalize


class TestNormalizeName:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("Chateau Margaux", "chateau margaux"),
            ("CHATEAU MARGAUX", "chateau margaux"),
            ("chateau margaux", "chateau margaux"),
            ("  Chateau   Margaux  ", "chateau margaux"),
            ("Chateau-Margaux", "chateau margaux"),
            ("Chateau, Margaux.", "chateau margaux"),
            ("Domaine de la Romanee-Conti", "domaine de la romanee conti"),
            ("Macallan 12", "macallan 12"),
            ("12yr", "12yr"),
        ],
    )
    def test_normalizes(self, raw: str, expected: str) -> None:
        assert _normalize(raw) == expected
