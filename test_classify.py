from dotenv import load_dotenv
load_dotenv()
from src.agent.classify_query import classify_query_message
for q in ["who is raju pairing with?", "who worked on the manager agent project", "who is working with divyansh"]:
    r = classify_query_message({"raw_text": q})
    print(q, "->", r["question_type"], "| person:", r["target_person"], "| project:", r["target_project"])
