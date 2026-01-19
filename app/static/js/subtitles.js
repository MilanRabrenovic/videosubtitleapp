(() => {
  const form = document.getElementById("subtitle-form");
  const subtitleList = document.getElementById("subtitle-list");
  const hiddenInput = document.getElementById("subtitles-json");
  const status = document.getElementById("edit-status");
  const saveStatus = document.getElementById("save-status");
  const timestampHint = document.getElementById("timestamp-hint");
  const exportStatus = document.getElementById("export-status");
  const exportSrtButton = document.querySelector("[data-export='srt']");
  const exportVideoButton = document.querySelector("[data-export='video']");
  const exportVideoStatus = document.getElementById("video-export-status");
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
      return {
        start: block.querySelector(".start").value.trim(),
        end: block.querySelector(".end").value.trim(),
        text: block.querySelector(".text").value.trim(),
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
      if (saveStatus) {
        saveStatus.style.display = "inline";
        setTimeout(() => {
          saveStatus.style.display = "none";
        }, 1800);
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

  if (exportVideoButton && exportVideoStatus) {
    exportVideoButton.addEventListener("click", async (event) => {
      event.preventDefault();
      const form = exportVideoButton.closest("form");
      if (!form) {
        return;
      }
      exportVideoButton.disabled = true;
      exportVideoStatus.textContent = "Exporting video...";
      exportVideoStatus.style.display = "block";
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
        link.download = filenameMatch ? filenameMatch[1] : "subtitled.mp4";
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        exportVideoStatus.textContent = "Video exported.";
      } catch (error) {
        console.error(error);
        exportVideoStatus.textContent = "Video export failed.";
      } finally {
        exportVideoButton.disabled = false;
      }
    });
  }
})();
