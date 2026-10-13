// ── Sidebar Toggle ──
    const sidebar = document.getElementById('sidebar');
    const toggleIcon = document.getElementById('toggle-icon');
    let sidebarCollapsed = false;

    function toggleSidebar() {
      sidebarCollapsed = !sidebarCollapsed;
      sidebar.classList.toggle('collapsed', sidebarCollapsed);
      toggleIcon.className = sidebarCollapsed
        ? 'ri-menu-unfold-line text-xl'
        : 'ri-menu-fold-line text-xl';
      localStorage.setItem('sidebarCollapsed', sidebarCollapsed);
    }

    // Restore sidebar state on page load
    window.addEventListener('DOMContentLoaded', () => {
      const saved = localStorage.getItem('sidebarCollapsed');
      if (saved === 'true') {
        sidebarCollapsed = true;
        sidebar.classList.add('collapsed');
        toggleIcon.className = 'ri-menu-unfold-line text-xl';
      }
    });

    // ── Notification Panel ──
    const notifPanel = document.getElementById('notif-panel');
    let notifOpen = false;

    function toggleNotif() {
      if (!notifPanel) return;
      notifOpen = !notifOpen;
      notifPanel.classList.toggle('hidden', !notifOpen);
      if (notifOpen) closeUserMenu();
    }

    // ── User Dropdown ──
    const userDropdown = document.getElementById('user-dropdown');
    let userMenuOpen = false;

    function toggleUserMenu() {
      userMenuOpen = !userMenuOpen;
      userDropdown.classList.toggle('hidden', !userMenuOpen);
      if (userMenuOpen) closeNotif();
    }

    function closeUserMenu() {
      userMenuOpen = false;
      userDropdown.classList.add('hidden');
    }

    function closeNotif() {
      if (!notifPanel) return;
      notifOpen = false;
      notifPanel.classList.add('hidden');
    }

    // ── Close dropdowns on outside click ──
    document.addEventListener('click', (e) => {
      if (notifPanel && !e.target.closest('#notif-btn') && !e.target.closest('#notif-panel')) closeNotif();
      if (!e.target.closest('#user-btn') && !e.target.closest('#user-dropdown')) closeUserMenu();
    });

    // ── Search keyboard shortcut (/) ──
    document.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
        e.preventDefault();
        document.getElementById('topbar-search').focus();
      }
    });

    // ── Topbar course search (students) ──
    const topbarSearch = document.getElementById('topbar-search');
    if (topbarSearch) {
      topbarSearch.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter') return;
        const searchUrl = (topbarSearch.dataset.searchUrl || '').trim();
        if (!searchUrl) return;
        const term = topbarSearch.value.trim();
        window.location.href = term
          ? `${searchUrl}?q=${encodeURIComponent(term)}`
          : searchUrl;
      });
    }

    // ── Auto-dismiss flash messages ──
    window.addEventListener('DOMContentLoaded', () => {
      document.querySelectorAll('.global-flash-message').forEach((el, idx) => {
        setTimeout(() => {
          el.classList.add('opacity-0', '-translate-y-1');
          setTimeout(() => el.remove(), 500);
        }, 3000 + (idx * 200));
      });
    });
