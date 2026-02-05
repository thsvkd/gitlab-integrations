# GitLab Integrations

[한국어](README.ko.md)

Integration service for **self-hosted (on-premise) GitLab** with external services (Slack, Notion, etc.)

> **Note**: This project is designed for **self-hosted GitLab servers** (GitLab CE/EE installed on your own infrastructure), not for GitLab.com (SaaS). It bridges your internal GitLab instance with external collaboration tools.

## Features

### Slack Integration
- **Slack → GitLab**: Create issues with `/issue` command
- **GitLab → Slack**: Notifications for issue status changes
- **Status Check**: Check issue status with `/issue status #123`

### Notion Integration
- **GitLab → Notion**: Auto-sync issues to Notion database (real-time via webhook)
- **Notion → GitLab**: Sync changes back to GitLab (polling-based)
- **Conflict Resolution**: Last Write Wins (LWW) strategy

## Architecture

```
        Internal Network                          External Services
    ┌───────────────────────┐                   ┌───────────────────┐
    │                       │                   │                   │
    │  ┌─────────────────┐  │    Webhook/API    │  ┌─────────────┐  │
    │  │ GitLab Server   │◄─┼───────────────────┼──│   Slack     │  │
    │  │ (self-hosted)   │  │                   │  │             │  │
    │  └────────┬────────┘  │                   │  └──────┬──────┘  │
    │           │           │                   │         │         │
    │           │ Webhook   │                   │  Slash  │         │
    │           ▼           │                   │ Command │         │
    │  ┌─────────────────┐  │   Tunnel/Proxy    │         │         │
    │  │  Integration    │◄─┼───────────────────┼─────────┘         │
    │  │  Server         │──┼───────────────────┼──────────────────►│
    │  │  (FastAPI)      │  │  (Cloudflare,     │                   │
    │  └────────┬────────┘  │   Tailscale, etc) │  ┌─────────────┐  │
    │           │           │                   │  │   Notion    │  │
    │           └───────────┼───────────────────┼─►│  Database   │  │
    │              Polling  │                   │  └─────────────┘  │
    │                       │                   │                   │
    └───────────────────────┘                   └───────────────────┘
```

**Key Points:**
- GitLab server runs on internal network (not accessible from internet)
- Integration server bridges internal GitLab with external services
- External access via tunnel (Cloudflare Tunnel, Tailscale, etc.) or reverse proxy
- Supports self-signed SSL certificates commonly used in internal servers

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

## 4. Notion Configuration (Optional)

> **Note**: Notion integration is optional. Skip this section if you only need Slack integration.

### Step 1: Create Notion Integration

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click **+ New integration**
3. Enter the following:

| Field | Value |
|-------|-------|
| Name | `GitLab Issue Sync` |
| Associated workspace | Select your workspace |
| Type | Internal |

4. Click **Submit**
5. Copy the **Internal Integration Secret** (starts with `secret_`)

### Step 2: Create Notion Database

Create a new database in Notion with the following properties:

| Property Name | Type | Description |
|---------------|------|-------------|
| Title | Title | Issue title (default property) |
| Status | Select | Options: `opened`, `closed` |
| Labels | Multi-select | GitLab labels |
| GitLab IID | Number | Issue number in GitLab |
| GitLab URL | URL | Link to GitLab issue |
| Author | Text | Issue author name |
| Description | Text | Issue description |
| Created At | Date | Issue creation date |
| Updated At | Date | Last update date |
| Last Synced | Date | Last sync timestamp |

> ⚠️ **Important**: Property names must match **exactly** as shown above (case-sensitive).

**Quick Setup:**
1. Create a new page in Notion
2. Type `/database` and select **Database - Full page**
3. Add each property with the exact names and types listed above
4. For **Status** property, add two options: `opened` and `closed`

### Step 3: Connect Integration to Database

> ⚠️ **Important**: You must connect the Integration to the **database itself**, not just the page containing it.

**For Full-page Database:**
1. Open the database as a full page (click ↗️ or "Open as full page")
2. Click **...** (menu) in the top-right corner
3. Click **+ Add connections**
4. Search for and select your integration (`GitLab Issue Sync`)
5. Click **Confirm**

**For Inline Database:**
1. Open the page that contains the database
2. Click **...** (menu) in the top-right corner of the **page**
3. Click **+ Add connections**
4. Select your integration - it will apply to all databases in that page

> **Tip**: If the integration doesn't appear in the connection list, try refreshing the page or check that the integration is set to "Internal" type.

### Step 4: Get Database ID

1. Open your Notion database in a browser
2. The URL looks like: `https://www.notion.so/workspace/DATABASE_ID?v=...`
3. Copy the **DATABASE_ID** part (32-character string)

Example:
```
URL: https://www.notion.so/myworkspace/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6?v=...
Database ID: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

> **Tip**: The database ID can also be found in "Copy link" - it's the part before the `?v=` parameter.

---

## 5. Environment Variables

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

# Notion settings (optional)
NOTION_TOKEN=secret_xxxxxxxxxxxxxxxxxxxx       # Integration Secret
NOTION_DATABASE_ID=a1b2c3d4e5f6...             # Database ID (32 characters)
NOTION_SYNC_ENABLED=true                       # Enable sync (true/false)
NOTION_SYNC_INTERVAL=60                        # Polling interval in seconds

# Server settings
HOST=0.0.0.0
PORT=8000
```

### Notion Settings Explained

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NOTION_TOKEN` | Yes* | - | Integration secret from Step 1 |
| `NOTION_DATABASE_ID` | Yes* | - | Database ID from Step 4 |
| `NOTION_SYNC_ENABLED` | No | `false` | Set to `true` to enable sync |
| `NOTION_SYNC_INTERVAL` | No | `60` | How often to poll Notion (seconds) |

> *Required only if `NOTION_SYNC_ENABLED=true`

---

## 6. Running

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

## 7. Usage

### Create Issue

Type `/issue` in Slack → Enter information in modal popup → Click Create

```
/issue
```

**Modal Fields:**
- **Title**: Issue title (required)
- **Description**: Detailed description (optional)
- **Labels**: Select from existing GitLab labels (optional, multi-select)

> **Note**: Labels are dynamically loaded from your GitLab project. Only existing labels will appear in the dropdown.

### Check Issue Status

```
/issue status 123
/issue status #123
```

### Notion Sync (if enabled)

**GitLab → Notion (Automatic)**
- When issues are created/updated/closed in GitLab, they automatically sync to Notion
- Triggered by GitLab webhooks (real-time)

**Notion → GitLab (Polling)**
- Changes made in Notion are synced back to GitLab
- Runs every 60 seconds (configurable via `NOTION_SYNC_INTERVAL`)
- Editable fields in Notion:
  - **Title** → Updates GitLab issue title
  - **Status** → `closed` closes the issue, `opened` reopens it
  - **Labels** → Updates GitLab labels
  - **Description** → Updates GitLab description

**Conflict Resolution**
- If both GitLab and Notion are modified since last sync, **Last Write Wins** (LWW)
- The more recently modified side takes precedence

---

## 8. Troubleshooting

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

### Notion Sync Errors

#### "Notion token is not configured"

**Cause**: `NOTION_TOKEN` not set while sync is enabled

**Solution**: Add valid `NOTION_TOKEN` to `.env` or set `NOTION_SYNC_ENABLED=false`

#### "Notion database ID is not configured"

**Cause**: `NOTION_DATABASE_ID` not set while sync is enabled

**Solution**: Add valid `NOTION_DATABASE_ID` to `.env`

#### Issues not syncing to Notion

**Check**:
1. Verify `NOTION_SYNC_ENABLED=true` in `.env`
2. Verify the Integration is connected to the database (Step 3 in Notion Configuration)
3. Check server logs for API errors
4. Verify database property names match exactly (case-sensitive)

#### Notion changes not syncing to GitLab

**Check**:
1. Wait for the polling interval (default 60 seconds)
2. Verify the page has a valid `GitLab IID` property
3. Check server logs for sync errors

---

## 9. Development

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
