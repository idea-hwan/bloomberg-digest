from __future__ import annotations

from app.extract import choose_text, parse_raw

MORNING_PLAIN = """
안녕하세요.

1. 미국 물가가 다시 가속했다
9월 CPI가 예상을 웃돌았다. 연준 인하 기대가 밀렸다.

2. 반도체는 6거래일째 올랐다
삼성전자와 SK하이닉스가 동반 강세였다.

3. 유가
중동 공급 우려가 이어졌다.

4. 환율
원달러는 1380원대.

5. 오늘 일정
미시간대 소비심리가 나온다.

수신 거부 | 구독 해지
""".strip()

MORNING_HTML = """
<html><body>
<ol>
<li>미국 물가<br>CPI가 올랐다</li>
<li>반도체<br>6일째</li>
<li>유가<br>공급 우려</li>
<li>환율<br>1380원</li>
<li>일정<br>소비심리</li>
</ol>
수신 거부
</body></html>
"""

MARKETS_PLAIN = """
Markets Daily

Tech's rough week

Good morning. Tech led the selloff as yields climbed.

Traders now look to earnings for a reason to buy the dip.

What to watch
Taiwan Semiconductor reports Thursday.

Elsewhere
Oil rose on supply concerns.

You received this email because you subscribed.
""".strip()


def _raw(**overrides) -> dict:
    base = {
        "gmail_id": "abc123",
        "series": "morning5",
        "date": "2026-10-15",
        "subject": "【오늘 아침 꼭 알아야 할 5가지】美인플레 가속, 반도체 6일째",
        "from": "Bloomberg <news@bloomberg.net>",
        "plain": MORNING_PLAIN,
        "html": "",
        "text": "",
    }
    base.update(overrides)
    return base


def test_morning5_extracts_hook_and_five_items():
    text = choose_text(MORNING_PLAIN, "")
    parsed = parse_raw(_raw(text=text))
    assert parsed["hook"] == "美인플레 가속, 반도체 6일째"
    assert parsed["body_parsed"] is True
    assert [item["n"] for item in parsed["items"]] == [1, 2, 3, 4, 5]
    assert parsed["items"][1]["headline"] == "반도체는 6거래일째 올랐다"
    assert "수신 거부" not in parsed["text"]
    assert "수신 거부" not in parsed["items"][-1]["summary"]


def test_morning5_falls_back_to_html_list():
    parsed = parse_raw(_raw(text="짧은 본문", html=MORNING_HTML))
    assert parsed["body_parsed"] is True
    assert parsed["items"][0]["headline"] == "미국 물가"
    assert len(parsed["items"]) == 5


def test_markets_daily_subject_and_sections():
    text = choose_text(MARKETS_PLAIN, "")
    parsed = parse_raw(
        _raw(
            series="markets_daily",
            subject="Markets Daily: Tech's rough week - Plus, why Taiwan's pro stock pickers are quiet",
            text=text,
            plain=MARKETS_PLAIN,
        )
    )
    assert parsed["headline"] == "Tech's rough week"
    assert parsed["secondary"] == "why Taiwan's pro stock pickers are quiet"
    assert parsed["lead"].startswith("Good morning.")
    assert [section["heading"] for section in parsed["sections"]] == ["What to watch", "Elsewhere"]
    assert "You received this" not in parsed["text"]
    assert parsed["body_parsed"] is True


MORNING_MAIL = """
<html><body>
<p>블룸버그 뉴스 한글팀은 평일 오전 7시 30분, 하루를 시작하기 전에 꼭 알아야 할 글로벌 뉴스 5가지를 엄선해 전해드립니다. 한글 뉴스레터는 무료로 제공되며, 여기 로 들어가서 이메일 주소를 입력해 구독하실 수 있습니다. 뉴욕증시는 크게 하락했다.</p>
<table>
<tr><td>S&P 500 지수</td><td>7,718.94</td><td>-1.1%</td></tr>
<tr><td>구독 취소 Bloomberg.com 문의처</td><td>서울</td><td>주소</td></tr>
</table>
<h3>美 9월 CPI</h3>
<p>물가가 0.6% 올랐다.</p>
<p>근원 CPI도 0.3% 올랐다.</p>
<h3>반도체</h3>
<p>6일째 하락했다.</p>
<h3>유가</h3>
<p>브렌트가 올랐다.</p>
<p>최다열람기사 (직전 8시간 기준)</p>
<p>다른 기사 제목</p>
<p>팔로우하세요</p>
</body></html>
"""

MARKETS_MAIL = """
<html><body>
<h3>Five things you need to know</h3>
<p>Stocks fell as the AI trade cracked.</p>
<p>Follow the news that matters to you</p>
<p>Introducing Your News, a curated news feed.</p>
<h3>Calm shattered</h3>
<p>The streak of tranquility is over.</p>
<p>Tech stocks faced heavy losses.</p>
<h3>Test Your Knowledge</h3>
<p>Today's clue is:</p>
<h3>What else we’re reading</h3>
<p>Arrested OpenAI Engineer Had One-Way Ticket</p>
<p>Please share your thoughts on how we’re doing and what we’re missing.</p>
<h3>Enjoying Markets Daily? You might also like:</h3>
<p>Odd Lots for Joe Weisenthal</p>
</body></html>
"""


def test_morning_html_keeps_stories_and_drops_ads():
    parsed = parse_raw(
        _raw(
            html=MORNING_MAIL,
            text="광고가 섞인 원문",
        )
    )
    assert [item["headline"] for item in parsed["items"]] == ["美 9월 CPI", "반도체", "유가"]
    assert "근원 CPI도 0.3% 올랐다." in parsed["items"][0]["body"]
    assert "최다열람" not in parsed["items"][-1]["body"]
    assert parsed["lead"] == "뉴욕증시는 크게 하락했다."
    assert parsed["markets"] == [{"name": "S&P 500 지수", "value": "7,718.94", "change": "-1.1%"}]
    assert "팔로우" not in parsed["text"]
    assert "구독하실 수 있습니다" not in parsed["text"]
    assert parsed["body_parsed"] is True


def test_markets_html_keeps_sections_and_drops_promos():
    parsed = parse_raw(
        _raw(
            series="markets_daily",
            subject="Markets Daily: Calm no more - Plus, CoreWeave",
            html=MARKETS_MAIL,
            text="광고가 섞인 원문",
        )
    )
    assert [section["heading"] for section in parsed["sections"]] == [
        "Five things you need to know",
        "Calm shattered",
        "What else we’re reading",
    ]
    assert parsed["sections"][0]["body"] == "Stocks fell as the AI trade cracked."
    assert "Tech stocks faced heavy losses." in parsed["sections"][1]["body"]
    assert "Please share your thoughts" not in parsed["text"]
    assert "Odd Lots" not in parsed["text"]
    assert "Follow the news" not in parsed["text"]
    assert parsed["secondary"] == "CoreWeave"


def test_unknown_series_uses_generic_parser():
    parsed = parse_raw(_raw(series="money_stuff", subject="Money Stuff: something", text="본문입니다. " * 30))
    assert parsed["parser"] == "generic"
    assert parsed["body_parsed"] is True
    assert parsed["raw_path"] == "data/raw/money_stuff/2026-10-15/abc123.json"
