(() => {
  const form = document.getElementById("subtitle-form");
  const subtitleList = document.getElementById("subtitle-list");
  const hiddenInput = document.getElementById("subtitles-json");
  const status = document.getElementById("edit-status");
  const saveStatus = document.getElementById("save-status");
  const timestampHint = document.getElementById("timestamp-hint");
  const exportStatus = document.getElementById("export-status");
  const exportSrtButton = document.querySelector("[data-export='srt']");
  const exportKaraokeButtons = document.querySelectorAll("[data-export='video-karaoke']");
  const exportVideoStatus = document.getElementById("video-export-status");
  const previewVideo = document.getElementById("preview-video");
  const saveButton = document.getElementById("save-button");
  const exportForms = document.querySelectorAll("form[action^='/export/']");
  const fontUploadButton = document.getElementById("font-upload-button");
  const pinSubmit = document.getElementById("pin-submit");
  const subtitleInputs = form ? form.querySelectorAll("input, select, textarea, button") : [];
  const jobStatus = document.getElementById("job-status");
  const previewJob = document.getElementById("preview-job");
  const editorJob = document.getElementById("editor-job");
  const timelineReset = document.getElementById("timeline-reset");
  const saveBar = document.getElementById("save-bar");
  const saveBarButton = document.getElementById("save-bar-button");
  const blockCount = document.getElementById("block-count");
  const focusedBlock = document.getElementById("focused-block");
  const focusedLabel = document.getElementById("focused-block-label");
  const focusedStart = document.getElementById("focused-start");
  const focusedEnd = document.getElementById("focused-end");
  const focusedText = document.getElementById("focused-text");
  const focusedDelete = document.getElementById("focused-delete");
  const pinForm = document.getElementById("pin-form");
  const pinCheckbox = document.getElementById("pin-checkbox");
  const pinStatus = document.getElementById("pin-status");
  const toast = document.getElementById("toast");
  const toastClasses = {
    info: "bg-slate-900/90 text-white border border-slate-700/60",
    success: "bg-emerald-50 text-emerald-900 border border-emerald-200",
    error: "bg-rose-50 text-rose-900 border border-rose-200",
    warning: "bg-amber-50 text-amber-900 border border-amber-200",
  };
  const fontLicenseConfirm = document.getElementById("font-license-confirm");
  const fontInput = document.getElementById("font-input");
  const fontValue = document.getElementById("font-value");
  const fontOptions = document.getElementById("font-options");
  const longVideoWarning = document.getElementById("long-video-warning");
  const waveformImage = document.getElementById("waveform-image");
  const TIMELINE_WINDOW_SECONDS = 30;
  const timestampPattern = /^\d{2}:\d{2}:\d{2},\d{3}$/;
  let isDirty = false;
  let saveTimeoutId = null;
  let toastTimer = null;
  let timelineBaseline = null;
  let timelineDirty = false;
  let suppressTimelineAutoScrollUntil = 0;

  const setProcessingState = (isProcessing) => {
    if (saveButton) {
      saveButton.disabled = isProcessing;
    }
    if (saveBarButton) {
      saveBarButton.disabled = isProcessing;
    }
    exportForms.forEach((formEl) => {
      const button = formEl.querySelector("button");
      if (button) {
        button.disabled = isProcessing;
      }
    });
    if (fontUploadButton) {
      fontUploadButton.disabled = isProcessing || !fontLicenseConfirm?.checked;
    }
    if (pinSubmit) {
      pinSubmit.disabled = isProcessing;
    }
    subtitleInputs.forEach((el) => {
      if (el === saveButton) {
        return;
      }
      if (el === fontUploadButton) {
        return;
      }
      if (el === pinSubmit) {
        return;
      }
      if (el.type === "hidden") {
        return;
      }
      el.disabled = isProcessing;
    });
  };

  const showToast = (message, type = "info", timeout = 2200) => {
    if (!toast) {
      return;
    }
    const base =
      "pointer-events-none fixed bottom-6 left-1/2 z-50 w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 rounded-xl px-4 py-3 text-center text-sm font-medium shadow-lg backdrop-blur";
    toast.className = `${base} ${toastClasses[type] || toastClasses.info}`;
    toast.textContent = message;
    toast.classList.remove("hidden");
    if (toastTimer) {
      clearTimeout(toastTimer);
    }
    if (timeout > 0) {
      toastTimer = setTimeout(() => {
        toast.classList.add("hidden");
      }, timeout);
    }
  };

  const hideToast = () => {
    if (!toast) {
      return;
    }
    if (toastTimer) {
      clearTimeout(toastTimer);
    }
    toast.classList.add("hidden");
  };

  const formatDuration = (seconds) => {
    if (!Number.isFinite(seconds) || seconds <= 0) {
      return "";
    }
    const total = Math.round(seconds);
    const mins = Math.floor(total / 60);
    const hrs = Math.floor(mins / 60);
    const mm = String(mins % 60).padStart(2, "0");
    const ss = String(total % 60).padStart(2, "0");
    if (hrs > 0) {
      return `${hrs}:${mm}:${ss}`;
    }
    return `${mins}:${ss}`;
  };

  const formatJobError = (job) => {
    if (!job || !job.error) {
      return "Something went wrong.";
    }
    if (typeof job.error === "string") {
      return job.error;
    }
    const message = job.error.message || "Something went wrong.";
    const hint = job.error.hint ? ` ${job.error.hint}` : "";
    return `${message}${hint}`;
  };

  const formatJobFailure = (job, fallback) => {
    const step = job && job.failed_step ? `Failed during ${job.failed_step}. ` : "";
    const message = formatJobError(job);
    return `${step}${message || fallback}`;
  };

  const pollJob = (jobId, onComplete, onError) => {
    if (!jobId) {
      return null;
    }
    let cancelled = false;
    const pollOnce = async () => {
      try {
        const response = await fetch(`/jobs/${jobId}`);
        if (!response.ok) {
          throw new Error("Job status failed");
        }
        const job = await response.json();
        if (job.status === "completed") {
          cancelled = true;
          onComplete(job);
        } else if (job.status === "failed") {
          cancelled = true;
          onError(job);
        }
      } catch (error) {
        console.error(error);
      }
    };
    pollOnce();
    const interval = setInterval(() => {
      if (cancelled) {
        clearInterval(interval);
        return;
      }
      pollOnce();
    }, 2500);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  };

  const touchEditorJob = (jobId, locked) => {
    if (!jobId) {
      return;
    }
    const formData = new FormData();
    if (locked !== null && locked !== undefined) {
      formData.append("locked", locked ? "on" : "off");
    }
    fetch(`/jobs/${jobId}/touch`, { method: "POST", body: formData }).catch((error) => {
      console.error(error);
    });
  };

  const startPreviewPolling = (jobId) => {
    if (!jobId) {
      return;
    }
    showToast("Rendering preview...", "info", 0);
    if (saveButton) {
      saveButton.disabled = true;
      saveButton.textContent = "Rendering preview...";
    }
    pollJob(
      jobId,
      () => {
        if (previewVideo) {
          const source = previewVideo.querySelector("source");
          if (source && source.src.includes("/media/outputs/")) {
            const cacheBuster = `v=${Date.now()}`;
            source.src = source.src.split("?")[0] + "?" + cacheBuster;
            previewVideo.load();
          }
        }
        hideToast();
        showToast("Preview updated.", "success");
        if (saveButton) {
          saveButton.disabled = false;
          saveButton.textContent = saveButton.dataset.originalText || "Save edits";
        }
      },
        (job) => {
          hideToast();
          showToast(formatJobFailure(job, "Preview failed."), "error", 3200);
          showErrorPanel(job);
          if (saveButton) {
            saveButton.disabled = false;
            saveButton.textContent = saveButton.dataset.originalText || "Save edits";
        }
      }
    );
  };

  const hasInvalidTimestamps = () => {
    const blocks = subtitleList.querySelectorAll(".subtitle-block");
    return Array.from(blocks).some((block) => {
      const start = block.querySelector(".start").value.trim();
      const end = block.querySelector(".end").value.trim();
      return !timestampPattern.test(start) || !timestampPattern.test(end);
    });
  };

  const parseTimestamp = (value) => {
    if (!timestampPattern.test(value)) {
      return null;
    }
    const [hours, minutes, secondsMs] = value.split(":");
    const [seconds, millis] = secondsMs.split(",");
    return (
      Number(hours) * 3600 +
      Number(minutes) * 60 +
      Number(seconds) +
      Number(millis) / 1000
    );
  };

  const formatTimestamp = (totalSeconds) => {
    const safe = Math.max(0, totalSeconds || 0);
    const hours = Math.floor(safe / 3600);
    const minutes = Math.floor((safe % 3600) / 60);
    const seconds = Math.floor(safe % 60);
    const millis = Math.floor((safe - Math.floor(safe)) * 1000);
    const pad = (value, size) => String(value).padStart(size, "0");
    return `${pad(hours, 2)}:${pad(minutes, 2)}:${pad(seconds, 2)},${pad(millis, 3)}`;
  };

  const updateBlockDurations = () => {
    const blocks = subtitleList.querySelectorAll(".subtitle-block");
    if (blockCount) {
      blockCount.textContent = String(blocks.length);
    }
    blocks.forEach((block) => {
      const holder = block.querySelector(".block-duration");
      if (!holder) {
        return;
      }
      const start = block.querySelector(".start").value.trim();
      const end = block.querySelector(".end").value.trim();
      const startSeconds = parseTimestamp(start);
      const endSeconds = parseTimestamp(end);
      if (startSeconds === null || endSeconds === null || endSeconds < startSeconds) {
        holder.textContent = "--";
        return;
      }
      const duration = endSeconds - startSeconds;
      holder.textContent = `${duration.toFixed(2)}s`;
    });
  };

  const updatePlayhead = () => {
    const timeline = document.getElementById("timeline");
    const playhead = document.getElementById("timeline-playhead");
    const viewport = document.getElementById("timeline-viewport");
    if (!timeline || !playhead || !previewVideo || !viewport) {
      return;
    }
    const duration = Number(timeline.dataset.duration || 0);
    if (!duration) {
      return;
    }
    const viewportWidth = viewport.clientWidth;
    if (!viewportWidth) {
      return;
    }
    const windowDuration = Math.min(TIMELINE_WINDOW_SECONDS, duration);
    const waveformWidth = Number(timeline.dataset.waveformWidth || 0);
    const totalWidth =
      duration <= windowDuration
        ? viewportWidth
        : Math.max(
            viewportWidth,
            waveformWidth > 0 ? waveformWidth : viewportWidth * (duration / windowDuration)
          );
    timeline.style.width = `${totalWidth}px`;
    playhead.style.left = `${(previewVideo.currentTime / duration) * 100}%`;
    updateWaveformWindow(totalWidth);
    syncTimelineScroll(duration, windowDuration, viewportWidth, totalWidth);
  };

  const updateWaveformWindow = (totalWidth) => {
    if (!waveformImage || !totalWidth) {
      return;
    }
    waveformImage.style.width = `${totalWidth}px`;
    waveformImage.style.transform = "translateX(0)";
  };

  const syncTimelineScroll = (duration, windowDuration, viewportWidth, totalWidth) => {
    const viewport = document.getElementById("timeline-viewport");
    if (!viewport || !duration || !viewportWidth || !totalWidth) {
      return;
    }
    if (Date.now() < suppressTimelineAutoScrollUntil) {
      return;
    }
    if (duration <= windowDuration) {
      viewport.scrollLeft = 0;
      return;
    }
    const targetCenter = (previewVideo.currentTime / duration) * totalWidth;
    const desiredLeft = Math.max(0, targetCenter - viewportWidth / 2);
    const maxScroll = Math.max(0, totalWidth - viewportWidth);
    viewport.scrollLeft = Math.min(desiredLeft, maxScroll);
  };

  const renderTimeline = () => {
    const timeline = document.getElementById("timeline");
    const overlay = document.getElementById("timeline-overlay");
    const viewport = document.getElementById("timeline-viewport");
    if (!timeline || !overlay || !viewport) {
      return;
    }
    const duration = Number(timeline.dataset.duration || 0);
    if (!duration || Number.isNaN(duration)) {
      return;
    }
    const viewportWidth = viewport.clientWidth;
    if (!viewportWidth) {
      return;
    }
    const windowDuration = Math.min(TIMELINE_WINDOW_SECONDS, duration);
    const waveformWidth = Number(timeline.dataset.waveformWidth || 0);
    const totalWidth =
      duration <= windowDuration
        ? viewportWidth
        : Math.max(
            viewportWidth,
            waveformWidth > 0 ? waveformWidth : viewportWidth * (duration / windowDuration)
          );
    timeline.style.width = `${totalWidth}px`;
    updateWaveformWindow(totalWidth);
    if (previewVideo) {
      syncTimelineScroll(duration, windowDuration, viewportWidth, totalWidth);
    }
    overlay.innerHTML = "";
    const blocks = subtitleList.querySelectorAll(".subtitle-block");
    blocks.forEach((block) => {
      const startValue = block.querySelector(".start").value.trim();
      const endValue = block.querySelector(".end").value.trim();
      const start = parseTimestamp(startValue);
      const end = parseTimestamp(endValue);
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
        const startSeconds = parseTimestamp(block.querySelector(".start").value.trim()) || 0;
        const endSeconds = parseTimestamp(block.querySelector(".end").value.trim()) || startSeconds + 0.1;
        const length = endSeconds - startSeconds;
        const startX = event.clientX;
        const onMove = (moveEvent) => {
          markTimelineDirty();
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
          block.querySelector(".start").value = formatTimestamp(nextStart);
          block.querySelector(".end").value = formatTimestamp(nextEnd);
          hiddenInput.value = JSON.stringify(collectSubtitles());
          markDirty();
          updateBlockDurations();
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
        const target = subtitleList.querySelector(`.subtitle-block[data-index="${index}"]`);
        if (!target) {
          return;
        }
        if (focusedBlock && focusedStart && focusedEnd && focusedText) {
          focusedBlock.classList.remove("hidden");
          focusedBlock.dataset.index = String(index);
          const allBars = overlay.querySelectorAll(".timeline-block");
          allBars.forEach((item) => {
            item.classList.remove("is-active");
          });
          bar.classList.add("is-active");
          if (focusedLabel) {
            focusedLabel.textContent = `Block ${index + 1}`;
          }
          focusedStart.value = target.querySelector(".start").value;
          focusedEnd.value = target.querySelector(".end").value;
          focusedText.value = target.querySelector(".text").value;
          focusedStart.focus();
        }
      });
    });
    updatePlayhead();
  };

  if (!form || !subtitleList || !hiddenInput) {
    return;
  }

  if (fontInput && fontValue && fontOptions) {
    const options = Array.from(fontOptions.querySelectorAll(".font-option"));
    const filterOptions = () => {
      const query = fontInput.value.trim().toLowerCase();
      options.forEach((option) => {
        const label = option.dataset.value.toLowerCase();
        option.style.display = label.includes(query) ? "block" : "none";
      });
    };

    fontInput.addEventListener("focus", () => {
      fontOptions.hidden = false;
      filterOptions();
    });

    fontInput.addEventListener("input", () => {
      fontValue.value = fontInput.value.trim();
      filterOptions();
    });

    options.forEach((option) => {
      option.addEventListener("click", () => {
        const value = option.dataset.value;
        fontInput.value = value;
        fontValue.value = value;
        fontOptions.hidden = true;
      });
    });

    document.addEventListener("click", (event) => {
      if (!fontOptions.contains(event.target) && event.target !== fontInput) {
        fontOptions.hidden = true;
      }
    });
  }

  const colorInputs = document.querySelectorAll(".color-input");
  if (colorInputs.length) {
    const updateColor = (key, value) => {
      const dot = document.querySelector(`.color-dot[data-color-key="${key}"]`);
      const hex = document.querySelector(`.color-hex[data-color-key="${key}"]`);
      if (dot) {
        dot.style.backgroundColor = value;
      }
      if (hex) {
        hex.textContent = value;
      }
    };
    colorInputs.forEach((input) => {
      const key = input.dataset.colorKey;
      if (!key) {
        return;
      }
      input.addEventListener("change", () => {
        updateColor(key, input.value);
      });
    });
    const triggers = document.querySelectorAll(".color-trigger");
    triggers.forEach((trigger) => {
      trigger.addEventListener("click", () => {
        const key = trigger.dataset.colorKey;
        const input = document.querySelector(`.color-input[data-color-key="${key}"]`);
        if (input) {
          input.click();
        }
      });
    });
  }

  if (fontLicenseConfirm && fontUploadButton) {
    const toggleFontUpload = () => {
      fontUploadButton.disabled = !fontLicenseConfirm.checked;
    };
    fontLicenseConfirm.addEventListener("change", toggleFontUpload);
    toggleFontUpload();
  }

  const collectSubtitles = () => {
    const blocks = subtitleList.querySelectorAll(".subtitle-block");
    return Array.from(blocks).map((block) => {
      const groupValue = Number(block.dataset.group);
      return {
        start: block.querySelector(".start").value.trim(),
        end: block.querySelector(".end").value.trim(),
        text: block.querySelector(".text").value.trim(),
        group_id: Number.isNaN(groupValue) ? null : groupValue,
      };
    });
  };

  const captureTimelineBaseline = () => {
    timelineBaseline = collectSubtitles();
    timelineDirty = false;
    if (timelineReset) {
      timelineReset.classList.add("hidden");
      timelineReset.disabled = true;
    }
  };

  const markTimelineDirty = () => {
    timelineDirty = true;
    if (timelineReset) {
      timelineReset.classList.remove("hidden");
      timelineReset.disabled = false;
    }
  };

  const markDirty = () => {
    if (exportStatus) {
      exportStatus.style.display = "none";
    }
    if (exportVideoStatus) {
      exportVideoStatus.style.display = "none";
    }
    if (exportVideoStatus) {
      exportVideoStatus.style.display = "none";
    }
    isDirty = true;
    if (saveBar) {
      saveBar.classList.remove("hidden");
      saveBar.classList.add("flex");
    }
  };

  subtitleList.addEventListener("input", () => {
    hiddenInput.value = JSON.stringify(collectSubtitles());
    markDirty();
    updateBlockDurations();
    renderTimeline();
    if (focusedBlock && focusedBlock.dataset.index) {
      const index = Number(focusedBlock.dataset.index);
      if (!Number.isNaN(index)) {
        const target = subtitleList.querySelector(`.subtitle-block[data-index="${index}"]`);
        if (target && focusedStart && focusedEnd && focusedText) {
          focusedStart.value = target.querySelector(".start").value;
          focusedEnd.value = target.querySelector(".end").value;
          focusedText.value = target.querySelector(".text").value;
        }
      }
    }
  });

  subtitleList.addEventListener("click", (event) => {
    const button = event.target.closest(".delete-block");
    if (!button) {
      return;
    }
    const block = button.closest(".subtitle-block");
    if (!block) {
      return;
    }
    block.remove();
    hiddenInput.value = JSON.stringify(collectSubtitles());
    markDirty();
    updateBlockDurations();
    renderTimeline();
  });

  const syncFocusedField = (field, selector) => {
    if (!focusedBlock || !field) {
      return;
    }
    const index = Number(focusedBlock.dataset.index || "");
    if (Number.isNaN(index)) {
      return;
    }
    const target = subtitleList.querySelector(`.subtitle-block[data-index="${index}"] ${selector}`);
    if (!target) {
      return;
    }
    target.value = field.value;
    hiddenInput.value = JSON.stringify(collectSubtitles());
    markDirty();
    updateBlockDurations();
    renderTimeline();
  };

  if (focusedStart) {
    focusedStart.addEventListener("input", () => {
      syncFocusedField(focusedStart, ".start");
    });
  }
  if (focusedEnd) {
    focusedEnd.addEventListener("input", () => {
      syncFocusedField(focusedEnd, ".end");
    });
  }
  if (focusedText) {
    focusedText.addEventListener("input", () => {
      syncFocusedField(focusedText, ".text");
    });
  }

  if (focusedDelete) {
    focusedDelete.addEventListener("click", () => {
      if (!focusedBlock) {
        return;
      }
      const index = Number(focusedBlock.dataset.index || "");
      if (Number.isNaN(index)) {
        return;
      }
      const target = subtitleList.querySelector(`.subtitle-block[data-index="${index}"]`);
      if (!target) {
        return;
      }
      target.remove();
      focusedBlock.classList.add("hidden");
      focusedBlock.dataset.index = "";
      hiddenInput.value = JSON.stringify(collectSubtitles());
      markDirty();
      updateBlockDurations();
      renderTimeline();
    });
  }

  const styleControls = form.querySelectorAll(
    "input[name^='style_'], select[name^='style_']"
  );
  styleControls.forEach((control) => {
    control.addEventListener("change", () => {
      markDirty();
    });
    control.addEventListener("input", () => {
      if (control.type !== "checkbox") {
        markDirty();
      }
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (saveButton && saveButton.disabled) {
      return;
    }
    hiddenInput.value = JSON.stringify(collectSubtitles());
    if (saveButton) {
      saveButton.disabled = true;
      saveButton.dataset.originalText = saveButton.dataset.originalText || saveButton.textContent;
      saveButton.textContent = "Saving...";
    }
    if (hasInvalidTimestamps()) {
      showToast("One or more timestamps look invalid (expected HH:MM:SS,mmm).", "warning", 3200);
    }
    const viewport = document.getElementById("timeline-viewport");
    const previousScroll = viewport ? viewport.scrollLeft : 0;
    try {
      const response = await fetch(form.action, { method: "POST", body: new FormData(form) });
      if (!response.ok) {
        let detail = "Save failed. Please try again.";
        if (response.status === 413) {
          detail = "Request too large. Try smaller changes.";
        } else if (response.status === 429) {
          detail = "Too many requests. Please wait a moment and try again.";
        }
        throw new Error(detail);
      }
      const html = await response.text();
      showToast("Subtitles saved.", "success");
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, "text/html");
      const updatedList = doc.getElementById("subtitle-list");
      if (updatedList) {
        subtitleList.innerHTML = updatedList.innerHTML;
        updateBlockDurations();
        renderTimeline();
        if (viewport) {
          suppressTimelineAutoScrollUntil = Date.now() + 1500;
          viewport.scrollLeft = previousScroll;
        }
      }
      const updatedForm = doc.getElementById("subtitle-form");
      if (updatedForm && form) {
        const fields = Array.from(form.querySelectorAll("input[name], select[name], textarea[name]"));
        fields.forEach((field) => {
          const name = field.getAttribute("name");
          if (!name) {
            return;
          }
          const updated = updatedForm.querySelector(`[name="${CSS.escape(name)}"]`);
          if (!updated) {
            return;
          }
          if (field.type === "checkbox") {
            field.checked = updated.checked;
          } else if (field.type === "radio") {
            field.checked = updated.checked;
          } else {
            field.value = updated.value;
          }
        });
      }
      const updatedJobStatus = doc.getElementById("job-status");
      if (updatedJobStatus && jobStatus) {
        jobStatus.textContent = updatedJobStatus.textContent || "";
        jobStatus.dataset.jobId = updatedJobStatus.dataset.jobId || "";
      }
      const updatedPreviewJob = doc.getElementById("preview-job");
      let queuedPreviewJob = false;
      if (updatedPreviewJob && previewJob) {
        previewJob.dataset.jobId = updatedPreviewJob.dataset.jobId || "";
        if (previewJob.dataset.jobId) {
          if (saveButton) {
            saveButton.textContent = "Rendering preview...";
          }
          queuedPreviewJob = true;
          startPreviewPolling(previewJob.dataset.jobId);
        }
      }
      if (previewVideo) {
        const source = previewVideo.querySelector("source");
        if (source && source.src.includes("/media/outputs/")) {
          const cacheBuster = `v=${Date.now()}`;
          source.src = source.src.split("?")[0] + "?" + cacheBuster;
          previewVideo.load();
        }
      }
      isDirty = false;
      if (saveBar) {
        saveBar.classList.add("hidden");
        saveBar.classList.remove("flex");
      }
      captureTimelineBaseline();
    } catch (error) {
      console.error(error);
      showToast(error.message || "Save failed. Please try again.", error.message?.includes("Too many") ? "warning" : "error", 3200);
    }
  if (saveButton && !queuedPreviewJob) {
    saveButton.disabled = false;
    saveButton.textContent = saveButton.dataset.originalText || "Save edits";
  }
  });

  // Initialize hidden input with current values.
  hiddenInput.value = JSON.stringify(collectSubtitles());
  isDirty = false;
  updateBlockDurations();
  renderTimeline();
  captureTimelineBaseline();
  if (waveformImage) {
    waveformImage.addEventListener("load", () => {
      renderTimeline();
    });
  }
  if (saveBar) {
    saveBar.classList.add("hidden");
    saveBar.classList.remove("flex");
  }
  if (longVideoWarning) {
    const duration = Number(longVideoWarning.dataset.duration || 0);
    const pretty = formatDuration(duration);
    const suffix = pretty ? ` (${pretty})` : "";
    showToast(`Long video${suffix}. Transcription may take a while.`, "warning", 5000);
  }

  if (previewVideo) {
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
    previewVideo.addEventListener("play", startTick);
    previewVideo.addEventListener("pause", stopTick);
    previewVideo.addEventListener("ended", stopTick);
    previewVideo.addEventListener("seeked", updatePlayhead);
    previewVideo.addEventListener("loadedmetadata", updatePlayhead);
  }

  const timeline = document.getElementById("timeline");
  const timelineViewport = document.getElementById("timeline-viewport");
  if (timelineViewport && timeline && previewVideo) {
    timelineViewport.addEventListener("click", (event) => {
      const duration = Number(timeline.dataset.duration || 0);
      if (!duration) {
        return;
      }
      const rect = timelineViewport.getBoundingClientRect();
      const x = Math.min(Math.max(event.clientX - rect.left, 0), rect.width);
      const windowDuration = Math.min(TIMELINE_WINDOW_SECONDS, duration);
      const waveformWidth = Number(timeline.dataset.waveformWidth || 0);
      const totalWidth =
        duration <= windowDuration
          ? timelineViewport.clientWidth
          : Math.max(
              timelineViewport.clientWidth,
              waveformWidth > 0
                ? waveformWidth
                : timelineViewport.clientWidth * (duration / windowDuration)
            );
      const absoluteX = timelineViewport.scrollLeft + x;
      const targetTime = (absoluteX / totalWidth) * duration;
      previewVideo.currentTime = targetTime;
      renderTimeline();
      updatePlayhead();
    });
  }

  if (timelineReset) {
    timelineReset.addEventListener("click", () => {
      if (!timelineBaseline || !timelineBaseline.length) {
        return;
      }
      const blocks = subtitleList.querySelectorAll(".subtitle-block");
      if (blocks.length !== timelineBaseline.length) {
        captureTimelineBaseline();
        return;
      }
      blocks.forEach((block, index) => {
        const baseline = timelineBaseline[index];
        if (!baseline) {
          return;
        }
        block.querySelector(".start").value = baseline.start;
        block.querySelector(".end").value = baseline.end;
      });
      hiddenInput.value = JSON.stringify(collectSubtitles());
      markDirty();
      updateBlockDurations();
      renderTimeline();
      timelineDirty = false;
      timelineReset.classList.add("hidden");
      timelineReset.disabled = true;
    });
  }

  if (saveBarButton && saveButton) {
    saveBarButton.addEventListener("click", () => {
      if (!saveButton.disabled) {
        saveButton.click();
      }
    });
  }

  if (exportSrtButton && exportStatus) {
    exportSrtButton.addEventListener("click", () => {
      showToast(
        isDirty
          ? "SRT export may not include unsaved changes."
          : "SRT exported from latest edits.",
        isDirty ? "warning" : "success"
      );
    });
  }

  const handleVideoExport = async (button, statusEl, fallbackName, startText) => {
    if (!button || !statusEl) {
      return;
    }
    const form = button.closest("form");
    if (!form) {
      return;
    }
    button.disabled = true;
    showToast(startText, "info", 2600);
    try {
      const response = await fetch(form.action, { method: "POST", body: new FormData(form) });
      if (!response.ok) {
        let detail = "Video export failed.";
        if (response.status === 413) {
          detail = "Export request too large. Please try again.";
        } else if (response.status === 429) {
          detail = "Too many export requests. Please wait and try again.";
        }
        throw new Error(detail);
      }
      const payload = await response.json();
      const jobId = payload.job_id;
      if (!jobId) {
        throw new Error("Missing export job ID");
      }
      pollJob(
        jobId,
        (job) => {
          const url = job.output && job.output.video_url ? job.output.video_url : null;
          const downloadName =
            job.output && job.output.download_name ? job.output.download_name : fallbackName;
          if (!url) {
            showToast("Video exported, but file was not found.", "warning", 3200);
            button.disabled = false;
            return;
          }
          const link = document.createElement("a");
          link.href = url;
          link.download = downloadName;
          document.body.appendChild(link);
          link.click();
          link.remove();
          showToast("Video exported.", "success");
          button.disabled = false;
        },
        (job) => {
          showToast(formatJobFailure(job, "Video export failed."), "error", 3600);
          showErrorPanel(job);
          button.disabled = false;
        }
      );
    } catch (error) {
      console.error(error);
      showToast(
        error.message || "Video export failed.",
        error.message?.includes("Too many") ? "warning" : "error",
        3600
      );
    }
  };

  const bindExportButtons = (buttons, statusEl, fallbackName, startText) => {
    if (!buttons.length || !statusEl) {
      return;
    }
    buttons.forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        handleVideoExport(button, statusEl, fallbackName, startText);
      });
    });
  };

  bindExportButtons(
    exportKaraokeButtons,
    exportVideoStatus,
    "karaoke.mp4",
    "Exporting video..."
  );

  if (jobStatus && jobStatus.dataset.jobId) {
    if (saveButton) {
      saveButton.disabled = true;
      saveButton.textContent = "Processing...";
    }
    setProcessingState(true);
    if (jobStatus.textContent.trim()) {
      showToast(jobStatus.textContent.trim(), "info", 0);
    }
    pollJob(
      jobStatus.dataset.jobId,
      () => {
        window.location.reload();
      },
      (job) => {
        showToast(formatJobFailure(job, "Processing failed."), "error", 3600);
        showErrorPanel(job);
        setProcessingState(false);
        if (saveButton) {
          saveButton.disabled = false;
          saveButton.textContent = saveButton.dataset.originalText || "Save edits";
        }
      }
    );
  } else if (jobStatus && jobStatus.textContent.trim()) {
    showToast(jobStatus.textContent.trim(), "error", 3600);
  }

  if (previewJob && previewJob.dataset.jobId) {
    startPreviewPolling(previewJob.dataset.jobId);
  }

  if (pinForm && pinCheckbox && pinSubmit) {
    const togglePinButton = () => {
      pinSubmit.disabled = false;
      if (pinStatus) {
        pinStatus.style.display = "none";
      }
    };
    pinCheckbox.addEventListener("change", togglePinButton);
    pinSubmit.addEventListener("click", async () => {
      pinSubmit.disabled = true;
      const formData = new FormData(pinForm);
      try {
        const response = await fetch(pinForm.action, { method: "POST", body: formData });
        if (!response.ok) {
          throw new Error("Pin update failed");
        }
        showToast("Pin saved.", "success");
      } catch (error) {
        console.error(error);
        pinSubmit.disabled = false;
        showToast("Pin update failed.", "error", 3200);
      }
    });
  }

  if (editorJob && editorJob.dataset.jobId) {
    const editorJobId = editorJob.dataset.jobId;
    touchEditorJob(editorJobId, true);
    setInterval(() => {
      touchEditorJob(editorJobId, null);
    }, 60000);
    window.addEventListener("beforeunload", () => {
      const formData = new FormData();
      formData.append("locked", "off");
      navigator.sendBeacon(`/jobs/${editorJobId}/touch`, formData);
    });
  }

  const copyErrorButton = document.getElementById("copy-error-id");
  const errorJobInput = document.getElementById("error-job-id");
  if (copyErrorButton && errorJobInput) {
    copyErrorButton.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(errorJobInput.value);
        showToast("Error ID copied.", "success", 1600);
      } catch (error) {
        console.error(error);
        showToast("Copy failed. Select the ID manually.", "warning", 2400);
      }
    });
  }

  const errorPanel = document.getElementById("error-panel");
  const errorPanelMessage = document.getElementById("error-panel-message");
  const errorPanelHint = document.getElementById("error-panel-hint");
  const errorPanelId = document.getElementById("error-panel-id");
  const copyErrorPanelId = document.getElementById("copy-error-panel-id");
  const errorPanelRetry = document.getElementById("error-panel-retry");
  const retryProcessing = document.getElementById("retry-processing");

  const retryJob = async (jobId, button) => {
    if (!jobId) {
      return;
    }
    if (button) {
      button.disabled = true;
    }
    try {
      const response = await fetch(`/jobs/${jobId}/retry`, { method: "POST" });
      if (!response.ok) {
        throw new Error("Retry failed");
      }
      showToast("Retry started.", "info", 2400);
      setProcessingState(true);
      setTimeout(() => {
        window.location.reload();
      }, 600);
    } catch (error) {
      console.error(error);
      showToast("Retry failed. Please try again.", "error", 2600);
      if (button) {
        button.disabled = false;
      }
    }
  };

  const showErrorPanel = (job) => {
    if (!errorPanel || !job) {
      return;
    }
    const message = job.error && job.error.message ? job.error.message : "Something went wrong.";
    const hint = job.error && job.error.hint ? job.error.hint : "";
    if (errorPanelMessage) {
      const step = job.failed_step ? `Failed during ${job.failed_step}. ` : "";
      errorPanelMessage.textContent = step + message;
    }
    if (errorPanelHint) {
      errorPanelHint.textContent = hint;
    }
    if (errorPanelId) {
      errorPanelId.value = job.job_id || "";
    }
    errorPanel.dataset.jobId = job.job_id || "";
    errorPanel.classList.remove("hidden");
  };

  if (copyErrorPanelId && errorPanelId) {
    copyErrorPanelId.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(errorPanelId.value);
        showToast("Error ID copied.", "success", 1600);
      } catch (error) {
        console.error(error);
        showToast("Copy failed. Select the ID manually.", "warning", 2400);
      }
    });
  }

  if (retryProcessing) {
    retryProcessing.addEventListener("click", () => {
      const jobId = retryProcessing.dataset.jobId;
      retryJob(jobId, retryProcessing);
    });
  }

  if (errorPanelRetry) {
    errorPanelRetry.addEventListener("click", () => {
      const jobId = errorPanel?.dataset.jobId;
      retryJob(jobId, errorPanelRetry);
    });
  }
})();
