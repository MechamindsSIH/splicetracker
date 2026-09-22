import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Sparkles, Play, Pause, ScanLine, RotateCcw, Package } from 'lucide-react';

interface MiniConveyorSceneProps {
  height?: string | number;
  interactive?: boolean;
  activeAnomaly?: string | null;
  speed?: number;
  spliceName?: string;
  condition?: string;
  showControls?: boolean;
}

export default function MiniConveyorScene({
  height = '320px',
  interactive = true,
  activeAnomaly = null,
  speed = 1.0,
  spliceName = 'Splice-001',
  condition = 'GOOD',
  showControls = true,
}: MiniConveyorSceneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [cameraView, setCameraView] = useState<'iso' | 'gantry' | 'top'>('iso');
  const [particlesActive, setParticlesActive] = useState(true);
  const [isRunning, setIsRunning] = useState(true);
  const [scanPulse, setScanPulse] = useState(false);
  const [payloadVisible, setPayloadVisible] = useState(true);

  const sceneState = useRef<{
    renderer?: THREE.WebGLRenderer;
    scene?: THREE.Scene;
    camera?: THREE.PerspectiveCamera;
    beltMesh?: THREE.Mesh;
    spliceMesh?: THREE.Mesh;
    laserMesh?: THREE.Mesh;
    thermalCone?: THREE.Mesh;
    animFrameId?: number;
    particles?: THREE.Points;
    idlers?: THREE.Mesh[];
    payload?: THREE.Group;
    spherical?: { radius: number; theta: number; phi: number };
  }>({});

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 600;
    const h = typeof height === 'number' ? height : parseInt(String(height)) || 320;

    // Scene & Camera
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a); // Deep industrial slate
    scene.fog = new THREE.FogExp2(0x0f172a, 0.025);

    const camera = new THREE.PerspectiveCamera(45, width / h, 0.1, 100);
    camera.position.set(10, 7, 12);
    camera.lookAt(0, 1.2, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(width, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;

    container.replaceChildren(renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xecfdf5, 1.4);
    dirLight.position.set(12, 18, 10);
    dirLight.castShadow = true;
    scene.add(dirLight);

    const blueBacklight = new THREE.DirectionalLight(0x38bdf8, 0.8);
    blueBacklight.position.set(-10, 6, -10);
    scene.add(blueBacklight);

    // Grid Floor
    const grid = new THREE.GridHelper(24, 24, 0x334155, 0x1e293b);
    grid.position.y = 0;
    scene.add(grid);

    // Conveyor Frame Structure
    const trussMat = new THREE.MeshStandardMaterial({
      color: 0x475569,
      metalness: 0.8,
      roughness: 0.3,
    });

    const sideBeamGeo = new THREE.BoxGeometry(16, 0.25, 0.3);
    const leftBeam = new THREE.Mesh(sideBeamGeo, trussMat);
    leftBeam.position.set(0, 1.8, 1.2);
    scene.add(leftBeam);

    const rightBeam = new THREE.Mesh(sideBeamGeo, trussMat);
    rightBeam.position.set(0, 1.8, -1.2);
    scene.add(rightBeam);

    // Support Legs
    for (let x = -6; x <= 6; x += 4) {
      const legGeo = new THREE.CylinderGeometry(0.12, 0.15, 1.8, 8);
      const legL = new THREE.Mesh(legGeo, trussMat);
      legL.position.set(x, 0.9, 1.2);
      scene.add(legL);

      const legR = new THREE.Mesh(legGeo, trussMat);
      legR.position.set(x, 0.9, -1.2);
      scene.add(legR);

      const braceGeo = new THREE.BoxGeometry(0.1, 0.1, 2.4);
      const brace = new THREE.Mesh(braceGeo, trussMat);
      brace.position.set(x, 0.5, 0);
      scene.add(brace);
    }

    // Pulleys / Rollers
    const pulleyMat = new THREE.MeshStandardMaterial({
      color: 0x94a3b8,
      metalness: 0.9,
      roughness: 0.2,
    });

    const headPulley = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 2.2, 24), pulleyMat);
    headPulley.rotation.x = Math.PI / 2;
    headPulley.position.set(7.5, 1.8, 0);
    scene.add(headPulley);

    const tailPulley = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 2.2, 24), pulleyMat);
    tailPulley.rotation.x = Math.PI / 2;
    tailPulley.position.set(-7.5, 1.8, 0);
    scene.add(tailPulley);

    // Idler rollers
    const idlers: THREE.Mesh[] = [];
    for (let x = -5; x <= 5; x += 2.5) {
      const idler = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 2.2, 16), pulleyMat);
      idler.rotation.x = Math.PI / 2;
      idler.position.set(x, 1.6, 0);
      scene.add(idler);
      idlers.push(idler);

      const retIdler = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 2.2, 16), pulleyMat);
      retIdler.rotation.x = Math.PI / 2;
      retIdler.position.set(x, 0.6, 0);
      scene.add(retIdler);
      idlers.push(retIdler);
    }

    // Rubber Belt (Top Strand & Bottom Strand)
    const beltMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.85,
      metalness: 0.1,
    });

    const topBelt = new THREE.Mesh(new THREE.BoxGeometry(15, 0.08, 2.1), beltMat);
    topBelt.position.set(0, 2.5, 0);
    topBelt.receiveShadow = true;
    scene.add(topBelt);

    const bottomBelt = new THREE.Mesh(new THREE.BoxGeometry(15, 0.08, 2.1), beltMat);
    bottomBelt.position.set(0, 1.1, 0);
    scene.add(bottomBelt);

    // Moving payload: gives the twin a clearer sense of scale, direction and load.
    const payload = new THREE.Group();
    const crateMat = new THREE.MeshStandardMaterial({ color: 0x9a5a2b, metalness: 0.15, roughness: 0.72 });
    const strapMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.35, roughness: 0.45 });
    for (let i = 0; i < 3; i++) {
      const crate = new THREE.Mesh(new THREE.BoxGeometry(0.95, 0.5, 0.72), crateMat);
      crate.position.set(i * 1.05 - 1.05, 2.82, 0);
      crate.castShadow = true;
      payload.add(crate);
      const strap = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.54, 0.76), strapMat);
      strap.position.set(i * 1.05 - 1.05, 2.82, 0);
      payload.add(strap);
    }
    payload.position.x = -6;
    payload.visible = payloadVisible;
    scene.add(payload);

    // Active Splice Joint Marker
    const spliceMat = new THREE.MeshStandardMaterial({
      color: 0x38bdf8,
      emissive: 0x0284c7,
      emissiveIntensity: 0.5,
      roughness: 0.4,
    });
    const spliceMesh = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.12, 2.15), spliceMat);
    spliceMesh.position.set(-3, 2.52, 0);
    scene.add(spliceMesh);

    // Sensor Gantry Arch
    const gantryMat = new THREE.MeshStandardMaterial({
      color: 0x0284c7,
      metalness: 0.8,
      roughness: 0.25,
    });

    const gantryPostL = new THREE.Mesh(new THREE.BoxGeometry(0.3, 3.2, 0.3), gantryMat);
    gantryPostL.position.set(0, 2.2, 1.4);
    scene.add(gantryPostL);

    const gantryPostR = new THREE.Mesh(new THREE.BoxGeometry(0.3, 3.2, 0.3), gantryMat);
    gantryPostR.position.set(0, 2.2, -1.4);
    scene.add(gantryPostR);

    const gantryTop = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.35, 3.1), gantryMat);
    gantryTop.position.set(0, 3.8, 0);
    scene.add(gantryTop);

    // Sensor modules mounted on Gantry
    // 1. Line-Scan Camera
    const camHousing = new THREE.Mesh(
      new THREE.BoxGeometry(0.5, 0.4, 0.6),
      new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.9 })
    );
    camHousing.position.set(0, 3.45, 0);
    scene.add(camHousing);

    // Camera Laser Scanning Plane
    const laserGeo = new THREE.ConeGeometry(1.2, 1.8, 4, 1, true);
    const laserMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.35,
      side: THREE.DoubleSide,
    });
    const laserMesh = new THREE.Mesh(laserGeo, laserMat);
    laserMesh.position.set(0, 2.6, 0);
    laserMesh.rotation.z = Math.PI;
    laserMesh.scale.set(1.6, 1.0, 0.1);
    scene.add(laserMesh);

    // 2. Thermal Camera & Cone
    const thermalHousing = new THREE.Mesh(
      new THREE.CylinderGeometry(0.18, 0.22, 0.4, 16),
      new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.8 })
    );
    thermalHousing.rotation.x = Math.PI / 2;
    thermalHousing.position.set(0.4, 3.5, 0.6);
    scene.add(thermalHousing);

    const thermalConeMat = new THREE.MeshBasicMaterial({
      color: 0xf59e0b,
      transparent: true,
      opacity: 0.25,
      side: THREE.DoubleSide,
    });
    const thermalCone = new THREE.Mesh(new THREE.ConeGeometry(0.9, 1.6, 16, 1, true), thermalConeMat);
    thermalCone.position.set(0.4, 2.6, 0.6);
    thermalCone.rotation.z = Math.PI;
    scene.add(thermalCone);

    // 3. SpliceTracker Edge Compute Box
    const edgeBox = new THREE.Mesh(
      new THREE.BoxGeometry(0.8, 1.0, 0.5),
      new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.7, roughness: 0.3 })
    );
    edgeBox.position.set(0, 2.6, 1.7);
    scene.add(edgeBox);

    // Data Flow Particles
    const particleCount = 140;
    const particleGeo = new THREE.BufferGeometry();
    const particlePos = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i++) {
      particlePos[i * 3 + 0] = (Math.random() - 0.5) * 14;
      particlePos[i * 3 + 1] = 2.5 + Math.random() * 0.8;
      particlePos[i * 3 + 2] = (Math.random() - 0.5) * 1.8;
    }
    particleGeo.setAttribute('position', new THREE.BufferAttribute(particlePos, 3));
    const particleMat = new THREE.PointsMaterial({
      color: 0x38bdf8,
      size: 0.08,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
    });
    const particles = new THREE.Points(particleGeo, particleMat);
    scene.add(particles);

    // Interaction Controls State
    const spherical = {
      radius: 16,
      theta: 0.8,
      phi: 1.1,
    };

    const updateCameraPos = () => {
      camera.position.x = spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta);
      camera.position.y = spherical.radius * Math.cos(spherical.phi);
      camera.position.z = spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta);
      camera.lookAt(0, 2.0, 0);
    };
    updateCameraPos();

    let isDragging = false;
    let prevMouse = { x: 0, y: 0 };

    const onMouseDown = (e: MouseEvent) => {
      if (!interactive) return;
      isDragging = true;
      prevMouse = { x: e.clientX, y: e.clientY };
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging || !interactive) return;
      const dx = e.clientX - prevMouse.x;
      const dy = e.clientY - prevMouse.y;
      spherical.theta -= dx * 0.008;
      spherical.phi = Math.max(0.2, Math.min(Math.PI / 2 - 0.05, spherical.phi - dy * 0.008));
      updateCameraPos();
      prevMouse = { x: e.clientX, y: e.clientY };
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    const onWheel = (e: WheelEvent) => {
      if (!interactive) return;
      e.preventDefault();
      spherical.radius = Math.max(6, Math.min(28, spherical.radius + e.deltaY * 0.015));
      updateCameraPos();
    };

    const dom = renderer.domElement;
    dom.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    dom.addEventListener('wheel', onWheel, { passive: false });

    sceneState.current = {
      renderer,
      scene,
      camera,
      beltMesh: topBelt,
      spliceMesh,
      laserMesh,
      thermalCone,
      particles,
      idlers,
      payload,
      spherical,
    };

    let lastTime = performance.now();
    let spliceOffset = -3.0;

    const animate = () => {
      sceneState.current.animFrameId = requestAnimationFrame(animate);

      const now = performance.now();
      const dt = (now - lastTime) / 1000;
      lastTime = now;

      // Splice movement
      if (isRunning) {
        spliceOffset += dt * 3.5 * speed;
        if (spliceOffset > 7.5) spliceOffset = -7.5;
        spliceMesh.position.x = spliceOffset;
        if (payload) {
          payload.position.x += dt * 3.5 * speed;
          if (payload.position.x > 8) payload.position.x = -8;
        }
        idlers.forEach(idler => { idler.rotation.y += dt * 7 * speed; });
      }

      // Anomaly color update
      if (activeAnomaly) {
        if (activeAnomaly === 'critical') {
          (spliceMesh.material as THREE.MeshStandardMaterial).color.setHex(0xef4444);
          (spliceMesh.material as THREE.MeshStandardMaterial).emissive.setHex(0xdc2626);
          (laserMat as THREE.MeshBasicMaterial).color.setHex(0xef4444);
        } else if (activeAnomaly === 'thermal') {
          (spliceMesh.material as THREE.MeshStandardMaterial).color.setHex(0xf59e0b);
          (spliceMesh.material as THREE.MeshStandardMaterial).emissive.setHex(0xd97706);
          (thermalConeMat as THREE.MeshBasicMaterial).opacity = 0.5 + Math.sin(now * 0.01) * 0.25;
        } else if (activeAnomaly === 'vision') {
          (spliceMesh.material as THREE.MeshStandardMaterial).color.setHex(0x38bdf8);
          (laserMat as THREE.MeshBasicMaterial).opacity = 0.6 + Math.sin(now * 0.01) * 0.3;
        } else {
          (spliceMesh.material as THREE.MeshStandardMaterial).color.setHex(0xa855f7);
        }
      } else {
        (spliceMesh.material as THREE.MeshStandardMaterial).color.setHex(0x10b981);
        (spliceMesh.material as THREE.MeshStandardMaterial).emissive.setHex(0x059669);
      }

      laserMesh.scale.x = 1.6 + Math.sin(now * 0.008) * 0.15;
      (laserMat as THREE.MeshBasicMaterial).opacity = scanPulse
        ? 0.55 + Math.sin(now * 0.02) * 0.35
        : 0.23 + Math.sin(now * 0.008) * 0.1;

      if (particles && particlesActive && isRunning) {
        const positions = particles.geometry.attributes.position.array as Float32Array;
        for (let i = 0; i < particleCount; i++) {
          positions[i * 3 + 0] += dt * 4.0;
          if (positions[i * 3 + 0] > 7.5) positions[i * 3 + 0] = -7.5;
        }
        particles.geometry.attributes.position.needsUpdate = true;
      }

      renderer.render(scene, camera);
    };

    animate();

    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        const newW = entry.contentRect.width;
        if (newW > 0) {
          camera.aspect = newW / h;
          camera.updateProjectionMatrix();
          renderer.setSize(newW, h);
        }
      }
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      if (sceneState.current.animFrameId) {
        cancelAnimationFrame(sceneState.current.animFrameId);
      }
      dom.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      dom.removeEventListener('wheel', onWheel);
      renderer.dispose();
    };
  }, [height, interactive, speed, activeAnomaly, particlesActive, isRunning, scanPulse, payloadVisible]);

  const switchCamera = (view: 'iso' | 'gantry' | 'top') => {
    setCameraView(view);
    const cam = sceneState.current.camera;
    const sp = sceneState.current.spherical;
    if (!cam || !sp) return;

    if (view === 'iso') {
      sp.radius = 16;
      sp.theta = 0.8;
      sp.phi = 1.1;
    } else if (view === 'gantry') {
      sp.radius = 8;
      sp.theta = 0.15;
      sp.phi = 1.25;
    } else if (view === 'top') {
      sp.radius = 14;
      sp.theta = 0.01;
      sp.phi = 0.2;
    }

    cam.position.x = sp.radius * Math.sin(sp.phi) * Math.sin(sp.theta);
    cam.position.y = sp.radius * Math.cos(sp.phi);
    cam.position.z = sp.radius * Math.sin(sp.phi) * Math.cos(sp.theta);
    cam.lookAt(0, 2.0, 0);
  };

  return (
    <div className="relative rounded-xl overflow-hidden border border-slate-700/60 shadow-lg bg-slate-900 group">
      {/* 3D WebGL Canvas */}
      <div ref={containerRef} style={{ height, width: '100%' }} className="cursor-grab active:cursor-grabbing" />

      {/* Top HUD Overlay */}
      <div className="absolute top-3 left-3 flex items-center gap-2 pointer-events-none">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900/80 backdrop-blur-md border border-slate-700/70 text-xs font-mono text-slate-200">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>3D CONVEYOR TWIN</span>
        </div>
        <div className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 text-[10px] font-mono">
          {spliceName}
        </div>
        {condition && (
          <div
            className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase ${
              condition === 'CRITICAL'
                ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                : condition === 'HIGH_RISK' || condition === 'POOR' || condition === 'DEGRADED'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
            }`}
          >
            {condition}
          </div>
        )}
      </div>

      {/* Quick Interactive Camera Controls */}
      {showControls && (
        <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-slate-900/80 backdrop-blur-md p-1 rounded-lg border border-slate-700/70">
          <button
            onClick={() => switchCamera('iso')}
            className={`px-2 py-1 rounded text-xs font-mono transition-colors ${
              cameraView === 'iso' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
            title="Isometric View"
          >
            ISO
          </button>
          <button
            onClick={() => switchCamera('gantry')}
            className={`px-2 py-1 rounded text-xs font-mono transition-colors ${
              cameraView === 'gantry' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
            title="Gantry Close-Up"
          >
            GANTRY
          </button>
          <button
            onClick={() => switchCamera('top')}
            className={`px-2 py-1 rounded text-xs font-mono transition-colors ${
              cameraView === 'top' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
            title="Top-Down Plan"
          >
            TOP
          </button>
          <button
            onClick={() => setParticlesActive(!particlesActive)}
            className={`p-1 rounded transition-colors ${
              particlesActive ? 'text-cyan-400 bg-cyan-950/60' : 'text-slate-500 hover:text-slate-300'
            }`}
            title="Toggle Particle Telemetry"
          >
            <Sparkles className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Operational interaction rail */}
      {showControls && (
        <div className="absolute bottom-9 left-3 flex items-center gap-1.5 bg-slate-900/85 backdrop-blur-md p-1 rounded-lg border border-slate-700/70">
          <button
            onClick={() => setIsRunning(v => !v)}
            className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono font-bold transition-colors ${isRunning ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-200'}`}
            title="Pause or resume the simulated conveyor"
          >
            {isRunning ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            {isRunning ? 'RUNNING' : 'PAUSED'}
          </button>
          <button
            onClick={() => setScanPulse(v => !v)}
            className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono transition-colors ${scanPulse ? 'bg-cyan-700 text-white' : 'text-cyan-300 hover:bg-cyan-950/70'}`}
            title="Toggle a high-intensity inspection scan"
          >
            <ScanLine className="w-3 h-3" /> SCAN
          </button>
          <button
            onClick={() => setPayloadVisible(v => !v)}
            className={`p-1 rounded transition-colors ${payloadVisible ? 'text-amber-300 bg-amber-950/60' : 'text-slate-500 hover:text-slate-300'}`}
            title="Show or hide the conveyed payload"
          >
            <Package className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => switchCamera('iso')}
            className="p-1 text-slate-400 hover:text-white rounded transition-colors"
            title="Reset to isometric view"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Bottom Telemetry HUD */}
      <div className="absolute bottom-2 left-3 right-3 flex items-center justify-between text-[10px] font-mono text-slate-400 pointer-events-none bg-slate-900/60 backdrop-blur-sm px-2.5 py-1 rounded border border-slate-800/80">
        <div className="flex items-center gap-3">
          <span className="text-cyan-400 font-medium">CAM 2048px LWIR</span>
          <span className="text-amber-400">THERMAL 60Hz</span>
          <span className="text-purple-400">VIB 3-AXIS</span>
          <span className={isRunning ? 'text-emerald-400' : 'text-slate-500'}>DRIVE {isRunning ? 'RUN' : 'HOLD'}</span>
        </div>
        <div className="text-slate-400">Drag to Orbit • Scroll to Zoom</div>
      </div>
    </div>
  );
}
