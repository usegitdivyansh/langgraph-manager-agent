# Intern Wiki Agent
A Slack-native knowledge-management agent for tracking intern activity, built on **LangGraph**. It ingests updates posted in Slack, maintains a structured local markdown wiki, answers questions about who did what, and posts scheduled follow-up reminders.
## Architecture
Three **independent skills**, connected only through a shared local markdown wiki (no tight coupling):
1. **Writing** -- parses an update, resolves the person, merges it into their page, self-checks for fabrication, and commits atomically. Also auto-updates project rosters, the index, and a follow-up list.
2. **Querying** -- answers questions using a hierarchical fallback search: index.md -> person page -> wikilinks -> raw minutes -> raw transcript.
3. **Follow-up** -- a scheduled (cron / Task Scheduler) job that reads the follow-up list, categorizes items by due date, and posts a report to Slack.
### Design principle
Anything correctness-critical (rosters, wikilinks, index sync, frontmatter, identity resolution) is **deterministic Python**. The LLM only writes prose. This avoids run-to-run LLM unreliability affecting the data layer.
## Question types (Querying)
- list_people -- who is on a project (reads the project roster)
- collaborators -- who a person shares projects with
- activity_on_date -- what someone did on a specific date (reads dated History)
- activity_general -- what someone has been doing (reads Summary)
- open_items -- what is pending for someone (reads the follow-up list)
- status -- current status of a person or project
## Stack
- **LangGraph** -- StateGraph per skill
- **Slack Bolt** (Socket Mode) -- Slack integration
- **OpenRouter** -- LLM access
- **thefuzz** -- fuzzy name/project resolution
- Local markdown files -- storage (no external DB)
## Wiki structure
See wiki-sample/ for the layout. Each person and project is a markdown file with YAML frontmatter, a Summary, and a dated History. Projects also have a deterministic People roster.
## Setup
1. python -m venv .venv  then  .venv\Scripts\activate
2. pip install -r requirements.txt
3. Copy .env.example to .env and fill in your Slack + OpenRouter credentials.
4. python main.py  to start the live listener.
5. Schedule  python -m src.followup_agent  (cron / Task Scheduler) for daily follow-up reports.
## Note
The live wiki/ folder (real intern data) is gitignored. A wiki-sample/ is included to demonstrate structure.
