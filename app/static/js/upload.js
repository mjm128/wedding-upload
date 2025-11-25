// upload.js - Handles file selection, preview, and upload with retry logic

let selectedFile = null;

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    // Register Service Worker
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js');
    }

    // Check for Config/Banner
    fetch('/config').then(r => r.json()).then(config => {
        const bannerMsg = config[`banner_message_${currentLang}`] || config[`banner_message_en`];
        if (bannerMsg) {
            const b = document.getElementById('banner');
            b.innerText = bannerMsg;
            b.style.display = 'block';
            document.body.classList.add('has-banner');
        }
        window.APP_CONFIG = config;
    });

    // Theme Toggle Logic
    if (localStorage.getItem("theme") === "light") {
        document.documentElement.setAttribute("data-theme", "light");
    }

    // Init Lang (Auto-detect if not set)
    let lang = localStorage.getItem("lang");
    if (!lang) {
        const browserLang = navigator.language || navigator.userLanguage;
        lang = browserLang.startsWith('es') ? 'es' : 'en';
    }
    setLanguage(lang);
    const btn = document.getElementById('lang-btn');
    if (btn) btn.innerText = lang.toUpperCase();

    // Check Guest Name
    checkGuestName();

    loadMyUploads();
});

function checkGuestName() {
    const name = getCookie("guest_name");
    if (!name) {
        document.getElementById('setup-modal').style.display = 'flex';
    } else {
        const display = name.split('-').reverse().join(' ');
        const welcome = document.getElementById('guest-welcome');
        welcome.innerText = t('welcome').replace('{name}', display);

        // Ensure UUID exists
        if (!getCookie("guest_uuid")) {
            document.cookie = `guest_uuid=${crypto.randomUUID()}; max-age=31536000; path=/; SameSite=Lax`;
        }
    }
}

function handleNameSubmit(e) {
    e.preventDefault();
    const first = document.getElementById('first-name').value.trim();
    const last = document.getElementById('last-name').value.trim();

    const regex = /^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s-]+$/;
    if (!regex.test(first) || !regex.test(last)) {
        showToast("Invalid characters in name. Use letters, numbers, spaces, hyphens.");
        return;
    }
    if (first.length > 20 || last.length > 20) {
        showToast("Name too long (max 20 chars).");
        return;
    }

    const fullName = `${last}-${first}`;
    document.cookie = `guest_name=${encodeURIComponent(fullName)}; max-age=31536000; path=/; SameSite=Lax`;
    document.cookie = `table_number=0; max-age=31536000; path=/; SameSite=Lax`;

    // Set UUID
    if (!getCookie("guest_uuid")) {
        document.cookie = `guest_uuid=${crypto.randomUUID()}; max-age=31536000; path=/; SameSite=Lax`;
    }

    document.getElementById('setup-modal').style.display = 'none';
    checkGuestName();
    loadMyUploads();
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return decodeURIComponent(parts.pop().split(';').shift());
}

function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
}

// --- File Handling ---

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Validate Size
    const maxSize = (window.APP_CONFIG?.max_file_size_mb || 500) * 1024 * 1024;
    if (file.size > maxSize) {
        showToast("File too large!");
        return;
    }

    // Video Duration Check (basic)
    if (file.type.startsWith('video')) {
         const video = document.createElement('video');
         video.preload = 'metadata';
         video.onloadedmetadata = function() {
             window.URL.revokeObjectURL(video.src);
             const maxDuration = window.APP_CONFIG?.max_video_duration_sec || 60;
             if (video.duration > maxDuration) {
                 showToast("Video too long! Max " + maxDuration + " seconds.");
                 resetSelection();
                 return;
             }
         }
         video.src = URL.createObjectURL(file);
    }

    selectedFile = file;
    document.getElementById('upload-btn').style.display = 'block';

    // Preview using blueimp-load-image for orientation fix
    const previewArea = document.getElementById('preview-area');
    previewArea.innerHTML = 'Generating preview...';

    if (file.type.startsWith('image')) {
        loadImage(
            file,
            function (img) {
                previewArea.innerHTML = '';
                previewArea.appendChild(img);
            },
            { maxWidth: 600, orientation: true }
        );
    } else {
        previewArea.innerHTML = `<div class="glass-card" style="padding:10px">Video selected: ${file.name}</div>`;
    }
}

function resetSelection() {
    selectedFile = null;
    document.getElementById('preview-area').innerHTML = '';
    document.getElementById('upload-btn').style.display = 'none';
    document.getElementById('file-input').value = '';
}

// --- Upload Logic with Retry ---

document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!selectedFile) return;

            // Wake Lock
            let wakeLock = null;
            try {
                wakeLock = await navigator.wakeLock.request('screen');
            } catch (err) {
                console.log('Wake Lock not supported or denied');
            }

            const caption = document.getElementById('caption').value;
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('caption', caption);

            const progressBar = document.getElementById('progress-bar');
            const progressContainer = document.getElementById('progress-bar-container');
            const uploadBtn = document.getElementById('upload-btn');

            progressContainer.style.display = 'block';
            uploadBtn.disabled = true;
            uploadBtn.innerText = 'Uploading...';

            // Retry Logic
            const maxRetries = 3;
            let attempt = 0;
            let success = false;

            while (attempt < maxRetries && !success) {
                try {
                    await uploadWithProgress(formData, (percent) => {
                        progressBar.style.width = percent + '%';
                    });
                    success = true;
                } catch (error) {
                    console.error(`Upload attempt ${attempt + 1} failed:`, error);
                    attempt++;
                    if (attempt < maxRetries) {
                        uploadBtn.innerText = `Retrying (${attempt}/${maxRetries})...`;
                        await new Promise(r => setTimeout(r, 2000 * attempt)); // Exponential backoffish
                    } else {
                        alert('Upload failed after multiple attempts. Please check your connection.');
                    }
                }
            }

            if (success) {
                showToast('Upload Successful!');
                resetSelection();
                document.getElementById('caption').value = '';
                progressContainer.style.display = 'none';
                loadMyUploads();

                // Post Upload Action
                if (window.APP_CONFIG && window.APP_CONFIG.post_upload_url) {
                    showConfirm(`Upload complete! Go to ${window.APP_CONFIG.post_upload_label || 'next step'}?`, () => {
                         window.location.href = window.APP_CONFIG.post_upload_url;
                    });
                }
            }

            uploadBtn.disabled = false;
            uploadBtn.innerText = 'Upload';
            if (wakeLock) wakeLock.release();
        });
    }
});

async function loadMyUploads() {
    const container = document.getElementById('my-uploads');
    if (!container) return;

    try {
        const res = await fetch('/my-uploads');
        const data = await res.json();

        if (data.length === 0) {
            container.innerHTML = '<p style="text-align:center; opacity:0.7;">No uploads yet.</p>';
            return;
        }

        container.innerHTML = '';
        const grid = document.createElement('div');
        grid.className = 'masonry-grid';

        data.forEach(item => {
            const div = document.createElement('div');
            div.className = 'grid-item';
            div.innerHTML = `
                <div class="glass-card" style="padding: 10px; margin:0; position:relative;">
                    ${item.type === 'video' ? '<span style="color:gold; font-size:0.8em;">[VIDEO]</span>' : ''}
                    <button onclick="deleteUpload(${item.id})" style="position:absolute; top:5px; right:5px; background:rgba(0,0,0,0.5); color:white; border:none; border-radius:50%; width:24px; height:24px; cursor:pointer;">&times;</button>
                    <img src="${item.thumbnail || item.url}" class="media-content" loading="lazy" onclick="previewImage('${item.url}', '${item.type}')" style="cursor:zoom-in;">
                    <div style="margin-top:5px; font-size:0.8em;">
                        ${item.caption ? `<p style="margin:0;">${item.caption}</p>` : ''}
                        <span style="color:#888; font-size:0.8em;">${new Date(item.created_at).toLocaleString()} | ${formatBytes(item.file_size || 0)}</span>
                    </div>
                </div>
            `;
            grid.appendChild(div);
        });
        container.appendChild(grid);

    } catch (e) {
        console.error("Failed to load uploads", e);
    }
}


function previewImage(url, type) {
    if (type === 'video') return; // Or implement video player modal

    const modalId = 'preview-modal';
    let modal = document.getElementById(modalId);
    if (!modal) {
        modal = document.createElement('div');
        modal.id = modalId;
        modal.style.cssText = "position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:3000; display:flex; align-items:center; justify-content:center;";
        modal.innerHTML = `
            <div style="position:relative; max-width:95%; max-height:95%;">
                <button onclick="document.getElementById('${modalId}').style.display='none'" style="position:absolute; top:-30px; right:0; color:white; background:none; border:none; font-size:30px; cursor:pointer;">&times;</button>
                <img id="${modalId}-img" style="max-width:100%; max-height:90vh; border-radius:8px;">
            </div>
        `;
        document.body.appendChild(modal);
        modal.onclick = (e) => { if(e.target === modal) modal.style.display='none'; };
    }

    document.getElementById(`${modalId}-img`).src = url;
    modal.style.display = 'flex';
}

async function deleteUpload(id) {
    showConfirm(t('confirm_delete'), async () => {
        try {
            const res = await fetch(`/media/${id}`, { method: 'DELETE' });
            if (res.ok) {
                showToast("Deleted");
                loadMyUploads();
            } else {
                const err = await res.json();
                showToast(err.detail || "Delete failed");
            }
        } catch (e) {
            console.error(e);
            showToast("Delete failed");
        }
    });
}

function uploadWithProgress(formData, onProgress) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/upload', true);

        xhr.upload.onprogress = function(e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                onProgress(percentComplete);
            }
        };

        xhr.onload = function() {
            if (xhr.status === 200) {
                resolve(xhr.responseText);
            } else {
                reject(new Error(xhr.statusText || 'Upload failed'));
            }
        };

        xhr.onerror = function() {
            reject(new Error('Network error'));
        };

        xhr.send(formData);
    });
}
