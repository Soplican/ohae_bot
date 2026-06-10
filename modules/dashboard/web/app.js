
const $ = (id)=>document.getElementById(id);

function toast(msg, ok=true){
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast show " + (ok ? "ok" : "bad");
  setTimeout(()=>{ t.className="toast"; }, 2600);
}

async function api(url, opts){
  const r = await fetch(url, opts);
  if(!r.ok){
    let t = "";
    try{ t = await r.text(); }catch(e){}
    throw new Error(`HTTP ${r.status}: ${t}`);
  }
  const ct = r.headers.get("content-type") || "";
  if(ct.includes("application/json")) return r.json();
  return r.text();
}

function escapeHtml(s){
  return String(s)
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

function snowflakeStr(v){
  if(v === null || v === undefined) return "";
  const s = String(v).trim();
  if(!s) return "";
  if(!/^\d{5,30}$/.test(s)) return "";
  return s;
}

function parseJsonSafe(s, fallback){
  try{ return JSON.parse(s); }catch(e){ return fallback; }
}

let allModules = [];
let activeModule = null;
let guilds = [];
let activeGuildId = "";
let rolesCache = [];
let channelsCache = [];
let currentData = {};
let currentSource = "";
let isGlobal = false;

// ---------- init ----------
async function init(){
  try{
    const meta = await api("/dashboard_api/meta");
    if(meta && meta.bot){
      $("brandName").textContent = meta.bot.name ? `${meta.bot.name}` : "ManceraBOT";
      $("botMeta").textContent = meta.bot.id ? `Bot ID: ${meta.bot.id}` : "";
    }
  }catch(e){}

  const mods = await api("/dashboard_api/modules");
  allModules = mods.modules || [];
  renderModulesList(allModules);

  const g = await api("/dashboard_api/guilds");
  guilds = g.guilds || [];
  renderGuildSelect();

  $("search").addEventListener("input", ()=>{
    const q = $("search").value.toLowerCase().trim();
    const filtered = !q ? allModules : allModules.filter(m=>m.toLowerCase().includes(q));
    renderModulesList(filtered);
  });

  $("guildSelect").addEventListener("change", async ()=>{
    activeGuildId = $("guildSelect").value || "";
    await preloadGuildData();
    if(activeModule) await loadModule(activeModule);
  });

  $("saveBtn").addEventListener("click", saveActive);

  // pick first guild by default
  if(guilds.length){
    activeGuildId = String(guilds[0].id);
    $("guildSelect").value = activeGuildId;
    await preloadGuildData();
  }
}

function renderModulesList(list){
  const box = $("modulesList");
  box.innerHTML = "";
  list.forEach((name)=>{
    const b = document.createElement("div");
    b.className = "navBtn" + (activeModule===name ? " active":"");
    b.innerHTML = `<div class="navName">${escapeHtml(name)}</div>`;
    b.onclick = async ()=>{
      document.querySelectorAll(".navBtn").forEach(x=>x.classList.remove("active"));
      b.classList.add("active");
      activeModule = name;
      await loadModule(name);
    };
    box.appendChild(b);
  });
}

function renderGuildSelect(){
  const sel = $("guildSelect");
  sel.innerHTML = "";
  const opt0 = document.createElement("option");
  opt0.value = "";
  opt0.textContent = "— выбери сервер —";
  sel.appendChild(opt0);

  guilds.forEach(g=>{
    const o = document.createElement("option");
    o.value = String(g.id);
    o.textContent = g.name;
    sel.appendChild(o);
  });

  if(activeGuildId){
    sel.value = activeGuildId;
  }
}

async function preloadGuildData(){
  rolesCache = [];
  channelsCache = [];
  if(!activeGuildId) return;

  try{
    const r = await api(`/dashboard_api/guilds/${activeGuildId}/roles`);
    rolesCache = r.roles || [];
  }catch(e){
    rolesCache = [];
  }

  try{
    const c = await api(`/dashboard_api/guilds/${activeGuildId}/channels`);
    channelsCache = c.categories || [];
  }catch(e){
    channelsCache = [];
  }
}

function setHint(text){
  $("pageHint").textContent = text || "";
}

// ---------- load/save ----------
async function loadModule(module){
  if(!activeGuildId && module !== "discohook_local"){
    $("content").innerHTML = `<div class="empty"><div class="emptyTitle">Выбери сервер</div><div class="emptyText">Сверху справа выбери сервер, чтобы редактировать настройки.</div></div>`;
    return;
  }
  const q = new URLSearchParams();
  q.set("module", module);
  if(activeGuildId) q.set("guild_id", activeGuildId);

  const res = await api(`/dashboard_api/config/get?${q.toString()}`);
  currentData = res.data || {};
  currentSource = res.source || "";
  isGlobal = !!res.is_global;

  renderForm(module, currentData, currentSource);
}

async function saveActive(){
  if(!activeModule) return toast("Выбери модуль слева", false);

  // pull latest data from UI
  const updated = collectFormData(activeModule);
  if(updated === null){
    // collectFormData already showed toast
    return;
  }
  const payload = {
    module: activeModule,
    guild_id: activeGuildId || null,
    data: updated
  };
  try{
    await api("/dashboard_api/config/save", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
    toast("Сохранено ✅", true);
  }catch(e){
    toast("Ошибка сохранения: " + e.message, false);
  }
}

// ---------- form routing ----------
function renderForm(module, data, source){
  $("pageTitle").textContent = `Модуль: ${module}`;
  $("cardTitle").textContent = `Настройки (${module})`;
  $("cardSub").textContent = source ? `Источник: ${source}. Изменения сохраняются в JSON.` : `Изменения сохраняются в JSON.`;

  if(module === "welcome"){
    renderWelcomeForm(data);
    return;
  }
  if(module === "infoaudit"){
    renderInfoauditForm(data);
    return;
  }
  if(module === "discohook_local"){
    renderDiscohookLocalForm(data);
    return;
  }
  if(module === "souz"){
    renderSouzForm(data);
    return;
  }
  if(module === "requests"){
    renderRequestsForm(data);
    return;
  }

  renderJsonEditor(module, data);
}

function renderJsonEditor(module, data){
  const content = $("content");
  const pretty = JSON.stringify(data || {}, null, 2);
  content.innerHTML = `
    <div class="smallNote">Для этого модуля пока нет визуальной формы. Можно править JSON вручную.</div>
    <div class="field">
      <label>Config JSON</label>
      <textarea class="textarea" id="rawJson">${escapeHtml(pretty)}</textarea>
    </div>
  `;

  // preview
  bindWelcomePreview();
}

function collectFormData(module){
  if(module === "welcome") return collectWelcome();
  if(module === "infoaudit") return collectInfoaudit();
  if(module === "discohook_local") return collectDiscohookLocal();
  if(module === "souz") return collectSouz();
  if(module === "requests") return collectRequests();

  // fallback JSON editor
  const raw = $("rawJson");
  if(raw){
    const parsed = parseJsonSafe(raw.value, null);
    if(parsed === null || typeof parsed !== "object"){
      toast("JSON неверный", false);
      return null;
    }
    return parsed;
  }
  return currentData || {};
}

// ---------- UI helpers ----------
function switchField(label, id, checked){
  return `
  <div class="field">
    <label>${escapeHtml(label)}</label>
    <div class="row">
      <input type="checkbox" id="${id}" ${checked ? "checked":""}/>
      <span class="badge">${checked ? "Включено":"Выключено"}</span>
    </div>
  </div>`;
}

function inputField(label, id, value="", type="text", placeholder=""){
  return `
  <div class="field">
    <label for="${id}">${escapeHtml(label)}</label>
    <input class="input" id="${id}" type="${type}" placeholder="${escapeHtml(placeholder)}" value="${escapeHtml(String(value ?? ""))}">
  </div>`;
}

function textareaField(label, id, value="", placeholder=""){
  return `
  <div class="field">
    <label for="${id}">${escapeHtml(label)}</label>
    <textarea class="textarea" id="${id}" placeholder="${escapeHtml(placeholder)}">${escapeHtml(String(value ?? ""))}</textarea>
  </div>`;
}

function channelSelectField(label, id, selected){
  const sel = snowflakeStr(selected || "");
  let html = `
  <div class="field">
    <label>${escapeHtml(label)}</label>
    <select class="select2" id="${id}">
      <option value="">— не выбран —</option>
  `;
  channelsCache.forEach(cat=>{
    const gLabel = cat.id ? cat.name : "Без категории";
    html += `<optgroup label="${escapeHtml(gLabel)}">`;
    (cat.channels||[]).forEach(ch=>{
      const cid = String(ch.id);
      html += `<option value="${cid}" ${cid===sel?"selected":""}>#${escapeHtml(ch.name)}</option>`;
    });
    html += `</optgroup>`;
  });
  html += `</select></div>`;
  return html;
}


function selectField(label, id, options, selected){
  const sel = String(selected ?? "");
  let html = `
  <div class="field">
    <label>${escapeHtml(label)}</label>
    <select class="select2" id="${id}">
  `;
  for(const [val, name] of (options || [])){
    const v = String(val);
    html += `<option value="${escapeHtml(v)}" ${v===sel ? "selected":""}>${escapeHtml(name)}</option>`;
  }
  html += `</select></div>`;
  return html;
}

function rolesMultiSelect(label, id, selectedList){
  const selected = new Set((selectedList||[]).map(x=>String(x)));
  let html = `
  <div class="field">
    <label>${escapeHtml(label)}</label>
    <select class="select2" id="${id}" multiple size="8">
  `;
  rolesCache.forEach(r=>{
    const rid = String(r.id);
    html += `<option value="${rid}" ${selected.has(rid)?"selected":""}>${escapeHtml(r.name)}</option>`;
  });
  html += `</select><div class="smallNote">Ctrl/Shift для выбора нескольких ролей</div></div>`;
  return html;
}

// ---------- welcome ----------
function renderWelcomeForm(d){
  const data = JSON.parse(JSON.stringify(d||{}));
  data.enabled = (data.enabled !== false);
  data.channel_id = data.channel_id || "";
  data.greeting = data.greeting || {};
  data.greeting.text = data.greeting.text || "{mention}, добро пожаловать!";
  data.footer_text = data.footer_text || "";
  data.rows = Array.isArray(data.rows) ? data.rows : [];

  const content = $("content");
  content.innerHTML = `
    <div class="sectionTitle">Основное</div>
    <div class="fieldGrid">
      ${switchField("Включено", "wel_enabled", data.enabled)}
      ${channelSelectField("Канал приветствия", "wel_channel", data.channel_id)}
      ${inputField("Текст приветствия", "wel_text", data.greeting.text, "text", "Можно использовать {mention}, {user}, {server}")}
      ${inputField("Footer (опционально)", "wel_footer", data.footer_text, "text")}
    </div>

    <div class="hr"></div>
    <div class="sectionTitle">Расширенно (компоненты/разметка)</div>
    <div class="smallNote">Если хочешь сложную панель как раньше — редактируй JSON ниже. Для новичков можно не трогать.</div>
    <div class="field">
      <label>rows (JSON массив)</label>
      <textarea class="textarea" id="wel_rows">${escapeHtml(JSON.stringify(data.rows, null, 2))}</textarea>
    </div>

    <div class="hr"></div>
    <div class="sectionTitle">Preview</div>
    <div class="smallNote">Превью имитирует Discord (сообщение + компоненты). Данные примерные.</div>
    <div id="wel_preview" class="dprevWrap"></div>

  `;
}

function collectWelcome(){
  const enabled = !!$("wel_enabled").checked;
  const channel_id = snowflakeStr($("wel_channel").value);
  const text = $("wel_text").value.trim();
  const footer_text = $("wel_footer").value.trim();
  const rowsRaw = $("wel_rows").value.trim();
  const rows = parseJsonSafe(rowsRaw, null);
  if(rows === null || !Array.isArray(rows)){
    toast("rows должен быть JSON массивом", false);
    return null;
  }
  return {
    enabled,
    channel_id: channel_id || "",
    greeting: { text: text || "{mention}, добро пожаловать!" },
    footer_text: footer_text || "",
    rows
  };
}
/* =========================
   Discord-like Preview (welcome)
   ========================= */

function _dprevEscape(s){
  return String(s ?? "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

function _dprevMd(text){
  // lightweight Discord-ish markdown (no HTML allowed from user input)
  let s = _dprevEscape(text || "");
  // codeblock ``` ```
  s = s.replace(/```([\s\S]*?)```/g, (m, code)=>`<pre class="dprevCodeblock"><code>${code}</code></pre>`);
  // inline code
  s = s.replace(/`([^`\n]+)`/g, `<code class="dprevCode">$1</code>`);
  // bold/italic/underline/strike (order matters)
  s = s.replace(/\*\*([^*]+)\*\*/g, `<strong>$1</strong>`);
  s = s.replace(/__([^_]+)__/g, `<u>$1</u>`);
  s = s.replace(/~~([^~]+)~~/g, `<s>$1</s>`);
  s = s.replace(/\*([^*\n]+)\*/g, `<em>$1</em>`);
  // blockquote
  s = s.replace(/^&gt;\s?(.*)$/gm, `<div class="dprevQuote"><div class="dprevQuoteBar"></div><div class="dprevQuoteText">$1</div></div>`);
  // newlines
  s = s.replace(/\n/g, `<br>`);
  // very small linkify
  s = s.replace(/(https?:\/\/[^\s<]+)/g, `<a class="dprevLink" href="$1" target="_blank" rel="noreferrer">$1</a>`);
  return s;
}

function _dprevReplaceVars(s){
  // example values
  const mention = `<span class="dprevMention">@User</span>`;
  const user = `User`;
  const server = `Server`;
  return (s || "")
    .replaceAll("{mention}", mention)
    .replaceAll("{user}", user)
    .replaceAll("{server}", server);
}

function updateWelcomePreview(){
  const wrap = $("wel_preview");
  if(!wrap) return;

  const text = $("wel_text")?.value ?? "";
  const footer = $("wel_footer")?.value ?? "";
  const rowsRaw = $("wel_rows")?.value ?? "[]";

  let rows = [];
  try{ rows = JSON.parse(rowsRaw || "[]"); }catch(e){
    wrap.innerHTML = `<div class="dprevError">Ошибка JSON в rows</div>`;
    return;
  }
  if(!Array.isArray(rows)) rows = [];

  // message header
  const botName = "Mancera FamQ | Assistant";
  const timeText = new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"});
  const mainText = _dprevReplaceVars(text.trim());
  const mainHtml = mainText ? `<div class="dprevContentText">${_dprevMd(mainText)}</div>` : "";

  // rows render
  let body = "";
  for(const r of rows){
    if(!r || typeof r !== "object") continue;
    const type = String(r.type||"").toLowerCase();

    if(type === "separator"){
      body += `<div class="dprevSep"></div>`;
      continue;
    }
    if(type === "heading"){
      body += `<div class="dprevHeading">${_dprevMd(_dprevReplaceVars(r.text||""))}</div>`;
      continue;
    }
    if(type === "section"){
      const txt = _dprevMd(_dprevReplaceVars(r.text||""));
      let btn = "";
      if(r.button){
        const lbl = _dprevEscape(r.button.label || "Кнопка");
        const emoji = r.button.emoji ? `<span class="dprevBtnEmoji">${_dprevEscape(r.button.emoji)}</span>` : "";
        const ext = r.button.url ? `<span class="dprevBtnExt">↗</span>` : "";
        btn = `<button class="dprevBtn" type="button">${emoji}<span>${lbl}</span>${ext}</button>`;
      }
      body += `<div class="dprevRowSection"><div class="dprevRowSectionText">${txt}</div>${btn}</div>`;
      continue;
    }
    if(type === "image"){
      const url = String(r.url||"").trim();
      if(url){
        body += `<img class="dprevImage" src="${_dprevEscape(url)}" alt="">`;
      }
      continue;
    }
  }

  const footerHtml = footer.trim() ? `<div class="dprevFooter">${_dprevMd(_dprevReplaceVars(footer.trim()))}</div>` : "";

  wrap.innerHTML = `
    <div class="dprevMsg">
      <div class="dprevAvatar">M</div>
      <div class="dprevRight">
        <div class="dprevHeader">
          <span class="dprevName">${botName}</span>
          <span class="dprevBadge">BOT</span>
          <span class="dprevTime">${timeText}</span>
        </div>
        <div class="dprevBubble">
          ${mainHtml}
          ${body}
          ${footerHtml}
        </div>
      </div>
    </div>
  `;
}

function bindWelcomePreview(){
  $("wel_text")?.addEventListener("input", updateWelcomePreview);
  $("wel_footer")?.addEventListener("input", updateWelcomePreview);
  $("wel_rows")?.addEventListener("input", updateWelcomePreview);
  updateWelcomePreview();
}

// inject CSS once
(function(){
  if(document.getElementById("dprevStyles")) return;
  const st = document.createElement("style");
  st.id = "dprevStyles";
  st.textContent = `
  .dprevWrap{background:transparent}
  .dprevMsg{display:flex;gap:12px;align-items:flex-start}
  .dprevAvatar{
    width:40px;height:40px;border-radius:50%;
    background:#111214;border:1px solid rgba(255,255,255,.08);
    display:flex;align-items:center;justify-content:center;
    color:#fff;font-weight:700;user-select:none;
    font-family:"gg sans","Whitney","Helvetica Neue",Arial,sans-serif;
  }
  .dprevRight{flex:1;min-width:0}
  .dprevHeader{display:flex;align-items:center;gap:8px;margin:2px 0 6px 0}
  .dprevName{
    color:#f2f3f5;font-weight:600;
    font-family:"gg sans","Whitney","Helvetica Neue",Arial,sans-serif;
  }
  .dprevBadge{
    font-size:11px;font-weight:700;
    padding:2px 6px;border-radius:6px;
    background:#5865F2;color:#fff;
    letter-spacing:.02em;
  }
  .dprevTime{color:#949BA4;font-size:12px}
  .dprevBubble{
    background:#2b2d31;
    border:1px solid rgba(255,255,255,.06);
    border-radius:10px;
    padding:12px 14px;
    color:#DBDEE1;
    font-family:"gg sans","Whitney","Helvetica Neue",Arial,sans-serif;
    line-height:1.35;
  }
  .dprevContentText{margin-bottom:10px}
  .dprevMention{
    background:rgba(88,101,242,.15);
    color:#c9cdfb;
    padding:0 4px;border-radius:4px;
    font-weight:500;
  }
  .dprevSep{height:1px;background:rgba(255,255,255,.08);margin:10px 0}
  .dprevHeading{font-weight:700;margin:6px 0 4px 0}
  .dprevRowSection{
    display:flex;align-items:center;justify-content:space-between;
    gap:12px;
    margin:6px 0;
  }
  .dprevRowSectionText{flex:1;min-width:0}
  .dprevBtn{
    display:inline-flex;align-items:center;gap:8px;
    background:#5865F2;border:none;color:#fff;
    padding:8px 12px;border-radius:8px;
    font-weight:600;cursor:pointer;
    white-space:nowrap;
  }
  .dprevBtn:hover{filter:brightness(.95)}
  .dprevBtnEmoji{font-size:16px;line-height:1}
  .dprevBtnExt{opacity:.9}
  .dprevImage{
    width:100%;
    max-height:420px;
    object-fit:cover;
    border-radius:8px;
    margin-top:10px;
    background:#1e1f22;
    border:1px solid rgba(255,255,255,.06);
  }
  .dprevFooter{
    margin-top:10px;
    color:#B5BAC1;
    font-size:12px;
  }
  .dprevLink{color:#00A8FC;text-decoration:none}
  .dprevLink:hover{text-decoration:underline}
  .dprevCode{
    background:#1e1f22;padding:2px 4px;border-radius:4px;
    font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace;
    font-size:.95em;
  }
  .dprevCodeblock{
    margin:8px 0;padding:10px 12px;border-radius:6px;
    background:#1e1f22;overflow:auto;
    font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace;
    font-size:12px;
  }
  .dprevQuote{display:flex;gap:10px;margin:6px 0}
  .dprevQuoteBar{width:4px;border-radius:2px;background:rgba(255,255,255,.14)}
  .dprevQuoteText{flex:1;min-width:0}
  .dprevError{padding:10px 12px;border-radius:8px;background:rgba(255,77,77,.12);color:#ffb4b4}
  `;
  document.head.appendChild(st);
})();


// ---------- infoaudit ----------
function renderInfoauditForm(d){
  const data = JSON.parse(JSON.stringify(d||{}));
  data.panel = data.panel || {};
  data.panel.title = data.panel.title || "Анкета участника";
  data.panel.description = data.panel.description || "Нажми кнопку ниже, чтобы заполнить данные. Ник обновится автоматически.";
  data.panel.image_url = data.panel.image_url || "";
  data.logs = data.logs || {};
  data.logs.channel_id = data.logs.channel_id || "";
  data.nickname = data.nickname || {};
  data.nickname.template = data.nickname.template || "{first_word(server_name)} | {rl_name} | {static_id}";

  const content = $("content");
  content.innerHTML = `
    <div class="sectionTitle">Панель анкеты</div>
    <div class="fieldGrid">
      ${inputField("Заголовок", "ia_title", data.panel.title)}
      ${inputField("URL картинки (опционально)", "ia_img", data.panel.image_url)}
      ${textareaField("Описание", "ia_desc", data.panel.description)}
      ${channelSelectField("Канал логов", "ia_logs", data.logs.channel_id)}
    </div>

    <div class="hr"></div>
    <div class="sectionTitle">Никнейм</div>
    <div class="fieldGrid">
      ${inputField("Шаблон ника", "ia_tpl", data.nickname.template, "text")}
    </div>

    <div class="hr"></div>
    <div class="smallNote">Если у тебя есть дополнительные ключи в конфиге infoaudit — они не удалятся, пока ты их не сотрёшь вручную. (Можно включить полный редактор позже.)</div>
  `;
}

function collectInfoaudit(){
  return {
    panel: {
      title: $("ia_title").value.trim() || "Анкета участника",
      description: $("ia_desc").value.trim() || "",
      image_url: $("ia_img").value.trim() || ""
    },
    logs: { channel_id: snowflakeStr($("ia_logs").value) || "" },
    nickname: { template: $("ia_tpl").value.trim() || "{first_word(server_name)} | {rl_name} | {static_id}" }
  };
}

// ---------- discohook_local (basic) ----------
function renderDiscohookLocalForm(d){
  const data = JSON.parse(JSON.stringify(d||{}));
  data.host = data.host || "0.0.0.0";
  data.port = data.port || 8787;
  data.api_secret = data.api_secret || "";
  const content = $("content");
  content.innerHTML = `
    <div class="sectionTitle">Discohook Local</div>
    <div class="fieldGrid">
      ${inputField("Host", "dl_host", data.host)}
      ${inputField("Port", "dl_port", data.port, "number")}
      ${inputField("API Secret (опц.)", "dl_secret", data.api_secret, "text")}
    </div>
    <div class="smallNote">Этот модуль поднимает сайт. Dashboard подключается к нему автоматически.</div>
  `;
}
function collectDiscohookLocal(){
  return {
    host: $("dl_host").value.trim() || "0.0.0.0",
    port: Number($("dl_port").value||8787) || 8787,
    api_secret: $("dl_secret").value.trim() || ""
  };
}

// ---------- souz ----------
function renderSouzForm(d){
  const data = JSON.parse(JSON.stringify(d||{}));
  data.enabled = (data.enabled !== false);
  data.main_guild_id = data.main_guild_id || "";
  data.log_channel_id = data.log_channel_id || "";
  data.log_mode = data.log_mode || "failed"; // all | failed
  data.main_manage = data.main_manage || {};
  data.main_manage.kick_if_unverified = (data.main_manage.kick_if_unverified === true);
  data.main_manage.kick_grace_seconds = Number(data.main_manage.kick_grace_seconds || 600) || 600;

  const content = $("content");
  content.innerHTML = `
    <div class="sectionTitle">Основное</div>
    <div class="fieldGrid">
      ${switchField("Включено", "sz_enabled", data.enabled)}
      ${inputField("Main guild id (где бот выдаёт роли)", "sz_main_guild", data.main_guild_id, "text", "обычно текущий сервер")}
      ${channelSelectField("Канал логов SOUZ", "sz_log_ch", data.log_channel_id)}
      <div class="field">
        <label>Режим логов</label>
        <select class="select2" id="sz_log_mode">
          <option value="failed" ${data.log_mode==="failed"?"selected":""}>Только кто НЕ прошёл</option>
          <option value="all" ${data.log_mode==="all"?"selected":""}>Все (и прошли, и нет)</option>
        </select>
      </div>
    </div>

    <div class="hr"></div>
    <div class="sectionTitle">Кик за отсутствие доступа</div>
    <div class="fieldGrid">
      ${switchField("Кикать после grace", "sz_kick", data.main_manage.kick_if_unverified)}
      ${inputField("Grace (сек)", "sz_grace", data.main_manage.kick_grace_seconds, "number")}
    </div>

    <div class="hr"></div>
    <div class="sectionTitle">Источники / whitelist (расширенно)</div>
    <div class="smallNote">Тут сложная логика (несколько серверов-источников). Пока редактируется JSON-ом.</div>
    <div class="field">
      <label>Advanced config (JSON)</label>
      <textarea class="textarea" id="sz_adv">${escapeHtml(JSON.stringify(data, null, 2))}</textarea>
    </div>
  `;
}

function collectSouz(){
  // basic
  const enabled = !!$("sz_enabled").checked;
  const main_guild_id = snowflakeStr($("sz_main_guild").value) || "";
  const log_channel_id = snowflakeStr($("sz_log_ch").value) || "";
  const log_mode = $("sz_log_mode").value || "failed";
  const kick_if_unverified = !!$("sz_kick").checked;
  const grace = Number($("sz_grace").value||600) || 600;

  // advanced JSON to keep other keys
  const advRaw = $("sz_adv").value.trim();
  const adv = parseJsonSafe(advRaw, null);
  if(adv === null || typeof adv !== "object"){
    toast("Advanced config JSON неверный", false);
    return null;
  }
  adv.enabled = enabled;
  adv.main_guild_id = main_guild_id ? Number(main_guild_id) : 0;
  adv.log_channel_id = log_channel_id ? Number(log_channel_id) : 0;
  adv.log_mode = log_mode;
  adv.main_manage = adv.main_manage || {};
  adv.main_manage.kick_if_unverified = kick_if_unverified;
  adv.main_manage.kick_grace_seconds = grace;

  return adv;
}

// ---------- requests (visual builder) ----------
function renderRequestsForm(d){

  const data = JSON.parse(JSON.stringify(d||{}));
  data.enabled = (data.enabled !== false);

  // types
  data.types = Array.isArray(data.types) ? data.types : [];

  // panels (multi)
  const legacy = data.panel || {};
  const panelsIn = Array.isArray(data.panels) && data.panels.length ? data.panels : [legacy];
  data.panels = panelsIn.map((p, i)=>{
    p = (p && typeof p === "object") ? p : {};
    return {
      id: String(p.id || p.panel_id || (i===0 ? "default":"panel_"+(i+1))),
      name: String(p.name || p.title || ("Панель "+(i+1))),
      channel_id: p.channel_id || "",
      message_id: p.message_id || "",
      title: p.title || "Подача заявок",
      text: p.text || p.description || "Выберите тип заявки и заполните форму.",
      emoji: p.emoji || "📝",
      cooldown_seconds: Number(p.cooldown_seconds || 30) || 30,
      image_url: p.image_url || "",
      mode: (p.mode || "select"),
      type_ids: Array.isArray(p.type_ids) ? p.type_ids : []
    };
  });

  window.__rq_panels = data.panels;
  let activePanelIdx = 0;
  function activePanel(){ return data.panels[activePanelIdx]; }

  const content = $("content");
  content.innerHTML = `
    <div class="sectionTitle">Панели</div>
    <div class="row" style="justify-content:space-between; align-items:center; margin-bottom:10px;">
      <div class="row">
        <button class="btn small primary" id="rq_panel_add">+ Добавить панель</button>
        <button class="btn small" id="rq_panel_dup">Дублировать</button>
        <button class="btn small danger" id="rq_panel_del">Удалить</button>
      </div>
      <div class="row">
        <button class="btn small primary" id="rq_publish_panel">Опубликовать</button>
      </div>
    </div>
    <div class="row" style="gap:12px; align-items:flex-start;">
      <div style="flex:1; min-width:280px;">
        <div class="list" id="rq_panels_list"></div>
        <div class="smallNote" style="margin-top:8px;">Опубликовать можно каждую панель отдельно. Бот запомнит message_id и будет обновлять сообщение.</div>
      </div>
      <div style="flex:2;">
        <div class="fieldGrid">
          ${switchField("Включено (модуль)", "rq_enabled", data.enabled)}
          ${inputField("panel_id (уникальный)", "rq_panel_id", activePanel().id)}
          ${inputField("Название панели", "rq_panel_name", activePanel().name)}
          ${channelSelectField("Канал панели", "rq_panel_ch", activePanel().channel_id)}
          ${inputField("Заголовок панели", "rq_title", activePanel().title)}
          ${inputField("Emoji панели", "rq_emoji", activePanel().emoji)}
          ${inputField("Cooldown (сек)", "rq_cd", activePanel().cooldown_seconds, "number")}
          ${selectField("Вид выбора типа", "rq_mode", [
            ["select","Selection (выпадающий список)"],
            ["buttons","Кнопки"]
          ], activePanel().mode)}
          ${textareaField("Текст панели", "rq_desc", activePanel().text)}
        </div>

        <div class="hr"></div>
        <div class="sectionTitle">Типы в этой панели</div>
        <div class="smallNote">Если ничего не выбрано — панель покажет все типы.</div>
        <div class="field">
          <div class="checkGrid" id="rq_panel_types"></div>
        </div>
      </div>
    </div>

    <div class="hr"></div>
    <div class="sectionTitle">Типы заявок</div>
    <div class="row">
      <button class="btn small primary" id="rq_add_type">+ Добавить тип</button>
      <span class="badge">До 5 вопросов в типе</span>
      <span class="badge">Поле-image можно сделать обязательным/необязательным</span>
    </div>

    <div class="list" id="rq_types_list"></div>

    <div class="hr"></div>
    <div class="sectionTitle">Для продвинутых</div>
    <div class="smallNote">Если надо — можно руками поправить JSON типов ниже (не обязательно).</div>
    <div class="field">
      <label>types (JSON)</label>
      <textarea class="textarea" id="rq_types_raw">${escapeHtml(JSON.stringify(data.types, null, 2))}</textarea>
    </div>
  `;

  // render panels list + editor bindings
  function renderPanelsList(){
    const box = $("rq_panels_list");
    box.innerHTML = "";
    data.panels.forEach((p, idx)=>{
      const item = document.createElement("div");
      item.className = "listItem" + (idx===activePanelIdx ? " active":"");
      item.dataset.pid = p.id;
      item.innerHTML = `<div class="row" style="justify-content:space-between; width:100%;">
        <div><b>${escapeHtml(p.name||p.id)}</b> <span class="badge">${escapeHtml(p.id)}</span></div>
        <div class="smallNote">${p.channel_id ? "#"+escapeHtml(String(p.channel_id).slice(-6)) : "канал не выбран"}</div>
      </div>`;
      item.onclick = ()=>{
        activePanelIdx = idx;
        // update fields without full rerender
        $("rq_panel_id").value = activePanel().id;
        $("rq_panel_name").value = activePanel().name;
        $("rq_panel_ch").value = String(activePanel().channel_id||"");
        $("rq_title").value = activePanel().title;
        $("rq_emoji").value = activePanel().emoji;
        $("rq_cd").value = String(activePanel().cooldown_seconds||30);
        $("rq_mode").value = activePanel().mode || "select";
        $("rq_desc").value = activePanel().text || "";
        renderPanelsList();
        renderPanelTypes();
      };
      box.appendChild(item);
    });
  }

  function renderPanelTypes(){
    const box = $("rq_panel_types");
    box.innerHTML = "";
    const p = activePanel();
    const selected = new Set((p.type_ids||[]).map(String));
    // list all enabled types by current data.types (not filtered by enabled)
    data.types.forEach((t)=>{
      const tid = String(t.type_id||"").trim();
      if(!tid) return;
      const label = String(t.title || tid);
      const id = "rq_pt_"+tid.replace(/[^a-zA-Z0-9_]/g,"_");
      const checked = selected.has(tid);
      const el = document.createElement("label");
      el.className = "checkItem";
      el.innerHTML = `<input type="checkbox" id="${id}" ${checked?"checked":""}/> <span>${escapeHtml(label)}</span>`;
      el.querySelector("input").addEventListener("change", (e)=>{
        if(e.target.checked) selected.add(tid); else selected.delete(tid);
        p.type_ids = Array.from(selected);
      });
      box.appendChild(el);
    });

    // helper button: clear selection (all types)
    const clear = document.createElement("div");
    clear.style.marginTop = "8px";
    clear.innerHTML = `<button class="btn small" id="rq_pt_clear">Показывать все типы</button>`;
    box.appendChild(clear);
    $("rq_pt_clear").onclick = ()=>{
      p.type_ids = [];
      renderPanelTypes();
    };
  }

  renderPanelsList();
  renderPanelTypes();

  // panel add/dup/del
  $("rq_panel_add").onclick = ()=>{
    const n = data.panels.length + 1;
    data.panels.push({
      id: "panel_"+n,
      name: "Панель "+n,
      channel_id: "",
      message_id: "",
      title: "Подача заявок",
      text: "Выберите тип заявки и заполните форму.",
      emoji: "📝",
      cooldown_seconds: 30,
      image_url: "",
      mode: "select",
      type_ids: []
    });
    activePanelIdx = data.panels.length-1;
    // refresh fields
    $("rq_panel_id").value = activePanel().id;
    $("rq_panel_name").value = activePanel().name;
    $("rq_panel_ch").value = "";
    $("rq_title").value = activePanel().title;
    $("rq_emoji").value = activePanel().emoji;
    $("rq_cd").value = "30";
    $("rq_mode").value = "select";
    $("rq_desc").value = activePanel().text;
    renderPanelsList();
    renderPanelTypes();
  };

  $("rq_panel_dup").onclick = ()=>{
    const src = activePanel();
    const n = data.panels.length + 1;
    const copy = JSON.parse(JSON.stringify(src));
    copy.id = "panel_"+n;
    copy.name = (src.name || "Панель") + " (копия)";
    copy.message_id = "";
    data.panels.push(copy);
    activePanelIdx = data.panels.length-1;
    $("rq_panel_id").value = activePanel().id;
    $("rq_panel_name").value = activePanel().name;
    $("rq_panel_ch").value = String(activePanel().channel_id||"");
    $("rq_title").value = activePanel().title;
    $("rq_emoji").value = activePanel().emoji;
    $("rq_cd").value = String(activePanel().cooldown_seconds||30);
    $("rq_mode").value = activePanel().mode || "select";
    $("rq_desc").value = activePanel().text || "";
    renderPanelsList();
    renderPanelTypes();
  };

  $("rq_panel_del").onclick = ()=>{
    if(data.panels.length <= 1){
      toast("Нельзя удалить последнюю панель", false);
      return;
    }
    data.panels.splice(activePanelIdx, 1);
    activePanelIdx = 0;
    $("rq_panel_id").value = activePanel().id;
    $("rq_panel_name").value = activePanel().name;
    $("rq_panel_ch").value = String(activePanel().channel_id||"");
    $("rq_title").value = activePanel().title;
    $("rq_emoji").value = activePanel().emoji;
    $("rq_cd").value = String(activePanel().cooldown_seconds||30);
    $("rq_mode").value = activePanel().mode || "select";
    $("rq_desc").value = activePanel().text || "";
    renderPanelsList();
    renderPanelTypes();
  };

  // bind panel editor fields
  $("rq_panel_id").addEventListener("change", ()=>{
    const v = $("rq_panel_id").value.trim() || activePanel().id;
    activePanel().id = v;
    renderPanelsList();
  });
  $("rq_panel_name").addEventListener("input", ()=>{
    activePanel().name = $("rq_panel_name").value;
    // update list label without rerendering full form
    renderPanelsList();
  });
  $("rq_panel_ch").addEventListener("change", ()=>{
    activePanel().channel_id = snowflakeStr($("rq_panel_ch").value) || "";
    renderPanelsList();
  });
  $("rq_title").addEventListener("input", ()=>{ activePanel().title = $("rq_title").value; });
  $("rq_emoji").addEventListener("input", ()=>{ activePanel().emoji = $("rq_emoji").value; });
  $("rq_cd").addEventListener("change", ()=>{ activePanel().cooldown_seconds = Number($("rq_cd").value||30)||30; });
  $("rq_desc").addEventListener("input", ()=>{ activePanel().text = $("rq_desc").value; });
  $("rq_mode").addEventListener("change", ()=>{ activePanel().mode = $("rq_mode").value; });

  // publish panel button
  const pubBtn = $("rq_publish_panel");
  if(pubBtn){
    pubBtn.onclick = async ()=>{
      if(!activeGuildId){
        toast("Выбери сервер сверху справа", false);
        return;
      }
      const updated = collectRequests();
      if(updated === null) return;
      try{
        await api("/dashboard_api/config/save", {
          method:"POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({ module:"requests", guild_id: activeGuildId || null, data: updated })
        });
      }catch(e){
        toast("Ошибка сохранения перед публикацией: " + e.message, false);
        return;
      }
      try{
        await api("/dashboard_api/requests/panel/publish", {
          method:"POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({ guild_id: activeGuildId, panel_id: activePanel().id })
        });
        toast("Панель опубликована ✅", true);
      }catch(e){
        toast("Не удалось опубликовать: " + e.message, false);
      }
    };
  }

  $("rq_add_type").onclick = ()=>{
    data.types.push(makeDefaultType());
    renderTypesList(data.types);
    $("rq_types_raw").value = JSON.stringify(data.types, null, 2);
    renderPanelTypes();
  };

  renderTypesList(data.types);

  $("rq_types_raw").addEventListener("input", ()=>{
    const parsed = parseJsonSafe($("rq_types_raw").value, null);
    if(parsed && Array.isArray(parsed)){
      data.types = parsed;
      renderTypesList(data.types);
      renderPanelTypes();
    }
  });

function renderTypesList(types){
    const box = $("rq_types_list");
    box.innerHTML = "";
    types.forEach((t, idx)=>{
      const type_id = t.type_id || `type_${idx+1}`;
      const title = t.title || "Новый тип";
      const card = document.createElement("div");
      card.className = "cardMini";
      card.innerHTML = `
        <div class="row" style="justify-content:space-between">
          <div class="cardMiniTitle">${escapeHtml(title)} <span class="badge">${escapeHtml(type_id)}</span></div>
          <div class="row">
            <button class="btn small" data-act="dup">Дублировать</button>
            <button class="btn small danger" data-act="del">Удалить</button>
          </div>
        </div>

        <div class="fieldGrid">
          ${inputField("type_id (уникальный)", `t_${idx}_id`, type_id, "text", "например: resign")}
          ${inputField("Название", `t_${idx}_title`, title)}
          ${textareaField("Описание", `t_${idx}_desc`, t.description || "")}
          ${channelSelectField("Канал куда отправлять заявку", `t_${idx}_target`, t.target_channel_id || "")}
          ${channelSelectField("Канал логов", `t_${idx}_log`, t.log_channel_id || "")}
        </div>

        <div class="hr"></div>
        <div class="sectionTitle">Кто проверяет (роли)</div>
        ${rolesMultiSelect("Роли staff", `t_${idx}_roles`, Array.isArray(t.reviewer_role_ids)?t.reviewer_role_ids:[])}

        <div class="hr"></div>
        <div class="sectionTitle">Вопросы (до 5)</div>
        <div class="list" id="fields_${idx}"></div>
        <div class="row">
          <button class="btn small primary" id="addField_${idx}">+ Добавить вопрос</button>
        </div>
        <div class="smallNote">kind=text — обычный текст; kind=image — загрузка фото (можно сделать обязательной/необязательной).</div>
      `;
      box.appendChild(card);

      card.querySelector('[data-act="del"]').onclick = ()=>{
        types.splice(idx,1);
        renderTypesList(types);
        $("rq_types_raw").value = JSON.stringify(types, null, 2);
      };
      card.querySelector('[data-act="dup"]').onclick = ()=>{
        const clone = JSON.parse(JSON.stringify(t));
        clone.type_id = (clone.type_id || "type") + "_copy";
        types.splice(idx+1,0,clone);
        renderTypesList(types);
        $("rq_types_raw").value = JSON.stringify(types, null, 2);
      };

      // fields
      t.fields = Array.isArray(t.fields) ? t.fields : [];
      renderFields(idx, t.fields);

      $("addField_"+idx).onclick = ()=>{
        t.fields = Array.isArray(t.fields) ? t.fields : [];
        if(t.fields.length >= 5){
          toast("Максимум 5 вопросов", false);
          return;
        }
        t.fields.push({ key:`q${t.fields.length+1}`, label:`Вопрос ${t.fields.length+1}`, kind:"text", required:true });
        renderFields(idx, t.fields);
        $("rq_types_raw").value = JSON.stringify(types, null, 2);
      };

      // input bindings
      const bind = (id, fn)=>{
        const el = $(id);
        el.addEventListener("input", ()=>{
          fn(el);
          $("rq_types_raw").value = JSON.stringify(types, null, 2);
        });
        el.addEventListener("change", ()=>{
          fn(el);
          $("rq_types_raw").value = JSON.stringify(types, null, 2);
          // update card header after user finishes editing
          renderTypesList(types);
        });
      };

      bind(`t_${idx}_id`, (el)=>{ t.type_id = el.value.trim(); });
      bind(`t_${idx}_title`, (el)=>{ t.title = el.value.trim(); });
      bind(`t_${idx}_desc`, (el)=>{ t.description = el.value; });
      bind(`t_${idx}_target`, (el)=>{ t.target_channel_id = el.value; });
      bind(`t_${idx}_log`, (el)=>{ t.log_channel_id = el.value; });

      // roles
      const rolesSel = $(`t_${idx}_roles`);
      rolesSel.addEventListener("change", ()=>{
        t.reviewer_role_ids = Array.from(rolesSel.selectedOptions).map(o=>o.value);
        $("rq_types_raw").value = JSON.stringify(types, null, 2);
      });
    });
  }

  function renderFields(typeIdx, fields){
    const box = $(`fields_${typeIdx}`);
    box.innerHTML = "";
    fields.forEach((f, i)=>{
      const card = document.createElement("div");
      card.className = "cardMini";
      const kind = f.kind || "text";
      const required = (f.required !== false);
      card.innerHTML = `
        <div class="row" style="justify-content:space-between">
          <div class="badge">${escapeHtml(f.key || ("q"+(i+1)))}</div>
          <button class="btn small danger" id="delF_${typeIdx}_${i}">Удалить</button>
        </div>
        <div class="fieldGrid">
          ${inputField("Ключ (key)", `f_${typeIdx}_${i}_key`, f.key || ("q"+(i+1)))}
          ${inputField("Текст вопроса", `f_${typeIdx}_${i}_label`, f.label || ("Вопрос "+(i+1)))}
          <div class="field">
            <label>Тип поля (kind)</label>
            <select class="select2" id="f_${typeIdx}_${i}_kind">
              <option value="text" ${kind==="text"?"selected":""}>text</option>
              <option value="image" ${kind==="image"?"selected":""}>image</option>
            </select>
          </div>
          ${switchField("Обязательное", `f_${typeIdx}_${i}_req`, required)}
        </div>
      `;
      box.appendChild(card);

      $(`delF_${typeIdx}_${i}`).onclick = ()=>{
        fields.splice(i,1);
        renderFields(typeIdx, fields);
        $("rq_types_raw").value = JSON.stringify(data.types, null, 2);
      };

      const bind = (id, fn)=>{
        const el = $(id);
        el.addEventListener("input", ()=>{ fn(el); $("rq_types_raw").value = JSON.stringify(data.types, null, 2); });
        el.addEventListener("change", ()=>{ fn(el); $("rq_types_raw").value = JSON.stringify(data.types, null, 2); });
      };

      bind(`f_${typeIdx}_${i}_key`, (el)=>{ f.key = el.value.trim(); });
      bind(`f_${typeIdx}_${i}_label`, (el)=>{ f.label = el.value; });
      bind(`f_${typeIdx}_${i}_kind`, (el)=>{ f.kind = el.value; });
      const reqEl = $(`f_${typeIdx}_${i}_req`);
      reqEl.addEventListener("change", ()=>{ f.required = !!reqEl.checked; $("rq_types_raw").value = JSON.stringify(data.types, null, 2); });
    });
  }

  function makeDefaultType(){
    const n = data.types.length + 1;
    return {
      type_id: `type_${n}`,
      title: `Тип заявки ${n}`,
      description: "",
      reviewer_role_ids: [],
      fields: [
        { key:"q1", label:"Ваше имя", kind:"text", required:true }
      ],
      target_channel_id: "",
      log_channel_id: ""
    };
  }
}

function collectRequests(){
  const enabled = !!$("rq_enabled").checked;

  // panels from runtime state
  const panels = Array.isArray(window.__rq_panels) ? window.__rq_panels : [];
  if(!panels.length){
    toast("Нужна хотя бы 1 панель", false);
    return null;
  }
  for(const p of panels){
    if(!p.id || !String(p.id).trim()){
      toast("У каждой панели должен быть panel_id", false);
      return null;
    }
    p.id = String(p.id).trim();
    p.name = String(p.name || p.id);
    p.channel_id = snowflakeStr(p.channel_id) || "";
    p.title = String(p.title || "Подача заявок");
    p.text = String(p.text || "");
    p.emoji = String(p.emoji || "📝");
    p.cooldown_seconds = Number(p.cooldown_seconds || 30) || 30;
    p.mode = (p.mode || "select");
    p.type_ids = Array.isArray(p.type_ids) ? p.type_ids : [];
  }

  // types (prefer raw json)
  const types = parseJsonSafe($("rq_types_raw").value, null);
  if(types === null || !Array.isArray(types)){
    toast("types JSON неверный (должен быть массив)", false);
    return null;
  }
  for(const t of types){
    if(!t.type_id || !String(t.type_id).trim()){
      toast("У каждого типа должен быть type_id", false);
      return null;
    }
    if(t.fields && Array.isArray(t.fields) && t.fields.length > 5){
      toast("В типе максимум 5 вопросов", false);
      return null;
    }
  }

  // preserve other keys if they exist
  const out = JSON.parse(JSON.stringify(currentData || {}));
  out.enabled = enabled;
  out.panels = panels;
  // legacy compat
  out.panel = panels[0];
  out.types = types;
  return out;
}

// boot
init().catch(e=>{
  console.error(e);
  toast("Ошибка загрузки: " + e.message, false);
});
