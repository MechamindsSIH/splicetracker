import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { AlertOctagon, MapPin, Eye, Filter } from 'lucide-react';

interface AlertItem {
  id: number;
  severity: string;
  splice_id: number;
  location?: string;
  reason?: string;
  risk_score?: number;
  status: string;
}

interface ConveyorAlerts3DMapProps {
  height?: string | number;
  alerts: AlertItem[];
  onSelectAlert?: (alert: AlertItem) => void;
}

export default function ConveyorAlerts3DMap({
  height = '340px',
  alerts = [],
  onSelectAlert,
}: ConveyorAlerts3DMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);

  const sceneState = useRef<{
    renderer?: THREE.WebGLRenderer;
    scene?: THREE.Scene;
    camera?: THREE.PerspectiveCamera;
    beaconMeshes: { mesh: THREE.Mesh; alert: AlertItem }[];
    animFrameId?: number;
    spherical?: { radius: number; theta: number; phi: number };
  }>({
    beaconMeshes: [],
  });

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 600;
    const h = typeof height === 'number' ? height : parseInt(String(height)) || 340;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0e1a);
    scene.fog = new THREE.FogExp2(0x0a0e1a, 0.02);

    const camera = new THREE.PerspectiveCamera(45, width / h, 0.1, 100);
    camera.position.set(16, 14, 18);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(width, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.3;

    container.replaceChildren(renderer.domElement);

    // Lights
    const ambient = new THREE.AmbientLight(0xffffff, 0.65);
    scene.add(ambient);

    const sun = new THREE.DirectionalLight(0xffffff, 1.3);
    sun.position.set(15, 25, 15);
    scene.add(sun);

    const blueFill = new THREE.DirectionalLight(0x38bdf8, 0.7);
    blueFill.position.set(-15, 10, -10);
    scene.add(blueFill);

    // Ground Grid & Facility Foundation
    const grid = new THREE.GridHelper(36, 36, 0x1e293b, 0x0f172a);
    grid.position.y = 0;
    scene.add(grid);

    // Conveyor Lines Definition (4 belts in industrial facility layout)
    const beltLines = [
      { id: 'BELT-01', name: 'Overland Main Line 1', start: [-12, 1.2, -6], end: [12, 1.2, -6], color: 0x3b82f6 },
      { id: 'BELT-02', name: 'In-Plant Secondary Feeder', start: [-8, 2.5, 0], end: [8, 1.8, 0], color: 0x10b981 },
      { id: 'BELT-03', name: 'Stacker Staging Conveyor', start: [0, 1.0, 6], end: [10, 4.5, 6], color: 0x8b5cf6 },
      { id: 'BELT-04', name: 'Decline Transfer Line', start: [-10, 4.2, 3], end: [-2, 1.0, -2], color: 0xf59e0b },
    ];

    beltLines.forEach(b => {
      const vStart = new THREE.Vector3(b.start[0], b.start[1], b.start[2]);
      const vEnd = new THREE.Vector3(b.end[0], b.end[1], b.end[2]);
      const dir = new THREE.Vector3().subVectors(vEnd, vStart);
      const len = dir.length();
      const mid = new THREE.Vector3().addVectors(vStart, vEnd).multiplyScalar(0.5);

      // Conveyor Belt Truss
      const trussGeo = new THREE.BoxGeometry(0.5, 0.3, len);
      const trussMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.8, roughness: 0.3 });
      const truss = new THREE.Mesh(trussGeo, trussMat);
      truss.position.copy(mid);
      truss.lookAt(vEnd);
      scene.add(truss);

      // Rubber Belt Top Ribbon
      const beltGeo = new THREE.BoxGeometry(0.38, 0.05, len);
      const beltMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.9 });
      const ribbon = new THREE.Mesh(beltGeo, beltMat);
      ribbon.position.copy(mid);
      ribbon.position.y += 0.18;
      ribbon.lookAt(vEnd);
      scene.add(ribbon);

      // Support Pylons to Ground
      const pylonCount = 4;
      for (let p = 0; p <= pylonCount; p++) {
        const pt = new THREE.Vector3().lerpVectors(vStart, vEnd, p / pylonCount);
        const pylonGeo = new THREE.CylinderGeometry(0.08, 0.1, pt.y, 8);
        const pylonMat = new THREE.MeshStandardMaterial({ color: 0x475569 });
        const pylon = new THREE.Mesh(pylonGeo, pylonMat);
        pylon.position.set(pt.x, pt.y / 2, pt.z);
        scene.add(pylon);
      }
    });

    // Alert Beacon Pins
    const beaconMeshes: { mesh: THREE.Mesh; alert: AlertItem }[] = [];
    const pinGeo = new THREE.ConeGeometry(0.28, 0.8, 16);
    pinGeo.rotateX(Math.PI); // Point down

    alerts.slice(0, 30).forEach((alert, i) => {
      // Map alert to belt
      let bLine = beltLines[0];
      if (alert.location?.includes('BELT-02') || (alert.splice_id >= 6 && alert.splice_id <= 9)) bLine = beltLines[1];
      else if (alert.location?.includes('BELT-03') || (alert.splice_id >= 10 && alert.splice_id <= 12)) bLine = beltLines[2];
      else if (alert.location?.includes('BELT-04') || alert.splice_id >= 13) bLine = beltLines[3];

      // Interpolation along belt line
      const alpha = 0.15 + (i * 0.11) % 0.7;
      const vStart = new THREE.Vector3(bLine.start[0], bLine.start[1], bLine.start[2]);
      const vEnd = new THREE.Vector3(bLine.end[0], bLine.end[1], bLine.end[2]);
      const pos = new THREE.Vector3().lerpVectors(vStart, vEnd, alpha);
      pos.y += 0.9;

      const isCritical = alert.severity === 'CRITICAL';
      const isHigh = alert.severity === 'HIGH';
      const color = isCritical ? 0xef4444 : isHigh ? 0xf97316 : 0xeab308;

      const pinMat = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: isCritical ? 0.9 : 0.6,
        roughness: 0.2,
      });

      const pin = new THREE.Mesh(pinGeo, pinMat);
      pin.position.copy(pos);
      scene.add(pin);

      // Pulsing Base Ring
      const ringGeo = new THREE.RingGeometry(0.15, 0.4, 16);
      const ringMat = new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide, transparent: true, opacity: 0.6 });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = Math.PI / 2;
      ring.position.set(pos.x, pos.y - 0.4, pos.z);
      scene.add(ring);

      beaconMeshes.push({ mesh: pin, alert });
    });

    // Orbit Camera
    const spherical = {
      radius: 26,
      theta: 0.7,
      phi: 0.9,
    };

    const updateCameraPos = () => {
      camera.position.x = spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta);
      camera.position.y = spherical.radius * Math.cos(spherical.phi);
      camera.position.z = spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta);
      camera.lookAt(0, 1.5, 0);
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
      spherical.theta -= dx * 0.007;
      spherical.phi = Math.max(0.15, Math.min(Math.PI / 2 - 0.05, spherical.phi - dy * 0.007));
      updateCameraPos();
      prevMouse = { x: e.clientX, y: e.clientY };
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      spherical.radius = Math.max(8, Math.min(45, spherical.radius + e.deltaY * 0.02));
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
      beaconMeshes,
      spherical,
    };

    // Animation Loop
    const animate = () => {
      sceneState.current.animFrameId = requestAnimationFrame(animate);
      const now = performance.now();

      beaconMeshes.forEach((bm, idx) => {
        bm.mesh.position.y += Math.sin(now * 0.005 + idx) * 0.002;
        bm.mesh.rotation.y += 0.015;
      });

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
  }, [height, alerts]);

  return (
    <div className="relative rounded-xl overflow-hidden border border-slate-700/60 shadow-lg bg-slate-900">
      {/* 3D Canvas */}
      <div ref={containerRef} style={{ height, width: '100%' }} className="cursor-grab active:cursor-grabbing" />

      {/* Top Header */}
      <div className="absolute top-3 left-3 flex items-center gap-2 pointer-events-none">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900/80 backdrop-blur-md border border-slate-700 text-xs font-mono text-slate-200">
          <MapPin className="w-3.5 h-3.5 text-red-400 animate-bounce" />
          <span>3D FACILITY ALERT LOCATOR</span>
        </div>
        <div className="px-2 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/30 text-[10px] font-mono">
          {alerts.length} Active Beacons
        </div>
      </div>

      {/* Belt Legend */}
      <div className="absolute top-3 right-3 flex items-center gap-2 bg-slate-900/85 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-700 text-[10px] font-mono text-slate-300">
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-blue-500" />
          <span>BELT-01</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span>BELT-02</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-purple-500" />
          <span>BELT-03</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-amber-500" />
          <span>BELT-04</span>
        </div>
      </div>

      {/* Bottom Technical Status */}
      <div className="absolute bottom-2 left-3 right-3 flex items-center justify-between text-[10px] font-mono text-slate-400 pointer-events-none bg-slate-900/70 backdrop-blur-sm px-2.5 py-1 rounded border border-slate-800">
        <div className="flex items-center gap-3">
          <span className="text-red-400 font-bold">● CRITICAL (Immediate Stop)</span>
          <span className="text-orange-400">● HIGH (Schedule Shift)</span>
          <span className="text-yellow-400">● WARNING (Trend Alert)</span>
        </div>
        <div>Drag to Rotate Facility • Scroll to Zoom</div>
      </div>
    </div>
  );
}
