/* ═══════════════════════════════════════════════════════════
   novel-downloader Web UI — 前端 JavaScript
   ═══════════════════════════════════════════════════════════ */

const INIT = window.__INIT__ || {};
let currentPlatform = INIT.platform || 'fanqie';
let _searchResults = [];
let _activeStreams = {};
let _taskPollTimer = null;
let _exportNovelId = null;

// Bootstrap modal instance
let _exportModal = null;

document.addEventListener('DOMContentLoaded', () => {
  _exportModal = new bootstrap.Modal(document.getElementById('export-modal'));
  loadTasks();
  _taskPollTimer = setInterval(loadTasks, 3000);
  fetchNovels();
});

// ══════════════════════════ 消息系统 ══════════════════════════
function showMessage(msg, type) {
  type = type || 'success'; // success | danger | warning | info
  const area = document.getElementById('message-area');
  const icon = { success:'check-circle', danger:'exclamation-triangle', warning:'exclamation-triangle', info:'info-circle' }[type] || 'info-circle';
  const div = document.createElement('div');
  div.className = `alert alert-${type} alert-dismissible fade show d-flex align-items-center`;
  div.innerHTML = `<i class="bi bi-${icon} me-2"></i> ${escapeHtml(msg)}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
  area.appendChild(div);
  setTimeout(() => {
    const bsAlert = bootstrap.Alert.getOrCreateInstance(div);
    if (bsAlert) bsAlert.close();
    else div.remove();
  }, 5000);
}

function showError(msg) { showMessage(msg, 'danger'); }
function showWarning(msg) { showMessage(msg, 'warning'); }

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// ══════════════════════════ 面板切换 ══════════════════════════
function switchPanel(name) {
  document.querySelectorAll('.sidebar .nav-link').forEach(b => {
    b.classList.toggle('active', b.dataset.panel === name);
  });
  document.querySelectorAll('.panel').forEach(p => {
    p.classList.toggle('hidden', p.id !== 'panel-' + name);
  });
  if (name === 'library') fetchNovels();
  else if (name === 'tasks') loadTasks();
}

// ══════════════════════════ SSE 进度 ══════════════════════════
function subscribeProgress(taskId) {
  if (_activeStreams[taskId]) _activeStreams[taskId].close();
  const es = new EventSource('/progress/' + taskId);
  _activeStreams[taskId] = es;

  es.onmessage = e => {
    try {
      const d = JSON.parse(e.data);
      if (d.type === 'error') showError(d.text);
      else if (d.type === 'done') showMessage(d.text);
      if (d.type === 'progress') updateTaskProgress(taskId, d.downloaded || 0, d.total || 0);
      if (d.type === 'end' || d.type === 'done' || d.type === 'error') {
        es.close();
        delete _activeStreams[taskId];
        loadTasks();
        fetchNovels();
      }
    } catch (_) {}
  };
  es.onerror = () => { es.close(); delete _activeStreams[taskId]; loadTasks(); };
  return es;
}

// ══════════════════════════ 任务面板 ══════════════════════════
async function loadTasks() {
  try {
    const r = await fetch('/api/tasks');
    const data = await r.json();
    renderTasks(data.tasks || []);
    updateTaskBadge(data.tasks ? data.tasks.length : 0);
  } catch (_) {}
}

function updateTaskBadge(count) {
  const badge = document.getElementById('task-count');
  if (!badge) return;
  badge.textContent = count;
  badge.classList.toggle('hidden', count === 0);
}

function renderTasks(tasks) {
  const container = document.getElementById('task-list');
  if (!container) return;
  if (!tasks.length) {
    container.innerHTML = '<div class="text-muted text-center py-4">暂无运行中的任务</div>';
    return;
  }

  let html = '';
  tasks.forEach(t => {
    const pct = t.total > 0 ? Math.round(t.downloaded / t.total * 100) : 0;
    const barCls = t.status === 'done' ? 'bg-success' : t.status === 'error' ? 'bg-danger' : '';
    const badgeCls = { pending:'bg-secondary', downloading:'bg-primary', paused:'bg-warning text-dark', done:'bg-success', error:'bg-danger', cancelled:'bg-secondary' }[t.status] || 'bg-secondary';
    const label = { pending:'等待中', downloading:'下载中', paused:'已暂停', done:'已完成', error:'出错', cancelled:'已取消' }[t.status] || t.status;

    html += `<div class="task-item">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <span><strong>${escapeHtml(t.title || '未知小说')}</strong></span>
        <span class="badge ${badgeCls}">${label}</span>
        <span class="ms-2 text-muted small">${t.downloaded}/${t.total} 章</span>
      </div>
      <div class="progress" style="height:6px">
        <div class="progress-bar progress-bar-striped progress-bar-animated ${barCls}"
             style="width:${pct}%"></div>
      </div>`;
    if (t.message) {
      html += `<small class="text-muted">${escapeHtml(t.message)}</small>`;
    }
    html += '</div>';
  });

  // SSE for active tasks
  tasks.forEach(t => {
    if ((t.status === 'downloading' || t.status === 'pending') && !_activeStreams[t.task_id]) {
      subscribeProgress(t.task_id);
    }
  });

  container.innerHTML = html;
}

function updateTaskProgress(taskId, downloaded, total) {
  const items = document.querySelectorAll('.task-item');
  // Simplest approach: reload all tasks from API
  loadTasks();
}

async function cancelTask(taskId) {
  try {
    await fetch('/api/tasks/' + taskId + '/cancel', { method: 'POST' });
    showMessage('任务已取消', 'warning');
    if (_activeStreams[taskId]) { _activeStreams[taskId].close(); delete _activeStreams[taskId]; }
    loadTasks();
    fetchNovels();
  } catch (e) { showError('取消失败: ' + e); }
}

// ══════════════════════════ 下载面板 ══════════════════════════
function doSearchOrDownload() {
  const q = document.getElementById('search-input').value.trim();
  if (!q) { showWarning('请输入关键词或链接'); return; }
  if (/^https?:\/\//i.test(q)) downloadUrl(q);
  else doSearch(0);
}

async function doSearch(page) {
  const q = document.getElementById('search-input').value.trim();
  if (!q) return;
  const container = document.getElementById('search-results');
  container.innerHTML = '<div class="text-muted text-center py-3"><div class="spinner-border spinner-border-sm me-2"></div>搜索中...</div>';

  try {
    const r = await fetch('/search?q=' + encodeURIComponent(q) + '&platform=' + currentPlatform + '&page=' + (page || 0));
    const d = await r.json();
    if (d.error) { showError('搜索失败: ' + d.error); container.innerHTML = ''; return; }
    if (!d.results || d.results.length === 0) {
      container.innerHTML = '<div class="text-muted text-center py-3">未找到结果</div>';
      return;
    }
    _searchResults = d.results;
    let html = '';
    d.results.forEach((item, i) => {
      const author = (item.author || '').length > 20 ? item.author.slice(0, 20) + '…' : item.author;
      html += `<div class="search-result-item">
        <div><span class="sr-title">${i + 1}. ${escapeHtml(item.title)}</span>
          <span class="sr-meta">— ${escapeHtml(author)}</span></div>
        <button class="btn btn-sm btn-success" onclick="searchDownload(${i})">
          <i class="bi bi-download"></i> 下载</button>
      </div>`;
    });
    container.innerHTML = html;
    showMessage(`找到 ${d.results.length} 个结果`);
  } catch (e) {
    showError('搜索异常: ' + e);
    container.innerHTML = '';
  }
}

function searchDownload(idx) {
  const item = _searchResults[idx];
  if (!item || !item.url) { showWarning('未获取到有效链接'); return; }
  downloadUrl(item.url);
}

function downloadUrl(url) {
  const tid = 'task-' + Date.now();
  subscribeProgress(tid);
  fetch('/download?url=' + encodeURIComponent(url) + '&task_id=' + tid, { method: 'POST' })
    .then(async r => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        showError('启动失败: ' + (err.error || r.statusText));
      } else {
        showMessage('下载任务已创建');
        switchPanel('tasks');
      }
    })
    .catch(e => showError('启动失败: ' + e));
}

async function switchPlatform() {
  const plat = document.getElementById('platform-select').value;
  try {
    const r = await fetch('/switch_platform?platform=' + plat, { method: 'POST' });
    const d = await r.json();
    d.status === 'ok' ? showMessage('已切换到: ' + plat) : showError('切换失败');
    if (d.status === 'ok') currentPlatform = plat;
  } catch (e) { showError('切换异常: ' + e); }
}

async function doLogin() {
  const tid = 'task-' + Date.now();
  subscribeProgress(tid);
  try {
    await fetch('/login?task_id=' + tid + '&platform=' + currentPlatform, { method: 'POST' });
    showMessage('登录请求已发送，请在服务器桌面查看浏览器', 'info');
  } catch (e) { showError('登录失败: ' + e); }
}

// ══════════════════════════ 已下载面板 ══════════════════════════
async function fetchNovels() {
  const container = document.getElementById('novel-groups');
  if (!container) return;
  try {
    const r = await fetch('/api/novels');
    const novels = await r.json();
    const badge = document.getElementById('novel-count-badge');
    if (badge) badge.textContent = novels.length;

    if (!novels.length) {
      container.innerHTML = '<div class="text-muted text-center py-4">暂无已存储小说</div>';
      return;
    }

    const groups = {};
    novels.forEach(n => { const g = n.group || '默认'; if (!groups[g]) groups[g] = []; groups[g].push(n); });

    let html = '';
    for (const [gname, items] of Object.entries(groups)) {
      html += `<div class="card novel-table-wrap" data-group="${escapeHtml(gname)}">
        <div class="card-header table-group-header" onclick="toggleGroup(this)" style="cursor:pointer">
          <span><i class="bi bi-folder2"></i> ${escapeHtml(gname)}</span>
          <span class="group-arrow"><i class="bi bi-chevron-down"></i></span>
        </div>
        <div class="table-group-body">
          <table class="novel-table table"><thead><tr>
            <th>书名</th><th>作者</th><th>进度</th><th>标签</th><th style="width:140px">操作</th>
          </tr></thead><tbody>`;
      items.forEach(n => {
        const tags = (n.tags || []).slice(0, 3).map(t => `<span class="badge bg-light text-dark me-1">${escapeHtml(t)}</span>`).join('');
        html += `<tr data-novel-id="${n.id}">
          <td><strong>${escapeHtml(n.title)}</strong></td>
          <td>${escapeHtml(n.author)}</td>
          <td class="novel-progress" data-id="${n.id}">
            <span class="fw-bold">${n.downloaded}</span><span class="text-muted"> / ${n.serial || '?'}</span>
          </td>
          <td>${tags}</td>
          <td class="actions-cell">
            <button class="btn btn-sm btn-outline-success" onclick="updateNovel('${n.id}')"><i class="bi bi-arrow-repeat"></i></button>
            <button class="btn btn-sm btn-outline-primary" onclick="openExportModal('${n.id}','${escapeHtml(n.title).replace(/'/g,"\\'")}')"><i class="bi bi-download"></i></button>
          </td></tr>`;
      });
      html += '</tbody></table></div></div>';

      // Async chapter counts
      items.forEach(n => { setTimeout(() => lazyLoadChapterCount(n.id), 100); });
    }
    container.innerHTML = html;
  } catch (e) { showError('加载小说列表失败: ' + e); }
}

async function lazyLoadChapterCount(novelId) {
  try {
    const r = await fetch('/api/novels/' + novelId + '/chapters/count');
    const d = await r.json();
    const cell = document.querySelector(`.novel-progress[data-id="${novelId}"]`);
    if (cell) {
      cell.innerHTML = `<span class="fw-bold">${d.downloaded}</span><span class="text-muted"> / ${d.total || '?'}</span>`;
    }
  } catch (_) {}
}

function toggleGroup(header) {
  const body = header.nextElementSibling;
  header.classList.toggle('collapsed');
  body.classList.toggle('hidden');
}

async function updateNovel(novelId) {
  const tid = 'task-' + Date.now();
  subscribeProgress(tid);
  try {
    await fetch('/update/' + novelId + '?task_id=' + tid, { method: 'POST' });
    showMessage('更新任务已创建');
    switchPanel('tasks');
  } catch (e) { showError('更新失败: ' + e); }
}

async function doUpdateAll() {
  const tid = 'task-' + Date.now();
  subscribeProgress(tid);
  try {
    await fetch('/update_all?task_id=' + tid, { method: 'POST' });
    showMessage('批量更新已开始');
    switchPanel('tasks');
  } catch (e) { showError('更新失败: ' + e); }
}

// ══════════════════════════ 导出 ══════════════════════════
function openExportModal(novelId, title) {
  _exportNovelId = novelId;
  document.getElementById('export-modal-title').textContent = '导出: ' + title;
  document.getElementById('export-modal-confirm').onclick = doExportDownload;
  _exportModal.show();
}

function closeExportModal() {
  _exportModal.hide();
  _exportNovelId = null;
}

async function doExportDownload() {
  if (!_exportNovelId) return;
  const fmts = [];
  document.querySelectorAll('input[name="modal-export-fmt"]:checked').forEach(cb => fmts.push(cb.value));
  if (!fmts.length) { showWarning('请至少选择一种格式'); return; }

  showMessage('正在导出，请稍候...', 'info');
  _exportModal.hide();

  try {
    const r = await fetch('/api/export/' + _exportNovelId + '/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'fmts=' + fmts.join(','),
    });
    const d = await r.json();
    if (d.status === 'ok') {
      showMessage('✅ 已导出到 ' + d.exported_to);
    } else {
      showError('导出失败: ' + (d.error || ''));
    }
  } catch (e) { showError('导出失败: ' + e); }
}

// ══════════════════════════ 设置 ══════════════════════════
async function saveAllSettings() {
  const main = {
    mode: document.getElementById('set-mode').value,
    group: document.getElementById('set-group').value.trim(),
    max_workers: document.getElementById('set-max-workers').value,
  };
  const sitePlatform = document.getElementById('set-site-platform').value;
  const site = { platform: sitePlatform };
  // 读取内联站点配置
  const timeoutEl = document.getElementById('site-browser-timeout');
  const retryEl = document.getElementById('site-browser-retry');
  const delayEl = document.getElementById('site-browser-delay');
  const headlessEl = document.getElementById('site-browser-headless');
  if (timeoutEl || retryEl || delayEl) {
    site.browser = {};
    if (timeoutEl) site.browser.timeout = parseInt(timeoutEl.value) || 30;
    if (retryEl) site.browser.retry_times = parseInt(retryEl.value) || 3;
    if (delayEl) {
      const parts = delayEl.value.split(',').map(s => parseFloat(s.trim()));
      site.browser.delay = parts.length >= 2 ? [parts[0], parts[1]] : [3, 5];
    }
    if (headlessEl) site.browser.headless = headlessEl.checked;
  }
  const exports = {};
  document.querySelectorAll('.export-fmt-toggle').forEach(cb => {
    const fmt = cb.dataset.fmt;
    const pathInput = document.querySelector(`.export-fmt-path[data-fmt="${fmt}"]`);
    exports[fmt] = { enabled: cb.checked, output_path: pathInput ? pathInput.value : '' };
  });

  try {
    const r = await fetch('/api/settings/save_all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ main, site, exports }),
    });
    const d = await r.json();
    d.status === 'ok' ? showMessage('💾 全部配置已保存') : showError('保存失败: ' + (d.error || ''));
  } catch (e) { showError('保存失败: ' + e); }
}

function toggleSiteConfig() {
  const header = document.querySelector('#site-config-card .card-header');
  const body = document.getElementById('site-config-body');
  header.classList.toggle('collapsed');
  body.classList.toggle('hidden');
}

const _defaultSiteConfig = {
  browser: { timeout: 30, retry_times: 3, delay: [3, 5], headless: false }
};

function _applySiteConfig(cfg) {
  const bc = cfg.browser || {};
  const el = id => document.getElementById(id);
  if (el('site-browser-timeout')) el('site-browser-timeout').value = bc.timeout ?? 30;
  if (el('site-browser-retry')) el('site-browser-retry').value = bc.retry_times ?? 3;
  if (el('site-browser-delay')) {
    const d = bc.delay;
    el('site-browser-delay').value = Array.isArray(d) ? d.join(',') : (d ?? '3,5');
  }
  if (el('site-browser-headless')) el('site-browser-headless').checked = !!bc.headless;
}

async function onSitePlatformChange() {
  const platform = document.getElementById('set-site-platform').value;
  try {
    const r = await fetch('/switch_platform?platform=' + platform, { method: 'POST' });
    const d = await r.json();
    if (d.status === 'ok') {
      currentPlatform = platform;
      document.getElementById('site-config-label').textContent =
        document.getElementById('set-site-platform').selectedOptions[0].textContent;
      // 刷新表单字段
      _applySiteConfig(d.site_config || {});
      showMessage('已切换到: ' + platform, 'info');
    }
  } catch (e) { showError('切换失败: ' + e); }
}