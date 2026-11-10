/** OneMoreTime player — play/pause, seek, rate, repeat, shuffle, queue */
(function () {
  const audio = document.getElementById("audio");
  const btnPlay = document.getElementById("btn-play");
  const btnPrev = document.getElementById("btn-prev");
  const btnNext = document.getElementById("btn-next");
  const btnShuffle = document.getElementById("btn-shuffle");
  const btnRepeat = document.getElementById("btn-repeat");
  const seek = document.getElementById("seek");
  const rate = document.getElementById("rate");
  const timeCur = document.getElementById("time-cur");
  const timeDur = document.getElementById("time-dur");
  const nowTitle = document.getElementById("now-title");
  const nowArtist = document.getElementById("now-artist");

  const state = {
    queue: [],
    index: -1,
    shuffle: false,
    repeat: "off", // off | one | all
    seeking: false,
  };

  function fmt(sec) {
    if (!Number.isFinite(sec)) return "0:00";
    const s = Math.max(0, Math.floor(sec));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}:${r.toString().padStart(2, "0")}`;
  }

  function current() {
    return state.index >= 0 ? state.queue[state.index] : null;
  }

  function setQueue(tracks, startId) {
    state.queue = tracks.slice();
    const idx = tracks.findIndex((t) => t.id === startId);
    state.index = idx >= 0 ? idx : tracks.length ? 0 : -1;
    if (state.index >= 0) playIndex(state.index, true);
  }

  function playIndex(i, autoplay) {
    if (i < 0 || i >= state.queue.length) return;
    state.index = i;
    const t = state.queue[i];
    nowTitle.textContent = t.title || "Track";
    nowArtist.textContent = t.artist || "";
    audio.src = `/api/stream/${t.id}`;
    audio.load();
    document.querySelectorAll(".track").forEach((el) => {
      el.classList.toggle("is-playing", Number(el.dataset.id) === t.id);
    });
    if (autoplay) {
      audio.play().catch((err) => {
        nowArtist.textContent = (nowArtist.textContent || "") +
          (err && err.message ? ` · ${err.message}` : " · playback failed");
      });
      btnPlay.textContent = "⏸";
    }
    audio.addEventListener(
      "error",
      () => {
        const code = audio.error && audio.error.code;
        nowArtist.textContent = `Ошибка потока${code ? " (" + code + ")" : ""} — проверьте вход / Диск`;
      },
      { once: true }
    );
    if (window.OMT && typeof window.OMT.onPlay === "function") {
      window.OMT.onPlay(t);
    }
  }

  function togglePlay() {
    if (!audio.src) {
      if (state.queue.length) playIndex(Math.max(state.index, 0), true);
      return;
    }
    if (audio.paused) {
      audio.play().catch(() => {});
      btnPlay.textContent = "⏸";
    } else {
      audio.pause();
      btnPlay.textContent = "▶";
    }
  }

  function next() {
    if (!state.queue.length) return;
    if (state.shuffle) {
      let n = Math.floor(Math.random() * state.queue.length);
      if (state.queue.length > 1 && n === state.index) n = (n + 1) % state.queue.length;
      playIndex(n, true);
      return;
    }
    if (state.index + 1 < state.queue.length) {
      playIndex(state.index + 1, true);
    } else if (state.repeat === "all") {
      playIndex(0, true);
    }
  }

  function prev() {
    if (!state.queue.length) return;
    if (audio.currentTime > 3) {
      audio.currentTime = 0;
      return;
    }
    if (state.shuffle) {
      next();
      return;
    }
    if (state.index > 0) playIndex(state.index - 1, true);
    else if (state.repeat === "all") playIndex(state.queue.length - 1, true);
  }

  btnPlay.addEventListener("click", togglePlay);
  btnNext.addEventListener("click", next);
  btnPrev.addEventListener("click", prev);

  btnShuffle.addEventListener("click", () => {
    state.shuffle = !state.shuffle;
    btnShuffle.setAttribute("aria-pressed", String(state.shuffle));
    btnShuffle.classList.toggle("is-on", state.shuffle);
  });

  btnRepeat.addEventListener("click", () => {
    const order = ["off", "all", "one"];
    const i = order.indexOf(state.repeat);
    state.repeat = order[(i + 1) % order.length];
    btnRepeat.dataset.mode = state.repeat;
    btnRepeat.classList.toggle("is-on", state.repeat !== "off");
    btnRepeat.textContent = state.repeat === "one" ? "Rep1" : "Repeat";
    audio.loop = state.repeat === "one";
  });

  rate.addEventListener("change", () => {
    audio.playbackRate = Number(rate.value) || 1;
  });

  seek.addEventListener("input", () => {
    state.seeking = true;
  });
  seek.addEventListener("change", () => {
    if (audio.duration) {
      audio.currentTime = (Number(seek.value) / 1000) * audio.duration;
    }
    state.seeking = false;
  });

  audio.addEventListener("timeupdate", () => {
    timeCur.textContent = fmt(audio.currentTime);
    if (!state.seeking && audio.duration) {
      seek.value = String(Math.round((audio.currentTime / audio.duration) * 1000));
    }
  });
  audio.addEventListener("loadedmetadata", () => {
    timeDur.textContent = fmt(audio.duration);
  });
  audio.addEventListener("play", () => { btnPlay.textContent = "⏸"; });
  audio.addEventListener("pause", () => { btnPlay.textContent = "▶"; });
  audio.addEventListener("ended", () => {
    if (state.repeat === "one") return;
    next();
  });

  window.OMTPlayer = { setQueue, playIndex, next, prev, current, state };
})();
