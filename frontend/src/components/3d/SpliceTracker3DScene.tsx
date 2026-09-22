import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

export interface ComponentDetail {
  id: string;
  name: string;
  category: 'PHYSICAL' | 'SENSING' | 'EDGE' | 'AI_ANALYTICS' | 'NETWORK';
  status: 'NORMAL' | 'WARNING' | 'CRITICAL' | 'OFFLINE';
  model: string;
  samplingRate: string;
  specs: Record<string, string>;
  description: string;
  telemetry: Record<string, string | number>;
}

export interface SpliceTracker3DSceneProps {
  onSelectComponent?: (comp: ComponentDetail | null) => void;
  selectedComponentId?: string | null;
  activeStatus?: 'NORMAL' | 'WARNING' | 'CRITICAL';
  beltRunning?: boolean;
  beltSpeed?: number;
  showDataFlow?: boolean;
  showAiOverlay?: boolean;
  cameraPreset?: 'overview' | 'inspection' | 'splice' | 'edge' | 'topdown';
  activeSpliceName?: string;
}

export default function SpliceTracker3DScene({
  onSelectComponent,
  selectedComponentId,
  activeStatus = 'NORMAL',
  beltRunning = true,
  beltSpeed = 3.5,
  showDataFlow = true,
  showAiOverlay = true,
  cameraPreset = 'overview',
  activeSpliceName = 'Splice-001',
}: SpliceTracker3DSceneProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const animFrameId = useRef<number>(0);

  // References for dynamic animated objects
  const beltMaterialsRef = useRef<THREE.MeshStandardMaterial[]>([]);
  const dataParticlesRef = useRef<THREE.Points | null>(null);
  const particlePositionsRef = useRef<Float32Array | null>(null);
  const particleProgressRef = useRef<Float32Array | null>(null);
  const particlePathsRef = useRef<{ start: THREE.Vector3; ctrl: THREE.Vector3; end: THREE.Vector3 }[]>([]);
  const vibrationRingRef = useRef<THREE.Mesh | null>(null);
  const ultrasonicRingsRef = useRef<THREE.Mesh[]>([]);
  const thermalConeRef = useRef<THREE.Mesh | null>(null);
  const visionFrustumRef = useRef<THREE.Mesh | null>(null);
  const edgeLedMeshRef = useRef<THREE.Mesh | null>(null);
  const interactiveMeshesRef = useRef<Map<THREE.Object3D, ComponentDetail>>(new Map());

  // Handle Camera Presets
  const applyCameraPreset = useCallback((preset: string) => {
    if (!cameraRef.current || !controlsRef.current) return;
    const cam = cameraRef.current;
    const ctrl = controlsRef.current;

    switch (preset) {
      case 'inspection':
        cam.position.set(0, 4.5, 7.5);
        ctrl.target.set(0, 1.8, 0);
        break;
      case 'splice':
        cam.position.set(1.5, 2.8, 3.2);
        ctrl.target.set(0.5, 1.6, 0);
        break;
      case 'edge':
        cam.position.set(4.8, 2.5, 5.0);
        ctrl.target.set(3.2, 1.5, 2.2);
        break;
      case 'topdown':
        cam.position.set(0, 16.0, 0.1);
        ctrl.target.set(0, 0, 0);
        break;
      case 'overview':
      default:
        cam.position.set(14.0, 9.5, 13.5);
        ctrl.target.set(0, 1.5, 0);
        break;
    }
    ctrl.update();
  }, []);

  useEffect(() => {
    applyCameraPreset(cameraPreset);
  }, [cameraPreset, applyCameraPreset]);

  // Main Three.js Scene Setup
  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 500;

    // 1. Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;
    scene.background = new THREE.Color(0x0a0e17);
    scene.fog = new THREE.FogExp2(0x0a0e17, 0.022);

    // 2. Camera
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(14.0, 9.5, 13.5);
    cameraRef.current = camera;

    // 3. Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    rendererRef.current = renderer;
    container.appendChild(renderer.domElement);

    // 4. Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 - 0.03; // Don't go underground
    controls.minDistance = 2.0;
    controls.maxDistance = 35.0;
    controls.target.set(0, 1.5, 0);
    controlsRef.current = controls;

    // 5. Lighting
    const ambientLight = new THREE.AmbientLight(0x1e293b, 1.4);
    scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0xffffff, 2.2);
    sunLight.position.set(12, 18, 10);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 2048;
    sunLight.shadow.mapSize.height = 2048;
    sunLight.shadow.camera.near = 0.5;
    sunLight.shadow.camera.far = 40;
    sunLight.shadow.camera.left = -15;
    sunLight.shadow.camera.right = 15;
    sunLight.shadow.camera.top = 15;
    sunLight.shadow.camera.bottom = -15;
    sunLight.shadow.bias = -0.0005;
    scene.add(sunLight);

    const fillLight = new THREE.DirectionalLight(0x38bdf8, 0.9);
    fillLight.position.set(-12, 8, -10);
    scene.add(fillLight);

    // Gantry inspection light (cyan spotlight)
    const inspectionSpot = new THREE.SpotLight(0x38bdf8, 4.5, 12, Math.PI / 5, 0.4, 1.2);
    inspectionSpot.position.set(0, 4.2, 0);
    inspectionSpot.target.position.set(0, 1.6, 0);
    scene.add(inspectionSpot);
    scene.add(inspectionSpot.target);

    // 6. Ground & Tech Grid
    const floorGeo = new THREE.PlaneGeometry(50, 50);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      roughness: 0.85,
      metalness: 0.2,
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.01;
    floor.receiveShadow = true;
    scene.add(floor);

    const grid = new THREE.GridHelper(40, 40, 0x1e3a8a, 0x1e293b);
    grid.position.y = 0.0;
    scene.add(grid);

    // Tech circular boundary ring around inspection station
    const ringGeo = new THREE.RingGeometry(3.8, 4.0, 64);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0x0284c7, transparent: true, opacity: 0.4, side: THREE.DoubleSide });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(0, 0.01, 0);
    scene.add(ring);

    // -------------------------------------------------------------------------
    // 7. Conveyor Physical Structure
    // -------------------------------------------------------------------------
    const conveyorLength = 22.0;
    const beltWidth = 2.2;
    const deckHeight = 1.6;

    // Materials
    const steelMat = new THREE.MeshStandardMaterial({
      color: 0x334155,
      roughness: 0.35,
      metalness: 0.8,
    });
    const paintYellowMat = new THREE.MeshStandardMaterial({
      color: 0xeab308,
      roughness: 0.4,
      metalness: 0.4,
    });
    const rubberMat = new THREE.MeshStandardMaterial({
      color: 0x18181b,
      roughness: 0.88,
      metalness: 0.05,
    });
    beltMaterialsRef.current = [rubberMat];

    const pulleyMat = new THREE.MeshStandardMaterial({
      color: 0x64748b,
      roughness: 0.25,
      metalness: 0.9,
    });

    // Structural truss rails (left and right)
    [-beltWidth / 2 - 0.25, beltWidth / 2 + 0.25].forEach((zPos) => {
      const beamGeo = new THREE.BoxGeometry(conveyorLength, 0.18, 0.12);
      const beam = new THREE.Mesh(beamGeo, steelMat);
      beam.position.set(0, deckHeight, zPos);
      beam.castShadow = true;
      beam.receiveShadow = true;
      scene.add(beam);

      const lowerBeam = new THREE.Mesh(beamGeo, steelMat);
      lowerBeam.position.set(0, deckHeight - 0.9, zPos);
      lowerBeam.castShadow = true;
      scene.add(lowerBeam);

      // Vertical structural legs every 3.5 meters
      for (let x = -conveyorLength / 2 + 1; x <= conveyorLength / 2 - 1; x += 3.6) {
        const legGeo = new THREE.BoxGeometry(0.14, deckHeight, 0.14);
        const leg = new THREE.Mesh(legGeo, steelMat);
        leg.position.set(x, deckHeight / 2, zPos);
        leg.castShadow = true;
        scene.add(leg);

        // Base foot pad
        const footGeo = new THREE.BoxGeometry(0.35, 0.05, 0.35);
        const foot = new THREE.Mesh(footGeo, steelMat);
        foot.position.set(x, 0.025, zPos);
        scene.add(foot);
      }
    });

    // Cross-ties and catwalk grating
    for (let x = -conveyorLength / 2 + 1; x <= conveyorLength / 2 - 1; x += 1.8) {
      const crossTieGeo = new THREE.BoxGeometry(0.1, 0.1, beltWidth + 0.6);
      const crossTie = new THREE.Mesh(crossTieGeo, steelMat);
      crossTie.position.set(x, deckHeight - 0.05, 0);
      scene.add(crossTie);
    }

    // Pulleys: Head Drive Pulley (x = +conveyorLength/2) and Tail Tension Pulley (x = -conveyorLength/2)
    const pulleyRadius = 0.55;
    const headPulleyGeo = new THREE.CylinderGeometry(pulleyRadius, pulleyRadius, beltWidth + 0.2, 36);
    const headPulley = new THREE.Mesh(headPulleyGeo, pulleyMat);
    headPulley.rotation.x = Math.PI / 2;
    headPulley.position.set(conveyorLength / 2, deckHeight - 0.3, 0);
    headPulley.castShadow = true;
    scene.add(headPulley);

    // Drive Motor & Gearbox assembly at Head Pulley
    const motorGroup = new THREE.Group();
    motorGroup.position.set(conveyorLength / 2 + 0.1, deckHeight - 0.3, beltWidth / 2 + 0.6);

    const motorBodyGeo = new THREE.CylinderGeometry(0.38, 0.38, 0.8, 24);
    const motorBody = new THREE.Mesh(motorBodyGeo, paintYellowMat);
    motorBody.rotation.z = Math.PI / 2;
    motorBody.castShadow = true;
    motorGroup.add(motorBody);

    const gearBoxGeo = new THREE.BoxGeometry(0.6, 0.7, 0.5);
    const gearBox = new THREE.Mesh(gearBoxGeo, steelMat);
    gearBox.position.set(-0.35, 0, 0);
    gearBox.castShadow = true;
    motorGroup.add(motorBox(gearBoxGeo, steelMat));

    scene.add(motorGroup);

    function motorBox(g: THREE.BufferGeometry, m: THREE.Material) {
      const mesh = new THREE.Mesh(g, m);
      mesh.position.set(-0.35, 0, 0);
      return mesh;
    }

    // Tail Pulley (Take-up frame)
    const tailPulley = new THREE.Mesh(headPulleyGeo, pulleyMat);
    tailPulley.rotation.x = Math.PI / 2;
    tailPulley.position.set(-conveyorLength / 2, deckHeight - 0.3, 0);
    tailPulley.castShadow = true;
    scene.add(tailPulley);

    // Idler sets (troughing idlers on top strand, flat return idlers below)
    for (let x = -conveyorLength / 2 + 1.2; x <= conveyorLength / 2 - 1.2; x += 1.6) {
      // Center horizontal idler roll
      const centerIdlerGeo = new THREE.CylinderGeometry(0.1, 0.1, beltWidth * 0.45, 16);
      const centerIdler = new THREE.Mesh(centerIdlerGeo, steelMat);
      centerIdler.rotation.x = Math.PI / 2;
      centerIdler.position.set(x, deckHeight + 0.05, 0);
      centerIdler.castShadow = true;
      scene.add(centerIdler);

      // Wing idler rolls (angled 30 degrees for troughed belt shape)
      [-1, 1].forEach((side) => {
        const wingGeo = new THREE.CylinderGeometry(0.09, 0.09, beltWidth * 0.35, 16);
        const wing = new THREE.Mesh(wingGeo, steelMat);
        wing.position.set(x, deckHeight + 0.16, side * (beltWidth * 0.32));
        wing.rotation.x = side * (Math.PI / 2 - 0.52);
        wing.castShadow = true;
        scene.add(wing);
      });

      // Bottom return flat idler
      if (Math.abs(x % 3.2) < 0.5) {
        const returnIdlerGeo = new THREE.CylinderGeometry(0.08, 0.08, beltWidth, 16);
        const returnIdler = new THREE.Mesh(returnIdlerGeo, steelMat);
        returnIdler.rotation.x = Math.PI / 2;
        returnIdler.position.set(x, deckHeight - 0.75, 0);
        returnIdler.castShadow = true;
        scene.add(returnIdler);
      }
    }

    // Continuous Conveyor Belt Surface (Top Strand + Bottom Strand + Curves)
    const beltTopGeo = new THREE.PlaneGeometry(conveyorLength, beltWidth, 64, 8);
    const beltTop = new THREE.Mesh(beltTopGeo, rubberMat);
    beltTop.rotation.x = -Math.PI / 2;
    beltTop.position.set(0, deckHeight + 0.17, 0);
    beltTop.receiveShadow = true;
    scene.add(beltTop);

    const beltBottomGeo = new THREE.PlaneGeometry(conveyorLength, beltWidth, 32, 4);
    const beltBottom = new THREE.Mesh(beltBottomGeo, rubberMat);
    beltBottom.rotation.x = Math.PI / 2;
    beltBottom.position.set(0, deckHeight - 0.85, 0);
    scene.add(beltBottom);

    // -------------------------------------------------------------------------
    // 8. Visual Belt Splice Joint (The Focal Point)
    // -------------------------------------------------------------------------
    const spliceGroup = new THREE.Group();
    spliceGroup.position.set(0.6, deckHeight + 0.18, 0);

    // Splice seam: distinct vulcanized step joint
    const spliceBaseGeo = new THREE.PlaneGeometry(1.6, beltWidth, 16, 8);
    const spliceMat = new THREE.MeshStandardMaterial({
      color: 0x27272a,
      roughness: 0.7,
      metalness: 0.15,
    });
    const spliceMesh = new THREE.Mesh(spliceBaseGeo, spliceMat);
    spliceMesh.rotation.x = -Math.PI / 2;
    spliceGroup.add(spliceMesh);

    // Finger / bias step splice seam line
    const seamGeo = new THREE.BoxGeometry(0.06, 0.02, beltWidth - 0.1);
    const seamMat = new THREE.MeshStandardMaterial({
      color: activeStatus === 'CRITICAL' ? 0xef4444 : activeStatus === 'WARNING' ? 0xf59e0b : 0x0284c7,
      emissive: activeStatus === 'CRITICAL' ? 0xb91c1c : activeStatus === 'WARNING' ? 0xd97706 : 0x0369a1,
      emissiveIntensity: 0.6,
      roughness: 0.3,
    });
    const seam = new THREE.Mesh(seamGeo, seamMat);
    seam.position.set(0, 0.01, 0);
    spliceGroup.add(seam);

    // Reinforcement cord simulation markers (longitudinal lines)
    for (let z = -beltWidth / 2 + 0.2; z <= beltWidth / 2 - 0.2; z += 0.35) {
      const cordGeo = new THREE.BoxGeometry(1.4, 0.012, 0.02);
      const cordMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.9, roughness: 0.2 });
      const cord = new THREE.Mesh(cordGeo, cordMat);
      cord.position.set(0, 0.012, z);
      spliceGroup.add(cord);
    }

    // If active status is warning/critical, add visible thermal hotspot or separation
    if (activeStatus !== 'NORMAL') {
      const defectGlowGeo = new THREE.SphereGeometry(0.35, 16, 16);
      defectGlowGeo.scale(1.2, 0.15, 0.6);
      const defectMat = new THREE.MeshBasicMaterial({
        color: activeStatus === 'CRITICAL' ? 0xef4444 : 0xf59e0b,
        transparent: true,
        opacity: 0.7,
      });
      const defectGlow = new THREE.Mesh(defectGlowGeo, defectMat);
      defectGlow.position.set(0.1, 0.02, 0.2);
      spliceGroup.add(defectGlow);
    }

    scene.add(spliceGroup);

    // Register Splice in interactive list
    const spliceDetail: ComponentDetail = {
      id: 'splice-joint',
      name: `${activeSpliceName} (Monitored Joint)`,
      category: 'PHYSICAL',
      status: activeStatus,
      model: 'ST-5400 Steel-Cord Vulcanized Step Joint',
      samplingRate: '100% full-width coverage',
      specs: {
        'Joint Type': 'Bias Step Vulcanized Finger Joint',
        'Cord Diameter': '8.2 mm High-Tensile Steel',
        'Carcass Rating': 'ST-3500 N/mm',
        'Joint Length': '1600 mm',
        'Cover Rubber': 'Grade X Abrasion Resistant (12+6 mm)',
        'Position': 'Zone Station (0.0 m offset)',
      },
      description: 'Primary structural joint connecting conveyor belt loops. Subject to continuous dynamic bending strain, cord tension, and thermal friction.',
      telemetry: {
        'Structural Severity': activeStatus === 'CRITICAL' ? '0.92 (CRITICAL)' : activeStatus === 'WARNING' ? '0.58 (ELEVATED)' : '0.04 (NOMINAL)',
        'Deformation Strain': activeStatus === 'CRITICAL' ? '4.8 mm/m' : '0.3 mm/m',
        'Cord Discontinuity': activeStatus === 'CRITICAL' ? 'CORD 7 SEVERED' : 'ALL 42 CORDS INTACT',
        'Thermal Delta': activeStatus === 'CRITICAL' ? '+24.6 °C HOTSPOT' : '+1.2 °C BASELINE',
      },
    };
    interactiveMeshesRef.current.set(spliceMesh, spliceDetail);

    // -------------------------------------------------------------------------
    // 9. Inspection Gantry & Multi-Modal Sensing Layer
    // -------------------------------------------------------------------------
    const gantryGroup = new THREE.Group();
    gantryGroup.position.set(0, 0, 0);

    // Arch Frame (Heavy steel box beam portal)
    const gantryMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.3,
      metalness: 0.85,
    });
    const gantryLegHeight = 4.2;
    const gantrySpan = beltWidth + 1.6;

    [-gantrySpan / 2, gantrySpan / 2].forEach((zPos) => {
      const columnGeo = new THREE.BoxGeometry(0.24, gantryLegHeight, 0.24);
      const column = new THREE.Mesh(columnGeo, gantryMat);
      column.position.set(0, gantryLegHeight / 2, zPos);
      column.castShadow = true;
      gantryGroup.add(column);
    });

    const headerBeamGeo = new THREE.BoxGeometry(0.3, 0.28, gantrySpan + 0.24);
    const headerBeam = new THREE.Mesh(headerBeamGeo, gantryMat);
    headerBeam.position.set(0, gantryLegHeight, 0);
    headerBeam.castShadow = true;
    gantryGroup.add(headerBeam);

    // Under-belt cross mounting bridge for ultrasonic & magnetic sensors
    const underBeamGeo = new THREE.BoxGeometry(0.22, 0.18, gantrySpan);
    const underBeam = new THREE.Mesh(underBeamGeo, gantryMat);
    underBeam.position.set(0, deckHeight - 0.45, 0);
    gantryGroup.add(underBeam);

    scene.add(gantryGroup);

    // SENSOR 1: RGB Industrial Line-Scan Camera
    const cameraHousingGeo = new THREE.BoxGeometry(0.42, 0.32, 0.32);
    const cameraBodyMat = new THREE.MeshStandardMaterial({ color: 0x0f766e, metalness: 0.9, roughness: 0.2 });
    const cameraMesh = new THREE.Mesh(cameraHousingGeo, cameraBodyMat);
    cameraMesh.position.set(0, gantryLegHeight - 0.4, 0);
    cameraMesh.castShadow = true;
    scene.add(cameraMesh);

    // Camera Lens Barrel
    const lensGeo = new THREE.CylinderGeometry(0.09, 0.09, 0.2, 24);
    const lensMat = new THREE.MeshStandardMaterial({ color: 0x0284c7, metalness: 0.95, roughness: 0.1 });
    const lens = new THREE.Mesh(lensGeo, lensMat);
    lens.position.set(0, gantryLegHeight - 0.6, 0);
    scene.add(lens);

    // Illumination Light Bar
    const lightBarGeo = new THREE.BoxGeometry(0.12, 0.08, beltWidth + 0.2);
    const lightBarMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, emissive: 0xe2e8f0, emissiveIntensity: 0.8 });
    const lightBar = new THREE.Mesh(lightBarGeo, lightBarMat);
    lightBar.position.set(0.18, gantryLegHeight - 0.45, 0);
    scene.add(lightBar);

    // Volumetric Vision Scan Frustum (translucent light sheet)
    const frustumGeo = new THREE.ConeGeometry(beltWidth * 0.65, gantryLegHeight - (deckHeight + 0.18), 4, 1, true);
    frustumGeo.rotateY(Math.PI / 4);
    const frustumMat = new THREE.MeshBasicMaterial({
      color: 0x06b6d4,
      transparent: true,
      opacity: 0.18,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const visionFrustum = new THREE.Mesh(frustumGeo, frustumMat);
    visionFrustum.position.set(0, (gantryLegHeight + deckHeight) / 2 - 0.1, 0);
    visionFrustumRef.current = visionFrustum;
    scene.add(visionFrustum);

    const cameraDetail: ComponentDetail = {
      id: 'sensor-rgb-camera',
      name: 'High-Speed RGB Line-Scan Camera',
      category: 'SENSING',
      status: 'NORMAL',
      model: 'SpliceTracker OptiScan 8K-GigE',
      samplingRate: '8192 px @ 48 kHz line-rate',
      specs: {
        'Resolution': '8192 × 1 pixels',
        'Interface': 'GigE Vision Dual-Port (2 Gbps)',
        'Illumination': 'Coaxial High-Power Pulsed LED Array',
        'Dynamic Range': '72 dB HDR',
        'Spatial Pitch': '0.35 mm/px @ 4.2 m/s belt speed',
      },
      description: 'Continuous optical surface inspection for transverse cuts, edge gouging, splice separation, and surface delamination.',
      telemetry: {
        'Frame Rate': '48,000 lines/sec',
        'Image Anomaly Score': activeStatus === 'CRITICAL' ? 0.94 : 0.03,
        'Optical Flow Stability': '99.4%',
        'Operating Temp': '36.8 °C',
      },
    };
    interactiveMeshesRef.current.set(cameraMesh, cameraDetail);

    // SENSOR 2: LWIR Radiometric Thermal Camera
    const thermalHousingGeo = new THREE.BoxGeometry(0.3, 0.26, 0.28);
    const thermalMat = new THREE.MeshStandardMaterial({ color: 0xb45309, metalness: 0.85, roughness: 0.25 });
    const thermalMesh = new THREE.Mesh(thermalHousingGeo, thermalMat);
    thermalMesh.position.set(0, gantryLegHeight - 0.4, 0.7);
    thermalMesh.castShadow = true;
    scene.add(thermalMesh);

    // Germanium lens
    const germLensGeo = new THREE.CylinderGeometry(0.07, 0.07, 0.12, 20);
    const germLensMat = new THREE.MeshStandardMaterial({ color: 0xd97706, metalness: 0.9, roughness: 0.1 });
    const germLens = new THREE.Mesh(germLensGeo, germLensMat);
    germLens.position.set(0, gantryLegHeight - 0.52, 0.7);
    scene.add(germLens);

    // Thermal scan cone
    const thermConeGeo = new THREE.ConeGeometry(0.9, gantryLegHeight - (deckHeight + 0.18), 16, 1, true);
    const thermConeMat = new THREE.MeshBasicMaterial({
      color: 0xf59e0b,
      transparent: true,
      opacity: 0.14,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const thermCone = new THREE.Mesh(thermConeGeo, thermConeMat);
    thermCone.position.set(0, (gantryLegHeight + deckHeight) / 2 - 0.1, 0.7);
    thermalConeRef.current = thermCone;
    scene.add(thermCone);

    const thermalDetail: ComponentDetail = {
      id: 'sensor-thermal-ir',
      name: 'LWIR Radiometric Thermal Sensor',
      category: 'SENSING',
      status: activeStatus === 'CRITICAL' ? 'CRITICAL' : 'NORMAL',
      model: 'ThermoGuard TG-640 Pro',
      samplingRate: '60 Hz radiometric stream',
      specs: {
        'Spectral Range': '7.5 – 14.0 μm (LWIR)',
        'Thermal Sensitivity (NETD)': '< 30 mK',
        'Resolution': '640 × 512 focal plane array',
        'Lens': '19 mm f/1.0 Anti-Reflective Germanium',
        'Measurement Range': '-20 °C to +180 °C',
      },
      description: 'Detects internal friction hotspots, defective steel-cord vulcanization bonding, and bearing heat transfer across the joint.',
      telemetry: {
        'Current Peak': activeStatus === 'CRITICAL' ? '68.4 °C (HOTSPOT)' : '35.8 °C (NORMAL)',
        'Baseline Ambient': '34.2 °C',
        'Delta T': activeStatus === 'CRITICAL' ? '+34.2 °C' : '+1.6 °C',
        'Gradient Rate': '0.12 °C/min',
      },
    };
    interactiveMeshesRef.current.set(thermalMesh, thermalDetail);

    // SENSOR 3: Ultrasonic / Transducer Core Inspection Array (Mounted under belt)
    const ultrasonicBarGeo = new THREE.BoxGeometry(0.3, 0.16, beltWidth + 0.1);
    const ultrasonicMat = new THREE.MeshStandardMaterial({ color: 0x6d28d9, metalness: 0.9, roughness: 0.2 });
    const ultrasonicMesh = new THREE.Mesh(ultrasonicBarGeo, ultrasonicMat);
    ultrasonicMesh.position.set(0, deckHeight - 0.28, 0);
    ultrasonicMesh.castShadow = true;
    scene.add(ultrasonicMesh);

    // Concentric Sonar Pulse Rings
    const rings: THREE.Mesh[] = [];
    for (let i = 0; i < 3; i++) {
      const sonarRingGeo = new THREE.RingGeometry(0.2 + i * 0.35, 0.25 + i * 0.35, 32);
      const sonarRingMat = new THREE.MeshBasicMaterial({
        color: 0x8b5cf6,
        transparent: true,
        opacity: 0.4 - i * 0.1,
        side: THREE.DoubleSide,
      });
      const sonarRing = new THREE.Mesh(sonarRingGeo, sonarRingMat);
      sonarRing.rotation.x = -Math.PI / 2;
      sonarRing.position.set(0, deckHeight - 0.1, 0);
      scene.add(sonarRing);
      rings.push(sonarRing);
    }
    ultrasonicRingsRef.current = rings;

    const ultrasonicDetail: ComponentDetail = {
      id: 'sensor-ultrasonic',
      name: 'High-Frequency Ultrasonic Core Transducer Array',
      category: 'SENSING',
      status: activeStatus === 'CRITICAL' ? 'CRITICAL' : 'NORMAL',
      model: 'SonicScan Array-16 Multi-Element',
      samplingRate: '5.0 MHz Acoustic Echo Pulser',
      specs: {
        'Element Count': '16 Piezo-Composite Transducers',
        'Center Frequency': '5.0 MHz',
        'Penetration Depth': 'Up to 45 mm rubber/steel composite',
        'Coupling Method': 'Non-contact acoustic air/roller bridge',
        'Defect Resolution': '1.2 mm internal void / cord debond',
      },
      description: 'Penetrates through the bottom rubber layer into the core to evaluate cord adhesion, core porosity, and subterranean layer separation.',
      telemetry: {
        'Core Adhesion Index': activeStatus === 'CRITICAL' ? '42% (DELAMINATED)' : '98.5% (OPTIMAL)',
        'Echo Amplitude': '48.2 dB',
        'Cord Debond Length': activeStatus === 'CRITICAL' ? '120 mm detected' : '0.0 mm',
        'Transducer Health': 'ALL 16 CHANNELS ONLINE',
      },
    };
    interactiveMeshesRef.current.set(ultrasonicMesh, ultrasonicDetail);

    // SENSOR 4: Tri-Axial Vibration Accelerometer
    const accelGeo = new THREE.CylinderGeometry(0.08, 0.08, 0.14, 16);
    const accelMat = new THREE.MeshStandardMaterial({ color: 0x059669, metalness: 0.9, roughness: 0.2 });
    const accelMesh = new THREE.Mesh(accelGeo, accelMat);
    accelMesh.position.set(conveyorLength / 2, deckHeight + 0.1, beltWidth / 2 + 0.35);
    accelMesh.castShadow = true;
    scene.add(accelMesh);

    // Vibration wave indicator
    const vibRingGeo = new THREE.TorusGeometry(0.22, 0.02, 16, 32);
    const vibRingMat = new THREE.MeshBasicMaterial({ color: 0x10b981, transparent: true, opacity: 0.6 });
    const vibRing = new THREE.Mesh(vibRingGeo, vibRingMat);
    vibRing.rotation.x = Math.PI / 2;
    vibRing.position.copy(accelMesh.position);
    vibrationRingRef.current = vibRing;
    scene.add(vibRing);

    const accelDetail: ComponentDetail = {
      id: 'sensor-vibration',
      name: 'Tri-Axial MEMS Vibration Accelerometer',
      category: 'SENSING',
      status: 'NORMAL',
      model: 'VibeTrack Tri-900 High-G',
      samplingRate: '10 kHz Continuous Synchronous',
      specs: {
        'Measurement Axes': 'X, Y, Z (Tri-Axial)',
        'Dynamic Range': '±50 g peak',
        'Frequency Band': '0.5 Hz – 5,000 Hz',
        'Output Data': 'RMS, Peak-to-Peak, Kurtosis, FFT Spectrum',
      },
      description: 'Monitors structural mechanical shockwaves generated when the splice passes over idlers and head pulleys.',
      telemetry: {
        'Current RMS': '1.24 g (NOMINAL)',
        'Peak Shock': '3.42 g',
        'FFT 1X Fundamental': '15.4 Hz',
        'Bearing Kurtosis': '2.8 (NORMAL)',
      },
    };
    interactiveMeshesRef.current.set(accelMesh, accelDetail);

    // SENSOR 5: Conductive Loop Inductive Sensor
    const loopAntennaGeo = new THREE.TorusGeometry(0.35, 0.03, 16, 32);
    const loopMat = new THREE.MeshStandardMaterial({ color: 0x10b981, metalness: 0.95, roughness: 0.15 });
    const loopMesh = new THREE.Mesh(loopAntennaGeo, loopMat);
    loopMesh.rotation.x = -Math.PI / 2;
    loopMesh.position.set(0.8, deckHeight - 0.2, 0);
    scene.add(loopMesh);

    const loopDetail: ComponentDetail = {
      id: 'sensor-conductive',
      name: 'Embedded Conductive Loop RF Receiver',
      category: 'SENSING',
      status: activeStatus === 'CRITICAL' ? 'CRITICAL' : 'NORMAL',
      model: 'MagnaLoop SpliceIntegrity-X',
      samplingRate: '100 kHz continuous induction',
      specs: {
        'Technology': 'High-Q Inductive Resonance Loop Interrogation',
        'Coil Frequency': '125 kHz RFID / Magnetic Coupling',
        'Response Speed': '< 2 milliseconds',
        'Loop Status': activeStatus === 'CRITICAL' ? 'LOOP OPEN / SEVERED' : 'CONTINUOUS CLOSED LOOP',
      },
      description: 'Passively monitors vulcanized steel continuity loops embedded inside the splice joint to instantly register rip or joint separation.',
      telemetry: {
        'Loop Continuity': activeStatus === 'CRITICAL' ? 'DISCONTINUOUS (FAIL)' : 'CONTINUOUS (PASS)',
        'Loop Resistance': activeStatus === 'CRITICAL' ? '> 10 MOhm' : '4.2 Ohm',
        'Transition Time': '142 ms',
      },
    };
    interactiveMeshesRef.current.set(loopMesh, loopDetail);

    // -------------------------------------------------------------------------
    // 10. Edge Computing Enclosure ("SpliceTracker EDGE")
    // -------------------------------------------------------------------------
    const edgeGroup = new THREE.Group();
    edgeGroup.position.set(3.6, deckHeight, beltWidth / 2 + 1.2);

    // Enclosure mounting stand
    const standGeo = new THREE.CylinderGeometry(0.08, 0.08, deckHeight, 16);
    const stand = new THREE.Mesh(standGeo, steelMat);
    stand.position.set(0, -deckHeight / 2, 0);
    stand.castShadow = true;
    edgeGroup.add(stand);

    // NEMA 4X Aluminum Enclosure Box
    const encGeo = new THREE.BoxGeometry(1.1, 1.4, 0.55);
    const encMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.25,
      metalness: 0.9,
    });
    const edgeBox = new THREE.Mesh(encGeo, encMat);
    edgeBox.castShadow = true;
    edgeGroup.add(edgeBox);

    // Heat Sink Fins on top/side
    for (let f = -0.4; f <= 0.4; f += 0.08) {
      const finGeo = new THREE.BoxGeometry(0.9, 0.03, 0.12);
      const fin = new THREE.Mesh(finGeo, steelMat);
      fin.position.set(0, 0.72, f);
      edgeGroup.add(fin);
    }

    // Industrial Brass Cable Glands at bottom
    [-0.3, -0.1, 0.1, 0.3].forEach((gx) => {
      const glandGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.14, 16);
      const glandMat = new THREE.MeshStandardMaterial({ color: 0xd97706, metalness: 0.95, roughness: 0.2 });
      const gland = new THREE.Mesh(glandGeo, glandMat);
      gland.position.set(gx, -0.74, 0);
      edgeGroup.add(gland);
    });

    // Conduit Pipe running from Edge Box to Gantry
    const conduitCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(3.6, deckHeight - 0.75, beltWidth / 2 + 1.2),
      new THREE.Vector3(2.2, deckHeight - 0.6, beltWidth / 2 + 0.8),
      new THREE.Vector3(0.4, deckHeight - 0.4, beltWidth / 2 + 0.8),
      new THREE.Vector3(0, deckHeight - 0.4, beltWidth / 2 + 0.5),
    ]);
    const conduitGeo = new THREE.TubeGeometry(conduitCurve, 24, 0.045, 12, false);
    const conduitMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.8, roughness: 0.3 });
    const conduit = new THREE.Mesh(conduitGeo, conduitMat);
    scene.add(conduit);

    // Front Status LED Indicators
    const ledGeo = new THREE.SphereGeometry(0.04, 16, 16);
    const ledColors = [0x10b981, 0x06b6d4, 0xf59e0b, 0x10b981];
    ledColors.forEach((col, idx) => {
      const ledMat = new THREE.MeshBasicMaterial({ color: col });
      const led = new THREE.Mesh(ledGeo, ledMat);
      led.position.set(-0.35 + idx * 0.22, 0.45, 0.29);
      edgeGroup.add(led);
      if (idx === 1) edgeLedMeshRef.current = led;
    });

    // Industrial Technical Stencil Decal (Canvas Texture)
    const labelCanvas = document.createElement('canvas');
    labelCanvas.width = 512;
    labelCanvas.height = 256;
    const ctx = labelCanvas.getContext('2d');
    if (ctx) {
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(0, 0, 512, 256);
      ctx.fillStyle = '#38bdf8';
      ctx.font = 'bold 36px monospace';
      ctx.fillText('SPLICETRACKER EDGE', 30, 70);
      ctx.fillStyle = '#94a3b8';
      ctx.font = '22px monospace';
      ctx.fillText('AI INFERENCE & DAQ UNIT', 30, 110);
      ctx.fillStyle = '#10b981';
      ctx.font = 'bold 20px monospace';
      ctx.fillText('STATUS: ONLINE // LATENCY: 14ms', 30, 160);
      ctx.fillStyle = '#64748b';
      ctx.font = '16px monospace';
      ctx.fillText('ARM64 GPU ACCELERATED // IP67', 30, 205);
    }
    const labelTex = new THREE.CanvasTexture(labelCanvas);
    const labelGeo = new THREE.PlaneGeometry(0.85, 0.45);
    const labelMat = new THREE.MeshBasicMaterial({ map: labelTex });
    const labelMesh = new THREE.Mesh(labelGeo, labelMat);
    labelMesh.position.set(0, -0.05, 0.285);
    edgeGroup.add(labelMesh);

    scene.add(edgeGroup);

    const edgeDetail: ComponentDetail = {
      id: 'edge-processing-unit',
      name: 'SpliceTracker Edge Computing & DAQ Enclosure',
      category: 'EDGE',
      status: 'NORMAL',
      model: 'ST-EDGE Industrial AI Workstation NEMA-4X',
      samplingRate: '100% Real-time Synchronous Ingestion',
      specs: {
        'Compute Core': 'NVIDIA Jetson Orin Industrial 64GB (275 TOPS)',
        'Data Acquisition': '16-Ch 24-Bit Synchronous A/D DAQ (PCIe)',
        'Vision Interface': 'Dual 10-GigE Optical Transceivers',
        'Enclosure Rating': 'IP67 / NEMA 4X Cast Aluminum',
        'Operating Range': '-40 °C to +75 °C Passive Convection',
        'Uplink': 'Industrial Dual-SIM 5G + Fiber Optic Gateway',
      },
      description: 'Edge computing appliance performing real-time multi-sensor ingestion, frame feature extraction, Farnebäck optical flow, sensor fusion, DIVE event grouping, and ATCE temporal correlation with sub-20ms latency.',
      telemetry: {
        'Inference Latency': '14.2 ms / frame',
        'GPU Utilization': '68%',
        'RAM Usage': '18.4 / 64 GB',
        'Core Temperature': '48.6 °C',
        'Pipeline Throughput': '48,000 sensor frames/min',
      },
    };
    interactiveMeshesRef.current.set(edgeBox, edgeDetail);

    // -------------------------------------------------------------------------
    // 11. Animated Data Flow Particle Stream
    // -------------------------------------------------------------------------
    const particleCount = 200;
    const pPositions = new Float32Array(particleCount * 3);
    const pProgress = new Float32Array(particleCount);
    const pPaths = [
      // Vision to Edge
      { start: new THREE.Vector3(0, gantryLegHeight - 0.4, 0), ctrl: new THREE.Vector3(1.5, gantryLegHeight - 0.8, 1.2), end: new THREE.Vector3(3.6, deckHeight, beltWidth / 2 + 1.2) },
      // Thermal to Edge
      { start: new THREE.Vector3(0, gantryLegHeight - 0.4, 0.7), ctrl: new THREE.Vector3(1.8, gantryLegHeight - 0.9, 1.5), end: new THREE.Vector3(3.6, deckHeight, beltWidth / 2 + 1.2) },
      // Ultrasonic to Edge
      { start: new THREE.Vector3(0, deckHeight - 0.28, 0), ctrl: new THREE.Vector3(1.5, deckHeight - 0.5, 0.9), end: new THREE.Vector3(3.6, deckHeight, beltWidth / 2 + 1.2) },
      // Vibration to Edge
      { start: new THREE.Vector3(conveyorLength / 2, deckHeight + 0.1, beltWidth / 2 + 0.35), ctrl: new THREE.Vector3(7.0, deckHeight + 0.3, beltWidth / 2 + 0.8), end: new THREE.Vector3(3.6, deckHeight, beltWidth / 2 + 1.2) },
      // Edge to Cloud / Dashboard (Skyward arch)
      { start: new THREE.Vector3(3.6, deckHeight + 0.7, beltWidth / 2 + 1.2), ctrl: new THREE.Vector3(6.0, 6.5, beltWidth / 2 + 2.5), end: new THREE.Vector3(8.5, 9.0, 6.0) },
    ];
    particlePathsRef.current = pPaths;

    for (let i = 0; i < particleCount; i++) {
      pProgress[i] = Math.random();
      pPositions[i * 3] = 0;
      pPositions[i * 3 + 1] = 0;
      pPositions[i * 3 + 2] = 0;
    }

    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
    const pMat = new THREE.PointsMaterial({
      color: 0x38bdf8,
      size: 0.18,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
    });
    const pSystem = new THREE.Points(pGeo, pMat);
    dataParticlesRef.current = pSystem;
    particlePositionsRef.current = pPositions;
    particleProgressRef.current = pProgress;
    scene.add(pSystem);

    // -------------------------------------------------------------------------
    // 12. Floating Holographic AI/Analytics Nodes (when showAiOverlay=true)
    // -------------------------------------------------------------------------
    const aiNodesGroup = new THREE.Group();
    const aiCallouts = [
      { text: 'DEFECT DETECTION // OPTICAL FLOW', pos: [0, 5.2, -1.8], color: '#38bdf8' },
      { text: 'THERMAL GRADIENT ANALYSIS', pos: [0, 5.2, 1.8], color: '#f59e0b' },
      { text: 'SENSOR FUSION & DIVE ENGINE', pos: [3.6, 3.4, 2.6], color: '#10b981' },
      { text: 'ATCE TEMPORAL DIGITAL TWIN', pos: [-3.2, 3.2, -1.8], color: '#8b5cf6' },
    ];

    aiCallouts.forEach((c) => {
      const cCanvas = document.createElement('canvas');
      cCanvas.width = 384;
      cCanvas.height = 96;
      const cCtx = cCanvas.getContext('2d');
      if (cCtx) {
        cCtx.fillStyle = 'rgba(15, 23, 42, 0.85)';
        cCtx.roundRect(4, 4, 376, 88, 12);
        cCtx.fill();
        cCtx.strokeStyle = c.color;
        cCtx.lineWidth = 4;
        cCtx.stroke();
        cCtx.fillStyle = c.color;
        cCtx.font = 'bold 20px monospace';
        cCtx.fillText(c.text, 20, 54);
      }
      const cTex = new THREE.CanvasTexture(cCanvas);
      const cGeo = new THREE.PlaneGeometry(1.8, 0.45);
      const cMat = new THREE.MeshBasicMaterial({ map: cTex, transparent: true, side: THREE.DoubleSide });
      const cMesh = new THREE.Mesh(cGeo, cMat);
      cMesh.position.set(c.pos[0], c.pos[1], c.pos[2]);
      aiNodesGroup.add(cMesh);

      // Connecting leader line to gantry or edge
      const lineGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(c.pos[0], c.pos[1] - 0.25, c.pos[2]),
        new THREE.Vector3(c.pos[0] * 0.5, c.pos[1] - 1.2, c.pos[2] * 0.5),
      ]);
      const lineMat = new THREE.LineBasicMaterial({ color: new THREE.Color(c.color), transparent: true, opacity: 0.5 });
      const line = new THREE.Line(lineGeo, lineMat);
      aiNodesGroup.add(line);
    });
    scene.add(aiNodesGroup);

    // -------------------------------------------------------------------------
    // 13. Interactive Raycaster (Clicking objects)
    // -------------------------------------------------------------------------
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const handleClick = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const interactiveList = Array.from(interactiveMeshesRef.current.keys());
      const intersects = raycaster.intersectObjects(interactiveList, true);

      if (intersects.length > 0) {
        let hitObj: THREE.Object3D | null = intersects[0].object;
        while (hitObj && !interactiveMeshesRef.current.has(hitObj)) {
          hitObj = hitObj.parent;
        }
        if (hitObj && interactiveMeshesRef.current.has(hitObj)) {
          const detail = interactiveMeshesRef.current.get(hitObj) || null;
          onSelectComponent?.(detail);
        }
      }
    };

    container.addEventListener('click', handleClick);

    // -------------------------------------------------------------------------
    // 14. Animation Render Loop
    // -------------------------------------------------------------------------
    let clock = new THREE.Clock();

    const animate = () => {
      animFrameId.current = requestAnimationFrame(animate);
      const delta = clock.getDelta();
      const time = clock.getElapsedTime();

      // Conveyor Motion Animation
      if (beltRunning) {
        beltMaterialsRef.current.forEach((mat) => {
          if (mat.map) {
            mat.map.offset.x = (mat.map.offset.x + (beltSpeed * 0.05 * delta)) % 1;
          }
        });
      }

      // Ultrasonic Sonar Expanding Pulse Rings
      ultrasonicRingsRef.current.forEach((ring, idx) => {
        const scale = 1.0 + ((time * 1.5 + idx * 0.5) % 2.0);
        ring.scale.set(scale, scale, scale);
        const mat = ring.material as THREE.MeshBasicMaterial;
        mat.opacity = Math.max(0, 0.45 * (1.0 - (scale - 1.0) / 2.0));
      });

      // Vibration Ring dynamic pulse
      if (vibrationRingRef.current) {
        const vibScale = 1.0 + Math.sin(time * 12.0) * 0.15;
        vibrationRingRef.current.scale.set(vibScale, vibScale, 1.0);
      }

      // Vision scan frustum subtle breathing
      if (visionFrustumRef.current) {
        const fMat = visionFrustumRef.current.material as THREE.MeshBasicMaterial;
        fMat.opacity = 0.16 + Math.sin(time * 4.0) * 0.05;
      }

      // Edge AI LED pulse
      if (edgeLedMeshRef.current) {
        const ledMat = edgeLedMeshRef.current.material as THREE.MeshBasicMaterial;
        ledMat.color.setHSL(0.55, 1.0, 0.4 + Math.sin(time * 6.0) * 0.2);
      }

      // Data Flow Particles animation along bezier paths
      if (showDataFlow && particlePositionsRef.current && particleProgressRef.current && dataParticlesRef.current) {
        const positions = particlePositionsRef.current;
        const progress = particleProgressRef.current;
        const paths = particlePathsRef.current;

        for (let i = 0; i < particleCount; i++) {
          progress[i] = (progress[i] + delta * 0.35) % 1.0;
          const p = progress[i];
          const path = paths[i % paths.length];

          // Quadratic Bezier interpolation: B(t) = (1-t)^2*P0 + 2(1-t)t*P1 + t^2*P2
          const inv = 1.0 - p;
          const x = inv * inv * path.start.x + 2 * inv * p * path.ctrl.x + p * p * path.end.x;
          const y = inv * inv * path.start.y + 2 * inv * p * path.ctrl.y + p * p * path.end.y;
          const z = inv * inv * path.start.z + 2 * inv * p * path.ctrl.z + p * p * path.end.z;

          positions[i * 3] = x;
          positions[i * 3 + 1] = y;
          positions[i * 3 + 2] = z;
        }
        dataParticlesRef.current.geometry.attributes.position.needsUpdate = true;
      }

      controls.update();
      renderer.render(scene, camera);
    };

    animate();

    // Resize Handler
    const handleResize = () => {
      if (!container || !camera || !renderer) return;
      const newW = container.clientWidth;
      const newH = container.clientHeight;
      camera.aspect = newW / newH;
      camera.updateProjectionMatrix();
      renderer.setSize(newW, newH);
    };
    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      container.removeEventListener('click', handleClick);
      cancelAnimationFrame(animFrameId.current);
      renderer.dispose();
      if (renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [activeStatus, beltRunning, beltSpeed, showDataFlow, showAiOverlay, onSelectComponent, activeSpliceName]);

  return (
    <div className="relative w-full h-full select-none overflow-hidden rounded-xl border border-slate-700 bg-slate-950">
      <div ref={mountRef} className="w-full h-full cursor-grab active:cursor-grabbing" />
      
      {/* 3D Scene Compass / HUD Watermark */}
      <div className="absolute top-3 left-3 pointer-events-none flex items-center gap-2 text-xs text-slate-400 font-mono bg-slate-900/80 px-2.5 py-1 rounded border border-slate-800 backdrop-blur-sm">
        <div className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
        <span>SPLICETRACKER 3D DIGITAL TWIN // LIVE ENGINE</span>
      </div>
    </div>
  );
}
