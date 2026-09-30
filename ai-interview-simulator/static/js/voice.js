(() => {
    "use strict";

    // =========================================================
    // ELEMENTS
    // =========================================================

    const recordBtn = document.getElementById("recordBtn");

    if (!recordBtn) {
        return;
    }

    const answerInput =
        document.getElementById("answerInput");

    const status =
        document.getElementById("recordStatus");

    const csrfElement =
        document.querySelector(
            'meta[name="csrf-token"]'
        );

    const csrf =
        csrfElement
            ? csrfElement.content
            : "";


    // =========================================================
    // STATE
    // =========================================================

    let stream = null;
    let mediaRecorder = null;
    let audioContext = null;

    let audioChunks = [];

    let isRecording = false;

    let recordingStartedAt = 0;


    // =========================================================
    // STATUS
    // =========================================================

    function setStatus(message, type = "normal") {

        if (!status) {
            return;
        }

        status.textContent = message;

        if (type === "error") {

            status.className =
                "small text-danger";

        } else if (type === "success") {

            status.className =
                "small text-success";

        } else {

            status.className =
                "small text-secondary";
        }
    }


    // =========================================================
    // RECORD BUTTON UI
    // =========================================================

    function setRecordingUI(recording) {

        if (recording) {

            recordBtn.classList.remove(
                "btn-danger"
            );

            recordBtn.classList.add(
                "btn-dark"
            );

            recordBtn.innerHTML =
                '<i class="bi bi-stop-fill"></i> Stop recording';

        } else {

            recordBtn.classList.add(
                "btn-danger"
            );

            recordBtn.classList.remove(
                "btn-dark"
            );

            recordBtn.innerHTML =
                '<i class="bi bi-mic-fill"></i> Start recording';
        }
    }


    // =========================================================
    // MICROPHONE DEVICES
    // =========================================================

    async function showMicrophones() {

        try {

            const devices =
                await navigator.mediaDevices.enumerateDevices();

            const microphones =
                devices.filter(
                    device =>
                        device.kind === "audioinput"
                );

            console.log(
                "AVAILABLE MICROPHONES:",
                microphones
            );

            if (!microphones.length) {

                console.warn(
                    "No microphone devices were found."
                );
            }

        } catch (error) {

            console.warn(
                "Could not enumerate microphones:",
                error
            );
        }
    }


    // =========================================================
    // CHOOSE MEDIA RECORDER MIME TYPE
    // =========================================================

    function getSupportedMimeType() {

        const types = [

            "audio/webm;codecs=opus",

            "audio/webm",

            "audio/ogg;codecs=opus",

            "audio/ogg"

        ];

        for (const type of types) {

            if (
                MediaRecorder.isTypeSupported(type)
            ) {

                console.log(
                    "Selected MediaRecorder MIME type:",
                    type
                );

                return type;
            }
        }

        console.warn(
            "No preferred MIME type found. Using browser default."
        );

        return "";
    }


    // =========================================================
    // FLOAT32 → WAV
    // =========================================================

    function encodeWAV(
        samples,
        sampleRate
    ) {

        const buffer =
            new ArrayBuffer(
                44 +
                samples.length * 2
            );

        const view =
            new DataView(buffer);


        function writeString(
            offset,
            text
        ) {

            for (
                let i = 0;
                i < text.length;
                i++
            ) {

                view.setUint8(
                    offset + i,
                    text.charCodeAt(i)
                );
            }
        }


        // RIFF
        writeString(
            0,
            "RIFF"
        );

        view.setUint32(
            4,
            36 + samples.length * 2,
            true
        );


        // WAVE
        writeString(
            8,
            "WAVE"
        );


        // fmt
        writeString(
            12,
            "fmt "
        );

        view.setUint32(
            16,
            16,
            true
        );


        // PCM format
        view.setUint16(
            20,
            1,
            true
        );


        // Mono
        view.setUint16(
            22,
            1,
            true
        );


        // Sample rate
        view.setUint32(
            24,
            sampleRate,
            true
        );


        // Byte rate
        view.setUint32(
            28,
            sampleRate * 2,
            true
        );


        // Block align
        view.setUint16(
            32,
            2,
            true
        );


        // Bits per sample
        view.setUint16(
            34,
            16,
            true
        );


        // data
        writeString(
            36,
            "data"
        );

        view.setUint32(
            40,
            samples.length * 2,
            true
        );


        // PCM samples
        let offset = 44;


        for (
            let i = 0;
            i < samples.length;
            i++
        ) {

            let sample =
                Math.max(
                    -1,
                    Math.min(
                        1,
                        samples[i]
                    )
                );


            let value;

            if (sample < 0) {

                value =
                    sample * 0x8000;

            } else {

                value =
                    sample * 0x7FFF;
            }


            view.setInt16(
                offset,
                value,
                true
            );

            offset += 2;
        }


        return new Blob(
            [buffer],
            {
                type: "audio/wav"
            }
        );
    }


    // =========================================================
    // CALCULATE AUDIO LEVEL
    // =========================================================

    function calculateAudioLevel(
        samples
    ) {

        if (
            !samples ||
            !samples.length
        ) {

            return {
                rms: 0,
                peak: 0
            };
        }


        let sumSquares = 0;
        let peak = 0;


        for (
            let i = 0;
            i < samples.length;
            i++
        ) {

            const value =
                Math.abs(
                    samples[i]
                );


            sumSquares +=
                value * value;


            if (
                value > peak
            ) {

                peak = value;
            }
        }


        const rms =
            Math.sqrt(
                sumSquares /
                samples.length
            );


        return {
            rms,
            peak
        };
    }


    // =========================================================
    // RESAMPLE AUDIO
    // =========================================================

    function resampleAudio(
        samples,
        inputSampleRate,
        outputSampleRate
    ) {

        if (
            inputSampleRate ===
            outputSampleRate
        ) {

            return samples;
        }


        const ratio =
            inputSampleRate /
            outputSampleRate;


        const newLength =
            Math.round(
                samples.length /
                ratio
            );


        const result =
            new Float32Array(
                newLength
            );


        for (
            let i = 0;
            i < newLength;
            i++
        ) {

            const position =
                i * ratio;


            const left =
                Math.floor(
                    position
                );


            const right =
                Math.min(
                    left + 1,
                    samples.length - 1
                );


            const weight =
                position - left;


            result[i] =
                samples[left] *
                (1 - weight) +
                samples[right] *
                weight;
        }


        return result;
    }


    // =========================================================
    // DOWNMIX TO MONO
    // =========================================================

    function convertToMono(
        audioBuffer
    ) {

        const channelCount =
            audioBuffer.numberOfChannels;


        const length =
            audioBuffer.length;


        if (
            channelCount === 1
        ) {

            return new Float32Array(
                audioBuffer.getChannelData(0)
            );
        }


        const mono =
            new Float32Array(
                length
            );


        for (
            let channel = 0;
            channel < channelCount;
            channel++
        ) {

            const channelData =
                audioBuffer.getChannelData(
                    channel
                );


            for (
                let i = 0;
                i < length;
                i++
            ) {

                mono[i] +=
                    channelData[i] /
                    channelCount;
            }
        }


        return mono;
    }


    // =========================================================
    // DECODE RECORDED WEBM/OPUS
    // =========================================================

    async function decodeRecordedAudio(
        blob
    ) {

        console.log(
            "Decoding recorded audio..."
        );


        const arrayBuffer =
            await blob.arrayBuffer();


        if (!audioContext) {

            const AudioContextClass =
                window.AudioContext ||
                window.webkitAudioContext;


            if (!AudioContextClass) {

                throw new Error(
                    "Web Audio API is not supported by this browser."
                );
            }


            audioContext =
                new AudioContextClass();
        }


        if (
            audioContext.state ===
            "suspended"
        ) {

            await audioContext.resume();
        }


        const decodedBuffer =
            await audioContext.decodeAudioData(
                arrayBuffer.slice(0)
            );


        console.log(
            "Decoded audio:",
            {
                duration:
                    decodedBuffer.duration,

                sampleRate:
                    decodedBuffer.sampleRate,

                channels:
                    decodedBuffer.numberOfChannels,

                samples:
                    decodedBuffer.length
            }
        );


        return decodedBuffer;
    }


    // =========================================================
    // RECORDING → WAV
    // =========================================================

    async function convertRecordingToWav(
        recordingBlob
    ) {

        const decoded =
            await decodeRecordedAudio(
                recordingBlob
            );


        if (
            decoded.duration < 0.2
        ) {

            throw new Error(
                "The recording is too short."
            );
        }


        // ---------------------------------------------
        // CONVERT TO MONO
        // ---------------------------------------------

        const mono =
            convertToMono(
                decoded
            );


        console.log(
            "Decoded mono samples:",
            mono.length
        );


        // ---------------------------------------------
        // CHECK AUDIO LEVEL
        // ---------------------------------------------

        const level =
            calculateAudioLevel(
                mono
            );


        console.log(
            "Decoded audio RMS:",
            level.rms
        );


        console.log(
            "Decoded audio peak:",
            level.peak
        );


        // IMPORTANT:
        // Real microphone audio should not be
        // approximately zero here.

        if (
            level.rms < 0.0001 &&
            level.peak < 0.001
        ) {

            throw new Error(
                "The browser recorded silence. Please check the selected microphone and Windows microphone permissions."
            );
        }


        // ---------------------------------------------
        // RESAMPLE TO 16 KHZ
        // ---------------------------------------------

        const samples16k =
            resampleAudio(
                mono,
                decoded.sampleRate,
                16000
            );


        console.log(
            "16 kHz samples:",
            samples16k.length
        );


        // ---------------------------------------------
        // FINAL LEVEL CHECK
        // ---------------------------------------------

        const finalLevel =
            calculateAudioLevel(
                samples16k
            );


        console.log(
            "16 kHz RMS:",
            finalLevel.rms
        );


        console.log(
            "16 kHz peak:",
            finalLevel.peak
        );


        // ---------------------------------------------
        // CREATE WAV
        // ---------------------------------------------

        const wavBlob =
            encodeWAV(
                samples16k,
                16000
            );


        console.log(
            "Final WAV size:",
            wavBlob.size,
            "bytes"
        );


        console.log(
            "Final WAV type:",
            wavBlob.type
        );


        return wavBlob;
    }


    // =========================================================
    // SEND WAV TO FLASK
    // =========================================================

    async function transcribeAudio(
        wavBlob
    ) {

        setStatus(
            "Transcribing your answer..."
        );


        console.log(
            "Sending WAV to Flask..."
        );


        console.log(
            "WAV size:",
            wavBlob.size,
            "bytes"
        );


        console.log(
            "WAV type:",
            wavBlob.type
        );


        const form =
            new FormData();


        form.append(
            "audio",
            wavBlob,
            "answer.wav"
        );


        const response =
            await fetch(
                "/api/transcribe",
                {
                    method: "POST",

                    headers: {
                        "X-CSRFToken": csrf
                    },

                    body: form
                }
            );


        console.log(
            "Transcription HTTP status:",
            response.status
        );


        let data;


        try {

            data =
                await response.json();

        } catch (error) {

            throw new Error(
                "The server returned an invalid response."
            );
        }


        console.log(
            "Transcription response:",
            data
        );


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Transcription failed."
            );
        }


        const text =
            String(
                data.text || ""
            ).trim();


        if (!text) {

            throw new Error(
                "No speech was detected. Please speak clearly and try again."
            );
        }


        // ---------------------------------------------
        // PUT TRANSCRIPTION INTO ANSWER BOX
        // ---------------------------------------------

        if (answerInput) {

            answerInput.value =
                text;

            // Trigger input/change events
            // in case another script listens
            // for changes.

            answerInput.dispatchEvent(
                new Event(
                    "input",
                    {
                        bubbles: true
                    }
                )
            );

            answerInput.dispatchEvent(
                new Event(
                    "change",
                    {
                        bubbles: true
                    }
                )
            );
        }


        setStatus(
            "Transcription ready. You can edit it before submitting.",
            "success"
        );


        return text;
    }


    // =========================================================
    // CLEAN UP
    // =========================================================

    async function cleanupAudio() {

        if (mediaRecorder) {

            mediaRecorder.ondataavailable = null;
            mediaRecorder.onstop = null;
            mediaRecorder.onerror = null;
        }


        mediaRecorder = null;


        if (stream) {

            stream
                .getTracks()
                .forEach(
                    track => {

                        try {
                            track.stop();
                        } catch (e) {}
                    }
                );

            stream = null;
        }


        if (audioContext) {

            try {

                await audioContext.close();

            } catch (e) {

                console.warn(
                    "AudioContext close error:",
                    e
                );
            }

            audioContext = null;
        }
    }


    // =========================================================
    // STOP RECORDING
    // =========================================================

    async function stopRecording() {

        if (
            !isRecording ||
            !mediaRecorder
        ) {

            return;
        }


        isRecording = false;


        console.log(
            "Stopping recording..."
        );


        setRecordingUI(false);


        const duration =
            Date.now() -
            recordingStartedAt;


        console.log(
            "Recording duration:",
            duration,
            "ms"
        );


        if (
            duration < 1500
        ) {

            setStatus(
                "Recording is too short. Please speak for at least 2 seconds.",
                "error"
            );


            try {

                if (
                    mediaRecorder.state !==
                    "inactive"
                ) {

                    mediaRecorder.stop();
                }

            } catch (e) {}


            return;
        }


        setStatus(
            "Processing your recording..."
        );


        // ---------------------------------------------
        // WAIT FOR MEDIARECORDER TO FINISH
        // ---------------------------------------------

        const recorder =
            mediaRecorder;


        return new Promise(
            (resolve) => {

                recorder.onstop =
                    async () => {

                        console.log(
                            "MediaRecorder stopped."
                        );


                        try {

                            if (
                                !audioChunks.length
                            ) {

                                throw new Error(
                                    "No audio data was recorded."
                                );
                            }


                            // ---------------------------------
                            // COMBINE RECORDED CHUNKS
                            // ---------------------------------

                            const recordingBlob =
                                new Blob(
                                    audioChunks,
                                    {
                                        type:
                                            recorder.mimeType ||
                                            "audio/webm"
                                    }
                                );


                            console.log(
                                "Original recording:",
                                recordingBlob.size,
                                "bytes",
                                recordingBlob.type
                            );


                            if (
                                recordingBlob.size <
                                1000
                            ) {

                                throw new Error(
                                    "The recording contains too little audio data."
                                );
                            }


                            // ---------------------------------
                            // CONVERT TO WAV
                            // ---------------------------------

                            const wavBlob =
                                await convertRecordingToWav(
                                    recordingBlob
                                );


                            // ---------------------------------
                            // SEND TO FLASK
                            // ---------------------------------

                            await transcribeAudio(
                                wavBlob
                            );


                        } catch (error) {

                            console.error(
                                "Transcription error:",
                                error
                            );


                            setStatus(
                                error.message ||
                                "Could not process the recording.",
                                "error"
                            );

                        } finally {

                            audioChunks = [];


                            await cleanupAudio();


                            resolve();
                        }
                    };


                try {

                    recorder.stop();

                } catch (error) {

                    console.error(
                        "Could not stop recorder:",
                        error
                    );


                    audioChunks = [];


                    cleanupAudio()
                        .finally(resolve);
                }
            }
        );
    }


    // =========================================================
    // START RECORDING
    // =========================================================

    async function startRecording() {

        if (isRecording) {
            return;
        }


        // ---------------------------------------------
        // BROWSER SUPPORT
        // ---------------------------------------------

        if (
            !navigator.mediaDevices ||
            !navigator.mediaDevices.getUserMedia
        ) {

            setStatus(
                "Your browser does not support microphone access.",
                "error"
            );

            return;
        }


        if (
            typeof MediaRecorder ===
            "undefined"
        ) {

            setStatus(
                "Your browser does not support audio recording.",
                "error"
            );

            return;
        }


        try {

            // ---------------------------------------------
            // CLEAR PREVIOUS STATE
            // ---------------------------------------------

            audioChunks = [];


            // ---------------------------------------------
            // SHOW MICROPHONES
            // ---------------------------------------------

            await showMicrophones();


            // ---------------------------------------------
            // GET MICROPHONE
            // ---------------------------------------------

            stream =
                await navigator.mediaDevices.getUserMedia(
                    {
                        audio: {
                            echoCancellation: false,
                            noiseSuppression: false,
                            autoGainControl: false,
                            channelCount: 1
                        }
                    }
                );


            const tracks =
                stream.getAudioTracks();


            if (
                !tracks.length
            ) {

                throw new Error(
                    "No microphone audio track was created."
                );
            }


            const track =
                tracks[0];


            console.log(
                "Microphone:",
                track.label
            );


            console.log(
                "Microphone settings:",
                track.getSettings()
            );


            // ---------------------------------------------
            // MICROPHONE CAPABILITIES
            // ---------------------------------------------

            try {

                console.log(
                    "Microphone capabilities:",
                    track.getCapabilities()
                );

            } catch (e) {}


            // ---------------------------------------------
            // MEDIA RECORDER MIME
            // ---------------------------------------------

            const mimeType =
                getSupportedMimeType();


            // ---------------------------------------------
            // CREATE MEDIA RECORDER
            // ---------------------------------------------

            if (mimeType) {

                mediaRecorder =
                    new MediaRecorder(
                        stream,
                        {
                            mimeType
                        }
                    );

            } else {

                mediaRecorder =
                    new MediaRecorder(
                        stream
                    );
            }


            console.log(
                "Actual recorder MIME type:",
                mediaRecorder.mimeType
            );


            // ---------------------------------------------
            // AUDIO DATA
            // ---------------------------------------------

            mediaRecorder.ondataavailable =
                (event) => {

                    if (
                        event.data &&
                        event.data.size > 0
                    ) {

                        audioChunks.push(
                            event.data
                        );


                        console.log(
                            "Audio chunk:",
                            event.data.size,
                            "bytes"
                        );
                    }
                };


            // ---------------------------------------------
            // RECORDER ERROR
            // ---------------------------------------------

            mediaRecorder.onerror =
                (event) => {

                    console.error(
                        "MediaRecorder error:",
                        event
                    );


                    setStatus(
                        "Recording error. Please try again.",
                        "error"
                    );
                };


            // ---------------------------------------------
            // START
            // ---------------------------------------------

            recordingStartedAt =
                Date.now();


            isRecording = true;


            setRecordingUI(true);


            setStatus(
                "Recording... Speak your answer now."
            );


            console.log(
                "Recording started"
            );


            // Request data every 500ms
            // so the browser continuously
            // produces recording chunks.

            mediaRecorder.start(
                500
            );


        } catch (error) {

            console.error(
                "Microphone error:",
                error
            );


            isRecording = false;


            await cleanupAudio();


            setRecordingUI(false);


            if (
                error.name ===
                "NotAllowedError"
            ) {

                setStatus(
                    "Microphone permission was denied. Allow microphone access and try again.",
                    "error"
                );

            } else if (
                error.name ===
                "NotFoundError"
            ) {

                setStatus(
                    "No microphone was found. Check your Windows microphone settings.",
                    "error"
                );

            } else if (
                error.name ===
                "NotReadableError"
            ) {

                setStatus(
                    "The microphone is already being used by another application.",
                    "error"
                );

            } else {

                setStatus(
                    "Could not start microphone: " +
                    error.message,
                    "error"
                );
            }
        }
    }


    // =========================================================
    // RECORD BUTTON
    // =========================================================

    recordBtn.addEventListener(
        "click",
        async () => {

            if (isRecording) {

                await stopRecording();

            } else {

                await startRecording();
            }
        }
    );


    // =========================================================
    // INITIAL STATE
    // =========================================================

    setRecordingUI(false);


    console.log(
        "Voice interview recorder loaded."
    );

})();
