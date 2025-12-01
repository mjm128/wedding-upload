// utils.js - Shared utilities

const TRANSLATIONS = {
    "en": {
        "share_memories": "Share Your Memories",
        "welcome": "Welcome, {name}!",
        "select_files": "Select Photos & Videos",
        "your_uploads": "Your Uploads",
        "add_caption": "Add a caption...",
        "upload_btn": "Upload",
        "upload_success": "Upload Successful!",
        "file_too_large": "File too large!",
        "video_too_long": "Video too long!",
        "action_failed": "Action failed",
        "confirm_delete": "Are you sure you want to delete this?",
        "yes": "Yes",
        "no": "No",
        "live_feed": "LIVE FEED",
        "help_title": "How it Works",
        "help_text": "Select photos or videos from your gallery. Add a caption if you like. Once uploaded, your memories will appear on the live slideshow!",
        "close": "Close",
        "logout_confirm": "Are you sure you want to logout? You will lose access to your previous uploads history on this device.",
        "permanent_action": "I understand this action is permanent."
    },
    "es": {
        "share_memories": "Comparte tus Recuerdos",
        "welcome": "¡Bienvenido, {name}!",
        "live_feed": "VER EN VIVO",
        "select_files": "Seleccionar Fotos y Videos",
        "your_uploads": "Tus Subidas",
        "add_caption": "Añade un pie de foto...",
        "upload_btn": "Subir",
        "upload_success": "¡Subida Exitosa!",
        "file_too_large": "¡Archivo demasiado grande!",
        "video_too_long": "¡Video demasiado largo!",
        "action_failed": "Acción fallida",
        "confirm_delete": "¿Estás seguro de que quieres eliminar esto?",
        "yes": "Sí",
        "no": "No",
        "help_title": "Cómo Funciona",
        "help_text": "Selecciona fotos o videos de tu galería. Añade un título si quieres. ¡Una vez subidos, tus recuerdos aparecerán en la presentación en vivo!",
        "close": "Cerrar",
        "logout_confirm": "¿Estás seguro de que quieres cerrar sesión? Perderás el acceso al historial de tus subidas anteriores en este dispositivo.",
        "permanent_action": "Entiendo que esta acción es permanente."
    }
};

let currentLang = localStorage.getItem("lang") || "en";

function t(key) {
    return TRANSLATIONS[currentLang][key] || key;
}

function setLanguage(lang) {
    currentLang = lang;
    localStorage.setItem("lang", lang);

    // Update text
    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        el.innerText = t(key);
    });

    // Update placeholders
    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
        const key = el.getAttribute("data-i18n-placeholder");
        el.placeholder = t(key);
    });

    // Handle dynamic elements
    if (typeof updateWelcomeMessage === 'function') {
        updateWelcomeMessage();
    }
    if (typeof updateBanner === 'function') {
        updateBanner();
    }
}

function toggleLanguage() {
    setLanguage(currentLang === "en" ? "es" : "en");
    const btn = document.getElementById('lang-btn');
    if (btn) btn.innerText = currentLang.toUpperCase();
}

function showToast(message, duration = 3000) {
    let snackbar = document.getElementById("snackbar");
    if (!snackbar) {
        snackbar = document.createElement("div");
        snackbar.id = "snackbar";
        document.body.appendChild(snackbar);
    }
    snackbar.innerText = message;
    snackbar.className = "show";
    setTimeout(function() {
        snackbar.className = snackbar.className.replace("show", "");
    }, duration);
}

function showConfirm(message, onConfirm, requireCheck = false) {
    // Simple Modal
    const modalId = 'confirm-modal';
    let modal = document.getElementById(modalId);

    if (!modal) {
        modal = document.createElement('div');
        modal.id = modalId;
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.7); z-index: 3000; display: flex;
            align-items: center; justify-content: center;
        `;
        modal.innerHTML = `
            <div class="glass-card" style="max-width: 300px; text-align: center;">
                <p id="${modalId}-msg" style="margin-bottom: 20px;"></p>
                <div id="${modalId}-check-container" style="margin-bottom: 15px; display:none; text-align:left; font-size:0.9em;">
                    <label><input type="checkbox" id="${modalId}-check"> <span data-i18n="permanent_action">I understand this action is permanent.</span></label>
                </div>
                <button id="${modalId}-yes" class="btn" style="margin-right: 10px;"></button>
                <button id="${modalId}-no" class="btn btn-secondary"></button>
            </div>
        `;
        document.body.appendChild(modal);
    }

    document.getElementById(`${modalId}-msg`).innerText = message;
    document.getElementById(`${modalId}-yes`).innerText = t('yes');
    document.getElementById(`${modalId}-no`).innerText = t('no');
    modal.querySelector('[data-i18n="permanent_action"]').innerText = t('permanent_action');


    const checkContainer = document.getElementById(`${modalId}-check-container`);
    const checkBox = document.getElementById(`${modalId}-check`);
    const yesBtn = document.getElementById(`${modalId}-yes`);
    const noBtn = document.getElementById(`${modalId}-no`);

    if (requireCheck) {
        checkContainer.style.display = 'block';
        checkBox.checked = false;
        yesBtn.disabled = true;
        checkBox.onchange = () => { yesBtn.disabled = !checkBox.checked; };
        yesBtn.style.opacity = 0.5;
        checkBox.addEventListener('change', () => {
             yesBtn.style.opacity = checkBox.checked ? 1 : 0.5;
        });
    } else {
        checkContainer.style.display = 'none';
        yesBtn.disabled = false;
        yesBtn.style.opacity = 1;
    }

    modal.style.display = 'flex';

    const cleanup = () => {
        modal.style.display = 'none';
        yesBtn.removeEventListener('click', yesHandler);
        noBtn.removeEventListener('click', noHandler);
        checkBox.onchange = null;
    };

    const yesHandler = () => {
        cleanup();
        onConfirm();
    };

    const noHandler = () => {
        cleanup();
    };

    yesBtn.addEventListener('click', yesHandler);
    noBtn.addEventListener('click', noHandler);
}

function formatBytes(bytes, decimals = 2) {
    if (!+bytes) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KiB', 'MiB', 'GiB', 'TiB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

function showHelp() {
    const modalId = 'help-modal';
    let modal = document.getElementById(modalId);

    if (!modal) {
        modal = document.createElement('div');
        modal.id = modalId;
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.7); z-index: 3000; display: flex;
            align-items: center; justify-content: center;
        `;
        modal.innerHTML = `
            <div class="glass-card" style="max-width: 400px; text-align: center; padding: 30px;">
                <h2 id="${modalId}-title" style="margin-top:0;"></h2>
                <p id="${modalId}-text"></p>
                <button id="${modalId}-close" class="btn" style="margin-top: 20px;"></button>
            </div>
        `;
        document.body.appendChild(modal);

        modal.querySelector('button').onclick = () => {
            modal.style.display = 'none';
        };
    }

    document.getElementById(`${modalId}-title`).innerText = t('help_title');
    document.getElementById(`${modalId}-text`).innerText = t('help_text');
    document.getElementById(`${modalId}-close`).innerText = t('close');
    modal.style.display = 'flex';
}

function logout() {
    showConfirm(t('logout_confirm'), () => {
        document.cookie = "guest_name=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        document.cookie = "table_number=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        document.cookie = "guest_uuid=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        location.reload();
    }, true); // Require checkbox
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return decodeURIComponent(parts.pop().split(';').shift());
}

function updateWelcomeMessage() {
    const name = getCookie("guest_name");
    if (!name) {
        document.getElementById('setup-modal').style.display = 'flex';
        document.body.classList.add('content-hidden'); // Ensure content is hidden if modal is up
    } else {
        document.getElementById('setup-modal').style.display = 'none';
        document.body.classList.remove('content-hidden'); // Unhide content
        const display = name.split('-').reverse().join(', ');
        const welcome = document.getElementById('guest-welcome');
        welcome.innerText = t('welcome').replace('{name}', display);

        // Ensure UUID exists
        if (!getCookie("guest_uuid")) {
            document.cookie = `guest_uuid=${crypto.randomUUID()}; max-age=31536000; path=/; SameSite=Lax`;
        }
    }
}

function toLocalTime(utcDateStr) {
    const date = new Date(utcDateStr);
    return date.toLocaleString();
}

function updateBanner() {
    if (window.APP_CONFIG) {
        const bannerMsg = window.APP_CONFIG[`banner_message_${currentLang}`] || window.APP_CONFIG[`banner_message_en`];
        if (bannerMsg) {
            const b = document.getElementById('banner');
            b.innerText = bannerMsg;
            b.style.display = 'block';
            document.body.classList.add('has-banner');
        } else {
            document.getElementById('banner').style.display = 'none';
            document.body.classList.remove('has-banner');
        }
    }
}
