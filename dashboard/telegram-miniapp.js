'use strict';

(function initTelegramMiniApp() {
  const root = document.documentElement;
  const isMini =
    root.classList.contains('tg-miniapp')
    || new URLSearchParams(location.search).has('miniapp')
    || sessionStorage.getItem('tg_miniapp') === '1';

  if (!isMini) return;

  root.classList.add('tg-miniapp');
  sessionStorage.setItem('tg_miniapp', '1');

  function loadSdk() {
    return new Promise((resolve) => {
      if (window.Telegram && window.Telegram.WebApp) {
        resolve(window.Telegram.WebApp);
        return;
      }
      const s = document.createElement('script');
      s.src = 'https://telegram.org/js/telegram-web-app.js';
      s.onload = () => resolve(window.Telegram && window.Telegram.WebApp);
      s.onerror = () => resolve(null);
      document.head.appendChild(s);
    });
  }

  function applyTelegramTheme(tg) {
    if (!tg) return;
    root.dataset.theme = tg.colorScheme === 'light' ? 'light' : 'dark';

    if (typeof renderKanban === 'function' && typeof state !== 'undefined' && state.tab === 'tasks') {
      renderKanban();
    }
    if (typeof renderCalendar === 'function' && typeof state !== 'undefined' && state.tab === 'calendar') {
      renderCalendar();
    }
  }

  function applyContentSafeArea(tg) {
    const inset = tg?.contentSafeAreaInset || {};
    const bottom = Math.max(Number(inset.bottom) || 0, 26);
    root.style.setProperty('--tg-chrome-bottom', `${bottom}px`);
  }

  function setupTelegramChrome(tg) {
    if (!tg) return;
    if (tg.MainButton && typeof tg.MainButton.hide === 'function') tg.MainButton.hide();
    if (tg.SecondaryButton && typeof tg.SecondaryButton.hide === 'function') tg.SecondaryButton.hide();
    if (tg.isFullscreen && typeof tg.exitFullscreen === 'function') {
      try { tg.exitFullscreen(); } catch (_) { /* unsupported */ }
    }
    applyContentSafeArea(tg);
    if (typeof tg.setBottomBarColor === 'function') {
      try { tg.setBottomBarColor('secondary_bg_color'); } catch (_) { /* unsupported */ }
    }
    ensureBottomChromeCover();
  }

  function ensureBottomChromeCover() {
    if (document.getElementById('tg-bottom-chrome-cover')) return;
    const cover = document.createElement('div');
    cover.id = 'tg-bottom-chrome-cover';
    cover.className = 'tg-bottom-chrome-cover';
    cover.setAttribute('aria-hidden', 'true');
    document.body.appendChild(cover);
  }

  function setVerticalSwipes(tg, enabled) {
    if (!tg) return;
    if (enabled && typeof tg.enableVerticalSwipes === 'function') {
      try { tg.enableVerticalSwipes(); } catch (_) { /* unsupported */ }
    } else if (!enabled && typeof tg.disableVerticalSwipes === 'function') {
      try { tg.disableVerticalSwipes(); } catch (_) { /* unsupported */ }
    }
  }

  function prepareTaskModalLayout() {
    const modal = document.querySelector('#kb-modal-overlay .kb-modal');
    if (!modal || modal.querySelector('.kb-modal-body')) return;
    const actions = modal.querySelector('.kb-modal-actions');
    if (!actions) return;
    const body = document.createElement('div');
    body.className = 'kb-modal-body';
    while (modal.firstChild && modal.firstChild !== actions) {
      body.appendChild(modal.firstChild);
    }
    modal.insertBefore(body, actions);
  }

  function prepareColModalLayout() {
    const modal = document.querySelector('#kb-col-modal-overlay .kb-modal');
    if (!modal || modal.querySelector('.kb-modal-body')) return;
    const actions = modal.querySelector('.kb-modal-actions');
    if (!actions) return;
    const body = document.createElement('div');
    body.className = 'kb-modal-body';
    while (modal.firstChild && modal.firstChild !== actions) {
      body.appendChild(modal.firstChild);
    }
    modal.insertBefore(body, actions);
  }

  function getKanbanLayout() {
    const v = localStorage.getItem('tg-kanban-layout');
    return v === 'board' ? 'board' : 'list';
  }

  function setKanbanLayout(layout) {
    const mode = layout === 'board' ? 'board' : 'list';
    localStorage.setItem('tg-kanban-layout', mode);
    root.classList.toggle('kb-layout-list', mode === 'list');
    root.classList.toggle('kb-layout-board', mode === 'board');
    const toggle = document.getElementById('tg-kb-layout-toggle');
    if (toggle) {
      toggle.querySelectorAll('button[data-layout]').forEach((b) => {
        b.classList.toggle('active', b.dataset.layout === mode);
      });
    }
    if (typeof renderKanban === 'function') renderKanban();
  }

  function buildKanbanLayoutToggle() {
    const header = document.querySelector('#view-tasks .board-header');
    if (!header || document.getElementById('tg-kb-layout-toggle')) return;
    const toggle = document.createElement('div');
    toggle.id = 'tg-kb-layout-toggle';
    toggle.className = 'kb-layout-toggle';
    toggle.setAttribute('aria-label', 'Вид Kanban');
    toggle.innerHTML = `
      <button type="button" data-layout="list" title="Список"><span aria-hidden="true">☰</span></button>
      <button type="button" data-layout="board" title="Колонки"><span aria-hidden="true">▦</span></button>
    `;
    toggle.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-layout]');
      if (!btn) return;
      setKanbanLayout(btn.dataset.layout);
    });
    const search = header.querySelector('#global-search');
    if (search) search.placeholder = 'Поиск задач…';
    header.insertBefore(toggle, header.firstChild);
    setKanbanLayout(getKanbanLayout());
  }

  function hookTaskModalScroll(tg) {
    prepareTaskModalLayout();
    prepareColModalLayout();

    if (typeof openTaskModal !== 'function') return;
    const orig = openTaskModal;
    window.openTaskModal = function (...args) {
      setVerticalSwipes(tg, true);
      orig(...args);
      requestAnimationFrame(() => {
        const body = document.querySelector('#kb-modal-overlay .kb-modal-body');
        if (body) body.scrollTop = 0;
      });
    };
    if (typeof closeTaskModal === 'function') {
      const origClose = closeTaskModal;
      window.closeTaskModal = function (...args) {
        const result = origClose(...args);
        setVerticalSwipes(tg, false);
        return result;
      };
    }
  }

  function buildBottomNav() {
    if (document.getElementById('tg-bottom-nav')) return;
    const nav = document.createElement('nav');
    nav.id = 'tg-bottom-nav';
    nav.className = 'tg-bottom-nav';
    nav.setAttribute('aria-label', 'Навигация');
    nav.innerHTML = `
      <button type="button" data-goto="tasks" class="active"><span class="ico">📋</span><span>Задачи</span></button>
      <button type="button" data-goto="calendar"><span class="ico">📅</span><span>Календарь</span></button>
      <button type="button" id="tg-btn-add"><span class="ico">➕</span><span>Новая</span></button>
    `;
    document.body.appendChild(nav);

    nav.addEventListener('click', (e) => {
      const add = e.target.closest('#tg-btn-add');
      if (add) {
        e.preventDefault();
        if (typeof openTaskModal === 'function') openTaskModal('todo');
        return;
      }
      const btn = e.target.closest('button[data-goto]');
      if (!btn) return;
      const tab = btn.dataset.goto;
      nav.querySelectorAll('button[data-goto]').forEach(b => b.classList.toggle('active', b === btn));
      if (typeof switchTab === 'function') switchTab(tab);
    });
  }

  async function authTelegram(tg) {
    if (!tg || !tg.initData) return;
    try {
      const r = await fetch(new URL('/api/telegram/auth', location.origin).pathname, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initData: tg.initData }),
      });
      if (!r.ok) return;
      const data = await r.json();
      if (data.user && data.user.id) {
        sessionStorage.setItem('tg_user_id', String(data.user.id));
      }
    } catch (_) { /* offline / local dev */ }
  }

  loadSdk().then((tg) => {
    if (!tg) {
      root.style.setProperty('--tg-chrome-bottom', '28px');
      ensureBottomChromeCover();
      buildBottomNav();
      buildKanbanLayoutToggle();
      hookTaskModalScroll(null);
      return;
    }
    tg.ready();
    setupTelegramChrome(tg);
    applyTelegramTheme(tg);
    setVerticalSwipes(tg, false);
    buildBottomNav();
    buildKanbanLayoutToggle();
    hookTaskModalScroll(tg);
    authTelegram(tg);

    tg.onEvent('themeChanged', () => {
      applyTelegramTheme(tg);
      setupTelegramChrome(tg);
    });
    tg.onEvent('viewportChanged', () => setupTelegramChrome(tg));
    tg.onEvent('contentSafeAreaChanged', () => applyContentSafeArea(tg));

    if (typeof switchTab === 'function') {
      const orig = switchTab;
      window.switchTab = function (tab) {
        orig(tab);
        const nav = document.getElementById('tg-bottom-nav');
        if (!nav) return;
        nav.querySelectorAll('button[data-goto]').forEach(b => {
          b.classList.toggle('active', b.dataset.goto === tab);
        });
      };
    }
  });
})();
