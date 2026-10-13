// Toggle password visibility
    function togglePassword() {
      const input = document.getElementById('password');
      const icon  = document.getElementById('eye-icon');
      if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'ri-eye-line text-base';
      } else {
        input.type = 'password';
        icon.className = 'ri-eye-off-line text-base';
      }
    }

    // Client-side validation + loading state
    document.getElementById('login-form').addEventListener('submit', function(e) {
      let valid = true;

      const email = document.getElementById('email');
      const password = document.getElementById('password');
      const emailErr = document.getElementById('email-error');
      const passErr  = document.getElementById('password-error');

      // Reset errors
      emailErr.classList.add('hidden');
      passErr.classList.add('hidden');
      email.classList.remove('border-red-300');
      password.classList.remove('border-red-300');

      // Validate email
      if (!email.value || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
        emailErr.classList.remove('hidden');
        email.classList.add('border-red-300');
        valid = false;
      }

      // Validate password
      if (!password.value) {
        passErr.classList.remove('hidden');
        password.classList.add('border-red-300');
        valid = false;
      }

      if (!valid) {
        e.preventDefault();
        document.getElementById('login-form').classList.add('shake');
        setTimeout(() => document.getElementById('login-form').classList.remove('shake'), 400);
        return;
      }

      // Loading state
      document.getElementById('btn-text').textContent = 'Signing in...';
      document.getElementById('btn-icon').classList.add('hidden');
      document.getElementById('btn-spinner').classList.remove('hidden');
      document.getElementById('submit-btn').disabled = true;
    });
