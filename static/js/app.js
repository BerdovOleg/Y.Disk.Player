(function () {
  const authLabel = document.getElementById("auth-label");
  const loginBtn = document.getElementById("login-btn");
  const logoutBtn = document.getElementById("logout-btn");
  const switchBtn = document.getElementById("switch-btn");

  const VIEW_HINTS = {
    genre: "Жанр → исполнитель → альбом → трек",
    artist: "Исполнитель → альбом → трек",
    album: "Альбом → трек",
  };

  window.OMT = {
    user: null,
    tracks: [],
    libraryView: "genre",
    onPlay(track) {
      fetch("/api/history", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track_id: track.id, position_sec: 0 }),
      }).catch(() => {});
    },
  };

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      const view = btn.dataset.view;
      document.querySelectorAll(".view").forEach((v) => v.classList.remove("is-visible"));
      document.getElementById(`view-${view}`).classList.add("is-visible");
      if (view === "favorites") loadFavorites();
      if (view === "history") loadHistory();
      if (view === "import") loadImport();
      if (view === "playlists") loadPlaylists();
      if (view === "library") {
        loadLibrary();
        loadScanStatus();
      }
    });
  });

  async function api(path, opts) {
    const res = await fetch(path, opts);
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const j = await res.json();
        detail = j.detail || JSON.stringify(j);
      } catch (_) {
        /* ignore */
      }
      throw new Error(detail);
    }
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    return res.text();
  }

  function collectAlbumTracks(album) {
    return (album.tracks || []).slice();
  }
  function collectArtistTracks(artist) {
    return (artist.albums || []).flatMap(collectAlbumTracks);
  }
  function collectGenreTracks(genre) {
    return (genre.artists || []).flatMap(collectArtistTracks);
  }

  function bindFavButtons(root) {
    root.querySelectorAll(".fav-btn").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = Number(btn.dataset.fav);
        const on = btn.classList.contains("is-on");
        try {
          if (on) await api(`/api/favorites/${id}`, { method: "DELETE" });
          else await api(`/api/favorites/${id}`, { method: "POST" });
          btn.classList.toggle("is-on", !on);
          btn.textContent = !on ? "♥" : "♡";
          const t = window.OMT.tracks.find((x) => x.id === id);
          if (t) t.is_favorite = !on ? 1 : 0;
        } catch (err) {
          alert(err.message);
        }
      });
    });
  }

  function renderTracks(el, tracks, opts = {}) {
    if (!tracks.length) {
      el.innerHTML = `<p class="muted">${opts.empty || "Пусто"}</p>`;
      return;
    }
    el.innerHTML = tracks
      .map(
        (t, i) => `
      <div class="track ${t.available === 0 ? "is-unavailable" : ""}" data-id="${t.id}" role="button" tabindex="0">
        <span class="track-num">${t.track_num || i + 1}</span>
        <div class="track-meta">
          <div class="track-title">${escapeHtml(t.title)}${t.available === 0 ? " <span class=\"muted\">(нет на Диске)</span>" : ""}</div>
          <div class="track-sub">${escapeHtml(t.artist || "")}${t.duration_sec ? " · " + Math.round(t.duration_sec) + "s" : ""}</div>
        </div>
        <button type="button" class="fav-btn ${t.is_favorite ? "is-on" : ""}" data-fav="${t.id}" aria-label="Favorite">${t.is_favorite ? "♥" : "♡"}</button>
        <span class="muted">${opts.extra ? opts.extra(t) : ""}</span>
      </div>`
      )
      .join("");

    el.querySelectorAll(".track").forEach((row) => {
      row.addEventListener("click", (e) => {
        if (e.target.closest(".fav-btn")) return;
        const id = Number(row.dataset.id);
        window.OMTPlayer.setQueue(tracks, id);
      });
    });
    bindFavButtons(el);
  }

  function renderAlbumBlock(alb, pathAttrs, open) {
    const tracks = collectAlbumTracks(alb);
    const year = alb.year ? `${alb.year} · ` : "";
    const artistBit =
      window.OMT.libraryView === "album"
        ? `<span class="muted"> · ${escapeHtml(alb.artist || "")}</span>`
        : "";
    return `
      <details class="tree-node tree-album" ${open ? "open" : ""}>
        <summary class="tree-summary">
          <button type="button" class="tree-play" data-queue="album" ${pathAttrs} title="Играть альбом">▶</button>
          <span class="tree-label">${escapeHtml(year + (alb.title || "Unknown Album"))}${artistBit}</span>
          <span class="muted tree-count">${tracks.length}</span>
        </summary>
        <div class="tree-children track-list">
          ${tracks.map((t, i) => trackRowHtml(t, i)).join("")}
        </div>
      </details>`;
  }

  function trackRowHtml(t, i) {
    return `
      <div class="track ${t.available === 0 ? "is-unavailable" : ""}" data-id="${t.id}" role="button" tabindex="0">
        <span class="track-num">${t.track_num || i + 1}</span>
        <div class="track-meta">
          <div class="track-title">${escapeHtml(t.title)}${t.available === 0 ? " <span class=\"muted\">(нет на Диске)</span>" : ""}</div>
          <div class="track-sub">${t.duration_sec ? Math.round(t.duration_sec) + "s" : ""}</div>
        </div>
        <button type="button" class="fav-btn ${t.is_favorite ? "is-on" : ""}" data-fav="${t.id}" aria-label="Favorite">${t.is_favorite ? "♥" : "♡"}</button>
      </div>`;
  }

  function renderLibraryTree(el, tree, flatTracks, mode) {
    if (!tree.length) {
      el.innerHTML = `<p class="muted">Библиотека пуста — загрузите трек или сканируйте Диск</p>`;
      return;
    }
    const byId = Object.fromEntries(flatTracks.map((t) => [t.id, t]));
    const view = mode || window.OMT.libraryView || "genre";

    if (view === "album") {
      el.innerHTML = tree
        .map((alb, ali) => renderAlbumBlock(alb, `data-ali="${ali}"`, ali === 0))
        .join("");
    } else if (view === "artist") {
      el.innerHTML = tree
        .map((a, ai) => {
          const aTracks = collectArtistTracks(a);
          return `
          <details class="tree-node tree-artist" ${ai === 0 ? "open" : ""}>
            <summary class="tree-summary">
              <button type="button" class="tree-play" data-queue="artist" data-ai="${ai}" title="Играть исполнителя">▶</button>
              <span class="tree-label">${escapeHtml(a.artist)}</span>
              <span class="muted tree-count">${aTracks.length}</span>
            </summary>
            <div class="tree-children">
              ${(a.albums || [])
                .map((alb, ali) =>
                  renderAlbumBlock(alb, `data-ai="${ai}" data-ali="${ali}"`, true)
                )
                .join("")}
            </div>
          </details>`;
        })
        .join("");
    } else {
      el.innerHTML = tree
        .map((g, gi) => {
          const gTracks = collectGenreTracks(g);
          return `
          <details class="tree-node tree-genre" ${gi === 0 ? "open" : ""}>
            <summary class="tree-summary">
              <button type="button" class="tree-play" data-queue="genre" data-gi="${gi}" title="Играть жанр">▶</button>
              <span class="tree-label">${escapeHtml(g.genre)}</span>
              <span class="muted tree-count">${gTracks.length}</span>
            </summary>
            <div class="tree-children">
              ${(g.artists || [])
                .map((a, ai) => {
                  const aTracks = collectArtistTracks(a);
                  return `
                  <details class="tree-node tree-artist">
                    <summary class="tree-summary">
                      <button type="button" class="tree-play" data-queue="artist" data-gi="${gi}" data-ai="${ai}" title="Играть исполнителя">▶</button>
                      <span class="tree-label">${escapeHtml(a.artist)}</span>
                      <span class="muted tree-count">${aTracks.length}</span>
                    </summary>
                    <div class="tree-children">
                      ${(a.albums || [])
                        .map((alb, ali) =>
                          renderAlbumBlock(
                            alb,
                            `data-gi="${gi}" data-ai="${ai}" data-ali="${ali}"`,
                            true
                          )
                        )
                        .join("")}
                    </div>
                  </details>`;
                })
                .join("")}
            </div>
          </details>`;
        })
        .join("");
    }

    el.querySelectorAll(".tree-play").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const gi = Number(btn.dataset.gi);
        const ai = Number(btn.dataset.ai);
        const ali = Number(btn.dataset.ali);
        let queue = [];
        if (view === "album") {
          queue = collectAlbumTracks(tree[ali]);
        } else if (view === "artist") {
          const a = tree[ai];
          if (btn.dataset.queue === "artist") queue = collectArtistTracks(a);
          else queue = collectAlbumTracks(a.albums[ali]);
        } else {
          const g = tree[gi];
          if (btn.dataset.queue === "genre") queue = collectGenreTracks(g);
          else if (btn.dataset.queue === "artist") queue = collectArtistTracks(g.artists[ai]);
          else queue = collectAlbumTracks(g.artists[ai].albums[ali]);
        }
        queue = queue.map((t) => byId[t.id] || t).filter(Boolean);
        if (queue.length) window.OMTPlayer.setQueue(queue, queue[0].id);
      });
    });

    el.querySelectorAll(".track").forEach((row) => {
      row.addEventListener("click", (e) => {
        if (e.target.closest(".fav-btn")) return;
        const id = Number(row.dataset.id);
        const albumEl = row.closest(".tree-album");
        let queue = flatTracks;
        if (albumEl) {
          const ids = [...albumEl.querySelectorAll(".track")].map((n) => Number(n.dataset.id));
          queue = ids.map((i) => byId[i]).filter(Boolean);
        }
        window.OMTPlayer.setQueue(queue, id);
      });
    });
    bindFavButtons(el);
  }

  function syncViewModeButtons(mode) {
    document.querySelectorAll(".view-mode-btn").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.viewMode === mode);
    });
    const hint = document.getElementById("library-view-hint");
    if (hint) hint.textContent = VIEW_HINTS[mode] || VIEW_HINTS.genre;
  }

  document.querySelectorAll(".view-mode-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const mode = btn.dataset.viewMode;
      if (!mode || mode === window.OMT.libraryView) return;
      try {
        await api("/api/preferences", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ library_view: mode }),
        });
        try {
          localStorage.setItem("omt_library_view", mode);
        } catch (_) {
          /* ignore */
        }
        window.OMT.libraryView = mode;
        syncViewModeButtons(mode);
        await loadLibrary();
      } catch (err) {
        alert(err.message);
      }
    });
  });

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function refreshAuth() {
    const st = await api("/auth/status");
    window.OMT.user = st.user;
    const banner = document.getElementById("disk-banner");
    if (st.authenticated) {
      authLabel.textContent = st.user.display_name || "User";
      loginBtn.classList.add("hidden");
      logoutBtn.classList.remove("hidden");
      if (switchBtn) switchBtn.classList.remove("hidden");
      if (st.disk_ok === false) {
        banner.classList.remove("hidden");
        banner.innerHTML =
          escapeHtml(st.relogin_hint || st.disk_error || "Нет доступа к Диску") +
          ' — <a href="/auth/login">войти снова через Яндекс</a>';
      } else {
        banner.classList.add("hidden");
        banner.textContent = "";
      }
    } else {
      authLabel.textContent = st.dev_auth_available
        ? "Гость (dev login)"
        : st.oauth_configured
          ? "Не вошли"
          : "OAuth не настроен";
      loginBtn.classList.remove("hidden");
      loginBtn.href = st.dev_auth_available ? "/auth/dev-login" : "/auth/login";
      loginBtn.textContent = st.dev_auth_available ? "Dev-вход" : "Войти";
      logoutBtn.classList.add("hidden");
      if (switchBtn) switchBtn.classList.add("hidden");
      banner.classList.add("hidden");
    }
    return st;
  }

  async function loadLibrary() {
    const el = document.getElementById("library-list");
    try {
      const data = await api("/api/library");
      window.OMT.tracks = data.tracks;
      window.OMT.tree = data.tree || [];
      window.OMT.libraryView = data.view || "genre";
      syncViewModeButtons(window.OMT.libraryView);
      renderLibraryTree(el, window.OMT.tree, data.tracks, window.OMT.libraryView);
    } catch (err) {
      el.innerHTML = `<p class="muted">${escapeHtml(err.message)}</p>`;
    }
  }

  async function loadScanStatus() {
    const el = document.getElementById("scan-last");
    if (!el) return;
    try {
      const st = await api("/api/library/scan/status");
      const u = st.user;
      if (!u || (!u.last_finished_at && !u.last_started_at)) {
        el.classList.remove("hidden");
        el.textContent = st.enabled
          ? `Авто-скан каждые ${st.interval_hours} ч — ещё не запускался`
          : "Авто-скан выключен (DISK_SCAN_INTERVAL_HOURS=0)";
        return;
      }
      el.classList.remove("hidden");
      const when = u.last_finished_at || u.last_started_at;
      el.textContent = `Последний скан: ${when} · ${u.last_status || "?"}` +
        (st.enabled ? ` · авто каждые ${st.interval_hours} ч` : "");
    } catch (_) {
      el.classList.add("hidden");
    }
  }

  let searchTimer = null;
  document.getElementById("library-search").addEventListener("input", (e) => {
    const q = e.target.value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => runSearch(q), 220);
  });

  async function runSearch(q) {
    const box = document.getElementById("search-results");
    const treeEl = document.getElementById("library-list");
    if (!q) {
      box.classList.add("hidden");
      box.innerHTML = "";
      treeEl.classList.remove("hidden");
      return;
    }
    try {
      const data = await api(`/api/search?q=${encodeURIComponent(q)}`);
      box.classList.remove("hidden");
      treeEl.classList.add("hidden");
      if (!data.tracks.length) {
        box.innerHTML = `<p class="muted">Ничего не найдено для «${escapeHtml(q)}»</p>`;
        return;
      }
      box.innerHTML = `<p class="muted">Найдено: ${data.tracks.length}</p><div class="track-list" id="search-track-list"></div>`;
      renderTracks(document.getElementById("search-track-list"), data.tracks);
      // Jump/highlight matching nodes in tree when clearing search is optional;
      // play from results uses flat queue.
    } catch (err) {
      box.classList.remove("hidden");
      box.innerHTML = `<p class="muted">${escapeHtml(err.message)}</p>`;
    }
  }

  document.getElementById("scan-btn").addEventListener("click", async () => {
    const status = document.getElementById("scan-status");
    const btn = document.getElementById("scan-btn");
    status.textContent = "Сканирование…";
    btn.disabled = true;
    try {
      const res = await api("/api/library/scan", { method: "POST" });
      status.textContent = `Готово: +${res.added} / ~${res.updated} / skip ${res.skipped} / нет ${res.unavailable}` +
        (res.error_count ? ` · ошибок ${res.error_count}` : "");
      await loadLibrary();
      await loadScanStatus();
    } catch (err) {
      status.textContent = err.message;
    }
    btn.disabled = false;
  });

  async function loadPlaylists() {
    const el = document.getElementById("playlists-list");
    try {
      const data = await api("/api/playlists");
      window.OMT.playlists = data.playlists || [];
      el.innerHTML =
        data.playlists
          .map(
            (p) => `
        <div class="job-row">
          <span>${escapeHtml(p.title)} · ${p.track_count || 0} трек.</span>
          <span style="display:flex;gap:0.35rem">
            <button type="button" class="btn btn-ghost pl-open" data-id="${p.id}">Открыть</button>
            <button type="button" class="btn btn-ghost pl-play" data-id="${p.id}">▶</button>
            <button type="button" class="btn btn-ghost pl-rename" data-id="${p.id}">Переименовать</button>
            <button type="button" class="btn btn-ghost pl-del" data-id="${p.id}">Удалить</button>
          </span>
        </div>`
          )
          .join("") || `<p class="muted">Плейлистов пока нет</p>`;
      el.querySelectorAll(".pl-open").forEach((b) =>
        b.addEventListener("click", () => showPlaylist(Number(b.dataset.id)))
      );
      el.querySelectorAll(".pl-play").forEach((b) =>
        b.addEventListener("click", () => playPlaylist(Number(b.dataset.id)))
      );
      el.querySelectorAll(".pl-rename").forEach((b) =>
        b.addEventListener("click", () => renamePlaylist(Number(b.dataset.id)))
      );
      el.querySelectorAll(".pl-del").forEach((b) =>
        b.addEventListener("click", () => deletePlaylist(Number(b.dataset.id)))
      );
    } catch (err) {
      el.innerHTML = `<p class="muted">${escapeHtml(err.message)}</p>`;
    }
  }

  async function showPlaylist(id) {
    const box = document.getElementById("playlist-detail");
    box.classList.remove("hidden");
    try {
      const pl = await api(`/api/playlists/${id}`);
      box.innerHTML = `
        <h3>${escapeHtml(pl.title)}</h3>
        <p class="muted">${pl.track_count || 0} треков</p>
        <div class="upload-bar">
          <button type="button" class="btn" id="pl-play-detail">Играть плейлист</button>
          <select id="pl-add-track">
            <option value="">+ добавить трек из библиотеки</option>
            ${(window.OMT.tracks || [])
              .map((t) => `<option value="${t.id}">${escapeHtml(t.artist)} — ${escapeHtml(t.title)}</option>`)
              .join("")}
          </select>
        </div>
        <div id="pl-tracks" class="track-list"></div>`;
      const listEl = document.getElementById("pl-tracks");
      listEl.innerHTML = (pl.tracks || [])
        .map(
          (t, i) => `
        <div class="track" data-id="${t.id}">
          <span class="track-num">${i + 1}</span>
          <div class="track-meta">
            <div class="track-title">${escapeHtml(t.title)}</div>
            <div class="track-sub">${escapeHtml(t.artist || "")}</div>
          </div>
          <button type="button" class="btn btn-ghost pl-up" data-id="${t.id}">↑</button>
          <button type="button" class="btn btn-ghost pl-down" data-id="${t.id}">↓</button>
          <button type="button" class="btn btn-ghost pl-rm" data-id="${t.id}">✕</button>
        </div>`
        )
        .join("") || `<p class="muted">Пусто — добавьте треки</p>`;

      document.getElementById("pl-play-detail").addEventListener("click", () => {
        if (pl.tracks && pl.tracks.length) window.OMTPlayer.setQueue(pl.tracks, pl.tracks[0].id);
      });
      document.getElementById("pl-add-track").addEventListener("change", async (e) => {
        const tid = Number(e.target.value);
        if (!tid) return;
        await api(`/api/playlists/${id}/tracks`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ track_id: tid }),
        });
        showPlaylist(id);
        loadPlaylists();
      });
      listEl.querySelectorAll(".pl-rm").forEach((b) =>
        b.addEventListener("click", async () => {
          await api(`/api/playlists/${id}/tracks/${b.dataset.id}`, { method: "DELETE" });
          showPlaylist(id);
          loadPlaylists();
        })
      );
      const ids = (pl.tracks || []).map((t) => t.id);
      listEl.querySelectorAll(".pl-up").forEach((b) =>
        b.addEventListener("click", async () => {
          const tid = Number(b.dataset.id);
          const i = ids.indexOf(tid);
          if (i <= 0) return;
          [ids[i - 1], ids[i]] = [ids[i], ids[i - 1]];
          await api(`/api/playlists/${id}/tracks`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ track_ids: ids }),
          });
          showPlaylist(id);
        })
      );
      listEl.querySelectorAll(".pl-down").forEach((b) =>
        b.addEventListener("click", async () => {
          const tid = Number(b.dataset.id);
          const i = ids.indexOf(tid);
          if (i < 0 || i >= ids.length - 1) return;
          [ids[i + 1], ids[i]] = [ids[i], ids[i + 1]];
          await api(`/api/playlists/${id}/tracks`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ track_ids: ids }),
          });
          showPlaylist(id);
        })
      );
      listEl.querySelectorAll(".track").forEach((row) => {
        row.addEventListener("click", (e) => {
          if (e.target.closest("button")) return;
          const start = Number(row.dataset.id);
          window.OMTPlayer.setQueue(pl.tracks, start);
        });
      });
    } catch (err) {
      box.innerHTML = `<p class="muted">${escapeHtml(err.message)}</p>`;
    }
  }

  async function playPlaylist(id) {
    const pl = await api(`/api/playlists/${id}`);
    if (pl.tracks && pl.tracks.length) window.OMTPlayer.setQueue(pl.tracks, pl.tracks[0].id);
  }

  async function renamePlaylist(id) {
    const title = prompt("Новое название");
    if (!title) return;
    await api(`/api/playlists/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    loadPlaylists();
  }

  async function deletePlaylist(id) {
    if (!confirm("Удалить плейлист?")) return;
    await api(`/api/playlists/${id}`, { method: "DELETE" });
    document.getElementById("playlist-detail").classList.add("hidden");
    loadPlaylists();
  }

  document.getElementById("playlist-create").addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("playlist-title").value.trim();
    if (!title) return;
    try {
      const pl = await api("/api/playlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      document.getElementById("playlist-title").value = "";
      await loadPlaylists();
      showPlaylist(pl.id);
    } catch (err) {
      alert(err.message);
    }
  });

  async function loadFavorites() {
    const el = document.getElementById("favorites-list");
    try {
      const data = await api("/api/favorites");
      data.tracks.forEach((t) => (t.is_favorite = 1));
      renderTracks(el, data.tracks, { empty: "Пока нет избранного" });
    } catch (err) {
      el.innerHTML = `<p class="muted">${escapeHtml(err.message)}</p>`;
    }
  }

  async function loadHistory() {
    const el = document.getElementById("history-list");
    try {
      const data = await api("/api/history");
      renderTracks(el, data.items, {
        empty: "История пуста",
        extra: (t) => escapeHtml(t.played_at || ""),
      });
    } catch (err) {
      el.innerHTML = `<p class="muted">${escapeHtml(err.message)}</p>`;
    }
  }

  document.getElementById("upload-input").addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    const status = document.getElementById("upload-status");
    if (!file) return;
    status.textContent = "Загрузка…";
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api("/api/upload", { method: "POST", body: fd });
      status.textContent = "Готово";
      await loadLibrary();
    } catch (err) {
      status.textContent = err.message;
    }
    e.target.value = "";
  });

  let pollTimer = null;

  async function loadImport() {
    const lt = document.getElementById("lt-status");
    try {
      const st = await api("/api/import/status");
      lt.textContent = st.available
        ? "libtorrent: доступен"
        : `libtorrent: недоступен (${st.error || "not installed"}) — список файлов может быть stub`;
    } catch (err) {
      lt.textContent = err.message;
    }
    await refreshJobs();
  }

  async function refreshJobs() {
    const el = document.getElementById("jobs-list");
    try {
      const data = await api("/api/import/jobs");
      el.innerHTML = data.jobs
        .map(
          (j) => `
        <div class="job-row" data-job="${j.id}">
          <span>#${j.id} · ${escapeHtml(j.source_type)} · ${escapeHtml(j.status)}${j.progress ? " · " + Math.round(j.progress * 100) + "%" : ""}</span>
          <button type="button" class="btn btn-ghost job-open" data-job="${j.id}">Открыть</button>
        </div>`
        )
        .join("") || `<p class="muted">Нет заданий</p>`;
      el.querySelectorAll(".job-open").forEach((btn) => {
        btn.addEventListener("click", () => showJob(Number(btn.dataset.job)));
      });
    } catch (err) {
      el.innerHTML = `<p class="muted">${escapeHtml(err.message)}</p>`;
    }
  }

  async function showJob(jobId) {
    const box = document.getElementById("import-job");
    box.classList.remove("hidden");
    const job = await api(`/api/import/jobs/${jobId}`);
    const files = job.file_list || [];
    if (job.status === "awaiting_confirm" || (files.length && job.status !== "done")) {
      box.innerHTML = `
        <h3>Задание #${job.id}</h3>
        <p class="muted">${escapeHtml(job.status)}${job.error ? " — " + escapeHtml(job.error) : ""}</p>
        <div class="file-pick">
          ${files
            .map(
              (f) => `
            <label>
              <input type="checkbox" value="${f.index}" ${f.audio ? "checked" : ""} />
              <span>${escapeHtml(f.path)} <span class="muted">(${f.size} bytes)${f.audio ? "" : " · not audio"}</span></span>
            </label>`
            )
            .join("")}
        </div>
        <label class="legal-check">
          <input type="checkbox" id="legal-ok" />
          <span>Подтверждаю, что у меня есть законное право скачивать и хранить выбранные файлы (личная копия / лицензия / общественное достояние).</span>
        </label>
        <button type="button" class="btn" id="confirm-import">Подтвердить и скачать</button>
      `;
      document.getElementById("confirm-import").addEventListener("click", async () => {
        const selected = [...box.querySelectorAll(".file-pick input:checked")].map((i) =>
          Number(i.value)
        );
        const legal = document.getElementById("legal-ok").checked;
        try {
          await api(`/api/import/jobs/${jobId}/confirm`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ selected, legal_confirmed: legal }),
          });
          startPoll(jobId);
        } catch (err) {
          alert(err.message);
        }
      });
    } else {
      box.innerHTML = `
        <h3>Задание #${job.id}</h3>
        <p>Статус: <strong>${escapeHtml(job.status)}</strong> · прогресс ${Math.round((job.progress || 0) * 100)}%</p>
        ${job.error ? `<p style="color:var(--danger)">${escapeHtml(job.error)}</p>` : ""}
      `;
      if (["downloading", "uploading", "listing", "pending"].includes(job.status)) {
        startPoll(jobId);
      }
    }
  }

  function startPoll(jobId) {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      try {
        await showJob(jobId);
        await refreshJobs();
        const job = await api(`/api/import/jobs/${jobId}`);
        if (["done", "error", "cancelled", "awaiting_confirm"].includes(job.status)) {
          clearInterval(pollTimer);
          pollTimer = null;
          if (job.status === "done") loadLibrary();
        }
      } catch (_) {
        /* ignore transient */
      }
    }, 2000);
  }

  document.getElementById("magnet-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const magnet = document.getElementById("magnet-input").value.trim();
    const fd = new FormData();
    fd.append("magnet", magnet);
    try {
      const res = await api("/api/import/magnet", { method: "POST", body: fd });
      startPoll(res.job_id);
      await refreshJobs();
      setTimeout(() => showJob(res.job_id), 800);
    } catch (err) {
      alert(err.message);
    }
  });

  document.getElementById("torrent-input").addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await api("/api/import/torrent", { method: "POST", body: fd });
      startPoll(res.job_id);
      await refreshJobs();
      setTimeout(() => showJob(res.job_id), 800);
    } catch (err) {
      alert(err.message);
    }
    e.target.value = "";
  });

  refreshAuth()
    .then(async (st) => {
      if (st.authenticated) {
        await loadLibrary();
        await loadScanStatus();
      }
    })
    .catch((err) => {
      authLabel.textContent = err.message;
    });
})();
