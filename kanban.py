#!/usr/bin/env python3
"""
OpenClaw Kanban v3 - Drag & Drop Edition
Uses streamlit-kanban-board for proper UX
"""

import streamlit as st
from streamlit_kanban_board import kanban_board
import requests
import re
from datetime import datetime

st.set_page_config(page_title="OpenClaw Kanban", layout="wide")

# GitHub config
GITHUB_REPO = "mobiusframeworks/openclaw-kanban"
GITHUB_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/backlogs"

AGENTS = ["BML CEO", "EnergyScout CEO", "Real Estate CEO", "Analytics", "Assistant"]

# Bot schedule
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

def parse_to_kanban_format():
    """Parse all backlogs into kanban board format"""
    columns = [
        {"id": "todo", "title": "TODO", "cards": []},
        {"id": "in_progress", "title": "IN PROGRESS", "cards": []},
        {"id": "blocked", "title": "BLOCKED", "cards": []},
        {"id": "done", "title": "DONE", "cards": []},
    ]

    col_map = {"TODO": 0, "IN PROGRESS": 1, "BLOCKED": 2, "DONE": 3}
    card_id = 0

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
                    columns[col_map[current_status]]["cards"].append({
                        "id": str(card_id),
                        "title": f"[{agent[:3]}] {task[:50]}",
                        "description": task,
                    })
                    card_id += 1

            if line.strip().startswith("- [x]"):
                task = line.replace("- [x]", "").strip()
                if task:
                    columns[col_map["DONE"]]["cards"].append({
                        "id": str(card_id),
                        "title": f"[{agent[:3]}] {task[:50]}",
                        "description": task,
                    })
                    card_id += 1
            elif line.strip().startswith("- [ ]"):
                task = line.replace("- [ ]", "").strip()
                if task:
                    columns[col_map["TODO"]]["cards"].append({
                        "id": str(card_id),
                        "title": f"[{agent[:3]}] {task[:50]}",
                        "description": task,
                    })
                    card_id += 1

    return columns

# Main UI
st.title("🗂️ OpenClaw Kanban")

tab1, tab2 = st.tabs(["📋 Board", "⏰ Schedule"])

with tab1:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

    columns = parse_to_kanban_format()

    # Render kanban board with drag-drop
    result = kanban_board(
        columns=columns,
        key="kanban",
    )

    if result:
        st.write("Board updated:", result)

with tab2:
    st.subheader("Bot Schedule")
    now_hour = datetime.now().hour
    for time, job in sorted(BOT_SCHEDULE.items()):
        hour = int(time.split(":")[0])
        icon = "🟢" if hour == now_hour else "⚪"
        st.markdown(f"{icon} **{time}** - {job}")

st.divider()
st.caption(f"[GitHub Repo](https://github.com/{GITHUB_REPO}) • Drag cards to reorder")
