# GitLab Integrations

[한국어](README.ko.md)

Integration service between GitLab and external services (Slack, Notion, etc.)

## Features

### Slack Integration
- **Slack → GitLab**: Create issues with `/issue` command
- **GitLab → Slack**: Notifications for issue status changes
- **Status Check**: Check issue status with `/issue status #123`

### Coming Soon
- Notion integration

## Architecture

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

## 1. Installation

### Requirements

- Python 3.10+
- uv (package manager)

### Setup

```bash
# Clone repository
git clone <repository-url>
cd gitlab-integrations

# Setup environment (creates venv + installs packages + generates .env)
./scripts/setup.sh

# Edit .env file
vi .env
```

---

## 2. Slack App Configuration

### Step 1: Create Slack App

1. Go to [Slack API page](https://api.slack.com/apps)
2. Click **Create New App**
3. Select **From scratch**
4. Enter App name (e.g., `GitLab Issue Bot`)
5. Select workspace and click **Create App**

### Step 2: Configure Bot Token Scopes

1. Click **OAuth & Permissions** in the left menu
2. In **Scopes** section, add the following **Bot Token Scopes**:

| Scope               | Purpose                                    |
| ------------------- | ------------------------------------------ |
| `chat:write`        | Send messages to channels                  |
| `chat:write.public` | Send messages to public channels bot isn't in |
| `commands`          | Use Slash commands                         |

### Step 3: Register Slash Command

1. Click **Slash Commands** in the left menu
2. Click **Create New Command**
3. Enter the following:

| Field             | Value                                  |
| ----------------- | -------------------------------------- |
| Command           | `/issue`                               |
| Request URL       | `https://<your-domain>/slack/commands` |
| Short Description | `Create and view GitLab issues`        |
| Usage Hint        | `[status #number]`                     |

4. Click **Save**

> ⚠️ **Warning**: Request URL must be the **Integration Server's externally accessible URL**.
> NOT the GitLab server URL!
>
> Example:
> - ✅ `https://your-app.company.com/slack/commands`
> - ❌ `https://gitlab.company.com/slack/commands`

### Step 4: Enable Interactivity (Required!)

> ⚠️ **Without this setting, you'll get "There was a problem connecting" error when submitting Modal.**

1. Click **Interactivity & Shortcuts** in the left menu
2. Toggle **Interactivity** to **On**
3. Enter **Request URL**: `https://<your-domain>/slack/interactions`
4. Click **Save Changes**

> ⚠️ **Warning**: Same as Step 3, enter the **Integration Server's external URL**.
> Shortcuts and Select Menus settings are not required.

### Step 5: Install App and Get Token

1. Click **OAuth & Permissions** in the left menu
2. Click **Install to Workspace**
3. Confirm permissions and click **Allow**
4. Copy the generated **Bot User OAuth Token** (starts with `xoxb-`)

### Step 6: Get Signing Secret

1. Click **Basic Information** in the left menu
2. Copy **Signing Secret** from **App Credentials** section

### Step 7: Get Channel ID

1. Right-click the channel to receive notifications in Slack
2. Click **View channel details**
3. Copy **Channel ID** at the bottom (string starting with `C`)

---

## 3. GitLab Configuration

### Step 1: Create Personal Access Token

1. Go to GitLab → Profile icon (top right) → **Preferences**
2. Click **Access Tokens** in the left menu
3. Click **Add new token**
4. Enter the following:

| Field           | Value                   |
| --------------- | ----------------------- |
| Token name      | `gitlab-integrations`   |
| Expiration date | Choose appropriate date |
| Scopes          | `api` (full API access) |

5. Click **Create personal access token**
6. Copy the generated token (you won't see it again after leaving this page)

### Step 2: Find Project ID

1. Go to the GitLab project page you want to integrate
2. **Project ID** is displayed below the project name
3. Or check in **Settings → General**

### Step 3: Configure Webhook

1. Go to GitLab project → **Settings → Webhooks**
2. Click **Add new webhook**
3. Enter the following:

| Field            | Value                                           |
| ---------------- | ----------------------------------------------- |
| URL              | `https://<your-domain>/gitlab/webhook`          |
| Secret token     | Same value as `GITLAB_WEBHOOK_SECRET` in `.env` |
| Trigger          | ✅ Issues events                                 |
| SSL verification | Choose based on environment                     |

4. Click **Add webhook**

> **How to generate Secret token**
> ```bash
> # Method 1: Using openssl
> openssl rand -hex 32
>
> # Method 2: Using Python
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

---

## 4. Environment Variables

Open `.env` file and enter the following values:

```bash
# GitLab settings
GITLAB_URL=https://gitlab.your-company.com    # GitLab server URL
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx       # Personal Access Token
GITLAB_PROJECT_ID=123                          # Project ID
GITLAB_WEBHOOK_SECRET=your-secret-token       # Webhook verification (same as GitLab Webhook setting)

# Slack settings
SLACK_BOT_TOKEN=xoxb-xxxx-xxxx-xxxx           # Bot User OAuth Token
SLACK_SIGNING_SECRET=xxxxxxxxxxxxxxxxxxxxxxx   # Signing Secret
SLACK_CHANNEL_ID=C0123456789                   # Notification channel ID

# Server settings
HOST=0.0.0.0
PORT=8000
```

---

## 5. Running

### Run with Script (Recommended)

```bash
# Default run (uses HOST, PORT from .env)
./scripts/run.sh

# Run on different port
./scripts/run.sh --port 9000

# Specify host and port
./scripts/run.sh --host 0.0.0.0 --port 9000
```

### Direct Run

```bash
source .venv/bin/activate
python -m gitlab_integrations.main --port 9000
```

### Docker Run

```bash
docker-compose up -d

# Check logs
docker-compose logs -f
```

---

## 6. Usage

### Create Issue

Type `/issue` in Slack → Enter information in modal popup → Click Create

```
/issue
```

### Check Issue Status

```
/issue status 123
/issue status #123
```

---

## 7. Troubleshooting

### Slack `/issue` Command Errors

#### "Error with /issue command" (dispatch_failed)

**Cause**: Slack cannot send request to Integration Server

**Check**:
1. **Verify Slash Commands Request URL**
   - Slack API Dashboard → Slash Commands → Select `/issue`
   - Confirm Request URL is set to `https://<your-domain>/slack/commands`
   - ⚠️ Must be **Integration Server URL**, not GitLab URL

2. **Check server status**
   ```bash
   curl https://<your-domain>/health
   # Confirm {"status": "healthy"} response
   ```

3. **Check server logs**
   - No requests: URL configuration issue
   - 401 error: Signing Secret mismatch
   - 502 error: Server not running

#### "There was a problem connecting" (When submitting Modal)

**Cause**: Interactivity not configured

**Solution**:
1. Slack API Dashboard → **Interactivity & Shortcuts**
2. Verify **Interactivity** toggle is **On**
3. Verify **Request URL** is set to `https://<your-domain>/slack/interactions`
4. Click **Save Changes**

---

### GitLab Webhook Errors

#### HTTP 422 Error

**Cause**: Webhook URL incorrectly configured (pointing to GitLab server itself)

**Check**:
```
❌ https://gitlab.company.com/gitlab/webhook  (GitLab URL)
✅ https://your-app.domain.com/gitlab/webhook  (Integration Server URL)
✅ http://localhost:9000/gitlab/webhook  (if on same server)
```

#### HTTP 502 Error

**Cause**: Integration Server is not running

**Solution**:
```bash
# Run server
source .venv/bin/activate
python -m gitlab_integrations.main --port 9000
```

#### SSL certificate verify failed (self-signed certificate)

**Cause**: GitLab server uses self-signed certificate

**Solution**: Already handled with `ssl_verify=False` in code. Also uncheck **Enable SSL verification** in GitLab Webhook settings.

---

### GitLab API Errors

#### "SSL: CERTIFICATE_VERIFY_FAILED"

**Symptom**: SSL error when creating issue
```
SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate'))
```

**Cause**: GitLab server uses self-signed certificate

**Solution**: Verify `ssl_verify=False` in `src/gitlab_integrations/gitlab/api.py`
```python
gl = gitlab.Gitlab(
    settings.gitlab_url,
    private_token=settings.gitlab_token,
    ssl_verify=False,  # Allow self-signed certificates
)
```

#### Other API Errors

- Verify `GITLAB_TOKEN` is valid
- Verify token has `api` scope
- Verify `GITLAB_URL` is correct (no trailing `/`)

---

### Installation Errors

#### "ensurepip is not available" (Ubuntu/Debian)

**Solution**:
```bash
sudo apt install python3.10-venv
```

#### "requires a different Python: 3.10 not in '>=3.11'"

**Cause**: Python version compatibility

**Solution**: Already configured as `requires-python = ">=3.10"` in `pyproject.toml`

---

### URL Configuration Summary

Summary of easily confused URL settings:

| Setting Location | URL Type | Example |
|------------------|----------|---------|
| `GITLAB_URL` in `.env` | GitLab server URL | `https://gitlab.company.com` |
| GitLab Webhook URL | Integration Server URL | `http://localhost:9000/gitlab/webhook` |
| Slack Slash Commands | Integration Server URL (external) | `https://your-app.domain.com/slack/commands` |
| Slack Interactivity | Integration Server URL (external) | `https://your-app.domain.com/slack/interactions` |

**Key Point**:
- Only `GITLAB_URL` in `.env` is the GitLab server URL
- Everything else is the **Integration Server URL**

---

## 8. Development

### Run Tests

```bash
./scripts/test.sh
./scripts/test.sh --cov  # with coverage
```

### Code Formatting

```bash
ruff check --fix .
ruff format .
```
