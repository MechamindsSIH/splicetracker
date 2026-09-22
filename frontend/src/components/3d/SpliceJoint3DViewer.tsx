import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Layers, Eye, ShieldAlert, Sparkles, ZoomIn } from 'lucide-react';

interface SpliceJoint3DViewerProps {
  height?: string | number;
  condition?: string;
  severity?: number;
  defectType?: string;
  spliceName?: string;
}

export default function SpliceJoint3DViewer({
  height = '340px',
  condition = 'GOOD',
  severity = 0.05,
  defectType = 'normal',
  spliceName = 'Splice-001',
}: SpliceJoint3DViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [showTopCover, setShowTopCover] = useState(true);
  const [showCords, setShowCords] = useState(true);
  const [showCore, setShowCore] = useState(true);
  const [showStressMap, setShowStressMap] = useState(true);
  const [selectedCord, setSelectedCord] = useState<number | null>(null);

  const sceneState = useRef<{
    renderer?: THREE.WebGLRenderer;
    scene?: THREE.Scene;
    camera?: THREE.PerspectiveCamera;
    topCover?: THREE.Mesh;
    coreLayer?: THREE.Mesh;
    cordsGroup?: THREE.Group;
    defectMarker?: THREE.Mesh;
    animFrameId?: number;
    spherical?: { radius: number; theta: number; phi: number };
  }>({});

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 600;
    const h = typeof height === 'number' ? height : parseInt(String(height)) || 340;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0f1d);

    const camera = new THREE.PerspectiveCamera(45, width / h, 0.1, 100);
    camera.position.set(7, 5, 8);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(width, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.3;

    container.replaceChildren(renderer.domElement);

    // Lights
    const ambient = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambient);

    const mainLight = new THREE.DirectionalLight(0xffffff, 1.2);
    mainLight.position.set(8, 12, 6);
    mainLight.castShadow = true;
    scene.add(mainLight);

    const blueLight = new THREE.PointLight(0x38bdf8, 1.5, 20);
    blueLight.position.set(-6, 3, -4);
    scene.add(blueLight);

    // Grid Floor
    const grid = new THREE.GridHelper(14, 14, 0x1e293b, 0x0f172a);
    grid.position.y = -1.5;
    scene.add(grid);

    // Splice Base Geometry Dimensions
    const length = 7.0;
    const widthBelt = 3.6;
    const coverThickness = 0.22;
    const coreThickness = 0.28;

    // Heatmap / Color selection based on severity
    const isCritical = condition === 'CRITICAL' || severity > 0.8;
    const isDegraded = condition === 'POOR' || condition === 'DEGRADED' || severity > 0.45;
    const isWarning = condition === 'WARNING' || condition === 'FAIR' || severity > 0.2;

    const stressColor = isCritical ? 0xef4444 : isDegraded ? 0xf97316 : isWarning ? 0xeab308 : 0x10b981;

    // 1. Bottom Rubber Cover
    const bottomCoverGeo = new THREE.BoxGeometry(length, coverThickness, widthBelt);
    const bottomCoverMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.8,
      metalness: 0.1,
    });
    const bottomCover = new THREE.Mesh(bottomCoverGeo, bottomCoverMat);
    bottomCover.position.set(0, -coverThickness / 2 - coreThickness / 2, 0);
    scene.add(bottomCover);

    // 2. Vulcanized Core / Skim Rubber (with Stress Heatmap)
    const coreGeo = new THREE.BoxGeometry(length, coreThickness, widthBelt, 32, 1, 16);
    const coreMat = new THREE.MeshStandardMaterial({
      color: showStressMap ? stressColor : 0x334155,
      roughness: 0.6,
      metalness: 0.2,
      transparent: true,
      opacity: 0.85,
    });
    const coreLayer = new THREE.Mesh(coreGeo, coreMat);
    coreLayer.position.set(0, 0, 0);
    scene.add(coreLayer);

    // 3. Top Rubber Cover
    const topCoverGeo = new THREE.BoxGeometry(length, coverThickness, widthBelt);
    const topCoverMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.75,
      metalness: 0.15,
      transparent: true,
      opacity: showTopCover ? 0.92 : 0.15,
    });
    const topCover = new THREE.Mesh(topCoverGeo, topCoverMat);
    topCover.position.set(0, coverThickness / 2 + coreThickness / 2, 0);
    scene.add(topCover);

    // 4. Steel Cord Matrix (7 cords running lengthwise through splice)
    const cordsGroup = new THREE.Group();
    const cordCount = 9;
    const cordRadius = 0.055;

    for (let i = 0; i < cordCount; i++) {
      const zOffset = (i - (cordCount - 1) / 2) * (widthBelt / (cordCount + 1));
      const isDamagedCord = isCritical && (i === 4 || i === 5);

      const cordMat = new THREE.MeshStandardMaterial({
        color: isDamagedCord ? 0xef4444 : 0x94a3b8,
        metalness: 0.95,
        roughness: 0.15,
        emissive: isDamagedCord ? 0xdc2626 : 0x000000,
        emissiveIntensity: isDamagedCord ? 0.6 : 0,
      });

      const cordGeo = new THREE.CylinderGeometry(cordRadius, cordRadius, length * 1.05, 16);
      const cord = new THREE.Mesh(cordGeo, cordMat);
      cord.rotation.z = Math.PI / 2;
      cord.position.set(0, 0, zOffset);
      cordsGroup.add(cord);
    }
    cordsGroup.visible = showCords;
    scene.add(cordsGroup);

    // 5. Splice Step Joint Lines (Visualizing bias/step cut angle)
    const stepMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, wireframe: true });
    const stepLineGeo = new THREE.BoxGeometry(1.4, 0.02, widthBelt);
    const stepJoint = new THREE.Mesh(stepLineGeo, stepMat);
    stepJoint.position.set(0, coverThickness / 2 + coreThickness / 2 + 0.01, 0);
    stepJoint.rotation.y = 0.26; // Bias angle
    scene.add(stepJoint);

    // 6. Defect Callout Mesh (if anomaly exists)
    let defectMarker: THREE.Mesh | undefined;
    if (isCritical || isDegraded || isWarning) {
      const defectGeo = new THREE.SphereGeometry(0.35 + severity * 0.4, 16, 16);
      const defectMat = new THREE.MeshStandardMaterial({
        color: isCritical ? 0xef4444 : 0xf97316,
        emissive: isCritical ? 0xdc2626 : 0xea580c,
        emissiveIntensity: 0.8,
        transparent: true,
        opacity: 0.75,
      });
      defectMarker = new THREE.Mesh(defectGeo, defectMat);
      defectMarker.position.set(0.3, coreThickness / 2, 0.4);
      scene.add(defectMarker);

      // Warning Ring Pulse
      const ringGeo = new THREE.RingGeometry(0.4, 0.6, 24);
      const ringMat = new THREE.MeshBasicMaterial({
        color: isCritical ? 0xef4444 : 0xf97316,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.6,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = Math.PI / 2;
      ring.position.set(0.3, coreThickness / 2 + 0.05, 0.4);
      scene.add(ring);
    }

    // Camera Orbit State
    const spherical = {
      radius: 10.5,
      theta: 0.7,
      phi: 1.0,
    };

    const updateCameraPos = () => {
      camera.position.x = spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta);
      camera.position.y = spherical.radius * Math.cos(spherical.phi);
      camera.position.z = spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta);
      camera.lookAt(0, 0, 0);
    };
    updateCameraPos();

    let isDragging = false;
    let prevMouse = { x: 0, y: 0 };

    const onMouseDown = (e: MouseEvent) => {
      isDragging = true;
      prevMouse = { x: e.clientX, y: e.clientY };
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const dx = e.clientX - prevMouse.x;
      const dy = e.clientY - prevMouse.y;
      spherical.theta -= dx * 0.008;
      spherical.phi = Math.max(0.1, Math.min(Math.PI / 2 - 0.05, spherical.phi - dy * 0.008));
      updateCameraPos();
      prevMouse = { x: e.clientX, y: e.clientY };
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      spherical.radius = Math.max(4.5, Math.min(20, spherical.radius + e.deltaY * 0.012));
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
      topCover,
      coreLayer,
      cordsGroup,
      defectMarker,
      spherical,
    };

    // Animation Loop
    const animate = () => {
      sceneState.current.animFrameId = requestAnimationFrame(animate);
      const now = performance.now();

      if (defectMarker) {
        const s = 1.0 + Math.sin(now * 0.006) * 0.15;
        defectMarker.scale.set(s, s, s);
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
      if (sceneState.current.animFrameId) cancelAnimationFrame(sceneState.current.animFrameId);
      dom.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      dom.removeEventListener('wheel', onWheel);
      renderer.dispose();
    };
  }, [height, condition, severity, defectType]);

  // Handle Layer Visibility Toggles
  useEffect(() => {
    if (sceneState.current.topCover) {
      const mat = sceneState.current.topCover.material as THREE.MeshStandardMaterial;
      mat.opacity = showTopCover ? 0.92 : 0.15;
    }
    if (sceneState.current.cordsGroup) {
      sceneState.current.cordsGroup.visible = showCords;
    }
    if (sceneState.current.coreLayer) {
      sceneState.current.coreLayer.visible = showCore;
    }
  }, [showTopCover, showCords, showCore]);

  return (
    <div className="relative rounded-xl overflow-hidden border border-slate-700/60 shadow-lg bg-slate-900">
      {/* 3D Canvas */}
      <div ref={containerRef} style={{ height, width: '100%' }} className="cursor-grab active:cursor-grabbing" />

      {/* Top Header & Splice Tag */}
      <div className="absolute top-3 left-3 flex items-center gap-2 pointer-events-none">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900/80 backdrop-blur-md border border-slate-700 text-xs font-mono text-slate-200">
          <Layers className="w-3.5 h-3.5 text-blue-400" />
          <span>VULCANIZED JOINT 3D</span>
        </div>
        <div className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 text-[10px] font-mono">
          {spliceName}
        </div>
        <div
          className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase ${
            condition === 'CRITICAL'
              ? 'bg-red-500/20 text-red-400 border border-red-500/30'
              : condition === 'HIGH_RISK' || condition === 'POOR' || condition === 'DEGRADED'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
          }`}
        >
          {condition} • Sev {(severity * 100).toFixed(0)}%
        </div>
      </div>

      {/* Layer Visibility Controls */}
      <div className="absolute top-3 right-3 flex items-center gap-1 bg-slate-900/85 backdrop-blur-md p-1 rounded-lg border border-slate-700 text-[11px] font-mono">
        <button
          onClick={() => setShowTopCover(!showTopCover)}
          className={`px-2 py-0.5 rounded transition-colors ${
            showTopCover ? 'bg-slate-700 text-slate-200' : 'text-slate-500 hover:text-slate-300'
          }`}
          title="Toggle Top Cover Transparency"
        >
          Top Cover
        </button>
        <button
          onClick={() => setShowCords(!showCords)}
          className={`px-2 py-0.5 rounded transition-colors ${
            showCords ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-slate-300'
          }`}
          title="Toggle Steel Cords Layer"
        >
          Steel Cords
        </button>
        <button
          onClick={() => setShowCore(!showCore)}
          className={`px-2 py-0.5 rounded transition-colors ${
            showCore ? 'bg-emerald-600 text-white' : 'text-slate-500 hover:text-slate-300'
          }`}
          title="Toggle Core Skim Compound"
        >
          Core Skim
        </button>
      </div>

      {/* Bottom Technical Spec */}
      <div className="absolute bottom-2 left-3 right-3 flex items-center justify-between text-[10px] font-mono text-slate-400 pointer-events-none bg-slate-900/70 backdrop-blur-sm px-2.5 py-1 rounded border border-slate-800">
        <div className="flex items-center gap-3">
          <span className="text-slate-300">Cut: 22° Bias Step Joint</span>
          <span className="text-blue-400">9x 7x7 High-Tensile Steel Cords</span>
          <span className={severity > 0.4 ? 'text-amber-400 font-bold' : 'text-emerald-400'}>
            Defect: {defectType.toUpperCase()}
          </span>
        </div>
        <div className="text-slate-400">Orbit with Mouse • Transparent Top Layer</div>
      </div>
    </div>
  );
}
