import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Activity, Eye, Layers, Compass } from 'lucide-react';

interface SensorSpatial3DGraphProps {
  height?: string | number;
  dataPoints?: { x: number; y: number; z: number; score: number; label: string }[];
}

export default function SensorSpatial3DGraph({
  height = '360px',
  dataPoints = [],
}: SensorSpatial3DGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [wireframeOnly, setWireframeOnly] = useState(false);

  const sceneState = useRef<{
    renderer?: THREE.WebGLRenderer;
    scene?: THREE.Scene;
    camera?: THREE.PerspectiveCamera;
    terrainMesh?: THREE.Mesh;
    particles?: THREE.Points;
    animFrameId?: number;
    spherical?: { radius: number; theta: number; phi: number };
  }>({});

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 600;
    const h = typeof height === 'number' ? height : parseInt(String(height)) || 360;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b1120);

    const camera = new THREE.PerspectiveCamera(45, width / h, 0.1, 100);
    camera.position.set(16, 12, 16);
    camera.lookAt(0, 1, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(width, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;

    container.replaceChildren(renderer.domElement);

    // Lights
    const ambient = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambient);

    const keyLight = new THREE.DirectionalLight(0x38bdf8, 1.4);
    keyLight.position.set(10, 18, 12);
    scene.add(keyLight);

    const magentaLight = new THREE.DirectionalLight(0xa855f7, 0.8);
    magentaLight.position.set(-10, 8, -10);
    scene.add(magentaLight);

    // 3D Bounding Cage / Axes
    const boxGeo = new THREE.BoxGeometry(14, 6, 14);
    const boxMat = new THREE.MeshBasicMaterial({ color: 0x1e293b, wireframe: true });
    const cage = new THREE.Mesh(boxGeo, boxMat);
    cage.position.y = 3;
    scene.add(cage);

    // Ground Grid
    const grid = new THREE.GridHelper(14, 14, 0x334155, 0x1e293b);
    grid.position.y = 0;
    scene.add(grid);

    // Dynamic 3D Risk Surface / Terrain Mesh
    const gridW = 32;
    const gridD = 32;
    const terrainGeo = new THREE.PlaneGeometry(14, 14, gridW - 1, gridD - 1);
    terrainGeo.rotateX(-Math.PI / 2);

    const posAttr = terrainGeo.attributes.position;
    const colors = new Float32Array(posAttr.count * 3);

    for (let i = 0; i < posAttr.count; i++) {
      const x = posAttr.getX(i);
      const z = posAttr.getZ(i);

      // Synthesize risk topology landscape
      const dist1 = Math.hypot(x - 3.2, z - 2.5); // Peak at critical splice
      const dist2 = Math.hypot(x + 2.8, z + 3.0); // Secondary degradation peak

      let elevation = 0.2 + 2.6 * Math.exp(-dist1 * 0.45) + 1.8 * Math.exp(-dist2 * 0.55);
      elevation += Math.sin(x * 0.8) * Math.cos(z * 0.8) * 0.2;

      posAttr.setY(i, Math.max(0.05, elevation));

      // Vertex color from green (low) -> amber (mod) -> red (high)
      const norm = Math.min(1.0, elevation / 3.0);
      if (norm > 0.65) {
        colors[i * 3 + 0] = 0.94; // Red
        colors[i * 3 + 1] = 0.27;
        colors[i * 3 + 2] = 0.27;
      } else if (norm > 0.35) {
        colors[i * 3 + 0] = 0.96; // Amber
        colors[i * 3 + 1] = 0.62;
        colors[i * 3 + 2] = 0.04;
      } else {
        colors[i * 3 + 0] = 0.06; // Emerald
        colors[i * 3 + 1] = 0.73;
        colors[i * 3 + 2] = 0.51;
      }
    }

    terrainGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    terrainGeo.computeVertexNormals();

    const terrainMat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      metalness: 0.3,
      roughness: 0.6,
      side: THREE.DoubleSide,
      wireframe: wireframeOnly,
      transparent: true,
      opacity: 0.88,
    });

    const terrainMesh = new THREE.Mesh(terrainGeo, terrainMat);
    scene.add(terrainMesh);

    // Inspection Data Points (3D Spatial Scatter)
    const scatterCount = 80;
    const scatterGeo = new THREE.BufferGeometry();
    const scatterPos = new Float32Array(scatterCount * 3);
    const scatterCol = new Float32Array(scatterCount * 3);

    for (let i = 0; i < scatterCount; i++) {
      const px = (Math.random() - 0.5) * 13;
      const pz = (Math.random() - 0.5) * 13;
      const d1 = Math.hypot(px - 3.2, pz - 2.5);
      const py = Math.max(0.1, 0.2 + 2.6 * Math.exp(-d1 * 0.45) + (Math.random() - 0.5) * 0.4);

      scatterPos[i * 3 + 0] = px;
      scatterPos[i * 3 + 1] = py;
      scatterPos[i * 3 + 2] = pz;

      const norm = Math.min(1.0, py / 3.0);
      if (norm > 0.6) {
        scatterCol[i * 3 + 0] = 1.0;
        scatterCol[i * 3 + 1] = 0.2;
        scatterCol[i * 3 + 2] = 0.2;
      } else {
        scatterCol[i * 3 + 0] = 0.2;
        scatterCol[i * 3 + 1] = 0.8;
        scatterCol[i * 3 + 2] = 1.0;
      }
    }

    scatterGeo.setAttribute('position', new THREE.BufferAttribute(scatterPos, 3));
    scatterGeo.setAttribute('color', new THREE.BufferAttribute(scatterCol, 3));

    const scatterMat = new THREE.PointsMaterial({
      size: 0.22,
      vertexColors: true,
      transparent: true,
      opacity: 0.9,
    });
    const particles = new THREE.Points(scatterGeo, scatterMat);
    scene.add(particles);

    // Orbit Camera Controls
    const spherical = {
      radius: 24,
      theta: 0.8,
      phi: 1.1,
    };

    const updateCameraPos = () => {
      camera.position.x = spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta);
      camera.position.y = spherical.radius * Math.cos(spherical.phi);
      camera.position.z = spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta);
      camera.lookAt(0, 1.8, 0);
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
      spherical.radius = Math.max(8, Math.min(38, spherical.radius + e.deltaY * 0.015));
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
      terrainMesh,
      particles,
      spherical,
    };

    let rot = 0;
    const animate = () => {
      sceneState.current.animFrameId = requestAnimationFrame(animate);
      rot += 0.002;
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
  }, [height, wireframeOnly]);

  return (
    <div className="relative rounded-xl overflow-hidden border border-slate-700/60 shadow-lg bg-slate-900">
      {/* 3D Canvas */}
      <div ref={containerRef} style={{ height, width: '100%' }} className="cursor-grab active:cursor-grabbing" />

      {/* Top Header */}
      <div className="absolute top-3 left-3 flex items-center gap-2 pointer-events-none">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900/80 backdrop-blur-md border border-slate-700 text-xs font-mono text-slate-200">
          <Activity className="w-3.5 h-3.5 text-cyan-400" />
          <span>3D RISK & ANOMALY TOPOGRAPHY</span>
        </div>
        <div className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 text-[10px] font-mono">
          Spatial Surface Fit
        </div>
      </div>

      {/* Wireframe toggle */}
      <div className="absolute top-3 right-3 flex items-center gap-1 bg-slate-900/85 backdrop-blur-md p-1 rounded-lg border border-slate-700 text-[11px] font-mono">
        <button
          onClick={() => setWireframeOnly(!wireframeOnly)}
          className={`px-2.5 py-1 rounded transition-colors ${
            wireframeOnly ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:text-white'
          }`}
        >
          {wireframeOnly ? 'Wireframe' : 'Surface Shaded'}
        </button>
      </div>

      {/* Axis Guide & Bottom Legend */}
      <div className="absolute bottom-2 left-3 right-3 flex items-center justify-between text-[10px] font-mono text-slate-400 pointer-events-none bg-slate-900/70 backdrop-blur-sm px-2.5 py-1 rounded border border-slate-800">
        <div className="flex items-center gap-4">
          <span className="text-cyan-400 font-semibold">X: Belt Station (0–1200m)</span>
          <span className="text-emerald-400 font-semibold">Y: Anomaly Score (0–1.0)</span>
          <span className="text-purple-400 font-semibold">Z: Conveyor Asset Line</span>
        </div>
        <div className="text-slate-400">Drag to Orbit Topography • Scroll to Zoom</div>
      </div>
    </div>
  );
}
