// admin.js - Admin Dashboard Logic

document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadMedia();
});

// Fetch Stats
function loadStats() {
    Promise.all([
        fetch('/admin/stats').then(r => r.json()),
        fetch('/public/stats').then(r => r.json())
    ]).then(([adminStats, publicStats]) => {
        const rcloneStatus = adminStats.rclone_configured ? '<span style="color: limegreen;">Configured</span>' : '<span style="color: orange;">Not Configured</span>';
        document.getElementById('stats').innerHTML = `
            <h3>System Metrics</h3>
            <strong>CPU:</strong> ${adminStats.cpu_percent}% (${adminStats.cpu_temp}) | <strong>RAM:</strong> ${adminStats.ram_percent}% (${adminStats.ram_used_gb}GB)<br>
            <strong>Storage:</strong> ${adminStats.disk_used_gb}GB / ${adminStats.disk_total_gb}GB (Free: ${adminStats.disk_free_gb}GB)<br>
            <strong>Rclone:</strong> ${rcloneStatus} | <strong>Last Backup:</strong> ${adminStats.last_backup}<br><br>

            <h3>Media Breakdown</h3>
            <strong>Total Media:</strong> ${publicStats.total_media}<br>
            <strong>Photos:</strong> ${publicStats.photos} | <strong>Videos:</strong> ${publicStats.videos}
        `;
    });
}

let searchTimeout = null;
function filterMedia() {
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        cursor = null; // Reset pagination
        document.getElementById('media-grid').innerHTML = '';
        loadMedia(); // Load media will now read from the filter inputs
    }, 300);
}

// Banner
async function setBanner() {
    const msg_en = document.getElementById('banner-input-en').value;
    const msg_es = document.getElementById('banner-input-es').value;
    const formData = new FormData();
    formData.append('message_en', msg_en);
    formData.append('message_es', msg_es);

    await fetch('/admin/banner', { method: 'POST', body: formData });
    showToast('Banners updated');
    updateCurrentBanner('en', msg_en);
    updateCurrentBanner('es', msg_es);
}

function clearBanners() {
    document.getElementById('banner-input-en').value = '';
    document.getElementById('banner-input-es').value = '';
    setBanner();
}


function updateCurrentBanner(lang, msg) {
    const display = document.getElementById(`current-banner-display-${lang}`);
    if (display) {
        display.innerText = msg ? `Current (${lang.toUpperCase()}): "${msg}"` : `No banner active (${lang.toUpperCase()})`;
        display.style.opacity = msg ? 1 : 0.5;
    }
}

// Init banner display
fetch('/config').then(r => r.json()).then(c => {
    document.getElementById('banner-input-en').value = c.banner_message_en || '';
    document.getElementById('banner-input-es').value = c.banner_message_es || '';
    updateCurrentBanner('en', c.banner_message_en);
    updateCurrentBanner('es', c.banner_message_es);
});

// Media
let cursor = null;

async function loadMedia() {
    const query = document.getElementById('media-search').value;
    const filter = document.querySelector('input[name="filter"]:checked').value;
    const type = document.querySelector('input[name="type"]:checked').value;

    let url = `/slideshow/feed?limit=20&admin_mode=true`;
    if (cursor) url += `&cursor=${cursor}`;
    if (query) url += `&q=${encodeURIComponent(query)}`;
    if (filter !== 'all') url += `&filter=${filter}`;
    if (type !== 'all') url += `&type=${type}`;

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
    if (!pin) {
        showToast("PIN is required.");
        return;
    }

    showConfirm("This will delete EVERYTHING: DB, uploads, archives, thumbnails. This is permanent.", () => {
        const fd = new FormData();
        fd.append('pin', pin);

        fetch('/admin/purge', { method: 'POST', body: fd })
            .then(async r => {
                if (r.ok) return r.json();
                const err = await r.json();
                throw new Error(err.detail || 'Purge failed');
            })
            .then(data => {
                if (data.status === 'purged') {
                    showToast("System Purged. Reloading page.");
                    setTimeout(() => location.reload(), 2000);
                }
            })
            .catch(e => {
                showToast(`Error: ${e.message}`);
            });

    }, true); // true = require checkbox

    hidePurgeModal();
}
