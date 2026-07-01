import * as THREE from "three";
import { knowledgeStageVisibility, stageTreeDim, updateStageUI } from "./tour-stage.js";

const COLORS = {
  problem: 0xff6bcb,
  cause: 0xff9a5c,
  cause_evidence: 0x3de8ff,
  remediation: 0x9b5cff,
  method: 0xb8ff5c,
  method_open: 0x5a6a7a,
  line: 0x3de8ff,
  agent: 0xff6bcb,
  knowledge: 0x9b5cff,
};

/** @type {Array<{ id: string, type: string, label: string, pos: THREE.Vector3, parent?: string, verdict?: string, reveal: number }>} */
const TREE = [
  { id: "problem", type: "problem", label: "Проблема", pos: new THREE.Vector3(0, 0, 0), reveal: 0.08 },
  { id: "cause1", type: "cause", label: "Причина", pos: new THREE.Vector3(-2.6, 0.9, -0.4), parent: "problem", reveal: 0.18 },
  { id: "ev1", type: "cause_evidence", label: "Доказательство", pos: new THREE.Vector3(-4.1, 1.5, -1.1), parent: "cause1", reveal: 0.26 },
  { id: "method1", type: "method", label: "Метод", pos: new THREE.Vector3(-5.4, 2.1, -1.7), parent: "ev1", verdict: "supported", reveal: 0.34 },
  { id: "cause2", type: "cause", label: "Причина", pos: new THREE.Vector3(2.6, 0.9, 0.4), parent: "problem", reveal: 0.22 },
  { id: "ev2", type: "remediation", label: "Устранение", pos: new THREE.Vector3(4.1, 1.5, 1.1), parent: "cause2", reveal: 0.3 },
  { id: "method2", type: "method", label: "Метод", pos: new THREE.Vector3(5.4, 2.1, 1.7), parent: "ev2", verdict: "open", reveal: 0.38 },
];

const CAMERA_KEYS = [
  { t: 0, pos: new THREE.Vector3(0, 1.8, 11), look: new THREE.Vector3(0, 0, 0) },
  { t: 0.16, pos: new THREE.Vector3(0, 1.2, 7), look: new THREE.Vector3(0, 0.2, 0) },
  { t: 0.36, pos: new THREE.Vector3(-3.8, 2.2, 6.5), look: new THREE.Vector3(-3.5, 1.4, -0.8) },
  { t: 0.48, pos: new THREE.Vector3(-3.2, 2.1, 7.5), look: new THREE.Vector3(-3.5, 1.6, -0.5) },
  { t: 0.58, pos: new THREE.Vector3(-3.0, 2.0, 7.0), look: new THREE.Vector3(-3.5, 1.5, -0.5) },
  { t: 0.68, pos: new THREE.Vector3(0.5, 3.2, 8.5), look: new THREE.Vector3(0, 1.2, 0) },
  { t: 0.78, pos: new THREE.Vector3(4.5, 2.4, 6.5), look: new THREE.Vector3(2.5, 1.2, 0) },
  { t: 0.88, pos: new THREE.Vector3(-4, 2.3, 6.8), look: new THREE.Vector3(-2, 1.1, 0.5) },
  { t: 0.94, pos: new THREE.Vector3(7, 2.2, 5.5), look: new THREE.Vector3(0, 0.5, 0) },
  { t: 1, pos: new THREE.Vector3(0, 1.5, 9.5), look: new THREE.Vector3(0, 0.3, 0) },
];

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function lerpVec(out, a, b, t) {
  out.set(lerp(a.x, b.x, t), lerp(a.y, b.y, t), lerp(a.z, b.z, t));
  return out;
}

function smoothstep(edge0, edge1, x) {
  const t = Math.min(1, Math.max(0, (x - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

function sampleCamera(progress, outPos, outLook) {
  let i = 0;
  while (i < CAMERA_KEYS.length - 2 && progress > CAMERA_KEYS[i + 1].t) i += 1;
  const a = CAMERA_KEYS[i];
  const b = CAMERA_KEYS[Math.min(i + 1, CAMERA_KEYS.length - 1)];
  const localT = b.t === a.t ? 0 : (progress - a.t) / (b.t - a.t);
  const eased = localT * localT * (3 - 2 * localT);
  lerpVec(outPos, a.pos, b.pos, eased);
  lerpVec(outLook, a.look, b.look, eased);
}

function nodeColor(def) {
  if (def.type === "method" && def.verdict === "open") return COLORS.method_open;
  if (def.type === "method") return COLORS.method;
  return COLORS[def.type] ?? 0xffffff;
}

function nodeSize(type) {
  if (type === "problem") return 0.52;
  if (type === "method") return 0.22;
  return 0.3;
}

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function isLowPowerDevice() {
  return window.matchMedia("(max-width: 720px)").matches || navigator.hardwareConcurrency <= 4;
}

export function initTour() {
  const canvas = document.getElementById("tour-canvas");
  const loader = document.getElementById("tour-loader");
  const scrollHint = document.getElementById("tour-scroll-hint");
  const progressBar = document.getElementById("tour-progress");
  const sections = [...document.querySelectorAll(".tour-section")];
  const reduced = prefersReducedMotion();
  const lowPower = isLowPowerDevice();

  if (!canvas) return;

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: !lowPower,
    alpha: true,
    powerPreference: lowPower ? "low-power" : "high-performance",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, lowPower ? 1.25 : 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x06060a, 1);

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x06060a, 0.045);

  const camera = new THREE.PerspectiveCamera(42, window.innerWidth / window.innerHeight, 0.1, 100);
  const camPos = new THREE.Vector3();
  const camLook = new THREE.Vector3();
  const lookTarget = new THREE.Vector3();

  scene.add(new THREE.AmbientLight(0x404060, 0.65));
  const keyLight = new THREE.PointLight(0x3de8ff, 1.4, 30);
  keyLight.position.set(4, 6, 8);
  scene.add(keyLight);
  const fillLight = new THREE.PointLight(0xff6bcb, 0.9, 25);
  fillLight.position.set(-6, 2, 4);
  scene.add(fillLight);

  const nodeMeshes = new Map();
  const lineMeshes = [];

  for (const def of TREE) {
    const size = nodeSize(def.type);
    const geo = new THREE.SphereGeometry(size, lowPower ? 20 : 32, lowPower ? 20 : 32);
    const mat = new THREE.MeshStandardMaterial({
      color: nodeColor(def),
      emissive: nodeColor(def),
      emissiveIntensity: def.type === "problem" ? 0.55 : 0.35,
      metalness: 0.2,
      roughness: 0.35,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(def.pos);
    mesh.scale.setScalar(0.001);
    mesh.userData.def = def;
    scene.add(mesh);
    nodeMeshes.set(def.id, mesh);

    const glowGeo = new THREE.SphereGeometry(size * 1.35, 16, 16);
    const glowMat = new THREE.MeshBasicMaterial({
      color: nodeColor(def),
      transparent: true,
      opacity: 0.12,
      depthWrite: false,
    });
    const glow = new THREE.Mesh(glowGeo, glowMat);
    mesh.add(glow);
  }

  for (const def of TREE) {
    if (!def.parent) continue;
    const parent = TREE.find((n) => n.id === def.parent);
    if (!parent) continue;
    const points = [parent.pos, def.pos];
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    const mat = new THREE.LineBasicMaterial({
      color: COLORS.line,
      transparent: true,
      opacity: 0,
    });
    const line = new THREE.Line(geo, mat);
    line.userData.reveal = def.reveal;
    scene.add(line);
    lineMeshes.push(line);
  }

  const knowledgeGroup = new THREE.Group();
  scene.add(knowledgeGroup);
  const knowledgeOrbs = [];
  for (let i = 0; i < (lowPower ? 24 : 48); i += 1) {
    const orb = new THREE.Mesh(
      new THREE.SphereGeometry(0.05 + Math.random() * 0.04, 8, 8),
      new THREE.MeshBasicMaterial({ color: i % 2 ? COLORS.knowledge : COLORS.cause_evidence, transparent: true, opacity: 0 })
    );
    const angle = (i / 48) * Math.PI * 2;
    const r = 3 + Math.random() * 2;
    orb.userData.home = new THREE.Vector3(Math.cos(angle) * r, 1 + Math.random() * 2, Math.sin(angle) * r);
    orb.userData.phase = Math.random() * Math.PI * 2;
    orb.position.copy(orb.userData.home);
    knowledgeGroup.add(orb);
    knowledgeOrbs.push(orb);
  }

  const knowledgeCore = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.45, 1),
    new THREE.MeshStandardMaterial({
      color: COLORS.knowledge,
      emissive: COLORS.knowledge,
      emissiveIntensity: 0,
      metalness: 0.4,
      roughness: 0.25,
      transparent: true,
      opacity: 0,
    })
  );
  knowledgeCore.position.set(0, 1.2, 0);
  scene.add(knowledgeCore);

  const agentOrb = new THREE.Mesh(
    new THREE.SphereGeometry(0.18, 20, 20),
    new THREE.MeshStandardMaterial({
      color: COLORS.agent,
      emissive: COLORS.agent,
      emissiveIntensity: 0.5,
      metalness: 0.3,
      roughness: 0.3,
    })
  );
  agentOrb.position.set(6, 2, 0);
  agentOrb.scale.setScalar(0.001);
  scene.add(agentOrb);

  const agentTrail = new THREE.Mesh(
    new THREE.TorusGeometry(5.5, 0.012, 8, 96),
    new THREE.MeshBasicMaterial({ color: COLORS.agent, transparent: true, opacity: 0 })
  );
  agentTrail.rotation.x = Math.PI / 2.2;
  agentTrail.position.y = 1;
  scene.add(agentTrail);

  const starsGeo = new THREE.BufferGeometry();
  const starCount = lowPower ? 400 : 900;
  const starPos = new Float32Array(starCount * 3);
  for (let i = 0; i < starCount; i += 1) {
    starPos[i * 3] = (Math.random() - 0.5) * 60;
    starPos[i * 3 + 1] = (Math.random() - 0.5) * 40;
    starPos[i * 3 + 2] = (Math.random() - 0.5) * 60;
  }
  starsGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
  scene.add(
    new THREE.Points(
      starsGeo,
      new THREE.PointsMaterial({ color: 0x8890b8, size: 0.04, transparent: true, opacity: 0.55 })
    )
  );

  let scrollProgress = reduced ? 0.5 : 0;
  let scrollMax = 1;
  const clock = new THREE.Clock();

  function updateScrollMetrics() {
    const doc = document.documentElement;
    scrollMax = Math.max(1, doc.scrollHeight - window.innerHeight);
    scrollProgress = reduced ? 0.5 : doc.scrollTop / scrollMax;
    if (progressBar) progressBar.style.width = `${scrollProgress * 100}%`;
    if (scrollHint) scrollHint.classList.toggle("is-hidden", scrollProgress > 0.06);
  }

  function updateSections() {
    const vh = window.innerHeight;
    sections.forEach((section) => {
      const inner = section.querySelector(".tour-section__inner");
      if (!inner) return;
      const rect = section.getBoundingClientRect();
      const center = rect.top + rect.height * 0.35;
      const visible = 1 - Math.min(1, Math.abs(center - vh * 0.42) / (vh * 0.5));
      const isActive = visible > 0.48;
      inner.classList.toggle("is-active", isActive);
      inner.style.opacity = isActive ? "" : String(lerp(0.35, 0.75, visible));
      inner.style.transform = `translateY(${(1 - visible) * 14}px)`;
    });
  }

  function animate() {
    requestAnimationFrame(animate);
    const t = clock.getElapsedTime();

    sampleCamera(scrollProgress, camPos, camLook);
    const wobbleAmp = lerp(1, 0.15, stageTreeDim(scrollProgress));
    if (!reduced) {
      camPos.x += Math.sin(t * 0.22) * 0.08 * wobbleAmp;
      camPos.y += Math.cos(t * 0.18) * 0.05 * wobbleAmp;
    }
    camera.position.copy(camPos);
    lookTarget.lerp(camLook, 0.08);
    camera.lookAt(lookTarget);

    const treeDim = stageTreeDim(scrollProgress);
    const treeMul = lerp(1, 0.22, treeDim);

    for (const def of TREE) {
      const mesh = nodeMeshes.get(def.id);
      if (!mesh) continue;
      const scale = smoothstep(def.reveal - 0.06, def.reveal + 0.04, scrollProgress);
      const pulse = def.type === "problem" ? 1 + Math.sin(t * 1.6) * 0.04 : 1;
      mesh.scale.setScalar(Math.max(0.001, scale * pulse * treeMul));
    }

    for (const line of lineMeshes) {
      const lineReveal = smoothstep(line.userData.reveal - 0.04, line.userData.reveal + 0.06, scrollProgress);
      line.material.opacity = lineReveal * 0.45 * lerp(1, 0.15, treeDim);
    }

    updateStageUI(scrollProgress);

    const knowT = knowledgeStageVisibility();
    knowledgeCore.material.opacity = knowT * 0.92;
    knowledgeCore.material.emissiveIntensity = knowT * 0.7;
    knowledgeCore.rotation.y = t * 0.35;
    knowledgeCore.rotation.x = Math.sin(t * 0.4) * 0.15;
    for (const orb of knowledgeOrbs) {
      orb.material.opacity = knowT * 0.85;
      const target = new THREE.Vector3(0, 1.2, 0);
      orb.position.lerpVectors(orb.userData.home, target, knowT);
      orb.position.y += Math.sin(t * 1.5 + orb.userData.phase) * 0.04 * knowT;
    }

    const agentT = smoothstep(0.58, 0.66, scrollProgress) * (1 - smoothstep(0.78, 0.86, scrollProgress));
    const agentT2 = smoothstep(0.90, 0.97, scrollProgress);
    const agentOrbT = Math.max(agentT, agentT2);
    agentOrb.scale.setScalar(Math.max(0.001, agentOrbT));
    agentTrail.material.opacity = agentOrbT * 0.35;
    const angle = t * 0.55;
    agentOrb.position.set(Math.cos(angle) * 5.5, 1.8 + Math.sin(t * 0.8) * 0.2, Math.sin(angle) * 5.5);

    renderer.render(scene, camera);
  }

  window.addEventListener("scroll", () => {
    updateScrollMetrics();
    updateSections();
    updateStageUI(scrollProgress);
  }, { passive: true });

  window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    updateScrollMetrics();
    updateSections();
  });

  requestAnimationFrame(() => {
    loader?.classList.add("is-hidden");
    updateScrollMetrics();
    updateSections();
    updateStageUI(scrollProgress);
    animate();
  });
}
