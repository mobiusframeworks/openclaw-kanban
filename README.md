# OpenClaw Kanban

Task management dashboard for AI agent teams.

## Run Locally
```bash
pip install streamlit
streamlit run kanban.py
```

## Deploy to Streamlit Cloud
1. Push to GitHub
2. Go to share.streamlit.io
3. Connect repo, select `kanban.py`
4. Deploy (free)

## Features
- Tab per agent (BML, EnergyScout, Real Estate, Analytics)
- Combined "All Tasks" view
- Color-coded columns: TODO, In Progress, Blocked, Done
- Reads from Obsidian backlog files
