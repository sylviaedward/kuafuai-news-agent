const $ = (id) => document.getElementById(id);
const hourSelect = $("delivery-hour");
for (let h = 0; h < 24; h++) {
  const option = document.createElement("option");
  option.value = String(h);
  option.textContent = `${String(h).padStart(2, "0")}:00`;
  if (h === 9) option.selected = true;
  hourSelect.append(option);
}
let userId = Number(localStorage.getItem("ai_daily_user_id")) || null;
const splitTerms = (value) => value.split(/[,，、]/).map(s => s.trim()).filter(Boolean);

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
  return data;
}
function setMessage(text, isError = false) {
  $("message").className = isError ? "notice error" : "notice";
  $("message").textContent = text;
  $("message").hidden = !text;
}
function fillUser(user) {
  $("name").value = user.name;
  $("email").value = user.email;
  $("topics").value = user.topics.join(", ");
  $("keywords").value = user.keywords.join(", ");
  hourSelect.value = String(user.delivery_hour);
  $("run-now").disabled = false;
}
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function renderRun(run) {
  const card = element("article", "run");
  const top = element("div", "run-top");
  const titleArea = element("div");
  titleArea.append(element("div", "meta", `${run.local_day} · ${run.is_manual ? "手动生成" : "每日定时"}`));
  titleArea.append(element("h3", "", run.headline || "简报生成中"));
  const statusText = {queued:"排队中", running:"生成中", completed:"已投递", failed:"失败"}[run.status] || run.status;
  top.append(titleArea, element("span", `status ${run.status}`, statusText));
  card.append(top);
  if (run.error) card.append(element("p", "error", run.error));
  if (run.delivery_status) card.append(element("div", "meta", run.delivery_status));
  if (run.briefing) {
    for (const item of run.briefing.items) {
      const row = element("div", "item");
      const link = element("a", "", item.title);
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      row.append(link, element("p", "", item.summary),
        element("div", "why", `${item.source} · ${item.published_at?.slice(0,10) || "日期未知"} · ${item.why}`));
      card.append(row);
    }
    card.append(element("p", "meta", run.briefing.closing));
  }
  if (run.trace?.length) {
    const details = element("details");
    details.append(element("summary", "", `查看 Agent 工具调用记录（${run.trace.length} 步）`));
    details.append(element("pre", "", JSON.stringify(run.trace, null, 2)));
    card.append(details);
  }
  return card;
}
async function refreshRuns() {
  if (!userId) return;
  const runs = await api(`/api/users/${userId}/runs`);
  const container = $("runs");
  container.replaceChildren();
  if (!runs.length) container.append(element("div", "empty", "尚无简报。保存订阅后可立即生成一份。"));
  else runs.forEach(run => container.append(renderRun(run)));
  return runs;
}
$("settings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const user = await api("/api/users", {method:"POST", body:JSON.stringify({
      name:$("name").value, email:$("email").value,
      topics:splitTerms($("topics").value), keywords:splitTerms($("keywords").value),
      delivery_hour:Number(hourSelect.value)
    })});
    userId = user.id;
    localStorage.setItem("ai_daily_user_id", String(userId));
    fillUser(user);
    setMessage("订阅已保存。定时任务会按北京时间检查并投递。", false);
    await refreshRuns();
  } catch (error) { setMessage(error.message, true); }
});
$("run-now").addEventListener("click", async () => {
  try {
    const {run_id} = await api(`/api/users/${userId}/runs`, {method:"POST"});
    setMessage("Agent 已开始工作。可在下方查看进度和工具记录。", false);
    await refreshRuns();
    for (let attempt = 0; attempt < 60; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      const run = await api(`/api/runs/${run_id}`);
      await refreshRuns();
      if (["completed", "failed"].includes(run.status)) {
        setMessage(run.status === "completed" ? "简报已投递。" : `生成失败：${run.error}`, run.status === "failed");
        break;
      }
    }
  } catch (error) { setMessage(error.message, true); }
});
$("refresh").addEventListener("click", () => refreshRuns().catch(e => setMessage(e.message, true)));
async function init() {
  setMessage("");
  try {
    const health = await api("/api/health");
    $("model-status").textContent = health.llm_configured ? "模型已连接" : "需要配置模型密钥";
    if (userId) { fillUser(await api(`/api/users/${userId}`)); await refreshRuns(); }
  } catch (error) { setMessage(error.message, true); }
}
init();
