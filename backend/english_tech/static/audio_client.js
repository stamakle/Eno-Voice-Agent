class LessonAudioClient {
    constructor(wsUrl, token) {
        this.wsUrl = wsUrl + "?token=" + token;
        this.ws = null;
        this.audioContext = null;
        this.mediaStream = null;
        this.processor = null;
        this.callbacks = {};
        
        // Playback queue and state
        this.ttsChunks = [];
        this.audioQueue = []; // Full ArrayBuffers waiting to be decoded/played
        this.isPlaying = false;
        
        // Recording state
        this.isRecording = false;
        
        // Add AudioContext init handler
        this.initAudioContext = () => {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)({sampleRate: 16000});
            }
            if (this.audioContext.state === 'suspended') {
                this.audioContext.resume();
            }
        };
        document.addEventListener('click', this.initAudioContext, { once: true });
    }
    
    on(event, callback) {
        if (!this.callbacks[event]) this.callbacks[event] = [];
        this.callbacks[event].push(callback);
    }
    
    emit(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(cb => cb(data));
        }
    }
    
    connect() {
        this.initAudioContext();
        this.ws = new WebSocket(this.wsUrl);
        this.ws.onmessage = this.handleMessage.bind(this);
        this.ws.onopen = () => this.emit('connected');
        this.ws.onclose = () => Object.values(this.callbacks).forEach(() => this.emit('disconnected'));
        this.ws.onerror = (e) => this.emit('error', e);
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
    
    sendJson(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    joinLesson(courseId, chapterId, lessonId) {
        this.sendJson({ type: 'join_lesson', course_id: courseId, chapter_id: chapterId, lesson_id: lessonId });
    }
    
    sendText(text) {
        this.sendJson({ type: 'learner_text', text: text });
    }
    
    async startRecording() {
        if (this.isRecording) return;
        this.isRecording = true;
        this.initAudioContext();
        
        try {
            this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
            const source = this.audioContext.createMediaStreamSource(this.mediaStream);
            
            // Using ScriptProcessor for wider browser support with raw PCM
            this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
            
            this.sendJson({ type: 'audio_input_start', sample_rate: this.audioContext.sampleRate });
            
            this.processor.onaudioprocess = (e) => {
                const inputData = e.inputBuffer.getChannelData(0);
                
                // Downsample from AudioContext rate to 16kHz (simplified, native recording is often already ~44/48k)
                // We'll let Faster-Whisper handle resampling if needed, but we should aim to send 16kHz if possible
                // Fast naive approach: send float32 directly? No backend expects Int16 PCM Base64.
                const pcm16 = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                
                // Convert to base64
                const bytes = new Uint8Array(pcm16.buffer);
                let binary = '';
                // Chunk conversions to avoid max call stack size
                const chunkSize = 8192;
                for (let i = 0; i < bytes.byteLength; i += chunkSize) {
                    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
                }
                this.sendJson({ type: 'audio_chunk', data: window.btoa(binary) });
            };
            
            source.connect(this.processor);
            this.processor.connect(this.audioContext.destination);
            this.emit('recording_started');
        } catch (e) {
            this.isRecording = false;
            this.emit('error', 'Microphone permission denied or failed to open');
        }
    }
    
    stopRecording() {
        if (!this.isRecording) return;
        this.isRecording = false;
        
        if (this.processor) {
            this.processor.disconnect();
            this.processor = null;
        }
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(t => t.stop());
            this.mediaStream = null;
        }
        this.sendJson({ type: 'audio_commit' });
        this.emit('recording_stopped');
    }

    handleMessage(event) {
        const msg = JSON.parse(event.data);
        this.emit('message', msg);
        
        switch(msg.type) {
            case 'assistant_audio_start':
                this.ttsChunks = [];
                break;
            case 'assistant_audio_chunk':
                // Base64 decode to bytes
                const binaryStr = window.atob(msg.data);
                const bytes = new Uint8Array(binaryStr.length);
                for(let i = 0; i < binaryStr.length; i++) {
                    bytes[i] = binaryStr.charCodeAt(i);
                }
                this.ttsChunks.push(bytes);
                break;
            case 'assistant_audio_complete':
                // Merge chunks into a single ArrayBuffer (WAV file bytes)
                const totalLength = this.ttsChunks.reduce((acc, val) => acc + val.length, 0);
                const completeBuffer = new Uint8Array(totalLength);
                let offset = 0;
                for (let chunk of this.ttsChunks) {
                    completeBuffer.set(chunk, offset);
                    offset += chunk.length;
                }
                
                this.audioQueue.push(completeBuffer.buffer);
                this.playNextAudioQueue();
                break;
                
            case 'stt_partial':
                this.emit('transcript_partial', msg.text);
                break;
            case 'stt_result':
                this.emit('transcript_final', msg.text);
                break;
            case 'correction':
                this.emit('correction', msg);
                break;
            case 'session_state':
                this.emit('session_state', msg.session);
                break;
            case 'lesson_prompt':
                this.emit('lesson_prompt', msg);
                break;
            case 'lesson_ready_to_complete':
                this.emit('lesson_ready', msg);
                break;
            case 'error':
                this.emit('server_error', msg.message);
                break;
        }
    }

    playNextAudioQueue() {
        if (this.isPlaying || this.audioQueue.length === 0) return;
        this.isPlaying = true;
        
        const arrayBuffer = this.audioQueue.shift();
        
        // Decode WebAudio and play
        this.initAudioContext();
        this.audioContext.decodeAudioData(arrayBuffer, (decodedBuffer) => {
            const source = this.audioContext.createBufferSource();
            source.buffer = decodedBuffer;
            source.connect(this.audioContext.destination);
            
            this.emit('audio_playback_started');
            
            source.onended = () => {
                this.isPlaying = false;
                this.emit('audio_playback_ended');
                this.playNextAudioQueue();
            };
            source.start(0);
        }, (e) => {
            console.error('Error decoding TTS audio:', e);
            this.isPlaying = false;
            this.playNextAudioQueue();
        });
    }
}
window.LessonAudioClient = LessonAudioClient;
