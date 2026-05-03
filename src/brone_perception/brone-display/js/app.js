/**
 * Main Application - Integrates MQTT client with Face Renderer
 * Handles expression state management, face tracking (MediaPipe), and
 * robot head pan control via MQTT for hardware integration.
 *
 * === Operating Modes ===
 * - DEFAULT (Shift+D) : Idle face + MediaPipe gaze tracking + head pan + manual expressions
 * - MIRROR  (M)       : Robot mirrors user emotion detected by FER-BRONE (Python ML)
 * - CONVERSATION (C)  : TTS speech animation + FER emotion between utterances
 *
 * === Head Pan Control Logic ===
 * When pupil offset exceeds PUPIL_EDGE_THRESHOLD AND stays there for
 * EDGE_HOLD_REQUIRED ms (hysteresis), a head pan command is sent to the
 * robot controller via MQTT topic `robot/head_control`.
 *
 * === Anti-Shake Design ===
 * - Hysteresis hold  : gaze must stay beyond threshold for ≥ EDGE_HOLD_REQUIRED ms
 * - Rate limiting    : at least HEAD_COMMAND_INTERVAL ms between commands
 *
 * === MQTT Topics ===
 * Subscribe : robot/expression      → incoming expression commands (TTS, manual)
 * Subscribe : robot/fer_emotion     → FER emotion data (Mirror/Conversation modes)
 * Subscribe : robot/fer_gaze        → FER gaze estimation (Mirror/Conversation modes)
 * Publish   : robot/head_control    → outgoing head servo commands
 * Publish   : robot/tracking_state  → full tracking telemetry (debug)
 * Publish   : robot/mode            → broadcast current mode to Python subsystems
 */

class ExpressionApp {
    constructor() {
        // Initialize face renderer
        this.canvas = document.getElementById('faceCanvas');
        this.faceRenderer = new FaceRenderer(this.canvas);

        // Speaking timer
        this.speakingTimer = null;
        this.speakingEndTime = null;

        // Face tracker for pupil movement
        this.faceTracker = null;
        this.trackingEnabled = true;

        // === Mode System ===
        // 'default' = MediaPipe gaze + manual expressions
        // 'mirror'  = FER emotion mirroring
        // 'conversation' = TTS speech + FER emotion between utterances
        this.currentMode = 'default';
        this.FER_EMOTION_TOPIC = 'robot/fer_emotion';
        this.FER_GAZE_TOPIC = 'robot/fer_gaze';
        this.MODE_TOPIC = 'robot/mode';
        this.FER_CONFIDENCE_THRESHOLD = 0.50;

        // === Head Pan Control ===
        this.headAngle = 0;                 // current virtual pan (degrees)
        this.HEAD_MAX_ANGLE = 45;
        this.HEAD_MIN_ANGLE = -45;
        this.HEAD_PAN_STEP = 15;          // degrees per trigger event

        // Pupil X threshold (0–1) before considering "at edge"
        this.PUPIL_EDGE_THRESHOLD = 0.65;

        // ── Anti-shake: hysteresis hold ──
        this.EDGE_HOLD_REQUIRED = 400;    // ms
        this.edgeHoldStart = null;

        // Rate limiting
        this.lastHeadCommandTime = 0;
        this.HEAD_COMMAND_INTERVAL = 600;   // ms

        // MQTT topics
        this.HEAD_CONTROL_TOPIC = 'robot/head_control';
        this.TRACKING_STATE_TOPIC = 'robot/tracking_state';
        this.MODE_TOPIC = 'robot/mode';       // remote control from CLI/SSH

        // Telemetry publish rate
        this.lastTelemetryTime = 0;
        this.TELEMETRY_INTERVAL = 150;      // ms (~6.7 Hz)

        // Get MQTT configuration from URL params or use defaults
        const urlParams = new URLSearchParams(window.location.search);
        this.mqttClient = new MQTTClient({
            host: urlParams.get('mqtt_host') || 'localhost',
            port: parseInt(urlParams.get('mqtt_port')) || 9001,
            topic: urlParams.get('mqtt_topic') || 'robot/expression'
        });

        this.setupEventHandlers();
        this.mqttClient.connect();
        this.initFaceTracker();
        this.showStatusBriefly();

        console.log('Expression App initialized');
    }

    // ──────────────────────────────────────────────────────────────
    // Event handlers
    // ──────────────────────────────────────────────────────────────
    setupEventHandlers() {
        // MQTT message routing — dispatch by topic
        this.mqttClient.on('onMessage', (msg) => {
            if (msg.topic === this.MODE_TOPIC) {
                // Remote mode control: from CLI / SSH / main-entry.py
                const mode = msg.data && msg.data.mode;
                if (mode) this.setMode(mode);
            } else if (msg.topic === this.FER_EMOTION_TOPIC) {
                this.handleFEREmotionMessage(msg.data);
            } else if (msg.topic === this.FER_GAZE_TOPIC) {
                this.handleFERGazeMessage(msg.data);
            } else {
                // Default: robot/expression (speech commands, TTS)
                this.handleExpressionMessage(msg.data);
            }
        });
        this.mqttClient.on('onConnect', () => {
            console.log('MQTT connected');
            // Subscribe to remote mode control topic
            this.mqttClient.subscribeExtra(this.MODE_TOPIC);
        });
        this.mqttClient.on('onDisconnect', () => console.log('MQTT disconnected'));
        this.mqttClient.on('onError', (err) => console.error('MQTT Error:', err));

        document.addEventListener('keydown', (e) => {
            // ── Key 0: Return to Default mode from ANY mode ──
            if (e.key === '0') { this.setMode('default'); return; }

            // ── Expression shortcuts (only in default mode) ──
            if (this.currentMode === 'default') {
                if (e.key === 's') { this.handleExpressionMessage({ expression: 'speaking', duration: 3 }); return; }
                if (e.key === 'i') { this.handleExpressionMessage({ expression: 'idle', duration: 0 }); return; }
                if (e.key === '1') { this.handleExpressionMessage({ expression: 'sad', duration: 0 }); return; }
                if (e.key === '2') { this.handleExpressionMessage({ expression: 'shock', duration: 0 }); return; }
                if (e.key === '3') { this.handleExpressionMessage({ expression: 'cry', duration: 0 }); return; }
                if (e.key === '4') { this.handleExpressionMessage({ expression: 'shy', duration: 0 }); return; }
                if (e.key === '5') { this.handleExpressionMessage({ expression: 'happier', duration: 0 }); return; }
            }

            // ── Mode switching ──
            if (e.key === 'm' || e.key === 'M') { this.setMode('mirror'); return; }
            if (e.key === 'c' || e.key === 'C') { this.setMode('conversation'); return; }
            if (e.key === 'D') { this.setMode('default'); return; }  // Shift+D

            // ── System controls (work in all modes) ──
            if (e.key === 'd') {
                const panel = document.getElementById('debugPanel');
                if (panel) panel.classList.toggle('hidden');
            }
            else if (e.key === 't') this.toggleTracking();
            else if (e.key === 'r') this.resetHeadAngle();
            else if (e.key === 'ArrowLeft') this.panHead(-this.HEAD_PAN_STEP, 'manual_key');
            else if (e.key === 'ArrowRight') this.panHead(this.HEAD_PAN_STEP, 'manual_key');
        });
    }

    // ──────────────────────────────────────────────────────────────
    // Mode System
    // ──────────────────────────────────────────────────────────────
    setMode(mode) {
        if (this.currentMode === mode) return;
        const prevMode = this.currentMode;
        this.currentMode = mode;

        // Broadcast mode to Python subsystems (FER publisher, TTS, etc.)
        this.mqttClient.publish(this.MODE_TOPIC, { mode, timestamp_ms: Date.now() });

        if (mode === 'default') {
            // ── SWITCHING TO DEFAULT ──
            // Browser takes camera back, unsubscribe FER topics
            this._unsubscribeFERTopics();
            this.stopSpeaking();
            this.faceRenderer.setState('idle');

            // Resume MediaPipe face tracking
            if (this.faceTracker && this.faceTracker.paused) {
                this.faceTracker.resume();
            }
            this.trackingEnabled = true;

        } else {
            // ── SWITCHING TO MIRROR or CONVERSATION ──
            // Python takes camera, subscribe FER topics
            if (this.faceTracker && !this.faceTracker.usingMouseFallback) {
                this.faceTracker.pause();  // release camera for Python
            }
            this.trackingEnabled = false;
            this._subscribeFERTopics();

            if (mode === 'mirror') {
                this.stopSpeaking();
                console.log('[Mode] MIRROR — robot akan meniru ekspresi user');
            } else if (mode === 'conversation') {
                console.log('[Mode] CONVERSATION — TTS speech + FER emosi di sela bicara');
            }
        }

        this._updateModeIndicator();
        console.log(`[Mode] ${prevMode} → ${mode}`);
    }

    _subscribeFERTopics() {
        this.mqttClient.subscribeExtra(this.FER_EMOTION_TOPIC);
        this.mqttClient.subscribeExtra(this.FER_GAZE_TOPIC);
    }

    _unsubscribeFERTopics() {
        this.mqttClient.unsubscribe(this.FER_EMOTION_TOPIC);
        this.mqttClient.unsubscribe(this.FER_GAZE_TOPIC);
    }

    _updateModeIndicator() {
        const el = document.getElementById('modeIndicator');
        if (!el) return;

        const labels = {
            'default':      '🎭 Default',
            'mirror':       '🪞 Mirror',
            'conversation': '💬 Conversation'
        };
        el.textContent = labels[this.currentMode] || '';
        el.className = 'mode-badge mode-' + this.currentMode;
    }

    // ──────────────────────────────────────────────────────────────
    // FER Message Handlers (Mirror / Conversation modes)
    // ──────────────────────────────────────────────────────────────

    /**
     * Handle emotion data from FER-BRONE publisher.
     * Payload: { emotion, expression, confidence, timestamp }
     */
    handleFEREmotionMessage(data) {
        // Only process in mirror or conversation mode
        if (this.currentMode !== 'mirror' && this.currentMode !== 'conversation') return;

        // Fallback mapping: if publisher doesn't include 'expression', derive from 'emotion'
        const EMOTION_MAP = {
            'Happy': 'happier', 'Neutral': 'idle', 'Sad': 'sad',
            'Shocked': 'shock', 'Upset': 'cry'
        };
        const expression = data.expression || EMOTION_MAP[data.emotion] || 'idle';
        const confidence = data.confidence || 0;

        // Filter low confidence predictions
        if (confidence < this.FER_CONFIDENCE_THRESHOLD) return;

        // In conversation mode, speaking animation takes priority over FER
        if (this.currentMode === 'conversation' && this.faceRenderer.state === 'speaking') return;

        this.faceRenderer.setState(expression);
        console.log(`[FER] ${data.emotion} (${(confidence * 100).toFixed(0)}%) → ${expression}`);
    }

    /**
     * Handle gaze estimation from FER-BRONE publisher.
     * Payload: { gaze_x, gaze_y, face_detected }
     */
    handleFERGazeMessage(data) {
        // Only process in mirror or conversation mode
        if (this.currentMode !== 'mirror' && this.currentMode !== 'conversation') return;
        if (!data.face_detected) return;

        this.faceRenderer.setPupilOffset(
            Math.max(-1, Math.min(1, data.gaze_x || 0)),
            Math.max(-1, Math.min(1, data.gaze_y || 0))
        );
    }

    // ──────────────────────────────────────────────────────────────
    // Expression handling (robot/expression topic — speech, manual)
    // ──────────────────────────────────────────────────────────────
    handleExpressionMessage(data) {
        const expression = data.expression || 'idle';
        const duration = parseFloat(data.duration) || 0;

        if (expression === 'speaking' && duration > 0) {
            // Speaking works in ALL modes (TTS always takes priority)
            this.startSpeaking(duration);
        } else if (this.currentMode === 'default') {
            // Non-speaking expressions only in default mode
            if (expression === 'idle' || expression === 'smile') {
                this.stopSpeaking();
                this.faceRenderer.setState('idle');
            } else {
                this.stopSpeaking();
                this.faceRenderer.setState(expression);
            }
        }
    }

    startSpeaking(duration) {
        if (this.speakingTimer) clearTimeout(this.speakingTimer);
        this.faceRenderer.startSpeaking();
        this.speakingEndTime = Date.now() + duration * 1000;
        this.speakingTimer = setTimeout(() => this.stopSpeaking(), duration * 1000);
    }

    stopSpeaking() {
        if (this.speakingTimer) { clearTimeout(this.speakingTimer); this.speakingTimer = null; }
        this.faceRenderer.stopSpeaking();
    }

    showStatusBriefly() {
        const status = document.getElementById('statusIndicator');
        status.classList.add('visible');
        setTimeout(() => status.classList.remove('visible'), 3000);
    }

    getRemainingTime() {
        return this.speakingEndTime ? Math.max(0, (this.speakingEndTime - Date.now()) / 1000) : 0;
    }

    // ──────────────────────────────────────────────────────────────
    // Face Tracking
    // ──────────────────────────────────────────────────────────────
    async initFaceTracker() {
        const videoEl = document.getElementById('webcamVideo');
        if (!videoEl) { console.warn('No webcamVideo element, face tracking disabled'); return; }

        this.faceTracker = new FaceTracker(videoEl);
        const success = await this.faceTracker.init();

        if (success) {
            console.log('Face tracking initialized');
            this.startTrackingLoop();
        } else {
            // Mouse fallback is activated inside FaceTracker; still start loop
            console.warn('Camera failed — using mouse/touch fallback');
            this.startTrackingLoop();
        }
    }

    startTrackingLoop() {
        const loop = () => {
            if (this.faceTracker && this.faceTracker.isRunning && this.trackingEnabled) {
                const gaze = this.faceTracker.getGaze();
                const now = Date.now();

                // ─── Head Pan Logic (anti-shake hysteresis) ───────────────
                const atEdge = Math.abs(gaze.x) > this.PUPIL_EDGE_THRESHOLD;

                if (atEdge) {
                    // Start or continue the hold timer
                    if (this.edgeHoldStart === null) this.edgeHoldStart = now;

                    const holdDuration = now - this.edgeHoldStart;
                    if (holdDuration >= this.EDGE_HOLD_REQUIRED &&
                        now - this.lastHeadCommandTime > this.HEAD_COMMAND_INTERVAL) {

                        const direction = gaze.x > 0 ? 1 : -1;
                        this.panHead(direction * this.HEAD_PAN_STEP, 'pupil_edge');
                        this.lastHeadCommandTime = now;
                        this.edgeHoldStart = null;  // reset after command fires
                    }
                } else {
                    this.edgeHoldStart = null;      // reset if gaze returns to safe zone
                }

                // ─── Pupil = raw gaze (no auto-compensation) ──────────────
                this.faceRenderer.setPupilOffset(gaze.x, gaze.y);

                // ─── Update debug overlay ─────────────────────────────────
                this.updateHeadControlDebug(gaze, gaze.x, atEdge, now);

                // ─── MQTT telemetry ───────────────────────────────────────
                if (now - this.lastTelemetryTime > this.TELEMETRY_INTERVAL) {
                    this.publishTrackingState(gaze);
                    this.lastTelemetryTime = now;
                }
            }
            requestAnimationFrame(loop);
        };
        requestAnimationFrame(loop);
    }

    // ──────────────────────────────────────────────────────────────
    // Head Control Debug Overlay
    // ──────────────────────────────────────────────────────────────
    updateHeadControlDebug(rawGaze, compensatedX, atEdge, now) {
        // Helpers
        const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

        // ── Head angle text + bar ──
        setTxt('hcHeadAngle', this.headAngle.toFixed(1) + '°');
        const barFill = document.getElementById('hcBarFill');
        if (barFill) {
            // Convert headAngle (-45..+45) → fill from center
            const pct = (this.headAngle / this.HEAD_MAX_ANGLE) * 50; // -50%..+50%
            if (pct >= 0) {
                barFill.style.left = '50%';
                barFill.style.width = pct + '%';
            } else {
                barFill.style.left = (50 + pct) + '%';
                barFill.style.width = (-pct) + '%';
            }
        }

        // ── Gaze readings ──
        setTxt('hcRawGaze', `x:${rawGaze.x.toFixed(2)} y:${rawGaze.y.toFixed(2)}`);
        setTxt('hcCompGaze', compensatedX.toFixed(2));

        // ── Edge / hold timer ──
        const edgeDot = document.getElementById('hcEdgeDot');
        if (edgeDot) edgeDot.className = 'hc-dot' + (atEdge ? ' edge' : '');

        const holdPct = this.edgeHoldStart !== null
            ? Math.min(100, ((now - this.edgeHoldStart) / this.EDGE_HOLD_REQUIRED) * 100)
            : 0;
        const holdBar = document.getElementById('hcHoldBar');
        if (holdBar) holdBar.style.width = holdPct + '%';
        setTxt('hcHoldPct', Math.round(holdPct) + '%');

        // ── Payload preview (dummy - shows what would be sent) ──
        const payload = {
            pan_deg: parseFloat(this.headAngle.toFixed(1)),
            tilt_deg: 0,
            pan_norm: parseFloat((this.headAngle / this.HEAD_MAX_ANGLE).toFixed(2)),
            trigger: atEdge && holdPct >= 100 ? 'pupil_edge' : 'idle',
            at_limit: Math.abs(this.headAngle) >= this.HEAD_MAX_ANGLE,
            timestamp_ms: Date.now()
        };
        const payloadEl = document.getElementById('hcPayload');
        if (payloadEl) payloadEl.textContent = JSON.stringify(payload, null, 2);
    }

    // ──────────────────────────────────────────────────────────────
    // Head Pan Control
    // ──────────────────────────────────────────────────────────────
    panHead(deltaDegrees, trigger = 'auto') {
        const prev = this.headAngle;
        this.headAngle = Math.max(this.HEAD_MIN_ANGLE,
            Math.min(this.HEAD_MAX_ANGLE, this.headAngle + deltaDegrees));

        if (this.headAngle === prev && deltaDegrees !== 0)
            console.log(`Head at limit (${this.headAngle}°)`);

        console.log(`Head pan: ${prev.toFixed(1)}° → ${this.headAngle.toFixed(1)}° [${trigger}]`);
        this.publishHeadControl(trigger);
    }

    resetHeadAngle() {
        this.headAngle = 0;
        this.edgeHoldStart = null;
        console.log('Head reset to center');
        this.publishHeadControl('reset');
    }

    // ──────────────────────────────────────────────────────────────
    // MQTT Publishing
    // ──────────────────────────────────────────────────────────────
    publishHeadControl(trigger = 'auto') {
        const payload = {
            pan_deg: parseFloat(this.headAngle.toFixed(2)),
            tilt_deg: 0,
            pan_norm: parseFloat((this.headAngle / this.HEAD_MAX_ANGLE).toFixed(3)),
            trigger: trigger,
            at_limit: Math.abs(this.headAngle) >= this.HEAD_MAX_ANGLE,
            timestamp_ms: Date.now()
        };
        this.mqttClient.publish(this.HEAD_CONTROL_TOPIC, payload);
        console.log('→ robot/head_control:', JSON.stringify(payload));
    }

    publishTrackingState(rawGaze) {
        const payload = {
            face_detected: this.faceTracker ? this.faceTracker.faceDetected : false,
            raw_gaze_x: parseFloat(rawGaze.x.toFixed(3)),
            raw_gaze_y: parseFloat(rawGaze.y.toFixed(3)),
            head_pan_deg: parseFloat(this.headAngle.toFixed(2)),
            head_pan_norm: parseFloat((this.headAngle / this.HEAD_MAX_ANGLE).toFixed(3)),
            pupil_at_edge: Math.abs(rawGaze.x) >= this.PUPIL_EDGE_THRESHOLD,
            edge_hold_pct: this.edgeHoldStart
                ? Math.min(100, ((Date.now() - this.edgeHoldStart) / this.EDGE_HOLD_REQUIRED) * 100)
                : 0,
            tracking_enabled: this.trackingEnabled,
            timestamp_ms: Date.now()
        };
        this.mqttClient.publish(this.TRACKING_STATE_TOPIC, payload);
    }

    // ──────────────────────────────────────────────────────────────
    // Toggle
    // ──────────────────────────────────────────────────────────────
    toggleTracking() {
        if (!this.faceTracker) { console.log('Face tracker not available'); return; }
        this.trackingEnabled = !this.trackingEnabled;
        if (this.trackingEnabled) {
            this.faceTracker.start();
            console.log('Face tracking ON');
        } else {
            this.faceTracker.stop();
            this.faceRenderer.setPupilOffset(0, 0);
            this.edgeHoldStart = null;
            console.log('Face tracking OFF');
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new ExpressionApp();
});
