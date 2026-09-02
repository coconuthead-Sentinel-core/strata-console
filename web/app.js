/* Strata Console — web shell front end.
 *
 * Talks to Python through pywebview's bridge (window.pywebview.api).
 * Nothing here reimplements engine logic: dictation punctuation, speech
 * normalisation and the clear floor all happen in Python, in the same
 * kernels the desktop shell uses. This file draws and listens.
 */

'use strict';

const $ = (id) => document.getElementById(id);
const log = $('log');

let api = null;
let lastReply = '';
let lastSpeakable = '';
let lastTurn = null;
let recording = false;
let speaking = false;

/* ---------- transcript ------------------------------------------------ */

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

/* A deliberately small markdown renderer.
 *
 * The desktop shell could not render markdown at all, which is why it
 * had to STRIP it before speaking. Here the model's formatting survives.
 * Everything is escaped first, so no model output can inject markup —
 * the reply is data, never trusted as HTML. */
function markdown(src) {
  const blocks = [];
  let text = esc(src).replace(/```([\s\S]*?)(?:```|$)/g, (_m, code) => {
    blocks.push(code.replace(/^[^\n]*\n/, ''));
    return ' BLOCK' + (blocks.length - 1) + ' ';
  });

  text = text
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*\*\*(\S(?:[\s\S]*?\S)?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(\S(?:[\s\S]*?\S)?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*(\S(?:[^*]*?\S)?)\*/g, '$1<em>$2</em>');

  const out = [];
  let list = null;
  const closeList = () => { if (list) { out.push('</' + list + '>'); list = null; } };

  for (const raw of text.split('\n')) {
    const line = raw.trimEnd();
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    const bullet = line.match(/^\s*[-*+]\s+(.*)$/);
    const number = line.match(/^\s*\d+[.)]\s+(.*)$/);
    const quote = line.match(/^\s*>\s?(.*)$/);

    if (bullet || number) {
      const want = bullet ? 'ul' : 'ol';
      if (list !== want) { closeList(); out.push('<' + want + '>'); list = want; }
      out.push('<li>' + (bullet || number)[1] + '</li>');
    } else if (heading) {
      closeList();
      out.push('<h3>' + heading[2] + '</h3>');
    } else if (quote) {
      closeList();
      out.push('<blockquote>' + quote[1] + '</blockquote>');
    } else if (line.trim() === '') {
      closeList();
    } else {
      closeList();
      out.push('<p>' + line + '</p>');
    }
  }
  closeList();

  return out.join('').replace(/ BLOCK(\d+) /g,
    (_m, i) => '<pre><code>' + blocks[Number(i)] + '</code></pre>');
}

function turn(who, body, cls) {
  const el = document.createElement('article');
  el.className = 'turn ' + (cls || '');
  el.innerHTML = '<div class="who">' + esc(who) + '</div>' +
                 '<div class="body">' + body + '</div>';
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

function note(text, bad) {
  const el = document.createElement('p');
  el.className = 'note' + (bad ? ' bad' : '');
  el.textContent = text;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
}

/* ---------- reading size ---------------------------------------------- */

let size = 17;
function applySize(next) {
  size = Math.max(12, Math.min(34, next));
  document.documentElement.style.setProperty('--text', size + 'px');
  $('size').value = size + 'px';
  if (api) api.set_pref('web_font_size', size);
}

/* ---------- read-along -------------------------------------------------
 *
 * Speak a reply sentence by sentence and highlight the sentence being
 * spoken, so the words can be followed while they are heard.
 *
 * The hard part is alignment. What is SPOKEN is not always what is
 * SHOWN — speech.speakable() turns "$32" into "thirty-two dollars" so
 * the engine pronounces it properly. So the page splits the RENDERED
 * text (what the reader actually sees) and Python returns the spoken
 * form of each piece plus a `matches` flag. Sentence highlighting is
 * therefore always exact, because both sides index the same array. Word
 * highlighting relies on the engine's character offsets, which only
 * point into the displayed string when `matches` is true — otherwise it
 * is skipped rather than lighting up the wrong word.
 *
 * Sentences are tracked by INDEX, not by element: a sentence can run
 * across inline markup ("a **bold** word.") and so may be several spans.
 * Every span of one sentence carries the same index.
 */

const SENTENCE_END = /[.!?…]["')\]]*\s*/;

let readIndex = -1;
let readSpans = [];
let readQueue = [];
let readTurn = null;

function splitSentences(text) {
  const out = [];
  let rest = text;
  while (rest) {
    const m = rest.match(SENTENCE_END);
    if (!m) { out.push({ text: rest, ends: false }); break; }
    const cut = m.index + m[0].length;
    out.push({ text: rest.slice(0, cut), ends: true });
    rest = rest.slice(cut);
  }
  return out;
}

function wrapSentences(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (n.nodeValue.trim()) nodes.push(n);
  }

  const spans = [];
  const texts = [];
  let index = 0;

  for (const node of nodes) {
    if (node.parentElement && node.parentElement.closest('pre')) continue;
    const frag = document.createDocumentFragment();
    for (const piece of splitSentences(node.nodeValue)) {
      const span = document.createElement('span');
      span.className = 's';
      span.dataset.i = String(index);
      span.textContent = piece.text;
      frag.appendChild(span);
      if (!spans[index]) spans[index] = [];
      spans[index].push(span);
      texts[index] = (texts[index] || '') + piece.text;
      if (piece.ends) index += 1;
    }
    node.parentNode.replaceChild(frag, node);
  }
  return { spans: spans, texts: texts.map((t) => (t || '').trim()) };
}

function clearHighlight() {
  document.querySelectorAll('.s.reading').forEach((e) => e.classList.remove('reading'));
  document.querySelectorAll('.w.now').forEach((e) => e.classList.remove('now'));
}

function highlight(i) {
  clearHighlight();
  const group = readSpans[i];
  if (!group || !group.length) return;
  group.forEach((e) => e.classList.add('reading'));
  const first = group[0];
  const box = first.getBoundingClientRect();
  const view = log.getBoundingClientRect();
  if (box.top < view.top || box.bottom > view.bottom) {
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    first.scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' });
  }
}

function wordify(i) {
  const group = readSpans[i];
  if (!group || !group.length || group[0].querySelector('.w')) return;
  for (const span of group) {
    const frag = document.createDocumentFragment();
    for (const part of span.textContent.split(/(\s+)/)) {
      if (!part) continue;
      if (/^\s+$/.test(part)) {
        frag.appendChild(document.createTextNode(part));
        continue;
      }
      const w = document.createElement('span');
      w.className = 'w';
      w.textContent = part;
      frag.appendChild(w);
    }
    span.textContent = '';
    span.appendChild(frag);
  }
}

function highlightWord(i, charIndex) {
  const group = readSpans[i];
  if (!group) return;
  const words = [];
  group.forEach((s) => s.querySelectorAll('.w').forEach((w) => words.push(w)));
  if (!words.length) return;

  const sentence = (readQueue[i] && readQueue[i].text) || '';
  let seen = 0;
  let target = words[0];
  for (const w of words) {
    const start = sentence.indexOf(w.textContent, seen);
    if (start < 0) continue;
    seen = start + w.textContent.length;
    if (start <= charIndex && charIndex < seen) { target = w; break; }
  }
  document.querySelectorAll('.w.now').forEach((e) => e.classList.remove('now'));
  target.classList.add('now');
}

function stopReading() {
  if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  speaking = false;
  readIndex = -1;
  clearHighlight();
  if (readTurn) readTurn.classList.remove('reading-on');
  setRead(false);
}

function speakFrom(start) {
  if (!('speechSynthesis' in window) || !readQueue.length) return;
  window.speechSynthesis.cancel();
  speaking = true;
  setRead(true);
  if (readTurn) readTurn.classList.add('reading-on');

  let last = -1;
  for (let i = start; i < readQueue.length; i += 1) {
    if (readQueue[i] && readQueue[i].spoken.trim()) last = i;
  }
  if (last < 0) { stopReading(); return; }

  for (let i = start; i < readQueue.length; i += 1) {
    const item = readQueue[i];
    if (!item || !item.spoken.trim()) continue;
    const utter = new SpeechSynthesisUtterance(item.spoken);
    utter.onstart = () => {
      readIndex = i;
      highlight(i);
      if (item.matches) wordify(i);
    };
    if (item.matches) {
      utter.onboundary = (e) => highlightWord(i, e.charIndex || 0);
    }
    if (i === last) utter.onend = () => stopReading();
    utter.onerror = () => stopReading();
    window.speechSynthesis.speak(utter);
  }
}

function speakPlain(text) {
  if (!text || !('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.onstart = () => { speaking = true; setRead(true); };
  utter.onend = () => { speaking = false; setRead(false); };
  utter.onerror = () => { speaking = false; setRead(false); };
  window.speechSynthesis.speak(utter);
}

async function readAlong(turnEl, fallbackText) {
  if (!('speechSynthesis' in window)) {
    note('This window has no speech engine.', true);
    return;
  }
  const body = turnEl && turnEl.querySelector('.body');
  if (!body) { speakPlain(fallbackText); return; }

  readTurn = turnEl;
  const wrapped = wrapSentences(body);
  readSpans = wrapped.spans;
  const texts = wrapped.texts;
  if (!texts.filter((t) => t).length) { speakPlain(fallbackText); return; }

  let spokenList = null;
  try {
    const r = await api.speakable_batch(texts.map((t) => t || ''));
    if (r && r.ok) spokenList = r.sentences;
  } catch (e) {
    spokenList = null;   /* read it as written rather than not at all */
  }

  readQueue = texts.map((t, i) => ({
    text: t || '',
    spoken: (spokenList && spokenList[i] && spokenList[i].spoken) || t || '',
    matches: spokenList ? !!(spokenList[i] && spokenList[i].matches) : true
  }));

  /* Click any sentence to hear it again from there. */
  readSpans.forEach((group) => {
    if (!group) return;
    group.forEach((span) => {
      span.addEventListener('click', () => speakFrom(Number(span.dataset.i)));
    });
  });

  speakFrom(0);
}

function setRead(on) {
  const b = $('read');
  b.setAttribute('aria-pressed', on ? 'true' : 'false');
  b.innerHTML = on ? '<span aria-hidden="true">■</span> Stop'
                   : '<span aria-hidden="true">🔊</span> Read';
}

/* ---------- sending --------------------------------------------------- */

async function send() {
  const box = $('msg');
  const text = box.value.trim();
  if (!text || !api) return;

  turn('You', markdown(text), 'me');
  box.value = '';
  box.style.height = 'auto';

  /* A slash command is an instruction to the console, not a question
     for the model. Asked of Python first: the grammar lives in
     strata_tools/commands.py, and a copy here would be a second
     grammar. handled:false means "ordinary message, carry on". */
  if (text.startsWith('/')) {
    try {
      const c = await api.run_command(text);
      if (c && c.handled) {
        if (c.clearLog) {
          stopReading();
          log.innerHTML = '';
          lastReply = ''; lastSpeakable = ''; lastTurn = null;
        }
        if (c.message) {
          if (c.markdown) lastTurn = turn('Strata', markdown(c.message));
          else note(c.message, !!c.bad);
        }
        if (c.status) $('status').textContent = c.status;
        if (c.zone) setZone(c.zone);
        box.focus();
        return;
      }
    } catch (e) {
      note('Command failed: ' + e, true);
      return;
    }
  }

  const pending = turn('Strata', '<p class="thinking">thinking…</p>');
  $('send').disabled = true;

  /* Which sources this turn will use is decided in Python -- typing
     "look this up" counts as ticking the box, and that rule lives in
     strata_tools/context_sources.py so both shells obey one copy of
     it. Asking costs one bridge call and saves a second rule here. */
  try {
    const b = await api.busy_for(text);
    $('status').textContent = b.label;
    const think = pending.querySelector('.thinking');
    if (think) think.textContent = b.label;
  } catch (e) { /* a missing label is cosmetic; the turn still runs */ }

  try {
    const r = await api.send(text);
    if (!r.ok) {
      pending.remove();
      note(r.error || 'The engine returned nothing.', true);
      return;
    }
    pending.querySelector('.body').innerHTML = markdown(r.reply);
    /* Say what was actually read. Without this the owner cannot tell a
       real search from the model answering out of its own head, which
       is the difference between grounded and confident-and-wrong. */
    if (r.used && r.used.length) {
      const src = document.createElement('p');
      src.className = 'used';
      src.textContent = 'Read: ' + r.used.join(' · ');
      pending.appendChild(src);
    }
    lastReply = r.reply;
    lastSpeakable = r.speakable || r.reply;
    lastTurn = pending;
    $('status').textContent = r.status;
    if ($('autoread').checked) readAlong(pending, lastSpeakable);
  } catch (e) {
    pending.remove();
    note('Bridge error: ' + e, true);
  } finally {
    $('send').disabled = false;
    log.scrollTop = log.scrollHeight;
  }
}

/* ---------- dictation -------------------------------------------------- */

async function toggleMic() {
  if (!api) return;
  const b = $('mic');
  if (!recording) {
    const r = await api.start_recording();
    if (!r.ok) { note(r.error, true); return; }
    recording = true;
    b.setAttribute('aria-pressed', 'true');
    b.innerHTML = '<span aria-hidden="true">■</span> Stop';
    $('status').textContent = 'Listening — speak, then press Stop.';
  } else {
    recording = false;
    b.setAttribute('aria-pressed', 'false');
    b.innerHTML = '<span aria-hidden="true">🎤</span> Speak';
    $('status').textContent = 'Transcribing…';
    const r = await api.stop_recording($('tier').value);
    if (!r.ok) { note(r.error, true); $('status').textContent = ''; return; }
    if (r.note) note(r.note);
    const box = $('msg');
    box.value = (box.value ? box.value + ' ' : '') + r.text;
    box.focus();
    grow(box);
    $('status').textContent = '';
  }
}

function grow(box) {
  box.style.height = 'auto';
  box.style.height = Math.min(box.scrollHeight, window.innerHeight * 0.3) + 'px';
}

/* ---------- context sources -------------------------------------------- */

/* Render whichever file is currently attached. The page is told the
   name and the label only -- never the text, which can run to two
   million characters and has no business crossing the bridge twice. */
function showAttachment(att) {
  const out = $('attached');
  const off = $('detach');
  if (att && att.label) {
    out.textContent = att.label;
    out.title = att.label;
    off.hidden = false;
  } else {
    out.textContent = '';
    out.title = '';
    off.hidden = true;
  }
}

async function upload() {
  if (!api) return;
  $('upload').disabled = true;
  try {
    const r = await api.upload_document();
    if (r.cancelled) return;
    if (!r.ok) { note(r.error, true); return; }
    showAttachment(r.attachment);
    note(r.message);
  } catch (e) {
    note('Upload failed: ' + e, true);
  } finally {
    $('upload').disabled = false;
  }
}

/* Background work reports here. Two producers share the queue: the
   voice-model release watch and OneDrive indexing. Before this loop
   existed the bridge had a memory_note() method that no page called,
   so the release watch was reporting to nobody. */
async function pollNotes() {
  if (!api) return;
  try {
    const r = await api.poll_notes();
    (r.notes || []).forEach((n) => note(n));
  } catch (e) { /* a dropped poll is not worth a message */ }
}

/* ---------- wiring ----------------------------------------------------- */

function setZone(zone) {
  document.querySelectorAll('.mode').forEach((b) => {
    b.setAttribute('aria-checked', b.dataset.zone === zone ? 'true' : 'false');
  });
}

async function boot() {
  api = window.pywebview.api;
  const s = await api.bootstrap();

  document.documentElement.dataset.font = s.fontFamily || 'system';
  $('font').value = s.fontFamily || 'system';
  applySize(s.fontSize || 17);
  $('autoread').checked = !!s.autoread;
  setZone(s.zone);
  $('status').textContent = s.status;

  /* Source state lives on the bridge, so a reload finds the boxes and
     the attachment exactly as they were left. */
  const src = s.sources || {};
  $('src-web').checked = !!src.web;
  $('src-onedrive').checked = !!src.onedrive;
  showAttachment(s.attachment);

  turn('Strata', markdown(
    s.brain
      ? 'Web shell online — local model **' + s.model + '**.\n\n' +
        'Same engine as the desktop console: same database, same modes, ' +
        'same voice path. Press **Speak** to dictate, or just type.\n\n' +
        'While an answer is read aloud, the sentence being spoken is ' +
        'highlighted so you can follow along. Click any sentence to hear ' +
        'it again from there.\n\n' +
        'Tick **🌐 Web search** or **☁ OneDrive files**, or press ' +
        '**📎 Upload document**, and I will read those before answering ' +
        '— and keep reading them for as long as they stay switched on, ' +
        'so you can go on asking about the same material. Saying ' +
        '"look this up" works without touching the box.'
      : 'Web shell online — **template mode**.\n\nThe local model is not ' +
        'answering: ' + s.error + '\n\nResponses use the deterministic ' +
        'engine until it is ready.'
  ));

  $('send').disabled = false;
}

document.addEventListener('DOMContentLoaded', () => {
  $('composer').addEventListener('submit', (e) => { e.preventDefault(); send(); });

  const box = $('msg');
  box.addEventListener('input', () => grow(box));
  box.addEventListener('keydown', (e) => {
    /* Enter sends; Shift+Enter makes a new line. The desktop shell's
       single-line Entry could not hold more than one line at all. */
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });

  $('bigger').addEventListener('click', () => applySize(size + 2));
  $('smaller').addEventListener('click', () => applySize(size - 2));

  $('font').addEventListener('change', (e) => {
    document.documentElement.dataset.font = e.target.value;
    if (api) api.set_pref('web_font', e.target.value);
  });

  $('mic').addEventListener('click', toggleMic);

  $('src-web').addEventListener('change', async (e) => {
    if (!api) return;
    await api.set_source('web', e.target.checked);
    note(e.target.checked
      ? '🌐 Web search ON — I will search before answering, and cite what I read.'
      : '🌐 Web search off. Saying "look this up" still works for one message.');
  });

  $('src-onedrive').addEventListener('change', async (e) => {
    if (!api) return;
    /* Switching this on starts the index build; the note telling him
       so arrives through pollNotes, not from here. */
    await api.set_source('onedrive', e.target.checked);
    if (!e.target.checked) note('☁ OneDrive files off — your documents stay indexed.');
  });

  $('upload').addEventListener('click', upload);

  $('detach').addEventListener('click', async () => {
    if (!api) return;
    const r = await api.clear_attachment();
    showAttachment(null);
    if (r.message) note(r.message);
  });

  $('read').addEventListener('click', () => {
    if (speaking) { stopReading(); return; }
    if (!lastTurn) { note('Nothing to read yet — send a message first.'); return; }
    readAlong(lastTurn, lastSpeakable);
  });

  $('autoread').addEventListener('change', (e) => {
    if (api) api.set_pref('autoread', e.target.checked ? '1' : '0');
    note(e.target.checked
      ? 'Auto-read ON — answers will be spoken as they arrive, with the sentence highlighted.'
      : 'Auto-read off — use the Read button.');
  });

  $('clear').addEventListener('click', async () => {
    if (!api) return;
    stopReading();
    const r = await api.clear();
    log.innerHTML = '';
    lastReply = '';
    lastSpeakable = '';
    lastTurn = null;
    note(r.message);
    $('status').textContent = r.status;
    $('msg').focus();
  });

  $('help').addEventListener('click', async () => {
    /* The command list comes from Python so it cannot drift from the
       table that actually dispatches them. */
    let cmds = '';
    try {
      const c = await api.run_command('/help');
      if (c && c.message) cmds = '\n\n' + c.message;
    } catch (e) { /* the rest of Help is still worth showing */ }
    lastTurn = turn('Strata', markdown([
      '### Keyboard',
      '- **Tab** moves through every control — all of them, natively.',
      '- **Enter** sends. **Shift+Enter** starts a new line.',
      '- **Ctrl+L** clears the window and what the model recalls.',
      '- **Escape** stops reading.',
      '',
      '### Reading along',
      'While an answer is spoken, the current sentence is highlighted and',
      'the current word is underlined. Click any sentence to hear it again',
      'from that point. Tick **Auto** to have every answer read as it arrives.',
      '',
      '### Speaking punctuation while you dictate',
      'Say `period`, `comma`, `question mark`, `new line`, `new paragraph`,',
      '`open paren` / `close paren`, `cap <word>`, `all caps on` … `all caps off`.',
      'If the recogniser already heard the pause and punctuated it, the',
      'duplicate is cleaned up for you.'
    ].join('\n') + cmds));
  });

  document.querySelectorAll('.mode').forEach((b) => {
    b.addEventListener('click', async () => {
      if (!api) return;
      const r = await api.change_zone(b.dataset.zone);
      setZone(r.zone);
      note(r.message);
      $('status').textContent = r.status;
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key.toLowerCase() === 'l') {
      e.preventDefault();
      $('clear').click();
    }
    if (e.key === 'Escape' && speaking) { e.preventDefault(); stopReading(); }
  });

  /* Five seconds: slow enough to cost nothing, fast enough that "☁
     OneDrive ready" lands while he is still looking at the window. */
  setInterval(pollNotes, 5000);

  window.addEventListener('pywebviewready', boot);
  if (window.pywebview && window.pywebview.api) boot();
});
