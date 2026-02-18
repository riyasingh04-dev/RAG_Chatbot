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
fetchFiles();

async function fetchFiles() {
    try {
        const res = await fetch('/api/v1/documents');
        if (res.ok) {
            const files = await res.json();
            fileList.innerHTML = ''; // Clear existing
            files.forEach(filename => {
                addFileToList(filename, 'success');
            });
        }
    } catch (err) {
        console.error('Failed to fetch files:', err);
    }
}

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

                        // Create wrapper for image + caption
                        const wrapper = document.createElement('div');
                        wrapper.className = "relative group";

                        const img = document.createElement('img');
                        img.src = source.image_url;
                        img.className = "w-full rounded-lg border border-slate-700 shadow-md hover:scale-105 transition-transform cursor-pointer object-cover";
                        img.onclick = () => window.open(source.image_url, '_blank');

                        // Caption overlay
                        const caption = document.createElement('div');
                        caption.className = "absolute bottom-0 left-0 right-0 bg-black/70 text-[10px] text-white p-1 rounded-b-lg opacity-0 group-hover:opacity-100 transition-opacity truncate";
                        caption.textContent = `${source.title} (Pg ${source.page})`;

                        wrapper.appendChild(img);
                        wrapper.appendChild(caption);
                        sourcesContainer.appendChild(wrapper);
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
        addFileToList(file.name, 'loading', fileMap);
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
                addFileToList(file.name, 'success', fileMap);
            });
        } else {
            // Server Error (e.g. OCR failed)
            const errorMsg = result.detail || 'Upload failed';
            console.error('Server error:', errorMsg);
            files.forEach(file => {
                addFileToList(file.name, 'error', fileMap, errorMsg);
            });
        }
    } catch (error) {
        console.error('Network or JS error:', error);
        files.forEach(file => {
            addFileToList(file.name, 'error', fileMap, 'Network Error');
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

function addFileToList(filename, status, map = null, errorMessage = '') {
    let li = map ? map.get(filename) : null;
    if (!li) {
        li = document.createElement('li');
        fileList.appendChild(li);
        if (map) map.set(filename, li);
    }

    if (status === 'loading') {
        li.className = "text-xs p-2.5 bg-slate-800/50 border border-slate-700 rounded-xl flex items-center justify-between animate-in fade-in zoom-in duration-300";
        li.innerHTML = `
            <div class="min-w-0 flex-1 mr-2">
                <p class="truncate text-slate-400">${filename}</p>
            </div>
            <span class="animate-spin text-indigo-400 text-[10px] flex-shrink-0">⏳</span>
        `;
    } else if (status === 'success') {
        console.log(`Rendering success state for: ${filename}`);
        li.className = "text-xs p-2.5 bg-emerald-500/5 border border-emerald-500/20 rounded-xl flex items-center justify-between group/item hover:bg-emerald-500/10 transition-colors";
        li.innerHTML = `
            <div class="min-w-0 flex-1 mr-2">
                <p class="truncate text-emerald-100 font-medium">${filename}</p>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
                <span class="text-emerald-500 text-[10px]">✅</span>
                <button onclick="deleteFile('${filename.replace(/'/g, "\\'")}', this.closest('li'))" 
                        class="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-800 text-slate-400 hover:bg-red-500/20 hover:text-red-400 transition-all border border-slate-700 hover:border-red-500/30"
                        title="Delete file">
                    🗑️
                </button>
            </div>
        `;
    } else if (status === 'error') {
        li.className = "text-xs p-2.5 bg-red-500/5 border border-red-500/20 rounded-xl flex flex-col gap-1";
        li.innerHTML = `
            <div class="flex items-center justify-between w-full">
                <div class="min-w-0 flex-1 mr-2">
                    <p class="truncate text-red-100 font-medium">${filename}</p>
                </div>
                <span class="text-red-500 flex-shrink-0">❌</span>
            </div>
            ${errorMessage ? `<p class="text-[10px] leading-tight text-red-400/80">${errorMessage}</p>` : ''}
        `;
    }
}

async function deleteFile(filename, li) {
    const originalContent = li.innerHTML;
    const statusIcon = li.querySelector('.text-emerald-500') || li.querySelector('button');

    // Show loading
    li.innerHTML = `
        <span class="truncate pr-2 text-slate-400">${filename}</span>
        <span class="animate-spin text-indigo-400 text-[10px]">⏳</span>
    `;

    try {
        const res = await fetch(`/api/v1/documents/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });

        if (res.ok) {
            li.classList.add('fade-out');
            setTimeout(() => li.remove(), 300);
            showToast('File deleted successfully', 'success');
        } else {
            throw new Error('Delete failed');
        }
    } catch (err) {
        console.error('Delete error:', err);
        li.innerHTML = `
            <span class="truncate pr-2 text-red-400">${filename}</span>
            <span class="text-red-500" title="${err.message}">❌</span>
        `;
        showToast('Failed to delete file', 'error');
        // Reset after 3 seconds
        setTimeout(() => {
            if (li.parentElement) li.innerHTML = originalContent;
        }, 3000);
    }
}

function showToast(message, type = 'success') {
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'fixed bottom-24 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 pointer-events-none';
        document.body.appendChild(toastContainer);
    }

    const toast = document.createElement('div');
    const bgColor = type === 'success' ? 'bg-emerald-600' : 'bg-red-600';
    toast.className = `${bgColor} text-white px-6 py-3 rounded-full shadow-2xl text-sm font-medium animate-in slide-in-from-bottom duration-300 pointer-events-auto`;
    toast.textContent = message;

    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.classList.replace('animate-in', 'animate-out');
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

const json = {
    stringify: JSON.stringify,
    parse: JSON.parse
};
