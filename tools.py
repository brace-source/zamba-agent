import requests
from ddgs import DDGS
from langchain_core.tools import Tool
from datetime import datetime

def save_to_txt(data: str, filename: str = "research_output.txt"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_text = f"--- Research Output ---\nTimestamp: {timestamp}\n\n{data}\n\n"

    with open(filename, "a", encoding="utf-8") as f:
        f.write(formatted_text)
    
    return f"Data successfully saved to {filename}"

save_tool = Tool(
    name="save_text_to_file",
    func=save_to_txt,
    description="Saves structured research data to a text file.",
)

def search_web(query: str) -> str:
    for backend in ["duckduckgo", "bing", "brave", "yahoo"]:
        try:
            results = DDGS(timeout=5).text(query, max_results=5, backend=backend)
            if results:
                return "\n\n".join(
                    f"{r['title']}: {r['body']} ({r['href']})" for r in results
                )
        except Exception:
            continue
    return "Web search is not available right now. Use Wikipedia instead."

search_tool = Tool(
    name="search",
    func=search_web,
    description="Search the web for recent information and news",
)

def search_wikipedia(query: str) -> str:
    headers = {"User-Agent": "ai-agent-learning/1.0 (personal project)"}
    try:
        search = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 1,
            },
            headers=headers,
            timeout=10,
        ).json()

        results = search["query"]["search"]
        if not results:
            return "No Wikipedia results found."

        title = results[0]["title"]
        page = requests.get(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + title.replace(" ", "_"),
            headers=headers,
            timeout=10,
        ).json()

        return page.get("extract", "No summary available.")
    except Exception as e:
        return f"Wikipedia search failed: {e}"

wiki_tool = Tool(
    name="wikipedia",
    func=search_wikipedia,
    description="Search Wikipedia and return a short summary of a topic",
)