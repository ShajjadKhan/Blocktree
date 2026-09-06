// BlockTree - Matrix Engine with Permanent Live Leaderboard

const canvasElem = document.getElementById("tree-canvas");
const panzoom = Panzoom(canvasElem, {
    maxScale: 3.5,
    minScale: 0.08,
    startScale: 0.75,
    canvas: true,
    contain: 'outside',
    cursor: 'grab'
});

canvasElem.parentElement.addEventListener("wheel", panzoom.zoomWithWheel);

// Sound Synthesizer
let soundEnabled = localStorage.getItem('blocktree_sound') !== 'false';
let audioCtx = null;

function getAudioContext() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === 'suspended') audioCtx.resume();
    return audioCtx;
}

function playSound(type) {
    if (!soundEnabled) return;
    try {
        const ctx = getAudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        const now = ctx.currentTime;

        if (type === 'click') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(800, now);
            osc.frequency.exponentialRampToValueAtTime(1200, now + 0.05);
            gain.gain.setValueAtTime(0.06, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
            osc.start(now); osc.stop(now + 0.05);
        } else if (type === 'success') {
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(523.25, now);
            osc.frequency.setValueAtTime(659.25, now + 0.08);
            osc.frequency.setValueAtTime(783.99, now + 0.16);
            gain.gain.setValueAtTime(0.1, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
            osc.start(now); osc.stop(now + 0.35);
        } else if (type === 'copy') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(1000, now);
            osc.frequency.exponentialRampToValueAtTime(500, now + 0.07);
            gain.gain.setValueAtTime(0.05, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.07);
            osc.start(now); osc.stop(now + 0.07);
        }
    } catch (e) {}
}

const audioBtn = document.getElementById('audio-toggle');
const audioIcon = document.getElementById('audio-icon');
function updateAudioUI() {
    audioIcon.className = soundEnabled ? 'bi bi-volume-up-fill text-cyan' : 'bi bi-volume-mute-fill opacity-50';
}
updateAudioUI();
audioBtn.addEventListener('click', () => {
    soundEnabled = !soundEnabled;
    localStorage.setItem('blocktree_sound', soundEnabled);
    updateAudioUI();
    if (soundEnabled) playSound('click');
});

// Toast Helper
function showToast(message, isError = false) {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toast-message');
    const toastIcon = document.getElementById('toast-icon');
    toastMsg.textContent = message;
    toastIcon.className = isError ? 'bi bi-exclamation-octagon-fill text-magenta' : 'bi bi-check-circle-fill text-cyan';
    toast.classList.remove('d-none');
    setTimeout(() => { toast.classList.add('d-none'); }, 3500);
}

// Camera Navigation
function panToCoordinate(targetX, targetY, scale = 1.0) {
    const container = document.getElementById('canvas-container');
    const viewW = container.clientWidth;
    const viewH = container.clientHeight;
    const panX = (viewW / 2) - (targetX * scale);
    const panY = (viewH / 2) - (targetY * scale);
    panzoom.zoom(scale, { animate: true });
    panzoom.pan(panX, panY, { animate: true });
}

function focusNode(nodeId) {
    const node = nodeMap[nodeId];
    if (node) {
        playSound('click');
        panToCoordinate(node.x + 75, node.y + 60, 1.15);
        const elem = document.querySelector(`.node[data-id="${nodeId}"]`);
        if (elem) {
            elem.style.transform = 'translateY(-6px) scale(1.12)';
            elem.style.borderColor = '#00f3ff';
            elem.style.boxShadow = '0 0 30px #00f3ff';
            setTimeout(() => {
                elem.style.transform = '';
                elem.style.borderColor = '';
                elem.style.boxShadow = '';
            }, 1500);
        }
    }
}

// Copy Helper
window.copyReferral = (refCode, e) => {
    if (e) e.stopPropagation();
    playSound('copy');
    const link = `${window.location.origin}/?ref=${refCode}`;
    navigator.clipboard.writeText(link).then(() => {
        showToast(`Copied: ${link}`);
    }).catch(() => {
        prompt("Copy this referral link:", link);
    });
};

// Global Matrix State
let currentNodes = [];
let nodeMap = {};
let systemStats = {};

// Compact Node Inspector
function openInspector(node) {
    playSound('click');
    const inspector = document.getElementById('node-inspector');
    
    document.getElementById('insp-avatar').src = node.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + node.name;
    document.getElementById('insp-name').textContent = node.name;
    document.getElementById('insp-text').textContent = `"${node.text}"`;
    
    const spillTag = document.getElementById('insp-spillover-tag');
    if (node.is_spillover) spillTag.classList.remove('d-none');
    else spillTag.classList.add('d-none');
    
    document.getElementById('insp-depth').textContent = node.depth;
    document.getElementById('insp-direct-refs').textContent = node.direct_refs;
    document.getElementById('insp-grid-slots').textContent = `${node.direct_children}/5`;
    
    const sponsorBtn = document.getElementById('insp-jump-sponsor');
    sponsorBtn.textContent = (node.sponsor_name || 'Root').slice(0, 10);
    sponsorBtn.onclick = () => { if (node.sponsor_id) focusNode(node.sponsor_id); };
    
    const refLinkInput = document.getElementById('insp-ref-link');
    const fullLink = `${window.location.origin}/?ref=${node.ref_code}`;
    refLinkInput.value = fullLink;
    
    document.getElementById('insp-copy-btn').onclick = () => {
        playSound('copy');
        navigator.clipboard.writeText(fullLink);
        showToast("Referral Link copied!");
    };
    
    inspector.classList.remove('d-none');
}

document.getElementById('inspector-close').addEventListener('click', () => {
    document.getElementById('node-inspector').classList.add('d-none');
});

// Telemetry Popover Toggle
const toggleStatsBtn = document.getElementById('toggle-stats-btn');
const detailedStatsCard = document.getElementById('detailed-stats-card');
const statsChevron = document.getElementById('stats-chevron');

toggleStatsBtn.addEventListener('click', () => {
    playSound('click');
    const isClosed = detailedStatsCard.classList.contains('d-none');
    if (isClosed) {
        detailedStatsCard.classList.remove('d-none');
        toggleStatsBtn.classList.add('open');
    } else {
        detailedStatsCard.classList.add('d-none');
        toggleStatsBtn.classList.remove('open');
    }
});

// Close telemetry popover when clicking on canvas (Leaderboard stays permanently OPEN)
canvasElem.addEventListener('click', () => {
    detailedStatsCard.classList.add('d-none');
    toggleStatsBtn.classList.remove('open');
});

// Load Matrix
async function loadMatrix(autoCenter = false) {
    try {
        const res = await fetch('/api/nodes');
        const data = await res.json();
        
        currentNodes = data.nodes || [];
        systemStats = data.stats || {};
        nodeMap = {};
        
        currentNodes.forEach(n => { nodeMap[n.id] = n; });
        
        // 1. Update Compact Top Navigation Bar
        document.getElementById('stat-total-users').textContent = systemStats.total_users || 0;
        document.getElementById('stat-spillovers').textContent = systemStats.total_spillovers || 0;
        document.getElementById('stat-depth').textContent = `GEN ${systemStats.max_depth || 0}`;
        
        const pillBadge = document.getElementById('scarcity-pill-badge');
        if (systemStats.is_invite_only) {
            pillBadge.textContent = "🔒 INVITE-ONLY";
            pillBadge.style.borderColor = "#d946ef";
            pillBadge.style.color = "#d946ef";
        } else {
            pillBadge.textContent = `${systemStats.genesis_slots_left} / 100 Left`;
            pillBadge.style.borderColor = "";
            pillBadge.style.color = "";
        }
        
        // Popover detailed values
        document.getElementById('card-total-users').textContent = systemStats.total_users || 0;
        document.getElementById('card-spillovers').textContent = systemStats.total_spillovers || 0;
        document.getElementById('card-depth').textContent = `GEN ${systemStats.max_depth || 0}`;
        document.getElementById('live-visitors').textContent = 12 + Math.floor(Math.random() * 6);
        
        const pct = Math.min(100, (systemStats.total_users / systemStats.genesis_limit) * 100);
        document.getElementById('scarcity-progress-fill').style.width = `${pct}%`;
        document.getElementById('scarcity-ratio').textContent = `${systemStats.total_users} / ${systemStats.genesis_limit}`;
        
        const addBtn = document.getElementById('add-btn');
        const addBtnText = document.getElementById('add-btn-text');
        const phaseBadge = document.getElementById('hud-phase-badge');
        
        if (systemStats.is_invite_only) {
            phaseBadge.textContent = "INVITE-ONLY LOCKED";
            phaseBadge.classList.add('locked');
            document.getElementById('scarcity-title').textContent = "Genesis Full - Invite Only";
            document.getElementById('scarcity-subtext').textContent = "Strict referral code required for all new citizens.";
            addBtnText.textContent = "INVITE-ONLY ACCESS";
            addBtn.classList.add('locked-btn');
        } else {
            phaseBadge.textContent = "GENESIS PHASE";
            phaseBadge.classList.remove('locked');
            document.getElementById('scarcity-title').textContent = "Genesis Open Access";
            document.getElementById('scarcity-subtext').textContent = `${systemStats.genesis_slots_left} slots remain before matrix locks.`;
            addBtnText.textContent = "JOIN MATRIX";
            addBtn.classList.remove('locked-btn');
        }
        
        // 2. Populate Permanent Live Leaderboard (Always Visible)
        const leaderList = document.getElementById('leader-list');
        if (!data.leaders || data.leaders.length === 0) {
            leaderList.innerHTML = '<div class="leader-loading">No referrals yet</div>';
        } else {
            let html = '';
            data.leaders.forEach((l, i) => {
                const medal = i === 0 ? '🥇' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : `#${i+1}`));
                html += `
                    <div class="leader-row" onclick="focusNode(${l.id})" title="Click to view on matrix">
                        <span>${medal}</span>
                        <img class="leader-avatar" src="${l.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + l.name}" alt="">
                        <span class="leader-name">${l.name}</span>
                        <span class="leader-count">${l.count} Ref</span>
                    </div>
                `;
            });
            leaderList.innerHTML = html;
        }
        
        // 3. Render Nodes on Canvas
        const canvas = document.getElementById('tree-canvas');
        const svgCanvas = document.getElementById('svg-canvas');
        
        canvas.querySelectorAll('.node').forEach(el => el.remove());
        svgCanvas.querySelectorAll('path.circuit-line').forEach(p => p.remove());
        
        currentNodes.forEach(node => {
            const div = document.createElement('div');
            div.className = 'node';
            div.setAttribute('data-id', node.id);
            div.style.left = `${node.x}px`;
            div.style.top = `${node.y}px`;
            
            if (node.id === 1 || node.parent_id === null) div.classList.add('root-node');
            else if (node.is_spillover) div.classList.add('spillover-node');
            
            const filledCount = node.direct_children || 0;
            let slotsDots = '';
            for (let s = 0; s < 5; s++) slotsDots += (s < filledCount) ? '●' : '○';
            
            const crownHtml = (node.id === 1) ? '<div class="node-crown">👑</div>' : '';
            const spilloverHtml = node.is_spillover ? '<div class="node-spillover-badge">⚡ SPILLOVER</div>' : '';
            
            div.innerHTML = `
                ${crownHtml}
                <div class="node-avatar-wrap">
                    <img src="${node.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + node.name}" alt="Avatar">
                    ${spilloverHtml}
                </div>
                <h3>${node.name}</h3>
                <p>${node.text}</p>
                <div class="node-slots">
                    <span class="slots-pips">${slotsDots}</span> ${filledCount}/5
                </div>
                <div class="ref-quick-btn" onclick="copyReferral('${node.ref_code}', event)">
                    <i class="bi bi-link-45deg"></i> Ref Link
                </div>
            `;
            
            div.addEventListener('click', (e) => {
                if (!e.target.closest('.ref-quick-btn')) {
                    openInspector(node);
                }
            });
            
            canvas.appendChild(div);
            
            // Draw Orthogonal 90-Degree Circuit Line
            if (node.parent_id && nodeMap[node.parent_id]) {
                const parent = nodeMap[node.parent_id];
                const fromX = parent.x + 77;
                const fromY = parent.y + 128;
                const toX = node.x + 77;
                const toY = node.y;
                const midY = (fromY + toY) / 2;
                
                const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
                let lineClass = "circuit-line";
                if (node.is_spillover) lineClass += " spillover";
                if (parent.id === 1) lineClass += " root-lead";
                
                path.setAttribute("class", lineClass);
                path.setAttribute("d", `M ${fromX} ${fromY} V ${midY} H ${toX} V ${toY}`);
                svgCanvas.appendChild(path);
            }
        });
        
        if (autoCenter && currentNodes.length > 0) {
            const root = currentNodes[0];
            panToCoordinate(root.x + 75, root.y + 120, 0.80);
        }
        
    } catch (err) {
        console.error("Failed to load matrix:", err);
    }
}

// Search HUD
const searchInput = document.getElementById('node-search-input');
const searchDropdown = document.getElementById('search-results-dropdown');

searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim().toLowerCase();
    if (!q) { searchDropdown.classList.add('d-none'); return; }
    
    const matches = currentNodes.filter(n => 
        n.name.toLowerCase().includes(q) || n.ref_code.toLowerCase().includes(q)
    ).slice(0, 5);
    
    if (matches.length === 0) {
        searchDropdown.innerHTML = '<div class="search-item text-muted">No citizen found</div>';
    } else {
        let html = '';
        matches.forEach(m => {
            html += `
                <div class="search-item" onclick="selectSearchNode(${m.id})">
                    <span><strong>${m.name}</strong> <small class="text-muted">(Gen ${m.depth})</small></span>
                    <span class="text-cyan">${m.ref_code}</span>
                </div>
            `;
        });
        searchDropdown.innerHTML = html;
    }
    searchDropdown.classList.remove('d-none');
});

window.selectSearchNode = (nodeId) => {
    searchDropdown.classList.add('d-none');
    searchInput.value = '';
    focusNode(nodeId);
};

document.addEventListener('click', (e) => {
    if (!document.getElementById('search-hud').contains(e.target)) {
        searchDropdown.classList.add('d-none');
    }
});

// Canvas Controls
document.getElementById('ctrl-zoom-in').addEventListener('click', () => {
    playSound('click'); panzoom.zoomIn({ animate: true });
});
document.getElementById('ctrl-zoom-out').addEventListener('click', () => {
    playSound('click'); panzoom.zoomOut({ animate: true });
});
document.getElementById('ctrl-reset').addEventListener('click', () => {
    playSound('click');
    if (currentNodes.length > 0) {
        panToCoordinate(currentNodes[0].x + 75, currentNodes[0].y + 120, 0.80);
    }
});

// Registration Modal
const modal = document.getElementById('modal');
const overlay = document.getElementById('overlay');
const addBtn = document.getElementById('add-btn');
const cancelBtn = document.getElementById('cancel-btn');
const modalCloseX = document.getElementById('modal-close-x');
const refInput = document.getElementById('node-ref-input');
const sponsorBanner = document.getElementById('sponsor-banner');
const lockoutNotice = document.getElementById('lockout-notice');

function openJoinModal() {
    playSound('click');
    modal.style.display = 'block';
    overlay.style.display = 'block';
    const urlParams = new URLSearchParams(window.location.search);
    const refCode = (urlParams.get('ref') || refInput.value || '').trim();
    if (systemStats.is_invite_only && !refCode) {
        lockoutNotice.classList.remove('d-none');
    } else {
        lockoutNotice.classList.add('d-none');
    }
}

function closeJoinModal() {
    modal.style.display = 'none';
    overlay.style.display = 'none';
}

addBtn.addEventListener('click', openJoinModal);
cancelBtn.addEventListener('click', closeJoinModal);
modalCloseX.addEventListener('click', closeJoinModal);
overlay.addEventListener('click', closeJoinModal);

// Instant Ref Code Validation
refInput.addEventListener('change', async () => {
    const code = refInput.value.trim();
    if (code.length === 8) {
        try {
            const res = await fetch(`/api/check-ref/${code}`);
            const data = await res.json();
            if (data.valid && data.sponsor) {
                document.getElementById('sponsor-banner-avatar').src = data.sponsor.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + data.sponsor.name;
                document.getElementById('sponsor-banner-name').textContent = `Invited by: ${data.sponsor.name}`;
                sponsorBanner.classList.remove('d-none');
                lockoutNotice.classList.add('d-none');
                document.getElementById('ref-status-hint').textContent = "Verified active sponsor!";
                document.getElementById('ref-status-hint').style.color = "#10b981";
            } else {
                sponsorBanner.classList.add('d-none');
                document.getElementById('ref-status-hint').textContent = "Code not recognized in matrix";
                document.getElementById('ref-status-hint').style.color = "#ef4444";
            }
        } catch (e) {}
    } else {
        sponsorBanner.classList.add('d-none');
    }
});

// URL Ref Parameter Detection
async function checkUrlReferral() {
    const urlParams = new URLSearchParams(window.location.search);
    const refCode = urlParams.get('ref');
    if (refCode) {
        refInput.value = refCode;
        try {
            const res = await fetch(`/api/check-ref/${refCode}`);
            const data = await res.json();
            if (data.valid && data.sponsor) {
                document.getElementById('sponsor-banner-avatar').src = data.sponsor.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + data.sponsor.name;
                document.getElementById('sponsor-banner-name').textContent = `Invited by: ${data.sponsor.name}`;
                sponsorBanner.classList.remove('d-none');
                setTimeout(() => { openJoinModal(); }, 600);
            }
        } catch (e) {}
    }
}

// Form Submission
document.getElementById('node-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('node-name').value.trim();
    const text = document.getElementById('node-text').value.trim();
    const refCode = refInput.value.trim();
    const fileInput = document.getElementById('node-image');
    
    if (!name || !text) {
        alert("Please enter your Name and Tagline!");
        return;
    }
    
    if (systemStats.is_invite_only && !refCode) {
        alert("Matrix Locked: 8-digit referral code is required!");
        return;
    }
    
    const submitBtn = document.getElementById('submit-btn');
    const submitBtnText = document.getElementById('submit-btn-text');
    submitBtn.disabled = true;
    submitBtnText.textContent = "CONNECTING...";
    
    const sendData = async (base64Img = '') => {
        try {
            const res = await fetch('/api/nodes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, text: text, image: base64Img, ref_id: refCode || null })
            });
            const result = await res.json();
            submitBtn.disabled = false;
            submitBtnText.textContent = "CONNECT NODE";
            
            if (res.status !== 200) {
                alert(result.error || "Failed to join matrix.");
                return;
            }
            
            playSound('success');
            closeJoinModal();
            document.getElementById('node-name').value = '';
            document.getElementById('node-text').value = '';
            fileInput.value = '';
            
            showToast(result.is_spillover 
                ? `⚡ Spillover Node connected under #${result.placed_under_id}!`
                : `🌐 Connected to Matrix!`
            );
            
            await loadMatrix(false);
            if (result.node_id) {
                setTimeout(() => {
                    focusNode(result.node_id);
                    if (nodeMap[result.node_id]) openInspector(nodeMap[result.node_id]);
                }, 350);
            }
        } catch (err) {
            submitBtn.disabled = false;
            submitBtnText.textContent = "CONNECT NODE";
            alert("Network transmission error.");
        }
    };
    
    if (fileInput.files && fileInput.files[0]) {
        const file = fileInput.files[0];
        if (file.size > 2.5 * 1024 * 1024) {
            alert("Image must be smaller than 2.5 MB.");
            submitBtn.disabled = false;
            submitBtnText.textContent = "CONNECT NODE";
            return;
        }
        const reader = new FileReader();
        reader.onload = (ev) => sendData(ev.target.result);
        reader.readAsDataURL(file);
    } else {
        sendData('');
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeJoinModal();
        document.getElementById('node-inspector').classList.add('d-none');
        detailedStatsCard.classList.add('d-none');
        toggleStatsBtn.classList.remove('open');
    }
});

document.addEventListener('DOMContentLoaded', async () => {
    await loadMatrix(true);
    await checkUrlReferral();
    setInterval(() => { loadMatrix(false); }, 20000);
});
