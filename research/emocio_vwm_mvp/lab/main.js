import * as THREE from "/node_modules/three/build/three.module.js";

const WIDTH = 128;
const HEIGHT = 128;
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(WIDTH, HEIGHT, false);
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.setClearColor(0x0b1020, 1);
document.body.appendChild(renderer.domElement);

const palette = {
  coral: 0xf06b62,
  cyan: 0x38c5d9,
  gold: 0xf1c75b,
  violet: 0x8f72d8,
  green: 0x43b581,
  rose: 0xd66f9d,
  blue: 0x5585d8,
  orange: 0xe9904e,
  lime: 0x9acb55,
};

const people = [
  ["person_self", "coral"],
  ["person_coworker", "cyan"],
  ["person_leader", "gold"],
  ["person_audience_01", "violet"],
  ["person_audience_02", "green"],
  ["person_audience_03", "rose"],
  ["person_audience_04", "blue"],
  ["person_audience_05", "orange"],
  ["person_audience_06", "lime"],
];

function material(color, roughness = 0.75) {
  return new THREE.MeshStandardMaterial({ color, roughness, metalness: 0.05 });
}

function addMesh(parent, geometry, mat, position, rotation = [0, 0, 0]) {
  const mesh = new THREE.Mesh(geometry, mat);
  mesh.position.set(...position);
  mesh.rotation.set(...rotation);
  parent.add(mesh);
  return mesh;
}

function makePerson(entityId, paletteName) {
  const group = new THREE.Group();
  group.userData.entityId = entityId;
  const color = palette[paletteName];
  addMesh(group, new THREE.CapsuleGeometry(0.27, 0.58, 4, 10), material(color), [0, 0.82, 0]);
  addMesh(group, new THREE.SphereGeometry(0.24, 18, 12), material(0xd7a98b), [0, 1.62, 0]);
  addMesh(group, new THREE.CylinderGeometry(0.08, 0.1, 0.55, 10), material(color), [-0.35, 0.9, 0], [0, 0, -0.12]);
  addMesh(group, new THREE.CylinderGeometry(0.08, 0.1, 0.55, 10), material(color), [0.35, 0.9, 0], [0, 0, 0.12]);
  if (entityId === "person_self") {
    addMesh(group, new THREE.TorusGeometry(0.105, 0.035, 8, 18), material(0xffffff), [-0.37, 0.72, 0], [Math.PI / 2, 0, 0]);
    addMesh(group, new THREE.TorusGeometry(0.105, 0.035, 8, 18), material(0x25304b), [0.37, 0.72, 0], [Math.PI / 2, 0, 0]);
  } else if (entityId === "person_coworker") {
    addMesh(group, new THREE.BoxGeometry(0.16, 0.16, 0.06), material(0xffffff), [0.17, 1.15, 0.26]);
  } else if (entityId === "person_leader") {
    addMesh(group, new THREE.BoxGeometry(0.62, 0.08, 0.08), material(0xffffff), [0, 1.28, 0.23]);
  } else {
    addMesh(group, new THREE.TorusGeometry(0.28, 0.035, 8, 20), material(color), [0, 1.65, 0], [Math.PI / 2, 0, 0]);
  }
  return group;
}

function addLights(scene) {
  scene.add(new THREE.HemisphereLight(0xe8f0ff, 0x28324c, 2.2));
  const key = new THREE.DirectionalLight(0xffffff, 2.8);
  key.position.set(-4, 8, 5);
  scene.add(key);
}

function addMeetingRoom(scene, variant) {
  addMesh(scene, new THREE.BoxGeometry(16, 0.25, 10), material(0x26324a), [0, -0.18, 0]);
  addMesh(scene, new THREE.BoxGeometry(16, 5, 0.2), material(0x172039), [0, 2.3, -5]);
  addMesh(scene, new THREE.BoxGeometry(5.8, 0.24, 2.4), material(0x5f4a3b), [0.5, 0.55, 0.2]);
  for (const x of [-2.0, 2.9]) for (const z of [-0.55, 0.9]) {
    addMesh(scene, new THREE.CylinderGeometry(0.1, 0.1, 1.1, 10), material(0x30384a), [x, 0.03, z]);
  }
  const screenX = variant % 2 === 0 ? 0 : -0.8;
  addMesh(scene, new THREE.BoxGeometry(5.2, 2.75, 0.12), material(0xe9edf2), [screenX, 2.72, -4.82]);
  addMesh(scene, new THREE.CircleGeometry(0.43, 24), material(0xf06b62), [screenX - 1.45, 2.75, -4.74]);
  addMesh(scene, new THREE.BoxGeometry(0.82, 0.82, 0.08), material(0x38c5d9), [screenX, 2.75, -4.73]);
  addMesh(scene, new THREE.TorusGeometry(0.42, 0.13, 10, 24), material(0xf1c75b), [screenX + 1.48, 2.75, -4.72]);
}

function addOffice(scene, variant) {
  addMesh(scene, new THREE.BoxGeometry(8, 0.25, 8), material(0x26324a), [13.5, -0.18, 0]);
  addMesh(scene, new THREE.BoxGeometry(8, 5, 0.2), material(0x18243c), [13.5, 2.3, -4]);
  addMesh(scene, new THREE.BoxGeometry(3.2, 0.25, 1.45), material(0x684d39), [13.4, 0.7, -0.4]);
  addMesh(scene, new THREE.BoxGeometry(1.1, 1.25, 0.08), material(0xdbe7f5), [15.8, 2.3, -3.85]);
  if (variant % 2 === 1) {
    addMesh(scene, new THREE.CylinderGeometry(0.32, 0.42, 1.4, 12), material(0x426b4a), [10.7, 0.7, -2.8]);
  }
}

function evidenceCard() {
  const card = new THREE.Group();
  addMesh(card, new THREE.BoxGeometry(0.82, 0.56, 0.08), material(0xf06b62), [0, 0, 0]);
  for (const x of [-0.24, 0, 0.24]) addMesh(card, new THREE.CircleGeometry(0.055, 12), material(0xffffff), [x, 0, 0.05]);
  return card;
}

function attributionMarker(kind) {
  const marker = new THREE.Group();
  if (kind === "official") {
    addMesh(marker, new THREE.CylinderGeometry(0.29, 0.29, 0.08, 24), material(0x48d17a), [0, 0, 0], [Math.PI / 2, 0, 0]);
    addMesh(marker, new THREE.TorusGeometry(0.18, 0.045, 8, 20), material(0xffffff), [0, 0, 0.06]);
  } else {
    addMesh(marker, new THREE.TorusGeometry(0.26, 0.07, 8, 16, Math.PI * 1.55), material(0xf0ab45), [0, 0, 0]);
  }
  return marker;
}

function meetingPositions(variant) {
  const shift = (variant % 3 - 1) * 0.22;
  return {
    person_self: [-3.2 + shift, 0, 1.75],
    person_coworker: [2.1, 0, -2.85],
    person_leader: [-0.1, 0, -2.9],
    person_audience_01: [-2.6, 0, -0.5],
    person_audience_02: [-1.25, 0, 0.9],
    person_audience_03: [0.15, 0, 1.4],
    person_audience_04: [1.55, 0, 1.2],
    person_audience_05: [2.95, 0, 0.45],
    person_audience_06: [3.55, 0, -1.05],
  };
}

function setCamera(camera, mode, variant) {
  if (mode === "office") {
    camera.position.set(13.3 + (variant % 2) * 0.4, 4.4, 6.8);
    camera.lookAt(13.5, 1.0, -0.7);
  } else if (mode === "anchor") {
    camera.position.set(-3.2, 1.55, 4.1);
    camera.lookAt(-3.2, 1.05, 1.7);
  } else {
    camera.position.set(0.2 + (variant % 2) * 0.35, 6.9, 9.8);
    camera.lookAt(0, 1.1, -0.5);
  }
}

function buildFrame(request) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b1020);
  addLights(scene);
  const camera = new THREE.PerspectiveCamera(41, WIDTH / HEIGHT, 0.1, 100);
  const frame = request.frame ?? 0;
  const total = request.totalFrames ?? 24;
  const progress = total <= 1 ? 1 : frame / (total - 1);
  const variant = request.variant ?? 0;
  const path = request.path ?? "public_reclaim";
  const anchor = request.view === "self_anchor";
  const office = path === "private_evidence" && progress >= 0.46 && !anchor;
  const visible = [];
  let markerTarget = "person_coworker";

  if (office) {
    addOffice(scene, variant);
    const positions = {
      person_self: [12.15, 0, 0.7],
      person_leader: [14.8, 0, -1.35],
    };
    for (const [entityId, paletteName] of people.slice(0, 3)) {
      if (!(entityId in positions)) continue;
      const person = makePerson(entityId, paletteName);
      person.position.set(...positions[entityId]);
      if (entityId === "person_self") person.position.x += Math.min(1.0, Math.max(0, progress - 0.5) * 2.0);
      scene.add(person);
      visible.push(entityId);
    }
    const card = evidenceCard();
    card.position.set(13.25, 1.55, -0.2);
    card.rotation.x = -0.25;
    scene.add(card);
    if (progress > 0.78) markerTarget = "person_self";
    const marker = attributionMarker(progress > 0.78 ? "official" : "pending");
    marker.position.set(progress > 0.78 ? 13.1 : 12.15, 2.4, progress > 0.78 ? 0.7 : 0.6);
    scene.add(marker);
  } else {
    addMeetingRoom(scene, variant);
    const positions = meetingPositions(variant);
    for (const [entityId, paletteName] of people) {
      const person = makePerson(entityId, paletteName);
      const pos = [...positions[entityId]];
      if (path === "public_reclaim" && entityId === "person_self") {
        pos[0] += Math.max(0, progress - 0.35) * 4.2;
        pos[2] -= Math.max(0, progress - 0.35) * 4.3;
      }
      person.position.set(...pos);
      scene.add(person);
      visible.push(entityId);
    }
    if (progress > 0.43 && path === "public_reclaim") {
      const card = evidenceCard();
      card.position.set(-0.7 + Math.max(0, progress - 0.45) * 1.1, 2.15, -2.35);
      card.rotation.x = -0.15;
      scene.add(card);
    }
    if (path === "public_reclaim" && progress > 0.77) markerTarget = "person_self";
    const targetPosition = markerTarget === "person_self"
      ? [-0.45, 2.7, -2.2]
      : [2.1, 2.7, -2.85];
    const marker = attributionMarker(path === "no_response" || progress < 0.77 ? "pending" : "official");
    marker.position.set(...targetPosition);
    scene.add(marker);
  }

  setCamera(camera, anchor ? "anchor" : (office ? "office" : "meeting"), variant);
  renderer.render(scene, camera);
  return {
    pngDataUrl: renderer.domElement.toDataURL("image/png"),
    evaluatorState: {
      frame,
      room_id: office ? "private_office" : "meeting_room",
      visible_entity_ids: visible,
      person_count: visible.length,
      duplicate_entity_ids: visible.length - new Set(visible).size,
      attribution_marker_target: markerTarget,
      evidence_card_visible: (office || (path === "public_reclaim" && progress > 0.43)),
      path,
      reality: "grounded_lab_reference"
    }
  };
}

window.renderVwmFrame = buildFrame;
window.vwmReady = true;
buildFrame({ path: "public_reclaim", frame: 0, totalFrames: 24, variant: 0 });
