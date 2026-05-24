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

  /* ── Cursor-following tooltip (shows author name on hover) ───────────── */
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
  ].join(';');
  document.body.appendChild(tooltip);

  editorEl.addEventListener('mouseover', function (e) {
    if (!isEditMode) { tooltip.style.display = 'none'; return; }
    var span = e.target.closest('[data-author]');
    if (!span || !span.dataset.author) {
      tooltip.style.display = 'none';
      return;
    }
    tooltip.textContent   = span.dataset.author;
    tooltip.style.color   = '#c8a97a';
    tooltip.style.display = 'block';
  });

  editorEl.addEventListener('mouseout', function (e) {
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
    if (x + tooltip.offsetWidth  > window.innerWidth  - 8) x = e.clientX - tooltip.offsetWidth  - pad;
    if (y < 8)                                              y = e.clientY + pad;
    if (y + tooltip.offsetHeight > window.innerHeight - 8) y = window.innerHeight - tooltip.offsetHeight - 8;
    tooltip.style.left = x + 'px';
    tooltip.style.top  = y + 'px';
  });

  /* ── Editor events ────────────────────────────────────────────────────── */
  if (CAN_EDIT) {
    editorEl.addEventListener('input', function () { markDirty(); });

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

  /* ── Edit / Read mode toggle ─────────────────────────────────────────── */
  var modeToggle   = document.getElementById('mode-toggle');
  var modeIconRead = document.getElementById('mode-icon-read');
  var modeIconEdit = document.getElementById('mode-icon-edit');
  var modeLabel    = document.getElementById('mode-label');
  var formatToolbar = document.getElementById('format-toolbar');
  var editorPage   = document.getElementById('editor-page');

  // Start in edit mode (default)
  var isEditMode = true;

  function setEditMode(edit) {
    isEditMode = edit;

    if (edit) {
      // Switch TO edit mode
      editorEl.setAttribute('contenteditable', 'true');
      editorEl.classList.remove('note-editor--readonly');
      if (formatToolbar) formatToolbar.style.display = '';
      if (saveBtn)       saveBtn.style.display = '';
      if (editorPage)    editorPage.classList.remove('read-mode');
      if (modeIconRead)  modeIconRead.style.display = '';
      if (modeIconEdit)  modeIconEdit.style.display = 'none';
      if (modeLabel)     modeLabel.textContent = 'Read';
      if (modeToggle)    modeToggle.title = 'Switch to read mode';
      tooltip.style.display = 'none'; // hide any stale tooltip
    } else {
      // Switch TO read mode
      editorEl.removeAttribute('contenteditable');
      editorEl.classList.add('note-editor--readonly');
      if (formatToolbar) formatToolbar.style.display = 'none';
      if (saveBtn)       saveBtn.style.display = 'none';
      if (editorPage)    editorPage.classList.add('read-mode');
      if (modeIconRead)  modeIconRead.style.display = 'none';
      if (modeIconEdit)  modeIconEdit.style.display = '';
      if (modeLabel)     modeLabel.textContent = 'Edit';
      if (modeToggle)    modeToggle.title = 'Switch to edit mode';
      tooltip.style.display = 'none';
    }
  }

  if (modeToggle && CAN_EDIT) {
    modeToggle.addEventListener('click', function () {
      setEditMode(!isEditMode);
    });
  }

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