# GitLab Integrations

[English](README.md)

**자체 호스팅 (온프레미스) GitLab**과 외부 서비스 (Slack, Notion 등) 간의 연동 서비스

> **참고**: 이 프로젝트는 **자체 호스팅 GitLab 서버** (사내 인프라에 설치된 GitLab CE/EE)를 위한 것입니다. GitLab.com (SaaS)이 아닌, 내부 GitLab 인스턴스를 외부 협업 도구와 연결합니다.

## 기능

### Slack 연동
- **Slack → GitLab**: `/issue` 커맨드로 이슈 생성
- **GitLab → Slack**: 이슈 상태 변경 알림
- **상태 조회**: `/issue status #123`으로 이슈 상태 확인

### Notion 연동
- **GitLab → Notion**: 이슈를 Notion 데이터베이스에 자동 동기화 (웹훅을 통한 실시간)
- **Notion → GitLab**: Notion 변경사항을 GitLab으로 동기화 (폴링 방식)
- **충돌 해결**: Last Write Wins (LWW) - 최신 수정 우선

## 아키텍처

```
           내부 네트워크                              외부 서비스
    ┌───────────────────────┐                   ┌───────────────────┐
    │                       │                   │                   │
    │  ┌─────────────────┐  │    Webhook/API    │  ┌─────────────┐  │
    │  │ GitLab 서버     │◄─┼───────────────────┼──│   Slack     │  │
    │  │ (자체 호스팅)   │  │                   │  │             │  │
    │  └────────┬────────┘  │                   │  └──────┬──────┘  │
    │           │           │                   │         │         │
    │           │ Webhook   │                   │  Slash  │         │
    │           ▼           │                   │ Command │         │
    │  ┌─────────────────┐  │   터널/프록시     │         │         │
    │  │  Integration    │◄─┼───────────────────┼─────────┘         │
    │  │  Server         │──┼───────────────────┼──────────────────►│
    │  │  (FastAPI)      │  │  (Cloudflare,     │                   │
    │  └────────┬────────┘  │   Tailscale 등)   │  ┌─────────────┐  │
    │           │           │                   │  │   Notion    │  │
    │           └───────────┼───────────────────┼─►│ 데이터베이스│  │
    │              폴링     │                   │  └─────────────┘  │
    │                       │                   │                   │
    └───────────────────────┘                   └───────────────────┘
```

**핵심 포인트:**
- GitLab 서버는 내부 네트워크에서 실행 (인터넷에서 직접 접근 불가)
- Integration 서버가 내부 GitLab과 외부 서비스를 연결하는 다리 역할
- 터널 (Cloudflare Tunnel, Tailscale 등) 또는 리버스 프록시를 통해 외부 접근
- 내부 서버에서 흔히 사용하는 자체 서명 SSL 인증서 지원

---

## 1. 설치

### 요구사항

- Python 3.10+
- uv (패키지 관리자)

### 설치 방법

```bash
# 저장소 클론
git clone <repository-url>
cd gitlab-integrations

# 환경 설정 (가상환경 생성 + 패키지 설치 + .env 파일 생성)
./scripts/setup.sh

# .env 파일 편집
vi .env
```

---

## 2. Slack App 설정

### Step 1: Slack App 생성

1. [Slack API 페이지](https://api.slack.com/apps) 접속
2. **Create New App** 클릭
3. **From scratch** 선택
4. App 이름 입력 (예: `GitLab Issue Bot`)
5. 워크스페이스 선택 후 **Create App**

### Step 2: Bot Token Scopes 설정

1. 좌측 메뉴에서 **OAuth & Permissions** 클릭
2. **Scopes** 섹션에서 **Bot Token Scopes**에 다음 권한 추가:

| Scope               | 용도                                         |
| ------------------- | -------------------------------------------- |
| `chat:write`        | 채널에 메시지 전송                           |
| `chat:write.public` | 봇이 참여하지 않은 public 채널에 메시지 전송 |
| `commands`          | Slash 커맨드 사용                            |

### Step 3: Slash Command 등록

1. 좌측 메뉴에서 **Slash Commands** 클릭
2. **Create New Command** 클릭
3. 다음 정보 입력:

| 필드              | 값                                     |
| ----------------- | -------------------------------------- |
| Command           | `/issue`                               |
| Request URL       | `https://<your-domain>/slack/commands` |
| Short Description | `GitLab 이슈 생성 및 조회`             |
| Usage Hint        | `[status #번호]`                       |

4. **Save** 클릭

> ⚠️ **주의**: Request URL은 **Integration Server의 외부 접근 가능한 URL**입니다.
> GitLab 서버 URL이 아닙니다!
>
> 예시:
> - ✅ `https://your-app.company.com/slack/commands`
> - ❌ `https://gitlab.company.com/slack/commands`

### Step 4: Interactivity 활성화 (필수!)

> ⚠️ **이 설정을 하지 않으면 Modal에서 "연결하는 데 문제가 발생했습니다" 에러가 발생합니다.**

1. 좌측 메뉴에서 **Interactivity & Shortcuts** 클릭
2. **Interactivity** 토글을 **On**으로 변경
3. **Request URL** 입력: `https://<your-domain>/slack/interactions`
4. **Save Changes** 클릭

> ⚠️ **주의**: Step 3과 마찬가지로 **Integration Server의 외부 URL**을 입력합니다.
> Shortcuts, Select Menus 설정은 필요 없습니다.

### Step 5: App 설치 및 토큰 획득

1. 좌측 메뉴에서 **OAuth & Permissions** 클릭
2. **Install to Workspace** 클릭
3. 권한 요청 확인 후 **허용**
4. 생성된 **Bot User OAuth Token** 복사 (`xoxb-`로 시작)

### Step 6: Signing Secret 획득

1. 좌측 메뉴에서 **Basic Information** 클릭
2. **App Credentials** 섹션에서 **Signing Secret** 복사

### Step 7: 채널 ID 확인

1. Slack에서 알림 받을 채널 우클릭
2. **채널 세부정보 보기** 클릭
3. 하단의 **채널 ID** 복사 (`C`로 시작하는 문자열)

---

## 3. GitLab 설정

### Step 1: Personal Access Token 생성

1. GitLab 접속 → 우측 상단 프로필 아이콘 → **Preferences**
2. 좌측 메뉴에서 **Access Tokens** 클릭
3. **Add new token** 클릭
4. 다음 정보 입력:

| 필드            | 값                    |
| --------------- | --------------------- |
| Token name      | `gitlab-integrations` |
| Expiration date | 적절한 만료일 선택    |
| Scopes          | `api` (전체 API 접근) |

5. **Create personal access token** 클릭
6. 생성된 토큰 복사 (이 화면을 벗어나면 다시 볼 수 없음)

### Step 2: Project ID 확인

1. 연동할 GitLab 프로젝트 페이지 접속
2. 프로젝트 이름 아래에 **Project ID** 표시됨
3. 또는 **Settings → General**에서 확인

### Step 3: Webhook 설정

1. GitLab 프로젝트 → **Settings → Webhooks**
2. **Add new webhook** 클릭
3. 다음 정보 입력:

| 필드             | 값                                              |
| ---------------- | ----------------------------------------------- |
| URL              | `https://<your-domain>/gitlab/webhook`          |
| Secret token     | `.env`의 `GITLAB_WEBHOOK_SECRET`과 동일한 값    |
| Trigger          | ✅ Issues events                                 |
| SSL verification | 환경에 맞게 선택                                |

4. **Add webhook** 클릭

> **Secret token 생성 방법**
> ```bash
> # 방법 1: openssl 사용
> openssl rand -hex 32
>
> # 방법 2: Python 사용
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

---

## 4. Notion 설정 (선택사항)

> **참고**: Notion 연동은 선택사항입니다. Slack 연동만 필요하면 이 섹션을 건너뛰세요.

### Step 1: Notion Integration 생성

1. [Notion Integrations](https://www.notion.so/my-integrations) 접속
2. **+ New integration** 클릭
3. 다음 정보 입력:

| 필드 | 값 |
|------|------|
| Name | `GitLab Issue Sync` |
| Associated workspace | 워크스페이스 선택 |
| Type | Internal |

4. **Submit** 클릭
5. **Internal Integration Secret** 복사 (`secret_`로 시작)

### Step 2: Notion 데이터베이스 생성

다음 속성을 가진 새 데이터베이스를 Notion에 생성합니다:

| 속성 이름 | 타입 | 설명 |
|-----------|------|------|
| Title | Title | 이슈 제목 (기본 속성) |
| Status | Select | 옵션: `opened`, `closed` |
| Labels | Multi-select | GitLab 라벨 |
| GitLab IID | Number | GitLab 이슈 번호 |
| GitLab URL | URL | GitLab 이슈 링크 |
| Author | Text | 이슈 작성자 |
| Description | Text | 이슈 설명 |
| Created At | Date | 이슈 생성일 |
| Updated At | Date | 마지막 수정일 |
| Last Synced | Date | 마지막 동기화 시간 |

> ⚠️ **중요**: 속성 이름은 위에 표시된 대로 **정확히** 일치해야 합니다 (대소문자 구분).

**빠른 설정:**
1. Notion에서 새 페이지 생성
2. `/database` 입력 후 **Database - Full page** 선택
3. 위 목록의 정확한 이름과 타입으로 각 속성 추가
4. **Status** 속성에 두 옵션 추가: `opened`, `closed`

### Step 3: Integration과 데이터베이스 연결

> ⚠️ **중요**: 데이터베이스가 있는 페이지가 아니라 **데이터베이스 자체**에 Integration을 연결해야 합니다.

**Full-page Database (전체 페이지 데이터베이스):**
1. 데이터베이스를 전체 페이지로 열기 (↗️ 클릭 또는 "Open as full page")
2. 우측 상단 **...** (메뉴) 클릭
3. **+ Add connections** 클릭
4. Integration 검색 및 선택 (`GitLab Issue Sync`)
5. **Confirm** 클릭

**Inline Database (인라인 데이터베이스):**
1. 데이터베이스가 포함된 페이지 열기
2. **페이지**의 우측 상단 **...** (메뉴) 클릭
3. **+ Add connections** 클릭
4. Integration 선택 - 해당 페이지의 모든 데이터베이스에 적용됨

> **팁**: 연결 목록에 Integration이 보이지 않으면 페이지를 새로고침하거나, Integration 타입이 "Internal"로 설정되어 있는지 확인하세요.

### Step 4: Database ID 확인

1. 브라우저에서 Notion 데이터베이스 열기
2. URL 형식: `https://www.notion.so/workspace/DATABASE_ID?v=...`
3. **DATABASE_ID** 부분 복사 (32자 문자열)

예시:
```
URL: https://www.notion.so/myworkspace/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6?v=...
Database ID: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

> **팁**: "Copy link"에서도 Database ID를 찾을 수 있습니다 - `?v=` 앞의 부분입니다.

---

## 5. 환경변수 설정

`.env` 파일을 열고 다음 값들을 입력:

```bash
# GitLab 설정
GITLAB_URL=https://gitlab.your-company.com    # GitLab 서버 주소
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx       # Personal Access Token
GITLAB_PROJECT_ID=123                          # 프로젝트 ID
GITLAB_WEBHOOK_SECRET=your-secret-token       # Webhook 검증용 (GitLab Webhook 설정과 동일하게)

# Slack 설정
SLACK_BOT_TOKEN=xoxb-xxxx-xxxx-xxxx           # Bot User OAuth Token
SLACK_SIGNING_SECRET=xxxxxxxxxxxxxxxxxxxxxxx   # Signing Secret
SLACK_CHANNEL_ID=C0123456789                   # 알림 채널 ID

# Notion 설정 (선택사항)
NOTION_TOKEN=secret_xxxxxxxxxxxxxxxxxxxx       # Integration Secret
NOTION_DATABASE_ID=a1b2c3d4e5f6...             # Database ID (32자)
NOTION_SYNC_ENABLED=true                       # 동기화 활성화 (true/false)
NOTION_SYNC_INTERVAL=60                        # 폴링 간격 (초)

# 서버 설정
HOST=0.0.0.0
PORT=8000
```

### Notion 설정 설명

| 변수 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `NOTION_TOKEN` | 예* | - | Step 1에서 얻은 Integration secret |
| `NOTION_DATABASE_ID` | 예* | - | Step 4에서 얻은 Database ID |
| `NOTION_SYNC_ENABLED` | 아니오 | `false` | `true`로 설정하면 동기화 활성화 |
| `NOTION_SYNC_INTERVAL` | 아니오 | `60` | Notion 폴링 간격 (초) |

> *`NOTION_SYNC_ENABLED=true`인 경우에만 필수

---

## 6. 실행

### 스크립트로 실행 (권장)

```bash
# 기본 실행 (.env의 HOST, PORT 사용)
./scripts/run.sh

# 다른 포트로 실행
./scripts/run.sh --port 9000

# 호스트와 포트 지정
./scripts/run.sh --host 0.0.0.0 --port 9000
```

### 직접 실행

```bash
source .venv/bin/activate
python -m gitlab_integrations.main --port 9000
```

### Docker 실행

```bash
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

---

## 7. 사용법

### 이슈 생성

Slack에서 `/issue` 입력 → 모달 팝업에서 정보 입력 → 생성하기

```
/issue
```

**모달 필드:**
- **Title**: 이슈 제목 (필수)
- **Description**: 상세 설명 (선택)
- **Labels**: GitLab 기존 라벨에서 선택 (선택, 다중 선택 가능)

> **참고**: 라벨 목록은 GitLab 프로젝트에서 동적으로 불러옵니다. 기존에 생성된 라벨만 드롭다운에 표시됩니다.

### 이슈 상태 조회

```
/issue status 123
/issue status #123
```

### Notion 동기화 (활성화된 경우)

**GitLab → Notion (자동)**
- GitLab에서 이슈 생성/수정/닫기 시 자동으로 Notion에 동기화
- GitLab 웹훅을 통해 실시간 동작

**Notion → GitLab (폴링)**
- Notion에서 변경한 내용이 GitLab에 동기화됨
- 60초마다 실행 (`NOTION_SYNC_INTERVAL`로 설정 가능)
- Notion에서 수정 가능한 필드:
  - **Title** → GitLab 이슈 제목 업데이트
  - **Status** → `closed`면 이슈 닫힘, `opened`면 다시 열림
  - **Labels** → GitLab 라벨 업데이트
  - **Description** → GitLab 설명 업데이트

**충돌 해결**
- GitLab과 Notion 모두 마지막 동기화 이후 수정된 경우, **Last Write Wins** (LWW) 적용
- 더 최근에 수정된 쪽이 우선

---

## 8. 트러블슈팅

### Slack `/issue` 커맨드 실행 시 에러

#### "오류가 발생해 /issue에 실패했습니다" (dispatch_failed)

**원인**: Slack이 Integration Server에 요청을 보내지 못함

**확인 사항**:
1. **Slash Commands의 Request URL** 확인
   - Slack API Dashboard → Slash Commands → `/issue` 선택
   - Request URL이 `https://<your-domain>/slack/commands`로 설정되어 있는지 확인
   - ⚠️ GitLab URL이 아닌 **Integration Server URL**이어야 함

2. **서버 실행 여부** 확인
   ```bash
   curl https://<your-domain>/health
   # {"status": "healthy"} 응답 확인
   ```

3. **서버 로그** 확인
   - 요청이 오지 않으면: URL 설정 문제
   - 401 에러: Signing Secret 불일치
   - 502 에러: 서버 미실행

#### "연결하는 데 문제가 발생했습니다" (Modal 제출 시)

**원인**: Interactivity 설정 누락

**해결**:
1. Slack API Dashboard → **Interactivity & Shortcuts**
2. **Interactivity** 토글이 **On**인지 확인
3. **Request URL**이 `https://<your-domain>/slack/interactions`로 설정되어 있는지 확인
4. **Save Changes** 클릭

---

### GitLab Webhook 에러

#### HTTP 422 에러

**원인**: Webhook URL이 잘못 설정됨 (GitLab 서버 자체를 가리킴)

**확인**:
```
❌ https://gitlab.company.com/gitlab/webhook  (GitLab URL)
✅ https://your-app.domain.com/gitlab/webhook  (Integration Server URL)
✅ http://localhost:9000/gitlab/webhook  (같은 서버인 경우)
```

#### HTTP 502 에러

**원인**: Integration Server가 실행 중이 아님

**해결**:
```bash
# 서버 실행
source .venv/bin/activate
python -m gitlab_integrations.main --port 9000
```

#### SSL certificate verify failed (self-signed certificate)

**원인**: GitLab 서버가 self-signed 인증서 사용

**해결**: 이미 코드에서 `ssl_verify=False`로 처리됨. GitLab Webhook 설정에서도 **Enable SSL verification** 체크 해제

---

### GitLab API 에러

#### "SSL: CERTIFICATE_VERIFY_FAILED"

**증상**: 이슈 생성 시 SSL 에러 발생
```
SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate'))
```

**원인**: GitLab 서버가 self-signed 인증서 사용

**해결**: `src/gitlab_integrations/gitlab/api.py`에서 `ssl_verify=False` 확인
```python
gl = gitlab.Gitlab(
    settings.gitlab_url,
    private_token=settings.gitlab_token,
    ssl_verify=False,  # self-signed 인증서 허용
)
```

#### 기타 API 에러

- `GITLAB_TOKEN`이 유효한지 확인
- 토큰에 `api` scope가 있는지 확인
- `GITLAB_URL`이 올바른지 확인 (끝에 `/` 없이)

---

### 설치 시 에러

#### "ensurepip is not available" (Ubuntu/Debian)

**해결**:
```bash
sudo apt install python3.10-venv
```

#### "requires a different Python: 3.10 not in '>=3.11'"

**원인**: Python 버전 호환성

**해결**: 이미 `pyproject.toml`에서 `requires-python = ">=3.10"`으로 설정됨

---

### URL 설정 정리

혼동하기 쉬운 URL 설정을 정리합니다:

| 설정 위치 | URL 종류 | 예시 |
|-----------|----------|------|
| `.env`의 `GITLAB_URL` | GitLab 서버 주소 | `https://gitlab.company.com` |
| GitLab Webhook URL | Integration Server 주소 | `http://localhost:9000/gitlab/webhook` |
| Slack Slash Commands | Integration Server 주소 (외부) | `https://your-app.domain.com/slack/commands` |
| Slack Interactivity | Integration Server 주소 (외부) | `https://your-app.domain.com/slack/interactions` |

**핵심**:
- `.env`의 `GITLAB_URL`만 GitLab 서버 주소
- 나머지는 모두 **Integration Server 주소**

---

### Notion 동기화 에러

#### "Notion token is not configured"

**원인**: 동기화가 활성화되었지만 `NOTION_TOKEN`이 설정되지 않음

**해결**: `.env`에 유효한 `NOTION_TOKEN` 추가 또는 `NOTION_SYNC_ENABLED=false` 설정

#### "Notion database ID is not configured"

**원인**: 동기화가 활성화되었지만 `NOTION_DATABASE_ID`가 설정되지 않음

**해결**: `.env`에 유효한 `NOTION_DATABASE_ID` 추가

#### 이슈가 Notion에 동기화되지 않음

**확인 사항**:
1. `.env`에 `NOTION_SYNC_ENABLED=true` 확인
2. Integration이 데이터베이스에 연결되었는지 확인 (Notion 설정 Step 3)
3. 서버 로그에서 API 에러 확인
4. 데이터베이스 속성 이름이 정확히 일치하는지 확인 (대소문자 구분)

#### Notion 변경사항이 GitLab에 동기화되지 않음

**확인 사항**:
1. 폴링 간격 대기 (기본 60초)
2. 페이지에 유효한 `GitLab IID` 속성이 있는지 확인
3. 서버 로그에서 동기화 에러 확인

---

## 9. 개발

### 테스트 실행

```bash
./scripts/test.sh
./scripts/test.sh --cov  # 커버리지 포함
```

### 코드 포맷팅

```bash
ruff check --fix .
ruff format .
```
