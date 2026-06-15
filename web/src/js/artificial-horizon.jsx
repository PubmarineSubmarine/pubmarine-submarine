import { useEffect, useRef } from "preact/hooks";

export default function ArtificialHorizon({ pitch, roll }) {
  const canvasRef = useRef(null);
  const targetPitch = useRef(pitch);
  const targetRoll = useRef(roll);
  const currentPitch = useRef(0);
  const currentRoll = useRef(0);

  useEffect(() => {
    targetPitch.current = pitch;
    targetRoll.current = roll;
  }, [pitch, roll]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const cx = 100,
      cy = 100;
    const hud = "rgba(0,255,200,",
      dim = "0.4)",
      bright = "0.9)",
      solid = "1)";
    const warn = "rgba(255,100,0,0.9)";

    let animId;
    const draw = () => {
      currentPitch.current +=
        (targetPitch.current - currentPitch.current) * 0.15;
      currentRoll.current += (targetRoll.current - currentRoll.current) * 0.15;
      // Invert pitch: with the chase-cam convention, positive pitch
      // (nose up) means the horizon sits lower in the sub's view, so
      // the ladder needs to render in the opposite direction.
      const p = -currentPitch.current;
      const r = currentRoll.current;
      const ps = 3,
        po = p * ps;

      ctx.clearRect(0, 0, 200, 200);

      // Horizon & Ladder
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate((-r * Math.PI) / 180);

      ctx.shadowBlur = 8;
      ctx.shadowColor = hud + solid;
      ctx.strokeStyle = hud + solid;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(-100, -po);
      ctx.lineTo(-20, -po);
      ctx.moveTo(20, -po);
      ctx.lineTo(100, -po);
      ctx.stroke();
      ctx.shadowBlur = 0;

      ctx.strokeStyle = hud + dim;
      ctx.lineWidth = 1.5;
      ctx.font = "bold 11px monospace";
      for (let a = -60; a <= 60; a += 20) {
        if (!a) continue;
        const y = -po - a * ps;
        if (Math.abs(y) > 150) continue;
        ctx.beginPath();
        ctx.moveTo(-35, y);
        ctx.lineTo(-8, y);
        ctx.moveTo(8, y);
        ctx.lineTo(35, y);
        ctx.stroke();
        ctx.fillStyle = hud + bright;
        ctx.textAlign = "right";
        ctx.fillText(Math.abs(a), -40, y + 4);
        ctx.textAlign = "left";
        ctx.fillText(Math.abs(a), 40, y + 4);
      }
      ctx.restore();

      // Reticle
      ctx.save();
      ctx.strokeStyle = hud + bright;
      ctx.fillStyle = hud + bright;
      ctx.lineWidth = 2;
      ctx.shadowBlur = 4;
      ctx.shadowColor = hud + bright;
      ctx.beginPath();
      ctx.arc(cx, cy, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(cx - 10, cy);
      ctx.lineTo(cx - 35, cy);
      ctx.moveTo(cx + 10, cy);
      ctx.lineTo(cx + 35, cy);
      ctx.stroke();
      ctx.shadowBlur = 0;
      ctx.restore();

      // Roll Scale
      ctx.save();
      ctx.translate(cx, cy);
      ctx.strokeStyle = hud + bright;
      ctx.fillStyle = hud + bright;
      ctx.lineWidth = 1.5;
      ctx.shadowBlur = 3;
      ctx.shadowColor = hud + bright;
      ctx.beginPath();
      ctx.arc(0, 0, 70, -Math.PI * 0.7, -Math.PI * 0.3);
      ctx.stroke();
      [-45, -30, 0, 30, 45].forEach((a) => {
        const rad = ((a - 90) * Math.PI) / 180;
        ctx.lineWidth = a ? 1.5 : 2;
        ctx.beginPath();
        ctx.moveTo(Math.cos(rad) * 65, Math.sin(rad) * 65);
        ctx.lineTo(
          Math.cos(rad) * (a ? 75 : 78),
          Math.sin(rad) * (a ? 75 : 78),
        );
        ctx.stroke();
      });
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, -78);
      ctx.lineTo(-4, -70);
      ctx.lineTo(4, -70);
      ctx.closePath();
      ctx.fill();
      ctx.rotate((-r * Math.PI) / 180);
      ctx.fillStyle = warn;
      ctx.strokeStyle = warn;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(0, -68);
      ctx.lineTo(-5, -60);
      ctx.lineTo(5, -60);
      ctx.closePath();
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.restore();

      // Readouts
      ctx.font = "bold 14px monospace";
      ctx.shadowBlur = 4;
      ctx.shadowColor = hud + bright;
      ctx.fillStyle = hud + bright;
      ctx.textAlign = "left";
      ctx.fillText("P", 165, 85);
      ctx.fillText(p.toFixed(1) + "°", 165, 105);
      ctx.textAlign = "right";
      ctx.fillText("R", 35, 85);
      ctx.fillText(r.toFixed(1) + "°", 35, 105);
      ctx.shadowBlur = 0;
    };

    const animate = () => {
      draw();
      animId = requestAnimationFrame(animate);
    };
    animate();
    return () => cancelAnimationFrame(animId);
  }, []);

  return <canvas ref={canvasRef} width={200} height={200} />;
}
