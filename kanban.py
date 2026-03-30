#!/usr/bin/env python3
"""
OpenClaw Kanban v6 - Using streamlit-elements for drag-drop
"""

import streamlit as st
from streamlit_elements import elements, mui, dashboard, sync
import requests
import re
from datetime import datetime
import json

st.set_page_config(page_title="OpenClaw Kanban", layout="wide")

GITHUB_REPO = "mobiusframeworks/openclaw-kanban"
GITHUB_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/backlogs"

AGENTS = ["BML CEO", "EnergyScout CEO", "Real Estate CEO", "Analytics", "Assistant"]
AGENT_COLORS = {"BML CEO": "#f7931a", "EnergyScout CEO": "#4CAF50", "Real Estate CEO": "#2196F3", "Analytics": "#9C27B0", "Assistant": "#FF5722"}

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
    tasks = {"todo": [], "progress": [], "blocked": [], "done": []}

    for agent in AGENTS:
        content = fetch_backlog(agent)
        if not content:
            continue

        current_status = "todo"
        color = AGENT_COLORS.get(agent, "#666")

        for line in content.split('\n'):
            if "**Status:**" in line or "Status:" in line:
                ll = line.lower()
                if "complete" in ll or "done" in ll:
                    current_status = "done"
                elif "progress" in ll:
                    current_status = "progress"
                elif "blocked" in ll:
                    current_status = "blocked"
                else:
                    current_status = "todo"

            if line.startswith("### "):
                task = re.sub(r'^\d+\.\s*', '', line.replace("###", "").strip())
                if task:
                    tasks[current_status].append({"text": task[:55], "agent": agent, "color": color})

            if line.strip().startswith("- [x]"):
                task = line.replace("- [x]", "").strip()
                if task:
                    tasks["done"].append({"text": task[:55], "agent": agent, "color": color})
            elif line.strip().startswith("- [ ]"):
                task = line.replace("- [ ]", "").strip()
                if task:
                    tasks["todo"].append({"text": task[:55], "agent": agent, "color": color})

    return tasks

# Main UI
st.title("OpenClaw Kanban")

if st.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()

tasks = parse_tasks()

# Define dashboard layout
layout = [
    dashboard.Item("todo", 0, 0, 3, 6),
    dashboard.Item("progress", 3, 0, 3, 6),
    dashboard.Item("blocked", 6, 0, 3, 6),
    dashboard.Item("done", 9, 0, 3, 6),
]

COLUMNS = {
    "todo": {"title": "📋 TODO", "color": "#FFE082", "tasks": tasks["todo"]},
    "progress": {"title": "🔄 IN PROGRESS", "color": "#81D4FA", "tasks": tasks["progress"]},
    "blocked": {"title": "🚫 BLOCKED", "color": "#EF9A9A", "tasks": tasks["blocked"]},
    "done": {"title": "✅ DONE", "color": "#A5D6A7", "tasks": tasks["done"][:15]},
}

with elements("kanban"):
    with dashboard.Grid(layout, draggableHandle=".drag-handle"):
        for col_id, col_data in COLUMNS.items():
            with mui.Paper(key=col_id, elevation=3, sx={
                "display": "flex",
                "flexDirection": "column",
                "height": "100%",
                "backgroundColor": "#1e1e1e",
                "borderRadius": "8px",
                "overflow": "hidden"
            }):
                # Column header
                mui.Box(
                    mui.Typography(col_data["title"], variant="h6"),
                    className="drag-handle",
                    sx={
                        "backgroundColor": col_data["color"],
                        "color": "#333",
                        "padding": "12px",
                        "cursor": "grab",
                        "fontWeight": "bold",
                        "textAlign": "center"
                    }
                )

                # Task cards
                with mui.Box(sx={"padding": "8px", "overflowY": "auto", "flex": 1}):
                    for i, task in enumerate(col_data["tasks"]):
                        mui.Card(
                            mui.CardContent(
                                mui.Typography(task["agent"][:3].upper(), variant="caption", sx={"color": task["color"], "fontWeight": "bold"}),
                                mui.Typography(task["text"], variant="body2", sx={"color": "#fff", "marginTop": "4px"})
                            ),
                            sx={
                                "marginBottom": "8px",
                                "backgroundColor": "#2d2d2d",
                                "borderLeft": f"4px solid {task['color']}",
                                "&:hover": {"backgroundColor": "#3d3d3d"}
                            }
                        )

                    if not col_data["tasks"]:
                        mui.Typography("No tasks", variant="body2", sx={"color": "#666", "textAlign": "center", "padding": "20px"})

st.divider()
st.caption(f"[GitHub](https://github.com/{GITHUB_REPO}) • Drag columns to rearrange")
