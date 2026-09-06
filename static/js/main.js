// BlockTree - High-End Matrix Engine & Circuit Canvas

// Panzoom Setup
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

// Web Audio API Synthesizer (Zero External Dependencies)
let soundEnabled = localStorage.getItem('blocktree_sound') !== 'false';
let audioCtx = null;

function getAudioContext() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
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
            osc.frequency.exponentialRampToValueAtTime(1200, now + 0.06);
            gain.gain.setValueAtTime(0.08, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.06);
            osc.start(now);
            osc.stop(now + 0.06);
        } else if (type === 'success') {
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(523.25, now); // C5
            osc.frequency.setValueAtTime(659.25, now + 0.08); // E5
            osc.frequency.setValueAtTime(783.99, now + 0.16); // G5
            osc.frequency.setValueAtTime(1046.50, now + 0.24); // C6
            gain.gain.setValueAtTime(0.12, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
            osc.start(now);
            osc.stop(now + 0.4);
        } else if (type === 'copy') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(1200, now);
            osc.frequency.exponentialRampToValueAtTime(600, now + 0.08);
            gain.gain.setValueAtTime(0.06, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
            osc.start(now);
            osc.stop(now + 0.08);
        }
    } catch (e) {
        // Audio policy ignore
    }
}

// Global Matrix State
let currentNodes = [];
let nodeMap = {};
let systemStats = {};
let inviterInfo = null;

// Audio Toggle Button
const audioBtn = document.getElementById('audio-toggle');
const audioIcon = document.getElementById('audio-icon');
function updateAudioUI() {
    if (soundEnabled) {
        audioIcon.className = 'bi bi-volume-up-fill text-cyan';
    } else {
        audioIcon.className = 'bi bi-volume-mute-fill opacity-50';
    }
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
    
    setTimeout(() => {
        toast.classList.add('d-none');
    }, 4500);
}

// Camera Pan & Zoom Helper
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
        panToCoordinate(node.x + 80, node.y + 70, 1.15);
        
        // Highlight node card visually
        const elem = document.querySelector(`.node[data-id="${nodeId}"]`);
        if (elem) {
            elem.style.transform = 'translateY(-8px) scale(1.15)';
            elem.style.borderColor = '#00f3ff';
            elem.style.boxShadow = '0 0 35px #00f3ff';
            setTimeout(() => {
                elem.style.transform = '';
                elem.style.borderColor = '';
                elem.style.boxShadow = '';
            }, 1800);
        }
    }
}

// Copy Referral Link
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

// Node Inspector Drawer
function openInspector(node) {
    playSound('click');
    const drawer = document.getElementById('node-inspector');
    
    document.getElementById('insp-avatar').src = node.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + node.name;
    document.getElementById('insp-name').textContent = node.name;
    document.getElementById('insp-text').textContent = `"${node.text}"`;
    
    const spilloverTag = document.getElementById('insp-spillover-tag');
    if (node.is_spillover) {
        spilloverTag.classList.remove('d-none');
    } else {
        spilloverTag.classList.add('d-none');
    }
    
    document.getElementById('insp-depth').textContent = `GEN ${node.depth}`;
    document.getElementById('insp-direct-refs').textContent = `${node.direct_refs} Recruits`;
    document.getElementById('insp-grid-slots').textContent = `${node.direct_children} / 5 Filled`;
    document.getElementById('insp-joined').textContent = node.created_at || 'Genesis Initial';
    
    const sponsorBtn = document.getElementById('insp-jump-sponsor');
    sponsorBtn.textContent = node.sponsor_name;
    sponsorBtn.onclick = () => {
        if (node.sponsor_id) focusNode(node.sponsor_id);
    };
    
    const parentBtn = document.getElementById('insp-jump-parent');
    parentBtn.textContent = node.parent_name;
    parentBtn.onclick = () => {
        if (node.parent_id) focusNode(node.parent_id);
    };
    
    const refLinkInput = document.getElementById('insp-ref-link');
    const fullLink = `${window.location.origin}/?ref=${node.ref_code}`;
    refLinkInput.value = fullLink;
    
    document.getElementById('insp-copy-btn').onclick = () => {
        playSound('copy');
        navigator.clipboard.writeText(fullLink);
        showToast("Referral Link copied to clipboard!");
    };
    
    document.getElementById('insp-focus-btn').onclick = () => {
        focusNode(node.id);
    };
    
    drawer.classList.add('open');
}

document.getElementById('inspector-close').addEventListener('click', () => {
    document.getElementById('node-inspector').classList.remove('open');
});

// Load Matrix Telemetry & Render Grid
async function loadMatrix(autoCenter = false) {
    try {
        const res = await fetch('/api/nodes');
        const data = await res.json();
        
        currentNodes = data.nodes || [];
        systemStats = data.stats || {};
        nodeMap = {};
        
        currentNodes.forEach(n => {
            nodeMap[n.id] = n;
        });
        
        // 1. Update Telemetry HUD
        document.getElementById('stat-total-users').textContent = systemStats.total_users || 0;
        document.getElementById('stat-spillovers').textContent = systemStats.total_spillovers || 0;
        document.getElementById('stat-depth').textContent = `GEN ${systemStats.max_depth || 0}`;
        
        // Live visitors random simulation
        const liveCount = 10 + Math.floor(Math.random() * 8);
        document.getElementById('live-visitors').textContent = liveCount;
        
        // 2. Update Scarcity / FOMO Progress
        const ratioText = `${systemStats.total_users} / ${systemStats.genesis_limit}`;
        document.getElementById('scarcity-ratio').textContent = ratioText;
        
        const pct = Math.min(100, (systemStats.total_users / systemStats.genesis_limit) * 100);
        document.getElementById('scarcity-progress-fill').style.width = `${pct}%`;
        
        const addBtn = document.getElementById('add-btn');
        const addBtnText = document.getElementById('add-btn-text');
        const phaseBadge = document.getElementById('hud-phase-badge');
        
        if (systemStats.is_invite_only) {
            phaseBadge.textContent = "INVITE-ONLY (LOCKED)";
            phaseBadge.classList.add('locked');
            document.getElementById('scarcity-title').textContent = "Genesis Full - Exclusivity Active";
            document.getElementById('scarcity-subtext').textContent = "Strict referral invitation code required for all new citizens.";
            addBtnText.textContent = "INVITE-ONLY ACCESS";
            addBtn.classList.add('locked-btn');
        } else {
            phaseBadge.textContent = "GENESIS PHASE";
            phaseBadge.classList.remove('locked');
            document.getElementById('scarcity-title').textContent = "Genesis Open Access";
            document.getElementById('scarcity-subtext').textContent = `${systemStats.genesis_slots_left} slots remain before matrix locks to Invite-Only.`;
            addBtnText.textContent = "JOIN MATRIX";
            addBtn.classList.remove('locked-btn');
        }
        
        // 3. Populate Leaderboard
        const leaderList = document.getElementById('leader-list');
        if (!data.leaders || data.leaders.length === 0) {
            leaderList.innerHTML = '<div class="leader-loading">No referrals recorded yet</div>';
        } else {
            let html = '';
            data.leaders.forEach((l, i) => {
                const rankClass = i === 0 ? 'top-1' : (i === 1 ? 'top-2' : (i === 2 ? 'top-3' : ''));
                const medal = i === 0 ? '🥇' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : `#${i+1}`));
                html += `
                    <div class="leader-row" onclick="focusNode(${l.id})">
                        <span class="leader-rank ${rankClass}">${medal}</span>
                        <img class="leader-avatar" src="${l.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + l.name}" alt="">
                        <span class="leader-name" title="${l.name}">${l.name}</span>
                        <span class="leader-count">${l.count} Ref</span>
                    </div>
                `;
            });
            leaderList.innerHTML = html;
        }
        
        // 4. Render Nodes on Canvas
        const canvas = document.getElementById('tree-canvas');
        const svgCanvas = document.getElementById('svg-canvas');
        
        // Clear previous nodes (preserve SVG)
        canvas.querySelectorAll('.node').forEach(el => el.remove());
        
        // Clear previous SVG paths
        svgCanvas.querySelectorAll('path.circuit-line').forEach(p => p.remove());
        
        currentNodes.forEach(node => {
            const div = document.createElement('div');
            div.className = 'node';
            div.setAttribute('data-id', node.id);
            div.style.left = `${node.x}px`;
            div.style.top = `${node.y}px`;
            
            if (node.id === 1 || node.parent_id === null) {
                div.classList.add('root-node');
            } else if (node.is_spillover) {
                div.classList.add('spillover-node');
            }
            
            // Slots dots representation
            const filledCount = node.direct_children || 0;
            let slotsDots = '';
            for (let s = 0; s < 5; s++) {
                slotsDots += (s < filledCount) ? '●' : '○';
            }
            
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
            
            // 5. Draw Orthogonal 90-Degree Circuit Line from Parent
            if (node.parent_id && nodeMap[node.parent_id]) {
                const parent = nodeMap[node.parent_id];
                const fromX = parent.x + 80;
                const fromY = parent.y + 135;
                const toX = node.x + 80;
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
        
        // 6. Update Activity Ticker with Recent Joins
        if (currentNodes.length > 1) {
            const latest = currentNodes[currentNodes.length - 1];
            const tickerEl = document.getElementById('ticker-text');
            if (latest.is_spillover) {
                tickerEl.innerHTML = `⚡ <strong>${latest.name}</strong> placed via spillover beneath <strong>${latest.parent_name}</strong> (Sponsored by ${latest.sponsor_name})`;
            } else {
                tickerEl.innerHTML = `🌐 <strong>${latest.name}</strong> joined the matrix under <strong>${latest.parent_name}</strong> (Gen ${latest.depth})`;
            }
        }
        
        // Auto-center on initial load
        if (autoCenter && currentNodes.length > 0) {
            const root = currentNodes[0];
            panToCoordinate(root.x + 80, root.y + 150, 0.85);
        }
        
    } catch (err) {
        console.error("Failed to load matrix:", err);
    }
}

// Search & Fast Jump HUD
const searchInput = document.getElementById('node-search-input');
const searchDropdown = document.getElementById('search-results-dropdown');

searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim().toLowerCase();
    if (!q) {
        searchDropdown.classList.add('d-none');
        return;
    }
    
    const matches = currentNodes.filter(n => 
        n.name.toLowerCase().includes(q) || 
        n.ref_code.toLowerCase().includes(q)
    ).slice(0, 6);
    
    if (matches.length === 0) {
        searchDropdown.innerHTML = '<div class="search-item text-muted">No citizen found</div>';
        searchDropdown.classList.remove('d-none');
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
        searchDropdown.classList.remove('d-none');
    }
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

// Floating Canvas Controls
document.getElementById('ctrl-zoom-in').addEventListener('click', () => {
    playSound('click');
    panzoom.zoomIn({ animate: true });
});

document.getElementById('ctrl-zoom-out').addEventListener('click', () => {
    playSound('click');
    panzoom.zoomOut({ animate: true });
});

document.getElementById('ctrl-reset').addEventListener('click', () => {
    playSound('click');
    if (currentNodes.length > 0) {
        panToCoordinate(currentNodes[0].x + 80, currentNodes[0].y + 150, 0.85);
    }
});

document.getElementById('ctrl-fit').addEventListener('click', () => {
    playSound('click');
    panzoom.zoom(0.22, { animate: true });
});

// Registration Modal & URL Referral Handling
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
    
    // Check if invite-only mode is active and no ref code in URL
    const urlParams = new URLSearchParams(window.location.search);
    const refCode = (urlParams.get('ref') || refInput.value || '').trim();
    
    if (systemStats.is_invite_only && !refCode) {
        lockoutNotice.classList.remove('d-none');
        document.getElementById('ref-status-hint').textContent = "Mandatory: Enter valid 8-digit sponsor code to register.";
        document.getElementById('ref-status-hint').style.color = "#d946ef";
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

// Instant Validation on Referral Code Input
refInput.addEventListener('change', async () => {
    const code = refInput.value.trim();
    if (code.length === 8) {
        try {
            const res = await fetch(`/api/check-ref/${code}`);
            const data = await res.json();
            if (data.valid && data.sponsor) {
                document.getElementById('sponsor-banner-avatar').src = data.sponsor.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + data.sponsor.name;
                document.getElementById('sponsor-banner-name').textContent = `Invited by: ${data.sponsor.name}`;
                document.getElementById('sponsor-banner-sub').textContent = `${data.sponsor.direct_referrals} members sponsored • 1x5 auto-spillover active`;
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

// Auto-Detect Referral Code from URL
async function checkUrlReferral() {
    const urlParams = new URLSearchParams(window.location.search);
    const refCode = urlParams.get('ref');
    
    if (refCode) {
        refInput.value = refCode;
        try {
            const res = await fetch(`/api/check-ref/${refCode}`);
            const data = await res.json();
            if (data.valid && data.sponsor) {
                inviterInfo = data.sponsor;
                document.getElementById('sponsor-banner-avatar').src = inviterInfo.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + inviterInfo.name;
                document.getElementById('sponsor-banner-name').textContent = `Invited by: ${inviterInfo.name}`;
                document.getElementById('sponsor-banner-sub').textContent = `${inviterInfo.direct_referrals} members recruited • Verified invitation`;
                sponsorBanner.classList.remove('d-none');
                
                // Automatically open join modal for invited visitors
                setTimeout(() => {
                    openJoinModal();
                }, 600);
            }
        } catch (e) {}
    }
}

// Form Submission & Anti-Spam UX
document.getElementById('node-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('node-name').value.trim();
    const text = document.getElementById('node-text').value.trim();
    const refCode = refInput.value.trim();
    const fileInput = document.getElementById('node-image');
    
    if (!name || !text) {
        alert("Please provide both your Name and Tagline!");
        return;
    }
    
    if (systemStats.is_invite_only && !refCode) {
        alert("Matrix Locked: An invitation referral code is required to join now that 100 Genesis slots are filled!");
        return;
    }
    
    const submitBtn = document.getElementById('submit-btn');
    const submitBtnText = document.getElementById('submit-btn-text');
    submitBtn.disabled = true;
    submitBtnText.textContent = "TRANSMITTING...";
    
    const sendData = async (base64Img = '') => {
        try {
            const res = await fetch('/api/nodes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    text: text,
                    image: base64Img,
                    ref_id: refCode || null
                })
            });
            
            const result = await res.json();
            submitBtn.disabled = false;
            submitBtnText.textContent = "TRANSMIT & DEPLOY";
            
            if (res.status !== 200) {
                alert(result.error || "Connection to matrix failed.");
                return;
            }
            
            // Success!
            playSound('success');
            closeJoinModal();
            
            // Clear inputs
            document.getElementById('node-name').value = '';
            document.getElementById('node-text').value = '';
            fileInput.value = '';
            
            showToast(result.is_spillover 
                ? `⚡ Node Deployed via Spillover under ID #${result.placed_under_id}!` 
                : `🌐 Node Successfully Integrated into Matrix!`
            );
            
            // Reload grid and focus on newly created node
            await loadMatrix(false);
            if (result.node_id) {
                setTimeout(() => {
                    focusNode(result.node_id);
                    if (nodeMap[result.node_id]) {
                        openInspector(nodeMap[result.node_id]);
                    }
                }, 400);
            }
            
        } catch (err) {
            submitBtn.disabled = false;
            submitBtnText.textContent = "TRANSMIT & DEPLOY";
            alert("Network transmission failed. Check server status.");
        }
    };
    
    if (fileInput.files && fileInput.files[0]) {
        const file = fileInput.files[0];
        if (file.size > 2.5 * 1024 * 1024) {
            alert("Profile image must be smaller than 2.5 MB.");
            submitBtn.disabled = false;
            submitBtnText.textContent = "TRANSMIT & DEPLOY";
            return;
        }
        const reader = new FileReader();
        reader.onload = (ev) => sendData(ev.target.result);
        reader.readAsDataURL(file);
    } else {
        sendData('');
    }
});

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
    await loadMatrix(true);
    await checkUrlReferral();
    
    // Auto-poll matrix every 25 seconds for live community updates
    setInterval(() => {
        loadMatrix(false);
    }, 25000);
});
