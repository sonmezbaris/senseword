/*
 * answers.js — save the learner's sentence + voice recording to the backend.
 *
 * Exposes window.SenseWordAnswers.save(catalogWordId, userSentence, audioBlob)
 * which POSTs to /study/answer and returns a Promise resolving to the JSON
 * response. Keeping upload logic here means study.js stays focused on UI flow.
 */
(function () {
    "use strict";

    function save(catalogWordId, userSentence, audioBlob) {
        var form = new FormData();
        form.append("catalog_word_id", String(catalogWordId));
        form.append("user_sentence", userSentence || "");

        if (audioBlob) {
            form.append("audio", audioBlob, "recording.webm");
        }

        return fetch("/study/answer", {
            method: "POST",
            body: form,
            credentials: "same-origin",
        }).then(function (response) {
            if (!response.ok) throw new Error("Save failed");
            return response.json();
        });
    }

    window.SenseWordAnswers = { save: save };
})();
