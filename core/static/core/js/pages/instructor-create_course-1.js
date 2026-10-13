let currentStep = 1;

  function goStep(step) {
    // Hide all panels
    [1,2,3].forEach(s => {
      document.getElementById('panel-' + s).classList.add('hidden');
      const dot = document.getElementById('step-' + s);
      dot.classList.remove('active');
      if (s < step) {
        dot.classList.add('done');
        dot.classList.remove('step-dot');
      } else {
        dot.classList.remove('done');
      }
    });

    // Update lines
    [1,2].forEach(l => {
      const line = document.getElementById('line-' + l);
      if (l < step) line.classList.add('done');
      else line.classList.remove('done');
    });

    document.getElementById('panel-' + step).classList.remove('hidden');
    document.getElementById('step-' + step).classList.add('active');
    currentStep = step;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Live preview
  function updatePreview() {
    const title = document.getElementById('course-title').value || 'Your Course Title';
    const desc  = document.getElementById('short-desc').value  || 'Short description appears here...';
    document.getElementById('preview-title').textContent = title;
    document.getElementById('preview-desc').textContent  = desc;
  }

  // Select banner color
  function selectColor(color) {
    document.getElementById('banner-color').value = color;
    const colorMap = {
      indigo:  'from-indigo-500 to-indigo-700',
      violet:  'from-violet-500 to-violet-700',
      emerald: 'from-emerald-500 to-emerald-700',
      sky:     'from-sky-500 to-sky-700',
      rose:    'from-rose-500 to-rose-700',
      amber:   'from-amber-500 to-amber-700',
    };
    const banner = document.getElementById('preview-banner');
    banner.className = `h-32 bg-gradient-to-br ${colorMap[color]} relative overflow-hidden p-4 flex flex-col justify-end`;

    // Highlight selected
    document.querySelectorAll('#color-options button').forEach(b => {
      b.style.border = b.dataset.color === color ? '3px solid white' : '';
    });
  }

  // Thumbnail preview
  function previewThumb(input) {
    if (input.files && input.files[0]) {
      const reader = new FileReader();
      reader.onload = e => {
        document.getElementById('thumb-placeholder').classList.add('hidden');
        const img = document.getElementById('thumb-preview');
        img.src = e.target.result;
        img.classList.remove('hidden');
      };
      reader.readAsDataURL(input.files[0]);
    }
  }

  // Tags
  function addTag(e) {
    if (e && e.key && e.key !== 'Enter') return;
    if (e && typeof e.preventDefault === 'function') {
      e.preventDefault();
    }

    const input = document.getElementById('tag-input');
    const val = input.value.trim();
    if (!val) return;

    const existingTags = Array.from(document.querySelectorAll('#tags-container .tag-pill-label'))
      .map(el => el.textContent.toLowerCase());
    if (existingTags.includes(val.toLowerCase())) {
      input.value = '';
      return;
    }

    const span = document.createElement('span');
    span.className = 'tag-pill flex items-center gap-1.5 bg-primary-50 text-primary-700 text-xs font-medium px-3 py-1.5 rounded-full cursor-pointer';

    const label = document.createElement('span');
    label.className = 'tag-pill-label';
    label.textContent = val;

    const icon = document.createElement('i');
    icon.className = 'ri-close-line text-xs';

    span.appendChild(label);
    span.appendChild(icon);
    span.onclick = () => {
      span.remove();
      syncTagsInput();
    };

    document.getElementById('tags-container').appendChild(span);
    input.value = '';
    syncTagsInput();
  }

  function syncTagsInput() {
    const tags = Array.from(document.querySelectorAll('#tags-container .tag-pill-label'))
      .map(el => el.textContent.trim())
      .filter(Boolean);
    document.getElementById('tags-hidden').value = tags.join(', ');
  }

  // Learning outcomes
  function addOutcome() {
    const div = document.createElement('div');
    div.className = 'flex items-center gap-2';
    div.innerHTML = `
      <i class="ri-drag-move-2-line text-slate-300 cursor-grab flex-shrink-0"></i>
      <input type="text" name="outcomes[]" placeholder="e.g. Understand recursion..."
        class="input-field flex-1 px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-700 transition-all"/>
      <button type="button" onclick="this.parentElement.remove()" class="text-slate-300 hover:text-red-400 transition flex-shrink-0">
        <i class="ri-close-line"></i>
      </button>`;
    document.getElementById('outcomes-list').appendChild(div);
    div.querySelector('input').focus();
  }

  function updatePublishLabel() {
    const on = document.getElementById('publish-toggle').classList.contains('on');
    document.getElementById('publish-label').textContent = on ? 'Publish Course' : 'Create Course';
  }

  function toggleCapacityInput() {
    const limited = document.querySelector('input[name="capacity_mode"][value="limited"]').checked;
    const input = document.getElementById('capacity-input');
    input.disabled = !limited;
    input.required = limited;
    if (!limited) {
      input.value = '';
    }
  }

  // Scroll reveal
  const observer = new IntersectionObserver(entries => {
    entries.forEach((e,i) => {
      if (e.isIntersecting) setTimeout(() => e.target.classList.add('visible'), i * 60);
    });
  }, { threshold: 0.05 });
  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
  toggleCapacityInput();
