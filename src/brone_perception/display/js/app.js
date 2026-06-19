
class BroneApp {
    constructor() {
        console.log('--- Initializing BRONE App (v10) ---');

        // Topics
        this.MODE_TOPIC         = 'robot/mode';
        this.EXPRESSION_TOPIC   = 'robot/expression';
        this.FER_EMOTION_TOPIC  = 'robot/fer_emotion';
        this.FER_GAZE_TOPIC     = 'robot/fer_gaze';
        this.HEAD_CONTROL_TOPIC = 'robot/head_control';

        // State
        this.currentMode = 'default';
        this.trackingEnabled = true;
        this.latestFERGaze = { x: 0, y: 0, detected: false, timestamp: 0 };

        // Components
        this.faceRenderer = new FaceRenderer(document.getElementById('faceCanvas'));
        this.faceTracker  = new FaceTracker(document.getElementById('webcamVideo'));
        
        this.mqttClient   = new MQTTClient({
            host: 'localhost',
            port: 9001,
            clientId: 'brone_display_' + Math.random().toString(16).substring(2, 8),
            topic: this.EXPRESSION_TOPIC
        });

        this.init();
    }

    init() {
        this.mqttClient.on('onConnect', () => {
            console.log('✓ MQTT Connected');
            this.mqttClient.subscribeExtra(this.MODE_TOPIC);
            this.mqttClient.subscribeExtra(this.FER_EMOTION_TOPIC);
            this.mqttClient.subscribeExtra(this.FER_GAZE_TOPIC);
        });

        this.mqttClient.on('onMessage', (msg) => {
            const topic = msg.topic;
            const data = msg.data;

            if (topic === this.MODE_TOPIC) this.setMode(data.mode);
            else if (topic === this.EXPRESSION_TOPIC) this.handleExpression(data);
            else if (topic === this.FER_EMOTION_TOPIC) this.handleFEREmotion(data);
            else if (topic === this.FER_GAZE_TOPIC) this.handleFERGaze(data);
        });

        this.mqttClient.connect();
        this.startControlLoop();
        this.initKeyboard();
    }

    async setMode(mode) {
        if (!mode || mode === this.currentMode) return;
        this.currentMode = mode;
        console.log('Display Mode Set to:', mode);

        if (mode === 'mirror' || mode === 'conversation' || mode === 'eyefollow' || mode === 'vision') {
            // Mode FER: Gunakan kamera Python (Jetson), Matikan kamera Browser
            this.faceTracker.pause();
            this.faceRenderer.setState('idle');
        } else {
            // Mode Default/EyeFollow: Gunakan kamera Browser (jika memungkinkan)
            // Atau biarkan fallback ke Jetson Gaze
            await this.ensureTrackerStarted();
            this.faceRenderer.setState('idle');
        }
    }

    async ensureTrackerStarted() {
        if (!this.faceTracker.isInitialized) {
            console.log('Initializing Browser FaceTracker for the first time...');
            try {
                await this.faceTracker.init();
            } catch (err) {
                console.warn('FaceTracker init failed (likely camera busy/denied)');
            }
        } else if (this.faceTracker.paused) {
            await this.faceTracker.resume();
        }
    }

    handleExpression(data) {
        if (this.faceRenderer) this.faceRenderer.setState(data.expression || 'idle');
    }

    handleFEREmotion(data) {
        if (this.currentMode !== 'mirror' && this.currentMode !== 'conversation') return;
        if (this.faceRenderer) this.faceRenderer.setState(data.expression || 'idle');
    }

    handleFERGaze(data) {
        this.latestFERGaze = {
            x: data.gaze_x || 0,
            y: data.gaze_y || 0,
            detected: data.face_detected || false,
            timestamp: Date.now()
        };

        if (this.latestFERGaze.detected && (!this.faceTracker.isRunning || this.faceTracker.paused || this.faceTracker.usingMouseFallback)) {
            this.faceRenderer.setPupilOffset(this.latestFERGaze.x, this.latestFERGaze.y);
        }
    }

    startControlLoop() {
        const FPS = 15;
        setInterval(() => {
            if (!this.trackingEnabled) return;

            let targetGaze = null;

            if (this.faceTracker.isRunning && !this.faceTracker.paused && !this.faceTracker.usingMouseFallback) {
                const gaze = this.faceTracker.getGaze();
                if (gaze.x !== 0 || gaze.y !== 0) {
                    targetGaze = gaze;
                }
            }

            // if (!targetGaze && this.latestFERGaze.detected) {
            //     if (Date.now() - this.latestFERGaze.timestamp < 1000) {
            //         targetGaze = { x: this.latestFERGaze.x, y: this.latestFERGaze.y };
            //     }
            // }

            if (targetGaze) {
                const pan = targetGaze.x * -35.0; 
                const tilt = targetGaze.y * 20.0;

                this.mqttClient.publish(this.HEAD_CONTROL_TOPIC, {
                    pan_deg: parseFloat(pan.toFixed(2)),
                    tilt_deg: parseFloat(tilt.toFixed(2)),
                    timestamp: Date.now()
                });

                if (this.faceTracker.isRunning && !this.faceTracker.paused && !this.faceTracker.usingMouseFallback) {
                    this.faceRenderer.setPupilOffset(targetGaze.x, targetGaze.y);
                }
            }
        }, 1000 / FPS);
    }

    initKeyboard() {
        window.addEventListener('keydown', (e) => {
            if (e.key === 'd') document.getElementById('debugPanel')?.classList.toggle('hidden');
            if (e.key === 't') this.ensureTrackerStarted();
        });
    }
}

window.addEventListener('DOMContentLoaded', () => {
    window.app = new BroneApp();
});
