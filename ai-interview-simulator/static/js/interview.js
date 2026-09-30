(() => {
  const app = document.getElementById("interviewApp");
  if (!app) return;

  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const answerInput = document.getElementById("answerInput");
  const submit = document.getElementById("submitAnswer");
  const status = document.getElementById("submitStatus");
  const timer = document.getElementById("timer");
  const modal = document.getElementById("evaluationModal");
  const body = document.getElementById("evaluationBody");
  const continueBtn = document.getElementById("continueBtn");
  const mode = app.dataset.mode;

  let seconds = 0;
  setInterval(() => {
    seconds++;
    const m = String(Math.floor(seconds / 60)).padStart(2, "0");
    const s = String(seconds % 60).padStart(2, "0");
    timer.textContent = `${m}:${s}`;
  }, 1000);

  if (mode === "Video") {
    navigator.mediaDevices?.getUserMedia({video: true, audio: false})
      .then(stream => {
        const video = document.getElementById("videoPreview");
        if (video) video.srcObject = stream;
      })
      .catch(() => {
        const overlay = document.querySelector(".video-overlay");
        if (overlay) overlay.textContent = "Camera permission unavailable";
      });
  }

  submit?.addEventListener("click", async () => {
    const answer = (answerInput?.value || "").trim();
    if (!answer) {
      status.textContent = "Please answer the question first.";
      status.className = "small text-danger";
      return;
    }

    submit.disabled = true;
    status.textContent = "Evaluating your answer...";
    status.className = "small text-secondary";

    try {
      const response = await fetch(`/api/interview/${app.dataset.interviewId}/answer`, {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrf},
        body: JSON.stringify({question_id: Number(app.dataset.questionId), answer})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Evaluation failed.");

      const e = data.evaluation;
      body.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-3">
          <strong class="fs-4">${escapeHtml(String(e.score))}/100</strong>
          <span class="badge-soft">${escapeHtml(e.classification)}</span>
        </div>
        <p>${escapeHtml(e.feedback)}</p>
        <div class="small text-secondary">Technical accuracy: ${e.technical_accuracy}/100 · Completeness: ${e.completeness}/100</div>
      `;
      bootstrap.Modal.getOrCreateInstance(modal).show();

      continueBtn.onclick = () => {
        if (data.done) window.location.href = data.redirect;
        else window.location.href = data.next_url;
      };
    } catch (err) {
      status.textContent = err.message;
      status.className = "small text-danger";
      submit.disabled = false;
    }
  });

  function escapeHtml(value) {
    return value.replace(/[&<>"']/g, (m) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
  }
})();
