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
  const timestampPattern = /^\d{2}:\d{2}:\d{2},\d{3}$/;
  let isDirty = false;

  const hasInvalidTimestamps = () => {
    const blocks = subtitleList.querySelectorAll(".subtitle-block");
    return Array.from(blocks).some((block) => {
      const start = block.querySelector(".start").value.trim();
      const end = block.querySelector(".end").value.trim();
      return !timestampPattern.test(start) || !timestampPattern.test(end);
    });
  };

  if (!form || !subtitleList || !hiddenInput) {
    return;
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

  const markDirty = () => {
    if (status) {
      status.textContent = "Unsaved changes";
    }
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
  };

  subtitleList.addEventListener("input", () => {
    hiddenInput.value = JSON.stringify(collectSubtitles());
    markDirty();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hiddenInput.value = JSON.stringify(collectSubtitles());
    if (timestampHint) {
      timestampHint.style.display = hasInvalidTimestamps() ? "block" : "none";
    }
    try {
      const response = await fetch(form.action, { method: "POST", body: new FormData(form) });
      if (!response.ok) {
        throw new Error("Save failed");
      }
      const html = await response.text();
      if (saveStatus) {
        saveStatus.style.display = "inline";
        setTimeout(() => {
          saveStatus.style.display = "none";
        }, 1800);
      }
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, "text/html");
      const updatedList = doc.getElementById("subtitle-list");
      if (updatedList) {
        subtitleList.innerHTML = updatedList.innerHTML;
      }
      if (previewVideo) {
        const source = previewVideo.querySelector("source");
        if (source && source.src.includes("/outputs/")) {
          const cacheBuster = `v=${Date.now()}`;
          source.src = source.src.split("?")[0] + "?" + cacheBuster;
          previewVideo.load();
        }
      }
      isDirty = false;
    } catch (error) {
      console.error(error);
    }
  });

  // Initialize hidden input with current values.
  hiddenInput.value = JSON.stringify(collectSubtitles());
  isDirty = false;

  if (exportSrtButton && exportStatus) {
    exportSrtButton.addEventListener("click", () => {
      exportStatus.textContent = isDirty
        ? "SRT export may not include unsaved changes."
        : "SRT exported from latest edits.";
      exportStatus.style.display = "block";
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
    statusEl.textContent = startText;
    statusEl.style.display = "block";
    try {
      const response = await fetch(form.action, { method: "POST", body: new FormData(form) });
      if (!response.ok) {
        throw new Error("Video export failed");
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      const disposition = response.headers.get("content-disposition") || "";
      const filenameMatch = disposition.match(/filename=\"?([^\";]+)\"?/);
      link.href = url;
      link.download = filenameMatch ? filenameMatch[1] : fallbackName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      statusEl.textContent = "Video exported.";
    } catch (error) {
      console.error(error);
      statusEl.textContent = "Video export failed.";
    } finally {
      button.disabled = false;
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
})();
