/**
 * Dialogue Engine Studio - Real-Time Web & Mobile Cowork Application.
 * Полноценный визуальный редактор сценариев и диалоговых графов для совместной работы.
 * Включает встроенные плагины: Плеер (Playtest), Авто-расстановку (DAG), Аудит графа,
 * Аналитику слов и Экспорт в Ren'Py.
 */

// --- ОПРЕДЕЛЕНИЕ СЕССИИ (У КАЖДОЙ СЕССИИ СВОЯ ССЫЛКА) ---
function getSessionId() {
  const params = new URLSearchParams(window.location.search);
  let s = params.get("session") || params.get("room") || params.get("s");

  if (!s && window.location.pathname) {
    const m = window.location.pathname.match(/\/s\/([a-zA-Z0-9_\-]+)/);
    if (m) s = m[1];
  }

  if (!s && window.location.hash) {
    const h = window.location.hash.replace(/^#/, "");
    if (h.includes("session=")) s = h.split("session=")[1].split("&")[0];
    else if (h.includes("room=")) s = h.split("room=")[1].split("&")[0];
    else if (h.length > 1 && !h.includes("/")) s = h;
  }

  if (!s) s = "violant";
  return s.trim().replace(/[^a-zA-Z0-9_\-]/g, "_") || "violant";
}

function syncSessionToUrl(sessionId) {
  try {
    const url = new URL(window.location.href);
    url.searchParams.set("session", sessionId);
    window.history.replaceState({}, "", url.toString());

    const displayEl = document.getElementById("sessionNameDisplay");
    if (displayEl) displayEl.innerText = sessionId;

    const linkInput = document.getElementById("sessionShareLinkInput");
    if (linkInput) linkInput.value = url.toString();

    const titleEl = document.getElementById("lblProjectTitle");
    if (titleEl) titleEl.innerText = `${sessionId}.json`;
  } catch (e) {}
}

// --- СОСТОЯНИЕ ПРИЛОЖЕНИЯ ---
const state = {
  sessionId: getSessionId(),
  isGitHubPages: window.location.hostname.includes("github.io") || window.location.protocol === "file:",
  peer: null,
  peerConnections: [],
  project: {
    metadata: { title: "violant.json" },
    nodes: [],
    connections: [],
    characters: []
  },
  collaborators: [],
  myUser: {
    id: "user_" + Math.random().toString(36).substr(2, 6),
    name: localStorage.getItem("de_user_name") || "Автор",
    color: "#4f8cff",
    device: "desktop"
  },
  zoom: 1.0,
  pan: { x: window.innerWidth / 4, y: window.innerHeight / 4 },
  selectedNodeId: null,
  ws: null,
  activePort: null,
  cableDrag: null,
  isPanning: false,
  panStart: { x: 0, y: 0 },
  nodeDrag: null,
  pinchStartDist: null,
  initialPinchZoom: 1.0,
  authToken: localStorage.getItem("de_auth_token") || "",
  hasAutoFocused: false,
  sprites: [],

  // Состояние встроенного плеера (Playtest)
  playtest: {
    active: false,
    currentNodeId: null,
    history: []
  }
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

// --- ИНИЦИАЛИЗАЦИЯ ПРИ ЗАГРУЗКЕ ---
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

  syncSessionToUrl(state.sessionId);

  setupCanvasEvents();
  setupTouchPinch();
  setupKeyboardNavigation();
  setupMinimapEvents();
  setupChatKey();

  checkAuthAndInit();
});

// --- АВТОРИЗАЦИЯ ПО ПАРОЛЮ ---
function checkAuthAndInit() {
  if (state.isGitHubPages) {
    connectNetwork();
    return;
  }
  const token = localStorage.getItem("de_auth_token") || "";
  fetch(`/api/auth/check?token=${encodeURIComponent(token)}`)
    .then(r => r.json())
    .then(data => {
      if (data.required && !data.authenticated) {
        showAuthModal();
      } else {
        hideAuthModal();
        connectNetwork();
      }
    })
    .catch(() => {
      connectNetwork();
    });
}

function showAuthModal(errMsg) {
  const modal = document.getElementById("authModal");
  if (modal) modal.classList.add("open");
  const errEl = document.getElementById("authErrorMsg");
  if (errEl) {
    if (errMsg) {
      errEl.innerText = errMsg;
      errEl.style.display = "block";
    } else {
      errEl.style.display = "none";
    }
  }
  const input = document.getElementById("authPasswordInput");
  if (input) setTimeout(() => input.focus(), 150);
}

function hideAuthModal() {
  const modal = document.getElementById("authModal");
  if (modal) modal.classList.remove("open");
}

function submitAuthPassword() {
  const pwdInput = document.getElementById("authPasswordInput");
  const pwd = pwdInput ? pwdInput.value.trim() : "";
  const remember = document.getElementById("authRememberMe") ? document.getElementById("authRememberMe").checked : true;

  if (!pwd) {
    showAuthModal("Пожалуйста, введите пароль");
    return;
  }

  fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: pwd })
  })
    .then(r => {
      if (!r.ok) throw new Error("Неверный пароль для входа");
      return r.json();
    })
    .then(data => {
      if (data.token) {
        if (remember) {
          localStorage.setItem("de_auth_token", data.token);
        }
        state.authToken = data.token;
        hideAuthModal();
        connectWebSocket();
      }
    })
    .catch(err => {
      showAuthModal(err.message || "Ошибка авторизации");
    });
}

// --- СЕТЕВАЯ СИНХРОНИЗАЦИЯ: WEBSOCKET & PEERJS P2P (ДЛЯ GITHUB PAGES) ---
function connectNetwork() {
  if (state.isGitHubPages) {
    console.log("[Studio] Running on GitHub Pages / Static host. Using Standalone + WebRTC P2P...");
    loadStandaloneSession();
    connectPeerP2P();
    return;
  }
  connectWebSocket();
}

function loadStandaloneSession() {
  const localKey = "de_project_" + state.sessionId;
  const cached = localStorage.getItem(localKey);
  if (cached) {
    try {
      state.project = JSON.parse(cached);
      console.log(`[Studio] Loaded session '${state.sessionId}' from localStorage (${state.project.nodes.length} nodes)`);
      renderAll();
      updateHeaderInfo();
      fetchSpritesList().then(renderAll);
      return;
    } catch (e) {}
  }

  // Если сессия violant (или пустая), загружаем встроенный файл violant.json
  const defaultFile = (state.sessionId === "violant") ? "violant.json" : null;
  if (defaultFile) {
    fetch(defaultFile)
      .then(r => r.json())
      .then(data => {
        state.project = data;
        localStorage.setItem(localKey, JSON.stringify(data));
        renderAll();
        updateHeaderInfo();
        fetchSpritesList().then(renderAll);
      })
      .catch(e => {
        console.warn("Could not load default violant.json, creating starter project:", e);
        createStarterProject();
      });
  } else {
    createStarterProject();
  }
}

function createStarterProject() {
  state.project = {
    metadata: { title: `Сессия ${state.sessionId}` },
    nodes: [
      {
        id: "start_node",
        x: 100,
        y: 150,
        title: "Начало",
        content: `Добро пожаловать в комнату "${state.sessionId}"!\nЗдесь можно писать сценарий вместе. Ссылка вверху уникальна для этой сессии.`,
        type: "story",
        custom_data: {}
      }
    ],
    connections: [],
    characters: [
      { name: "Ривер", color: "#0080ff" },
      { name: "Ника", color: "#00ffcc" },
      { name: "Энджи", color: "#c060f8" }
    ]
  };
  renderAll();
  updateHeaderInfo();
  saveLocalSessionProject();
}

function connectPeerP2P() {
  if (typeof Peer === "undefined") {
    console.log("[P2P] PeerJS library not available, working in local mode.");
    return;
  }
  try {
    const safeRoom = "de_room_" + state.sessionId;
    const peer = new Peer({
      config: {
        iceServers: [
          { urls: "stun:stun.l.google.com:19302" },
          { urls: "stun:stun1.l.google.com:19302" }
        ]
      }
    });
    state.peer = peer;
    state.peerConnections = [];

    peer.on("open", (myPeerId) => {
      console.log("[P2P] Connected to WebRTC broker. My Peer ID:", myPeerId);
      // Подключаемся к хосту комнаты
      const conn = peer.connect(safeRoom, { reliable: true });
      setupP2PConn(conn);
    });

    peer.on("connection", (conn) => {
      setupP2PConn(conn);
      conn.on("open", () => {
        conn.send({
          type: "init",
          client_id: state.myUser.id,
          user: state.myUser,
          project: state.project
        });
      });
    });
  } catch (e) {
    console.warn("[P2P] PeerJS init error:", e);
  }
}

function setupP2PConn(conn) {
  if (!conn) return;
  state.peerConnections.push(conn);
  conn.on("data", (data) => {
    try {
      handleServerMessage(typeof data === "string" ? JSON.parse(data) : data);
    } catch (e) {}
  });
  conn.on("close", () => {
    state.peerConnections = state.peerConnections.filter(c => c !== conn);
  });
}

function saveLocalSessionProject() {
  try {
    localStorage.setItem("de_project_" + state.sessionId, JSON.stringify(state.project));
  } catch (e) {}
}

// --- WEBSOCKET И СЕТЬ СИНХРОНИЗАЦИИ ---
function connectWebSocket() {
  if (state.ws && (state.ws.readyState === WebSocket.OPEN || state.ws.readyState === WebSocket.CONNECTING)) {
    return;
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const token = state.authToken || localStorage.getItem("de_auth_token") || "";
  const wsUrl = `${protocol}//${window.location.host}/ws?session=${encodeURIComponent(state.sessionId)}&token=${encodeURIComponent(token)}`;
  console.log("[Cowork] Connecting to:", wsUrl);

  let ws;
  try {
    ws = new WebSocket(wsUrl);
  } catch (e) {
    console.warn("[Cowork] WebSocket creation failed, falling back to standalone:", e);
    loadStandaloneSession();
    connectPeerP2P();
    return;
  }
  state.ws = ws;

  ws.onopen = () => {
    console.log(`[Cowork] Connected to session '${state.sessionId}'!`);
    ws.send(JSON.stringify({ ...state.myUser, session: state.sessionId, token: token }));
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
    console.log("[Cowork] Disconnected. Reconnecting in 3s...");
    setTimeout(() => {
      if (!state.isGitHubPages) connectWebSocket();
    }, 3000);
  };

  ws.onerror = (err) => {
    console.warn("[Cowork] WebSocket error. Switching to standalone/P2P mode.");
    if (!state.project || state.project.nodes.length === 0) {
      loadStandaloneSession();
      connectPeerP2P();
    }
  };
}

function sendServer(msg) {
  // Отправка через WebSocket (если сервер доступен)
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(msg));
  }
  // Отправка через P2P DataChannels (для работы без сервера на GitHub Pages)
  if (state.peerConnections && state.peerConnections.length > 0) {
    state.peerConnections.forEach(conn => {
      if (conn.open) {
        try { conn.send(msg); } catch (e) {}
      }
    });
  }
  // Всегда сохраняем в localStorage сессии
  saveLocalSessionProject();
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
      fetchSpritesList().then(() => {
        if (state.sprites && state.sprites.length > 0) {
          renderAll();
        }
      });
      if (!state.hasAutoFocused) {
        state.hasAutoFocused = true;
        // Фокусируемся на стартовом блоке или общем виде
        const startNode = state.project.nodes.find(n => n.title && n.title.toLowerCase().includes("start")) || state.project.nodes[0];
        if (startNode) {
          setTimeout(() => focusOnNode(startNode.id), 120);
        } else {
          setTimeout(fitViewToNodes, 120);
        }
      }
      if (msg.activity) {
        msg.activity.forEach(addChatMsg);
      }
      break;

    case "auth_error":
      localStorage.removeItem("de_auth_token");
      if (state.ws) {
        try { state.ws.close(); } catch(e) {}
        state.ws = null;
      }
      showAuthModal(msg.message || "Ошибка авторизации");
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
        drawMinimap();
      }
      break;

    case "batch_move":
      if (msg.moves) {
        msg.moves.forEach(m => {
          const n = state.project.nodes.find(node => node.id === m.id);
          if (n) {
            n.x = m.x;
            n.y = m.y;
            updateNodeElementPosition(n);
          }
        });
        renderConnections();
        drawMinimap();
      }
      break;

    case "node_create":
      if (!state.project.nodes.some(n => n.id === msg.node.id)) {
        state.project.nodes.push(msg.node);
        renderNode(msg.node);
        renderConnections();
        updateHeaderInfo();
        drawMinimap();
      }
      break;

    case "node_update":
      const idx = state.project.nodes.findIndex(n => n.id === msg.node.id);
      if (idx !== -1) {
        state.project.nodes[idx] = { ...state.project.nodes[idx], ...msg.node };
        renderNode(state.project.nodes[idx]);
        renderConnections();
        updateHeaderInfo();
      }
      break;

    case "node_delete":
      state.project.nodes = state.project.nodes.filter(n => n.id !== msg.id);
      state.project.connections = state.project.connections.filter(c => c.from !== msg.id && c.to !== msg.id);
      const elDel = document.getElementById(`node_${msg.id}`);
      if (elDel) elDel.remove();
      renderConnections();
      updateHeaderInfo();
      drawMinimap();
      break;

    case "connection_create":
      if (!state.project.connections.some(c => c.from === msg.connection.from && c.to === msg.connection.to && (c.out_idx || 0) === (msg.connection.out_idx || 0))) {
        state.project.connections.push(msg.connection);
        renderConnections();
        drawMinimap();
      }
      break;

    case "connection_delete":
      state.project.connections = state.project.connections.filter(c => !(c.from === msg.from && c.to === msg.to && (c.out_idx || 0) === (msg.out_idx || 0)));
      renderConnections();
      drawMinimap();
      break;

    case "cursor_move":
      updateRemoteCursor(msg.client_id, msg.user, msg.color, msg.x, msg.y);
      break;

    case "chat_message":
      addChatMsg(msg.message);
      break;

    case "characters_list_updated":
      if (msg.characters) {
        state.project.characters = msg.characters;
        const charModal = document.getElementById("charactersModal");
        if (charModal && charModal.classList.contains("open")) {
          renderCharactersList();
        }
      }
      break;

    case "batch_nodes_updated":
      if (msg.nodes && Array.isArray(msg.nodes)) {
        msg.nodes.forEach(un => {
          const idx = state.project.nodes.findIndex(n => n.id === un.id);
          if (idx !== -1) {
            state.project.nodes[idx] = { ...state.project.nodes[idx], ...un };
            renderNode(state.project.nodes[idx]);
          }
        });
      }
      break;

    case "notification":
      showToast(msg.text);
      break;
  }
}

// --- ОТРИСОВКА ВСЕХ ЭЛЕМЕНТОВ (RENDER ALL) ---
function renderAll() {
  const container = document.getElementById("nodesContainer");
  if (!container) return;
  container.innerHTML = "";
  state.project.nodes.forEach(node => renderNode(node));
  renderConnections();
  applyWorldTransform();
  drawMinimap();
}

function applyWorldTransform() {
  const world = document.getElementById("canvasWorld");
  if (world) {
    world.style.transform = `translate(${state.pan.x}px, ${state.pan.y}px) scale(${state.zoom})`;
  }
  const zoomLbl = document.getElementById("lblZoom");
  if (zoomLbl) {
    zoomLbl.innerText = Math.round(state.zoom * 100) + "%";
  }
  drawMinimap();
}

// Определение цвета шапки узла
function getNodeHeaderColor(node) {
  if (node.custom_data && node.custom_data.header_color) return node.custom_data.header_color;
  switch (node.type) {
    case "choice": return "#f59e0b";
    case "condition": return "#8b5cf6";
    case "music": return "#10b981";
    case "media": return "#06b6d4";
    case "label": return "#f97316";
    case "pause": return "#64748b";
    case "python_code": return "#3b82f6";
    case "variable": return "#14b8a6";
    case "animation": return "#ec4899";
    default: return "#4f8cff";
  }
}

// ==========================================================================
// СЕРВИС ПЕРСОНАЖЕЙ, ЭМОЦИЙ И СПРАЙТОВ
// ==========================================================================
const KNOWN_NAME_ALIASES = {
  "энджи": ["enjie", "endzhi", "angie"],
  "ника": ["nika", "veronika"],
  "ривер": ["river"],
  "джен": ["jen", "dzhen", "jennifer"],
  "телевизор": ["tv", "televizor"],
  "???": ["unknown"]
};

const EMOTION_ALIASES = {
  "обычный": ["neutral", "normal", "idle", "default", "pose_01", "pose_1"],
  "нейтральный": ["neutral", "normal", "idle", "default", "pose_01"],
  "радость": ["happy", "smile", "joy", "pose_02"],
  "грусть": ["sad", "cry", "gloom", "pose_03"],
  "злость": ["angry", "rage", "pose_04"],
  "удивление": ["surprised", "shock", "pose_05"],
  "смущение": ["shy", "blush", "pose_06"]
};

const DEFAULT_CHAR_PALETTE = {
  "ривер": "#0080ff",
  "river": "#0080ff",
  "ника": "#00ffcc",
  "nika": "#00ffcc",
  "джен": "#ffff00",
  "jen": "#ffff00",
  "энджи": "#c060f8",
  "enjie": "#c060f8",
  "телевизор": "#66ccff",
  "tv": "#66ccff",
  "???": "#8000ff"
};

// Разбор заголовка узла на имя персонажа и эмоцию
function parseTitleCharacterAndEmotion(title) {
  if (!title) return { character: "", emotion: "", isComment: false };
  const t = title.trim();
  if (t.startsWith("#")) {
    const comment = t.replace(/^#+\s*/, "").trim();
    return { character: "", emotion: "", isComment: true, comment: comment };
  }

  // 1. Формат "Имя (эмоция)" или "Имя [эмоция]" или "Имя {эмоция}"
  let m = t.match(/^([^([{:–—]+?)\s*[({\[]([^)\]}]+)[)}\]]$/);
  if (m) {
    return { character: m[1].trim(), emotion: m[2].trim(), isComment: false };
  }

  // 2. Формат "Имя: эмоция" или "Имя - эмоция"
  m = t.match(/^([^:–—]+?)\s*[:–—]\s*(.+)$/);
  if (m) {
    return { character: m[1].trim(), emotion: m[2].trim(), isComment: false };
  }

  // 3. Формат "Имя pose_01" или "Имя радость"
  m = t.match(/^(.+?)\s+(pose_?\d+|радость|грусть|злость|удивление|смущение|обычный|neutral|happy|sad|angry|surprised|shy)$/i);
  if (m) {
    return { character: m[1].trim(), emotion: m[2].trim(), isComment: false };
  }

  return { character: t, emotion: "", isComment: false };
}

// Получение цвета имени говорящего персонажа
function getCharacterColor(characterName) {
  if (!characterName) return "#ffffff";
  const clean = characterName.trim().toLowerCase();
  if (state.project && state.project.characters) {
    const found = state.project.characters.find(c => c.name && c.name.trim().toLowerCase() === clean);
    if (found && found.color) return found.color;
  }
  if (DEFAULT_CHAR_PALETTE[clean]) return DEFAULT_CHAR_PALETTE[clean];
  for (const [key, aliases] of Object.entries(KNOWN_NAME_ALIASES)) {
    if (clean === key || aliases.includes(clean)) {
      if (DEFAULT_CHAR_PALETTE[key]) return DEFAULT_CHAR_PALETTE[key];
    }
  }
  return "#ffffff";
}

// Загрузка доступных файлов спрайтов с сервера
async function fetchSpritesList() {
  try {
    const res = await fetch("/api/sprites");
    if (res.ok) {
      const data = await res.json();
      state.sprites = data.sprites || [];
    }
  } catch (e) {
    console.warn("Could not fetch /api/sprites:", e);
  }
}

// Автоматический резолвер спрайта персонажа по эмоции
function resolveSprite(characterName, emotion) {
  if (!characterName) return null;
  const charClean = characterName.trim().toLowerCase();
  const emoClean = (emotion || "").trim().toLowerCase();

  const charVariants = [charClean];
  for (const [k, aliases] of Object.entries(KNOWN_NAME_ALIASES)) {
    if (charClean === k || aliases.includes(charClean)) {
      charVariants.push(k, ...aliases);
      break;
    }
  }

  const emoVariants = emoClean ? [emoClean] : ["neutral", "normal", "idle", "default", "pose_01", "pose_1"];
  for (const [k, aliases] of Object.entries(EMOTION_ALIASES)) {
    if (emoClean === k || aliases.includes(emoClean)) {
      emoVariants.push(k, ...aliases);
      break;
    }
  }
  const poseMatch = emoClean.match(/(?:pose|поза)[_ -]?(\d+)/i);
  if (poseMatch) {
    const pNum = parseInt(poseMatch[1]);
    emoVariants.push(`pose_${String(pNum).padStart(2, "0")}`, `pose_${pNum}`, `${pNum}`);
  }

  // 1. Поиск в списке спрайтов, загруженных с сервера
  if (state.sprites && state.sprites.length > 0) {
    for (const cv of charVariants) {
      const charSprites = state.sprites.filter(s => {
        const pathLower = s.rel_path.toLowerCase();
        return pathLower.includes(`/${cv}/`) || pathLower.startsWith(`${cv}/`) || pathLower.startsWith(`${cv}_`);
      });

      if (charSprites.length > 0) {
        if (!emoClean) {
          return charSprites[0];
        }
        for (const ev of emoVariants) {
          const matched = charSprites.find(s => s.name.toLowerCase().includes(ev));
          if (matched) return matched;
        }
        return charSprites[0];
      }
    }
  }

  // 2. Встроенные пути для проекта Violant
  for (const cv of charVariants) {
    if (cv === "enjie" || cv === "энджи") {
      return { url: "sprites/enjie_neutral.png", file: "enjie_neutral.png", name: "enjie_neutral" };
    }
    if (cv === "nika" || cv === "ника") {
      let poseId = "01";
      if (emoClean) {
        if (emoClean.includes("радость") || emoClean.includes("happy") || emoClean.includes("02")) poseId = "02";
        else if (emoClean.includes("грусть") || emoClean.includes("sad") || emoClean.includes("03")) poseId = "03";
        else if (emoClean.includes("злость") || emoClean.includes("angry") || emoClean.includes("04")) poseId = "04";
        else if (emoClean.includes("удивление") || emoClean.includes("05")) poseId = "05";
        else if (emoClean.includes("смущение") || emoClean.includes("06")) poseId = "06";
        else {
          const numM = emoClean.match(/\d+/);
          if (numM) poseId = String(parseInt(numM[0])).padStart(2, "0");
        }
      }
      return { url: `sprites/nika/nika_pose_${poseId}.png`, file: `nika_pose_${poseId}.png`, name: `nika_pose_${poseId}` };
    }
  }

  return null;
}

// Отрисовка отдельной карточки узла
function renderNode(node) {
  let el = document.getElementById(`node_${node.id}`);
  if (!el) {
    el = document.createElement("div");
    el.id = `node_${node.id}`;
    document.getElementById("nodesContainer").appendChild(el);
  }

  el.className = `node-card node-type-${node.type}`;
  if (state.selectedNodeId === node.id) {
    el.classList.add("selected");
  }

  const hColor = getNodeHeaderColor(node);
  const badgeInfo = {
    story: { text: "СЮЖЕТ", icon: "📝" },
    choice: { text: "ВЫБОР", icon: "🔀" },
    condition: { text: "УСЛОВИЕ", icon: "⚡" },
    music: { text: "МУЗЫКА", icon: "🎵" },
    media: { text: "МЕДИА", icon: "🖼️" },
    label: { text: "МЕТКА", icon: "🏷️" },
    pause: { text: "ПАУЗА", icon: "⏱️" },
    python_code: { text: "PYTHON", icon: "🐍" },
    variable: { text: "ПЕРЕМЕННАЯ", icon: "📦" },
    animation: { text: "АНИМАЦИЯ", icon: "✨" }
  }[node.type] || { text: "БЛОК", icon: "📄" };

  el.style.left = `${node.x}px`;
  el.style.top = `${node.y}px`;

  // Формирование заголовка блока с цветом имени персонажа и спрайтом
  let headerTitleHtml = "";
  if (node.type === "story") {
    const parsed = parseTitleCharacterAndEmotion(node.title);
    if (parsed.isComment) {
      headerTitleHtml = `<span class="node-author-label">💭 ${escapeHtml(parsed.comment || "Слова автора")}</span>`;
    } else if (parsed.character) {
      const nameColor = (node.custom_data && node.custom_data.header_text_color) || getCharacterColor(parsed.character);
      const spr = resolveSprite(parsed.character, parsed.emotion || (node.custom_data && node.custom_data.emotion));
      const iconHtml = spr && spr.url 
        ? `<img src="${spr.url}" class="node-sprite-icon" alt="${escapeHtml(parsed.character)}" onerror="this.style.display='none'">`
        : `<span class="node-char-avatar-circle" style="background: ${nameColor}33; color: ${nameColor}; border: 1px solid ${nameColor}77;">${(parsed.character[0] || "?").toUpperCase()}</span>`;
      
      const emotionBadgeHtml = parsed.emotion 
        ? `<span class="node-emotion-tag" title="Эмоция: ${escapeHtml(parsed.emotion)}">[${escapeHtml(parsed.emotion)}]</span>` 
        : "";

      headerTitleHtml = `
        <div style="display: flex; align-items: center; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; max-width: 155px;">
          ${iconHtml}
          <span class="node-char-name" style="color: ${nameColor};">${escapeHtml(parsed.character)}</span>
          ${emotionBadgeHtml}
        </div>
      `;
    } else {
      headerTitleHtml = `<span class="node-title">${badgeInfo.icon} ${escapeHtml(node.title || "Безымянный")}</span>`;
    }
  } else {
    headerTitleHtml = `<span class="node-title">${badgeInfo.icon} ${escapeHtml(node.title || "Безымянный")}</span>`;
  }

  // Формирование содержимого тела блока
  let bodyContentHtml = "";
  if (node.type === "choice") {
    const choices = (node.content || "").split("\n").filter(Boolean);
    if (choices.length > 0) {
      bodyContentHtml = `<div class="node-choices-container">`;
      choices.forEach((cText, idx) => {
        bodyContentHtml += `
          <div class="node-choice-item">
            <span>${idx + 1}. ${escapeHtml(cText)}</span>
            <div class="port port-output" data-nid="${node.id}" data-idx="${idx}" data-type="output" title="Ветка: ${escapeHtml(cText)}"></div>
          </div>
        `;
      });
      bodyContentHtml += `</div>`;
    } else {
      bodyContentHtml = `<div style="color: #94a3b8; font-style: italic;">Добавьте варианты в текст...</div>`;
    }
  } else {
    const preview = escapeHtml(node.content || "").replace(/\n/g, "<br>");
    bodyContentHtml = `<div>${preview || "<span style='color: #64748b; font-style: italic;'>(пусто)</span>"}</div>`;
  }

  // Одиночный выходной порт для всех узлов, кроме choice
  const standardOutputPort = node.type !== "choice" 
    ? `<div class="port port-output" data-nid="${node.id}" data-idx="0" data-type="output" title="Выход (Output)"></div>`
    : "";

  el.innerHTML = `
    <!-- Входной порт -->
    <div class="port port-input" data-nid="${node.id}" data-type="input" title="Вход (Input)"></div>

    <!-- Шапка блока -->
    <div class="node-header" style="background-color: ${hColor};">
      ${headerTitleHtml}
      <div class="node-actions">
        <button class="node-action-btn" onclick="openNodeModal('${node.id}')" title="Редактировать">✏️</button>
        <button class="node-action-btn" onclick="deleteNode('${node.id}')" title="Удалить">✕</button>
      </div>
    </div>

    <!-- Тело блока -->
    <div class="node-body">
      <span class="node-badge" style="background-color: ${hColor}33; color: ${hColor};">${badgeInfo.text}</span>
      ${bodyContentHtml}
    </div>

    ${standardOutputPort}
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

// --- ОТРИСОВКА СВЯЗЕЙ (SVG CUBIC BEZIER) ---
function renderConnections() {
  const svg = document.getElementById("connectionsSvg");
  if (!svg) return;
  const oldPaths = svg.querySelectorAll("path:not(#tempCable)");
  oldPaths.forEach(p => p.remove());

  state.project.connections.forEach(conn => {
    const fromNode = state.project.nodes.find(n => String(n.id) === String(conn.from));
    const toNode = state.project.nodes.find(n => String(n.id) === String(conn.to));
    if (!fromNode || !toNode) return;

    const outIdx = Number(conn.out_idx || 0);

    // Точные координаты портов
    const x1 = fromNode.x + 210;
    let y1 = fromNode.y + 45;
    if (fromNode.type === "choice") {
      // Смещение по высоте для конкретного варианта выбора
      y1 = fromNode.y + 70 + (outIdx * 28);
    }

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
        deleteConnection(conn.from, conn.to, outIdx);
      }
    };

    svg.appendChild(path);
  });
}

function getBezierPath(x1, y1, x2, y2) {
  const dx = Math.abs(x2 - x1) * 0.55;
  const cx1 = x1 + Math.max(40, dx);
  const cy1 = y1;
  const cx2 = x2 - Math.max(40, dx);
  const cy2 = y2;
  return `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`;
}

// --- СОБЫТИЯ ХОЛСТА (PAN, ZOOM, DRAG) ---
function setupCanvasEvents() {
  const container = document.getElementById("canvasContainer");
  if (!container) return;

  // Начало панорамирования холста
  container.addEventListener("mousedown", (e) => {
    if (e.target === container || e.target.id === "connectionsSvg") {
      state.isPanning = true;
      state.panStart = { x: e.clientX - state.pan.x, y: e.clientY - state.pan.y };
      deselectNode();
    }
  });

  window.addEventListener("mousemove", (e) => {
    // 1. Перемещение выбранного узла
    if (state.nodeDrag) {
      const dx = (e.clientX - state.nodeDrag.startX) / state.zoom;
      const dy = (e.clientY - state.nodeDrag.startY) / state.zoom;
      state.nodeDrag.node.x = Math.round((state.nodeDrag.origX + dx) / 10) * 10;
      state.nodeDrag.node.y = Math.round((state.nodeDrag.origY + dy) / 10) * 10;
      updateNodeElementPosition(state.nodeDrag.node);
      renderConnections();

      // Периодическая рассылка координат соавторам
      if (Math.random() < 0.25) {
        sendServer({
          type: "node_move",
          id: state.nodeDrag.node.id,
          x: state.nodeDrag.node.x,
          y: state.nodeDrag.node.y
        });
      }
      return;
    }

    // 2. Панорамирование камеры
    if (state.isPanning) {
      state.pan.x = e.clientX - state.panStart.x;
      state.pan.y = e.clientY - state.panStart.y;
      applyWorldTransform();
      return;
    }

    // 3. Вытягивание связи (кабеля)
    if (state.cableDrag) {
      const worldX = (e.clientX - state.pan.x) / state.zoom;
      const worldY = (e.clientY - state.pan.y) / state.zoom;
      const d = getBezierPath(state.cableDrag.startX, state.cableDrag.startY, worldX, worldY);
      const tempCable = document.getElementById("tempCable");
      if (tempCable) {
        tempCable.setAttribute("d", d);
        tempCable.style.display = "block";
      }
      return;
    }

    // 4. Синхронизация курсора соавторам
    if (Math.random() < 0.15) {
      const wx = (e.clientX - state.pan.x) / state.zoom;
      const wy = (e.clientY - state.pan.y) / state.zoom;
      sendServer({ type: "cursor_move", x: wx, y: wy });
    }
  });

  window.addEventListener("mouseup", (e) => {
    if (state.nodeDrag) {
      sendServer({
        type: "node_move",
        id: state.nodeDrag.node.id,
        x: state.nodeDrag.node.x,
        y: state.nodeDrag.node.y
      });
      state.nodeDrag = null;
      drawMinimap();
    }
    state.isPanning = false;

    if (state.cableDrag) {
      const tempCable = document.getElementById("tempCable");
      if (tempCable) tempCable.style.display = "none";
      state.cableDrag = null;
    }
  });

  // Зум колесиком мыши
  container.addEventListener("wheel", (e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.15 : 0.87;
    zoomCanvas(factor, e.clientX, e.clientY);
  }, { passive: false });
}

// Перетаскивание узла мышкой / тачем
function setupNodeDrag(el, node) {
  el.addEventListener("mousedown", (e) => {
    if (e.target.classList.contains("port") || e.target.classList.contains("node-action-btn")) return;
    e.stopPropagation();
    selectNode(node.id);
    state.nodeDrag = {
      node: node,
      startX: e.clientX,
      startY: e.clientY,
      origX: node.x,
      origY: node.y
    };
  });
}

// Соединение портов (тянуть или кликать тапом)
function setupPortClick(el, node) {
  const ports = el.querySelectorAll(".port");
  ports.forEach(port => {
    port.addEventListener("mousedown", (e) => {
      e.stopPropagation();
      const ptype = port.dataset.type;
      const pidx = parseInt(port.dataset.idx || "0", 10);

      if (ptype === "output") {
        const outX = node.x + 210;
        let outY = node.y + 45;
        if (node.type === "choice") {
          outY = node.y + 70 + (pidx * 28);
        }
        state.cableDrag = {
          fromNodeId: node.id,
          outIdx: pidx,
          startX: outX,
          startY: outY
        };
      }
    });

    port.addEventListener("mouseup", (e) => {
      e.stopPropagation();
      const ptype = port.dataset.type;
      if (state.cableDrag && ptype === "input") {
        createConnection(state.cableDrag.fromNodeId, node.id, state.cableDrag.outIdx);
        state.cableDrag = null;
        const tempCable = document.getElementById("tempCable");
        if (tempCable) tempCable.style.display = "none";
      }
    });

    // Мобильное соединение двумя тапами
    port.addEventListener("click", (e) => {
      e.stopPropagation();
      const ptype = port.dataset.type;
      const pidx = parseInt(port.dataset.idx || "0", 10);

      if (!state.activePort) {
        if (ptype === "output") {
          state.activePort = { nodeId: node.id, outIdx: pidx };
          port.style.transform = "scale(1.6)";
          port.style.boxShadow = "0 0 15px #ffcc00";
          showToast("Порт выбран. Теперь нажмите на ВХОД целевого блока.");
        }
      } else {
        if (ptype === "input" && state.activePort.nodeId !== node.id) {
          createConnection(state.activePort.nodeId, node.id, state.activePort.outIdx);
          showToast("Связь создана!");
        }
        clearActivePorts();
      }
    });
  });
}

function clearActivePorts() {
  state.activePort = null;
  document.querySelectorAll(".port").forEach(p => {
    p.style.transform = "";
    p.style.boxShadow = "";
  });
}

// Выбор узла
function selectNode(id) {
  state.selectedNodeId = id;
  document.querySelectorAll(".node-card").forEach(el => el.classList.remove("selected"));
  const el = document.getElementById(`node_${id}`);
  if (el) el.classList.add("selected");
}

function deselectNode() {
  state.selectedNodeId = null;
  document.querySelectorAll(".node-card").forEach(el => el.classList.remove("selected"));
}

// ==========================================================================
// УПРАВЛЕНИЕ СТРЕЛОЧКАМИ И ГОРЯЧИЕ КЛАВИШИ
// ==========================================================================
function setupKeyboardNavigation() {
  window.addEventListener("keydown", (e) => {
    // Не перехватываем ввод, если пользователь печатает в поле формы
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable) {
      return;
    }

    const speed = e.shiftKey ? 180 : 50;
    let handled = false;

    // В режиме Playtest клавиши передаются плееру
    if (state.playtest.active) {
      if (e.key === " " || e.key === "Enter" || e.key === "ArrowRight") {
        playtestNext();
        handled = true;
      } else if (e.key === "ArrowLeft" || e.key === "Backspace") {
        playtestBack();
        handled = true;
      } else if (e.key === "Escape") {
        stopQuickPlaytest();
        handled = true;
      }
      if (handled) e.preventDefault();
      return;
    }

    // Навигация стрелочками или WASD
    if (e.key === "ArrowLeft" || e.key === "a" || e.key === "A") {
      if (state.selectedNodeId && !e.shiftKey && e.key === "ArrowLeft") {
        nudgeSelectedNode(-20, 0);
      } else {
        state.pan.x += speed;
        applyWorldTransform();
      }
      handled = true;
    } else if (e.key === "ArrowRight" || e.key === "d" || e.key === "D") {
      if (state.selectedNodeId && !e.shiftKey && e.key === "ArrowRight") {
        nudgeSelectedNode(20, 0);
      } else {
        state.pan.x -= speed;
        applyWorldTransform();
      }
      handled = true;
    } else if (e.key === "ArrowUp" || e.key === "w" || e.key === "W") {
      if (state.selectedNodeId && !e.shiftKey && e.key === "ArrowUp") {
        nudgeSelectedNode(0, -20);
      } else {
        state.pan.y += speed;
        applyWorldTransform();
      }
      handled = true;
    } else if (e.key === "ArrowDown" || e.key === "s" || e.key === "S") {
      if (state.selectedNodeId && !e.shiftKey && e.key === "ArrowDown") {
        nudgeSelectedNode(0, 20);
      } else {
        state.pan.y -= speed;
        applyWorldTransform();
      }
      handled = true;
    } else if (e.key === "+" || e.key === "=") {
      zoomCanvas(1.15);
      handled = true;
    } else if (e.key === "-" || e.key === "_") {
      zoomCanvas(0.85);
      handled = true;
    } else if (e.key === "0") {
      fitViewToNodes();
      handled = true;
    } else if (e.key === "f" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      openNodeSearchModal();
      handled = true;
    } else if (e.key === "l" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      runAutoLayout();
      handled = true;
    } else if (e.key === "s" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      saveProject();
      handled = true;
    } else if (e.key === " " && !state.selectedNodeId) {
      e.preventDefault();
      startQuickPlaytest();
      handled = true;
    } else if (e.key === "Delete") {
      if (state.selectedNodeId) {
        deleteNode(state.selectedNodeId);
        handled = true;
      }
    } else if (e.key === "Escape") {
      closeAllModals();
      deselectNode();
      handled = true;
    }

    if (handled) {
      e.preventDefault();
    }
  });
}

// Сдвиг выбранного узла клавишами
function nudgeSelectedNode(dx, dy) {
  const node = state.project.nodes.find(n => n.id === state.selectedNodeId);
  if (!node) return;
  node.x = Math.round((node.x + dx) / 20) * 20;
  node.y = Math.round((node.y + dy) / 20) * 20;
  updateNodeElementPosition(node);
  renderConnections();
  sendServer({ type: "node_move", id: node.id, x: node.x, y: node.y });
  drawMinimap();
}

// Зум холста с сохранением фокуса
function zoomCanvas(factor, clientX, clientY) {
  const newZoom = Math.max(0.015, Math.min(3.0, state.zoom * factor));
  const mouseX = clientX !== undefined ? clientX : window.innerWidth / 2;
  const mouseY = clientY !== undefined ? clientY : window.innerHeight / 2;

  state.pan.x = mouseX - (mouseX - state.pan.x) * (newZoom / state.zoom);
  state.pan.y = mouseY - (mouseY - state.pan.y) * (newZoom / state.zoom);
  state.zoom = newZoom;
  applyWorldTransform();
}

// Сенсорный Pinch-to-Zoom для смартфонов
function setupTouchPinch() {
  const container = document.getElementById("canvasContainer");
  if (!container) return;

  container.addEventListener("touchstart", (e) => {
    if (e.touches.length === 1 && (e.target === container || e.target.id === "connectionsSvg")) {
      state.isPanning = true;
      state.panStart = { x: e.touches[0].clientX - state.pan.x, y: e.touches[0].clientY - state.pan.y };
    } else if (e.touches.length === 2) {
      state.isPanning = false;
      state.pinchStartDist = getTouchDist(e.touches[0], e.touches[1]);
      state.initialPinchZoom = state.zoom;
    }
  }, { passive: false });

  container.addEventListener("touchmove", (e) => {
    if (e.touches.length === 1 && state.isPanning) {
      state.pan.x = e.touches[0].clientX - state.panStart.x;
      state.pan.y = e.touches[0].clientY - state.panStart.y;
      applyWorldTransform();
      e.preventDefault();
    } else if (e.touches.length === 2 && state.pinchStartDist) {
      const currentDist = getTouchDist(e.touches[0], e.touches[1]);
      const factor = currentDist / state.pinchStartDist;
      state.zoom = Math.max(0.015, Math.min(3.0, state.initialPinchZoom * factor));
      applyWorldTransform();
      e.preventDefault();
    }
  }, { passive: false });

  container.addEventListener("touchend", () => {
    state.isPanning = false;
    state.pinchStartDist = null;
  });
}

function getTouchDist(t1, t2) {
  const dx = t1.clientX - t2.clientX;
  const dy = t1.clientY - t2.clientY;
  return Math.sqrt(dx * dx + dy * dy);
}

// ==========================================================================
// МИНИКАРТА (MINIMAP)
// ==========================================================================
function setupMinimapEvents() {
  const panel = document.getElementById("minimapPanel");
  if (!panel) return;
  panel.addEventListener("click", (e) => {
    const rect = panel.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / rect.width;
    const my = (e.clientY - rect.top) / rect.height;

    const bounds = getGraphBounds();
    const targetWorldX = bounds.minX + mx * bounds.width;
    const targetWorldY = bounds.minY + my * bounds.height;

    state.pan.x = window.innerWidth / 2 - targetWorldX * state.zoom;
    state.pan.y = window.innerHeight / 2 - targetWorldY * state.zoom;
    applyWorldTransform();
  });
}

function getGraphBounds() {
  const nodes = state.project.nodes || [];
  if (nodes.length === 0) return { minX: 0, maxX: 1000, minY: 0, maxY: 600, width: 1000, height: 600 };

  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  nodes.forEach(n => {
    const nx = Number(n.x) || 0;
    const ny = Number(n.y) || 0;
    if (nx < minX) minX = nx;
    if (nx + 210 > maxX) maxX = nx + 210;
    if (ny < minY) minY = ny;
    if (ny + 120 > maxY) maxY = ny + 120;
  });

  const pad = 120;
  minX -= pad;
  maxX += pad;
  minY -= pad;
  maxY += pad;

  return {
    minX, maxX, minY, maxY,
    width: Math.max(100, maxX - minX),
    height: Math.max(100, maxY - minY)
  };
}

function drawMinimap() {
  const canvas = document.getElementById("minimapCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  canvas.width = canvas.clientWidth || 190;
  canvas.height = canvas.clientHeight || 130;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const bounds = getGraphBounds();
  const scaleX = canvas.width / bounds.width;
  const scaleY = canvas.height / bounds.height;

  // Отрисовка точек узлов
  (state.project.nodes || []).forEach(n => {
    const mx = (n.x - bounds.minX) * scaleX;
    const my = (n.y - bounds.minY) * scaleY;
    ctx.fillStyle = getNodeHeaderColor(n);
    ctx.beginPath();
    ctx.arc(mx, my, 2.5, 0, Math.PI * 2);
    ctx.fill();
  });

  // Рамка области видимости камеры
  const viewX1 = (-state.pan.x) / state.zoom;
  const viewY1 = (-state.pan.y) / state.zoom;
  const viewX2 = (window.innerWidth - state.pan.x) / state.zoom;
  const viewY2 = (window.innerHeight - state.pan.y) / state.zoom;

  const rx = (viewX1 - bounds.minX) * scaleX;
  const ry = (viewY1 - bounds.minY) * scaleY;
  const rw = (viewX2 - viewX1) * scaleX;
  const rh = (viewY2 - viewY1) * scaleY;

  ctx.strokeStyle = "#4f8cff";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(rx, ry, rw, rh);
  ctx.fillStyle = "rgba(79, 140, 255, 0.12)";
  ctx.fillRect(rx, ry, rw, rh);
}

// ==========================================================================
// ПЛАГИН 1: БЫСТРЫЙ ТЕСТ НОВЕЛЛЫ (QUICK PLAYTEST)
// ==========================================================================
function startQuickPlaytest() {
  const nodes = state.project.nodes || [];
  if (nodes.length === 0) {
    showToast("Сценарий пуст! Нечего тестировать.");
    return;
  }

  // Если выбран узел - стартуем с него, иначе ищем start или первый
  let startNode = null;
  if (state.selectedNodeId) {
    startNode = nodes.find(n => n.id === state.selectedNodeId);
  }
  if (!startNode) {
    startNode = nodes.find(n => n.title && n.title.toLowerCase().trim() === "start") || nodes[0];
  }

  state.playtest.active = true;
  state.playtest.currentNodeId = startNode.id;
  state.playtest.history = [];

  const modal = document.getElementById("playtestModal");
  if (modal) modal.classList.add("open");

  renderPlaytestStep();
}

function stopQuickPlaytest() {
  state.playtest.active = false;
  const sprWrap = document.getElementById("playtestCurrentSpriteWrap");
  if (sprWrap) sprWrap.remove();
  const modal = document.getElementById("playtestModal");
  if (modal) modal.classList.remove("open");
}

function renderPlaytestStep() {
  const node = state.project.nodes.find(n => n.id === state.playtest.currentNodeId);
  const speakerTag = document.getElementById("playtestSpeakerTag");
  const dialogueEl = document.getElementById("playtestDialogueText");
  const choicesBox = document.getElementById("playtestChoicesBox");
  const sceneLabel = document.getElementById("playtestSceneLabel");
  const centerStage = document.getElementById("playtestCenterStage");

  // Очистка предыдущего спрайта со сцены
  const existingSprite = document.getElementById("playtestCurrentSpriteWrap");
  if (existingSprite) existingSprite.remove();

  if (!node) {
    speakerTag.innerText = "Конец";
    dialogueEl.innerText = "Сцена завершена (нет исходящих связей).";
    choicesBox.style.display = "none";
    return;
  }

  document.getElementById("playtestNodeId").innerText = `Узел: ${node.title || node.id} (${node.type})`;

  // Разбор персонажа, эмоции и цвета
  const parsed = parseTitleCharacterAndEmotion(node.title);
  const charName = parsed.character || "";
  const emotion = parsed.emotion || (node.custom_data && node.custom_data.emotion) || "";
  const charColor = (node.custom_data && node.custom_data.header_text_color) || getCharacterColor(charName) || "#60a5fa";

  if (node.type === "label") {
    sceneLabel.innerText = `🏷️ ${node.title || "Новая сцена"}`;
  } else {
    sceneLabel.innerText = "";
  }

  // Настройка тега говорящего
  if (parsed.isComment || !charName) {
    speakerTag.innerHTML = `<span>💭 ${escapeHtml(parsed.comment || "Автор")}</span>`;
    speakerTag.style.borderColor = "rgba(148, 163, 184, 0.4)";
    speakerTag.style.color = "#94a3b8";
    speakerTag.style.background = "rgba(148, 163, 184, 0.15)";
  } else {
    const emoBadge = emotion ? `<span class="playtest-emotion-badge">[${escapeHtml(emotion)}]</span>` : "";
    speakerTag.innerHTML = `<span style="font-weight: 700;">${escapeHtml(charName)}</span>${emoBadge}`;
    speakerTag.style.borderColor = charColor;
    speakerTag.style.color = charColor;
    speakerTag.style.background = `${charColor}22`;
  }

  // Отображение спрайта на сцене визуальной новеллы
  if (charName && !parsed.isComment && centerStage) {
    const spr = resolveSprite(charName, emotion);
    if (spr && spr.url) {
      const spriteWrap = document.createElement("div");
      spriteWrap.id = "playtestCurrentSpriteWrap";
      spriteWrap.className = "playtest-sprite-wrap";
      spriteWrap.innerHTML = `<img src="${spr.url}" class="playtest-sprite-img" alt="${escapeHtml(charName)}">`;
      centerStage.appendChild(spriteWrap);
    }
  }

  // Если узел - ВЫБОР (Choice)
  if (node.type === "choice") {
    choicesBox.innerHTML = "";
    choicesBox.style.display = "flex";
    dialogueEl.innerText = "Сделайте выбор для продолжения сюжета:";

    const options = (node.content || "").split("\n").filter(Boolean);
    const conns = state.project.connections.filter(c => String(c.from) === String(node.id));

    if (options.length === 0) {
      choicesBox.innerHTML = `<div style="color: #cbd5e1;">(Варианты выбора не заданы в блоке)</div>`;
    } else {
      options.forEach((optText, idx) => {
        const btn = document.createElement("button");
        btn.className = "playtest-choice-btn";
        btn.innerText = `${idx + 1}. ${optText}`;
        btn.onclick = (e) => {
          e.stopPropagation();
          const targetConn = conns.find(c => Number(c.out_idx || 0) === idx);
          if (targetConn) {
            state.playtest.history.push(node.id);
            state.playtest.currentNodeId = targetConn.to;
            renderPlaytestStep();
          } else {
            showToast("⚠️ У этого варианта выбора нет исходящей связи!");
          }
        };
        choicesBox.appendChild(btn);
      });
    }
  } else {
    choicesBox.style.display = "none";
    dialogueEl.innerHTML = escapeHtml(node.content || "").replace(/\n/g, "<br>");
  }
}

function playtestNext() {
  if (!state.playtest.active) return;
  const node = state.project.nodes.find(n => n.id === state.playtest.currentNodeId);
  if (!node) return;

  // Если это выбор, переход осуществляется кликом по кнопке выбора
  if (node.type === "choice") return;

  const conns = state.project.connections.filter(c => String(c.from) === String(node.id));
  if (conns.length > 0) {
    state.playtest.history.push(node.id);
    state.playtest.currentNodeId = conns[0].to;
    renderPlaytestStep();
  } else {
    showToast("Сценарий подошел к концу");
  }
}

function playtestBack() {
  if (!state.playtest.active || state.playtest.history.length === 0) return;
  state.playtest.currentNodeId = state.playtest.history.pop();
  renderPlaytestStep();
}

function playtestRestart() {
  const nodes = state.project.nodes || [];
  const startNode = nodes.find(n => n.title && n.title.toLowerCase().trim() === "start") || nodes[0];
  if (startNode) {
    state.playtest.currentNodeId = startNode.id;
    state.playtest.history = [];
    renderPlaytestStep();
  }
}

// ==========================================================================
// ПЛАГИН 2: АВТО-РАССТАНОВКА УЗЛОВ (AUTO-LAYOUT DAG)
// ==========================================================================
function runAutoLayout() {
  const nodes = state.project.nodes || [];
  const conns = state.project.connections || [];
  if (nodes.length === 0) return;

  showToast("📐 Выполняется автоматическая расстановка графа...");

  const adj = {};
  const inDeg = {};
  nodes.forEach(n => {
    adj[n.id] = [];
    inDeg[n.id] = 0;
  });

  conns.forEach(c => {
    if (adj[c.from]) adj[c.from].push({ to: c.to, outIdx: Number(c.out_idx || 0) });
    if (inDeg[c.to] !== undefined) inDeg[c.to]++;
  });

  // Корни графа
  let roots = nodes.filter(n => inDeg[n.id] === 0).map(n => n.id);
  if (roots.length === 0) roots = [nodes[0].id];

  // Топологические слои (ранги X)
  const rank = {};
  roots.forEach(r => rank[r] = 0);

  const queue = [...roots];
  while (queue.length > 0) {
    const u = queue.shift();
    const currRank = rank[u];
    (adj[u] || []).forEach(edge => {
      rank[edge.to] = Math.max(rank[edge.to] || 0, currRank + 1);
      inDeg[edge.to]--;
      if (inDeg[edge.to] <= 0 && !queue.includes(edge.to)) {
        queue.push(edge.to);
      }
    });
  }

  // Для узлов вне циклов
  nodes.forEach(n => {
    if (rank[n.id] === undefined) rank[n.id] = 0;
  });

  // Группировка по рангу
  const byRank = {};
  nodes.forEach(n => {
    const r = rank[n.id];
    if (!byRank[r]) byRank[r] = [];
    byRank[r].push(n);
  });

  const moves = [];
  const startX = 120;
  const baselineY = 400;
  const dx = 320;
  const dy = 160;

  Object.keys(byRank).forEach(r => {
    const colNodes = byRank[r];
    const x = startX + Number(r) * dx;
    const totalH = colNodes.length * dy;
    const startY = baselineY - totalH / 2;

    colNodes.forEach((node, idx) => {
      const y = Math.round((startY + idx * dy) / 20) * 20;
      node.x = x;
      node.y = y;
      moves.push({ id: node.id, x: x, y: y });
      updateNodeElementPosition(node);
    });
  });

  renderConnections();
  drawMinimap();
  fitViewToNodes();

  // Отправляем изменения соавторам на сервер
  sendServer({ type: "batch_move", moves: moves });
  showToast("✅ Граф аккуратно выровнен по цепочке сценария!");
}

// ==========================================================================
// ПЛАГИН 3: ДИАГНОСТИКА СЮЖЕТА (GRAPH VALIDATOR)
// ==========================================================================
function openGraphAuditModal() {
  const modal = document.getElementById("auditModal");
  if (modal) {
    modal.classList.add("open");
    runGraphAudit();
  }
}

function closeGraphAuditModal() {
  const modal = document.getElementById("auditModal");
  if (modal) modal.classList.remove("open");
}

function runGraphAudit() {
  const nodes = state.project.nodes || [];
  const conns = state.project.connections || [];
  const container = document.getElementById("auditIssuesList");
  const summaryBar = document.getElementById("auditSummaryBar");
  if (!container) return;

  const issues = [];
  const inMap = {};
  const outMap = {};
  nodes.forEach(n => {
    inMap[n.id] = 0;
    outMap[n.id] = 0;
  });

  conns.forEach(c => {
    if (outMap[c.from] !== undefined) outMap[c.from]++;
    if (inMap[c.to] !== undefined) inMap[c.to]++;
  });

  // 1. Поиск начала сюжета
  const startNode = nodes.find(n => n.title && n.title.toLowerCase().trim() === "start");
  if (!startNode) {
    issues.push({
      severity: "warning",
      title: "Нет явного стартового блока 'start'",
      desc: "Рекомендуется назвать начальный узел истории 'start' для корректного экспорта в Ren'Py."
    });
  }

  // 2. Тупиковые реплики (Dead-ends)
  nodes.forEach(n => {
    if (outMap[n.id] === 0 && !n.title.toLowerCase().includes("end") && n.type !== "label") {
      issues.push({
        severity: "warning",
        nodeId: n.id,
        title: `Тупик: [${n.title || n.id}]`,
        desc: `У этого узла нет исходящих связей (история обрывается).`
      });
    }
  });

  // 3. Недостижимые узлы (изолированные блоки)
  nodes.forEach(n => {
    if (inMap[n.id] === 0 && n !== startNode && !n.title.toLowerCase().includes("start")) {
      issues.push({
        severity: "error",
        nodeId: n.id,
        title: `Недостижимый узел: [${n.title || n.id}]`,
        desc: `В этот блок не ведет ни одна связь — игрок никогда сюда не попадет.`
      });
    }
  });

  // 4. Пустые развилки
  nodes.filter(n => n.type === "choice").forEach(n => {
    const opts = (n.content || "").split("\n").filter(Boolean);
    const outs = conns.filter(c => String(c.from) === String(n.id));
    if (outs.length < opts.length) {
      issues.push({
        severity: "warning",
        nodeId: n.id,
        title: `Выбор не полностью соединен: [${n.title || n.id}]`,
        desc: `В блоке ${opts.length} вариантов, но подключено только ${outs.length} стрелок.`
      });
    }
  });

  // Рендер отчета
  const errCount = issues.filter(i => i.severity === "error").length;
  const warnCount = issues.filter(i => i.severity === "warning").length;

  summaryBar.innerHTML = `
    <span style="color: ${errCount ? '#ef4444' : '#10b981'}; font-weight: 700;">Ошибок: ${errCount}</span>
    <span>•</span>
    <span style="color: ${warnCount ? '#f59e0b' : '#94a3b8'}; font-weight: 700;">Предупреждений: ${warnCount}</span>
    <span>•</span>
    <span style="color: #94a3b8;">Всего узлов: ${nodes.length}</span>
  `;

  container.innerHTML = "";
  if (issues.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 30px; color: #10b981; font-size: 15px; font-weight: 600;">
        🎉 Отлично! Сюжетный граф не содержит тупиков и изолированных блоков.
      </div>
    `;
    return;
  }

  issues.forEach(iss => {
    const item = document.createElement("div");
    const borderCol = iss.severity === "error" ? "#ef4444" : "#f59e0b";
    item.style.cssText = `background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-left: 3px solid ${borderCol}; padding: 10px 14px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;`;

    item.innerHTML = `
      <div>
        <div style="font-weight: 600; color: #f8fafc; font-size: 13px;">${escapeHtml(iss.title)}</div>
        <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">${escapeHtml(iss.desc)}</div>
      </div>
      ${iss.nodeId ? `<button class="btn btn-primary" onclick="closeGraphAuditModal(); focusOnNode('${iss.nodeId}')" style="padding: 4px 10px; font-size: 12px;">📍 Перейти</button>` : ""}
    `;
    container.appendChild(item);
  });
}

// ==========================================================================
// ПЛАГИН 4: СТАТИСТИКА СЛОВ И ПЕРСОНАЖЕЙ (WORD COUNTER)
// ==========================================================================
function openWordStatsModal() {
  const modal = document.getElementById("statsModal");
  if (!modal) return;
  modal.classList.add("open");

  const nodes = state.project.nodes || [];
  let totalWords = 0;
  let totalChars = 0;
  const charStats = {};

  nodes.forEach(n => {
    const text = (n.content || "").trim();
    const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
    const chars = text.length;

    totalWords += words;
    totalChars += chars;

    const speaker = (n.title || "Без имени").trim();
    if (!charStats[speaker]) {
      charStats[speaker] = { lines: 0, words: 0, chars: 0, color: getNodeHeaderColor(n) };
    }
    charStats[speaker].lines++;
    charStats[speaker].words += words;
    charStats[speaker].chars += chars;
  });

  document.getElementById("statTotalWords").innerText = totalWords.toLocaleString();
  document.getElementById("statTotalChars").innerText = totalChars.toLocaleString();
  document.getElementById("statTotalNodes").innerText = nodes.length;
  document.getElementById("statReadingTime").innerText = Math.max(1, Math.ceil(totalWords / 160)) + " мин";

  const tableEl = document.getElementById("statCharactersTable");
  tableEl.innerHTML = "";

  const sortedSpeakers = Object.keys(charStats).sort((a, b) => charStats[b].words - charStats[a].words);
  sortedSpeakers.forEach(spk => {
    const s = charStats[spk];
    const pct = totalWords > 0 ? Math.round((s.words / totalWords) * 100) : 0;

    const row = document.createElement("div");
    row.style.cssText = "background: rgba(255,255,255,0.03); border: 1px solid var(--border); padding: 8px 12px; border-radius: 6px; display: flex; flex-direction: column; gap: 4px;";
    row.innerHTML = `
      <div style="display: flex; justify-content: space-between; font-size: 13px;">
        <span style="font-weight: 700; color: ${s.color};">${escapeHtml(spk)}</span>
        <span style="color: #cbd5e1;">${s.lines} реплик • ${s.words} слов (${pct}%)</span>
      </div>
      <div style="width: 100%; height: 5px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden;">
        <div style="width: ${pct}%; height: 100%; background: ${s.color};"></div>
      </div>
    `;
    tableEl.appendChild(row);
  });
}

function closeWordStatsModal() {
  const modal = document.getElementById("statsModal");
  if (modal) modal.classList.remove("open");
}

// ==========================================================================
// ПЛАГИН 5: ЭКСПОРТ В REN'PY (.RPY)
// ==========================================================================
function openRenPyExportModal() {
  const modal = document.getElementById("renpyModal");
  if (!modal) return;
  modal.classList.add("open");

  const rpyCode = generateRenPyScript();
  const preview = document.getElementById("renpyCodePreview");
  if (preview) preview.value = rpyCode;
}

function closeRenPyExportModal() {
  const modal = document.getElementById("renpyModal");
  if (modal) modal.classList.remove("open");
}

function generateRenPyScript() {
  const nodes = state.project.nodes || [];
  const conns = state.project.connections || [];

  let out = `# Generated by Dialogue Engine Studio 24/7\n# Project: ${state.project.metadata.title || "Violant"}\n\n`;

  // 1. Определение персонажей
  const characters = new Set();
  nodes.forEach(n => {
    if (n.title && !n.title.startsWith("#") && n.type === "story") {
      characters.add(n.title.trim());
    }
  });

  out += `# --- Characters ---\n`;
  const charVarMap = {};
  characters.forEach(cName => {
    const slug = cName.toLowerCase().replace(/[^a-z0-9]/g, "_") || "speaker";
    const varName = `char_${slug}`;
    charVarMap[cName] = varName;
    out += `define ${varName} = Character("${cName}")\n`;
  });

  out += `\n# --- Scenario Script ---\n`;
  nodes.forEach(node => {
    const labelName = `node_${node.id}`;
    out += `\nlabel ${labelName}:\n`;

    if (node.type === "story") {
      const varName = charVarMap[node.title] || "";
      const text = (node.content || "").replace(/"/g, '\\"');
      if (varName) {
        out += `    ${varName} "${text}"\n`;
      } else {
        out += `    "${text}"\n`;
      }
    } else if (node.type === "choice") {
      out += `    menu:\n`;
      const opts = (node.content || "").split("\n").filter(Boolean);
      opts.forEach((optText, idx) => {
        const c = conns.find(conn => String(conn.from) === String(node.id) && Number(conn.out_idx || 0) === idx);
        out += `        "${optText}":\n`;
        if (c) {
          out += `            jump node_${c.to}\n`;
        } else {
          out += `            pass\n`;
        }
      });
      return;
    } else if (node.type === "music") {
      out += `    play music "${node.content || 'music.mp3'}"\n`;
    }

    // Переход к следующему блоку
    const nextConns = conns.filter(c => String(c.from) === String(node.id));
    if (nextConns.length > 0) {
      out += `    jump node_${nextConns[0].to}\n`;
    } else {
      out += `    return\n`;
    }
  });

  return out;
}

function copyRenPyCode() {
  const preview = document.getElementById("renpyCodePreview");
  if (preview) {
    preview.select();
    navigator.clipboard.writeText(preview.value).then(() => {
      showToast("📋 Код Ren'Py скопирован в буфер обмена!");
    });
  }
}

function downloadRenPyFile() {
  const code = generateRenPyScript();
  const blob = new Blob([code], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "script.rpy";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast("📥 Файл script.rpy успешно скачан!");
}

// ==========================================================================
// ПОИСК, ФОКУСИРОВКА И УТИЛИТЫ
// ==========================================================================
function fitViewToNodes() {
  const nodes = state.project.nodes || [];
  if (nodes.length === 0) return;

  const bounds = getGraphBounds();
  const container = document.getElementById("canvasContainer");
  const viewW = container ? container.clientWidth : window.innerWidth;
  const viewH = container ? container.clientHeight : window.innerHeight;

  const scaleX = viewW / bounds.width;
  const scaleY = viewH / bounds.height;
  const newZoom = Math.max(0.015, Math.min(1.2, Math.min(scaleX, scaleY)));

  state.zoom = newZoom;
  state.pan.x = (viewW - bounds.width * newZoom) / 2 - bounds.minX * newZoom;
  state.pan.y = (viewH - bounds.height * newZoom) / 2 - bounds.minY * newZoom;

  applyWorldTransform();
  showToast(`🎯 Весь граф (${nodes.length} узлов) умещен на экране`);
}

function focusOnNode(nodeId) {
  const node = state.project.nodes.find(n => String(n.id) === String(nodeId));
  if (!node) return;
  const container = document.getElementById("canvasContainer");
  const viewW = container ? container.clientWidth : window.innerWidth;
  const viewH = container ? container.clientHeight : window.innerHeight;

  state.zoom = 1.0;
  state.pan.x = viewW / 2 - (node.x + 105) * state.zoom;
  state.pan.y = viewH / 2 - (node.y + 50) * state.zoom;
  applyWorldTransform();
  selectNode(node.id);

  const el = document.getElementById(`node_${node.id}`);
  if (el) {
    el.style.boxShadow = "0 0 28px #ffcc00";
    el.style.borderColor = "#ffcc00";
    setTimeout(() => {
      el.style.boxShadow = "";
      el.style.borderColor = "";
    }, 2500);
  }
}

function openNodeSearchModal() {
  const modal = document.getElementById("searchModal");
  if (modal) {
    modal.classList.add("open");
    filterNodeList("");
    const input = document.getElementById("nodeSearchInput");
    if (input) {
      input.value = "";
      setTimeout(() => input.focus(), 120);
    }
  }
}

function closeNodeSearchModal() {
  const modal = document.getElementById("searchModal");
  if (modal) modal.classList.remove("open");
}

function filterNodeList(q) {
  const container = document.getElementById("nodeSearchResults");
  if (!container) return;
  const query = (q || "").toLowerCase().trim();
  const nodes = state.project.nodes || [];
  const filtered = nodes.filter(n => {
    if (!query) return true;
    const title = (n.title || "").toLowerCase();
    const content = (n.content || "").toLowerCase();
    const id = String(n.id).toLowerCase();
    const type = (n.type || "").toLowerCase();
    return title.includes(query) || content.includes(query) || id.includes(query) || type.includes(query);
  });

  const countEl = document.getElementById("searchResultCount");
  if (countEl) countEl.innerText = filtered.length;

  container.innerHTML = "";
  if (filtered.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: #64748b; padding: 25px;">Ничего не найдено</div>`;
    return;
  }

  filtered.slice(0, 100).forEach(n => {
    const item = document.createElement("div");
    const hCol = getNodeHeaderColor(n);
    item.style.cssText = "padding: 10px 14px; background: rgba(255,255,255,0.03); border-radius: 8px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; border: 1px solid var(--border);";
    item.onmouseenter = () => item.style.borderColor = "#4f8cff";
    item.onmouseleave = () => item.style.borderColor = "var(--border)";
    item.onclick = () => {
      closeNodeSearchModal();
      focusOnNode(n.id);
      showToast(`📍 Узел: ${n.title || n.id}`);
    };

    const preview = (n.content || "").slice(0, 75).replace(/\n/g, " ");
    item.innerHTML = `
      <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 80%;">
        <span style="font-weight: 700; color: ${hCol};">${escapeHtml(n.title || "Безымянный")}</span>
        <span style="font-size: 11px; color: #64748b; margin-left: 6px;">(${n.type})</span>
        <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">${escapeHtml(preview)}</div>
      </div>
      <span style="color: #4f8cff; font-size: 12px; font-weight: 600;">Перейти ➔</span>
    `;
    container.appendChild(item);
  });
}

function closeAllModals() {
  document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("open"));
  stopQuickPlaytest();
}

// ==========================================================================
// СОЗДАНИЕ, ИЗМЕНЕНИЕ И УДАЛЕНИЕ НОД
// ==========================================================================
function createNode(type) {
  const screenCenterX = window.innerWidth / 2;
  const screenCenterY = window.innerHeight / 2;
  const worldX = Math.round(((screenCenterX - state.pan.x) / state.zoom - 105) / 20) * 20;
  const worldY = Math.round(((screenCenterY - state.pan.y) / state.zoom - 50) / 20) * 20;

  const titles = {
    story: "Реплика",
    choice: "Выбор",
    condition: "Условие",
    music: "Фоновая музыка",
    media: "Фон / Спрайт",
    label: "Метка сцены",
    pause: "Пауза"
  };

  const newNode = {
    id: String(Math.floor(Date.now() + Math.random() * 1000)),
    x: worldX,
    y: worldY,
    title: titles[type] || "Блок",
    content: type === "choice" ? "Вариант 1\nВариант 2" : "Текст сценария...",
    type: type,
    mode: "standard",
    custom_data: {}
  };

  state.project.nodes.push(newNode);
  renderNode(newNode);
  updateHeaderInfo();
  selectNode(newNode.id);
  drawMinimap();

  sendServer({ type: "node_create", node: newNode });
  showToast(`Создан блок: ${newNode.title}`);
}

function deleteNode(id) {
  if (!confirm("Удалить этот узел и все его связи?")) return;
  state.project.nodes = state.project.nodes.filter(n => n.id !== id);
  state.project.connections = state.project.connections.filter(c => c.from !== id && c.to !== id);
  const el = document.getElementById(`node_${id}`);
  if (el) el.remove();
  renderConnections();
  updateHeaderInfo();
  drawMinimap();
  sendServer({ type: "node_delete", id: id });
}

function createConnection(fromId, toId, outIdx) {
  if (fromId === toId) return;
  const exists = state.project.connections.some(c => String(c.from) === String(fromId) && String(c.to) === String(toId) && Number(c.out_idx || 0) === Number(outIdx || 0));
  if (exists) return;

  const conn = {
    from: String(fromId),
    out_idx: Number(outIdx || 0),
    to: String(toId)
  };

  state.project.connections.push(conn);
  renderConnections();
  drawMinimap();
  sendServer({ type: "connection_create", connection: conn });
}

function deleteConnection(fromId, toId, outIdx) {
  state.project.connections = state.project.connections.filter(c => !(String(c.from) === String(fromId) && String(c.to) === String(toId) && Number(c.out_idx || 0) === Number(outIdx || 0)));
  renderConnections();
  drawMinimap();
  sendServer({ type: "connection_delete", from: fromId, to: toId, out_idx: outIdx });
}

// Редактирование в модальном окне
function openNodeModal(id) {
  const node = state.project.nodes.find(n => n.id === id);
  if (!node) return;

  document.getElementById("editNodeId").value = node.id;
  document.getElementById("editNodeType").value = node.type;
  document.getElementById("editNodeTitle").value = node.title || "";
  document.getElementById("editNodeContent").value = node.content || "";
  document.getElementById("editNodeColor").value = (node.custom_data && node.custom_data.header_color) || "";
  const colorPicker = document.getElementById("editNodeColorPicker");
  if (colorPicker) {
    colorPicker.value = (node.custom_data && node.custom_data.header_color) || "#3b82f6";
  }

  // Разбираем персонажа и эмоцию из заголовка
  const parsed = parseTitleCharacterAndEmotion(node.title);
  const charName = parsed.character || "";
  const emotion = parsed.emotion || (node.custom_data && node.custom_data.emotion) || "";

  // Цвет имени персонажа (header_text_color)
  const nameColor = (node.custom_data && node.custom_data.header_text_color) || getCharacterColor(charName) || "#ffffff";
  setCharTextColor(nameColor);

  // Эмоция
  const emoInput = document.getElementById("editNodeEmotion");
  if (emoInput) emoInput.value = emotion;

  // Отрисовка быстрых чипов персонажей
  renderCharQuickPills(charName);

  // Отрисовка пресетов эмоций
  renderEmotionPills(charName, emotion);

  // Превью спрайта в модалке
  updateNodeModalSpritePreview(charName, emotion);

  // Видимость блоков в зависимости от типа узла
  onNodeTypeChanged(node.type);

  document.getElementById("nodeModal").classList.add("open");
}

function closeNodeModal() {
  document.getElementById("nodeModal").classList.remove("open");
}

function onNodeTypeChanged(type) {
  const isStory = (type === "story");
  const charGroup = document.getElementById("nodeHeaderTextColorGroup");
  const emoGroup = document.getElementById("nodeEmotionGroup");
  const spritePreview = document.getElementById("nodeSpritePreviewContainer");
  if (charGroup) charGroup.style.display = isStory ? "block" : "none";
  if (emoGroup) emoGroup.style.display = isStory ? "block" : "none";
  if (spritePreview) spritePreview.style.display = isStory ? "flex" : "none";
}

function setCharTextColor(color) {
  if (!color) color = "#ffffff";
  const input = document.getElementById("editNodeHeaderTextColor");
  const picker = document.getElementById("editNodeHeaderTextColorPicker");
  const preview = document.getElementById("charColorPreview");
  if (input) input.value = color;
  if (picker && color.startsWith("#") && color.length === 7) picker.value = color;
  if (preview) {
    preview.style.color = color;
    const titleVal = document.getElementById("editNodeTitle")?.value || "";
    const parsed = parseTitleCharacterAndEmotion(titleVal);
    preview.innerText = parsed.character || "Имя персонажа";
  }
}

function setNarratorTitle() {
  const titleInput = document.getElementById("editNodeTitle");
  if (titleInput) titleInput.value = "#";
  const emoInput = document.getElementById("editNodeEmotion");
  if (emoInput) emoInput.value = "";
  setCharTextColor("#94a3b8");
  updateNodeModalSpritePreview("", "");
}

function onNodeTitleInput(val) {
  const parsed = parseTitleCharacterAndEmotion(val);
  const charName = parsed.character || "";
  const currentEmotion = document.getElementById("editNodeEmotion")?.value || "";
  const emotion = parsed.emotion || currentEmotion;

  // Если персонаж сменился и текущий цвет совпадает с дефолтом или белым, подтягиваем цвет героя
  const charColor = getCharacterColor(charName);
  const currentTextColor = document.getElementById("editNodeHeaderTextColor")?.value || "";
  if (!currentTextColor || currentTextColor === "#ffffff") {
    setCharTextColor(charColor);
  } else {
    // Обновляем текст в бейджике превью
    const preview = document.getElementById("charColorPreview");
    if (preview) preview.innerText = charName || "Имя персонажа";
  }

  if (parsed.emotion) {
    const emoInput = document.getElementById("editNodeEmotion");
    if (emoInput) emoInput.value = parsed.emotion;
  }

  renderCharQuickPills(charName);
  renderEmotionPills(charName, emotion);
  updateNodeModalSpritePreview(charName, emotion);
}

function onEmotionInputChanged(val) {
  const titleInput = document.getElementById("editNodeTitle");
  if (!titleInput) return;
  const parsed = parseTitleCharacterAndEmotion(titleInput.value);
  const charName = parsed.character || titleInput.value.split("(")[0].trim();

  if (charName && !charName.startsWith("#")) {
    if (val.trim()) {
      titleInput.value = `${charName} (${val.trim()})`;
    } else {
      titleInput.value = charName;
    }
  }

  renderEmotionPills(charName, val);
  updateNodeModalSpritePreview(charName, val);
}

function clearEmotion() {
  const emoInput = document.getElementById("editNodeEmotion");
  if (emoInput) emoInput.value = "";
  onEmotionInputChanged("");
}

function selectCharQuickPill(charName) {
  const emoInput = document.getElementById("editNodeEmotion");
  const emotion = emoInput ? emoInput.value.trim() : "";
  const titleInput = document.getElementById("editNodeTitle");
  if (titleInput) {
    titleInput.value = emotion ? `${charName} (${emotion})` : charName;
  }
  const color = getCharacterColor(charName);
  setCharTextColor(color);
  renderCharQuickPills(charName);
  renderEmotionPills(charName, emotion);
  updateNodeModalSpritePreview(charName, emotion);
}

function renderCharQuickPills(activeCharName) {
  const container = document.getElementById("charQuickPills");
  if (!container) return;
  container.innerHTML = "";

  const knownChars = new Set(["???", "Энджи", "Ника", "Ривер", "Джен", "Телевизор"]);
  if (state.project && state.project.characters) {
    state.project.characters.forEach(c => {
      if (c.name && c.name.trim()) knownChars.add(c.name.trim());
    });
  }

  const activeClean = (activeCharName || "").trim().toLowerCase();
  knownChars.forEach(name => {
    const color = getCharacterColor(name);
    const isActive = (name.toLowerCase() === activeClean);
    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = `char-quick-pill ${isActive ? "active" : ""}`;
    pill.style.borderColor = isActive ? color : `${color}44`;
    pill.innerHTML = `
      <span style="width: 8px; height: 8px; border-radius: 50%; background: ${color}; display: inline-block;"></span>
      <span>${escapeHtml(name)}</span>
    `;
    pill.onclick = () => selectCharQuickPill(name);
    container.appendChild(pill);
  });
}

function renderEmotionPills(charName, activeEmotion) {
  const container = document.getElementById("nodeEmotionPills");
  if (!container) return;
  container.innerHTML = "";

  if (!charName || charName.startsWith("#")) return;

  const charClean = charName.trim().toLowerCase();
  let emotions = ["обычный", "радость", "грусть", "злость", "удивление", "смущение"];

  if (charClean === "ника" || charClean === "nika") {
    emotions = ["pose_01", "pose_02", "pose_03", "pose_04", "pose_05", "pose_06", "pose_07", "pose_08", "pose_09", "pose_10"];
  }

  const activeClean = (activeEmotion || "").trim().toLowerCase();
  emotions.forEach(emo => {
    const isActive = (emo.toLowerCase() === activeClean);
    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = `emotion-quick-pill ${isActive ? "active" : ""}`;
    pill.innerText = emo;
    pill.onclick = () => {
      const emoInput = document.getElementById("editNodeEmotion");
      if (emoInput) emoInput.value = emo;
      onEmotionInputChanged(emo);
    };
    container.appendChild(pill);
  });
}

function updateNodeModalSpritePreview(charName, emotion) {
  const imgEl = document.getElementById("nodeModalSpriteImg");
  const placeholderEl = document.getElementById("nodeModalSpritePlaceholder");
  const titleEl = document.getElementById("nodeModalSpriteTitle");
  const fileEl = document.getElementById("nodeModalSpriteFile");
  if (!imgEl || !placeholderEl || !titleEl || !fileEl) return;

  if (!charName || charName.startsWith("#")) {
    imgEl.style.display = "none";
    placeholderEl.style.display = "flex";
    titleEl.innerText = charName ? "💭 Слова автора" : "Персонаж не выбран";
    fileEl.innerText = "—";
    return;
  }

  titleEl.innerText = emotion ? `${charName} (${emotion})` : charName;
  const spr = resolveSprite(charName, emotion);
  if (spr && spr.url) {
    imgEl.src = spr.url;
    imgEl.style.display = "block";
    placeholderEl.style.display = "none";
    fileEl.innerText = `🧍 ${spr.file || spr.name || "спрайт"}`;
    fileEl.style.color = "#10b981";
  } else {
    imgEl.style.display = "none";
    placeholderEl.style.display = "flex";
    fileEl.innerText = "Спрайт не найден на диске";
    fileEl.style.color = "#94a3b8";
  }
}

function setEditColor(color) {
  document.getElementById("editNodeColor").value = color;
  const picker = document.getElementById("editNodeColorPicker");
  if (picker && color) picker.value = color;
}

function saveNodeModal() {
  const id = document.getElementById("editNodeId").value;
  const node = state.project.nodes.find(n => n.id === id);
  if (!node) return;

  node.type = document.getElementById("editNodeType").value;
  node.title = document.getElementById("editNodeTitle").value.trim();
  node.content = document.getElementById("editNodeContent").value;

  node.custom_data = node.custom_data || {};

  // Сохранение цвета шапки узла
  const customColor = document.getElementById("editNodeColor").value;
  if (customColor) {
    node.custom_data.header_color = customColor;
  } else {
    delete node.custom_data.header_color;
  }

  // Сохранение цвета имени персонажа
  const headerTextColor = document.getElementById("editNodeHeaderTextColor").value.trim();
  if (headerTextColor) {
    node.custom_data.header_text_color = headerTextColor;
  }

  // Сохранение эмоции и пути к спрайту
  const emotion = document.getElementById("editNodeEmotion").value.trim();
  if (emotion) {
    node.custom_data.emotion = emotion;
  } else {
    delete node.custom_data.emotion;
  }

  const parsed = parseTitleCharacterAndEmotion(node.title);
  const spr = resolveSprite(parsed.character, emotion || parsed.emotion);
  if (spr && spr.url) {
    node.custom_data.sprite_path = spr.url;
  }

  renderNode(node);
  renderConnections();
  updateHeaderInfo();
  closeNodeModal();

  sendServer({ type: "node_update", node: node });
}

function deleteCurrentNode() {
  const id = document.getElementById("editNodeId").value;
  closeNodeModal();
  if (id) deleteNode(id);
}

// ==========================================================================
// БАЗА ПЕРСОНАЖЕЙ (CHARACTER MANAGER)
// ==========================================================================
function openCharactersModal() {
  renderCharactersList();
  document.getElementById("charactersModal").classList.add("open");
}

function closeCharactersModal() {
  document.getElementById("charactersModal").classList.remove("open");
}

function renderCharactersList() {
  const container = document.getElementById("charactersListContainer");
  if (!container) return;
  container.innerHTML = "";

  const charsMap = new Map();
  (state.project.characters || []).forEach(c => {
    if (c.name && c.name.trim()) charsMap.set(c.name.trim(), { ...c });
  });

  // Подсчет реплик в графе
  const linesCount = {};
  (state.project.nodes || []).forEach(n => {
    if (n.type === "story" && n.title) {
      const parsed = parseTitleCharacterAndEmotion(n.title);
      if (parsed.character && !parsed.isComment) {
        linesCount[parsed.character] = (linesCount[parsed.character] || 0) + 1;
        if (!charsMap.has(parsed.character)) {
          charsMap.set(parsed.character, {
            name: parsed.character,
            color: (n.custom_data && n.custom_data.header_text_color) || getCharacterColor(parsed.character),
            emotions: ["обычный", "радость", "грусть", "злость"]
          });
        }
      }
    }
  });

  if (charsMap.size === 0) {
    container.innerHTML = `<div style="color: #94a3b8; text-align: center; padding: 20px;">Персонажи не найдены. Нажмите "Добавить персонажа" или "Сканировать из сценария".</div>`;
    return;
  }

  charsMap.forEach((charData, name) => {
    const color = charData.color || getCharacterColor(name);
    const count = linesCount[name] || 0;
    const card = document.createElement("div");
    card.className = "char-manager-card";
    card.innerHTML = `
      <div style="display: flex; align-items: center; gap: 12px;">
        <div class="char-avatar-badge" style="background: ${color}33; color: ${color}; border-color: ${color};">
          ${(name[0] || "?").toUpperCase()}
        </div>
        <div>
          <div style="font-weight: 700; font-size: 14px; color: ${color}; display: flex; align-items: center; gap: 8px;">
            <span>${escapeHtml(name)}</span>
            <span style="font-size: 11px; padding: 2px 7px; border-radius: 10px; background: rgba(255,255,255,0.08); color: #cbd5e1; font-weight: normal;">${count} реплик</span>
          </div>
          <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
            Цвет имени: <span style="font-family: monospace; color: ${color}; font-weight: bold;">${color}</span>
          </div>
        </div>
      </div>
      <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
        <input type="color" value="${color}" style="width: 32px; height: 32px; padding: 0; border: none; border-radius: 4px; cursor: pointer; background: transparent;"
          onchange="updateCharacterColor('${escapeHtml(name)}', this.value)">
        <button class="btn" style="font-size: 11px; padding: 5px 10px; background: rgba(79, 140, 255, 0.15); border-color: #4f8cff; color: #93c5fd;"
          onclick="applyCharacterColorToAllNodes('${escapeHtml(name)}', '${color}')" title="Применить этот цвет ко всем узлам этого персонажа">
          🎨 Окрасить все реплики
        </button>
      </div>
    `;
    container.appendChild(card);
  });
}

function updateCharacterColor(name, newColor) {
  state.project.characters = state.project.characters || [];
  let found = state.project.characters.find(c => c.name && c.name.trim().toLowerCase() === name.trim().toLowerCase());
  if (found) {
    found.color = newColor;
  } else {
    found = { name: name, color: newColor, emotions: ["обычный", "радость", "грусть", "злость"] };
    state.project.characters.push(found);
  }
  renderCharactersList();
  sendServer({ type: "character_update", character: found });
  showToast(`Цвет персонажа "${name}" изменен на ${newColor}`);
}

async function applyCharacterColorToAllNodes(name, color) {
  const cleanName = name.trim().toLowerCase();
  let updatedCount = 0;
  (state.project.nodes || []).forEach(n => {
    if (n.type === "story" && n.title) {
      const parsed = parseTitleCharacterAndEmotion(n.title);
      if (parsed.character && parsed.character.toLowerCase() === cleanName) {
        n.custom_data = n.custom_data || {};
        n.custom_data.header_text_color = color;
        renderNode(n);
        updatedCount++;
      }
    }
  });

  sendServer({ type: "character_batch_apply_color", name: name, color: color });
  showToast(`✅ Цвет применен к ${updatedCount} репликам персонажа "${name}"!`);
}

function scanCharactersFromGraph() {
  const discovered = new Set();
  (state.project.nodes || []).forEach(n => {
    if (n.type === "story" && n.title) {
      const parsed = parseTitleCharacterAndEmotion(n.title);
      if (parsed.character && !parsed.isComment) {
        discovered.add(parsed.character);
      }
    }
  });

  state.project.characters = state.project.characters || [];
  let added = 0;
  discovered.forEach(name => {
    const exists = state.project.characters.some(c => c.name && c.name.trim().toLowerCase() === name.toLowerCase());
    if (!exists) {
      const newChar = {
        name: name,
        color: getCharacterColor(name),
        emotions: ["обычный", "радость", "грусть", "злость"]
      };
      state.project.characters.push(newChar);
      sendServer({ type: "character_update", character: newChar });
      added++;
    }
  });

  renderCharactersList();
  showToast(added > 0 ? `Найдено и добавлено новых персонажей: ${added}` : "Все персонажи уже в базе!");
}

function openAddCharacterPrompt() {
  const name = prompt("Введите имя нового персонажа:");
  if (!name || !name.trim()) return;
  const clean = name.trim();
  state.project.characters = state.project.characters || [];
  if (state.project.characters.some(c => c.name.toLowerCase() === clean.toLowerCase())) {
    showToast("Персонаж с таким именем уже существует!");
    return;
  }
  const color = getCharacterColor(clean);
  const newChar = {
    name: clean,
    color: color,
    emotions: ["обычный", "радость", "грусть", "злость"]
  };
  state.project.characters.push(newChar);
  renderCharactersList();
  sendServer({ type: "character_update", character: newChar });
  showToast(`Персонаж "${clean}" добавлен!`);
}

// ==========================================================================
// СОХРАНЕНИЕ, ЭКСПОРТ JSON И СЕТЕВЫЕ КУРСОРЫ
// ==========================================================================
function saveProject() {
  sendServer({ type: "save_project" });
  showToast("💾 Запрос сохранения отправлен на сервер...");
}

function downloadProjectJson() {
  fetch("/api/project")
    .then(res => res.json())
    .then(data => {
      const blob = new Blob([JSON.stringify(data, null, 4)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "violant.json";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast("📥 Файл violant.json скачан!");
    })
    .catch(err => {
      console.error("Download error:", err);
      window.open("/api/project", "_blank");
    });
}

function updateHeaderInfo() {
  const title = (state.project.metadata && state.project.metadata.title) || "violant.json";
  const titleEl = document.getElementById("lblProjectTitle");
  if (titleEl) titleEl.innerText = title;

  const countEl = document.getElementById("lblNodeCount");
  if (countEl && state.project.nodes) {
    countEl.innerText = `${state.project.nodes.length} узлов`;
  }
  updateCollaboratorsUI();
}

function updateCollaboratorsUI() {
  const count = state.collaborators.length || 1;
  const lbl = document.getElementById("lblOnlineCount");
  if (lbl) lbl.innerText = count;

  const drawerLbl = document.getElementById("drawerOnlineCount");
  if (drawerLbl) drawerLbl.innerText = count;

  const container = document.getElementById("avatarsContainer");
  if (container) {
    container.innerHTML = "";
    state.collaborators.slice(0, 4).forEach(c => {
      const av = document.createElement("div");
      av.className = "user-avatar";
      av.style.backgroundColor = c.color || "#4f8cff";
      av.innerText = (c.name || "U")[0].toUpperCase();
      container.appendChild(av);
    });
  }

  const listEl = document.getElementById("collaboratorsList");
  if (listEl) {
    listEl.innerHTML = "";
    state.collaborators.forEach(c => {
      const row = document.createElement("div");
      row.style.cssText = "display: flex; align-items: center; gap: 8px; font-size: 12px; padding: 4px 6px; background: rgba(255,255,255,0.03); border-radius: 4px;";
      row.innerHTML = `
        <span style="width: 8px; height: 8px; border-radius: 50%; background: ${c.color || '#4f8cff'};"></span>
        <span style="color: #f8fafc; font-weight: 600;">${escapeHtml(c.name || "Участник")}</span>
        <span style="color: #64748b; font-size: 10px; margin-left: auto;">${c.device || ""}</span>
      `;
      listEl.appendChild(row);
    });
  }
}

function updateRemoteCursor(clientId, userName, color, wx, wy) {
  let el = document.getElementById(`cursor_${clientId}`);
  if (!el) {
    el = document.createElement("div");
    el.id = `cursor_${clientId}`;
    el.className = "remote-cursor";
    el.innerHTML = `
      <div class="remote-cursor-arrow" style="border-bottom-color: ${color || '#ffcc00'};"></div>
      <div class="remote-cursor-label" style="background-color: ${color || '#ffcc00'};">${escapeHtml(userName || "Соавтор")}</div>
    `;
    document.getElementById("remoteCursorsContainer").appendChild(el);
  }
  el.style.transform = `translate(${wx}px, ${wy}px)`;
}

function removeRemoteCursor(clientId) {
  const el = document.getElementById(`cursor_${clientId}`);
  if (el) el.remove();
}

// Чат
function toggleDrawer() {
  const drawer = document.getElementById("coworkDrawer");
  if (drawer) drawer.classList.toggle("open");
}

function setupChatKey() {
  const input = document.getElementById("inputChatMsg");
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendChatMessage();
    });
  }
}

function sendChatMessage() {
  const input = document.getElementById("inputChatMsg");
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;
  sendServer({ type: "chat_message", text: text });
  input.value = "";
}

function addChatMsg(msg) {
  const box = document.getElementById("chatBox");
  if (!box) return;
  const el = document.createElement("div");
  el.className = "chat-msg";
  el.innerHTML = `
    <span class="chat-author" style="color: ${msg.color || '#4f8cff'};">${escapeHtml(msg.user || "Гость")}:</span>
    <span class="chat-text">${escapeHtml(msg.text || "")}</span>
    <span class="chat-time">${msg.time || ""}</span>
  `;
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

function updateMyName() {
  const input = document.getElementById("inputMyName");
  if (!input) return;
  const name = input.value.trim();
  if (name) {
    state.myUser.name = name;
    localStorage.setItem("de_user_name", name);
    sendServer({ type: "user_info", name: name });
    showToast(`Имя изменено на: ${name}`);
  }
}

// Тосты / Уведомления
function showToast(text) {
  let toast = document.getElementById("appToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "appToast";
    toast.style.cssText = "position: fixed; bottom: 74px; left: 50%; transform: translateX(-50%); background: rgba(18,20,26,0.95); border: 1px solid #4f8cff; color: #ffffff; padding: 9px 18px; border-radius: 20px; font-size: 13px; z-index: 9999; box-shadow: 0 8px 24px rgba(0,0,0,0.6); pointer-events: none; transition: opacity 0.25s;";
    document.body.appendChild(toast);
  }
  toast.innerText = text;
  toast.style.opacity = "1";
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.style.opacity = "0"; }, 2500);
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ==========================================================================
// УПРАВЛЕНИЕ СЕССИЯМИ (У КАЖДОЙ СЕССИИ СВОЯ ССЫЛКА)
// ==========================================================================
function copySessionShareLink() {
  const url = new URL(window.location.href);
  url.searchParams.set("session", state.sessionId);
  const shareUrl = url.toString();

  navigator.clipboard.writeText(shareUrl).then(() => {
    showToast(`🔗 Ссылка на сессию "${state.sessionId}" скопирована! Отправьте её для совместной работы.`);
  }).catch(() => {
    prompt("Скопируйте ссылку на сессию:", shareUrl);
  });
}

function openSessionModal() {
  const url = new URL(window.location.href);
  url.searchParams.set("session", state.sessionId);
  const linkInput = document.getElementById("sessionShareLinkInput");
  if (linkInput) linkInput.value = url.toString();

  refreshSessionsList();
  document.getElementById("sessionModal").classList.add("open");
}

function closeSessionModal() {
  document.getElementById("sessionModal").classList.remove("open");
}

function createNewSessionFromModal() {
  const input = document.getElementById("newSessionNameInput");
  let val = input ? input.value.trim() : "";
  if (!val) {
    val = "room_" + Math.random().toString(36).substr(2, 6);
  }
  const safeId = val.replace(/[^a-zA-Z0-9_\-]/g, "_");
  closeSessionModal();
  switchSession(safeId);
}

function switchSession(newSessionId) {
  if (newSessionId === state.sessionId) return;
  const url = new URL(window.location.href);
  url.searchParams.set("session", newSessionId);
  window.location.href = url.toString();
}

async function refreshSessionsList() {
  const container = document.getElementById("sessionsListContainer");
  if (!container) return;
  container.innerHTML = `<div style="color: #94a3b8; font-size: 12px; padding: 6px;">Загрузка списка комнат...</div>`;

  let serverSessions = [];
  try {
    const res = await fetch("/api/sessions");
    if (res.ok) {
      serverSessions = await res.json();
    }
  } catch (e) {}

  // Также собираем сессии из localStorage
  const localSessions = [];
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k && k.startsWith("de_project_")) {
      const sid = k.replace("de_project_", "");
      if (!serverSessions.some(s => s.id === sid)) {
        localSessions.push({ id: sid, title: sid, nodes_count: "локально", active_users: 1 });
      }
    }
  }

  const allSessions = [...serverSessions, ...localSessions];
  if (allSessions.length === 0) {
    allSessions.push({ id: "violant", title: "violant (основная)", nodes_count: state.project.nodes.length, active_users: 1 });
  }

  container.innerHTML = "";
  allSessions.forEach(s => {
    const isActive = (s.id === state.sessionId);
    const item = document.createElement("div");
    item.className = `session-item ${isActive ? "active" : ""}`;
    item.innerHTML = `
      <div>
        <div style="font-weight: 700; font-size: 13px; color: ${isActive ? '#60a5fa' : '#f1f5f9'}; display: flex; align-items: center; gap: 6px;">
          <span>🏷️ ${escapeHtml(s.id)}</span>
          ${isActive ? '<span style="font-size: 10px; background: #3b82f6; color: white; padding: 1px 6px; border-radius: 8px;">Текущая</span>' : ''}
        </div>
        <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
          ${s.nodes_count ? s.nodes_count + ' узлов' : ''} ${s.active_users ? '• онлайн: ' + s.active_users : ''}
        </div>
      </div>
      <button class="btn" style="font-size: 11px; padding: 3px 8px;" onclick="switchSession('${escapeHtml(s.id)}')">
        ${isActive ? 'В этой комнате' : 'Перейти ➔'}
      </button>
    `;
    container.appendChild(item);
  });
}

// ==========================================================================
// РАЗВЕРТЫВАНИЕ В GITHUB РЕПОЗИТОРИЙ
// ==========================================================================
function openGitHubModal() {
  const ghLink = document.getElementById("githubPagesUrl");
  if (ghLink) {
    ghLink.href = "https://komendant-zero.github.io/dialogue-engine/app/?session=" + encodeURIComponent(state.sessionId);
    ghLink.innerText = ghLink.href;
  }
  document.getElementById("githubModal").classList.add("open");
}

function closeGitHubModal() {
  document.getElementById("githubModal").classList.remove("open");
}

function copyGitHubPagesLink() {
  const url = "https://komendant-zero.github.io/dialogue-engine/app/?session=" + encodeURIComponent(state.sessionId);
  navigator.clipboard.writeText(url).then(() => {
    showToast("📋 Ссылка на GitHub Pages скопирована в буфер обмена!");
  }).catch(() => {
    prompt("Ссылка на GitHub Pages:", url);
  });
}
