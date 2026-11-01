"use strict";

const state = {
  homes: [],
  rooms: [],
  devices: [],
  activeHomeId: null,
  activeRoomId: "all",
  onlineFilter: "online",
  homeRequest: null,
  detailRequest: null,
  loginPromise: null,
};

const elements = {
  loginView: document.querySelector("#login-view"),
  loginStatus: document.querySelector("#login-status"),
  loginQr: document.querySelector("#login-qr"),
  qrFrame: document.querySelector("#qr-frame"),
  loginRetry: document.querySelector("#login-retry"),
  workspace: document.querySelector("#workspace"),
  homePicker: document.querySelector("#home-picker"),
  homeSelect: document.querySelector("#home-select"),
  homeName: document.querySelector("#home-name"),
  deviceTotal: document.querySelector("#device-total"),
  roomList: document.querySelector("#room-list"),
  refreshButton: document.querySelector("#refresh-button"),
  logoutButton: document.querySelector("#logout-button"),
  statusFilter: document.querySelector("#status-filter"),
  onlineCount: document.querySelector("#online-count"),
  offlineCount: document.querySelector("#offline-count"),
  allCount: document.querySelector("#all-count"),
  metricTotal: document.querySelector("#metric-total"),
  metricOnline: document.querySelector("#metric-online"),
  metricOffline: document.querySelector("#metric-offline"),
  sectionTitle: document.querySelector("#section-title"),
  sectionSummary: document.querySelector("#section-summary"),
  lastUpdated: document.querySelector("#last-updated"),
  notice: document.querySelector("#notice"),
  loading: document.querySelector("#loading"),
  deviceList: document.querySelector("#device-list"),
  emptyState: document.querySelector("#empty-state"),
  dialog: document.querySelector("#device-dialog"),
  dialogTitle: document.querySelector("#dialog-title"),
  dialogModel: document.querySelector("#dialog-model"),
  dialogContent: document.querySelector("#dialog-content"),
  dialogClose: document.querySelector("#dialog-close"),
  toast: document.querySelector("#toast"),
};

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

async function requestJson(url, options = {}) {
  const { skipAuthHandler = false, ...fetchOptions } = options;
  const response = await fetch(url, fetchOptions);
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = await response.json();
      if (body.detail) message = typeof body.detail === "string" ? body.detail : message;
    } catch (_) {
      // 保留 HTTP 状态错误，不覆盖原始响应解析问题。
    }
    if (response.status === 503 && !skipAuthHandler) {
      showLoginView();
      void startLogin();
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function showLoginView(message = "") {
  state.homeRequest?.abort();
  state.detailRequest?.abort();
  state.homes = [];
  state.rooms = [];
  state.devices = [];
  state.activeHomeId = null;
  state.activeRoomId = "all";
  if (elements.dialog.open) elements.dialog.close();
  elements.homeSelect.replaceChildren();
  elements.homePicker.hidden = true;
  elements.refreshButton.hidden = true;
  elements.logoutButton.hidden = true;
  elements.workspace.hidden = true;
  elements.loginView.hidden = false;
  elements.loading.hidden = true;
  elements.deviceList.replaceChildren();
  elements.roomList.replaceChildren();
  if (message) elements.loginStatus.textContent = message;
}

function showWorkspace() {
  elements.loginView.hidden = true;
  elements.workspace.hidden = false;
  elements.homePicker.hidden = false;
  elements.refreshButton.hidden = false;
  elements.logoutButton.hidden = false;
  elements.logoutButton.disabled = false;
  elements.qrFrame.hidden = true;
  elements.loginQr.removeAttribute("src");
  showNotice("");
}

function showLoginError(message) {
  elements.qrFrame.hidden = true;
  elements.loginStatus.textContent = message;
  elements.loginRetry.hidden = false;
}

async function performLogin() {
  showLoginView();
  elements.loginRetry.hidden = true;
  elements.qrFrame.hidden = true;
  elements.loginStatus.textContent = "正在获取登录二维码…";
  try {
    const login = await requestJson("/api/auth/qr-login", {
      method: "POST",
      skipAuthHandler: true,
    });
    if (login.status !== "authenticated") {
      elements.loginQr.src = login.qr_url;
      elements.qrFrame.hidden = false;
      elements.loginStatus.textContent = "等待扫码确认；二维码有效期以米家提示为准";
      const result = await requestJson("/api/auth/qr-login/complete", {
        method: "POST",
        skipAuthHandler: true,
      });
      if (result.status !== "authenticated") throw new Error("米家未确认登录");
    }
    elements.loginStatus.textContent = "登录成功，正在加载设备…";
    await initialize();
  } catch (error) {
    showLoginError(`登录未完成：${error.message}。请重新获取二维码后再试。`);
  }
}

function startLogin() {
  if (!state.loginPromise) {
    state.loginPromise = performLogin().finally(() => {
      state.loginPromise = null;
    });
  }
  return state.loginPromise;
}

function showNotice(message, isError = false) {
  elements.notice.textContent = message;
  elements.notice.classList.toggle("error", isError);
  elements.notice.hidden = !message;
}

function setLoading(loading) {
  elements.loading.hidden = !loading;
  elements.refreshButton.disabled = loading || !state.activeHomeId;
  elements.homeSelect.disabled = loading || state.homes.length === 0;
}

function deviceGlyph(model = "") {
  if (model.includes("aircondition")) return "空";
  if (model.includes("light") || model.includes("lamp")) return "灯";
  if (model.includes("plug") || model.includes("outlet")) return "插";
  if (model.includes("speaker")) return "音";
  if (model.includes("sensor_gas")) return "气";
  if (model.includes("miwifi")) return "网";
  return "设";
}

function onlineLabel(online) {
  if (online === true) return { text: "在线", className: "online" };
  if (online === false) return { text: "离线", className: "offline" };
  return { text: "状态未知", className: "unknown" };
}

function roomName(roomId) {
  if (roomId === "all") return "全屋设备";
  if (roomId === "unassigned") return "未分配房间";
  return state.rooms.find((room) => String(room.id) === roomId)?.name || "房间设备";
}

function devicesInRoom() {
  if (state.activeRoomId === "all") return state.devices;
  if (state.activeRoomId === "unassigned") {
    return state.devices.filter((device) => !device.room_id);
  }
  return state.devices.filter((device) => String(device.room_id) === state.activeRoomId);
}

function visibleDevices() {
  const devices = devicesInRoom();
  if (state.onlineFilter === "online") return devices.filter((device) => device.online === true);
  if (state.onlineFilter === "offline") return devices.filter((device) => device.online === false);
  return devices;
}

function renderRooms() {
  elements.roomList.replaceChildren();
  const rooms = [
    { id: "all", name: "全屋", count: state.devices.length },
    ...state.rooms.map((room) => ({
      id: String(room.id),
      name: room.name,
      count: state.devices.filter((device) => String(device.room_id) === String(room.id)).length,
    })),
  ];
  const unassignedCount = state.devices.filter((device) => !device.room_id).length;
  if (unassignedCount) rooms.push({ id: "unassigned", name: "未分配", count: unassignedCount });

  rooms.forEach((room) => {
    const button = createElement("button", "room-button");
    button.type = "button";
    button.classList.toggle("active", room.id === state.activeRoomId);
    button.setAttribute("aria-pressed", String(room.id === state.activeRoomId));
    button.append(createElement("span", "", room.name), createElement("span", "room-count", room.count));
    button.addEventListener("click", () => {
      state.activeRoomId = room.id;
      renderRooms();
      renderDevices();
    });
    elements.roomList.append(button);
  });
}

function renderDevices() {
  const roomDevices = devicesInRoom();
  const devices = visibleDevices();
  const onlineCount = roomDevices.filter((device) => device.online === true).length;
  const offlineCount = roomDevices.filter((device) => device.online === false).length;
  const unknownCount = roomDevices.length - onlineCount - offlineCount;
  const homeOnlineCount = state.devices.filter((device) => device.online === true).length;
  const homeOfflineCount = state.devices.filter((device) => device.online === false).length;
  elements.metricTotal.textContent = state.devices.length;
  elements.metricOnline.textContent = homeOnlineCount;
  elements.metricOffline.textContent = homeOfflineCount;
  elements.onlineCount.textContent = onlineCount;
  elements.offlineCount.textContent = offlineCount;
  elements.allCount.textContent = roomDevices.length;
  elements.statusFilter.querySelectorAll("button").forEach((button) => {
    const active = button.dataset.filter === state.onlineFilter;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });

  elements.sectionTitle.textContent = roomName(state.activeRoomId);
  elements.sectionSummary.textContent = `当前显示 ${devices.length} 台，房间共 ${roomDevices.length} 台设备${unknownCount ? `，${unknownCount} 台状态未知` : ""}`;
  elements.deviceList.replaceChildren();
  elements.emptyState.hidden = devices.length !== 0;
  elements.emptyState.querySelector("h2").textContent = roomDevices.length ? "当前筛选下没有设备" : "这个房间还没有设备";
  elements.emptyState.querySelector("p").textContent = roomDevices.length ? "切换在线状态，或点击“全部”查看。" : "切换到全屋或其他房间查看。";

  devices.forEach((device) => {
    const status = onlineLabel(device.online);
    const row = createElement("button", "device-row");
    row.type = "button";
    row.setAttribute("aria-label", `查看${device.display_name || device.name}详情`);

    const glyph = createElement("span", "device-glyph", deviceGlyph(device.model));
    glyph.setAttribute("aria-hidden", "true");

    const nameBlock = createElement("span");
    nameBlock.append(createElement("span", "device-name", device.display_name || device.name || "未命名设备"));
    if (device.display_name && device.name && device.display_name !== device.name) {
      nameBlock.append(createElement("span", "device-original-name", device.name));
    }

    const model = createElement("span", "device-model", device.model || "未知型号");
    const statusElement = createElement("span", `device-state ${status.className}`);
    statusElement.append(createElement("span", "state-dot"), createElement("span", "", status.text));
    const open = createElement("span", "device-open", "›");
    open.setAttribute("aria-hidden", "true");

    row.append(glyph, nameBlock, model, statusElement, open);
    row.addEventListener("click", () => openDevice(device));
    elements.deviceList.append(row);
  });
}

async function loadHome(homeId) {
  state.homeRequest?.abort();
  const controller = new AbortController();
  state.homeRequest = controller;
  state.activeHomeId = homeId;
  state.activeRoomId = "all";
  setLoading(true);
  showNotice("");
  elements.deviceList.replaceChildren();
  elements.emptyState.hidden = true;
  elements.lastUpdated.textContent = "";

  try {
    const query = encodeURIComponent(homeId);
    const [rooms, devices] = await Promise.all([
      requestJson(`/api/homes/${query}/rooms`, { signal: controller.signal }),
      requestJson(`/api/devices?home_id=${query}`, { signal: controller.signal }),
    ]);
    if (state.activeHomeId !== homeId) return;
    state.rooms = rooms;
    state.devices = devices;
    const home = state.homes.find((item) => String(item.id) === homeId);
    elements.homeName.textContent = home?.name || "我的家庭";
    elements.deviceTotal.textContent = `${devices.length} 台设备`;
    elements.lastUpdated.textContent = `更新于 ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
    localStorage.setItem("mijia.homeId", homeId);
    renderRooms();
    renderDevices();
  } catch (error) {
    if (error.name === "AbortError") return;
    showNotice(`无法获取设备：${error.message}`, true);
    elements.sectionSummary.textContent = "请检查米家登录状态后刷新";
  } finally {
    if (state.homeRequest === controller) setLoading(false);
  }
}

function accessLabel(access) {
  if (access === "r") return "只读";
  if (access === "w") return "只写";
  return "读写";
}

function propertyValue(property) {
  if (property.read_error) return `读取失败：${property.read_error}`;
  if (!property.access.includes("r")) return "该属性仅可写入，无法读取当前值";
  if (typeof property.value === "boolean") return property.value ? "是" : "否";
  if (property.value === null || property.value === undefined) return "暂无数据";
  const choice = property.choices?.find((item) => item.value === property.value);
  return choice ? `${choice.description}（${property.value}）` : String(property.value);
}

let toastTimer;
function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", isError);
  elements.toast.hidden = false;
  toastTimer = setTimeout(() => { elements.toast.hidden = true; }, 4500);
}

async function runControl(button, operation, successMessage) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "发送中…";
  try {
    await operation();
    showToast(successMessage);
  } catch (error) {
    showToast(`控制失败：${error.message}`, true);
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

function readControlValue(input) {
  if (input.dataset.kind === "values") {
    return input.controlValues[Number(input.value)];
  }
  if (input.dataset.kind === "number") {
    if (input.value.trim() === "") throw new Error("请输入要设置的数值");
    const value = Number(input.value);
    if (!Number.isFinite(value)) throw new Error("请输入有效数值");
    return value;
  }
  return input.value;
}

async function setProperty(did, property, input, button) {
  let value;
  try {
    value = readControlValue(input);
  } catch (error) {
    showToast(error.message, true);
    return;
  }
  await runControl(
    button,
    () => requestJson(`/api/devices/${encodeURIComponent(did)}/properties/${encodeURIComponent(property.name)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    }),
    `${property.description || property.name}设置指令已发送`,
  );
}

function createPropertyControl(did, property) {
  const wrapper = createElement("div", "property-control");
  let input;
  if (property.choices?.length) {
    input = createElement("select", "control-input");
    input.controlValues = property.choices.map((choice) => choice.value);
    property.choices.forEach((choice, index) => {
      const option = createElement("option", "", `${choice.description}（${choice.value}）`);
      option.value = String(index);
      input.append(option);
    });
    input.dataset.kind = "values";
    const currentIndex = input.controlValues.findIndex((value) => value === property.value);
    if (currentIndex >= 0) input.value = String(currentIndex);
  } else if (property.type === "bool") {
    input = createElement("select", "control-input");
    input.controlValues = [true, false];
    ["是（true）", "否（false）"].forEach((label, index) => {
      const option = createElement("option", "", label);
      option.value = String(index);
      input.append(option);
    });
    input.dataset.kind = "values";
    if (typeof property.value === "boolean") input.value = property.value ? "0" : "1";
  } else if (["int", "uint", "float"].includes(property.type)) {
    input = createElement("input", "control-input");
    input.type = "number";
    input.dataset.kind = "number";
    input.placeholder = "输入数值";
    if (property.range?.length >= 2) {
      input.min = String(property.range[0]);
      input.max = String(property.range[1]);
      input.step = String(property.range[2] || 1);
    }
    if (property.value !== null && property.value !== undefined) input.value = String(property.value);
  } else {
    input = createElement("input", "control-input");
    input.type = "text";
    input.dataset.kind = "text";
    input.value = property.value || "";
  }
  input.setAttribute("aria-label", `设置${property.description || property.name}`);
  const button = createElement("button", "control-button", "设置");
  button.type = "button";
  button.addEventListener("click", () => setProperty(did, property, input, button));
  wrapper.append(input, button);
  return wrapper;
}

async function runDeviceAction(did, action, values, button) {
  const options = { method: "POST" };
  if (values !== null) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify({ values });
  }
  const label = action.display_name || action.description || action.name;
  await runControl(
    button,
    () => requestJson(`/api/devices/${encodeURIComponent(did)}/actions/${encodeURIComponent(action.name)}`, options),
    `${label}指令已发送，请观察设备实际响应`,
  );
}

function createActionParameterField(parameter) {
  let input;
  let kind = "text";
  let controlValues = null;
  if (parameter.choices?.length) {
    input = createElement("select", "control-input");
    controlValues = parameter.choices.map((choice) => choice.value);
    input.append(createElement("option", "", "请选择"));
    parameter.choices.forEach((choice, index) => {
      const option = createElement("option", "", `${choice.description}（${choice.value}）`);
      option.value = String(index);
      input.append(option);
    });
    input.firstElementChild.value = "";
    kind = "values";
  } else if (parameter.type === "bool") {
    input = createElement("select", "control-input");
    controlValues = [true, false];
    const placeholder = createElement("option", "", "请选择");
    placeholder.value = "";
    input.append(placeholder);
    ["是", "否"].forEach((label, index) => {
      const option = createElement("option", "", label);
      option.value = String(index);
      input.append(option);
    });
    kind = "values";
  } else if (["int", "uint", "float"].includes(parameter.type)) {
    input = createElement("input", "control-input");
    input.type = "number";
    if (parameter.range?.length >= 2) {
      input.min = String(parameter.range[0]);
      input.max = String(parameter.range[1]);
      input.step = String(parameter.range[2] || 1);
    }
    kind = "number";
  } else {
    input = createElement("textarea", "control-input action-textarea");
    input.rows = 2;
  }
  input.required = true;
  const label = createElement("label", "action-parameter");
  label.append(createElement("span", "", parameter.description || parameter.name), input);
  if (parameter.range) {
    label.append(createElement("small", "", `范围 ${parameter.range[0]}～${parameter.range[1]}，步长 ${parameter.range[2] || 1}`));
  }
  return { parameter, input, kind, controlValues, label };
}

function readActionParameter(field) {
  const rawValue = field.input.value.trim();
  if (!rawValue) throw new Error(`请填写${field.parameter.description || field.parameter.name}`);
  if (field.kind === "values") return field.controlValues[Number(rawValue)];
  if (field.kind === "number") {
    const value = Number(rawValue);
    if (!Number.isFinite(value)) throw new Error(`${field.parameter.description}必须是有效数值`);
    return value;
  }
  return field.input.value;
}

let actionFormSequence = 0;
function createActionItem(did, action) {
  const item = createElement("div", "action-item");
  const label = action.display_name || action.description || action.name;
  if (Array.isArray(action.parameters) && action.parameters.length === 0) {
    const button = createElement("button", "action-button", label);
    button.type = "button";
    button.addEventListener("click", () => runDeviceAction(did, action, null, button));
    item.append(button);
    return item;
  }

  const toggle = createElement("button", "action-button action-expand", label);
  toggle.type = "button";
  toggle.setAttribute("aria-expanded", "false");
  const form = createElement("form", "action-form");
  form.id = `action-form-${++actionFormSequence}`;
  form.hidden = true;
  toggle.setAttribute("aria-controls", form.id);
  toggle.addEventListener("click", () => {
    form.hidden = !form.hidden;
    toggle.setAttribute("aria-expanded", String(!form.hidden));
  });

  const typedFields = Array.isArray(action.parameters)
    ? action.parameters.map(createActionParameterField)
    : null;
  let fallbackInput = null;
  if (typedFields) {
    typedFields.forEach((field) => form.append(field.label));
  } else {
    fallbackInput = createElement("textarea", "control-input action-textarea");
    fallbackInput.rows = 2;
    fallbackInput.placeholder = "无参数留空；有参数填写 JSON 数组，如 [1, 26]";
    const fallbackLabel = createElement("label", "action-parameter");
    fallbackLabel.append(createElement("span", "", "动作参数（规格不可用）"), fallbackInput);
    form.append(fallbackLabel);
  }

  const submit = createElement("button", "control-button", `执行${label}`);
  submit.type = "submit";
  form.append(submit);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    let values;
    try {
      if (typedFields) {
        values = typedFields.map(readActionParameter);
      } else {
        const rawValue = fallbackInput.value.trim();
        values = rawValue ? JSON.parse(rawValue) : null;
        if (values !== null && !Array.isArray(values)) throw new Error("动作参数必须是 JSON 数组");
      }
    } catch (error) {
      showToast(error instanceof SyntaxError ? "动作参数不是有效的 JSON" : error.message, true);
      return;
    }
    runDeviceAction(did, action, values, submit);
  });
  item.append(toggle, form);
  return item;
}

function renderDeviceDetail(detail) {
  elements.dialogTitle.textContent = detail.device.display_name || detail.device.name || "设备详情";
  elements.dialogModel.textContent = detail.device.model || "未知型号";
  elements.dialogContent.replaceChildren();

  const identity = createElement("section", "detail-section");
  identity.append(createElement("h3", "", "设备 ID"), createElement("div", "did-value", detail.device.did));
  if (detail.device.name && detail.device.name !== detail.device.display_name) {
    identity.append(createElement("p", "detail-meta", `米家原始名称：${detail.device.name}`));
  }

  const properties = createElement("section", "detail-section");
  properties.append(createElement("h3", "", `属性（${detail.properties.length}）`));
  const propertyList = createElement("div", "detail-list");
  detail.properties.forEach((property) => {
    const row = createElement("div", "detail-row");
    const header = createElement("div", "detail-row-header");
    header.append(createElement("strong", "", property.description || property.name), createElement("small", "", accessLabel(property.access)));
    row.append(header, createElement("div", "detail-value", propertyValue(property)));
    row.append(createElement("p", "detail-meta", `${property.name} · ${property.type}`));
    if (property.access.includes("w")) row.append(createPropertyControl(detail.device.did, property));
    propertyList.append(row);
  });
  properties.append(propertyList);

  const actions = createElement("section", "detail-section");
  actions.append(createElement("h3", "", `设备动作（${detail.actions.length}）`));
  const actionList = createElement("div", "action-list");
  detail.actions.forEach((action) => actionList.append(createActionItem(detail.device.did, action)));
  actions.append(actionList);
  elements.dialogContent.append(identity, properties, actions);
}

async function openDevice(device) {
  state.detailRequest?.abort();
  const controller = new AbortController();
  state.detailRequest = controller;
  elements.dialogTitle.textContent = device.display_name || device.name;
  elements.dialogModel.textContent = device.model || "";
  elements.dialogContent.replaceChildren(createElement("p", "dialog-loading", "正在读取设备详情…"));
  if (!elements.dialog.open) elements.dialog.showModal();

  try {
    const detail = await requestJson(`/api/devices/${encodeURIComponent(device.did)}`, { signal: controller.signal });
    renderDeviceDetail(detail);
  } catch (error) {
    if (error.name === "AbortError") return;
    elements.dialogContent.replaceChildren(createElement("p", "dialog-error", `无法读取设备详情：${error.message}`));
  }
}

async function logout() {
  if (!window.confirm("退出后将删除本机保存的米家认证文件，需要重新扫码登录。确定退出吗？")) return;
  elements.logoutButton.disabled = true;
  try {
    await requestJson("/api/auth/logout", { method: "POST", skipAuthHandler: true });
    showLoginView("已退出登录，正在获取新的登录二维码…");
    await startLogin();
  } catch (error) {
    elements.logoutButton.disabled = false;
    showNotice(`退出登录失败：${error.message}`, true);
  }
}

async function initialize() {
  let auth;
  try {
    auth = await requestJson("/api/auth/status", { skipAuthHandler: true });
  } catch (error) {
    showLoginView();
    showLoginError(`无法检查登录状态：${error.message}`);
    return;
  }
  if (!auth.authenticated) {
    showLoginView();
    await startLogin();
    return;
  }

  showWorkspace();
  elements.homeSelect.replaceChildren();
  try {
    state.homes = await requestJson("/api/homes");
    state.homes.forEach((home) => {
      const option = createElement("option", "", home.name || home.id);
      option.value = String(home.id);
      elements.homeSelect.append(option);
    });
    if (!state.homes.length) {
      setLoading(false);
      showNotice("米家账号下暂未找到家庭。", true);
      elements.sectionSummary.textContent = "请先在米家 App 中添加家庭和设备";
      return;
    }
    const savedHomeId = localStorage.getItem("mijia.homeId");
    const homeId = state.homes.some((home) => String(home.id) === savedHomeId)
      ? savedHomeId
      : String(state.homes[0].id);
    elements.homeSelect.value = homeId;
    await loadHome(homeId);
  } catch (error) {
    if (!elements.loginView.hidden) return;
    setLoading(false);
    showNotice(`无法连接米家：${error.message}`, true);
    elements.sectionSummary.textContent = "请检查服务状态后刷新";
  }
}

elements.statusFilter.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-filter]");
  if (!button) return;
  state.onlineFilter = button.dataset.filter;
  renderDevices();
});
elements.homeSelect.addEventListener("change", (event) => loadHome(event.target.value));
elements.refreshButton.addEventListener("click", () => state.activeHomeId && loadHome(state.activeHomeId));
elements.logoutButton.addEventListener("click", logout);
elements.loginRetry.addEventListener("click", () => startLogin());
elements.dialogClose.addEventListener("click", () => elements.dialog.close());
elements.dialog.addEventListener("close", () => state.detailRequest?.abort());
elements.dialog.addEventListener("click", (event) => {
  if (event.target === elements.dialog) {
    const bounds = elements.dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) {
      elements.dialog.close();
    }
  }
});

initialize();
