// Greeting by time
  const hour = new Date().getHours();
  const greetEl = document.getElementById('greeting-time');
  if (greetEl) {
    if (hour < 12)      greetEl.textContent = 'Good morning,';
    else if (hour < 17) greetEl.textContent = 'Good afternoon,';
    else                greetEl.textContent = 'Good evening,';
  }

  // Filter users table by role
  function filterUsers(role) {
    document.querySelectorAll('#users-table tbody tr').forEach(row => {
      if (role === 'all' || row.dataset.role === role) {
        row.style.display = '';
      } else {
        row.style.display = 'none';
      }
    });
  }

  // Scroll reveal
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        setTimeout(() => entry.target.classList.add('visible'), i * 80);
      }
    });
  }, { threshold: 0.05 });
  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
