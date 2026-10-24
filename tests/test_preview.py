from datetime import date

from app.preview import commentary_summary, daily_view, first_sentence, recent_dates, summarize, themes_for

def test_commentary_summary_stops_near_ten_lines():
    paragraphs = ["A" * 400, "B" * 400, "C" * 400]
    summary = commentary_summary("\n\n".join(paragraphs))
    assert summary == "\n\n".join(paragraphs[:2])


def test_day_headline_is_the_first_sentence_of_the_lead():
    lead = "인공지능 우려와 중동 긴장이 겹치며 뉴욕증시가 급락했다. 나스닥은 2.9% 내렸다.\n\n유가가 올랐다."
    assert first_sentence(lead) == "인공지능 우려와 중동 긴장이 겹치며 뉴욕증시가 급락했다."
    spaced = "중동 긴장 까지 고조되면서 뉴욕증시 가 급락했다. 유가는 올랐다."
    assert first_sentence(spaced) == "중동 긴장까지 고조되면서 뉴욕증시가 급락했다."
    body = "첫 문단이다. 둘째 문장이다.\n\n둘째 문단은 빼야 한다."
    assert summarize(body) == "첫 문단이다. 둘째 문장이다."


def test_new_layout_starts_on_oct_23_and_keeps_older_days():
    sections = [
        {"heading": "Five things you need to know", "body": "One.\n\nTwo."},
        {"heading": "On the move", "body": "movers"},
        {"heading": "Election scenarios", "body": "essay"},
        {"heading": "Word from Wall Street", "body": "quote"},
    ]
    older = daily_view({"date": "2026-10-22", "headline": "Old", "sections": sections})
    current = daily_view({"date": "2026-10-23", "headline": "New", "sections": sections})
    assert "five" not in older
    assert older["sections"] == ["Election scenarios"]
    assert current["five"] == ["One.", "Two."]
    assert current["commentary"][0]["heading"] == "Election scenarios"
    assert current["commentary"][0]["summary"] == "essay"
    assert current["sections"] == ["Election scenarios"]


def test_day_list_keeps_only_the_latest_month():
    dates = ["2026-10-24", "2026-09-24", "2026-09-23", "2026-08-01"]
    assert recent_dates(dates, date(2026, 10, 24)) == ["2026-10-24", "2026-09-24"]


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
