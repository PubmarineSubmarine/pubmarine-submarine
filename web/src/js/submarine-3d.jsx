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

export default function Submarine3D({ modelPath, gyro }) {
  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const submarineRef = useRef(null);
  const gridRef = useRef(null);
  const targetRotationRef = useRef({ x: 0, y: 0, z: 0 });
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
        const target = targetRotationRef.current;
        sub.rotation.x += (target.x - sub.rotation.x) * 0.01;
        sub.rotation.z += (target.z - sub.rotation.z) * 0.01;
      }

      if (gridRef.current) {
        const grid = gridRef.current;
        const target = targetRotationRef.current;
        grid.rotation.y += (target.y - grid.rotation.y) * 0.01;
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
    if (gyro) {
      targetRotationRef.current = {
        x: THREE.MathUtils.degToRad(gyro.y),
        y: THREE.MathUtils.degToRad(gyro.z),
        z: THREE.MathUtils.degToRad(gyro.x),
      };
    }
  }, [gyro]);

  return <div ref={containerRef} class="submarine-3d-container" />;
}
