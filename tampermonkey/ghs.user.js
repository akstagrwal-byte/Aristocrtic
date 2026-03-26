// ==UserScript==
// @name         GHS Automation Script UI
// @namespace    https://aristocrtic.local
// @version      0.3.0
// @description  Minimal UI + connected auth/credit/run flow
// @match        https://target-site.example/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_notification
// @connect      localhost
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const API = 'http://localhost:8000';

  function api(path, method = 'GET', data = null, token = null) {
    return new Promise((resolve, reject) => {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers.Authorization = `Bearer ${token}`;

      GM_xmlhttpRequest({
        method,
        url: `${API}${path}`,
        data: data ? JSON.stringify(data) : undefined,
        headers,
        onload: (res) => {
          try {
            const payload = JSON.parse(res.responseText || '{}');
            if (res.status >= 200 && res.status < 300) {
              resolve(payload);
            } else {
              reject(new Error(payload.detail || `HTTP ${res.status}`));
            }
          } catch {
            reject(new Error(`Invalid response from ${path}`));
          }
        },
        onerror: () => reject(new Error(`Network error calling ${path}`)),
      });
    });
  }

  function el(tag, attrs = {}, text = '') {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    if (text) node.textContent = text;
    return node;
  }

  function addStyles() {
    const style = el('style');
    style.textContent = `
      #ghs-panel {
        position: fixed;
        top: 20px;
        right: 20px;
        width: 320px;
        z-index: 999999;
        background: #0f172a;
        color: #e2e8f0;
        border: 1px solid #334155;
        border-radius: 12px;
        box-shadow: 0 10px 30px rgba(0,0,0,.35);
        font-family: Inter, system-ui, -apple-system, Segoe UI, sans-serif;
      }
      #ghs-panel .header {
        padding: 12px 14px;
        border-bottom: 1px solid #334155;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      #ghs-panel .title { font-size: 14px; font-weight: 700; }
      #ghs-panel .body { padding: 12px; display: grid; gap: 10px; }
      #ghs-panel input {
        width: 100%;
        border: 1px solid #334155;
        background: #111827;
        color: #e2e8f0;
        border-radius: 8px;
        padding: 8px;
        box-sizing: border-box;
      }
      #ghs-panel .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
      #ghs-panel button {
        border: 1px solid #334155;
        background: #1e293b;
        color: #f8fafc;
        border-radius: 8px;
        padding: 8px 10px;
        cursor: pointer;
      }
      #ghs-panel button.primary { background: #2563eb; border-color: #1d4ed8; }
      #ghs-panel button.success { background: #059669; border-color: #047857; }
      #ghs-log {
        max-height: 130px;
        overflow: auto;
        padding: 8px;
        border-radius: 8px;
        background: #020617;
        border: 1px solid #334155;
        font-size: 12px;
        line-height: 1.3;
        white-space: pre-wrap;
      }
      #ghs-toggle {
        position: fixed;
        right: 20px;
        top: 20px;
        z-index: 999998;
        border-radius: 999px;
        padding: 10px 12px;
        border: 1px solid #334155;
        background: #111827;
        color: #e2e8f0;
        cursor: pointer;
      }
    `;
    document.head.appendChild(style);
  }

  function log(msg) {
    const area = document.querySelector('#ghs-log');
    if (!area) return;
    const ts = new Date().toLocaleTimeString();
    area.textContent = `[${ts}] ${msg}\n` + area.textContent;
  }

  async function onboard() {
    const name = document.querySelector('#ghs-name').value.trim();
    const referral = document.querySelector('#ghs-referral').value.trim() || null;
    if (!name) {
      log('Enter name before onboarding.');
      return;
    }

    try {
      log('Registering user...');
      const registerRes = await api('/users/register', 'POST', { name, referral_code: referral });
      const codeRes = await api(`/auth/code/create/${registerRes.user_id}`, 'POST');
      const verifyRes = await api('/auth/code/verify', 'POST', { code: codeRes.code });

      await GM_setValue('user_id', verifyRes.user_id);
      await GM_setValue('access_token', verifyRes.access_token);
      await GM_setValue('referral_code', registerRes.referral_code);

      log(`Onboarded ${registerRes.name}. Referral: ${registerRes.referral_code}`);
      GM_notification('Onboarding success');
      await refreshWallet();
    } catch (err) {
      log(`Onboarding failed: ${err.message}`);
    }
  }

  async function refreshWallet() {
    try {
      const token = await GM_getValue('access_token');
      if (!token) {
        log('No token available. Onboard first.');
        return;
      }
      const wallet = await api('/wallet/me', 'GET', null, token);
      document.querySelector('#ghs-wallet').textContent = `Credits: ${wallet.available_credits} | Locked: ${wallet.locked_credits} | Run Cost: ${wallet.run_cost}`;
      log('Wallet refreshed.');
    } catch (err) {
      log(`Wallet refresh failed: ${err.message}`);
    }
  }

  async function runGHSFlow() {
    const token = await GM_getValue('access_token');
    if (!token) {
      log('No access token found. Onboard first.');
      return;
    }

    const country = document.querySelector('#ghs-country').value.trim() || 'us';
    const state = document.querySelector('#ghs-state').value.trim() || 'ca';
    const city = document.querySelector('#ghs-city').value.trim() || 'san francisco';

    try {
      const wallet = await api('/wallet/me', 'GET', null, token);
      if (wallet.available_credits < wallet.run_cost) {
        log(`Insufficient credits. Need ${wallet.run_cost}, have ${wallet.available_credits}.`);
        return;
      }

      log('Creating run...');
      const run = await api('/runs', 'POST', {}, token);
      const hold = await api('/wallet/hold', 'POST', { run_id: run.run_id }, token);
      log(`Hold created: ${hold.hold_id}`);

      const result = await api('/runs/execute', 'POST', {
        run_id: run.run_id,
        hold_id: hold.hold_id,
        country,
        state,
        city,
        simulate_failure: false,
      }, token);

      log(`Run ${result.run_id} complete: ${result.status} (${result.college || 'N/A'})`);
      GM_notification(`Run status: ${result.status}`);
      await refreshWallet();
    } catch (err) {
      log(`Run failed: ${err.message}`);
    }
  }

  async function copyReferral() {
    const code = await GM_getValue('referral_code');
    if (!code) {
      log('No referral code yet. Onboard first.');
      return;
    }
    navigator.clipboard.writeText(code);
    log(`Referral copied: ${code}`);
  }

  function buildPanel() {
    addStyles();

    const toggle = el('button', { id: 'ghs-toggle' }, 'GHS UI');
    const panel = el('div', { id: 'ghs-panel' });

    panel.innerHTML = `
      <div class="header">
        <div class="title">GHS Control</div>
        <button id="ghs-hide">Hide</button>
      </div>
      <div class="body">
        <input id="ghs-name" placeholder="Name" />
        <input id="ghs-referral" placeholder="Referral code (optional)" />
        <div class="row">
          <input id="ghs-country" placeholder="Country" value="us" />
          <input id="ghs-state" placeholder="State" value="ca" />
        </div>
        <input id="ghs-city" placeholder="City" value="san francisco" />

        <div class="row">
          <button id="ghs-onboard" class="primary">Onboard</button>
          <button id="ghs-wallet">Refresh Wallet</button>
        </div>

        <div class="row">
          <button id="ghs-run" class="success">Run GHS</button>
          <button id="ghs-ref">Copy Referral</button>
        </div>

        <div id="ghs-wallet">Credits: -</div>
        <div id="ghs-log">Ready.</div>
      </div>
    `;

    document.body.appendChild(toggle);
    document.body.appendChild(panel);

    toggle.addEventListener('click', () => {
      panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    });
    panel.querySelector('#ghs-hide').addEventListener('click', () => {
      panel.style.display = 'none';
    });

    panel.querySelector('#ghs-onboard').addEventListener('click', onboard);
    panel.querySelector('#ghs-wallet').addEventListener('click', refreshWallet);
    panel.querySelector('#ghs-run').addEventListener('click', runGHSFlow);
    panel.querySelector('#ghs-ref').addEventListener('click', copyReferral);
  }

  buildPanel();

  window.GHSAutomation = { onboard, runGHSFlow, refreshWallet, copyReferral };
})();
