import { useEffect, useRef } from "preact/hooks";
import * as THREE from "three";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { MTLLoader } from "three/examples/jsm/loaders/MTLLoader.js";

const COLOR_MAP = {
  "Material.003": new THREE.Color(0.517334, 0.494389, 0.0128),
  "Material.004": new THREE.Color(0.517334, 0.494389, 0.0128),
  "Material.006": new THREE.Color(0.517334, 0.494389, 0.0128),
  "Material.010": new THREE.Color(0.343772, 0.8, 0.212815),
  "Material.015": new THREE.Color(0.8, 0.028684, 0.010701),
  "Material.016": new THREE.Color(0.8, 0.108524, 0.265348),
  bread: new THREE.Color(0.8, 0.212443, 0.010012),
};

// Axis remap between the MPU-6050's body frame and three.js's coordinate
// frame. The Madgwick filter reports rotations as a quaternion in a body
// frame where +Z is "up" (opposite to gravity) and the ZYX Euler order
// is (yaw around Z, pitch around Y, roll around X).
//
// Rather than conjugate by a single static rotation (which can't exactly
// map a Z-up chassis frame to a Y-up three.js model without leaving a
// little cross-axis leakage), we decompose to ZYX Euler and apply each
// angle to a chosen model axis. This makes the axis mapping explicit and
// trivially tunable for different OBJ conventions.
//
// The defaults below assume a Y-up OBJ with the nose along +Z:
//   chassis roll (around X, lateral)   -> model Z (longitudinal)
//   chassis pitch (around Y, forward)  -> model X (lateral, right)
//   chassis yaw (around Z, up)         -> grid only (model stays put)
//
// If the OBJ is authored differently, change MODEL_ROLL_AXIS or
// MODEL_PITCH_AXIS below.
const MODEL_ROLL_AXIS = new THREE.Vector3(0, 0, 1);
const MODEL_PITCH_AXIS = new THREE.Vector3(1, 0, 0);

// Take the filter's chassis-in-world quaternion, decompose to ZYX
// Euler, and return the model-space quaternion (yaw stripped) plus the
// chassis yaw (used to spin the grid).
function chassisOriToModel(ori) {
  const q = new THREE.Quaternion(ori.qx, ori.qy, ori.qz, ori.qw);
  const euler = new THREE.Euler().setFromQuaternion(q, "ZYX");
  const roll = euler.x;
  const pitch = euler.y;
  const yaw = euler.z;
  const qRoll = new THREE.Quaternion().setFromAxisAngle(MODEL_ROLL_AXIS, roll);
  const qPitch = new THREE.Quaternion().setFromAxisAngle(
    MODEL_PITCH_AXIS,
    pitch,
  );
  return {
    modelQuat: qRoll.multiply(qPitch),
    yaw,
  };
}

export default function Submarine3D({ modelPath, gyro, orientation }) {
  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const submarineRef = useRef(null);
  const gridRef = useRef(null);
  // The submarine model shows only roll + pitch (tilt); heading is
  // represented by the reference grid spinning under it.
  const targetModelQuatRef = useRef(new THREE.Quaternion());
  // The reference grid spins around world Y by the chassis's yaw, so
  // the world appears to rotate under the submarine as it turns.
  const targetGridQuatRef = useRef(new THREE.Quaternion());
  const animFrameRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = null;
    sceneRef.current = scene;

    const width = container.clientWidth;
    const height = container.clientHeight;
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 2.5, 6);
    camera.lookAt(0, -0.5, 0);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.sortObjects = true;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const topLight = new THREE.DirectionalLight(0xffffff, 0.8);
    topLight.position.set(0, 10, 0);
    scene.add(topLight);
    const frontLight = new THREE.DirectionalLight(0xffffff, 0.5);
    frontLight.position.set(0, 0, 10);
    scene.add(frontLight);
    const rimLight = new THREE.DirectionalLight(0x4488ff, 0.3);
    rimLight.position.set(-5, 2, -5);
    scene.add(rimLight);

    const gridHelper = new THREE.GridHelper(60, 60, 0x00ffff, 0x00ffff);
    gridHelper.material.transparent = true;
    gridHelper.material.opacity = 0.2;
    scene.add(gridHelper);
    gridRef.current = gridHelper;

    const basePath = modelPath.substring(0, modelPath.lastIndexOf("/") + 1);
    const mtlPath = modelPath.replace(".obj", ".mtl");
    const mtlFile = mtlPath.substring(mtlPath.lastIndexOf("/") + 1);

    const mtlLoader = new MTLLoader();
    mtlLoader.setPath(basePath);

    const loadObj = (materials) => {
      const objLoader = new OBJLoader();
      if (materials) objLoader.setMaterials(materials);

      objLoader.load(
        modelPath,
        (object) => {
          const box = new THREE.Box3().setFromObject(object);
          const scale =
            4 /
            Math.max(
              box.getSize(new THREE.Vector3()).x,
              box.getSize(new THREE.Vector3()).y,
              box.getSize(new THREE.Vector3()).z,
            );
          object.scale.set(scale, scale, scale);
          const scaledBox = new THREE.Box3().setFromObject(object);
          object.position.sub(scaledBox.getCenter(new THREE.Vector3()));

          if (!materials) {
            object.traverse((child) => {
              if (child instanceof THREE.Mesh) {
                child.material = new THREE.MeshStandardMaterial({
                  color: 0xffd700,
                  metalness: 0.7,
                  roughness: 0.3,
                });
              }
            });
          }

          submarineRef.current = object;
          scene.add(object);
        },
        undefined,
        () => {
          if (materials) {
            loadObj(null);
          }
        },
      );
    };

    mtlLoader.load(
      mtlFile,
      (materials) => {
        materials.preload();
        Object.entries(materials.materials).forEach(([key, mat]) => {
          if (COLOR_MAP[key]) mat.color.copy(COLOR_MAP[key]);
        });
        loadObj(materials);
      },
      undefined,
      () => loadObj(null),
    );

    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    const animate = () => {
      animFrameRef.current = requestAnimationFrame(animate);

      if (submarineRef.current) {
        const sub = submarineRef.current;
        sub.quaternion.slerp(targetModelQuatRef.current, 0.15);
      }

      if (gridRef.current) {
        const grid = gridRef.current;
        grid.quaternion.slerp(targetGridQuatRef.current, 0.15);
      }

      if (renderer && scene && camera) {
        renderer.render(scene, camera);
      }
    };
    animate();

    return () => {
      cancelAnimationFrame(animFrameRef.current);
      window.removeEventListener("resize", handleResize);
      if (renderer) {
        renderer.dispose();
        if (container && renderer.domElement) {
          container.removeChild(renderer.domElement);
        }
      }
    };
  }, [modelPath]);

  useEffect(() => {
    if (orientation && orientation.qw != null && orientation.ready) {
      // Absolute orientation from the Madgwick filter, remapped to the
      // model's axis convention.
      const { modelQuat, yaw } = chassisOriToModel(orientation);
      // Model: roll + pitch only; yaw is shown on the grid.
      targetModelQuatRef.current = modelQuat;
      // Grid: rotate around world Y by the chassis's yaw, negated for a
      // chase-cam feel: when the sub yaws left, the world appears to
      // spin right under it.
      targetGridQuatRef.current = new THREE.Quaternion().setFromAxisAngle(
        new THREE.Vector3(0, 1, 0),
        -yaw,
      );
    } else if (gyro) {
      // Fallback before the filter produces a sample: integrate raw
      // gyro as a chained rotation around the chassis's X, Y, Z axes.
      // This is angular velocity, not absolute angle, but keeps the
      // canvas from being frozen on first paint.
      const qx = new THREE.Quaternion().setFromAxisAngle(
        new THREE.Vector3(1, 0, 0),
        THREE.MathUtils.degToRad(gyro.x),
      );
      const qy = new THREE.Quaternion().setFromAxisAngle(
        new THREE.Vector3(0, 1, 0),
        THREE.MathUtils.degToRad(gyro.y),
      );
      const qz = new THREE.Quaternion().setFromAxisAngle(
        new THREE.Vector3(0, 0, 1),
        THREE.MathUtils.degToRad(gyro.z),
      );
      const composed = new THREE.Quaternion()
        .copy(qx)
        .multiply(qy)
        .multiply(qz);
      const { modelQuat, yaw } = chassisOriToModel({
        qw: composed.w,
        qx: composed.x,
        qy: composed.y,
        qz: composed.z,
      });
      targetModelQuatRef.current = modelQuat;
      targetGridQuatRef.current = new THREE.Quaternion().setFromAxisAngle(
        new THREE.Vector3(0, 1, 0),
        -yaw,
      );
    }
  }, [gyro, orientation]);

  return <div ref={containerRef} class="submarine-3d-container" />;
}
