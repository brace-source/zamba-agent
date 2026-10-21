import truststore
truststore.inject_into_ssl()
import streamlit as st
st.set_page_config(page_title="Research Agent", page_icon="🔎")
from langchain_core.messages import HumanMessage, AIMessage
from main import ask_agent, ask_file_first, ask_from_notes, pdf_text

import time
import random
import re
import json

def type_out(text):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.01)

ABOUT_ZAMBA = [
    "hi", "hello", "hey", "thanks", "thank you",
    "your name", "call you", "who are you", "what are you",
    "your logo", "yourself", "yours", "made for", "my name",
    "your dp", "profile pic", "your picture", "your photo", "your face", "your avatar", "your icon",
]

def is_about_zamba(text):
    text = text.lower()
    return any(re.search(r"\b" + phrase + r"\b", text) for phrase in ABOUT_ZAMBA) 

MEMORY_FILE = "memory.json"

def load_name():
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("name")
    except Exception:
        return None

def save_name(name):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump({"name": name}, f)

def find_name(text):
    match = re.search(r"(?:my name is|call me|my name's)\s+([A-Za-z]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).capitalize()
    return None

def fresh_history():
    name = load_name()
    if name:
        return [
            HumanMessage(content=f"My name is {name}."),
            AIMessage(content=f"Nice to meet you, {name}!"),
        ]
    return []  

CHAT_FILE = "chat_history.json"

def load_chat():
    try:
        with open(CHAT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_chat(display):
    with open(CHAT_FILE, "w", encoding="utf-8") as f:
        json.dump(display, f)

def history_from_display(display):
    history = fresh_history()
    for m in display:
        if m["role"] == "user":
            history.append(HumanMessage(content=m["text"]))
        else:
            history.append(AIMessage(content=m["text"]))
    return history  

CHATS_FILE = "chats.json"

def load_all():
    try:
        with open(CHATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"current": None, "chats": {}}

def save_all():
    with open(CHATS_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.all_chats, f)

def start_chat():
    cid = str(int(time.time() * 1000))
    st.session_state.all_chats["chats"][cid] = {"title": "New chat", "display": []}
    st.session_state.all_chats["current"] = cid
    st.session_state.display = []
    st.session_state.history = fresh_history()
    st.session_state.files = []
    st.session_state.notes = ""
    save_all()

def open_chat(cid):
    st.session_state.all_chats["current"] = cid
    st.session_state.display = st.session_state.all_chats["chats"][cid]["display"]
    st.session_state.history = history_from_display(st.session_state.display)
    st.session_state.files = []
    st.session_state.notes = ""
    save_all()

def save_current():
    chats = st.session_state.all_chats
    cid = chats["current"]
    chats["chats"][cid]["display"] = st.session_state.display
    first = next((m["text"] for m in st.session_state.display if m["role"] == "user"), None)
    if first:
        chats["chats"][cid]["title"] = first[:30]
    save_all()

def delete_current():
    chats = st.session_state.all_chats
    chats["chats"].pop(chats["current"], None)
    start_chat()     

LOADING = [
    "Zamba is thinking...",
    "Digging up the answer...",
    "Chasing down the facts...",
    "One moment, tail wagging...",
]        

st.set_page_config(page_title="Zamba", page_icon="🐈‍⬛", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.cat-runner {
    display: inline-block;
    vertical-align: middle;
    margin-right: 6px;
    animation: cat-flip 3s ease-in-out infinite;
}
.cat-svg {
    width: 42px;
    height: 28px;
    display: block;
    scale: -1 1;
    animation: cat-bob 0.3s ease-in-out infinite;
}

.leg {
    transform-box: fill-box;
    transform-origin: 50% 0%;
    animation: leg-swing 0.3s ease-in-out infinite;
}
.leg.b { animation-delay: -0.15s; }
.tail {
    transform-box: fill-box;
    transform-origin: 100% 100%;
    animation: tail-wag 0.6s ease-in-out infinite;
}
@keyframes leg-swing {
    0%, 100% { transform: rotate(35deg); }
    50% { transform: rotate(-35deg); }
}
@keyframes cat-bob {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-2px); }
}
@keyframes tail-wag {
    0%, 100% { transform: rotate(-12deg); }
    50% { transform: rotate(12deg); }
}
@keyframes cat-flip {
    0%, 60% { transform: translateY(0) rotate(0deg); }
    70% { transform: translateY(-18px) rotate(-180deg); }
    80%, 100% { transform: translateY(0) rotate(-360deg); }
}
</style>
""", unsafe_allow_html=True)

CAT_SVG = "".join([
    '<svg class="cat-svg" viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg">',
    '<path class="tail" d="M14 16 Q4 8 6 2" stroke="#7c4dbd" stroke-width="3.5" fill="none" stroke-linecap="round"/>',
    '<rect class="leg b" x="16" y="22" width="4" height="13" rx="2" fill="#5b3a99"/>',
    '<rect class="leg a" x="22" y="22" width="4" height="13" rx="2" fill="#5b3a99"/>',
    '<ellipse cx="30" cy="20" rx="17" ry="9" fill="#7c4dbd"/>',
    '<rect class="leg a" x="35" y="22" width="4" height="13" rx="2" fill="#7c4dbd"/>',
    '<rect class="leg b" x="41" y="22" width="4" height="13" rx="2" fill="#7c4dbd"/>',
    '<circle cx="47" cy="14" r="8" fill="#7c4dbd"/>',
    '<polygon points="41,8 43,0 48,6" fill="#7c4dbd"/>',
    '<polygon points="48,6 53,0 55,9" fill="#7c4dbd"/>',
    '<circle cx="50" cy="13" r="1.3" fill="#ffffff"/>',
    '</svg>',
])
st.title("🐈‍⬛ Zamba")
AVATARS = {"user": "🙂", "assistant": "🐈‍⬛"}

if "all_chats" not in st.session_state:
    st.session_state.all_chats = load_all()
if st.session_state.all_chats["current"] not in st.session_state.all_chats["chats"]:
    start_chat()
elif "display" not in st.session_state:
    open_chat(st.session_state.all_chats["current"])
if "files" not in st.session_state:
    st.session_state.files = []
if "notes" not in st.session_state:
    st.session_state.notes = ""    

if st.button("➕ New chat"):
    if st.session_state.display:
        start_chat()
    st.rerun()

if st.sidebar.button("🗑️ Clear chat"):
    delete_current()
    st.rerun()

example = None
with st.sidebar:
    st.header("🐈‍⬛ Zamba")
    st.write("Your friendly research assistant. Ask me for facts, news, or just say hi.")
    st.markdown("**Try asking:**")
    for q in [
        "Tell me something interesting about cats",
        "What is the latest news in AI?",
        "Who invented the telephone?",
    ]:
        if st.button(q):
            example = q  

    if st.session_state.files:
        st.markdown("**📎 Attached file:**")
        for f in st.session_state.files:
            st.caption(f.name)
        if st.button("Remove file"):
            st.session_state.files = []
            st.rerun()    

        st.markdown("**💬 Your chats:**")
    for cid, chat in reversed(list(st.session_state.all_chats["chats"].items())):
        if not chat["display"]:
            continue
        label = chat["title"]
        if cid == st.session_state.all_chats["current"]:
            label = "▶ " + label
        if st.button(label, key="chat_" + cid):
            open_chat(cid)
            st.rerun()      

for m in st.session_state.display:
    with st.chat_message(m["role"], avatar=AVATARS[m["role"]]):
        st.write(m["text"])
        if m.get("sources"):
            st.caption("Sources: " + ", ".join(m["sources"]))

chat_value = st.chat_input(
    "Ask me anything...",
    accept_file="multiple",
    file_type=["pdf", "png", "jpg", "jpeg"],
)
query = None
if chat_value:
    query = chat_value.text or "Please look at my attached file and tell me what it is."
    if chat_value.files:
        st.session_state.files = chat_value.files
        pdfs = [f for f in chat_value.files if f.type == "application/pdf"]
        if len(pdfs) == len(chat_value.files):
            st.session_state.notes = "\n\n".join(pdf_text(f) for f in pdfs).strip()
        else:
            st.session_state.notes = ""
files = st.session_state.files

if example:
    query = example

if query:
    st.session_state.display.append({"role": "user", "text": query})
    with st.chat_message("user",  avatar=AVATARS["user"]):
        st.write(query)
    new_name = find_name(query)
    if new_name:
        save_name(new_name)

    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        label = "reading your file..." if files else ("typing..." if is_about_zamba(query) else "searching...")
        loader = st.empty()
        loader.markdown(f'<span class="cat-runner">{CAT_SVG}</span> {label}', unsafe_allow_html=True)
        def switch_label():
            new_label = "typing..." if is_about_zamba(query) else "searching..."
            loader.markdown(f'<span class="cat-runner">{CAT_SVG}</span> {new_label}', unsafe_allow_html=True)        
        try:
            if files and st.session_state.notes:
                answer, sources, tools_used = ask_from_notes(query, st.session_state.history, st.session_state.notes, switch_label)
            elif files:
                answer, sources, tools_used = ask_file_first(query, st.session_state.history, files, switch_label)
            else:
                answer, sources, tools_used = ask_agent(query, st.session_state.history)
        except Exception as e:
            answer = "Sorry, I lost my connection for a moment. Please send that again."
            sources, tools_used = [], []
            
        loader.empty()
        st.write_stream(type_out(answer))
        if sources:
            st.caption("Sources: " + ", ".join(sources))

    st.session_state.history.append(HumanMessage(content=query))
    st.session_state.history.append(AIMessage(content=answer))
    st.session_state.display.append(
        {"role": "assistant", "text": answer, "sources": sources}
    )
    save_current()
    st.rerun()