// Role selector
    document.querySelectorAll('input[name="role"]').forEach(radio => {
      radio.addEventListener('change', function() {
        document.querySelectorAll('.role-card').forEach(c => c.classList.remove('selected'));
        this.closest('.role-card').classList.add('selected');
      });
    });
    document.querySelectorAll('.role-card').forEach(card => {
      card.addEventListener('click', function() {
        const radio = this.querySelector('input[type="radio"]');
        radio.checked = true;
        radio.dispatchEvent(new Event('change'));
      });
    });

    // Toggle password visibility
    function togglePass(inputId, iconId) {
      const input = document.getElementById(inputId);
      const icon  = document.getElementById(iconId);
      input.type = input.type === 'password' ? 'text' : 'password';
      icon.className = input.type === 'password' ? 'ri-eye-off-line text-base' : 'ri-eye-line text-base';
    }

    // Password strength checker
    function checkStrength(val) {
      const bars   = ['bar1','bar2','bar3','bar4'];
      const colors = ['bg-red-400','bg-amber-400','bg-amber-400','bg-emerald-500'];
      const labels = ['Too short','Weak — add numbers','Fair — add symbols','Strong password'];

      let score = 0;
      if (val.length >= 8)  score++;
      if (/[0-9]/.test(val)) score++;
      if (/[^a-zA-Z0-9]/.test(val)) score++;
      if (val.length >= 12) score++;

      bars.forEach((b, i) => {
        const el = document.getElementById(b);
        if (i < score) {
          el.style.width = '100%';
          el.className = `strength-bar h-full rounded-full ${colors[score - 1]}`;
        } else {
          el.style.width = '0%';
        }
      });

      const label = document.getElementById('strength-label');
      label.textContent = val.length === 0 ? 'Use 8+ characters with numbers and symbols' : labels[Math.max(score - 1, 0)];
      label.className = 'text-xs mt-0.5 ' + (score >= 4 ? 'text-emerald-500' : score >= 2 ? 'text-amber-500' : 'text-red-400');
    }

    // Form validation
    document.getElementById('register-form').addEventListener('submit', function(e) {
      let valid = true;
      const hide = id => document.getElementById(id).classList.add('hidden');
      const show = id => document.getElementById(id).classList.remove('hidden');
      const mark = id => document.getElementById(id).classList.add('border-red-300');

      ['fname-error','lname-error','email-error','pass-error','pass2-error','terms-error'].forEach(hide);

      const fname = document.getElementById('first_name').value.trim();
      const lname = document.getElementById('last_name').value.trim();
      const email = document.getElementById('email').value.trim();
      const pass1 = document.getElementById('password1').value;
      const pass2 = document.getElementById('password2').value;
      const terms = document.getElementById('terms').checked;

      if (!fname) { show('fname-error'); mark('first_name'); valid = false; }
      if (!lname) { show('lname-error'); mark('last_name'); valid = false; }
      if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { show('email-error'); mark('email'); valid = false; }
      if (pass1.length < 8) { show('pass-error'); mark('password1'); valid = false; }
      if (pass1 !== pass2) { show('pass2-error'); mark('password2'); valid = false; }
      if (!terms) { show('terms-error'); valid = false; }

      if (!valid) {
        e.preventDefault();
        this.classList.add('shake');
        setTimeout(() => this.classList.remove('shake'), 400);
        return;
      }

      // Loading state
      document.getElementById('btn-text').textContent = 'Creating account...';
      document.getElementById('btn-icon').classList.add('hidden');
      document.getElementById('btn-spinner').classList.remove('hidden');
      document.getElementById('submit-btn').disabled = true;
    });
