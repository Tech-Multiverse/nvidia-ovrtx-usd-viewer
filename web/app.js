// DOM elements used across the UI.
const statusEl = document.getElementById('status');
const streamEl = document.getElementById('stream');
const selectedPathEl = document.getElementById('selected-path');
const primListEl = document.getElementById('prim-list');
const scenePathEl = document.getElementById('scene-path');
const selectedPanel = document.getElementById('selected-panel');

let ws = null;
let reconnectTimer = null;
let selectedPath = null;

function setStatus(text) {
    statusEl.textContent = text;
}

function connect() {
    // Open a WebSocket to the same host that served the page.
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${window.location.host}/ws`;
    ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';

    ws.onopen = async () => {
        setStatus('Connected');
        // Ask the server for the default scene path and load it automatically.
        try {
            const res = await fetch('/api/default_scene');
            const data = await res.json();
            if (data.path) {
                setStatus('Loading default scene...');
                send({ cmd: 'load', path: data.path });
            }
        } catch (err) {
            console.error('Failed to fetch default scene', err);
        }
        // Refresh the prim list once the default scene is loaded.
        send({ cmd: 'list_prims' });
    };

    ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
            // Binary messages are JPEG frames. Update the image and clean up
            // the previous blob URL to avoid memory leaks.
            const blob = new Blob([event.data], { type: 'image/jpeg' });
            const oldUrl = streamEl.src;
            streamEl.src = URL.createObjectURL(blob);
            if (oldUrl && oldUrl.startsWith('blob:')) {
                URL.revokeObjectURL(oldUrl);
            }
        } else {
            handleMessage(JSON.parse(event.data));
        }
    };

    ws.onclose = () => {
        setStatus('Disconnected — reconnecting...');
        if (!reconnectTimer) {
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                connect();
            }, 2000);
        }
    };

    ws.onerror = () => setStatus('WebSocket error');
}

function send(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(msg));
    }
}

function handleMessage(msg) {
    if (!msg.ok) {
        console.error('Command failed:', msg.error);
        setStatus(`Error: ${msg.error}`);
        return;
    }

    switch (msg.cmd) {
        case 'pick':
            if (msg.path) {
                selectedPath = msg.path;
                selectPrim(msg.path);
            } else {
                setStatus('No prim picked');
            }
            break;
        case 'select':
            selectedPath = msg.selected;
            updateSelectedUI();
            break;
        case 'list_prims':
            renderPrimList(msg.prims);
            break;
        case 'load':
            setStatus(`Loaded ${msg.scene}`);
            send({ cmd: 'list_prims' });
            break;
        case 'translate':
        case 'rotate':
        case 'scale':
        case 'camera':
            // visual feedback comes from the stream
            break;
    }
}

function selectPrim(path) {
    selectedPath = path;
    updateSelectedUI();
    send({ cmd: 'select', path });
}

function updateSelectedUI() {
    selectedPathEl.textContent = selectedPath || 'none';
    selectedPanel.classList.toggle('active', !!selectedPath);
    for (const li of primListEl.children) {
        li.classList.toggle('selected', li.dataset.path === selectedPath);
    }
}

function renderPrimList(paths) {
    // Render every prim path as a clickable list item.
    primListEl.innerHTML = '';
    for (const path of paths) {
        const li = document.createElement('li');
        li.textContent = path;
        li.dataset.path = path;
        li.title = path;
        li.addEventListener('click', () => selectPrim(path));
        primListEl.appendChild(li);
    }
    updateSelectedUI();
}

streamEl.addEventListener('click', (event) => {
    // Convert click coordinates to normalized 0..1 image space and ask the
    // server to pick the prim at that pixel.
    const rect = streamEl.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    send({ cmd: 'pick', x, y });
});

document.getElementById('btn-load').addEventListener('click', () => {
    const path = scenePathEl.value.trim();
    if (path) {
        send({ cmd: 'load', path });
    }
});

// File picker wiring: clicking Browse opens the hidden <input type="file">.
const sceneFileEl = document.getElementById('scene-file');
const browseBtn = document.getElementById('btn-browse');

browseBtn.addEventListener('click', () => sceneFileEl.click());

sceneFileEl.addEventListener('change', async () => {
    const file = sceneFileEl.files[0];
    if (!file) return;
    setStatus('Uploading scene...');
    const formData = new FormData();
    formData.append('file', file);
    try {
        // Upload the file to the server, then load the returned path.
        const res = await fetch('/api/upload_scene', { method: 'POST', body: formData });
        const data = await res.json();
        if (!data.path) {
            throw new Error(data.error || 'Upload failed');
        }
        scenePathEl.value = data.path;
        send({ cmd: 'load', path: data.path });
    } catch (err) {
        console.error('Upload failed', err);
        setStatus('Upload failed: ' + err.message);
    }
});

document.getElementById('btn-list').addEventListener('click', () => {
    send({ cmd: 'list_prims' });
});

// Wire up every transform/camera button that declares data-cmd attributes.
for (const btn of document.querySelectorAll('button[data-cmd]')) {
    const cmd = btn.dataset.cmd;
    btn.addEventListener('click', () => {
        const payload = { cmd };
        if (cmd === 'translate') {
            payload.dx = parseFloat(btn.dataset.dx);
            payload.dy = parseFloat(btn.dataset.dy);
            payload.dz = parseFloat(btn.dataset.dz);
        } else if (cmd === 'rotate') {
            payload.axis = btn.dataset.axis;
            payload.degrees = parseFloat(btn.dataset.degrees);
        } else if (cmd === 'scale') {
            payload.sx = parseFloat(btn.dataset.sx);
            payload.sy = parseFloat(btn.dataset.sy);
            payload.sz = parseFloat(btn.dataset.sz);
        } else if (cmd === 'camera') {
            payload.dx = parseFloat(btn.dataset.dx);
            payload.dy = parseFloat(btn.dataset.dy);
            payload.dz = parseFloat(btn.dataset.dz);
        }
        send(payload);
    });
}

connect();
