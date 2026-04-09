(function () {
  'use strict';

  const noteMeta    = document.querySelector('meta[name="note-id"]');
  const canEditMeta = document.querySelector('meta[name="can-edit"]');
  if (!noteMeta) return;

  const NOTE_ID  = noteMeta.getAttribute('content');
  const CAN_EDIT = canEditMeta && canEditMeta.getAttribute('content') === 'true';

  const editorEl      = document.getElementById('note-editor');
  const titleEl       = document.getElementById('note-title');
  const hiddenContent = document.getElementById('note-content-hidden');
  const noteForm      = document.getElementById('note-form');
  const saveStatus    = document.getElementById('save-status');
  const collabBar     = document.getElementById('collab-avatars');
  const lastEditorEl  = document.getElementById('last-editor');

  if (!editorEl) return;

  function debounce(fn, ms) {
    let t;
    return function (...args) { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), ms); };
  }

  function setStatus(text, cls) {
    if (!saveStatus) return;
    saveStatus.textContent = text;
    saveStatus.className = 'save-status' + (cls ? ' ' + cls : '');
  }

  function setLastEditor(name) {
    if (!lastEditorEl) return;
    if (name) {
      lastEditorEl.textContent = name + ' is editing';
      lastEditorEl.style.display = 'inline';
    } else {
      lastEditorEl.textContent = '';
      lastEditorEl.style.display = 'none';
    }
  }

  // Sync contenteditable → hidden textarea before form POST (fallback save)
  if (noteForm) {
    noteForm.addEventListener('submit', function () {
      if (hiddenContent) hiddenContent.value = editorEl.innerHTML;
    });
  }

  // Format toolbar
  document.querySelectorAll('.fmt-btn[data-cmd]').forEach(function (btn) {
    btn.addEventListener('mousedown', function (e) {
      e.preventDefault();
      document.execCommand(btn.dataset.cmd, false, btn.dataset.val || null);
      editorEl.focus();
      syncToolbarState();
    });
  });

  function syncToolbarState() {
    ['bold', 'italic', 'underline', 'strikeThrough', 'insertUnorderedList', 'insertOrderedList']
      .forEach(function (cmd) {
        const btn = document.querySelector('.fmt-btn[data-cmd="' + cmd + '"]');
        if (btn) btn.classList.toggle('active', document.queryCommandState(cmd));
      });
  }

  if (CAN_EDIT) {
    editorEl.addEventListener('keyup', syncToolbarState);
    editorEl.addEventListener('mouseup', syncToolbarState);
    editorEl.addEventListener('keydown', function (e) {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key === 'b') { e.preventDefault(); document.execCommand('bold'); }
      if (mod && e.key === 'i') { e.preventDefault(); document.execCommand('italic'); }
      if (mod && e.key === 'u') { e.preventDefault(); document.execCommand('underline'); }
    });
  }

  // WebSocket
  const WS_RECONNECT_BASE = 1500;
  const WS_RECONNECT_MAX  = 30000;
  const SEND_DEBOUNCE_MS  = 600;

  let socket           = null;
  let reconnectAttempt = 0;
  let reconnectTimer   = null;
  let wsConnected      = false;

  function wsUrl() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    return proto + '://' + location.host + '/ws/notes/' + NOTE_ID + '/';
  }

  function connect() {
    socket = new WebSocket(wsUrl());

    socket.onopen = function () {
      wsConnected = true;
      reconnectAttempt = 0;
      clearTimeout(reconnectTimer);
      // Only update status if user can edit — viewers just silently connect
      if (CAN_EDIT) setStatus('All changes saved', '');
    };

    socket.onmessage = function (ev) {
      try { handleMessage(JSON.parse(ev.data)); } catch (_) {}
    };

    socket.onclose = function (ev) {
      wsConnected = false;
      if (ev.code === 4001 || ev.code === 4003) {
        setStatus('Not authorised', 'error');
        return;
      }
      // Don't show reconnecting if we haven't connected yet (e.g. runserver without daphne)
      if (reconnectAttempt > 0 && CAN_EDIT) {
        setStatus('Reconnecting…', 'error');
      }
      reconnectAttempt++;
      const delay = Math.min(WS_RECONNECT_BASE * Math.pow(1.5, reconnectAttempt - 1), WS_RECONNECT_MAX);
      reconnectTimer = setTimeout(connect, delay);
    };

    socket.onerror = function () { /* onclose handles it */ };
  }

  function sendMsg(obj) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(obj));
      return true;
    }
    return false;
  }

  function handleMessage(msg) {
    switch (msg.type) {

      case 'saved':
        // Server confirmed our save
        setStatus('Saved', 'saved');
        setTimeout(function () {
          if (saveStatus && saveStatus.classList.contains('saved')) {
            setStatus('All changes saved', '');
          }
        }, 2000);
        break;

      case 'content_update':
        // Another user saved — update our view
        if (msg.updated_by) setLastEditor(msg.updated_by);
        // Clear "editing" indicator after 3s of no updates
        clearTimeout(window._lastEditorTimer);
        window._lastEditorTimer = setTimeout(function () { setLastEditor(null); }, 3000);

        if (document.activeElement !== editorEl) {
          editorEl.innerHTML = msg.content;
        } else {
          applyRemoteContent(msg.content);
        }
        if (msg.title && titleEl && document.activeElement !== titleEl) {
          titleEl.value = msg.title;
        }
        // Update note title in browser tab too
        if (msg.title) document.title = msg.title + ' — CollabNotes';
        break;

      case 'title_update':
        if (msg.title && titleEl && document.activeElement !== titleEl) {
          titleEl.value = msg.title;
          document.title = msg.title + ' — CollabNotes';
        }
        break;

      case 'user_joined':
        addCollabAvatar(msg.user_id, msg.display_name, msg.initials);
        break;

      case 'user_left':
        removeCollabAvatar(msg.user_id);
        // Clear their editing indicator if it was them
        break;

      case 'error':
        setStatus(msg.message || 'Error', 'error');
        break;
    }
  }

  function applyRemoteContent(html) {
    if (editorEl.innerHTML === html) return;
    const offset = getCaretOffset(editorEl);
    editorEl.innerHTML = html;
    if (offset !== null) setCaretOffset(editorEl, offset);
  }

  function getCaretOffset(container) {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return null;
    const range = sel.getRangeAt(0);
    const pre   = range.cloneRange();
    pre.selectNodeContents(container);
    pre.setEnd(range.endContainer, range.endOffset);
    return pre.toString().length;
  }

  function setCaretOffset(container, offset) {
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    let remaining = offset;
    let node;
    while ((node = walker.nextNode())) {
      if (remaining <= node.textContent.length) {
        const range = document.createRange();
        const sel   = window.getSelection();
        range.setStart(node, remaining);
        range.collapse(true);
        sel.removeAllRanges();
        sel.addRange(range);
        return;
      }
      remaining -= node.textContent.length;
    }
  }

  // Send content on input (debounced)
  if (CAN_EDIT) {
    const sendContent = debounce(function () {
      const sent = sendMsg({
        type:    'content_update',
        content: editorEl.innerHTML,
        title:   titleEl ? titleEl.value : '',
      });
      // Only show "Saving…" if WS actually sent — otherwise content saves on form submit
      if (sent) setStatus('Saving…', 'saving');
    }, SEND_DEBOUNCE_MS);

    editorEl.addEventListener('input', function () {
      // Show "Saving…" immediately on keypress so user gets instant feedback
      if (wsConnected) setStatus('Saving…', 'saving');
      sendContent();
    });

    const sendTitle = debounce(function () {
      sendMsg({ type: 'title_update', title: titleEl.value });
    }, 400);

    if (titleEl) {
      titleEl.addEventListener('input', function () {
        if (wsConnected) setStatus('Saving…', 'saving');
        sendTitle();
      });
    }
  }

  // Collaborator avatars
  const AVATAR_COLORS = ['#c8a97a','#6fcf97','#56b4e9','#bb8fce','#f08080','#85c1e9','#f7dc6f','#98d8c8'];

  function colorForId(id) {
    let h = 0;
    for (let i = 0; i < id.length; i++) h = id.charCodeAt(i) + ((h << 5) - h);
    return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
  }

  function addCollabAvatar(userId, displayName, initials) {
    if (!collabBar || collabBar.querySelector('[data-uid="' + userId + '"]')) return;
    const el = document.createElement('span');
    el.className = 'avatar avatar--sm';
    el.dataset.uid = userId;
    el.title = displayName;
    el.textContent = initials || displayName.slice(0, 2).toUpperCase();
    el.style.background = colorForId(userId);
    el.style.color = '#111113';
    collabBar.appendChild(el);
  }

  function removeCollabAvatar(userId) {
    if (!collabBar) return;
    const el = collabBar.querySelector('[data-uid="' + userId + '"]');
    if (el) el.remove();
  }

  connect();

  setInterval(function () { sendMsg({ type: 'ping' }); }, 25000);

  window.addEventListener('beforeunload', function () {
    if (CAN_EDIT && noteForm && navigator.sendBeacon) {
      const fd = new FormData(noteForm);
      fd.set('content', editorEl.innerHTML);
      navigator.sendBeacon(noteForm.action, fd);
    }
  });

}());