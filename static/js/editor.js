(function () {
  'use strict';

  const editorEl     = document.getElementById('note-editor');
  const titleEl      = document.getElementById('note-title');
  const contentField = document.getElementById('note-content-field');
  const noteForm     = document.getElementById('note-form');
  const saveStatus   = document.getElementById('save-status');
  const saveBtn      = document.getElementById('save-btn');

  if (!editorEl || !noteForm) return;

  const CAN_EDIT     = editorEl.getAttribute('contenteditable') === 'true';
  const CAN_RENAME   = (document.querySelector('meta[name="can-rename"]') || {}).content === 'true';
  const CAN_MANAGE   = (document.querySelector('meta[name="can-manage"]') || {}).content === 'true';
  const CURRENT_USER = (document.querySelector('meta[name="current-user"]') || {}).content || '';
  const NOTE_ID      = (document.querySelector('meta[name="note-id"]') || {}).content || '';

  let isDirty  = false;
  let isSaving = false;

  // ── Helpers ──────────────────────────────────────────────────────────────

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

  // ── Save ──────────────────────────────────────────────────────────────────

  function save() {
    if (!CAN_EDIT || isSaving) return;

    fadeOldAuthorSpans();
    wrapNewTextWithAuthor();

    if (contentField) contentField.value = editorEl.innerHTML;

    isSaving = true;
    isDirty  = false;
    setStatus('Saving…', 'saving');
    if (saveBtn) { saveBtn.classList.remove('btn-primary--pulse'); saveBtn.disabled = true; }

    noteForm.submit();
  }

  // ── Feature 6: Author highlighting with fading ────────────────────────────
  // Palette: 4 soft, accessible colors only
  const AUTHOR_PALETTE = ['#c8a97a', '#6fcf97', '#56b4e9', '#bb8fce'];
  // How long before an edit fades back to default (ms)
  const FADE_AFTER_MS = 5 * 60 * 1000; // 5 minutes

  function colorForName(name) {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
    return AUTHOR_PALETTE[Math.abs(h) % AUTHOR_PALETTE.length];
  }

  function wrapNewTextWithAuthor() {
    if (!CURRENT_USER) return;
    const color = colorForName(CURRENT_USER);
    const now   = Date.now();

    const walker  = document.createTreeWalker(editorEl, NodeFilter.SHOW_TEXT);
    const toWrap  = [];
    let node;
    while ((node = walker.nextNode())) {
      if (node.parentElement.closest('[data-author]')) continue;
      if (!node.textContent.trim()) continue;
      toWrap.push(node);
    }

    toWrap.forEach(function (textNode) {
      const span = document.createElement('span');
      span.dataset.author    = CURRENT_USER;
      span.dataset.editTime  = now;
      span.style.setProperty('--author-color', color);
      span.className = 'author-span author-span--fresh';
      textNode.parentNode.insertBefore(span, textNode);
      span.appendChild(textNode);
    });
  }

  // Fade spans older than FADE_AFTER_MS back to default text color
  function fadeOldAuthorSpans() {
    const now = Date.now();
    editorEl.querySelectorAll('.author-span[data-edit-time]').forEach(function (span) {
      const age = now - parseInt(span.dataset.editTime || '0', 10);
      if (age > FADE_AFTER_MS) {
        span.classList.remove('author-span--fresh');
        span.classList.add('author-span--faded');
      }
    });
  }

  // Run fade check every 30 seconds while on the page
  setInterval(fadeOldAuthorSpans, 30000);
  // Also run on load to fade any saved old spans
  fadeOldAuthorSpans();

  const debouncedWrap = debounce(wrapNewTextWithAuthor, 1500);

  // ── Event wiring ─────────────────────────────────────────────────────────

  if (CAN_EDIT) {
    editorEl.addEventListener('input', function () { markDirty(); debouncedWrap(); });

    // Title: only fires markDirty if owner (title field is readonly for non-owners)
    if (titleEl && CAN_RENAME) titleEl.addEventListener('input', markDirty);

    if (saveBtn) saveBtn.addEventListener('click', function (e) { e.preventDefault(); save(); });

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

  // ── Format toolbar ────────────────────────────────────────────────────────

  document.querySelectorAll('.fmt-btn[data-cmd]').forEach(function (btn) {
    btn.addEventListener('mousedown', function (e) {
      e.preventDefault();
      document.execCommand(btn.dataset.cmd, false, btn.dataset.val || null);
      editorEl.focus();
      syncToolbarState();
      markDirty();
    });
  });

  function syncToolbarState() {
    ['bold','italic','underline','strikeThrough','insertUnorderedList','insertOrderedList']
      .forEach(function (cmd) {
        const btn = document.querySelector('.fmt-btn[data-cmd="' + cmd + '"]');
        if (btn) btn.classList.toggle('active', document.queryCommandState(cmd));
      });
  }

  editorEl.addEventListener('keyup', syncToolbarState);
  editorEl.addEventListener('mouseup', syncToolbarState);

  // ── Feature 5: Collaborators panel ───────────────────────────────────────

  const collabsBtn   = document.getElementById('collabs-btn');
  const collabsPanel = document.getElementById('collabs-panel');

  if (collabsBtn && collabsPanel) {
    collabsBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      const open = collabsPanel.hidden === false;
      collabsPanel.hidden = open;
      collabsBtn.setAttribute('aria-expanded', String(!open));
      // Close history panel if open
      if (historyPanel && !historyPanel.hidden) closeHistoryPanel();
    });

    document.addEventListener('click', function (e) {
      if (!collabsPanel.hidden && !collabsPanel.contains(e.target) && e.target !== collabsBtn) {
        collabsPanel.hidden = true;
        collabsBtn.setAttribute('aria-expanded', 'false');
      }
    });

    collabsPanel.addEventListener('click', function (e) { e.stopPropagation(); });
  }

  // ── Feature 7: Inline history panel ──────────────────────────────────────

  const historyBtn     = document.getElementById('history-btn');
  const historyPanel   = document.getElementById('history-panel');
  const historyOverlay = document.getElementById('history-overlay');
  const historyClose   = document.getElementById('history-close');
  const historyList    = document.getElementById('history-list');

  function openHistoryPanel() {
    if (!historyPanel) return;
    historyPanel.hidden  = false;
    historyOverlay.hidden = false;
    // Close collabs panel if open
    if (collabsPanel && !collabsPanel.hidden) { collabsPanel.hidden = true; }
    loadVersions();
  }

  function closeHistoryPanel() {
    if (!historyPanel) return;
    historyPanel.hidden  = true;
    historyOverlay.hidden = true;
  }

  function loadVersions() {
    const url = window.NOTE_VERSIONS_URL;
    if (!url || !historyList) return;
    historyList.innerHTML = '<p class="history-loading">Loading…</p>';

    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.versions || data.versions.length === 0) {
          historyList.innerHTML = '<p class="history-empty">No versions saved yet.</p>';
          return;
        }
        historyList.innerHTML = data.versions.map(function (v, i) {
          const label = v.label || (i === 0 ? 'Current version' : '');
          const by    = v['saved_by__display_name'] || 'Unknown';
          const restoreUrl = '/notes/' + NOTE_ID + '/history/' + v.id + '/restore/';
          return (
            '<div class="history-version-item">' +
              '<div class="history-version-meta">' +
                '<span class="history-version-time">' + v.time_ago + '</span>' +
                (i === 0 ? '<span class="history-current-tag">Current</span>' : '') +
              '</div>' +
              (label ? '<p class="history-version-label">' + escHtml(label) + '</p>' : '') +
              '<p class="history-version-by">by ' + escHtml(by) + '</p>' +
              (i > 0 && (document.querySelector('meta[name="can-edit"]') || {}).content === 'true'
                ? '<form method="post" action="' + restoreUrl + '">' +
                    getCsrf() +
                    '<button type="submit" class="btn-ghost btn-sm history-restore-btn">Restore this version</button>' +
                  '</form>'
                : ''
              ) +
            '</div>'
          );
        }).join('');
      })
      .catch(function () {
        historyList.innerHTML = '<p class="history-empty">Could not load versions.</p>';
      });
  }

  function getCsrf() {
    const name = 'csrftoken';
    for (const part of document.cookie.split(';')) {
      const [k, v] = part.trim().split('=');
      if (k === name) return '<input type="hidden" name="csrfmiddlewaretoken" value="' + decodeURIComponent(v) + '">';
    }
    return '';
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  if (historyBtn)     historyBtn.addEventListener('click', openHistoryPanel);
  if (historyClose)   historyClose.addEventListener('click', closeHistoryPanel);
  if (historyOverlay) historyOverlay.addEventListener('click', closeHistoryPanel);

}());