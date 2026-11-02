/**
 * Dialogue Engine - Real-Time Web & Mobile Cowork Application.
 * Полноценный визуальный редактор графов для совместной работы в браузере.
 */

// --- СОСТОЯНИЕ ПРИЛОЖЕНИЯ ---
const state = {
  project: {
    metadata: { title: "Новый проект" },
    nodes: [],
    connections: [],
    characters: []
  },
  collaborators: [],
  myUser: {
    id: "user_" + Math.random().toString(36).substr(2, 6),
    name: "Участник",
    color: "#4a90e2",
    device: "desktop"
  },
  zoom: 1.0,
  pan: { x: window.innerWidth / 4, y: window.innerHeight / 4 },
  selectedNodeId: null,
  ws: null,
  activePort: null, // для мобильного соединения тапом
  cableDrag: null,  // { fromNodeId, outIdx, startX, startY }
  isPanning: false,
  panStart: { x: 0, y: 0 },
  nodeDrag: null,   // { node, startX, startY, origX, origY }
  pinchStartDist: null,
  initialPinchZoom: 1.0
};

// --- ОПРЕДЕЛЕНИЕ ТИПА УСТРОЙСТВА ---
function detectDevice() {
  const ua = navigator.userAgent.toLowerCase();
  const isTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  const isMobile = /mobile|iphone|ipod|android.*mobile/.test(ua);
  const isTablet = /ipad|tablet|(android(?!.*mobile))/.test(ua);

  if (isMobile) return "phone";
  if (isTablet) return "tablet";
  if (isTouch) return "touch_pc";
  return "desktop";
}

// --- ИНИЦИАЛИЗАЦИЯ И СЕТЬ ---
window.addEventListener("DOMContentLoaded", () => {
  state.myUser.device = detectDevice();
  const savedName = localStorage.getItem("de_user_name");
  if (savedName) {
    state.myUser.name = savedName;
  } else {
    const devLabel = state.myUser.device === "phone" ? "📱 Телефон" : (state.myUser.device === "tablet" ? "📟 Планшет" : "💻 ПК");
    state.myUser.name = `Автор (${devLabel})`;
  }

  const nameInput = document.getElementById("inputMyName");
  if (nameInput) nameInput.value = state.myUser.name;

  setupCanvasEvents();
  connectWebSocket();
  setupTouchPinch();
  setupChatKey();
});

function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;
  console.log("[Cowork] Connecting to:", wsUrl);

  const ws = new WebSocket(wsUrl);
  state.ws = ws;

  ws.onopen = () => {
    console.log("[Cowork] Connected!");
    // Отправляем информацию о себе
    ws.send(JSON.stringify(state.myUser));
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleServerMessage(msg);
    } catch (e) {
      console.error("[Cowork] Parse error:", e);
    }
  };

  ws.onclose = () => {
    console.log("[Cowork] Disconnected. Reconnecting in 2s...");
    setTimeout(connectWebSocket, 2000);
  };

  ws.onerror = (err) => {
    console.error("[Cowork] WebSocket error:", err);
  };
}

// --- ОБРАБОТКА СООБЩЕНИЙ СЕРВЕРА ---
function handleServerMessage(msg) {
  switch (msg.type) {
    case "init":
      state.project = msg.project || state.project;
      state.collaborators = msg.collaborators || [];
      if (msg.user) state.myUser = msg.user;
      updateHeaderInfo();
      renderAll();
      if (msg.activity) {
        msg.activity.forEach(addChatMsg);
      }
      break;

    case "user_joined":
      state.collaborators = msg.collaborators || [];
      updateCollaboratorsUI();
      addChatMsg({ text: `👋 ${msg.user.name} присоединился`, user: "Система", color: "#888888", time: "" });
      break;

    case "user_left":
      state.collaborators = msg.collaborators || [];
      updateCollaboratorsUI();
      removeRemoteCursor(msg.client_id);
      break;

    case "node_move":
      const nodeToMove = state.project.nodes.find(n => n.id === msg.id);
      if (nodeToMove) {
        nodeToMove.x = msg.x;
        nodeToMove.y = msg.y;
        updateNodeElementPosition(nodeToMove);
        renderConnections();
        showNodeEditingHalo(msg.id, msg.user, msg.color);
      }
      break;

    case "node_create":
      if (!state.project.nodes.some(n => n.id === msg.node.id)) {
        state.project.nodes.push(msg.node);
        renderNode(msg.node);
      }
      break;

    case "node_update":
      const idx = state.project.nodes.findIndex(n => n.id === msg.node.id);
      if (idx !== -1) {
        state.project.nodes[idx] = msg.node;
        renderNode(msg.node); // обновляем вид карточки
        renderConnections();
      }
      break;

    case "node_delete":
      state.project.nodes = state.project.nodes.filter(n => n.id !== msg.id);
      state.project.connections = state.project.connections.filter(c => c.from !== msg.id && c.to !== msg.id);
      const el = document.getElementById(`node_${msg.id}`);
      if (el) el.remove();
      renderConnections();
      break;

    case "connection_create":
      const exists = state.project.connections.some(
        c => c.from === msg.connection.from && c.out_idx === msg.connection.out_idx && c.to === msg.connection.to
      );
      if (!exists) {
        state.project.connections.push(msg.connection);
        renderConnections();
      }
      break;

    case "connection_delete":
      state.project.connections = state.project.connections.filter(
        c => !(c.from === msg.connection.from && c.out_idx === msg.connection.out_idx && c.to === msg.connection.to)
      );
      renderConnections();
      break;

    case "cursor_move":
      updateRemoteCursor(msg.client_id, msg.user, msg.color, msg.x, msg.y);
      break;

    case "chat_message":
      addChatMsg(msg.message);
      break;

    case "notification":
      showToast(msg.text);
      break;
  }
}

// --- ОТПРАВКА СООБЩЕНИЙ НА СЕРВЕР ---
function sendServer(msg) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(msg));
  }
}

// --- РЕНДЕРИНГ ГРАФА ---
function renderAll() {
  const container = document.getElementById("nodesContainer");
  container.innerHTML = "";
  state.project.nodes.forEach(node => renderNode(node));
  renderConnections();
  applyWorldTransform();
}

function applyWorldTransform() {
  const world = document.getElementById("canvasWorld");
  world.style.transform = `translate(${state.pan.x}px, ${state.pan.y}px) scale(${state.zoom})`;
  const zoomLbl = document.getElementById("lblZoom");
  if (zoomLbl) zoomLbl.innerText = Math.round(state.zoom * 100) + "%";
}

function getNodeHeaderColor(node) {
  if (node.custom_data && node.custom_data.header_color) return node.custom_data.header_color;
  switch (node.type) {
    case "choice": return "#e67e22";
    case "condition": return "#9b59b6";
    case "music": return "#1abc9c";
    case "label": return "#d35400";
    default: return "#4a90e2";
  }
}

function renderNode(node) {
  let el = document.getElementById(`node_${node.id}`);
  if (!el) {
    el = document.createElement("div");
    el.id = `node_${node.id}`;
    el.className = "node-card";
    document.getElementById("nodesContainer").appendChild(el);
  }

  const hColor = getNodeHeaderColor(node);
  const badgeLabel = {
    story: "СЮЖЕТ",
    choice: "ВЫБОР",
    condition: "УСЛОВИЕ",
    music: "МУЗЫКА",
    label: "МЕТКА"
  }[node.type] || "БЛОК";

  el.style.left = `${node.x}px`;
  el.style.top = `${node.y}px`;

  el.innerHTML = `
    <!-- Входной порт -->
    <div class="port port-input" data-nid="${node.id}" data-type="input" title="Вход (Input)"></div>

    <!-- Шапка блока -->
    <div class="node-header" style="background-color: ${hColor};">
      <span class="node-title">${escapeHtml(node.title || "Безымянный")}</span>
      <div class="node-actions">
        <button class="node-action-btn" onclick="openNodeModal('${node.id}')" title="Редактировать">✏️</button>
        <button class="node-action-btn" onclick="deleteNode('${node.id}')" title="Удалить">✕</button>
      </div>
    </div>

    <!-- Тело блока -->
    <div class="node-body">
      <span class="node-badge" style="background-color: ${hColor}33; color: ${hColor};">${badgeLabel}</span>
      <div>${escapeHtml(node.content || "").replace(/\n/g, "<br>")}</div>
    </div>

    <!-- Выходной порт -->
    <div class="port port-output" data-nid="${node.id}" data-idx="0" data-type="output" title="Выход (Output)"></div>
  `;

  setupNodeDrag(el, node);
  setupPortClick(el, node);
}

function updateNodeElementPosition(node) {
  const el = document.getElementById(`node_${node.id}`);
  if (el) {
    el.style.left = `${node.x}px`;
    el.style.top = `${node.y}px`;
  }
}

// --- ОТРИСОВКА СОЕДИНЕНИЙ (SVG BEZIER) ---
function renderConnections() {
  const svg = document.getElementById("connectionsSvg");
  // Удаляем старые пути, кроме tempCable
  const oldPaths = svg.querySelectorAll("path:not(#tempCable)");
  oldPaths.forEach(p => p.remove());

  state.project.connections.forEach(conn => {
    const fromNode = state.project.nodes.find(n => n.id === conn.from);
    const toNode = state.project.nodes.find(n => n.id === conn.to);
    if (!fromNode || !toNode) return;

    // Вычисляем координаты портов
    const x1 = fromNode.x + 200; // ширина ноды
    const y1 = fromNode.y + 45;  // центр по Y
    const x2 = toNode.x;
    const y2 = toNode.y + 45;

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", getBezierPath(x1, y1, x2, y2));
    path.setAttribute("class", "connection-path");
    path.setAttribute("marker-end", "url(#arrow)");

    // Удаление связи по клику
    path.onclick = (e) => {
      e.stopPropagation();
      if (confirm("Разорвать эту связь между блоками?")) {
        deleteConnection(conn);
      }
    };

    svg.appendChild(path);
  });
}

function getBezierPath(x1, y1, x2, y2) {
  const dx = Math.abs(x2 - x1) * 0.5;
  const cx1 = x1 + Math.max(dx, 40);
  const cy1 = y1;
  const cx2 = x2 - Math.max(dx, 40);
  const cy2 = y2;
  return `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`;
}

// --- ПЕРЕМЕЩЕНИЕ УЗЛОВ (TOUCH & MOUSE) ---
function setupNodeDrag(el, node) {
  const header = el.querySelector(".node-header");

  const startDrag = (clientX, clientY, e) => {
    e.stopPropagation();
    state.nodeDrag = {
      node: node,
      startX: clientX,
      startY: clientY,
      origX: node.x,
      origY: node.y
    };
  };

  header.addEventListener("mousedown", (e) => {
    if (e.button === 0) startDrag(e.clientX, e.clientY, e);
  });

  header.addEventListener("touchstart", (e) => {
    if (e.touches.length === 1) {
      startDrag(e.touches[0].clientX, e.touches[0].clientY, e);
    }
  }, { passive: false });
}

// --- СОЕДИНЕНИЕ ПОРТОВ (DESKTOP DRAG & MOBILE TAP) ---
function setupPortClick(el, node) {
  const outPort = el.querySelector(".port-output");
  const inPort = el.querySelector(".port-input");

  // Мобильный / Тап клик
  outPort.addEventListener("click", (e) => {
    e.stopPropagation();
    if (state.activePort && state.activePort.type === "output") {
      state.activePort.el.classList.remove("active");
    }
    state.activePort = { el: outPort, node: node, type: "output" };
    outPort.classList.add("active");
    showToast("Выход выбран. Теперь нажмите на вход целевого блока!");
  });

  inPort.addEventListener("click", (e) => {
    e.stopPropagation();
    if (state.activePort && state.activePort.type === "output") {
      if (state.activePort.node.id !== node.id) {
        createConnection(state.activePort.node.id, 0, node.id);
      }
      state.activePort.el.classList.remove("active");
      state.activePort = null;
    }
  });

  // Десктопное перетаскивание кабеля
  outPort.addEventListener("mousedown", (e) => {
    e.stopPropagation();
    const x1 = node.x + 200;
    const y1 = node.y + 45;
    state.cableDrag = { fromNodeId: node.id, outIdx: 0, startX: x1, startY: y1 };
    document.getElementById("tempCable").style.display = "block";
  });
}

// --- СОБЫТИЯ ХОЛСТА (PAN, ZOOM, CABLE) ---
function setupCanvasEvents() {
  const container = document.getElementById("canvasContainer");

  // Панорамирование мышью
  container.addEventListener("mousedown", (e) => {
    if (e.target === container || e.target.id === "connectionsSvg" || e.target.id === "canvasWorld") {
      state.isPanning = true;
      state.panStart = { x: e.clientX - state.pan.x, y: e.clientY - state.pan.y };
    }
  });

  window.addEventListener("mousemove", (e) => {
    // 1. Движение узла
    if (state.nodeDrag) {
      const dx = (e.clientX - state.nodeDrag.startX) / state.zoom;
      const dy = (e.clientY - state.nodeDrag.startY) / state.zoom;
      state.nodeDrag.node.x = state.nodeDrag.origX + dx;
      state.nodeDrag.node.y = state.nodeDrag.origY + dy;
      updateNodeElementPosition(state.nodeDrag.node);
      renderConnections();

      // Отправляем на сервер
      sendServer({
        type: "node_move",
        id: state.nodeDrag.node.id,
        x: state.nodeDrag.node.x,
        y: state.nodeDrag.node.y
      });
      return;
    }

    // 2. Панорамирование
    if (state.isPanning) {
      state.pan.x = e.clientX - state.panStart.x;
      state.pan.y = e.clientY - state.panStart.y;
      applyWorldTransform();
      return;
    }

    // 3. Вытягивание кабеля
    if (state.cableDrag) {
      const worldX = (e.clientX - state.pan.x) / state.zoom;
      const worldY = (e.clientY - state.pan.y) / state.zoom;
      const d = getBezierPath(state.cableDrag.startX, state.cableDrag.startY, worldX, worldY);
      const tempCable = document.getElementById("tempCable");
      tempCable.setAttribute("d", d);
      tempCable.style.display = "block";
      return;
    }

    // 4. Отправка курсора другим участникам (троттлинг)
    if (Math.random() < 0.2) {
      const wx = (e.clientX - state.pan.x) / state.zoom;
      const wy = (e.clientY - state.pan.y) / state.zoom;
      sendServer({ type: "cursor_move", x: wx, y: wy });
    }
  });

  window.addEventListener("mouseup", (e) => {
    state.isPanning = false;
    state.nodeDrag = null;

    if (state.cableDrag) {
      document.getElementById("tempCable").style.display = "none";
      // Проверяем, отпустили ли над входным портом
      const target = document.elementFromPoint(e.clientX, e.clientY);
      if (target && target.classList.contains("port-input")) {
        const toNid = target.getAttribute("data-nid");
        if (toNid && toNid !== state.cableDrag.fromNodeId) {
          createConnection(state.cableDrag.fromNodeId, state.cableDrag.outIdx, toNid);
        }
      }
      state.cableDrag = null;
    }
  });

  // Зум колесиком мыши
  container.addEventListener("wheel", (e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    zoomCanvas(factor, e.clientX, e.clientY);
  }, { passive: false });
}

// --- TOUCH PINCH-TO-ZOOM И ТАЧ-ПАН ДЛЯ ТЕЛЕФОНОВ ---
function setupTouchPinch() {
  const container = document.getElementById("canvasContainer");

  container.addEventListener("touchstart", (e) => {
    if (e.touches.length === 1 && (e.target === container || e.target.id === "connectionsSvg")) {
      state.isPanning = true;
      state.panStart = {
        x: e.touches[0].clientX - state.pan.x,
        y: e.touches[0].clientY - state.pan.y
      };
    } else if (e.touches.length === 2) {
      state.isPanning = false;
      state.pinchStartDist = getTouchDist(e.touches[0], e.touches[1]);
      state.initialPinchZoom = state.zoom;
    }
  }, { passive: false });

  container.addEventListener("touchmove", (e) => {
    if (e.touches.length === 1 && state.nodeDrag) {
      const t = e.touches[0];
      const dx = (t.clientX - state.nodeDrag.startX) / state.zoom;
      const dy = (t.clientY - state.nodeDrag.startY) / state.zoom;
      state.nodeDrag.node.x = state.nodeDrag.origX + dx;
      state.nodeDrag.node.y = state.nodeDrag.origY + dy;
      updateNodeElementPosition(state.nodeDrag.node);
      renderConnections();

      sendServer({
        type: "node_move",
        id: state.nodeDrag.node.id,
        x: state.nodeDrag.node.x,
        y: state.nodeDrag.node.y
      });
      e.preventDefault();
      return;
    }

    if (e.touches.length === 1 && state.isPanning) {
      state.pan.x = e.touches[0].clientX - state.panStart.x;
      state.pan.y = e.touches[0].clientY - state.panStart.y;
      applyWorldTransform();
      e.preventDefault();
    } else if (e.touches.length === 2 && state.pinchStartDist) {
      const currentDist = getTouchDist(e.touches[0], e.touches[1]);
      const factor = currentDist / state.pinchStartDist;
      state.zoom = Math.max(0.3, Math.min(2.5, state.initialPinchZoom * factor));
      applyWorldTransform();
      e.preventDefault();
    }
  }, { passive: false });

  container.addEventListener("touchend", () => {
    state.isPanning = false;
    state.nodeDrag = null;
    state.pinchStartDist = null;
  });
}

function getTouchDist(t1, t2) {
  const dx = t1.clientX - t2.clientX;
  const dy = t1.clientY - t2.clientY;
  return Math.sqrt(dx * dx + dy * dy);
}

function zoomCanvas(factor, clientX, clientY) {
  const newZoom = Math.max(0.3, Math.min(2.5, state.zoom * factor));
  const mouseX = clientX !== undefined ? clientX : window.innerWidth / 2;
  const mouseY = clientY !== undefined ? clientY : window.innerHeight / 2;

  state.pan.x = mouseX - (mouseX - state.pan.x) * (newZoom / state.zoom);
  state.pan.y = mouseY - (mouseY - state.pan.y) * (newZoom / state.zoom);
  state.zoom = newZoom;
  applyWorldTransform();
}

function resetZoom() {
  state.zoom = 1.0;
  state.pan = { x: 50, y: 80 };
  applyWorldTransform();
}

// --- УПРАВЛЕНИЕ УЗЛАМИ И СВЯЗЯМИ ---
function createNode(type = "story") {
  const screenCenterX = window.innerWidth / 2;
  const screenCenterY = window.innerHeight / 2;
  const worldX = (screenCenterX - state.pan.x) / state.zoom - 100;
  const worldY = (screenCenterY - state.pan.y) / state.zoom - 45;

  const titles = {
    story: "Новая реплика",
    choice: "Развилка выбора",
    condition: "Проверка условия",
    music: "Фоновая музыка"
  };

  const newNode = {
    id: Math.floor(Math.random() * 1000000000000).toString(),
    x: Math.round(worldX),
    y: Math.round(worldY),
    title: titles[type] || "Блок",
    content: type === "story" ? "Текст диалога..." : "",
    type: type,
    mode: "standard",
    custom_data: {}
  };

  state.project.nodes.push(newNode);
  renderNode(newNode);

  sendServer({ type: "node_create", node: newNode });
  showToast(`Создан блок ${titles[type]}`);
}

function createConnection(fromId, outIdx, toId) {
  const conn = { from: fromId, out_idx: outIdx, to: toId };
  state.project.connections.push(conn);
  renderConnections();
  sendServer({ type: "connection_create", connection: conn });
}

function deleteConnection(conn) {
  state.project.connections = state.project.connections.filter(
    c => !(c.from === conn.from && c.out_idx === conn.out_idx && c.to === conn.to)
  );
  renderConnections();
  sendServer({ type: "connection_delete", connection: conn });
}

function deleteNode(id) {
  if (!confirm("Удалить этот узел и все его связи?")) return;
  state.project.nodes = state.project.nodes.filter(n => n.id !== id);
  state.project.connections = state.project.connections.filter(c => c.from !== id && c.to !== id);
  const el = document.getElementById(`node_${id}`);
  if (el) el.remove();
  renderConnections();
  sendServer({ type: "node_delete", id: id });
}

// --- МОДАЛЬНОЕ ОКНО РЕДАКТИРОВАНИЯ ---
function openNodeModal(id) {
  const node = state.project.nodes.find(n => n.id === id);
  if (!node) return;

  document.getElementById("editNodeId").value = node.id;
  document.getElementById("editNodeType").value = node.type;
  document.getElementById("editNodeTitle").value = node.title || "";
  document.getElementById("editNodeContent").value = node.content || "";
  document.getElementById("editNodeColor").value = (node.custom_data && node.custom_data.header_color) || "";

  document.getElementById("nodeModal").classList.add("open");
}

function closeNodeModal() {
  document.getElementById("nodeModal").classList.remove("open");
}

function setEditColor(color) {
  document.getElementById("editNodeColor").value = color;
}

function saveNodeModal() {
  const id = document.getElementById("editNodeId").value;
  const node = state.project.nodes.find(n => n.id === id);
  if (!node) return;

  node.type = document.getElementById("editNodeType").value;
  node.title = document.getElementById("editNodeTitle").value.trim();
  node.content = document.getElementById("editNodeContent").value;
  const customColor = document.getElementById("editNodeColor").value;
  if (customColor) {
    node.custom_data = node.custom_data || {};
    node.custom_data.header_color = customColor;
  }

  renderNode(node);
  renderConnections();
  closeNodeModal();

  sendServer({ type: "node_update", node: node });
}

function deleteCurrentNode() {
  const id = document.getElementById("editNodeId").value;
  closeNodeModal();
  deleteNode(id);
}

// --- УДАЛЕННЫЕ КУРСОРЫ И ПОДСВЕТКА РЕДАКТИРОВАНИЯ ---
function updateRemoteCursor(clientId, name, color, x, y) {
  let cEl = document.getElementById(`cursor_${clientId}`);
  if (!cEl) {
    cEl = document.createElement("div");
    cEl.id = `cursor_${clientId}`;
    cEl.className = "remote-cursor";
    cEl.innerHTML = `
      <div class="cursor-pointer" style="border-bottom-color: ${color};"></div>
      <div class="cursor-tag" style="background-color: ${color};">${escapeHtml(name)}</div>
    `;
    document.getElementById("remoteCursorsContainer").appendChild(cEl);
  }
  cEl.style.transform = `translate(${x}px, ${y}px)`;
}

function removeRemoteCursor(clientId) {
  const cEl = document.getElementById(`cursor_${clientId}`);
  if (cEl) cEl.remove();
}

function showNodeEditingHalo(nodeId, userName, userColor) {
  const el = document.getElementById(`node_${nodeId}`);
  if (!el) return;

  let halo = el.querySelector(".node-editing-halo");
  if (!halo) {
    halo = document.createElement("div");
    halo.className = "node-editing-halo";
    el.appendChild(halo);
  }
  halo.style.borderColor = userColor || "#f1c40f";
  halo.innerHTML = `<span class="node-editing-tag" style="background-color: ${userColor}; color: white;">✏️ ${escapeHtml(userName)}</span>`;

  clearTimeout(el._haloTimer);
  el._haloTimer = setTimeout(() => {
    if (halo) halo.remove();
  }, 1200);
}

// --- ЧАТ И УЧАСТНИКИ ---
function toggleDrawer() {
  const drawer = document.getElementById("coworkDrawer");
  drawer.classList.toggle("open");
}

function updateCollaboratorsUI() {
  const container = document.getElementById("avatarsContainer");
  const list = document.getElementById("collaboratorsList");
  const countLbl = document.getElementById("lblOnlineCount");

  container.innerHTML = "";
  list.innerHTML = "";

  const total = state.collaborators.length;
  countLbl.innerText = `${total} онлайн`;

  state.collaborators.forEach(u => {
    // Аватар в шапке
    const av = document.createElement("div");
    av.className = "user-avatar";
    av.style.backgroundColor = u.color;
    av.innerText = u.name.substring(0, 1).toUpperCase();
    av.title = u.name;
    container.appendChild(av);

    // Строка в боковой панели
    const row = document.createElement("div");
    row.className = "collaborator-row";
    const devIcon = u.device === "phone" ? "📱" : (u.device === "tablet" ? "📟" : "💻");
    row.innerHTML = `
      <div class="user-avatar" style="background-color: ${u.color}; width: 26px; height: 26px; font-size: 12px;">
        ${u.name.substring(0, 1).toUpperCase()}
      </div>
      <div style="flex-grow: 1;">
        <div style="font-weight: 600;">${escapeHtml(u.name)}</div>
        <div style="font-size: 10px; color: #888;">${devIcon} ${u.device}</div>
      </div>
    `;
    list.appendChild(row);
  });
}

function updateMyName() {
  const newName = document.getElementById("inputMyName").value.trim();
  if (newName) {
    state.myUser.name = newName;
    localStorage.setItem("de_user_name", newName);
    sendServer(state.myUser);
    showToast("Имя обновлено!");
  }
}

function setupChatKey() {
  const input = document.getElementById("inputChatMsg");
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendChatMessage();
  });
}

function sendChatMessage() {
  const input = document.getElementById("inputChatMsg");
  const text = input.value.trim();
  if (!text) return;

  sendServer({ type: "chat_message", text: text });
  input.value = "";
}

function addChatMsg(msg) {
  const box = document.getElementById("chatBox");
  const el = document.createElement("div");
  el.className = "chat-msg";
  el.innerHTML = `
    <span class="chat-msg-author" style="color: ${msg.color || '#4a90e2'};">${escapeHtml(msg.user)}:</span>
    <span>${escapeHtml(msg.text)}</span>
    <span class="chat-msg-time">${msg.time || ""}</span>
  `;
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

// --- СОХРАНЕНИЕ ПРОЕКТА ---
function saveProject() {
  sendServer({ type: "save_project" });
  showToast("Запрос сохранения отправлен...");
}

function updateHeaderInfo() {
  const title = (state.project.metadata && state.project.metadata.title) || "Проект";
  document.getElementById("lblProjectTitle").innerText = title;
  updateCollaboratorsUI();
}

// --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
function escapeHtml(text) {
  if (!text) return "";
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showToast(text) {
  let toast = document.getElementById("appToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "appToast";
    toast.style.position = "fixed";
    toast.style.bottom = "80px";
    toast.style.left = "50%";
    toast.style.transform = "translateX(-50%)";
    toast.style.backgroundColor = "rgba(20, 20, 20, 0.9)";
    toast.style.border = "1px solid #4a90e2";
    toast.style.color = "#ffffff";
    toast.style.padding = "8px 16px";
    toast.style.borderRadius = "20px";
    toast.style.fontSize = "12px";
    toast.style.zIndex = "9999";
    toast.style.boxShadow = "0 4px 12px rgba(0,0,0,0.5)";
    toast.style.pointerEvents = "none";
    toast.style.transition = "opacity 0.3s";
    document.body.appendChild(toast);
  }
  toast.innerText = text;
  toast.style.opacity = "1";
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.style.opacity = "0";
  }, 2500);
}
