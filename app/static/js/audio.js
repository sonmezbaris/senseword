/*
 * audio.js — pronunciation playback helper.
 *
 * Plays a pre-recorded audio file when an audio_url is available, and falls
 * back to browser text-to-speech (speech.js) otherwise. Isolating this here
 * means the rest of the app doesn't care whether audio comes from a file or
 * from TTS — later we can add a real TTS API behind the same interface.
 *
 * Exposes: window.SenseWordAudio.play(audioUrl, fallbackText, lang)
 */
(function () {
    "use strict";

    function play(audioUrl, fallbackText, lang) {
        if (audioUrl) {
            var audio = new Audio(audioUrl);
            // If the file is missing/unsupported, fall back to TTS.
            audio.addEventListener("error", function () {
                speakFallback(fallbackText, lang);
            });
            var promise = audio.play();
            if (promise && typeof promise.catch === "function") {
                promise.catch(function () {
                    speakFallback(fallbackText, lang);
                });
            }
            return;
        }
        speakFallback(fallbackText, lang);
    }

    function speakFallback(text, lang) {
        if (text && window.SenseWordSpeech) {
            window.SenseWordSpeech.speak(text, lang);
        }
    }

    window.SenseWordAudio = { play: play };
})();
