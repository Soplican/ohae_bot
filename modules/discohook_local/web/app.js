const el = (id)=>document.getElementById(id);

const tabVisual = el("tabVisual");
const tabJson = el("tabJson");
const panelVisual = el("panelVisual");
const panelJson = el("panelJson");

const modeEl = el("mode");

const guildSelect = el("guildSelect"); // hidden
const guildDropdownBtn = el("guildDropdownBtn");
const guildDropdownMenu = el("guildDropdownMenu");
const guildDropdownList = el("guildDropdownList");
const guildSearch = el("guildSearch");
const guildBanner = el("guildBanner");

const channelSelect = el("channelSelect"); // hidden
const channelDropdownBtn = el("channelDropdownBtn");
const channelDropdownMenu = el("channelDropdownMenu");

const channelIdEl = el("channelId");
const webhookUrlEl = el("webhookUrl");

const vContentEl = el("v_content");
const vUsernameEl = el("v_username");
const vAvatarEl = el("v_avatar");

const payloadEl = el("payload");
const resultEl = el("result");
const resultEl2 = el("result2");

const pNameEl = el("p_name");
const pAvatarEl = el("p_avatar");
const pContentEl = el("p_content");
const pEmbedsEl = el("p_embeds");
const pButtonsEl = el("p_buttons");

// Элементы шапки
const userDisplay = el("userDisplay");
const logoutBtn = el("logoutBtn");

let BOT_META = {name:"Bot", avatar:""};
let embedsState = [];
let buttonsState = [];

let GUILDS = [];     // [{id,name,icon_url,banner_url}]
let CHANNEL_GROUPS = []; // [{category_name, channels:[{id,name}]}]
let COLLAPSE = {};   // category_name -> bool collapsed

const LS_LAST_GUILD = "dl_last_guild";
const LS_LAST_CHAN  = "dl_last_channel";
const LS_FAVS       = "dl_fav_guilds";
const LS_COLLAPSE   = "dl_collapse";

function loadFavs(){
  try{ return new Set(JSON.parse(localStorage.getItem(LS_FAVS) || "[]")); }
  catch(e){ return new Set(); }
}
function saveFavs(set){
  localStorage.setItem(LS_FAVS, JSON.stringify([...set]));
}
function loadCollapse(){
  try{ return JSON.parse(localStorage.getItem(LS_COLLAPSE) || "{}") || {}; }
  catch(e){ return {}; }
}
function saveCollapse(obj){
  localStorage.setItem(LS_COLLAPSE, JSON.stringify(obj));
}

function setResult(ok, txt){
  const msg = (ok ? "OK: " : "ERR: ") + txt;
  resultEl.textContent = msg;
  resultEl2.textContent = msg;
}

function showTab(which){
  if(which === "visual"){
    panelVisual.classList.remove("hidden");
    panelJson.classList.add("hidden");
    tabVisual.classList.add("active");
    tabJson.classList.remove("active");
  }else{
    panelVisual.classList.add("hidden");
    panelJson.classList.remove("hidden");
    tabVisual.classList.remove("active");
    tabJson.classList.add("active");
    renderPreview();
  }
}

tabVisual.addEventListener("click", ()=>showTab("visual"));
tabJson.addEventListener("click", ()=>showTab("json"));

// ---- Обёртка fetch с обработкой 401 ----
async function fetchWithAuth(url, options = {}) {
  const res = await fetch(url, options);
  if (res.status === 401) {
    window.location.href = "/login";
    return null;
  }
  return res;
}

async function loadBotMeta(){
  try{
    const r = await fetchWithAuth("/api/meta");
    if (!r) return;
    const j = await r.json();
    if(j.ok){
      BOT_META.name = j.bot_name || BOT_META.name;
      BOT_META.avatar = j.bot_avatar || "";
    }
  }catch(e){}
}

async function loadUserInfo() {
  try {
    const r = await fetchWithAuth("/api/user");
    if (!r) return;
    const j = await r.json();
    if (j.ok && userDisplay) {
      userDisplay.textContent = `👤 ${j.username}`;
    }
  } catch (e) {}
}

logoutBtn?.addEventListener("click", () => {
  window.location.href = "/logout";
});

function parseJsonSafe(text){
  const s = (text ?? "").trim();
  if(!s) return {};
  try{ return JSON.parse(s); }
  catch(e){
    const endObj = s.lastIndexOf("}");
    const endArr = s.lastIndexOf("]");
    const end = Math.max(endObj, endArr);
    if(end > -1){
      const cut = s.slice(0, end+1);
      return JSON.parse(cut);
    }
    throw e;
  }
}

function parseColorToHex(c){
  if(typeof c === "string"){
    let s = c.trim();
    if(!s) return null;
    if(!s.startsWith("#")) s = "#"+s;
    return s;
  }
  if(typeof c === "number"){
    return "#"+c.toString(16).padStart(6,"0");
  }
  return null;
}

function escapeHtml(s){
  return String(s ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
}

function setChannelBtnLabel(text){
  if(channelDropdownBtn.classList.contains("dropdownBtn")){
    channelDropdownBtn.innerHTML = `
      <div class="channelBtnIcon">#</div>
      <span>${escapeHtml(String(text||"Select channel"))}</span>
    `;
  }else{
    channelDropdownBtn.textContent = text || "Select channel";
  }
}


/* ---------------- Server dropdown: search + favorites + remember + banner ---------------- */
function openGuildMenu(){
  guildDropdownMenu.style.display = "block";
  guildDropdownMenu.classList.add("open");
  guildSearch.value = "";
  renderGuildList("");
  const sel = guildSelect.value || localStorage.getItem(LS_LAST_GUILD) || "";
  if(sel){
    const node = guildDropdownList.querySelector(`[data-gid="${sel}"]`);
    if(node) node.scrollIntoView({block:"center"});
  }
  guildSearch.focus();
}

function closeGuildMenu(){ guildDropdownMenu.style.display = "none";
  guildDropdownMenu.classList.remove("open"); }

guildDropdownBtn.addEventListener("click", (e)=>{
  e.stopPropagation();
  const open = guildDropdownMenu.style.display === "block";
  if(open) closeGuildMenu(); else openGuildMenu();
});

document.addEventListener("click", (e)=>{
  const t = e.target;
  const inGuild = guildDropdownBtn.contains(t) || guildDropdownMenu.contains(t);
  const inChan = channelDropdownBtn.contains(t) || channelDropdownMenu.contains(t);
  if(!inGuild) closeGuildMenu();
  if(!inChan) channelDropdownMenu.style.display = "none";
  channelDropdownMenu.classList.remove("open");
});

guildSearch.addEventListener("input", ()=>{
  renderGuildList(guildSearch.value || "");
});

function setBanner(url){
  if(url){
    guildBanner.src = url;
    guildBanner.style.display = "block";
  }else{
    guildBanner.removeAttribute("src");
    guildBanner.style.display = "none";
  }
}

function selectGuild(g){
  guildSelect.value = g.id;
  guildDropdownBtn.innerHTML = `
    <div class="dropdownBtnIcon">
      ${g.icon_url ? `<img src="${g.icon_url}">` : g.name[0]}
    </div>
    <span>${g.name}</span>
  `;
  localStorage.setItem(LS_LAST_GUILD, g.id);
  if(g.banner_url){
    guildBanner.src = g.banner_url;
    guildBanner.style.display = "block";
  }else{
    guildBanner.style.display = "none";
  }
  closeGuildMenu();
}

function renderGuildList(filter){
  const f = (filter||"").trim().toLowerCase();
  const favs = loadFavs();

  const list = (GUILDS || []).filter(g=>{
    if(!f) return true;
    return (g.name || "").toLowerCase().includes(f);
  }).sort((a,b)=>{
    const af = favs.has(a.id) ? 0 : 1;
    const bf = favs.has(b.id) ? 0 : 1;
    if(af !== bf) return af - bf;
    return (a.name||"").localeCompare(b.name||"");
  });

  guildDropdownList.innerHTML = "";
  list.forEach(g=>{
    const row = document.createElement("div");
    row.className = "dropdownItem";
    row.dataset.gid = g.id;

    const icon = document.createElement("div");
    icon.className = "dropdownIcon";
    if(g.icon_url){
      const img = document.createElement("img");
      img.src = String(g.icon_url);
      img.alt = "icon";
      icon.appendChild(img);
    }

    const name = document.createElement("div");
    name.textContent = g.name;

    const star = document.createElement("button");
    star.type = "button";
    star.className = "starBtn" + (favs.has(g.id) ? " on" : "");
    star.textContent = "★";
    star.onclick = (ev)=>{
      ev.stopPropagation();
      const s = loadFavs();
      if(s.has(g.id)) s.delete(g.id); else s.add(g.id);
      saveFavs(s);
      renderGuildList(guildSearch.value || "");
    };

    const rowWrap = document.createElement("div");
    rowWrap.className = "dropdownRow";
    const left = document.createElement("div");
    left.style.display = "flex";
    left.style.gap = "10px";
    left.style.alignItems = "center";
    left.appendChild(icon);
    left.appendChild(name);
    rowWrap.appendChild(left);
    rowWrap.appendChild(star);

    row.appendChild(rowWrap);

    row.onclick = async ()=>{
      selectGuild(g);
      await loadChannels(g.id);
      syncFromForm();
    };

    guildDropdownList.appendChild(row);
  });
}

async function initGuilds(){
  try{
    const r = await fetchWithAuth("/api/guilds");
    if (!r) return;
    const j = await r.json();
    if(!j.ok) return;
    GUILDS = j.guilds || [];

    guildSelect.innerHTML = "";
    GUILDS.forEach(g=>{
      const opt = document.createElement("option");
      opt.value = g.id;
      opt.textContent = g.name;
      guildSelect.appendChild(opt);
    });

    const last = localStorage.getItem(LS_LAST_GUILD);
    const pick = (last && GUILDS.find(x=>x.id===last)) || GUILDS[0];
    if(pick){
      selectGuild(pick);
      await loadChannels(pick.id);
    }else{
      guildDropdownBtn.innerHTML = `
  <div class="dropdownBtnIcon"></div>
  <span>Select server</span>
`;
      setBanner("");
      setChannelBtnLabel("Select channel");
      channelSelect.innerHTML = "";
      CHANNEL_GROUPS = [];
    }
  }catch(e){}
}

/* ---------------- Channels dropdown: categories collapse + remember ---------------- */
function openChannelMenu(){
  channelDropdownMenu.style.display = "block";
  channelDropdownMenu.classList.add("open");
  const sel = channelSelect.value || localStorage.getItem(LS_LAST_CHAN) || "";
  if(sel){
    const node = channelDropdownMenu.querySelector(`[data-cid="${sel}"]`);
    if(node) node.scrollIntoView({block:"center"});
  }
}
function closeChannelMenu(){ channelDropdownMenu.style.display = "none";
  channelDropdownMenu.classList.remove("open"); }

channelDropdownBtn.addEventListener("click", (e)=>{
  e.stopPropagation();
  const open = channelDropdownMenu.style.display === "block";
  if(open) closeChannelMenu(); else openChannelMenu();
});

function renderChannelMenu(){
  channelDropdownMenu.innerHTML = "";
  const collapse = COLLAPSE;

  CHANNEL_GROUPS.forEach(gr=>{
    const catName = gr.category_name || "Channels";
    const header = document.createElement("div");
    header.className = "catHeader";
    header.innerHTML = `<span>${escapeHtml(catName)}</span><span class="chev">${collapse[catName] ? "▸" : "▾"}</span>`;
    header.onclick = ()=>{
      collapse[catName] = !collapse[catName];
      saveCollapse(collapse);
      renderChannelMenu();
    };
    channelDropdownMenu.appendChild(header);

    if(!collapse[catName]){
      (gr.channels || []).forEach(c=>{
        const item = document.createElement("div");
        item.className = "channelItem";
        item.dataset.cid = c.id;
        item.innerHTML = `<span class="hash">#</span><span>${escapeHtml(c.name.replace(/^#/, ""))}</span>`;
        item.onclick = ()=>{
          channelSelect.value = c.id;
          setChannelBtnLabel(c.name);
          channelIdEl.value = c.id;
          localStorage.setItem(LS_LAST_CHAN, c.id);
          closeChannelMenu();
          syncFromForm();
        };
        channelDropdownMenu.appendChild(item);
      });
    }
  });
}

async function loadChannels(guildId){
  channelSelect.innerHTML = "";
  setChannelBtnLabel("Select channel");
  channelIdEl.value = "";

  try{
    const r = await fetchWithAuth(`/api/channels?guild_id=${encodeURIComponent(guildId)}`);
    if (!r) return;
    const j = await r.json();
    if(!j.ok) return;

    CHANNEL_GROUPS = j.groups || [];
    COLLAPSE = loadCollapse();

    const flat = [];
    CHANNEL_GROUPS.forEach(gr=>{
      (gr.channels||[]).forEach(c=>flat.push(c));
    });
    flat.forEach(c=>{
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.name;
      channelSelect.appendChild(opt);
    });

    renderChannelMenu();

    const lastChan = localStorage.getItem(LS_LAST_CHAN);
    const pick = (lastChan && flat.find(x=>x.id===lastChan)) || flat[0];
    if(pick){
      channelSelect.value = pick.id;
      setChannelBtnLabel(pick.name);
      channelIdEl.value = pick.id;
    }
  }catch(e){}
}

/* ---------- minimal payload builder ---------- */
function makeEmbedDefault(){
  return {
    title:"", description:"", url:"", color:"#5865F2",
    fields:[], thumbnail:{url:""}, image:{url:""},
    footer:{text:"", icon_url:""},
    _openSections: { author: false, body: false, fields: false, images: false, footer: false }
  };
}
function makeFieldDefault(){ return {name:"", value:"", inline:false}; }
function makeButtonDefault(){ return {type:2, style:2, label:"Button", custom_id:"btn_1", url:"", disabled:false}; }

function cleanEmbed(e){
  const out = {};
  if(e.title) out.title = e.title;
  if(e.description) out.description = e.description;
  if(e.url) out.url = e.url;
  const col = parseColorToHex(e.color);
  if(col) out.color = col;
  const fields = Array.isArray(e.fields) ? e.fields : [];
  if(fields.length){
    out.fields = fields.filter(f=>f.name||f.value).slice(0,25).map(f=>({name:f.name||"\u200b", value:f.value||"\u200b", inline:!!f.inline}));
  }
  if(e.thumbnail?.url) out.thumbnail = {url:e.thumbnail.url};
  if(e.image?.url) out.image = {url:e.image.url};
  if(e.footer && (e.footer.text || e.footer.icon_url)){
    out.footer = {};
    if(e.footer.text) out.footer.text = e.footer.text;
    if(e.footer.icon_url) out.footer.icon_url = e.footer.icon_url;
  }
  return out;
}
function buildComponents(){
  const btns = buttonsState.slice(0,5).map(b=>{
    const out = {type:2, style:Number(b.style ?? 2), label:String(b.label || "Button")};
    if(b.disabled) out.disabled = true;
    if(out.style === 5){ if(b.url) out.url = String(b.url); }
    else out.custom_id = String(b.custom_id || ("btn_"+Math.random().toString(16).slice(2,8)));
    return out;
  });
  if(!btns.length) return undefined;
  return [{type:1, components: btns}];
}

function syncFromForm(){
  const payload = {};
  const content = vContentEl.value || "";
  if(content) payload.content = content;

  if(modeEl.value === "webhook"){
    const uname = vUsernameEl.value || "";
    const av = vAvatarEl.value || "";
    if(uname) payload.username = uname;
    if(av) payload.avatar_url = av;
  }

  const embeds = embedsState.slice(0,10).map(cleanEmbed).filter(e=>Object.keys(e).length);
  if(embeds.length) payload.embeds = embeds;

  const comps = buildComponents();
  if(comps) payload.components = comps;

  payloadEl.value = JSON.stringify(payload, null, 2);
  renderPreview();
}

function syncFormFromPayload(){
  let data;
  try{ data = parseJsonSafe(payloadEl.value); }
  catch(e){ setResult(false, "JSON invalid"); return; }

  vContentEl.value = data.content || "";
  vUsernameEl.value = data.username || "";
  vAvatarEl.value = data.avatar_url || "";

  embedsState = [];
  (Array.isArray(data.embeds)?data.embeds:[]).slice(0,10).forEach(ed=>{
    const e = makeEmbedDefault();
    e.title = ed.title || "";
    e.description = ed.description || "";
    e.url = ed.url || "";
    e.color = ed.color || e.color;
    if(Array.isArray(ed.fields)){
      e.fields = ed.fields.slice(0,25).map(f=>({name:f.name||"", value:f.value||"", inline:!!f.inline}));
    }
    if(ed.thumbnail?.url) e.thumbnail.url = ed.thumbnail.url;
    if(ed.image?.url) e.image.url = ed.image.url;
    if(ed.footer){
      e.footer.text = ed.footer.text || "";
      e.footer.icon_url = ed.footer.icon_url || "";
    }
    // Сброс состояния секций (по умолчанию все закрыты)
    e._openSections = { author: false, body: false, fields: false, images: false, footer: false };
    embedsState.push(e);
  });

  buttonsState = [];
  const comps = Array.isArray(data.components)?data.components:[];
  const row = comps[0]?.components;
  (Array.isArray(row)?row:[]).slice(0,5).forEach(b=>{
    const d = makeButtonDefault();
    d.label = b.label || "Button";
    d.style = Number(b.style ?? 2);
    d.custom_id = b.custom_id || "";
    d.url = b.url || "";
    d.disabled = !!b.disabled;
    buttonsState.push(d);
  });

  syncFromForm();
}

/* ---------- preview ---------- */
function renderPreview(){
  let data;
  try{ data = parseJsonSafe(payloadEl.value); }
  catch(e){ return; }

  const uname = data.username || BOT_META.name || "Bot";
  pNameEl.textContent = uname;

  pAvatarEl.innerHTML = "";
  const avatarUrl = data.avatar_url || BOT_META.avatar || "";
  if(avatarUrl){
    const img = document.createElement("img");
    img.src = String(avatarUrl);
    img.alt = "avatar";
    pAvatarEl.appendChild(img);
  }

  pContentEl.textContent = data.content || "";

  pEmbedsEl.innerHTML = "";
  (Array.isArray(data.embeds)?data.embeds:[]).slice(0,10).forEach(e=>{
    const box = document.createElement("div");
    box.className = "embed";
    const col = parseColorToHex(e.color);
    if(col) box.style.borderLeftColor = col;

    const top = document.createElement("div");
    top.className = "embedTop";
    const main = document.createElement("div");
    main.className = "embedMain";

    if(e.title){
      const t = document.createElement("div");
      t.className = "embedTitle";
      t.innerHTML = escapeHtml(e.title);
      main.appendChild(t);
    }
    if(e.description){
      const d = document.createElement("div");
      d.className = "embedDesc";
      d.innerHTML = escapeHtml(e.description);
      main.appendChild(d);
    }

    const fields = Array.isArray(e.fields)?e.fields:[];
    if(fields.length){
      const anyInline = fields.some(f=>!!f.inline);
      const grid = document.createElement("div");
      grid.className = "fields" + (anyInline ? " two" : "");
      fields.slice(0,25).forEach(f=>{
        const fd = document.createElement("div");
        fd.className = "field";
        fd.innerHTML = `<div class="fn">${escapeHtml(f.name||"")}</div><div class="fv">${escapeHtml(f.value||"")}</div>`;
        grid.appendChild(fd);
      });
      main.appendChild(grid);
    }

    top.appendChild(main);

    if(e.thumbnail?.url){
      const img = document.createElement("img");
      img.className = "embedThumb";
      img.src = String(e.thumbnail.url);
      top.appendChild(img);
    }

    box.appendChild(top);

    if(e.image?.url){
      const img2 = document.createElement("img");
      img2.className = "embedImage";
      img2.src = String(e.image.url);
      box.appendChild(img2);
    }

    if(e.footer && (e.footer.text || e.footer.icon_url)){
      const ft = document.createElement("div");
      ft.className = "footer";
      if(e.footer.icon_url){
        const i = document.createElement("img");
        i.src = String(e.footer.icon_url);
        ft.appendChild(i);
      }
      const s = document.createElement("span");
      s.textContent = e.footer.text || "";
      ft.appendChild(s);
      box.appendChild(ft);
    }

    pEmbedsEl.appendChild(box);
  });

  pButtonsEl.innerHTML = "";
  (Array.isArray(data.components)?data.components:[]).slice(0,1).forEach(row=>{
    const btns = Array.isArray(row.components)?row.components:[];
    btns.slice(0,5).forEach(b=>{
      const div = document.createElement("div");
      div.className = "btn";
      const style = Number(b.style ?? 2);
      if(style === 1) div.classList.add("primary");
      else if(style === 3) div.classList.add("success");
      else if(style === 4) div.classList.add("danger");
      else if(style === 5) div.classList.add("link");
      div.textContent = b.label || "Button";
      pButtonsEl.appendChild(div);
    });
  });
}

/* ---------- sending ---------- */
async function sendNow(){
  if(!panelVisual.classList.contains("hidden")) syncFromForm();

  let payload;
  try{ payload = parseJsonSafe(payloadEl.value); }
  catch(e){
    setResult(false, "JSON invalid (payload)");
    return;
  }

  const body = {
    mode: modeEl.value,
    channel_id: channelIdEl.value,
    webhook_url: webhookUrlEl.value,
    payload
  };

  try{
    const r = await fetchWithAuth("/api/send", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify(body)
    });
    if (!r) return;
    const j = await r.json();
    if(!j.ok) setResult(false, j.error || "Unknown error");
    else setResult(true, JSON.stringify(j));
  }catch(e){
    setResult(false, String(e));
  }
}

function formatJson(){
  try{
    const obj = parseJsonSafe(payloadEl.value);
    payloadEl.value = JSON.stringify(obj, null, 2);
    renderPreview();
    setResult(true, "Formatted");
  }catch(e){
    setResult(false, "JSON invalid");
  }
}

function loadExample(){
  const ex = {
    content: "Hey, welcome!",
    embeds: [
      {
        title: "What's this about?",
        description: "Это локальный Discohook-редактор.\nМожно отправлять как бот или через webhook.",
        color: "#5865F2",
        fields: [
          {name:"Поле 1", value:"Значение 1", inline:true},
          {name:"Поле 2", value:"Значение 2", inline:true}
        ]
      }
    ],
    components: [
      {type:1, components:[
        {type:2, style:5, label:"Site", url:"https://discohook.app"},
        {type:2, style:1, label:"Primary", custom_id:"primary_btn"},
      ]}
    ]
  };
  payloadEl.value = JSON.stringify(ex, null, 2);
  syncFormFromPayload();
  showTab("visual");
}


/* ---------- Visual editor UI (Buttons + Embeds) ---------- */
const buttonsContainer = el("buttonsContainer");
const embedsContainer  = el("embedsContainer");

function renderButtonsEditor(){
  if(!buttonsContainer) return;
  buttonsContainer.innerHTML = "";

  if(!buttonsState.length){
    const empty = document.createElement("div");
    empty.className = "small";
    empty.textContent = "Кнопок пока нет. Нажми «Добавить кнопку».";
    buttonsContainer.appendChild(empty);
    return;
  }

  buttonsState.slice(0,5).forEach((b, idx)=>{
    const card = document.createElement("div");
    card.className = "card";

    const head = document.createElement("div");
    head.className = "cardHead";
    const title = document.createElement("div");
    title.className = "cardTitle";
    title.textContent = `Button ${idx+1}`;
    const btns = document.createElement("div");
    btns.className = "cardBtns";

    const dup = document.createElement("button");
    dup.type = "button";
    dup.className = "iconBtn";
    dup.textContent = "⧉";
    dup.title = "Дублировать";
    dup.onclick = ()=>{
      if(buttonsState.length >= 5) return;
      buttonsState.splice(idx+1, 0, JSON.parse(JSON.stringify(b)));
      renderButtonsEditor();
      syncFromForm();
    };

    const del = document.createElement("button");
    del.type = "button";
    del.className = "iconBtn danger";
    del.textContent = "✕";
    del.title = "Удалить";
    del.onclick = ()=>{
      buttonsState.splice(idx,1);
      renderButtonsEditor();
      syncFromForm();
    };

    btns.appendChild(dup);
    btns.appendChild(del);

    head.appendChild(title);
    head.appendChild(btns);

    const body = document.createElement("div");
    body.className = "cardBody";

    const tools = document.createElement("div");
    tools.className = "embedTools";
    const exp = document.createElement("button");
    exp.type="button";
    exp.textContent="Expand all";
    exp.onclick=()=>{ card.querySelectorAll("details").forEach(d=>d.open=true); };
    const col = document.createElement("button");
    col.type="button";
    col.textContent="Collapse all";
    col.onclick=()=>{ card.querySelectorAll("details").forEach(d=>d.open=false); };
    tools.appendChild(exp);
    tools.appendChild(col);
    body.appendChild(tools);


    const row1 = document.createElement("div");
    row1.className = "row";

    const c1 = document.createElement("div");
    const l1 = document.createElement("label");
    l1.textContent = "Label";
    const i1 = document.createElement("input");
    i1.value = b.label || "";
    i1.oninput = ()=>{ b.label = i1.value; syncFromForm(); };
    c1.appendChild(l1); c1.appendChild(i1);

    const c2 = document.createElement("div");
    const l2 = document.createElement("label");
    l2.textContent = "Style";
    const s2 = document.createElement("select");
    [
      ["1","Primary"],["2","Secondary"],["3","Success"],["4","Danger"],["5","Link"]
    ].forEach(([val,txt])=>{
      const o = document.createElement("option");
      o.value = val; o.textContent = txt;
      s2.appendChild(o);
    });
    s2.value = String(b.style ?? 2);
    s2.onchange = ()=>{
      b.style = Number(s2.value);
      renderButtonsEditor(); // show/hide url/custom_id
      syncFromForm();
    };
    c2.appendChild(l2); c2.appendChild(s2);

    row1.appendChild(c1);
    row1.appendChild(c2);

    const row2 = document.createElement("div");
    row2.className = "row";

    const c3 = document.createElement("div");
    const l3 = document.createElement("label");
    l3.textContent = (Number(b.style)===5) ? "URL (для Link)" : "Custom ID";
    const i3 = document.createElement("input");
    i3.value = (Number(b.style)===5) ? (b.url||"") : (b.custom_id||"");
    i3.oninput = ()=>{
      if(Number(b.style)===5) b.url = i3.value;
      else b.custom_id = i3.value;
      syncFromForm();
    };
    c3.appendChild(l3); c3.appendChild(i3);

    const c4 = document.createElement("div");
    const l4 = document.createElement("label");
    l4.textContent = "Disabled";
    const wrap = document.createElement("div");
    wrap.className = "chkRow";
    const chk = document.createElement("input");
    chk.type = "checkbox";
    chk.checked = !!b.disabled;
    chk.onchange = ()=>{ b.disabled = chk.checked; syncFromForm(); };
    const txt = document.createElement("div");
    txt.className = "small";
    txt.textContent = "Отключить кнопку";
    wrap.appendChild(chk); wrap.appendChild(txt);
    c4.appendChild(l4); c4.appendChild(wrap);

    row2.appendChild(c3);
    row2.appendChild(c4);

    body.appendChild(row1);
    body.appendChild(row2);

    card.appendChild(head);
    card.appendChild(body);

    buttonsContainer.appendChild(card);
  });
}

function renderEmbedsEditor(){
  if(!embedsContainer) return;
  embedsContainer.innerHTML = "";

  if(!embedsState.length){
    const empty = document.createElement("div");
    empty.className = "small";
    empty.textContent = "Embed пока нет. Нажми «Добавить Embed».";
    embedsContainer.appendChild(empty);
    return;
  }

  embedsState.slice(0,10).forEach((e, idx)=>{
    const card = document.createElement("div");
    card.className = "card";

    const head = document.createElement("div");
    head.className = "cardHead";

    const title = document.createElement("div");
    title.className = "cardTitle";
    title.textContent = `Embed ${idx+1} — ${e.title ? e.title.slice(0,40) : "без названия"}`;

    const btns = document.createElement("div");
    btns.className = "cardBtns";

    const dup = document.createElement("button");
    dup.type = "button";
    dup.className = "iconBtn";
    dup.textContent = "⧉";
    dup.title = "Дублировать";
    dup.onclick = ()=>{
      if(embedsState.length >= 10) return;
      embedsState.splice(idx+1, 0, JSON.parse(JSON.stringify(e)));
      renderEmbedsEditor();
      syncFromForm();
    };

    const del = document.createElement("button");
    del.type = "button";
    del.className = "iconBtn danger";
    del.textContent = "✕";
    del.title = "Удалить";
    del.onclick = ()=>{
      embedsState.splice(idx,1);
      renderEmbedsEditor();
      syncFromForm();
    };

    btns.appendChild(dup);
    btns.appendChild(del);

    head.appendChild(title);
    head.appendChild(btns);

    const body = document.createElement("div");
    body.className = "cardBody";

    const tools = document.createElement("div");
    tools.className = "embedTools";
    const exp = document.createElement("button");
    exp.type="button";
    exp.textContent="Expand all";
    exp.onclick = ()=>{
      for (let key in e._openSections) e._openSections[key] = true;
      renderEmbedsEditor();
      syncFromForm();
    };
    const col = document.createElement("button");
    col.type="button";
    col.textContent="Collapse all";
    col.onclick = ()=>{
      for (let key in e._openSections) e._openSections[key] = false;
      renderEmbedsEditor();
      syncFromForm();
    };
    tools.appendChild(exp);
    tools.appendChild(col);
    body.appendChild(tools);

    function section(label, icon, sectionKey) {
      const d = document.createElement("details");
      d.open = e._openSections[sectionKey] || false;

      const s = document.createElement("summary");
      const left = document.createElement("div");
      left.className = "sumLeft";

      const ic = document.createElement("div");
      ic.className = "sumIcon";
      ic.textContent = icon || "▦";

      const txt = document.createElement("div");
      txt.textContent = label;

      left.appendChild(ic);
      left.appendChild(txt);

      const chev = document.createElement("div");
      chev.className = "sumChev";
      chev.textContent = "›";

      s.appendChild(left);
      s.appendChild(chev);

      s.addEventListener("click", (event) => {
        event.preventDefault();
        e._openSections[sectionKey] = !e._openSections[sectionKey];
        renderEmbedsEditor();
        syncFromForm();
      });

      const body = document.createElement("div");
      body.className = "detailsBody";

      d.appendChild(s);
      d.appendChild(body);

      return {d, body};
    }

    const secAuthor = section("Автор","👤", "author");
    {
      const row = document.createElement("div");
      row.className = "row";
      const c1 = document.createElement("div");
      const l1 = document.createElement("label"); l1.textContent = "Автор";
      const i1 = document.createElement("input"); i1.value = (e.author?.name)||"";
      i1.oninput = ()=>{
        e.author = e.author || {name:"",url:"",icon_url:""};
        e.author.name = i1.value;
        syncFromForm();
      };
      c1.appendChild(l1); c1.appendChild(i1);

      const c2 = document.createElement("div");
      const l2 = document.createElement("label"); l2.textContent = "Автор лого URL";
      const i2 = document.createElement("input"); i2.value = (e.author?.icon_url)||"";
      i2.oninput = ()=>{
        e.author = e.author || {name:"",url:"",icon_url:""};
        e.author.icon_url = i2.value;
        syncFromForm();
      };
      c2.appendChild(l2); c2.appendChild(i2);

      const row2 = document.createElement("div");
      row2.className = "row";
      const c3 = document.createElement("div");
      const l3 = document.createElement("label"); l3.textContent = "Author URL";
      const i3 = document.createElement("input"); i3.value = (e.author?.url)||"";
      i3.oninput = ()=>{
        e.author = e.author || {name:"",url:"",icon_url:""};
        e.author.url = i3.value;
        syncFromForm();
      };
      c3.appendChild(l3); c3.appendChild(i3);

      const c4 = document.createElement("div");
      row.appendChild(c1); row.appendChild(c2);
      row2.appendChild(c3); row2.appendChild(c4);
      secAuthor.body.appendChild(row);
      secAuthor.body.appendChild(row2);
    }

    const secBody = section("Основа","📝", "body");
    {
      const row = document.createElement("div");
      row.className = "row";
      const c1 = document.createElement("div");
      const l1 = document.createElement("label"); l1.textContent = "Заголовок";
      const i1 = document.createElement("input"); i1.value = e.title || "";
      i1.oninput = ()=>{
        e.title = i1.value;
        title.textContent = `Embed ${idx+1} — ${e.title ? e.title.slice(0,40) : "без названия"}`;
        syncFromForm();
      };
      c1.appendChild(l1); c1.appendChild(i1);

      const c2 = document.createElement("div");
      const l2 = document.createElement("label"); l2.textContent = "Цвет (#rrggbb)";
      const i2 = document.createElement("input"); i2.value = e.color || "#5865F2";
      i2.oninput = ()=>{ e.color = i2.value; syncFromForm(); };
      c2.appendChild(l2); c2.appendChild(i2);

      const l3 = document.createElement("label"); l3.textContent = "Описание";
      const ta = document.createElement("textarea");
      ta.style.minHeight = "120px";
      ta.value = e.description || "";
      ta.oninput = ()=>{ e.description = ta.value; syncFromForm(); };

      const l4 = document.createElement("label"); l4.textContent = "Ссылка";
      const i4 = document.createElement("input"); i4.value = e.url || "";
      i4.oninput = ()=>{ e.url = i4.value; syncFromForm(); };

      row.appendChild(c1); row.appendChild(c2);
      secBody.body.appendChild(row);
      secBody.body.appendChild(l3); secBody.body.appendChild(ta);
      secBody.body.appendChild(l4); secBody.body.appendChild(i4);
    }

    const secFields = section("Поля","📌", "fields");
    {
      const top = document.createElement("div");
      top.className = "row";
      const left = document.createElement("div");
      const hint = document.createElement("div");
      hint.className = "hint";
      hint.textContent = "До 25 полей. Inline = 2 колонки.";
      left.appendChild(hint);

      const right = document.createElement("div");
      right.className = "right";
      const add = document.createElement("button");
      add.type = "button";
      add.className = "secondary";
      add.textContent = "Добавить поле";
      add.onclick = ()=>{
        e.fields = Array.isArray(e.fields) ? e.fields : [];
        if(e.fields.length >= 25) return;
        e.fields.push(makeFieldDefault());
        renderEmbedsEditor(); // теперь состояние секции сохранится
        syncFromForm();
      };
      right.appendChild(add);

      top.appendChild(left);
      top.appendChild(right);
      secFields.body.appendChild(top);

      const fields = Array.isArray(e.fields) ? e.fields : [];
      fields.forEach((f, fi)=>{
        const fcard = document.createElement("div");
        fcard.className = "card";
        fcard.style.marginTop = "10px";

        const fh = document.createElement("div");
        fh.className = "cardHead";
        const ft = document.createElement("div");
        ft.className = "cardTitle";
        ft.textContent = `Field ${fi+1}`;
        const fbtns = document.createElement("div");
        fbtns.className = "cardBtns";

        const fdel = document.createElement("button");
        fdel.type="button";
        fdel.className="iconBtn danger";
        fdel.textContent="✕";
        fdel.onclick=()=>{
          e.fields.splice(fi,1);
          renderEmbedsEditor();
          syncFromForm();
        };
        fbtns.appendChild(fdel);

        fh.appendChild(ft);
        fh.appendChild(fbtns);

        const fb = document.createElement("div");
        fb.className = "cardBody";

        const row = document.createElement("div");
        row.className = "row";
        const c1 = document.createElement("div");
        const l1 = document.createElement("label"); l1.textContent = "Name";
        const i1 = document.createElement("input"); i1.value = f.name || "";
        i1.oninput = ()=>{ f.name = i1.value; syncFromForm(); };
        c1.appendChild(l1); c1.appendChild(i1);

        const c2 = document.createElement("div");
        const l2 = document.createElement("label"); l2.textContent = "Inline";
        const wrap = document.createElement("div"); wrap.className="chkRow";
        const chk = document.createElement("input"); chk.type="checkbox"; chk.checked=!!f.inline;
        chk.onchange = ()=>{ f.inline = chk.checked; syncFromForm(); };
        const txt = document.createElement("div"); txt.className="small"; txt.textContent="В две колонки";
        wrap.appendChild(chk); wrap.appendChild(txt);
        c2.appendChild(l2); c2.appendChild(wrap);

        const l3 = document.createElement("label"); l3.textContent = "Value";
        const ta = document.createElement("textarea");
        ta.style.minHeight="90px";
        ta.value = f.value || "";
        ta.oninput = ()=>{ f.value = ta.value; syncFromForm(); };

        row.appendChild(c1); row.appendChild(c2);

        fb.appendChild(row);
        fb.appendChild(l3);
        fb.appendChild(ta);

        fcard.appendChild(fh);
        fcard.appendChild(fb);

        secFields.body.appendChild(fcard);
      });
    }

    const secImages = section("Картинка","🖼️", "images");
    {
      const row = document.createElement("div");
      row.className = "row";

      const c1 = document.createElement("div");
      const l1 = document.createElement("label"); l1.textContent = "Маленькая картинка URL";
      const i1 = document.createElement("input"); i1.value = (e.thumbnail?.url)||"";
      i1.oninput = ()=>{
        e.thumbnail = e.thumbnail || {url:""};
        e.thumbnail.url = i1.value;
        syncFromForm();
      };
      c1.appendChild(l1); c1.appendChild(i1);

      const c2 = document.createElement("div");
      const l2 = document.createElement("label"); l2.textContent = "Большая картинка URL";
      const i2 = document.createElement("input"); i2.value = (e.image?.url)||"";
      i2.oninput = ()=>{
        e.image = e.image || {url:""};
        e.image.url = i2.value;
        syncFromForm();
      };
      c2.appendChild(l2); c2.appendChild(i2);

      row.appendChild(c1); row.appendChild(c2);
      secImages.body.appendChild(row);
    }

    const secFooter = section("Текст внизу","🔻", "footer");
    {
      const row = document.createElement("div");
      row.className = "row";

      const c1 = document.createElement("div");
      const l1 = document.createElement("label"); l1.textContent = "Текст внизу";
      const i1 = document.createElement("input"); i1.value = (e.footer?.text)||"";
      i1.oninput = ()=>{
        e.footer = e.footer || {text:"", icon_url:""};
        e.footer.text = i1.value;
        syncFromForm();
      };
      c1.appendChild(l1); c1.appendChild(i1);

      const c2 = document.createElement("div");
      const l2 = document.createElement("label"); l2.textContent = "Иконка внизу URL";
      const i2 = document.createElement("input"); i2.value = (e.footer?.icon_url)||"";
      i2.oninput = ()=>{
        e.footer = e.footer || {text:"", icon_url:""};
        e.footer.icon_url = i2.value;
        syncFromForm();
      };
      c2.appendChild(l2); c2.appendChild(i2);

      row.appendChild(c1); row.appendChild(c2);
      secFooter.body.appendChild(row);
    }

    body.appendChild(secAuthor.d);
    body.appendChild(secBody.d);
    body.appendChild(secFields.d);
    body.appendChild(secImages.d);
    body.appendChild(secFooter.d);

    card.appendChild(head);
    card.appendChild(body);

    embedsContainer.appendChild(card);
  });
}


/* events */
el("addButton").addEventListener("click", ()=>{
  if(buttonsState.length >= 5) return;
  buttonsState.push({type:2, style:2, label:"Button", custom_id:"btn_1", url:"", disabled:false});
  renderButtonsEditor();
  syncFromForm();
});
el("addEmbed").addEventListener("click", ()=>{
  if(embedsState.length >= 10) return;
  embedsState.push(makeEmbedDefault());
  renderEmbedsEditor();
  syncFromForm();
});
el("sendBtn").addEventListener("click", sendNow);
el("sendBtn2").addEventListener("click", sendNow);
el("exampleBtn").addEventListener("click", loadExample);
el("formatBtn").addEventListener("click", formatJson);
el("jsonToVisualBtn").addEventListener("click", syncFormFromPayload);

[vContentEl, vUsernameEl, vAvatarEl, modeEl, channelIdEl, webhookUrlEl].forEach(x=>{
  x.addEventListener("input", syncFromForm);
  x.addEventListener("change", syncFromForm);
});

payloadEl.addEventListener("input", ()=>{
  if(!panelJson.classList.contains("hidden")) renderPreview();
});

/* init */
(async ()=>{
  COLLAPSE = loadCollapse();
  await loadBotMeta();  // загружаем имя бота (должно быть "Phantom Bot")
  await loadUserInfo();
  await initGuilds();

  // Ваш кастомный payload
  const myPayload = {
    content: "Привет от Phantom Bot!",
    embeds: [
      {
        title: "Заголовок",
        description: "Описание вашего embed'а",
        color: "#5865F2",
        fields: [
          { name: "Поле 1", value: "Значение 1", inline: true },
          { name: "Поле 2", value: "Значение 2", inline: true }
        ]
      }
    ],
    components: [] // если нужны кнопки
  };
  payloadEl.value = JSON.stringify(myPayload, null, 2);
  syncFormFromPayload();  // заполнит визуальный редактор из JSON
  renderPreview();
  renderButtonsEditor();
  renderEmbedsEditor();
})();


guildDropdownMenu.addEventListener("click", (e)=>e.stopPropagation());
channelDropdownMenu.addEventListener("click", (e)=>e.stopPropagation());