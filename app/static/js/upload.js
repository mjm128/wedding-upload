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
        if (config.banner_message) {
            const b = document.getElementById('banner');
            b.innerText = config.banner_message;
            b.style.display = 'block';
            document.body.classList.add('has-banner');
        }
        window.APP_CONFIG = config;
    });

    // Theme Toggle Logic
    if (localStorage.getItem("theme") === "light") {
        document.documentElement.setAttribute("data-theme", "light");
    }

    // Init Lang
    const lang = localStorage.getItem("lang") || "en";
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
        // We use custom text logic here instead of simple i18n key replacement
        // because we need to insert the name.
        // Simple hack:
        const msg = t('welcome');
        welcome.innerText = `${msg} ${display}`;
    }
}

function handleNameSubmit(e) {
    e.preventDefault();
    const first = document.getElementById('first-name').value.trim();
    const last = document.getElementById('last-name').value.trim();

    // Validation
    const regex = /^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s-]+$/;
    if (!regex.test(first) || !regex.test(last)) {
        showToast("Invalid characters in name.");
        return;
    }
    if (first.length > 20 || last.length > 20) {
        showToast("Name too long (max 20 chars).");
        return;
    }

    const fullName = `${last}-${first}`;
    // Set cookie for 1 year
    document.cookie = `guest_name=${encodeURIComponent(fullName)}; max-age=31536000; path=/`;
    // Table number is legacy/optional now, set to 0
    document.cookie = `table_number=0; max-age=31536000; path=/`;

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
                img.style.maxWidth = '100%';
                img.style.borderRadius = '8px';
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
                <div class="glass-card" style="padding: 10px; margin:0;">
                    ${item.type === 'video' ? '<span style="color:gold; font-size:0.8em;">[VIDEO]</span>' : ''}
                    <img src="${item.thumbnail || item.url}" class="media-content" loading="lazy">
                    ${item.caption ? `<p style="margin-top:5px; font-size:0.9em;">${item.caption}</p>` : ''}
                </div>
            `;
            grid.appendChild(div);
        });
        container.appendChild(grid);

    } catch (e) {
        console.error("Failed to load uploads", e);
    }
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
