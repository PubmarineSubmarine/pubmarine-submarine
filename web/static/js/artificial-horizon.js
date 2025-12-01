/**
 * Artificial Horizon Indicator
 * Displays pitch and roll orientation on a circular canvas HUD element
 */

class ArtificialHorizon {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error(`Canvas ${canvasId} not found`);
            return;
        }

        this.ctx = this.canvas.getContext('2d');
        this.width = this.canvas.width;
        this.height = this.canvas.height;
        this.centerX = this.width / 2;
        this.centerY = this.height / 2;
        this.radius = Math.min(this.width, this.height) / 2 - 10;

        // Current orientation (in degrees)
        this.roll = 0;   // rotation around forward axis
        this.pitch = 0;  // nose up/down

        // Target orientation for smooth interpolation
        this.targetRoll = 0;
        this.targetPitch = 0;

        // Smoothing factor
        this.smoothing = 0.15;

        // Colors - HUD style with cyan/green
        this.hudColor = 'rgba(0, 255, 200, 0.9)';      // Cyan-green primary
        this.hudColorDim = 'rgba(0, 255, 200, 0.4)';   // Dimmed version
        this.horizonColor = 'rgba(0, 255, 200, 1)';    // Bright horizon line
        this.warningColor = 'rgba(255, 100, 0, 0.9)';  // Orange for warnings

        // Start animation
        this.animate();
    }

    /**
     * Update target orientation from gyro data
     * @param {Object} gyro - Gyro data with x (roll), y (pitch), z (yaw)
     */
    updateOrientation(gyro) {
        // Set target values for smooth interpolation
        this.targetPitch = gyro.y || 0;  // pitch
        this.targetRoll = gyro.x || 0;   // roll
    }

    /**
     * Main animation loop
     */
    animate() {
        // Smooth interpolation
        this.pitch += (this.targetPitch - this.pitch) * this.smoothing;
        this.roll += (this.targetRoll - this.roll) * this.smoothing;

        this.draw();
        requestAnimationFrame(() => this.animate());
    }

    /**
     * Draw the artificial horizon - flight sim HUD style
     */
    draw() {
        const ctx = this.ctx;

        // Clear canvas
        ctx.clearRect(0, 0, this.width, this.height);

        // Save context state
        ctx.save();

        // Move to center and apply roll rotation
        ctx.translate(this.centerX, this.centerY);
        ctx.rotate(-this.roll * Math.PI / 180);

        // Calculate pitch offset (pixels per degree)
        const pitchScale = 3;
        const pitchOffset = this.pitch * pitchScale;

        // Draw horizon line with glow effect
        ctx.shadowBlur = 8;
        ctx.shadowColor = this.horizonColor;
        ctx.strokeStyle = this.horizonColor;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(-100, -pitchOffset);
        ctx.lineTo(-20, -pitchOffset);
        ctx.moveTo(20, -pitchOffset);
        ctx.lineTo(100, -pitchOffset);
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Draw pitch ladder
        this.drawPitchLadder(ctx, pitchOffset, pitchScale);

        // Restore context
        ctx.restore();

        // Draw fixed reference elements
        this.drawHUDReticle(ctx);
        this.drawRollScale(ctx);
        this.drawPitchReadout(ctx);
        this.drawRollReadout(ctx);
    }

    /**
     * Draw pitch ladder - simplified
     */
    drawPitchLadder(ctx, pitchOffset, pitchScale) {
        ctx.strokeStyle = this.hudColorDim;
        ctx.lineWidth = 1.5;
        ctx.font = 'bold 11px monospace';
        ctx.fillStyle = this.hudColor;
        ctx.textAlign = 'left';

        // Draw lines at 20-degree intervals only
        for (let angle = -60; angle <= 60; angle += 20) {
            if (angle === 0) continue; // Skip horizon line

            const y = -pitchOffset - (angle * pitchScale);

            // Only draw if within reasonable viewing distance
            if (Math.abs(y) > 150) continue;

            const lineLength = 35;

            ctx.strokeStyle = this.hudColorDim;
            ctx.lineWidth = 1.5;

            // Draw ladder lines (split in middle)
            ctx.beginPath();
            ctx.moveTo(-lineLength, y);
            ctx.lineTo(-8, y);
            ctx.moveTo(8, y);
            ctx.lineTo(lineLength, y);
            ctx.stroke();

            // Draw angle labels
            ctx.fillStyle = this.hudColor;
            ctx.textAlign = 'right';
            ctx.fillText(`${Math.abs(angle)}`, -lineLength - 5, y + 4);
            ctx.textAlign = 'left';
            ctx.fillText(`${Math.abs(angle)}`, lineLength + 5, y + 4);
        }
    }

    /**
     * Draw HUD center reticle - simplified
     */
    drawHUDReticle(ctx) {
        ctx.save();
        ctx.strokeStyle = this.hudColor;
        ctx.fillStyle = this.hudColor;
        ctx.lineWidth = 2;
        ctx.shadowBlur = 4;
        ctx.shadowColor = this.hudColor;

        const cx = this.centerX;
        const cy = this.centerY;

        // Center dot
        ctx.beginPath();
        ctx.arc(cx, cy, 2, 0, Math.PI * 2);
        ctx.fill();

        // Simple horizontal wings
        ctx.beginPath();
        ctx.moveTo(cx - 10, cy);
        ctx.lineTo(cx - 35, cy);
        ctx.moveTo(cx + 10, cy);
        ctx.lineTo(cx + 35, cy);
        ctx.stroke();

        ctx.shadowBlur = 0;
        ctx.restore();
    }

    /**
     * Draw roll scale arc at top - simplified
     */
    drawRollScale(ctx) {
        ctx.save();
        ctx.strokeStyle = this.hudColor;
        ctx.fillStyle = this.hudColor;
        ctx.lineWidth = 1.5;
        ctx.shadowBlur = 3;
        ctx.shadowColor = this.hudColor;

        const arcRadius = 70;
        const angles = [-45, -30, 0, 30, 45];

        ctx.translate(this.centerX, this.centerY);

        // Draw arc
        ctx.beginPath();
        ctx.arc(0, 0, arcRadius, -Math.PI * 0.7, -Math.PI * 0.3, false);
        ctx.stroke();

        // Draw roll marks (fewer marks)
        angles.forEach(angle => {
            const rad = (angle - 90) * Math.PI / 180;
            const innerR = arcRadius - 5;
            const outerR = (angle === 0) ? arcRadius + 8 : arcRadius + 5;

            const x1 = Math.cos(rad) * innerR;
            const y1 = Math.sin(rad) * innerR;
            const x2 = Math.cos(rad) * outerR;
            const y2 = Math.sin(rad) * outerR;

            ctx.lineWidth = (angle === 0) ? 2 : 1.5;
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.stroke();
        });

        // Draw roll pointer (fixed at top)
        ctx.lineWidth = 2;
        ctx.fillStyle = this.hudColor;
        ctx.beginPath();
        ctx.moveTo(0, -arcRadius - 8);
        ctx.lineTo(-4, -arcRadius);
        ctx.lineTo(4, -arcRadius);
        ctx.closePath();
        ctx.fill();

        // Draw current roll indicator (rotates with horizon)
        ctx.rotate(-this.roll * Math.PI / 180);
        ctx.fillStyle = this.warningColor;
        ctx.strokeStyle = this.warningColor;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(0, -arcRadius + 2);
        ctx.lineTo(-5, -arcRadius + 10);
        ctx.lineTo(5, -arcRadius + 10);
        ctx.closePath();
        ctx.fill();

        ctx.shadowBlur = 0;
        ctx.restore();
    }

    /**
     * Draw pitch readout
     */
    drawPitchReadout(ctx) {
        ctx.save();
        ctx.fillStyle = this.hudColor;
        ctx.strokeStyle = this.hudColor;
        ctx.font = 'bold 14px monospace';
        ctx.textAlign = 'left';
        ctx.shadowBlur = 4;
        ctx.shadowColor = this.hudColor;

        // Pitch indicator on right side
        const pitchText = `${this.pitch.toFixed(1)}°`;
        const x = this.centerX + 65;
        const y = this.centerY + 5;

        ctx.fillText('P', x, y - 20);
        ctx.fillText(pitchText, x, y);

        ctx.shadowBlur = 0;
        ctx.restore();
    }

    /**
     * Draw roll readout
     */
    drawRollReadout(ctx) {
        ctx.save();
        ctx.fillStyle = this.hudColor;
        ctx.strokeStyle = this.hudColor;
        ctx.font = 'bold 14px monospace';
        ctx.textAlign = 'right';
        ctx.shadowBlur = 4;
        ctx.shadowColor = this.hudColor;

        // Roll indicator on left side
        const rollText = `${this.roll.toFixed(1)}°`;
        const x = this.centerX - 65;
        const y = this.centerY + 5;

        ctx.fillText('R', x, y - 20);
        ctx.fillText(rollText, x, y);

        ctx.shadowBlur = 0;
        ctx.restore();
    }
}
