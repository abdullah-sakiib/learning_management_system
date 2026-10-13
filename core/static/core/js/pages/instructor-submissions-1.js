function openGrading(row) {
    // Highlight selected row
    document.querySelectorAll('.sub-row').forEach(r => r.classList.remove('selected'));
    row.classList.add('selected');

    const name = row.dataset.student;
    const assignment = row.dataset.assignment;
    const course = row.dataset.course;
    const status = row.dataset.status;
    const maxScore = parseFloat(row.dataset.maxScore || '100');
    const score = row.dataset.score;
    const submissionId = row.dataset.submissionId;
    const fileName = row.dataset.file || 'submission_file';

    // Show grade form, hide empty state
    document.getElementById('grade-empty').classList.add('hidden');
    document.getElementById('grade-form').classList.remove('hidden');

    // Populate
    const initials = name.split(' ').map(n=>n[0]).join('+');
    const colors   = ['4f46e5','818cf8','10b981','f59e0b','a78bfa','64748b'];
    const color    = colors[Math.floor(Math.random() * colors.length)];
    document.getElementById('gf-avatar').src  = `https://ui-avatars.com/api/?name=${initials}&background=${color}&color=fff&size=64`;
    document.getElementById('gf-name').textContent       = name;
    document.getElementById('gf-assignment').textContent = assignment + ' · ' + course;
    document.getElementById('gf-file').textContent       = fileName;
    document.getElementById('gf-submission-id').value    = submissionId;
    document.getElementById('gf-score').max              = maxScore;
    document.getElementById('gf-max-score').textContent  = maxScore;

    if (score) {
      document.getElementById('gf-score').value = score;
      updateScoreBar((parseFloat(score) / maxScore) * 100);
    } else {
      document.getElementById('gf-score').value = '';
      updateScoreBar(0);
    }
    document.getElementById('gf-feedback').value = '';
  }

  function updateScoreBar(val) {
    const pct   = Math.min(Math.max(val, 0), 100);
    const bar   = document.getElementById('score-bar');
    const label = document.getElementById('score-label');
    bar.style.width = pct + '%';
    bar.className = `h-full rounded-full transition-all duration-300 ${
      pct >= 80 ? 'bg-emerald-500' : pct >= 60 ? 'bg-amber-400' : 'bg-red-400'
    }`;
    label.textContent = pct >= 80 ? 'Excellent' : pct >= 60 ? 'Satisfactory' : pct > 0 ? 'Needs improvement' : 'Enter a score';
    label.className = `text-xs mt-1 ${pct >= 80 ? 'text-emerald-500' : pct >= 60 ? 'text-amber-500' : pct > 0 ? 'text-red-400' : 'text-slate-400'}`;
  }

  function addFeedback(text) {
    const fb = document.getElementById('gf-feedback');
    fb.value = fb.value ? fb.value + ' ' + text : text;
    fb.focus();
  }

  // Filter pills
  function setStatusFilter(status) {
    ['all','pending','graded','late'].forEach(s => {
      document.getElementById('pill-' + s).classList.toggle('active', s === status);
    });
    filterByStatus(status);
  }

  function filterByStatus(status) {
    document.querySelectorAll('#sub-tbody tr').forEach(row => {
      const rowStatus = row.dataset.status;
      const normalized = rowStatus === 'submitted' ? 'pending' : rowStatus;
      row.style.display = (status === 'all' || normalized === status) ? '' : 'none';
    });
  }

  function filterSubs() {
    const course  = document.getElementById('course-filter').value.toLowerCase();
    const status  = document.getElementById('status-filter').value;
    document.querySelectorAll('#sub-tbody tr').forEach(row => {
      const text = row.textContent.toLowerCase();
      const rowStatus = row.dataset.status === 'submitted' ? 'pending' : row.dataset.status;
      const show = (!course || text.includes(course)) && (!status || rowStatus === status);
      row.style.display = show ? '' : 'none';
    });
  }

  function searchSubs(val) {
    const q = val.toLowerCase();
    document.querySelectorAll('#sub-tbody tr').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  }

  // Scroll reveal
  const observer = new IntersectionObserver(entries => {
    entries.forEach((e,i) => {
      if (e.isIntersecting) setTimeout(() => e.target.classList.add('visible'), i * 60);
    });
  }, { threshold: 0.05 });
  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
