/*
 * vocabulary_add.js — auto-fill the pronunciation field on the Add Word page.
 *
 * When the user types an English word, after a short debounce we ask the
 * backend (/api/v1/pronunciation) for the pronunciation and fill the
 * pronunciation input. The user can still edit the field manually; once they
 * do, we stop overwriting it so their edits are never lost.
 */
(function () {
    "use strict";

    var DEBOUNCE_MS = 500;

    document.addEventListener("DOMContentLoaded", function () {
        var wordInput = document.getElementById("word-input");
        var pronunciationInput = document.getElementById("pronunciation-input");
        if (!wordInput || !pronunciationInput) return;

        var debounceTimer = null;
        // Track whether the user has manually edited the pronunciation field.
        var userEdited = false;

        pronunciationInput.addEventListener("input", function () {
            userEdited = pronunciationInput.value.trim() !== "";
        });

        function fetchPronunciation(word) {
            var url = "/api/v1/pronunciation?word=" + encodeURIComponent(word);
            fetch(url)
                .then(function (response) {
                    if (!response.ok) throw new Error("Request failed");
                    return response.json();
                })
                .then(function (data) {
                    // Don't clobber a value the user typed themselves.
                    if (!userEdited && data && data.pronunciation) {
                        pronunciationInput.value = data.pronunciation;
                    }
                })
                .catch(function () {
                    // Silently ignore — pronunciation is optional and editable.
                });
        }

        wordInput.addEventListener("input", function () {
            var word = wordInput.value.trim();

            if (debounceTimer) clearTimeout(debounceTimer);

            if (!word) return;

            debounceTimer = setTimeout(function () {
                fetchPronunciation(word);
            }, DEBOUNCE_MS);
        });
    });
})();
