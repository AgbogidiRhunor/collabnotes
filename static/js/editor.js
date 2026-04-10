(function () {
  'use strict';

  const editorEl      = document.getElementById('note-editor');
  const titleEl       = document.getElementById('note-title');
  const hiddenContent = document.getElementById('note-content-hidden');
  const noteForm      = document.getElementById('note-form');
  const saveStatus    = document.getElementById('save-status');
  const saveBtn       = document.getElementById('save-btn');

  if (!editorEl) return;

  const CAN_EDIT = editorEl.getAttribute('contenteditable') === 'true';

  // Track whether there are unsaved changes
  let isDirty = false;

  function setStatus(text, cls) {
    if (!saveStatus) return;
    saveStatus.textContent = text;
    saveStatus.className = 'save-status' + (cls ? ' ' + cls : '');
  }

  function markDirty() {
    if (!isDirty) {
      isDirty = true;
      setStatus('Unsaved changes', 'saving');
      if (saveBtn) saveBtn.classList.add('btn-primary--pulse');
    }
  }

  function syncAndSubmit() {
    if (hiddenContent) hiddenContent.value = editorEl.innerHTML;
    setStatus('Saving…', 'saving');
    noteForm.submit();
  }

  // Sync contenteditable → hidden textarea before any form submit
  if (noteForm) {
    noteForm.addEventListener('submit', function () {
      if (hiddenContent) hiddenContent.value = editorEl.innerHTML;
    });
  }

  if (!CAN_EDIT) return;

  // Mark dirty on any edit
  editorEl.addEventListener('input', markDirty);
  if (titleEl) titleEl.addEventListener('input', markDirty);

  // Ctrl+S / Cmd+S to save
  document.addEventListener('keydown', function (e) {
    const mod = e.ctrlKey || e.metaKey;

    if (mod && e.key === 's') {
      e.preventDefault();
      syncAndSubmit();
      return;
    }

    // Formatting shortcuts
    if (mod && e.key === 'b') { e.preventDefault(); document.execCommand('bold'); }
    if (mod && e.key === 'i') { e.preventDefault(); document.execCommand('italic'); }
    if (mod && e.key === 'u') { e.preventDefault(); document.execCommand('underline'); }
  });

  // Save button click
  if (saveBtn) {
    saveBtn.addEventListener('click', function (e) {
      e.preventDefault();
      syncAndSubmit();
    });
  }

  // Warn before leaving with unsaved changes
  window.addEventListener('beforeunload', function (e) {
    if (isDirty) {
      e.preventDefault();
      e.returnValue = '';
    }
  });

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