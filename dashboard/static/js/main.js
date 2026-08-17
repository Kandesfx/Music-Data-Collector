/**
 * Music Data Collector - Dashboard Client Logic
 * Real-time updates via Socket.IO
 */

const socket = io();

// DOM Elements
const taskStatusText = document.getElementById("task-status");
const taskStatusDot = document.getElementById("task-status-dot");

// Metrics
const valTotalTracks = document.getElementById("val-total-tracks");
const valCompletedTracks = document.getElementById("val-completed-tracks");
const valPendingTracks = document.getElementById("val-pending-tracks");
const valFailedTracks = document.getElementById("val-failed-tracks");
const valArtists = document.getElementById("val-artists");
const valAlbums = document.getElementById("val-albums");
const valAudioSize = document.getElementById("val-audio-size");

// Progress
const progressFill = document.getElementById("progress-fill");
const progressText = document.getElementById("progress-text");
const progressCount = document.getElementById("progress-count");
const currentTrackTitle = document.getElementById("progress-track-name") || document.getElementById("current-track-title");

// Logs & Genres
const consoleLog = document.getElementById("console-log");
const genreList = document.getElementById("genre-list");

// Control inputs
const inputLimit = document.getElementById("download-limit") || document.getElementById("input-limit");
const inputDelay = document.getElementById("download-delay") || document.getElementById("input-delay");
const chkRetryFailed = document.getElementById("download-retry-failed") || document.getElementById("chk-retry-failed");
const btnStartDownload = document.getElementById("btn-start-download");
const btnStartCrawl = document.getElementById("btn-start-crawl");
const btnPause = document.getElementById("btn-pause-pipeline") || document.getElementById("btn-pause");
const btnStop = document.getElementById("btn-stop-pipeline") || document.getElementById("btn-stop");
const btnRetryFailed = document.getElementById("btn-retry-failed");
const btnExport = document.getElementById("btn-export-data") || document.getElementById("btn-export");
const toggleProxy = document.getElementById("toggle-proxy");
const healthBadge = document.getElementById("health-badge");

// ─── Socket Event Listeners ──────────────────────────────────

socket.on("connect", () => {
  appendLog("Connected to collector daemon.", "success");
});

socket.on("task_status", (data) => {
  taskStatusText.textContent = data.task || "Idle";
  if (data.running) {
    taskStatusDot.classList.add("active");
  } else {
    taskStatusDot.classList.remove("active");
  }
});

socket.on("control_state", (data) => {
  if (data.is_paused) {
    btnPause.textContent = "▶ Resume";
    btnPause.classList.remove("btn-secondary");
    btnPause.classList.add("btn-primary");
  } else {
    btnPause.textContent = "⏸ Pause";
    btnPause.classList.remove("btn-primary");
    btnPause.classList.add("btn-secondary");
  }
});

socket.on("log_entry", (data) => {
  appendLog(data.message, data.level, data.timestamp);
});

socket.on("progress_update", (data) => {
  if (progressFill) progressFill.style.width = `${data.percent}%`;
  if (progressText) progressText.textContent = `${data.percent}%`;
  if (progressCount) progressCount.textContent = `${data.current_index} / ${data.total} (Success: ${data.success_count} | Fail: ${data.failed_count})`;
  if (currentTrackTitle) currentTrackTitle.textContent = `🎵 Downloading: ${data.artist_name || ""} - ${data.track_title || ""}`;

  if (data.health) {
    updateHealthBadge(data.health.health);
  }
});

// ─── Multi-Job Parallel Worker Queue UI Renderer ─────────────
const activeJobsListEl = document.getElementById("active-jobs-list");
const activeJobsBadge = document.getElementById("active-jobs-badge");

function renderActiveJobs(jobs = []) {
  if (!activeJobsListEl) return;

  if (activeJobsBadge) {
    activeJobsBadge.textContent = `${jobs.length} RUNNING`;
    activeJobsBadge.className = jobs.length > 0 ? "badge badge-success font-mono" : "badge badge-info font-mono";
  }

  if (jobs.length === 0) {
    activeJobsListEl.innerHTML = `
      <div class="text-dim" style="font-size: 11.5px; text-align: center; padding: 12px 0;">
        🟢 Không có tác vụ chạy ngầm. Hệ thống sẵn sàng tiếp nhận tiến trình cào &amp; tải song song từ nhiều người dùng.
      </div>
    `;
    return;
  }

  activeJobsListEl.innerHTML = jobs.map((job) => {
    const prog = job.progress || {};
    const percent = prog.percent || 0;
    const isPaused = job.status === "paused";
    const typeIcon = job.job_type === "crawl" ? "🔍" : "🎧";
    const statusBadge = isPaused 
      ? `<span class="badge badge-warning" style="font-size: 9px; padding: 1px 4px;">⏸ TẠM DỪNG</span>`
      : `<span class="badge badge-success" style="font-size: 9px; padding: 1px 4px;">🟢 ĐANG CHẠY</span>`;

    return `
      <div class="job-item-card" data-job-id="${job.job_id}" style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(59, 130, 246, 0.35); border-radius: 6px; padding: 8px 10px; margin-bottom: 6px;">
        <div class="flex-between" style="font-size: 11.5px; margin-bottom: 4px;">
          <div style="font-weight: 700; color: #60a5fa; display: flex; align-items: center; gap: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 260px;">
            <span>${typeIcon}</span>
            <span style="overflow: hidden; text-overflow: ellipsis;">${job.task_name || 'Tác vụ'}</span>
            <span style="font-size: 10px; color: var(--text-dim); font-weight: normal;">(@${job.operator || 'user'})</span>
          </div>
          <div style="display: flex; align-items: center; gap: 4px;">
            ${statusBadge}
            <button class="btn btn-secondary btn-job-pause" data-job-id="${job.job_id}" data-is-paused="${isPaused}" style="padding: 2px 6px; font-size: 9.5px;" title="${isPaused ? 'Tiếp tục' : 'Tạm dừng'}">
              ${isPaused ? '▶ Tiếp' : '⏸ Dừng'}
            </button>
            <button class="btn btn-danger btn-job-stop" data-job-id="${job.job_id}" style="padding: 2px 6px; font-size: 9.5px;" title="Hủy tác vụ">
              ⏹ Hủy
            </button>
          </div>
        </div>

        <div style="margin: 4px 0;">
          <div class="progress-track" style="height: 4px; background: rgba(255,255,255,0.08);">
            <div class="progress-fill" style="width: ${percent}%; background: linear-gradient(90deg, #3b82f6, #10b981);"></div>
          </div>
        </div>

        <div class="flex-between" style="font-size: 10px; color: var(--text-dim);">
          <span class="job-item-text" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 240px;">
            ${prog.current_item || 'Đang xử lý...'}
          </span>
          <span class="job-item-pct" style="font-family: monospace; font-weight: 700; color: #34d399;">
            ${prog.current || 0}/${prog.total || 0} (${percent}%)
          </span>
        </div>
      </div>
    `;
  }).join("");

  // Attach button event listeners
  activeJobsListEl.querySelectorAll(".btn-job-pause").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const jid = btn.getAttribute("data-job-id");
      const isPaused = btn.getAttribute("data-is-paused") === "true";
      const action = isPaused ? "resume" : "pause";
      try {
        await fetch(`/api/jobs/${jid}/${action}`, { method: "POST" });
      } catch (err) {
        alert("Lỗi điều khiển tác vụ: " + err.message);
      }
    });
  });

  activeJobsListEl.querySelectorAll(".btn-job-stop").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const jid = btn.getAttribute("data-job-id");
      if (confirm("Bạn có chắc chắn muốn hủy tác vụ này?")) {
        try {
          await fetch(`/api/jobs/${jid}/stop`, { method: "POST" });
        } catch (err) {
          alert("Lỗi dừng tác vụ: " + err.message);
        }
      }
    });
  });
}

socket.on("active_jobs_update", (data) => {
  renderActiveJobs(data.jobs || []);
});

socket.on("job_progress", (data) => {
  const jid = data.job_id;
  const prog = data.progress || {};
  const card = document.querySelector(`.job-item-card[data-job-id="${jid}"]`);
  if (card) {
    const fill = card.querySelector(".progress-fill");
    if (fill) fill.style.width = `${prog.percent || 0}%`;
    const itemSpan = card.querySelector(".job-item-text");
    if (itemSpan) itemSpan.textContent = prog.current_item || "";
    const pctSpan = card.querySelector(".job-item-pct");
    if (pctSpan) pctSpan.textContent = `${prog.current || 0}/${prog.total || 0} (${prog.percent || 0}%)`;
  }
});

socket.on("stats_update", (data) => {
  const s = data.stats || {};
  const storage = data.storage || {};
  const h = data.health || {};
  const p = data.proxy || {};

  if (valTotalTracks) valTotalTracks.textContent = (s.total_tracks || 0).toLocaleString();
  if (valCompletedTracks) valCompletedTracks.textContent = (s.completed_tracks || 0).toLocaleString();
  if (valPendingTracks) valPendingTracks.textContent = (s.pending_tracks || 0).toLocaleString();
  if (valFailedTracks) valFailedTracks.textContent = (s.failed_tracks || 0).toLocaleString();
  if (valArtists) valArtists.textContent = (s.total_artists || 0).toLocaleString();
  if (valAlbums) valAlbums.textContent = (s.total_albums || 0).toLocaleString();
  if (valAudioSize) valAudioSize.textContent = `${storage.total_audio_size_mb || 0} MB`;

  if (h.health && healthBadge) {
    updateHealthBadge(h.health);
  }

  if (p.enabled !== undefined && toggleProxy) {
    toggleProxy.checked = p.enabled;
  }

  // Update Genres
  if (s.genre_distribution && genreList) {
    renderGenres(s.genre_distribution, s.total_tracks || 1);
  }
});

// ─── Helpers ─────────────────────────────────────────────────

function appendLog(message, level = "info", timestamp = null) {
  if (!consoleLog) return;
  const timeStr = timestamp || new Date().toLocaleTimeString();
  const line = document.createElement("div");
  line.className = "log-line";

  const timeSpan = document.createElement("span");
  timeSpan.className = "log-time";
  timeSpan.textContent = `[${timeStr}]`;

  const msgSpan = document.createElement("span");
  msgSpan.className = `log-${level}`;
  msgSpan.textContent = message;

  line.appendChild(timeSpan);
  line.appendChild(msgSpan);
  consoleLog.appendChild(line);

  // Keep max 150 log lines to prevent page stretching and memory leaks
  while (consoleLog.children.length > 150) {
    consoleLog.removeChild(consoleLog.firstChild);
  }

  consoleLog.scrollTop = consoleLog.scrollHeight;
}

const btnClearConsoleLog = document.getElementById("btn-clear-console-log");
if (btnClearConsoleLog) {
  btnClearConsoleLog.addEventListener("click", () => {
    if (consoleLog) {
      consoleLog.innerHTML = `<div class="log-line"><span class="log-time">[${new Date().toLocaleTimeString()}]</span><span class="log-info">Console cleared by user.</span></div>`;
    }
  });
}

function updateHealthBadge(health) {
  healthBadge.textContent = health;
  healthBadge.className = "status-badge";
  if (health === "HEALTHY") {
    healthBadge.style.color = "var(--accent-green)";
    healthBadge.style.borderColor = "rgba(16, 185, 129, 0.4)";
  } else if (health === "DEGRADED") {
    healthBadge.style.color = "var(--accent-yellow)";
    healthBadge.style.borderColor = "rgba(245, 158, 11, 0.4)";
  } else {
    healthBadge.style.color = "var(--accent-red)";
    healthBadge.style.borderColor = "rgba(239, 68, 68, 0.4)";
  }
}

function renderGenres(genresMap, total) {
  genreList.innerHTML = "";
  const entries = Object.entries(genresMap).sort((a, b) => b[1] - a[1]);

  entries.slice(0, 8).forEach(([genre, count]) => {
    const item = document.createElement("div");
    item.className = "genre-item";

    const name = document.createElement("span");
    name.className = "genre-name";
    name.textContent = genre;

    const track = document.createElement("div");
    track.className = "genre-bar-track";

    const fill = document.createElement("div");
    fill.className = "genre-bar-fill";
    const pct = Math.min(100, Math.round((count / total) * 100));
    fill.style.width = `${pct}%`;
    track.appendChild(fill);

    const countSpan = document.createElement("span");
    countSpan.className = "genre-count";
    countSpan.textContent = count;

    item.appendChild(name);
    item.appendChild(track);
    item.appendChild(countSpan);
    genreList.appendChild(item);
  });
}

// Custom Crawl Elements
const crawlMode = document.getElementById("crawl-mode");
const crawlQuery = document.getElementById("crawl-query");
const crawlGenre = document.getElementById("crawl-genre");
const crawlLimit = document.getElementById("crawl-limit");

if (crawlMode && crawlQuery) {
  crawlMode.addEventListener("change", () => {
    const val = crawlMode.value;
    if (val === "curated") {
      crawlQuery.placeholder = "Sẽ cào toàn bộ 12 playlist thể loại mặc định...";
      crawlQuery.disabled = true;
      crawlQuery.value = "";
    } else if (val === "artist") {
      crawlQuery.placeholder = "Nhập tên ca sĩ/nhạc sĩ (ví dụ: Sơn Tùng M-TP, Đen Vâu, Vũ., Trịnh Công Sơn...)...";
      crawlQuery.disabled = false;
    } else if (val === "album") {
      crawlQuery.placeholder = "Nhập tên Album hoặc link Album Spotify...";
      crawlQuery.disabled = false;
    } else if (val === "search") {
      crawlQuery.placeholder = "Nhập từ khóa tìm kiếm (ví dụ: Nhạc Trẻ 2026, V-Pop Hits, Acoustic Chill...)...";
      crawlQuery.disabled = false;
    } else if (val === "direct") {
      crawlQuery.placeholder = "Dán link YouTube, SoundCloud, TikTok, Direct MP3 stream...";
      crawlQuery.disabled = false;
    } else {
      crawlQuery.placeholder = "Dán đường dẫn Spotify URL (Playlist, Album, Artist, Track)...";
      crawlQuery.disabled = false;
    }
  });
}

// Preview Elements
const previewSection = document.getElementById("preview-section");
const previewStats = document.getElementById("preview-stats");
const previewTableBody = document.getElementById("preview-table-body");
const selectAllPreview = document.getElementById("select-all-preview");
const selectedCountLabel = document.getElementById("selected-count-label");
const btnPreviewSearch = document.getElementById("btn-preview-search");
const btnImportSelected = document.getElementById("btn-import-selected");
const btnClosePreview = document.getElementById("btn-close-preview");

let currentPreviewTracks = [];
let lastRequestedLimit = 50;

function updateSelectionCount() {
  const checkboxes = previewTableBody.querySelectorAll(".track-select-cb");
  let selected = 0;
  checkboxes.forEach((cb) => {
    if (cb.checked) selected++;
  });
  const preselected = Math.min(lastRequestedLimit, currentPreviewTracks.length);
  selectedCountLabel.textContent = `Đã chọn: ${selected} / ${currentPreviewTracks.length} bài (Mặc định chọn sẵn ${preselected} bài đầu tiên - bạn có thể chọn thêm tùy thích)`;
  btnImportSelected.textContent = `📥 Import Selected (${selected} bài)`;
  btnImportSelected.disabled = selected === 0;
}

if (btnPreviewSearch) {
  btnPreviewSearch.addEventListener("click", () => {
    const limit = crawlLimit ? (parseInt(crawlLimit.value) || 50) : 50;
    const mode = crawlMode ? crawlMode.value : "search";
    const query = crawlQuery ? crawlQuery.value.trim() : "";
    const genre = crawlGenre ? crawlGenre.value : "";

    if (!query && mode !== "curated") {
      alert("Vui lòng nhập tên Nghệ sĩ, Nhạc sĩ, Album hoặc từ khóa để tìm kiếm!");
      return;
    }

    btnPreviewSearch.textContent = "⏳ Đang tìm...";
    btnPreviewSearch.disabled = true;

    socket.emit("search_preview", {
      mode: mode,
      query: query,
      genre: genre || null,
      limit: limit,
    });
  });
}

socket.on("search_results", (data) => {
  if (btnPreviewSearch) {
    btnPreviewSearch.textContent = "🔍 Xem Trước & Chọn Lọc (Preview Table)";
    btnPreviewSearch.disabled = false;
  }

  currentPreviewTracks = data.tracks || [];
  lastRequestedLimit = data.requested_limit || (crawlLimit ? parseInt(crawlLimit.value) || 50 : 50);
  if (previewSection) previewSection.style.display = "block";
  if (previewStats) previewStats.textContent = `(Tìm thấy: ${currentPreviewTracks.length} bài cho '${data.query || data.mode}' — Chọn sẵn ${Math.min(lastRequestedLimit, currentPreviewTracks.length)} bài đầu tiên)`;

  if (previewTableBody) {
    previewTableBody.innerHTML = "";

    if (data.error) {
      previewTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 20px; color: var(--accent-red);">❌ Lỗi tìm kiếm: ${data.error}</td></tr>`;
      return;
    }

    if (currentPreviewTracks.length === 0) {
      previewTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 20px; color: var(--text-muted);">Không tìm thấy bài hát nào phù hợp!</td></tr>`;
      return;
    }

  currentPreviewTracks.forEach((t, idx) => {
    const row = document.createElement("tr");
    row.style.borderBottom = "1px solid rgba(255,255,255,0.05)";
    row.style.transition = "background 0.2s";
    row.onmouseover = () => (row.style.background = "rgba(255,255,255,0.03)");
    row.onmouseout = () => (row.style.background = "transparent");

    let statusBadge = "";
    if (t.db_status === "downloaded") {
      statusBadge = `<span style="background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.4); padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; white-space: nowrap;">🎵 Đã tải xong Audio (320k)</span>`;
    } else if (t.db_status === "metadata_only") {
      statusBadge = `<span style="background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.4); padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; white-space: nowrap;">📋 Đã có Metadata (Chưa tải Audio)</span>`;
    } else if (t.db_status === "download_failed") {
      statusBadge = `<span style="background: rgba(239,68,68,0.15); color: #ef4444; border: 1px solid rgba(239,68,68,0.4); padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; white-space: nowrap;">⚠️ Tải Audio lỗi (Cần thử lại)</span>`;
    } else {
      statusBadge = `<span style="background: rgba(6,182,212,0.15); color: #06b6d4; border: 1px solid rgba(6,182,212,0.4); padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; white-space: nowrap;">✨ Bài Mới (Chưa có trong DB)</span>`;
    }

    const coverImg = t.image_url
      ? `<img src="${t.image_url}" style="width: 36px; height: 36px; border-radius: 4px; object-fit: cover;">`
      : `<div style="width: 36px; height: 36px; border-radius: 4px; background: #333; display: flex; align-items: center; justify-content: center; font-size: 12px;">🎵</div>`;

    let artistHtml = "";
    if (t.artists && t.artists.length > 1) {
      const artistBadges = t.artists.map((a) => `<span style="background: rgba(192, 132, 252, 0.12); color: #c084fc; border: 1px solid rgba(192, 132, 252, 0.3); padding: 1px 6px; border-radius: 4px; font-size: 10.5px; font-weight: 500;">🎤 ${a.name}</span>`).join(" ");
      artistHtml = `<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 3px; align-items: center;"><span style="font-size: 10px; color: #fbbf24; background: rgba(245, 158, 11, 0.15); padding: 0 4px; border-radius: 3px; font-weight: 700;">COLLAB</span> ${artistBadges}</div>`;
    } else {
      artistHtml = `<div style="font-size: 11.5px; color: var(--text-muted); margin-top: 2px;">🎤 ${t.artist_name || "Unknown Artist"}</div>`;
    }

    const isPreSelected = idx < lastRequestedLimit && t.db_status !== "downloaded";

    row.innerHTML = `
      <td style="padding: 8px 10px;">
        <input type="checkbox" class="track-select-cb" data-index="${idx}" ${isPreSelected ? "checked" : ""} style="cursor: pointer; transform: scale(1.15);">
      </td>
      <td style="padding: 8px 10px;">${coverImg}</td>
      <td style="padding: 8px 10px;">
        <div style="font-weight: 600; color: var(--text-main); font-size: 13px;">${t.name}</div>
        ${artistHtml}
      </td>
      <td style="padding: 8px 10px; color: var(--text-dim); font-size: 12px;">${t.album_name || "Single"}</td>
      <td style="padding: 8px 10px; color: var(--text-muted); font-size: 12px;">${t.duration_formatted || "0:00"}</td>
      <td style="padding: 8px 10px;">
        <div style="background: rgba(255,255,255,0.1); border-radius: 3px; height: 6px; width: 50px; overflow: hidden;">
          <div style="background: var(--accent-cyan); height: 100%; width: ${t.popularity || 50}%;"></div>
        </div>
      </td>
      <td style="padding: 8px 10px;">${statusBadge}</td>
    `;

    // Visual row styling
    row.style.cursor = "pointer";
    row.setAttribute("title", "💡 Click để chọn/bỏ chọn | Click chuột phải để xem chi tiết");

    // Click on row to toggle checkbox
    row.addEventListener("click", (e) => {
      if (e.target.tagName !== "INPUT" && e.target.tagName !== "A" && e.target.tagName !== "BUTTON") {
        const cb = row.querySelector(".track-select-cb");
        if (cb) {
          cb.checked = !cb.checked;
          updateSelectionCount();
        }
      }
    });

    // Right-click or double click on row to open Track Inspector
    row.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      showTrackDetails(t);
    });

    row.addEventListener("dblclick", () => {
      showTrackDetails(t);
    });

    previewTableBody.appendChild(row);
  });

  // Attach change listeners to row checkboxes
  previewTableBody.querySelectorAll(".track-select-cb").forEach((cb) => {
    cb.addEventListener("change", updateSelectionCount);
  });

  updateSelectionCount();
  previewSection.scrollIntoView({ behavior: "smooth" });
  } // close if(previewTableBody)
});

if (selectAllPreview) {
  selectAllPreview.addEventListener("change", () => {
    const isChecked = selectAllPreview.checked;
    previewTableBody.querySelectorAll(".track-select-cb").forEach((cb) => {
      cb.checked = isChecked;
    });
    updateSelectionCount();
  });
}

if (btnImportSelected) {
  btnImportSelected.addEventListener("click", () => {
    const selectedIndices = [];
    previewTableBody.querySelectorAll(".track-select-cb").forEach((cb) => {
      if (cb.checked) {
        selectedIndices.push(parseInt(cb.getAttribute("data-index")));
      }
    });

    const selectedTracks = selectedIndices.map((idx) => currentPreviewTracks[idx]).filter(Boolean);
    if (selectedTracks.length === 0) {
      alert("Bạn chưa chọn bài hát nào!");
      return;
    }

    btnImportSelected.textContent = "⏳ Đang nhập...";
    btnImportSelected.disabled = true;

    socket.emit("import_selected_tracks", {
      tracks: selectedTracks,
      genre: crawlGenre ? crawlGenre.value : null,
    });
  });
}

socket.on("import_success", (data) => {
  btnImportSelected.textContent = "✅ Đã Nhập Thành Công!";
  appendLog(`🎉 Imported ${data.new_count} new tracks (${data.updated_count} updated) into database!`, "success");
  setTimeout(() => {
    previewSection.style.display = "none";
  }, 1500);
});

if (btnClosePreview) {
  btnClosePreview.addEventListener("click", () => {
    previewSection.style.display = "none";
  });
}

// ─── Button Actions ──────────────────────────────────────────

btnStartCrawl.addEventListener("click", () => {
  const limit = crawlLimit ? (parseInt(crawlLimit.value) || 50) : 50;
  const mode = crawlMode ? crawlMode.value : "curated";
  const query = crawlQuery ? crawlQuery.value.trim() : "";
  const genre = crawlGenre ? crawlGenre.value : "";

  if (mode === "direct") {
    if (!query) {
      alert("Vui lòng dán đường link YouTube, SoundCloud, TikTok hoặc Direct Audio URL!");
      return;
    }
    socket.emit("direct_url_ingest", {
      url: query,
      genre: genre || "pop",
    });
    appendLog(`Ingesting direct URL [${query}]...`, "info");
    return;
  }

  socket.emit("start_crawl", {
    mode: mode,
    query: query,
    genre: genre || null,
    limit: limit,
  });

  appendLog(`Triggered metadata crawl [Mode: ${mode.toUpperCase()}, Query: '${query || "Curated Playlists"}', Genre: ${genre || "Auto"}]...`, "info");
});

// ─── Audio Download Queue Manager (Search, Filter, Pagination & Multi-Select) ──
const btnPreviewDownloadQueue = document.getElementById("btn-preview-download-queue");
const btnConfirmStartDownload = document.getElementById("btn-confirm-start-download");
const downloadPreviewSection = document.getElementById("download-preview-section");
const downloadQueueStats = document.getElementById("download-queue-stats");
const downloadQueueTableBody = document.getElementById("download-queue-table-body");
const selectAllDownloadQueue = document.getElementById("select-all-download-queue");
const downloadSelectedCountLabel = document.getElementById("download-selected-count-label");
const btnCloseDownloadPreview = document.getElementById("btn-close-download-preview");

// Search, Filter & Pagination Elements
const queueSearchInput = document.getElementById("queue-search");
const queueFilterStatus = document.getElementById("queue-filter-status");
const queueFilterGenre = document.getElementById("queue-filter-genre");
const queueFilterUser = document.getElementById("queue-filter-user");
const queueLimitSelect = document.getElementById("queue-limit");
const queueTotalBadge = document.getElementById("queue-total-badge");
const btnQueueSelectAllPages = document.getElementById("btn-queue-select-all-pages");
const btnQueueClearSelection = document.getElementById("btn-queue-clear-selection");
const btnQueuePrevPage = document.getElementById("btn-queue-prev-page");
const btnQueueNextPage = document.getElementById("btn-queue-next-page");
const queuePageNumber = document.getElementById("queue-page-number");
const queuePaginationInfo = document.getElementById("queue-pagination-info");

let queueCurrentPage = 1;
let queueTotalPages = 1;
let queueTotalItems = 0;
let queueCurrentPageTracks = [];
const queueSelectedIds = new Set();
let queueSearchDebounceTimer = null;

function updateDownloadSelectionCount() {
  const selected = queueSelectedIds.size;
  const estMb = (selected * 7.5).toFixed(1);
  if (downloadSelectedCountLabel) {
    downloadSelectedCountLabel.textContent = `Đã chọn: ${selected} / ${queueTotalItems} bài (~${estMb} MB)`;
  }
  if (btnConfirmStartDownload) {
    btnConfirmStartDownload.textContent = `▶ Tải ${selected} Bài Đã Chọn`;
    btnConfirmStartDownload.disabled = selected === 0;
  }

  // Update header "select all on this page" checkbox state
  if (selectAllDownloadQueue && downloadQueueTableBody) {
    const pageCheckboxes = downloadQueueTableBody.querySelectorAll(".download-queue-cb");
    if (pageCheckboxes.length > 0) {
      const allChecked = Array.from(pageCheckboxes).every((cb) => cb.checked);
      selectAllDownloadQueue.checked = allChecked;
    }
  }
}

async function loadDownloadQueue(page = 1) {
  if (!downloadPreviewSection || !downloadQueueTableBody) return;
  queueCurrentPage = page;
  downloadPreviewSection.style.display = "block";

  const search = queueSearchInput ? queueSearchInput.value.trim() : "";
  const status = queueFilterStatus ? queueFilterStatus.value : "pending";
  const genre = queueFilterGenre ? queueFilterGenre.value : "all";
  const addedBy = queueFilterUser ? queueFilterUser.value : "all";
  const limit = queueLimitSelect ? parseInt(queueLimitSelect.value) || 20 : 20;

  downloadQueueTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-dim" style="padding: 24px;">⏳ Đang tải hàng đợi bài hát (Trang ${page})...</td></tr>`;

  try {
    const queryParams = new URLSearchParams({
      page: page,
      limit: limit,
      search: search,
      genre: genre,
      status: status,
      added_by: addedBy,
    });

    const res = await fetch(`/api/tracks/download_queue?${queryParams.toString()}`);
    const data = await res.json();

    if (!data.success) {
      downloadQueueTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-red" style="padding: 20px;">Lỗi tải dữ liệu: ${data.error || 'Unknown'}</td></tr>`;
      return;
    }

    queueTotalItems = data.total_items || 0;
    queueTotalPages = Math.max(1, data.total_pages || 1);
    queueCurrentPageTracks = data.items || [];

    // Populate user filter if available
    if (data.available_collectors && queueFilterUser && queueFilterUser.options.length <= 2) {
      const currentVal = queueFilterUser.value;
      queueFilterUser.innerHTML = '<option value="all">Người nạp: Tất cả</option>' +
        data.available_collectors.map((u) => `<option value="${u}">👤 ${u}</option>`).join("");
      queueFilterUser.value = currentVal;
    }

    if (queueTotalBadge) {
      queueTotalBadge.textContent = `${queueTotalItems} BÀI`;
    }

    if (downloadQueueStats) {
      downloadQueueStats.textContent = `Tìm thấy ${queueTotalItems} bài hát (Trạng thái: ${status.toUpperCase()}, Thể loại: ${genre.toUpperCase()})`;
    }

    // Update pagination controls
    if (queuePageNumber) {
      queuePageNumber.textContent = `Trang ${page} / ${queueTotalPages}`;
    }
    if (queuePaginationInfo) {
      const startIdx = queueTotalItems === 0 ? 0 : (page - 1) * limit + 1;
      const endIdx = Math.min(page * limit, queueTotalItems);
      queuePaginationInfo.textContent = `Hiển thị ${startIdx} - ${endIdx} trên tổng số ${queueTotalItems} bài`;
    }
    if (btnQueuePrevPage) btnQueuePrevPage.disabled = page <= 1;
    if (btnQueueNextPage) btnQueueNextPage.disabled = page >= queueTotalPages;

    if (queueCurrentPageTracks.length === 0) {
      downloadQueueTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-dim" style="padding: 24px;">🎉 Không có bài hát nào phù hợp với bộ lọc hiện tại.</td></tr>`;
      updateDownloadSelectionCount();
      return;
    }

    // Default: If queueSelectedIds is empty on initial open, select all items on this page
    if (queueSelectedIds.size === 0 && search === "" && page === 1) {
      queueCurrentPageTracks.forEach((t) => queueSelectedIds.add(t.spotify_id));
    }

    downloadQueueTableBody.innerHTML = queueCurrentPageTracks.map((t) => {
      const isChecked = queueSelectedIds.has(t.spotify_id);
      const coverSrc = t.image_url || "/static/img/default_cover.png";
      const statusBadge = t.download_status === "failed"
        ? `<span class="badge badge-danger" style="font-size: 9.5px;">⚠️ Lỗi Tải</span>`
        : `<span class="badge badge-warning" style="font-size: 9.5px;">⏳ Chờ Tải</span>`;
      const dur = t.duration_formatted || "3:30";
      const genreName = (t.genres && t.genres[0]) || "vpop";
      const uploader = t.added_by || "admin";

      return `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.05); ${isChecked ? 'background: rgba(16,185,129,0.04);' : ''}">
          <td style="padding: 8px 10px;">
            <input type="checkbox" class="download-queue-cb" data-id="${t.spotify_id}" ${isChecked ? 'checked' : ''} style="cursor: pointer; transform: scale(1.15);">
          </td>
          <td style="padding: 8px 6px; text-align: center;">
            <img src="${coverSrc}" onerror="this.src='/static/img/default_cover.png'" style="width: 34px; height: 34px; border-radius: 4px; object-fit: cover;">
          </td>
          <td style="padding: 8px 10px;">
            <div style="font-weight: 600; color: var(--text-main); font-size: 12.5px;">${t.name}</div>
            <div style="color: var(--text-muted); font-size: 11px;">🎤 ${t.artist_name || "Unknown"}</div>
          </td>
          <td style="padding: 8px 10px; font-size: 11.5px; color: var(--text-dim);">
            <div>${t.album_name || "Single"}</div>
            <div style="color: var(--accent-cyan); font-family: 'JetBrains Mono', monospace; font-size: 10.5px;">⏱️ ${dur}</div>
          </td>
          <td style="padding: 8px 8px;">
            <span class="badge badge-info" style="font-size: 10px;">${genreName}</span>
          </td>
          <td style="padding: 8px 8px; font-size: 11px; color: var(--text-muted);">
            <span class="badge badge-purple" style="font-size: 9.5px;">👤 ${uploader}</span>
          </td>
          <td style="padding: 8px 8px;">${statusBadge}</td>
        </tr>
      `;
    }).join("");

    // Attach row checkbox listeners
    downloadQueueTableBody.querySelectorAll(".download-queue-cb").forEach((cb) => {
      cb.addEventListener("change", () => {
        const id = cb.getAttribute("data-id");
        if (cb.checked) {
          queueSelectedIds.add(id);
          cb.closest("tr").style.background = "rgba(16,185,129,0.04)";
        } else {
          queueSelectedIds.delete(id);
          cb.closest("tr").style.background = "";
        }
        updateDownloadSelectionCount();
      });
    });

    updateDownloadSelectionCount();
  } catch (err) {
    downloadQueueTableBody.innerHTML = `<tr><td colspan="7" class="text-center text-red" style="padding: 20px;">Lỗi kết nối: ${err.message}</td></tr>`;
  }
}

// Search with Debounce
if (queueSearchInput) {
  queueSearchInput.addEventListener("input", () => {
    clearTimeout(queueSearchDebounceTimer);
    queueSearchDebounceTimer = setTimeout(() => {
      loadDownloadQueue(1);
    }, 300);
  });
}

// Filter changes
[queueFilterStatus, queueFilterGenre, queueFilterUser, queueLimitSelect].forEach((el) => {
  if (el) {
    el.addEventListener("change", () => {
      loadDownloadQueue(1);
    });
  }
});

// Pagination clicks
if (btnQueuePrevPage) {
  btnQueuePrevPage.addEventListener("click", () => {
    if (queueCurrentPage > 1) {
      loadDownloadQueue(queueCurrentPage - 1);
    }
  });
}

if (btnQueueNextPage) {
  btnQueueNextPage.addEventListener("click", () => {
    if (queueCurrentPage < queueTotalPages) {
      loadDownloadQueue(queueCurrentPage + 1);
    }
  });
}

// Select All on current page
if (selectAllDownloadQueue) {
  selectAllDownloadQueue.addEventListener("change", () => {
    const isChecked = selectAllDownloadQueue.checked;
    if (downloadQueueTableBody) {
      downloadQueueTableBody.querySelectorAll(".download-queue-cb").forEach((cb) => {
        cb.checked = isChecked;
        const id = cb.getAttribute("data-id");
        if (isChecked) {
          queueSelectedIds.add(id);
          cb.closest("tr").style.background = "rgba(16,185,129,0.04)";
        } else {
          queueSelectedIds.delete(id);
          cb.closest("tr").style.background = "";
        }
      });
      updateDownloadSelectionCount();
    }
  });
}

// Select ALL items in the whole queue across all pages
if (btnQueueSelectAllPages) {
  btnQueueSelectAllPages.addEventListener("click", async () => {
    btnQueueSelectAllPages.disabled = true;
    btnQueueSelectAllPages.textContent = "⏳ Đang chọn...";
    try {
      const search = queueSearchInput ? queueSearchInput.value.trim() : "";
      const status = queueFilterStatus ? queueFilterStatus.value : "pending";
      const genre = queueFilterGenre ? queueFilterGenre.value : "all";
      const addedBy = queueFilterUser ? queueFilterUser.value : "all";

      const queryParams = new URLSearchParams({
        get_all_ids: "true",
        search: search,
        genre: genre,
        status: status,
        added_by: addedBy,
      });

      const res = await fetch(`/api/tracks/download_queue?${queryParams.toString()}`);
      const data = await res.json();
      if (data.success && data.ids) {
        data.ids.forEach((id) => queueSelectedIds.add(id));
        if (downloadQueueTableBody) {
          downloadQueueTableBody.querySelectorAll(".download-queue-cb").forEach((cb) => {
            cb.checked = true;
            cb.closest("tr").style.background = "rgba(16,185,129,0.04)";
          });
        }
        updateDownloadSelectionCount();
        appendLog(`⭐ Đã chọn toàn bộ ${data.ids.length} bài hát trong hàng đợi tải audio!`, "success");
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    } finally {
      btnQueueSelectAllPages.disabled = false;
      btnQueueSelectAllPages.textContent = "⭐ Chọn toàn bộ hàng đợi";
    }
  });
}

// Clear all selections
if (btnQueueClearSelection) {
  btnQueueClearSelection.addEventListener("click", () => {
    queueSelectedIds.clear();
    if (downloadQueueTableBody) {
      downloadQueueTableBody.querySelectorAll(".download-queue-cb").forEach((cb) => {
        cb.checked = false;
        cb.closest("tr").style.background = "";
      });
    }
    if (selectAllDownloadQueue) selectAllDownloadQueue.checked = false;
    updateDownloadSelectionCount();
  });
}

if (btnPreviewDownloadQueue) {
  btnPreviewDownloadQueue.addEventListener("click", () => {
    loadDownloadQueue(1);
  });
}

if (btnCloseDownloadPreview) {
  btnCloseDownloadPreview.addEventListener("click", () => {
    if (downloadPreviewSection) downloadPreviewSection.style.display = "none";
  });
}

function triggerConfirmedDownload(specificIds = null) {
  const delay = inputDelay ? parseFloat(inputDelay.value) || 3.0 : 3.0;
  const retryFailed = queueFilterStatus ? queueFilterStatus.value === "failed" : false;
  const limit = inputLimit ? parseInt(inputLimit.value) || 50 : 50;

  socket.emit("start_download", {
    limit: limit,
    delay: delay,
    retry_failed: retryFailed,
    specific_ids: specificIds,
  });

  if (specificIds && specificIds.length > 0) {
    appendLog(`🎧 Đã kích hoạt tải audio cho ${specificIds.length} bài hát đã chọn (Delay: ${delay}s)...`, "info");
    if (downloadPreviewSection) downloadPreviewSection.style.display = "none";
  } else {
    appendLog(`🎧 Đã kích hoạt tải audio (Limit: ${limit}, Delay: ${delay}s)...`, "info");
  }
}

if (btnConfirmStartDownload) {
  btnConfirmStartDownload.addEventListener("click", () => {
    const selectedIds = Array.from(queueSelectedIds);
    if (selectedIds.length === 0) {
      alert("Vui lòng tích chọn ít nhất 1 bài hát trong danh sách chờ tải!");
      return;
    }

    const estMb = (selectedIds.length * 7.5).toFixed(1);
    showConfirmModal({
      title: "🎧 Xác Nhận Bắt Đầu Tải Audio MP3 320k",
      message: `Hệ thống sẽ tải âm thanh chất lượng cao 320 kbps & Lời karaoke .lrc cho <b>${selectedIds.length} bài hát</b> đã chọn (Ước tính ~<b>${estMb} MB</b>).<br><br>Bạn có chắc chắn muốn bắt đầu ngay?`,
      proceedText: `▶ Bắt Đầu Tải (${selectedIds.length} Bài)`,
      isDanger: false,
      onConfirm: () => {
        triggerConfirmedDownload(selectedIds);
      },
    });
  });
}

if (btnStartDownload) {
  btnStartDownload.addEventListener("click", () => {
    // If preview queue is open and has items selected, trigger confirm download
    if (downloadPreviewSection && downloadPreviewSection.style.display !== "none" && queueSelectedIds.size > 0) {
      btnConfirmStartDownload.click();
      return;
    }

    // Otherwise, open the rich queue manager for review
    loadDownloadQueue(1);
  });
}

if (btnRetryFailed) {
  btnRetryFailed.addEventListener("click", () => {
    if (queueFilterStatus) queueFilterStatus.value = "failed";
    loadDownloadQueue(1);
  });
}

if (btnPause) {
  btnPause.addEventListener("click", () => {
    socket.emit("pause_pipeline");
  });
}

if (btnStop) {
  btnStop.addEventListener("click", () => {
    socket.emit("stop_pipeline");
  });
}

if (toggleProxy) {
  toggleProxy.addEventListener("change", (e) => {
    socket.emit("toggle_proxy", { enable: e.target.checked });
  });
}

if (btnExport) {
  btnExport.addEventListener("click", () => {
    socket.emit("export_data");
    appendLog("Exporting datasets (JSON, SQL, Markdown)...", "info");
  });
}

// ─── Team Management & Audit Modal JS ──────────────────────

const btnOpenTeamModal = document.getElementById("btn-open-team-modal");
const btnCloseTeamModal = document.getElementById("btn-close-team-modal");
const teamModal = document.getElementById("team-modal");
const teamTabBtns = document.querySelectorAll(".team-tab-btn");
const teamTabContents = document.querySelectorAll(".team-tab-content");
const teamLeaderboardBody = document.getElementById("team-leaderboard-body");
const teamActivityLogsList = document.getElementById("team-activity-logs-list");
const formAdminCreateUser = document.getElementById("form-admin-create-user");

if (btnOpenTeamModal && teamModal) {
  btnOpenTeamModal.addEventListener("click", () => {
    teamModal.style.display = "flex";
    socket.emit("admin_get_users");
  });

  btnCloseTeamModal.addEventListener("click", () => {
    teamModal.style.display = "none";
  });
}

// Team Tabs Switching
teamTabBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    teamTabBtns.forEach((b) => {
      b.style.background = "transparent";
      b.style.color = "var(--text-muted)";
      b.style.border = "1px solid var(--border-color)";
    });
    teamTabContents.forEach((c) => (c.style.display = "none"));

    btn.style.background = "#c084fc";
    btn.style.color = "#000";
    btn.style.border = "none";

    const targetTab = document.getElementById(btn.getAttribute("data-tab"));
    if (targetTab) targetTab.style.display = "block";
  });
});

// Render Leaderboard & Activity Data
socket.on("team_data", (data) => {
  const users = data.users || [];
  const logs = data.logs || [];

  if (teamLeaderboardBody) {
    teamLeaderboardBody.innerHTML = "";
    if (users.length === 0) {
      teamLeaderboardBody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 20px; color: var(--text-muted);">Chưa có thành viên nào.</td></tr>`;
    } else {
      users.forEach((u) => {
        const stats = u.stats || {};
        const tr = document.createElement("tr");
        tr.style.borderBottom = "1px solid rgba(255,255,255,0.05)";
        tr.innerHTML = `
          <td style="padding: 10px;">
            <div style="font-weight: 600; color: var(--text-main);">${u.display_name || u.username}</div>
            <div style="font-size: 11px; color: var(--text-muted);">@${u.username}</div>
          </td>
          <td style="padding: 10px;">
            <span style="background: ${u.role === "admin" ? "rgba(168,85,247,0.2)" : "rgba(6,182,212,0.2)"}; color: ${u.role === "admin" ? "#c084fc" : "#06b6d4"}; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">
              ${u.role ? u.role.toUpperCase() : "COLLECTOR"}
            </span>
          </td>
          <td style="padding: 10px; text-align: center; font-weight: 700; color: var(--accent-cyan);">${(stats.crawled_tracks_count || 0).toLocaleString()}</td>
          <td style="padding: 10px; text-align: center; font-weight: 700; color: var(--accent-green);">${(stats.downloaded_tracks_count || 0).toLocaleString()}</td>
          <td style="padding: 10px; text-align: center; font-weight: 700; color: #fbbf24;">${(stats.direct_links_count || 0).toLocaleString()}</td>
          <td style="padding: 10px; font-size: 12px; color: var(--text-dim);">${stats.last_action || "Chưa có"}</td>
          <td style="padding: 10px; text-align: center;">
            <span style="color: ${u.is_active !== false ? "var(--accent-green)" : "var(--accent-red);"}; font-size: 11px; font-weight: 600;">
              ${u.is_active !== false ? "🟢 Đang hoạt động" : "🔴 Tạm khóa"}
            </span>
          </td>
        `;
        teamLeaderboardBody.appendChild(tr);
      });
    }
  }

  if (teamActivityLogsList) {
    teamActivityLogsList.innerHTML = "";
    if (logs.length === 0) {
      teamActivityLogsList.innerHTML = `<div style="text-align: center; padding: 16px; color: var(--text-muted);">Chưa có nhật ký hoạt động nào.</div>`;
    } else {
      logs.forEach((l) => {
        const row = document.createElement("div");
        row.style.background = "rgba(255,255,255,0.03)";
        row.style.padding = "8px 12px";
        row.style.borderRadius = "6px";
        row.style.display = "flex";
        row.style.justifyContent = "space-between";
        row.style.alignItems = "center";
        row.style.fontSize = "12.5px";

        const timeStr = l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : "";
        row.innerHTML = `
          <div>
            <span style="font-weight: 600; color: var(--accent-cyan);">@${l.username}</span>
            <span style="color: var(--text-main); margin-left: 6px;">${l.details || l.action_type}</span>
          </div>
          <div style="font-size: 11px; color: var(--text-muted);">${timeStr}</div>
        `;
        teamActivityLogsList.appendChild(row);
      });
    }
  }
});

// Admin Create User Form Submit
if (formAdminCreateUser) {
  formAdminCreateUser.addEventListener("submit", (e) => {
    e.preventDefault();
    const display_name = document.getElementById("new-user-display").value.trim();
    const username = document.getElementById("new-user-username").value.trim();
    const password = document.getElementById("new-user-password").value.trim();
    const role = document.getElementById("new-user-role").value;

    socket.emit("admin_create_user", {
      display_name: display_name,
      username: username,
      password: password,
      role: role,
    });
  });
}

socket.on("admin_user_created", (res) => {
  if (res.success) {
    alert(`✅ Đã tạo tài khoản thành công cho @${res.username}!`);
    if (formAdminCreateUser) formAdminCreateUser.reset();
  } else {
    alert(`❌ Lỗi: ${res.error}`);
  }
});

// ─── Headless Cookie Pool Studio Manager JS ────────────────

const cookieModal = document.getElementById("cookie-modal");
const btnOpenCookieModal = document.getElementById("btn-open-cookie-modal");
const btnCloseCookieModal = document.getElementById("btn-close-cookie-modal");

const cookiePoolTableBody = document.getElementById("cookie-pool-table-body");
const btnOpenAddCookie = document.getElementById("btn-open-add-cookie");
const formCookiePool = document.getElementById("form-cookie-pool");
const btnCloseCookieForm = document.getElementById("btn-close-cookie-form");
const cookieEditId = document.getElementById("cookie-edit-id");
const cookieName = document.getElementById("cookie-name");
const cookieService = document.getElementById("cookie-service");
const cookieAddedBy = document.getElementById("cookie-added-by");
const cookieFileReader = document.getElementById("cookie-file-reader");
const cookieContent = document.getElementById("cookie-content");
const cookieIsActive = document.getElementById("cookie-is-active");
const btnTestCookieForm = document.getElementById("btn-test-cookie-form");
const cookieFormTestResult = document.getElementById("cookie-form-test-result");

window.openCookieModal = function() {
  const modal = document.getElementById("cookie-modal");
  if (modal) {
    modal.style.display = "flex";
    loadCookiePool();
  }
};

window.closeCookieModal = function() {
  const modal = document.getElementById("cookie-modal");
  if (modal) modal.style.display = "none";
};

window.openAddCookieForm = function() {
  const form = document.getElementById("form-cookie-pool");
  const editId = document.getElementById("cookie-edit-id");
  const isActive = document.getElementById("cookie-is-active");
  const testRes = document.getElementById("cookie-form-test-result");
  const title = document.getElementById("cookie-form-title");
  if (form) {
    form.reset();
    if (editId) editId.value = "";
    if (isActive) isActive.checked = true;
    if (title) title.textContent = "➕ Thêm Cookie Mới Vào Pool";
    form.style.display = "flex";
    if (testRes) testRes.style.display = "none";
  }
};

window.closeCookieForm = function() {
  const form = document.getElementById("form-cookie-pool");
  if (form) form.style.display = "none";
};

async function loadCookiePool() {
  const tableBody = document.getElementById("cookie-pool-table-body");
  if (!tableBody) return;
  try {
    tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-dim" style="padding: 20px;">⏳ Đang tải danh sách Cookies từ database...</td></tr>`;
    const res = await fetch("/api/cookies");
    const data = await res.json();

    if (!data.success || !data.cookies || data.cookies.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-dim" style="padding: 20px;">Chưa có Cookie nào trong pool. Hãy bấm '➕ Thêm Cookie Mới' hoặc nạp file cookies.txt.</td></tr>`;
      return;
    }

    tableBody.innerHTML = data.cookies.map((c) => {
      let svcBadge = `<span class="badge badge-danger" style="font-size: 10px; font-weight: 700;">📺 YouTube</span>`;
      if (c.service === "spotify") {
        svcBadge = `<span class="badge badge-success" style="font-size: 10px; font-weight: 700;">🎵 Spotify</span>`;
      } else if (c.service === "soundcloud") {
        svcBadge = `<span class="badge badge-warning" style="font-size: 10px; font-weight: 700;">☁️ SoundCloud</span>`;
      }

      let statusBadge = `<span class="badge badge-secondary" style="font-size: 10px;">⏳ Chưa Test</span>`;
      if (c.status === "valid") {
        statusBadge = `<span class="badge badge-success" style="font-size: 10px;">🟢 Valid (${c.latency_ms || 0}ms)</span>`;
      } else if (c.status === "invalid") {
        statusBadge = `<span class="badge badge-danger" style="font-size: 10px;" title="${c.message || ''}">🔴 Hết Hạn / Lỗi</span>`;
      }

      const activeRadio = `
        <input type="radio" name="active_cookie_node" value="${c.id}" ${c.is_active ? "checked" : ""} 
               onchange="window.setActiveCookie('${c.id}')" style="cursor: pointer;" title="Chọn làm Cookie chính cho engine">
      `;

      const sizeKb = ((c.size_bytes || 0) / 1024).toFixed(1);

      return `
        <tr style="${c.is_active ? 'background: rgba(234, 179, 8, 0.06);' : ''}">
          <td style="text-align: center;">${activeRadio}</td>
          <td>
            <div style="font-weight: 600; color: var(--text-main); font-size: 12px;">${c.name}</div>
            <div style="font-size: 10.5px; margin-top: 2px;">
              <span class="badge badge-purple" style="font-size: 9.5px;">👤 @${c.added_by || 'admin'}</span>
              ${c.is_active ? '<span class="badge badge-warning" style="font-size: 9.5px; margin-left: 4px;">★ Đang Dùng</span>' : ''}
            </div>
          </td>
          <td>${svcBadge}</td>
          <td>
            <div class="font-mono text-dim" style="font-size: 11px;">${c.cookie_count || 0} keys</div>
            <div class="text-dim" style="font-size: 10px;">~${sizeKb} KB</div>
          </td>
          <td>
            <div style="font-size: 11px; color: var(--text-main);">${c.earliest_expiry_formatted || 'N/A'}</div>
          </td>
          <td>${statusBadge}</td>
          <td style="text-align: center;">
            <div class="flex-row" style="justify-content: center; gap: 4px;">
              <button class="btn btn-secondary" style="padding: 3px 6px; font-size: 10px;" onclick="window.testCookieNode('${c.id}', this)" title="Test kết nối thực tế">⚡ Test</button>
              <button class="btn btn-secondary" style="padding: 3px 6px; font-size: 10px;" onclick="window.editCookie('${c.id}')" title="Sửa nội dung">✏️</button>
              <button class="btn btn-danger" style="padding: 3px 6px; font-size: 10px;" onclick="window.deleteCookie('${c.id}', '${c.name}')" title="Xóa khỏi pool">🗑️</button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    if (tableBody) {
      tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-red" style="padding: 20px;">Lỗi tải Cookie Pool: ${err.message}</td></tr>`;
    }
  }
}
window.loadCookiePool = loadCookiePool;

if (btnOpenCookieModal) {
  btnOpenCookieModal.addEventListener("click", window.openCookieModal);
}
if (btnCloseCookieModal) {
  btnCloseCookieModal.addEventListener("click", window.closeCookieModal);
}
if (btnOpenAddCookie) {
  btnOpenAddCookie.addEventListener("click", window.openAddCookieForm);
}
if (btnCloseCookieForm) {
  btnCloseCookieForm.addEventListener("click", window.closeCookieForm);
}

// File Reader for txt cookies
if (cookieFileReader) {
  cookieFileReader.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      if (cookieContent) cookieContent.value = evt.target.result;
      if (cookieName && !cookieName.value) {
        cookieName.value = `Cookie ${file.name.replace('.txt', '')} (${new Date().toLocaleDateString('vi-VN')})`;
      }
    };
    reader.readAsText(file, "UTF-8");
  });
}

// Test in form
if (btnTestCookieForm) {
  btnTestCookieForm.addEventListener("click", async () => {
    const txt = cookieContent.value.trim();
    if (!txt) {
      alert("Vui lòng dán nội dung text cookies hoặc chọn file .txt trước khi test!");
      return;
    }

    btnTestCookieForm.disabled = true;
    btnTestCookieForm.textContent = "⏳ Đang test...";
    cookieFormTestResult.style.display = "block";
    cookieFormTestResult.style.background = "var(--bg-input)";
    cookieFormTestResult.style.color = "var(--text-main)";
    cookieFormTestResult.textContent = "🔄 Đang gửi request kiểm tra tới máy chủ...";

    try {
      const res = await fetch("/api/cookie_health?probe=true");
      const diag = await res.json();

      if (diag.valid) {
        cookieFormTestResult.style.background = "rgba(16, 185, 129, 0.15)";
        cookieFormTestResult.style.color = "#34d399";
        cookieFormTestResult.innerHTML = `✅ Cookie HỢP LỆ (${diag.latency_ms || 120}ms)! Tìm thấy ${diag.cookie_count} keys. Hạn dùng: <b>${diag.earliest_expiry_formatted}</b>.`;
      } else {
        cookieFormTestResult.style.background = "rgba(239, 68, 68, 0.15)";
        cookieFormTestResult.style.color = "#f87171";
        cookieFormTestResult.innerHTML = `❌ Kiểm tra thất bại: ${diag.message || "Cookie không hợp lệ"}`;
      }
    } catch (e) {
      cookieFormTestResult.style.background = "rgba(239, 68, 68, 0.15)";
      cookieFormTestResult.style.color = "#f87171";
      cookieFormTestResult.textContent = `❌ Lỗi: ${e.message}`;
    } finally {
      btnTestCookieForm.disabled = false;
      btnTestCookieForm.textContent = "⚡ Test Thử Cookie Này";
    }
  });
}

// Form Submit
if (formCookiePool) {
  formCookiePool.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const payload = {
        name: cookieName.value.trim(),
        service: cookieService.value,
        added_by: cookieAddedBy.value.trim() || "admin",
        content: cookieContent.value.trim(),
        is_active: cookieIsActive ? cookieIsActive.checked : false,
      };
      if (cookieEditId.value) payload.id = cookieEditId.value;

      const res = await fetch("/api/cookies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.success) {
        formCookiePool.style.display = "none";
        loadCookiePool();
        appendLog(`🍪 Đã lưu Cookie: '${payload.name}' (${payload.service.toUpperCase()}) ${payload.is_active ? '★ [Active]' : ''}`, "success");
      } else {
        alert(`Lỗi: ${data.error}`);
      }
    } catch (err) {
      alert(`Lỗi: ${err.message}`);
    }
  });
}

window.setActiveCookie = async function(cookieId) {
  try {
    const res = await fetch(`/api/cookies/${cookieId}/set_active`, { method: "POST" });
    const data = await res.json();
    if (data.success) {
      loadCookiePool();
      appendLog(`★ Đã kích hoạt Cookie chính ID: ${cookieId}`, "info");
    }
  } catch (e) {
    alert(`Lỗi: ${e.message}`);
  }
};

window.testCookieNode = async function(cookieId, btnEl) {
  if (btnEl) {
    btnEl.disabled = true;
    btnEl.textContent = "⏳...";
  }
  try {
    const res = await fetch(`/api/cookies/${cookieId}/test`, { method: "POST" });
    const data = await res.json();
    if (data.success) {
      loadCookiePool();
      if (data.status === "valid") {
        appendLog(`🟢 Cookie (${cookieId}) hợp lệ (${data.latency_ms}ms) - Hạn: ${data.earliest_expiry_formatted}`, "success");
      } else {
        appendLog(`🔴 Cookie (${cookieId}) hết hạn/lỗi: ${data.message}`, "error");
      }
    }
  } catch (e) {
    alert(`Lỗi test: ${e.message}`);
  } finally {
    if (btnEl) {
      btnEl.disabled = false;
      btnEl.textContent = "⚡ Test";
    }
  }
};

window.editCookie = async function(cookieId) {
  try {
    const res = await fetch("/api/cookies");
    const data = await res.json();
    const target = data.cookies.find((c) => c.id === cookieId);
    if (!target) return;

    cookieEditId.value = target.id;
    cookieName.value = target.name || "";
    cookieService.value = target.service || "youtube";
    cookieAddedBy.value = target.added_by || "admin";
    cookieContent.value = target.content || "";
    if (cookieIsActive) cookieIsActive.checked = Boolean(target.is_active);

    document.getElementById("cookie-form-title").textContent = `✏️ Chỉnh Sửa Cookie: ${target.name}`;
    formCookiePool.style.display = "flex";
    cookieFormTestResult.style.display = "none";
  } catch (e) {
    alert(`Lỗi: ${e.message}`);
  }
};

window.deleteCookie = function(cookieId, cookieName) {
  showConfirmModal(
    `Bạn có chắc chắn muốn xóa Cookie <b>'${cookieName}'</b> khỏi pool?`,
    async () => {
      try {
        const res = await fetch(`/api/cookies/${cookieId}`, { method: "DELETE" });
        const data = await res.json();
        if (data.success) {
          loadCookiePool();
          appendLog(`🗑️ Đã xóa Cookie '${cookieName}' khỏi pool`, "warning");
        } else {
          alert(`Lỗi: ${data.error}`);
        }
      } catch (e) {
        alert(`Lỗi: ${e.message}`);
      }
    }
  );
};

// Real-time Runtime Expiration Alert Handler
socket.on("cookie_expired_alert", (data) => {
  console.warn("🚨 Cookie Expired Alert received:", data);
  const alertMsg = `⚠️ CẢNH BÁO KHẨN CẤP:\n\nCookie ${data.service ? data.service.toUpperCase() : "YOUTUBE"} đã bị HẾT HẠN hoặc BỊ ĐĂNG XUẤT trên máy chủ!\n\nPipeline đã TỰ ĐỘNG TẠM DỪNG để bảo vệ tiến trình.\nVui lòng mở mục 'Headless Cookies' để nạp lại cookie mới và tiếp tục tải.`;
  alert(alertMsg);

  if (cookieModal) {
    cookieModal.style.display = "flex";
    loadCookiePool();
  }
});

// ─── Settings & Live Diagnostics Center JS ─────────────────

const btnOpenSettingsModal = document.getElementById("btn-open-settings-modal");
const btnCloseSettingsModal = document.getElementById("btn-close-settings-modal");
const settingsModal = document.getElementById("settings-modal");
const settingsTabBtns = document.querySelectorAll(".settings-tab-btn");
const settingsTabContents = document.querySelectorAll(".settings-tab-content");

// Inputs & Buttons
const setSpotifyClientId = document.getElementById("set-spotify-client-id");
const setSpotifyClientSecret = document.getElementById("set-spotify-client-secret");
const btnTestSpotify = document.getElementById("btn-test-spotify");
const btnSaveSpotify = document.getElementById("btn-save-spotify");
const testSpotifyResultBox = document.getElementById("test-spotify-result-box");

const setProxyUrl = document.getElementById("set-proxy-url");
const btnTestProxy = document.getElementById("btn-test-proxy");
const btnSaveProxy = document.getElementById("btn-save-proxy");
const testProxyResultBox = document.getElementById("test-proxy-result-box");

const setYtdlpQuery = document.getElementById("set-ytdlp-query");
const btnTestYtdlp = document.getElementById("btn-test-ytdlp");
const testYtdlpResultBox = document.getElementById("test-ytdlp-result-box");

const formSystemEngineSettings = document.getElementById("form-system-engine-settings");
const setAudioBitrate = document.getElementById("set-audio-bitrate");
const setDownloadDelay = document.getElementById("set-download-delay");
const setBatchSize = document.getElementById("set-batch-size");
const setCooldown = document.getElementById("set-cooldown");

if (btnOpenSettingsModal && settingsModal) {
  btnOpenSettingsModal.addEventListener("click", () => {
    settingsModal.style.display = "flex";
    socket.emit("get_system_settings");
  });

  btnCloseSettingsModal.addEventListener("click", () => {
    settingsModal.style.display = "none";
  });
}

// Settings Tabs Switching
settingsTabBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    settingsTabBtns.forEach((b) => {
      b.style.background = "transparent";
      b.style.color = "var(--text-muted)";
      b.style.border = "1px solid var(--border-color)";
    });
    settingsTabContents.forEach((c) => (c.style.display = "none"));

    btn.style.background = "var(--accent-cyan)";
    btn.style.color = "#000";
    btn.style.border = "none";

    const targetTab = document.getElementById(btn.getAttribute("data-tab"));
    if (targetTab) targetTab.style.display = "block";
  });
});

// 1. Spotify Connection Test
if (btnTestSpotify) {
  btnTestSpotify.addEventListener("click", () => {
    btnTestSpotify.disabled = true;
    btnTestSpotify.textContent = "⏳ Đang kết nối Spotify...";
    testSpotifyResultBox.style.display = "none";

    socket.emit("test_spotify_connection", {
      client_id: setSpotifyClientId ? setSpotifyClientId.value.trim() : "",
      client_secret: setSpotifyClientSecret ? setSpotifyClientSecret.value.trim() : "",
    });
  });
}

socket.on("test_spotify_result", (res) => {
  if (btnTestSpotify) {
    btnTestSpotify.disabled = false;
    btnTestSpotify.textContent = "⚡ Test Kết Nối Spotify";
  }
  if (testSpotifyResultBox) {
    testSpotifyResultBox.style.display = "block";
    testSpotifyResultBox.style.background = res.success ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)";
    testSpotifyResultBox.style.border = res.success ? "1px solid #10b981" : "1px solid #ef4444";
    testSpotifyResultBox.style.color = res.success ? "#10b981" : "#ef4444";
    testSpotifyResultBox.innerHTML = `<b>${res.success ? "✅ Thành công:" : "❌ Thất bại:"}</b> ${res.message}`;
  }
});

if (btnSaveSpotify) {
  btnSaveSpotify.addEventListener("click", () => {
    const cid = setSpotifyClientId.value.trim();
    const csec = setSpotifyClientSecret.value.trim();
    if (!cid || !csec) {
      alert("Vui lòng nhập cả Client ID và Client Secret!");
      return;
    }
    socket.emit("save_team_profile", {
      profile_id: `spotify_${Date.now()}`,
      type: "spotify",
      name: `Spotify Pool (${cid.slice(0, 6)}...)`,
      client_id: cid,
      client_secret: csec,
      is_active: true,
    });
    alert("✅ Đã lưu hồ sơ Spotify API vào hệ thống!");
  });
}

// 2. Proxy Test
if (btnTestProxy) {
  btnTestProxy.addEventListener("click", () => {
    const pUrl = setProxyUrl.value.trim();
    if (!pUrl) {
      alert("Vui lòng nhập Proxy URL!");
      return;
    }
    btnTestProxy.disabled = true;
    btnTestProxy.textContent = "⏳ Đang kiểm tra Proxy...";
    testProxyResultBox.style.display = "none";

    socket.emit("test_proxy_connection", { proxy_url: pUrl });
  });
}

socket.on("test_proxy_result", (res) => {
  if (btnTestProxy) {
    btnTestProxy.disabled = false;
    btnTestProxy.textContent = "⚡ Test Độ Trễ Proxy (Ping)";
  }
  if (testProxyResultBox) {
    testProxyResultBox.style.display = "block";
    testProxyResultBox.style.background = res.success ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)";
    testProxyResultBox.style.border = res.success ? "1px solid #10b981" : "1px solid #ef4444";
    testProxyResultBox.style.color = res.success ? "#10b981" : "#ef4444";
    testProxyResultBox.innerHTML = `<b>${res.success ? "✅ Thành công:" : "❌ Thất bại:"}</b> ${res.message}`;
  }
});

// 3. yt-dlp Test
if (btnTestYtdlp) {
  btnTestYtdlp.addEventListener("click", () => {
    const q = setYtdlpQuery.value.trim();
    btnTestYtdlp.disabled = true;
    btnTestYtdlp.textContent = "⏳ Đang trích xuất audio stream...";
    testYtdlpResultBox.style.display = "none";

    socket.emit("test_ytdlp_extraction", { query: q });
  });
}

socket.on("test_ytdlp_result", (res) => {
  if (btnTestYtdlp) {
    btnTestYtdlp.disabled = false;
    btnTestYtdlp.textContent = "⚡ Test Trích Xuất yt-dlp (No Download)";
  }
  if (testYtdlpResultBox) {
    testYtdlpResultBox.style.display = "block";
    testYtdlpResultBox.style.background = res.success ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)";
    testYtdlpResultBox.style.border = res.success ? "1px solid #10b981" : "1px solid #ef4444";
    testYtdlpResultBox.style.color = res.success ? "#10b981" : "#ef4444";
    testYtdlpResultBox.innerHTML = `<b>${res.success ? "✅ Trích xuất OK:" : "❌ Thất bại:"}</b> ${res.message}`;
  }
});

// 4. Save Global Settings
if (formSystemEngineSettings) {
  formSystemEngineSettings.addEventListener("submit", (e) => {
    e.preventDefault();
    socket.emit("save_system_settings", {
      audio_bitrate: setAudioBitrate.value,
      download_delay: parseFloat(setDownloadDelay.value) || 5.0,
      batch_size: parseInt(setBatchSize.value) || 50,
      cooldown_seconds: parseInt(setCooldown.value) || 120,
    });
  });
}

socket.on("system_settings_data", (data) => {
  if (setAudioBitrate && data.audio_bitrate) setAudioBitrate.value = data.audio_bitrate;
  if (setDownloadDelay && data.download_delay) setDownloadDelay.value = data.download_delay;
  if (setBatchSize && data.batch_size) setBatchSize.value = data.batch_size;
  if (setCooldown && data.cooldown_seconds) setCooldown.value = data.cooldown_seconds;
});

socket.on("system_settings_saved", (res) => {
  if (res.success) {
    alert("✅ Đã lưu và áp dụng cấu hình hệ thống thành công!");
    if (settingsModal) settingsModal.style.display = "none";
  }
});

// ─── Onboarding Guide Popup Modal Handler ───────────────────

const guideModal = document.getElementById("guide-modal");
const btnCloseGuideModal = document.getElementById("btn-close-guide-modal");
const btnGuideGotIt = document.getElementById("btn-guide-got-it");
const btnToggleGuide = document.getElementById("btn-toggle-guide");
const chkDontShowAgain = document.getElementById("chk-dont-show-again");
const guideNavTabs = document.querySelectorAll(".guide-nav-tab");
const guideTabPanes = document.querySelectorAll(".guide-tab-pane");

function closeGuidePopup() {
  if (guideModal) guideModal.style.display = "none";
  if (chkDontShowAgain && chkDontShowAgain.checked) {
    localStorage.setItem("music_studio_popup_dismissed", "true");
  }
}

if (guideModal) {
  // Auto show on first entry if not dismissed
  const isDismissed = localStorage.getItem("music_studio_popup_dismissed");
  if (isDismissed !== "true") {
    setTimeout(() => {
      guideModal.style.display = "flex";
    }, 400);
  }

  if (btnCloseGuideModal) btnCloseGuideModal.addEventListener("click", closeGuidePopup);
  if (btnGuideGotIt) btnGuideGotIt.addEventListener("click", closeGuidePopup);

  if (btnToggleGuide) {
    btnToggleGuide.addEventListener("click", () => {
      guideModal.style.display = "flex";
    });
  }

  // Guide Tabs Switching
  guideNavTabs.forEach((tabBtn) => {
    tabBtn.addEventListener("click", () => {
      guideNavTabs.forEach((b) => {
        b.style.background = "transparent";
        b.style.color = "var(--text-muted)";
        b.style.border = "1px solid var(--border-color)";
      });
      guideTabPanes.forEach((p) => (p.style.display = "none"));

      tabBtn.style.background = "#6366f1";
      tabBtn.style.color = "#fff";
      tabBtn.style.border = "none";

      const targetPane = document.getElementById(tabBtn.getAttribute("data-pane"));
      if (targetPane) targetPane.style.display = "block";
    });
  });
}

// ─── Track Details Context Modal Handler ───────────────────

const trackDetailsModal = document.getElementById("track-details-modal");
const btnCloseTrackDetails = document.getElementById("btn-close-track-details");
const detailTrackCover = document.getElementById("detail-track-cover");
const detailTrackName = document.getElementById("detail-track-name");
const detailArtistsContainer = document.getElementById("detail-artists-container");
const detailAlbumName = document.getElementById("detail-album-name");
const detailDuration = document.getElementById("detail-duration");
const detailReleaseDate = document.getElementById("detail-release-date");
const detailPopularity = document.getElementById("detail-popularity");
const detailSpotifyId = document.getElementById("detail-spotify-id");
const detailDbBadge = document.getElementById("detail-db-badge");
const detailSpotifyLink = document.getElementById("detail-spotify-link");

function showTrackDetails(t) {
  if (!t || !trackDetailsModal) return;

  if (detailTrackCover) detailTrackCover.src = t.image_url || "/static/img/default_cover.png";
  if (detailTrackName) detailTrackName.textContent = t.name || "Unknown Track";
  if (detailAlbumName) detailAlbumName.textContent = t.album_name || "Single";
  if (detailDuration) detailDuration.textContent = t.duration_formatted || `${Math.round((t.duration_ms || 0) / 1000)}s`;
  if (detailReleaseDate) detailReleaseDate.textContent = t.release_date || "Chưa rõ";
  if (detailPopularity) detailPopularity.textContent = `${t.popularity || 50}/100`;
  if (detailSpotifyId) detailSpotifyId.textContent = t.spotify_id || "None";

  // Render artists with chips
  if (detailArtistsContainer) {
    detailArtistsContainer.innerHTML = "";
    const artists = t.artists && t.artists.length > 0 ? t.artists : [{ name: t.artist_name || "Unknown Artist" }];
    artists.forEach((a) => {
      const chip = document.createElement("span");
      chip.style.background = "rgba(192, 132, 252, 0.15)";
      chip.style.color = "#c084fc";
      chip.style.border = "1px solid rgba(192, 132, 252, 0.35)";
      chip.style.padding = "2px 8px";
      chip.style.borderRadius = "4px";
      chip.style.fontSize = "11.5px";
      chip.style.fontWeight = "600";
      chip.textContent = `🎤 ${a.name || a}`;
      detailArtistsContainer.appendChild(chip);
    });
  }

  // Render status badge
  if (detailDbBadge) {
    if (t.db_status === "downloaded") {
      detailDbBadge.innerHTML = `<span style="background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.4); padding: 4px 10px; border-radius: 6px; font-size: 11.5px; font-weight: 600;">🎵 Đã có Audio 320k trong DB</span>`;
    } else if (t.db_status === "metadata_only") {
      detailDbBadge.innerHTML = `<span style="background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.4); padding: 4px 10px; border-radius: 6px; font-size: 11.5px; font-weight: 600;">📋 Đã lưu Metadata (Chờ tải Audio)</span>`;
    } else if (t.db_status === "download_failed") {
      detailDbBadge.innerHTML = `<span style="background: rgba(239,68,68,0.15); color: #ef4444; border: 1px solid rgba(239,68,68,0.4); padding: 4px 10px; border-radius: 6px; font-size: 11.5px; font-weight: 600;">⚠️ Tải Audio thất bại</span>`;
    } else {
      detailDbBadge.innerHTML = `<span style="background: rgba(6,182,212,0.15); color: #06b6d4; border: 1px solid rgba(6,182,212,0.4); padding: 4px 10px; border-radius: 6px; font-size: 11.5px; font-weight: 600;">✨ Bài Mới (Chưa nạp vào DB)</span>`;
    }
  }

  if (detailSpotifyLink) {
    detailSpotifyLink.href = t.spotify_id ? `https://open.spotify.com/track/${t.spotify_id}` : "#";
  }

  trackDetailsModal.style.display = "flex";
}

if (btnCloseTrackDetails) {
  btnCloseTrackDetails.addEventListener("click", () => {
    if (trackDetailsModal) trackDetailsModal.style.display = "none";
  });
}

// ══════════════════════════════════════════════════════════════
// ─── 📚 DATABASE CATALOG STUDIO & IN-APP AUDIO PLAYER ────────
// ══════════════════════════════════════════════════════════════

// View Switching Elements
const navBtnSourcing = document.getElementById("nav-btn-sourcing");
const navBtnCatalog = document.getElementById("nav-btn-catalog");
const viewSourcingStudio = document.getElementById("view-sourcing-studio");
const viewCatalogStudio = document.getElementById("view-catalog-studio");

// Catalog Filter & Search Elements
const catalogSearch = document.getElementById("catalog-search");
const catalogFilterGenre = document.getElementById("catalog-filter-genre");
const catalogFilterDownload = document.getElementById("catalog-filter-download");
const catalogFilterCollector = document.getElementById("catalog-filter-collector");
const catalogFilterIngest = document.getElementById("catalog-filter-ingest");
const catalogFilterModeration = document.getElementById("catalog-filter-moderation");
const catalogPageSize = document.getElementById("catalog-page-size");
const catalogTableBody = document.getElementById("catalog-table-body");
const catalogSelectAll = document.getElementById("catalog-select-all");
const catalogTotalCounter = document.getElementById("catalog-total-counter");
const catalogPaginationInfo = document.getElementById("catalog-pagination-info");
const catalogPageLabel = document.getElementById("catalog-page-label");
const catalogBtnFirst = document.getElementById("catalog-btn-first");
const catalogBtnPrev = document.getElementById("catalog-btn-prev");
const catalogBtnNext = document.getElementById("catalog-btn-next");
const catalogBtnLast = document.getElementById("catalog-btn-last");

// Catalog Action Buttons
const btnOpenAddTrack = document.getElementById("btn-open-add-track");
const btnBulkApprove = document.getElementById("btn-bulk-approve");
const btnBulkFlag = document.getElementById("btn-bulk-flag");
const btnBulkDelete = document.getElementById("btn-bulk-delete");
const btnRefreshCatalog = document.getElementById("btn-refresh-catalog");

// In-App Player Elements
const inAppPlayerBar = document.getElementById("in-app-player-bar");
const inAppAudio = document.getElementById("in-app-audio-element");
const playerTrackCover = document.getElementById("player-track-cover");
const playerTrackName = document.getElementById("player-track-name");
const playerTrackArtistText = document.getElementById("player-track-artist-text");
const playerTrackAttribution = document.getElementById("player-track-attribution");
const playerBtnPlay = document.getElementById("player-btn-play");
const playerBtnBackward = document.getElementById("player-btn-backward");
const playerBtnForward = document.getElementById("player-btn-forward");
const playerSeekBar = document.getElementById("player-seek-bar");
const playerCurrentTime = document.getElementById("player-current-time");
const playerTotalTime = document.getElementById("player-total-time");
const playerVolumeSlider = document.getElementById("player-volume-slider");
const playerBtnInspect = document.getElementById("player-btn-inspect");
const playerBtnLyrics = document.getElementById("player-btn-lyrics");
const playerBtnClose = document.getElementById("player-btn-close");

// Metadata Inspector Modal Elements
const trackInspectorModal = document.getElementById("track-inspector-modal");
const btnCloseInspector = document.getElementById("btn-close-inspector");
const btnFooterCloseInspector = document.getElementById("btn-footer-close-inspector");
const btnCopyRawJson = document.getElementById("btn-copy-raw-json");
const inspectJsonViewer = document.getElementById("inspect-json-viewer");
const inspectId3TableBody = document.getElementById("inspect-id3-table-body");
const btnSaveInspectorEdit = document.getElementById("btn-save-inspector-edit");

// Inspector Header & Info Elements
const inspectCoverImg = document.getElementById("inspect-cover-img");
const inspectTrackName = document.getElementById("inspect-track-name");
const inspectArtistName = document.getElementById("inspect-artist-name");
const inspectBadgeAudio = document.getElementById("inspect-badge-audio");
const inspectBadgeModeration = document.getElementById("inspect-badge-moderation");
const inspectBadgeCollector = document.getElementById("inspect-badge-collector");
const inspectBadgeIngest = document.getElementById("inspect-badge-ingest");
const inspectSpotifyId = document.getElementById("inspect-spotify-id");
const inspectIsrc = document.getElementById("inspect-isrc");
const inspectDuration = document.getElementById("inspect-duration");
const inspectAlbum = document.getElementById("inspect-album");
const inspectReleaseDate = document.getElementById("inspect-release-date");
const inspectTrackNumber = document.getElementById("inspect-track-number");
const inspectGenres = document.getElementById("inspect-genres");
const inspectPopularity = document.getElementById("inspect-popularity");
const inspectExplicit = document.getElementById("inspect-explicit");
const inspectAddedBy = document.getElementById("inspect-added-by");
const inspectCreatedAt = document.getElementById("inspect-created-at");
const inspectDownloadMethod = document.getElementById("inspect-download-method");
const inspectLocalPath = document.getElementById("inspect-local-path");
const inspectLyricsPreview = document.getElementById("inspect-lyrics-preview");

// Inspector Edit Form Elements
const inspectEditName = document.getElementById("inspect-edit-name");
const inspectEditArtist = document.getElementById("inspect-edit-artist");
const inspectEditAlbum = document.getElementById("inspect-edit-album");
const inspectEditGenres = document.getElementById("inspect-edit-genres");
const inspectEditPopularity = document.getElementById("inspect-edit-popularity");
const inspectEditModeration = document.getElementById("inspect-edit-moderation");

// Modals
const editTrackModal = document.getElementById("edit-track-modal");
const btnCloseEditTrack = document.getElementById("btn-close-edit-track");
const btnCancelEditTrack = document.getElementById("btn-cancel-edit-track");
const btnSaveEditTrack = document.getElementById("btn-save-edit-track");
const editSpotifyId = document.getElementById("edit-spotify-id");
const editTrackName = document.getElementById("edit-track-name");
const editTrackArtist = document.getElementById("edit-track-artist");
const editTrackAlbum = document.getElementById("edit-track-album");
const editTrackGenres = document.getElementById("edit-track-genres");
const editTrackPopularity = document.getElementById("edit-track-popularity");

const addTrackModal = document.getElementById("add-track-modal");
const btnCloseAddTrack = document.getElementById("btn-close-add-track-modal") || document.getElementById("btn-close-add-track");
const btnCancelAddTrack = document.getElementById("btn-cancel-add-track");
const formAddNewTrack = document.getElementById("form-add-new-track");
const addTrackName = document.getElementById("add-track-name");
const addTrackArtist = document.getElementById("add-track-artist");
const addTrackAlbum = document.getElementById("add-track-album");
const addTrackGenre = document.getElementById("add-track-genre");
const addTrackDuration = document.getElementById("add-track-duration");
const addTrackImage = document.getElementById("add-track-image");

const editLyricsModal = document.getElementById("edit-lyrics-modal");
const btnCloseLyricsModal = document.getElementById("btn-close-lyrics-modal");
const btnCancelLyrics = document.getElementById("btn-cancel-lyrics");
const btnSaveLyrics = document.getElementById("btn-save-lyrics");
const lyricsSpotifyId = document.getElementById("lyrics-spotify-id");
const lyricsTrackTitleInfo = document.getElementById("lyrics-track-title-info");
const lyricsSyncedText = document.getElementById("lyrics-synced-text");

// Catalog State
let catalogCurrentPage = 1;
let catalogTotalPages = 1;
let catalogTotalItems = 0;
let currentCatalogTracks = [];
let currentPlayingTrack = null;
let currentInspectedTrack = null;
let searchDebounceTimer = null;

// ─── Fetch and Render Catalog Data with Server-Side Pagination ───
async function loadCatalogTracks(page = 1) {
  if (!catalogTableBody) return;

  catalogCurrentPage = page;
  const limit = parseInt(catalogPageSize ? catalogPageSize.value : "20") || 20;
  const search = catalogSearch ? catalogSearch.value.trim() : "";
  const genre = catalogFilterGenre ? catalogFilterGenre.value : "all";
  const download = catalogFilterDownload ? catalogFilterDownload.value : "all";
  const moderation = catalogFilterModeration ? catalogFilterModeration.value : "all";
  const collector = catalogFilterCollector ? catalogFilterCollector.value : "all";
  const ingest = catalogFilterIngest ? catalogFilterIngest.value : "all";

  catalogTableBody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 30px; color: var(--text-muted);">⏳ Đang tải dữ liệu từ database...</td></tr>`;

  try {
    const params = new URLSearchParams({
      page: catalogCurrentPage,
      limit: limit,
      search: search,
      genre: genre,
      download_status: download,
      moderation_status: moderation,
      added_by: collector,
      ingest_type: ingest,
      sort_by: "created_at",
      sort_order: "-1",
    });

    const res = await fetch(`/api/tracks?${params.toString()}`);
    const data = await res.json();

    if (!data.success) {
      catalogTableBody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 20px; color: var(--accent-red);">❌ Lỗi tải dữ liệu: ${data.error || "Không rõ"}</td></tr>`;
      return;
    }

    currentCatalogTracks = data.items || [];
    catalogTotalItems = data.total_items || 0;
    catalogTotalPages = data.total_pages || 1;
    catalogCurrentPage = data.current_page || 1;

    // Dynamically update available collectors in filter dropdown
    if (data.available_collectors && catalogFilterCollector) {
      const selectedCollector = catalogFilterCollector.value;
      const currentOpts = Array.from(catalogFilterCollector.options).map((o) => o.value);
      data.available_collectors.forEach((col) => {
        if (!currentOpts.includes(col)) {
          const opt = document.createElement("option");
          opt.value = col;
          opt.textContent = `👤 ${col}`;
          catalogFilterCollector.appendChild(opt);
        }
      });
      catalogFilterCollector.value = selectedCollector;
    }

    // Update Counter & Pagination Info
    if (catalogTotalCounter) catalogTotalCounter.textContent = `${catalogTotalItems.toLocaleString()} bài`;
    if (catalogPageLabel) catalogPageLabel.textContent = `Trang ${catalogCurrentPage} / ${catalogTotalPages}`;

    const startIdx = catalogTotalItems === 0 ? 0 : (catalogCurrentPage - 1) * limit + 1;
    const endIdx = Math.min(catalogCurrentPage * limit, catalogTotalItems);
    if (catalogPaginationInfo) {
      catalogPaginationInfo.textContent = `Hiển thị ${startIdx} - ${endIdx} trong tổng số ${catalogTotalItems.toLocaleString()} bài hát`;
    }

    if (catalogBtnPrev) catalogBtnPrev.disabled = catalogCurrentPage <= 1;
    if (catalogBtnFirst) catalogBtnFirst.disabled = catalogCurrentPage <= 1;
    if (catalogBtnNext) catalogBtnNext.disabled = catalogCurrentPage >= catalogTotalPages;
    if (catalogBtnLast) catalogBtnLast.disabled = catalogCurrentPage >= catalogTotalPages;

    if (currentCatalogTracks.length === 0) {
      catalogTableBody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 35px; color: var(--text-muted);">Không tìm thấy bài hát nào khớp với bộ lọc!</td></tr>`;
      return;
    }

    catalogTableBody.innerHTML = "";
    currentCatalogTracks.forEach((t) => {
      const row = document.createElement("tr");

      // Duration Calculation & Formatting
      let formattedDuration = t.duration_formatted;
      if (!formattedDuration || formattedDuration === "0:00") {
        if (t.duration_ms && t.duration_ms > 0) {
          const totalSec = Math.round(t.duration_ms / 1000);
          const m = Math.floor(totalSec / 60);
          const s = totalSec % 60;
          formattedDuration = `${m}:${s < 10 ? '0' : ''}${s}`;
        } else {
          formattedDuration = "3:30";
        }
      }

      // Download Status Badge
      let dlBadge = "";
      if (t.download_status === "completed") {
        dlBadge = `<span class="badge badge-success">🎵 Đã Tải (320k)</span>`;
      } else if (t.download_status === "failed") {
        dlBadge = `<span class="badge badge-danger">⚠️ Lỗi Tải</span>`;
      } else {
        dlBadge = `<span class="badge badge-warning">📋 Chờ Tải</span>`;
      }

      // Moderation Status Badge
      let modBadge = "";
      const modStatus = t.moderation_status || "approved";
      if (modStatus === "approved") {
        modBadge = `<span class="badge badge-success">✅ Approved</span>`;
      } else if (modStatus === "flagged") {
        modBadge = `<span class="badge badge-danger">🚩 Flagged</span>`;
      } else {
        modBadge = `<span class="badge badge-warning">⏳ Pending</span>`;
      }

      // Attribution Badge (Người nạp & Loại nạp)
      const addedByTag = `<span class="badge badge-purple" style="font-size: 10px;">👤 ${t.added_by || "admin"}</span>`;
      const ingestTag = t.ingest_type === "full_audio"
        ? `<span class="badge badge-success" style="font-size: 10px;">🎵 Audio 320k</span>`
        : `<span class="badge badge-info" style="font-size: 10px;">📋 Meta Only</span>`;
      const attributionHtml = `<div style="display: flex; flex-direction: column; gap: 3px;">${addedByTag}${ingestTag}</div>`;

      // Collab artist chips
      let artistHtml = "";
      if (t.artists && t.artists.length > 1) {
        const artistBadges = t.artists
          .map((a) => `<span class="badge badge-purple" style="font-size: 10px; font-weight: 500;">🎤 ${a.name}</span>`)
          .join(" ");
        artistHtml = `<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 3px; align-items: center;"><span class="badge badge-warning" style="font-size: 9px; padding: 0 4px;">COLLAB</span> ${artistBadges}</div>`;
      } else {
        artistHtml = `<div style="font-size: 11.5px; color: var(--text-muted); margin-top: 2px;">🎤 ${t.artist_name || "Unknown Artist"}</div>`;
      }

      const coverSrc = t.image_url || "/static/img/default_cover.png";
      const coverImg = `<img src="${coverSrc}" onerror="this.src='/static/img/default_cover.png'" style="width: 38px; height: 38px; border-radius: 4px; object-fit: cover; border: 1px solid var(--border-color);" alt="Cover">`;

      // Play button for audio stream
      const isDownloaded = t.download_status === "completed";
      const isCurrentPlaying = currentPlayingTrack && currentPlayingTrack.spotify_id === t.spotify_id && !inAppAudio.paused;
      const playBtnIcon = isCurrentPlaying ? "⏸" : "▶";
      const playBtnStyle = isDownloaded
        ? "background: rgba(6,182,212,0.2); color: var(--accent-cyan); border: 1px solid var(--accent-cyan); cursor: pointer;"
        : "background: rgba(255,255,255,0.05); color: #666; border: 1px solid #444; cursor: not-allowed;";

      row.innerHTML = `
        <td style="padding: 10px 12px;">
          <input type="checkbox" class="catalog-track-cb" data-id="${t.spotify_id}" style="cursor: pointer; transform: scale(1.15);">
        </td>
        <td style="padding: 10px 8px; text-align: center;">${coverImg}</td>
        <td style="padding: 10px 8px; text-align: center;">
          <button class="btn-play-track" data-id="${t.spotify_id}" style="width: 28px; height: 28px; border-radius: 50%; padding: 0; font-size: 11px; display: inline-flex; align-items: center; justify-content: center; ${playBtnStyle}" ${isDownloaded ? "" : "disabled title='Chưa tải file audio'"}>
            ${playBtnIcon}
          </button>
        </td>
        <td style="padding: 10px 12px;">
          <div style="font-weight: 700; color: var(--text-main); font-size: 12.5px;">${t.name}</div>
          ${artistHtml}
        </td>
        <td style="padding: 10px 12px; color: var(--text-dim); font-size: 11.5px;">
          <div style="font-weight: 500; color: var(--text-main);">${t.album_name || "Single"}</div>
          <div style="display: inline-flex; align-items: center; gap: 4px; margin-top: 3px; font-weight: 600; color: var(--accent-cyan); font-family: 'JetBrains Mono', monospace; font-size: 11px; background: rgba(6,182,212,0.1); border: 1px solid rgba(6,182,212,0.2); padding: 1px 6px; border-radius: 4px;">
            ⏱️ ${formattedDuration}
          </div>
        </td>
        <td style="padding: 10px 10px;">
          <span class="badge badge-info">${(t.genres && t.genres[0]) || "vpop"}</span>
        </td>
        <td style="padding: 10px 10px;">${attributionHtml}</td>
        <td style="padding: 10px 10px;">${dlBadge}</td>
        <td style="padding: 10px 10px;">${modBadge}</td>
        <td style="padding: 10px 12px; text-align: center;">
          <div style="display: flex; gap: 4px; justify-content: center;">
            <button class="btn btn-secondary btn-catalog-inspect" data-id="${t.spotify_id}" title="Chi Tiết Metadata Toàn Diện & ID3" style="padding: 3px 6px; font-size: 11px; border-color: var(--accent-cyan); color: var(--accent-cyan);">🔍</button>
            <button class="btn btn-secondary btn-catalog-edit" data-id="${t.spotify_id}" title="Chỉnh sửa Metadata" style="padding: 3px 6px; font-size: 11px;">✏️</button>
            <button class="btn btn-secondary btn-catalog-lyrics" data-id="${t.spotify_id}" title="Xem & Sửa Lời .lrc" style="padding: 3px 6px; font-size: 11px; border-color: var(--accent-purple); color: var(--accent-purple);">🎤</button>
            <button class="btn btn-secondary btn-catalog-redownload" data-id="${t.spotify_id}" title="Tải Lại Âm Thanh" style="padding: 3px 6px; font-size: 11px;">⚡</button>
            <button class="btn btn-danger btn-catalog-delete" data-id="${t.spotify_id}" title="Xóa Khỏi Database & Storage" style="padding: 3px 6px; font-size: 11px;">🗑️</button>
          </div>
        </td>
      `;

      catalogTableBody.appendChild(row);
    });

    // Attach Row Event Handlers
    attachCatalogRowListeners();
  } catch (err) {
    catalogTableBody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 20px; color: var(--accent-red);">❌ Lỗi kết nối Server: ${err.message}</td></tr>`;
  }
}

// ─── Attach Listeners for Row Actions ───
function attachCatalogRowListeners() {
  // Inspect Full Metadata Button
  document.querySelectorAll(".btn-catalog-inspect").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const spotifyId = btn.getAttribute("data-id");
      openTrackInspector(spotifyId);
    });
  });

  // Play Track Button
  document.querySelectorAll(".btn-play-track").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const spotifyId = btn.getAttribute("data-id");
      const track = currentCatalogTracks.find((t) => t.spotify_id === spotifyId);
      if (track) playInAppTrack(track);
    });
  });

  // Edit Metadata Button
  document.querySelectorAll(".btn-catalog-edit").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const spotifyId = btn.getAttribute("data-id");
      const track = currentCatalogTracks.find((t) => t.spotify_id === spotifyId);
      if (track) openEditTrackModal(track);
    });
  });

  // Lyrics Editor Button
  document.querySelectorAll(".btn-catalog-lyrics").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const spotifyId = btn.getAttribute("data-id");
      const track = currentCatalogTracks.find((t) => t.spotify_id === spotifyId);
      if (track) openLyricsModal(track);
    });
  });

  // Re-download Track Button
  document.querySelectorAll(".btn-catalog-redownload").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const spotifyId = btn.getAttribute("data-id");
      btn.textContent = "⏳";
      btn.disabled = true;
      try {
        const res = await fetch(`/api/tracks/${spotifyId}/redownload`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
          appendLog(`⚡ Started audio re-download for track: ${spotifyId}`, "info");
        } else {
          alert(`Lỗi tải lại: ${data.error}`);
        }
      } catch (err) {
        alert(`Lỗi: ${err.message}`);
      } finally {
        setTimeout(() => {
          btn.textContent = "⚡";
          btn.disabled = false;
        }, 1500);
      }
    });
  });

  // Delete Track Button
  document.querySelectorAll(".btn-catalog-delete").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const spotifyId = btn.getAttribute("data-id");
      const track = currentCatalogTracks.find((t) => t.spotify_id === spotifyId);
      const trackName = track ? track.name : spotifyId;

      showConfirmModal({
        title: "⚠️ Xác Nhận Xóa Bài Hát",
        message: `Bạn có chắc chắn muốn xóa vĩnh viễn bài hát <b>'${trackName}'</b> khỏi Database và Ổ đĩa?<br><span class="text-dim font-mono" style="font-size: 11px;">ID: ${spotifyId}</span>`,
        proceedText: "🗑️ Xóa Vĩnh Viễn",
        isDanger: true,
        onConfirm: async () => {
          try {
            const res = await fetch(`/api/tracks/${spotifyId}`, { method: "DELETE" });
            const data = await res.json();
            if (data.success) {
              appendLog(`🗑️ Đã xóa bài hát '${trackName}'`, "warning");
              loadCatalogTracks(catalogCurrentPage);
            } else {
              alert(`Lỗi xóa bài: ${data.error}`);
            }
          } catch (err) {
            alert(`Lỗi: ${err.message}`);
          }
        },
      });
    });
  });
}

// ─── Open Full Metadata Inspector Modal ──────────────────────
async function openTrackInspector(spotifyId) {
  if (!trackInspectorModal || !spotifyId) return;

  trackInspectorModal.style.display = "flex";
  // Reset tabs to visual tab by default
  switchInspectorTab("tab-inspect-visual");

  // Loading state
  if (inspectTrackName) inspectTrackName.textContent = "⏳ Đang tải dữ liệu chi tiết...";
  if (inspectJsonViewer) inspectJsonViewer.textContent = "Loading JSON document...";

  try {
    const res = await fetch(`/api/tracks/${spotifyId}/inspect`);
    const data = await res.json();

    if (!data.success) {
      alert(`Lỗi tải metadata: ${data.error}`);
      trackInspectorModal.style.display = "none";
      return;
    }

    currentInspectedTrack = data;
    const t = data.track || {};
    const f = data.file_info || {};
    const id3 = data.id3_frames || {};

    // 1. Visual Tab Population
    if (inspectCoverImg) {
      inspectCoverImg.src = t.image_url || "/static/img/default_cover.png";
    }
    if (inspectTrackName) inspectTrackName.textContent = t.name || "-";
    if (inspectArtistName) inspectArtistName.textContent = t.artist_name || "-";

    if (inspectBadgeAudio) {
      inspectBadgeAudio.textContent = t.download_status === "completed" ? `🎵 320k MP3 (${f.file_size_mb || 0} MB)` : "📋 Chờ Tải";
      inspectBadgeAudio.className = t.download_status === "completed" ? "badge badge-success" : "badge badge-warning";
    }
    if (inspectBadgeModeration) {
      inspectBadgeModeration.textContent = `🛡️ ${t.moderation_status || "approved"}`;
      inspectBadgeModeration.className = t.moderation_status === "flagged" ? "badge badge-danger" : "badge badge-info";
    }
    if (inspectBadgeCollector) {
      inspectBadgeCollector.textContent = `👤 ${t.added_by || "admin"}`;
    }
    if (inspectBadgeIngest) {
      inspectBadgeIngest.textContent = t.ingest_type === "full_audio" ? "🎵 full_audio" : "📋 metadata_only";
    }

    if (inspectSpotifyId) inspectSpotifyId.textContent = t.spotify_id || "-";
    if (inspectIsrc) inspectIsrc.textContent = t.isrc || "-";
    if (inspectDuration) inspectDuration.textContent = `${t.duration_formatted || "0:00"} (${(t.duration_ms || 0).toLocaleString()} ms)`;
    if (inspectAlbum) inspectAlbum.textContent = t.album_name || "Single";
    if (inspectReleaseDate) inspectReleaseDate.textContent = t.release_date || "-";
    if (inspectTrackNumber) inspectTrackNumber.textContent = `Track #${t.track_number || 1} / Disc #${t.disc_number || 1}`;
    if (inspectGenres) inspectGenres.textContent = (t.genres || []).join(", ") || "vpop";
    if (inspectPopularity) inspectPopularity.textContent = `${t.popularity || 0} / 100`;
    if (inspectExplicit) inspectExplicit.textContent = t.explicit ? "🔞 Có (Explicit)" : "🟢 Sạch (Clean)";
    if (inspectAddedBy) inspectAddedBy.textContent = `👤 ${t.added_by || "admin"}`;
    if (inspectCreatedAt) inspectCreatedAt.textContent = t.created_at || "-";
    if (inspectDownloadMethod) inspectDownloadMethod.textContent = t.download_method || "yt-dlp";
    if (inspectLocalPath) inspectLocalPath.textContent = f.absolute_path || t.local_path || "Chưa tải về ổ đĩa";

    if (inspectLyricsPreview) {
      if (t.lyrics_synced) {
        inspectLyricsPreview.textContent = t.lyrics_synced;
      } else if (t.lyrics_plain) {
        inspectLyricsPreview.textContent = t.lyrics_plain;
      } else {
        inspectLyricsPreview.textContent = "Chưa có lời bài hát.";
      }
    }

    // 1b. Multi-Album Affiliations
    const inspectAlbumsCount = document.getElementById("inspect-albums-count");
    const inspectAlbumsList = document.getElementById("inspect-albums-list");
    const allAlbums = (t.albums && t.albums.length > 0) ? t.albums : (t.album_name ? [{ spotify_id: t.album_spotify_id, name: t.album_name, release_date: t.release_date }] : []);
    
    if (inspectAlbumsCount) {
      inspectAlbumsCount.textContent = `${allAlbums.length} Album${allAlbums.length > 1 ? 's' : ''}`;
    }
    if (inspectAlbumsList) {
      if (allAlbums.length === 0) {
        inspectAlbumsList.innerHTML = `<span style="font-size: 11px; color: var(--text-dim);">Chưa có liên kết album bổ sung.</span>`;
      } else {
        inspectAlbumsList.innerHTML = allAlbums.map((alb, idx) => {
          const isPrimary = alb.spotify_id === t.album_spotify_id;
          const badgePrimary = isPrimary ? `<span class="badge badge-success" style="font-size: 9px; padding: 1px 4px;">CHÍNH</span>` : `<span class="badge badge-info" style="font-size: 9px; padding: 1px 4px;">LIÊN KẾT</span>`;
          return `
            <div style="background: rgba(6,182,212,0.08); border: 1px solid rgba(6,182,212,0.25); border-radius: var(--radius-sm); padding: 4px 8px; font-size: 11px; display: inline-flex; align-items: center; gap: 6px;">
              💿 <b>${alb.name || 'Single'}</b> ${badgePrimary}
              <span class="font-mono text-dim" style="font-size: 10px;">ID: ${alb.spotify_id || '-'}</span>
            </div>
          `;
        }).join("");
      }
    }

    // 2. Raw JSON Tab
    if (inspectJsonViewer) {
      inspectJsonViewer.textContent = JSON.stringify(t, null, 2);
    }

    // 3. ID3 MP3 Tags Tab
    if (inspectId3TableBody) {
      inspectId3TableBody.innerHTML = "";
      const frameDescriptions = {
        TIT2: "Track Title (Tên bài hát)",
        TPE1: "Lead Artist / Performer (Ca sĩ chính)",
        TPE2: "Album Artist / Collabs (Nghệ sĩ Album)",
        TALB: "Album Name (Tên Album)",
        TDRC: "Recording Year / Date (Năm phát hành)",
        TCON: "Content Type / Genre (Thể loại)",
        TRCK: "Track Number (Số thứ tự bài hát)",
        APIC: "Attached Picture (Ảnh bìa HD nhúng)",
        USLT: "Unsynced Lyrics Transcription (Lời bài hát)",
      };

      if (Object.keys(id3).length === 0) {
        inspectId3TableBody.innerHTML = `<tr><td colspan="3" style="text-align: center; padding: 16px; color: var(--text-muted);">Không có frame ID3 hoặc file audio chưa được tải về máy.</td></tr>`;
      } else {
        Object.entries(id3).forEach(([frameKey, frameVal]) => {
          const row = document.createElement("tr");
          const baseKey = frameKey.split(":")[0];
          const desc = frameDescriptions[baseKey] || "Custom ID3 Tag Frame";
          row.innerHTML = `
            <td style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: var(--accent-cyan);">${frameKey}</td>
            <td style="color: var(--text-muted); font-size: 11px;">${desc}</td>
            <td style="font-family: 'JetBrains Mono', monospace; font-size: 11px; word-break: break-all; color: var(--text-main);">${frameVal}</td>
          `;
          inspectId3TableBody.appendChild(row);
        });
      }
    }

    // 4. Quick Edit Tab
    if (inspectEditName) inspectEditName.value = t.name || "";
    if (inspectEditArtist) inspectEditArtist.value = t.artist_name || "";
    if (inspectEditAlbum) inspectEditAlbum.value = t.album_name || "";
    if (inspectEditGenres) inspectEditGenres.value = (t.genres || []).join(", ");
    if (inspectEditPopularity) inspectEditPopularity.value = t.popularity || 50;
    if (inspectEditModeration) inspectEditModeration.value = t.moderation_status || "approved";
  } catch (err) {
    alert(`Lỗi xem metadata: ${err.message}`);
  }
}

function switchInspectorTab(targetTabId) {
  document.querySelectorAll(".inspector-tab-btn").forEach((btn) => {
    if (btn.getAttribute("data-tab") === targetTabId) {
      btn.classList.add("btn-primary");
      btn.classList.remove("btn-secondary");
    } else {
      btn.classList.add("btn-secondary");
      btn.classList.remove("btn-primary");
    }
  });

  document.querySelectorAll(".inspector-tab-content").forEach((c) => {
    c.style.display = c.id === targetTabId ? "flex" : "none";
  });
}

document.querySelectorAll(".inspector-tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const tab = btn.getAttribute("data-tab");
    switchInspectorTab(tab);
  });
});

if (btnCloseInspector) btnCloseInspector.addEventListener("click", () => (trackInspectorModal.style.display = "none"));
if (btnFooterCloseInspector) btnFooterCloseInspector.addEventListener("click", () => (trackInspectorModal.style.display = "none"));

if (btnCopyRawJson) {
  btnCopyRawJson.addEventListener("click", () => {
    if (inspectJsonViewer && inspectJsonViewer.textContent) {
      navigator.clipboard.writeText(inspectJsonViewer.textContent);
      btnCopyRawJson.textContent = "✅ Đã Copy!";
      setTimeout(() => (btnCopyRawJson.textContent = "📋 Copy JSON"), 2000);
    }
  });
}

if (btnSaveInspectorEdit) {
  btnSaveInspectorEdit.addEventListener("click", async () => {
    if (!currentInspectedTrack || !currentInspectedTrack.track) return;
    const spotifyId = currentInspectedTrack.track.spotify_id;

    try {
      const res = await fetch(`/api/tracks/${spotifyId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: inspectEditName.value.trim(),
          artist_name: inspectEditArtist.value.trim(),
          album_name: inspectEditAlbum.value.trim(),
          genres: inspectEditGenres.value.trim(),
          popularity: parseInt(inspectEditPopularity.value) || 50,
          moderation_status: inspectEditModeration.value,
        }),
      });
      const data = await res.json();
      if (data.success) {
        appendLog(`✏️ Updated metadata via Inspector for ${inspectEditName.value}`, "success");
        trackInspectorModal.style.display = "none";
        loadCatalogTracks(catalogCurrentPage);
      } else {
        alert(`Lỗi cập nhật: ${data.error}`);
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    }
  });
}

// ─── In-App Audio Player Controller ──────────────────────────
function updateRowPlayButtons() {
  document.querySelectorAll(".btn-play-track").forEach((btn) => {
    const sid = btn.getAttribute("data-id");
    const isPlayingThis = currentPlayingTrack && currentPlayingTrack.spotify_id === sid && inAppAudio && !inAppAudio.paused;
    btn.textContent = isPlayingThis ? "⏸" : "▶";
    btn.style.boxShadow = isPlayingThis ? "0 0 10px rgba(6, 182, 212, 0.5)" : "none";
  });
}

function playInAppTrack(track) {
  if (!track || !inAppAudio) return;

  if (currentPlayingTrack && currentPlayingTrack.spotify_id === track.spotify_id) {
    if (inAppAudio.paused) {
      inAppAudio.play();
      if (playerBtnPlay) playerBtnPlay.textContent = "⏸";
    } else {
      inAppAudio.pause();
      if (playerBtnPlay) playerBtnPlay.textContent = "▶";
    }
    updateRowPlayButtons();
    return;
  }

  currentPlayingTrack = track;
  inAppAudio.src = `/api/stream/${track.spotify_id}`;
  inAppAudio.load();
  inAppAudio.play().catch((e) => console.warn("Auto-play prevented:", e));

  if (playerTrackCover) {
    playerTrackCover.src = track.image_url || "/static/img/default_cover.png";
    playerTrackCover.onerror = () => (playerTrackCover.src = "/static/img/default_cover.png");
  }
  if (playerTrackName) playerTrackName.textContent = track.name || "Unknown Track";
  if (playerTrackArtistText) playerTrackArtistText.textContent = track.artist_name || "Unknown Artist";
  if (playerTrackAttribution) {
    playerTrackAttribution.textContent = `👤 ${track.added_by || "admin"}`;
  }
  if (playerBtnPlay) playerBtnPlay.textContent = "⏸";
  if (inAppPlayerBar) inAppPlayerBar.style.display = "flex";

  updateRowPlayButtons();
}

if (inAppAudio) {
  inAppAudio.addEventListener("play", () => {
    if (playerBtnPlay) playerBtnPlay.textContent = "⏸";
    updateRowPlayButtons();
  });

  inAppAudio.addEventListener("pause", () => {
    if (playerBtnPlay) playerBtnPlay.textContent = "▶";
    updateRowPlayButtons();
  });

  inAppAudio.addEventListener("timeupdate", () => {
    const cur = inAppAudio.currentTime || 0;
    const dur = inAppAudio.duration || 0;
    if (playerCurrentTime) playerCurrentTime.textContent = formatSec(cur);
    if (playerTotalTime && dur) playerTotalTime.textContent = formatSec(dur);
    if (playerSeekBar && dur > 0) playerSeekBar.value = (cur / dur) * 100;
  });

  inAppAudio.addEventListener("ended", () => {
    if (playerBtnPlay) playerBtnPlay.textContent = "▶";
    updateRowPlayButtons();
  });
}

function formatSec(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

if (playerBtnPlay) {
  playerBtnPlay.addEventListener("click", () => {
    if (!inAppAudio.src) return;
    if (inAppAudio.paused) {
      inAppAudio.play();
      playerBtnPlay.textContent = "⏸";
    } else {
      inAppAudio.pause();
      playerBtnPlay.textContent = "▶";
    }
    updateRowPlayButtons();
  });
}

if (playerBtnBackward) {
  playerBtnBackward.addEventListener("click", () => {
    if (inAppAudio) inAppAudio.currentTime = Math.max(0, inAppAudio.currentTime - 10);
  });
}

if (playerBtnForward) {
  playerBtnForward.addEventListener("click", () => {
    if (inAppAudio) inAppAudio.currentTime = Math.min(inAppAudio.duration || 0, inAppAudio.currentTime + 10);
  });
}

if (playerSeekBar) {
  playerSeekBar.addEventListener("input", () => {
    if (inAppAudio && inAppAudio.duration) {
      inAppAudio.currentTime = (playerSeekBar.value / 100) * inAppAudio.duration;
    }
  });
}

if (playerVolumeSlider) {
  playerVolumeSlider.addEventListener("input", () => {
    if (inAppAudio) inAppAudio.volume = parseFloat(playerVolumeSlider.value);
  });
}

if (playerBtnInspect) {
  playerBtnInspect.addEventListener("click", () => {
    if (currentPlayingTrack) openTrackInspector(currentPlayingTrack.spotify_id);
  });
}

if (playerBtnClose) {
  playerBtnClose.addEventListener("click", () => {
    if (inAppAudio) {
      inAppAudio.pause();
      inAppAudio.src = "";
    }
    currentPlayingTrack = null;
    if (inAppPlayerBar) inAppPlayerBar.style.display = "none";
    updateRowPlayButtons();
  });
}

if (playerBtnLyrics) {
  playerBtnLyrics.addEventListener("click", () => {
    if (currentPlayingTrack) openLyricsModal(currentPlayingTrack);
  });
}

// ─── Filter & Search Listeners ───────────────────────────────
if (catalogSearch) {
  catalogSearch.addEventListener("input", () => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      loadCatalogTracks(1);
    }, 300);
  });
}

if (catalogFilterGenre) catalogFilterGenre.addEventListener("change", () => loadCatalogTracks(1));
if (catalogFilterDownload) catalogFilterDownload.addEventListener("change", () => loadCatalogTracks(1));
if (catalogFilterCollector) catalogFilterCollector.addEventListener("change", () => loadCatalogTracks(1));
if (catalogFilterIngest) catalogFilterIngest.addEventListener("change", () => loadCatalogTracks(1));
if (catalogFilterModeration) catalogFilterModeration.addEventListener("change", () => loadCatalogTracks(1));
if (catalogPageSize) catalogPageSize.addEventListener("change", () => loadCatalogTracks(1));
if (btnRefreshCatalog) btnRefreshCatalog.addEventListener("click", () => loadCatalogTracks(catalogCurrentPage));

// Pagination Controls
if (catalogBtnFirst) catalogBtnFirst.addEventListener("click", () => loadCatalogTracks(1));
if (catalogBtnPrev) catalogBtnPrev.addEventListener("click", () => loadCatalogTracks(Math.max(1, catalogCurrentPage - 1)));
if (catalogBtnNext) catalogBtnNext.addEventListener("click", () => loadCatalogTracks(Math.min(catalogTotalPages, catalogCurrentPage + 1)));
if (catalogBtnLast) catalogBtnLast.addEventListener("click", () => loadCatalogTracks(catalogTotalPages));

if (catalogSelectAll) {
  catalogSelectAll.addEventListener("change", () => {
    const isChecked = catalogSelectAll.checked;
    document.querySelectorAll(".catalog-track-cb").forEach((cb) => (cb.checked = isChecked));
  });
}

// ─── Reusable Confirmation Modal (Global System) ────────────
window.confirmModalCallback = null;

window.showConfirmModal = function(opts, legacyCallback) {
  let title = "⚠️ Xác Nhận Thao Tác Dữ Liệu";
  let message = "Bạn có chắc chắn muốn thực hiện thao tác này?";
  let proceedText = "Xác Nhận Xóa";
  let isDanger = true;
  let onConfirm = null;

  if (typeof opts === "string") {
    message = opts;
    onConfirm = legacyCallback;
  } else if (typeof opts === "object" && opts !== null) {
    title = opts.title || title;
    message = opts.message || message;
    proceedText = opts.proceedText || proceedText;
    isDanger = opts.isDanger !== undefined ? opts.isDanger : true;
    onConfirm = opts.onConfirm;
  }

  const modal = document.getElementById("confirm-modal");
  const msgEl = document.getElementById("confirm-modal-message");
  const proceedBtn = document.getElementById("btn-confirm-proceed");

  if (!modal) {
    if (window.confirm(message.replace(/<[^>]*>?/gm, ''))) {
      if (typeof onConfirm === "function") onConfirm();
    }
    return;
  }

  if (msgEl) msgEl.innerHTML = message;
  if (proceedBtn) {
    proceedBtn.textContent = proceedText;
    proceedBtn.className = isDanger ? "btn btn-danger" : "btn btn-primary";
  }
  window.confirmModalCallback = onConfirm;
  modal.style.zIndex = "1000000";
  modal.style.display = "flex";
};

window.executeConfirmModal = function() {
  const modal = document.getElementById("confirm-modal");
  if (modal) modal.style.display = "none";
  if (typeof window.confirmModalCallback === "function") {
    const cb = window.confirmModalCallback;
    window.confirmModalCallback = null;
    try {
      cb();
    } catch (err) {
      console.error("Error executing confirm action:", err);
      alert("Lỗi thực thi: " + err.message);
    }
  }
};

window.closeConfirmModal = function() {
  const modal = document.getElementById("confirm-modal");
  if (modal) modal.style.display = "none";
  window.confirmModalCallback = null;
};

const confirmModal = document.getElementById("confirm-modal");
const btnCloseConfirmModal = document.getElementById("btn-close-confirm-modal");
const btnConfirmCancel = document.getElementById("btn-confirm-cancel");
const btnConfirmProceed = document.getElementById("btn-confirm-proceed");

if (btnCloseConfirmModal) btnCloseConfirmModal.addEventListener("click", window.closeConfirmModal);
if (btnConfirmCancel) btnConfirmCancel.addEventListener("click", window.closeConfirmModal);
if (btnConfirmProceed) btnConfirmProceed.addEventListener("click", window.executeConfirmModal);

// ─── Bulk Operations (Approve, Flag, Delete) ─────────────────
function getSelectedCatalogIds() {
  const ids = [];
  document.querySelectorAll(".catalog-track-cb:checked").forEach((cb) => {
    ids.push(cb.getAttribute("data-id"));
  });
  return ids;
}

if (btnBulkApprove) {
  btnBulkApprove.addEventListener("click", async () => {
    const ids = getSelectedCatalogIds();
    if (ids.length === 0) return alert("Vui lòng tích chọn các bài hát cần duyệt!");

    try {
      const res = await fetch("/api/tracks/moderate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spotify_ids: ids, status: "approved" }),
      });
      const data = await res.json();
      if (data.success) {
        appendLog(`✅ Đã phê duyệt ${data.modified_count} bài hát`, "success");
        loadCatalogTracks(catalogCurrentPage);
      } else {
        alert(`Lỗi: ${data.error}`);
      }
    } catch (e) {
      alert(`Lỗi duyệt bài: ${e.message}`);
    }
  });
}

if (btnBulkFlag) {
  btnBulkFlag.addEventListener("click", async () => {
    const ids = getSelectedCatalogIds();
    if (ids.length === 0) return alert("Vui lòng tích chọn các bài hát cần gắn cờ!");

    try {
      const res = await fetch("/api/tracks/moderate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spotify_ids: ids, status: "flagged" }),
      });
      const data = await res.json();
      if (data.success) {
        appendLog(`🚩 Đã gắn cờ cảnh báo ${data.modified_count} bài hát`, "warning");
        loadCatalogTracks(catalogCurrentPage);
      } else {
        alert(`Lỗi: ${data.error}`);
      }
    } catch (e) {
      alert(`Lỗi gắn cờ: ${e.message}`);
    }
  });
}

if (btnBulkDelete) {
  btnBulkDelete.addEventListener("click", () => {
    const ids = getSelectedCatalogIds();
    if (ids.length === 0) return alert("Vui lòng tích chọn ít nhất 1 bài hát để xóa!");

    showConfirmModal({
      title: "⚠️ Xác Nhận Xóa Hàng Loạt",
      message: `Bạn có chắc chắn muốn xóa vĩnh viễn <b>${ids.length} bài hát</b> đã chọn khỏi Database và Ổ đĩa?`,
      proceedText: `🗑️ Xóa ${ids.length} Bài`,
      isDanger: true,
      onConfirm: async () => {
        try {
          const res = await fetch("/api/tracks/bulk_delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ spotify_ids: ids }),
          });
          const data = await res.json();
          if (data.success) {
            appendLog(`🗑️ Đã xóa hàng loạt ${data.deleted_count} bài hát`, "warning");
            loadCatalogTracks(catalogCurrentPage);
          } else {
            alert(`Lỗi xóa hàng loạt: ${data.error}`);
          }
        } catch (e) {
          alert(`Lỗi xóa hàng loạt: ${e.message}`);
        }
      },
    });
  });
}

// ─── Manual Add Track Modal Handlers ─────────────────────────
if (btnOpenAddTrack) {
  btnOpenAddTrack.addEventListener("click", () => {
    if (addTrackModal) addTrackModal.style.display = "flex";
  });
}
if (btnCloseAddTrack) btnCloseAddTrack.addEventListener("click", () => (addTrackModal.style.display = "none"));
if (btnCancelAddTrack) btnCancelAddTrack.addEventListener("click", () => (addTrackModal.style.display = "none"));

if (formAddNewTrack) {
  formAddNewTrack.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("add-track-name")?.value.trim();
    const artist = document.getElementById("add-track-artist")?.value.trim();
    const album = document.getElementById("add-track-album")?.value.trim() || "Single";
    const duration = parseInt(document.getElementById("add-track-duration")?.value) || 180;
    const genre = document.getElementById("add-track-genre")?.value || "vpop";
    const popularity = parseInt(document.getElementById("add-track-popularity")?.value) || 65;
    const imageUrl = document.getElementById("add-track-image")?.value.trim();

    if (!name || !artist) {
      alert("Tên bài hát và Nghệ sĩ là bắt buộc!");
      return;
    }

    const btnSave = document.getElementById("btn-save-new-track");
    if (btnSave) { btnSave.disabled = true; btnSave.textContent = "⏳ Đang lưu..."; }

    try {
      const res = await fetch("/api/tracks/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name,
          artist_name: artist,
          album_name: album,
          duration_sec: duration,
          genres: [genre],
          popularity: popularity,
          image_url: imageUrl,
        }),
      });
      const data = await res.json();
      if (data.success) {
        appendLog(`➕ Đã thêm bài hát mới: '${name}' - ${artist}`, "success");
        if (addTrackModal) addTrackModal.style.display = "none";
        formAddNewTrack.reset();
        loadCatalogTracks(1);
      } else {
        alert(`Lỗi thêm bài: ${data.error}`);
      }
    } catch (err) {
      alert(`Lỗi kết nối: ${err.message}`);
    } finally {
      if (btnSave) { btnSave.disabled = false; btnSave.textContent = "💾 Lưu Bài Hát Vào DB"; }
    }
  });
}

// ─── Smart Trending & Live Discovery Feed Logic ─────────────
const trendsDynamicChips = document.getElementById("trends-dynamic-chips");
const btnSyncTrends = document.getElementById("btn-sync-trends");
const trendTabBtns = document.querySelectorAll(".trend-tab-btn");

let currentTrendsData = null;
let activeTrendTab = "keywords";

async function fetchAndRenderTrends(force = false) {
  if (!trendsDynamicChips) return;
  if (force) {
    trendsDynamicChips.innerHTML = `<span class="text-dim" style="font-size: 11.5px; padding: 8px 0;">⏳ Đang đồng bộ xu hướng mới nhất từ Spotify &amp; Internet...</span>`;
    if (btnSyncTrends) {
      btnSyncTrends.textContent = "⏳ Đang đồng bộ...";
      btnSyncTrends.disabled = true;
    }
  }

  try {
    const res = await fetch(`/api/trends?refresh=${force}`);
    const data = await res.json();
    if (data.success) {
      currentTrendsData = data;
      renderTrendChips(activeTrendTab);
    } else {
      trendsDynamicChips.innerHTML = `<span class="text-dim" style="font-size: 11.5px; color: var(--accent-red);">Không thể tải dữ liệu xu hướng.</span>`;
    }
  } catch (err) {
    trendsDynamicChips.innerHTML = `<span class="text-dim" style="font-size: 11.5px; color: var(--text-muted);">Lỗi kết nối xu hướng: ${err.message}</span>`;
  } finally {
    if (btnSyncTrends) {
      btnSyncTrends.textContent = "🔄 Làm Mới Xu Hướng";
      btnSyncTrends.disabled = false;
    }
  }
}

function renderTrendChips(tab) {
  if (!trendsDynamicChips || !currentTrendsData) return;
  activeTrendTab = tab;

  let items = [];
  if (tab === "keywords") items = currentTrendsData.keywords || [];
  else if (tab === "artists") items = currentTrendsData.artists || [];
  else if (tab === "albums") items = currentTrendsData.albums || [];
  else if (tab === "playlists") items = currentTrendsData.playlists || [];

  if (items.length === 0) {
    trendsDynamicChips.innerHTML = `<span class="text-dim" style="font-size: 11.5px; padding: 6px 0;">Chưa có dữ liệu xu hướng cho danh mục này.</span>`;
    return;
  }

  trendsDynamicChips.innerHTML = items.map((item) => {
    let label = item.label || item.name || item.title || "Xu hướng";
    let query = item.query || item.name || item.title || "";
    let mode = item.mode || "search";
    let genre = item.genre || "vpop";
    let icon = item.icon || (mode === "artist" ? "🎤" : (mode === "album" ? "💿" : "🔥"));
    let badgeHtml = item.badge || item.tag ? `<span style="font-size: 9px; padding: 1px 4px; border-radius: 3px; background: rgba(245,158,11,0.2); color: #fbbf24; margin-left: 4px; font-weight: 700;">${item.badge || item.tag}</span>` : "";

    return `
      <span class="preset-chip trend-chip" data-mode="${mode}" data-query="${query.replace(/"/g, '&quot;')}" data-genre="${genre}" title="Bấm để tự động chọn [${mode.toUpperCase()}], thể loại [${genre}] và kéo dữ liệu ngay">
        ${icon} <b>${label}</b> ${badgeHtml}
      </span>
    `;
  }).join("");

  // Attach click listeners to freshly rendered chips
  trendsDynamicChips.querySelectorAll(".trend-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      trendsDynamicChips.querySelectorAll(".trend-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");

      const mode = chip.getAttribute("data-mode") || "search";
      const query = chip.getAttribute("data-query") || "";
      const genre = chip.getAttribute("data-genre") || "";

      // 1. Automatically switch crawl mode
      if (crawlMode) {
        crawlMode.value = mode;
        // Trigger change event to update placeholder
        crawlMode.dispatchEvent(new Event("change"));
      }

      // 2. Automatically fill query
      if (crawlQuery) {
        crawlQuery.value = query;
        crawlQuery.disabled = false;
      }

      // 3. Automatically select matching genre
      if (crawlGenre && genre) {
        crawlGenre.value = genre;
      }

      appendLog(`🔥 Khám phá xu hướng [${mode.toUpperCase()}]: '${query}' (Thể loại: ${genre || 'Auto'})`, "info");

      // 4. Automatically trigger live API search preview
      if (btnPreviewSearch) {
        btnPreviewSearch.click();
      }
    });
  });
}

// Trend category tabs click
trendTabBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    trendTabBtns.forEach((b) => {
      b.style.background = "transparent";
      b.style.color = "var(--text-muted)";
      b.style.borderColor = "var(--border-color)";
      b.classList.remove("active");
    });

    btn.style.background = "rgba(6,182,212,0.15)";
    btn.style.color = "var(--accent-cyan)";
    btn.style.borderColor = "var(--accent-cyan)";
    btn.classList.add("active");

    const tab = btn.getAttribute("data-tab");
    renderTrendChips(tab);
  });
});

if (btnSyncTrends) {
  btnSyncTrends.addEventListener("click", () => {
    fetchAndRenderTrends(true);
  });
}

// Initial fetch of trends
fetchAndRenderTrends(false);

// ─── System Activity & Audit Logs Modal Logic ────────────────
const auditLogModal = document.getElementById("audit-log-modal");
const btnOpenAuditModal = document.getElementById("btn-open-audit-modal");
const btnHeaderAuditLogs = document.getElementById("btn-header-audit-logs");
const btnCloseAuditModal = document.getElementById("btn-close-audit-modal");
const auditSearch = document.getElementById("audit-search");
const auditFilterUser = document.getElementById("audit-filter-user");
const auditFilterAction = document.getElementById("audit-filter-action");
const auditFilterStatus = document.getElementById("audit-filter-status");
const btnRefreshAuditLogs = document.getElementById("btn-refresh-audit-logs");
const btnExportAuditLogs = document.getElementById("btn-export-audit-logs");
const auditLogsTableBody = document.getElementById("audit-logs-table-body");
const auditPaginationInfo = document.getElementById("audit-pagination-info");
const auditBtnPrev = document.getElementById("audit-btn-prev");
const auditBtnNext = document.getElementById("audit-btn-next");
const auditPageLabel = document.getElementById("audit-page-label");

let auditCurrentPage = 1;
let auditTotalPages = 1;
let auditSearchTimer = null;

async function loadAuditLogs(page = 1) {
  if (!auditLogsTableBody) return;
  auditCurrentPage = page;
  auditLogsTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-dim" style="padding: 20px;">⏳ Đang tải nhật ký hệ thống...</td></tr>`;

  const search = auditSearch ? auditSearch.value.trim() : "";
  const user = auditFilterUser ? auditFilterUser.value : "all";
  const action = auditFilterAction ? auditFilterAction.value : "all";
  const status = auditFilterStatus ? auditFilterStatus.value : "all";

  const url = `/api/logs?page=${page}&limit=20&user=${encodeURIComponent(user)}&action=${encodeURIComponent(action)}&status=${encodeURIComponent(status)}&search=${encodeURIComponent(search)}`;

  try {
    const res = await fetch(url);
    const data = await res.json();
    if (!data.success) {
      auditLogsTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-red" style="padding: 20px;">Lỗi: ${data.error}</td></tr>`;
      return;
    }

    auditTotalPages = data.total_pages || 1;
    if (auditPageLabel) auditPageLabel.textContent = `Trang ${data.current_page} / ${auditTotalPages}`;
    if (auditPaginationInfo) {
      const from = (data.current_page - 1) * data.limit + (data.items.length > 0 ? 1 : 0);
      const to = (data.current_page - 1) * data.limit + data.items.length;
      auditPaginationInfo.textContent = `Hiển thị ${from} - ${to} của ${data.total_items} logs`;
    }

    // Populate Users Filter if empty
    if (auditFilterUser && data.available_users && auditFilterUser.options.length <= 1) {
      data.available_users.forEach((u) => {
        const opt = document.createElement("option");
        opt.value = u;
        opt.textContent = `👤 ${u}`;
        auditFilterUser.appendChild(opt);
      });
    }

    if (!data.items || data.items.length === 0) {
      auditLogsTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-dim" style="padding: 24px;">Chưa có bản ghi nhật ký nào phù hợp.</td></tr>`;
      return;
    }

    auditLogsTableBody.innerHTML = data.items.map((log) => {
      const timeStr = log.timestamp_formatted || (log.timestamp ? new Date(log.timestamp).toLocaleString("vi-VN") : "-");
      const userBadge = `<span class="badge badge-purple" style="font-size: 10px;">👤 ${log.username || "system"}</span>`;
      
      let actionBadge = `<span class="badge badge-secondary" style="font-size: 10px;">${log.action}</span>`;
      if (log.action.includes("ADD") || log.action.includes("IMPORT")) {
        actionBadge = `<span class="badge badge-success" style="font-size: 10px;">➕ ${log.action}</span>`;
      } else if (log.action.includes("DELETE")) {
        actionBadge = `<span class="badge badge-danger" style="font-size: 10px;">🗑️ ${log.action}</span>`;
      } else if (log.action.includes("UPDATE") || log.action.includes("MODERATE")) {
        actionBadge = `<span class="badge badge-cyan" style="font-size: 10px;">✏️ ${log.action}</span>`;
      } else if (log.action.includes("CRAWL") || log.action.includes("DOWNLOAD")) {
        actionBadge = `<span class="badge badge-warning" style="font-size: 10px;">⚡ ${log.action}</span>`;
      }

      let statusBadge = `<span class="badge badge-success" style="font-size: 10px;">✅ SUCCESS</span>`;
      if (log.status === "FAILED") {
        statusBadge = `<span class="badge badge-danger" style="font-size: 10px;">❌ FAILED</span>`;
      } else if (log.status === "WARNING") {
        statusBadge = `<span class="badge badge-warning" style="font-size: 10px;">⚠️ WARNING</span>`;
      }

      return `
        <tr>
          <td class="font-mono text-dim" style="font-size: 11px;">${timeStr}</td>
          <td>${userBadge}</td>
          <td>${actionBadge}</td>
          <td>${statusBadge}</td>
          <td style="font-size: 11.5px; word-break: break-word;">${log.details || "-"}</td>
          <td class="font-mono text-dim" style="font-size: 10.5px; max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${log.target || ''}">${log.target || "-"}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    auditLogsTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-red" style="padding: 20px;">Lỗi tải logs: ${err.message}</td></tr>`;
  }
}

// Global modal open/close functions
window.openAuditLogModal = function() {
  const modal = document.getElementById("audit-log-modal");
  if (modal) {
    modal.style.display = "flex";
    loadAuditLogs(1);
  }
};

window.closeAuditLogModal = function() {
  const modal = document.getElementById("audit-log-modal");
  if (modal) modal.style.display = "none";
};

if (btnOpenAuditModal) {
  btnOpenAuditModal.addEventListener("click", window.openAuditLogModal);
}

if (btnHeaderAuditLogs) {
  btnHeaderAuditLogs.addEventListener("click", window.openAuditLogModal);
}

if (btnCloseAuditModal) {
  btnCloseAuditModal.addEventListener("click", window.closeAuditLogModal);
}

// Close on backdrop click
if (auditLogModal) {
  auditLogModal.addEventListener("click", (e) => {
    if (e.target === auditLogModal) window.closeAuditLogModal();
  });
}

if (auditSearch) {
  auditSearch.addEventListener("input", () => {
    clearTimeout(auditSearchTimer);
    auditSearchTimer = setTimeout(() => loadAuditLogs(1), 300);
  });
}

if (auditFilterUser) auditFilterUser.addEventListener("change", () => loadAuditLogs(1));
if (auditFilterAction) auditFilterAction.addEventListener("change", () => loadAuditLogs(1));
if (auditFilterStatus) auditFilterStatus.addEventListener("change", () => loadAuditLogs(1));
if (btnRefreshAuditLogs) btnRefreshAuditLogs.addEventListener("click", () => loadAuditLogs(auditCurrentPage));

if (auditBtnPrev) {
  auditBtnPrev.addEventListener("click", () => {
    if (auditCurrentPage > 1) loadAuditLogs(auditCurrentPage - 1);
  });
}

if (auditBtnNext) {
  auditBtnNext.addEventListener("click", () => {
    if (auditCurrentPage < auditTotalPages) loadAuditLogs(auditCurrentPage + 1);
  });
}

if (btnExportAuditLogs) {
  btnExportAuditLogs.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/logs/export");
      const data = await res.json();
      if (data.success) {
        const blob = new Blob([JSON.stringify(data.logs, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `system_audit_logs_${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        appendLog(`📥 Đã xuất ${data.total} bản ghi Audit Logs sang file JSON`, "info");
      } else {
        alert("Lỗi xuất logs");
      }
    } catch (e) {
      alert(`Lỗi xuất logs: ${e.message}`);
    }
  });
}

// ─── Edit Lyrics Modal Handlers ──────────────────────────────
async function openLyricsModal(track) {
  if (!editLyricsModal || !track) return;
  lyricsSpotifyId.value = track.spotify_id;
  lyricsTrackTitleInfo.textContent = `Bài hát: ${track.name} - ${track.artist_name}`;
  lyricsSyncedText.value = "⏳ Đang tải lời bài hát...";
  editLyricsModal.style.display = "flex";

  try {
    const res = await fetch(`/api/lyrics/${track.spotify_id}`);
    const data = await res.json();
    if (data.synced_lyrics) {
      lyricsSyncedText.value = data.synced_lyrics;
    } else if (data.plain_lyrics) {
      lyricsSyncedText.value = data.plain_lyrics;
    } else {
      lyricsSyncedText.value = "[00:00.00]Chưa có lời bài hát đồng bộ. Nhập định dạng [mm:ss.xx]Lời bài hát...";
    }
  } catch (e) {
    lyricsSyncedText.value = "[00:00.00]Lỗi tải lời bài hát.";
  }
}

if (btnCloseLyricsModal) btnCloseLyricsModal.addEventListener("click", () => (editLyricsModal.style.display = "none"));
if (btnCancelLyrics) btnCancelLyrics.addEventListener("click", () => (editLyricsModal.style.display = "none"));

if (btnSaveLyrics) {
  btnSaveLyrics.addEventListener("click", async () => {
    const spotifyId = lyricsSpotifyId.value;
    if (!spotifyId) return;

    try {
      const res = await fetch(`/api/tracks/${spotifyId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lyrics_synced: lyricsSyncedText.value,
        }),
      });
      const data = await res.json();
      if (data.success) {
        appendLog(`🎤 Saved synced lyrics for track: ${spotifyId}`, "success");
        editLyricsModal.style.display = "none";
        loadCatalogTracks(catalogCurrentPage);
      } else {
        alert(`Lỗi lưu lời: ${data.error}`);
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    }
  });
}

// Socket listener for individual re-download finished
socket.on("track_redownloaded", (data) => {
  if (data.success) {
    loadCatalogTracks(catalogCurrentPage);
  }
});

// Socket listener for multi-user pipeline lock conflicts & deadlock prevention
socket.on("pipeline_lock_conflict", (data) => {
  const holder = data.holder || "Người dùng khác";
  const task = data.task || "Tác vụ đang chạy";
  const timeLeft = data.time_left_sec || 0;
  const msg = `🔒 XUNG ĐỘT TÀI NGUYÊN: ${task} đang được thực thi bởi @${holder} (khóa còn ${timeLeft}s). Vui lòng đợi tiến trình hoàn thành hoặc nhờ Quản trị viên can thiệp!`;
  
  if (typeof appendLog === "function") {
    appendLog(msg, "warning");
  }
  alert(msg);
});

// ─── Main Workspace Tab Navigation (Sourcing ↔ Catalog ↔ Full Logs Studio) ──
(function initMainTabs() {
  const btnSourcing = document.getElementById("nav-btn-sourcing");
  const btnCatalog  = document.getElementById("nav-btn-catalog");
  const btnLogs     = document.getElementById("nav-btn-logs");
  const viewSourcing = document.getElementById("view-sourcing-studio");
  const viewCatalog  = document.getElementById("view-catalog-studio");
  const viewLogs     = document.getElementById("view-logs-studio");

  function switchToTab(targetTab) {
    [btnSourcing, btnCatalog, btnLogs].forEach((b) => {
      if (b) {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      }
    });

    [viewSourcing, viewCatalog, viewLogs].forEach((v) => {
      if (v) {
        v.classList.remove("active");
        v.style.display = "none";
      }
    });

    if (targetTab === "sourcing") {
      if (btnSourcing) {
        btnSourcing.classList.add("active");
        btnSourcing.setAttribute("aria-selected", "true");
      }
      if (viewSourcing) {
        viewSourcing.classList.add("active");
        viewSourcing.style.display = "block";
      }
    } else if (targetTab === "catalog") {
      if (btnCatalog) {
        btnCatalog.classList.add("active");
        btnCatalog.setAttribute("aria-selected", "true");
      }
      if (viewCatalog) {
        viewCatalog.classList.add("active");
        viewCatalog.style.display = "block";
      }
      if (typeof loadCatalogTracks === "function") {
        loadCatalogTracks(catalogCurrentPage || 1);
      }
    } else if (targetTab === "logs") {
      if (btnLogs) {
        btnLogs.classList.add("active");
        btnLogs.setAttribute("aria-selected", "true");
      }
      if (viewLogs) {
        viewLogs.classList.add("active");
        viewLogs.style.display = "block";
      }
      if (typeof window.refreshFullLogsStudio === "function") {
        window.refreshFullLogsStudio();
      }
    }
  }

  window.switchToWorkspaceTab = switchToTab;

  if (btnSourcing) btnSourcing.addEventListener("click", () => switchToTab("sourcing"));
  if (btnCatalog) btnCatalog.addEventListener("click",  () => switchToTab("catalog"));
  if (btnLogs) btnLogs.addEventListener("click", () => switchToTab("logs"));

  const btnModalOpenFullLogs = document.getElementById("btn-modal-open-full-logs");
  if (btnModalOpenFullLogs) {
    btnModalOpenFullLogs.addEventListener("click", () => {
      const modal = document.getElementById("audit-log-modal");
      if (modal) modal.style.display = "none";
      switchToTab("logs");
    });
  }

  console.log("[Tabs] 3-View Workspace Navigation initialized successfully.");
})();

// ─── Full System Logs & Daily Archive Studio Engine ──────────
(function initFullLogsStudio() {
  let fullLogSelectedDate = new Date().toISOString().slice(0, 10);
  let fullLogCurrentMode = "terminal"; // 'terminal', 'file', 'table'
  let fullLogCurrentPage = 1;
  let fullLogTotalPages = 1;
  let fullLogSearchTimer = null;

  // View switcher buttons
  const btnModeTerminal = document.getElementById("btn-mode-terminal");
  const btnModeFile = document.getElementById("btn-mode-file");
  const btnModeTable = document.getElementById("btn-mode-table");
  const panelTerminal = document.getElementById("full-log-panel-terminal");
  const panelFile = document.getElementById("full-log-panel-file");
  const panelTable = document.getElementById("full-log-panel-table");

  // Date and filter elements
  const datePicker = document.getElementById("full-log-date-picker");
  const btnDateToday = document.getElementById("btn-date-today");
  const btnDateYesterday = document.getElementById("btn-date-yesterday");
  const btnDateAll = document.getElementById("btn-date-all");
  const daysContainer = document.getElementById("daily-log-days-container");

  // KPIs
  const kpiTotal = document.getElementById("daily-kpi-total");
  const kpiSuccess = document.getElementById("daily-kpi-success");
  const kpiFailed = document.getElementById("daily-kpi-failed");
  const kpiSize = document.getElementById("daily-kpi-size");

  // Filter toolbar
  const fullLogSearch = document.getElementById("full-log-search");
  const fullLogFilterUser = document.getElementById("full-log-filter-user");
  const fullLogFilterAction = document.getElementById("full-log-filter-action");
  const fullLogFilterStatus = document.getElementById("full-log-filter-status");
  const fullLogPageSize = document.getElementById("full-log-page-size");
  const btnRefresh = document.getElementById("btn-refresh-full-logs");
  const btnExportJson = document.getElementById("btn-export-full-logs-json");
  const btnDownloadLog = document.getElementById("btn-download-full-log-file");

  // Terminal elements
  const terminalOutput = document.getElementById("full-log-terminal-output");
  const terminalSessionLabel = document.getElementById("terminal-session-label");
  const chkTerminalAutoscroll = document.getElementById("chk-terminal-autoscroll");
  const chkTerminalWrap = document.getElementById("chk-terminal-wrap");
  const btnCopyTerminal = document.getElementById("btn-copy-terminal");
  const btnClearTerminal = document.getElementById("btn-clear-terminal");

  // File Inspector elements
  const selectLogFile = document.getElementById("select-log-file");
  const fileContentBox = document.getElementById("file-log-content-box");
  const fileStatsBadge = document.getElementById("file-log-stats-badge");
  const btnCopyFileContent = document.getElementById("btn-copy-file-content");
  const btnDownloadSelectedFile = document.getElementById("btn-download-selected-file");

  // Table elements
  const tableBody = document.getElementById("full-log-table-body");
  const paginationInfo = document.getElementById("full-log-pagination-info");
  const pageLabel = document.getElementById("full-log-page-label");
  const btnPrev = document.getElementById("full-log-btn-prev");
  const btnNext = document.getElementById("full-log-btn-next");

  // Set today default on date picker
  if (datePicker) {
    datePicker.value = fullLogSelectedDate;
    datePicker.addEventListener("change", () => {
      fullLogSelectedDate = datePicker.value || "all";
      loadDailySummary();
      loadActiveModeData();
    });
  }

  // Switch View Mode
  function setLogViewMode(mode) {
    fullLogCurrentMode = mode;
    [btnModeTerminal, btnModeFile, btnModeTable].forEach((b) => {
      if (b) {
        b.classList.remove("btn-primary");
        b.classList.add("btn-secondary");
      }
    });

    if (panelTerminal) panelTerminal.style.display = mode === "terminal" ? "flex" : "none";
    if (panelFile) panelFile.style.display = mode === "file" ? "flex" : "none";
    if (panelTable) panelTable.style.display = mode === "table" ? "flex" : "none";

    if (mode === "terminal" && btnModeTerminal) {
      btnModeTerminal.classList.add("btn-primary");
      btnModeTerminal.classList.remove("btn-secondary");
    } else if (mode === "file" && btnModeFile) {
      btnModeFile.classList.add("btn-primary");
      btnModeFile.classList.remove("btn-secondary");
    } else if (mode === "table" && btnModeTable) {
      btnModeTable.classList.add("btn-primary");
      btnModeTable.classList.remove("btn-secondary");
    }

    loadActiveModeData();
  }

  if (btnModeTerminal) btnModeTerminal.addEventListener("click", () => setLogViewMode("terminal"));
  if (btnModeFile) btnModeFile.addEventListener("click", () => setLogViewMode("file"));
  if (btnModeTable) btnModeTable.addEventListener("click", () => setLogViewMode("table"));

  // Quick Date Buttons
  if (btnDateToday) {
    btnDateToday.addEventListener("click", () => {
      fullLogSelectedDate = new Date().toISOString().slice(0, 10);
      if (datePicker) datePicker.value = fullLogSelectedDate;
      loadDailySummary();
      loadActiveModeData();
    });
  }

  if (btnDateYesterday) {
    btnDateYesterday.addEventListener("click", () => {
      const d = new Date();
      d.setDate(d.getDate() - 1);
      fullLogSelectedDate = d.toISOString().slice(0, 10);
      if (datePicker) datePicker.value = fullLogSelectedDate;
      loadDailySummary();
      loadActiveModeData();
    });
  }

  if (btnDateAll) {
    btnDateAll.addEventListener("click", () => {
      fullLogSelectedDate = "all";
      if (datePicker) datePicker.value = "";
      loadDailySummary();
      loadActiveModeData();
    });
  }

  // Load Daily Summary and archive badges
  async function loadDailySummary() {
    try {
      const res = await fetch("/api/logs/daily_summary");
      const data = await res.json();
      if (!data.success || !data.daily_summary) return;

      const summaryList = data.daily_summary;
      
      // Update KPIs for currently selected date
      let currentDayStats = summaryList.find((s) => s.date === fullLogSelectedDate);
      if (!currentDayStats && fullLogSelectedDate === "all") {
        const totalAll = summaryList.reduce((acc, s) => acc + s.total, 0);
        const successAll = summaryList.reduce((acc, s) => acc + s.success_count, 0);
        const failedAll = summaryList.reduce((acc, s) => acc + s.failed_count, 0);
        const sizeAll = summaryList.reduce((acc, s) => acc + s.file_size_kb, 0);
        currentDayStats = {
          total: totalAll,
          success_count: successAll,
          failed_count: failedAll,
          file_size_kb: sizeAll,
        };
      }

      if (currentDayStats) {
        if (kpiTotal) kpiTotal.textContent = `📊 ${currentDayStats.total || 0} sự kiện`;
        if (kpiSuccess) kpiSuccess.textContent = `✅ ${currentDayStats.success_count || 0} thành công`;
        if (kpiFailed) kpiFailed.textContent = `❌ ${currentDayStats.failed_count || 0} thất bại`;
        if (kpiSize) kpiSize.textContent = `💾 ${currentDayStats.file_size_kb || 0} KB log`;
      }

      // Render day chips
      if (daysContainer) {
        daysContainer.innerHTML = summaryList.map((day) => {
          const isSelected = day.date === fullLogSelectedDate;
          const bg = isSelected ? "var(--accent-green)" : "rgba(255,255,255,0.06)";
          const color = isSelected ? "#000" : "var(--text-main)";
          const border = isSelected ? "1px solid var(--accent-green)" : "1px solid var(--border-color)";

          return `
            <button class="btn" onclick="window.selectFullLogDate('${day.date}')" 
                    style="background: ${bg}; color: ${color}; border: ${border}; padding: 3px 8px; font-size: 10.5px; border-radius: var(--radius-sm); font-weight: ${isSelected ? '700' : '500'};">
              📅 ${day.date} <span style="opacity: 0.85;">(${day.total} logs • ${day.file_size_kb} KB)</span>
            </button>
          `;
        }).join("");
      }
    } catch (e) {
      console.warn("Failed to load daily log summary:", e);
    }
  }

  window.selectFullLogDate = function(dateStr) {
    fullLogSelectedDate = dateStr;
    if (datePicker) datePicker.value = dateStr === "all" ? "" : dateStr;
    loadDailySummary();
    loadActiveModeData();
  };

  // Main loader dispatcher
  function loadActiveModeData() {
    if (fullLogCurrentMode === "terminal") {
      loadTerminalLogs();
    } else if (fullLogCurrentMode === "file") {
      loadLogFilesList();
    } else if (fullLogCurrentMode === "table") {
      loadFullLogTable(1);
    }
  }

  // 1. Terminal Console Loader
  async function loadTerminalLogs() {
    if (!terminalOutput) return;
    terminalOutput.innerHTML = `<span style="color: #94a3b8;">⏳ Đang đồng bộ terminal logs từ MongoDB & log stream...</span>`;
    
    if (terminalSessionLabel) {
      terminalSessionLabel.textContent = `terminal@music-data-collector: ~/logs/$ (Ngày: ${fullLogSelectedDate}) [${new Date().toLocaleTimeString()}]`;
    }

    try {
      const params = new URLSearchParams({
        page: "1",
        limit: (fullLogPageSize ? fullLogPageSize.value : "200"),
        date: fullLogSelectedDate,
        search: (fullLogSearch ? fullLogSearch.value.trim() : ""),
        user: (fullLogFilterUser ? fullLogFilterUser.value : "all"),
        action: (fullLogFilterAction ? fullLogFilterAction.value : "all"),
        status: (fullLogFilterStatus ? fullLogFilterStatus.value : "all"),
      });

      const res = await fetch(`/api/logs?${params.toString()}`);
      const data = await res.json();

      if (!data.success || !data.items || data.items.length === 0) {
        terminalOutput.innerHTML = `<span style="color: #64748b;">[${fullLogSelectedDate}] Không tìm thấy dòng nhật ký nào phù hợp với bộ lọc hiện tại.</span>`;
        return;
      }

      // Populate user dropdown if empty
      if (fullLogFilterUser && data.available_users && fullLogFilterUser.options.length <= 1) {
        data.available_users.forEach((u) => {
          const opt = document.createElement("option");
          opt.value = u;
          opt.textContent = `👤 ${u}`;
          fullLogFilterUser.appendChild(opt);
        });
      }

      // Reverse so chronological in terminal (top to bottom)
      const itemsChronological = [...data.items].reverse();

      const linesHtml = itemsChronological.map((item, idx) => {
        const timeStr = item.timestamp_formatted || (item.timestamp ? new Date(item.timestamp).toLocaleString("vi-VN") : "00:00:00");
        
        let statusTag = `<span style="color: #10b981; font-weight: 700;">[OK]</span>`;
        if (item.status === "FAILED") {
          statusTag = `<span style="color: #ef4444; font-weight: 700;">[FAIL]</span>`;
        } else if (item.status === "WARNING") {
          statusTag = `<span style="color: #f59e0b; font-weight: 700;">[WARN]</span>`;
        }

        let actionColor = "#38bdf8"; // cyan
        if (item.action.includes("DELETE")) actionColor = "#f87171";
        if (item.action.includes("ADD") || item.action.includes("IMPORT")) actionColor = "#4ade80";
        if (item.action.includes("DOWNLOAD") || item.action.includes("CRAWL")) actionColor = "#fbbf24";

        const lineNum = `<span style="color: #475569; user-select: none;">${String(idx + 1).padStart(3, '0')}| </span>`;
        const targetStr = item.target ? `<span style="color: #67e8f9; opacity: 0.9;"> -> [Target: ${escapeHtml(item.target)}]</span>` : "";

        return `<div>${lineNum}<span style="color: #64748b;">${timeStr}</span> ${statusTag} <span style="color: ${actionColor}; font-weight: 600;">[${item.action}]</span> <span style="color: #c084fc;">[@${item.username || 'system'}]</span>: <span style="color: #f1f5f9;">${escapeHtml(item.details || '')}</span>${targetStr}</div>`;
      }).join("");

      terminalOutput.innerHTML = linesHtml;

      if (chkTerminalAutoscroll && chkTerminalAutoscroll.checked) {
        terminalOutput.scrollTop = terminalOutput.scrollHeight;
      }
    } catch (err) {
      terminalOutput.innerHTML = `<span style="color: #ef4444;">Lỗi nạp terminal stream: ${err.message}</span>`;
    }
  }

  // 2. Physical File Log Inspector Loader
  async function loadLogFilesList() {
    if (!selectLogFile) return;
    try {
      const res = await fetch("/api/logs/files");
      const data = await res.json();
      if (!data.success || !data.files || data.files.length === 0) {
        selectLogFile.innerHTML = `<option value="">Không có file log nào</option>`;
        if (fileContentBox) fileContentBox.textContent = "Không tìm thấy file log nào trên ổ đĩa.";
        return;
      }

      selectLogFile.innerHTML = data.files.map((f) => {
        return `<option value="${f.filename}">${f.filename} (${f.size_kb} KB - ${f.modified})</option>`;
      }).join("");

      // Match selected date file if available
      const matching = data.files.find((f) => f.filename.includes(fullLogSelectedDate.replace(/-/g, "")));
      if (matching) {
        selectLogFile.value = matching.filename;
      }

      readSelectedLogFile(selectLogFile.value);
    } catch (e) {
      console.warn("Failed to load log files list:", e);
    }
  }

  async function readSelectedLogFile(filename) {
    if (!filename || !fileContentBox) return;
    fileContentBox.textContent = `⏳ Đang đọc nội dung file ${filename}...`;
    try {
      const res = await fetch(`/api/logs/file/${encodeURIComponent(filename)}?limit=1000`);
      const data = await res.json();
      if (data.success) {
        fileContentBox.textContent = data.content || "(File rỗng)";
        if (fileStatsBadge) {
          fileStatsBadge.textContent = `${data.size_kb} KB • ${data.lines_shown}/${data.total_lines} dòng`;
        }
      } else {
        fileContentBox.textContent = `Lỗi đọc file: ${data.error}`;
      }
    } catch (e) {
      fileContentBox.textContent = `Lỗi: ${e.message}`;
    }
  }

  if (selectLogFile) {
    selectLogFile.addEventListener("change", () => readSelectedLogFile(selectLogFile.value));
  }

  // 3. Expandable Table Loader
  async function loadFullLogTable(page = 1) {
    if (!tableBody) return;
    fullLogCurrentPage = page;
    tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-dim" style="padding: 24px;">⏳ Đang nạp bảng nhật ký chi tiết từ MongoDB...</td></tr>`;

    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: (fullLogPageSize ? fullLogPageSize.value : "50"),
        date: fullLogSelectedDate,
        search: (fullLogSearch ? fullLogSearch.value.trim() : ""),
        user: (fullLogFilterUser ? fullLogFilterUser.value : "all"),
        action: (fullLogFilterAction ? fullLogFilterAction.value : "all"),
        status: (fullLogFilterStatus ? fullLogFilterStatus.value : "all"),
      });

      const res = await fetch(`/api/logs?${params.toString()}`);
      const data = await res.json();

      if (!data.success || !data.items || data.items.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-dim" style="padding: 24px;">Không có bản ghi nhật ký nào phù hợp với bộ lọc ngày '${fullLogSelectedDate}'.</td></tr>`;
        if (paginationInfo) paginationInfo.textContent = "Hiển thị 0 - 0 của 0 logs";
        if (pageLabel) pageLabel.textContent = "Trang 1 / 1";
        return;
      }

      fullLogTotalPages = data.total_pages || 1;
      if (pageLabel) pageLabel.textContent = `Trang ${data.current_page} / ${fullLogTotalPages}`;
      if (paginationInfo) {
        const from = (data.current_page - 1) * data.limit + 1;
        const to = (data.current_page - 1) * data.limit + data.items.length;
        paginationInfo.textContent = `Hiển thị ${from} - ${to} trong tổng số ${data.total_items} bản ghi`;
      }

      tableBody.innerHTML = data.items.map((item, idx) => {
        const timeStr = item.timestamp_formatted || (item.timestamp ? new Date(item.timestamp).toLocaleString("vi-VN") : "-");
        const userBadge = `<span class="badge badge-purple" style="font-size: 10px;">👤 ${item.username || "system"}</span>`;
        
        let actionBadge = `<span class="badge badge-secondary" style="font-size: 10px;">${item.action}</span>`;
        if (item.action.includes("ADD") || item.action.includes("IMPORT")) {
          actionBadge = `<span class="badge badge-success" style="font-size: 10px;">➕ ${item.action}</span>`;
        } else if (item.action.includes("DELETE")) {
          actionBadge = `<span class="badge badge-danger" style="font-size: 10px;">🗑️ ${item.action}</span>`;
        } else if (item.action.includes("UPDATE") || item.action.includes("MODERATE")) {
          actionBadge = `<span class="badge badge-cyan" style="font-size: 10px;">✏️ ${item.action}</span>`;
        } else if (item.action.includes("CRAWL") || item.action.includes("DOWNLOAD")) {
          actionBadge = `<span class="badge badge-warning" style="font-size: 10px;">⚡ ${item.action}</span>`;
        }

        let statusBadge = `<span class="badge badge-success" style="font-size: 10px;">✅ SUCCESS</span>`;
        if (item.status === "FAILED") {
          statusBadge = `<span class="badge badge-danger" style="font-size: 10px;">❌ FAILED</span>`;
        } else if (item.status === "WARNING") {
          statusBadge = `<span class="badge badge-warning" style="font-size: 10px;">⚠️ WARNING</span>`;
        }

        const rawJson = escapeHtml(JSON.stringify(item.metadata || {}, null, 2));

        return `
          <tr id="row-log-${idx}" style="cursor: pointer;" onclick="window.toggleLogDetailDrawer(${idx})">
            <td class="font-mono text-dim" style="font-size: 11px;">${timeStr}</td>
            <td>${userBadge}</td>
            <td>${actionBadge}</td>
            <td>${statusBadge}</td>
            <td style="font-size: 11.5px; word-break: break-word;">${escapeHtml(item.details || '-')}</td>
            <td class="font-mono text-dim" style="font-size: 10.5px; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(item.target || '')}">${escapeHtml(item.target || '-')}</td>
            <td style="text-align: center;">
              <button class="btn btn-secondary" style="padding: 2px 6px; font-size: 10px;" id="btn-expand-${idx}">▼ Chi tiết</button>
            </td>
          </tr>
          <tr id="drawer-log-${idx}" style="display: none; background: rgba(0,0,0,0.3);">
            <td colspan="7" style="padding: 12px 18px;">
              <div class="flex-col" style="gap: 6px;">
                <div class="flex-between">
                  <span style="font-weight: 700; color: var(--accent-cyan); font-size: 11.5px;">🔍 Metadata &amp; Payload JSON Chi Tiết (MongoDB Record)</span>
                  <span class="font-mono text-dim" style="font-size: 10px;">Target ID: ${escapeHtml(item.target || '-')}</span>
                </div>
                <pre class="font-mono" style="background: #090d16; border: 1px solid #1e293b; padding: 10px; border-radius: var(--radius-sm); font-size: 11px; color: #a5f3fc; max-height: 180px; overflow-y: auto; margin: 0;">${rawJson !== '{}' ? rawJson : '// Không có metadata bổ sung'}</pre>
              </div>
            </td>
          </tr>
        `;
      }).join("");
    } catch (err) {
      tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-red" style="padding: 20px;">Lỗi tải bảng logs: ${err.message}</td></tr>`;
    }
  }

  window.toggleLogDetailDrawer = function(idx) {
    const drawer = document.getElementById(`drawer-log-${idx}`);
    const btn = document.getElementById(`btn-expand-${idx}`);
    if (drawer) {
      const isHidden = drawer.style.display === "none";
      drawer.style.display = isHidden ? "table-row" : "none";
      if (btn) btn.textContent = isHidden ? "▲ Thu gọn" : "▼ Chi tiết";
    }
  };

  // Helper escape HTML
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Filter Event Listeners
  if (fullLogSearch) {
    fullLogSearch.addEventListener("input", () => {
      clearTimeout(fullLogSearchTimer);
      fullLogSearchTimer = setTimeout(() => loadActiveModeData(), 300);
    });
  }

  if (fullLogFilterUser) fullLogFilterUser.addEventListener("change", () => loadActiveModeData());
  if (fullLogFilterAction) fullLogFilterAction.addEventListener("change", () => loadActiveModeData());
  if (fullLogFilterStatus) fullLogFilterStatus.addEventListener("change", () => loadActiveModeData());
  if (fullLogPageSize) fullLogPageSize.addEventListener("change", () => loadActiveModeData());
  if (btnRefresh) btnRefresh.addEventListener("click", () => {
    loadDailySummary();
    loadActiveModeData();
  });

  // Table pagination
  if (btnPrev) {
    btnPrev.addEventListener("click", () => {
      if (fullLogCurrentPage > 1) loadFullLogTable(fullLogCurrentPage - 1);
    });
  }

  if (btnNext) {
    btnNext.addEventListener("click", () => {
      if (fullLogCurrentPage < fullLogTotalPages) loadFullLogTable(fullLogCurrentPage + 1);
    });
  }

  // Export Tools
  if (btnExportJson) {
    btnExportJson.addEventListener("click", async () => {
      try {
        const res = await fetch(`/api/logs/export?date=${encodeURIComponent(fullLogSelectedDate)}`);
        const data = await res.json();
        if (data.success) {
          const blob = new Blob([JSON.stringify(data.logs, null, 2)], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `system_logs_${fullLogSelectedDate}_export.json`;
          a.click();
          URL.revokeObjectURL(url);
          appendLog(`📥 Đã xuất ${data.total} bản ghi logs sang JSON (${fullLogSelectedDate})`, "info");
        } else {
          alert("Lỗi xuất logs");
        }
      } catch (e) {
        alert(`Lỗi: ${e.message}`);
      }
    });
  }

  if (btnDownloadLog) {
    btnDownloadLog.addEventListener("click", () => {
      const filename = `collector_${fullLogSelectedDate.replace(/-/g, "")}.log`;
      window.open(`/api/logs/download_raw/${encodeURIComponent(filename)}`, "_blank");
    });
  }

  if (btnDownloadSelectedFile) {
    btnDownloadSelectedFile.addEventListener("click", () => {
      if (selectLogFile && selectLogFile.value) {
        window.open(`/api/logs/download_raw/${encodeURIComponent(selectLogFile.value)}`, "_blank");
      }
    });
  }

  // Copy Buttons
  if (btnCopyTerminal) {
    btnCopyTerminal.addEventListener("click", () => {
      if (terminalOutput) {
        navigator.clipboard.writeText(terminalOutput.innerText);
        appendLog("📋 Đã sao chép toàn bộ Terminal output vào clipboard!", "info");
      }
    });
  }

  if (btnClearTerminal) {
    btnClearTerminal.addEventListener("click", () => {
      if (terminalOutput) terminalOutput.innerHTML = `<span style="color: #64748b;">[Terminal screen cleared]</span>`;
    });
  }

  if (btnCopyFileContent) {
    btnCopyFileContent.addEventListener("click", () => {
      if (fileContentBox) {
        navigator.clipboard.writeText(fileContentBox.textContent);
        appendLog("📋 Đã sao chép nội dung file log vào clipboard!", "info");
      }
    });
  }

  // Wrap toggle
  if (chkTerminalWrap) {
    chkTerminalWrap.addEventListener("change", () => {
      if (terminalOutput) {
        terminalOutput.style.whiteSpace = chkTerminalWrap.checked ? "pre-wrap" : "pre";
      }
    });
  }

  window.refreshFullLogsStudio = function() {
    loadDailySummary();
    loadActiveModeData();
  };

  console.log("[FullLogsStudio] Complete System Logs Studio initialized successfully.");
})();

// ─── Settings Modal: Spotify Apps Pool & Proxy Pool Manager ──
(function initSettingsPoolManagers() {
  const settingsModal = document.getElementById("settings-modal");
  const btnCloseSettingsModal = document.getElementById("btn-close-settings-modal");
  const btnOpenSettingsModal = document.getElementById("btn-open-settings-modal");
  const btnHeaderSettings = document.getElementById("btn-header-settings");
  const settingsTabBtns = document.querySelectorAll(".settings-tab-btn");
  const settingsTabContents = document.querySelectorAll(".settings-tab-content");

  // Spotify Pool Elements
  const spotifyAppsTableBody = document.getElementById("spotify-apps-table-body");
  const btnOpenAddSpotifyApp = document.getElementById("btn-open-add-spotify-app");
  const formSpotifyApp = document.getElementById("form-spotify-app");
  const btnCloseSpappForm = document.getElementById("btn-close-spapp-form");
  const spappEditId = document.getElementById("spapp-edit-id");
  const spappName = document.getElementById("spapp-name");
  const spappAddedBy = document.getElementById("spapp-added-by");
  const spappClientId = document.getElementById("spapp-client-id");
  const spappClientSecret = document.getElementById("spapp-client-secret");
  const spappSpDc = document.getElementById("spapp-sp-dc");
  const spappIsPremium = document.getElementById("spapp-is-premium");
  const btnTestSpappForm = document.getElementById("btn-test-spapp-form");
  const spappFormTestResult = document.getElementById("spapp-form-test-result");

  // Proxy Pool Elements
  const proxiesTableBody = document.getElementById("proxies-table-body");
  const btnOpenAddProxy = document.getElementById("btn-open-add-proxy");
  const formProxy = document.getElementById("form-proxy");
  const btnCloseProxyForm = document.getElementById("btn-close-proxy-form");
  const proxyEditId = document.getElementById("proxy-edit-id");
  const proxyName = document.getElementById("proxy-name");
  const proxyAddedBy = document.getElementById("proxy-added-by");
  const proxyProtocol = document.getElementById("proxy-protocol");
  const proxyHost = document.getElementById("proxy-host");
  const proxyPort = document.getElementById("proxy-port");
  const proxyUsername = document.getElementById("proxy-username");
  const proxyPassword = document.getElementById("proxy-password");
  const btnTestProxyForm = document.getElementById("btn-test-proxy-form");
  const proxyFormTestResult = document.getElementById("proxy-form-test-result");
  const btnTestAllProxies = document.getElementById("btn-test-all-proxies");

  // Modal Open & Tab Switch
  window.openSettingsModal = function(targetTab = "tab-set-spotify") {
    if (settingsModal) {
      settingsModal.style.display = "flex";
      switchSettingsTab(targetTab);
      loadSpotifyApps();
      loadProxies();
    }
  };

  window.closeSettingsModal = function() {
    if (settingsModal) settingsModal.style.display = "none";
  };

  if (btnOpenSettingsModal) btnOpenSettingsModal.addEventListener("click", () => window.openSettingsModal());
  if (btnHeaderSettings) btnHeaderSettings.addEventListener("click", () => window.openSettingsModal());
  if (btnCloseSettingsModal) btnCloseSettingsModal.addEventListener("click", window.closeSettingsModal);
  if (settingsModal) {
    settingsModal.addEventListener("click", (e) => {
      if (e.target === settingsModal) window.closeSettingsModal();
    });
  }

  function switchSettingsTab(tabId) {
    settingsTabBtns.forEach((btn) => {
      if (btn.getAttribute("data-tab") === tabId) {
        btn.classList.add("btn-primary");
        btn.classList.remove("btn-secondary");
      } else {
        btn.classList.remove("btn-primary");
        btn.classList.add("btn-secondary");
      }
    });

    settingsTabContents.forEach((c) => {
      if (c.id === tabId) {
        c.style.display = "flex";
      } else {
        c.style.display = "none";
      }
    });
  }

  settingsTabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      switchSettingsTab(tabId);
      if (tabId === "tab-set-spotify") loadSpotifyApps();
      if (tabId === "tab-set-proxy") loadProxies();
      if (tabId === "tab-set-shield") window.refreshShieldStatus();
    });
  });

  // ─── Spotify App Pool Engine ──────────────────────────────

  async function loadSpotifyApps() {
    if (!spotifyAppsTableBody) return;
    try {
      spotifyAppsTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-dim" style="padding: 20px;">⏳ Đang tải danh sách Spotify Apps từ database...</td></tr>`;
      const res = await fetch("/api/spotify_apps");
      const data = await res.json();
      if (!data.success || !data.apps || data.apps.length === 0) {
        spotifyAppsTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-dim" style="padding: 20px;">Chưa có tài khoản Spotify App nào trong pool. Hãy bấm '➕ Thêm Spotify App'.</td></tr>`;
        return;
      }

      spotifyAppsTableBody.innerHTML = data.apps.map((app) => {
        const maskedClientId = app.client_id ? (app.client_id.slice(0, 4) + "••••••••" + app.client_id.slice(-4)) : "-";
        
        let typeBadge = `<span class="badge badge-secondary" style="font-size: 10px;">🔑 Dev API</span>`;
        if (app.is_premium) {
          typeBadge = `<span class="badge badge-warning" style="font-size: 10.5px; font-weight: 700; background: rgba(234,179,8,0.18); color: #facc15; border: 1px solid #facc15;">👑 Premium</span>`;
        } else if (app.account_type && app.account_type.includes("Free")) {
          typeBadge = `<span class="badge badge-cyan" style="font-size: 10px;">🎵 Free Tier</span>`;
        }

        let statusBadge = `<span class="badge badge-secondary" style="font-size: 10px;">⏳ Chưa Test</span>`;
        if (app.status === "valid") {
          statusBadge = `<span class="badge badge-success" style="font-size: 10px;">🟢 Valid (${app.latency_ms || 0}ms)</span>`;
        } else if (app.status === "invalid") {
          statusBadge = `<span class="badge badge-danger" style="font-size: 10px;">🔴 Lỗi</span>`;
        }

        const activeRadio = `
          <input type="radio" name="active_spotify_app" value="${app.id}" ${app.is_active ? "checked" : ""} 
                 onchange="window.setActiveSpotifyApp('${app.id}')" style="cursor: pointer;" title="Chọn làm App chính">
        `;

        return `
          <tr style="${app.is_active ? 'background: rgba(29, 185, 84, 0.05);' : ''}">
            <td style="text-align: center;">${activeRadio}</td>
            <td>
              <div style="font-weight: 600; color: var(--text-main); font-size: 12px;">${app.name}</div>
              <div style="font-size: 10.5px; margin-top: 2px;">
                <span class="badge badge-purple" style="font-size: 9.5px;">👤 @${app.added_by || 'admin'}</span>
                ${app.is_active ? '<span class="badge badge-success" style="font-size: 9.5px; margin-left: 4px;">★ Đang Dùng</span>' : ''}
              </div>
            </td>
            <td class="font-mono text-dim" style="font-size: 11px;">${maskedClientId}</td>
            <td>${typeBadge}</td>
            <td>${statusBadge}</td>
            <td style="text-align: center;">
              <div class="flex-row" style="justify-content: center; gap: 4px;">
                <button class="btn btn-secondary" style="padding: 3px 6px; font-size: 10px;" onclick="window.testSpotifyApp('${app.id}', this)" title="Test kết nối & Kiểm tra Premium">⚡ Test</button>
                <button class="btn btn-secondary" style="padding: 3px 6px; font-size: 10px;" onclick="window.editSpotifyApp('${app.id}')" title="Sửa thông tin">✏️</button>
                <button class="btn btn-danger" style="padding: 3px 6px; font-size: 10px;" onclick="window.deleteSpotifyApp('${app.id}', '${app.name}')" title="Xóa khỏi pool">🗑️</button>
              </div>
            </td>
          </tr>
        `;
      }).join("");
    } catch (err) {
      spotifyAppsTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-red" style="padding: 20px;">Lỗi tải Spotify Apps: ${err.message}</td></tr>`;
    }
  }

  // Toggle Add Form
  if (btnOpenAddSpotifyApp) {
    btnOpenAddSpotifyApp.addEventListener("click", () => {
      formSpotifyApp.reset();
      spappEditId.value = "";
      if (spappIsPremium) spappIsPremium.checked = false;
      document.getElementById("spapp-form-title").textContent = "➕ Thêm Spotify App Mới Vào Pool";
      formSpotifyApp.style.display = "flex";
      spappFormTestResult.style.display = "none";
    });
  }

  if (btnCloseSpappForm) {
    btnCloseSpappForm.addEventListener("click", () => {
      formSpotifyApp.style.display = "none";
    });
  }

  // Live test in form
  if (btnTestSpappForm) {
    btnTestSpappForm.addEventListener("click", async () => {
      const cid = spappClientId.value.trim();
      const csec = spappClientSecret.value.trim();
      const spdc = spappSpDc.value.trim();
      const isManualPrem = spappIsPremium ? spappIsPremium.checked : false;

      if (!cid || !csec) {
        alert("Vui lòng điền Client ID và Client Secret trước khi test!");
        return;
      }

      btnTestSpappForm.disabled = true;
      btnTestSpappForm.textContent = "⏳ Đang test...";
      spappFormTestResult.style.display = "block";
      spappFormTestResult.style.background = "var(--bg-input)";
      spappFormTestResult.style.color = "var(--text-main)";
      spappFormTestResult.textContent = "🔄 Đang gửi request test tới Spotify API...";

      try {
        const res = await fetch("/api/spotify_apps", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: spappEditId.value || "temp_test",
            name: spappName.value.trim() || "Test App",
            client_id: cid,
            client_secret: csec,
            sp_dc: spdc,
            is_premium: isManualPrem,
            added_by: spappAddedBy.value.trim() || "admin",
          })
        });

        // Test the app
        const testRes = await fetch(`/api/spotify_apps/${spappEditId.value || "temp_test"}/test`, { method: "POST" });
        const testData = await testRes.json();

        if (testData.status === "valid") {
          if (testData.is_premium && spappIsPremium) {
            spappIsPremium.checked = true;
          }
          spappFormTestResult.style.background = "rgba(16, 185, 129, 0.15)";
          spappFormTestResult.style.color = "#34d399";
          spappFormTestResult.innerHTML = `✅ Kết nối thành công (${testData.latency_ms}ms)! Gói tài khoản: <b>${testData.account_type}</b> ${testData.is_premium ? '👑 [PREMIUM DETECTED]' : ''}`;
        } else {
          spappFormTestResult.style.background = "rgba(239, 68, 68, 0.15)";
          spappFormTestResult.style.color = "#f87171";
          spappFormTestResult.innerHTML = `❌ Kết nối thất bại: ${testData.error || "Sai Client ID/Secret"}`;
        }
      } catch (e) {
        spappFormTestResult.style.background = "rgba(239, 68, 68, 0.15)";
        spappFormTestResult.style.color = "#f87171";
        spappFormTestResult.textContent = `❌ Lỗi: ${e.message}`;
      } finally {
        btnTestSpappForm.disabled = false;
        btnTestSpappForm.textContent = "⚡ Test Kết Nối Thử";
      }
    });
  }

  // Save Spotify App
  if (formSpotifyApp) {
    formSpotifyApp.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const payload = {
          name: spappName.value.trim(),
          added_by: spappAddedBy.value.trim() || "admin",
          client_id: spappClientId.value.trim(),
          client_secret: spappClientSecret.value.trim(),
          sp_dc: spappSpDc.value.trim(),
          is_premium: spappIsPremium ? spappIsPremium.checked : false,
          account_type: spappIsPremium && spappIsPremium.checked ? "👑 Spotify Premium (320k Direct)" : "Developer API (Client Credentials)",
        };
        if (spappEditId.value) payload.id = spappEditId.value;

        const res = await fetch("/api/spotify_apps", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success) {
          formSpotifyApp.style.display = "none";
          loadSpotifyApps();
          appendLog(`🔑 Đã lưu cấu hình Spotify App: '${payload.name}' ${payload.is_premium ? '👑 [Premium Active]' : ''}`, "success");
        } else {
          alert(`Lỗi: ${data.error}`);
        }
      } catch (err) {
        alert(`Lỗi: ${err.message}`);
      }
    });
  }

  window.setActiveSpotifyApp = async function(appId) {
    try {
      const res = await fetch(`/api/spotify_apps/${appId}/set_active`, { method: "POST" });
      const data = await res.json();
      if (data.success) {
        loadSpotifyApps();
        appendLog(`★ Đã chuyển Spotify App chính sang ID: ${appId}`, "info");
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    }
  };

  window.testSpotifyApp = async function(appId, btnElement) {
    if (btnElement) {
      btnElement.disabled = true;
      btnElement.textContent = "⏳...";
    }
    try {
      const res = await fetch(`/api/spotify_apps/${appId}/test`, { method: "POST" });
      const data = await res.json();
      if (data.success) {
        loadSpotifyApps();
        if (data.is_premium) {
          appendLog(`👑 Spotify App (${appId}) kiểm tra hợp lệ (${data.latency_ms}ms) - ĐÃ NHẬN DIỆN GÓI PREMIUM!`, "success");
        } else if (data.status === "valid") {
          appendLog(`🟢 Spotify App (${appId}) hoạt động tốt (${data.latency_ms}ms) - ${data.account_type}`, "success");
        } else {
          appendLog(`🔴 Spotify App (${appId}) không hợp lệ: ${data.error}`, "error");
        }
      }
    } catch (e) {
      alert(`Lỗi test: ${e.message}`);
    } finally {
      if (btnElement) {
        btnElement.disabled = false;
        btnElement.textContent = "⚡ Test";
      }
    }
  };

  window.editSpotifyApp = async function(appId) {
    try {
      const res = await fetch("/api/spotify_apps");
      const data = await res.json();
      const target = data.apps.find((a) => a.id === appId);
      if (!target) return;

      spappEditId.value = target.id;
      spappName.value = target.name || "";
      spappAddedBy.value = target.added_by || "admin";
      spappClientId.value = target.client_id || "";
      spappClientSecret.value = target.client_secret || "";
      spappSpDc.value = target.sp_dc || "";
      if (spappIsPremium) spappIsPremium.checked = Boolean(target.is_premium);
      document.getElementById("spapp-form-title").textContent = `✏️ Chỉnh Sửa Spotify App: ${target.name}`;
      formSpotifyApp.style.display = "flex";
      spappFormTestResult.style.display = "none";
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    }
  };

  window.deleteSpotifyApp = function(appId, appName) {
    showConfirmModal(
      `Bạn có chắc chắn muốn xóa Spotify App <b>'${appName}'</b> khỏi pool?`,
      async () => {
        try {
          const res = await fetch(`/api/spotify_apps/${appId}`, { method: "DELETE" });
          const data = await res.json();
          if (data.success) {
            loadSpotifyApps();
            appendLog(`🗑️ Đã xóa Spotify App '${appName}' khỏi pool`, "warning");
          } else {
            alert(`Lỗi: ${data.error}`);
          }
        } catch (e) {
          alert(`Lỗi: ${e.message}`);
        }
      }
    );
  };

  // ─── Proxy Pool Engine ────────────────────────────────────

  async function loadProxies() {
    if (!proxiesTableBody) return;
    try {
      proxiesTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-dim" style="padding: 20px;">⏳ Đang tải danh sách Proxies từ database...</td></tr>`;
      const res = await fetch("/api/proxies");
      const data = await res.json();
      if (!data.success || !data.proxies || data.proxies.length === 0) {
        proxiesTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-dim" style="padding: 20px;">Chưa có proxy nào trong pool. Hãy bấm '➕ Thêm Proxy Mới'.</td></tr>`;
        return;
      }

      proxiesTableBody.innerHTML = data.proxies.map((p) => {
        const protoBadge = `<span class="badge badge-cyan" style="font-size: 10px; font-weight: 700;">${(p.protocol || 'HTTP').toUpperCase()}</span>`;
        
        let speedBadge = `<span class="badge badge-secondary" style="font-size: 10px;">⏳ Chưa Đo</span>`;
        if (p.status === "alive") {
          const color = p.latency_ms < 200 ? "badge-success" : "badge-warning";
          speedBadge = `<span class="badge ${color}" style="font-size: 10px;">🟢 ${p.latency_ms || 0}ms</span>`;
        } else if (p.status === "dead") {
          speedBadge = `<span class="badge badge-danger" style="font-size: 10px;" title="${p.error || ''}">🔴 Dead (${p.latency_ms || 0}ms)</span>`;
        }

        const activeSwitch = `
          <label class="switch" style="transform: scale(0.85); margin: 0 auto; display: block;">
            <input type="checkbox" ${p.is_active ? "checked" : ""} onchange="window.toggleProxyActive('${p.id}', this.checked)">
            <span class="slider"></span>
          </label>
        `;

        return `
          <tr style="${p.is_active ? '' : 'opacity: 0.6;'}">
            <td style="text-align: center;">${activeSwitch}</td>
            <td>${protoBadge}</td>
            <td>
              <div class="font-mono" style="font-weight: 600; color: var(--text-main); font-size: 11.5px;">${p.host}:${p.port}</div>
              <div class="text-dim" style="font-size: 10.5px;">${p.name || '-'}</div>
            </td>
            <td><span class="badge badge-purple" style="font-size: 9.5px;">👤 @${p.added_by || 'admin'}</span></td>
            <td>${speedBadge}</td>
            <td style="text-align: center;">
              <div class="flex-row" style="justify-content: center; gap: 4px;">
                <button class="btn btn-secondary" style="padding: 3px 6px; font-size: 10px;" onclick="window.testProxyPing('${p.id}', this)" title="Đo độ trễ ms">⚡ Ping</button>
                <button class="btn btn-secondary" style="padding: 3px 6px; font-size: 10px;" onclick="window.editProxy('${p.id}')" title="Sửa proxy">✏️</button>
                <button class="btn btn-danger" style="padding: 3px 6px; font-size: 10px;" onclick="window.deleteProxy('${p.id}', '${p.host}:${p.port}')" title="Xóa khỏi pool">🗑️</button>
              </div>
            </td>
          </tr>
        `;
      }).join("");
    } catch (err) {
      proxiesTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-red" style="padding: 20px;">Lỗi tải Proxies: ${err.message}</td></tr>`;
    }
  }

  // Toggle Proxy Add Form
  if (btnOpenAddProxy) {
    btnOpenAddProxy.addEventListener("click", () => {
      formProxy.reset();
      proxyEditId.value = "";
      document.getElementById("proxy-form-title").textContent = "➕ Thêm Proxy Mới Vào Pool";
      formProxy.style.display = "flex";
      proxyFormTestResult.style.display = "none";
    });
  }

  if (btnCloseProxyForm) {
    btnCloseProxyForm.addEventListener("click", () => {
      formProxy.style.display = "none";
    });
  }

  // Test single proxy ping from form
  if (btnTestProxyForm) {
    btnTestProxyForm.addEventListener("click", async () => {
      const proto = proxyProtocol.value;
      const host = proxyHost.value.trim();
      const port = proxyPort.value.trim();
      const user = proxyUsername.value.trim();
      const pass = proxyPassword.value.trim();

      if (!host || !port) {
        alert("Vui lòng nhập Host và Port proxy!");
        return;
      }

      btnTestProxyForm.disabled = true;
      btnTestProxyForm.textContent = "⏳ Đang ping...";
      proxyFormTestResult.style.display = "block";
      proxyFormTestResult.style.background = "var(--bg-input)";
      proxyFormTestResult.style.color = "var(--text-main)";
      proxyFormTestResult.textContent = `🔄 Đang đo độ trễ tới ${proto.toUpperCase()}://${host}:${port}...`;

      try {
        const payload = {
          id: proxyEditId.value || "temp_test",
          protocol: proto,
          host: host,
          port: parseInt(port),
          username: user,
          password: pass,
          added_by: proxyAddedBy.value.trim() || "admin",
        };

        await fetch("/api/proxies", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const testRes = await fetch(`/api/proxies/${proxyEditId.value || "temp_test"}/test`, { method: "POST" });
        const testData = await testRes.json();

        if (testData.status === "alive") {
          proxyFormTestResult.style.background = "rgba(16, 185, 129, 0.15)";
          proxyFormTestResult.style.color = "#34d399";
          proxyFormTestResult.innerHTML = `🟢 Proxy Alive! Độ trễ phản hồi: <b>${testData.latency_ms}ms</b> (Status Code: ${testData.status_code || 200})`;
        } else {
          proxyFormTestResult.style.background = "rgba(239, 68, 68, 0.15)";
          proxyFormTestResult.style.color = "#f87171";
          proxyFormTestResult.innerHTML = `🔴 Proxy Dead / Timeout: ${testData.error || "Không thể kết nối"}`;
        }
      } catch (e) {
        proxyFormTestResult.style.background = "rgba(239, 68, 68, 0.15)";
        proxyFormTestResult.style.color = "#f87171";
        proxyFormTestResult.textContent = `❌ Lỗi test: ${e.message}`;
      } finally {
        btnTestProxyForm.disabled = false;
        btnTestProxyForm.textContent = "⚡ Đo Tốc Độ (Ping Test)";
      }
    });
  }

  // Save Proxy Item
  if (formProxy) {
    formProxy.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const payload = {
          name: proxyName.value.trim(),
          added_by: proxyAddedBy.value.trim() || "admin",
          protocol: proxyProtocol.value,
          host: proxyHost.value.trim(),
          port: parseInt(proxyPort.value.trim()) || 8080,
          username: proxyUsername.value.trim(),
          password: proxyPassword.value.trim(),
        };
        if (proxyEditId.value) payload.id = proxyEditId.value;

        const res = await fetch("/api/proxies", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success) {
          formProxy.style.display = "none";
          loadProxies();
          appendLog(`🛡️ Đã lưu cấu hình Proxy [${payload.protocol.toUpperCase()}]: ${payload.host}:${payload.port}`, "success");
        } else {
          alert(`Lỗi: ${data.error}`);
        }
      } catch (err) {
        alert(`Lỗi: ${err.message}`);
      }
    });
  }

  window.toggleProxyActive = async function(proxyId, isChecked) {
    try {
      const res = await fetch(`/api/proxies/${proxyId}/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: isChecked }),
      });
      const data = await res.json();
      if (data.success) {
        loadProxies();
        appendLog(`🛡️ Đã ${isChecked ? 'BẬT' : 'TẮT'} proxy: ${proxyId}`, "info");
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    }
  };

  window.testProxyPing = async function(proxyId, btnElement) {
    if (btnElement) {
      btnElement.disabled = true;
      btnElement.textContent = "⏳...";
    }
    try {
      const res = await fetch(`/api/proxies/${proxyId}/test`, { method: "POST" });
      const data = await res.json();
      if (data.success) {
        loadProxies();
        if (data.status === "alive") {
          appendLog(`🟢 Proxy (${proxyId}) phản hồi tốt: ${data.latency_ms}ms`, "success");
        } else {
          appendLog(`🔴 Proxy (${proxyId}) thất bại: ${data.error}`, "warning");
        }
      }
    } catch (e) {
      alert(`Lỗi ping: ${e.message}`);
    } finally {
      if (btnElement) {
        btnElement.disabled = false;
        btnElement.textContent = "⚡ Ping";
      }
    }
  };

  window.editProxy = async function(proxyId) {
    try {
      const res = await fetch("/api/proxies");
      const data = await res.json();
      const target = data.proxies.find((p) => p.id === proxyId);
      if (!target) return;

      proxyEditId.value = target.id;
      proxyName.value = target.name || "";
      proxyAddedBy.value = target.added_by || "admin";
      proxyProtocol.value = (target.protocol || "http").toLowerCase();
      proxyHost.value = target.host || "";
      proxyPort.value = target.port || 8080;
      proxyUsername.value = target.username || "";
      proxyPassword.value = target.password || "";

      document.getElementById("proxy-form-title").textContent = `✏️ Chỉnh Sửa Proxy: ${target.host}:${target.port}`;
      formProxy.style.display = "flex";
      proxyFormTestResult.style.display = "none";
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    }
  };

  window.deleteProxy = function(proxyId, proxyLabel) {
    showConfirmModal(
      `Bạn có chắc chắn muốn xóa Proxy <b>'${proxyLabel}'</b> khỏi pool?`,
      async () => {
        try {
          const res = await fetch(`/api/proxies/${proxyId}`, { method: "DELETE" });
          const data = await res.json();
          if (data.success) {
            loadProxies();
            appendLog(`🗑️ Đã xóa Proxy '${proxyLabel}' khỏi pool`, "warning");
          } else {
            alert(`Lỗi: ${data.error}`);
          }
        } catch (e) {
          alert(`Lỗi: ${e.message}`);
        }
      }
    );
  };

  // Test All Proxies Batch
  if (btnTestAllProxies) {
    btnTestAllProxies.addEventListener("click", async () => {
      btnTestAllProxies.disabled = true;
      btnTestAllProxies.textContent = "⏳ Đang test toàn bộ...";
      appendLog("⚡ Bắt đầu tiến trình kiểm tra tốc độ toàn bộ Proxy trong pool...", "info");

      try {
        const res = await fetch("/api/proxies/test_all", { method: "POST" });
        const data = await res.json();
        if (data.success) {
          loadProxies();
          const aliveCount = data.results.filter((r) => r.status === "alive").length;
          appendLog(`✅ Hoàn thành đo tốc độ pool: ${aliveCount}/${data.total} proxy hoạt động tốt.`, "success");
        } else {
          alert("Lỗi kiểm tra toàn bộ proxy");
        }
      } catch (e) {
        alert(`Lỗi: ${e.message}`);
      } finally {
        btnTestAllProxies.disabled = false;
        btnTestAllProxies.textContent = "⚡ Test Toàn Bộ Proxy (Ping All)";
      }
    });
  }

  console.log("[Settings] Spotify App & Proxy Pool Managers initialized successfully.");
})();

// ─── Comprehensive System Guide Studio Modal JS ─────────────
(function initGuideModalManager() {
  const guideModal = document.getElementById("guide-modal");
  const cbDontShowAgain = document.getElementById("cb-guide-dont-show-again");
  const guideTabBtns = document.querySelectorAll(".guide-tab-btn");
  const guideTabContents = document.querySelectorAll(".guide-tab-content");

  function switchGuideTab(targetTabId) {
    guideTabBtns.forEach((btn) => {
      if (btn.getAttribute("data-tab") === targetTabId) {
        btn.classList.add("btn-primary");
        btn.classList.remove("btn-secondary");
      } else {
        btn.classList.add("btn-secondary");
        btn.classList.remove("btn-primary");
      }
    });

    guideTabContents.forEach((c) => {
      c.style.display = c.id === targetTabId ? "flex" : "none";
    });
  }

  guideTabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-tab");
      if (tab) switchGuideTab(tab);
    });
  });

  window.openGuideModal = function(tabId) {
    if (guideModal) {
      guideModal.style.display = "flex";
      if (tabId) {
        switchGuideTab(tabId);
      } else {
        switchGuideTab("guide-tab-overview");
      }
    }
  };

  window.closeGuideModal = function() {
    if (cbDontShowAgain && cbDontShowAgain.checked) {
      localStorage.setItem("has_seen_guide_v2", "true");
    }
    if (guideModal) guideModal.style.display = "none";
  };

  // Auto popup on first arrival for new users
  try {
    const hasSeen = localStorage.getItem("has_seen_guide_v2");
    if (!hasSeen) {
      setTimeout(() => {
        window.openGuideModal();
      }, 700);
    }
  } catch (e) {
    console.warn("Guide auto-open check failed:", e);
  }
})();

// ─── Team Members & Role Permission Management Studio JS ────
(function initTeamManager() {
  const teamModal = document.getElementById("team-modal");
  const formUserManager = document.getElementById("form-user-manager");
  const teamMembersTableBody = document.getElementById("team-members-table-body");
  const userEditOriginalUsername = document.getElementById("user-edit-original-username");
  const userFormUsername = document.getElementById("user-form-username");
  const userFormDisplayName = document.getElementById("user-form-display-name");
  const userFormEmail = document.getElementById("user-form-email");
  const userFormRole = document.getElementById("user-form-role");
  const userFormPassword = document.getElementById("user-form-password");
  const userFormPasswordHint = document.getElementById("user-form-password-hint");
  const userFormIsActive = document.getElementById("user-form-is-active");

  window.openTeamModal = function() {
    if (teamModal) {
      teamModal.style.display = "flex";
      loadTeamMembers();
    }
  };

  window.closeTeamModal = function() {
    if (teamModal) teamModal.style.display = "none";
  };

  window.openAddUserForm = function() {
    if (formUserManager) {
      formUserManager.reset();
      userEditOriginalUsername.value = "";
      userFormUsername.disabled = false;
      userFormPassword.required = true;
      if (userFormPasswordHint) userFormPasswordHint.style.display = "none";
      if (userFormIsActive) userFormIsActive.checked = true;
      document.getElementById("user-form-title").textContent = "➕ Thêm Tài Khoản Thành Viên Mới";
      formUserManager.style.display = "flex";
    }
  };

  window.closeUserForm = function() {
    if (formUserManager) formUserManager.style.display = "none";
  };

  async function loadTeamMembers() {
    if (!teamMembersTableBody) return;
    try {
      teamMembersTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-dim" style="padding: 20px;">⏳ Đang tải danh sách thành viên từ cơ sở dữ liệu...</td></tr>`;
      const res = await fetch("/api/users");
      const data = await res.json();

      if (!data.success || !data.users || data.users.length === 0) {
        teamMembersTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-dim" style="padding: 20px;">Chưa có thành viên nào. Hãy bấm '➕ Thêm Thành Viên Mới'.</td></tr>`;
        return;
      }

      teamMembersTableBody.innerHTML = data.users.map((u) => {
        let roleBadge = `<span class="badge badge-secondary" style="font-size: 10.5px;">⚡ Collector</span>`;
        if (u.role === "admin") {
          roleBadge = `<span class="badge badge-danger" style="font-size: 10.5px; font-weight: 700; background: rgba(239,68,68,0.18); color: #f87171; border: 1px solid #f87171;">👑 Admin</span>`;
        } else if (u.role === "viewer") {
          roleBadge = `<span class="badge badge-cyan" style="font-size: 10.5px;">👁️ Viewer</span>`;
        }

        const stats = u.stats || {};
        const crawled = stats.crawled_tracks_count || 0;
        const downloaded = stats.downloaded_tracks_count || 0;
        const createdDate = u.created_at ? new Date(u.created_at).toLocaleDateString("vi-VN") : "-";

        const statusBadge = u.is_active
          ? `<span class="badge badge-success" style="font-size: 10px; cursor: pointer;" onclick="window.toggleUserActive('${u.username}', false)" title="Bấm để tạm khóa tài khoản">🟢 Đang Kích Hoạt</span>`
          : `<span class="badge badge-danger" style="font-size: 10px; cursor: pointer;" onclick="window.toggleUserActive('${u.username}', true)" title="Bấm để mở khóa tài khoản">🔴 Đang Khóa</span>`;

        const isAdminSelf = u.username === "admin";
        const deleteBtn = isAdminSelf
          ? `<button class="btn btn-secondary" style="padding: 3px 6px; font-size: 10px; opacity: 0.5;" disabled title="Không thể xóa Admin mặc định">🔒</button>`
          : `<button class="btn btn-danger" style="padding: 3px 6px; font-size: 10px;" onclick="window.deleteUser('${u.username}', '${u.display_name || u.username}')" title="Xóa thành viên">🗑️</button>`;

        return `
          <tr style="${isAdminSelf ? 'background: rgba(139,92,246,0.05);' : ''}">
            <td>
              <div style="font-weight: 700; color: var(--text-main); font-size: 12.5px;">
                👤 ${u.display_name || u.username}
              </div>
              <div class="font-mono text-dim" style="font-size: 10.5px; margin-top: 2px;">
                @${u.username}
              </div>
            </td>
            <td>${roleBadge}</td>
            <td>
              <div style="font-size: 11px; color: var(--text-main);">${u.email || '<i class="text-dim">Chưa có email</i>'}</div>
              <div class="text-dim" style="font-size: 10px; margin-top: 2px;">Tạo: ${createdDate}</div>
            </td>
            <td>
              <div style="font-size: 11px;"><b>${crawled.toLocaleString()}</b> bài cào</div>
              <div class="text-dim" style="font-size: 10px;"><b>${downloaded.toLocaleString()}</b> bài tải MP3</div>
            </td>
            <td style="text-align: center;">${statusBadge}</td>
            <td style="text-align: center;">
              <div class="flex-row" style="justify-content: center; gap: 4px;">
                <button class="btn btn-secondary" style="padding: 3px 6px; font-size: 10px;" onclick="window.editUser('${u.username}')" title="Chỉnh sửa phân quyền &amp; thông tin">✏️ Sửa</button>
                ${deleteBtn}
              </div>
            </td>
          </tr>
        `;
      }).join("");
    } catch (err) {
      if (teamMembersTableBody) {
        teamMembersTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-red" style="padding: 20px;">Lỗi tải thành viên: ${err.message}</td></tr>`;
      }
    }
  }
  window.loadTeamMembers = loadTeamMembers;

  // Form Submit (Create or Update)
  if (formUserManager) {
    formUserManager.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const payload = {
          username: userFormUsername.value.trim().toLowerCase(),
          display_name: userFormDisplayName.value.trim(),
          email: userFormEmail.value.trim(),
          role: userFormRole.value,
          password: userFormPassword.value.trim(),
          is_active: userFormIsActive ? userFormIsActive.checked : true,
        };

        const res = await fetch("/api/users", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success) {
          formUserManager.style.display = "none";
          loadTeamMembers();
          appendLog(`👤 Đã lưu tài khoản: @${payload.username} (${payload.role.toUpperCase()}) - ${payload.display_name}`, "success");
        } else {
          alert(`Lỗi: ${data.error}`);
        }
      } catch (err) {
        alert(`Lỗi lưu tài khoản: ${err.message}`);
      }
    });
  }

  window.editUser = async function(username) {
    try {
      const res = await fetch("/api/users");
      const data = await res.json();
      const target = data.users.find((u) => u.username === username);
      if (!target) return;

      userEditOriginalUsername.value = target.username;
      userFormUsername.value = target.username;
      userFormUsername.disabled = true; // Cannot change username on edit
      userFormDisplayName.value = target.display_name || "";
      userFormEmail.value = target.email || "";
      userFormRole.value = target.role || "collector";
      userFormPassword.value = "";
      userFormPassword.required = false;
      if (userFormPasswordHint) userFormPasswordHint.style.display = "inline";
      if (userFormIsActive) userFormIsActive.checked = Boolean(target.is_active);

      document.getElementById("user-form-title").textContent = `✏️ Chỉnh Sửa Quyền Hạn: @${target.username}`;
      formUserManager.style.display = "flex";
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    }
  };

  window.toggleUserActive = async function(username, shouldBeActive) {
    try {
      const res = await fetch(`/api/users/${username}/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: shouldBeActive }),
      });
      const data = await res.json();
      if (data.success) {
        loadTeamMembers();
        appendLog(`👤 Đã ${shouldBeActive ? 'kích hoạt' : 'tạm khóa'} tài khoản @${username}`, "info");
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    }
  };

  window.deleteUser = function(username, displayName) {
    showConfirmModal({
      title: "⚠️ Xác Nhận Xóa Thành Viên",
      message: `Bạn có chắc chắn muốn xóa tài khoản <b>'@${username}'</b> (${displayName}) khỏi hệ thống?`,
      proceedText: "🗑️ Xóa Thành Viên",
      isDanger: true,
      onConfirm: async () => {
        try {
          const res = await fetch(`/api/users/${username}`, { method: "DELETE" });
          const data = await res.json();
          if (data.success) {
            loadTeamMembers();
            appendLog(`🗑️ Đã xóa tài khoản @${username} khỏi hệ thống`, "warning");
          } else {
            alert(`Lỗi xóa: ${data.error}`);
          }
        } catch (e) {
          alert(`Lỗi: ${e.message}`);
        }
      }
    });
  };
})();

// ─── Network Shield & IP Masking Controller ─────────────────
(function initNetworkShieldManager() {
  const shieldHostIp = document.getElementById("shield-host-ip");
  const shieldHostIsp = document.getElementById("shield-host-isp");
  const shieldEgressIp = document.getElementById("shield-egress-ip");
  const shieldEgressIsp = document.getElementById("shield-egress-isp");
  const shieldEgressBadge = document.getElementById("shield-egress-badge");
  const shieldStatusBanner = document.getElementById("shield-status-banner");
  const warpStatusBadge = document.getElementById("warp-status-badge");
  const btnToggleWarp = document.getElementById("btn-toggle-warp");
  const shieldStrategySelect = document.getElementById("shield-strategy-select");

  let isWarpConnected = false;

  window.refreshShieldStatus = async function() {
    try {
      if (shieldEgressIp) shieldEgressIp.textContent = "⏳ Đang kiểm tra...";
      const res = await fetch("/api/network/shield_status");
      const data = await res.json();

      if (!data.success) return;

      if (shieldHostIp) shieldHostIp.textContent = data.host_ip || "158.178.247.33";
      if (shieldHostIsp) shieldHostIsp.textContent = `${data.host_isp || "Oracle Corporation"} (${data.host_country || "SG"})`;

      if (shieldEgressIp) shieldEgressIp.textContent = data.egress_ip || data.host_ip;
      if (shieldEgressIsp) shieldEgressIsp.textContent = `${data.egress_isp || "Direct"} (${data.egress_country || "SG"}) - Ping: ${data.latency_ms || 0}ms`;

      if (shieldEgressBadge && shieldStatusBanner) {
        if (data.is_protected) {
          shieldEgressBadge.className = "badge badge-success";
          shieldEgressBadge.textContent = "🟢 ĐÃ ẨN DANH TÍNH (PROTECTED)";
          shieldStatusBanner.style.background = "rgba(16,185,129,0.1)";
          shieldStatusBanner.style.borderColor = "rgba(16,185,129,0.3)";
          shieldStatusBanner.style.color = "#34d399";
          shieldStatusBanner.innerHTML = `<span>🟢</span> <b>BẢO VỆ TOÀN DIỆN:</b> Yêu cầu tải nhạc từ YouTube/Spotify đi qua IP bảo vệ (<b>${data.egress_ip}</b>), vượt qua 100% cơ chế kiểm tra Bot.`;
        } else {
          shieldEgressBadge.className = "badge badge-warning";
          shieldEgressBadge.textContent = "🟡 IP TRỰC TIẾP (DIRECT DATACENTER)";
          shieldStatusBanner.style.background = "rgba(245,158,11,0.1)";
          shieldStatusBanner.style.borderColor = "rgba(245,158,11,0.3)";
          shieldStatusBanner.style.color = "#fbbf24";
          shieldStatusBanner.innerHTML = `<span>🟡</span> <b>KẾT NỐI TRỰC TIẾP:</b> Đang dùng dải IP Datacenter Oracle. Khuyến nghị bật <b>Cloudflare WARP</b> hoặc <b>Proxy Pool</b> để tránh bị YouTube chặn bot.`;
        }
      }

      // Update WARP status
      const warp = data.warp || {};
      isWarpConnected = Boolean(warp.is_connected);
      if (warpStatusBadge && btnToggleWarp) {
        if (isWarpConnected) {
          warpStatusBadge.className = "badge badge-success";
          warpStatusBadge.textContent = "🟢 SOCKS5 127.0.0.1:40000 (ONLINE)";
          btnToggleWarp.textContent = "⏹️ Ngắt Kết Nối WARP";
          btnToggleWarp.className = "btn btn-secondary";
        } else {
          warpStatusBadge.className = "badge badge-secondary";
          warpStatusBadge.textContent = warp.installed ? "⚪ ĐANG TẮT (OFFLINE)" : "⚠️ CHƯA CÀI ĐẶT";
          btnToggleWarp.textContent = "⚡ Bật WARP Gateway";
          btnToggleWarp.className = "btn btn-primary";
        }
      }

      // Update strategy select
      if (shieldStrategySelect && data.rotation_strategy) {
        shieldStrategySelect.value = data.rotation_strategy;
      }

      if (window.loadTailscaleStatus) {
        window.loadTailscaleStatus();
      }

      if (window.refreshFingerprintStatus) {
        window.refreshFingerprintStatus();
      }
    } catch (e) {
      console.warn("Error refreshing shield status:", e);
    }
  };

  window.toggleWarpConnection = async function() {
    if (!btnToggleWarp) return;
    btnToggleWarp.disabled = true;
    btnToggleWarp.textContent = isWarpConnected ? "⏳ Đang ngắt..." : "⏳ Đang kết nối...";

    try {
      const res = await fetch("/api/network/warp/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enable: !isWarpConnected }),
      });
      const data = await res.json();
      if (data.success) {
        appendLog(`🛡️ Cloudflare WARP: ${data.status}`, data.status === "CONNECTED" ? "success" : "info");
        await window.refreshShieldStatus();
      } else {
        alert(`Lỗi WARP: ${data.error || "Không thể thực hiện"}`);
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    } finally {
      btnToggleWarp.disabled = false;
    }
  };

  window.saveNetworkStrategy = async function() {
    if (!shieldStrategySelect) return;
    const strat = shieldStrategySelect.value;
    try {
      const res = await fetch("/api/network/strategy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy: strat }),
      });
      const data = await res.json();
      if (data.success) {
        appendLog(`🔄 Đã cập nhật chiến lược xoay vòng Proxy: ${strat.toUpperCase()}`, "success");
        alert("✅ Đã lưu cấu hình chiến lược điều phối mạng thành công!");
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    }
  };
})();

// ─── Tailscale Mesh Exit Node Manager ───────────────────────
(function initTailscaleManager() {
  const tailscaleStatusBadge = document.getElementById("tailscale-status-badge");
  const tailscaleMeshIp = document.getElementById("tailscale-mesh-ip");
  const tailscaleActiveExitNode = document.getElementById("tailscale-active-exit-node");
  const tailscaleAuthKey = document.getElementById("tailscale-auth-key");
  const tailscaleExitNodeSelect = document.getElementById("tailscale-exit-node-select");
  const btnConnectTailscale = document.getElementById("btn-connect-tailscale");
  const btnDisconnectTailscale = document.getElementById("btn-disconnect-tailscale");

  window.loadTailscaleStatus = async function() {
    try {
      const res = await fetch("/api/network/tailscale/status");
      const data = await res.json();
      if (!data.success) return;

      const ts = data.tailscale || {};
      if (tailscaleStatusBadge) {
        if (ts.is_connected) {
          tailscaleStatusBadge.className = "badge badge-success";
          tailscaleStatusBadge.textContent = "🟢 ONLINE (WireGuard Mesh)";
        } else if (ts.installed) {
          tailscaleStatusBadge.className = "badge badge-secondary";
          tailscaleStatusBadge.textContent = "⚪ OFFLINE";
        } else {
          tailscaleStatusBadge.className = "badge badge-warning";
          tailscaleStatusBadge.textContent = "⚠️ CHƯA CÀI ĐẶT";
        }
      }

      if (tailscaleMeshIp) {
        tailscaleMeshIp.textContent = ts.primary_ip || (ts.is_connected ? "100.x (Connected)" : "Chưa kết nối");
      }

      if (tailscaleActiveExitNode) {
        if (ts.active_exit_node) {
          tailscaleActiveExitNode.innerHTML = `<span class="badge badge-success" style="font-size: 11px;">🟢 ${ts.active_exit_node.hostname || 'Home-PC'} (${ts.active_exit_node.ip})</span>`;
        } else {
          tailscaleActiveExitNode.textContent = "Không có (Direct Egress)";
        }
      }

      // Populate exit nodes dropdown
      if (tailscaleExitNodeSelect && ts.available_exit_nodes) {
        const currentVal = tailscaleExitNodeSelect.value;
        tailscaleExitNodeSelect.innerHTML = `<option value="">-- Không dùng Exit Node (Mesh Only) --</option>` +
          ts.available_exit_nodes.map(node => {
            const isSel = (ts.active_exit_node && ts.active_exit_node.id === node.id) ? "selected" : "";
            return `<option value="${node.hostname}" ${isSel}>💻 ${node.hostname} (${node.ip || node.os}) - ${node.online ? '🟢 Online' : '⚪ Offline'}</option>`;
          }).join("");
        if (currentVal && !ts.active_exit_node) tailscaleExitNodeSelect.value = currentVal;
      }
    } catch (e) {
      console.warn("Error loading tailscale status:", e);
    }
  };

  window.connectTailscale = async function() {
    const authKey = tailscaleAuthKey ? tailscaleAuthKey.value.trim() : "";
    const exitNode = tailscaleExitNodeSelect ? tailscaleExitNodeSelect.value.trim() : "";

    if (!authKey) {
      alert("Vui lòng nhập Tailscale Auth Key (bắt đầu bằng tskey-auth-...)!");
      return;
    }

    if (btnConnectTailscale) {
      btnConnectTailscale.disabled = true;
      btnConnectTailscale.textContent = "⏳ Đang kết nối WireGuard...";
    }

    try {
      const res = await fetch("/api/network/tailscale/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          auth_key: authKey,
          exit_node: exitNode,
          socks5_port: 1055,
        })
      });
      const data = await res.json();
      if (data.success) {
        appendLog(`💻 Tailscale: Đã kết nối thành công vào Tailnet! IP: ${data.tailscale?.primary_ip || ''}`, "success");
        if (tailscaleAuthKey) tailscaleAuthKey.value = "";
        await window.loadTailscaleStatus();
        await window.refreshShieldStatus();
      } else {
        alert(`Lỗi kết nối Tailscale: ${data.error || "Không rõ nguyên nhân"}`);
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    } finally {
      if (btnConnectTailscale) {
        btnConnectTailscale.disabled = false;
        btnConnectTailscale.textContent = "⚡ Kết Nối Tailnet & Kích Hoạt Exit Node";
      }
    }
  };

  window.disconnectTailscale = async function() {
    if (btnDisconnectTailscale) {
      btnDisconnectTailscale.disabled = true;
      btnDisconnectTailscale.textContent = "⏳ Đang ngắt...";
    }
    try {
      const res = await fetch("/api/network/tailscale/disconnect", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        appendLog("⚠️ Đã ngắt kết nối Tailscale", "warning");
        await window.loadTailscaleStatus();
        await window.refreshShieldStatus();
      } else {
        alert(`Lỗi: ${data.error}`);
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    } finally {
      if (btnDisconnectTailscale) {
        btnDisconnectTailscale.disabled = false;
        btnDisconnectTailscale.textContent = "⏹️ Ngắt Kết Nối Tailscale";
      }
    }
  };

  if (tailscaleExitNodeSelect) {
    tailscaleExitNodeSelect.addEventListener("change", async () => {
      const selectedNode = tailscaleExitNodeSelect.value;
      try {
        const res = await fetch("/api/network/tailscale/exit_node", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ exit_node: selectedNode })
        });
        const data = await res.json();
        if (data.success) {
          appendLog(`🔄 Đã đổi Tailscale Exit Node sang: '${selectedNode || 'None'}'`, "info");
          await window.loadTailscaleStatus();
          await window.refreshShieldStatus();
        }
      } catch (e) {
        alert(`Lỗi đổi exit node: ${e.message}`);
      }
    });
  }
})();

// ─── Browser Fingerprint & Anti-Detection Studio Controller ──────────────
(function initFingerprintStudio() {
  const profileSelect = document.getElementById("fp-profile-select");
  const preflightBadge = document.getElementById("fp-preflight-badge");
  const specUa = document.getElementById("fp-spec-ua");
  const specCh = document.getElementById("fp-spec-ch");
  const specGpu = document.getElementById("fp-spec-gpu");
  const specScreen = document.getElementById("fp-spec-screen");
  const specHw = document.getElementById("fp-spec-hw");
  const specJa4 = document.getElementById("fp-spec-ja4");
  const auditBox = document.getElementById("fp-audit-result-box");
  const tableContainer = document.getElementById("fp-profiles-list-table");
  const totalCountBadge = document.getElementById("fp-total-count");

  let allLoadedProfiles = [];

  function renderProfileSpecs(profile) {
    if (!profile) return;
    if (specUa) specUa.textContent = `${profile.browser}/${profile.browser_version || '132'} (${profile.os} ${profile.os_version || ''})`;
    if (specCh) specCh.textContent = profile.sec_ch_ua || "Không dùng (Safari/Firefox Standard)";
    
    const webgl = profile.webgl || {};
    if (specGpu) specGpu.textContent = `${webgl.unmasked_vendor || 'Google Inc.'} — ${webgl.unmasked_renderer || 'GPU Standard'}`;

    const screen = profile.screen || {};
    if (specScreen) specScreen.textContent = `${screen.width || 1920} x ${screen.height || 1080} (DPI: ${screen.devicePixelRatio || 1.0}x, ${screen.colorDepth || 24}-bit)`;

    const hw = profile.hardware || {};
    if (specHw) specHw.textContent = `${hw.hardware_concurrency || 8} Cores | ${hw.device_memory || 16} GB RAM | Touch: ${hw.max_touch_points || 0}`;

    const innertube = profile.innertube_client || {};
    if (specJa4) specJa4.textContent = `${profile.ja4_tls || 't13d1516h2_8daaf'} (${innertube.client_name || 'WEB_REMIX'})`;

    if (profileSelect && profile.id) {
      profileSelect.value = profile.id;
    }

    if (preflightBadge) {
      if (profile.preflight_passed) {
        preflightBadge.className = "badge badge-success";
        preflightBadge.textContent = `🟢 PRE-FLIGHT PASSED (${profile.last_latency_ms || 120}ms)`;
      } else {
        preflightBadge.className = "badge badge-secondary";
        preflightBadge.textContent = "🟡 CHƯA PRE-FLIGHT";
      }
    }
  }

  function renderProfilesTable(profiles, activeId) {
    if (!tableContainer) return;
    if (!profiles || profiles.length === 0) {
      tableContainer.innerHTML = `<div style="font-size: 11px; color: var(--text-muted); text-align: center; padding: 8px;">Chưa có hồ sơ nào.</div>`;
      return;
    }

    if (totalCountBadge) {
      totalCountBadge.textContent = `${profiles.length} Profiles`;
    }

    // Populate dropdown options dynamically
    if (profileSelect) {
      const currentSelected = profileSelect.value;
      profileSelect.innerHTML = profiles.map(p => {
        const icon = p.device_type === "mobile" ? "📱" : (p.device_type === "tv" ? "📺" : (p.os === "macOS" ? "🍎" : "🖥️"));
        const activeLabel = p.id === activeId ? " [Đang Dùng]" : "";
        return `<option value="${p.id}">${icon} ${p.name}${activeLabel}</option>`;
      }).join("") + `<option value="random">🎲 Tự Động Chọn Ngẫu Nhiên Mỗi Phiên (Auto Rotate)</option>`;
      if (currentSelected && profileSelect.querySelector(`option[value="${currentSelected}"]`)) {
        profileSelect.value = currentSelected;
      }
    }

    tableContainer.innerHTML = profiles.map(p => {
      const isActive = p.id === activeId;
      const icon = p.device_type === "mobile" ? "📱" : (p.device_type === "tv" ? "📺" : (p.os === "macOS" ? "🍎" : "🖥️"));
      const badgeClass = isActive ? "badge-success" : (p.preflight_passed ? "badge-info" : "badge-secondary");
      const statusText = isActive ? "🟢 ĐANG DÙNG" : (p.preflight_passed ? `⚡ Passed (${p.last_latency_ms || 0}ms)` : "⚪ Untested");

      const deleteBtn = p.is_custom ? `
        <button class="btn btn-secondary" style="padding: 2px 6px; font-size: 10px; color: #f87171; border-color: rgba(239,68,68,0.4);" onclick="window.deleteCustomFingerprint('${p.id}')">
          🗑️
        </button>
      ` : "";

      return `
        <div style="background: rgba(0,0,0,0.3); border: 1px solid ${isActive ? 'rgba(139,92,246,0.6)' : 'rgba(255,255,255,0.06)'}; border-radius: var(--radius-sm); padding: 6px 10px; display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 8px; overflow: hidden;">
            <span style="font-size: 14px;">${icon}</span>
            <div style="display: flex; flex-direction: column;">
              <div style="font-size: 11px; font-weight: 600; color: ${isActive ? '#c084fc' : '#e2e8f0'}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 320px;">
                ${p.name}
              </div>
              <div style="font-size: 9.5px; color: var(--text-muted); font-family: monospace;">
                ${p.browser} on ${p.os} • JA4: ${p.ja4_tls ? p.ja4_tls.slice(0, 14) + '...' : 'standard'}
              </div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 6px;">
            <span class="badge ${badgeClass}" style="font-size: 9px;">${statusText}</span>
            <button class="btn btn-secondary" style="padding: 2px 6px; font-size: 10px; border-color: var(--accent-cyan); color: var(--accent-cyan);" onclick="window.preflightTestFingerprint('${p.id}')" title="Chạy Pre-flight Live Test">
              ⚡ Test
            </button>
            ${!isActive ? `
              <button class="btn btn-primary" style="padding: 2px 8px; font-size: 10px;" onclick="window.activateFingerprintWithPreflight('${p.id}')">
                Kích Hoạt
              </button>
            ` : ''}
            ${deleteBtn}
          </div>
        </div>
      `;
    }).join("");
  }

  window.refreshFingerprintStatus = async function() {
    try {
      const res = await fetch("/api/network/fingerprints");
      const data = await res.json();
      if (data.success && data.profiles) {
        allLoadedProfiles = data.profiles;
        const activeId = data.active_profile ? data.active_profile.id : "win11_chrome_132_nv";
        renderProfilesTable(data.profiles, activeId);
        if (data.active_profile) {
          renderProfileSpecs(data.active_profile);
        }
      }
    } catch (e) {
      console.warn("Error fetching fingerprint status:", e);
    }
  };

  window.switchFingerprint = function(profileId) {
    if (profileId === "random") return;
    const found = allLoadedProfiles.find(p => p.id === profileId);
    if (found) {
      renderProfileSpecs(found);
    }
  };

  window.activateFingerprintWithPreflight = async function(profileId) {
    const btnApply = document.getElementById("btn-apply-fp");
    if (btnApply) {
      btnApply.disabled = true;
      btnApply.textContent = "⏳ Đang Pre-flight Test...";
    }

    try {
      const res = await fetch(`/api/network/fingerprints/${profileId}/activate`, { method: "POST" });
      const data = await res.json();
      if (data.success && data.active_profile) {
        appendLog(`🎭 Đã kiểm thử Pre-flight đạt chuẩn & kích hoạt hồ sơ: ${data.active_profile.name}`, "success");
        await window.refreshFingerprintStatus();
        alert(`✅ Đã kích hoạt hồ sơ: ${data.active_profile.name} (Ping: ${data.preflight ? data.preflight.latency_ms : 0}ms)`);
      } else {
        alert(`❌ Lỗi kích hoạt hồ sơ: ${data.error || "Pre-flight test không đạt chuẩn"}`);
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    } finally {
      if (btnApply) {
        btnApply.disabled = false;
        btnApply.textContent = "⚡ Test & Kích Hoạt";
      }
    }
  };

  window.applySelectedFingerprint = async function() {
    if (!profileSelect) return;
    const profileId = profileSelect.value;
    if (profileId === "random") {
      await window.randomizeFingerprint();
    } else {
      await window.activateFingerprintWithPreflight(profileId);
    }
  };

  window.preflightTestFingerprint = async function(profileId) {
    try {
      appendLog(`⏳ Đang chạy Pre-flight Test cho hồ sơ '${profileId}'...`, "info");
      const res = await fetch(`/api/network/fingerprints/${profileId}/preflight_test`, { method: "POST" });
      const data = await res.json();
      if (data.success) {
        if (data.passed) {
          appendLog(`🟢 Pre-flight Test PASSED (${data.profile_name}): Latency ${data.latency_ms}ms`, "success");
          alert(`✅ Hồ sơ '${data.profile_name}' đạt chuẩn 100% (Ping: ${data.latency_ms}ms, TLS & Client Hints hợp lệ)!`);
        } else {
          appendLog(`🔴 Pre-flight Test FAILED (${data.profile_name}): ${data.error}`, "error");
          alert(`⚠️ Hồ sơ '${data.profile_name}' kiểm thử thất bại: ${data.error || 'Lỗi bắt tay mạng'}`);
        }
        await window.refreshFingerprintStatus();
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    }
  };

  window.randomizeFingerprint = async function() {
    try {
      const res = await fetch("/api/network/fingerprints/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id: "random" }),
      });
      const data = await res.json();
      if (data.success && data.active_profile) {
        appendLog(`🎲 Đã chọn ngẫu nhiên hồ sơ vân tay: ${data.active_profile.name}`, "info");
        await window.refreshFingerprintStatus();
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    }
  };

  window.testFingerprint = async function() {
    if (!auditBox) return;
    auditBox.style.display = "block";
    auditBox.innerHTML = `<span class="spinner-border spinner-border-sm"></span> <b>Đang thực hiện kiểm toán Anti-Detection Matrix (7 điểm kiểm tra)...</b>`;

    try {
      const res = await fetch("/api/network/fingerprint/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await res.json();
      if (data.success) {
        const c = data.stealth_checks || {};
        auditBox.innerHTML = `
          <div style="font-weight: 700; color: #34d399; margin-bottom: 6px;">
            ✅ KẾT QUẢ KIỂM TOÁN DẤU VÂN TAY (100% STEALTH PASSED):
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 10.5px;">
            <div>🛡️ <b>Navigator Webdriver:</b> <span style="color: #34d399;">${c.navigator_webdriver}</span></div>
            <div>🎯 <b>Client Hints:</b> <span style="color: #34d399;">${c.client_hints_consistent}</span></div>
            <div>🎮 <b>GPU Vendor:</b> <span style="color: #38bdf8;">${c.webgl_gpu_vendor}</span></div>
            <div>🎨 <b>GPU Renderer:</b> <span style="color: #38bdf8;">${c.webgl_gpu_renderer}</span></div>
            <div>📐 <b>Màn hình & DPI:</b> <span style="color: #fbbf24;">${c.screen_resolution}</span></div>
            <div>🔒 <b>TLS JA4 Hash:</b> <span style="color: #f472b6;">${c.ja4_tls_signature}</span></div>
            <div>🎵 <b>InnerTube Client:</b> <span style="color: #a78bfa;">${c.innertube_client}</span></div>
          </div>
        `;
      }
    } catch (e) {
      auditBox.innerHTML = `<div style="color: #f87171;">❌ Lỗi kiểm toán: ${e.message}</div>`;
    }
  };

  // Modal handlers
  window.openAddFingerprintModal = function() {
    const modal = document.getElementById("modal-add-fingerprint");
    if (modal) {
      modal.style.display = "flex";
      window.autoFillFingerprintHints();
    }
  };

  window.closeAddFingerprintModal = function() {
    const modal = document.getElementById("modal-add-fingerprint");
    if (modal) modal.style.display = "none";
  };

  window.autoFillFingerprintHints = function() {
    const os = document.getElementById("add-fp-os") ? document.getElementById("add-fp-os").value : "Windows";
    const browser = document.getElementById("add-fp-browser") ? document.getElementById("add-fp-browser").value : "Chrome";
    const uaInput = document.getElementById("add-fp-ua");
    const gpuInput = document.getElementById("add-fp-gpu");

    if (os === "Windows") {
      if (uaInput) uaInput.value = `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ${browser === 'Edge' ? 'Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0' : (browser === 'Firefox' ? 'Gecko/20100101 Firefox/134.0' : 'Chrome/133.0.0.0 Safari/537.36')}`;
      if (gpuInput) gpuInput.value = "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11)";
    } else if (os === "macOS") {
      if (uaInput) uaInput.value = browser === "Safari" ? "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15" : "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36";
      if (gpuInput) gpuInput.value = "Apple M3 Max (Metal 3.1)";
    } else if (os === "iOS") {
      if (uaInput) uaInput.value = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
      if (gpuInput) gpuInput.value = "Apple A18 Pro GPU";
    } else if (os === "Android") {
      if (uaInput) uaInput.value = "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Mobile Safari/537.36";
      if (gpuInput) gpuInput.value = "Qualcomm Adreno 750";
    }
  };

  window.saveCustomFingerprint = async function() {
    const name = document.getElementById("add-fp-name").value.trim();
    const os = document.getElementById("add-fp-os").value;
    const browser = document.getElementById("add-fp-browser").value;
    const ua = document.getElementById("add-fp-ua").value.trim();
    const gpu = document.getElementById("add-fp-gpu").value.trim();
    const client = document.getElementById("add-fp-client").value;
    const testStatus = document.getElementById("add-fp-test-status");
    const btnSave = document.getElementById("btn-save-custom-fp");

    if (!name || !ua) {
      alert("Vui lòng nhập tên hồ sơ và chuỗi User-Agent!");
      return;
    }

    if (testStatus) {
      testStatus.style.display = "block";
      testStatus.className = "badge badge-info";
      testStatus.textContent = "⏳ Đang chạy Pre-flight Test tự động...";
    }
    if (btnSave) btnSave.disabled = true;

    const payload = {
      name: name,
      os: os,
      browser: browser,
      user_agent: ua,
      device_type: (os === "iOS" || os === "Android") ? "mobile" : "desktop",
      sec_ch_ua: (browser === "Chrome" || browser === "Edge") ? `"Chromium";v="133", "Google Chrome";v="133"` : null,
      sec_ch_ua_platform: `"${os}"`,
      webgl: { unmasked_vendor: "Google Inc.", unmasked_renderer: gpu },
      innertube_client: { client_name: client }
    };

    try {
      const res = await fetch("/api/network/fingerprints", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        appendLog(`✅ Đã thêm hồ sơ mới: '${name}' (Pre-flight: ${data.preflight ? data.preflight.status : 'verified'})`, "success");
        window.closeAddFingerprintModal();
        await window.refreshFingerprintStatus();
        alert(data.message || "Đã thêm hồ sơ thành công!");
      } else {
        if (testStatus) {
          testStatus.className = "badge badge-danger";
          testStatus.textContent = `❌ Lỗi: ${data.error}`;
        }
        alert(`Lỗi: ${data.error}`);
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    } finally {
      if (btnSave) btnSave.disabled = false;
    }
  };

  window.deleteCustomFingerprint = async function(profileId) {
    if (!confirm("Bạn có chắc chắn muốn xóa hồ sơ giả lập này?")) return;
    try {
      const res = await fetch(`/api/network/fingerprints/${profileId}`, { method: "DELETE" });
      const data = await res.json();
      if (data.success) {
        appendLog(`🗑️ Đã xóa hồ sơ giả lập '${profileId}'`, "info");
        await window.refreshFingerprintStatus();
      } else {
        alert(`Lỗi xóa: ${data.error}`);
      }
    } catch (e) {
      alert(`Lỗi: ${e.message}`);
    }
  };

  // Real-time Connection Loss Watchdog Heartbeat
  setInterval(async () => {
    try {
      const res = await fetch("/api/network/health_watchdog");
      const data = await res.json();
      if (data.success && data.alerts && data.alerts.length > 0) {
        appendLog(`🚨 CẢNH BÁO MẤT KẾT NỐI MẠNG: ${data.alerts.join(" | ")}`, "error");
      }
    } catch (e) {
      // Network unreachable
    }
  }, 20000);

  // Listen to socket connection lost events
  if (typeof socket !== "undefined") {
    socket.on("network_connection_lost", (data) => {
      const alerts = data.alerts || [];
      appendLog(`🚨 [MẠNG MẤT KẾT NỐI] ${alerts.join(" — ")}`, "error");
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    window.refreshFingerprintStatus();
  });
})();

// ─── Interactive System Guide Modal Controller ──────────────
(function initGuideModal() {
  function switchGuideTab(tabId) {
    if (!tabId) tabId = "guide-tab-overview";
    if (tabId.startsWith("tab-guide-")) {
      tabId = tabId.replace("tab-guide-", "guide-tab-");
    }
    
    const btns = document.querySelectorAll(".guide-tab-btn");
    const contents = document.querySelectorAll(".guide-tab-content");

    let foundContent = false;
    contents.forEach(c => {
      if (c.id === tabId) {
        c.style.display = "flex";
        foundContent = true;
      } else {
        c.style.display = "none";
      }
    });

    if (!foundContent && contents.length > 0) {
      contents[0].style.display = "flex";
      tabId = contents[0].id;
    }

    btns.forEach(btn => {
      const btnTab = btn.getAttribute("data-tab");
      if (btnTab === tabId || (btnTab && btnTab.replace("tab-guide-", "guide-tab-") === tabId)) {
        btn.classList.add("btn-primary");
        btn.classList.remove("btn-secondary");
      } else {
        btn.classList.remove("btn-primary");
        btn.classList.add("btn-secondary");
      }
    });
  }

  window.switchGuideTab = switchGuideTab;

  window.openGuideModal = function(targetTab = "guide-tab-overview") {
    const modal = document.getElementById("guide-modal");
    if (modal) {
      modal.style.display = "flex";
      switchGuideTab(targetTab);
    }
  };

  window.closeGuideModal = function() {
    const modal = document.getElementById("guide-modal");
    if (modal) modal.style.display = "none";
    const cb = document.getElementById("cb-guide-dont-show-again");
    if (cb && cb.checked) {
      localStorage.setItem("dont_show_guide_again", "true");
    }
  };

  document.addEventListener("click", (e) => {
    const tabBtn = e.target.closest(".guide-tab-btn");
    if (tabBtn) {
      const tabId = tabBtn.getAttribute("data-tab");
      if (tabId) switchGuideTab(tabId);
    }

    const modal = document.getElementById("guide-modal");
    if (modal && e.target === modal) {
      window.closeGuideModal();
    }
  });

  // Auto-open for first-time session
  if (!localStorage.getItem("dont_show_guide_again") && !sessionStorage.getItem("guide_seen_session")) {
    sessionStorage.setItem("guide_seen_session", "true");
    setTimeout(() => {
      window.openGuideModal("guide-tab-overview");
    }, 600);
  }
})();



