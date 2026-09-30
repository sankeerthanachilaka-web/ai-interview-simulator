(() => {

    // =========================================================
    // GET ELEMENTS
    // =========================================================

    const app =
        document.getElementById("interviewApp");

    if (!app) {
        return;
    }

    if (app.dataset.mode !== "Video") {
        return;
    }


    const videoPreview =
        document.getElementById("videoPreview");

    const videoRecordBtn =
        document.getElementById("videoRecordBtn");

    const videoRecordStatus =
        document.getElementById("videoRecordStatus");

    const videoOverlay =
        document.getElementById("videoOverlay");

    const recordedVideoContainer =
        document.getElementById("recordedVideoContainer");

    const recordedVideoPreview =
        document.getElementById("recordedVideoPreview");

    const answerInput =
        document.getElementById("answerInput");


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

    let videoChunks = [];

    let isRecording = false;

    let recordingStartedAt = 0;


    // =========================================================
    // AUDIO RECORDING
    //
    // This uses Web Audio API exactly like the working
    // voice implementation.
    // =========================================================

    let audioContext = null;

    let audioSource = null;

    let audioProcessor = null;

    let audioChunks = [];


    // =========================================================
    // VIDEO FORMAT
    // =========================================================

    function getSupportedVideoMimeType() {

        const types = [

            "video/webm;codecs=vp9,opus",

            "video/webm;codecs=vp8,opus",

            "video/webm"

        ];

        for (const type of types) {

            if (
                MediaRecorder.isTypeSupported(
                    type
                )
            ) {

                return type;
            }
        }

        return "";
    }


    // =========================================================
    // UI
    // =========================================================

    function setRecordingUI(recording) {

        if (recording) {

            videoRecordBtn.classList.remove(
                "btn-danger"
            );

            videoRecordBtn.classList.add(
                "btn-dark"
            );

            videoRecordBtn.innerHTML =
                '<i class="bi bi-stop-fill"></i> Stop video recording';

            videoRecordStatus.textContent =
                "Recording video and audio...";

        } else {

            videoRecordBtn.classList.add(
                "btn-danger"
            );

            videoRecordBtn.classList.remove(
                "btn-dark"
            );

            videoRecordBtn.innerHTML =
                '<i class="bi bi-camera-video-fill"></i> Start video recording';

        }
    }


    // =========================================================
    // ENCODE WAV
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


        writeString(
            0,
            "RIFF"
        );

        view.setUint32(
            4,
            36 + samples.length * 2,
            true
        );

        writeString(
            8,
            "WAVE"
        );

        writeString(
            12,
            "fmt "
        );

        view.setUint32(
            16,
            16,
            true
        );

        view.setUint16(
            20,
            1,
            true
        );

        view.setUint16(
            22,
            1,
            true
        );

        view.setUint32(
            24,
            sampleRate,
            true
        );

        view.setUint32(
            28,
            sampleRate * 2,
            true
        );

        view.setUint16(
            32,
            2,
            true
        );

        view.setUint16(
            34,
            16,
            true
        );

        writeString(
            36,
            "data"
        );

        view.setUint32(
            40,
            samples.length * 2,
            true
        );


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
            [view],
            {
                type: "audio/wav"
            }
        );
    }


    // =========================================================
    // RESAMPLE
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
    // CREATE AUDIO PROCESSOR
    // =========================================================

    async function setupAudioCapture() {

        const AudioContextClass =
            window.AudioContext ||
            window.webkitAudioContext;


        if (!AudioContextClass) {

            throw new Error(
                "Web Audio API is not supported."
            );
        }


        audioContext =
            new AudioContextClass();


        if (
            audioContext.state ===
            "suspended"
        ) {

            await audioContext.resume();
        }


        audioSource =
            audioContext.createMediaStreamSource(
                stream
            );


        audioProcessor =
            audioContext.createScriptProcessor(
                4096,
                1,
                1
            );


        audioChunks = [];


        audioProcessor.onaudioprocess =
            (event) => {

                if (!isRecording) {
                    return;
                }


                const input =
                    event.inputBuffer
                        .getChannelData(0);


                const copy =
                    new Float32Array(
                        input.length
                    );


                copy.set(input);


                audioChunks.push(
                    copy
                );
            };


        audioSource.connect(
            audioProcessor
        );


        audioProcessor.connect(
            audioContext.destination
        );
    }


    // =========================================================
    // STOP AUDIO CAPTURE
    // =========================================================

    async function stopAudioCapture() {

        if (audioProcessor) {

            audioProcessor.disconnect();

            audioProcessor.onaudioprocess =
                null;

            audioProcessor = null;
        }


        if (audioSource) {

            try {
                audioSource.disconnect();
            } catch (e) {}

            audioSource = null;
        }


        if (!audioChunks.length) {

            if (audioContext) {

                try {
                    await audioContext.close();
                } catch (e) {}

                audioContext = null;
            }

            return null;
        }


        let totalLength = 0;


        for (
            const chunk of audioChunks
        ) {

            totalLength +=
                chunk.length;
        }


        const combined =
            new Float32Array(
                totalLength
            );


        let offset = 0;


        for (
            const chunk of audioChunks
        ) {

            combined.set(
                chunk,
                offset
            );

            offset +=
                chunk.length;
        }


        const sampleRate =
            audioContext
                ? audioContext.sampleRate
                : 48000;


        const samples16k =
            resampleAudio(
                combined,
                sampleRate,
                16000
            );


        const wavBlob =
            encodeWAV(
                samples16k,
                16000
            );


        if (audioContext) {

            try {
                await audioContext.close();
            } catch (e) {}

            audioContext = null;
        }


        return wavBlob;
    }


    // =========================================================
    // TRANSCRIBE AUDIO
    // =========================================================

    async function transcribeAudio(
        wavBlob
    ) {

        videoRecordStatus.textContent =
            "Transcribing your answer...";


        const form =
            new FormData();


        form.append(
            "audio",
            wavBlob,
            "video-answer.wav"
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


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Transcription failed."
            );
        }


        const text =
            (data.text || "").trim();


        if (!text) {

            throw new Error(
                "No speech was detected."
            );
        }


        answerInput.value =
            text;


        return text;
    }


    // =========================================================
    // UPLOAD VIDEO
    // =========================================================

    async function uploadVideo(
        videoBlob
    ) {

        videoRecordStatus.textContent =
            "Uploading video...";


        const form =
            new FormData();


        form.append(
            "video",
            videoBlob,
            "interview-answer.webm"
        );


        form.append(
            "interview_id",
            app.dataset.interviewId
        );


        form.append(
            "question_id",
            app.dataset.questionId
        );


        const response =
            await fetch(
                "/api/interview/upload-video",
                {
                    method: "POST",

                    headers: {
                        "X-CSRFToken": csrf
                    },

                    body: form
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Video upload failed."
            );
        }


        console.log(
            "Video uploaded:",
            data
        );


        return data;
    }


    // =========================================================
    // START VIDEO RECORDING
    // =========================================================

    async function startRecording() {

        if (isRecording) {
            return;
        }


        try {

            // -------------------------------------------------
            // CAMERA + MICROPHONE
            // -------------------------------------------------

            stream =
                await navigator.mediaDevices.getUserMedia(
                    {
                        video: {
                            width: {
                                ideal: 1280
                            },

                            height: {
                                ideal: 720
                            },

                            facingMode:
                                "user"
                        },

                        audio: {
                            echoCancellation: true,

                            noiseSuppression: true,

                            autoGainControl: true,

                            channelCount: 1
                        }
                    }
                );


            // -------------------------------------------------
            // CAMERA PREVIEW
            // -------------------------------------------------

            videoPreview.srcObject =
                stream;


            videoPreview.muted =
                true;


            await videoPreview.play();


            videoOverlay.textContent =
                "Camera ready";


            // -------------------------------------------------
            // VIDEO RECORDER
            // -------------------------------------------------

            const mimeType =
                getSupportedVideoMimeType();


            const options =
                mimeType
                    ? {
                        mimeType
                    }
                    : {};


            videoChunks = [];


            mediaRecorder =
                new MediaRecorder(
                    stream,
                    options
                );


            mediaRecorder.ondataavailable =
                (event) => {

                    if (
                        event.data &&
                        event.data.size > 0
                    ) {

                        videoChunks.push(
                            event.data
                        );
                    }
                };


            mediaRecorder.onerror =
                (event) => {

                    console.error(
                        "MediaRecorder error:",
                        event
                    );
                };


            // -------------------------------------------------
            // AUDIO CAPTURE
            // -------------------------------------------------

            await setupAudioCapture();


            // -------------------------------------------------
            // START
            // -------------------------------------------------

            mediaRecorder.start(
                1000
            );


            recordingStartedAt =
                Date.now();


            isRecording =
                true;


            setRecordingUI(
                true
            );


            videoRecordStatus.textContent =
                "Recording... Speak your answer now.";


            console.log(
                "Video recording started."
            );


        } catch (error) {

            console.error(
                "Video start error:",
                error
            );


            await cleanup();


            if (
                error.name ===
                "NotAllowedError"
            ) {

                videoRecordStatus.textContent =
                    "Camera/microphone permission was denied. Allow access and try again.";

            } else if (
                error.name ===
                "NotFoundError"
            ) {

                videoRecordStatus.textContent =
                    "Camera or microphone was not found.";

            } else {

                videoRecordStatus.textContent =
                    "Could not start video: " +
                    error.message;
            }
        }
    }


    // =========================================================
    // STOP VIDEO RECORDING
    // =========================================================

    async function stopRecording() {

        if (!isRecording) {
            return;
        }


        isRecording =
            false;


        setRecordingUI(
            false
        );


        videoRecordStatus.textContent =
            "Stopping recording...";


        const duration =
            Date.now() -
            recordingStartedAt;


        // -----------------------------------------------------
        // STOP MEDIA RECORDER
        // -----------------------------------------------------

        if (
            mediaRecorder &&
            mediaRecorder.state !== "inactive"
        ) {

            mediaRecorder.stop();
        }


        // -----------------------------------------------------
        // CAPTURE AUDIO
        // -----------------------------------------------------

        let wavBlob = null;


        try {

            wavBlob =
                await stopAudioCapture();

        } catch (error) {

            console.error(
                "Audio capture error:",
                error
            );
        }


        // -----------------------------------------------------
        // WAIT FOR VIDEO DATA
        // -----------------------------------------------------

        await new Promise(
            resolve => {

                setTimeout(
                    resolve,
                    300
                );

            }
        );


        // -----------------------------------------------------
        // VIDEO BLOB
        // -----------------------------------------------------

        const mimeType =
            mediaRecorder?.mimeType ||
            "video/webm";


        const videoBlob =
            new Blob(
                videoChunks,
                {
                    type: mimeType
                }
            );


        console.log(
            "Video size:",
            videoBlob.size
        );


        console.log(
            "Audio WAV size:",
            wavBlob
                ? wavBlob.size
                : 0
        );


        // -----------------------------------------------------
        // STOP CAMERA
        // -----------------------------------------------------

        if (stream) {

            stream
                .getTracks()
                .forEach(
                    track => track.stop()
                );

            stream = null;
        }


        // -----------------------------------------------------
        // SHOW RECORDED VIDEO
        // -----------------------------------------------------

        if (
            videoBlob.size > 0
        ) {

            const videoURL =
                URL.createObjectURL(
                    videoBlob
                );


            recordedVideoPreview.src =
                videoURL;


            recordedVideoContainer.style.display =
                "block";
        }


        // -----------------------------------------------------
        // TOO SHORT
        // -----------------------------------------------------

        if (duration < 1500) {

            videoRecordStatus.textContent =
                "Recording is too short. Please record for at least 2 seconds.";

            return;
        }


        // -----------------------------------------------------
        // TRANSCRIBE
        // -----------------------------------------------------

        if (wavBlob) {

            try {

                await transcribeAudio(
                    wavBlob
                );

            } catch (error) {

                console.error(
                    "Transcription error:",
                    error
                );

                videoRecordStatus.textContent =
                    error.message ||
                    "Transcription failed.";
            }

        } else {

            videoRecordStatus.textContent =
                "Audio could not be captured.";
        }


        // -----------------------------------------------------
        // UPLOAD VIDEO
        // -----------------------------------------------------

        if (
            videoBlob.size > 0
        ) {

            try {

                await uploadVideo(
                    videoBlob
                );

                videoRecordStatus.textContent =
                    "Video recorded and answer transcribed successfully.";

            } catch (error) {

                console.error(
                    "Video upload error:",
                    error
                );

                videoRecordStatus.textContent =
                    "Answer transcribed, but video upload failed.";
            }

        }


        mediaRecorder =
            null;

        videoChunks = [];
    }


    // =========================================================
    // CLEANUP
    // =========================================================

    async function cleanup() {

        isRecording =
            false;


        if (
            mediaRecorder &&
            mediaRecorder.state !== "inactive"
        ) {

            try {
                mediaRecorder.stop();
            } catch (e) {}
        }


        if (audioProcessor) {

            try {
                audioProcessor.disconnect();
            } catch (e) {}

            audioProcessor = null;
        }


        if (audioSource) {

            try {
                audioSource.disconnect();
            } catch (e) {}

            audioSource = null;
        }


        if (audioContext) {

            try {
                await audioContext.close();
            } catch (e) {}

            audioContext = null;
        }


        if (stream) {

            stream
                .getTracks()
                .forEach(
                    track => track.stop()
                );

            stream = null;
        }


        mediaRecorder =
            null;

        videoChunks = [];

        audioChunks = [];

        setRecordingUI(
            false
        );
    }


    // =========================================================
    // BUTTON
    // =========================================================

    videoRecordBtn.addEventListener(
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
    // INITIAL CAMERA PREVIEW
    // =========================================================

    async function initializeCamera() {

        try {

            stream =
                await navigator.mediaDevices.getUserMedia(
                    {
                        video: {
                            width: {
                                ideal: 1280
                            },

                            height: {
                                ideal: 720
                            },

                            facingMode:
                                "user"
                        },

                        audio: {
                            echoCancellation: true,

                            noiseSuppression: true,

                            autoGainControl: true,

                            channelCount: 1
                        }
                    }
                );


            videoPreview.srcObject =
                stream;


            videoPreview.muted =
                true;


            await videoPreview.play();


            videoOverlay.textContent =
                "Camera ready. Click Start video recording when you are ready.";


            // We don't record yet.
            // Stop tracks until the user starts.
            stream
                .getTracks()
                .forEach(
                    track => track.stop()
                );


            stream = null;


        } catch (error) {

            console.error(
                "Camera initialization error:",
                error
            );


            videoOverlay.textContent =
                "Camera permission unavailable. Click Start video recording to try again.";
        }
    }


    // =========================================================
    // INITIALIZE
    // =========================================================

    initializeCamera();

})();