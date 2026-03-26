// ==UserScript==
// @name         GHS Automation Script
// @namespace    https://aristocrtic.local
// @version      0.2.0
// @description  Full connected client for auth + credits + run orchestration
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
          if (res.status >= 200 && res.status < 300) {
            resolve(JSON.parse(res.responseText));
          } else {
            reject(new Error(`HTTP ${res.status} ${res.responseText}`));
          }
        },
        onerror: reject,
      });
    });
  }

  async function onboard(name, referralCode = null) {
    const registerRes = await api('/users/register', 'POST', {
      name,
      referral_code: referralCode,
    });

    const codeRes = await api(`/auth/code/create/${registerRes.user_id}`, 'POST');
    // In production, code is delivered by bot UX. For scaffold we use returned code.
    const verifyRes = await api('/auth/code/verify', 'POST', { code: codeRes.code });

    await GM_setValue('user_id', verifyRes.user_id);
    await GM_setValue('access_token', verifyRes.access_token);

    return verifyRes;
  }

  async function runGHSFlow(country = 'us', state = 'ca', city = 'san francisco') {
    const token = await GM_getValue('access_token');
    if (!token) {
      GM_notification('No access token found. Run onboard(name) first.');
      return;
    }

    const wallet = await api('/wallet/me', 'GET', null, token);
    if (wallet.available_credits < wallet.run_cost) {
      GM_notification(`Insufficient credits. Need ${wallet.run_cost}, have ${wallet.available_credits}.`);
      return;
    }

    const run = await api('/runs', 'POST', {}, token);
    const hold = await api('/wallet/hold', 'POST', { run_id: run.run_id }, token);
    const result = await api('/runs/execute', 'POST', {
      run_id: run.run_id,
      hold_id: hold.hold_id,
      country,
      state,
      city,
      simulate_failure: false,
    }, token);

    GM_notification(`Run ${result.run_id}: ${result.status}`);
    return result;
  }

  window.GHSAutomation = { onboard, runGHSFlow };
})();
