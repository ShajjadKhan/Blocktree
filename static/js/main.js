// ==========================================================================
// BLOCKTREE EDITORIAL - Matrix Engine
// Spatial Newsletter, Branching Discourse, Verified Authors & Series Writing
// ==========================================================================

const canvasElem = document.getElementById("tree-canvas");
const panzoom = Panzoom(canvasElem, {
    maxScale: 3.5,
    minScale: 0.08,
    startScale: 0.80,
    canvas: true,
    cursor: 'grab'
});

// Stabilized Wheel & Gesture Handler (Google Maps / Figma standard)
canvasElem.parentElement.addEventListener("wheel", (e) => {
    // If scrolling inside any drawer, modal, or dropdown, allow normal element scroll
    if (e.target.closest('.reader-scrollable, .cyber-modal, .leader-scroll, .search-dropdown, .emoji-grid')) {
        return;
    }
    
    e.preventDefault();
    
    if (e.ctrlKey) {
        // Trackpad pinch-to-zoom or Ctrl + mouse wheel: Smooth focal zoom centered on cursor
        const currentScale = panzoom.getScale();
        const factor = Math.exp(-e.deltaY * 0.008);
        const targetScale = Math.min(3.5, Math.max(0.08, currentScale * factor));
        panzoom.zoomToPoint(targetScale, { clientX: e.clientX, clientY: e.clientY });
        updateZoomDisplay(targetScale);
    } else {
        // Trackpad two-finger pan or regular mouse wheel: Smoothly pan matrix
        panzoom.pan(-e.deltaX, -e.deltaY, { relative: true });
    }
}, { passive: false });

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
        // Ignore audio errors
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

// Camera Centering Formula
function panToCoordinate(targetX, targetY, scale = 0.85) {
    const container = document.getElementById('canvas-container');
    const viewW = container.clientWidth || window.innerWidth;
    const viewH = container.clientHeight || window.innerHeight;
    const canvasW = canvasElem.offsetWidth || 12000;
    const canvasH = canvasElem.offsetHeight || 12000;
    
    const panX = (viewW / (2 * scale)) + (canvasW / 2) * (1 - 1 / scale) - targetX;
    const panY = (viewH / (2 * scale)) + (canvasH / 2) * (1 - 1 / scale) - targetY;
    
    panzoom.zoom(scale, { animate: true });
    panzoom.pan(panX, panY, { animate: true });
    updateZoomDisplay(scale);
}

function resetView() {
    if (currentNodes.length > 0) {
        focusNode(currentNodes[0].id, 0.80);
    } else {
        panToCoordinate(3000, 200, 0.80);
    }
}

// Global State
let currentNodes = [];
let nodeMap = {};
let activeReaderNodeId = null;
let currentAuthor = null; // Verified author state

// Category Styling Helpers
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
        panToCoordinate(node.x + 135, node.y + 80, scale);
        
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

// ==========================================================================
// Check & Manage Verified Author Session
// ==========================================================================
async function checkAuth() {
    try {
        const res = await fetch('/api/auth/me');
        const data = await res.json();
        
        const loggedOutGroup = document.getElementById('nav-logged-out');
        const loggedInGroup = document.getElementById('nav-logged-in');
        
        if (data.logged_in && data.author) {
            currentAuthor = data.author;
            loggedOutGroup.classList.add('d-none');
            loggedInGroup.classList.remove('d-none');
            
            document.getElementById('nav-user-avatar').src = currentAuthor.avatar || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + currentAuthor.username;
            document.getElementById('nav-user-name').textContent = currentAuthor.pen_name;
            
            // Populate series datalist in composer
            const datalist = document.getElementById('existing-series-datalist');
            if (currentAuthor.series && currentAuthor.series.length > 0) {
                datalist.innerHTML = currentAuthor.series.map(s => `<option value="${s}">`).join('');
            }
        } else {
            currentAuthor = null;
            loggedOutGroup.classList.remove('d-none');
            loggedInGroup.classList.add('d-none');
        }
    } catch (e) {
        console.error("Auth check failed:", e);
    }
}

// ==========================================================================
// Load Matrix Data & Render Canvas Cards
// ==========================================================================
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
            document.getElementById('stat-series').textContent = data.stats.total_series || 0;
        }
        
        // 2. Populate Trending Stories Tab
        const trendingList = document.getElementById('trending-list');
        if (data.trending && data.trending.length > 0) {
            let tHtml = '';
            data.trending.forEach((item, i) => {
                const medal = i === 0 ? '🔥' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : `#${i+1}`));
                let seriesSubtitle = '';
                if (item.series_title) {
                    seriesSubtitle = `<span class="text-gold"><i class="bi bi-collection-fill"></i> ${item.series_title}</span> • `;
                }
                tHtml += `
                    <div class="trend-row" onclick="openReader(${item.id})" title="Read article & view on tree">
                        <div class="trend-main">
                            <span class="trend-title">${item.title}</span>
                            <span class="trend-author">${seriesSubtitle}${medal} by @${item.name}</span>
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

        // 3. Populate Series Tab
        const seriesList = document.getElementById('series-list');
        if (data.active_series && data.active_series.length > 0) {
            let sHtml = '';
            data.active_series.forEach(s => {
                sHtml += `
                    <div class="series-row" onclick="focusNode(${s.first_node_id}); openReader(${s.first_node_id})" title="View Series">
                        <div class="trend-main">
                            <span class="trend-title text-gold"><i class="bi bi-collection-fill"></i> ${s.title}</span>
                            <span class="trend-author">by @${s.author_name}</span>
                        </div>
                        <div class="trend-stats">
                            <span class="badge-cat cat-discussion">${s.parts_count} Parts</span>
                        </div>
                    </div>
                `;
            });
            seriesList.innerHTML = sHtml;
        } else {
            seriesList.innerHTML = '<div class="leader-loading">No active series yet</div>';
        }
        
        // 4. Populate Top Writers Tab
        const authorsList = document.getElementById('authors-list');
        if (data.leaders && data.leaders.length > 0) {
            let aHtml = '';
            data.leaders.forEach((w, i) => {
                const medal = i === 0 ? '👑' : `#${i+1}`;
                aHtml += `
                    <div class="author-row" onclick="openAuthorDrawer(${w.id})" title="View verified author profile">
                        <div class="author-left">
                            <img src="${w.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + w.username}" class="author-mini-img" alt="">
                            <div class="author-details" style="max-width: 120px;">
                                <span class="author-name-text">${w.name} <i class="bi bi-patch-check-fill text-cyan" style="font-size: 8px;"></i></span>
                                <span style="font-size: 8px; color: var(--text-muted);">${w.badge}</span>
                            </div>
                        </div>
                        <div class="trend-stats">
                            <i class="bi bi-heart-fill text-gold"></i> ${w.total_claps}
                        </div>
                    </div>
                `;
            });
            authorsList.innerHTML = aHtml;
        } else {
            authorsList.innerHTML = '<div class="leader-loading">No verified writers ranked yet</div>';
        }
        
        // 5. Render Canvas Cards & Connecting Lines
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
            
            // Lineage badge: who replied to whom
            let replyBadgeHtml = '';
            if (parent) {
                replyBadgeHtml = `
                    <div class="card-reply-lineage" title="Replying to ${parent.title}">
                        <i class="bi bi-reply-fill"></i>
                        <span>↳ in reply to <strong>@${parent.name}</strong></span>
                    </div>
                `;
            }

            // Series badge: if part of an ongoing series
            let seriesBadgeHtml = '';
            if (node.series_title) {
                seriesBadgeHtml = `
                    <div class="card-series-tag" title="Part ${node.series_part || 1} of ${node.series_title}">
                        <i class="bi bi-collection-fill text-gold"></i>
                        <span>Series: <strong>${node.series_title}</strong> • Part ${node.series_part || 1}</span>
                    </div>
                `;
            }

            // Verified author checkmark
            const verifiedHtml = node.is_verified_author ? `<i class="bi bi-patch-check-fill text-cyan" title="Verified Author" style="font-size: 10px; margin-left: 2px;"></i>` : '';
            
            card.innerHTML = `
                <div class="card-top-row">
                    <span class="badge-cat ${catClass}">${node.category}</span>
                    <span class="card-read-time">${node.read_time}</span>
                </div>
                
                <h3 class="card-headline">${node.title}</h3>
                <p class="card-excerpt">${node.text}</p>
                
                ${seriesBadgeHtml}
                ${replyBadgeHtml}
                
                <div class="card-bottom-row">
                    <div class="card-author-info">
                        <img src="${node.image || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + node.name}" class="card-avatar" alt="">
                        <span class="card-author-name">${node.name}${verifiedHtml}</span>
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
                const fromX = parent.x + 135;
                const fromY = parent.y + 165;
                const toX = node.x + 135;
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
            panToCoordinate(first.x + 135, first.y + 80, 0.80);
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
        
        // Verified badge in reader
        const vBadge = document.getElementById('reader-verified-badge');
        if (node.is_verified_author) {
            vBadge.classList.remove('d-none');
        } else {
            vBadge.classList.add('d-none');
        }

        // Author click opens author portfolio
        document.getElementById('reader-author-click-wrap').onclick = () => {
            if (node.author_id) {
                openAuthorDrawer(node.author_id);
            }
        };
        
        // EXACT ATTACHED COVER PHOTO
        const coverImg = document.getElementById('reader-cover-img');
        coverImg.src = node.cover_image || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&auto=format&fit=crop&q=80';
        
        document.getElementById('reader-quick-claps').textContent = node.claps || 0;
        document.getElementById('reader-quick-replies').textContent = node.reply_count || 0;
        document.getElementById('reader-clap-badge').textContent = node.claps || 0;
        
        // Series Navigation Banner
        const seriesBanner = document.getElementById('reader-series-banner');
        if (node.series_title) {
            document.getElementById('reader-series-name').textContent = node.series_title;
            document.getElementById('reader-series-part-tag').textContent = `Part ${node.series_part || 1}`;
            
            const pillsRow = document.getElementById('reader-series-siblings-pills');
            if (node.series_siblings && node.series_siblings.length > 0) {
                let sHtml = '';
                node.series_siblings.forEach(part => {
                    const isActive = part.id === node.id ? 'active' : '';
                    sHtml += `
                        <button class="series-pill-btn ${isActive}" onclick="openReader(${part.id}); focusNode(${part.id})">
                            Part ${part.series_part || 1}: ${part.title}
                        </button>
                    `;
                });
                pillsRow.innerHTML = sHtml;
            } else {
                pillsRow.innerHTML = `<span class="text-muted" style="font-size: 10px;">Part ${node.series_part || 1} of ongoing series</span>`;
            }
            seriesBanner.classList.remove('d-none');
        } else {
            seriesBanner.classList.add('d-none');
        }

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
            
            if (nodeMap[activeReaderNodeId]) {
                nodeMap[activeReaderNodeId].claps = data.claps;
                const card = document.querySelector(`.editorial-card[data-id="${activeReaderNodeId}"] .card-metric-tag`);
                if (card) card.innerHTML = `<i class="bi bi-heart-fill text-magenta"></i> ${data.claps}`;
            }
            
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
// Article & Branch Reply Composer Modal (Photo Upload & Series)
// ==========================================================================
const overlay = document.getElementById('overlay');
const composerModal = document.getElementById('composer-modal');
const composerCloseX = document.getElementById('composer-close-x');
const composerCancelBtn = document.getElementById('composer-cancel-btn');
const form = document.getElementById('article-form');

// Photo Attachment Elements
const tabPhotoFile = document.getElementById('tab-photo-file');
const tabPhotoUrl = document.getElementById('tab-photo-url');
const photoFileSection = document.getElementById('photo-file-section');
const photoUrlSection = document.getElementById('photo-url-section');
const composerFileInput = document.getElementById('composer-file-input');
const composerUrlInput = document.getElementById('composer-url-input');
const fileDropZone = document.getElementById('file-drop-zone');
const photoPreviewWrap = document.getElementById('photo-preview-wrap');
const composerPreviewImg = document.getElementById('composer-preview-img');
const previewFilename = document.getElementById('preview-filename');
const btnRemovePhoto = document.getElementById('btn-remove-photo');
const formFinalCover = document.getElementById('form-final-cover');

// Photo Tab Toggles
tabPhotoFile.addEventListener('click', () => {
    tabPhotoFile.classList.add('active');
    tabPhotoUrl.classList.remove('active');
    photoFileSection.classList.remove('d-none');
    photoUrlSection.classList.add('d-none');
});

tabPhotoUrl.addEventListener('click', () => {
    tabPhotoUrl.classList.add('active');
    tabPhotoFile.classList.remove('active');
    photoUrlSection.classList.remove('d-none');
    photoFileSection.classList.add('d-none');
});

// Photo File Upload Handler
composerFileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    // Live preview immediately
    const reader = new FileReader();
    reader.onload = (ev) => {
        composerPreviewImg.src = ev.target.result;
        previewFilename.textContent = file.name;
        photoPreviewWrap.classList.remove('d-none');
    };
    reader.readAsDataURL(file);
    
    // Upload to server
    const fd = new FormData();
    fd.append('file', file);
    try {
        const res = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (res.ok && data.url) {
            formFinalCover.value = data.url;
            showToast("Photo attached successfully!");
        } else {
            showToast(data.error || "Upload failed", true);
        }
    } catch (err) {
        showToast("Error uploading image file", true);
    }
});

// Photo URL Input Handler
composerUrlInput.addEventListener('input', () => {
    const url = composerUrlInput.value.trim();
    if (url) {
        formFinalCover.value = url;
        composerPreviewImg.src = url;
        previewFilename.textContent = url.slice(0, 30) + '...';
        photoPreviewWrap.classList.remove('d-none');
    } else {
        formFinalCover.value = '';
        photoPreviewWrap.classList.add('d-none');
    }
});

btnRemovePhoto.addEventListener('click', () => {
    composerFileInput.value = '';
    composerUrlInput.value = '';
    formFinalCover.value = '';
    composerPreviewImg.src = '';
    photoPreviewWrap.classList.add('d-none');
});

// Series Toggle in Composer
const formIsSeries = document.getElementById('form-is-series');
const seriesInputsPanel = document.getElementById('series-inputs-panel');

formIsSeries.addEventListener('change', () => {
    if (formIsSeries.checked) {
        seriesInputsPanel.classList.remove('d-none');
    } else {
        seriesInputsPanel.classList.add('d-none');
    }
});

// ==========================================================================
// Microsoft Word Studio Mode & Formatting Toolbar System
// ==========================================================================
const composerFullscreenBtn = document.getElementById('composer-fullscreen-btn');
const fsIcon = document.getElementById('fs-icon');
const studioBadge = document.getElementById('composer-studio-badge');
const contentTextarea = document.getElementById('form-content');
const wordCountElem = document.getElementById('editor-word-count');
const charCountElem = document.getElementById('editor-char-count');
const readTimeElem = document.getElementById('editor-read-time');
const livePreviewPane = document.getElementById('composer-live-preview');
const previewBody = document.getElementById('composer-preview-body');
const btnTogglePreview = document.getElementById('btn-toggle-preview');

// Fullscreen Studio Mode Toggle
function toggleFullscreenStudio() {
    playSound('click');
    const isFs = composerModal.classList.toggle('fullscreen-studio');
    if (isFs) {
        fsIcon.className = 'bi bi-fullscreen-exit';
        composerFullscreenBtn.title = 'Exit Word Studio (Restore)';
        if (studioBadge) studioBadge.classList.remove('d-none');
        showToast("🖥️ Word Studio Mode active - Distraction-free writing canvas");
    } else {
        fsIcon.className = 'bi bi-arrows-fullscreen';
        composerFullscreenBtn.title = 'Toggle Word Studio (Fullscreen Mode)';
        if (studioBadge) studioBadge.classList.add('d-none');
    }
}

if (composerFullscreenBtn) {
    composerFullscreenBtn.addEventListener('click', toggleFullscreenStudio);
}

// Live Document Statistics (Word count, Character count, Estimated read time)
function updateLiveStats() {
    if (!contentTextarea) return;
    const text = contentTextarea.value || '';
    const trimmed = text.trim();
    const words = trimmed ? trimmed.split(/\s+/).length : 0;
    const chars = text.length;
    const readMin = Math.max(1, Math.ceil(words / 200));

    if (wordCountElem) wordCountElem.innerHTML = `<i class="bi bi-file-earmark-text"></i> <strong>${words}</strong> words`;
    if (charCountElem) charCountElem.innerHTML = `<strong>${chars}</strong> characters`;
    if (readTimeElem) readTimeElem.innerHTML = `<i class="bi bi-clock"></i> ${readMin} min read`;

    // Live preview update
    if (livePreviewPane && !livePreviewPane.classList.contains('d-none') && previewBody) {
        if (typeof marked !== 'undefined') {
            previewBody.innerHTML = marked.parse(text || '*Preview your formatted story here...*');
        } else {
            previewBody.innerHTML = `<p>${text}</p>`;
        }
    }
}

if (contentTextarea) {
    contentTextarea.addEventListener('input', updateLiveStats);
}

// Live Split Preview Toggle
if (btnTogglePreview) {
    btnTogglePreview.addEventListener('click', () => {
        playSound('click');
        const isHidden = livePreviewPane.classList.toggle('d-none');
        btnTogglePreview.classList.toggle('active', !isHidden);
        if (!isHidden) {
            updateLiveStats();
        }
    });
}

// Selection-preserving Word Formatting Engine
function applyFormatting(action) {
    if (!contentTextarea) return;
    playSound('click');
    const start = contentTextarea.selectionStart;
    const end = contentTextarea.selectionEnd;
    const fullText = contentTextarea.value;
    const selectedText = fullText.substring(start, end);
    
    let replacement = '';
    let selStartOffset = 0;
    let selEndOffset = 0;
    let selectAfter = false;

    switch (action) {
        case 'bold':
            if (selectedText.startsWith('**') && selectedText.endsWith('**') && selectedText.length >= 4) {
                replacement = selectedText.slice(2, -2);
            } else {
                replacement = `**${selectedText || 'bold text'}**`;
                if (!selectedText) { selStartOffset = 2; selEndOffset = replacement.length - 2; selectAfter = true; }
            }
            break;
        case 'italic':
            if (selectedText.startsWith('*') && selectedText.endsWith('*') && selectedText.length >= 2) {
                replacement = selectedText.slice(1, -1);
            } else {
                replacement = `*${selectedText || 'italic text'}*`;
                if (!selectedText) { selStartOffset = 1; selEndOffset = replacement.length - 1; selectAfter = true; }
            }
            break;
        case 'underline':
            if (selectedText.startsWith('<u>') && selectedText.endsWith('</u>') && selectedText.length >= 7) {
                replacement = selectedText.slice(3, -4);
            } else {
                replacement = `<u>${selectedText || 'underlined text'}</u>`;
                if (!selectedText) { selStartOffset = 3; selEndOffset = replacement.length - 4; selectAfter = true; }
            }
            break;
        case 'strike':
            if (selectedText.startsWith('~~') && selectedText.endsWith('~~') && selectedText.length >= 4) {
                replacement = selectedText.slice(2, -2);
            } else {
                replacement = `~~${selectedText || 'strikethrough text'}~~`;
                if (!selectedText) { selStartOffset = 2; selEndOffset = replacement.length - 2; selectAfter = true; }
            }
            break;
        case 'h1':
            replacement = `\n# ${selectedText || 'Heading 1'}\n`;
            break;
        case 'h2':
            replacement = `\n## ${selectedText || 'Heading 2'}\n`;
            break;
        case 'h3':
            replacement = `\n### ${selectedText || 'Heading 3'}\n`;
            break;
        case 'quote':
            replacement = `\n> ${selectedText || 'Quote text'}\n`;
            break;
        case 'code':
            if (selectedText.includes('\n')) {
                replacement = `\n\`\`\`\n${selectedText || 'code block'}\n\`\`\`\n`;
            } else {
                replacement = `\`${selectedText || 'code'}\``;
            }
            break;
        case 'ul':
            if (selectedText) {
                replacement = selectedText.split('\n').map(l => `- ${l}`).join('\n');
            } else {
                replacement = `\n- Item 1\n- Item 2\n- Item 3\n`;
            }
            break;
        case 'ol':
            if (selectedText) {
                replacement = selectedText.split('\n').map((l, idx) => `${idx + 1}. ${l}`).join('\n');
            } else {
                replacement = `\n1. Point 1\n2. Point 2\n3. Point 3\n`;
            }
            break;
        case 'hr':
            replacement = `\n\n---\n\n`;
            break;
        case 'link':
            const url = prompt("Enter hyperlink URL (e.g. https://example.com):", "https://");
            if (url) {
                const label = selectedText || "link title";
                replacement = `[${label}](${url})`;
            } else {
                return;
            }
            break;
        default:
            return;
    }

    contentTextarea.focus();
    contentTextarea.setRangeText(replacement, start, end, 'end');
    if (selectAfter) {
        contentTextarea.setSelectionRange(start + selStartOffset, start + selEndOffset);
    }
    contentTextarea.dispatchEvent(new Event('input'));
}

// Bind all toolbar buttons
document.querySelectorAll('.word-toolbar .tb-btn[data-action]').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.preventDefault();
        const action = btn.getAttribute('data-action');
        if (action) applyFormatting(action);
    });
});

// Keyboard shortcuts inside textarea (Ctrl+B, Ctrl+I, Ctrl+U, Ctrl+K)
if (contentTextarea) {
    contentTextarea.addEventListener('keydown', (e) => {
        const isMod = e.ctrlKey || e.metaKey;
        if (isMod && e.key.toLowerCase() === 'b') {
            e.preventDefault();
            applyFormatting('bold');
        } else if (isMod && e.key.toLowerCase() === 'i') {
            e.preventDefault();
            applyFormatting('italic');
        } else if (isMod && e.key.toLowerCase() === 'u') {
            e.preventDefault();
            applyFormatting('underline');
        } else if (isMod && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            applyFormatting('link');
        }
    });
}

// ==========================================================================
// Interactive Emoji Picker System
// ==========================================================================
const emojiToggleBtn = document.getElementById('btn-toggle-emoji');
const emojiDropdown = document.getElementById('emoji-picker-dropdown');
const emojiGrid = document.getElementById('emoji-grid');
const emojiTabBtns = document.querySelectorAll('.emoji-tab-btn');

const EMOJI_SETS = {
    editorial: ['📰', '🖋️', '📝', '💡', '📜', '📡', '🌐', '📢', '🔍', '📖', '📊', '📈', '📌', '🎯', '🏷️', '🔖', '📑', '🗞️', '🔬', '🧠'],
    reactions: ['👏', '❤️', '🔥', '🚀', '💎', '👑', '⭐', '💯', '👍', '🙌', '🎉', '🥂', '🏆', '✨', '⚡', '🤩', '💪', '🤝', '🎯', '🙏'],
    faces: ['😀', '😃', '😄', '😁', '😎', '🤔', '🧐', '🤩', '🤖', '🧙', '🤯', '🥳', '😇', '🤓', '🤠', '🤐', '😮', '😴', '😏', '🫡'],
    tech: ['⚡', '💻', '🖥️', '🔗', '🔒', '🗝️', '⚙️', '🛰️', '🔋', '💾', '🧬', '🕹️', '🔌', '📡', '🌐', '🛡️', '🤖', '📦', '📱', '⌨️'],
    symbols: ['✦', '❖', '✹', '➔', '➜', '↳', '•', '—', '▪', '★', '⬢', '🟢', '🔴', '🟡', '🔵', '✔️', '✖️', '⚠️', '💎', '♾️']
};

let currentEmojiTab = 'editorial';

function renderEmojis(category) {
    currentEmojiTab = category;
    const emojis = EMOJI_SETS[category] || EMOJI_SETS.editorial;
    if (emojiGrid) {
        emojiGrid.innerHTML = emojis.map(em => `<button type="button" class="emoji-item" data-emoji="${em}">${em}</button>`).join('');
        emojiGrid.querySelectorAll('.emoji-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.stopPropagation();
                const emoji = item.getAttribute('data-emoji');
                insertEmoji(emoji);
            });
        });
    }
}

function insertEmoji(emoji) {
    if (!contentTextarea) return;
    playSound('click');
    const start = contentTextarea.selectionStart;
    const end = contentTextarea.selectionEnd;
    contentTextarea.setRangeText(emoji, start, end, 'end');
    contentTextarea.focus();
    contentTextarea.dispatchEvent(new Event('input'));
    if (emojiDropdown) emojiDropdown.classList.add('d-none');
}

if (emojiToggleBtn && emojiDropdown) {
    emojiToggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        playSound('click');
        const isHidden = emojiDropdown.classList.toggle('d-none');
        if (!isHidden) {
            renderEmojis(currentEmojiTab);
        }
    });

    emojiTabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            playSound('click');
            emojiTabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const tab = btn.getAttribute('data-tab');
            renderEmojis(tab);
        });
    });

    document.addEventListener('click', (e) => {
        if (emojiToggleBtn && !emojiToggleBtn.contains(e.target) && emojiDropdown && !emojiDropdown.contains(e.target)) {
            emojiDropdown.classList.add('d-none');
        }
    });
}

function openComposer(parentId = null, parentTitle = null, parentAuthor = null) {
    playSound('click');
    document.getElementById('form-parent-id').value = parentId || '';
    
    const banner = document.getElementById('composer-reply-target-banner');
    const modalTitle = document.getElementById('composer-modal-title');
    const submitText = document.getElementById('composer-submit-text');
    const catSelect = document.getElementById('form-category');
    
    // Verified author bar
    const vBanner = document.getElementById('composer-verified-author-banner');
    const gBanner = document.getElementById('composer-guest-banner');
    const authorInput = document.getElementById('form-author');
    
    if (currentAuthor) {
        vBanner.classList.remove('d-none');
        gBanner.classList.add('d-none');
        document.getElementById('composer-auth-name').textContent = currentAuthor.pen_name;
        document.getElementById('composer-auth-badge').textContent = currentAuthor.badge;
        authorInput.value = currentAuthor.pen_name;
        authorInput.readOnly = true;
    } else {
        vBanner.classList.add('d-none');
        gBanner.classList.remove('d-none');
        authorInput.readOnly = false;
        authorInput.value = '';
    }
    
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
    updateLiveStats();
    document.getElementById('form-title').focus();
}

function closeComposer() {
    overlay.style.display = 'none';
    composerModal.classList.add('d-none');
    if (emojiDropdown) emojiDropdown.classList.add('d-none');
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
    const coverImage = formFinalCover.value.trim();
    
    // Series fields
    const isSeries = formIsSeries.checked;
    const seriesTitle = isSeries ? document.getElementById('form-series-title').value.trim() : '';
    const seriesPart = isSeries ? parseInt(document.getElementById('form-series-part').value) || 1 : null;
    
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
            name: author || (currentAuthor ? currentAuthor.pen_name : "Anonymous Thinker"),
            category: category,
            content: content,
            parent_id: parentId || null,
            cover_image: coverImage,
            series_title: seriesTitle,
            series_part: seriesPart
        };
        
        const res = await fetch('/api/nodes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        
        if (res.ok && data.status === 'success') {
            playSound('publish');
            showToast(parentId ? "⚡ Branch Reply published successfully!" : "📰 Article published to matrix!");
            closeComposer();
            form.reset();
            btnRemovePhoto.click();
            
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
// Verified Author Registration & Login Modals
// ==========================================================================
const registerModal = document.getElementById('register-modal');
const loginModal = document.getElementById('login-modal');

function openRegisterModal() {
    closeComposer();
    loginModal.classList.add('d-none');
    overlay.style.display = 'block';
    registerModal.classList.remove('d-none');
}

function closeRegisterModal() {
    registerModal.classList.add('d-none');
    overlay.style.display = 'none';
}

function openLoginModal() {
    closeComposer();
    registerModal.classList.add('d-none');
    overlay.style.display = 'block';
    loginModal.classList.remove('d-none');
}

function closeLoginModal() {
    loginModal.classList.add('d-none');
    overlay.style.display = 'none';
}

// Nav Buttons
document.getElementById('btn-open-register').addEventListener('click', openRegisterModal);
document.getElementById('btn-open-login').addEventListener('click', openLoginModal);
document.getElementById('composer-prompt-register').addEventListener('click', (e) => { e.preventDefault(); openRegisterModal(); });
document.getElementById('composer-prompt-login').addEventListener('click', (e) => { e.preventDefault(); openLoginModal(); });
document.getElementById('link-to-login').addEventListener('click', (e) => { e.preventDefault(); openLoginModal(); });
document.getElementById('link-to-register').addEventListener('click', (e) => { e.preventDefault(); openRegisterModal(); });

document.getElementById('register-close-x').addEventListener('click', closeRegisterModal);
document.getElementById('reg-cancel-btn').addEventListener('click', closeRegisterModal);
document.getElementById('login-close-x').addEventListener('click', closeLoginModal);
document.getElementById('login-cancel-btn').addEventListener('click', closeLoginModal);

// Register Form Submit
document.getElementById('register-form').addEventListener('submit', async () => {
    const penName = document.getElementById('reg-pen-name').value.trim();
    const username = document.getElementById('reg-username').value.trim();
    const email = document.getElementById('reg-email').value.trim();
    const password = document.getElementById('reg-password').value.trim();
    const bio = document.getElementById('reg-bio').value.trim();
    
    if (!penName || !username || !password) {
        showToast("Please fill in Pen Name, Username, and Password.", true);
        return;
    }
    
    try {
        const res = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pen_name: penName, username, email, password, bio })
        });
        const data = await res.json();
        
        if (res.ok && data.status === 'success') {
            playSound('publish');
            showToast(`⭐ Welcome, ${data.author.pen_name}! Verified Author ID created.`);
            closeRegisterModal();
            await checkAuth();
            await loadMatrix(false);
        } else {
            showToast(data.error || "Registration failed.", true);
        }
    } catch (e) {
        showToast("Network error during registration.", true);
    }
});

// Login Form Submit
document.getElementById('login-form').addEventListener('submit', async () => {
    const identifier = document.getElementById('login-identifier').value.trim();
    const password = document.getElementById('login-password').value.trim();
    
    if (!identifier || !password) {
        showToast("Please enter your Username/Email and Password.", true);
        return;
    }
    
    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ identifier, password })
        });
        const data = await res.json();
        
        if (res.ok && data.status === 'success') {
            playSound('click');
            showToast(`🔑 Logged in as ${data.author.pen_name}!`);
            closeLoginModal();
            await checkAuth();
            await loadMatrix(false);
        } else {
            showToast(data.error || "Invalid credentials.", true);
        }
    } catch (e) {
        showToast("Network error during login.", true);
    }
});

// Logout
document.getElementById('btn-logout').addEventListener('click', async () => {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
        showToast("Logged out successfully.");
        await checkAuth();
        await loadMatrix(false);
    } catch (e) {
        console.error("Logout failed:", e);
    }
});

// ==========================================================================
// Author Portfolio & Series Drawer
// ==========================================================================
const authorDrawer = document.getElementById('author-portfolio-drawer');
const authorDrawerCloseBtn = document.getElementById('author-drawer-close-btn');

async function openAuthorDrawer(authorId) {
    playSound('click');
    try {
        const res = await fetch(`/api/authors/${authorId}`);
        const data = await res.json();
        if (!res.ok) { showToast(data.error || "Author not found", true); return; }
        
        const a = data.author;
        document.getElementById('portfolio-avatar').src = a.avatar || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + a.username;
        document.getElementById('portfolio-name').textContent = a.pen_name;
        document.getElementById('portfolio-handle').textContent = `@${a.username}`;
        document.getElementById('portfolio-badge').innerHTML = `<i class="bi bi-patch-check-fill text-cyan"></i> ${a.badge}`;
        document.getElementById('portfolio-bio').textContent = a.bio || "No bio provided.";
        document.getElementById('portfolio-total-claps').textContent = a.total_claps;
        document.getElementById('portfolio-articles-count').textContent = a.article_count;
        
        // Render Series
        const seriesContainer = document.getElementById('portfolio-series-list');
        const seriesKeys = Object.keys(data.series || {});
        if (seriesKeys.length === 0) {
            seriesContainer.innerHTML = '<div class="text-muted" style="font-size: 11px;">No multi-part series created yet.</div>';
        } else {
            let sHtml = '';
            seriesKeys.forEach(st => {
                const parts = data.series[st];
                let chipsHtml = '';
                parts.forEach(p => {
                    chipsHtml += `
                        <button class="series-chip" onclick="openReader(${p.id}); focusNode(${p.id})">
                            Part ${p.series_part || 1}: ${p.title}
                        </button>
                    `;
                });
                sHtml += `
                    <div class="portfolio-series-card">
                        <div class="series-card-title"><i class="bi bi-collection-fill text-gold"></i> ${st} (${parts.length} Parts)</div>
                        <div class="series-parts-chips">${chipsHtml}</div>
                    </div>
                `;
            });
            seriesContainer.innerHTML = sHtml;
        }
        
        // Render Standalone Writings
        const articlesContainer = document.getElementById('portfolio-articles-list');
        if (!data.standalone_articles || data.standalone_articles.length === 0) {
            articlesContainer.innerHTML = '<div class="text-muted" style="font-size: 11px;">No standalone writings.</div>';
        } else {
            let aHtml = '';
            data.standalone_articles.forEach(art => {
                aHtml += `
                    <div class="branch-reply-card" onclick="openReader(${art.id}); focusNode(${art.id})">
                        <div class="reply-card-top">
                            <span class="badge-cat ${getCategoryClass(art.category)}">${art.category}</span>
                            <span class="text-gold"><i class="bi bi-heart-fill"></i> ${art.claps}</span>
                        </div>
                        <h4 class="reply-card-title">${art.title}</h4>
                        <p class="reply-card-snippet">${art.text}</p>
                    </div>
                `;
            });
            articlesContainer.innerHTML = aHtml;
        }
        
        authorDrawer.classList.remove('d-none');
    } catch (e) {
        console.error("Failed to load author portfolio:", e);
    }
}

authorDrawerCloseBtn.addEventListener('click', () => {
    authorDrawer.classList.add('d-none');
});

document.getElementById('nav-author-pill').addEventListener('click', () => {
    if (currentAuthor) openAuthorDrawer(currentAuthor.id);
});

document.getElementById('btn-my-series').addEventListener('click', () => {
    if (currentAuthor) openAuthorDrawer(currentAuthor.id);
});

// ==========================================================================
// Scoreboard Tabs & Search HUD
// ==========================================================================
const tabTrending = document.getElementById('tab-trending');
const tabSeries = document.getElementById('tab-series');
const tabAuthors = document.getElementById('tab-authors');
const trendingList = document.getElementById('trending-list');
const seriesList = document.getElementById('series-list');
const authorsList = document.getElementById('authors-list');

tabTrending.addEventListener('click', () => {
    playSound('click');
    tabTrending.classList.add('active');
    tabSeries.classList.remove('active');
    tabAuthors.classList.remove('active');
    trendingList.classList.remove('d-none');
    seriesList.classList.add('d-none');
    authorsList.classList.add('d-none');
});

tabSeries.addEventListener('click', () => {
    playSound('click');
    tabSeries.classList.add('active');
    tabTrending.classList.remove('active');
    tabAuthors.classList.remove('active');
    seriesList.classList.remove('d-none');
    trendingList.classList.add('d-none');
    authorsList.classList.add('d-none');
});

tabAuthors.addEventListener('click', () => {
    playSound('click');
    tabAuthors.classList.add('active');
    tabTrending.classList.remove('active');
    tabSeries.classList.remove('active');
    authorsList.classList.remove('d-none');
    trendingList.classList.add('d-none');
    seriesList.classList.add('d-none');
});

// Search HUD
const searchInput = document.getElementById('node-search-input');
const searchDropdown = document.getElementById('search-results-dropdown');

searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim().toLowerCase();
    if (!q) { searchDropdown.classList.add('d-none'); return; }
    
    const matches = currentNodes.filter(n => 
        (n.title && n.title.toLowerCase().includes(q)) || 
        (n.name && n.name.toLowerCase().includes(q)) ||
        (n.category && n.category.toLowerCase().includes(q)) ||
        (n.series_title && n.series_title.toLowerCase().includes(q)) ||
        (n.text && n.text.toLowerCase().includes(q))
    ).slice(0, 6);
    
    if (matches.length === 0) {
        searchDropdown.innerHTML = '<div class="search-item text-muted">No matching articles or series found</div>';
    } else {
        let html = '';
        matches.forEach(m => {
            const seriesTag = m.series_title ? `<span class="text-gold"><i class="bi bi-collection"></i> ${m.series_title}</span> • ` : '';
            html += `
                <div class="search-item" onclick="selectSearchNode(${m.id})">
                    <span class="search-item-title">${m.title}</span>
                    <div class="search-item-meta">
                        <span>${seriesTag}by @${m.name}</span>
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

// ==========================================================================
// Precision Zoom Workflow & Live Display (+ / - / 100% Reset)
// ==========================================================================
function updateZoomDisplay(scale) {
    const s = scale || (panzoom ? panzoom.getScale() : 0.80);
    const pct = Math.round(s * 100);
    const textElem = document.getElementById('zoom-level-text');
    if (textElem) {
        textElem.textContent = `${pct}%`;
    }
}

// Center-focal Zoom Engine (Ensures zoom is anchored on viewport center)
function smoothZoom(direction) {
    playSound('click');
    const container = document.getElementById('canvas-container');
    const center = {
        clientX: container ? container.clientWidth / 2 : window.innerWidth / 2,
        clientY: container ? container.clientHeight / 2 : window.innerHeight / 2
    };
    const currentScale = panzoom.getScale();
    const factor = direction === 'in' ? 1.25 : 0.80;
    const targetScale = Math.min(3.5, Math.max(0.08, currentScale * factor));
    panzoom.zoomToPoint(targetScale, center, { animate: true });
    updateZoomDisplay(targetScale);
}

// Hold-to-zoom and click-to-zoom engine for + and - buttons
function attachZoomBtnEvents(btnId, direction) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    
    let pressTimer = null;
    let holdInterval = null;
    let hasHeld = false;

    const onPointerDown = (e) => {
        e.preventDefault();
        hasHeld = false;
        pressTimer = setTimeout(() => {
            hasHeld = true;
            holdInterval = setInterval(() => {
                const container = document.getElementById('canvas-container');
                const center = {
                    clientX: container ? container.clientWidth / 2 : window.innerWidth / 2,
                    clientY: container ? container.clientHeight / 2 : window.innerHeight / 2
                };
                const cur = panzoom.getScale();
                const factor = direction === 'in' ? 1.04 : 0.96;
                const targetScale = Math.min(3.5, Math.max(0.08, cur * factor));
                panzoom.zoomToPoint(targetScale, center, { animate: false });
                updateZoomDisplay(targetScale);
            }, 35);
        }, 280);
    };

    const onPointerUp = (e) => {
        if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; }
        if (holdInterval) { clearInterval(holdInterval); holdInterval = null; }
        if (!hasHeld) {
            smoothZoom(direction);
        }
    };

    const onPointerCancel = () => {
        if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; }
        if (holdInterval) { clearInterval(holdInterval); holdInterval = null; }
    };

    btn.addEventListener('pointerdown', onPointerDown);
    btn.addEventListener('pointerup', onPointerUp);
    btn.addEventListener('pointerleave', onPointerCancel);
    btn.addEventListener('pointercancel', onPointerCancel);
}

// Reset zoom to 100% on pill click
const zoomPill = document.getElementById('zoom-level-pill');
if (zoomPill) {
    zoomPill.addEventListener('click', () => {
        playSound('click');
        const container = document.getElementById('canvas-container');
        const center = {
            clientX: container ? container.clientWidth / 2 : window.innerWidth / 2,
            clientY: container ? container.clientHeight / 2 : window.innerHeight / 2
        };
        panzoom.zoomToPoint(1.0, center, { animate: true });
        updateZoomDisplay(1.0);
        showToast("🔍 Zoom reset to 100%");
    });
}

// Recenter camera on matrix
const ctrlResetBtn = document.getElementById('ctrl-reset');
if (ctrlResetBtn) {
    ctrlResetBtn.addEventListener('click', () => {
        playSound('click');
        resetView();
        showToast("🎯 Recenter camera on matrix");
    });
}

// Attach hold/click events for zoom buttons
attachZoomBtnEvents('ctrl-zoom-in', 'in');
attachZoomBtnEvents('ctrl-zoom-out', 'out');

// Panzoom scale event listeners
canvasElem.addEventListener('panzoomzoom', (e) => {
    if (e && e.detail && e.detail.scale) updateZoomDisplay(e.detail.scale);
});
canvasElem.addEventListener('panzoomreset', (e) => {
    if (e && e.detail && e.detail.scale) updateZoomDisplay(e.detail.scale);
});

// ==========================================================================
// 360° Virtual Flight Joystick Controller
// ==========================================================================
const joystickBase = document.getElementById('joystick-base');
const joystickThumb = document.getElementById('joystick-thumb');
const joyVectorBeam = document.getElementById('joy-vector-beam');
const joyCoordIndicator = document.getElementById('joy-coord-indicator');

let isJoyDragging = false;
let joyAnimFrameId = null;
let joySpeed = 0;
let joyAngle = 0;

const JOY_MAX_RADIUS = 32; // Limit thumb movement inside circle
const JOY_MAX_SPEED = 24;  // Max pan speed in pixels per frame

function initJoystick() {
    if (!joystickBase || !joystickThumb) return;

    function getBaseCenter() {
        const rect = joystickBase.getBoundingClientRect();
        return {
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2
        };
    }

    function onPointerDown(e) {
        e.preventDefault();
        isJoyDragging = true;
        try {
            joystickThumb.setPointerCapture(e.pointerId);
        } catch (err) {}
        
        joystickThumb.classList.add('active');
        joystickThumb.style.transition = 'none';
        if (joyVectorBeam) joyVectorBeam.style.opacity = '1';

        handlePointerMove(e);
        startJoyAnimation();
    }

    function handlePointerMove(e) {
        if (!isJoyDragging) return;
        const center = getBaseCenter();
        const rawDx = e.clientX - center.x;
        const rawDy = e.clientY - center.y;
        const distance = Math.hypot(rawDx, rawDy);
        joyAngle = Math.atan2(rawDy, rawDx);

        const clampedDist = Math.min(distance, JOY_MAX_RADIUS);
        const thumbX = Math.cos(joyAngle) * clampedDist;
        const thumbY = Math.sin(joyAngle) * clampedDist;

        // Position thumbstick knob
        joystickThumb.style.transform = `translate(${thumbX}px, ${thumbY}px)`;

        // Deadzone of 3px
        if (clampedDist > 3) {
            const norm = (clampedDist - 3) / (JOY_MAX_RADIUS - 3);
            joySpeed = Math.pow(norm, 1.35) * JOY_MAX_SPEED;

            // Heading in degrees: 0° = East, 90° = South, 180° = West, 270° = North
            const deg = Math.round((joyAngle * 180 / Math.PI) + 360) % 360;
            if (joyCoordIndicator) {
                joyCoordIndicator.textContent = `${deg}°`;
                joyCoordIndicator.classList.add('active');
            }

            if (joyVectorBeam) {
                joyVectorBeam.style.width = `${clampedDist}px`;
                joyVectorBeam.style.transform = `rotate(${joyAngle * 180 / Math.PI}deg)`;
            }
        } else {
            joySpeed = 0;
            if (joyCoordIndicator) joyCoordIndicator.textContent = `0°`;
            if (joyVectorBeam) joyVectorBeam.style.width = '0px';
        }
    }

    function onPointerUp(e) {
        if (!isJoyDragging) return;
        isJoyDragging = false;
        try {
            joystickThumb.releasePointerCapture(e.pointerId);
        } catch (err) {}

        joystickThumb.classList.remove('active');
        // Snappy spring back to center
        joystickThumb.style.transition = 'transform 0.22s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
        joystickThumb.style.transform = 'translate(0px, 0px)';

        if (joyVectorBeam) {
            joyVectorBeam.style.opacity = '0';
            joyVectorBeam.style.width = '0px';
        }
        if (joyCoordIndicator) {
            joyCoordIndicator.textContent = `360°`;
            joyCoordIndicator.classList.remove('active');
        }

        joySpeed = 0;
        stopJoyAnimation();
    }

    function startJoyAnimation() {
        if (joyAnimFrameId) return;
        function step() {
            if (isJoyDragging && joySpeed > 0.1) {
                // Moving camera:
                // If stick is pushed UP (joyAngle ~ -PI/2), camera moves UP, so canvas moves DOWN (+panY)
                // If stick is pushed RIGHT (joyAngle ~ 0), camera moves RIGHT, so canvas moves LEFT (-panX)
                const moveX = -Math.cos(joyAngle) * joySpeed;
                const moveY = -Math.sin(joyAngle) * joySpeed;
                panzoom.pan(moveX, moveY, { relative: true });
            }
            if (isJoyDragging) {
                joyAnimFrameId = requestAnimationFrame(step);
            } else {
                joyAnimFrameId = null;
            }
        }
        joyAnimFrameId = requestAnimationFrame(step);
    }

    function stopJoyAnimation() {
        if (joyAnimFrameId) {
            cancelAnimationFrame(joyAnimFrameId);
            joyAnimFrameId = null;
        }
    }

    joystickThumb.addEventListener('pointerdown', onPointerDown);
    joystickBase.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerUp);

    // Cardinal quick-nudge buttons (▲, ►, ▼, ◄)
    document.querySelectorAll('.joy-cardinal').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            playSound('click');
            const dir = btn.getAttribute('data-dir');
            const stepDist = 180;
            let px = 0, py = 0;
            if (dir === 'N') py = stepDist;
            else if (dir === 'S') py = -stepDist;
            else if (dir === 'E') px = -stepDist;
            else if (dir === 'W') px = stepDist;
            panzoom.pan(px, py, { relative: true, animate: true });
        });
    });
}

// Arrow / WASD keys for matrix panning when not typing
window.addEventListener('keydown', (e) => {
    const tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    if (composerModal && !composerModal.classList.contains('d-none')) return;
    if (registerModal && !registerModal.classList.contains('d-none')) return;
    if (loginModal && !loginModal.classList.contains('d-none')) return;

    const panStep = e.shiftKey ? 260 : 130;
    if (e.key === 'ArrowUp' || e.key === 'w' || e.key === 'W') {
        panzoom.pan(0, panStep, { relative: true, animate: true });
    } else if (e.key === 'ArrowDown' || e.key === 's' || e.key === 'S') {
        panzoom.pan(0, -panStep, { relative: true, animate: true });
    } else if (e.key === 'ArrowLeft' || e.key === 'a' || e.key === 'A') {
        panzoom.pan(panStep, 0, { relative: true, animate: true });
    } else if (e.key === 'ArrowRight' || e.key === 'd' || e.key === 'D') {
        panzoom.pan(-panStep, 0, { relative: true, animate: true });
    } else if (e.key === '+' || e.key === '=') {
        smoothZoom('in');
    } else if (e.key === '-' || e.key === '_') {
        smoothZoom('out');
    } else if (e.key === '0') {
        resetView();
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
    if (e.key === 'F11' && composerModal && !composerModal.classList.contains('d-none')) {
        e.preventDefault();
        toggleFullscreenStudio();
        return;
    }
    if (e.key === 'Escape') {
        if (composerModal && composerModal.classList.contains('fullscreen-studio')) {
            toggleFullscreenStudio();
            return;
        }
        closeComposer();
        closeRegisterModal();
        closeLoginModal();
        readerDrawer.classList.add('d-none');
        authorDrawer.classList.add('d-none');
        activeReaderNodeId = null;
    }
});

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
    initJoystick();
    updateZoomDisplay();
    await checkAuth();
    await loadMatrix(true);
    await checkDeepLink();
    setInterval(() => { loadMatrix(false); }, 25000);
});
