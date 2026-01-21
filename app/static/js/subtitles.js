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
  const jobStatus = document.getElementById("job-status");
  const previewJob = document.getElementById("preview-job");
  const fontLicenseConfirm = document.getElementById("font-license-confirm");
  const fontUploadButton = document.getElementById("font-upload-button");
  const fontInput = document.getElementById("font-input");
  const fontValue = document.getElementById("font-value");
  const fontOptions = document.getElementById("font-options");
  const timestampPattern = /^\d{2}:\d{2}:\d{2},\d{3}$/;
  let isDirty = false;
  let saveTimeoutId = null;

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

  const startPreviewPolling = (jobId) => {
    if (!jobId) {
      return;
    }
    if (status) {
      status.textContent = "Rendering preview...";
    }
    pollJob(
      jobId,
      () => {
        if (previewVideo) {
          const source = previewVideo.querySelector("source");
          if (source && source.src.includes("/outputs/")) {
            const cacheBuster = `v=${Date.now()}`;
            source.src = source.src.split("?")[0] + "?" + cacheBuster;
            previewVideo.load();
          }
        }
        if (status) {
          status.textContent = "Preview updated.";
          setTimeout(() => {
            status.textContent = "";
          }, 1800);
        }
      },
      (job) => {
        if (status) {
          status.textContent = job.error ? `Preview failed: ${job.error}` : "Preview failed.";
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
    if (saveButton) {
      saveButton.disabled = true;
      saveButton.dataset.originalText = saveButton.dataset.originalText || saveButton.textContent;
      saveButton.textContent = "Saving...";
    }
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
        if (saveTimeoutId) {
          clearTimeout(saveTimeoutId);
        }
        saveTimeoutId = setTimeout(() => {
          saveStatus.style.display = "none";
        }, 1800);
      }
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, "text/html");
      const updatedList = doc.getElementById("subtitle-list");
      if (updatedList) {
        subtitleList.innerHTML = updatedList.innerHTML;
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
      if (updatedPreviewJob && previewJob) {
        previewJob.dataset.jobId = updatedPreviewJob.dataset.jobId || "";
        if (previewJob.dataset.jobId) {
          startPreviewPolling(previewJob.dataset.jobId);
        }
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
    if (saveButton) {
      saveButton.disabled = false;
      saveButton.textContent = saveButton.dataset.originalText || "Save edits";
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
      const payload = await response.json();
      const jobId = payload.job_id;
      if (!jobId) {
        throw new Error("Missing export job ID");
      }
      pollJob(
        jobId,
        (job) => {
          const url = job.output && job.output.video_url ? job.output.video_url : null;
          if (!url) {
            statusEl.textContent = "Video exported, but file was not found.";
            button.disabled = false;
            return;
          }
          const link = document.createElement("a");
          link.href = url;
          link.download = fallbackName;
          document.body.appendChild(link);
          link.click();
          link.remove();
          statusEl.textContent = "Video exported.";
          button.disabled = false;
        },
        (job) => {
          statusEl.textContent = job.error ? job.error : "Video export failed.";
          button.disabled = false;
        }
      );
    } catch (error) {
      console.error(error);
      statusEl.textContent = "Video export failed.";
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
    pollJob(
      jobStatus.dataset.jobId,
      () => {
        window.location.reload();
      },
      (job) => {
        jobStatus.textContent = job.error ? `Processing failed: ${job.error}` : "Processing failed.";
      }
    );
  }

  if (previewJob && previewJob.dataset.jobId) {
    startPreviewPolling(previewJob.dataset.jobId);
  }
})();
