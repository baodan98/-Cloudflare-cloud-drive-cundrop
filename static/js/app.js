/* CunDrop 前端逻辑 */
const $ = (s) => document.querySelector(s);
let FILES = [], SHARES = [];

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add("hidden"), 2200);
}

function fmtSize(n) {
  n = +n || 0;
  if (n < 1024) return n + " B";
  if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
  if (n < 1073741824) return (n / 1048576).toFixed(1) + " MB";
  return (n / 1073741824).toFixed(2) + " GB";
}
function fmtDate(ts) {
  return new Date(ts * 1000).toLocaleString("zh-CN", { hour12: false }).slice(0, 16);
}
function kindOf(mime) {
  mime = mime || "";
  if (mime.startsWith("video")) return "video";
  if (mime.startsWith("image")) return "image";
  if (mime.startsWith("audio")) return "audio";
  return "file";
}
async function api(url, opt = {}) {
  const r = await fetch(url, opt);
  if (r.status === 401) { location.href = "/login"; throw new Error("未登录"); }
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || "请求失败");
  return j;
}

/* ---------- 视图切换 ---------- */
document.querySelectorAll(".nav-item").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
    $("#view-" + b.dataset.view).classList.remove("hidden");
    if (b.dataset.view === "shares") loadShares();
    if (b.dataset.view === "settings") checkR2();
  })
);

/* ---------- 文件库 ---------- */
async function loadFiles() {
  const j = await api("/api/files");
  FILES = j.files;
  renderFiles();
  const st = j.stats;
  $("#storageText").textContent = `${st.files} 个文件 · 共 ${fmtSize(st.bytes)}`;
  $("#storageBar").style.width = Math.min(100, st.files) + "%";
}
function renderFiles() {
  const q = $("#search").value.trim().toLowerCase();
  const list = FILES.filter((f) => f.filename.toLowerCase().includes(q));
  $("#emptyFiles").classList.toggle("hidden", list.length > 0);
  $("#fileList").innerHTML = list.map((f) => `
    <div class="file-row">
      <div class="file-icon ${kindOf(f.mime)}"></div>
      <div class="file-info">
        <div class="file-name">${esc(f.filename)}</div>
        <div class="file-sub">${fmtSize(f.size)} · ${fmtDate(f.created_at)}</div>
      </div>
      <div class="file-actions">
        <button class="btn primary" onclick="openShare(${f.id}, '${escAttr(f.filename)}')">分享</button>
        <button class="btn danger" onclick="delFile(${f.id})">删除</button>
      </div>
    </div>`).join("");
}
$("#search").addEventListener("input", renderFiles);
function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
function escAttr(s) { return s.replace(/'/g, "\\'").replace(/"/g, "&quot;"); }

async function delFile(id) {
  if (!confirm("确定删除这个文件吗？R2 上的源文件也会一起删除。")) return;
  await api("/api/files/" + id, { method: "DELETE" });
  toast("已删除");
  loadFiles();
}

/* ---------- 上传（直传 R2，带进度） ---------- */
const dz = $("#dropzone"), fi = $("#fileInput");
$("#uploadBtn").onclick = () => fi.click();
dz.onclick = () => fi.click();
["dragover", "dragenter"].forEach((e) => dz.addEventListener(e, (ev) => { ev.preventDefault(); dz.classList.add("over"); }));
["dragleave", "drop"].forEach((e) => dz.addEventListener(e, (ev) => { ev.preventDefault(); dz.classList.remove("over"); }));
dz.addEventListener("drop", (ev) => uploadMany(ev.dataTransfer.files));
fi.addEventListener("change", () => { uploadMany(fi.files); fi.value = ""; });

async function uploadMany(files) {
  for (const f of files) uploadOne(f);
}
function uploadOne(file) {
  const box = document.createElement("div");
  box.className = "up-item";
  box.innerHTML = `<div class="up-top"><span>${esc(file.name)}</span><span class="pct">准备…</span></div><div class="up-bar"><i></i></div>`;
  $("#uploadList").prepend(box);
  const bar = box.querySelector(".up-bar i"), pct = box.querySelector(".pct");

  (async () => {
    // 1. 初始化：拿预签名 URL
    const init = await api("/api/files/init", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, size: file.size, mime: file.type || "application/octet-stream" }),
    });
    // 2. 直传 R2
    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", init.upload_url);
      xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const p = Math.round((e.loaded / e.total) * 100);
          bar.style.width = p + "%"; pct.textContent = p + "%";
        }
      };
      xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error("R2 返回 " + xhr.status)));
      xhr.onerror = () => reject(new Error("网络错误"));
      xhr.send(file);
    });
    // 3. 确认完成
    await api("/api/files/complete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_id: init.file_id }),
    });
    box.classList.add("done"); pct.textContent = "完成 ✓";
    setTimeout(() => box.remove(), 2500);
    loadFiles();
  })().catch((e) => {
    box.classList.add("error"); pct.textContent = "失败";
    toast("上传失败：" + e.message);
  });
}

/* ---------- 分享 ---------- */
let shareFileId = null;
function openShare(id, name) {
  shareFileId = id;
  $("#shareFileName").textContent = name;
  $("#shareResult").classList.add("hidden");
  $("#shareModal").classList.remove("hidden");
}
$("#shareCancel").onclick = () => $("#shareModal").classList.add("hidden");
$("#shareCreate").onclick = async () => {
  const days = $("#shareExpire").value ? +$("#shareExpire").value : null;
  const j = await api("/api/shares", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id: shareFileId, expires_in_days: days, password: $("#sharePwd").value }),
  });
  $("#shareUrl").value = j.url;
  $("#shareResult").classList.remove("hidden");
  loadShares();
};
$("#copyBtn").onclick = async () => {
  await navigator.clipboard.writeText($("#shareUrl").value);
  toast("链接已复制");
};

async function loadShares() {
  const j = await api("/api/shares");
  SHARES = j.shares;
  $("#emptyShares").classList.toggle("hidden", SHARES.length > 0);
  $("#shareList").innerHTML = SHARES.map((s) => {
    const exp = s.expires_at ? fmtDate(s.expires_at) : "永久";
    const gone = s.expires_at && s.expires_at * 1000 < Date.now();
    return `
    <div class="file-row">
      <div class="file-icon ${kindOf("")}"></div>
      <div class="file-info">
        <div class="file-name">${esc(s.filename)}
          ${s.password_hash ? '<span class="tag pwd">密码</span>' : ""}
          ${gone ? '<span class="tag exp">已过期</span>' : ""}
        </div>
        <div class="file-sub"><a href="/f/${s.token}" target="_blank">/f/${s.token}</a> · ${exp}到期 · ${s.views} 次查看</div>
      </div>
      <div class="file-actions">
        <button class="btn" onclick="copyShare('${s.token}')">复制</button>
        <button class="btn danger" onclick="delShare('${s.token}')">删除</button>
      </div>
    </div>`;
  }).join("");
}
async function copyShare(token) {
  await navigator.clipboard.writeText(location.origin + "/f/" + token);
  toast("链接已复制");
}
async function delShare(token) {
  if (!confirm("删除这个分享链接？文件本身不受影响。")) return;
  await api("/api/shares/" + token, { method: "DELETE" });
  toast("已删除"); loadShares();
}

/* ---------- 设置 ---------- */
async function checkR2() {
  try {
    const j = await api("/api/r2/ping");
    $("#r2status").textContent = "✅ 已连接，Bucket：" + j.bucket;
  } catch (e) {
    $("#r2status").textContent = "❌ " + e.message;
    const w = $("#r2warn");
    w.textContent = "R2 连接失败，请检查环境变量配置。";
    w.classList.remove("hidden");
  }
}
$("#changePwdBtn").onclick = async () => {
  try {
    await api("/api/password", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old: $("#oldPwd").value, new: $("#newPwd").value }),
    });
    $("#pwdMsg").textContent = "✅ 已修改（重启服务后恢复为环境变量中的密码）";
    $("#oldPwd").value = $("#newPwd").value = "";
  } catch (e) { $("#pwdMsg").textContent = "❌ " + e.message; }
};

loadFiles();
