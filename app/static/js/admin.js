// admin.js - Admin Dashboard Logic

document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadMedia();
});

// Fetch Stats
function loadStats() {
    fetch('/admin/stats').then(r => r.json()).then(data => {
        document.getElementById('stats').innerHTML = `
            <h3>System Metrics</h3>
            <strong>CPU:</strong> ${data.cpu_percent}% | <strong>RAM:</strong> ${data.ram_percent}% (${data.ram_used_gb}GB)<br>
            <strong>Storage:</strong> ${data.disk_used_gb}GB / ${data.disk_total_gb}GB (Free: ${data.disk_free_gb}GB)<br>
            <strong>Last Backup:</strong> ${data.last_backup}<br><br>

            <h3>Media Breakdown</h3>
            <strong>Total Media:</strong> ${data.media_total}<br>
            <strong>Photos:</strong> ${data.media_photos} | <strong>Videos:</strong> ${data.media_videos}
        `;
    });
}

let searchTimeout = null;
function filterMedia() {
    const query = document.getElementById('media-search').value;
    if (searchTimeout) clearTimeout(searchTimeout);

    searchTimeout = setTimeout(() => {
        cursor = null; // Reset pagination
        document.getElementById('media-grid').innerHTML = '';
        loadMedia(query);
    }, 500);
}

// Banner
async function setBanner(msg) {
    const val = msg !== undefined ? msg : document.getElementById('banner-input').value;
    const formData = new FormData();
    formData.append('message', val);
    await fetch('/admin/banner', { method: 'POST', body: formData });
    showToast('Banner updated');
    document.getElementById('banner-input').value = val || '';
    updateCurrentBanner(val);
}

function updateCurrentBanner(msg) {
    const display = document.getElementById('current-banner-display');
    if (display) {
        display.innerText = msg ? `Current: "${msg}"` : "No banner active";
        display.style.opacity = msg ? 1 : 0.5;
    }
}

// Init banner display
fetch('/config').then(r => r.json()).then(c => {
    if(c.banner_message) {
        document.getElementById('banner-input').value = c.banner_message;
        updateCurrentBanner(c.banner_message);
    } else {
        updateCurrentBanner("");
    }
});

// Media
let cursor = null;

async function loadMedia(query = null) {
    let url = '/slideshow/feed?limit=20';
    if (cursor) url += '&cursor=' + cursor;
    if (query) url += '&q=' + encodeURIComponent(query);

    const res = await fetch(url);
    const data = await res.json();

    const grid = document.getElementById('media-grid');

    if (data.items.length === 0 && !cursor) {
        if (grid.innerHTML === '') grid.innerHTML = '<p>No media found.</p>';
        return;
    }

    data.items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'grid-item';
        div.innerHTML = `
            <div class="glass-card" style="padding: 10px;">
                <div style="font-size:0.7em; color:#aaa; margin-bottom:5px;">UUID: ${item.filename.split('/').pop().split('.')[0]}</div>
                ${item.type === 'video' ? '<span style="color:gold; font-weight:bold;">[VIDEO]</span>' : ''}
                <img src="${item.thumbnail || item.url}" class="media-content ${item.is_hidden ? 'hidden-media' : ''} ${item.is_starred ? 'starred-media' : ''}" loading="lazy">
                <p><strong>${item.author || 'Guest'}</strong><br>${item.caption || ''}</p>
                <div style="display: flex; gap: 5px; flex-wrap: wrap;">
                    <button class="btn-secondary" style="padding: 5px; flex:1;" onclick="action(${item.id}, '${item.is_hidden ? 'unhide' : 'hide'}')">${item.is_hidden ? 'Unhide' : 'Hide'}</button>
                    <button class="btn-secondary" style="padding: 5px; flex:1;" onclick="action(${item.id}, '${item.is_starred ? 'unstar' : 'star'}')">${item.is_starred ? 'Unstar' : 'Star'}</button>
                    <button class="btn-secondary" style="padding: 5px; color: red; border-color: red; flex:1;" onclick="action(${item.id}, 'delete')">Delete</button>
                </div>
                <div style="margin-top:5px; font-size:0.8em; color:#888;">
                    ${new Date(item.created_at).toLocaleString()}<br>
                    ${formatBytes(item.file_size || 0)}
                </div>
            </div>
        `;
        grid.appendChild(div);
    });

    if (data.items.length > 0) {
        // Fix: Only update cursor if the new items provide a new cursor (older items)
        // The backend returns next_cursor as the created_at of the LAST item.
        cursor = data.next_cursor;
        document.getElementById('load-more-btn').style.display = 'block';
    } else {
        document.getElementById('load-more-btn').style.display = 'none';
    }
}

async function action(id, act) {
    if (act === 'delete') {
        showConfirm('Are you sure you want to delete this?', async () => {
            await performAction(id, act);
        });
    } else {
        await performAction(id, act);
    }
}

async function performAction(id, act) {
    const fd = new FormData();
    fd.append('action', act);
    const res = await fetch(`/admin/media/${id}/action`, { method: 'POST', body: fd });

    if (res.ok) {
        document.getElementById('media-grid').innerHTML = '';
        cursor = null;
        loadMedia();
    } else {
        showToast("Action failed");
    }
}

function showPurgeModal() {
    document.getElementById('purge-modal').style.display = 'flex';
}

function hidePurgeModal() {
    document.getElementById('purge-modal').style.display = 'none';
    document.getElementById('purge-pin').value = '';
}

function submitPurge() {
    const pin = document.getElementById('purge-pin').value;
    if (!pin) return;

    const fd = new FormData();
    fd.append('pin', pin);

    fetch('/admin/purge', { method: 'POST', body: fd })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'purged') {
                showToast("System Purged. Reloading.");
                setTimeout(() => location.reload(), 2000);
            } else {
                showToast("Purge failed: " + (data.detail || 'Unknown error'));
            }
        })
        .catch(e => showToast("Error: " + e));

    hidePurgeModal();
}
