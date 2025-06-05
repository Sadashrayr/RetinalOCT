document.addEventListener('DOMContentLoaded', () => {
    // Form validation for login
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            const username = loginForm.querySelector('input[name="username"]').value;
            const password = loginForm.querySelector('input[name="password"]').value;
            if (username.length < 3 || password.length < 6) {
                e.preventDefault();
                alert('Username must be at least 3 characters and password at least 6 characters.');
            }
        });
    }

    // Form validation for register
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', (e) => {
            const username = registerForm.querySelector('input[name="username"]').value;
            const password = registerForm.querySelector('input[name="password"]').value;
            if (username.length < 3 || password.length < 6) {
                e.preventDefault();
                alert('Username must be at least 3 characters and password at least 6 characters.');
            }
        });
    }

    // Real-time progress for upload
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        const socket = io('/upload');
        const progress = document.getElementById('progress');
        socket.on('progress', (data) => {
            progress.innerText = data.status;
            progress.style.opacity = '1';
            if (data.status === 'Prediction complete!') {
                setTimeout(() => {
                    progress.style.opacity = '0';
                }, 2000);
            }
        });
        uploadForm.addEventListener('submit', () => {
            const submitButton = uploadForm.querySelector('button');
            submitButton.disabled = true;
            submitButton.innerText = 'Uploading...';
        });
    }
});