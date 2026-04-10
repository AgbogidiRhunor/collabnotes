(function () {
  'use strict';

  const editorEl    = document.getElementById('note-editor');
  const titleEl     = document.getElementById('note-title');
  const contentField = document.getElementById('note-content-field'); // hidden textarea
  const noteForm    = document.getElementById('note-form');
  const saveStatus  = document.getElementById('save-status');
  const saveBtn     = document.getElementById('save-btn');

  if (!editorEl || !noteForm) return;

  const CAN_EDIT   = editorEl.getAttribute('contenteditable') === 'true';
  const CURRENT_USER = (document.querySelector('meta[name="current-user"]') || {}).content || '';

  let isDirty  = false;
  let isSaving = false;

  // Status helper
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

  // Save
  function save() {
    if (!CAN_EDIT || isSaving) return;

    // Wrap any plain text the user just typed with their author span
    wrapNewTextWithAuthor();

    // Copy editor HTML into the hidden textarea so the POST includes it
    if (contentField) contentField.value = editorEl.innerHTML;

    // Mark as saving — clears dirty so beforeunload won't fire
    isSaving = true;
    isDirty  = false;
    setStatus('Saving…', 'saving');
    if (saveBtn) {
      saveBtn.classList.remove('btn-primary--pulse');
      saveBtn.disabled = true;
    }

    noteForm.submit();
  }

  // Author highlighting 
  // Strategy: when the user stops typing (debounced), we find any text nodes
  // that are NOT already inside an author <span> and wrap them in one.

  const AUTHOR_COLORS = [
    '#c8a97a','#6fcf97','#56b4e9','#bb8fce',
    '#f08080','#f7dc6f','#98d8c8','#85c1e9',
  ];

  function colorForName(name) {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
    return AUTHOR_COLORS[Math.abs(h) % AUTHOR_COLORS.length];
  }

  function wrapNewTextWithAuthor() {
    if (!CURRENT_USER) return;
    const color = colorForName(CURRENT_USER);

    // Walk all text nodes inside the editor
    const walker = document.createTreeWalker(editorEl, NodeFilter.SHOW_TEXT);
    const toWrap = [];

    let node;
    while ((node = walker.nextNode())) {
      // Skip if already inside an author span
      if (node.parentElement.closest('[data-author]')) continue;
      // Skip empty/whitespace-only nodes
      if (!node.textContent.trim()) continue;
      toWrap.push(node);
    }

    toWrap.forEach(function (textNode) {
      const span = document.createElement('span');
      span.dataset.author = CURRENT_USER;
      span.style.setProperty('--author-color', color);
      span.className = 'author-span';
      textNode.parentNode.insertBefore(span, textNode);
      span.appendChild(textNode);
    });
  }

  // Debounce the wrap so it doesn't interrupt mid-word typing
  function debounce(fn, ms) {
    let t;
    return function () { clearTimeout(t); t = setTimeout(fn, ms); };
  }

  const debouncedWrap = debounce(wrapNewTextWithAuthor, 1500);

  // Event wiring
  if (CAN_EDIT) {
    editorEl.addEventListener('input', function () {
      markDirty();
      debouncedWrap();
    });

    if (titleEl) titleEl.addEventListener('input', markDirty);

    // Save button
    if (saveBtn) {
      saveBtn.addEventListener('click', function (e) {
        e.preventDefault();
        save();
      });
    }

    // Ctrl+S / Cmd+S
    document.addEventListener('keydown', function (e) {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key === 's') { e.preventDefault(); save(); return; }
      if (mod && e.key === 'b') { e.preventDefault(); document.execCommand('bold'); }
      if (mod && e.key === 'i') { e.preventDefault(); document.execCommand('italic'); }
      if (mod && e.key === 'u') { e.preventDefault(); document.execCommand('underline'); }
    });

    // Warn before leaving only if there are unsaved changes AND we're not mid-save
    window.addEventListener('beforeunload', function (e) {
      if (isDirty && !isSaving) {
        e.preventDefault();
        e.returnValue = '';
      }
    });
  }

  // Format toolbar 
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
    ['bold', 'italic', 'underline', 'strikeThrough', 'insertUnorderedList', 'insertOrderedList']
      .forEach(function (cmd) {
        const btn = document.querySelector('.fmt-btn[data-cmd="' + cmd + '"]');
        if (btn) btn.classList.toggle('active', document.queryCommandState(cmd));
      });
  }

  editorEl.addEventListener('keyup', syncToolbarState);
  editorEl.addEventListener('mouseup', syncToolbarState);

}());