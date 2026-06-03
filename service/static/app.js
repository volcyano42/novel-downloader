/* novel-downloader Web UI — 前端 JavaScript */

let currentPlatform = 'fanqie';
let _searchQ = '';

// ── Tab 切换 ─────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('hidden', p.id !== 'tab-' + name));
  if (name === 'library') fetchNovels();
  else if (name === 'export') fetchExportDirs();
}

// ── 日志 ──────────────────────────────────────
function log(msg, type) {
  const el = document.getElementById('log');
  if (!el) return;
  const d = document.createElement('div');
  d.className = type || 'info';
  d.textContent = msg;
  el.appendChild(d);
  el.scrollTop = el.scrollHeight;
}
function clearLog() {
  const el = document.getElementById('log');
  if (el) el.innerHTML = '';
}

// ── SSE 进度监听 ──────────────────────────────
function subscribeProgress(tid, onEnd) {
  const es = new EventSource('/progress/' + tid);
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    log(d.text, d.type === 'error' ? 'error' : d.type === 'done' ? 'done' : 'info');
    if (d.type === 'end') { es.close(); if (onEnd) onEnd(d.status); }
  };
  es.onerror = () => { es.close(); log('进度连接断开', 'error'); };
  return es;
}

// ── 通用操作（POST + SSE）─────────────────────
function doAction(action, onEnd) {
  const tid = 'task-' + Date.now();
  subscribeProgress(tid, onEnd);
  // update_xxx → /update/xxx, export_xxx → /export/xxx
  const idx = action.lastIndexOf('_');
  const route = idx > 0 && action.slice(idx) !== '_all'
    ? '/' + action.slice(0, idx) + '/' + action.slice(idx + 1)
    : '/' + action;
  fetch(route + '?task_id=' + tid, { method: 'POST' })
    .catch(e => { log('操作失败: ' + e, 'error'); });
}

// ── 平台切换 ──────────────────────────────────
function switchPlatform() {
  const sel = document.getElementById('platform-select');
  const plat = sel.value;
  fetch('/switch_platform?platform=' + plat + '&task_id=switch-' + Date.now(), { method: 'POST' })
    .then(r => r.json())
    .then(d => {
      if (d.status === 'ok') {
        currentPlatform = plat;
        log('✓ 已切换到: ' + plat, 'done');
      } else {
        log('切换失败: ' + (d.error || ''), 'error');
      }
    })
    .catch(e => log('切换异常: ' + e, 'error'));
}

// ── 搜索 ──────────────────────────────────────
async function doSearch(page) {
  const q = document.getElementById('search-input').value.trim();
  if (!q) { log('请输入搜索关键词', 'error'); return; }
  log('搜索中: ' + q, 'info');
  _searchQ = q;
  const p = page || 0;
  try {
    const r = await fetch('/search?q=' + encodeURIComponent(q) + '&platform=' + currentPlatform + '&page=' + p);
    const d = await r.json();
    const container = document.getElementById('search-results');
    if (d.error) { log('搜索失败: ' + d.error, 'error'); return; }
    if (!d.results || d.results.length === 0) { log('未找到结果', 'error'); return; }
    log('找到 ' + d.results.length + ' 个结果', 'done');
    let html = '';
    d.results.forEach((item, i) => {
      html += '<div class="list-item">'
           + '<div><span class="title">' + (i + 1) + '. ' + item.title + '</span>'
           + '<span class="meta"> — ' + item.author + '</span></div>'
           + '<button class="btn-sm btn-success" onclick="searchDownload(' + i + ')">下载</button></div>';
    });
    container.innerHTML = html;
  } catch (e) { log('搜索异常: ' + e, 'error'); }
}

async function searchDownload(idx) {
  if (!_searchQ) { log('请先搜索', 'error'); return; }
  log('正在获取下载链接...', 'info');
  try {
    const r = await fetch('/search?q=' + encodeURIComponent(_searchQ) + '&platform=' + currentPlatform + '&choice=' + idx);
    const d = await r.json();
    if (d.error) { log('获取链接失败: ' + d.error, 'error'); return; }
    if (!d.url) { log('未获取到有效链接', 'error'); return; }
    downloadUrl(d.url);
  } catch (e) { log('获取链接异常: ' + e, 'error'); }
}

// ── 直接下载 ──────────────────────────────────
function doDirectDownload() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) { log('请输入链接', 'error'); return; }
  downloadUrl(url);
}

function downloadUrl(url) {
  const tid = 'task-' + Date.now();
  subscribeProgress(tid, () => fetchNovels());
  fetch('/download?url=' + encodeURIComponent(url) + '&task_id=' + tid, { method: 'POST' })
    .then(async r => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        log('启动失败: ' + (err.error || r.statusText), 'error');
      }
    })
    .catch(e => { log('启动失败: ' + e, 'error'); });
}

// ── 已存储小说 ────────────────────────────────
async function fetchNovels() {
  try {
    const r = await fetch('/api/novels');
    const novels = await r.json();
    const list = document.getElementById('novel-list');
    if (!list) return;
    if (!novels.length) {
      list.innerHTML = '<div class="text-muted">暂无已存储小说</div>';
    } else {
      let html = '';
      novels.forEach(n => {
        const tags = (n.tags || []).slice(0, 3).map(t => '<span class="tag">' + t + '</span>').join('');
        html += '<div class="list-item">'
             + '<div><strong>' + n.title + '</strong> — ' + n.author + ' (' + n.downloaded + ' 章) ' + tags + '</div>'
             + '<div style="display:flex;gap:6px;">'
             + '<button class="btn-sm btn-success" onclick="doAction(\'update_' + n.id + '\',fetchNovels)">更新</button>'
             + '<button class="btn-sm" onclick="doAction(\'export_' + n.id + '\',fetchNovels)">导出</button></div></div>';
      });
      list.innerHTML = html;
    }
  } catch (e) { log('加载小说列表失败: ' + e, 'error'); }
}

// ── 重新导出 ──────────────────────────────────
async function fetchExportDirs() {
  try {
    const r = await fetch('/api/export_dirs');
    const dirs = await r.json();
    const sel = document.getElementById('export-dir');
    if (!sel) return;
    sel.innerHTML = '';
    (dirs.dirs || []).forEach(d => {
      const opt = document.createElement('option');
      opt.value = d;
      opt.textContent = d;
      sel.appendChild(opt);
    });
    // 添加自定义选项
    const custom = document.createElement('option');
    custom.value = '__custom__';
    custom.textContent = '自定义路径...';
    sel.appendChild(custom);
  } catch (e) { log('加载导出目录失败: ' + e, 'error'); }
}

function onExportDirChange() {
  const sel = document.getElementById('export-dir');
  const custom = document.getElementById('export-dir-custom');
  if (sel.value === '__custom__') {
    custom.classList.remove('hidden');
  } else {
    custom.classList.add('hidden');
    custom.value = sel.value;
  }
}

function doReExport() {
  const dirEl = document.getElementById('export-dir');
  let dir = dirEl.value;
  if (dir === '__custom__') {
    dir = document.getElementById('export-dir-custom').value.trim();
  }
  if (!dir && dir !== '') {
    log('请选择导出目录', 'error');
    return;
  }

  // 收集选中的格式
  const fmts = [];
  document.querySelectorAll('input[name="export-fmt"]:checked').forEach(cb => fmts.push(cb.value));
  if (!fmts.length) { log('请至少选择一种导出格式', 'error'); return; }

  const tid = 'task-' + Date.now();
  subscribeProgress(tid, () => { fetchNovels(); });
  fetch('/export_selected?task_id=' + tid + '&dir=' + encodeURIComponent(dir) + '&fmts=' + fmts.join(','), { method: 'POST' })
    .catch(e => log('启动导出失败: ' + e, 'error'));
}

// ── 登录 ──────────────────────────────────────
function doLogin() {
  const tid = 'task-' + Date.now();
  subscribeProgress(tid);
  fetch('/login?task_id=' + tid + '&platform=' + currentPlatform, { method: 'POST' })
    .catch(e => { log('登录失败: ' + e, 'error'); });
}

// ── 初始化 ────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  fetchNovels();
  const platSel = document.getElementById('platform-select');
  if (platSel) currentPlatform = platSel.value;
});
