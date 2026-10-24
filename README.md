# bloomberg-digest

`bloomberg` 라벨 안에서 고른 레터만 매일 JSON으로 남깁니다. 지금은 두 시리즈입니다.

- 오늘 아침 꼭 알아야 할 5가지
- Markets Daily

시리즈를 늘리려면 `config/series.json`에 항목을 추가합니다. 전용 파서가 없는 id는 제목과 본문만 저장합니다.

메일은 두 겹으로 쌓입니다.

- `data/raw/` 원문. 다시 뽑을 때 씁니다.
- `data/extracted/` 제목에서 뽑은 훅, 항목, 리드. 주간·월간은 이 파일을 모아서 만듭니다.

이미 저장한 Gmail 메시지 id는 다시 받지 않습니다.

## 준비

Python 3.10이 필요합니다.

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Gmail은 읽기 권한만 씁니다. 보내기, 삭제, 라벨 변경은 하지 않습니다.

1. [Google Cloud](https://console.cloud.google.com)에서 프로젝트를 만듭니다.
2. Gmail API를 켭니다.
3. OAuth 동의 화면에서 사용자 유형은 외부로 두고, 범위에 `https://www.googleapis.com/auth/gmail.readonly`를 넣습니다. 테스트 사용자에 본인 Gmail을 추가합니다.
4. 게시 상태를 **프로덕션**으로 바꿉니다. 테스트로 두면 새로고침 토큰이 7일 뒤 끊깁니다. 본인만 쓰는 앱이면 검증 신청은 필요 없고, 첫 로그인에서 확인되지 않은 앱 경고가 나오면 계속 진행하면 됩니다.
5. 사용자 인증 정보에서 OAuth 클라이언트 ID를 만듭니다. 애플리케이션 유형은 **데스크톱 앱**입니다.
6. JSON을 내려받아 프로젝트 루트의 `credentials.json`으로 저장합니다.

```bash
python -m app auth
python -m app ingest --days 14
python -m app status
```

`auth`는 브라우저를 엽니다. 권한은 Gmail 읽기만 허용하면 됩니다. 토큰은 `token.json`에 저장되며, 둘 다 git에 올라가지 않습니다.

매일 아침에는 같은 디렉터리에서 아래만 실행하면 됩니다.

```bash
python -m app ingest
```

기본은 최근 3일입니다. 이미 저장한 메일은 건너뜁니다.

저장하지 않고 제목만 보려면 `python -m app ingest --dry-run`입니다. 추출 방식을 고친 뒤에는 `python -m app extract`로 원문에서 추출본만 다시 만듭니다.

본문 항목은 번호 목록과 HTML 목록을 기준으로 뽑습니다. 실제 메일 모양이 다르면 원문은 그대로 두고 파서만 고치면 됩니다. 제목의 훅은 본문 파서와 따로 저장됩니다.
