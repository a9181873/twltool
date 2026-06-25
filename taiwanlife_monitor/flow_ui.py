"""Local management UI for website inspection settings."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from taiwanlife_monitor.flow_editor import (
    FlowValidationError,
    delete_flow,
    delete_page,
    editor_payload,
    latest_report,
    load_config,
    save_config,
    update_general,
    update_link_crawl,
    update_search_check,
    update_ssl,
    upsert_flow,
    upsert_page,
)


HTML = r"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>巡檢管理後台</title>
  <style>
    :root {
      --bg: #f4f6f4;
      --panel: #ffffff;
      --subtle: #f8faf8;
      --line: #dce3dd;
      --text: #1f2724;
      --muted: #66736d;
      --accent: #2f6f62;
      --accent-dark: #285c52;
      --blue: #244a73;
      --danger: #a23c39;
      --warn: #986318;
      --shadow: 0 10px 28px rgba(24, 32, 28, .08);
      font-family: "Segoe UI", "Noto Sans TC", system-ui, sans-serif;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); font-size: 15px; letter-spacing: 0; }
    button, input, textarea, select { font: inherit; letter-spacing: 0; }
    button {
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      padding: 0 12px;
      cursor: pointer;
    }
    button:hover { border-color: #b8c4bd; background: #fbfcfa; }
    button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
    button.primary:hover { background: var(--accent-dark); }
    button.danger { color: var(--danger); border-color: #e4c0be; }
    button.small { min-height: 30px; padding: 0 9px; font-size: 13px; }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      padding: 9px 10px;
      outline: none;
    }
    textarea { min-height: 86px; resize: vertical; line-height: 1.5; }
    input:focus, textarea:focus, select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(47, 111, 98, .12); }
    label { display: block; color: var(--muted); font-size: 13px; margin-bottom: 6px; }
    .app { min-height: 100vh; display: grid; grid-template-columns: 260px 1fr; }
    .sidebar { background: #eef2ee; border-right: 1px solid var(--line); min-width: 0; }
    .brand { padding: 18px 18px 14px; border-bottom: 1px solid var(--line); }
    .brand h1 { margin: 0; font-size: 20px; }
    .brand p { margin: 6px 0 0; color: var(--muted); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .nav { padding: 12px; display: grid; gap: 6px; }
    .nav button { text-align: left; border-color: transparent; background: transparent; justify-content: flex-start; }
    .nav button.active { background: #fff; border-color: var(--line); box-shadow: var(--shadow); color: var(--accent); font-weight: 650; }
    .main { min-width: 0; }
    .topbar {
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 0 22px;
      background: rgba(255, 255, 255, .92);
      border-bottom: 1px solid var(--line);
      position: sticky;
      top: 0;
      z-index: 3;
    }
    .topbar h2 { margin: 0; font-size: 18px; }
    .status { color: var(--muted); font-size: 13px; min-height: 20px; }
    .status.ok { color: var(--accent); }
    .status.error { color: var(--danger); }
    .content { padding: 22px; max-width: 1280px; margin: 0 auto; }
    .section { display: none; }
    .section.active { display: block; }
    .toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      margin-bottom: 18px;
    }
    .panel-head { padding: 15px 18px; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .panel-head h3 { margin: 0; font-size: 15px; }
    .panel-body { padding: 18px; }
    .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }
    .span-3 { grid-column: span 3; }
    .span-4 { grid-column: span 4; }
    .span-5 { grid-column: span 5; }
    .span-6 { grid-column: span 6; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }
    .list { display: grid; gap: 8px; }
    .row {
      width: 100%;
      min-height: 54px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--subtle);
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      align-items: center;
      padding: 10px 12px;
      text-align: left;
    }
    .row.active { background: #fff; border-color: var(--accent); }
    .row-title { font-weight: 650; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
    .row-sub { color: var(--muted); font-size: 12px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; margin-top: 3px; }
    .badge { display: inline-flex; align-items: center; height: 24px; border-radius: 999px; border: 1px solid var(--line); padding: 0 8px; font-size: 12px; color: var(--muted); background: #fff; }
    .badge.on { color: #fff; background: var(--accent); border-color: var(--accent); }
    .badge.warn { color: var(--warn); border-color: #e6cfa3; }
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { border-bottom: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }
    .table th { color: var(--muted); font-size: 12px; font-weight: 600; }
    .check { display: inline-flex; align-items: center; gap: 8px; color: var(--text); font-size: 14px; }
    .check input { width: 18px; height: 18px; }
    .split { display: grid; grid-template-columns: 360px 1fr; gap: 18px; align-items: start; }
    .steps { display: grid; gap: 10px; }
    .step { border: 1px solid var(--line); border-radius: 8px; background: var(--subtle); overflow: hidden; }
    .step-head { display: grid; grid-template-columns: 40px 180px 1fr auto; gap: 10px; align-items: center; padding: 12px; background: #fff; border-bottom: 1px solid var(--line); }
    .step-no { color: var(--muted); font-weight: 700; text-align: center; }
    .step-body { padding: 14px; }
    .empty { border: 1px dashed #c7d0c9; border-radius: 8px; padding: 28px; color: var(--muted); text-align: center; }
    .hidden { display: none !important; }
    .token-box { max-width: 420px; margin: 14vh auto 0; background: #fff; border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); padding: 22px; display: grid; gap: 12px; }
    pre { white-space: pre-wrap; word-break: break-word; background: #111816; color: #dfe9e4; padding: 14px; border-radius: 8px; max-height: 360px; overflow: auto; }
    @media (max-width: 980px) {
      .app { grid-template-columns: 1fr; }
      .sidebar { border-right: 0; border-bottom: 1px solid var(--line); }
      .nav { grid-template-columns: repeat(2, 1fr); }
      .topbar { height: auto; padding: 14px; align-items: flex-start; flex-direction: column; }
      .content { padding: 14px; }
      .split { grid-template-columns: 1fr; }
      .span-3, .span-4, .span-5, .span-6, .span-8 { grid-column: span 12; }
      .step-head { grid-template-columns: 32px 1fr; }
      .step-head select, .step-head input, .step-head .toolbar { grid-column: 2; }
    }
  </style>
</head>
<body>
  <div id="tokenBox" class="token-box hidden">
    <h1>巡檢管理後台</h1>
    <label for="tokenInput">存取 token</label>
    <input id="tokenInput" type="password" autocomplete="current-password">
    <button class="primary" id="tokenButton">進入</button>
    <div id="tokenStatus" class="status"></div>
  </div>

  <div id="app" class="app hidden">
    <aside class="sidebar">
      <div class="brand">
        <h1>巡檢管理後台</h1>
        <p id="targetMeta"></p>
      </div>
      <nav class="nav">
        <button data-tab="overview" class="active">總覽</button>
        <button data-tab="pages">頁面巡檢</button>
        <button data-tab="search">搜尋檢查</button>
        <button data-tab="health">SSL / 連結</button>
        <button data-tab="flows">自訂流程</button>
        <button data-tab="results">結果 / 試跑</button>
      </nav>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <h2 id="viewTitle">總覽</h2>
          <div id="status" class="status"></div>
        </div>
        <div class="toolbar">
          <button id="reloadButton">重新整理</button>
          <button id="runButton" class="primary">一鍵試跑</button>
        </div>
      </header>
      <div class="content">
        <section id="overview" class="section active"></section>
        <section id="pages" class="section"></section>
        <section id="search" class="section"></section>
        <section id="health" class="section"></section>
        <section id="flows" class="section"></section>
        <section id="results" class="section"></section>
      </div>
    </main>
  </div>

  <script>
    const tabs = {
      overview: '總覽',
      pages: '頁面巡檢',
      search: '搜尋檢查',
      health: 'SSL / 連結',
      flows: '自訂流程',
      results: '結果 / 試跑'
    };
    const actionNames = {
      goto: '開啟頁面',
      click_first: '點擊物件',
      fill_first: '輸入欄位',
      press_first: '鍵盤操作',
      wait_for_load_state: '等待載入',
      wait: '固定等待',
      assert_any_text: '任一文字',
      assert_all_text: '全部文字',
      screenshot: '截圖',
      manual_note: '人工註記'
    };
    const state = {
      token: sessionStorage.getItem('inspectionUiToken') || '',
      data: null,
      selectedPage: null,
      selectedFlow: null,
      activeTab: 'overview'
    };
    const $ = (id) => document.getElementById(id);
    const lines = (value) => String(value || '').split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
    const lineText = (value) => Array.isArray(value) ? value.join('\n') : '';
    const html = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    const attr = html;
    const slug = (value) => String(value || 'item').trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 70) || 'item';

    function headers() {
      const h = { 'Content-Type': 'application/json' };
      if (state.token) h['X-Flow-Editor-Token'] = state.token;
      return h;
    }
    async function api(path, options = {}) {
      const res = await fetch(path, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
      const payload = await res.json().catch(() => ({}));
      if (res.status === 401) {
        showToken(payload.error || '需要 token');
        throw new Error(payload.error || '需要 token');
      }
      if (!res.ok) throw new Error(payload.error || `HTTP ${res.status}`);
      return payload;
    }
    function setStatus(text, type = '') {
      $('status').textContent = text || '';
      $('status').className = `status ${type}`;
    }
    function showToken(message = '') {
      $('app').classList.add('hidden');
      $('tokenBox').classList.remove('hidden');
      $('tokenStatus').textContent = message;
    }
    function showApp() {
      $('tokenBox').classList.add('hidden');
      $('app').classList.remove('hidden');
    }
    async function load() {
      try {
        state.data = await api('/api/config');
        if (!state.selectedPage) state.selectedPage = state.data.pages?.[0]?.id || null;
        if (!state.selectedFlow) state.selectedFlow = state.data.flows?.[0]?.id || null;
        $('targetMeta').textContent = [state.data.target_name, state.data.base_url].filter(Boolean).join(' · ');
        showApp();
        render();
        setStatus('已載入', 'ok');
      } catch (error) {
        if (!String(error.message).includes('token')) setStatus(error.message, 'error');
      }
    }
    function switchTab(tab) {
      state.activeTab = tab;
      document.querySelectorAll('.nav button').forEach((button) => button.classList.toggle('active', button.dataset.tab === tab));
      document.querySelectorAll('.section').forEach((section) => section.classList.toggle('active', section.id === tab));
      $('viewTitle').textContent = tabs[tab] || tab;
      render();
    }
    function render() {
      if (!state.data) return;
      renderOverview();
      renderPages();
      renderSearch();
      renderHealth();
      renderFlows();
      renderResults();
    }
    function renderOverview() {
      const inv = state.data.inventory || [];
      const latest = state.data.latest_report;
      $('overview').innerHTML = `
        <div class="panel">
          <div class="panel-head"><h3>目前巡檢項目</h3><button class="small" data-save-general>儲存基本設定</button></div>
          <div class="panel-body">
            <table class="table">
              <thead><tr><th>項目</th><th>狀態</th><th>數量</th><th>說明</th></tr></thead>
              <tbody>${inv.map((item) => `
                <tr>
                  <td>${html(item.name)}</td>
                  <td><span class="badge ${item.enabled ? 'on' : ''}">${item.enabled ? '啟用' : '停用'}</span></td>
                  <td>${html(item.count)}</td>
                  <td>${html(item.detail)}</td>
                </tr>`).join('')}</tbody>
            </table>
          </div>
        </div>
        <div class="panel">
          <div class="panel-head"><h3>基本設定</h3></div>
          <div class="panel-body grid">
            <div class="span-4"><label>目標名稱</label><input id="targetName" value="${attr(state.data.target_name || '')}"></div>
            <div class="span-5"><label>Base URL</label><input id="baseUrl" value="${attr(state.data.base_url || '')}"></div>
            <div class="span-3"><label>全域逾時秒數</label><input id="globalTimeout" type="number" value="${attr(state.data.global_timeout_seconds || 1800)}"></div>
            <div class="span-6"><label>允許主機</label><textarea id="allowedHosts">${html(lineText(state.data.allowed_hosts || []))}</textarea></div>
            <div class="span-6"><label>忽略 URL 關鍵字</label><textarea id="ignoreKeywords">${html(lineText(state.data.ignore_url_keywords || []))}</textarea></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-head"><h3>最近一次結果</h3></div>
          <div class="panel-body">
            ${latest ? `
              <div class="toolbar">
                <span class="badge ${latest.ok ? 'on' : 'warn'}">${latest.ok ? 'OK' : '有異常'}</span>
                <span>${html(latest.run_id || '')}</span>
                <span class="status">PASS ${html(latest.summary?.pass || 0)} / WARN ${html(latest.summary?.warn || 0)} / FAIL ${html(latest.summary?.fail || 0)}</span>
              </div>` : '<div class="empty">尚未產生 reports/latest.json</div>'}
          </div>
        </div>`;
    }
    function selectedPage() {
      return (state.data.pages || []).find((page) => page.id === state.selectedPage) || null;
    }
    function pageForm(page) {
      page = page || { id: '', name: '', path: '/', expected_title_contains: [], required_texts: [] };
      return `
        <div class="grid">
          <div class="span-4"><label>頁面 ID</label><input id="pageId" value="${attr(page.id || '')}"></div>
          <div class="span-4"><label>頁面名稱</label><input id="pageName" value="${attr(page.name || '')}"></div>
          <div class="span-4"><label>路徑</label><input id="pagePath" value="${attr(page.path || '/')}"></div>
          <div class="span-6"><label>Title 應包含</label><textarea id="pageTitleRules">${html(lineText(page.expected_title_contains || []))}</textarea></div>
          <div class="span-6"><label>頁面必要文字</label><textarea id="pageRequiredTexts">${html(lineText(page.required_texts || []))}</textarea></div>
          <div class="span-12"><label class="check"><input id="pageFullShot" type="checkbox" ${page.full_page_screenshot ? 'checked' : ''}> 整頁截圖</label></div>
        </div>`;
    }
    function renderPages() {
      const pages = state.data.pages || [];
      $('pages').innerHTML = `
        <div class="split">
          <div class="panel">
            <div class="panel-head"><h3>頁面清單</h3><button class="small primary" data-new-page>新增</button></div>
            <div class="panel-body list">
              ${pages.map((page) => `
                <button class="row ${page.id === state.selectedPage ? 'active' : ''}" data-select-page="${attr(page.id)}">
                  <span><span class="row-title">${html(page.name || page.id)}</span><span class="row-sub">${html(page.path || '')}</span></span>
                  <span class="badge">${html((page.required_texts || []).length)} 文字</span>
                </button>`).join('') || '<div class="empty">尚未設定頁面</div>'}
            </div>
          </div>
          <div class="panel">
            <div class="panel-head"><h3>頁面設定</h3><div class="toolbar"><button class="small danger" data-delete-page>刪除</button><button class="small primary" data-save-page>儲存</button></div></div>
            <div class="panel-body">${pageForm(selectedPage())}</div>
          </div>
        </div>`;
    }
    function renderSearch() {
      const cfg = state.data.search_check || {};
      $('search').innerHTML = `
        <div class="panel">
          <div class="panel-head"><h3>搜尋檢查</h3><button class="small primary" data-save-search>儲存</button></div>
          <div class="panel-body grid">
            <div class="span-4"><label>搜尋字</label><input id="searchQuery" value="${attr(cfg.query || '')}"></div>
            <div class="span-8"><label class="check"><input id="searchEnabled" type="checkbox" ${cfg.enabled ? 'checked' : ''}> 啟用搜尋檢查</label></div>
            <div class="span-6"><label>開啟搜尋物件 selectors</label><textarea id="searchTriggerSelectors">${html(lineText(cfg.trigger_selectors || []))}</textarea></div>
            <div class="span-6"><label>輸入框 selectors</label><textarea id="searchInputSelectors">${html(lineText(cfg.input_selectors || []))}</textarea></div>
            <div class="span-6"><label>送出 selectors</label><textarea id="searchSubmitSelectors">${html(lineText(cfg.submit_selectors || []))}</textarea></div>
            <div class="span-6"><label>成功時應出現任一文字</label><textarea id="searchExpectedText">${html(lineText(cfg.expected_any_text || []))}</textarea></div>
          </div>
        </div>`;
    }
    function renderHealth() {
      const ssl = state.data.ssl || {};
      const link = state.data.link_crawl || {};
      $('health').innerHTML = `
        <div class="panel">
          <div class="panel-head"><h3>SSL 憑證檢查</h3><button class="small primary" data-save-ssl>儲存 SSL</button></div>
          <div class="panel-body grid">
            <div class="span-3"><label class="check"><input id="sslEnabled" type="checkbox" ${ssl.enabled ? 'checked' : ''}> 啟用</label></div>
            <div class="span-3"><label>Port</label><input id="sslPort" type="number" value="${attr(ssl.port || 443)}"></div>
            <div class="span-3"><label>Warn 天數</label><input id="sslWarnDays" type="number" value="${attr(ssl.warn_days || 30)}"></div>
            <div class="span-3"><label>Fail 天數</label><input id="sslFailDays" type="number" value="${attr(ssl.fail_days || 7)}"></div>
            <div class="span-12"><label>指定主機，空白時使用 allowed_hosts</label><textarea id="sslHosts">${html(lineText(ssl.hosts || []))}</textarea></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-head"><h3>連結檢查</h3><button class="small primary" data-save-link>儲存連結</button></div>
          <div class="panel-body grid">
            <div class="span-3"><label class="check"><input id="linkEnabled" type="checkbox" ${link.enabled ? 'checked' : ''}> 啟用</label></div>
            <div class="span-3"><label>最多連結</label><input id="linkMaxLinks" type="number" value="${attr(link.max_links || 120)}"></div>
            <div class="span-3"><label>Request 逾時 ms</label><input id="linkTimeout" type="number" value="${attr(link.request_timeout_ms || 25000)}"></div>
            <div class="span-6"><label>種子路徑</label><textarea id="linkSeedPaths">${html(lineText(link.seed_paths || []))}</textarea></div>
            <div class="span-6"><label>忽略 URL 關鍵字</label><textarea id="linkIgnoreKeywords">${html(lineText(link.ignore_url_keywords || []))}</textarea></div>
          </div>
        </div>`;
    }
    function selectedFlow() {
      return (state.data.flows || []).find((flow) => flow.id === state.selectedFlow) || null;
    }
    function blankStep(action = 'goto') {
      if (action === 'goto') return { action, name: '開啟頁面', path: '/' };
      if (action === 'click_first') return { action, name: '點擊物件', selectors: ["button:has-text('按鈕文字')"] };
      if (action === 'fill_first') return { action, name: '輸入欄位', selectors: ["input[type='text']"], value: '' };
      if (action === 'press_first') return { action, name: '鍵盤操作', selectors: ["input[type='text']"], key: 'Enter' };
      if (action === 'assert_any_text') return { action, name: '驗證文字', texts: ['成功文字'] };
      if (action === 'screenshot') return { action, name: '截圖' };
      if (action === 'wait') return { action, name: '等待', milliseconds: 1000 };
      return { action, name: actionNames[action] || action };
    }
    function blankFlow() {
      const next = (state.data.flows || []).length + 1;
      return { id: `flow-${next}`, name: '新增流程', group: '未分類', enabled: false, input: {}, acceptance: [], steps: [blankStep('goto'), blankStep('screenshot')] };
    }
    function stepFields(step) {
      return `
        <div class="span-4"><label>路徑</label><input data-step-field="path" value="${attr(step.path || '')}" placeholder="/target-page"></div>
        <div class="span-4"><label>完整網址</label><input data-step-field="url" value="${attr(step.url || '')}" placeholder="https://..."></div>
        <div class="span-4"><label>逾時 ms</label><input data-step-field="timeout_ms" type="number" value="${attr(step.timeout_ms || '')}"></div>
        <div class="span-6"><label>物件 selectors</label><textarea data-step-field="selectors">${html(lineText(step.selectors || []))}</textarea></div>
        <div class="span-6"><label>預期文字</label><textarea data-step-field="texts">${html(lineText(step.texts || []))}</textarea></div>
        <div class="span-4"><label>輸入值</label><input data-step-field="value" value="${attr(step.value || '')}"></div>
        <div class="span-4"><label>按鍵</label><input data-step-field="key" value="${attr(step.key || '')}" placeholder="Enter"></div>
        <div class="span-4"><label>等待毫秒</label><input data-step-field="milliseconds" type="number" value="${attr(step.milliseconds || '')}"></div>
        <div class="span-4"><label>截圖檔名</label><input data-step-field="filename" value="${attr(step.filename || '')}"></div>
        <div class="span-4"><label>載入狀態</label><select data-step-field="state">
          ${['load', 'domcontentloaded', 'networkidle'].map((item) => `<option value="${item}" ${step.state === item ? 'selected' : ''}>${item}</option>`).join('')}
        </select></div>
        <div class="span-4"><label class="check"><input data-step-field="full_page" type="checkbox" ${step.full_page ? 'checked' : ''}> 整頁截圖</label></div>
        <div class="span-12"><label>註記</label><textarea data-step-field="note">${html(step.note || '')}</textarea></div>`;
    }
    function flowForm(flow) {
      flow = flow || blankFlow();
      const steps = flow.steps || [];
      return `
        <div class="grid">
          <div class="span-3"><label>流程 ID</label><input id="flowId" value="${attr(flow.id || '')}"></div>
          <div class="span-5"><label>名稱</label><input id="flowName" value="${attr(flow.name || '')}"></div>
          <div class="span-4"><label>分類</label><input id="flowGroup" value="${attr(flow.group || '')}"></div>
          <div class="span-12 toolbar">
            <label class="check"><input id="flowEnabled" type="checkbox" ${flow.enabled ? 'checked' : ''}> 啟用</label>
            <label class="check" title="會送出申請、寄信、下載、新增收藏、修改資料等真實改動時，請標記為有副作用。"><input id="flowSideEffect" type="checkbox" ${flow.side_effect ? 'checked' : ''}> 有副作用</label>
            <span class="status">會改變資料、送出表單或產生外部動作的流程，建議使用測試帳號並避免排程自動執行。</span>
          </div>
          <div class="span-6"><label>參數 JSON</label><textarea id="flowInput" spellcheck="false">${html(JSON.stringify(flow.input || {}, null, 2))}</textarea></div>
          <div class="span-6"><label>驗收條件</label><textarea id="flowAcceptance">${html(lineText(flow.acceptance || []))}</textarea></div>
          <div class="span-12 toolbar">
            ${Object.entries({goto:'開頁',click_first:'按鈕',fill_first:'輸入',press_first:'鍵盤',assert_any_text:'驗證',screenshot:'截圖',wait:'等待'}).map(([action, label]) => `<button class="small" data-add-step="${action}">${label}</button>`).join('')}
          </div>
          <div class="span-12 steps">
            ${steps.map((step, index) => `
              <div class="step" data-step="${index}">
                <div class="step-head">
                  <div class="step-no">${index + 1}</div>
                  <select data-step-field="action">${Object.entries(actionNames).map(([key, label]) => `<option value="${key}" ${step.action === key ? 'selected' : ''}>${label}</option>`).join('')}</select>
                  <input data-step-field="name" value="${attr(step.name || '')}" placeholder="步驟名稱">
                  <div class="toolbar">
                    <label class="check"><input data-step-field="optional" type="checkbox" ${step.optional ? 'checked' : ''}> 可略過</label>
                    <button class="small" data-step-move="-1">上移</button>
                    <button class="small" data-step-move="1">下移</button>
                    <button class="small danger" data-step-delete>刪除</button>
                  </div>
                </div>
                <div class="step-body grid">${stepFields(step)}</div>
              </div>`).join('') || '<div class="empty">尚未建立步驟</div>'}
          </div>
        </div>`;
    }
    function renderFlows() {
      const flows = state.data.flows || [];
      $('flows').innerHTML = `
        <div class="split">
          <div class="panel">
            <div class="panel-head"><h3>流程清單</h3><button class="small primary" data-new-flow>新增</button></div>
            <div class="panel-body list">
              ${flows.map((flow) => `
                <button class="row ${flow.id === state.selectedFlow ? 'active' : ''}" data-select-flow="${attr(flow.id)}">
                  <span><span class="row-title">${html(flow.name || flow.id)}</span><span class="row-sub">${html(flow.group || '未分類')} · ${html(flow.id)}</span></span>
                  <span class="badge ${flow.enabled ? 'on' : ''}">${flow.enabled ? '啟用' : '停用'}</span>
                </button>`).join('') || '<div class="empty">尚未設定自訂流程</div>'}
            </div>
          </div>
          <div class="panel">
            <div class="panel-head"><h3>流程設定</h3><div class="toolbar"><button class="small danger" data-delete-flow>刪除</button><button class="small primary" data-save-flow>儲存</button></div></div>
            <div class="panel-body">${flowForm(selectedFlow())}</div>
          </div>
        </div>`;
    }
    function renderResults() {
      const latest = state.data.latest_report;
      $('results').innerHTML = `
        <div class="panel">
          <div class="panel-head"><h3>執行控制</h3><button class="small primary" data-run-now>立即試跑</button></div>
          <div class="panel-body">
            <label class="check"><input id="runEnableFlows" type="checkbox"> 試跑時啟用自訂流程</label>
            <div id="runOutput" class="status" style="margin-top:12px"></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-head"><h3>Latest Report</h3></div>
          <div class="panel-body">
            ${latest ? `
              <table class="table"><tbody>
                <tr><th>Run ID</th><td>${html(latest.run_id)}</td></tr>
                <tr><th>狀態</th><td><span class="badge ${latest.ok ? 'on' : 'warn'}">${latest.ok ? 'OK' : '有異常'}</span></td></tr>
                <tr><th>Summary</th><td>PASS ${html(latest.summary?.pass || 0)} / WARN ${html(latest.summary?.warn || 0)} / FAIL ${html(latest.summary?.fail || 0)}</td></tr>
                <tr><th>檔案</th><td>${html(latest.path || '')}</td></tr>
              </tbody></table>
              <pre>${html(JSON.stringify(latest, null, 2))}</pre>` : '<div class="empty">尚未產生 reports/latest.json</div>'}
          </div>
        </div>`;
    }
    function currentPageFromForm() {
      return {
        id: $('pageId').value.trim(),
        name: $('pageName').value.trim(),
        path: $('pagePath').value.trim(),
        expected_title_contains: lines($('pageTitleRules').value),
        required_texts: lines($('pageRequiredTexts').value),
        full_page_screenshot: $('pageFullShot').checked
      };
    }
    function currentFlowFromForm() {
      let input = {};
      try { input = JSON.parse($('flowInput').value || '{}'); } catch (error) { throw new Error('參數 JSON 格式錯誤'); }
      const steps = Array.from(document.querySelectorAll('#flows .step')).map((el) => {
        const action = el.querySelector('[data-step-field="action"]').value;
        const step = { action };
        el.querySelectorAll('[data-step-field]').forEach((field) => {
          const key = field.dataset.stepField;
          if (key === 'action') return;
          if (field.type === 'checkbox') {
            if (field.checked) step[key] = true;
          } else if (['selectors', 'texts'].includes(key)) {
            const value = lines(field.value);
            if (value.length) step[key] = value;
          } else if (field.value !== '') {
            step[key] = field.value;
          }
        });
        return step;
      });
      return {
        id: $('flowId').value.trim(),
        name: $('flowName').value.trim(),
        group: $('flowGroup').value.trim(),
        enabled: $('flowEnabled').checked,
        side_effect: $('flowSideEffect').checked,
        input,
        acceptance: lines($('flowAcceptance').value),
        steps
      };
    }
    async function savePayload(path, body, okText) {
      try {
        setStatus('儲存中...');
        await api(path, { method: 'POST', body: JSON.stringify(body) });
        await load();
        setStatus(okText || '已儲存', 'ok');
      } catch (error) {
        setStatus(error.message, 'error');
      }
    }
    async function runNow() {
      try {
        $('runOutput')?.classList.remove('error');
        if ($('runOutput')) $('runOutput').textContent = '執行中，請稍候...';
        setStatus('試跑中...');
        const payload = await api('/api/run', {
          method: 'POST',
          body: JSON.stringify({ enable_flows: Boolean($('runEnableFlows')?.checked) })
        });
        await load();
        setStatus(`試跑完成，exit=${payload.return_code}`, payload.return_code === 0 ? 'ok' : 'error');
        switchTab('results');
      } catch (error) {
        if ($('runOutput')) $('runOutput').textContent = error.message;
        setStatus(error.message, 'error');
      }
    }
    document.addEventListener('click', async (event) => {
      const target = event.target;
      if (target.dataset.tab) switchTab(target.dataset.tab);
      if (target.id === 'reloadButton') load();
      if (target.id === 'runButton' || target.dataset.runNow !== undefined) runNow();
      if (target.dataset.saveGeneral !== undefined) {
        savePayload('/api/settings/general', { settings: {
          target_name: $('targetName').value,
          base_url: $('baseUrl').value,
          global_timeout_seconds: $('globalTimeout').value,
          allowed_hosts: lines($('allowedHosts').value),
          ignore_url_keywords: lines($('ignoreKeywords').value)
        }}, '基本設定已儲存');
      }
      if (target.dataset.newPage !== undefined) {
        const page = { id: `page-${(state.data.pages || []).length + 1}`, name: '新增頁面', path: '/', expected_title_contains: [], required_texts: [] };
        state.data.pages = [...(state.data.pages || []), page];
        state.selectedPage = page.id;
        renderPages();
      }
      if (target.dataset.selectPage) { state.selectedPage = target.dataset.selectPage; renderPages(); }
      if (target.dataset.savePage !== undefined) savePayload('/api/pages', { previous_id: state.selectedPage, page: currentPageFromForm() }, '頁面已儲存');
      if (target.dataset.deletePage !== undefined && state.selectedPage && confirm('刪除此頁面巡檢？')) {
        await api(`/api/pages/${encodeURIComponent(state.selectedPage)}`, { method: 'DELETE' });
        state.selectedPage = null;
        await load();
      }
      if (target.dataset.saveSearch !== undefined) {
        savePayload('/api/settings/search', { settings: {
          enabled: $('searchEnabled').checked,
          query: $('searchQuery').value,
          trigger_selectors: lines($('searchTriggerSelectors').value),
          input_selectors: lines($('searchInputSelectors').value),
          submit_selectors: lines($('searchSubmitSelectors').value),
          expected_any_text: lines($('searchExpectedText').value)
        }}, '搜尋檢查已儲存');
      }
      if (target.dataset.saveSsl !== undefined) {
        savePayload('/api/settings/ssl', { settings: {
          enabled: $('sslEnabled').checked,
          port: $('sslPort').value,
          warn_days: $('sslWarnDays').value,
          fail_days: $('sslFailDays').value,
          hosts: lines($('sslHosts').value)
        }}, 'SSL 設定已儲存');
      }
      if (target.dataset.saveLink !== undefined) {
        savePayload('/api/settings/link', { settings: {
          enabled: $('linkEnabled').checked,
          max_links: $('linkMaxLinks').value,
          request_timeout_ms: $('linkTimeout').value,
          seed_paths: lines($('linkSeedPaths').value),
          ignore_url_keywords: lines($('linkIgnoreKeywords').value)
        }}, '連結檢查已儲存');
      }
      if (target.dataset.newFlow !== undefined) {
        const flow = blankFlow();
        flow.id = slug(`${flow.id}-${Date.now().toString().slice(-4)}`);
        state.data.flows = [...(state.data.flows || []), flow];
        state.selectedFlow = flow.id;
        renderFlows();
      }
      if (target.dataset.selectFlow) { state.selectedFlow = target.dataset.selectFlow; renderFlows(); }
      if (target.dataset.saveFlow !== undefined) savePayload('/api/flows', { previous_id: state.selectedFlow, flow: currentFlowFromForm() }, '流程已儲存');
      if (target.dataset.deleteFlow !== undefined && state.selectedFlow && confirm('刪除此自訂流程？')) {
        await api(`/api/flows/${encodeURIComponent(state.selectedFlow)}`, { method: 'DELETE' });
        state.selectedFlow = null;
        await load();
      }
      if (target.dataset.addStep) {
        const flow = currentFlowFromForm();
        flow.steps.push(blankStep(target.dataset.addStep));
        const idx = state.data.flows.findIndex((item) => item.id === state.selectedFlow);
        if (idx >= 0) state.data.flows[idx] = flow;
        renderFlows();
      }
      if (target.dataset.stepDelete !== undefined) {
        const flow = currentFlowFromForm();
        const index = Number(target.closest('.step').dataset.step);
        flow.steps.splice(index, 1);
        const idx = state.data.flows.findIndex((item) => item.id === state.selectedFlow);
        if (idx >= 0) state.data.flows[idx] = flow;
        renderFlows();
      }
      if (target.dataset.stepMove) {
        const flow = currentFlowFromForm();
        const index = Number(target.closest('.step').dataset.step);
        const next = index + Number(target.dataset.stepMove);
        if (next >= 0 && next < flow.steps.length) {
          const [item] = flow.steps.splice(index, 1);
          flow.steps.splice(next, 0, item);
        }
        const idx = state.data.flows.findIndex((item) => item.id === state.selectedFlow);
        if (idx >= 0) state.data.flows[idx] = flow;
        renderFlows();
      }
    });
    document.addEventListener('change', (event) => {
      if (event.target.dataset.stepField === 'action') {
        const flow = currentFlowFromForm();
        const index = Number(event.target.closest('.step').dataset.step);
        flow.steps[index] = { ...blankStep(event.target.value), name: flow.steps[index].name || blankStep(event.target.value).name };
        const idx = state.data.flows.findIndex((item) => item.id === state.selectedFlow);
        if (idx >= 0) state.data.flows[idx] = flow;
        renderFlows();
      }
    });
    $('tokenButton').addEventListener('click', () => {
      state.token = $('tokenInput').value;
      sessionStorage.setItem('inspectionUiToken', state.token);
      load();
    });
    $('tokenInput').addEventListener('keydown', (event) => {
      if (event.key === 'Enter') $('tokenButton').click();
    });
    load();
  </script>
</body>
</html>
"""


class FlowUIHandler(BaseHTTPRequestHandler):
    config_path: Path
    output_dir: Path
    repo_root: Path
    token: str = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"ok": False, "error": message})

    def _authorized(self) -> bool:
        if not self.token:
            return True
        return self.headers.get("X-Flow-Editor-Token", "") == self.token

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._error(401, "需要有效 token")
        return False

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(data, dict):
            raise FlowValidationError("request body must be an object")
        return data

    def _load(self) -> dict[str, Any]:
        return load_config(self.config_path)

    def _save(self, config: dict[str, Any]) -> Path | None:
        return save_config(self.config_path, config)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/config":
            if not self._require_auth():
                return
            try:
                self._json(200, editor_payload(self._load(), self.output_dir))
            except Exception as exc:
                self._error(500, str(exc))
            return
        if parsed.path == "/api/latest":
            if not self._require_auth():
                return
            try:
                self._json(200, {"ok": True, "report": latest_report(self.output_dir)})
            except Exception as exc:
                self._error(500, str(exc))
            return
        self._error(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not self._require_auth():
            return
        try:
            data = self._read_json()
            if parsed.path == "/api/flows":
                config = self._load()
                flow = upsert_flow(config, data.get("flow", {}), data.get("previous_id"))
                backup = self._save(config)
                self._json(200, {"ok": True, "flow": flow, "backup": str(backup) if backup else ""})
                return
            if parsed.path == "/api/pages":
                config = self._load()
                page = upsert_page(config, data.get("page", {}), data.get("previous_id"))
                backup = self._save(config)
                self._json(200, {"ok": True, "page": page, "backup": str(backup) if backup else ""})
                return
            if parsed.path.startswith("/api/settings/"):
                config = self._load()
                name = parsed.path.rsplit("/", 1)[-1]
                settings = data.get("settings", {})
                if name == "general":
                    saved = update_general(config, settings)
                elif name == "search":
                    saved = update_search_check(config, settings)
                elif name == "link":
                    saved = update_link_crawl(config, settings)
                elif name == "ssl":
                    saved = update_ssl(config, settings)
                else:
                    self._error(404, "not found")
                    return
                backup = self._save(config)
                self._json(200, {"ok": True, "settings": saved, "backup": str(backup) if backup else ""})
                return
            if parsed.path == "/api/run":
                self._json(200, self._run_monitor(data))
                return
            self._error(404, "not found")
        except (FlowValidationError, json.JSONDecodeError) as exc:
            self._error(400, str(exc))
        except Exception as exc:
            self._error(500, str(exc))

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not self._require_auth():
            return
        try:
            config = self._load()
            if parsed.path.startswith("/api/flows/"):
                removed = delete_flow(config, unquote(parsed.path[len("/api/flows/") :]))
            elif parsed.path.startswith("/api/pages/"):
                removed = delete_page(config, unquote(parsed.path[len("/api/pages/") :]))
            else:
                self._error(404, "not found")
                return
            backup = self._save(config) if removed else None
            self._json(200, {"ok": True, "removed": removed, "backup": str(backup) if backup else ""})
        except Exception as exc:
            self._error(500, str(exc))

    def _run_monitor(self, data: dict[str, Any]) -> dict[str, Any]:
        config = self._load()
        timeout_seconds = int(config.get("global_timeout_seconds", 1800) or 1800) + 120
        command = [
            sys.executable,
            "-m",
            "taiwanlife_monitor.monitor",
            "--config",
            str(self.config_path),
            "--output-dir",
            str(self.output_dir),
            "--scheduler",
            "flow-ui",
            "--fail-exit-code",
        ]
        if data.get("enable_flows"):
            command.append("--enable-rpa84")
        completed = subprocess.run(
            command,
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        parsed: dict[str, Any] | None = None
        for line in reversed(completed.stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                parsed = candidate
                break
        return {
            "ok": completed.returncode == 0,
            "return_code": completed.returncode,
            "payload": parsed,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="巡檢管理後台")
    parser.add_argument("--config", default="config/taiwanlife.json", help="設定檔路徑")
    parser.add_argument("--output-dir", default="reports", help="巡檢報表目錄")
    parser.add_argument("--host", default="127.0.0.1", help="綁定 IP，預設只允許本機")
    parser.add_argument("--port", type=int, default=8787, help="服務 port")
    parser.add_argument("--token", default=os.environ.get("FLOW_UI_TOKEN", ""), help="API 存取 token")
    parser.add_argument("--no-browser", action="store_true", help="不要自動開啟瀏覽器")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 2
    if args.host not in {"127.0.0.1", "localhost", "::1"} and not args.token:
        print("Refusing non-local bind without --token or FLOW_UI_TOKEN.", file=sys.stderr)
        return 2
    FlowUIHandler.config_path = config_path
    FlowUIHandler.output_dir = output_dir
    FlowUIHandler.repo_root = Path.cwd().resolve()
    FlowUIHandler.token = args.token
    server = ThreadingHTTPServer((args.host, args.port), FlowUIHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Inspection UI running: {url}", flush=True)
    print(f"Config: {config_path}", flush=True)
    print(f"Output dir: {output_dir}", flush=True)
    if args.token:
        print("Token protection: enabled", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping inspection UI.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
