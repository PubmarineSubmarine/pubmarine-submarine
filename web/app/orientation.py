from __future__ import annotations

import math
import time
from dataclasses import dataclass
from math import asin, atan2, cos, sin, sqrt
from typing import Optional, Tuple

import numpy as np

from app.protocol import OriCmd

# Tune these three angles (roll, pitch, yaw in degrees) to match the physical install of the MPU-6050
#MOUNT_OFFSET_EULER_DEG = (0.0, -90.0, 0.0)
MOUNT_OFFSET_EULER_DEG = (0.0, 0.0, 0.0)

# Higher = faster convergence to gravity but more noise during motion.
MADGWICK_BETA: float = 0.1

# Exponential moving average applied to the *emitted* orientation quaternion
# (slerp from the previous emit toward the new target). Range (0, 1]:
#   1.0 -> no smoothing, no added latency (current behavior)
#   0.8 -> time constant ~ 0.45 s at the default 10 Hz emit rate
#   0.5 -> time constant ~ 0.14 s
# Applied to quaternions (not Euler) so it's well-defined near gimbal-lock.
ORI_LPF_ALPHA: float = 0.8

INVALID_SENTINEL: float = -1.0


def _euler_to_quat(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    """ZYX intrinsic Euler angles (degrees) -> quaternion (w, x, y, z)."""
    r = math.radians(roll_deg)
    p = math.radians(pitch_deg)
    y = math.radians(yaw_deg)

    cr, sr = cos(r / 2), sin(r / 2)
    cp, sp = cos(p / 2), sin(p / 2)
    cy, sy = cos(y / 2), sin(y / 2)

    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return np.array([w, x, y, z], dtype=np.float64)


def _quat_to_euler(q: np.ndarray) -> Tuple[float, float, float]:
    """Quaternion -> ZYX intrinsic Euler angles (degrees)."""
    w, x, y, z = q

    # roll (x-axis rotation)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = atan2(sinr_cosp, cosr_cosp)

    # pitch (y-axis rotation)
    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1.0:
        pitch = math.copysign(math.pi / 2, sinp)
    else:
        pitch = asin(sinp)

    # yaw (z-axis rotation)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = atan2(siny_cosp, cosy_cosp)

    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)


def _quat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Hamilton product of two (w, x, y, z) quaternions."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return np.array(
        [
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        ],
        dtype=np.float64,
    )


def _normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n == 0.0:
        return v
    return v / n


def _slerp(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    """Spherical linear interpolation between unit quaternions a and b.

    ``t`` is the interpolation parameter (0 -> a, 1 -> b). Shortest-path
    is used (flips the sign of b if the dot product is negative).
    """
    dot = float(np.dot(a, b))
    if dot < 0.0:
        b = -b
        dot = -dot
    # If the inputs are nearly parallel, fall back to normalized lerp to
    # avoid a divide-by-near-zero in the slerp formula.
    if dot > 0.9995:
        out = a + t * (b - a)
    else:
        theta_0 = math.acos(max(-1.0, min(1.0, dot)))
        sin_theta_0 = math.sin(theta_0)
        theta = theta_0 * t
        s0 = math.cos(theta) - dot * math.sin(theta) / sin_theta_0
        s1 = math.sin(theta) / sin_theta_0
        out = s0 * a + s1 * b
    return _normalize(out)


@dataclass
class MadgwickFilter:
    beta: float = MADGWICK_BETA
    q: np.ndarray = None  # type: ignore[assignment]
    ready: bool = False

    def __post_init__(self) -> None:
        if self.q is None:
            self.q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)

    def reset(self) -> None:
        self.q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        self.ready = False

    def update(
        self,
        accel: Tuple[float, float, float],
        gyro: Tuple[float, float, float],
        dt: float,
    ) -> None:
        ax, ay, az = accel
        gx, gy, gz = gyro

        # Skip samples that look like firmware error sentinels.
        if (
            ax == INVALID_SENTINEL
            and ay == INVALID_SENTINEL
            and az == INVALID_SENTINEL
        ):
            return
        if gx == 0.0 and gy == 0.0 and gz == 0.0 and ax == 0.0 and ay == 0.0 and az == 0.0:
            return

        if dt <= 0.0 or not math.isfinite(dt):
            return

        q0, q1, q2, q3 = self.q

        # Rate of change from gyroscope (rad/s) in the body frame.
        gxrad = float(gx)
        gyrad = float(gy)
        gzrad = float(gz)

        qDot0 = 0.5 * (-q1 * gxrad - q2 * gyrad - q3 * gzrad)
        qDot1 = 0.5 * (q0 * gxrad + q2 * gzrad - q3 * gyrad)
        qDot2 = 0.5 * (q0 * gyrad - q1 * gzrad + q3 * gxrad)
        qDot3 = 0.5 * (q0 * gzrad + q1 * gyrad - q2 * gxrad)

        # Accelerometer-based correction toward gravity.
        anorm = sqrt(ax * ax + ay * ay + az * az)
        if anorm > 1e-8:
            axn, ayn, azn = ax / anorm, ay / anorm, az / anorm

            # Objective function: difference between estimated and measured
            # gravity direction in the body frame.
            f1 = 2.0 * (q1 * q3 - q0 * q2) - axn
            f2 = 2.0 * (q0 * q1 + q2 * q3) - ayn
            f3 = 2.0 * (0.5 - q1 * q1 - q2 * q2) - azn

            # Jacobian (J^T f).
            j41 = -2.0 * q2
            j42 = 2.0 * q3
            j43 = -2.0 * q0
            j44 = 2.0 * q1

            j51 = 2.0 * q1
            j52 = 2.0 * q0
            j53 = 2.0 * q3
            j54 = 2.0 * q2

            j61 = 0.0
            j62 = -4.0 * q1
            j63 = -4.0 * q2
            j64 = 0.0

            grad_w = j41 * f1 + j51 * f2 + j61 * f3
            grad_x = j42 * f1 + j52 * f2 + j62 * f3
            grad_y = j43 * f1 + j53 * f2 + j63 * f3
            grad_z = j44 * f1 + j54 * f2 + j64 * f3

            gnorm = sqrt(
                grad_w * grad_w
                + grad_x * grad_x
                + grad_y * grad_y
                + grad_z * grad_z
            )
            if gnorm > 1e-8:
                grad_w /= gnorm
                grad_x /= gnorm
                grad_y /= gnorm
                grad_z /= gnorm

            qDot0 -= self.beta * grad_w
            qDot1 -= self.beta * grad_x
            qDot2 -= self.beta * grad_y
            qDot3 -= self.beta * grad_z

        # Integrate.
        q0 += qDot0 * dt
        q1 += qDot1 * dt
        q2 += qDot2 * dt
        q3 += qDot3 * dt

        self.q = _normalize(np.array([q0, q1, q2, q3], dtype=np.float64))
        self.ready = True


class OrientationEstimator:
    """Run a Madgwick filter on incoming STAT data and produce ORI messages.

    The estimator:
      * applies a static mount offset to the raw MPU-6050 readings,
      * runs a Madgwick filter to get an absolute orientation in world frame,
      * emits a fresh ``OriCmd`` at most every 100 ms (10 Hz).
    """

    def __init__(
        self,
        mount_offset_euler_deg: Tuple[float, float, float] = MOUNT_OFFSET_EULER_DEG,
        beta: float = MADGWICK_BETA,
        emit_interval_s: float = 0.1,
        ori_lpf_alpha: float = ORI_LPF_ALPHA,
    ) -> None:
        self._offset_q = _euler_to_quat(*mount_offset_euler_deg)
        # Pre-compute its inverse (conjugate of a unit quaternion).
        self._offset_q_inv = self._offset_q.copy()
        self._offset_q_inv[1:] = -self._offset_q_inv[1:]
        self._home_offset_q = _euler_to_quat(0, 0, 0)
        self._home_offset_q_inv = self._home_offset_q.copy()
        self._home_offset_q_inv[1:] = -self._home_offset_q_inv[1:]
        # Last emitted orientation, used as the prior for the smoothing
        # EMA. Starts at identity so the first emit is a normal slerp
        # toward the first target.
        self._emit_q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        self._ori_lpf_alpha = float(ori_lpf_alpha)
        self._filter = MadgwickFilter(beta=beta)
        self._last_sample_ts: Optional[float] = None
        self._last_emit_ts: float = 0.0
        self._emit_interval_s = emit_interval_s
        # Most recent raw reading, used when the firmware timestamp isn't
        # available. We synthesize a dt from wall time.
        self._has_pending: bool = False
        self._pending_accel: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._pending_gyro: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        # Most recent reading that was actually fed to the filter, kept for
        # debug logging.
        self._last_accel: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._last_gyro: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        # Gyro bias, in chassis frame (post-mount-offset). Subtracted from
        # every gyro reading before it reaches the filter. Captured at
        # ``calibrate()`` time -- the user holds the sub still, runs CAL,
        # and whatever the gyro reads at that moment is treated as zero.
        self._gyro_bias: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    def _rotate_sensor_to_chassis(
        self,
        accel: Tuple[float, float, float],
        gyro: Tuple[float, float, float],
    ) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        a = np.array(accel, dtype=np.float64)
        g = np.array(gyro, dtype=np.float64)
        # Rotate by the offset quaternion using the standard v' = q v q^-1.
        # Represent the vector as a pure quaternion (0, v).
        def _rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
            vq = np.array([0.0, v[0], v[1], v[2]], dtype=np.float64)
            out = _quat_mul(_quat_mul(q, vq), self._offset_q_inv)
            return out[1:]

        a_rot = _rotate(self._offset_q, a)
        g_rot = _rotate(self._offset_q, g)
        return (
            (float(a_rot[0]), float(a_rot[1]), float(a_rot[2])),
            (float(g_rot[0]), float(g_rot[1]), float(g_rot[2])),
        )

    def reset(self) -> None:
        self._filter.reset()
        self._last_sample_ts = None
        self._has_pending = False
        self._home_offset_q = _euler_to_quat(0.0, 0.0, 0.0)
        self._home_offset_q_inv = self._home_offset_q.copy()
        self._home_offset_q_inv[1:] = -self._home_offset_q_inv[1:]
        self._emit_q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
        self._gyro_bias = (0.0, 0.0, 0.0)

    def on_state(self, accel, gyro) -> None:
        """Called whenever a fresh accel/gyro sample is available."""
        if accel is None or gyro is None:
            return
        if len(accel) != 3 or len(gyro) != 3:
            return
        accel_corrected, gyro_corrected = self._rotate_sensor_to_chassis(
            tuple(float(x) for x in accel),
            tuple(float(x) for x in gyro),
        )
        self._pending_accel = accel_corrected
        self._pending_gyro = gyro_corrected
        self._has_pending = True

    def tick(self) -> None:
        """Advance the filter with any pending sample, regardless of emit rate."""
        if not self._has_pending:
            return
        now = time.monotonic()
        if self._last_sample_ts is None:
            # First sample: just adopt a sensible dt (one tick).
            dt = 0.05
        else:
            dt = now - self._last_sample_ts
        # Clamp dt to a sane window so a long stall doesn't blow up the
        # integrator.
        if dt < 0.0:
            dt = 0.0
        if dt > 0.5:
            dt = 0.5
        self._last_accel = self._pending_accel
        self._last_gyro = self._pending_gyro
        # Apply the captured gyro bias. The bias is in chassis frame, which
        # is what ``_pending_gyro`` already is (it was rotated by the mount
        # offset in ``on_state``).
        bx, by, bz = self._gyro_bias
        gx, gy, gz = self._pending_gyro
        gyro_corrected = (gx - bx, gy - by, gz - bz)
        self._filter.update(self._pending_accel, gyro_corrected, dt)
        self._last_sample_ts = now
        self._has_pending = False

    def calibrate(self) -> bool:
        """Capture the current chassis-in-world orientation as the new home,
        and the current gyro reading as the new bias.

        After this call, the ORI message will read (0, 0, 0) until the
        chassis moves, and subsequent gyro readings will have the captured
        bias subtracted so the filter no longer drifts from a non-zero
        resting rate. The user should hold the sub perfectly still while
        sending ``CAL`` -- any actual rotation at calibration time will be
        captured as part of the "bias" and show up as a counter-rotation
        on the next real motion.

        Returns ``False`` if the filter has not yet produced a valid
        estimate.
        """
        if not self._filter.ready:
            return False
        self._home_offset_q = self._filter.q.copy()
        self._home_offset_q_inv = self._home_offset_q.copy()
        self._home_offset_q_inv[1:] = -self._home_offset_q_inv[1:]
        # Capture the gyro bias from the most recent chassis-frame reading.
        # Prefer the pending one (newer); fall back to the last integrated
        # sample if no pending is available.
        if self._has_pending:
            self._gyro_bias = self._pending_gyro
        else:
            self._gyro_bias = self._last_gyro
        return True

    def get_debug_info(self) -> dict:
        """Return a snapshot of the estimator state for logging/diagnostics."""
        info: dict = {
            "raw_accel": self._last_accel,
            "raw_gyro": self._last_gyro,
            "filter_ready": self._filter.ready,
            "gyro_bias": self._gyro_bias,
        }
        if self._filter.ready:
            r, p, y = _quat_to_euler(self._filter.q)
            info["chassis_euler"] = (r, p, y)
            # Direct tilt from the raw accelerometer (no filter). Compare
            # against ``chassis_euler`` to see if the filter is tracking
            # gravity correctly.
            ax, ay, az = self._last_accel
            an = sqrt(ax * ax + ay * ay + az * az)
            if an > 1e-8:
                axn = ax / an
                ayn = ay / an
                azn = az / an
                info["accel_tilt_deg"] = (
                    math.degrees(math.atan2(axn, azn)),
                    math.degrees(math.atan2(ayn, azn)),
                )
        return info

    def maybe_emit(self) -> OriCmd | None:
        self.tick()
        now = time.monotonic()
        if not self._filter.ready:
            return None
        if now - self._last_emit_ts < self._emit_interval_s:
            return None
        self._last_emit_ts = now

        # q_user = q_home^-1 * q_chassis_in_world
        q = _quat_mul(self._home_offset_q_inv, self._filter.q)
        q = _normalize(q)
        # Slerp from the previous emit toward this target to attenuate
        # residual high-frequency jitter. alpha == 1 reproduces the
        # original (unsmoothed) behavior exactly.
        q = _slerp(self._emit_q, q, self._ori_lpf_alpha)
        self._emit_q = q
        roll, pitch, yaw = _quat_to_euler(q)
        return OriCmd(
            roll=round(roll, 3),
            pitch=round(pitch, 3),
            yaw=round(yaw, 3),
            qw=round(float(q[0]), 6),
            qx=round(float(q[1]), 6),
            qy=round(float(q[2]), 6),
            qz=round(float(q[3]), 6),
            ready=1,
        )
