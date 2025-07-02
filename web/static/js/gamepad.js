/**
 * Gamepad API Demo - Vanilla JavaScript
 * Displays gamepad button presses and analog stick positions
 */

class GamepadDemo {
    constructor() {
        this.gamepadIndex = null;
        this.previousButtons = [];
        this.animationFrame = null;
        this.isRunning = false;
        this.websocket = null;
        this.wsConnected = false;
        
        // Button mapping for standard gamepad
        this.buttonNames = {
            0: 'A / Cross',
            1: 'B / Circle', 
            2: 'X / Square',
            3: 'Y / Triangle',
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
    }
    
    bindEvents() {
        // Gamepad connect/disconnect events
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
        
        // Manual start/stop buttons
        document.getElementById('start-demo')?.addEventListener('click', () => {
            this.checkForGamepads();
            this.start();
        });
        
        document.getElementById('stop-demo')?.addEventListener('click', () => {
            this.stop();
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
    
    updateGamepadState() {
        const gamepads = navigator.getGamepads();
        const gamepad = gamepads[this.gamepadIndex];
        
        if (!gamepad) {
            this.stop();
            return;
        }
        
        // Check buttons
        gamepad.buttons.forEach((button, index) => {
            const wasPressed = this.previousButtons[index] || false;
            const isPressed = button.pressed;
            
            if (!wasPressed && isPressed) {
                this.onButtonPress(index, button.value);
            }
        });
        
        // Update analog sticks
        this.updateAnalogSticks(gamepad.axes);
        
        // Store current button state for next frame (store just the pressed boolean)
        this.previousButtons = gamepad.buttons.map(button => button.pressed);
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
        
        // Add to button history
        this.addToButtonHistory(buttonName, value);
    }
    
    updateAnalogSticks(axes) {
        if (axes.length >= 4) {
            // Left stick (axes 0, 1)
            this.updateStickDisplay('left-stick', axes[0], axes[1]);
            
            // Right stick (axes 2, 3)  
            this.updateStickDisplay('right-stick', axes[2], axes[3]);
            
            // Send analog stick data via WebSocket (throttled and with deadzone)
            if (!this.lastStickSent || Date.now() - this.lastStickSent > 100) {
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
                }
                
                this.lastStickSent = Date.now();
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
            
            // Update visual indicator (assuming a 100px container)
            const centerX = 50;
            const centerY = 50;
            const maxRadius = 40;
            
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
    
    addToButtonHistory(buttonName, value) {
        const historyEl = document.getElementById('button-history');
        if (!historyEl) return;
        
        const timestamp = new Date().toLocaleTimeString();
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';
        historyItem.innerHTML = `
            <span class="timestamp">${timestamp}</span>
            <span class="button-name">${buttonName}</span>
            <span class="button-value">${value.toFixed(3)}</span>
        `;
        
        historyEl.insertBefore(historyItem, historyEl.firstChild);
        
        // Keep only last 10 items
        while (historyEl.children.length > 10) {
            historyEl.removeChild(historyEl.lastChild);
        }
    }
    
    updateConnectionStatus(connected, gamepadId = '') {
        const statusEl = document.getElementById('connection-status');
        const gamepadInfoEl = document.getElementById('gamepad-info');
        
        if (statusEl) {
            statusEl.textContent = connected ? 'Connected' : 'Disconnected';
            statusEl.className = connected ? 'status-connected' : 'status-disconnected';
        }
        
        if (gamepadInfoEl) {
            gamepadInfoEl.textContent = connected ? gamepadId : 'No gamepad detected';
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
                console.log('Received from server:', data);
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
                The Gamepad API requires HTTPS. Please access this page via:<br>
                <code>https://localhost:8000/gamepad</code><br>
                <small>Or use the HTTPS server command below.</small>
            `;
        }
        return;
    }
    
    // Initialize gamepad demo
    window.gamepadDemo = new GamepadDemo();
});