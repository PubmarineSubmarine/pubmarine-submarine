class GamepadController {
    constructor() {
        this.gamepadIndex = null;
        this.previousButtons = [];
        this.animationFrame = null;
        this.isRunning = false;
        this.websocket = null;
        this.wsConnected = false;
        this.objectGamepadState = "";
        this.submarine3D = null;
        this.artificialHorizon = null;

        this.consoleBufferLimit = 50_000;
        this.consoleHistory = [];

        // Button mapping for standard gamepad
        this.buttonNames = {
            0: 'A',
            1: 'B',
            2: 'X',
            3: 'Y',
            4: 'Left Bumper',
            5: 'Right Bumper',
            6: 'Left Trigger',
            7: 'Right Trigger',
            8: 'Back / Select',
            9: 'Start',
            10: 'Left Stick',
            11: 'Right Stick',
            12: 'D-Pad Up',
            13: 'D-Pad Down',
            14: 'D-Pad Left',
            15: 'D-Pad Right',
            16: 'Home / Xbox'
        };

        this.init();
    }

    init() {
        this.bindEvents();
        this.initWebSocket();
        this.updateDisplay();
        this.init3DSubmarine();
        this.initArtificialHorizon();
        document.getElementById("testing-btn").addEventListener("click", () => {
            this.onButtonPress(8, 1.0);
        });
        const dlBtn = document.getElementById("download-console");
        if (dlBtn) {
            dlBtn.addEventListener("click", () => this.downloadConsole());
        }
        const consoleInput = document.getElementById("console-input");
        if (consoleInput) {
            consoleInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter" && consoleInput.value.trim()) {
                    this.sendWebSocketData({
                        type: "console_command",
                        text: consoleInput.value.trim()
                    });
                    consoleInput.value = "";
                }
            });
        }
    }

    initArtificialHorizon() {
        if (typeof ArtificialHorizon !== 'undefined') {
            this.artificialHorizon = new ArtificialHorizon('artificial-horizon');
            console.log('Artificial horizon initialized');
        } else {
            console.warn('ArtificialHorizon class not found');
        }
    }

    init3DSubmarine() {
        // Wait for THREE and OBJLoader to be ready before initializing
        const initSub = () => {
            if (typeof THREE !== 'undefined' && typeof OBJLoader !== 'undefined' && typeof Submarine3D !== 'undefined') {
                const modelPath = '/static/subsanwich.obj';
                this.submarine3D = new Submarine3D('submarine-3d-container', modelPath);
                console.log('3D submarine visualization initialized');
            } else {
                console.warn('THREE, Submarine3D class or OBJLoader not found');
            }
        };

        // If THREE and OBJLoader are already loaded, init immediately
        if (typeof THREE !== 'undefined' && typeof OBJLoader !== 'undefined') {
            initSub();
        } else {
            // Otherwise wait for the event
            window.addEventListener('objloader-ready', initSub, { once: true });
        }
    }

    bindEvents() {
        window.addEventListener('gamepadconnected', (e) => {
            console.log('Gamepad connected:', e.gamepad.id);
            this.gamepadIndex = e.gamepad.index;
            this.updateConnectionStatus(true, e.gamepad.id);
            this.sendWebSocketData({
                type: 'gamepad_connected',
                gamepad_id: e.gamepad.id,
                index: e.gamepad.index
            });
            this.start();
        });

        window.addEventListener('gamepaddisconnected', (e) => {
            console.log('Gamepad disconnected:', e.gamepad.id);
            this.updateConnectionStatus(false);
            this.sendWebSocketData({
                type: 'gamepad_disconnected',
                gamepad_id: e.gamepad.id
            });
            this.stop();
            this.gamepadIndex = null;
        });
    }

    checkForGamepads() {
        const gamepads = navigator.getGamepads();
        for (let i = 0; i < gamepads.length; i++) {
            if (gamepads[i]) {
                this.gamepadIndex = i;
                this.updateConnectionStatus(true, gamepads[i].id);
                return true;
            }
        }
        this.updateConnectionStatus(false);
        return false;
    }

    start() {
        if (!this.isRunning && this.gamepadIndex !== null) {
            this.isRunning = true;
            this.loop();
        } else if (this.gamepadIndex === null) {
            // Try to force detection by checking again
            if (this.checkForGamepads()) {
                this.start();
            }
        }
    }

    stop() {
        this.isRunning = false;
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
    }

    loop() {
        if (!this.isRunning) return;

        this.updateGamepadState();
        this.animationFrame = requestAnimationFrame(() => this.loop());
    }

    gamepadToObject(obj) {
        if (obj === null || typeof obj !== 'object') {
            return obj;
        }

        if (Array.isArray(obj)) {
            return obj.map(item => this.gamepadToObject(item));
        }

        const result = {};
        for (let prop in obj) {
            const value = obj[prop];
            if (typeof value !== 'function') {
                result[prop] = this.gamepadToObject(value);
            }
        }

        return result;
    }

    updateGamepadState() {
        const gamepads = navigator.getGamepads();
        const gamepad = gamepads[this.gamepadIndex];

        if (!gamepad) {
            this.stop();
            return;
        }

        const gamepadObj = this.gamepadToObject(gamepad)
        if (!_.isEqual(gamepadObj, this.objectGamepadState)) {
            console.log(gamepadObj)
            this.objectGamepadState = gamepadObj
            this.sendWebSocketData(
                {
                    type: 'gamepad_state',
                    gamepad: gamepadObj,
                }
            )
        }

        // Check buttons
        gamepad.buttons.forEach((button, index) => {
            const wasPressed = this.previousButtons[index] || false;
            const isPressed = button.pressed;

            if (!wasPressed && isPressed) {
                this.onButtonPress(index, button.value);
            } else if (wasPressed && !isPressed) {
                this.onButtonRelease(index, button.value)
            }
        });

        // Update analog sticks
        this.updateAnalogSticks(gamepad.axes);

        this.updateAnalogTriggers(gamepad.buttons);

        // Store current button state for next frame (store just the pressed boolean)
        this.previousButtons = gamepad.buttons.map(button => button.pressed);
    }

    onButtonRelease(buttonIndex, value) {
        const buttonName = this.buttonNames[buttonIndex] || `Button ${buttonIndex}`;
        this.sendWebSocketData({
            type: 'button_release',
            button_index: buttonIndex,
            button_name: buttonName,
            value: value,
            timestamp: Date.now()
        });
    }

    onButtonPress(buttonIndex, value) {
        const buttonName = this.buttonNames[buttonIndex] || `Button ${buttonIndex}`;

        // Send to WebSocket
        this.sendWebSocketData({
            type: 'button_press',
            button_index: buttonIndex,
            button_name: buttonName,
            value: value,
            timestamp: Date.now()
        });

        // Update last pressed button display
        const lastButtonEl = document.getElementById('last-button');
        if (lastButtonEl) {
            lastButtonEl.textContent = buttonName;
            lastButtonEl.className = 'button-pressed';

            // Remove animation class after animation completes
            setTimeout(() => {
                lastButtonEl.className = '';
            }, 500);
        }

        // Log to console
        this.logConsole("BTN", buttonName);
    }

    updateAnalogSticks(axes) {
        if (axes.length >= 4) {
            // Left stick (axes 0, 1)
            this.updateStickDisplay('left-stick', axes[0], axes[1]);

            // Right stick (axes 2, 3)  
            this.updateStickDisplay('right-stick', axes[2], axes[3]);

            // Send analog stick data via WebSocket (throttled and with deadzone)
            if (!this.lastStickSent || Date.now() - this.lastStickSent > 10) {
                const deadzone = 0.1;

                // Left stick - only send if outside deadzone
                if (Math.abs(axes[0]) >= deadzone || Math.abs(axes[1]) >= deadzone) {
                    this.sendWebSocketData({
                        type: 'analog_stick',
                        stick: 'left',
                        x: axes[0],
                        y: axes[1],
                        timestamp: Date.now()
                    });
                    this.lastLeftStickSent = true;
                } else if (this.lastLeftStickSent) {
                    this.sendWebSocketData({
                        type: 'analog_stick',
                        stick: 'left',
                        x: 0.0,
                        y: 0.0,
                        timestamp: Date.now()
                    });
                    this.lastLeftStickSent = false;
                }

                // Right stick - only send if outside deadzone
                if (Math.abs(axes[2]) >= deadzone || Math.abs(axes[3]) >= deadzone) {
                    this.sendWebSocketData({
                        type: 'analog_stick',
                        stick: 'right',
                        x: axes[2],
                        y: axes[3],
                        timestamp: Date.now()
                    });
                    this.lastRightStickSent = true;
                } else if (this.lastRightStickSent) {
                    this.sendWebSocketData({
                        type: 'analog_stick',
                        stick: 'right',
                        x: 0.0,
                        y: 0.0,
                        timestamp: Date.now()
                    });
                    this.lastRightStickSent = false;
                }

                this.lastStickSent = Date.now();
            }
        }
    }

    updateAnalogTriggers(buttons) {
        if (buttons.length >= 8) {
            // Left trigger (button 6)
            this.updateTriggerDisplay('left-trigger', buttons[6].value);

            // Right trigger (button 7)
            this.updateTriggerDisplay('right-trigger', buttons[7].value);

            // Send analog trigger data via WebSocket with deadzone
            const deadzone = 0.1;
            const now = Date.now();

            // Left trigger - send when value changes
            if (Math.abs(buttons[6].value) >= deadzone) {
                this.sendWebSocketData({
                    type: 'analog_trigger',
                    trigger: 'left',
                    value: buttons[6].value,
                    timestamp: now
                });
                this.lastLeftTriggerSent = true;
            }
            if (Math.abs(buttons[6].value) < deadzone && this.lastLeftTriggerSent) {
                this.sendWebSocketData({
                    type: 'analog_trigger',
                    trigger: 'left',
                    value: 0,
                    timestamp: now
                });
                this.lastLeftTriggerSent = false;
            }

            // Right trigger - send when value changes
            if (Math.abs(buttons[7].value) >= deadzone) {
                this.sendWebSocketData({
                    type: 'analog_trigger',
                    trigger: 'right',
                    value: buttons[7].value,
                    timestamp: now
                });
                this.lastRightTriggerSent = true;
            }
            if (Math.abs(buttons[7].value) < deadzone && this.lastRightTriggerSent) {
                this.sendWebSocketData({
                    type: 'analog_trigger',
                    trigger: 'right',
                    value: 0,
                    timestamp: now
                });
                this.lastRightTriggerSent = false;
            }
        }
    }

    updateStatusDisplay(state) {
        //console.log(`update ${state}`)
        const valuesEl = document.getElementById('left-status-values');
        if (valuesEl) {
            valuesEl.innerHTML = `Battery: ${state.bat}<br/>Depth: ${state.depth}<br/>Accel: ${state.acc}<br/>Gyro: ${state.gyro}`;
        }

        // Update 3D submarine orientation and artificial horizon if gyro data is available
        if (this.submarine3D && state.gyro) {
            // Parse gyro data (comes as tuple string like "(1.2,3.4,5.6)")
            let gyroData;
            if (typeof state.gyro === 'string') {
                const matches = state.gyro.match(/\(([-\d.]+),([-\d.]+),([-\d.]+)\)/);
                if (matches) {
                    gyroData = {
                        x: parseFloat(matches[1]),
                        y: parseFloat(matches[2]),
                        z: parseFloat(matches[3])
                    };
                }
            } else if (Array.isArray(state.gyro)) {
                gyroData = {
                    x: state.gyro[0],
                    y: state.gyro[1],
                    z: state.gyro[2]
                };
            } else if (typeof state.gyro === 'object') {
                gyroData = state.gyro;
            }

            if (gyroData) {
                this.submarine3D.updateOrientation(gyroData);
                this.artificialHorizon.updateOrientation(gyroData);
            }
        }
    }

    updateStickDisplay(stickId, x, y) {
        const stickEl = document.getElementById(stickId);
        const valuesEl = document.getElementById(`${stickId}-values`);

        if (stickEl) {
            // Apply deadzone
            const deadzone = 0.1;
            const adjustedX = Math.abs(x) < deadzone ? 0 : x;
            const adjustedY = Math.abs(y) < deadzone ? 0 : y;

            // Update visual indicator (80px container)
            const containerSize = 80;
            const centerX = containerSize / 2;
            const centerY = containerSize / 2;
            const maxRadius = (containerSize / 2) - 10; // Leave some margin from edge

            const visualX = centerX + (adjustedX * maxRadius);
            const visualY = centerY + (adjustedY * maxRadius);

            const indicator = stickEl.querySelector('.stick-indicator');
            if (indicator) {
                indicator.style.left = `${visualX}px`;
                indicator.style.top = `${visualY}px`;
            }
        }

        if (valuesEl) {
            valuesEl.textContent = `X: ${x.toFixed(3)}, Y: ${y.toFixed(3)}`;
        }
    }

    updateTriggerDisplay(triggerId, value) {
        const triggerEl = document.getElementById(triggerId);
        const valuesEl = document.getElementById(`${triggerId}-values`);

        /* if (stickEl) {
            // Apply deadzone
            const deadzone = 0.1;
            const adjustedX = Math.abs(x) < deadzone ? 0 : x;
            const adjustedY = Math.abs(y) < deadzone ? 0 : y;

            // Update visual indicator (80px container)
            const containerSize = 80;
            const centerX = containerSize / 2;
            const centerY = containerSize / 2;
            const maxRadius = (containerSize / 2) - 10; // Leave some margin from edge

            const visualX = centerX + (adjustedX * maxRadius);
            const visualY = centerY + (adjustedY * maxRadius);

            const indicator = stickEl.querySelector('.stick-indicator');
            if (indicator) {
                indicator.style.left = `${visualX}px`;
                indicator.style.top = `${visualY}px`;
            }
        } */

        if (valuesEl) {
            let label = triggerId == 'left' ? 'LT' : 'RT';
            valuesEl.textContent = `${label}: ${value.toFixed(3)}`;
        }
    }

    logConsole(label, message) {
        const timestamp = new Date().toISOString();
        this.consoleHistory.push({ ts: timestamp, label, message });

        // Trim internal buffer to limit
        while (this.consoleHistory.length > this.consoleBufferLimit * 2) {
            this.consoleHistory.shift();
        }

        const historyEl = document.getElementById('console-history');
        if (!historyEl) return;

        // Remove placeholder on first entry
        const ph = historyEl.querySelector('.history-placeholder');
        if (ph) ph.remove();

        const item = document.createElement('div');
        item.className = 'history-item';
        item.innerHTML = `
            <span class="timestamp">${new Date(timestamp).toLocaleTimeString()}</span>
            <span class="button-name">[${label}]</span>
            <span class="button-value">${message}</span>
        `;

        historyEl.appendChild(item);

        // Auto-scroll to bottom
        historyEl.scrollTop = historyEl.scrollHeight;

        // Keep only last 500 DOM items for performance
        while (historyEl.querySelectorAll('.history-item').length > this.consoleBufferLimit) {
            const first = historyEl.querySelector(':scope > .history-item:first-child');
            if (first) first.remove();
        }
    }

    downloadConsole() {
        if (!this.consoleHistory.length) return;

        const lines = this.consoleHistory.map(e => `${e.ts} [${e.label}] ${e.message}`);
        const text = `--- Console Log (${new Date().toISOString()}) ---\n\n` + lines.join('\n') + '\n';

        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `console-${Date.now()}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        // Clear buffer and UI
        this.consoleHistory.length = 0;
        const historyEl = document.getElementById('console-history');
        if (historyEl) {
            historyEl.innerHTML = '<div class="history-placeholder">No messages...</div>';
        }
    }

    updateConnectionStatus(connected, gamepadId = '') {
        const statusEl = document.getElementById('connection-status');

        if (statusEl) {
            statusEl.textContent = connected ? gamepadId : 'Disconnected';
            statusEl.className = connected ? 'status-connected' : 'status-disconnected';
        }
    }

    updateDisplay() {
        // Initial check for already connected gamepads
        this.checkForGamepads();
    }

    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/gamepad`;

        try {
            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                console.log('WebSocket connected');
                this.wsConnected = true;
                this.updateWebSocketStatus(true);
            };

            this.websocket.onclose = () => {
                console.log('WebSocket disconnected');
                this.wsConnected = false;
                this.updateWebSocketStatus(false);
                // Attempt to reconnect after 3 seconds
                setTimeout(() => this.initWebSocket(), 3000);
            };

            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.wsConnected = false;
                this.updateWebSocketStatus(false);
            };

            this.websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                //console.log('Received from server:', data);
                if (data.name === "STAT") {
                    this.updateStatusDisplay(data);
                } else if (data.name === "CONSOLE") {
                    console.info(data.line);
                    this.logConsole(data.level, data.line);
                } else {
                    this.logConsole(data.name, JSON.stringify(data));
                }
            };

        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.updateWebSocketStatus(false);
        }
    }

    sendWebSocketData(data) {
        if (this.websocket && this.wsConnected && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify(data));
        }
    }

    updateWebSocketStatus(connected) {
        const wsStatusEl = document.getElementById('websocket-status');
        if (wsStatusEl) {
            wsStatusEl.textContent = connected ? 'Connected' : 'Disconnected';
            wsStatusEl.className = connected ? 'status-connected' : 'status-disconnected';
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Check if gamepad API is supported
    if (!navigator.getGamepads) {
        const errorEl = document.getElementById('gamepad-error');
        if (errorEl) {
            errorEl.style.display = 'block';
            errorEl.textContent = 'Gamepad API is not supported in this browser.';
        }
        return;
    }

    // Check for secure context (required for Gamepad API)
    if (!window.isSecureContext) {
        const errorEl = document.getElementById('gamepad-error');
        if (errorEl) {
            errorEl.style.display = 'block';
            errorEl.innerHTML = `
                <strong>Secure Context Required</strong><br>
                The Gamepad API requires HTTPS.<br>
            `;
        }
        return;
    }

    window.gamepadController = new GamepadController();
});
