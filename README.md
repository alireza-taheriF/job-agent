# job-agent

**Two semi-autonomous job-search agents with a human in the loop.** They find work, score it against my real profile, draft the application, and wait for one tap on Telegram before anything is sent.

- **Agent 1: Karlancer** (Persian freelance market). Collects projects with Playwright, scores them, drafts Persian proposals and submits after approval.
- **Agent 2: International roles** (English). Pulls remote jobs *and* on-site jobs that offer relocation or visa sponsorship, scores fit and visa realism, writes the cover letter, emails the application when the posting gives an address.
- **Cold outreach.** Personalised emails to hiring managers from a contacts CSV, a daily send cap, one follow-up, and IMAP reply detection that stops the sequence.

```
sources ──► collect ──► filter ──► LLM score ──► shortlist ──► LLM draft ──► Telegram card
 (APIs,                (keywords,   (fit, visa,                (profile      ✅ Apply / ⏭ Skip / ✏️ Edit
  ATS boards,           work mode,   seniority,                 facts only)        │
  Playwright)           salary)      cached)                                        ▼
                                                                         email / Karlancer / manual link
```

## Design choices

- **The LLM drafts, the code decides.** Filtering (work mode, residency restrictions, salary floor, de-duplication, daily caps) is plain Python with unit tests. The LLM only scores and writes, always as JSON that is parsed and validated.
- **No invented facts.** `profile.md` is the single source of truth; lines marked `TODO` are stripped before any prompt. Prompts forbid claiming experience that is not in the profile.
- **Nothing leaves without approval.** `mailer.send()` raises unless `approved=True`, `dry_run` builds the message but never opens an SMTP connection, and every `auto_send` flag ships `false`.
- **Polite to every site.** Only public APIs and RSS feeds for discovery; logged-in browsing only on Karlancer with rate limits; no CAPTCHA bypass. If a session expires, the agent stops and alerts on Telegram.
- **Edits teach it.** ✏️ Edit regenerates with your instruction; once a week the edits are summarised into `style_notes.md`, which every prompt reads.
- **Two LLM backends.** The `claude` CLI in headless mode (no API key needed) or the Anthropic API, with a prompt-hash cache, a concurrency limit and an hourly health check.

## Sources

| Kind | Sources |
|---|---|
| Remote boards | RemoteOK, Remotive, We Work Remotely, Himalayas, Hacker News "Who is hiring" |
| Relocation / visa roles | Company boards on Greenhouse, Lever and Ashby (slugs in `config.yaml`), Arbeitnow |
| Freelance (Persian) | Karlancer (Playwright, saved session) |

A job is kept if it is remote with no residency restriction, or on-site/hybrid **and** the posting mentions relocation or visa sponsorship. `work_mode` in `config.yaml` turns either mode off. `python scripts/check_ats_slugs.py` checks which company slugs return live jobs.

## Quick start

```bash
git clone https://github.com/alireza-taheriF/job-agent.git && cd job-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && playwright install chromium

cp .env.example .env              # TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID are required
cp profile.example.md profile.md  # your real CV facts: the only thing the agent may use
python main.py
```

Open your bot in Telegram and send `/start`. Put `CV.pdf` in `data/` to attach it to emailed applications.

## Telegram commands

| Command | |
|---|---|
| `/today` | Shortlisted jobs with drafted materials |
| `/run` | Collect and score now |
| `/import` | Load `data/contacts.csv` (`company,name,role,email,linkedin,note`) |
| `/outreach` | Review cold-email drafts (📤 Send / ⏭ Skip) |
| `/stats`, `/sources`, `/settings` | Status |
| `/pause`, `/resume` | Pause the scheduler |

Only the `TELEGRAM_USER_ID` in `.env` can use the bot.

## Schedule (Asia/Tehran)

International collection 08:00 · Karlancer 09:00 · outreach (replies, follow-ups, new drafts) 10:00 · daily digest 21:00 · Karlancer inbox every 12 min · LLM health check hourly · style notes weekly.

## Tests

```bash
pytest -q     # 35 tests, no network or API key needed
```

They cover de-duplication, salary and residency filters, the remote/relocation filter, Greenhouse/Lever/Ashby parsers on canned payloads, the email approval and dry-run gates, application-address extraction, CSV import, the daily cap, follow-up timing and reply detection.

## Deploy

`docker compose up -d --build` on a VPS. Log in locally with `python login_helper.py karlancer` and copy `data/sessions/` across; authenticate the Claude CLI there with `claude setup-token`.

## Limits

- ATS forms (Greenhouse, Lever and so on) are not auto-filled. The bot gives the link and the letter, and you submit by hand.
- LinkedIn, Wellfound and YC jobs are not collected because they need scraping behind a login.
- Ashby's API refuses Iranian IPs, so it is off by default. Turn it on when running on a VPS.
