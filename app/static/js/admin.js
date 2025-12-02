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
        const cpuTemp = adminStats.cpu_temp !== "N/A" ? `(${adminStats.cpu_temp})` : '';

        // Populate Throttle Inputs
        document.getElementById('throttle-limit').value = adminStats.throttle_limit;
        document.getElementById('throttle-window').value = adminStats.throttle_window;

        document.getElementById('stats').innerHTML = `
            <h3>System Metrics</h3>
            <strong>CPU:</strong> ${adminStats.cpu_percent}% ${cpuTemp} | <strong>RAM:</strong> ${adminStats.ram_percent}% (${adminStats.ram_used_gb}GB)<br>
            <strong>Storage:</strong> ${adminStats.disk_used_gb}GB / ${adminStats.disk_total_gb}GB (Free: ${adminStats.disk_free_gb}GB)<br>
            <strong>Rclone:</strong> ${rcloneStatus} | <strong>Last Backup:</strong> ${adminStats.last_backup}<br>
            <strong>Timezone:</strong> ${adminStats.timezone}<br><br>

            <h3>Media Breakdown</h3>
            <strong>Total Media:</strong> ${publicStats.total_media}<br>
            <strong>Photos:</strong> ${publicStats.photos} | <strong>Videos:</strong> ${publicStats.videos}
        `;
    });
}

async function updateThrottle() {
    const limit = document.getElementById('throttle-limit').value;
    const window = document.getElementById('throttle-window').value;
    const fd = new FormData();
    fd.append('limit', limit);
    fd.append('window', window);

    const res = await fetch('/admin/throttle', { method: 'POST', body: fd });
    if (res.ok) {
        showToast("Throttling updated");
        loadStats();
    } else {
        showToast("Update failed");
    }
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

// Schedule
async function loadSchedule() {
    const res = await fetch('/admin/schedule');
    const schedule = await res.json();
    const list = document.getElementById('schedule-list');
    list.innerHTML = '';
    schedule.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'schedule-item';
        div.style.marginBottom = '10px';
        div.innerHTML = `
            <div><strong>${item.mode.toUpperCase()}</strong>: ${toLocalTime(item.start)} - ${toLocalTime(item.end)}</div>
            <div style="display:flex; gap:10px; margin-top:5px;">
                <input type="text" id="schedule-msg-${index}" value="${item.message || ''}" placeholder="Custom message..." style="flex:1;">
                <button class="btn-secondary" onclick="updateSchedule(${index})">Update</button>
                <button class="btn-secondary" style="border-color:red; color:red;" onclick="deleteSchedule(${index})">Delete</button>
            </div>
        `;
        list.appendChild(div);
    });
}

async function addSchedule() {
    const start = document.getElementById('schedule-start').value;
    const end = document.getElementById('schedule-end').value;
    const mode = document.getElementById('schedule-mode').value;
    const message = document.getElementById('schedule-message').value;

    if (!start || !end) {
        showToast("Please select a start and end time.");
        return;
    }

    const res = await fetch(`/admin/schedule?start=${start}&end=${end}&mode=${mode}&message=${message}`, { method: 'POST' });
    if (res.ok) {
        loadSchedule();
    } else {
        showToast("Failed to add schedule.");
    }
}

async function updateSchedule(index) {
    const message = document.getElementById(`schedule-msg-${index}`).value;
    const res = await fetch(`/admin/schedule/${index}?message=${encodeURIComponent(message)}`, { method: 'PUT' });
    if (res.ok) {
        showToast("Schedule updated.");
        loadSchedule();
    } else {
        showToast("Failed to update schedule.");
    }
}

async function deleteSchedule(index) {
    const res = await fetch(`/admin/schedule/${index}`, { method: 'DELETE' });
    if (res.ok) {
        loadSchedule();
    } else {
        showToast("Failed to delete schedule.");
    }
}

document.addEventListener('DOMContentLoaded', loadSchedule);

// Media
let cursor = null;
let isLoading = false;

async function loadMedia() {
    if (isLoading) return;

    const query = document.getElementById('media-search').value;
    const filter = document.querySelector('input[name="filter"]:checked').value;
    const type = document.querySelector('input[name="type"]:checked').value;
    const loadMoreBtn = document.getElementById('load-more-btn');

    let url = `/slideshow/feed?limit=6&admin_mode=true`;
    if (cursor) url += `&cursor=${cursor}`;
    if (query) url += `&q=${encodeURIComponent(query)}`;
    if (filter !== 'all') url += `&filter=${filter}`;
    if (type !== 'all') url += `&type=${type}`;

    isLoading = true;
    loadMoreBtn.innerText = "Loading...";
    loadMoreBtn.disabled = true;

    try {
        const res = await fetch(url);
        const data = await res.json();
        const grid = document.getElementById('media-grid');

        // Update cursor immediately
        cursor = data.next_cursor;

        if (data.items.length === 0 && !cursor && grid.innerHTML === '') {
            grid.innerHTML = '<p>No media found.</p>';
        }

        data.items.forEach(item => {
            // FIX 1: Deduplication Check
            // If the element ID already exists, do not append it again.
            if (document.getElementById(`media-item-${item.id}`)) return;

            const div = document.createElement('div');
            div.className = 'grid-item';
            div.id = `media-item-${item.id}`; // Add ID for the check above
            
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
                        ${toLocalTime(item.created_at)}<br>
                        ${formatBytes(item.file_size || 0)}
                    </div>
                </div>
            `;
            grid.appendChild(div);
        });

    } catch (err) {
        console.error("Error loading media:", err);
    } finally {
        // FIX 2: Re-enable button LAST
        // This ensures we don't allow a new click until the DOM is fully updated
        isLoading = false;
        loadMoreBtn.innerText = "Load More";

        if (cursor) {
            loadMoreBtn.disabled = false;
            loadMoreBtn.style.display = 'block';
        } else {
            loadMoreBtn.style.display = 'none';
        }
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
