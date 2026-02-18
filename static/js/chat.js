const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const roleSelector = document.getElementById('role-selector');
const currentRoleDisplay = document.getElementById('current-role');
const typingIndicator = document.getElementById('typing-indicator');
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const token = localStorage.getItem('token');
if (!token && window.location.pathname === '/chat') {
    window.location.href = '/';
}

let currentUser = {
    full_name: 'User',
    email: '',
    initials: 'U'
};

async function fetchUserInfo() {
    try {
        const res = await fetch('/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            currentUser = await res.json();
            currentUser.initials = currentUser.full_name
                .split(' ')
                .map(n => n[0])
                .join('')
                .toUpperCase()
                .substring(0, 2);

            // Update Sidebar
            document.getElementById('user-name').textContent = currentUser.full_name;
            const avatarContainer = document.getElementById('user-avatar-container');
            const initialsEl = document.getElementById('user-avatar-initials');

            if (currentUser.profile_image) {
                avatarContainer.innerHTML = `<img src="${currentUser.profile_image}" class="w-full h-full object-cover">`;
            } else {
                if (initialsEl) initialsEl.textContent = currentUser.initials;
            }
        }
    } catch (err) {
        console.error('Failed to fetch user info:', err);
    }
}

function logout() {
    localStorage.removeItem('token');
    window.location.href = '/';
}

fetchUserInfo();

const sessionId = Math.random().toString(36).substring(7);
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(`${wsProtocol}//${window.location.host}/api/v1/chat/ws/chat/${sessionId}?token=${token}`);

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'error' && data.content === 'Unauthorized') {
        localStorage.removeItem('token');
        window.location.href = '/';
        return;
    }
    if (data.type === 'chunk') {
        typingIndicator.classList.add('hidden');
        let lastMsg = chatMessages.lastElementChild;
        if (!lastMsg || !lastMsg.classList.contains('ai-msg-container')) {
            lastMsg = appendMessage('ai', '');
        }
        const textEl = lastMsg.querySelector('.msg-content');
        // Accumulate raw text in a data attribute
        lastMsg.dataset.raw = (lastMsg.dataset.raw || '') + data.content;
        // Parse and render accumulated markdown
        textEl.innerHTML = marked.parse(lastMsg.dataset.raw);

        // Handle Sources/Images if present in the chunk metadata
        if (data.sources && data.sources.length > 0) {
            const sourcesContainer = lastMsg.querySelector('.sources-container');
            if (sourcesContainer) {
                data.sources.forEach(source => {
                    // Avoid duplicates
                    if (!sourcesContainer.querySelector(`[src="${source.image_url}"]`) && source.image_url) {
                        sourcesContainer.classList.remove('hidden');
                        const img = document.createElement('img');
                        img.src = source.image_url;
                        img.className = "rounded-lg border border-slate-700 shadow-md hover:scale-105 transition-transform cursor-pointer";
                        img.onclick = () => window.open(source.image_url, '_blank');
                        sourcesContainer.appendChild(img);
                    }
                });
            }
        }
    } else if (data.type === 'done') {
        typingIndicator.classList.add('hidden');
    }
    chatMessages.scrollTop = chatMessages.scrollHeight;
};

// File Upload
dropZone.onclick = () => fileInput.click();
fileInput.onchange = async () => {
    const files = Array.from(fileInput.files);
    if (files.length === 0) return;

    const fileMap = new Map();
    const formData = new FormData();

    files.forEach(file => {
        formData.append('files', file);
        const li = document.createElement('li');
        li.className = "text-xs p-2 bg-slate-800/50 border border-slate-700 rounded flex items-center justify-between animate-in fade-in zoom-in duration-300";
        li.innerHTML = `
            <span class="truncate pr-2">${file.name}</span>
            <span class="status-icon animate-pulse text-indigo-400">⏳</span>
        `;
        fileList.appendChild(li);
        fileMap.set(file.name, li);
    });

    try {
        const res = await fetch('/api/v1/documents/upload', {
            method: 'POST',
            body: formData
        });

        let result = {};
        try {
            result = await res.json();
        } catch (e) {
            console.error('Response was not JSON:', e);
        }

        if (res.ok) {
            // Success
            files.forEach(file => {
                const li = fileMap.get(file.name);
                if (li) {
                    li.className = "text-xs p-2 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded flex items-center justify-between";
                    li.innerHTML = `
                        <span class="truncate pr-2">${file.name}</span>
                        <span class="text-emerald-500">✅</span>
                    `;
                }
            });
        } else {
            // Server Error (e.g. OCR failed)
            const errorMsg = result.detail || 'Upload failed';
            console.error('Server error:', errorMsg);
            files.forEach(file => {
                const li = fileMap.get(file.name);
                if (li) {
                    li.className = "text-xs p-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded flex flex-col gap-1";
                    li.innerHTML = `
                        <div class="flex items-center justify-between w-full font-medium">
                            <span class="truncate pr-2">${file.name}</span>
                            <span>❌</span>
                        </div>
                        <p class="text-[10px] leading-tight text-red-300 opacity-80">${errorMsg}</p>
                    `;
                }
            });
        }
    } catch (error) {
        console.error('Network or JS error:', error);
        files.forEach(file => {
            const li = fileMap.get(file.name);
            if (li) {
                li.className = "text-xs p-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded flex items-center justify-between";
                li.innerHTML = `
                    <span class="truncate pr-2">Network Error</span>
                    <span class="text-red-500">⚠️</span>
                `;
            }
        });
    }

    // Clear input so same file can be re-uploaded if needed
    fileInput.value = '';
};

// Chat
chatForm.onsubmit = (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;

    appendMessage('user', message);
    ws.send(json.stringify({
        message: message,
        role: roleSelector.value
    }));

    userInput.value = '';
    typingIndicator.classList.remove('hidden');
};

roleSelector.onchange = () => {
    currentRoleDisplay.textContent = roleSelector.value;
};

function appendMessage(role, text) {
    const div = document.createElement('div');
    if (role === 'user') {
        div.className = "flex gap-4 items-start flex-row-reverse animate-in fade-in slide-in-from-right duration-300";
        const avatarHtml = currentUser.profile_image
            ? `<img src="${currentUser.profile_image}" class="w-full h-full object-cover rounded-xl shadow-lg ring-2 ring-slate-600/50">`
            : `<div class="w-10 h-10 rounded-xl bg-slate-700 flex-shrink-0 flex items-center justify-center text-white font-bold ring-2 ring-slate-600/50 shadow-lg">${currentUser.initials}</div>`;

        div.innerHTML = `
            <div class="w-10 h-10 flex-shrink-0">
                ${avatarHtml}
            </div>
            <div class="space-y-1 text-right">
                <p class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest px-1">${currentUser.full_name}</p>
                <div class="bg-indigo-600 p-4 rounded-2xl rounded-tr-none shadow-xl shadow-indigo-600/10">
                    <p class="text-sm leading-relaxed text-white">${text}</p>
                </div>
            </div>
        `;
    } else {
        div.className = "flex gap-4 items-start ai-msg-container animate-in fade-in slide-in-from-left duration-300";
        div.innerHTML = `
            <div class="w-10 h-10 rounded-xl bg-indigo-600 flex-shrink-0 flex items-center justify-center text-white font-bold shadow-lg shadow-indigo-600/20">
                AI
            </div>
            <div class="space-y-1">
                <p class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest px-1">Enterprise AI</p>
                <div class="bg-slate-800/80 backdrop-blur-sm p-4 rounded-2xl rounded-tl-none border border-slate-700/50 shadow-xl">
                    <div class="text-sm leading-relaxed msg-content">${text}</div>
                    <div class="sources-container grid grid-cols-2 gap-2 mt-4 hidden"></div>
                </div>
            </div>
        `;
    }
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}

const json = {
    stringify: JSON.stringify,
    parse: JSON.parse
};
