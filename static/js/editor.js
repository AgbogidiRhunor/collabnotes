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

  /* ── Author colours ───────────────────────────────────────────────────── */
  // 4 distinct soft colours — one per collaborator, deterministic by name
  const AUTHOR_PALETTE = ['#c8a97a', '#6fcf97', '#56b4e9', '#bb8fce'];
  const FADE_AFTER_MS  = 5 * 60 * 1000; // 5 minutes

  function colorForName(name) {
    var h = 0;
    for (var i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
    return AUTHOR_PALETTE[Math.abs(h) % AUTHOR_PALETTE.length];
  }

  /* ── Author highlighting ──────────────────────────────────────────────── */
  function wrapNewTextWithAuthor() {
    if (!CURRENT_USER) return;
    var color  = colorForName(CURRENT_USER);
    var now    = Date.now();
    var walker = document.createTreeWalker(editorEl, NodeFilter.SHOW_TEXT);
    var toWrap = [];
    var node;
    while ((node = walker.nextNode())) {
      if (node.parentElement.closest('[data-author]')) continue;
      if (!node.textContent.trim()) continue;
      toWrap.push(node);
    }
    toWrap.forEach(function (tn) {
      var span = document.createElement('span');
      span.dataset.author   = CURRENT_USER;
      span.dataset.editTime = now;
      span.dataset.color    = color; // store as data attr — readable without CSS vars
      span.className        = 'author-span author-span--fresh';
      span.style.background = hexToRgba(color, 0.18);
      tn.parentNode.insertBefore(span, tn);
      span.appendChild(tn);
    });
  }

  function fadeOldAuthorSpans() {
    var now = Date.now();
    editorEl.querySelectorAll('.author-span[data-edit-time]').forEach(function (span) {
      if (now - parseInt(span.dataset.editTime || '0', 10) > FADE_AFTER_MS) {
        span.classList.remove('author-span--fresh');
        span.classList.add('author-span--faded');
        span.style.background = 'transparent';
      }
    });
  }

  // Convert hex colour to rgba string — avoids color-mix() browser issues
  function hexToRgba(hex, alpha) {
    var r = parseInt(hex.slice(1, 3), 16);
    var g = parseInt(hex.slice(3, 5), 16);
    var b = parseInt(hex.slice(5, 7), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
  }

  // On page load: re-apply colours to all existing author spans in saved content
  editorEl.querySelectorAll('[data-author]').forEach(function (span) {
    var author = span.dataset.author;
    if (!author) return;
    var color = colorForName(author);
    span.dataset.color = color;
    // Only apply background if fresh (not already faded)
    if (span.classList.contains('author-span--faded')) {
      span.style.background = 'transparent';
    } else {
      span.style.background = hexToRgba(color, 0.18);
      if (!span.classList.contains('author-span--fresh')) {
        span.classList.add('author-span', 'author-span--fresh');
      }
    }
  });

  // Run fade check immediately and every 30s
  fadeOldAuthorSpans();
  setInterval(fadeOldAuthorSpans, 30000);

  /* ── Tooltip (JS-driven, follows cursor, single instance) ────────────── */
  var tooltip = document.createElement('div');
  tooltip.style.cssText = [
    'position:fixed',
    'display:none',
    'padding:3px 10px',
    'border-radius:5px',
    'font-size:0.72rem',
    'font-weight:600',
    'font-family:Inter,system-ui,sans-serif',
    'font-style:normal',
    'white-space:nowrap',
    'pointer-events:none',
    'z-index:9999',
    'box-shadow:0 4px 12px rgba(0,0,0,0.4)',
    'border:1px solid rgba(255,255,255,0.12)',
    'background:#1e1e23',
    'color:#c8a97a',
  ].join(';');
  document.body.appendChild(tooltip);

  editorEl.addEventListener('mouseover', function (e) {
    var span = e.target.closest('[data-author]');
    if (!span || !span.dataset.author) {
      tooltip.style.display = 'none';
      return;
    }
    var color = span.dataset.color || colorForName(span.dataset.author);
    tooltip.textContent   = span.dataset.author;
    tooltip.style.color   = color;
    tooltip.style.display = 'block';
  });

  editorEl.addEventListener('mouseout', function (e) {
    // Only hide if we're leaving the editor entirely or moving to a non-author element
    var to = e.relatedTarget;
    if (!to || !to.closest || !to.closest('[data-author]')) {
      tooltip.style.display = 'none';
    }
  });

  document.addEventListener('mousemove', function (e) {
    if (tooltip.style.display === 'none') return;
    var pad = 14;
    var x   = e.clientX + pad;
    var y   = e.clientY - 34;
    // Clamp inside viewport
    if (x + tooltip.offsetWidth  > window.innerWidth  - 8) x = e.clientX - tooltip.offsetWidth  - pad;
    if (y < 8)                                              y = e.clientY + pad;
    if (y + tooltip.offsetHeight > window.innerHeight - 8) y = window.innerHeight - tooltip.offsetHeight - 8;
    tooltip.style.left = x + 'px';
    tooltip.style.top  = y + 'px';
  });

  /* ── Debounced wrap — defined here so it's available to editor input ── */
  var debouncedWrap = debounce(wrapNewTextWithAuthor, 1500);

  /* ── Editor events ────────────────────────────────────────────────────── */
  if (CAN_EDIT) {
    editorEl.addEventListener('input', function () { markDirty(); debouncedWrap(); });

    if (titleEl && CAN_RENAME) titleEl.addEventListener('input', markDirty);

    if (saveBtn) saveBtn.addEventListener('click', function (e) { e.preventDefault(); save(); });

    document.addEventListener('keydown', function (e) {
      var mod = e.ctrlKey || e.metaKey;
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
        var btn = document.querySelector('.fmt-btn[data-cmd="' + cmd + '"]');
        if (btn) btn.classList.toggle('active', document.queryCommandState(cmd));
      });
  }

  editorEl.addEventListener('keyup', syncToolbar);
  editorEl.addEventListener('mouseup', syncToolbar);

  /* ── Collaborators panel ──────────────────────────────────────────────── */
  if (collabsBtn && collabsPanel) {
    collabsBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (collabsPanel.classList.contains('is-open')) {
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