let activeView = 'grid';
  let activeCat  = '';
  let activeTag  = '';

  function setView(v) {
    activeView = v;
    document.getElementById('grid-view').classList.toggle('hidden', v !== 'grid');
    document.getElementById('list-view').classList.toggle('hidden', v !== 'list');
    document.getElementById('view-grid').classList.toggle('active', v === 'grid');
    document.getElementById('view-list').classList.toggle('active', v === 'list');
  }

  function setCat(cat) {
    activeCat = cat;
    document.querySelectorAll('.filter-btn[data-cat]').forEach(b => {
      b.classList.toggle('active', b.dataset.cat === cat);
    });
    document.getElementById('category-filter').value = cat;
    filterCourses();
  }

  function setTag(tag) {
    activeTag = tag;
    document.querySelectorAll('.tag-filter-btn[data-tag]').forEach(b => {
      b.classList.toggle('active', b.dataset.tag === tag);
    });
    const tagFilter = document.getElementById('tag-filter');
    if (tagFilter) {
      tagFilter.value = tag;
    }
    filterCourses();
  }

  function filterCourses() {
    const search = document.getElementById('search-input').value.toLowerCase();
    const level  = document.getElementById('level-filter').value;
    const cat    = activeCat || document.getElementById('category-filter').value;
    const tag    = activeTag || document.getElementById('tag-filter').value;
    const cards  = document.querySelectorAll('#grid-view .course-card');
    const rows   = document.querySelectorAll('#list-view .list-row');
    let count = 0;

    cards.forEach(card => {
      const name  = card.dataset.name.toLowerCase();
      const inst  = card.dataset.instructor.toLowerCase();
      const tags  = (card.dataset.tags || '').toLowerCase();
      const ccat  = card.dataset.category;
      const clvl  = card.dataset.level;
      const match = (!search || name.includes(search) || inst.includes(search) || tags.includes(search))
                 && (!cat    || ccat === cat)
                 && (!tag    || tags.split(',').map(t => t.trim()).includes(tag))
                 && (!level  || clvl === level);
      card.style.display = match ? '' : 'none';
      if (match) count++;
    });

    rows.forEach(row => {
      const name  = row.dataset.name.toLowerCase();
      const inst  = row.dataset.instructor.toLowerCase();
      const tags  = (row.dataset.tags || '').toLowerCase();
      const ccat  = row.dataset.category;
      const clvl  = row.dataset.level;
      const match = (!search || name.includes(search) || inst.includes(search) || tags.includes(search))
                 && (!cat    || ccat === cat)
                 && (!tag    || tags.split(',').map(t => t.trim()).includes(tag))
                 && (!level  || clvl === level);
      row.style.display = match ? '' : 'none';
    });

    document.getElementById('result-count').textContent = count;
    document.getElementById('empty-state').style.display = count === 0 ? 'block' : 'none';
  }

  function resetFilters() {
    activeCat = '';
    activeTag = '';
    document.getElementById('search-input').value = '';
    document.getElementById('category-filter').value = '';
    document.getElementById('level-filter').value = '';
    const tagFilter = document.getElementById('tag-filter');
    if (tagFilter) {
      tagFilter.value = '';
    }
    document.querySelectorAll('.filter-btn[data-cat]').forEach(b => b.classList.remove('active'));
    document.querySelector('.filter-btn[data-cat=""]').classList.add('active');
    document.querySelectorAll('.tag-filter-btn[data-tag]').forEach(b => b.classList.remove('active'));
    const allTagButton = document.querySelector('.tag-filter-btn[data-tag=""]');
    if (allTagButton) {
      allTagButton.classList.add('active');
    }
    filterCourses();
  }

  function sortCourses(by) {
    const container = document.getElementById('grid-view');
    const cards = [...container.querySelectorAll('.course-card')];
    const listContainer = document.getElementById('list-view');
    const rows = [...listContainer.querySelectorAll('.list-row')];
    cards.sort((a, b) => {
      if (by === 'name')     return a.dataset.name.localeCompare(b.dataset.name);
      if (by === 'students') return parseInt(b.dataset.students) - parseInt(a.dataset.students);
      if (by === 'rating')   return parseFloat(b.dataset.rating) - parseFloat(a.dataset.rating);
      return 0;
    });
    rows.sort((a, b) => {
      if (by === 'name') return a.dataset.name.localeCompare(b.dataset.name);
      return 0;
    });
    cards.forEach(c => container.appendChild(c));
    rows.forEach(r => listContainer.appendChild(r));
  }

  // Scroll reveal
  const observer = new IntersectionObserver(entries => {
    entries.forEach((e, i) => {
      if (e.isIntersecting) setTimeout(() => e.target.classList.add('visible'), i * 60);
    });
  }, { threshold: 0.05 });
  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
