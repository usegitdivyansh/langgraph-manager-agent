"""
followup_agent -- entry point for the Follow-up skill.
Detect-only: reads follow-up-list.md, reports overdue/due-today/upcoming items,
and posts the report to Slack. Intended to run on a schedule (Task Scheduler /
cron / systemd timer), NOT triggered by Slack messages.
Does not modify any files.
"""
import os
from dotenv import load_dotenv
from src.tools.followup_detect import detect_followups, format_report
from src.tools.slack_tools import send_reply
load_dotenv()
FOLLOWUP_CHANNEL = os.environ.get("FOLLOWUP_CHANNEL", "C0B9QR1BR7S")
def run_followup_check(mention_fn=None) -> str:
    """Runs the detect-only follow-up check and returns a formatted report string.
    mention_fn: optional callable(name) -> str, used to Slack-tag people."""
    categorized = detect_followups()
    return format_report(categorized, mention_fn=mention_fn)
def post_followup_report() -> None:
    """Runs the check and posts the report to Slack as a new channel message."""
    from src.tools.slack_users import mention
    report = run_followup_check(mention_fn=mention)
    header = ":bell: *Daily Follow-up Report*\n"
    send_reply(channel=FOLLOWUP_CHANNEL, thread_ts=None, text=header + report)
    print("=== Follow-up Report (posted to Slack) ===")
    print(report)
if __name__ == "__main__":
    post_followup_report()
