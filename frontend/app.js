// Langsame Nachrichten — App Logic
// Security: NEVER use innerHTML for content from digest.json. textContent only.

(function () {
  "use strict";

  // --- State ---
  let digest = null;
  let currentStoryIndex = null;
  const audio = new Audio();
  audio.preservesPitch = true;

  // --- Preferences (localStorage) ---
  function getLevel() {
    const val = parseInt(localStorage.getItem("difficulty"), 10);
    return Math.max(1, Math.min(3, isNaN(val) ? 1 : val));
  }
  function setLevel(level) {
    localStorage.setItem("difficulty", String(level));
  }
  function getSpeed() {
    const val = parseFloat(localStorage.getItem("speed"));
    return isNaN(val) ? 1.0 : Math.max(0.5, Math.min(2.0, val));
  }
  function setSpeed(speed) {
    localStorage.setItem("speed", String(speed));
  }

  // --- DOM References ---
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const storyList = $("#story-list");
  const storyDetail = $("#story-detail");
  const errorState = $("#error-state");
  const loadingState = $("#loading-state");
  const levelSelector = $("#level-selector");
  const audioPlayer = $("#audio-player");

  // --- German Date Formatting ---
  const MONTHS_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
  ];
  function formatDateDE(dateStr) {
    const d = new Date(dateStr + "T00:00:00");
    return d.getDate() + ". " + MONTHS_DE[d.getMonth()] + " " + d.getFullYear();
  }

  // --- Time Formatting ---
  function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  // --- Level Selector ---
  function updateLevelUI() {
    const level = getLevel();
    $$(".level-pill").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.level === String(level));
    });
  }

  levelSelector.addEventListener("click", (e) => {
    const btn = e.target.closest(".level-pill");
    if (!btn) return;
    setLevel(parseInt(btn.dataset.level, 10));
    updateLevelUI();

    // If viewing a story, update the displayed text and audio
    if (currentStoryIndex !== null) {
      renderStoryDetail(currentStoryIndex);
    }
  });

  // --- Fetch Data ---
  async function fetchDigest() {
    try {
      const resp = await fetch("./content/latest.json");
      if (!resp.ok) throw new Error("Fetch failed: " + resp.status);
      digest = await resp.json();
      loadingState.classList.add("hidden");
      renderStoryList();
    } catch (err) {
      console.error("Failed to fetch digest:", err);
      loadingState.classList.add("hidden");
      errorState.classList.remove("hidden");
    }
  }

  // --- Render Story List ---
  function renderStoryList() {
    storyList.innerHTML = "";
    storyDetail.classList.add("hidden");
    storyList.classList.remove("hidden");
    audioPlayer.classList.add("hidden");
    audio.pause();
    currentStoryIndex = null;

    $("#date-display").textContent = formatDateDE(digest.date);

    digest.stories.forEach((story, index) => {
      const level = getLevel();
      const levelData = story.levels[String(level)];
      const duration = levelData && levelData.audio_duration_seconds
        ? Math.ceil(levelData.audio_duration_seconds / 60) + " Min."
        : "";

      const item = document.createElement("div");
      item.className = "story-entry py-4 cursor-pointer";
      item.style.animationDelay = (index * 0.1) + "s";

      if (index > 0) {
        item.classList.add("border-t", "border-border");
      }

      const headline = document.createElement("h2");
      headline.className = "font-headline text-xl font-semibold leading-snug";
      headline.textContent = story.headline_en;
      item.appendChild(headline);

      const summary = document.createElement("p");
      summary.className = "font-body text-[15px] text-secondary mt-1.5 leading-relaxed";
      summary.textContent = story.summary_en;
      item.appendChild(summary);

      if (duration) {
        const meta = document.createElement("p");
        meta.className = "font-ui text-xs text-secondary mt-2";
        meta.textContent = duration;
        item.appendChild(meta);
      }

      item.addEventListener("click", () => showStoryDetail(index));
      storyList.appendChild(item);
    });
  }

  // --- Show Story Detail ---
  function showStoryDetail(index) {
    currentStoryIndex = index;
    storyList.classList.add("hidden");
    storyDetail.classList.remove("hidden");
    audioPlayer.classList.remove("hidden");
    renderStoryDetail(index);
  }

  function renderStoryDetail(index) {
    const story = digest.stories[index];
    const level = getLevel();
    const levelData = story.levels[String(level)];

    // Headline
    const headlineDe = levelData ? levelData.text_de : story.headline_de;
    $("#detail-headline").textContent = story.headline_de;

    // Text content
    $("#german-content").textContent = levelData ? levelData.text_de : "";
    $("#english-content").textContent = levelData ? levelData.text_en : "";

    // Load audio
    audio.pause();
    if (levelData && levelData.audio_url) {
      audio.src = "./" + levelData.audio_url;
      audio.preload = "auto";
      audio.playbackRate = getSpeed();
      updatePlayButton(false);
      $("#total-time").textContent = levelData.audio_duration_seconds
        ? formatTime(levelData.audio_duration_seconds)
        : "0:00";
      $("#current-time").textContent = "0:00";
      $("#progress-fill").style.width = "0%";
    } else {
      audio.src = "";
      updatePlayButton(false);
    }
  }

  // --- Back Button ---
  $("#back-btn").addEventListener("click", () => {
    audio.pause();
    renderStoryList();
  });

  // --- Text Toggles ---
  function setupToggle(btnId, textId) {
    const btn = $(btnId);
    const text = $(textId);
    btn.addEventListener("click", () => {
      const isActive = btn.classList.toggle("active");
      text.classList.toggle("hidden", !isActive);
      text.classList.toggle("visible", isActive);
    });
  }
  setupToggle("#toggle-german", "#german-text");
  setupToggle("#toggle-english", "#english-text");

  // --- Audio Player ---
  function updatePlayButton(isPlaying) {
    $("#play-icon").classList.toggle("hidden", isPlaying);
    $("#pause-icon").classList.toggle("hidden", !isPlaying);
  }

  $("#rewind-btn").addEventListener("click", () => {
    if (!audio.src) return;
    audio.currentTime = Math.max(0, audio.currentTime - 10);
  });

  $("#play-btn").addEventListener("click", () => {
    if (!audio.src) return;
    if (audio.paused) {
      audio.play().catch((err) => console.error("Audio play failed:", err));
    } else {
      audio.pause();
    }
  });

  audio.addEventListener("play", () => updatePlayButton(true));
  audio.addEventListener("pause", () => updatePlayButton(false));
  audio.addEventListener("ended", () => updatePlayButton(false));

  audio.addEventListener("timeupdate", () => {
    if (!audio.duration) return;
    const pct = (audio.currentTime / audio.duration) * 100;
    $("#progress-fill").style.width = pct + "%";
    $("#current-time").textContent = formatTime(audio.currentTime);
  });

  audio.addEventListener("loadedmetadata", () => {
    $("#total-time").textContent = formatTime(audio.duration);
  });

  // Progress bar scrubbing
  $("#progress-bar").addEventListener("click", (e) => {
    if (!audio.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    audio.currentTime = pct * audio.duration;
  });

  // Speed selector
  $$("#speed-selector .speed-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const speed = parseFloat(btn.dataset.speed);
      setSpeed(speed);
      audio.playbackRate = speed;
      $$("#speed-selector .speed-btn").forEach((b) => {
        b.classList.toggle("active", b === btn);
      });
    });
  });

  // Initialize speed UI
  function initSpeedUI() {
    const speed = getSpeed();
    audio.playbackRate = speed;
    $$("#speed-selector .speed-btn").forEach((btn) => {
      btn.classList.toggle("active", parseFloat(btn.dataset.speed) === speed);
    });
  }

  // Media Session API for lock screen controls
  function setupMediaSession() {
    if (!("mediaSession" in navigator)) return;
    navigator.mediaSession.setActionHandler("play", () => audio.play());
    navigator.mediaSession.setActionHandler("pause", () => audio.pause());
  }

  // --- Service Worker Registration ---
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.warn("SW registration failed:", err);
    });
  }

  // --- Init ---
  updateLevelUI();
  initSpeedUI();
  setupMediaSession();
  fetchDigest();
})();
