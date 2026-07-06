import os
import sys
import argparse
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from src.graph_writing import writing_agent
from src.graph_querying import querying_agent
from src.intent_router import route_intent
from src.followup_agent import run_followup_check
app = App(token=os.environ["SLACK_BOT_TOKEN"])
@app.event("message")
def handle_message(event, logger, say):
    if event.get("subtype") == "bot_message" or event.get("bot_id"):
        return
    channel = event.get("channel", "")
    if channel != os.environ.get("SLACK_HOME_CHANNEL", channel):
        return
    text = event.get("text", "").strip()
    if not text:
        return
    thread_ts = event.get("thread_ts") or event.get("ts")
    try:
        intent = route_intent(text)
        print(f"[ROUTER] intent={intent} | {text[:80]}")
        if intent == "write":
            result = writing_agent.invoke({
                "raw_text": text,
                "sender": event.get("user", "unknown"),
                "channel": channel,
                "thread_ts": thread_ts,
            })
            print(f"[WRITE RESULT] {result.get('final_response')}")
        else:
            result = querying_agent.invoke({
                "raw_text": text,
                "sender": event.get("user", "unknown"),
                "channel": channel,
                "thread_ts": thread_ts,
            })
            say(text=result.get("final_response", "No answer found."), thread_ts=thread_ts)
    except Exception as e:
        logger.error(f"[AGENT ERROR] {e}")
        say(
            text=f":warning: Sorry, something went wrong processing that message ({type(e).__name__}). Please try again in a moment.",
            thread_ts=thread_ts,
        )
def run_followup_and_post():
    """Runs the follow-up cron pass: purge expired items (due before today, 1-day
    grace), then post the report to Slack. One-shot, meant for cron."""
    from src.tools.followup_detect import purge_expired_followups
    removed = purge_expired_followups()
    if removed:
        print(f"Purged {removed} expired follow-up(s).")
    report = run_followup_check()
    channel = os.environ.get("SLACK_HOME_CHANNEL")
    app.client.chat_postMessage(channel=channel, text=f":clipboard: *Follow-up Check*\n{report}")
    print("Posted follow-up report to Slack.")
    print(report)
def run_listener():
    print("Starting intern-wiki-agent (Writing + Querying)...")
    from src.tools.local_wiki import ensure_wiki_structure
    ensure_wiki_structure()
    _start_followup_scheduler()
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
def _start_followup_scheduler():
    """Background daily follow-up at 11:00 AM IST. Uses existing run_followup_and_post().
    Does not touch agent logic -- only schedules an existing function."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Asia/Kolkata")
        scheduler = BackgroundScheduler(timezone=tz)
        scheduler.add_job(run_followup_and_post, CronTrigger(hour=11, minute=0, timezone=tz))
        scheduler.start()
        print("Follow-up scheduler started (daily 11:00 AM IST).")
    except Exception as e:
        print(f"[SCHEDULER WARNING] could not start follow-up scheduler: {e}")
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["listen", "followup"], default="listen")
    args = parser.parse_args()
    if args.mode == "followup":
        run_followup_and_post()
    else:
        run_listener()
