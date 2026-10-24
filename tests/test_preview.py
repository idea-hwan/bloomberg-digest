from datetime import date

from app.preview import commentary_summary, daily_view, first_sentence, market_label, narrative_for, recent_dates, summarize, themes_for, week_windows

def test_commentary_summary_stops_near_ten_lines():
    paragraphs = ["A" * 400, "B" * 400, "C" * 400]
    summary = commentary_summary("\n\n".join(paragraphs))
    assert summary == "\n\n".join(paragraphs[:2])


def test_market_cards_use_english_names():
    assert market_label("나스닥 100 지수") == "Nasdaq 100"
    assert market_label("美 국채 10년물 금리") == "US 10Y"
    assert market_label("달러-원 환율") == "USD/KRW"
    assert market_label("블룸버그 달러 지수") == "Bloomberg Dollar"
    assert market_label("브렌트 원유 선물") == "Brent"
    assert market_label("S&P 500 지수") == "S&P 500"


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


def test_reviews_follow_the_days_still_in_the_window():
    week = narrative_for("Tech", [{"date": "2026-10-19"}, {"date": "2026-10-20"}, {"date": "2026-10-23"}])
    assert "코어위브" in week and "블랙스톤" in week and "내렸다" in week and "그런데" in week
    assert "엔비디아" not in week and not week.startswith("전환.")
    shifted = narrative_for("Tech", [{"date": "2026-10-23"}])
    assert "블랙스톤" in shifted and "내렸다" in shifted
    assert "코어위브" not in shifted and not shifted.startswith("약세.")
    month = narrative_for("Tech", [{"date": "2026-10-07"}, {"date": "2026-10-15"}, {"date": "2026-10-23"}])
    assert "엔비디아" in month and "부실" in month and "블랙스톤" in month
    assert narrative_for("Macro", []) == "변화없음."
    macro = narrative_for("Macro", [
        {"date": "2026-10-19"},
        {"date": "2026-10-20"},
        {"date": "2026-10-21"},
        {"date": "2026-10-22"},
        {"date": "2026-10-23"},
    ])
    assert "12%" in macro and "1.99조" in macro and "146bp" in macro
    assert "150bp" in macro and "159.4bp" in macro and "178bp" in macro
    assert "그리고" in macro and "그래서" in macro
    shifted = narrative_for("Macro", [{"date": "2026-10-23"}])
    assert "178bp" in shifted and "146bp" not in shifted


def test_each_mail_day_opens_its_own_week():
    days = {
        "2026-10-22": {"morning": {"hook": "佛10년물 5%", "items": [], "markets": []}, "daily": None},
        "2026-10-23": {"morning": {"hook": "나스닥 급락", "items": [{"headline": "佛국채 불안"}], "markets": []}, "daily": None},
    }
    weeks = week_windows(days, ["2026-10-23", "2026-10-22"])
    assert weeks["2026-10-23"]["start"] == "2026-10-17"
    assert weeks["2026-10-22"]["start"] == "2026-10-16"
    assert weeks["2026-10-23"]["themes"][0]["name"] == "Macro"


def test_themes_stay_on_three_lanes():
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
            "daily": {"headline": "A single oil note", "sections": ["브렌트유가 올랐다"]},
        },
    }
    themes = themes_for(days, date(2026, 10, 12), date(2026, 10, 18))
    assert [theme["name"] for theme in themes] == ["Macro", "Geopolitics", "Tech"]
    tech = themes[2]
    assert tech["days"] == 2
    assert any(hit["cited"] for hit in tech["hits"])
