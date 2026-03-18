const conversationEl = document.getElementById("conversation");
const serverStatusEl = document.getElementById("serverStatus");
const micStatusEl = document.getElementById("micStatus");
const micButton = document.getElementById("micButton");
const messageForm = document.getElementById("messageForm");
const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const liveTranscriptEl = document.getElementById("liveTranscript");
const connectionHintEl = document.getElementById("connectionHint");
const mobileHintEl = document.getElementById("mobileHint");
const mobileHintTextEl = document.getElementById("mobileHintText");
const announcerEl = document.getElementById("announcer");
const imageUploadParams = { fileBase64: null, fileName: null };
const imageUpload = document.getElementById("imageUpload");
const attachBtn = document.getElementById("attachBtn");

const history = [];

let ws = null;
let connectionPromise = null;
let audioContext = null;
let sourceNode = null;
let workletNode = null;
let silentMonitorNode = null;
let mediaStream = null;
let audioWorkletLoaded = false;
let captureEnabled = false;
let serverAllowsCapture = false;
let audioReady = false;
let connectionReady = false;
let bootStarted = false;
let isEnablingMic = false;
let playbackNode = null;
let playbackQueue = [];
let finalAudioChunkReceived = false;
let activeAssistantMessage = null;

function setConnectionHint(text) {
    if (connectionHintEl) {
        connectionHintEl.textContent = text;
    }
}

function setMobileHint(text, visible = true) {
    if (!mobileHintEl || !mobileHintTextEl) {
        return;
    }
    mobileHintTextEl.textContent = text;
    mobileHintEl.hidden = !visible;
}

function announce(text) {
    if (!announcerEl) {
        return;
    }
    announcerEl.textContent = "";
    window.requestAnimationFrame(() => {
        announcerEl.textContent = text;
    });
}

function isLoopbackHost() {
    const host = window.location.hostname;
    return host === "localhost" || host === "127.0.0.1" || host === "::1";
}

function getMicCapability() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return {
            ok: false,
            label: "Mic Unsupported",
            reason: "This browser cannot capture microphone audio. Text chat is still available.",
        };
    }

    if (!window.isSecureContext && !isLoopbackHost()) {
        return {
            ok: false,
            label: "Mic Needs HTTPS",
            reason: "Open Ama over HTTPS so the phone browser can grant microphone access.",
        };
    }

    return {
        ok: true,
        label: "Talk",
        reason: "",
    };
}

function shouldAutoEnableMicrophone() {
    return getMicCapability().ok;
}

function setServerStatus(text, extraClass = "") {
    // In new UI, serverStatus text usually isn't displayed directly inside the dot, but we can set aria-label
    // Or we just update the micStatus for both for simplicity, since they are bundled.
    if (!serverStatusEl) return;
    
    // extraClass 'live' in old code meant connected
    if (extraClass.includes('live')) {
        serverStatusEl.className = "w-2 h-2 rounded-full bg-emerald-400 animate-pulse";
    } else if (extraClass.includes('muted')) {
        serverStatusEl.className = "w-2 h-2 rounded-full bg-rose-400";
    } else {
        serverStatusEl.className = "w-2 h-2 rounded-full bg-slate-400";
    }
    serverStatusEl.setAttribute("aria-label", `Server status ${text}`);
}

function setMicStatus(text, extraClass = "") {
    if (!micStatusEl) return;
    micStatusEl.textContent = text;
    // We can conditionally change text color
    if (extraClass.includes('live')) {
        micStatusEl.className = "text-emerald-400";
    } else if (extraClass.includes('muted')) {
        micStatusEl.className = "text-rose-400";
    } else {
        micStatusEl.className = "text-slate-400";
    }
    micStatusEl.setAttribute("aria-label", `Microphone status ${text}`);
}

function appendMessage(role, text) {
    const item = document.createElement("div");
    item.className = `message ${role}`;
    item.setAttribute("aria-label", `${role} message`);

    const textEl = document.createElement("div");
    textEl.className = "message-text";
    textEl.textContent = text;

    item.appendChild(textEl);
    conversationEl.appendChild(item);
    conversationEl.scrollTo({ top: conversationEl.scrollHeight, behavior: "smooth" });
    return { item, textEl };
}

function startAssistantMessage() {
    activeAssistantMessage = appendMessage("assistant", "");
}

function appendAssistantDelta(text) {
    if (!activeAssistantMessage) {
        startAssistantMessage();
    }
    activeAssistantMessage.textEl.textContent += text;
    conversationEl.scrollTop = conversationEl.scrollHeight;
}

function finalizeAssistantMessage(text) {
    if (activeAssistantMessage) {
        activeAssistantMessage.textEl.textContent = text;
        activeAssistantMessage = null;
        return;
    }
    appendMessage("assistant", text);
}

function appendSources(items) {
    if (!items || items.length === 0) {
        return;
    }

    const refs = items
        .map((item) => {
            const endLine = item.end_line && item.end_line !== item.line ? `-${item.end_line}` : "";
            const symbolBits = item.symbol_kind && item.symbol ? ` ${item.symbol_kind} ${item.symbol}` : "";
            return `${item.path}:${item.line}${endLine}${symbolBits}`;
        })
        .join("\n");
    appendMessage("meta", `Sources\n${refs}`);
}

function updateMicButton() {
    if (!micButton) {
        return;
    }

    const capability = getMicCapability();
    let label = "Talk";

    if (isEnablingMic) {
        label = "Starting Talk";
    } else if (!connectionReady) {
        label = bootStarted ? "Reconnect" : "Connect";
    } else if (!capability.ok) {
        label = capability.label;
    } else if (!audioReady) {
        label = "Enable Talk";
    } else if (captureEnabled) {
        label = "Pause Talk";
    } else if (playbackNode || playbackQueue.length > 0) {
        label = "Interrupt";
    } else {
        label = "Resume Talk";
    }

    micButton.textContent = label;
    micButton.classList.toggle("listening", captureEnabled);
    micButton.disabled = isEnablingMic;
    micButton.setAttribute("aria-label", label);
    micButton.setAttribute("aria-pressed", captureEnabled ? "true" : "false");
}

function updateSendButton() {
    if (!sendButton || !messageInput) {
        return;
    }
    sendButton.disabled = messageInput.value.trim().length === 0;
}

function syncActionState() {
    updateMicButton();
    updateSendButton();
}

async function ensureAudioContext() {
    if (!audioContext) {
        audioContext = new window.AudioContext();
    }
    if (audioContext.state === "suspended") {
        await audioContext.resume();
    }
}

function finishPlayback() {
    playbackNode = null;
    playbackQueue = [];
    finalAudioChunkReceived = false;
    syncActionState();

    if (window.aiAvatar) {
        window.aiAvatar.setState("idle");
        window.aiAvatar.stopMonitoring();
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
        try {
            sendJson({ type: "playback_complete" });
        } catch (error) {
            setServerStatus("Unavailable", "muted");
        }
    }
}

function stopSpeaking(notifyServer = true) {
    playbackQueue = [];
    finalAudioChunkReceived = false;

    if (playbackNode) {
        playbackNode.onended = null;
        try {
            playbackNode.stop(0);
        } catch (error) {
            // Ignore invalid state when playback already ended.
        }
        playbackNode.disconnect();
        playbackNode = null;
    }

    if (window.aiAvatar) {
        window.aiAvatar.setState("idle");
        window.aiAvatar.stopMonitoring();
    }

    syncActionState();

    if (notifyServer && ws && ws.readyState === WebSocket.OPEN) {
        try {
            sendJson({ type: "interrupt", aggressive: true });
        } catch (error) {
            setServerStatus("Unavailable", "muted");
        }
    }
}

// Add File Upload Logic
if (attachBtn && imageUpload) {
    attachBtn.addEventListener('click', () => {
        imageUpload.click();
    });

    imageUpload.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (event) => {
            imageUploadParams.fileBase64 = event.target.result;
            imageUploadParams.fileName = file.name;
            messageInput.placeholder = `Attached: ${file.name}`;
            messageInput.focus();
        };
        reader.readAsDataURL(file);
    });
}

async function pumpPlaybackQueue() {
    if (playbackNode || playbackQueue.length === 0) {
        if (!playbackNode && playbackQueue.length === 0 && finalAudioChunkReceived) {
            finishPlayback();
        }
        return;
    }

    await ensureAudioContext();
    const nextChunk = playbackQueue.shift();
    const binaryString = window.atob(nextChunk.audioBase64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i += 1) {
        bytes[i] = binaryString.charCodeAt(i);
    }

    const decodedBuffer = await audioContext.decodeAudioData(bytes.buffer.slice(0));
    const source = audioContext.createBufferSource();
    source.buffer = decodedBuffer;
    source.connect(audioContext.destination);

    if (window.aiAvatar) {
        window.aiAvatar.setState("talking");
        window.aiAvatar.startMonitoring(audioContext, source);
    }

    source.onended = () => {
        source.disconnect();
        playbackNode = null;
        syncActionState();
        if (playbackQueue.length > 0) {
            void pumpPlaybackQueue();
        } else if (finalAudioChunkReceived) {
            finishPlayback();
        }
    };

    playbackNode = source;
    syncActionState();
    source.start(0);
}

async function playAssistantAudioChunk(audioBase64, isLast) {
    if (isLast) {
        finalAudioChunkReceived = true;
    }
    playbackQueue.push({ audioBase64 });
    syncActionState();
    await pumpPlaybackQueue();
}

function markAssistantAudioComplete() {
    finalAudioChunkReceived = true;
    if (!playbackNode && playbackQueue.length === 0) {
        finishPlayback();
    }
}

function pauseCapture() {
    captureEnabled = false;
    updateMicButton();
}

function resumeCapture() {
    if (!audioReady || !serverAllowsCapture) {
        return;
    }
    captureEnabled = true;
    updateMicButton();
}

function getWebSocketUrl() {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    return `${protocol}://${window.location.host}/ws`;
}

function connectWebSocket() {
    return new Promise((resolve, reject) => {
        ws = new WebSocket(getWebSocketUrl());
        ws.binaryType = "arraybuffer";

        ws.onopen = () => {
            connectionReady = true;
            setServerStatus("Connected", "live");
            setConnectionHint("Connected to Ama. You can type immediately, and voice mode will start when microphone access succeeds.");
            syncActionState();
            resolve();
        };

        ws.onmessage = async (event) => {
            const payload = JSON.parse(event.data);

            if (payload.type === "ready") {
                setServerStatus("Ready", "live");
                if (!audioReady) {
                    const capability = getMicCapability();
                    if (!capability.ok) {
                        setMicStatus(capability.label, "muted");
                    } else {
                        setMicStatus("Starting Talk", "live");
                    }
                }
                syncActionState();
                return;
            }

            if (payload.type === "state") {
                const serverState = payload.server || "ready";
                const micState = payload.mic || "idle";
                const capture = Boolean(payload.capture);
                serverAllowsCapture = capture;

                if (serverState === "generating" || serverState === "transcribing" || serverState === "synthesizing") {
                    const labels = {
                        generating: "Generating",
                        transcribing: "Transcribing",
                        synthesizing: "Speaking Soon",
                    };
                    setServerStatus(labels[serverState], "live");
                    if (window.aiAvatar) {
                        window.aiAvatar.setState("thinking");
                    }
                } else if (serverState === "speaking") {
                    setServerStatus("Speaking", "live");
                    if (window.aiAvatar) {
                        window.aiAvatar.setState("talking");
                    }
                } else if (serverState === "error") {
                    setServerStatus("Error", "muted");
                    if (window.aiAvatar) {
                        window.aiAvatar.setState("idle");
                    }
                } else {
                    setServerStatus("Ready", "live");
                    if (window.aiAvatar && playbackQueue.length === 0 && !playbackNode) {
                        window.aiAvatar.setState("idle");
                    }
                }

                if (micState === "listening") {
                    setMicStatus("Listening", "live");
                } else if (micState === "paused") {
                    setMicStatus("Paused", "muted");
                } else {
                    setMicStatus("Idle", "muted");
                }

                if (payload.transcript) {
                    liveTranscriptEl.textContent = payload.transcript;
                } else if (micState === "listening") {
                    liveTranscriptEl.textContent = "Ama is listening for speech.";
                }

                if (capture) {
                    resumeCapture();
                } else {
                    pauseCapture();
                }
                syncActionState();
                return;
            }

            if (payload.type === "user_transcript" || payload.type === "user_message") {
                activeAssistantMessage = null;
                appendMessage("user", payload.text);
                history.push({ role: "user", content: payload.text });
                liveTranscriptEl.textContent = payload.text;
                return;
            }

            if (payload.type === "assistant_reply") {
                finalizeAssistantMessage(payload.text);
                if (!history.length || history[history.length - 1].role !== "assistant" || history[history.length - 1].content !== payload.text) {
                    history.push({ role: "assistant", content: payload.text });
                }
                liveTranscriptEl.textContent = payload.text;
                announce("Ama finished replying.");
                return;
            }

            if (payload.type === "assistant_reply_start") {
                startAssistantMessage();
                return;
            }

            if (payload.type === "assistant_reply_delta") {
                appendAssistantDelta(payload.text);
                liveTranscriptEl.textContent = (activeAssistantMessage && activeAssistantMessage.textEl.textContent) || payload.text;
                return;
            }

            if (payload.type === "assistant_sources") {
                appendSources(payload.items);
                return;
            }

            if (payload.type === "assistant_audio_chunk") {
                try {
                    await playAssistantAudioChunk(payload.audio_b64, Boolean(payload.is_last));
                } catch (error) {
                    liveTranscriptEl.textContent = `Audio playback failed: ${error.message}`;
                    setConnectionHint("Audio playback is blocked on this browser until it allows audio output. Tap Talk once if needed.");
                    announce("Audio playback failed.");
                    stopSpeaking(true);
                }
                return;
            }

            if (payload.type === "assistant_audio_end") {
                markAssistantAudioComplete();
                return;
            }

            if (payload.type === "notice") {
                activeAssistantMessage = null;
                liveTranscriptEl.textContent = payload.message;
                announce(payload.message);
                return;
            }

            if (payload.type === "cleared") {
                liveTranscriptEl.textContent = captureEnabled ? "Ama is listening for speech." : "Session cleared. Ask a new question.";
                announce("Conversation cleared.");
                return;
            }

            if (payload.type === "error") {
                setServerStatus("Error", "muted");
                setConnectionHint("Ama reported an error. Retry the request or reconnect if needed.");
                liveTranscriptEl.textContent = payload.message;
                announce(payload.message);
            }
        };

        ws.onerror = () => {
            setServerStatus("Unavailable", "muted");
            setConnectionHint("Could not reach Ama. Confirm this device can reach the server address and port.");
            syncActionState();
            reject(new Error("WebSocket connection failed"));
        };

        ws.onclose = () => {
            connectionReady = false;
            setServerStatus("Disconnected", "muted");
            setConnectionHint("Connection lost. Reconnect when the local service is reachable again.");
            stopSpeaking(false);
            pauseCapture();
            ws = null;
            syncActionState();
        };
    });
}

async function ensureConnection() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        connectionReady = true;
        return;
    }

    if (!connectionPromise) {
        setServerStatus("Connecting", "live");
        connectionPromise = connectWebSocket().finally(() => {
            connectionPromise = null;
        });
    }

    await connectionPromise;
}

async function setupAudio() {
    mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
        },
    });

    await ensureAudioContext();
    if (!audioWorkletLoaded) {
        await audioContext.audioWorklet.addModule("/static/audio-processor.js");
        audioWorkletLoaded = true;
    }

    sourceNode = audioContext.createMediaStreamSource(mediaStream);
    workletNode = new AudioWorkletNode(audioContext, "local-audio-processor", {
        processorOptions: {
            sourceSampleRate: audioContext.sampleRate,
            targetSampleRate: 16000,
            targetChunkFrames: 1280,
        },
    });
    silentMonitorNode = audioContext.createGain();
    silentMonitorNode.gain.value = 0;

    workletNode.port.onmessage = (event) => {
        if (!captureEnabled || !ws || ws.readyState !== WebSocket.OPEN) {
            return;
        }
        ws.send(event.data);
    };

    sourceNode.connect(workletNode);
    workletNode.connect(silentMonitorNode);
    silentMonitorNode.connect(audioContext.destination);
    audioReady = true;
}

async function enableMicrophone() {
    const capability = getMicCapability();
    if (!capability.ok) {
        setMicStatus(capability.label, "muted");
        setConnectionHint(capability.reason);
        setMobileHint(capability.reason, true);
        liveTranscriptEl.textContent = capability.reason;
        announce(capability.reason);
        syncActionState();
        return false;
    }

    if (audioReady) {
        if (serverAllowsCapture) {
            sendJson({ type: "resume" });
        }
        return true;
    }

    isEnablingMic = true;
    syncActionState();
    setMicStatus("Requesting Mic", "muted");
    liveTranscriptEl.textContent = "Ama is requesting microphone access.";

    try {
        await ensureConnection();
        await setupAudio();
        setMobileHint("Microphone connected. Ama is ready to listen on this device.", false);
        setConnectionHint("Microphone connected. Speak naturally or type into the question box.");
        if (serverAllowsCapture) {
            resumeCapture();
            setMicStatus("Listening", "live");
            liveTranscriptEl.textContent = "Ama is listening for speech.";
        } else {
            setMicStatus("Waiting", "muted");
            liveTranscriptEl.textContent = "Connected. Waiting for Ama to reopen microphone capture.";
        }
        announce("Microphone ready.");
        syncActionState();
        return true;
    } catch (error) {
        const message = error.message || "Microphone setup failed.";
        setMicStatus("Mic Blocked", "muted");
        liveTranscriptEl.textContent = `Microphone setup failed: ${message}. Text chat is still available.`;
        setConnectionHint("Microphone capture is unavailable right now. Text chat is still available.");
        setMobileHint("Tap Talk after granting microphone permission. If this is a phone, open Ama over trusted HTTPS.", true);
        announce("Microphone unavailable. Text chat is still available.");
        syncActionState();
        return false;
    } finally {
        isEnablingMic = false;
        syncActionState();
    }
}

async function boot() {
    bootStarted = true;
    setServerStatus("Connecting", "live");
    setMicStatus("Checking Mic", "muted");
    setConnectionHint("Connecting to Ama.");

    try {
        await ensureConnection();
        const capability = getMicCapability();

        if (shouldAutoEnableMicrophone()) {
            await enableMicrophone();
            return;
        }

        if (!capability.ok) {
            setMicStatus(capability.label, "muted");
            liveTranscriptEl.textContent = capability.reason;
            setMobileHint(capability.reason, true);
            setConnectionHint("Connected. Text chat is ready now, and voice mode can be enabled later in a supported browser context.");
        } else {
            setMicStatus("Talk Ready", "muted");
            liveTranscriptEl.textContent = "Connected. Ama is ready when you tap Talk or type a question.";
            setMobileHint("Text chat is ready. Tap Talk when you want speech input on this device.", true);
            setConnectionHint("Connected. Ama is ready, and the microphone can be enabled when you tap Talk.");
        }
    } catch (error) {
        setServerStatus("Unavailable", "muted");
        setMicStatus("Offline", "muted");
        setConnectionHint("Could not reach Ama. Confirm this device can reach the server address and port.");
        liveTranscriptEl.textContent = `Connection failed: ${error.message}`;
        announce("Connection failed.");
        syncActionState();
    }
}

function sendJson(payload) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        throw new Error("WebSocket is not connected");
    }
    ws.send(JSON.stringify(payload));
}

micButton.addEventListener("click", async () => {
    if (!connectionReady) {
        await boot();
        return;
    }

    if (!audioReady) {
        await enableMicrophone();
        return;
    }

    if (captureEnabled) {
        sendJson({ type: "pause" });
        announce("Microphone paused.");
        return;
    }

    if (playbackNode || playbackQueue.length > 0 || !serverAllowsCapture) {
        stopSpeaking(true);
        announce("Reply interrupted.");
        return;
    }

    sendJson({ type: "resume" });
    announce("Microphone resumed.");
});

messageForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = messageInput.value.trim();
    if (!text) {
        return;
    }

    messageInput.value = "";
    updateSendButton();

    try {
        await ensureConnection();
        stopSpeaking(true);
        let payload = { type: "chat_message", text: text };
    
        if (imageUploadParams.fileBase64) {
            payload.image = imageUploadParams.fileBase64;
            payload.imageName = imageUploadParams.fileName;
            // Optionally append indicator to the text for UX
            if (text) {
                payload.text = `[Image: ${imageUploadParams.fileName}] ${text}`;
            } else {
                payload.text = `[Image: ${imageUploadParams.fileName}]`;
            }
            
            // Reset after send
            imageUploadParams.fileBase64 = null;
            imageUploadParams.fileName = null;
            messageInput.placeholder = "Ask Voice Assistant";
        }

        sendJson(payload);
        
        setConnectionHint("Question sent. Ama is generating a response.");
    } catch (error) {
        appendMessage("assistant", `Request failed: ${error.message}`);
        setServerStatus("Unavailable", "muted");
        setConnectionHint("The request could not be sent because Ama is unavailable.");
        announce("Request failed.");
    }
});

messageInput.addEventListener("input", () => {
    updateSendButton();
});

messageInput.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        messageForm.requestSubmit();
    }
});

window.addEventListener("load", () => {
    syncActionState();
    boot();
});
