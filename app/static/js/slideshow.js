// slideshow.js - Handles the live slideshow logic

let queue = [];
let currentIndex = -1;
let container = document.getElementById('container');
let isFetching = false;
let currentOrder = 'newest'; // 'newest' or 'random'

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    const orderToggle = document.getElementById('order-toggle');
    orderToggle.addEventListener('click', toggleOrder);

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

function toggleOrder() {
    currentOrder = (currentOrder === 'newest') ? 'random' : 'newest';
    const orderToggle = document.getElementById('order-toggle');
    if (currentOrder === 'random') {
        orderToggle.innerHTML = '🎲 Random';
    } else {
        orderToggle.textContent = 'Newest';
    }
    // Reload data with new order
    loadInitial();
}

function resetSlideshow() {
    // Clear intervals associated with video playback
    const oldVideo = container.querySelector('video');
    if (oldVideo) {
        oldVideo.onended = null;
    }
    // Stop any pending nextSlide timeouts
    clearTimeout(window.nextSlideTimeout);

    container.innerHTML = '';
    queue = [];
    currentIndex = -1;
}

async function loadInitial() {
    resetSlideshow();
    try {
        const res = await fetch(`/slideshow/feed?limit=50&order=${currentOrder}`);
        const data = await res.json();
        queue = data.items;

        if (queue.length > 0) {
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

    try {
        const res = await fetch(`/slideshow/feed?limit=20&order=${currentOrder}`);
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

const TRANSITIONS = ['fade', 'slide', 'zoom'];
function getRandomTransition() {
    return TRANSITIONS[Math.floor(Math.random() * TRANSITIONS.length)];
}

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

    // Mark as viewed
    fetch(`/media/${item.id}/viewed`, { method: 'POST' });

    // Create Element
    const el = document.createElement(item.type === 'video' ? 'video' : 'img');
    el.src = (item.type !== 'video' && item.thumbnail) ? item.thumbnail : item.url;
    el.className = 'slide';

    if (item.type === 'video') {
        el.muted = true;
        el.autoplay = true;
        el.playsInline = true;
        el.onerror = () => { console.error("Video failed", item.url); nextSlide(); };
    } else {
        el.onerror = () => {
            console.error("Image failed", item.url);
            queue.splice(currentIndex, 1);
            currentIndex--;
            nextSlide();
        }
    }

    const oldSlide = container.querySelector('.slide.active');
    container.appendChild(el);

    // Caption
    const oldCap = container.querySelector('.caption-overlay');
    if (oldCap) oldCap.remove();
    if (item.caption || item.author) {
        const cap = document.createElement('div');
        cap.className = 'caption-overlay';
        let author = (item.author || 'Guest').split('-').join(', ');
        cap.innerHTML = `<strong>${author}</strong><br>${item.caption || ''}`;
        container.appendChild(cap);
    }

    // Apply Random Transition
    const transition = getRandomTransition();
    el.classList.add(`transition-${transition}`);

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.classList.add('active');
      });
    });

    if (oldSlide) {
        const transitionDuration = 1500; // ms
        oldSlide.classList.remove('active');
        setTimeout(() => oldSlide.remove(), transitionDuration);
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
        window.nextSlideTimeout = setTimeout(nextSlide, duration);
    } else {
        // Video safety timeout
         window.nextSlideTimeout = setTimeout(() => {
             if (el.paused || !el.ended) {
                 // Check if it's still playing?
                 // Just force next slide if it's been too long
                 console.log("Video timeout forced next");
                 nextSlide();
             }
         }, 60000); // 60s safety
    }
}
