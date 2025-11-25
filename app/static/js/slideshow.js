// slideshow.js - Handles the live slideshow logic

let queue = [];
let currentIndex = -1;
let container = document.getElementById('container');
let cursor = null; // Timestamp for pagination/newest
let isFetching = false;

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    loadInitial();

    // Config poller
    setInterval(pollConfig, 30000);

    // Stats poller
    pollStats();
    setInterval(pollStats, 60000);
});

async function pollConfig() {
     fetch('/config').then(r => r.json()).then(config => {
        if (config.banner_message) {
            const b = document.getElementById('banner');
            b.innerText = config.banner_message;
            b.style.display = 'block';
            document.body.classList.add('has-banner');
        } else {
            document.getElementById('banner').style.display = 'none';
            document.body.classList.remove('has-banner');
        }
    });
}

async function pollStats() {
    try {
        const res = await fetch('/public/stats');
        const data = await res.json();
        const el = document.getElementById('stats-overlay');
        if (el) {
            el.innerHTML = `📸 ${data.photos} | 🎥 ${data.videos}`;
        }
    } catch (e) {
        console.error("Stats poll failed", e);
    }
}

// --- Media Fetching ---

async function loadInitial() {
    // Load existing media (limit 50)
    try {
        const res = await fetch('/slideshow/feed?limit=50');
        const data = await res.json();
        queue = data.items;

        if (queue.length > 0) {
            // Start the show
            nextSlide();
        } else {
            container.innerHTML = '<div style="color:white; font-family:var(--header-font)">Waiting for uploads...</div>';
            setTimeout(loadInitial, 5000);
        }
    } catch (e) {
        console.error("Initial load failed", e);
        setTimeout(loadInitial, 5000);
    }
}

async function fetchMore() {
    if (isFetching) return;
    isFetching = true;

    // Strategy: We want to intersperse new photos.
    // If we just cycle `queue`, we show old stuff.
    // We need to poll for *new* stuff periodically and inject it.
    // The API uses `cursor` (created_at) to get older stuff.
    // We want NEWER stuff. The API `feed` endpoints usually return newest first.
    // If we ask for feed without cursor, we get newest.
    // So we can check if the newest item ID is already in our queue.

    try {
        const res = await fetch('/slideshow/feed?limit=20');
        const data = await res.json();
        const newItems = data.items;

        // Filter out items we already have in queue
        const existingIds = new Set(queue.map(i => i.id));
        const brandNew = newItems.filter(i => !existingIds.has(i.id));

        if (brandNew.length > 0) {
            console.log(`Found ${brandNew.length} new items`);
            // Add them to the queue *next* so they appear soon
            // Or just shuffle them in?
            // Let's Insert them after current index
            queue.splice(currentIndex + 1, 0, ...brandNew);
        }
    } catch (e) {
        console.error("Fetch failed", e);
    } finally {
        isFetching = false;
    }
}

// --- Playback Logic ---

function nextSlide() {
    if (queue.length === 0) {
        setTimeout(loadInitial, 2000);
        return;
    }

    // Increment index
    currentIndex = (currentIndex + 1) % queue.length;

    // Periodically poll for new content when we loop or every N slides
    if (currentIndex === 0 || currentIndex % 5 === 0) {
        fetchMore();
    }

    const item = queue[currentIndex];

    // Create Element
    const el = document.createElement(item.type === 'video' ? 'video' : 'img');
    // Prefer thumbnail for images if available to save bandwidth
    el.src = (item.type !== 'video' && item.thumbnail) ? item.thumbnail : item.url;
    el.className = 'slide';

    if (item.type === 'video') {
        el.muted = true; // Auto-play requires mute usually
        el.autoplay = true;
        el.playsInline = true;

        // Error handling for video
        el.onerror = () => {
             console.error("Video failed to load", item.url);
             nextSlide();
        };
    } else {
        el.onload = () => {
            // Ready
        };
        el.onerror = () => {
            console.error("Image failed to load", item.url);
            // Remove bad item from queue?
            queue.splice(currentIndex, 1);
            currentIndex--; // step back
            nextSlide();
        }
    }

    // Clear container (keep old one for crossfade? CSS handles opacity)
    // For simple crossfade: append new, fade in, remove old after delay.
    // Current CSS: .slide.active { opacity: 1 }
    // We need to keep the OLD slide for a second.

    const oldSlide = container.querySelector('.slide.active');
    container.appendChild(el); // Add new one (opacity 0)

    // Caption
    // Remove old caption
    const oldCap = container.querySelector('.caption-overlay');
    if (oldCap) oldCap.remove();

    if (item.caption || item.author) {
        const cap = document.createElement('div');
        cap.className = 'caption-overlay';
        let author = item.author || 'Guest';
        // Format "Last-First" to "First Last" or "Last, First"?
        // User asked: "replace the '-' with ', ' so that it is Last Name, First name format."
        if (author.includes('-')) {
            author = author.split('-').join(', ');
        }
        cap.innerHTML = `<strong>${author}</strong><br>${item.caption || ''}`;
        container.appendChild(cap);
    }

    // Trigger Fade In
    // Force reflow
    void el.offsetWidth;
    el.classList.add('active');

    // Remove old slide after transition
    if (oldSlide) {
        oldSlide.classList.remove('active');
        setTimeout(() => oldSlide.remove(), 1000); // 1s matches CSS transition
    }

    // Schedule next
    let duration = 5000;
    if (item.type === 'video') {
         // Default max 15s if metadata fails
         duration = 15000;
         el.onloadedmetadata = () => {
             if (el.duration && el.duration < 60) duration = el.duration * 1000;
             // If duration is super long, maybe cut it?
             // But we set max upload duration to 60s.
         };
         el.onended = () => {
             // Move to next immediately
             nextSlide();
         };
         // Fallback if ended doesn't fire (stalled)
         // We rely on the implicit timer just in case, or clear it if ended fires?
         // Simpler: Just rely on onended for video, with a safety timeout.
    }

    if (item.type !== 'video') {
        setTimeout(nextSlide, duration);
    } else {
        // Video safety timeout
         setTimeout(() => {
             if (el.paused || !el.ended) {
                 // Check if it's still playing?
                 // Just force next slide if it's been too long
                 console.log("Video timeout forced next");
                 nextSlide();
             }
         }, 60000); // 60s safety
    }
}
