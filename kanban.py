#!/usr/bin/env python3
"""
OpenClaw Kanban v5 - Native Streamlit Columns (Clean Layout)
"""

import streamlit as st
import requests
import re
from datetime import datetime

st.set_page_config(page_title="OpenClaw Kanban", layout="wide")

# Custom CSS for kanban styling
st.markdown("""
<style>
.kanban-card {
    background: #2d2d2d;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
    border-left: 4px solid #666;
    font-size: 14px;
}
.kanban-card.bml { border-left-color: #f7931a; }
.kanban-card.ene { border-left-color: #4CAF50; }
.kanban-card.rea { border-left-color: #2196F3; }
.kanban-card.ana { border-left-color: #9C27B0; }
.kanban-card.ass { border-left-color: #FF5722; }
.agent-tag {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
    background: #444;
    margin-right: 6px;
}
.col-header {
    font-size: 18px;
    font-weight: bold;
    padding: 10px;
    border-radius: 8px;
    text-align: center;
    margin-bottom: 10px;
}
.todo-header { background: #FFE082; color: #333; }
.progress-header { background: #81D4FA; color: #333; }
.blocked-header { background: #EF9A9A; color: #333; }
.done-header { background: #A5D6A7; color: #333; }
</style>
""", unsafe_allow_html=True)

GITHUB_REPO = "mobiusframeworks/openclaw-kanban"
GITHUB_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/backlogs"

AGENTS = ["BML CEO", "EnergyScout CEO", "Real Estate CEO", "Analytics", "Assistant"]
AGENT_KEYS = {"BML CEO": "bml", "EnergyScout CEO": "ene", "Real Estate CEO": "rea", "Analytics": "ana", "Assistant": "ass"}

BOT_SCHEDULE = {
    "07:00": "morning-briefing (Assistant)",
    "08:00": "realestate-leads (RE)",
    "09:00": "bml-content-pipeline (BML)",
    "10:00": "es-sprint-check (ES)",
    "11:00": "realestate-social (RE)",
    "12:00": "midday-nudge (Assistant)",
    "14:00": "research-bitcoin (BML)",
    "15:00": "research-solar (ES)",
    "17:00": "daily-metrics (Assistant)",
    "19:00": "evening-content (BML)",
    "21:00": "nightly-review (Assistant)",
    "23:00": "nightly-builder (Assistant)",
}

@st.cache_data(ttl=300)
def fetch_backlog(agent: str) -> str:
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

def parse_tasks():
    """Parse all backlogs into task lists by status"""
    tasks = {"TODO": [], "IN PROGRESS": [], "BLOCKED": [], "DONE": []}

    for agent in AGENTS:
        content = fetch_backlog(agent)
        if not content:
            continue

        agent_key = AGENT_KEYS.get(agent, "unk")
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
                    tasks[current_status].append({"text": task[:60], "agent": agent, "key": agent_key})

            if line.strip().startswith("- [x]"):
                task = line.replace("- [x]", "").strip()
                if task:
                    tasks["DONE"].append({"text": task[:60], "agent": agent, "key": agent_key})
            elif line.strip().startswith("- [ ]"):
                task = line.replace("- [ ]", "").strip()
                if task:
                    tasks["TODO"].append({"text": task[:60], "agent": agent, "key": agent_key})

    return tasks

def render_card(task):
    """Render a single task card"""
    return f"""<div class="kanban-card {task['key']}">
        <span class="agent-tag">{task['key'].upper()}</span>
        {task['text']}
    </div>"""

# Main UI
st.title("OpenClaw Kanban")

tab1, tab2 = st.tabs(["Board", "Schedule"])

with tab1:
    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    tasks = parse_tasks()

    # Create 4 columns for kanban
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown('<div class="col-header todo-header">TODO</div>', unsafe_allow_html=True)
        st.caption(f"{len(tasks['TODO'])} tasks")
        for task in tasks["TODO"]:
            st.markdown(render_card(task), unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="col-header progress-header">IN PROGRESS</div>', unsafe_allow_html=True)
        st.caption(f"{len(tasks['IN PROGRESS'])} tasks")
        for task in tasks["IN PROGRESS"]:
            st.markdown(render_card(task), unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="col-header blocked-header">BLOCKED</div>', unsafe_allow_html=True)
        st.caption(f"{len(tasks['BLOCKED'])} tasks")
        for task in tasks["BLOCKED"]:
            st.markdown(render_card(task), unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="col-header done-header">DONE</div>', unsafe_allow_html=True)
        st.caption(f"{len(tasks['DONE'])} tasks")
        for task in tasks["DONE"][:20]:
            st.markdown(render_card(task), unsafe_allow_html=True)
        if len(tasks["DONE"]) > 20:
            st.caption(f"...and {len(tasks['DONE']) - 20} more")

with tab2:
    st.subheader("Bot Schedule")
    now_hour = datetime.now().hour
    for time, job in sorted(BOT_SCHEDULE.items()):
        hour = int(time.split(":")[0])
        icon = "🟢" if hour == now_hour else "⚪"
        st.markdown(f"{icon} **{time}** - {job}")

st.divider()
st.caption(f"[GitHub](https://github.com/{GITHUB_REPO}) • Edit markdown files to move tasks")
