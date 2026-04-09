(function () {
  'use strict';

  /* Read config from the page */
  const noteMeta    = document.querySelector('meta[name="note-id"]');
  const canEditMeta = document.querySelector('meta[name="can-edit"]');

  if (!noteMeta) return;   // Not on an editor page — do nothing

  const NOTE_ID  = noteMeta.getAttribute('content');
  const CAN_EDIT = canEditMeta && canEditMeta.getAttribute('content') === 'true';

  /* DOM references */
  const editorEl      = document.getElementById('note-editor');
  const titleEl       = document.getElementById('note-title');
  const hiddenContent = document.getElementById('note-content-hidden');
  const noteForm      = document.getElementById('note-form');
  const saveStatus    = document.getElementById('save-status');
  const collabBar     = document.getElementById('collab-avatars');

  if (!editorEl) return;

  /* Helpers */
  function debounce(fn, ms) {
    let t;
    return function (...args) { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), ms); };
  }

  function setStatus(text, cls) {
    if (!saveStatus) return;
    saveStatus.textContent = text;
    saveStatus.className   = 'save-status ' + (cls || '');
  }

  /* Sync contenteditable → hidden textarea before POST */
  if (noteForm) {
    noteForm.addEventListener('submit', function () {
      if (hiddenContent) hiddenContent.value = editorEl.innerHTML;
    });
  }

  /* Format toolbar */
  document.querySelectorAll('.fmt-btn[data-cmd]').forEach(function (btn) {
    btn.addEventListener('mousedown', function (e) {
      e.preventDefault();                          // Keep focus in editor
      const cmd = btn.dataset.cmd;
      const val = btn.dataset.val || null;
      document.execCommand(cmd, false, val);
      editorEl.focus();
      syncToolbarState();
    });
  });

  function syncToolbarState() {
    ['bold', 'italic', 'underline', 'strikeThrough',
     'insertUnorderedList', 'insertOrderedList'].forEach(function (cmd) {
      const btn = document.querySelector('.fmt-btn[data-cmd="' + cmd + '"]');
      if (btn) btn.classList.toggle('active', document.queryCommandState(cmd));
    });
  }

  if (CAN_EDIT) {
    editorEl.addEventListener('keyup',  syncToolbarState);
    editorEl.addEventListener('mouseup', syncToolbarState);

    // Keyboard shortcuts
    editorEl.addEventListener('keydown', function (e) {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key === 'b') { e.preventDefault(); document.execCommand('bold'); }
      if (mod && e.key === 'i') { e.preventDefault(); document.execCommand('italic'); }
      if (mod && e.key === 'u') { e.preventDefault(); document.execCommand('underline'); }
    });
  }

  /* WebSocket */
  const WS_RECONNECT_BASE = 1500;
  const WS_RECONNECT_MAX  = 30000;
  const SEND_DEBOUNCE_MS  = 600;

  let socket           = null;
  let reconnectAttempt = 0;
  let reconnectTimer   = null;

  function wsUrl() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    return proto + '://' + location.host + '/ws/notes/' + NOTE_ID + '/';
  }

  function connect() {
    socket = new WebSocket(wsUrl());

    socket.onopen = function () {
      reconnectAttempt = 0;
      clearTimeout(reconnectTimer);
      if (CAN_EDIT) {
        setStatus('Connected', '');
      }
    };

    socket.onmessage = function (ev) {
      try {
        handleMessage(JSON.parse(ev.data));
      } catch (_) {}
    };

    socket.onclose = function (ev) {
      // 4001 = unauthenticated, 4003 = unauthorised — don't retry
      if (ev.code === 4001 || ev.code === 4003) {
        setStatus('Not authorised', 'error');
        return;
      }
      setStatus('Reconnecting…', 'error');
      reconnectAttempt++;
      const delay = Math.min(
        WS_RECONNECT_BASE * Math.pow(1.5, reconnectAttempt - 1),
        WS_RECONNECT_MAX
      );
      reconnectTimer = setTimeout(connect, delay);
    };

    socket.onerror = function () {
      /* onclose fires right after — handled there */
    };
  }

  function sendMsg(obj) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(obj));
    }
  }

  /* Incoming message handler */
  function handleMessage(msg) {
    switch (msg.type) {

      case 'content_update':
        // Another user edited — update our editor without losing our own cursor
        if (document.activeElement !== editorEl) {
          editorEl.innerHTML = msg.content;
        } else {
          // User is currently typing: apply carefully to avoid cursor jump
          applyRemoteContent(msg.content);
        }
        if (msg.title && titleEl && document.activeElement !== titleEl) {
          titleEl.value = msg.title;
        }
        setStatus('Up to date', '');
        break;

      case 'title_update':
        if (msg.title && titleEl && document.activeElement !== titleEl) {
          titleEl.value = msg.title;
        }
        break;

      case 'saved':
        setStatus('Saved', 'saved');
        // Reset to "All changes saved" after 2 s
        setTimeout(function () { setStatus('All changes saved', ''); }, 2000);
        break;

      case 'user_joined':
        addCollabAvatar(msg.user_id, msg.display_name, msg.initials);
        break;

      case 'user_left':
        removeCollabAvatar(msg.user_id);
        break;

      case 'error':
        setStatus(msg.message || 'Error', 'error');
        break;
    }
  }

  /**
   * Apply remote HTML without moving the cursor if the user is mid-type.
   * Simple strategy: only update if the content actually changed.
   */
  function applyRemoteContent(html) {
    if (editorEl.innerHTML !== html) {
      const sel = window.getSelection();
      // Save caret position as text offset
      const offset = getCaretOffset(editorEl);
      editorEl.innerHTML = html;
      // Restore caret approximately
      if (sel && offset !== null) {
        setCaretOffset(editorEl, offset);
      }
    }
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

  /* Send content on editor input (debounced) */
  if (CAN_EDIT) {
    const sendContent = debounce(function () {
      setStatus('Saving…', 'saving');
      sendMsg({
        type:    'content_update',
        content: editorEl.innerHTML,
        title:   titleEl ? titleEl.value : '',
      });
    }, SEND_DEBOUNCE_MS);

    editorEl.addEventListener('input', sendContent);

    const sendTitle = debounce(function () {
      sendMsg({ type: 'title_update', title: titleEl.value });
    }, 400);

    if (titleEl) {
      titleEl.addEventListener('input', function () {
        sendTitle();
        setStatus('Saving…', 'saving');
      });
    }
  }

  /* Collaborator avatars */
  const AVATAR_COLORS = [
    '#c8a97a','#6fcf97','#56b4e9','#bb8fce',
    '#f08080','#85c1e9','#f7dc6f','#98d8c8',
  ];

  function colorForId(id) {
    let hash = 0;
    for (let i = 0; i < id.length; i++) hash = id.charCodeAt(i) + ((hash << 5) - hash);
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
  }

  function addCollabAvatar(userId, displayName, initials) {
    if (!collabBar) return;
    if (collabBar.querySelector('[data-uid="' + userId + '"]')) return;
    const el       = document.createElement('span');
    el.className   = 'avatar avatar--sm';
    el.dataset.uid = userId;
    el.title       = displayName;
    el.textContent = initials || displayName.slice(0, 2).toUpperCase();
    el.style.background = colorForId(userId);
    el.style.color      = '#111113';
    collabBar.appendChild(el);
  }

  function removeCollabAvatar(userId) {
    if (!collabBar) return;
    const el = collabBar.querySelector('[data-uid="' + userId + '"]');
    if (el) el.remove();
  }

  /* Bootstrap */
  connect();

  // Keep-alive ping every 25 s
  setInterval(function () { sendMsg({ type: 'ping' }); }, 25000);

  // On page unload, try to flush content via sendBeacon
  window.addEventListener('beforeunload', function () {
    if (CAN_EDIT && navigator.sendBeacon) {
      // POST the form data so Django saves it even if WS is closing
      const fd = new FormData(noteForm);
      fd.set('content', editorEl.innerHTML);
      navigator.sendBeacon(noteForm.action, fd);
    }
  });

}());
