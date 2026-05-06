(function () {
  'use strict';

  /* ── DOM ──────────────────────────────────────────────────────────────── */
  const editorEl     = document.getElementById('note-editor');
  const titleEl      = document.getElementById('note-title');
  const contentField = document.getElementById('note-content-field');
  const noteForm     = document.getElementById('note-form');
  const saveStatus   = document.getElementById('save-status');
  const saveBtn      = document.getElementById('save-btn');
  const collabsBtn   = document.getElementById('collabs-btn');
  const collabsPanel = document.getElementById('collabs-panel');

  if (!editorEl || !noteForm) return;

  /* ── Meta ─────────────────────────────────────────────────────────────── */
  const CAN_EDIT     = editorEl.getAttribute('contenteditable') === 'true';
  const CAN_RENAME   = (document.querySelector('meta[name="can-rename"]') || {}).content === 'true';
  const CURRENT_USER = (document.querySelector('meta[name="current-user"]') || {}).content || '';

  let isDirty  = false;
  let isSaving = false;

  /* ── Helpers ──────────────────────────────────────────────────────────── */
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

  /* ── Author tooltip (JS-driven, avoids CSS ::after clipping issues) ──── */
  const authorTooltip = document.createElement('div');
  authorTooltip.id = 'author-tooltip';
  authorTooltip.style.cssText = [
    'position:fixed',
    'display:none',
    'padding:3px 10px',
    'background:var(--bg-elevated,#1e1e23)',
    'border:1px solid var(--border-strong,rgba(255,255,255,0.15))',
    'border-radius:5px',
    'font-size:0.72rem',
    'font-weight:600',
    'font-family:Inter,system-ui,sans-serif',
    'white-space:nowrap',
    'pointer-events:none',
    'z-index:500',
    'box-shadow:0 4px 12px rgba(0,0,0,0.35)',
    'transition:opacity 0.1s',
  ].join(';');
  document.body.appendChild(authorTooltip);

  editorEl.addEventListener('mouseover', function (e) {
    const span = e.target.closest('[data-author]');
    if (!span) { authorTooltip.style.display = 'none'; return; }
    const author = span.dataset.author;
    const color  = getComputedStyle(span).getPropertyValue('--author-color').trim() || '#c8a97a';
    authorTooltip.textContent = author;
    authorTooltip.style.color = color;
    authorTooltip.style.display = 'block';
  });

  editorEl.addEventListener('mouseout', function (e) {
    if (!e.relatedTarget || !e.relatedTarget.closest('[data-author]')) {
      authorTooltip.style.display = 'none';
    }
  });

  document.addEventListener('mousemove', function (e) {
    if (authorTooltip.style.display === 'none') return;
    const pad = 12;
    let x = e.clientX + pad;
    let y = e.clientY - 30;
    /* Keep inside viewport */
    const tw = authorTooltip.offsetWidth;
    const th = authorTooltip.offsetHeight;
    if (x + tw > window.innerWidth  - 8) x = e.clientX - tw - pad;
    if (y < 8) y = e.clientY + pad;
    if (y + th > window.innerHeight - 8) y = window.innerHeight - th - 8;
    authorTooltip.style.left = x + 'px';
    authorTooltip.style.top  = y + 'px';
  });


  /* ── Editor events ────────────────────────────────────────────────────── */
  if (CAN_EDIT) {
    editorEl.addEventListener('input', function () { markDirty(); debouncedWrap(); });

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

  /* ── Collaborators panel ──────────────────────────────────────────────── */
  if (collabsBtn && collabsPanel) {
    collabsBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      const isOpen = collabsPanel.classList.contains('is-open');
      if (isOpen) {
        collabsPanel.classList.remove('is-open');
        collabsBtn.setAttribute('aria-expanded', 'false');
      } else {
        collabsPanel.classList.add('is-open');
        collabsBtn.setAttribute('aria-expanded', 'true');
      }
    });

    document.addEventListener('click', function (e) {
      if (collabsPanel.classList.contains('is-open') &&
          !collabsPanel.contains(e.target) &&
          !collabsBtn.contains(e.target)) {
        collabsPanel.classList.remove('is-open');
        collabsBtn.setAttribute('aria-expanded', 'false');
      }
    });

    collabsPanel.addEventListener('click', function (e) { e.stopPropagation(); });
  }

}());