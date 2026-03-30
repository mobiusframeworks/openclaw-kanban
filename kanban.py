#!/usr/bin/env python3
"""
OpenClaw Kanban v4 - Using streamlit-sortables
"""

import streamlit as st
from streamlit_sortables import sort_items
import requests
import re
from datetime import datetime

st.set_page_config(page_title="OpenClaw Kanban", layout="wide")

GITHUB_REPO = "mobiusframeworks/openclaw-kanban"
GITHUB_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/backlogs"

AGENTS = ["BML CEO", "EnergyScout CEO", "Real Estate CEO", "Analytics", "Assistant"]

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
                    tasks[current_status].append(f"[{agent[:3]}] {task[:50]}")

            if line.strip().startswith("- [x]"):
                task = line.replace("- [x]", "").strip()
                if task:
                    tasks["DONE"].append(f"[{agent[:3]}] {task[:50]}")
            elif line.strip().startswith("- [ ]"):
                task = line.replace("- [ ]", "").strip()
                if task:
                    tasks["TODO"].append(f"[{agent[:3]}] {task[:50]}")

    return tasks

# Main UI
st.title("OpenClaw Kanban")

tab1, tab2 = st.tabs(["Board", "Schedule"])

with tab1:
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Refresh"):
            st.cache_data.clear()
            st.rerun()

    tasks = parse_tasks()

    # Build sortable containers
    containers = [
        {"header": "TODO", "items": tasks["TODO"]},
        {"header": "IN PROGRESS", "items": tasks["IN PROGRESS"]},
        {"header": "BLOCKED", "items": tasks["BLOCKED"]},
        {"header": "DONE", "items": tasks["DONE"]},
    ]

    st.markdown("**Drag tasks between columns:**")

    sorted_items = sort_items(
        containers,
        multi_containers=True,
        direction="horizontal"
    )

    # Show counts
    st.divider()
    cols = st.columns(4)
    labels = ["TODO", "IN PROGRESS", "BLOCKED", "DONE"]
    colors = ["#FFE082", "#81D4FA", "#EF9A9A", "#A5D6A7"]

    for i, (col, label, color) in enumerate(zip(cols, labels, colors)):
        count = len([c for c in sorted_items if c.get("header") == label][0].get("items", [])) if sorted_items else 0
        col.markdown(f"<div style='background:{color};padding:8px;border-radius:4px;text-align:center'><b>{label}</b><br>{count} tasks</div>", unsafe_allow_html=True)

with tab2:
    st.subheader("Bot Schedule")
    now_hour = datetime.now().hour
    for time, job in sorted(BOT_SCHEDULE.items()):
        hour = int(time.split(":")[0])
        icon = "🟢" if hour == now_hour else "⚪"
        st.markdown(f"{icon} **{time}** - {job}")

st.divider()
st.caption(f"[GitHub](https://github.com/{GITHUB_REPO}) • Drag tasks to reorder")
