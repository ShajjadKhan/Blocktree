// ==========================================================================
// BLOCKTREE EDITORIAL - Matrix Engine
// Spatial Newsletter, Branching Discourse, Interactive Reader & Composer
// ==========================================================================

const canvasElem = document.getElementById("tree-canvas");
const panzoom = Panzoom(canvasElem, {
    maxScale: 3.5,
    minScale: 0.08,
    startScale: 0.80,
    canvas: true,
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
        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        if (type === 'click') {
            osc.frequency.setValueAtTime(480, now);
            osc.frequency.exponentialRampToValueAtTime(160, now + 0.05);
            gain.gain.setValueAtTime(0.06, now);
            gain.gain.linearRampToValueAtTime(0.001, now + 0.05);
            osc.start(now);
            osc.stop(now + 0.05);
        } else if (type === 'publish') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(320, now);
            osc.frequency.exponentialRampToValueAtTime(640, now + 0.12);
            osc.frequency.exponentialRampToValueAtTime(960, now + 0.22);
            gain.gain.setValueAtTime(0.08, now);
            gain.gain.linearRampToValueAtTime(0.001, now + 0.25);
            osc.start(now);
            osc.stop(now + 0.25);
        } else if (type === 'clap') {
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(520, now);
            osc.frequency.exponentialRampToValueAtTime(840, now + 0.08);
            gain.gain.setValueAtTime(0.09, now);
            gain.gain.linearRampToValueAtTime(0.001, now + 0.09);
            osc.start(now);
            osc.stop(now + 0.09);
        }
    } catch (e) {
        // Ignore audio failure
    }
}

// Sound Toggle
const soundBtn = document.getElementById('sound-toggle-btn');
const soundIcon = document.getElementById('sound-icon');

function updateSoundIcon() {
    if (soundEnabled) {
        soundIcon.className = 'bi bi-volume-up-fill';
        soundBtn.style.borderColor = 'var(--cyan)';
        soundBtn.style.color = 'var(--cyan)';
    } else {
        soundIcon.className = 'bi bi-volume-mute-fill';
        soundBtn.style.borderColor = 'rgba(255, 255, 255, 0.15)';
        soundBtn.style.color = 'var(--text-muted)';
    }
}
updateSoundIcon();

soundBtn.addEventListener('click', () => {
    soundEnabled = !soundEnabled;
    localStorage.setItem('blocktree_sound', soundEnabled);
    updateSoundIcon();
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

// Mathematically Exact Camera Centering
function panToCoordinate(targetX, targetY, scale = 0.85) {
    const container = document.getElementById('canvas-container');
    const viewW = container.clientWidth || window.innerWidth;
    const viewH = container.clientHeight || window.innerHeight;
    const canvasW = canvasElem.offsetWidth || 12000;
    const canvasH = canvasElem.offsetHeight || 12000;
    
    // Panzoom applies scale(scale) translate(panX, panY) with transform-origin at canvas center
    const panX = (viewW / (2 * scale)) + (canvasW / 2) * (1 - 1 / scale) - targetX;
    const panY = (viewH / (2 * scale)) + (canvasH / 2) * (1 - 1 / scale) - targetY;
    
    panzoom.zoom(scale, { animate: true });
    panzoom.pan(panX, panY, { animate: true });
}

// Global State
let currentNodes = [];
let nodeMap = {};
let activeReaderNodeId = null;

// Category Badge Helper
function getCategoryClass(cat) {
    if (!cat) return 'cat-perspective';
    const c = cat.toLowerCase();
    if (c.includes('news')) return 'cat-newsletter';
    if (c.includes('counter')) return 'cat-counterpoint';
    if (c.includes('deep')) return 'cat-deep-dive';
    if (c.includes('disc')) return 'cat-discussion';
    return 'cat-perspective';
}

function getCardCategoryClass(cat) {
    if (!cat) return 'card-cat-perspective';
    const c = cat.toLowerCase();
    if (c.includes('news')) return 'card-cat-newsletter';
    if (c.includes('counter')) return 'card-cat-counterpoint';
    if (c.includes('deep')) return 'card-cat-deep-dive';
    if (c.includes('disc')) return 'card-cat-discussion';
    return 'card-cat-perspective';
}

function getBranchClass(cat) {
    if (!cat) return 'branch-perspective';
    const c = cat.toLowerCase();
    if (c.includes('news')) return 'branch-newsletter';
    if (c.includes('counter')) return 'branch-counterpoint';
    if (c.includes('deep')) return 'branch-deep-dive';
    if (c.includes('disc')) return 'branch-discussion';
    return 'branch-perspective';
}

// Focus Node on Matrix
function focusNode(nodeId, scale = 1.05) {
    const node = nodeMap[nodeId];
    if (node) {
        playSound('click');
        // Card is 265px wide, ~160px tall
        panToCoordinate(node.x + 132.5, node.y + 80, scale);
        
        const elem = document.querySelector(`.editorial-card[data-id="${nodeId}"]`);
        if (elem) {
            elem.style.transform = 'translateY(-6px) scale(1.08)';
            elem.style.boxShadow = '0 0 35px var(--cyan)';
            elem.style.borderColor = 'var(--cyan)';
            setTimeout(() => {
                elem.style.transform = '';
                elem.style.boxShadow = '';
                elem.style.borderColor = '';
            }, 1800);
        }
    }
}

// Load Matrix
async function loadMatrix(autoCenter = false) {
    try {
        const res = await fetch('/api/nodes');
        const data = await res.json();
        
        currentNodes = data.nodes || [];
        nodeMap = {};
        currentNodes.forEach(n => { nodeMap[n.id] = n; });
        
        // 1. Update Telemetry Status
        if (data.stats) {
            document.getElementById('stat-editions').textContent = data.stats.total_editions || 0;
            document.getElementById('stat-replies').textContent = data.stats.total_replies || 0;
            document.getElementById('stat-claps').textContent = data.stats.total_claps || 0;
        }
        
        // 2. Populate Trending Stories
        const trendingList = document.getElementById('trending-list');
        if (data.trending && data.trending.length > 0) {
            let tHtml = '';
            data.trending.forEach((item, i) => {
                const medal = i === 0 ? '🔥' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : `#${i+1}`));
                tHtml += `
                    <div class="trend-row" onclick="openReader(${item.id})" title="Read article & view on tree">
                        <div class="trend-main">
                            <span class="trend-title">${item.title}</span>
                            <span class="trend-author">${medal} by @${item.name}</span>
                        </div>
                        <div class="trend-stats">
                            <i class="bi bi-heart-fill text-magenta"></i> ${item.claps}
                        </div>
                    </div>
                `;
            });
            trendingList.innerHTML = tHtml;
        } else {
            trendingList.innerHTML = '<div class="leader-loading">No stories published yet</div>';
        }
        
        // 3. Populate Top Writers
        const authorsList = document.getElementById('authors-list');
        if (data.leaders && data.leaders.length > 0) {
            let aHtml = '';
            data.leaders.forEach((w, i) => {
                const medal = i === 0 ? '👑' : `#${i+1}`;
                aHtml += `
                    <div class="author-row" onclick="focusNode(${w.id})" title="Jump to author on canvas">
                        <div class="author-left">
                            <img src="${w.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + w.name}" class="author-mini-img" alt="">
                            <span class="author-name-text">${w.name}</span>
                        </div>
                        <div class="trend-stats">
                            <i class="bi bi-heart-fill text-gold"></i> ${w.total_claps}
                        </div>
                    </div>
                `;
            });
            authorsList.innerHTML = aHtml;
        } else {
            authorsList.innerHTML = '<div class="leader-loading">No writers ranked yet</div>';
        }
        
        // 4. Render Canvas Cards & Connecting Lines
        const svgCanvas = document.getElementById('svg-canvas');
        const existingPaths = svgCanvas.querySelectorAll('.tree-branch-line');
        existingPaths.forEach(p => p.remove());
        
        let nodesContainer = document.getElementById('nodes');
        if (!nodesContainer) {
            nodesContainer = document.createElement('div');
            nodesContainer.id = 'nodes';
            canvasElem.appendChild(nodesContainer);
        }
        nodesContainer.innerHTML = '';
        
        // Render Nodes
        currentNodes.forEach(node => {
            const card = document.createElement('div');
            card.className = `editorial-card ${getCardCategoryClass(node.category)}`;
            card.dataset.id = node.id;
            card.style.left = `${node.x}px`;
            card.style.top = `${node.y}px`;
            
            const catClass = getCategoryClass(node.category);
            const parent = nodeMap[node.parent_id];
            
            // Lineage badge: who replied to whom!
            let replyBadgeHtml = '';
            if (parent) {
                replyBadgeHtml = `
                    <div class="card-reply-lineage" title="Replying to ${parent.title}">
                        <i class="bi bi-reply-fill"></i>
                        <span>↳ in reply to <strong>@${parent.name}</strong></span>
                    </div>
                `;
            }
            
            card.innerHTML = `
                <div class="card-top-row">
                    <span class="badge-cat ${catClass}">${node.category}</span>
                    <span class="card-read-time">${node.read_time}</span>
                </div>
                
                <h3 class="card-headline">${node.title}</h3>
                <p class="card-excerpt">${node.text}</p>
                
                ${replyBadgeHtml}
                
                <div class="card-bottom-row">
                    <div class="card-author-info">
                        <img src="${node.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + node.name}" class="card-avatar" alt="">
                        <span class="card-author-name">${node.name}</span>
                    </div>
                    
                    <div class="card-actions-quick">
                        <span class="card-metric-tag" title="${node.claps} reader claps">
                            <i class="bi bi-heart-fill text-magenta"></i> ${node.claps}
                        </span>
                        <span class="card-metric-tag" title="${node.reply_count} direct replies">
                            <i class="bi bi-chat-dots-fill text-cyan"></i> ${node.reply_count}
                        </span>
                        <button class="btn-card-read" onclick="event.stopPropagation(); openReader(${node.id})">READ →</button>
                    </div>
                </div>
            `;
            
            card.addEventListener('click', () => {
                openReader(node.id);
            });
            
            nodesContainer.appendChild(card);
            
            // Render Curved Bezier Branch Line (from Parent bottom to Child top)
            if (parent) {
                const fromX = parent.x + 132.5;
                const fromY = parent.y + 165;
                const toX = node.x + 132.5;
                const toY = node.y;
                const midY = (fromY + toY) / 2;
                
                const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
                path.setAttribute("class", `tree-branch-line ${getBranchClass(node.category)}`);
                path.setAttribute("d", `M ${fromX} ${fromY} C ${fromX} ${midY}, ${toX} ${midY}, ${toX} ${toY}`);
                path.setAttribute("data-child", node.id);
                path.setAttribute("data-parent", parent.id);
                
                svgCanvas.appendChild(path);
            }
        });
        
        // Auto-center on initial load
        if (autoCenter && currentNodes.length > 0) {
            const first = currentNodes[0];
            panToCoordinate(first.x + 132.5, first.y + 80, 0.80);
        }
        
    } catch (err) {
        console.error("Failed to load editorial matrix:", err);
    }
}

// ==========================================================================
// The Cyber-Editorial Reader Drawer
// ==========================================================================
const readerDrawer = document.getElementById('article-reader-drawer');
const readerCloseBtn = document.getElementById('reader-close-btn');
const readerPanBtn = document.getElementById('reader-pan-btn');
const readerClapBtn = document.getElementById('reader-clap-btn');
const readerReplyBtn = document.getElementById('reader-reply-btn');
const readerShareBtn = document.getElementById('reader-share-btn');
const readerJumpParentBtn = document.getElementById('reader-jump-parent-btn');

async function openReader(nodeId) {
    playSound('click');
    activeReaderNodeId = nodeId;
    
    try {
        const res = await fetch(`/api/nodes/${nodeId}`);
        const data = await res.json();
        const node = data.node || nodeMap[nodeId];
        if (!node) return;
        
        // Populate Meta
        document.getElementById('reader-category-pill').className = `badge-cat ${getCategoryClass(node.category)}`;
        document.getElementById('reader-category-pill').textContent = node.category;
        document.getElementById('reader-read-time').innerHTML = `<i class="bi bi-clock"></i> ${node.read_time}`;
        
        document.getElementById('reader-title').textContent = node.title;
        document.getElementById('reader-author-name').textContent = node.name;
        document.getElementById('reader-author-avatar').src = node.image || `https://api.dicebear.com/7.x/bottts/svg?seed=${node.name}`;
        document.getElementById('reader-date').textContent = node.created_at || 'Recently published';
        
        document.getElementById('reader-cover-img').src = node.cover_image || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&auto=format&fit=crop&q=80';
        
        document.getElementById('reader-quick-claps').textContent = node.claps || 0;
        document.getElementById('reader-quick-replies').textContent = node.reply_count || 0;
        document.getElementById('reader-clap-badge').textContent = node.claps || 0;
        
        // In Reply To Breadcrumb
        const breadcrumb = document.getElementById('reader-reply-breadcrumb');
        if (node.parent_id && node.parent_title) {
            document.getElementById('reader-parent-title').textContent = node.parent_title;
            document.getElementById('reader-parent-author').textContent = `@${node.parent_name || 'Author'}`;
            breadcrumb.classList.remove('d-none');
            
            readerJumpParentBtn.onclick = () => {
                openReader(node.parent_id);
                focusNode(node.parent_id);
            };
        } else {
            breadcrumb.classList.add('d-none');
        }
        
        // Render Markdown Body
        const bodyElem = document.getElementById('reader-content-body');
        if (typeof marked !== 'undefined' && node.content) {
            bodyElem.innerHTML = marked.parse(node.content);
        } else {
            bodyElem.innerHTML = `<p>${node.content || node.text}</p>`;
        }
        
        // Render Direct Branch Replies
        const repliesContainer = document.getElementById('reader-replies-container');
        const repliesCount = document.getElementById('reader-replies-count');
        
        const replies = node.replies || currentNodes.filter(n => n.parent_id === node.id);
        repliesCount.textContent = replies.length;
        
        if (replies.length === 0) {
            repliesContainer.innerHTML = `
                <div class="branch-reply-card" style="text-align: center; color: var(--text-muted); font-size: 11px;">
                    No branching perspectives yet. Be the first to reply as a node!
                </div>
            `;
        } else {
            let rHtml = '';
            replies.forEach(r => {
                rHtml += `
                    <div class="branch-reply-card" onclick="openReader(${r.id}); focusNode(${r.id})">
                        <div class="reply-card-top">
                            <span class="badge-cat ${getCategoryClass(r.category)}">${r.category}</span>
                            <span class="text-gold"><i class="bi bi-heart-fill"></i> ${r.claps}</span>
                        </div>
                        <h4 class="reply-card-title">${r.title}</h4>
                        <p class="reply-card-snippet">${r.text}</p>
                        <div class="reply-card-footer">
                            <span>by @${r.name}</span>
                            <span class="text-cyan"><i class="bi bi-diagram-3"></i> View branch →</span>
                        </div>
                    </div>
                `;
            });
            repliesContainer.innerHTML = rHtml;
        }
        
        readerDrawer.classList.remove('d-none');
        
    } catch (e) {
        console.error("Failed to load article:", e);
    }
}

// Reader Actions
readerCloseBtn.addEventListener('click', () => {
    readerDrawer.classList.add('d-none');
    activeReaderNodeId = null;
});

readerPanBtn.addEventListener('click', () => {
    if (activeReaderNodeId) focusNode(activeReaderNodeId, 1.15);
});

readerClapBtn.addEventListener('click', async () => {
    if (!activeReaderNodeId) return;
    playSound('clap');
    try {
        const res = await fetch(`/api/nodes/${activeReaderNodeId}/clap`, { method: 'POST' });
        const data = await res.json();
        if (data.claps) {
            document.getElementById('reader-clap-badge').textContent = data.claps;
            document.getElementById('reader-quick-claps').textContent = data.claps;
            
            // Update nodeMap and canvas card
            if (nodeMap[activeReaderNodeId]) {
                nodeMap[activeReaderNodeId].claps = data.claps;
                const card = document.querySelector(`.editorial-card[data-id="${activeReaderNodeId}"] .card-metric-tag`);
                if (card) card.innerHTML = `<i class="bi bi-heart-fill text-magenta"></i> ${data.claps}`;
            }
            
            // Visual bounce
            readerClapBtn.style.transform = 'scale(1.15)';
            setTimeout(() => { readerClapBtn.style.transform = ''; }, 200);
        }
    } catch (e) {
        console.error("Clap failed:", e);
    }
});

readerReplyBtn.addEventListener('click', () => {
    if (!activeReaderNodeId) return;
    const parentNode = nodeMap[activeReaderNodeId];
    if (parentNode) {
        openComposer(parentNode.id, parentNode.title, parentNode.name);
    }
});

readerShareBtn.addEventListener('click', () => {
    if (!activeReaderNodeId) return;
    playSound('click');
    const url = `${window.location.origin}/?article=${activeReaderNodeId}`;
    navigator.clipboard.writeText(url);
    showToast("Article Deep-link copied to clipboard!");
});

// ==========================================================================
// Article & Branch Reply Composer Modal
// ==========================================================================
const overlay = document.getElementById('overlay');
const composerModal = document.getElementById('composer-modal');
const composerCloseX = document.getElementById('composer-close-x');
const composerCancelBtn = document.getElementById('composer-cancel-btn');
const form = document.getElementById('article-form');

function openComposer(parentId = null, parentTitle = null, parentAuthor = null) {
    playSound('click');
    document.getElementById('form-parent-id').value = parentId || '';
    
    const banner = document.getElementById('composer-reply-target-banner');
    const modalTitle = document.getElementById('composer-modal-title');
    const submitText = document.getElementById('composer-submit-text');
    const catSelect = document.getElementById('form-category');
    
    if (parentId) {
        modalTitle.innerHTML = `<i class="bi bi-diagram-3-fill text-cyan"></i> Write Branch Reply`;
        document.getElementById('composer-target-title').textContent = parentTitle || 'Parent Article';
        document.getElementById('composer-target-author').textContent = `by @${parentAuthor || 'Author'}`;
        banner.classList.remove('d-none');
        submitText.textContent = "PUBLISH BRANCH REPLY";
        catSelect.value = "Perspective";
    } else {
        modalTitle.innerHTML = `<i class="bi bi-pen-fill text-cyan"></i> Publish New Edition`;
        banner.classList.add('d-none');
        submitText.textContent = "PUBLISH TO MATRIX";
        catSelect.value = "Newsletter";
    }
    
    overlay.style.display = 'block';
    composerModal.classList.remove('d-none');
    document.getElementById('form-title').focus();
}

function closeComposer() {
    overlay.style.display = 'none';
    composerModal.classList.add('d-none');
}

composerCloseX.addEventListener('click', closeComposer);
composerCancelBtn.addEventListener('click', closeComposer);
overlay.addEventListener('click', closeComposer);

// Header Publish Button & Floating Add Button
document.getElementById('header-publish-btn').addEventListener('click', () => {
    openComposer(null);
});

document.getElementById('add-btn').addEventListener('click', () => {
    openComposer(null);
});

// Submit Form
form.addEventListener('submit', async () => {
    const parentId = document.getElementById('form-parent-id').value;
    const category = document.getElementById('form-category').value;
    const author = document.getElementById('form-author').value.trim();
    const title = document.getElementById('form-title').value.trim();
    const content = document.getElementById('form-content').value.trim();
    
    const checkedPreset = document.querySelector('input[name="cover-preset"]:checked');
    const coverImage = checkedPreset ? checkedPreset.value : '';
    
    if (!title || !content) {
        showToast("Please provide both a Title and Article Content!", true);
        return;
    }
    
    const submitBtn = document.getElementById('composer-submit-btn');
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<i class="bi bi-arrow-repeat spin"></i> Publishing...`;
    
    try {
        const payload = {
            title: title,
            name: author || "Anonymous Thinker",
            category: category,
            content: content,
            parent_id: parentId || null,
            cover_image: coverImage
        };
        
        const res = await fetch('/api/nodes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        
        if (res.ok && data.status === 'success') {
            playSound('publish');
            showToast(parentId ? "⚡ Branch Reply published successfully!" : "📰 New Newsletter Edition published!");
            closeComposer();
            form.reset();
            
            // Reload matrix and smoothly focus on the new node
            await loadMatrix(false);
            if (data.node) {
                setTimeout(() => {
                    focusNode(data.node.id, 1.15);
                    openReader(data.node.id);
                }, 300);
            }
        } else {
            showToast(data.error || "Failed to publish article", true);
        }
    } catch (err) {
        showToast("Network error. Could not connect to matrix.", true);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<i class="bi bi-send-fill"></i> <span id="composer-submit-text">PUBLISH TO MATRIX</span>`;
    }
});

// ==========================================================================
// Scoreboard Tabs & Search
// ==========================================================================
const tabTrending = document.getElementById('tab-trending');
const tabAuthors = document.getElementById('tab-authors');
const trendingList = document.getElementById('trending-list');
const authorsList = document.getElementById('authors-list');

tabTrending.addEventListener('click', () => {
    playSound('click');
    tabTrending.classList.add('active');
    tabAuthors.classList.remove('active');
    trendingList.classList.remove('d-none');
    authorsList.classList.add('d-none');
});

tabAuthors.addEventListener('click', () => {
    playSound('click');
    tabAuthors.classList.add('active');
    tabTrending.classList.remove('active');
    authorsList.classList.remove('d-none');
    trendingList.classList.add('d-none');
});

// Search HUD
const searchInput = document.getElementById('node-search-input');
const searchDropdown = document.getElementById('search-results-dropdown');

searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim().toLowerCase();
    if (!q) { searchDropdown.classList.add('d-none'); return; }
    
    const matches = currentNodes.filter(n => 
        n.title.toLowerCase().includes(q) || 
        n.name.toLowerCase().includes(q) ||
        n.category.toLowerCase().includes(q) ||
        n.text.toLowerCase().includes(q)
    ).slice(0, 6);
    
    if (matches.length === 0) {
        searchDropdown.innerHTML = '<div class="search-item text-muted">No matching articles found</div>';
    } else {
        let html = '';
        matches.forEach(m => {
            html += `
                <div class="search-item" onclick="selectSearchNode(${m.id})">
                    <span class="search-item-title">${m.title}</span>
                    <div class="search-item-meta">
                        <span>by @${m.name}</span>
                        <span class="text-cyan">${m.category}</span>
                    </div>
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
    openReader(nodeId);
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
        const root = currentNodes[0];
        panToCoordinate(root.x + 132.5, root.y + 80, 0.80);
    } else {
        panToCoordinate(3000, 200, 0.80);
    }
});

// Deep Linking Check
async function checkDeepLink() {
    const params = new URLSearchParams(window.location.search);
    const targetId = params.get('article') || params.get('node');
    if (targetId) {
        const nid = parseInt(targetId);
        if (nodeMap[nid]) {
            setTimeout(() => {
                focusNode(nid);
                openReader(nid);
            }, 500);
        }
    }
}

// Keyboard Navigation
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeComposer();
        readerDrawer.classList.add('d-none');
        activeReaderNodeId = null;
    }
});

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
    await loadMatrix(true);
    await checkDeepLink();
    setInterval(() => { loadMatrix(false); }, 25000);
});
