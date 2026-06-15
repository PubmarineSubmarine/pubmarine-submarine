from __future__ import annotations

import math
import time
from dataclasses import dataclass
from math import asin, atan2, cos, sin, sqrt
from typing import Optional, Tuple

import numpy as np

from protocol import OriCmd

# --- Mounting offset -----------------------------------------------------------
#
# The MPU-6050 is not mounted flat in the chassis. Apply a constant rotation
# to bring sensor-frame readings into the chassis frame. Tune these three
# angles (roll, pitch, yaw in degrees) to match the physical install.
MOUNT_OFFSET_EULER_DEG = (0.0, 0.0, 0.0)
# --- Home / "level" offset ----------------------------------------------------
#
# The chassis rarely sits in a "level + heading-zero" pose on the bench. After
# the sensor-to-chassis mount offset is applied, this offset is applied to the
# filter's chassis-in-world quaternion to define the *user* frame. The ORI
# message is reported in the user frame, so setting this to the inverse of
# the current chassis orientation is equivalent to a zero calibration.
#
# You can either set this constant or send ``CAL`` from the console at runtime
# to capture the current pose as the new home. Runtime calibration overrides
# whatever is hardcoded here.
HOME_OFFSET_EULER_DEG = (0.0, 0.0, 0.0)

# Higher = faster convergence to gravity but more noise during motion.
MADGWICK_BETA: float = 0.1

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


@dataclass
class MadgwickFilter:
    """Stateful Madgwick AHRS filter.

    The ``update`` method should be called with every (accel, gyro) sample. The
    filter integrates the gyroscope and corrects toward the gravity vector
    estimated by the accelerometer. ``dt`` is the time delta since the previous
    sample in seconds.
    """

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

    Call ``on_state`` from the serial callback whenever a ``StateCmd`` arrives
    with ``acc``/``gyro`` populated, then call ``tick`` periodically (the
    plumbing class does this on a 100 ms timer).
    """

    def __init__(
        self,
        mount_offset_euler_deg: Tuple[float, float, float] = MOUNT_OFFSET_EULER_DEG,
        home_offset_euler_deg: Tuple[float, float, float] = HOME_OFFSET_EULER_DEG,
        beta: float = MADGWICK_BETA,
        emit_interval_s: float = 0.1,
    ) -> None:
        self._offset_q = _euler_to_quat(*mount_offset_euler_deg)
        # Pre-compute its inverse (conjugate of a unit quaternion).
        self._offset_q_inv = self._offset_q.copy()
        self._offset_q_inv[1:] = -self._offset_q_inv[1:]
        # The "home" pose: chassis-in-world quaternion that the user wants
        # to call zero. The ORI message is reported relative to this.
        self._home_offset_q = _euler_to_quat(*home_offset_euler_deg)
        self._home_offset_q_inv = self._home_offset_q.copy()
        self._home_offset_q_inv[1:] = -self._home_offset_q_inv[1:]
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

    def _rotate_sensor_to_chassis(
        self,
        accel: Tuple[float, float, float],
        gyro: Tuple[float, float, float],
    ) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Apply the static mount offset to accel and gyro vectors.

        The MPU-6050's body frame is rotated relative to the chassis by
        ``self._offset_q``. We rotate the measured vectors by the *inverse*
        offset to express them in the chassis frame before feeding them to the
        filter.
        """
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
        self._filter.update(self._pending_accel, self._pending_gyro, dt)
        self._last_sample_ts = now
        self._has_pending = False

    def calibrate(self) -> bool:
        """Capture the current chassis-in-world orientation as the new home.

        After this call, the ORI message will read (0, 0, 0) until the chassis
        moves relative to the pose it was in at calibration time. Returns
        ``False`` if the filter has not yet produced a valid estimate.
        """
        if not self._filter.ready:
            return False
        self._home_offset_q = self._filter.q.copy()
        self._home_offset_q_inv = self._home_offset_q.copy()
        self._home_offset_q_inv[1:] = -self._home_offset_q_inv[1:]
        return True

    def get_debug_info(self) -> dict:
        """Return a snapshot of the estimator state for logging/diagnostics."""
        info: dict = {
            "raw_accel": self._last_accel,
            "raw_gyro": self._last_gyro,
            "filter_ready": self._filter.ready,
        }
        if self._filter.ready:
            r, p, y = _quat_to_euler(self._filter.q)
            info["chassis_euler"] = (r, p, y)
            info["chassis_quat"] = tuple(float(x) for x in self._filter.q)
            # Compute the gravity vector the filter *predicts* in the body
            # frame, given its current orientation. If the filter is well
            # aligned with the accelerometer, ``accel_residual`` is small.
            q = self._filter.q
            w, x, yi, z = q
            # R[:, 2] extracts the third column of the rotation matrix,
            # which is the world +Z axis expressed in the body frame. Since
            # the accel measures -gravity (i.e., +Z in world), the
            # predicted normalized accel is R[:, 2].
            pred_x = 2.0 * (x * z + w * yi)
            pred_y = 2.0 * (yi * z - w * x)
            pred_z = 1.0 - 2.0 * (x * x + yi * yi)
            an = sqrt(
                self._last_accel[0] ** 2
                + self._last_accel[1] ** 2
                + self._last_accel[2] ** 2
            )
            if an > 1e-8:
                mx, my, mz = (
                    self._last_accel[0] / an,
                    self._last_accel[1] / an,
                    self._last_accel[2] / an,
                )
            else:
                mx = my = mz = 0.0
            info["accel_predicted"] = (pred_x, pred_y, pred_z)
            info["accel_residual"] = (
                pred_x - mx,
                pred_y - my,
                pred_z - mz,
            )
            # Direct tilt from the raw accelerometer (no filter): atan2 of
            # the horizontal component over the vertical. Independent of
            # any filter state, so the user can compare it against
            # ``chassis_euler`` to see if the filter is tracking gravity.
            info["accel_tilt_deg"] = (
                math.degrees(math.atan2(mx, mz)),
                math.degrees(math.atan2(my, mz)),
            )
        hr, hp, hy = _quat_to_euler(self._home_offset_q)
        info["home_euler"] = (hr, hp, hy)
        info["home_quat"] = tuple(float(x) for x in self._home_offset_q)
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
