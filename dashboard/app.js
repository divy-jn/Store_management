const API_URL = 'http://localhost:8000';
let STORE_ID = document.getElementById('store-selector') ? document.getElementById('store-selector').value : 'ST1008';
let activeWebSocket = null;

// Chart instances
let funnelChart = null;
let heatmapChart = null;

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initCharts();
    fetchInitialData();
    connectWebSocket();
    initNavigation();
    
    // Store Selector logic
    const storeSelector = document.getElementById('store-selector');
    if (storeSelector) {
        storeSelector.addEventListener('change', (e) => {
            STORE_ID = e.target.value;
            showToast('INFO', 'Store Changed', `Now viewing live analytics for ${e.target.options[e.target.selectedIndex].text}`);
            
            // Clear UI optimistically
            document.getElementById('current-visitors').textContent = '0';
            document.getElementById('conversion-rate').textContent = '0.0%';
            document.getElementById('queue-depth').textContent = '0';
            document.getElementById('abandonment-rate').textContent = '0.0%';
            updateFunnelChart([]);
            updateHeatmapChart([]);
            document.getElementById('dwell-container').innerHTML = '<div class="loading-state">Fetching store data...</div>';
            
            // Refetch and reconnect
            fetchInitialData();
            if (activeWebSocket) {
                // Prevent auto-reconnect logic from the old socket
                activeWebSocket.onclose = null;
                activeWebSocket.close();
            }
            connectWebSocket();
        });
    }

    document.getElementById('refresh-btn').addEventListener('click', () => {
        fetchInitialData();
        showToast('INFO', 'Data Sync', 'Dashboard data has been refreshed manually.');
    });

    document.getElementById('demo-btn').addEventListener('click', async () => {
        if (!confirm('This will clear the current data and restart the live demo replay. Continue?')) return;
        
        try {
            const res = await fetch(`${API_URL}/system/demo-replay`, { method: 'POST' });
            if (res.ok) {
                showToast('INFO', 'Live Demo Started', 'Database cleared. Events will stream in real-time shortly.');
                
                // Activate Timer and UI changes
                demoTimerActive = true;
                demoElapsedSeconds = 0;
                document.getElementById('clock').style.color = 'var(--brand-purple)';
                
                const demoBtn = document.getElementById('demo-btn');
                demoBtn.innerHTML = '<i class="fa-solid fa-rotate-left"></i> Restart';
                document.getElementById('skip-btn').style.display = 'inline-block';
                
                // Optimistically clear UI
                document.getElementById('current-visitors').textContent = '0';
                document.getElementById('conversion-rate').textContent = '0.0%';
                document.getElementById('queue-depth').textContent = '0';
                document.getElementById('abandonment-rate').textContent = '0.0%';
                updateFunnelChart([]);
                updateHeatmapChart([]);
                document.getElementById('dwell-container').innerHTML = '<div class="loading-state">Waiting for dwell data...</div>';
            } else {
                showToast('CRITICAL', 'Demo Error', 'Failed to start demo replay.');
            }
        } catch (e) {
            showToast('CRITICAL', 'API Error', 'Failed to connect to API.');
        }
    });

    document.getElementById('skip-btn').addEventListener('click', async () => {
        try {
            const res = await fetch(`${API_URL}/system/demo-skip`, { method: 'POST' });
            if (res.ok) {
                showToast('INFO', 'Fast Forward', 'Skipped 10 seconds of simulation time.');
                demoElapsedSeconds += 10;
                
                // Automatically fetch charts so they update during the skip without needing manual Sync
                fetchInitialData();
            }
        } catch (e) {
            console.error("Skip failed", e);
        }
    });
});

// --- Navigation ---

function initNavigation() {
    const navItems = {
        'nav-overview': () => window.scrollTo({ top: 0, behavior: 'smooth' }),
        'nav-cameras': () => showToast('WARN', 'Live Feeds Offline', 'Raw RTSP camera feeds are not exposed directly to the dashboard to save bandwidth. Rely on the analytics.'),
        'nav-heatmap': () => document.getElementById('section-heatmap').scrollIntoView({ behavior: 'smooth', block: 'center' }),
        'nav-funnel': () => document.getElementById('section-funnel').scrollIntoView({ behavior: 'smooth', block: 'center' }),
        'nav-anomalies': () => showToast('INFO', 'Anomalies', 'No new anomalies detected right now. The anomaly daemon runs in the background.')
    };

    for (const [id, action] of Object.entries(navItems)) {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                // Update active state
                document.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                el.classList.add('active');
                // Perform action
                action();
            });
        }
    }
}

// --- UI Helpers ---

let clockInterval = null;
let demoTimerActive = false;
let demoElapsedSeconds = 0;

function initClock() {
    const clockEl = document.getElementById('clock');
    
    clockInterval = setInterval(() => {
        if (demoTimerActive) {
            demoElapsedSeconds++;
            const mins = String(Math.floor(demoElapsedSeconds / 60)).padStart(2, '0');
            const secs = String(demoElapsedSeconds % 60).padStart(2, '0');
            clockEl.textContent = `${mins}:${secs}`;
        } else {
            const now = new Date();
            clockEl.textContent = now.toLocaleTimeString('en-US', { hour12: false });
        }
    }, 1000);
}

function showToast(severity, title, message, durationMs = 6000) {
    const container = document.getElementById('toast-container');
    
    // Limit max toasts on screen to 4 to prevent overwhelming UI
    if (container.children.length >= 4) {
        const oldestToast = container.firstElementChild;
        oldestToast.classList.remove('show');
        setTimeout(() => oldestToast.remove(), 400);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast ${severity}`;
    
    let icon = 'fa-circle-info';
    if (severity === 'CRITICAL') icon = 'fa-triangle-exclamation';
    if (severity === 'WARN') icon = 'fa-circle-exclamation';
    
    // The inline style sets the animation duration for the progress bar
    toast.innerHTML = `
        <div class="toast-icon"><i class="fa-solid ${icon}"></i></div>
        <div class="toast-content">
            <h4>${title}</h4>
            <p>${message}</p>
        </div>
        <button class="toast-close" onclick="this.parentElement.classList.remove('show'); setTimeout(() => this.parentElement.remove(), 400);"><i class="fa-solid fa-xmark"></i></button>
        <div class="toast-progress" style="animation-duration: ${durationMs}ms;"></div>
    `;
    
    container.appendChild(toast);
    
    // Animate in
    setTimeout(() => toast.classList.add('show'), 50);
    
    // Auto remove
    setTimeout(() => {
        if (toast.parentElement) {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 400);
        }
    }, durationMs);
}

// --- Data Fetching ---

async function fetchInitialData() {
    try {
        await Promise.all([
            fetchMetrics(),
            fetchFunnel(),
            fetchHeatmap(),
            fetchAnomalies()
        ]);
    } catch (err) {
        console.error("Error fetching initial data:", err);
        showToast('CRITICAL', 'API Error', 'Failed to connect to the Store Intelligence API.');
    }
}

async function fetchMetrics() {
    const res = await fetch(`${API_URL}/stores/${STORE_ID}/metrics`);
    const data = await res.json();
    
    // We update current visitors via websocket, but metrics gives unique visitors today
    // and queue depth, abandonment etc.
    
    // Since 'in-store right now' requires entries - exits
    const currentInStore = data.total_entries - data.total_exits;
    document.getElementById('current-visitors').textContent = Math.max(0, currentInStore);
    
    document.getElementById('conversion-rate').textContent = `${(data.conversion_rate * 100).toFixed(1)}%`;
    document.getElementById('queue-depth').textContent = data.current_queue_depth;
    document.getElementById('abandonment-rate').textContent = `${(data.abandonment_rate * 100).toFixed(1)}%`;
    
    // Render zone dwell times
    renderZoneBars(data.avg_dwell_per_zone);
}

async function fetchFunnel() {
    const res = await fetch(`${API_URL}/stores/${STORE_ID}/funnel`);
    const data = await res.json();
    updateFunnelChart(data.stages);
}

async function fetchHeatmap() {
    const res = await fetch(`${API_URL}/stores/${STORE_ID}/heatmap`);
    const data = await res.json();
    updateHeatmapChart(data.zones);
}

async function fetchAnomalies() {
    const res = await fetch(`${API_URL}/stores/${STORE_ID}/anomalies`);
    const data = await res.json();
    
    if (data.anomalies && data.anomalies.length > 0) {
        data.anomalies.forEach(a => {
            showToast(a.severity, a.anomaly_type.replace(/_/g, ' '), a.description);
        });
    }
}

// --- WebSocket ---

function connectWebSocket() {
    // Determine WS URL based on current host (handling local vs docker)
    const wsUrl = `ws://localhost:8000/ws/live/${STORE_ID}`;
    const ws = new WebSocket(wsUrl);
    activeWebSocket = ws;
    
    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'metrics_update') {
            const data = msg.data;
            // Update live counters
            document.getElementById('current-visitors').textContent = data.current_in_store;
            document.getElementById('queue-depth').textContent = data.queue_depth;
            
            // Add a subtle flash animation to indicate live update
            const el = document.getElementById('current-visitors');
            el.style.color = 'var(--brand-primary)';
            setTimeout(() => el.style.color = '', 500);
        } else if (msg.type === 'demo_completed') {
            demoTimerActive = false;
            document.getElementById('skip-btn').style.display = 'none';
            const demoBtn = document.getElementById('demo-btn');
            demoBtn.innerHTML = '<i class="fa-solid fa-rotate-left"></i> Restart Demo';
            demoBtn.style.display = 'inline-block';
            fetchInitialData();
            showToast('INFO', 'Demo Complete', 'Checkout simulation complete! Funnel is updated.');
        }
    };
    
    ws.onclose = () => {
        console.log("WebSocket disconnected. Retrying in 5s...");
        setTimeout(connectWebSocket, 5000);
    };
}

// --- Charts & Visualizations ---

function renderZoneBars(zones) {
    const container = document.getElementById('dwell-container');
    container.innerHTML = '';
    
    if (!zones || zones.length === 0) {
        container.innerHTML = '<div class="loading-state">No dwell data available yet.</div>';
        return;
    }
    
    // Find max for normalization
    const maxDwell = Math.max(...zones.map(z => z.avg_dwell_ms));
    
    zones.forEach(zone => {
        const seconds = Math.round(zone.avg_dwell_ms / 1000);
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
        
        const pct = maxDwell > 0 ? (zone.avg_dwell_ms / maxDwell) * 100 : 0;
        
        const html = `
            <div class="zone-row">
                <div class="zone-name">${zone.zone_name}</div>
                <div class="zone-bar-bg">
                    <div class="zone-bar-fill" style="width: ${pct}%"></div>
                </div>
                <div class="zone-val">${timeStr}</div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);
    });
}

function initCharts() {
    // Common Chart.js global settings for Dark Mode glass UI
    Chart.defaults.color = '#a3a3b5';
    Chart.defaults.font.family = "'Outfit', sans-serif";
    Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(20, 20, 35, 0.9)';
    Chart.defaults.plugins.tooltip.titleColor = '#fff';
    Chart.defaults.plugins.tooltip.padding = 12;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    
    const funnelCtx = document.getElementById('funnelChart').getContext('2d');
    funnelChart = new Chart(funnelCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Visitors',
                data: [],
                backgroundColor: [
                    'rgba(233, 30, 99, 0.8)',   // brand-primary
                    'rgba(156, 39, 176, 0.8)',  // brand-purple
                    'rgba(0, 230, 118, 0.8)',   // success
                    'rgba(0, 176, 255, 0.8)'    // info
                ],
                borderRadius: 6,
                barThickness: 40
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                x: { grid: { display: false } }
            }
        }
    });

    const heatmapCtx = document.getElementById('heatmapChart').getContext('2d');
    heatmapChart = new Chart(heatmapCtx, {
        type: 'polarArea',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [
                    'rgba(233, 30, 99, 0.6)',
                    'rgba(156, 39, 176, 0.6)',
                    'rgba(0, 230, 118, 0.6)',
                    'rgba(255, 179, 0, 0.6)',
                    'rgba(0, 176, 255, 0.6)'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: { 
                    ticks: { display: false },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                }
            },
            plugins: {
                legend: { position: 'right' }
            }
        }
    });
}

function updateFunnelChart(stages) {
    if (!stages || stages.length === 0) return;
    
    funnelChart.data.labels = stages.map(s => s.stage);
    funnelChart.data.datasets[0].data = stages.map(s => s.count);
    funnelChart.update();
}

function updateHeatmapChart(zones) {
    if (!zones || zones.length === 0) return;
    
    // Sort by visit count
    const sorted = [...zones].sort((a,b) => b.visit_count - a.visit_count);
    
    heatmapChart.data.labels = sorted.map(z => z.zone_name);
    heatmapChart.data.datasets[0].data = sorted.map(z => z.visit_count);
    heatmapChart.update();
}
