// utils.js - Shared utilities

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

// Custom Confirm Dialog (Simple implementation using standard confirm for now,
// or we can build a modal. User asked to "Replace all system popups with real container popups".
// Let's build a simple modal logic here.)

function showConfirm(message, onConfirm) {
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
                <button id="${modalId}-yes" class="btn" style="margin-right: 10px;">Yes</button>
                <button id="${modalId}-no" class="btn btn-secondary">No</button>
            </div>
        `;
        document.body.appendChild(modal);
    }

    document.getElementById(`${modalId}-msg`).innerText = message;
    modal.style.display = 'flex';

    const cleanup = () => {
        modal.style.display = 'none';
        yesBtn.removeEventListener('click', yesHandler);
        noBtn.removeEventListener('click', noHandler);
    };

    const yesBtn = document.getElementById(`${modalId}-yes`);
    const noBtn = document.getElementById(`${modalId}-no`);

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
