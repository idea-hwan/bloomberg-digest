from datetime import date

from app.preview import themes_for


def test_themes_group_repeated_headlines_and_skip_one_offs():
    days = {
        "2026-10-14": {
            "morning": {"hook": "AI 균열", "items": [{"headline": "반도체주 급락"}], "markets": []},
            "daily": {"headline": "Tech week", "sections": ["CoreWeave bonds slide"]},
        },
        "2026-10-15": {
            "morning": {"hook": "물가", "items": [{"headline": "반도체 6일째"}], "markets": []},
            "daily": {"headline": "Calm", "sections": ["CoreWeave’s yikes moment"]},
        },
        "2026-10-16": {
            "morning": None,
            "daily": {"headline": "A single oil note", "sections": []},
        },
    }
    themes = themes_for(days, date(2026, 10, 12), date(2026, 10, 18))
    names = [theme["name"] for theme in themes]
    assert "반도체 · AI" in names
    chip = next(theme for theme in themes if theme["name"] == "반도체 · AI")
    assert chip["days"] == 2
    assert all(theme["days"] >= 2 for theme in themes)
