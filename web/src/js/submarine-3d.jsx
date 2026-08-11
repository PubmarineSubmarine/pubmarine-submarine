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

// The Madgwick filter reports a chassis-in-world quaternion (ZYX Euler
// convention, Z up). We decompose to Euler and remap roll/pitch to
// model axes below; yaw goes to the grid (it would just spin the sub
// about its own axis otherwise). Tune MODEL_ROLL_AXIS / MODEL_PITCH_AXIS
// if the OBJ is authored differently.
const MODEL_ROLL_AXIS = new THREE.Vector3(0, 0, -1);
const MODEL_PITCH_AXIS = new THREE.Vector3(-1, 0, 0);

function chassisOriToModel(qw, qx, qy, qz) {
  const q = new THREE.Quaternion(qx, qy, qz, qw);
  const euler = new THREE.Euler().setFromQuaternion(q, "ZYX");
  const qRoll = new THREE.Quaternion().setFromAxisAngle(MODEL_ROLL_AXIS, euler.x);
  const qPitch = new THREE.Quaternion().setFromAxisAngle(MODEL_PITCH_AXIS, euler.y);
  return {
    modelQuat: qRoll.multiply(qPitch),
    yaw: euler.z,
  };
}

export default function Submarine3D({ modelPath, orientation }) {
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
    if (!orientation || orientation.qw == null || !orientation.ready) return;
    const { modelQuat, yaw } = chassisOriToModel(
      orientation.qw,
      orientation.qx,
      orientation.qy,
      orientation.qz,
    );
    // Model: roll + pitch only. Grid: rotate around world Y by chassis
    // yaw (negated for a chase-cam feel — yawing left makes the world
    // appear to spin right under the sub).
    targetModelQuatRef.current = modelQuat;
    targetGridQuatRef.current = new THREE.Quaternion().setFromAxisAngle(
      new THREE.Vector3(0, 1, 0),
      -yaw,
    );
  }, [orientation]);

  return <div ref={containerRef} class="submarine-3d-container" />;
}
