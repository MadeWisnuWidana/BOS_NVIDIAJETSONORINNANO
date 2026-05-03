/**
 * MQTT Client - Handles MQTT connection and message processing
 * Uses Paho MQTT library for WebSocket connection
 */

class MQTTClient {
    constructor(options = {}) {
        // Default configuration
        this.config = {
            host: options.host || 'localhost',
            port: options.port || 9001, // WebSocket port
            clientId: options.clientId || 'expression_display_' + Math.random().toString(16).substr(2, 8),
            topic: options.topic || 'robot/expression',
            reconnectInterval: options.reconnectInterval || 3000,
            ...options
        };

        this.client = null;
        this.isConnected = false;
        this.callbacks = {
            onMessage: [],
            onConnect: [],
            onDisconnect: [],
            onError: []
        };

        // Status element
        this.statusElement = document.getElementById('mqttStatus');
    }

    connect() {
        try {
            this.updateStatus('connecting', 'Connecting...');

            // Create MQTT client
            this.client = new Paho.MQTT.Client(
                this.config.host,
                this.config.port,
                this.config.clientId
            );

            // Set callback handlers
            this.client.onConnectionLost = (responseObject) => this.onConnectionLost(responseObject);
            this.client.onMessageArrived = (message) => this.onMessageArrived(message);

            // Connect options
            const connectOptions = {
                onSuccess: () => this.onConnect(),
                onFailure: (error) => this.onConnectFailure(error),
                timeout: 10,
                keepAliveInterval: 30,
                cleanSession: true
            };

            // Use SSL if specified
            if (this.config.useSSL) {
                connectOptions.useSSL = true;
            }

            // Connect
            this.client.connect(connectOptions);

        } catch (error) {
            console.error('MQTT connection error:', error);
            this.updateStatus('disconnected', 'Error');
            this.emit('onError', error);
            this.scheduleReconnect();
        }
    }

    onConnect() {
        console.log('MQTT Connected successfully');
        this.isConnected = true;
        this.updateStatus('connected', 'Connected');

        // Subscribe to topic
        this.client.subscribe(this.config.topic, {
            onSuccess: () => {
                console.log(`Subscribed to topic: ${this.config.topic}`);
            },
            onFailure: (error) => {
                console.error('Subscribe failed:', error);
            }
        });

        this.emit('onConnect');
    }

    onConnectFailure(error) {
        console.error('MQTT Connection failed:', error);
        this.isConnected = false;
        this.updateStatus('disconnected', 'Failed');
        this.emit('onError', error);
        this.scheduleReconnect();
    }

    onConnectionLost(responseObject) {
        this.isConnected = false;

        if (responseObject.errorCode !== 0) {
            console.error('MQTT Connection lost:', responseObject.errorMessage);
        }

        this.updateStatus('disconnected', 'Disconnected');
        this.emit('onDisconnect', responseObject);
        this.scheduleReconnect();
    }

    onMessageArrived(message) {
        try {
            const payload = message.payloadString;
            console.log(`MQTT Message received on ${message.destinationName}:`, payload);

            // Try to parse as JSON
            let data;
            try {
                data = JSON.parse(payload);
            } catch (e) {
                // If not JSON, use raw payload
                data = { raw: payload };
            }

            this.emit('onMessage', {
                topic: message.destinationName,
                payload: payload,
                data: data
            });

        } catch (error) {
            console.error('Error processing message:', error);
        }
    }

    scheduleReconnect() {
        if (!this.reconnectTimer) {
            console.log(`Reconnecting in ${this.config.reconnectInterval}ms...`);
            this.updateStatus('connecting', 'Reconnecting...');

            this.reconnectTimer = setTimeout(() => {
                this.reconnectTimer = null;
                this.connect();
            }, this.config.reconnectInterval);
        }
    }

    disconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.client && this.isConnected) {
            this.client.disconnect();
            this.isConnected = false;
            this.updateStatus('disconnected', 'Disconnected');
        }
    }

    publish(topic, message) {
        if (this.isConnected) {
            const mqttMessage = new Paho.MQTT.Message(JSON.stringify(message));
            mqttMessage.destinationName = topic;
            this.client.send(mqttMessage);
        } else {
            console.warn('Cannot publish: not connected');
        }
    }

    /**
     * Subscribe to an additional topic (beyond the primary config.topic).
     * Used by Mirror/Conversation modes to dynamically join FER topics.
     */
    subscribeExtra(topic) {
        if (this.isConnected && this.client) {
            this.client.subscribe(topic, {
                onSuccess: () => console.log(`[MQTT] Subscribed extra: ${topic}`),
                onFailure: (e) => console.error(`[MQTT] Subscribe extra failed: ${topic}`, e)
            });
        } else {
            console.warn(`[MQTT] Cannot subscribe ${topic}: not connected`);
        }
    }

    /**
     * Unsubscribe from a topic.
     */
    unsubscribe(topic) {
        if (this.isConnected && this.client) {
            this.client.unsubscribe(topic, {
                onSuccess: () => console.log(`[MQTT] Unsubscribed: ${topic}`),
                onFailure: (e) => console.error(`[MQTT] Unsubscribe failed: ${topic}`, e)
            });
        }
    }

    // Event handling
    on(event, callback) {
        if (this.callbacks[event]) {
            this.callbacks[event].push(callback);
        }
    }

    emit(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(callback => callback(data));
        }
    }

    updateStatus(status, text) {
        if (this.statusElement) {
            this.statusElement.textContent = text;
            this.statusElement.className = status;
        }
    }
}

// Export for use in other modules
window.MQTTClient = MQTTClient;
