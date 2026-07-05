from dotenv import load_dotenv
load_dotenv()
from src.agent.merge_write import merge_write
from src.tools.local_wiki import read_person_file
from pathlib import Path
current = read_person_file(Path("wiki/people/maaz.md"))
result = merge_write({
    "current_wiki_content": current,
    "update_content": "collaborated with Harshit on the search module",
    "person_name": "Maaz",
})
print(result["draft"])
