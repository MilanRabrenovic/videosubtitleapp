(() => {
  const api = {};
  let helpers = {};
  let timeline = null;
  let overlay = null;
  let viewport = null;
  let playhead = null;

  const ensureElements = () => {
    if (!timeline) {
      timeline = document.getElementById("timeline");
      overlay = document.getElementById("timeline-overlay");
      viewport = document.getElementById("timeline-viewport");
      playhead = document.getElementById("timeline-playhead");
    }
  };

  const getDuration = () => {
    if (!timeline) {
      return 0;
    }
    const duration = Number(timeline.dataset.duration || 0);
    return Number.isFinite(duration) ? duration : 0;
  };

  const getWindowDuration = (duration) => {
    const fallback = helpers.TIMELINE_WINDOW_SECONDS || 30;
    return Math.min(fallback, duration || 0);
  };

  const totalWidthFor = (duration, windowDuration, viewportWidth) => {
    const waveformWidth = Number(timeline?.dataset.waveformWidth || 0);
    if (duration <= windowDuration) {
      return viewportWidth;
    }
    return Math.max(
      viewportWidth,
      waveformWidth > 0 ? waveformWidth : viewportWidth * (duration / windowDuration)
    );
  };

  const updateWaveformWindow = (totalWidth) => {
    const image = helpers.waveformImage;
    if (!image || !totalWidth) {
      return;
    }
    image.style.width = `${totalWidth}px`;
    image.style.transform = "translateX(0)";
  };

  const getSuppressUntil = () => {
    if (typeof helpers.getSuppressTimelineAutoScrollUntil === 'function') {
      return helpers.getSuppressTimelineAutoScrollUntil();
    }
    return helpers.suppressTimelineAutoScrollUntil || 0;
  };

  const syncTimelineScroll = (duration, windowDuration, viewportWidth, totalWidth) => {
    if (!viewport || !duration || !viewportWidth || !totalWidth) {
      return;
    }
    if (Date.now() < getSuppressUntil()) {
      return;
    }
    if (duration <= windowDuration) {
      viewport.scrollLeft = 0;
      return;
    }
    const targetCenter = (helpers.previewVideo.currentTime / duration) * totalWidth;
    const desiredLeft = Math.max(0, targetCenter - viewportWidth / 2);
    const maxScroll = Math.max(0, totalWidth - viewportWidth);
    viewport.scrollLeft = Math.min(desiredLeft, maxScroll);
  };

  const updatePlayhead = () => {
    ensureElements();
    if (!timeline || !playhead || !viewport || !helpers.previewVideo) {
      return;
    }
    const duration = getDuration();
    if (!duration) {
      return;
    }
    const viewportWidth = viewport.clientWidth;
    if (!viewportWidth) {
      return;
    }
    const windowDuration = getWindowDuration(duration);
    const totalWidth = totalWidthFor(duration, windowDuration, viewportWidth);
    timeline.style.width = `${totalWidth}px`;
    playhead.style.left = `${(helpers.previewVideo.currentTime / duration) * 100}%`;
    updateWaveformWindow(totalWidth);
    syncTimelineScroll(duration, windowDuration, viewportWidth, totalWidth);
  };

  const render = () => {
    ensureElements();
    if (!timeline || !overlay || !viewport || !helpers.subtitleList) {
      return;
    }
    const duration = getDuration();
    if (!duration) {
      return;
    }
    const viewportWidth = viewport.clientWidth;
    if (!viewportWidth) {
      return;
    }
    const windowDuration = getWindowDuration(duration);
    const totalWidth = totalWidthFor(duration, windowDuration, viewportWidth);
    timeline.style.width = `${totalWidth}px`;
    updateWaveformWindow(totalWidth);
    if (helpers.previewVideo) {
      syncTimelineScroll(duration, windowDuration, viewportWidth, totalWidth);
    }
    overlay.innerHTML = "";
    const blocks = helpers.subtitleList.querySelectorAll(".subtitle-block");
    blocks.forEach((block) => {
      const startValue = block.querySelector(".start").value.trim();
      const endValue = block.querySelector(".end").value.trim();
      const start = helpers.parseTimestamp(startValue);
      const end = helpers.parseTimestamp(endValue);
      if (start === null || end === null || end <= start) {
        return;
      }
      const left = (start / duration) * 100;
      const width = ((end - start) / duration) * 100;
      const bar = document.createElement("div");
      bar.className =
        "timeline-block absolute top-3 h-4 rounded-sm border border-slate-300/40 bg-slate-200/35";
      bar.style.left = `${left}%`;
      bar.style.width = `${width}%`;
      bar.dataset.index = block.dataset.index || "";
      const textValue = block.querySelector(".text")?.value || "";
      const wordCount = textValue.trim() ? textValue.trim().split(/\s+/).length : 0;
      bar.innerHTML =
        "<span class='handle-left absolute top-0 h-full cursor-ew-resize' style='left:-4px;width:8px;'></span>" +
        "<span class='handle-right absolute top-0 h-full cursor-ew-resize' style='right:-4px;width:8px;'></span>" +
        "<span class='handle-left absolute left-0 top-0 h-full w-px bg-slate-500/60 pointer-events-none'></span>" +
        "<span class='handle-right absolute right-0 top-0 h-full w-px bg-slate-500/60 pointer-events-none'></span>";
      overlay.appendChild(bar);
      if (wordCount > 1) {
        const barWidth = bar.getBoundingClientRect().width;
        if (barWidth >= 18) {
          const maxSeparators = Math.min(wordCount - 1, 30);
          for (let i = 1; i <= maxSeparators; i += 1) {
            const leftPos = (i / wordCount) * barWidth;
            const separator = document.createElement("span");
            separator.className = "absolute inset-y-1 w-px bg-slate-500/20";
            separator.style.left = `${leftPos}px`;
            bar.appendChild(separator);
          }
        }
      }

      const onPointerDown = (event, mode) => {
        event.preventDefault();
        const startSeconds = helpers.parseTimestamp(block.querySelector(".start").value.trim()) || 0;
        const endSeconds = helpers.parseTimestamp(block.querySelector(".end").value.trim()) || startSeconds + 0.1;
        const length = endSeconds - startSeconds;
        const startX = event.clientX;
        const onMove = (moveEvent) => {
          helpers.markTimelineDirty(block.dataset.index);
          const delta = moveEvent.clientX - startX;
          const deltaSeconds = (delta / totalWidth) * duration;
          let nextStart = startSeconds;
          let nextEnd = endSeconds;
          if (mode === "move") {
            nextStart = Math.max(0, Math.min(duration - length, startSeconds + deltaSeconds));
            nextEnd = nextStart + length;
          } else if (mode === "start") {
            nextStart = Math.max(0, Math.min(endSeconds - 0.05, startSeconds + deltaSeconds));
          } else if (mode === "end") {
            nextEnd = Math.min(duration, Math.max(startSeconds + 0.05, endSeconds + deltaSeconds));
          }
          block.querySelector(".start").value = helpers.formatTimestamp(nextStart);
          block.querySelector(".end").value = helpers.formatTimestamp(nextEnd);
          helpers.hiddenInput.value = JSON.stringify(helpers.collectSubtitles());
          helpers.markDirty();
          helpers.updateBlockDurations();
          const newLeft = (nextStart / duration) * 100;
          const newWidth = ((nextEnd - nextStart) / duration) * 100;
          bar.style.left = `${newLeft}%`;
          bar.style.width = `${newWidth}%`;
        };
        const onUp = () => {
          document.removeEventListener("pointermove", onMove);
          document.removeEventListener("pointerup", onUp);
        };
        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp);
      };

      bar.addEventListener("pointerdown", (event) => {
        if (event.target.classList.contains("handle-left")) {
          onPointerDown(event, "start");
        } else if (event.target.classList.contains("handle-right")) {
          onPointerDown(event, "end");
        } else {
          onPointerDown(event, "move");
        }
      });
      bar.addEventListener("click", (event) => {
        event.stopPropagation();
        const index = Number(bar.dataset.index);
        if (Number.isNaN(index)) {
          return;
        }
        const target = helpers.subtitleList.querySelector(`.subtitle-block[data-index="${index}"]`);
        if (!target) {
          return;
        }
        if (helpers.focusedBlock && helpers.focusedStart && helpers.focusedEnd && helpers.focusedText) {
          helpers.focusedBlock.classList.remove("hidden");
          helpers.focusedBlock.dataset.index = String(index);
          const allBars = overlay.querySelectorAll(".timeline-block");
          allBars.forEach((item) => {
            item.classList.remove("is-active");
          });
          bar.classList.add("is-active");
          if (helpers.focusedLabel) {
            helpers.focusedLabel.textContent = `Block ${index + 1}`;
          }
          helpers.focusedStart.value = target.querySelector(".start").value;
          helpers.focusedEnd.value = target.querySelector(".end").value;
          helpers.focusedText.value = target.querySelector(".text").value;
          helpers.focusedStart.focus();
        }
      });
    });
    updatePlayhead();
  };

  const init = () => {
    ensureElements();
    if (!timeline || !overlay || !viewport) {
      return;
    }
    if (helpers.waveformImage) {
      helpers.waveformImage.addEventListener("load", () => {
        render();
      });
    }
    if (helpers.previewVideo) {
      let rafId = null;
      const tick = () => {
        updatePlayhead();
        rafId = requestAnimationFrame(tick);
      };
      const startTick = () => {
        if (rafId !== null) {
          return;
        }
        rafId = requestAnimationFrame(tick);
      };
      const stopTick = () => {
        if (rafId === null) {
          return;
        }
        cancelAnimationFrame(rafId);
        rafId = null;
      };
      helpers.previewVideo.addEventListener("play", startTick);
      helpers.previewVideo.addEventListener("pause", stopTick);
      helpers.previewVideo.addEventListener("ended", stopTick);
      helpers.previewVideo.addEventListener("seeked", updatePlayhead);
      helpers.previewVideo.addEventListener("loadedmetadata", updatePlayhead);
    }
    if (viewport && helpers.previewVideo) {
      viewport.addEventListener("click", (event) => {
        const duration = getDuration();
        if (!duration) {
          return;
        }
        const rect = viewport.getBoundingClientRect();
        const x = Math.min(Math.max(event.clientX - rect.left, 0), rect.width);
        const windowDuration = getWindowDuration(duration);
        const totalWidth = totalWidthFor(duration, windowDuration, viewport.clientWidth);
        const absoluteX = viewport.scrollLeft + x;
        const targetTime = (absoluteX / totalWidth) * duration;
        helpers.previewVideo.currentTime = targetTime;
        render();
        updatePlayhead();
      });
    }
  };

  api.setHelpers = (value) => {
    helpers = { ...helpers, ...(value || {}) };
  };
  api.init = init;
  api.render = render;
  api.updatePlayhead = updatePlayhead;
  window.SubtitleTimeline = api;
})();
