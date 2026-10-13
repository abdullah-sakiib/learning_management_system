// ── Quiz list / taking / results view switching ──
  function startQuiz() {
    document.getElementById('quiz-list-view').classList.add('hidden');
    document.getElementById('quiz-taking-view').classList.remove('hidden');
    startTimer(15 * 60);
  }

  function backToList() {
    document.getElementById('quiz-results-view').classList.add('hidden');
    document.getElementById('quiz-list-view').classList.remove('hidden');
  }

  // ── Timer ──
  let timeLeft = 0;
  let timerInterval;
  const TOTAL_TIME = 15 * 60;
  const CIRCUMFERENCE = 2 * Math.PI * 22; // ~138.2

  function startTimer(seconds) {
    timeLeft = seconds;
    timerInterval = setInterval(() => {
      timeLeft--;
      const mins = Math.floor(timeLeft / 60);
      const secs = timeLeft % 60;
      document.getElementById('timer-display').textContent =
        `${String(mins).padStart(2,'0')}:${String(secs).padStart(2,'0')}`;

      // Ring progress
      const pct    = timeLeft / TOTAL_TIME;
      const offset = CIRCUMFERENCE * (1 - pct);
      const ring   = document.getElementById('timer-ring');
      ring.style.strokeDashoffset = offset;
      ring.className = 'timer-ring-fg' + (pct < 0.2 ? ' critical' : pct < 0.4 ? ' warning' : '');

      if (timeLeft <= 0) { clearInterval(timerInterval); submitQuiz(); }
    }, 1000);
  }

  // ── Questions ──
  let currentQ = 1;
  let answers  = {};
  const totalQ  = 10;

  function updateProgress() {
    const pct = (currentQ / totalQ) * 100;
    document.getElementById('quiz-progress-bar').style.width = pct + '%';
    document.getElementById('q-current').textContent = currentQ;
  }

  function goQuestion(n) {
    // Update dots
    document.querySelectorAll('.q-dot').forEach((d, i) => {
      d.classList.remove('current');
      if (answers[i+1] !== undefined) d.classList.add('answered');
    });
    document.getElementById('qdot-' + n).classList.add('current');
    currentQ = n;
    updateProgress();
    // Reset options UI
    document.querySelectorAll('.quiz-option').forEach(o => {
      o.classList.remove('selected');
      if (answers[currentQ] === parseInt(o.dataset.idx)) o.classList.add('selected');
    });
    // Last question: change button
    document.getElementById('next-btn').textContent = currentQ === totalQ ? 'Submit ' : 'Next ';
    document.getElementById('next-btn').innerHTML   = currentQ === totalQ
      ? '<i class="ri-flag-fill mr-1"></i>Submit'
      : 'Next <i class="ri-arrow-right-line ml-1"></i>';
  }

  function selectOption(el, idx) {
    document.querySelectorAll('.quiz-option').forEach(o => o.classList.remove('selected'));
    el.classList.add('selected');
    el.dataset.idx = idx;
    answers[currentQ] = idx;
    document.getElementById('qdot-' + currentQ).classList.add('answered');
  }

  function nextQuestion() {
    if (currentQ < totalQ) goQuestion(currentQ + 1);
    else submitQuiz();
  }

  function prevQuestion() {
    if (currentQ > 1) goQuestion(currentQ - 1);
  }

  function submitQuiz() {
    clearInterval(timerInterval);
    document.getElementById('quiz-taking-view').classList.add('hidden');
    document.getElementById('quiz-results-view').classList.remove('hidden');
    // Animate score ring
    setTimeout(() => {
      const score  = 9;
      const pct    = score / 10;
      const CIRC   = 2 * Math.PI * 52; // ~326.7
      const offset = CIRC * (1 - pct);
      document.getElementById('result-ring').style.strokeDashoffset = offset;
    }, 200);
  }

  // Scroll reveal
  const observer = new IntersectionObserver(entries => {
    entries.forEach((e,i) => {
      if (e.isIntersecting) setTimeout(() => e.target.classList.add('visible'), i * 60);
    });
  }, { threshold: 0.05 });
  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
