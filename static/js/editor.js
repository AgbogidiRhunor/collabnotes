(function () {
  'use strict';

  /* ── DOM refs ─────────────────────────────────────────────────────────── */
  const editorEl     = document.getElementById('note-editor');
  const titleEl      = document.getElementById('note-title');
  const contentField = document.getElementById('note-content-field');
  const noteForm     = document.getElementById('note-form');
  const saveStatus   = document.getElementById('save-status');
  const saveBtn      = document.getElementById('save-btn');

  if (!editorEl || !noteForm) return;

  /* ── Config from meta tags ────────────────────────────────────────────── */
  const CAN_EDIT     = editorEl.getAttribute('contenteditable') === 'true';
  const CAN_RENAME   = (document.querySelector('meta[name="can-rename"]') || {}).content === 'true';
  const CURRENT_USER = (document.querySelector('meta[name="current-user"]') || {}).content || '';
  const NOTE_ID      = (document.querySelector('meta[name="note-id"]') || {}).content || '';

  let isDirty  = false;
  let isSaving = false;

  /* ── Utility ──────────────────────────────────────────────────────────── */
  function debounce(fn, ms) {
    let t;
    return function () { clearTimeout(t); t = setTimeout(fn, ms); };
  }

  function setStatus(text, cls) {
    if (!saveStatus) return;
    saveStatus.textContent = text;
    saveStatus.className = 'save-status' + (cls ? ' ' + cls : '');
  }

  function markDirty() {
    if (isSaving) return;
    isDirty = true;
    setStatus('Unsaved changes', 'saving');
    if (saveBtn) saveBtn.classList.add('btn-primary--pulse');
  }

  function getCsrf() {
    for (const part of document.cookie.split(';')) {
      const eq = part.indexOf('=');
      if (eq < 0) continue;
      if (part.slice(0, eq).trim() === 'csrftoken') {
        return '<input type="hidden" name="csrfmiddlewaretoken" value="' +
               decodeURIComponent(part.slice(eq + 1).trim()) + '">';
      }
    }
    return '';
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  /* ── Save ─────────────────────────────────────────────────────────────── */
  function save() {
    if (!CAN_EDIT || isSaving) return;
    fadeOldAuthorSpans();
    wrapNewTextWithAuthor();
    if (contentField) contentField.value = editorEl.innerHTML;
    isSaving = true;
    isDirty  = false;
    setStatus('Saving…', 'saving');
    if (saveBtn) {
      saveBtn.classList.remove('btn-primary--pulse');
      saveBtn.disabled = true;
    }
    noteForm.submit();
  }

  /* ── Author highlighting ──────────────────────────────────────────────── */
  const AUTHOR_PALETTE = ['#c8a97a', '#6fcf97', '#56b4e9', '#bb8fce'];
  const FADE_AFTER_MS  = 5 * 60 * 1000;

  function colorForName(name) {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
    return AUTHOR_PALETTE[Math.abs(h) % AUTHOR_PALETTE.length];
  }

  function wrapNewTextWithAuthor() {
    if (!CURRENT_USER) return;
    const color  = colorForName(CURRENT_USER);
    const now    = Date.now();
    const walker = document.createTreeWalker(editorEl, NodeFilter.SHOW_TEXT);
    const toWrap = [];
    let node;
    while ((node = walker.nextNode())) {
      if (node.parentElement.closest('[data-author]')) continue;
      if (!node.textContent.trim()) continue;
      toWrap.push(node);
    }
    toWrap.forEach(function (tn) {
      const span = document.createElement('span');
      span.dataset.author   = CURRENT_USER;
      span.dataset.editTime = now;
      span.style.setProperty('--author-color', color);
      span.className = 'author-span author-span--fresh';
      tn.parentNode.insertBefore(span, tn);
      span.appendChild(tn);
    });
  }

  function fadeOldAuthorSpans() {
    const now = Date.now();
    editorEl.querySelectorAll('.author-span[data-edit-time]').forEach(function (span) {
      if (now - parseInt(span.dataset.editTime || '0', 10) > FADE_AFTER_MS) {
        span.classList.remove('author-span--fresh');
        span.classList.add('author-span--faded');
      }
    });
  }

  setInterval(fadeOldAuthorSpans, 30000);
  fadeOldAuthorSpans();

  const debouncedWrap = debounce(wrapNewTextWithAuthor, 1500);

  /* ── Editor events ────────────────────────────────────────────────────── */
  if (CAN_EDIT) {
    editorEl.addEventListener('input', function () { markDirty(); debouncedWrap(); });
    if (titleEl && CAN_RENAME) titleEl.addEventListener('input', markDirty);

    if (saveBtn) {
      saveBtn.addEventListener('click', function (e) { e.preventDefault(); save(); });
    }

    document.addEventListener('keydown', function (e) {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key === 's') { e.preventDefault(); save(); return; }
      if (mod && e.key === 'b') { e.preventDefault(); document.execCommand('bold'); }
      if (mod && e.key === 'i') { e.preventDefault(); document.execCommand('italic'); }
      if (mod && e.key === 'u') { e.preventDefault(); document.execCommand('underline'); }
    });

    window.addEventListener('beforeunload', function (e) {
      if (isDirty && !isSaving) { e.preventDefault(); e.returnValue = ''; }
    });
  }

  /* ── Format toolbar ───────────────────────────────────────────────────── */
  document.querySelectorAll('.fmt-btn[data-cmd]').forEach(function (btn) {
    btn.addEventListener('mousedown', function (e) {
      e.preventDefault();
      document.execCommand(btn.dataset.cmd, false, btn.dataset.val || null);
      editorEl.focus();
      syncToolbar();
      markDirty();
    });
  });

  function syncToolbar() {
    ['bold','italic','underline','strikeThrough','insertUnorderedList','insertOrderedList']
      .forEach(function (cmd) {
        const btn = document.querySelector('.fmt-btn[data-cmd="' + cmd + '"]');
        if (btn) btn.classList.toggle('active', document.queryCommandState(cmd));
      });
  }
  editorEl.addEventListener('keyup', syncToolbar);
  editorEl.addEventListener('mouseup', syncToolbar);

  /* ── History panel ────────────────────────────────────────────────────── */
  // Declare ALL history vars before collaborators panel so there are no
  // forward-reference issues.

  const historyBtn     = document.getElementById('history-btn');
  const historyPanel   = document.getElementById('history-panel');
  const historyOverlay = document.getElementById('history-overlay');
  const historyClose   = document.getElementById('history-close');
  const historyList    = document.getElementById('history-list');

  function openHistory() {
    if (!historyPanel) return;
    historyPanel.classList.add('is-open');
    if (historyOverlay) historyOverlay.style.display = 'block';
    loadVersions();
  }

  function closeHistory() {
    if (historyPanel) historyPanel.classList.remove('is-open');
    if (historyOverlay) historyOverlay.style.display = 'none';
  }

  function loadVersions() {
    const url = window.NOTE_VERSIONS_URL;
    if (!url || !historyList) return;
    historyList.innerHTML = '<p class="history-loading">Loading…</p>';

    fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (!data.versions || data.versions.length === 0) {
          historyList.innerHTML = '<p class="history-empty">No saved versions yet.</p>';
          return;
        }
        const canEdit = (document.querySelector('meta[name="can-edit"]') || {}).content === 'true';
        historyList.innerHTML = data.versions.map(function (v, i) {
          const label      = v.label ? escHtml(v.label) : (i === 0 ? 'Current version' : '');
          const by         = escHtml(v['saved_by__display_name'] || 'Unknown');
          const restoreUrl = '/notes/' + NOTE_ID + '/history/' + v.id + '/restore/';
          return [
            '<div class="history-version-item">',
              '<div class="history-version-meta">',
                '<span class="history-version-time">' + escHtml(v.time_ago) + '</span>',
                i === 0 ? '<span class="history-current-tag">Current</span>' : '',
              '</div>',
              label ? '<p class="history-version-label">' + label + '</p>' : '',
              '<p class="history-version-by">Saved by ' + by + '</p>',
              i > 0 && canEdit
                ? '<form method="post" action="' + restoreUrl + '">' +
                    getCsrf() +
                    '<button type="submit" class="btn-ghost btn-sm history-restore-btn">Restore</button>' +
                  '</form>'
                : '',
            '</div>'
          ].join('');
        }).join('');
      })
      .catch(function (err) {
        historyList.innerHTML = '<p class="history-empty">Could not load versions.<br><small>' + escHtml(String(err)) + '</small></p>';
      });
  }

  if (historyBtn)     historyBtn.addEventListener('click', openHistory);
  if (historyClose)   historyClose.addEventListener('click', closeHistory);
  if (historyOverlay) historyOverlay.addEventListener('click', closeHistory);

  /* ── Collaborators panel ──────────────────────────────────────────────── */
  // Declared AFTER history so closeHistory() is available.

  const collabsBtn   = document.getElementById('collabs-btn');
  const collabsPanel = document.getElementById('collabs-panel');

  function closeCollabs() {
    if (!collabsPanel) return;
    collabsPanel.classList.remove('is-open');
    if (collabsBtn) collabsBtn.setAttribute('aria-expanded', 'false');
  }

  if (collabsBtn && collabsPanel) {
    collabsBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (collabsPanel.classList.contains('is-open')) {
        closeCollabs();
      } else {
        collabsPanel.classList.add('is-open');
        collabsBtn.setAttribute('aria-expanded', 'true');
        closeHistory();
      }
    });

    document.addEventListener('click', function (e) {
      if (collabsPanel.classList.contains('is-open') &&
          !collabsPanel.contains(e.target) &&
          !collabsBtn.contains(e.target)) {
        closeCollabs();
      }
    });

    collabsPanel.addEventListener('click', function (e) { e.stopPropagation(); });
  }

}());