// Detect if running remotely or on mobile
const isLocal = ['localhost', '127.0.0.1', ''].includes(location.hostname) || location.protocol === 'file:';
const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
const savedExecutorUrl = localStorage.getItem('executor-url');
const executorHost = (location.hostname && location.hostname !== '') ? location.hostname : 'localhost';
let EXECUTOR_URL = savedExecutorUrl || (isLocal ? 'http://localhost:8765' : `http://${executorHost}:8765`);

function setExecutorUrl() {
    const url = prompt('Enter executor URL (e.g., https://your-tunnel.ngrok.io):', EXECUTOR_URL);
    if (url) {
        localStorage.setItem('executor-url', url);
        EXECUTOR_URL = url;
        location.reload();
    }
}
const AGENTS = [
    { id: 'bml', name: 'BML CEO', color: '#f7931a' },
    { id: 'ene', name: 'EnergyScout', color: '#3fb950' },
    { id: 'rea', name: 'Real Estate', color: '#58a6ff' },
    { id: 'ana', name: 'Analytics', color: '#a371f7' },
    { id: 'ass', name: 'Assistant', color: '#f78166' }
];
const TIME_SLOTS = ['Now', '+1h', '+2h', '+3h', 'Today', 'Tomorrow', 'This Week', 'Next Week', 'Later'];

let tasks = JSON.parse(localStorage.getItem('dashboard-tasks') || '[]');
let cronJobs = [];
let cronJobStatus = {};
let currentView = 'kanban';
let matrixFilter = 'q1';
let draggedId = null;
let executorOnline = false;
let routingAvailable = false;
let routingStats = { local_tasks: 0, cloud_tasks: 0, total_tasks: 0 };
let agentFilter = localStorage.getItem('agent-filter') || 'all';
let quadrantFilter = localStorage.getItem('quadrant-filter') || 'all';

function filterByQuadrant(quadrant) {
    quadrantFilter = quadrant;
    localStorage.setItem('quadrant-filter', quadrant);
    document.querySelectorAll('.matrix-filter').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.quadrant === quadrant);
    });
    renderAll();
}

function filterByAgent(agent) {
    agentFilter = agent;
    localStorage.setItem('agent-filter', agent);
    document.querySelectorAll('.agent-filter').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.agent === agent);
    });
    if (agent !== 'all') {
        const chatBotMap = { bml: 'bitcoinml', ene: 'energyscout', rea: 'realestate', ana: 'assistant', ass: 'assistant' };
        document.getElementById('chatBot').value = chatBotMap[agent] || 'assistant';
        renderChat();
    }
    renderAll();
}

function initAgentFilter() {
    const savedAgent = localStorage.getItem('agent-filter') || 'all';
    const savedQuadrant = localStorage.getItem('quadrant-filter') || 'all';
    agentFilter = savedAgent;
    quadrantFilter = savedQuadrant;
    document.querySelectorAll('.agent-filter').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.agent === savedAgent);
    });
    document.querySelectorAll('.matrix-filter').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.quadrant === savedQuadrant);
    });
}

async function init() {
    initAgentFilter();
    updateMainHeight();
    await checkExecutor();
    await syncTasksFromServer();  // Sync tasks from server on load
    await loadCronJobs();
    autoMovePastCronJobs();
    await loadLinkedBots();
    await loadAgentActivity();
    renderAll();

    // Auto-show terminal panel on load
    initTerminal();

    setInterval(checkExecutor, 10000);
    setInterval(pollTaskStatus, 15000);
    setInterval(loadLinkedBots, 10000);
    setInterval(loadAgentActivity, 5000);
    setInterval(syncTasksFromServer, 30000);  // Sync tasks every 30 seconds
    setInterval(loadWorkers, 5000);  // Poll parallel workers
    setInterval(async () => {
        await loadCronJobs();
        autoMovePastCronJobs();
        if (currentView === 'timeline') renderTimeline();
    }, 60000);
}

function initTerminal() {
    // Show terminal panel by default
    const panel = document.getElementById('bottomPanel');
    const panelContent = panel?.querySelector('.panel-content');
    if (panelContent) {
        panelContent.style.display = 'flex';
        panel.classList.add('expanded');
    }

    // Set default agent and start refresh
    currentCliAgent = 'assistant';
    document.getElementById('cliAgent').textContent = 'claude-assistant';
    document.getElementById('cliPath').textContent = '/Users/macmini/Vaults/openclaw';
    cliPanelVisible = true;

    // Initialize vertical sidebar tabs
    document.querySelectorAll('.agent-tab-vertical').forEach(tab => {
        const isActive = tab.dataset.agent === 'assistant';
        tab.classList.toggle('active', isActive);
        tab.style.opacity = isActive ? '1' : '0.5';
    });

    // Start CLI refresh
    refreshCli();
    if (cliRefreshInterval) clearInterval(cliRefreshInterval);
    cliRefreshInterval = setInterval(refreshCli, 2000);

    // Focus input
    setTimeout(() => document.getElementById('cliInput')?.focus(), 500);
}

function switchTerminalAgent(agent) {
    currentCliAgent = agent;
    document.getElementById('cliAgent').textContent = `claude-${agent}`;

    // Update vertical sidebar tabs
    document.querySelectorAll('.agent-tab-vertical').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.agent === agent);
        tab.style.opacity = tab.dataset.agent === agent ? '1' : '0.5';
    });

    // Update path based on agent
    const agentPaths = {
        'assistant': '/Users/macmini/Vaults/openclaw',
        'bitcoinml': '/Users/macmini/bitcoinml',
        'energyscout': '/Users/macmini/energyscout',
        'realestate': '/Users/macmini/realestate',
        'analytics': '/Users/macmini/Vaults/openclaw'
    };
    const path = agentPaths[agent] || '/Users/macmini/Vaults/openclaw';
    document.getElementById('cliPath').textContent = path;
    document.getElementById('cliRepoSelect').value = path;

    // Refresh output
    refreshCli();

    // Focus input
    document.getElementById('cliInput')?.focus();
}

function copyPath() {
    const path = document.getElementById('cliPath').textContent;
    navigator.clipboard.writeText(path).then(() => {
        const btn = document.querySelector('.path-bar button');
        const originalText = btn.textContent;
        btn.textContent = 'copied!';
        btn.style.color = '#3fb950';
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.color = '#9eaab6';
        }, 1500);
    });
}

function updatePath() {
    const select = document.getElementById('cliRepoSelect');
    document.getElementById('cliPath').textContent = select.value;
}

function handleTerminalKeydown(event) {
    const input = event.target;

    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendCliCommand();
    } else if (event.key === 'Escape') {
        event.preventDefault();
        sendCliKey('Escape');
    } else if (event.key === 'c' && event.ctrlKey) {
        event.preventDefault();
        sendCliKey('C-c');
    } else if (event.key === 'Tab') {
        event.preventDefault();
        if (event.shiftKey) {
            sendCliKey('BTab');
        } else {
            // Send tab for autocomplete
            sendCliKey('Tab');
        }
    } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        sendCliKey('Up');
    } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        sendCliKey('Down');
    }
}

async function loadDailyBrief() {
    if (!executorOnline) return;
    try {
        const resp = await fetch(`${EXECUTOR_URL}/daily-brief`);
        const brief = await resp.json();
        if (brief.bots?.assistant?.outbox) {
            chatHistory.push({
                bot: 'assistant',
                type: 'bot',
                content: '📋 **Daily Brief**\n\n' + brief.bots.assistant.outbox,
                timestamp: new Date().toISOString()
            });
        }
        if (brief.backlog?.length > 0) {
            chatHistory.push({
                bot: 'assistant',
                type: 'bot',
                content: '📝 **Top TODOs:**\n' + brief.backlog.slice(0, 5).join('\n'),
                timestamp: new Date().toISOString()
            });
        }
        const botStatus = Object.entries(brief.bots || {})
            .map(([name, data]) => `${name}: ${data.tmux ? '🟢' : '⚫'}`)
            .join(' | ');
        if (botStatus) {
            chatHistory.push({
                bot: 'assistant',
                type: 'bot',
                content: '🤖 **Bot Status:** ' + botStatus,
                timestamp: new Date().toISOString()
            });
        }
        localStorage.setItem('chat-history', JSON.stringify(chatHistory));
        document.getElementById('chatBot').value = 'assistant';
        renderChat();
    } catch (e) {
        console.log('Could not load daily brief:', e);
    }
}

async function checkExecutor() {
    try {
        const resp = await fetch(`${EXECUTOR_URL}/status`, { mode: 'cors' });
        executorOnline = resp.ok;
    } catch { executorOnline = false; }
    const dot = document.getElementById('serverStatus');
    dot.className = 'status-dot ' + (executorOnline ? 'online' : 'offline');
    document.getElementById('executorBtn').textContent = executorOnline ? 'Executor Online' : 'Start Executor';

    // Check routing availability
    if (executorOnline) {
        try {
            const routingResp = await fetch(`${EXECUTOR_URL}/routing-stats`);
            const data = await routingResp.json();
            routingAvailable = data.available || false;
            routingStats = data;
        } catch { routingAvailable = false; }
    }

    // Update routing badge
    const routingBadge = document.getElementById('routingBadge');
    if (routingBadge) {
        if (routingAvailable) {
            const providers = routingStats.providers || {};
            const ollamaOk = providers.ollama?.available;
            const openrouterOk = providers.openrouter?.available;
            const localPct = (routingStats.local_percentage || 0).toFixed(0);
            const openrouterPct = (routingStats.openrouter_percentage || 0).toFixed(0);

            let badges = [];
            if (ollamaOk) badges.push(`🏠Local`);
            if (openrouterOk) badges.push(`🌐Free`);
            badges.push(`☁️Pro`);

            routingBadge.style.display = 'inline';
            routingBadge.style.background = ollamaOk ? '#1f6feb' : (openrouterOk ? '#f0883e' : '#8957e5');
            routingBadge.style.color = '#fff';
            routingBadge.innerHTML = badges.join(' | ');
            routingBadge.title = `Routing: ${routingStats.local_tasks || 0} Ollama, ${routingStats.openrouter_tasks || 0} OpenRouter, ${routingStats.cloud_tasks || 0} Claude`;
        } else if (executorOnline) {
            routingBadge.style.display = 'inline';
            routingBadge.style.background = '#8957e5';
            routingBadge.style.color = '#fff';
            routingBadge.innerHTML = '☁️ Claude only';
            routingBadge.title = 'Local models unavailable - routing to Claude';
        } else {
            routingBadge.style.display = 'none';
        }
    }
}

async function checkRouting(taskText) {
    if (!executorOnline) return null;
    try {
        const resp = await fetch(`${EXECUTOR_URL}/routing-check?task=${encodeURIComponent(taskText)}`);
        return await resp.json();
    } catch { return null; }
}

async function loadCronJobs() {
    if (!executorOnline) return;
    try {
        const resp = await fetch(`${EXECUTOR_URL}/jobs`);
        const data = await resp.json();
        cronJobs = data.jobs || [];
        const statusResp = await fetch(`${EXECUTOR_URL}/job-status`);
        const statusData = await statusResp.json();
        cronJobStatus = statusData.jobs || {};
    } catch { cronJobs = []; cronJobStatus = {}; }
}

function autoMovePastCronJobs() {
    const now = new Date();
    const currentHour = now.getHours();
    const today = now.toISOString().split('T')[0];
    const botToAgent = {
        'assistant': 'ass', 'bitcoinml': 'bml', 'energyscout': 'ene',
        'realestate': 'rea', 'analytics': 'ana', 'system': 'ass'
    };
    cronJobs.forEach(job => {
        if (!job.schedule || !job.schedule.includes(':')) return;
        const [h] = job.schedule.split(':');
        const jobHour = parseInt(h);
        if (jobHour >= currentHour) return;
        const cronTaskId = `cron-${job.name}-${today}`;
        if (tasks.find(t => t.id === cronTaskId)) return;
        const jobStatus = cronJobStatus[job.name];
        let status = 'ai-review';
        let notes = '';
        if (jobStatus?.completed) {
            notes = `✓ Cron job completed at ${jobStatus.time}`;
        } else if (jobStatus?.failed) {
            notes = `✗ Cron job FAILED at ${jobStatus.time}`;
            status = 'blocked';
        } else {
            notes = `? Cron job did not run (no log entry found)`;
            status = 'blocked';
        }
        const newTask = {
            id: cronTaskId,
            text: `[CRON] ${job.name}`,
            agent: botToAgent[job.bot] || 'ass',
            quadrant: 'q3',
            status: status,
            notes: notes,
            scheduled: true,
            scheduledSlot: 0,
            scheduledAgent: botToAgent[job.bot] || 'ass',
            created: new Date().toISOString(),
            cronJob: true,
            cronJobName: job.name,
            workLog: [{
                timestamp: new Date().toLocaleString(),
                content: notes,
                type: jobStatus?.completed ? 'completed' : 'warning'
            }]
        };
        tasks.push(newTask);
    });
    save();
}

async function pollTaskStatus() {
    if (!executorOnline) return;
    const executing = tasks.filter(t => t.status === 'executing');
    if (executing.length === 0) return;
    for (const task of executing) {
        try {
            const resp = await fetch(`${EXECUTOR_URL}/outbox?bot=${task.agent}`);
            const data = await resp.json();
            if (data.content) {
                const lower = data.content.toLowerCase();
                if (lower.includes('done') || lower.includes('completed') || lower.includes('finished')) {
                    task.status = 'done';
                    task.notes = data.content.substring(0, 200);
                    addWorkLog(task.id, 'Completed: ' + data.content.substring(0, 300), 'completed');
                } else if (lower.includes('blocked') || lower.includes('need') || lower.includes('error')) {
                    task.status = 'blocked';
                    task.notes = data.content.substring(0, 200);
                    addWorkLog(task.id, 'Blocked: ' + data.content.substring(0, 300), 'blocked');
                }
            }
        } catch {}
    }
    save();
    renderAll();
}

function switchView(view) {
    currentView = view;
    document.querySelectorAll('.view-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.view-tab[onclick="switchView('${view}')"]`).classList.add('active');
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(`${view}-view`).classList.add('active');
    renderAll();
}

function renderAll() {
    if (currentView === 'kanban') renderKanban();
    else renderTimeline();
}

function renderKanban() {
    const quadrantOrder = { q1: 0, q2: 1, q3: 2, q4: 3 };
    ['todo', 'progress', 'blocked', 'done'].forEach(status => {
        const container = document.getElementById(`k-${status}`);
        let statusTasks = tasks.filter(t => {
            if (status === 'progress') return t.status === 'progress' || t.status === 'executing';
            if (status === 'blocked') return t.status === 'blocked' || t.status === 'ai-review' || t.status === 'human-review';
            return t.status === status;
        });
        if (quadrantFilter !== 'all') {
            statusTasks = statusTasks.filter(t => t.quadrant === quadrantFilter);
        }
        if (agentFilter !== 'all') {
            statusTasks = statusTasks.filter(t => t.agent === agentFilter);
        }
        if (status === 'progress') {
            statusTasks.sort((a, b) => {
                if (a.status === 'executing' && b.status !== 'executing') return -1;
                if (b.status === 'executing' && a.status !== 'executing') return 1;
                return (quadrantOrder[a.quadrant] || 9) - (quadrantOrder[b.quadrant] || 9);
            });
        } else {
            statusTasks.sort((a, b) => (quadrantOrder[a.quadrant] || 9) - (quadrantOrder[b.quadrant] || 9));
        }
        document.getElementById(`k-count-${status}`).textContent = statusTasks.length;

        // Render Review column with sub-sections
        if (status === 'blocked') {
            const aiReviewTasks = statusTasks.filter(t => t.status === 'ai-review');
            const humanReviewTasks = statusTasks.filter(t => t.status === 'human-review');
            const blockedTasks = statusTasks.filter(t => t.status === 'blocked');
            const cronTasks = statusTasks.filter(t => t.cronJob);

            let html = '';
            if (aiReviewTasks.length > 0) {
                html += '<div class="review-section-header ai-review">🤖 AI Review (' + aiReviewTasks.length + ')</div>';
                html += aiReviewTasks.map(t => renderCard(t)).join('');
            }
            if (humanReviewTasks.length > 0) {
                html += '<div class="review-section-header human-review">👤 Human Review (' + humanReviewTasks.length + ')</div>';
                html += humanReviewTasks.map(t => renderCard(t)).join('');
            }
            if (blockedTasks.length > 0) {
                html += '<div class="review-section-header blocked">⚠️ Blocked/Failed (' + blockedTasks.length + ')</div>';
                html += blockedTasks.map(t => renderCard(t)).join('');
            }
            if (cronTasks.length > 0) {
                html += renderCronSummary(cronTasks);
            }
            container.innerHTML = html;
        } else {
            container.innerHTML = statusTasks.map(t => renderCard(t)).join('');
        }
    });
    setupDragDrop();
    renderExecutingBanner();
}

function renderExecutingBanner() {
    const doingCol = document.getElementById('k-progress');
    const executing = tasks.filter(t => t.status === 'executing');

    if (executing.length === 0) {
        const existing = doingCol.querySelector('.executing-banner');
        if (existing) existing.remove();
        return;
    }

    let banner = doingCol.querySelector('.executing-banner');
    if (!banner) {
        banner = document.createElement('div');
        banner.className = 'executing-banner';
        doingCol.prepend(banner);
    }

    const tasks_text = executing.length === 1 ? 'task' : 'tasks';
    const elapsed = executing[0].startedAt ?
        Math.round((Date.now() - new Date(executing[0].startedAt).getTime()) / 60000) : 0;

    banner.innerHTML = `
        <div class="pulse"></div>
        <span>${executing.length} ${tasks_text} executing · ${elapsed}m elapsed</span>
    `;
}

function renderCronSummary(cronTasks) {
    const completed = cronTasks.filter(t => {
        const jobName = t.cronJobName;
        return cronJobStatus[jobName]?.completed;
    }).length;
    const failed = cronTasks.filter(t => {
        const jobName = t.cronJobName;
        return cronJobStatus[jobName]?.failed;
    }).length;

    const html = `
        <div class="cron-summary-card" onclick="this.classList.toggle('expanded')">
            <div class="summary-header">
                <span>⏰ Daily Cron Summary</span>
                <span class="summary-badge ${failed > 0 ? 'warning' : ''}">${completed}/${cronTasks.length} passed</span>
            </div>
            <div class="summary-content">
                <ul class="cron-checklist">
                    ${cronTasks.map(t => {
                        const jobName = t.cronJobName;
                        const status = cronJobStatus[jobName];
                        const passed = status?.completed;
                        return `<li class="${passed ? 'passed' : 'failed'}">
                            ${passed ? '✓' : '✗'} ${jobName}
                        </li>`;
                    }).join('')}
                </ul>
            </div>
        </div>
    `;
    return html;
}

let sidebarCollapsed = false;

function toggleReadySidebar() {
    sidebarCollapsed = !sidebarCollapsed;
    document.getElementById('readySidebar').classList.toggle('collapsed', sidebarCollapsed);
    document.getElementById('sidebarArrow').textContent = sidebarCollapsed ? '▶' : '◀';
    document.getElementById('sidebarLabel').textContent = sidebarCollapsed ? 'Tasks' : 'Ready to Schedule';
}

function renderReadyTasks() {
    let readyTasks = tasks.filter(t => (t.status === 'progress' || t.status === 'todo') && !t.scheduled);
    if (agentFilter !== 'all') {
        readyTasks = readyTasks.filter(t => t.agent === agentFilter);
    }
    if (readyTasks.length === 0) {
        document.getElementById('readyTasks').innerHTML = `
            <div class="sidebar-empty">
                No tasks in Backlog or Doing${agentFilter !== 'all' ? ' for ' + agentFilter.toUpperCase() : ''}.<br><br>
                Move tasks to Doing in Kanban view, then schedule them here.
            </div>
        `;
        return;
    }
    document.getElementById('readyTasks').innerHTML = readyTasks.map(t => `
        <div class="ready-task" draggable="true" data-id="${t.id}">
            <div class="task-agent">${t.agent.toUpperCase()}</div>
            <div class="task-text">${t.text}</div>
        </div>
    `).join('');
    document.querySelectorAll('.ready-task').forEach(el => {
        el.ondragstart = e => {
            draggedId = el.dataset.id;
            el.classList.add('dragging');
        };
        el.ondragend = e => el.classList.remove('dragging');
    });
}

function renderTimeline() {
    const now = new Date();
    const currentHour = now.getHours();
    const botToAgent = {
        'assistant': 'ass', 'bitcoinml': 'bml', 'energyscout': 'ene',
        'realestate': 'rea', 'analytics': 'ana', 'system': 'ass'
    };
    const timeSlots = [];
    for (let i = 0; i < 12; i++) {
        const hour = (currentHour + i) % 24;
        const label = i === 0 ? 'Now' : `${hour}:00`;
        timeSlots.push({ hour, label, isNow: i === 0 });
    }
    document.getElementById('time-header').innerHTML = timeSlots.map(s =>
        `<div class="time-slot-label ${s.isNow ? 'now' : ''}">${s.label}</div>`
    ).join('');
    document.getElementById('swimlanes').innerHTML = AGENTS.map(agent => `
        <div class="swimlane">
            <div class="swimlane-label">
                <div class="dot" style="background:${agent.color}"></div>
                ${agent.name}
            </div>
            <div class="swimlane-track">
                ${timeSlots.map((slot, i) => `
                    <div class="time-slot ${slot.isNow ? 'now' : ''}" data-agent="${agent.id}" data-slot="${i}" data-hour="${slot.hour}"></div>
                `).join('')}
            </div>
        </div>
    `).join('');

    cronJobs.forEach(job => {
        if (!job.schedule || !job.schedule.includes(':')) return;
        const [h] = job.schedule.split(':');
        const jobHour = parseInt(h);
        const agentId = botToAgent[job.bot] || 'ass';
        const slotIndex = timeSlots.findIndex(s => s.hour === jobHour);
        if (slotIndex === -1) return;
        const slot = document.querySelector(`.time-slot[data-agent="${agentId}"][data-slot="${slotIndex}"]`);
        if (!slot) return;
        let status = 'waiting';
        let statusNote = '';
        const jobStatus = cronJobStatus[job.name];
        if (jobHour < currentHour) {
            if (jobStatus?.completed) {
                status = 'done';
                statusNote = '✓ Completed';
            } else if (jobStatus?.failed) {
                status = 'stopped';
                statusNote = '✗ Failed';
            } else {
                status = 'review';
                statusNote = '? Not run';
            }
        } else if (jobHour === currentHour) {
            status = 'running';
            statusNote = '● Running';
        }
        slot.innerHTML += `
            <div class="timeline-task ${status}" onclick="runCronJob('${job.name}')" title="${statusNote}">
                <div class="task-name">${job.name}</div>
                <div class="task-time">${job.schedule} ${statusNote}</div>
            </div>
        `;
    });

    tasks.filter(t => t.scheduled && (agentFilter === 'all' || t.agent === agentFilter)).forEach(t => {
        const slot = document.querySelector(`.time-slot[data-agent="${t.scheduledAgent}"][data-slot="${t.scheduledSlot}"]`);
        if (!slot) return;
        let status = 'waiting';
        if (t.status === 'executing') status = 'running';
        else if (t.status === 'done') status = 'done';
        else if (t.status === 'ai-review') status = 'review';
        else if (t.status === 'human-review') status = 'human-review';
        const playBtn = status !== 'running' && status !== 'done' ? `<button class="play-btn" onclick="event.stopPropagation();playTask('${t.id}')" title="Execute">▶ Run</button>` : '';
        const stopBtn = status === 'running' ? `<button class="stop-btn" onclick="event.stopPropagation();stopTask('${t.id}')" title="Stop">⏹ Stop</button>` : '';
        const aiReviewBtn = status === 'running' ? `<button class="review-btn" onclick="event.stopPropagation();aiReviewTask('${t.id}')" title="Send to AI Review">AI Review</button>` : '';
        const humanBtn = status === 'review' ? `<button class="human-btn" onclick="event.stopPropagation();humanReviewTask('${t.id}')" title="Send to Human Review">Human Review</button>` : '';
        const doneBtn = (status === 'human-review' || status === 'review') ? `<button class="done-btn" onclick="event.stopPropagation();completeTask('${t.id}')" title="Approve & Archive">✓ Done</button>` : '';
        const progress = status === 'running' ? getTaskProgress(t) : null;
        const progressHtml = progress ? `
            <div class="task-progress">
                <div class="progress-bar"><div class="progress-fill" style="width:${progress.percent}%"></div></div>
                <div class="progress-text"><span>${progress.percent}%</span><span>${progress.eta}</span></div>
            </div>` : '';
        slot.innerHTML += `
            <div class="timeline-task ${status}" onclick="openDetailModal('${t.id}')" draggable="true" data-id="${t.id}">
                <div class="task-name">${t.text.substring(0, 30)}</div>
                ${progressHtml}
                <div class="task-controls">${playBtn}${stopBtn}${aiReviewBtn}${humanBtn}${doneBtn}</div>
            </div>
        `;
    });

    tasks.filter(t => t.status === 'executing' && !t.scheduled && (agentFilter === 'all' || t.agent === agentFilter)).forEach(t => {
        const agentId = t.agent || 'ass';
        const slot = document.querySelector(`.time-slot[data-agent="${agentId}"][data-slot="0"]`);
        if (!slot) return;
        const progress = getTaskProgress(t);
        slot.innerHTML += `
            <div class="timeline-task running" onclick="openDetailModal('${t.id}')" data-id="${t.id}">
                <div class="task-name">${t.text.substring(0, 30)}</div>
                <div class="task-progress">
                    <div class="progress-bar"><div class="progress-fill" style="width:${progress.percent}%"></div></div>
                    <div class="progress-text"><span>${progress.percent}%</span><span>${progress.eta}</span></div>
                </div>
                <div class="task-controls">
                    <button class="stop-btn" onclick="event.stopPropagation();stopTask('${t.id}')" title="Stop">⏹ Stop</button>
                    <button class="review-btn" onclick="event.stopPropagation();aiReviewTask('${t.id}')" title="Send to AI Review">AI Review</button>
                </div>
            </div>
        `;
    });

    renderReadyTasks();
    setupDragDrop();
}

function renderProgressTrail(task) {
    const statuses = ['todo', 'progress', 'blocked', 'done'];
    const currentIndex = statuses.indexOf(task.status === 'executing' ? 'progress' : task.status);

    return `
        <div class="task-progress-trail">
            ${statuses.map((s, i) => {
                let classes = 'trail-dot';
                if (i < currentIndex) classes += ' passed';
                else if (i === currentIndex) classes += ' active';
                return `<span class="${classes}" title="${s}"></span>`;
            }).join('')}
        </div>
    `;
}

function renderCard(t, mini = false) {
    const executingClass = t.status === 'executing' ? 'executing' : '';
    const completedClass = t.status === 'done' ? 'completed' : '';
    let executionDetails = '';
    if (t.status === 'executing') {
        const agentActivity = agentActivityCache[t.agent] || {};
        const statusText = agentActivity.status || 'working';
        const statusEmoji = { thinking: '💭', working: '🔄', error: '❌', completed: '✅', idle: '💤' }[statusText] || '🔄';
        const elapsed = t.startedAt ? getElapsedTime(t.startedAt) : 'recently';
        const preview = agentActivity.current_output ?
            agentActivity.current_output.split('\n').slice(-3).join('\n').substring(0, 150) : '';
        executionDetails = `
            <div class="execution-status">
                <span>${statusEmoji} ${statusText.charAt(0).toUpperCase() + statusText.slice(1)}</span>
                <span style="color:#9eaab6;margin-left:8px;">${elapsed}</span>
            </div>
            <div class="terminal-preview" id="term-${t.id}" onclick="event.stopPropagation(); showCli('${t.agent}')">
                <pre>${preview || 'Click to view live output...'}</pre>
            </div>
            <div style="margin-top:6px;display:flex;gap:4px;" onclick="event.stopPropagation()">
                <button class="view-cli-btn" onclick="showCli('${t.agent}')" style="flex:1;background:#238636;">📺 Live Terminal</button>
                <button class="check-btn" onclick="crossAgentCheck('${t.id}', '${t.agent}')">👁</button>
            </div>
        `;
    }
    let doingActions = '';
    if (t.status === 'progress') {
        if (t.schedule && t.schedule.time) {
            const days = t.schedule.days?.length ? t.schedule.days.map(d => d.substring(0,3)).join(', ') : 'Daily';
            doingActions = `
                <div class="doing-actions scheduled-info">
                    <span>📅 Scheduled: ${t.schedule.time} (${days})</span>
                </div>
            `;
        } else {
            doingActions = `
                <div class="doing-actions" onclick="event.stopPropagation()">
                    <button class="execute-btn" onclick="quickExecute('${t.id}')" title="Execute now">▶ Run</button>
                    <button class="schedule-btn" onclick="goToTimelineWithTask('${t.id}')" title="Schedule on Timeline">📅 Schedule</button>
                </div>
            `;
        }
    }
    const tooltipNotes = t.notes ? t.notes.substring(0, 200) : '';
    const lastLog = t.workLog?.length ? t.workLog[t.workLog.length - 1].content.substring(0, 100) : '';
    const tooltipText = [tooltipNotes, lastLog ? 'Last: ' + lastLog : ''].filter(Boolean).join(' | ') || 'Click for details';

    return `
        <div class="task-card ${t.agent} ${executingClass} ${completedClass}" draggable="true" data-id="${t.id}" onclick="openDetailModal('${t.id}')" title="${tooltipText.replace(/"/g, '&quot;')}">
            <div class="task-actions" onclick="event.stopPropagation()">
                ${executorOnline ? `<button class="run" onclick="quickExecute('${t.id}')" title="Execute">▶</button>` : ''}
                <button onclick="toggleComplete('${t.id}')" title="Toggle complete">✓</button>
                <button onclick="openEditModal('${t.id}')" title="Edit">✎</button>
            </div>
            <div class="task-badges">
                <span class="badge agent">${t.agent.toUpperCase()}</span>
                <span class="badge ${t.quadrant}">Q${t.quadrant.charAt(1)}</span>
                ${t.status === 'executing' ? '<span class="badge executing">RUNNING</span>' : ''}
                ${t.workLog && t.workLog.length ? '<span class="badge" style="background:#238636;">📋</span>' : ''}
                ${t.routedTo ? `<span class="badge" style="background:${t.routedTo === 'ollama' ? '#1f6feb' : t.routedTo === 'openrouter' ? '#f0883e' : '#8957e5'};font-size:9px;" title="${t.model || 'claude'}">${t.routedTo === 'ollama' ? '🏠LOCAL' : t.routedTo === 'openrouter' ? '🌐FREE' : '☁️PRO'}</span>` : ''}
            </div>
            <div class="task-text">${t.text}</div>
            ${t.notes ? `<div class="task-notes">${t.notes.substring(0, 80)}</div>` : ''}
            ${doingActions}
            ${executionDetails}
            ${renderReviewActions(t)}
            ${renderProgressTrail(t)}
        </div>
    `;
}

function renderReviewActions(t) {
    if (t.status !== 'ai-review' && t.status !== 'human-review' && t.status !== 'blocked') return '';
    const statusLabel = t.status === 'ai-review' ? '🤖 AI Review' :
                       t.status === 'human-review' ? '👤 Human Review' : '⚠️ Blocked';
    const isComplete = t.workLog?.some(w => w.type === 'completed');
    const statusBadge = isComplete ?
        '<span style="color:#3fb950;">✓ Complete</span>' :
        '<span style="color:#f0883e;">⏳ Pending</span>';
    return `
        <div class="review-section" style="margin-top:8px;padding-top:8px;border-top:1px solid #30363d;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <span style="font-size:11px;color:#9eaab6;">${statusLabel}</span>
                ${statusBadge}
            </div>
            <div class="review-actions" onclick="event.stopPropagation()" style="display:flex;gap:4px;flex-wrap:wrap;">
                <button onclick="moveTaskTo('${t.id}','todo')" style="background:#21262d;border:1px solid #30363d;color:#e6edf3;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:10px;">📋 Backlog</button>
                <button onclick="moveTaskTo('${t.id}','progress')" style="background:#21262d;border:1px solid #30363d;color:#e6edf3;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:10px;">▶ Run Again</button>
                <button onclick="completeTask('${t.id}')" style="background:#238636;border:none;color:#fff;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:10px;">✓ Done</button>
                <button onclick="addQuickNote('${t.id}')" style="background:#21262d;border:1px solid #30363d;color:#e6edf3;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:10px;">📝 Note</button>
            </div>
        </div>
    `;
}

function moveTaskTo(id, newStatus) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    task.status = newStatus;
    task.scheduled = false;
    addWorkLog(id, 'Moved to ' + newStatus, 'move');
    save(); renderAll();
}

function addQuickNote(id) {
    const note = prompt('Add note:');
    if (!note) return;
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    task.notes = (task.notes ? task.notes + '\n' : '') + note;
    addWorkLog(id, 'Note: ' + note, 'note');
    save(); renderAll();
}

function goToTimelineWithTask(taskId) {
    switchView('timeline');
    setTimeout(() => {
        const taskEl = document.querySelector(`.ready-task[data-id="${taskId}"]`);
        if (taskEl) {
            taskEl.style.background = '#238636';
            setTimeout(() => taskEl.style.background = '', 2000);
        }
    }, 100);
}

function setupDragDrop() {
    document.querySelectorAll('[draggable="true"]').forEach(el => {
        el.ondragstart = e => { draggedId = e.target.dataset.id; e.target.classList.add('dragging'); };
        el.ondragend = e => e.target.classList.remove('dragging');
    });
    document.querySelectorAll('.kanban-cards').forEach(col => {
        col.ondragover = e => { e.preventDefault(); col.classList.add('drag-over'); };
        col.ondragleave = () => col.classList.remove('drag-over');
        col.ondrop = e => {
            e.preventDefault(); col.classList.remove('drag-over');
            const task = tasks.find(t => t.id === draggedId);
            if (task) { task.status = col.id.replace('k-', ''); task.scheduled = false; save(); renderAll(); }
        };
    });
    document.querySelectorAll('.time-slot').forEach(slot => {
        slot.ondragover = e => { e.preventDefault(); slot.classList.add('drag-over'); };
        slot.ondragleave = () => slot.classList.remove('drag-over');
        slot.ondrop = e => {
            e.preventDefault(); slot.classList.remove('drag-over');
            const task = tasks.find(t => t.id === draggedId);
            if (task) {
                task.scheduled = true;
                task.scheduledAgent = slot.dataset.agent;
                task.scheduledSlot = parseInt(slot.dataset.slot);
                save(); renderAll();
            }
        };
    });
}

function toggleComplete(id) {
    const task = tasks.find(t => t.id === id);
    if (task) { task.status = task.status === 'done' ? 'todo' : 'done'; save(); renderAll(); }
}

async function quickExecute(id, options = {}) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    if (!executorOnline) {
        alert('Executor not running. Starting it now...\n\nIf this doesn\'t work, run manually:\ncd ~/Vaults/openclaw/bridge/kanban && python executor.py');
        try {
            await fetch(`${EXECUTOR_URL}/status`);
        } catch {}
        return;
    }

    const agentType = options.agentType || task.agentType || 'general';
    const parallel = options.parallel || task.parallel || false;
    const workingDir = options.workingDir || task.linkedFiles?.[0]?.path?.replace(/\/[^\/]+$/, '') || null;

    task.status = 'executing';
    task.startedAt = new Date().toISOString();
    task.estimatedMinutes = task.estimatedMinutes || 5;
    task.agentType = agentType;

    const agentTypeEmoji = { general: '🤖', code: '💻', research: '🔬', fast: '⚡' }[agentType] || '🤖';
    addWorkLog(task.id, `Started ${agentTypeEmoji} ${agentType} execution${parallel ? ' (parallel)' : ''} via ${task.agent}`, 'started');
    save(); renderAll();
    startProgressTimer(task.id);

    try {
        const resp = await fetch(`${EXECUTOR_URL}/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: task.id,
                text: task.text,
                agent: task.agent,
                agent_type: agentType,
                parallel: parallel,
                working_dir: workingDir
            })
        });
        const data = await resp.json();
        if (data.success) {
            // Capture routing info
            task.routedTo = data.routed_to || 'claude';
            task.model = data.model || 'claude';
            task.workerId = data.worker_id || null;
            const provider = data.routed_to || 'claude';

            if (provider === 'ollama' || provider === 'openrouter') {
                // Fast execution completed immediately
                task.status = 'done';
                task.completedAt = new Date().toISOString();
                const modelShort = (data.model || '').split('/').pop().split(':')[0];
                addWorkLog(task.id, `Completed via ${provider.toUpperCase()} (${modelShort}) in ${data.latency_ms}ms`, 'completed');
            } else if (data.worker_id) {
                // Parallel worker spawned
                addWorkLog(task.id, `Spawned ${agentType} worker: ${data.worker_id}`, 'progress');
                loadWorkers();
            } else {
                // Claude execution via tmux - show live terminal
                addWorkLog(task.id, `Task sent to ${task.agent} inbox (Claude)`, 'progress');
                // Auto-open terminal for Claude tasks
                setTimeout(() => showCli(task.agent), 500);
            }
            save(); renderAll();
        }
    } catch (e) {
        task.status = 'blocked';
        task.notes = 'Executor error: ' + e.message;
        addWorkLog(task.id, 'Execution failed: ' + e.message, 'error');
        save(); renderAll();
    }
}

// Parallel workers management
let activeWorkers = [];

async function loadWorkers() {
    if (!executorOnline) return;
    try {
        const resp = await fetch(`${EXECUTOR_URL}/workers`);
        const data = await resp.json();
        activeWorkers = data.workers || [];
        renderWorkersDropdown();
    } catch (e) {
        activeWorkers = [];
    }
}

function renderWorkersDropdown() {
    const badge = document.getElementById('workersCountBadge');
    const content = document.getElementById('workersDropdownContent');
    if (!badge || !content) return;

    badge.textContent = activeWorkers.length;
    badge.style.background = activeWorkers.length > 0 ? '#a371f7' : '#6e7681';

    if (activeWorkers.length === 0) {
        content.innerHTML = '<div style="padding:12px;color:#6e7681;text-align:center;">No parallel workers running</div>';
        return;
    }

    const agentTypeColors = { general: '#58a6ff', code: '#f0883e', research: '#a371f7', fast: '#3fb950' };

    content.innerHTML = activeWorkers.map(w => `
        <div class="running-task-item" style="border-left:3px solid ${agentTypeColors[w.agent_type] || '#58a6ff'};">
            <span class="agent-tag" style="background:${agentTypeColors[w.agent_type] || '#30363d'};">${w.agent_type?.toUpperCase() || 'GEN'}</span>
            <span class="task-text" title="${w.task_id}">${w.task_id?.substring(0, 20) || 'unknown'}...</span>
            <span style="color:#6e7681;font-size:10px;">${w.window || ''}</span>
            <button class="stop-btn" onclick="stopWorker('${w.worker_id}')">Stop</button>
            <button style="background:#238636;border:none;color:#fff;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:10px;margin-left:4px;" onclick="viewWorker('${w.worker_id}')">View</button>
        </div>
    `).join('');
}

function toggleWorkersDropdown() {
    const content = document.getElementById('workersDropdownContent');
    content.classList.toggle('show');
    if (content.classList.contains('show')) {
        loadWorkers();
    }
}

async function stopWorker(workerId) {
    if (!confirm('Stop this worker?')) return;
    try {
        await fetch(`${EXECUTOR_URL}/stop-worker`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ worker_id: workerId })
        });
        loadWorkers();
    } catch (e) {
        console.error('Failed to stop worker:', e);
    }
}

async function viewWorker(workerId) {
    try {
        const resp = await fetch(`${EXECUTOR_URL}/worker-output?id=${workerId}&lines=100`);
        const data = await resp.json();
        if (data.success) {
            document.getElementById('cliOutput').textContent = data.output || 'No output yet';
            const panel = document.getElementById('bottomPanel');
            if (!panel.classList.contains('expanded')) {
                togglePanel();
            }
        }
    } catch (e) {
        console.error('Failed to get worker output:', e);
    }
}

async function spawnParallelWorker(taskId, agentType = 'general') {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;

    const workingDir = task.linkedFiles?.[0]?.path?.replace(/\/[^\/]+$/, '') || null;

    try {
        const resp = await fetch(`${EXECUTOR_URL}/spawn-worker`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: task.id,
                text: task.text,
                agent: task.agent,
                agent_type: agentType,
                working_dir: workingDir
            })
        });
        const data = await resp.json();
        if (data.success) {
            task.workerId = data.worker_id;
            task.status = 'executing';
            task.startedAt = new Date().toISOString();
            addWorkLog(task.id, `Spawned ${agentType} worker: ${data.worker_id}`, 'started');
            save();
            renderAll();
            loadWorkers();
        }
    } catch (e) {
        console.error('Failed to spawn worker:', e);
    }
}

const progressTimers = {};

function startProgressTimer(taskId) {
    if (progressTimers[taskId]) clearInterval(progressTimers[taskId]);
    progressTimers[taskId] = setInterval(() => {
        const task = tasks.find(t => t.id === taskId);
        if (!task || task.status !== 'executing') {
            clearInterval(progressTimers[taskId]);
            delete progressTimers[taskId];
            return;
        }
        if (currentView === 'timeline') renderTimeline();
    }, 5000);
}

function getTaskProgress(task) {
    if (!task.startedAt) return { percent: 0, eta: 'Starting...' };
    const started = new Date(task.startedAt).getTime();
    const now = Date.now();
    const elapsed = now - started;
    const estimatedMs = (task.estimatedMinutes || 5) * 60 * 1000;
    let percent = Math.min(95, Math.round((elapsed / estimatedMs) * 100));
    const remaining = Math.max(0, estimatedMs - elapsed);
    let eta;
    if (remaining <= 0) {
        eta = 'Almost done...';
        percent = 95;
    } else if (remaining < 60000) {
        eta = `${Math.round(remaining/1000)}s left`;
    } else {
        eta = `${Math.round(remaining/60000)}m left`;
    }
    return { percent, eta };
}

function getElapsedTime(startedAt) {
    if (!startedAt) return 'just now';
    const started = new Date(startedAt).getTime();
    const elapsed = Date.now() - started;
    if (elapsed < 60000) return `${Math.round(elapsed/1000)}s`;
    if (elapsed < 3600000) return `${Math.round(elapsed/60000)}m`;
    return `${Math.round(elapsed/3600000)}h ${Math.round((elapsed % 3600000)/60000)}m`;
}

function playTask(id) {
    quickExecute(id);
}

function stopTask(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    task.status = 'todo';
    addWorkLog(task.id, 'Task stopped by user', 'stopped');
    save(); renderAll();
}

function aiReviewTask(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    task.status = 'ai-review';
    addWorkLog(task.id, 'Sent to AI for review', 'ai-review');
    save(); renderAll();
}

async function humanReviewTask(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    task.status = 'human-review';
    addWorkLog(task.id, 'AI approved, awaiting human review', 'human-review');
    if (executorOnline) {
        try {
            const date = new Date().toISOString().split('T')[0];
            const filename = `agents/memory/assistant/reviews/${date}-${task.id}.md`;
            const agentMap = { bml: 'bitcoinml', ene: 'energyscout', rea: 'realestate', ana: 'analytics', ass: 'assistant' };
            const agentName = agentMap[task.agent] || task.agent;
            const content = `# Review: ${task.text}\n\n## Task Details\n- **Agent:** ${agentName}\n- **Status:** Awaiting Human Review\n- **Started:** ${task.startedAt || 'N/A'}\n- **Duration:** ${task.startedAt ? Math.round((Date.now() - new Date(task.startedAt).getTime()) / 60000) + ' minutes' : 'N/A'}\n\n## AI Summary\nThe task has been processed by the ${agentName} agent.\n\n${task.workLog?.map(w => '- ' + w.content).join('\n') || '- No detailed log available'}\n\n## Notes\n${task.notes || 'No notes'}\n\n---\n*Generated: ${new Date().toISOString()}*`;
            await fetch(`${EXECUTOR_URL}/save-to-vault`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename, content })
            });
            task.reviewFile = filename;
        } catch (e) { console.error('Review file failed:', e); }
    }
    save(); renderAll();
}

async function completeTask(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    task.status = 'done';
    task.completedAt = new Date().toISOString();
    addWorkLog(task.id, 'Human approved - archived', 'completed');
    if (executorOnline) {
        try {
            const filename = `agents/memory/assistant/completed/${task.id}.md`;
            const content = `# ${task.text}\n\n**Agent:** ${task.agent}\n**Completed:** ${task.completedAt}\n\n## Work Log\n${task.workLog?.map(w => `- ${w.timestamp}: ${w.content}`).join('\n') || 'No log'}\n\n## Notes\n${task.notes || 'None'}`;
            await fetch(`${EXECUTOR_URL}/save-to-vault`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename, content })
            });
        } catch (e) { console.error('Archive failed:', e); }
    }
    save(); renderAll();
}

async function runCronJob(jobName) {
    if (!executorOnline) { alert('Start executor first'); return; }
    if (!confirm(`Run "${jobName}" now?`)) return;
    try {
        const resp = await fetch(`${EXECUTOR_URL}/run-job`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_name: jobName })
        });
        const data = await resp.json();
        alert(data.success ? `Job "${jobName}" started` : `Error: ${data.error}`);
    } catch (e) { alert('Error: ' + e.message); }
}

function startExecutor() {
    if (executorOnline) return;
    alert('Run this in terminal:\n\ncd ~/Vaults/openclaw/bridge/kanban && python executor.py');
}

function openDetailModal(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    const agentMap = { bml: 'bitcoinml', ene: 'energyscout', rea: 'realestate', ana: 'assistant', ass: 'assistant' };
    const chatBot = agentMap[task.agent] || 'assistant';
    document.getElementById('chatBot').value = chatBot;
    updateChatSidebar();
    const taskInfo = `📋 **Task:** ${task.text}\n**Status:** ${task.status.toUpperCase()} | **Agent:** ${task.agent.toUpperCase()} | **Priority:** Q${task.quadrant?.charAt(1) || '2'}\n\n💬 Add any notes or updates for this task:`;
    chatHistory.push({
        bot: chatBot,
        type: 'bot',
        content: taskInfo,
        timestamp: new Date().toISOString()
    });
    localStorage.setItem('chat-history', JSON.stringify(chatHistory));
    renderChat();
    if (panelCollapsed) togglePanel();
    document.getElementById('detail-title').textContent = task.text;
    document.getElementById('detail-status-select').value = task.status === 'executing' ? 'progress' : task.status;
    document.getElementById('detail-agent-select').value = task.agent;
    document.getElementById('detail-quadrant-select').value = task.quadrant || 'q2';
    document.getElementById('detail-text').textContent = task.text;
    const tags = task.tags || [];
    const tagsHTML = `
        <div style="margin-bottom:8px;">
            ${tags.map(t => `<span style="background:#30363d;padding:3px 8px;border-radius:4px;font-size:11px;margin-right:4px;">#${t}</span>`).join('')}
            <button onclick="addTagPrompt('${task.id}')" style="background:transparent;border:1px dashed #30363d;color:#9eaab6;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:11px;">+ tag</button>
        </div>
    `;
    const artifacts = task.artifacts || [];
    const obsidianFile = `bridge/kanban/tasks/${task.id}`;
    const obsidianPath = `obsidian://open?vault=openclaw&file=${encodeURIComponent(obsidianFile)}`;
    document.getElementById('detail-artifacts').innerHTML = tagsHTML + `
        <button onclick="openInObsidian('${task.id}')" class="artifact-link" style="cursor:pointer;border:none;">📓 Open in Obsidian</button>
        <button onclick="saveToObsidian('${task.id}')" class="artifact-link" style="cursor:pointer;border:none;">💾 Save to Vault</button>
        <button onclick="addCheckpoint('${task.id}')" class="artifact-link" style="cursor:pointer;border:none;background:#1a3a1a;border:1px solid #238636;">📍 Checkpoint</button>
        ${artifacts.map(a => `<a href="${a.url}" target="_blank" class="artifact-link">📎 ${a.name}</a>`).join('')}
    `;
    const workLog = task.workLog || [];
    // Build resumption context header if available
    let resumptionHeader = '';
    if (task.lastCheckpoint) {
        const cp = task.lastCheckpoint;
        resumptionHeader = `
            <div class="resumption-context" style="background:#1a3a1a;border:1px solid #238636;border-radius:8px;padding:12px;margin-bottom:12px;">
                <div style="font-weight:600;color:#3fb950;margin-bottom:8px;">🔄 Resumption Context (${cp.percentComplete || 0}% complete)</div>
                <div style="color:#e6edf3;margin-bottom:6px;"><strong>Last checkpoint:</strong> ${cp.timestamp}</div>
                <div style="color:#e6edf3;margin-bottom:6px;"><strong>Where we left off:</strong> ${cp.summary || 'No summary'}</div>
                ${cp.nextSteps ? `<div style="color:#f0883e;"><strong>Next steps:</strong> ${cp.nextSteps}</div>` : ''}
            </div>
        `;
    }
    document.getElementById('detail-worklog').innerHTML = resumptionHeader + (workLog.length
        ? workLog.map(log => `
            <div class="work-log-entry ${log.type || ''}" style="border-left:3px solid ${log.type === 'checkpoint' ? '#238636' : log.type === 'blocker' ? '#da3633' : log.type === 'completed' ? '#3fb950' : '#30363d'};">
                <div class="timestamp">${log.timestamp} ${log.percentComplete !== undefined ? `<span style="color:#3fb950;">(${log.percentComplete}%)</span>` : ''}</div>
                <div class="content">${log.content}</div>
                ${log.filesModified ? `<div style="font-size:11px;color:#9eaab6;margin-top:4px;">📁 Files: ${log.filesModified.join(', ')}</div>` : ''}
                ${log.checkpoint ? `<div style="font-size:11px;color:#238636;margin-top:4px;">📍 Checkpoint: ${log.checkpoint}</div>` : ''}
                ${log.nextSteps ? `<div style="font-size:11px;color:#f0883e;margin-top:4px;">➡️ Next: ${log.nextSteps}</div>` : ''}
            </div>
        `).join('')
        : `<div style="color:#9eaab6;">No work logged yet.</div>
           ${task.notes ? `<div class="work-log-entry"><div class="content">${task.notes}</div></div>` : ''}`);
    document.getElementById('detailModal').dataset.taskId = id;
    renderLinkedFiles(id);
    document.getElementById('detailModal').classList.add('show');
    setTimeout(() => document.getElementById('chatInput').focus(), 100);
}

function quickUpdateTask(field, value) {
    const taskId = document.getElementById('detailModal').dataset.taskId;
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    task[field] = value;
    addWorkLog(taskId, `Changed ${field} to ${value}`, 'update');
    save();
    renderAll();
}

function moveToBacklog() {
    const taskId = document.getElementById('detailModal').dataset.taskId;
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    task.status = 'todo';
    task.scheduled = false;
    delete task.startedAt;
    addWorkLog(taskId, 'Moved back to Backlog', 'backlog');
    save();
    closeDetailModal();
    renderAll();
}

function deleteTaskFromDetail() {
    const taskId = document.getElementById('detailModal').dataset.taskId;
    if (confirm('Delete this task permanently?')) {
        tasks = tasks.filter(t => t.id !== taskId);
        save();
        closeDetailModal();
        renderAll();
    }
}

function archiveTask() {
    const taskId = document.getElementById('detailModal').dataset.taskId;
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    task.status = 'done';
    if (!task.tags) task.tags = [];
    task.tags.push('archived');
    addWorkLog(taskId, 'Task archived', 'archive');
    save();
    closeDetailModal();
    renderAll();
}

function chatAboutTask(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    closeDetailModal();
    document.getElementById('chatInput').value = `About task "${task.text}": `;
    document.getElementById('chatInput').focus();
}

function addTagPrompt(id) {
    const tag = prompt('Enter tag name:');
    if (!tag) return;
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    if (!task.tags) task.tags = [];
    task.tags.push(tag.toLowerCase().replace(/[^a-z0-9-]/g, ''));
    addWorkLog(id, `Added tag: #${tag}`, 'tag');
    save();
    openDetailModal(id);
}

function generateTaskMarkdown(task) {
    const agentNames = { bml: 'Bitcoin ML CEO', ene: 'EnergyScout CEO', rea: 'Real Estate', ana: 'Analytics', ass: 'Assistant' };
    const quadrantNames = { q1: 'Urgent + Important', q2: 'Important (Strategic)', q3: 'Urgent (Delegate)', q4: 'Low Priority' };
    const statusEmoji = { todo: '📋', progress: '🔄', blocked: '🚫', done: '✅' };
    const createdDate = task.created ? new Date(task.created).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }) : 'Unknown';
    const updatedDate = new Date().toISOString();

    return `---
id: ${task.id}
agent: ${task.agent}
agent_name: ${agentNames[task.agent] || task.agent}
status: ${task.status}
quadrant: ${task.quadrant}
tags: [${(task.tags || []).join(', ')}]
created: ${task.created || updatedDate}
updated: ${updatedDate}
delegated_by: ${task.delegatedBy || 'dashboard'}
vault_path: bridge/kanban/tasks/${task.id}.md
---

# ${statusEmoji[task.status] || '📋'} ${task.text}

## Overview
| Field | Value |
|-------|-------|
| **Status** | ${task.status.toUpperCase()} |
| **Agent** | ${agentNames[task.agent] || task.agent} |
| **Priority** | ${quadrantNames[task.quadrant] || task.quadrant} |
| **Created** | ${createdDate} |
| **Delegated By** | ${task.delegatedBy || 'Dashboard'} |

## Description & Notes
${task.notes || '_No notes yet. Add context, requirements, or acceptance criteria here._'}

## Work Log
${(task.workLog || []).length > 0
    ? (task.workLog || []).map(log => `### ${log.timestamp}\n**Type:** ${log.type || 'note'}\n\n${log.content}\n`).join('\n---\n\n')
    : '_No work logged yet._'}

## Artifacts & Links
${(task.artifacts || []).length > 0
    ? (task.artifacts || []).map(a => `- [${a.name}](${a.url})`).join('\n')
    : '_No artifacts attached._'}

## Related Files
${(task.relatedFiles || []).length > 0
    ? (task.relatedFiles || []).map(f => `- [[${f}]]`).join('\n')
    : '_No related files linked._'}

---
*Last synced from [OpenClaw Dashboard](file://${window.location.pathname}) at ${new Date().toLocaleString()}*
`;
}

async function saveToObsidian(id, silent = false) {
    const task = tasks.find(t => t.id === id);
    if (!task) return false;

    const md = generateTaskMarkdown(task);
    const filename = `bridge/kanban/tasks/${task.id}.md`;

    if (executorOnline) {
        try {
            const resp = await fetch(`${EXECUTOR_URL}/save-to-vault`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename, content: md })
            });
            const data = await resp.json();
            if (data.success) {
                task.vaultPath = filename;
                if (!silent) {
                    addWorkLog(id, 'Saved to Obsidian vault', 'save');
                    alert('Task saved to Obsidian!');
                }
                save();
                return true;
            } else {
                if (!silent) alert('Error: ' + data.error);
                return false;
            }
        } catch (e) {
            if (!silent) alert('Error saving: ' + e.message);
            return false;
        }
    } else {
        navigator.clipboard.writeText(md);
        if (!silent) alert('Markdown copied to clipboard. Paste into Obsidian.');
        return false;
    }
}

async function openInObsidian(id) {
    // Save first to ensure file exists, then open
    const saved = await saveToObsidian(id, true);
    const obsidianFile = `bridge/kanban/tasks/${id}`;
    const obsidianPath = `obsidian://open?vault=openclaw&file=${encodeURIComponent(obsidianFile)}`;
    window.location.href = obsidianPath;
}

function addRelatedFile(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    const filePath = prompt('Enter file path relative to vault (e.g., agents/memory/assistant/notes/idea.md):');
    if (!filePath) return;
    task.relatedFiles = task.relatedFiles || [];
    if (!task.relatedFiles.includes(filePath)) {
        task.relatedFiles.push(filePath);
        addWorkLog(id, `Linked file: ${filePath}`, 'link');
        save();
        saveToObsidian(id, true);  // Auto-update Obsidian file
        openDetailModal(id);  // Refresh modal
    }
}

function addArtifact(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    const name = prompt('Artifact name:');
    if (!name) return;
    const url = prompt('Artifact URL:');
    if (!url) return;
    task.artifacts = task.artifacts || [];
    task.artifacts.push({ name, url });
    addWorkLog(id, `Added artifact: ${name}`, 'artifact');
    save();
    saveToObsidian(id, true);
    openDetailModal(id);
}

async function addCheckpoint(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;

    const summary = prompt('Checkpoint summary (where are we now?):');
    if (!summary) return;

    const nextSteps = prompt('Next steps (what should happen next?):');
    const percentStr = prompt('Percent complete (0-100):', '50');
    const percent = parseInt(percentStr) || 0;

    // Add to work log
    const logEntry = {
        timestamp: new Date().toLocaleString(),
        content: summary,
        type: 'checkpoint',
        checkpoint: summary,
        nextSteps: nextSteps || '',
        percentComplete: percent
    };
    task.workLog = task.workLog || [];
    task.workLog.push(logEntry);

    // Update last checkpoint for easy resumption
    task.lastCheckpoint = {
        timestamp: logEntry.timestamp,
        summary: summary,
        nextSteps: nextSteps || '',
        percentComplete: percent
    };

    save();

    // Sync to server
    if (executorOnline) {
        try {
            await fetch(`${EXECUTOR_URL}/update-worklog`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: id,
                    content: summary,
                    type: 'checkpoint',
                    checkpoint: summary,
                    next_steps: nextSteps,
                    percent_complete: percent
                })
            });
        } catch (e) {
            console.error('Failed to sync checkpoint:', e);
        }
    }

    saveToObsidian(id, true);
    openDetailModal(id);
}

function closeDetailModal() {
    document.getElementById('detailModal').classList.remove('show');
}

function openEditFromDetail() {
    const id = document.getElementById('detailModal').dataset.taskId;
    closeDetailModal();
    openEditModal(id);
}

function addWorkLog(taskId, content, type = '') {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    if (!task.workLog) task.workLog = [];
    task.workLog.push({
        timestamp: new Date().toLocaleString(),
        content: content,
        type: type
    });
    save();
}

function addArtifact(taskId, name, url) {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    if (!task.artifacts) task.artifacts = [];
    task.artifacts.push({ name, url });
    save();
}

// File Linking Functions
async function linkFileToTask() {
    const taskId = document.getElementById('detailModal').dataset.taskId;
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;

    try {
        // Use File System Access API (Chrome/Edge)
        if (window.showOpenFilePicker) {
            const [fileHandle] = await window.showOpenFilePicker({
                multiple: false
            });
            const file = await fileHandle.getFile();
            // Get full path by resolving against known directories
            const path = await getFilePath(fileHandle, file.name);
            addLinkedFile(taskId, path, 'file');
        } else {
            // Fallback for other browsers
            manualLinkPath();
        }
    } catch (err) {
        if (err.name !== 'AbortError') {
            console.error('File picker error:', err);
            manualLinkPath();
        }
    }
}

async function linkFolderToTask() {
    const taskId = document.getElementById('detailModal').dataset.taskId;
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;

    try {
        if (window.showDirectoryPicker) {
            const dirHandle = await window.showDirectoryPicker();
            const path = await getFolderPath(dirHandle);
            addLinkedFile(taskId, path, 'folder');
        } else {
            manualLinkPath();
        }
    } catch (err) {
        if (err.name !== 'AbortError') {
            console.error('Folder picker error:', err);
            manualLinkPath();
        }
    }
}

async function getFilePath(fileHandle, fileName) {
    // Try to get path from handle name and common directories
    const knownBases = [
        '/Users/macmini/Vaults/openclaw',
        '/Users/macmini/bitcoinml',
        '/Users/macmini/energyscout',
        '/Users/macmini/realestate',
        '/Users/macmini'
    ];
    // File System Access API doesn't expose full path for security
    // Return the file name and let user confirm/edit
    return fileName;
}

async function getFolderPath(dirHandle) {
    return dirHandle.name;
}

function manualLinkPath() {
    const taskId = document.getElementById('detailModal').dataset.taskId;
    const path = prompt('Enter file or folder path:\n\nExample: /Users/macmini/Vaults/openclaw/some-file.py');
    if (path && path.trim()) {
        const isFolder = !path.includes('.') || path.endsWith('/');
        addLinkedFile(taskId, path.trim(), isFolder ? 'folder' : 'file');
    }
}

function addLinkedFile(taskId, path, type = 'file') {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    if (!task.linkedFiles) task.linkedFiles = [];

    // Avoid duplicates
    if (task.linkedFiles.some(f => f.path === path)) {
        alert('This path is already linked.');
        return;
    }

    task.linkedFiles.push({
        path: path,
        type: type,
        linkedAt: new Date().toISOString()
    });
    save();
    renderLinkedFiles(taskId);
}

function removeLinkedFile(taskId, path) {
    const task = tasks.find(t => t.id === taskId);
    if (!task || !task.linkedFiles) return;
    task.linkedFiles = task.linkedFiles.filter(f => f.path !== path);
    save();
    renderLinkedFiles(taskId);
}

function renderLinkedFiles(taskId) {
    const task = tasks.find(t => t.id === taskId);
    const container = document.getElementById('detail-linked-files');
    if (!container) return;

    if (!task?.linkedFiles?.length) {
        container.innerHTML = '<span style="color:#6e7681;font-size:12px;">No files linked. Click to add.</span>';
        return;
    }

    container.innerHTML = task.linkedFiles.map(f => `
        <div class="linked-file" style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:#21262d;border-radius:6px;margin-bottom:6px;font-family:'SF Mono',monospace;font-size:12px;">
            <span style="color:${f.type === 'folder' ? '#f0883e' : '#58a6ff'};">${f.type === 'folder' ? '📁' : '📄'}</span>
            <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#e6edf3;" title="${f.path}">${f.path}</span>
            <button onclick="copyLinkedPath('${f.path.replace(/'/g, "\\'")}')" style="background:#30363d;border:none;color:#9eaab6;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:10px;" title="Copy path">copy</button>
            <button onclick="openInTerminal('${f.path.replace(/'/g, "\\'")}')" style="background:#238636;border:none;color:#fff;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:10px;" title="Open in terminal">cd</button>
            <button onclick="removeLinkedFile('${taskId}', '${f.path.replace(/'/g, "\\'")}')" style="background:#da3633;border:none;color:#fff;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;" title="Remove">×</button>
        </div>
    `).join('');
}

function copyLinkedPath(path) {
    navigator.clipboard.writeText(path).then(() => {
        // Brief visual feedback
        const btn = event.target;
        const original = btn.textContent;
        btn.textContent = '✓';
        btn.style.background = '#238636';
        setTimeout(() => {
            btn.textContent = original;
            btn.style.background = '#30363d';
        }, 1000);
    });
}

function openInTerminal(path) {
    // Set the path in the terminal and send cd command
    const isFile = path.includes('.') && !path.endsWith('/');
    const dirPath = isFile ? path.substring(0, path.lastIndexOf('/')) : path;

    // Update the terminal path display
    document.getElementById('cliPath').textContent = dirPath;
    document.getElementById('cliRepoSelect').value = '';

    // Send cd command to terminal
    const input = document.getElementById('cliInput');
    input.value = `cd "${dirPath}"`;
    sendCliCommand();

    // Expand terminal panel if not already
    const panel = document.getElementById('bottomPanel');
    if (!panel.classList.contains('expanded')) {
        togglePanel();
    }
}

function openAddModal() {
    document.getElementById('modal-title').textContent = 'Add Task';
    document.getElementById('edit-id').value = '';
    document.getElementById('edit-text').value = '';
    document.getElementById('edit-agent').value = 'bml';
    document.getElementById('edit-quadrant').value = 'q2';
    document.getElementById('edit-status').value = 'todo';
    document.getElementById('edit-notes').value = '';
    document.getElementById('delete-btn').style.display = 'none';
    document.getElementById('run-btn').style.display = 'none';
    document.getElementById('outbox-preview').style.display = 'none';
    document.getElementById('editModal').classList.add('show');
}

async function openEditModal(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    document.getElementById('modal-title').textContent = 'Edit Task';
    document.getElementById('edit-id').value = task.id;
    document.getElementById('edit-text').value = task.text;
    document.getElementById('edit-agent').value = task.agent;
    document.getElementById('edit-quadrant').value = task.quadrant;
    document.getElementById('edit-status').value = task.status;
    document.getElementById('edit-notes').value = task.notes || '';
    document.getElementById('edit-agent-type').value = task.agentType || 'general';
    document.getElementById('edit-parallel').checked = task.parallel || false;
    document.getElementById('delete-btn').style.display = 'block';
    document.getElementById('run-btn').style.display = executorOnline ? 'block' : 'none';
    const isRecurring = task.recurring || false;
    document.getElementById('edit-recurring').checked = isRecurring;
    document.getElementById('schedule-options').style.display = isRecurring ? 'block' : 'none';
    if (task.schedule) {
        document.getElementById('edit-schedule-time').value = task.schedule.time || '09:00';
        document.getElementById('edit-schedule-timeout').value = task.schedule.timeout || 300;
        document.querySelectorAll('input[name="schedule-day"]').forEach(cb => {
            cb.checked = task.schedule.days?.includes(cb.value) || false;
        });
    } else {
        document.getElementById('edit-schedule-time').value = '09:00';
        document.getElementById('edit-schedule-timeout').value = 300;
        document.querySelectorAll('input[name="schedule-day"]').forEach(cb => cb.checked = false);
    }
    if (executorOnline) {
        try {
            const resp = await fetch(`${EXECUTOR_URL}/outbox?bot=${task.agent}`);
            const data = await resp.json();
            if (data.content) {
                document.getElementById('outbox-preview').textContent = data.content;
                document.getElementById('outbox-preview').style.display = 'block';
            }
        } catch {}
    }
    document.getElementById('editModal').classList.add('show');
}

function closeModal() {
    document.getElementById('editModal').classList.remove('show');
    document.getElementById('outbox-preview').style.display = 'none';
}

async function executeTask() {
    const id = document.getElementById('edit-id').value;
    if (id) {
        const agentType = document.getElementById('edit-agent-type').value || 'general';
        const parallel = document.getElementById('edit-parallel').checked || false;
        await quickExecute(id, { agentType, parallel });
        closeModal();
    }
}

function toggleScheduleOptions() {
    const enabled = document.getElementById('edit-recurring').checked;
    document.getElementById('schedule-options').style.display = enabled ? 'block' : 'none';
}

async function saveCronJob(task) {
    const time = document.getElementById('edit-schedule-time').value || '09:00';
    const timeout = parseInt(document.getElementById('edit-schedule-timeout').value) || 300;
    const dayCheckboxes = document.querySelectorAll('input[name="schedule-day"]:checked');
    const days = Array.from(dayCheckboxes).map(cb => cb.value);
    const agentMap = { bml: 'bitcoinml', ene: 'energyscout', rea: 'realestate', ana: 'analytics', ass: 'assistant' };
    const job = {
        name: `task-${task.id}`,
        schedule: time,
        bot: agentMap[task.agent] || 'assistant',
        description: task.text.substring(0, 80),
        prompt: task.text + (task.notes ? `\n\nNotes: ${task.notes}` : ''),
        timeout: timeout
    };
    if (days.length > 0 && days.length < 7) {
        job.weekdays = days;
    }
    try {
        await fetch(`${EXECUTOR_URL}/save-cron-job`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job })
        });
        task.cronJob = job.name;
        task.schedule = { time, days, timeout };
    } catch (e) {
        console.error('Failed to save cron job:', e);
    }
}

async function deleteCronJob(jobName) {
    try {
        await fetch(`${EXECUTOR_URL}/delete-cron-job`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: jobName })
        });
    } catch (e) {
        console.error('Failed to delete cron job:', e);
    }
}

async function saveTask() {
    const id = document.getElementById('edit-id').value;
    const text = document.getElementById('edit-text').value.trim();
    if (!text) return;
    const isRecurring = document.getElementById('edit-recurring').checked;
    const agentType = document.getElementById('edit-agent-type').value || 'general';
    const parallel = document.getElementById('edit-parallel').checked || false;
    let task;
    if (id) {
        task = tasks.find(t => t.id === id);
        if (task) {
            task.text = text;
            task.agent = document.getElementById('edit-agent').value;
            task.quadrant = document.getElementById('edit-quadrant').value;
            task.status = document.getElementById('edit-status').value;
            task.notes = document.getElementById('edit-notes').value;
            task.agentType = agentType;
            task.parallel = parallel;
            task.recurring = isRecurring;
            if (isRecurring) {
                await saveCronJob(task);
            } else if (task.cronJob) {
                await deleteCronJob(task.cronJob);
                delete task.cronJob;
                delete task.schedule;
            }
        }
    } else {
        task = {
            id: 'task-' + Date.now(),
            text, agent: document.getElementById('edit-agent').value,
            quadrant: document.getElementById('edit-quadrant').value,
            status: document.getElementById('edit-status').value,
            notes: '', scheduled: false,
            agentType: agentType,
            parallel: parallel,
            recurring: isRecurring,
            created: new Date().toISOString(),
            tags: [],
            workLog: [],
            artifacts: []
        };
        tasks.push(task);
        if (isRecurring) {
            await saveCronJob(task);
        }
    }
    closeModal(); save(); renderAll();
    // Auto-save to Obsidian for workflow documentation
    if (task && executorOnline) {
        saveToObsidian(task.id, true);
    }
}

function deleteTask() {
    const id = document.getElementById('edit-id').value;
    if (confirm('Delete this task?')) {
        tasks = tasks.filter(t => t.id !== id);
        closeModal(); save(); renderAll();
    }
}

function save() { localStorage.setItem('dashboard-tasks', JSON.stringify(tasks)); }

async function syncTasksFromServer() {
    // Merge server-created tasks (from agent delegations) with local tasks
    if (!executorOnline) return;
    try {
        const resp = await fetch(`${EXECUTOR_URL}/tasks`);
        const data = await resp.json();
        const serverTasks = data.tasks || [];

        // Find tasks that exist on server but not locally (by ID)
        const localIds = new Set(tasks.map(t => t.id));
        const newTasks = serverTasks.filter(t => !localIds.has(t.id));

        if (newTasks.length > 0) {
            tasks = [...tasks, ...newTasks];
            save();
            renderAll();
            console.log(`Synced ${newTasks.length} new tasks from server`);

            // Auto-save new tasks to Obsidian for workflow documentation
            for (const task of newTasks) {
                await saveToObsidian(task.id, true);
                console.log(`Auto-saved task ${task.id} to Obsidian`);
            }
        }

        // Also update server with any local-only tasks
        const serverIds = new Set(serverTasks.map(t => t.id));
        const localOnlyTasks = tasks.filter(t => !serverIds.has(t.id));
        if (localOnlyTasks.length > 0 || tasks.length !== serverTasks.length) {
            await fetch(`${EXECUTOR_URL}/save-tasks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tasks })
            });
        }
    } catch (e) {
        console.log('Task sync failed:', e);
    }
}

async function syncFromGitHub() {
    const GITHUB_BASE = 'https://raw.githubusercontent.com/mobiusframeworks/openclaw-kanban/main/backlogs';
    const files = { bml: 'bml-ceo.md', ene: 'energyscout-ceo.md', rea: 'realestate-ceo.md', ana: 'analytics.md', ass: 'assistant.md' };
    for (const [agent, file] of Object.entries(files)) {
        try {
            const resp = await fetch(`${GITHUB_BASE}/${file}`);
            if (!resp.ok) continue;
            const content = await resp.text();
            let status = 'todo';
            content.split('\n').forEach(line => {
                if (line.includes('Status:')) {
                    const ll = line.toLowerCase();
                    if (ll.includes('done') || ll.includes('complete')) status = 'done';
                    else if (ll.includes('progress')) status = 'progress';
                    else if (ll.includes('blocked')) status = 'blocked';
                    else status = 'todo';
                }
                let text = null;
                if (line.startsWith('### ')) text = line.replace('###', '').replace(/^\d+\.\s*/, '').trim();
                else if (line.trim().startsWith('- [x]')) { text = line.replace('- [x]', '').trim(); status = 'done'; }
                else if (line.trim().startsWith('- [ ]')) text = line.replace('- [ ]', '').trim();
                if (text && !tasks.some(t => t.text === text)) {
                    let q = 'q2';
                    const ll = text.toLowerCase();
                    if (ll.includes('urgent') || ll.includes('asap')) q = 'q1';
                    else if (ll.includes('research') || ll.includes('plan')) q = 'q2';
                    else if (ll.includes('email') || ll.includes('call')) q = 'q3';
                    else if (ll.includes('maybe') || ll.includes('optional')) q = 'q4';
                    tasks.push({
                        id: 'gh-' + Date.now() + Math.random(),
                        text, agent, quadrant: q, status,
                        scheduled: false, notes: '',
                        created: new Date().toISOString(),
                        tags: [],
                        workLog: [{ timestamp: new Date().toLocaleString(), content: 'Imported from GitHub', type: 'import' }],
                        artifacts: []
                    });
                }
            });
        } catch {}
    }
    save(); renderAll();
    alert(`Synced. Total: ${tasks.length} tasks`);
}

let panelCollapsed = true;
let chatHistory = JSON.parse(localStorage.getItem('chat-history') || '[]');
let panelExpanded = false;
let panelMaximized = false;
let cliCollapsed = false;

function togglePanel() {
    panelCollapsed = !panelCollapsed;
    panelExpanded = false;
    panelMaximized = false;
    const panel = document.getElementById('bottomPanel');
    panel.classList.remove('expanded', 'maximized');
    panel.classList.toggle('collapsed', panelCollapsed);
    if (panelCollapsed) {
        panel.style.height = '40px';
        document.querySelector('.panel-content').style.display = 'none';
    } else {
        panel.style.height = '280px';
        document.querySelector('.panel-content').style.display = 'flex';
    }
    document.querySelector('.panel-toggle').textContent = panelCollapsed ? '▲ Chat' : '▼ Chat';
    updateMainHeight();
}

function expandPanel() {
    panelExpanded = !panelExpanded;
    panelCollapsed = false;
    panelMaximized = false;
    const panel = document.getElementById('bottomPanel');
    panel.classList.remove('expanded', 'maximized');
    panel.classList.toggle('expanded', panelExpanded);
    document.getElementById('expandBtn').textContent = panelExpanded ? '⤡ Normal' : '⤢ Expand';
    updateMainHeight();
}

function maximizePanel() {
    panelMaximized = !panelMaximized;
    panelCollapsed = false;
    panelExpanded = false;
    const panel = document.getElementById('bottomPanel');
    panel.classList.remove('collapsed', 'expanded');
    panel.classList.toggle('maximized', panelMaximized);
    document.getElementById('maximizeBtn').textContent = panelMaximized ? '⤡ Restore' : '⛶ Max';
    document.getElementById('expandBtn').textContent = '⤢ Expand';
    updateMainHeight();
}

let cliFullscreen = false;
let cliPanelVisible = false;

function toggleCliPanel() {
    const cliPanel = document.getElementById('cliPanel');
    cliPanelVisible = !cliPanelVisible;
    cliPanel.classList.toggle('show', cliPanelVisible);
    document.getElementById('cliToggleBtn').style.background = cliPanelVisible ? '#238636' : '';
    if (cliPanelVisible && cliCollapsed) {
        cliCollapsed = false;
        cliPanel.classList.remove('collapsed');
        document.getElementById('cliCollapseBtn').textContent = '◀';
    }
}

function toggleCliCollapse() {
    const cliPanel = document.getElementById('cliPanel');
    if (cliFullscreen) {
        cliFullscreen = false;
        cliPanel.classList.remove('fullscreen');
        document.getElementById('cliFullscreenBtn').textContent = '⛶';
    }
    cliCollapsed = !cliCollapsed;
    cliPanel.classList.toggle('collapsed', cliCollapsed);
    document.getElementById('cliCollapseBtn').textContent = cliCollapsed ? '▶' : '◀';
}

function toggleCliFullscreen() {
    const cliPanel = document.getElementById('cliPanel');
    if (cliCollapsed) {
        cliCollapsed = false;
        cliPanel.classList.remove('collapsed');
        document.getElementById('cliCollapseBtn').textContent = '◀';
    }
    cliFullscreen = !cliFullscreen;
    cliPanel.classList.toggle('fullscreen', cliFullscreen);
    document.getElementById('cliFullscreenBtn').textContent = cliFullscreen ? '⤡' : '⛶';
}

function startCliResize(e) {
    e.preventDefault();
    const cliPanel = document.getElementById('cliPanel');
    const startX = e.clientX;
    const startWidth = cliPanel.offsetWidth;
    cliPanel.style.transition = 'none';
    function onMove(e) {
        const newWidth = Math.max(200, Math.min(window.innerWidth - 200, startWidth + (e.clientX - startX)));
        cliPanel.style.width = newWidth + 'px';
        cliPanel.classList.remove('collapsed', 'fullscreen');
        cliCollapsed = false;
        cliFullscreen = false;
        document.getElementById('cliCollapseBtn').textContent = '◀';
        document.getElementById('cliFullscreenBtn').textContent = '⛶';
    }
    function onUp() {
        cliPanel.style.transition = '';
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
}

function updateMainHeight() {
    const panel = document.getElementById('bottomPanel');
    const height = panel.offsetHeight;
    document.querySelector('.main-content').style.height = `calc(100vh - ${height + 56}px)`;
}

window.addEventListener('resize', updateMainHeight);

function startResize(e) {
    e.preventDefault();
    const panel = document.getElementById('bottomPanel');
    const startY = e.clientY;
    const startHeight = panel.offsetHeight;
    function onMove(e) {
        const newHeight = Math.max(100, Math.min(window.innerHeight - 100, startHeight - (e.clientY - startY)));
        panel.style.height = newHeight + 'px';
        panel.classList.remove('collapsed', 'expanded', 'maximized');
        panelExpanded = false;
        panelMaximized = false;
        document.getElementById('expandBtn').textContent = '⤢ Expand';
        document.getElementById('maximizeBtn').textContent = '⛶ Max';
        updateMainHeight();
    }
    function onUp() {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
}

let linkedSessions = [];
let agentActivityCache = {};
let currentCliAgent = null;
let cliRefreshInterval = null;

async function loadAgentActivity() {
    if (!executorOnline) return;
    try {
        const resp = await fetch(`${EXECUTOR_URL}/agent-activity`);
        const data = await resp.json();
        agentActivityCache = data.agents || {};
        // Update terminal previews for executing tasks
        updateTerminalPreviews();
    } catch (e) {
        console.log('Could not load agent activity:', e);
    }
}

function updateTerminalPreviews() {
    const executingTasks = tasks.filter(t => t.status === 'executing');
    executingTasks.forEach(t => {
        const preview = document.getElementById(`term-${t.id}`);
        if (preview) {
            const activity = agentActivityCache[t.agent] || {};
            const output = activity.current_output || '';
            const lines = output.split('\n').slice(-4).join('\n').substring(0, 200);
            const pre = preview.querySelector('pre');
            if (pre && lines) {
                pre.textContent = lines || 'Waiting for output...';
            }
        }
    });
}

async function crossAgentCheck(taskId, targetAgent) {
    if (!executorOnline) {
        alert('Executor offline');
        return;
    }
    const idleAgents = Object.entries(agentActivityCache)
        .filter(([name, info]) => info.status === 'idle' && name !== targetAgent)
        .map(([name]) => name);
    const checker = idleAgents[0] || 'assistant';
    chatHistory.push({
        bot: checker,
        type: 'bot',
        content: `👁 Checking on ${targetAgent.toUpperCase()}...`,
        timestamp: new Date().toISOString()
    });
    document.getElementById('chatBot').value = checker;
    renderChat();
    try {
        const resp = await fetch(`${EXECUTOR_URL}/check-agent`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ checker, target: targetAgent, task_id: taskId })
        });
        const data = await resp.json();
        if (data.success) {
            chatHistory.push({
                bot: checker,
                type: 'bot',
                content: `📊 **Status of ${targetAgent.toUpperCase()}:**\n${data.target_running ? '🟢 Running' : '⚫ Not running'}\n\n${data.summary.substring(0, 400)}`,
                timestamp: new Date().toISOString()
            });
        }
    } catch (e) {
        chatHistory.push({
            bot: checker,
            type: 'bot',
            content: `❌ Error checking: ${e.message}`,
            timestamp: new Date().toISOString()
        });
    }
    localStorage.setItem('chat-history', JSON.stringify(chatHistory));
    renderChat();
}

function showCli(agent) {
    currentCliAgent = agent;
    document.getElementById('cliAgent').textContent = agent;
    document.getElementById('cliPanel').classList.add('show');
    cliPanelVisible = true;
    document.getElementById('cliToggleBtn').style.background = '#238636';
    refreshCli();
    if (cliRefreshInterval) clearInterval(cliRefreshInterval);
    cliRefreshInterval = setInterval(refreshCli, 2000);
    if (panelCollapsed) togglePanel();
}

function closeCli() {
    document.getElementById('cliPanel').classList.remove('show');
    cliPanelVisible = false;
    document.getElementById('cliToggleBtn').style.background = '';
    if (cliRefreshInterval) {
        clearInterval(cliRefreshInterval);
        cliRefreshInterval = null;
    }
}

async function startClaudeSession() {
    if (!currentCliAgent) {
        alert('Select an agent first');
        return;
    }
    const repo = document.getElementById('cliRepoSelect').value;
    const btn = document.getElementById('startClaudeBtn');
    btn.textContent = '...';
    btn.disabled = true;
    try {
        const resp = await fetch(`${EXECUTOR_URL}/start-claude`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bot: currentCliAgent, repo: repo })
        });
        const data = await resp.json();
        if (data.success) {
            btn.textContent = data.already_running ? '● Running' : '✓ Started';
            btn.style.background = '#238636';
            refreshCli();
            if (!cliRefreshInterval) {
                cliRefreshInterval = setInterval(refreshCli, 2000);
            }
        } else {
            btn.textContent = '✗ Error';
            btn.style.background = '#da3633';
            console.error('Start Claude failed:', data.error);
        }
    } catch (e) {
        btn.textContent = '✗ Error';
        btn.style.background = '#da3633';
        console.error('Start Claude error:', e);
    }
    setTimeout(() => {
        btn.textContent = '▶ Start';
        btn.disabled = false;
    }, 3000);
}

async function refreshCli() {
    if (!currentCliAgent || !executorOnline) return;
    try {
        const resp = await fetch(`${EXECUTOR_URL}/tmux-output?bot=${currentCliAgent}&lines=100`);
        const data = await resp.json();
        let output = data.output || 'No output - session may not be running';

        // Escape HTML but preserve structure
        output = output
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            // Highlight keywords
            .replace(/(thinking|processing|waiting)/gi, '<span style="color:#f0883e;">$1</span>')
            .replace(/(error|failed|exception)/gi, '<span style="color:#f85149;">$1</span>')
            .replace(/(done|completed|success|✓)/gi, '<span style="color:#3fb950;">$1</span>')
            .replace(/(claude|Claude)/g, '<span style="color:#a371f7;">$1</span>');

        const cliOutput = document.getElementById('cliOutput');
        const wasAtBottom = cliOutput.scrollHeight - cliOutput.scrollTop - cliOutput.clientHeight < 100;
        cliOutput.innerHTML = output;
        if (wasAtBottom) {
            cliOutput.scrollTop = cliOutput.scrollHeight;
        }
    } catch (e) {
        document.getElementById('cliOutput').textContent = 'Error loading CLI output: ' + e.message;
    }
}

async function sendCliCommand() {
    if (!currentCliAgent || !executorOnline) return;
    const input = document.getElementById('cliInput');
    const cmd = input.value;
    if (!cmd) return;

    try {
        // Send the command text
        await fetch(`${EXECUTOR_URL}/tmux-send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bot: currentCliAgent, keys: cmd })
        });
        // Send Enter to execute
        await fetch(`${EXECUTOR_URL}/tmux-send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bot: currentCliAgent, keys: 'Enter' })
        });

        input.value = '';
        input.focus();

        // Refresh output after a short delay
        setTimeout(refreshCli, 300);
        setTimeout(refreshCli, 1000);
        setTimeout(refreshCli, 3000);
    } catch (e) {
        console.error('Failed to send command:', e);
    }
}

async function sendCliKey(key) {
    if (!currentCliAgent || !executorOnline) return;
    try {
        await fetch(`${EXECUTOR_URL}/tmux-send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bot: currentCliAgent, keys: key })
        });
        setTimeout(refreshCli, 300);
    } catch (e) {
        console.error('Failed to send key:', e);
    }
}

async function refreshCliInChat(bot) {
    if (!executorOnline) return;
    const agentMap = { assistant: 'assistant', bitcoinml: 'bitcoinml', energyscout: 'energyscout', realestate: 'realestate' };
    const botName = agentMap[bot] || bot;
    try {
        const resp = await fetch(`${EXECUTOR_URL}/tmux-output?bot=${botName}&lines=40`);
        const data = await resp.json();
        if (data.output) {
            chatHistory.push({
                bot,
                type: 'bot',
                content: '```\n' + data.output.substring(0, 1500) + '\n```',
                timestamp: new Date().toISOString(),
                source: 'cli'
            });
            localStorage.setItem('chat-history', JSON.stringify(chatHistory));
            renderChat();
        }
    } catch (e) {
        console.error('Failed to get CLI output:', e);
    }
}

async function loadLinkedBots() {
    if (!executorOnline) return;
    try {
        const resp = await fetch(`${EXECUTOR_URL}/status`);
        const data = await resp.json();
        linkedSessions = data.sessions || [];
        updateBotStatusIndicators(data.bots);
    } catch (e) {
        console.log('Error loading bots:', e);
    }
}

function updateBotStatusIndicators(bots) {
    document.querySelectorAll('.bot-indicator').forEach(el => {
        const botName = el.dataset.bot;
        const botData = bots?.[botName];
        el.classList.remove('online', 'busy');
        if (botData?.tmux) {
            el.classList.add('online');
            const hasBusyTask = tasks.some(t => t.status === 'executing' &&
                (t.agent === botName ||
                 (botName === 'assistant' && t.agent === 'ass') ||
                 (botName === 'bitcoinml' && t.agent === 'bml') ||
                 (botName === 'energyscout' && t.agent === 'ene') ||
                 (botName === 'realestate' && t.agent === 'rea')));
            if (hasBusyTask) el.classList.add('busy');
        }
    });
}

function toggleRunningDropdown() {
    document.getElementById('runningDropdownContent').classList.toggle('show');
}

document.addEventListener('click', (e) => {
    if (!e.target.closest('.running-dropdown')) {
        document.getElementById('runningDropdownContent')?.classList.remove('show');
    }
});

function selectBot(name) {
    const botMap = {
        'assistant': 'assistant',
        'bitcoinml': 'bitcoinml',
        'energyscout': 'energyscout',
        'realestate': 'realestate',
        'analytics': 'assistant'
    };
    document.getElementById('chatBot').value = botMap[name] || 'assistant';
    renderChat();
}

function sendToBot(name) {
    selectBot(name);
    document.getElementById('chatInput').focus();
}

function renderRunningTasks() {
    const running = tasks.filter(t => t.status === 'executing');
    const badge = document.getElementById('runningCountBadge');
    const dropdown = document.getElementById('runningDropdownContent');
    badge.textContent = running.length;
    badge.classList.toggle('zero', running.length === 0);
    if (running.length === 0) {
        dropdown.innerHTML = '<div style="color:#9eaab6;text-align:center;padding:15px;font-size:12px;">No tasks running</div>';
        return;
    }
    dropdown.innerHTML = running.map(t => `
        <div class="running-task-item">
            <span class="agent-tag">${t.agent.toUpperCase()}</span>
            <span class="task-text">${t.text}</span>
            <button class="stop-btn" onclick="event.stopPropagation();stopTask('${t.id}')">Stop</button>
        </div>
    `).join('');
}

function renderChat() {
    const bot = document.getElementById('chatBot').value;
    const botHistory = chatHistory.filter(m => m.bot === bot).slice(-20);
    document.getElementById('chatMessages').innerHTML = botHistory.map(m => {
        const senderLabel = m.source === 'telegram' ? '📱 Telegram' : (m.type === 'user' ? 'You' : m.bot.toUpperCase());
        const msgClass = m.source === 'telegram' ? 'user telegram' : m.type;
        return `
            <div class="chat-message ${msgClass}">
                <div class="sender">${senderLabel}</div>
                ${m.content}
            </div>
        `;
    }).join('') || '<div style="color:#9eaab6;text-align:center;padding:20px;">No messages yet</div>';
    const msgs = document.getElementById('chatMessages');
    msgs.scrollTop = msgs.scrollHeight;
}

async function sendChat() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;
    const bot = document.getElementById('chatBot').value;
    if (message === '/clear') {
        chatHistory = chatHistory.filter(m => m.bot !== bot);
        localStorage.setItem('chat-history', JSON.stringify(chatHistory));
        input.value = '';
        renderChat();
        return;
    }
    if (message === '/cli') {
        input.value = '';
        await refreshCliInChat(bot);
        return;
    }
    const modalTaskId = document.getElementById('detailModal').dataset.taskId;
    if (modalTaskId && document.getElementById('detailModal').classList.contains('show')) {
        const task = tasks.find(t => t.id === modalTaskId);
        if (task) {
            addWorkLog(modalTaskId, message, 'note');
            task.notes = (task.notes ? task.notes + '\n' : '') + `[${new Date().toLocaleTimeString()}] ${message}`;
            save();
            chatHistory.push({ bot, type: 'user', content: message, timestamp: new Date().toISOString() });
            chatHistory.push({ bot, type: 'bot', content: '✅ Note saved to task.', timestamp: new Date().toISOString() });
            localStorage.setItem('chat-history', JSON.stringify(chatHistory));
            input.value = '';
            renderChat();
            return;
        }
    }
    chatHistory.push({ bot, type: 'user', content: message, timestamp: new Date().toISOString() });
    localStorage.setItem('chat-history', JSON.stringify(chatHistory));
    input.value = '';
    renderChat();
    if (!executorOnline) {
        chatHistory.push({ bot, type: 'bot', content: 'Executor offline. Start it to send messages.', timestamp: new Date().toISOString() });
        localStorage.setItem('chat-history', JSON.stringify(chatHistory));
        renderChat();
        return;
    }
    chatHistory.push({ bot, type: 'bot', content: '💭 Thinking...', timestamp: new Date().toISOString(), pending: true });
    localStorage.setItem('chat-history', JSON.stringify(chatHistory));
    renderChat();
    try {
        const resp = await fetch(`${EXECUTOR_URL}/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: 'chat-' + Date.now(),
                text: message,
                agent: bot
            })
        });
        const data = await resp.json();
        chatHistory = chatHistory.filter(m => !m.pending);
        if (data.success) {
            chatHistory.push({ bot, type: 'bot', content: `📤 Message sent to ${bot}. Waiting for response...`, timestamp: new Date().toISOString() });
        } else {
            chatHistory.push({ bot, type: 'bot', content: '❌ Error: ' + (data.error || 'Unknown'), timestamp: new Date().toISOString() });
        }
    } catch (e) {
        chatHistory = chatHistory.filter(m => !m.pending);
        chatHistory.push({ bot, type: 'bot', content: '❌ Error: ' + e.message, timestamp: new Date().toISOString() });
    }
    localStorage.setItem('chat-history', JSON.stringify(chatHistory));
    renderChat();
    setTimeout(async () => {
        try {
            const resp = await fetch(`${EXECUTOR_URL}/outbox?bot=${bot}`);
            const data = await resp.json();
            if (data.content && data.content.trim()) {
                chatHistory.push({ bot, type: 'bot', content: '💬 ' + data.content.substring(0, 500), timestamp: new Date().toISOString() });
                localStorage.setItem('chat-history', JSON.stringify(chatHistory));
                renderChat();
            }
        } catch {}
    }, 5000);
}

document.getElementById('chatBot').addEventListener('change', () => {
    updateChatSidebar();
    renderChat();
});

function switchChatBot(bot) {
    document.getElementById('chatBot').value = bot;
    updateChatSidebar();
    renderChat();
}

function updateChatSidebar() {
    const bot = document.getElementById('chatBot').value;
    document.querySelectorAll('.chat-session').forEach(el => {
        el.classList.toggle('active', el.dataset.bot === bot);
    });
}

function clearChat() {
    const bot = document.getElementById('chatBot').value;
    chatHistory = chatHistory.filter(m => m.bot !== bot);
    localStorage.setItem('chat-history', JSON.stringify(chatHistory));
    renderChat();
}

let lastOutboxContent = {};

async function pollMessages() {
    if (!executorOnline) return;
    const bot = document.getElementById('chatBot').value;
    try {
        const resp = await fetch(`${EXECUTOR_URL}/outbox?bot=${bot}`);
        const data = await resp.json();
        if (data.content && data.content.trim()) {
            const content = data.content.trim();
            if (content.includes('Execute this task') || content.includes('- [ ]') || content.includes('Top TODOs')) {
                return;
            }
            if (lastOutboxContent[bot] !== content) {
                lastOutboxContent[bot] = content;
                chatHistory.push({
                    bot,
                    type: 'bot',
                    content: content.substring(0, 800),
                    timestamp: new Date().toISOString()
                });
                localStorage.setItem('chat-history', JSON.stringify(chatHistory));
                renderChat();
            }
        }
    } catch {}
}

setInterval(pollMessages, 3000);
setTimeout(pollMessages, 1000);

const originalRenderAll = renderAll;
renderAll = function() {
    originalRenderAll();
    renderRunningTasks();
};

updateMainHeight();
setTimeout(renderChat, 100);

function openClineKanban() {
    const port = localStorage.getItem('kanban-port') || '3484';
    const clineHost = isLocal ? '127.0.0.1' : executorHost;
    document.getElementById('clineFrame').src = `http://${clineHost}:${port}/openclaw`;
    document.getElementById('clineModal').classList.add('show');
}

function closeClineModal() {
    document.getElementById('clineModal').classList.remove('show');
    document.getElementById('clineFrame').src = '';
}

if (isMobile) {
    panelCollapsed = true;
    document.getElementById('bottomPanel')?.classList.add('collapsed');
}

let kanbanConnected = false;
async function connectKanban() {
    const port = '3484';
    const url = `http://localhost:${port}`;
    try {
        const check = await fetch(url, { mode: 'no-cors', cache: 'no-cache' });
    } catch (e) {
        document.getElementById('kanbanStatus').textContent = 'Not running, launching...';
        document.getElementById('kanbanStatus').style.color = '#f0883e';
        await launchKanban();
        return;
    }
    document.getElementById('kanbanFrame').innerHTML = `
        <iframe src="http://127.0.0.1:${port}/openclaw" style="width:100%;height:100%;border:none;background:#0d1117;"
            onerror="handleIframeError()"></iframe>
    `;
    document.getElementById('kanbanStatus').textContent = `Connected to 127.0.0.1:${port}`;
    document.getElementById('kanbanStatus').style.color = '#3fb950';
    kanbanConnected = true;
    localStorage.setItem('kanban-port', port);
}

async function launchKanban() {
    document.getElementById('kanbanStatus').textContent = 'Launching npx kanban...';
    document.getElementById('kanbanStatus').style.color = '#f0883e';
    if (!executorOnline) {
        document.getElementById('kanbanFrame').innerHTML = `
            <div style="text-align:center;color:#9eaab6;padding:40px;">
                <h3>Executor Offline</h3>
                <p>Start executor first:</p>
                <code style="background:#21262d;padding:8px 16px;border-radius:6px;display:inline-block;margin:10px 0;">
                    cd ~/Vaults/openclaw/bridge/kanban && python3 executor.py
                </code>
                <p style="margin-top:20px;">Then run npx kanban:</p>
                <code style="background:#21262d;padding:8px 16px;border-radius:6px;display:inline-block;">
                    npx kanban
                </code>
            </div>
        `;
        return;
    }
    try {
        const resp = await fetch(`${EXECUTOR_URL}/launch-npx-kanban`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const data = await resp.json();
        if (data.success) {
            document.getElementById('kanbanStatus').textContent = 'Launching... (connecting in 4s)';
            setTimeout(() => {
                const port = document.getElementById('kanbanPort').value || '3484';
                document.getElementById('kanbanFrame').innerHTML = `
                    <iframe src="http://127.0.0.1:${port}/openclaw" style="width:100%;height:100%;border:none;background:#0d1117;"></iframe>
                `;
                document.getElementById('kanbanStatus').textContent = `Connected to 127.0.0.1:${port}`;
                document.getElementById('kanbanStatus').style.color = '#3fb950';
                kanbanConnected = true;
            }, 4000);
        } else {
            showKanbanError(data.error || 'Launch failed');
        }
    } catch (e) {
        showKanbanError(e.message);
    }
}

function showKanbanError(msg) {
    document.getElementById('kanbanStatus').textContent = 'Error: ' + msg;
    document.getElementById('kanbanStatus').style.color = '#da3633';
    document.getElementById('kanbanFrame').innerHTML = `
        <div style="text-align:center;color:#9eaab6;padding:40px;">
            <h3>Could not launch npx kanban</h3>
            <p>Run manually in terminal:</p>
            <code style="background:#21262d;padding:8px 16px;border-radius:6px;display:inline-block;">
                npx kanban
            </code>
            <p style="margin-top:20px;color:#da3633;">${msg}</p>
        </div>
    `;
}

function initIdeKanban() {
    const savedPort = localStorage.getItem('kanban-port');
    if (savedPort) {
        document.getElementById('kanbanPort').value = savedPort;
    }
    if (!kanbanConnected && executorOnline) {
        launchKanban();
    }
}

const baseRenderAll = renderAll;
renderAll = function() {
    baseRenderAll();
    if (currentView === 'ide') {
        initIdeKanban();
    }
};

init();
