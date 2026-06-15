"""Smoke test for the orientation filter."""
import math
import time

from app.orientation import MadgwickFilter, OrientationEstimator
from app.protocol import OriCmd

# 1) Stationary upright -> identity
f = MadgwickFilter()
dt = 0.01
for _ in range(100):
    f.update((0.0, 0.0, 9.81), (0.0, 0.0, 0.0), dt)
assert abs(f.q[0] - 1.0) < 1e-6, f.q
print(f"[1] Stationary upright: q = {f.q} (expected ~identity)")

# 2) Constant yaw rate of 1 rad/s for 1s -> ~57.3 deg yaw
f2 = MadgwickFilter()
for _ in range(100):
    f2.update((0.0, 0.0, 9.81), (0.0, 0.0, 1.0), 0.01)
from app.orientation import _quat_to_euler
roll, pitch, yaw = _quat_to_euler(f2.q)
assert abs(yaw - 57.296) < 0.1, yaw
print(f"[2] Yaw rate integration: yaw = {yaw:.2f} deg (expected ~57.3)")

# 3) 45 deg mount offset, chassis level -> filter reports chassis as level
est = OrientationEstimator(mount_offset_euler_deg=(45.0, 0.0, 0.0))
a = math.radians(45)
gx = 0.0
gy = -math.sin(a) * 9.81
gz = math.cos(a) * 9.81
for _ in range(500):
    est.on_state((gx, gy, gz), (0.0, 0.0, 0.0))
    est.tick()
ori = est.maybe_emit()
assert isinstance(ori, OriCmd)
assert abs(ori.roll) < 1.0, f"roll={ori.roll}"
assert abs(ori.pitch) < 1.0, f"pitch={ori.pitch}"
print(f"[3] 45 deg sensor mount, chassis level: roll={ori.roll:.3f} pitch={ori.pitch:.3f} yaw={ori.yaw:.3f}")

# 4) Emit rate limit: ~10 Hz
est2 = OrientationEstimator(emit_interval_s=0.1)
est2.on_state((0, 0, 9.81), (0, 0, 0))
t0 = time.monotonic()
emits = 0
while time.monotonic() - t0 < 0.5:
    if est2.maybe_emit() is not None:
        emits += 1
    time.sleep(0.005)
assert 3 <= emits <= 7, emits
print(f"[4] Emit rate: {emits} emits in 0.5s (expected ~5, ±2)")

# 5) OriCmd round-trips through serialize/deserialize
cmd = OriCmd(roll=1.2, pitch=-3.4, yaw=90.0, qw=0.99, qx=0.01, qy=-0.03, qz=0.0, ready=1)
text = cmd.serialize()
roundtrip = OriCmd.deserialize(text)
assert roundtrip == cmd
print(f"[5] OriCmd round-trips: {text}")

print("All orientation tests passed.")
