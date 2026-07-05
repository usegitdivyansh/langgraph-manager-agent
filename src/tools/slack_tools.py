"""
Slack tools — send replies back to Slack.
Called by the final node in both write and query paths.
"""

import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def get_slack_client() -> WebClient:
    return WebClient(token=os.environ["SLACK_BOT_TOKEN"])


def send_reply(channel: str, thread_ts: str, text: str) -> None:
    """
    Post a threaded reply in Slack.
    If thread_ts is None, posts as a new message.
    """
    client = get_slack_client()
    try:
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=text,
        )
    except SlackApiError as e:
        print(f"[Slack error] {e.response['error']}")
        raise