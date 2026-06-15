/*
 * learning.js — wires up the multisensory learning page.
 *
 * Depends on speech.js (window.SenseWordSpeech).
 */
(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        const card = document.querySelector(".learn-card");
        if (!card) return;

        const word = card.dataset.word;
        const lang = card.dataset.lang || "en-US";

        // --- Play pronunciation of the word ---
        const playWordBtn = document.getElementById("play-pronunciation");
        if (playWordBtn) {
            playWordBtn.addEventListener("click", function () {
                window.SenseWordSpeech.speak(word, lang);
            });
        }

        // --- Play the example sentence ---
        const playExampleBtn = document.getElementById("play-example");
        const exampleEl = document.getElementById("example-sentence");
        if (playExampleBtn && exampleEl) {
            playExampleBtn.addEventListener("click", function () {
                window.SenseWordSpeech.speak(exampleEl.textContent.trim(), lang);
            });
        }

        // --- Read aloud (speech recognition) ---
        const startBtn = document.getElementById("start-speech");
        const statusEl = document.getElementById("speech-status");
        const resultEl = document.getElementById("speech-result");
        const sentenceField = document.getElementById("user_sentence");

        if (startBtn) {
            startBtn.addEventListener("click", function () {
                if (statusEl) statusEl.textContent = "Listening...";
                startBtn.disabled = true;

                window.SenseWordSpeech.listen(
                    function (transcript) {
                        if (resultEl) {
                            resultEl.textContent = 'You said: "' + transcript + '"';
                        }
                        // If the sentence box is empty, prefill it with what was heard.
                        if (sentenceField && !sentenceField.value.trim()) {
                            sentenceField.value = transcript;
                        }
                        // Simple feedback: did they say the target word?
                        if (
                            transcript.toLowerCase().includes(word.toLowerCase()) &&
                            resultEl
                        ) {
                            resultEl.textContent += "  ✅ Nice pronunciation!";
                        }
                    },
                    function () {
                        if (statusEl) statusEl.textContent = "";
                        startBtn.disabled = false;
                    }
                );
            });
        }
    });
})();
