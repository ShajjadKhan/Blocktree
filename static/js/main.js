const elem = document.getElementById("tree-canvas");
const panzoom = Panzoom(elem, { maxScale: 3, minScale: 0.1, startScale: 1, contain: "outside" });
elem.parentElement.addEventListener("wheel", panzoom.zoomWithWheel);

window.copyRef = (id) => {
    const link = `${window.location.origin}/?ref=${id}`;
    navigator.clipboard.writeText(link);
    alert(`Referral Link Copied: ${link}\nSend this to your friends to build your grid!`);
};

async function loadGrid() {
    const res = await fetch('/api/nodes');
    const data = await res.json();
    const nodes = data.nodes;
    
    document.getElementById("total-users").innerText = nodes.length;
    
    // URL চেক: রেফারেল আইডি আছে কি না
    const urlParams = new URLSearchParams(window.location.search);
    const refId = urlParams.get('ref');

    // লিডারবোর্ড আপডেট
    let leaderHTML = "";
    data.leaders.forEach((l, i) => { 
        leaderHTML += `<div class="leader-row"><span>${i+1}. ${l.name}</span><span>${l.count} Ref</span></div>`; 
    });
    document.getElementById("leader-list").innerHTML = leaderHTML;
    
    const canvas = document.getElementById("tree-canvas");
    const svgCanvas = document.getElementById("svg-canvas");
    canvas.querySelectorAll('.node').forEach(e => e.remove());
    svgCanvas.innerHTML = '';
    
    const nodeMap = {};
    let inviterName = null;

    nodes.forEach(node => {
        nodeMap[node.id] = { x: node.x, y: node.y, name: node.name };
        if (refId && String(node.id) === String(refId)) {
            inviterName = node.name;
        }

        const div = document.createElement("div");
        div.className = "node"; 
        div.style.left = node.x + "px"; 
        div.style.top = node.y + "px";
        if(node.id === 1) div.style.borderColor = "gold";
        div.innerHTML = `<img src="${node.image}"><h3>${node.name}</h3><p>${node.text}</p><div class="ref-btn" onclick="copyRef(${node.id})">🔗 Copy Link</div>`;
        canvas.appendChild(div);
        
        if (node.parent_id && nodeMap[node.parent_id]) {
            const p = nodeMap[node.parent_id];
            const fromX = p.x + 75; const fromY = p.y + 110;
            const toX = node.x + 75; const toY = node.y;
            const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
            path.setAttribute("class", "circuit-line");
            path.setAttribute("d", `M ${fromX} ${fromY} V ${toY-40} H ${toX} V ${toY}`);
            svgCanvas.appendChild(path);
        }
    });

    // অটো-পপআপ লজিক: যদি ref আইডি থাকে, স্বয়ংক্রিয়ভাবে ফর্ম ওপেন হবে
    if (refId) {
        const modal = document.getElementById("modal");
        const overlay = document.getElementById("overlay");
        const titleElem = modal.querySelector("h2");
        titleElem.innerText = inviterName ? `Invited by: ${inviterName}` : "Join via Referral";
        titleElem.style.fontSize = "18px";
        modal.style.display = "block";
        overlay.style.display = "block";
    }
}
loadGrid();
setTimeout(() => { panzoom.pan(-1400, 0); }, 300);
const modal = document.getElementById("modal");
const overlay = document.getElementById("overlay");
document.getElementById("add-btn").onclick = () => { modal.style.display = "block"; overlay.style.display = "block"; };
document.getElementById("cancel-btn").onclick = () => { modal.style.display = "none"; overlay.style.display = "none"; };

document.getElementById("submit-btn").onclick = () => {
    const name = document.getElementById("node-name").value;
    const text = document.getElementById("node-text").value;
    const file = document.getElementById("node-image").files[0];
    
    if(!name || !text || !file) { alert("Please fill all fields!"); return; }
    
    const urlParams = new URLSearchParams(window.location.search);
    const ref_id = urlParams.get('ref') || null;
    
    const reader = new FileReader();
    reader.onload = async (e) => {
        const res = await fetch('/api/nodes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, text: text, image: e.target.result, ref_id: ref_id })
        });
        
        const responseData = await res.json();
        if (responseData.error) {
            alert(responseData.error);
        } else {
            document.getElementById("node-name").value = "";
            document.getElementById("node-text").value = "";
            document.getElementById("node-image").value = "";
            modal.style.display = "none"; 
            overlay.style.display = "none";
            loadGrid();
        }
    };
    reader.readAsDataURL(file);
};
