/*
 * recorder.js — browser voice recording wrapper (MediaRecorder API).
 *
 * Exposes window.SenseWordRecorder with:
 *   - start(onReady)  -> begin recording; onReady() when the mic is live
 *   - stop(onBlob)    -> stop and return the audio Blob via onBlob(blob)
 *   - isRecording()   -> boolean
 *
 * The study screen uses this for Step 7 (read your sentence aloud). The blob
 * is handed to answers.js for upload.
 */
(function () {
    "use strict";

    var mediaRecorder = null;
    var chunks = [];

    function start(onReady) {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert("Microphone recording is not supported in this browser.");
            return;
        }

        navigator.mediaDevices
            .getUserMedia({ audio: true })
            .then(function (stream) {
                chunks = [];
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.ondataavailable = function (e) {
                    if (e.data && e.data.size > 0) chunks.push(e.data);
                };
                mediaRecorder.start();
                if (onReady) onReady();
            })
            .catch(function () {
                alert("Could not access the microphone. Please allow mic access.");
            });
    }

    function stop(onBlob) {
        if (!mediaRecorder || mediaRecorder.state === "inactive") return;

        mediaRecorder.onstop = function () {
            // Stop all mic tracks so the browser releases the microphone.
            mediaRecorder.stream.getTracks().forEach(function (t) {
                t.stop();
            });
            var blob = new Blob(chunks, { type: mediaRecorder.mimeType || "audio/webm" });
            chunks = [];
            mediaRecorder = null;
            if (onBlob) onBlob(blob);
        };
        mediaRecorder.stop();
    }

    function isRecording() {
        return mediaRecorder !== null && mediaRecorder.state === "recording";
    }

    window.SenseWordRecorder = { start: start, stop: stop, isRecording: isRecording };
})();
