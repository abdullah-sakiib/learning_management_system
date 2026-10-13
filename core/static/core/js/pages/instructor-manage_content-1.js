document.addEventListener('DOMContentLoaded', function () {
    const sections = document.querySelectorAll('.mc-accordion');
    sections.forEach((section) => {
      section.addEventListener('toggle', function () {
        if (!section.open) {
          return;
        }
        sections.forEach((other) => {
          if (other !== section) {
            other.open = false;
          }
        });
      });
    });

    toggleManageCapacity();
  });

  function toggleManageCapacity() {
    const modeEl = document.getElementById('capacity-mode');
    const maxEl = document.getElementById('max-students-input');
    if (!modeEl || !maxEl) {
      return;
    }
    const limited = modeEl.value === 'limited';
    maxEl.disabled = !limited;
    maxEl.required = limited;
    if (!limited) {
      maxEl.value = '';
    }
  }
