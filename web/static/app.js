/* 专属工作台 · 内网 Web 版（ES5 兼容写法，适配老内核浏览器，无外部依赖） */
"use strict";

/* -------------------------------------------------- 环境检测 ---------------- */
(function () {
  if (window.location && window.location.protocol === "file:") {
    alert("请勿直接双击打开本文件！\n请先运行：bash web/start.sh\n然后用浏览器访问 http://本机IP:8000");
  }
  if (typeof window.Promise === "undefined") {
    alert("当前浏览器不支持 Promise，无法运行 Web 版。\n请使用较新的浏览器（如 Chromium 65+ / Firefox 55+），或改用桌面版程序。");
  }
})();

/* -------------------------------------------------- 基础工具 ---------------- */
function $(id) { return document.getElementById(id); }

function esc(s) {
  s = (s === null || s === undefined) ? "" : String(s);
  return s.replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

function pad2(n) { n = String(n); return n.length >= 2 ? n : "0" + n; }

function today() {
  var d = new Date();
  return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
}

function dtLocal(dt) { return dt ? String(dt).replace(" ", "T") : ""; }
function dtJs(dt) { return dt ? String(dt).replace("T", " ").slice(0, 16) : ""; }

var _toastTimer = null;
function toast(msg, ms) {
  var t = $("toast");
  t.textContent = msg;
  t.className = "toast show";
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(function () { t.className = "toast"; }, ms || 2400);
}

function showError(e) {
  var m = (e && e.message) ? e.message : String(e);
  toast("操作失败：" + m);
}

function openModal(id) { $(id).className = "modal-mask show"; }
function closeModal(id) { $(id).className = "modal-mask"; }

function fillSelect(id, values, cur) {
  var s = $(id);
  if (!s) return;
  var html = "";
  for (var i = 0; i < values.length; i++) html += "<option>" + esc(values[i]) + "</option>";
  s.innerHTML = html;
  s.value = cur || "";
}

/* 访问口令（可选）：服务端启用口令时，请求需带 Authorization 头 */
var WB_TOKEN = (function () {
  try { return window.localStorage.getItem("wb_token") || ""; }
  catch (e) { return ""; }
})();
function askToken() {
  var t = prompt("请输入访问口令（未启用口令时留空并点确定）：", "");
  if (t === null) return false;             // 用户取消
  if (t) {
    WB_TOKEN = t;
    try { window.localStorage.setItem("wb_token", t); } catch (e) {}
  }
  return true;
}

/* XHR -> Promise（兼容 IE11/老内核；无 Promise 时前面已提示） */
function xhr(method, url, body, isForm) {
  return new Promise(function (resolve, reject) {
    var retried = false;
    function sendOnce() {
      var x = new XMLHttpRequest();
      x.open(method, url, true);
      if (!isForm) x.setRequestHeader("Content-Type", "application/json; charset=utf-8");
      if (WB_TOKEN) x.setRequestHeader("Authorization", "Bearer " + WB_TOKEN);
      x.onreadystatechange = function () {
        if (x.readyState !== 4) return;
        var ct = x.getResponseHeader("Content-Type") || "";
        if (x.status === 401) {
          // 口令缺失/错误：让用户输入后重试一次
          if (!retried && askToken()) { retried = true; return sendOnce(); }
          return reject(new Error("需要访问口令"));
        }
        if (ct.indexOf("json") >= 0) {
          var j = null;
          try { j = JSON.parse(x.responseText); } catch (e) { j = null; }
          if (x.status === 200 && j && j.ok) return resolve(j);
          return reject(new Error((j && j.error) || ("HTTP " + x.status)));
        }
        if (x.status === 200) return resolve(null);
        reject(new Error("HTTP " + x.status));
      };
      x.onerror = function () { reject(new Error("网络错误，无法连接服务")); };
      if (body && !isForm) x.send(JSON.stringify(body));
      else if (body && isForm) x.send(body);
      else x.send();
    }
    sendOnce();
  });
}

/* 隐藏表单 POST（老内核浏览器下载文件用的方式） */
function formPost(url, params) {
  var f = document.createElement("form");
  f.method = "POST";
  f.action = url + (url.indexOf("?") >= 0 ? "&" : "?") +
             "token=" + encodeURIComponent(WB_TOKEN);
  f.target = "_blank";
  f.style.display = "none";
  for (var k in params) {
    if (!params.hasOwnProperty(k)) continue;
    var i = document.createElement("input");
    i.type = "hidden";
    i.name = k;
    i.value = params[k];
    f.appendChild(i);
  }
  document.body.appendChild(f);
  f.submit();
  document.body.removeChild(f);
}

function downloadUrl(url) {
  if (WB_TOKEN) {
    window.location.href = url + (url.indexOf("?") >= 0 ? "&" : "?") +
                           "token=" + encodeURIComponent(WB_TOKEN);
  } else {
    window.location.href = url;
  }
}

/* -------------------------------------------------- 全局状态 ---------------- */
var TAGS = ["一般", "会议", "待办", "通知", "想法"];
var STATUSES = ["待办", "处理中", "已完成", "暂停"];
var DUTY_SHORT = { "值班": "值", "节假日值班": "节值", "督查": "督", "节假日督查": "节督" };
var DICTS = { levels: [], urgencies: [], orgs: [], duty_types: ["值班", "节假日值班", "督查", "节假日督查"] };
var PERSONS = [];
var TASKS = [];
var MEMOS = [];
var CAL = { y: new Date().getFullYear(), m: new Date().getMonth() + 1 };
var DUTY = { y: new Date().getFullYear(), m: new Date().getMonth() + 1 };
var HOL = {};
var MODAL_DATA = null;

/* -------------------------------------------------- Tab 切换 ---------------- */
function switchTab(key) {
  var btns = document.querySelectorAll("#tabs button");
  for (var i = 0; i < btns.length; i++) {
    btns[i].className = (btns[i].dataset && btns[i].dataset.tab === key) ? "active" : "";
  }
  var tabs = document.querySelectorAll("main .tab");
  for (var j = 0; j < tabs.length; j++) {
    tabs[j].className = (tabs[j].id === "tab-" + key) ? "tab active" : "tab";
  }
  var fn = { task: taskLoad, memo: memoLoad, calendar: calLoad, duty: dutyLoad,
             stats: statsLoad, base: baseLoad, recycle: recycleLoad }[key];
  if (fn) fn();
}

(function () {
  var btns = document.querySelectorAll("#tabs button");
  for (var i = 0; i < btns.length; i++) {
    btns[i].onclick = (function (key) { return function () { switchTab(key); }; })(btns[i].dataset.tab);
  }
})();

/* -------------------------------------------------- 初始化 ---------------- */
function loadPersons() {
  return xhr("GET", "/api/persons").then(function (d) {
    PERSONS = d.rows || [];
  });
}

function init() {
  xhr("GET", "/api/dicts")
    .then(function (d) {
      DICTS = d;
      return loadPersons();
    })
    .then(function () {
      var y = new Date().getFullYear();
      return xhr("GET", "/api/holidays?y=" + y);
    })
    .then(function (h) {
      HOL = h.holidays || {};
      fillSelect("f_level", ["全部"].concat(DICTS.levels), "全部");
      fillSelect("f_urgency", ["全部"].concat(DICTS.urgencies), "全部");
      fillSelect("t_level", DICTS.levels, DICTS.levels[0] || "");
      fillSelect("t_urgency", DICTS.urgencies, DICTS.urgencies[0] || "");
      fillSelect("t_status", STATUSES, "待办");
      fillSelect("m_tag", ["全部"].concat(TAGS), "全部");
      fillSelect("m_tag_edit", TAGS, "一般");
      fillSelect("d_type", DICTS.duty_types, DICTS.duty_types[0]);
      var bl = "", bu = "";
      for (var i = 0; i < DICTS.levels.length; i++) bl += "<option>" + esc(DICTS.levels[i]) + "</option>";
      for (var j = 0; j < DICTS.urgencies.length; j++) bu += "<option>" + esc(DICTS.urgencies[j]) + "</option>";
      $("base_level").innerHTML = bl;
      $("base_urgency").innerHTML = bu;
      var dtv = "";
      for (var k = 0; k < DICTS.duty_types.length; k++) dtv += "<span class='chip'>" + esc(DICTS.duty_types[k]) + "</span> ";
      $("duty_types_view").innerHTML = dtv;
      var pl = "";
      for (var m = 0; m < PERSONS.length; m++) pl += "<option value='" + esc(PERSONS[m].name) + "'>";
      $("t_person_list").innerHTML = pl;
      $("d_person_list").innerHTML = pl;
      var d0 = new Date();
      $("f_start").value = today();
      $("f_end").value = today();
      $("s_start").value = d0.getFullYear() + "-01-01";
      $("s_end").value = today();
      $("duty_s").value = d0.getFullYear() + "-01-01";
      $("duty_e").value = today();
      taskLoad();
    })
    .catch(showError);
}

/* -------------------------------------------------- 工作记录 ---------------- */
function taskQuery() {
  var q = [];
  if (!$("f_all").checked) {
    if ($("f_start").value) q.push("start=" + encodeURIComponent($("f_start").value));
    if ($("f_end").value) q.push("end=" + encodeURIComponent($("f_end").value));
  }
  if ($("f_level").value && $("f_level").value !== "全部") q.push("level=" + encodeURIComponent($("f_level").value));
  if ($("f_urgency").value && $("f_urgency").value !== "全部") q.push("urgency=" + encodeURIComponent($("f_urgency").value));
  // 状态用 ASCII 码传参，避免中文查询参数在某些浏览器/代理链路乱码
  var _stCodes = { "待办": "todo", "处理中": "doing", "已完成": "done", "暂停": "paused" };
  if ($("f_status").value && $("f_status").value !== "全部")
    q.push("status=" + (_stCodes[$("f_status").value] || $("f_status").value));
  if ($("f_person").value.trim()) q.push("person=" + encodeURIComponent($("f_person").value.trim()));
  if ($("f_kw").value.trim()) q.push("kw=" + encodeURIComponent($("f_kw").value.trim()));
  return q.join("&");
}

function taskLoad() {
  xhr("GET", "/api/tasks?" + taskQuery())
    .then(function (d) {
      TASKS = d.rows || [];
      renderTasks();
    })
    .catch(showError);
}

function renderTasks() {
  var tb = $("task_table").querySelector("tbody");
  $("task_count").textContent = TASKS.length ? "共 " + TASKS.length + " 条记录" : "无记录";
  var html = "";
  for (var i = 0; i < TASKS.length; i++) {
    var t = TASKS[i];
    var st = t.status || "待办";
    var clsMap = { "已完成": "st-done", "待办": "st-todo", "处理中": "st-undoing", "暂停": "st-paused" };
    var cls = clsMap[st] || "";
    var urgCls = "";
    if (t.urgency_name === "特急") urgCls = "urgent";
    else if (t.urgency_name === "加急") urgCls = "rush";
    html += "<tr data-id='" + t.id + "' onclick='taskRowClick(this," + t.id + ")'>" +
      "<td onclick='event.stopPropagation()'><input type='checkbox' class='trow' value='" + t.id +
      "' onclick='event.stopPropagation()'></td>" +
      "<td>" + esc(t.name) + "</td>" +
      "<td><span class='" + cls + "'>" + esc(st) + "</span></td>" +
      "<td>" + esc(String(t.start_time || "").slice(0, 16)) + "</td>" +
      "<td>" + esc(String(t.end_time || "").slice(0, 16)) + "</td>" +
      "<td>" + esc(t.level_name || "") + "</td>" +
      "<td>" + esc(t.org_name || "") + "</td>" +
      "<td>" + esc(t.person || "") + "</td>" +
      "<td class='" + urgCls + "'>" + esc(t.urgency_name || "") + "</td>" +
      "<td>" + esc(t.source || "") + "</td></tr>";
  }
  tb.innerHTML = html;
  taskSyncHeader();
}

function taskRowClick(tr) {
  var rows = document.querySelectorAll("#task_table tbody tr");
  for (var i = 0; i < rows.length; i++) rows[i].className = "";
  tr.className = "sel";
  var cb = tr.querySelector("input[type=checkbox]");
  if (cb) cb.checked = true;
}

function taskSelCbs() {
  var out = [];
  var cbs = document.querySelectorAll("#task_table .trow:checked");
  for (var i = 0; i < cbs.length; i++) out.push(parseInt(cbs[i].value, 10));
  return out;
}

function taskSelAll(cb) {
  var cbs = document.querySelectorAll("#task_table .trow");
  for (var i = 0; i < cbs.length; i++) cbs[i].checked = cb.checked;
}

function taskSyncHeader() {
  var head = document.querySelector("#task_table thead input[type=checkbox]");
  if (!head) return;
  var all = document.querySelectorAll("#task_table .trow");
  var checked = taskSelCbs();
  head.checked = all.length > 0 && checked.length === all.length;
}

function taskReset() {
  $("f_all").checked = true;
  $("f_start").value = today();
  $("f_end").value = today();
  $("f_level").value = "全部";
  $("f_urgency").value = "全部";
  $("f_status").value = "全部";
  $("f_person").value = "";
  $("f_kw").value = "";
  taskLoad();
}

function taskDelete() {
  var ids = taskSelCbs();
  if (!ids.length) return toast("请先在表格勾选要删除的记录");
  if (!confirm("确定删除选中的 " + ids.length + " 条记录吗？（可在回收站恢复）")) return;
  xhr("POST", "/api/tasks/delete", { ids: ids })
    .then(function () { toast("已删除"); taskLoad(); })
    .catch(showError);
}

function taskStatusQuick() {
  var sel = $("f_status_quick");
  var val = sel.value;
  if (!val) return;
  var ids = taskSelCbs();
  if (!ids.length) {
    var tr = document.querySelector("#task_table tbody tr");
    if (tr) ids = [parseInt(tr.getAttribute("data-id"), 10)];
  }
  if (!ids.length) return toast("请先选中记录");
  xhr("POST", "/api/tasks/status", { ids: ids, status: val })
    .then(function () {
      toast("状态已设为「" + val + "」");
      sel.value = "";
      taskLoad();
    })
    .catch(showError);
}

function taskExport() {
  if (!TASKS.length) return toast("当前没有可导出的记录");
  /* 隐藏表单提交，兼容老内核浏览器 */
  formPost("/api/tasks/export", { rows: JSON.stringify(TASKS) });
}

function taskOpen(task) {
  MODAL_DATA = task || null;
  $("task_modal_title").textContent = task ? "编辑工作记录" : "新增工作记录";
  $("t_name").value = task ? task.name : "";
  var lvl = (task && DICTS.levels.indexOf(task.level_name) >= 0) ? task.level_name : (DICTS.levels[0] || "");
  var urg = (task && DICTS.urgencies.indexOf(task.urgency_name) >= 0) ? task.urgency_name : (DICTS.urgencies[0] || "");
  $("t_level").value = lvl;
  $("t_urgency").value = urg;
  var depts = "";
  for (var i = 0; i < DICTS.orgs.length; i++) {
    if (!DICTS.orgs[i].parent_id) depts += "<option>" + esc(DICTS.orgs[i].name) + "</option>";
  }
  $("t_dept").innerHTML = "<option></option>" + depts;
  $("t_section").innerHTML = "<option></option>";
  if (task && task.org_name) {
    var org = null;
    for (var j = 0; j < DICTS.orgs.length; j++) {
      if (DICTS.orgs[j].name === task.org_name) { org = DICTS.orgs[j]; break; }
    }
    if (org) {
      if (!org.parent_id) {
        $("t_dept").value = org.name;
        deptFillSec(org.id);
      } else {
        var parent = null;
        for (var k = 0; k < DICTS.orgs.length; k++) {
          if (DICTS.orgs[k].id === org.parent_id) { parent = DICTS.orgs[k]; break; }
        }
        if (parent) { $("t_dept").value = parent.name; deptFillSec(parent.id); $("t_section").value = org.name; }
      }
    }
  }
  $("t_person").value = task ? (task.person || "") : "";
  $("t_source").value = task ? (task.source || "") : "";
  $("t_start").value = dtLocal(task ? task.start_time : (today() + " 09:00"));
  $("t_end").value = dtLocal(task ? task.end_time : "");
  $("t_status").value = task ? (task.status || "待办") : "待办";
  $("t_remind").value = (task && task.remind_hours != null) ? task.remind_hours : "";
  $("t_cross").checked = task ? !!task.cross_dept : false;
  $("t_content").value = task ? (task.content || "") : "";
  $("t_remark").value = task ? (task.remark || "") : "";
  openModal("task_modal");
}

function deptFillSec(pid) {
  var html = "<option></option>";
  for (var i = 0; i < DICTS.orgs.length; i++) {
    if (DICTS.orgs[i].parent_id === pid) html += "<option>" + esc(DICTS.orgs[i].name) + "</option>";
  }
  $("t_section").innerHTML = html;
}

function deptChange() {
  var s = $("t_dept");
  var org = null;
  for (var i = 0; i < DICTS.orgs.length; i++) {
    if (DICTS.orgs[i].name === s.value) { org = DICTS.orgs[i]; break; }
  }
  deptFillSec(org ? org.id : null);
}

function taskSave() {
  var name = $("t_name").value.trim();
  if (!name) return toast("标题不能为空");
  var secS = $("t_section").value, deptS = $("t_dept").value, orgId = null;
  for (var i = 0; i < DICTS.orgs.length; i++) {
    var o = DICTS.orgs[i];
    if (secS && o.name === secS && o.parent_id != null) { orgId = o.id; secS = ""; break; }
  }
  if (!orgId) {
    for (var j = 0; j < DICTS.orgs.length; j++) {
      if (DICTS.orgs[j].name === deptS) { orgId = DICTS.orgs[j].id; break; }
    }
  }
  var remind = $("t_remind").value ? parseInt($("t_remind").value, 10) : null;
  var body = {
    id: MODAL_DATA ? MODAL_DATA.id : null,
    name: name,
    level: $("t_level").value,
    urgency: $("t_urgency").value,
    org_id: orgId,
    person: $("t_person").value.trim(),
    source: $("t_source").value.trim(),
    start_time: dtJs($("t_start").value),
    end_time: dtJs($("t_end").value),
    status: $("t_status").value,
    remind_hours: remind,
    cross_dept: $("t_cross").checked ? 1 : 0,
    content: $("t_content").value,
    remark: $("t_remark").value
  };
  xhr("POST", "/api/tasks/save", body)
    .then(function () { toast("已保存"); closeModal("task_modal"); taskLoad(); })
    .catch(showError);
}

/* -------------------------------------------------- 备忘录 ---------------- */
function memoLoad() {
  var q = [];
  if ($("m_tag").value && $("m_tag").value !== "全部") q.push("tag=" + encodeURIComponent($("m_tag").value));
  if ($("m_kw").value.trim()) q.push("kw=" + encodeURIComponent($("m_kw").value.trim()));
  xhr("GET", "/api/memos?" + q.join("&"))
    .then(function (d) {
      MEMOS = d.rows || [];
      $("memo_count").textContent = MEMOS.length ? "共 " + MEMOS.length + " 条" : "无记录";
      var html = "";
      for (var i = 0; i < MEMOS.length; i++) {
        var m = MEMOS[i];
        html += "<tr data-id='" + m.id + "' onclick='memoRowClick(this)'>" +
          "<td onclick='event.stopPropagation()'><input type='checkbox' class='mrow' value='" + m.id + "'></td>" +
          "<td>" + esc(String(m.created_at || "").slice(0, 16)) + "</td>" +
          "<td>" + esc(m.tag || "一般") + "</td>" +
          "<td>" + esc(String(m.content || "").replace(/\s+/g, " ").slice(0, 80)) + "</td></tr>";
      }
      $("memo_table").querySelector("tbody").innerHTML = html;
    })
    .catch(showError);
}

function memoRowClick(tr) {
  var rows = document.querySelectorAll("#memo_table tbody tr");
  for (var i = 0; i < rows.length; i++) rows[i].className = "";
  tr.className = "sel";
  var cb = tr.querySelector("input[type=checkbox]");
  if (cb) cb.checked = true;
}

function memoRowSel() {
  var out = [];
  var cbs = document.querySelectorAll("#memo_table .mrow:checked");
  for (var i = 0; i < cbs.length; i++) out.push(parseInt(cbs[i].value, 10));
  return out;
}

function memoReset() { $("m_tag").value = "全部"; $("m_kw").value = ""; memoLoad(); }

function memoDelete() {
  var ids = memoRowSel();
  if (!ids.length) return toast("请先勾选备忘录");
  if (!confirm("删除所选 " + ids.length + " 条备忘录？（可在回收站恢复）")) return;
  xhr("POST", "/api/memos/delete", { ids: ids })
    .then(function () { memoLoad(); })
    .catch(showError);
}

function memoOpen(memo) {
  MODAL_DATA = memo || null;
  $("memo_modal_title").textContent = memo ? "编辑备忘录" : "新建备忘录";
  $("m_tag_edit").value = memo ? (memo.tag || "一般") : "一般";
  $("m_content").value = memo ? (memo.content || "") : "";
  openModal("memo_modal");
}

function memoSave() {
  var content = $("m_content").value.trim();
  if (!content) return toast("内容不能为空");
  xhr("POST", "/api/memos/save", { id: MODAL_DATA ? MODAL_DATA.id : null, content: content, tag: $("m_tag_edit").value })
    .then(function () { closeModal("memo_modal"); memoLoad(); })
    .catch(showError);
}

function memoExport() { downloadUrl("/api/memo/export"); }

/* -------------------------------------------------- 日历 ---------------- */
function calShift(d) {
  CAL.m += d;
  if (CAL.m < 1) { CAL.m = 12; CAL.y--; }
  if (CAL.m > 12) { CAL.m = 1; CAL.y++; }
  calLoad();
}
function calToday() { CAL = { y: new Date().getFullYear(), m: new Date().getMonth() + 1 }; calLoad(); }

function calLoad() {
  $("cal_title").textContent = CAL.y + "年" + CAL.m + "月";
  xhr("GET", "/api/calendar/month?y=" + CAL.y + "&m=" + CAL.m)
    .then(function (cal) {
      return xhr("GET", "/api/duty/month?y=" + CAL.y + "&m=" + CAL.m)
        .then(function (duty) {
          return xhr("GET", "/api/holidays?y=" + CAL.y)
            .then(function (hol) {
              HOL = hol.holidays || {};
              renderCal(cal.tasks || {}, duty.month || {});
              calDetail(today());
            });
        });
    })
    .catch(showError);
}

function holBadge(dt) {
  var h = HOL[dt];
  if (!h) return "";
  if (h.rest) return "<span class='hol'>休</span>";
  if (h.work) return "<span class='workday'>班</span>";
  return "";
}

function dutyChips(entries) {
  var html = "";
  for (var i = 0; i < entries.length; i++) {
    var e = entries[i];
    if (!e[1]) continue;
    var short = DUTY_SHORT[e[0]] || e[0][0];
    html += "<span class='duty-tag" + (e[3] ? " manual" : "") + "'>" + short + ":" + esc(e[1]) + "</span>";
  }
  return html;
}

function renderCal(tasks, duties) {
  var grid = $("cal_grid");
  var heads = ["一", "二", "三", "四", "五", "六", "日"];
  var html = "";
  for (var i = 0; i < heads.length; i++) html += "<div class='cal-head'>周" + heads[i] + "</div>";
  var y = CAL.y, m = CAL.m;
  var first = new Date(y, m - 1, 1);
  var startDow = (first.getDay() + 6) % 7;
  var days = new Date(y, m, 0).getDate();
  var tday = today();
  for (var s = 0; s < startDow; s++) {
    var pd = new Date(y, m - 1, s - startDow + 1);
    html += "<div class='cell other'><div class='dnum'>" + pd.getDate() + "</div></div>";
  }
  for (var d = 1; d <= days; d++) {
    var dt = y + "-" + pad2(m) + "-" + pad2(d);
    var items = tasks[dt] || [];
    html += "<div class='cell" + (dt === tday ? " today" : "") + "' onclick=\"calPick('" + dt + "')\">" +
      "<div class='dnum'>" + d + "</div>" + holBadge(dt) + dutyChips(duties[dt] || []);
    var shown = items.slice(0, 3);
    for (var t = 0; t < shown.length; t++) {
      html += "<div class='item'>· " + esc(shown[t].name) +
        (shown[t].urgency ? " [" + esc(shown[t].urgency) + "]" : "") + "</div>";
    }
    if (items.length > 3) html += "<div class='item muted'>…共" + items.length + "项</div>";
    html += "</div>";
  }
  var tail = 7 - ((startDow + days) % 7 || 7);
  for (var e = 1; e <= tail; e++) {
    var nd = new Date(y, m - 1, days + e);
    html += "<div class='cell other'><div class='dnum'>" + nd.getDate() + "</div></div>";
  }
  grid.innerHTML = html;
}

function calPick(ds) { calDetail(ds); }

function calDetail(ds) {
  var box = $("cal_detail");
  var ym = ds.slice(0, 4), mm = parseInt(ds.slice(5, 7), 10);
  xhr("GET", "/api/duty/month?y=" + ym + "&m=" + mm)
    .then(function (duty) {
      return xhr("GET", "/api/calendar/month?y=" + ym + "&m=" + mm)
        .then(function (cal) {
          var entries = (duty.month || {})[ds] || [];
          var ts = (cal.tasks || {})[ds] || [];
          var html = "<b>" + ds + " 当天安排</b>　工作 " + ts.length + " 项；排班 " +
                     (entries.filter(function (x) { return x[1]; }).length) + " 条<ul style='margin:8px 0 0 18px'>";
          for (var i = 0; i < entries.length; i++) {
            if (!entries[i][1]) continue;
            html += "<li>" + esc(entries[i][0]) + "：" + esc(entries[i][1]) +
              (entries[i][2] ? "（" + esc(entries[i][2]) + "）" : "") + "</li>";
          }
          for (var j = 0; j < ts.length; j++) {
            html += "<li>" + esc(ts[j].name) + (ts[j].urgency ? " [" + esc(ts[j].urgency) + "]" : "") + "</li>";
          }
          var hasDuty = false;
          for (var k = 0; k < entries.length; k++) if (entries[k][1]) hasDuty = true;
          if (!hasDuty && !ts.length) html += "<li class='muted'>当天暂无安排</li>";
          html += "</ul>";
          box.innerHTML = html;
        });
    })
    .catch(showError);
}

/* -------------------------------------------------- 值班排班 ---------------- */
function dutyShift(d) {
  DUTY.m += d;
  if (DUTY.m < 1) { DUTY.m = 12; DUTY.y--; }
  if (DUTY.m > 12) { DUTY.m = 1; DUTY.y++; }
  dutyLoad();
}
function dutyToday() { DUTY = { y: new Date().getFullYear(), m: new Date().getMonth() + 1 }; dutyLoad(); }

function dutyLoad() {
  $("duty_title").textContent = DUTY.y + "年" + DUTY.m + "月";
  xhr("GET", "/api/duty/month?y=" + DUTY.y + "&m=" + DUTY.m)
    .then(function (duty) {
      return xhr("GET", "/api/holidays?y=" + DUTY.y)
        .then(function (hol) {
          HOL = hol.holidays || {};
          renderDuty(duty.month || {});
          dutyStats();
        });
    })
    .catch(showError);
}

function renderDuty(duties) {
  var grid = $("duty_grid");
  var heads = ["一", "二", "三", "四", "五", "六", "日"];
  var html = "";
  for (var i = 0; i < heads.length; i++) html += "<div class='cal-head'>" + heads[i] + "</div>";
  var y = DUTY.y, m = DUTY.m;
  var first = new Date(y, m - 1, 1);
  var startDow = (first.getDay() + 6) % 7;
  var days = new Date(y, m, 0).getDate();
  var tday = today();
  for (var s = 0; s < startDow; s++) {
    var pd = new Date(y, m - 1, s - startDow + 1);
    html += "<div class='cell other'><div class='dnum'>" + pd.getDate() + "</div></div>";
  }
  for (var d = 1; d <= days; d++) {
    var dt = y + "-" + pad2(m) + "-" + pad2(d);
    var entries = duties[dt] || [];
    html += "<div class='cell" + (dt === tday ? " today" : "") + "' onclick=\"dutyPick('" + dt + "')\" style='min-height:64px'>" +
      "<div class='dnum'>" + d + " " + holBadge(dt) + "</div>" + dutyChips(entries) + "</div>";
  }
  var tail = 7 - ((startDow + days) % 7 || 7);
  for (var e = 1; e <= tail; e++) {
    var nd = new Date(y, m - 1, days + e);
    html += "<div class='cell other'><div class='dnum'>" + nd.getDate() + "</div></div>";
  }
  grid.innerHTML = html;
}

function dutyPick(ds) {
  $("duty_date_show").textContent = ds;
  $("d_person").value = "";
  $("d_note").value = "";
  $("d_type").value = DICTS.duty_types[0] || "值班";
  openModal("duty_modal");
  dutyRefill(ds, $("d_type").value);
}

function dutyRefill(ds, t) {
  ds = ds || $("duty_date_show").textContent;
  t = t || $("d_type").value;
  xhr("GET", "/api/duty/month?y=" + ds.slice(0, 4) + "&m=" + parseInt(ds.slice(5, 7), 10))
    .then(function (d) {
      var entries = (d.month || {})[ds] || [];
      var cur = null;
      for (var i = 0; i < entries.length; i++) {
        if (entries[i][0] === t) { cur = entries[i]; break; }
      }
      $("d_person").value = (cur && cur[1]) ? cur[1] : "";
      var note = (cur && cur[2]) ? String(cur[2]).replace(/^原:/, "") : "";
      $("d_note").value = note;
    })
    .catch(function () {});
}

function dutySave() {
  var ds = $("duty_date_show").textContent;
  var name = $("d_person").value.trim();
  if (!name) return toast("请填写值班人姓名（可直接输入未登记人员）");
  var dt = $("d_type").value || "值班";
  xhr("POST", "/api/duty/save", { date: ds, duty_type: dt, person: name, note: $("d_note").value })
    .then(function () {
      toast("已保存（未登记姓名已自动加入名单）");
      closeModal("duty_modal");
      dutyLoad();
      loadPersons().then(function () {
        var pl = "";
        for (var i = 0; i < PERSONS.length; i++) pl += "<option value='" + esc(PERSONS[i].name) + "'>";
        $("d_person_list").innerHTML = pl;
        $("t_person_list").innerHTML = pl;
      }).catch(function () {});
    })
    .catch(showError);
}

function dutyRemove() {
  var ds = $("duty_date_show").textContent;
  var dt = $("d_type").value || "值班";
  if (!confirm("确定删除 " + ds + " 的「" + dt + "」排班吗？")) return;
  xhr("POST", "/api/duty/remove", { date: ds, duty_type: dt })
    .then(function () { toast("已删除"); closeModal("duty_modal"); dutyLoad(); })
    .catch(showError);
}

function dutyGenerate() {
  var s = $("duty_s").value, e = $("duty_e").value;
  if (!s || !e) return toast("请先选择自动排班起止日期（默认整年）");
  if (!confirm("按名单轮转生成 " + s + " ~ " + e + " 的「值班/节假日值班」排班？\n（督查类请手动安排；已有手动/排班的天不覆盖）")) return;
  xhr("POST", "/api/duty/generate", { start: s, end: e })
    .then(function (d) { toast("已生成 " + d.n + " 天排班"); dutyLoad(); })
    .catch(showError);
}

/* ---------- 批量排班（日期范围 / 开始日期＋天数） ---------- */
function dutyBatchMode() {
  var mode = document.querySelector("input[name=db_mode]:checked").value;
  $("db_row_range").style.display = (mode === "range") ? "" : "none";
  $("db_row_days").style.display = (mode === "days") ? "" : "none";
}

function openDutyBatch() {
  fillSelect("db_type", DICTS.duty_types, DICTS.duty_types[0] || "值班");
  xhr("GET", "/api/persons")
    .then(function (d) {
      var names = [];
      for (var i = 0; i < (d.rows || []).length; i++) names.push(d.rows[i].name);
      $("db_names").value = names.join("，");
    })
    .catch(function () {});
  var t = today();
  $("db_start").value = t;
  $("db_end").value = t;
  $("db_begin").value = t;
  dutyBatchMode();
  openModal("duty_batch_modal");
}

function submitDutyBatch() {
  var mode = document.querySelector("input[name=db_mode]:checked").value;
  var names = $("db_names").value.trim();
  if (!names) return toast("请填写值班人员（多个用逗号/顿号分隔）");
  var body = {
    mode: mode,
    duty_type: $("db_type").value || "值班",
    names: names,
    rotate_days: $("db_rotate").value,
    overwrite: (document.querySelector("input[name=db_conflict]:checked").value === "overwrite")
  };
  if (mode === "days") {
    body.begin = $("db_begin").value;
    body.days = $("db_days").value;
    if (!body.begin || !parseInt(body.days, 10) || parseInt(body.days, 10) < 1) {
      return toast("请填写开始日期与连续天数（正整数）");
    }
  } else {
    body.start = $("db_start").value;
    body.end = $("db_end").value;
    if (!body.start || !body.end) return toast("请选择起止日期");
    if (body.start > body.end) return toast("开始日期不能晚于结束日期");
  }
  xhr("POST", "/api/duty/batch", body)
    .then(function (d) {
      toast("已批量排班 " + d.n + " 天（" + d.start + " ~ " + d.end + "）");
      closeModal("duty_batch_modal");
      dutyLoad();
    })
    .catch(showError);
}

function dutyClearAuto() {
  var s = $("duty_s").value, e = $("duty_e").value;
  if (!confirm("清除 " + (s || "全年") + " ~ " + (e || "全年") + " 的自动排班？（手动保留）")) return;
  xhr("POST", "/api/duty/clear_auto", { start: s, end: e })
    .then(function () { toast("已清除"); dutyLoad(); })
    .catch(showError);
}

function dutyExport() {
  var s = $("duty_s").value || (new Date().getFullYear() + "-01-01");
  var e = $("duty_e").value || today();
  downloadUrl("/api/duty/export?start=" + encodeURIComponent(s) + "&end=" + encodeURIComponent(e));
}

function dutyStats() {
  xhr("GET", "/api/duty/stats?start=" + DUTY.y + "-01-01&end=" + DUTY.y + "-12-31")
    .then(function (d) {
      var rows = d.rows || [];
      var by = {};
      for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        if (!r || !r.name) continue;
        if (!by[r.name]) by[r.name] = [];
        by[r.name].push(r.duty_type + r.c);
      }
      var html = "<tr><th>" + DUTY.y + "年人员统计</th><th>类型·次数</th></tr>";
      var names = Object.keys(by);
      for (var j = 0; j < names.length; j++) {
        html += "<tr><td>" + esc(names[j]) + "</td><td>" + esc(by[names[j]].join("，")) + "</td></tr>";
      }
      if (!names.length) html += "<tr><td colspan='2' class='muted'>本年暂无排班</td></tr>";
      $("duty_stat").innerHTML = html;
    })
    .catch(function () {});
}

/* -------------------------------------------------- 统计 ---------------- */
function statsLoad() {
  var s = $("s_start").value, e = $("s_end").value;
  var year = new Date().getFullYear();
  var q = "start=" + encodeURIComponent(s) + "&end=" + encodeURIComponent(e) + "&year=" + year;
  $("stats_box").innerHTML =
    "<h3>每日工作数量 <span class='muted'>(" + (s || "—") + " ~ " + (e || "—") + ")</span></h3>" +
    "<img src='/api/stats/chart?kind=daily&" + q + "'>" +
    "<h3>按紧急程度</h3><img src='/api/stats/chart?kind=urgency&" + q + "'>" +
    "<h3>按来源级别</h3><img src='/api/stats/chart?kind=level&" + q + "'>" +
    "<h3>按责任人</h3><img src='/api/stats/chart?kind=person&" + q + "'>" +
    "<h3>工作时段热度</h3><img src='/api/stats/chart?kind=heat&" + q + "'>" +
    "<h3>" + year + "年各月工时</h3><img src='/api/stats/chart?kind=hours&" + q + "'>";
}

/* -------------------------------------------------- 基础数据 ---------------- */
function baseLoad() {
  loadPersons().then(renderPersons).catch(showError);
}

function renderPersons() {
  var tb = $("person_table").querySelector("tbody");
  var html = "";
  for (var i = 0; i < PERSONS.length; i++) {
    var p = PERSONS[i];
    html += "<tr data-id='" + p.id + "' onclick='personRowClick(this)'>" +
      "<td onclick='event.stopPropagation()'><input type='checkbox' class='prow' value='" + p.id + "'></td>" +
      "<td>" + esc(p.name) + "</td>" +
      "<td>" + (p.active ? "启用" : "<span class='muted'>停用</span>") + "</td>" +
      "<td>" + (p.dc || 0) + "</td></tr>";
  }
  tb.innerHTML = html;
}

function personRowClick(tr) {
  var rows = document.querySelectorAll("#person_table tbody tr");
  for (var i = 0; i < rows.length; i++) rows[i].className = "";
  tr.className = "sel";
  var cb = tr.querySelector("input[type=checkbox]");
  if (cb) cb.checked = true;
}

function personSel() {
  var out = [];
  var cbs = document.querySelectorAll("#person_table .prow:checked");
  for (var i = 0; i < cbs.length; i++) out.push(parseInt(cbs[i].value, 10));
  return out;
}

function personAdd() {
  var name = $("person_new").value.trim();
  if (!name) return toast("请输入姓名");
  xhr("POST", "/api/persons/add", { name: name })
    .then(function () {
      $("person_new").value = "";
      return loadPersons();
    })
    .then(function () {
      renderPersons();
      var pl = "";
      for (var i = 0; i < PERSONS.length; i++) pl += "<option value='" + esc(PERSONS[i].name) + "'>";
      $("t_person_list").innerHTML = pl;
      $("d_person_list").innerHTML = pl;
      toast("已新增");
    })
    .catch(showError);
}

function personToggle(active) {
  var ids = personSel();
  if (!ids.length) return toast("请先选中人员");
  var seq = Promise.resolve();
  for (var i = 0; i < ids.length; i++) {
    (function (pid, act) {
      seq = seq.then(function () { return xhr("POST", "/api/persons/toggle", { id: pid, active: act }); });
    })(ids[i], active);
  }
  seq.then(loadPersons).then(renderPersons).catch(showError);
}

function personHardDel() {
  var ids = personSel();
  if (!ids.length) return toast("请先选中人员");
  var p = null;
  for (var i = 0; i < PERSONS.length; i++) if (PERSONS[i].id === ids[0]) p = PERSONS[i];
  var msg = "确定彻底删除「" + (p ? p.name : "") + "」吗？\n· 从值班名单移除（不可恢复）；\n· 历史排班保留（回显原姓名）；\n· 工作记录负责人保留。";
  if (!confirm(msg)) return;
  xhr("POST", "/api/persons/hard_delete", { id: ids[0] })
    .then(loadPersons).then(renderPersons)
    .then(function () { toast("已彻底删除，历史排班与负责人均已保留"); })
    .catch(showError);
}

function personRestoreAll() {
  xhr("GET", "/api/persons")
    .then(function (d) {
      var rows = d.rows || [];
      var seq = Promise.resolve();
      for (var i = 0; i < rows.length; i++) {
        if (rows[i].active) continue;
        (function (pid) {
          seq = seq.then(function () { return xhr("POST", "/api/persons/toggle", { id: pid, active: true }); });
        })(rows[i].id);
      }
      return seq;
    })
    .then(loadPersons).then(renderPersons)
    .then(function () { toast("已全部恢复启用"); })
    .catch(showError);
}

/* -------------------------------------------------- 回收站 ---------------- */
function recycleLoad() {
  xhr("GET", "/api/recycle/tasks")
    .then(function (d) {
      var rows = d.rows || [];
      var html = "";
      for (var i = 0; i < rows.length; i++) {
        var t = rows[i];
        html += "<tr data-id='" + t.id + "' onclick='recycleRowClick(this)'>" +
          "<td onclick='event.stopPropagation()'><input type='checkbox' class='rrow' value='" + t.id + "'></td>" +
          "<td>" + esc(t.name) + "</td>" +
          "<td>" + esc(String(t.start_time || "").slice(0, 16)) + "</td>" +
          "<td>" + esc(String(t.end_time || "").slice(0, 16)) + "</td>" +
          "<td>" + esc(t.person || "") + "</td>" +
          "<td>" + esc(String(t.updated_at || "").slice(0, 16)) + "</td></tr>";
      }
      $("recycle_table").querySelector("tbody").innerHTML = html;
    })
    .catch(showError);
}

function recycleRowClick(tr) {
  var rows = document.querySelectorAll("#recycle_table tbody tr");
  for (var i = 0; i < rows.length; i++) rows[i].className = "";
  tr.className = "sel";
  var cb = tr.querySelector("input[type=checkbox]");
  if (cb) cb.checked = true;
}

function recycleSel() {
  var out = [];
  var cbs = document.querySelectorAll("#recycle_table .rrow:checked");
  for (var i = 0; i < cbs.length; i++) out.push(parseInt(cbs[i].value, 10));
  return out;
}

function recycleRestore() {
  var ids = recycleSel();
  if (!ids.length) return toast("请先选中记录");
  xhr("POST", "/api/recycle/restore", { ids: ids }).then(recycleLoad).catch(showError);
}

function recyclePurge() {
  var ids = recycleSel();
  if (!ids.length) return toast("请先选中记录");
  if (!confirm("彻底删除选中的 " + ids.length + " 条？（不可恢复）")) return;
  xhr("POST", "/api/recycle/purge", { ids: ids }).then(recycleLoad).catch(showError);
}

/* -------------------------------------------------- 启动 ---------------- */
window.addEventListener("DOMContentLoaded", function () { init(); });