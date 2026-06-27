// Interactive cloze exam: instant feedback (green tick), live score, timer.
(function () {
  "use strict";

  const page = document.querySelector(".exam-page");
  if (!page) return;

  const total = parseInt(page.dataset.total, 10) || 0;
  let correct = 0;
  let wrong = 0;
  let answered = 0;

  const elCorrect = document.getElementById("scoreCorrect");
  const elWrong = document.getElementById("scoreWrong");
  const elLeft = document.getElementById("scoreLeft");
  const finish = document.getElementById("examFinish");
  const result = document.getElementById("examResult");

  function refreshScore() {
    elCorrect.textContent = correct;
    elWrong.textContent = wrong;
    elLeft.textContent = total - answered;
    if (answered === total && total > 0) {
      const pct = Math.round((correct / total) * 100);
      result.textContent =
        "Doğru: " + correct + " / " + total + "  (%" + pct + ")";
      finish.hidden = false;
      finish.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function handleAnswer(btn) {
    const q = btn.closest(".exam-q");
    if (!q || q.dataset.answered === "1") return;
    q.dataset.answered = "1";
    answered += 1;

    const isCorrect = btn.dataset.correct === "1";
    if (isCorrect) {
      correct += 1;
      btn.classList.add("correct");
      btn.querySelector(".opt-mark").textContent = "✓";
    } else {
      wrong += 1;
      btn.classList.add("wrong");
      btn.querySelector(".opt-mark").textContent = "✗";
      // Reveal the correct option with a green tick.
      const right = q.querySelector('.exam-option[data-correct="1"]');
      if (right) {
        right.classList.add("correct");
        right.querySelector(".opt-mark").textContent = "✓";
      }
    }

    // Lock all options for this question.
    q.querySelectorAll(".exam-option").forEach(function (b) {
      b.disabled = true;
    });

    // Reveal the explanation (Turkish meaning + pronunciation).
    const exp = q.querySelector(".exam-explanation");
    if (exp) exp.hidden = false;

    refreshScore();
  }

  page.querySelectorAll(".exam-option").forEach(function (btn) {
    btn.addEventListener("click", function () {
      handleAnswer(btn);
    });
  });

  // Digital countdown timer (simulation; does not lock the exam).
  const timerEl = document.getElementById("examTimer");
  let remaining = (parseInt(page.dataset.minutes, 10) || 0) * 60;
  function tick() {
    if (remaining < 0) {
      timerEl.textContent = "Süre doldu";
      timerEl.classList.add("time-up");
      return;
    }
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    timerEl.textContent =
      String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
    remaining -= 1;
    setTimeout(tick, 1000);
  }
  if (remaining > 0) tick();

  refreshScore();
})();
