from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from tools import search_tool, wiki_tool, save_tool
from langchain_core.messages import HumanMessage, AIMessage
import base64
import io
from pypdf import PdfReader
load_dotenv()

class ResearchResponse(BaseModel):
    topic: str
    summary: str
    sources: list[str]
    tools_used: list[str]
    
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", thinking_level="medium")
file_llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", thinking_level="low")
parser = PydanticOutputParser(pydantic_object=ResearchResponse)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            
           You are a friendly research assistant talking directly to the user. Speak to them as "you", never in the third person.
Only use tools when the user asks for facts, news or research you need to look up.
Do not use tools for personal statements, greetings or things the user told you in this conversation. Just reply and remember them.
When you do search, search at most 2 times, then write your final answer from what you found. Your name is Zamba. If anyone asks your name or what they should call you, answer with: My name is Zamba. You can call me Zamba.
When the user greets you, greet them back by name if you know their name from this conversation, for example: Hello, Sara! If you do not know their name yet, ask politely: Hi! May I ask your good name?
When the user tells you their name, remember it and use it in later replies.Your name is Zamba. If anyone asks your name or what they should call you, answer in a warm, natural way and keep it short, for example: I am Zamba, nice to meet you. 
If the user has just told you their own name, say it was nice to meet them by name and then give yours, for example: Nice to meet you, Maya! I am Zamba. Do not repeat the same sentence every time.
Your personality: you are Zamba, a witty and relaxed assistant who talks like a friendly buddy. You use casual language and light humour, but you never joke about serious topics, and you always give correct, useful answers.
Sometimes the conversation begins with a message that contains an attached file. If there is no attached file, do not mention any file. If there is one, check it first for every question and answer from it. 
Quote exact details such as names, prices and times from the file. Never guess or invent details. 
If you cannot find something in the file, say that you cannot find it, and only then search the web if it makes sense. 
Read the whole file, including every paragraph, table and list, before you decide something is missing.
Do not start every reply with a greeting or with the user's name. Greet the user only at the start of the conversation, and use their name only now and then.
The summary field of your answer is your actual reply to the user. Write it as your own words spoken directly to the user.
Never describe or summarize the conversation, and never write about the user in the third person. 
For example, if the user says hi, the summary should be a friendly greeting such as: Hi! How can I help you today?
Your logo, profile picture, display picture (also called a dp), avatar and icon are all the same thing: a friendly purple cat shown next to your name at the top of the page.
If anyone asks what picture or logo you have, say it is a purple cat. Never say you have no logo or picture, and do not make up other pictures.
            Wrap the output in this format and provide no other text\n{format_instructions}
            """,
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{query}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
).partial(format_instructions=parser.get_format_instructions())

tools = [search_tool, wiki_tool, save_tool]
agent = create_tool_calling_agent(
    llm=llm,
    prompt=prompt,
    tools=tools
)


def file_blocks(files):
    blocks = []
    for f in files:
        data = base64.b64encode(f.getvalue()).decode("utf-8")
        if f.type == "application/pdf":
            blocks.append({"type": "media", "mime_type": f.type, "data": data})
        else:
            blocks.append({"type": "image_url", "image_url": f"data:{f.type};base64,{data}"})
    return blocks

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False, max_iterations=10)
def ask_agent(query, chat_history, files=None):
    if files:
        intro = [{"type": "text", "text": "I am attaching a file. My questions may be about it, so check the file first before searching the web."}]
        chat_history = [
            HumanMessage(content=intro + file_blocks(files)),
            AIMessage(content="Got it, I have read your file."),
        ] + list(chat_history)
    raw_response = agent_executor.invoke({
        "query": query,
        "chat_history": chat_history,
    })

    output = raw_response.get("output")
    if isinstance(output, list):
        output = "".join(
            block.get("text", "") for block in output if isinstance(block, dict)
        )

    try:
        structured_response = parser.parse(output)
        return structured_response.summary, structured_response.sources, structured_response.tools_used
    except Exception:
        return output, [], []


def ask_with_files(query, chat_history, files):
    content = [{"type": "text", "text": query}]
    for f in files:
        data = base64.b64encode(f.getvalue()).decode("utf-8")
        mime = f.type
        if mime == "application/pdf":
            content.append({"type": "media", "mime_type": mime, "data": data})
        else:
            content.append({"type": "image_url", "image_url": f"data:{mime};base64,{data}"})

    messages = [
        ("system", "Your name is Zamba. You are a friendly assistant talking directly to the user. Answer using the attached file. Be clear and helpful."),
        *chat_history,
        HumanMessage(content=content),
    ]
    response = llm.invoke(messages)
    output = response.content
    if isinstance(output, list):
        output = "".join(
            block.get("text", "") for block in output if isinstance(block, dict)
        )
    return output, [], []


def ask_file_first(query, chat_history, files, on_fallback=None):
    content = [{"type": "text", "text": query}] + file_blocks(files)
    messages = [
        ("system", "Your name is Zamba. You are a friendly assistant talking directly to the user. The user has attached a file, and most of their questions are about it, even short or general ones such as what is the secret code word or who is the founder. Read the whole file carefully, every page, paragraph, table and list, to the very end, before answering. If the answer is in the file, answer from it and quote exact names, prices, times and words. Never guess or invent details. Only if you have checked everything and the answer is truly not in the file, reply with exactly the single word NOT_IN_FILE and nothing else."),
        *chat_history,
        HumanMessage(content=content),
    ]
    response = llm.invoke(messages)
    output = response.content
    if isinstance(output, list):
        output = "".join(
            block.get("text", "") for block in output if isinstance(block, dict)
        )
    if "NOT_IN_FILE" in output:
        if on_fallback:
            on_fallback()
        return ask_agent(query, chat_history)
    return output, ["Attached file"], []  


def pdf_text(f):
    try:
        reader = PdfReader(io.BytesIO(f.getvalue()))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def ask_from_notes(query, chat_history, notes, on_fallback=None):
    notes = notes[:200000]
    messages = [
        ("system", "Your name is Zamba. You are a friendly assistant talking directly to the user. The user has attached a file, and its full text is given below. Most of their questions are about it, even short or general ones. If the answer is in the text, answer from it and quote exact names, prices, times and words. Never guess or invent details. Only if you have checked everything and the answer is truly not in the text, reply with exactly the single word NOT_IN_FILE and nothing else.\n\nTEXT OF THE FILE:\n" + notes),
        *chat_history,
        HumanMessage(content=query),
    ]
    response = file_llm.invoke(messages)
    output = response.content
    if isinstance(output, list):
        output = "".join(
            block.get("text", "") for block in output if isinstance(block, dict)
        )
    if "NOT_IN_FILE" in output:
        if on_fallback:
            on_fallback()
        return ask_agent(query, chat_history)
    return output, ["Attached file"], []  

if __name__ == "__main__":
    chat_history = []
    print("Research agent ready. Type 'quit' to stop.")

    while True:
        query = input("\nYou: ")
        if query.strip().lower() in ["quit", "exit"]:
            print("Goodbye!")
            break

        answer, sources, tools_used = ask_agent(query, chat_history)
        print("\nAgent:", answer)
        print("Sources:", sources)
        print("Tools used:", tools_used)

        chat_history.append(HumanMessage(content=query))
        chat_history.append(AIMessage(content=answer))