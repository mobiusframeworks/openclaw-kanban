#!/usr/bin/env python3
"""
OpenClaw Kanban Dashboard
Reads backlogs from GitHub for Streamlit Cloud deployment
"""

import streamlit as st
import requests
import re

st.set_page_config(page_title="OpenClaw Kanban", layout="wide")

# GitHub raw URLs for backlogs
GITHUB_BASE = "https://raw.githubusercontent.com/mobiusframeworks/openclaw-kanban/main/backlogs"

BACKLOGS = {
    "BML CEO": f"{GITHUB_BASE}/bml-ceo.md",
    "EnergyScout CEO": f"{GITHUB_BASE}/energyscout-ceo.md",
    "Real Estate CEO": f"{GITHUB_BASE}/realestate-ceo.md",
    "Analytics": f"{GITHUB_BASE}/analytics.md",
    "Assistant": f"{GITHUB_BASE}/assistant.md",
}

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_backlog(url: str) -> str:
    """Fetch backlog from GitHub"""
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.text
        return ""
    except:
        return ""

def parse_tasks(content: str) -> dict:
    """Parse markdown backlog into task lists"""
    tasks = {"TODO": [], "IN PROGRESS": [], "DONE": [], "BLOCKED": []}

    if not content:
        return tasks

    lines = content.split('\n')
    current_status = "TODO"

    for line in lines:
        # Check for status markers
        if "**Status:**" in line or "Status:" in line:
            line_lower = line.lower()
            if "complete" in line_lower or "done" in line_lower:
                current_status = "DONE"
            elif "progress" in line_lower:
                current_status = "IN PROGRESS"
            elif "blocked" in line_lower:
                current_status = "BLOCKED"
            else:
                current_status = "TODO"

        # Check for task headers
        if line.startswith("### "):
            task_name = line.replace("###", "").strip()
            task_name = re.sub(r'^\d+\.\s*', '', task_name)
            if task_name and task_name not in tasks[current_status]:
                tasks[current_status].append(task_name)

        # Check for checkbox items
        if line.strip().startswith("- [x]"):
            task = line.replace("- [x]", "").strip()
            if task and task not in tasks["DONE"]:
                tasks["DONE"].append(task)
        elif line.strip().startswith("- [ ]"):
            task = line.replace("- [ ]", "").strip()
            if task and task not in tasks["TODO"]:
                tasks["TODO"].append(task)

    return tasks

def render_column(title: str, items: list, color: str):
    """Render a kanban column"""
    st.markdown(f"### {title} ({len(items)})")
    for item in items[:10]:
        st.markdown(f"""
        <div style="background-color: {color}; padding: 10px; margin: 5px 0; border-radius: 5px; color: black;">
            {item[:60]}{'...' if len(item) > 60 else ''}
        </div>
        """, unsafe_allow_html=True)

st.title("OpenClaw Kanban")
st.caption("Task overview across all agents • Auto-refreshes every 5 min")

if st.button("Refresh Now"):
    st.cache_data.clear()

# Tabs for each agent
tabs = st.tabs(list(BACKLOGS.keys()) + ["All Tasks"])

for i, (agent, url) in enumerate(BACKLOGS.items()):
    with tabs[i]:
        content = fetch_backlog(url)
        if content:
            tasks = parse_tasks(content)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                render_column("TODO", tasks["TODO"], "#FFE082")
            with col2:
                render_column("IN PROGRESS", tasks["IN PROGRESS"], "#81D4FA")
            with col3:
                render_column("BLOCKED", tasks["BLOCKED"], "#EF9A9A")
            with col4:
                render_column("DONE", tasks["DONE"], "#A5D6A7")
        else:
            st.info(f"No backlog found for {agent}")

# All Tasks tab
with tabs[-1]:
    all_tasks = {"TODO": [], "IN PROGRESS": [], "DONE": [], "BLOCKED": []}

    for agent, url in BACKLOGS.items():
        content = fetch_backlog(url)
        if content:
            tasks = parse_tasks(content)
            for status in all_tasks:
                for task in tasks[status]:
                    all_tasks[status].append(f"[{agent}] {task}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_column("TODO", all_tasks["TODO"], "#FFE082")
    with col2:
        render_column("IN PROGRESS", all_tasks["IN PROGRESS"], "#81D4FA")
    with col3:
        render_column("BLOCKED", all_tasks["BLOCKED"], "#EF9A9A")
    with col4:
        render_column("DONE", all_tasks["DONE"], "#A5D6A7")

st.divider()
st.caption("Synced from Obsidian → GitHub • [OpenClaw](https://github.com/ahorton/openclaw-kanban)")
