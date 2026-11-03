"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const key = "carrotGoogleShareToken";
  let token = "", selected = null, busy = false;
  try { token = localStorage.getItem(key) || ""; } catch (_) {}
  const status = text => { $("status").textContent = text; };
  function pairUI() { $("pairPanel").hidden = Boolean(token); }
  function choose(place) {
    selected = place;
    $("place").textContent = place.place_name;
    $("coords").textContent = `${place.latitude}, ${place.longitude}`;
    $("preview").hidden = false;
    status("請確認這是正確地點，再按「確認，傳送到 Carrot」。");
  }
  async function api(path, body, paired = true) {
    const headers = {"Content-Type": "application/json"};
    if (paired) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(`/api/navigation/share/${path}`, {method: "POST", headers, body: JSON.stringify(body), cache: "no-store"});
    const value = await response.json();
    if (response.status === 401) { token = ""; try { localStorage.removeItem(key); } catch (_) {} pairUI(); }
    if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
    return value;
  }
  async function task(fn) {
    if (busy) return;
    busy = true;
    document.querySelectorAll("button").forEach(b => { b.disabled = true; });
    try { await fn(); } catch (error) { status(error.message); }
    finally { busy = false; document.querySelectorAll("button").forEach(b => { b.disabled = false; }); }
  }
  function clearPreview() { selected = null; $("preview").hidden = true; $("results").replaceChildren(); }
  $("pairForm").addEventListener("submit", event => {
    event.preventDefault();
    task(async () => {
      const value = await api("pair", {code: $("code").value.trim()}, false);
      token = value.token;
      try { localStorage.setItem(key, token); } catch (_) { status("已配對；此瀏覽器無法保存配對，下次可能需重新配對。"); pairUI(); return; }
      $("code").value = ""; pairUI(); status("配對完成，請解析分享連結。");
    });
  });
  $("importForm").addEventListener("submit", event => {
    event.preventDefault();
    task(async () => {
      clearPreview();
      if (!token) throw new Error("請先配對手機。");
      status("正在解析 Google Maps 地點…");
      const result = await api("resolve", {url: $("shared").value.trim()});
      if (result.destination) choose(result.destination);
      else { $("query").value = result.query; status("連結只有地名，請按「搜尋候選地點」並選擇正確結果。"); }
    });
  });
  $("searchForm").addEventListener("submit", event => {
    event.preventDefault();
    task(async () => {
      clearPreview();
      if (!token) throw new Error("請先配對手機。");
      const response = await fetch(`/api/navigation/search?q=${encodeURIComponent($("query").value.trim())}`, {cache: "no-store"});
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
      for (const place of value.results) {
        const row = document.createElement("li"), button = document.createElement("button");
        button.textContent = place.place_name;
        button.addEventListener("click", () => choose(place));
        row.append(button); $("results").append(row);
      }
      status(value.results.length ? "請選擇正確的候選地點。" : "找不到地點，請輸入更完整地址。");
    });
  });
  $("confirm").addEventListener("click", () => task(async () => {
    if (!selected) return;
    const name = selected.place_name;
    await api("confirm", selected);
    clearPreview(); status(`已傳送：${name}\nCarrot 正在依目前位置計算路線，請到導航頁查看地圖。`);
  }));
  $("forget").addEventListener("click", () => {
    token = ""; clearPreview(); try { localStorage.removeItem(key); } catch (_) {} pairUI(); status("已清除此瀏覽器的配對；要撤銷所有配對，請在 C4 產生新配對碼。");
  });
  // Shortcuts puts the shared URL in the fragment, never in server request logs.
  const shared = new URLSearchParams(location.hash.slice(1)).get("url");
  if (shared) { $("shared").value = shared.slice(0, 4096); history.replaceState(null, "", location.pathname); status("已帶入分享連結，請按「解析地點」。"); }
  $("shortcutBase").value = `${location.origin}/navigation/share#url=`;
  pairUI();
})();
