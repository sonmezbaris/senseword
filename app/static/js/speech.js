/*
 * speech.js — thin wrapper around the browser Web Speech API.
 *
 * Exposes window.SenseWordSpeech with:
 *   - speak(text, lang)        -> text-to-speech (SpeechSynthesis)
 *   - listen(onResult, onEnd)  -> speech-to-text (SpeechRecognition)
 *
 * Keeping this in one place means the backend speech_service can later
 * provide audio URLs / scoring without changing the page scripts much.
 */
(function () {
    "use strict";

    function speak(text, lang) {
        if (!("speechSynthesis" in window)) {
            console.warn("Speech synthesis not supported in this browser.");
            return;
        }
        // Cancel anything currently being spoken to avoid overlap.
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = lang || "en-US";
        utterance.rate = 0.95;
        window.speechSynthesis.speak(utterance);
    }

    function getRecognition(lang) {
        const SpeechRecognition =
            window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            return null;
        }
        const recognition = new SpeechRecognition();
        recognition.lang = lang || "en-US";
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;
        return recognition;
    }

    /**
     * Start listening. Calls onResult(transcript) on success and
     * onEnd() when recognition stops (success or failure).
     * Returns the recognition object (or null if unsupported).
     */
    function listen(onResult, onEnd) {
        const recognition = getRecognition("en-US");
        if (!recognition) {
            alert("Speech recognition is not supported in this browser. Try Chrome.");
            if (onEnd) onEnd();
            return null;
        }

        recognition.onresult = function (event) {
            const transcript = event.results[0][0].transcript;
            if (onResult) onResult(transcript);
        };
        recognition.onerror = function (event) {
            console.warn("Speech recognition error:", event.error);
        };
        recognition.onend = function () {
            if (onEnd) onEnd();
        };

        recognition.start();
        return recognition;
    }

    window.SenseWordSpeech = { speak: speak, listen: listen };
})();
