# GitLab-Slack Integration

[English](README.md)

GitLab과 Slack 간의 이슈 연동 서비스

## 기능

- **Slack → GitLab**: `/issue` 커맨드로 이슈 생성
- **GitLab → Slack**: 이슈 상태 변경 알림
- **상태 조회**: `/issue status #123`으로 이슈 상태 확인

## 아키텍처

```
┌─────────────┐     ┌─────────────────────┐     ┌──────────────┐
│   GitLab    │────►│  Integration Server │◄────│    Slack     │
│   (inner)   │◄────│      (FastAPI)      │────►│  (external)  │
└─────────────┘     └─────────────────────┘     └──────────────┘
      │                       │                       │
      │ Webhook               │                       │ Slash Command
      │ (issue update notify) │                       │ (/issue)
      └───────────────────────┴───────────────────────┘
```

---

## 1. 설치

### 요구사항

- Python 3.10+
- uv (패키지 관리자)

### 설치 방법

```bash
# 저장소 클론
git clone <repository-url>
cd gitlab-slack-integration

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
| Token name      | `slack-integration`   |
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

## 4. 환경변수 설정

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

# 서버 설정
HOST=0.0.0.0
PORT=8000
```

---

## 5. 실행

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
python -m gitlab_slack.main --port 9000
```

### Docker 실행

```bash
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

---

## 6. 사용법

### 이슈 생성

Slack에서 `/issue` 입력 → 모달 팝업에서 정보 입력 → 생성하기

```
/issue
```

### 이슈 상태 조회

```
/issue status 123
/issue status #123
```

---

## 7. 트러블슈팅

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
python -m gitlab_slack.main --port 9000
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

**해결**: `src/gitlab_slack/gitlab/api.py`에서 `ssl_verify=False` 확인
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

## 8. 개발

### 테스트 실행

```bash
pytest
```

### 코드 포맷팅

```bash
ruff check --fix .
ruff format .
```
