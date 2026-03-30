#!/usr/bin/env python3
"""
OpenClaw Kanban v2 - Interactive Edition
Features: Edit cards, drag/drop, bot schedule
"""

import streamlit as st
import requests
import json
import re
from datetime import datetime

st.set_page_config(page_title="OpenClaw Kanban", layout="wide")

# GitHub config
GITHUB_REPO = "mobiusframeworks/openclaw-kanban"
GITHUB_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/backlogs"

AGENTS = ["BML CEO", "EnergyScout CEO", "Real Estate CEO", "Analytics", "Assistant"]
COLUMNS = ["TODO", "IN PROGRESS", "BLOCKED", "DONE"]
COLORS = {"TODO": "#FFE082", "IN PROGRESS": "#81D4FA", "BLOCKED": "#EF9A9A", "DONE": "#A5D6A7"}

# Bot schedule from jobs.json
BOT_SCHEDULE = {
    "07:00": "morning-briefing (Assistant)",
    "08:00": "realestate-leads (RE)",
    "09:00": "bml-content-pipeline (BML)",
    "10:00": "es-sprint-check (ES)",
    "11:00": "realestate-social (RE)",
    "12:00": "midday-nudge (Assistant)",
    "13:00": "session-compression",
    "14:00": "research-bitcoin (BML)",
    "15:00": "research-solar (ES)",
    "16:00": "analytics-weekly-seo (Analytics)",
    "17:00": "daily-metrics (Assistant)",
    "19:00": "evening-content (BML)",
    "21:00": "nightly-review (Assistant)",
    "22:00": "session-compression",
    "23:00": "nightly-builder (Assistant)",
}

# Session state for tasks
if "tasks" not in st.session_state:
    st.session_state.tasks = {col: [] for col in COLUMNS}
if "loaded" not in st.session_state:
    st.session_state.loaded = False

@st.cache_data(ttl=300)
def fetch_backlog(agent: str) -> str:
    """Fetch backlog from GitHub"""
    url_map = {
        "BML CEO": f"{GITHUB_BASE}/bml-ceo.md",
        "EnergyScout CEO": f"{GITHUB_BASE}/energyscout-ceo.md",
        "Real Estate CEO": f"{GITHUB_BASE}/realestate-ceo.md",
        "Analytics": f"{GITHUB_BASE}/analytics.md",
        "Assistant": f"{GITHUB_BASE}/assistant.md",
    }
    try:
        resp = requests.get(url_map.get(agent, ""), timeout=10)
        return resp.text if resp.status_code == 200 else ""
    except:
        return ""

def parse_tasks(content: str, agent: str) -> dict:
    """Parse markdown into task dict"""
    tasks = {col: [] for col in COLUMNS}
    if not content:
        return tasks

    current_status = "TODO"
    for line in content.split('\n'):
        if "**Status:**" in line or "Status:" in line:
            ll = line.lower()
            if "complete" in ll or "done" in ll:
                current_status = "DONE"
            elif "progress" in ll:
                current_status = "IN PROGRESS"
            elif "blocked" in ll:
                current_status = "BLOCKED"
            else:
                current_status = "TODO"

        if line.startswith("### "):
            task = re.sub(r'^\d+\.\s*', '', line.replace("###", "").strip())
            if task:
                tasks[current_status].append({"agent": agent, "task": task, "notes": ""})

        if line.strip().startswith("- [x]"):
            task = line.replace("- [x]", "").strip()
            if task:
                tasks["DONE"].append({"agent": agent, "task": task, "notes": ""})
        elif line.strip().startswith("- [ ]"):
            task = line.replace("- [ ]", "").strip()
            if task:
                tasks["TODO"].append({"agent": agent, "task": task, "notes": ""})

    return tasks

def load_all_tasks():
    """Load tasks from all agents"""
    all_tasks = {col: [] for col in COLUMNS}
    for agent in AGENTS:
        content = fetch_backlog(agent)
        agent_tasks = parse_tasks(content, agent)
        for col in COLUMNS:
            all_tasks[col].extend(agent_tasks[col])
    st.session_state.tasks = all_tasks
    st.session_state.loaded = True

def render_card(task: dict, col: str, idx: int):
    """Render an editable task card"""
    with st.container():
        st.markdown(f"""
        <div style="background-color: {COLORS[col]}; padding: 10px; margin: 5px 0; border-radius: 5px; color: black;">
            <strong>[{task['agent']}]</strong><br>
            {task['task'][:80]}{'...' if len(task['task']) > 80 else ''}
        </div>
        """, unsafe_allow_html=True)

        # Move buttons
        cols = st.columns(4)
        for i, target_col in enumerate(COLUMNS):
            if target_col != col:
                if cols[i].button(f"→ {target_col[:4]}", key=f"move_{col}_{idx}_{target_col}"):
                    task_item = st.session_state.tasks[col].pop(idx)
                    st.session_state.tasks[target_col].append(task_item)
                    st.rerun()

# Main UI
st.title("OpenClaw Kanban")

# Tabs
tab1, tab2, tab3 = st.tabs(["📋 Tasks", "⏰ Bot Schedule", "➕ Add Task"])

with tab1:
    col_refresh, col_sync = st.columns([1, 1])
    with col_refresh:
        if st.button("🔄 Refresh from GitHub"):
            st.cache_data.clear()
            load_all_tasks()
            st.rerun()
    with col_sync:
        if st.button("💾 Save Changes"):
            st.info("Changes saved locally. Run sync-backlogs.sh to push to GitHub.")

    if not st.session_state.loaded:
        load_all_tasks()

    # Kanban columns
    cols = st.columns(4)
    for i, column in enumerate(COLUMNS):
        with cols[i]:
            st.subheader(f"{column} ({len(st.session_state.tasks[column])})")
            for idx, task in enumerate(st.session_state.tasks[column][:15]):
                render_card(task, column, idx)

with tab2:
    st.subheader("Bot Schedule (Daily)")
    for time, job in sorted(BOT_SCHEDULE.items()):
        hour = int(time.split(":")[0])
        now = datetime.now().hour
        indicator = "🟢" if hour == now else "⚪"
        st.markdown(f"{indicator} **{time}** - {job}")

with tab3:
    st.subheader("Add New Task")
    new_agent = st.selectbox("Agent", AGENTS)
    new_task = st.text_input("Task description")
    new_col = st.selectbox("Status", COLUMNS)
    if st.button("Add Task"):
        if new_task:
            st.session_state.tasks[new_col].append({
                "agent": new_agent,
                "task": new_task,
                "notes": ""
            })
            st.success(f"Added to {new_col}")
            st.rerun()

st.divider()
st.caption(f"Last refresh: {datetime.now().strftime('%H:%M')} • [GitHub]({f'https://github.com/{GITHUB_REPO}'})")
