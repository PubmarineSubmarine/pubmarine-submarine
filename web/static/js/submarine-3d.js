/**
 * Submarine 3D Visualization Module
 * Renders a 3D submarine model using Three.js and updates orientation based on gyro data
 */

class Submarine3D {
    constructor(containerId, modelPath) {
        this.containerId = containerId;
        this.modelPath = modelPath;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.submarine = null;
        this.animationFrameId = null;

        // Gyro data (roll, pitch, yaw in degrees)
        this.gyro = { x: 0, y: 0, z: 0 };

        // Target rotation for smooth interpolation
        this.targetRotation = { x: 0, y: 0, z: 0 };

        // Smoothing factor (0-1, lower = smoother but more lag)
        this.smoothing = .01;

        this.init();
    }

    init() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`Container ${this.containerId} not found`);
            return;
        }

        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a1929);

        // Camera setup
        const width = container.clientWidth;
        const height = container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
        this.camera.position.set(0, 2, 6);
        this.camera.lookAt(0, -1, 0);

        // Renderer setup
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        container.appendChild(this.renderer.domElement);

        // Lighting
        this.setupLighting();

        // Load submarine model
        this.loadModel();

        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize());

        // Start render loop
        this.animate();
    }

    setupLighting() {
        // Ambient light for overall illumination
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);

        // Directional light from top
        const topLight = new THREE.DirectionalLight(0xffffff, 0.8);
        topLight.position.set(0, 10, 0);
        this.scene.add(topLight);

        // Front light
        const frontLight = new THREE.DirectionalLight(0xffffff, 0.5);
        frontLight.position.set(0, 0, 10);
        this.scene.add(frontLight);

        // Rim light for better definition
        const rimLight = new THREE.DirectionalLight(0x4488ff, 0.3);
        rimLight.position.set(-5, 2, -5);
        this.scene.add(rimLight);
    }

    loadModel() {
        // Get the MTL file path from the OBJ path
        const mtlPath = this.modelPath.replace('.obj', '.mtl');
        const basePath = this.modelPath.substring(0, this.modelPath.lastIndexOf('/') + 1);

        // Load materials first
        const mtlLoader = new MTLLoader();
        mtlLoader.setPath(basePath);

        mtlLoader.load(
            mtlPath.substring(mtlPath.lastIndexOf('/') + 1),
            (materials) => {
                materials.preload();

                // Fix and convert materials
                Object.keys(materials.materials).forEach(key => {
                    const mat = materials.materials[key];

                    console.log(`Material ${key} before:`, mat.color.getHex());

                    // The issue is that MTLLoader might be reading Kd values incorrectly
                    // Let's manually set the correct colors from the MTL spec
                    // The Kd line specifies diffuse color (R G B)

                    // Map the materials to their correct colors from the MTL file
                    const colorMap = {
                        'Material.003': new THREE.Color(0.517334, 0.494389, 0.012800), // Yellow
                        'Material.004': new THREE.Color(0.517334, 0.494389, 0.012800), // Yellow
                        'Material.006': new THREE.Color(0.517334, 0.494389, 0.012800), // Yellow
                        'Material.010': new THREE.Color(0.343772, 0.800000, 0.212815), // Green
                        'Material.015': new THREE.Color(0.800000, 0.028684, 0.010701), // Red
                        'Material.016': new THREE.Color(0.800000, 0.108524, 0.265348), // Pink
                        'bread': new THREE.Color(0.800000, 0.212443, 0.010012)  // Orange/Brown
                    };

                    if (colorMap[key]) {
                        mat.color.copy(colorMap[key]);
                        console.log(`Material ${key} after:`, mat.color.getHex());
                    }
                });

                // Now load the OBJ with materials
                const objLoader = new OBJLoader();
                objLoader.setMaterials(materials);

                objLoader.load(
                    this.modelPath,
                    (object) => {
                        // Center the model
                        const box = new THREE.Box3().setFromObject(object);
                        const center = box.getCenter(new THREE.Vector3());
                        object.position.sub(center);

                        // Scale the model to fit the view (2x larger)
                        const size = box.getSize(new THREE.Vector3());
                        const maxDim = Math.max(size.x, size.y, size.z);
                        const scale = 4 / maxDim;
                        object.scale.set(scale, scale, scale);

                        this.submarine = object;
                        this.scene.add(object);

                        console.log('Submarine model loaded successfully with materials');
                    },
                    (xhr) => {
                        console.log('OBJ: ' + (xhr.loaded / xhr.total * 100) + '% loaded');
                    },
                    (error) => {
                        console.error('Error loading submarine OBJ:', error);
                    }
                );
            },
            (xhr) => {
                console.log('MTL: ' + (xhr.loaded / xhr.total * 100) + '% loaded');
            },
            (error) => {
                console.error('Error loading materials, loading OBJ without materials:', error);
                // Fallback: load OBJ without materials
                this.loadModelWithoutMaterials();
            }
        );
    }

    loadModelWithoutMaterials() {
        const loader = new OBJLoader();

        loader.load(
            this.modelPath,
            (object) => {
                // Center the model
                const box = new THREE.Box3().setFromObject(object);
                const center = box.getCenter(new THREE.Vector3());
                object.position.sub(center);

                // Scale the model to fit the view (2x larger)
                const size = box.getSize(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);
                const scale = 4 / maxDim;
                object.scale.set(scale, scale, scale);

                // Apply default material
                object.traverse((child) => {
                    if (child instanceof THREE.Mesh) {
                        child.material = new THREE.MeshStandardMaterial({
                            color: 0xffd700,
                            metalness: 0.7,
                            roughness: 0.3,
                            flatShading: false
                        });
                    }
                });

                this.submarine = object;
                this.scene.add(object);

                console.log('Submarine model loaded successfully (no materials)');
            },
            (xhr) => {
                console.log((xhr.loaded / xhr.total * 100) + '% loaded');
            },
            (error) => {
                console.error('Error loading submarine model:', error);
            }
        );
    }

    /**
     * Update submarine orientation from gyro data
     * @param {Object} gyro - Gyro data with x (roll), y (pitch), z (yaw)
     */
    updateOrientation(gyro) {
        if (!this.submarine) return;

        this.gyro = gyro;

        // Convert degrees to radians and store as target
        this.targetRotation.x = THREE.MathUtils.degToRad(gyro.y); // pitch
        this.targetRotation.y = THREE.MathUtils.degToRad(gyro.z); // yaw
        this.targetRotation.z = THREE.MathUtils.degToRad(gyro.x); // roll
    }

    animate() {
        this.animationFrameId = requestAnimationFrame(() => this.animate());

        // Smoothly interpolate rotation
        if (this.submarine) {
            this.submarine.rotation.x += (this.targetRotation.x - this.submarine.rotation.x) * this.smoothing;
            this.submarine.rotation.y += (this.targetRotation.y - this.submarine.rotation.y) * this.smoothing;
            this.submarine.rotation.z += (this.targetRotation.z - this.submarine.rotation.z) * this.smoothing;
        }

        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }

    onWindowResize() {
        const container = document.getElementById(this.containerId);
        if (!container) return;

        const width = container.clientWidth;
        const height = container.clientHeight;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    destroy() {
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
        }

        if (this.renderer) {
            this.renderer.dispose();
            const container = document.getElementById(this.containerId);
            if (container && this.renderer.domElement) {
                container.removeChild(this.renderer.domElement);
            }
        }

        window.removeEventListener('resize', () => this.onWindowResize());
    }
}
