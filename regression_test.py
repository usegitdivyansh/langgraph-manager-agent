from dotenv import load_dotenv
load_dotenv()
from src.graph_writing import writing_agent
from src.graph_querying import querying_agent
tests = [
    ("Divyansh here - regression test passed for divyansh", "what is divyansh working on?"),
    ("Riya here - regression test passed for riya", "what is riya working on?"),
    ("Harshit here - regression test passed for harshit", "what is harshit working on?"),
    ("Maaz here - regression test passed for maaz", "what is maaz working on?"),
]
for write_text, query_text in tests:
    w = writing_agent.invoke({
        "raw_text": write_text,
        "sender": "test",
        "channel": "C0B9QR1BR7S",
        "thread_ts": None,
    })
    verdict = w.get("reflection_verdict")
    response = w.get("final_response")
    print("WRITE:", write_text)
    print("  verdict:", verdict, "| response:", response)
    q = querying_agent.invoke({"raw_text": query_text})
    answer = q.get("final_response", "")
    print("QUERY:", query_text)
    print("  answer:", answer[:150])
    print()
