/*
 * study.js — progressive multisensory learning flow controller.
 *
 * Steps are revealed one at a time when the user clicks "Show next":
 *   1 word -> 2 meaning -> 3 pronunciation -> 4 image -> 5 example ->
 *   6 user sentence + recording + save
 *
 * Depends on: speech.js, audio.js, recorder.js, answers.js
 */
(function () {
    "use strict";

    // Button labels for each reveal transition (step N -> step N+1).
    var REVEAL_LABELS = {
        1: "Show meaning ▾",
        2: "Show pronunciation ▾",
        3: "Show image ▾",
        4: "Show example ▾",
        5: "Write your sentence ▾",
    };

    var MAX_STEP = 6;
    var currentStep = 1;
    var recordedBlob = null;

    function wireQuickJump() {
        var input = document.getElementById("jump-input");
        var go = document.getElementById("jump-go");
        if (!input || !go) return;

        function jump() {
            var n = parseInt(input.value, 10);
            if (isNaN(n) || n < 1) n = 1;
            var max = parseInt(input.getAttribute("max"), 10) || n;
            if (n > max) n = max;
            // Preserve the current context (level/size or path) via data-qs.
            var qs = input.dataset.qs || "level=all&size=100";
            // Position is 0-based; the word number shown is 1-based.
            window.location.href = "/study/card/" + (n - 1) + "?" + qs;
        }

        go.addEventListener("click", jump);
        input.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
                e.preventDefault();
                jump();
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        wireQuickJump();

        var card = document.getElementById("study-card");
        if (!card) return;

        var revealBtn = document.getElementById("reveal-next");
        var playAudioBtn = document.getElementById("play-audio");
        var playExampleBtn = document.getElementById("play-example");
        var recordBtn = document.getElementById("record-btn");
        var stopBtn = document.getElementById("stop-btn");
        var recordStatus = document.getElementById("record-status");
        var saveBtn = document.getElementById("save-answer");
        var saveStatus = document.getElementById("save-status");
        var sentenceField = document.getElementById("user-sentence");
        var playback = document.getElementById("recording-playback");
        var imageEl = document.getElementById("study-image");

        var wordId = parseInt(card.dataset.wordId, 10);
        var word = card.dataset.word;
        var lang = card.dataset.lang || "en-US";
        var audioUrl = card.dataset.audioUrl;
        var example = card.dataset.example;

        // Hide broken image placeholders gracefully.
        if (imageEl) {
            imageEl.addEventListener("error", function () {
                imageEl.style.display = "none";
            });
        }

        // --- Progressive reveal ------------------------------------------------
        if (revealBtn) {
            revealBtn.addEventListener("click", function () {
                if (currentStep >= MAX_STEP) return;

                currentStep += 1;
                var stepEl = card.querySelector('[data-step="' + currentStep + '"]');
                if (stepEl) stepEl.classList.remove("is-hidden");

                if (currentStep >= MAX_STEP) {
                    revealBtn.classList.add("is-hidden");
                } else {
                    revealBtn.textContent = REVEAL_LABELS[currentStep] || "Continue ▾";
                }
            });
        }

        // --- Step 3: pronunciation audio ---------------------------------------
        if (playAudioBtn) {
            playAudioBtn.addEventListener("click", function () {
                if (window.SenseWordAudio) {
                    window.SenseWordAudio.play(audioUrl, word, lang);
                }
            });
        }

        // --- Step 5: example sentence audio ------------------------------------
        if (playExampleBtn && example) {
            playExampleBtn.addEventListener("click", function () {
                if (window.SenseWordAudio) {
                    window.SenseWordAudio.play(null, example, lang);
                }
            });
        }

        // --- Step 7: voice recording -------------------------------------------
        if (recordBtn && window.SenseWordRecorder) {
            recordBtn.addEventListener("click", function () {
                recordBtn.disabled = true;
                if (stopBtn) stopBtn.disabled = false;
                if (recordStatus) recordStatus.textContent = "Recording…";

                window.SenseWordRecorder.start(function () {
                    /* mic is live */
                });
            });
        }

        if (stopBtn && window.SenseWordRecorder) {
            stopBtn.addEventListener("click", function () {
                stopBtn.disabled = true;
                if (recordBtn) recordBtn.disabled = false;
                if (recordStatus) recordStatus.textContent = "Processing…";

                window.SenseWordRecorder.stop(function (blob) {
                    recordedBlob = blob;
                    if (recordStatus) recordStatus.textContent = "Recorded ✓";

                    // Let the user preview what they just recorded.
                    if (playback) {
                        playback.src = URL.createObjectURL(blob);
                        playback.classList.remove("is-hidden");
                    }
                });
            });
        }

        // --- Step 8: save answer -----------------------------------------------
        if (saveBtn && window.SenseWordAnswers) {
            saveBtn.addEventListener("click", function () {
                saveBtn.disabled = true;
                if (saveStatus) {
                    saveStatus.textContent = "Saving…";
                    saveStatus.className = "save-status";
                }

                var sentence = sentenceField ? sentenceField.value.trim() : "";

                window.SenseWordAnswers
                    .save(wordId, sentence, recordedBlob)
                    .then(function (data) {
                        if (saveStatus) {
                            saveStatus.textContent = "Saved ✓";
                            saveStatus.className = "save-status save-ok";
                        }
                        // If the server returned a permanent URL, use it.
                        if (data.recording_url && playback) {
                            playback.src = data.recording_url;
                            playback.classList.remove("is-hidden");
                        }
                        recordedBlob = null;
                    })
                    .catch(function (err) {
                        if (saveStatus) {
                            var msg = "Save failed — try again";
                            if (err.data && err.data.message) {
                                msg = err.data.message;
                            }
                            saveStatus.textContent = msg;
                            saveStatus.className = "save-status save-error";
                        }
                        if (err.data && err.data.upgrade_url) {
                            setTimeout(function () {
                                if (confirm("Upgrade to Premium for unlimited access?")) {
                                    window.location.href = err.data.upgrade_url;
                                }
                            }, 100);
                        }
                    })
                    .finally(function () {
                        saveBtn.disabled = false;
                    });
            });
        }
    });
})();
