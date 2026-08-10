import * as THREE from "/node_modules/three/build/three.module.js";

const WIDTH = 128;
const HEIGHT = 128;
const renderer = new THREE.WebGLRenderer({
  antialias: false,
  preserveDrawingBuffer: true,
  powerPreference: "low-power",
});
renderer.setSize(WIDTH, HEIGHT, false);
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.setClearColor(0x0b1020, 1);
document.body.appendChild(renderer.domElement);

const roleOrder = [
  "self", "coworker", "leader", "audience_01", "audience_02",
  "audience_03", "audience_04", "audience_05", "audience_06",
];

const appearances = {
  A01: { color: 0xef6a62, signature: "double_band" },
  A02: { color: 0x38bfd2, signature: "square_lapel" },
  A03: { color: 0xe8bd55, signature: "shoulder_bar" },
  A04: { color: 0x8b70d1, signature: "double_band" },
  A05: { color: 0x43ad7b, signature: "square_lapel" },
  A06: { color: 0xd36d9a, signature: "shoulder_bar" },
  A07: { color: 0x5480cf, signature: "head_ring" },
  A08: { color: 0xdf894b, signature: "head_ring" },
  A09: { color: 0x94bf52, signature: "head_ring" },
};

function assignment(blockIndex) {
  return Object.fromEntries(roleOrder.map((role, index) => [
    role,
    `A${String(((index + blockIndex) % 9) + 1).padStart(2, "0")}`,
  ]));
}

function rgbHex(value) {
  return `#${value.toString(16).padStart(6, "0")}`;
}

function lighten(value) {
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;
  const blend = (channel) => Math.round(channel + (255 - channel) * 0.58);
  return (blend(r) << 16) | (blend(g) << 8) | blend(b);
}

function flat(color) {
  return new THREE.MeshBasicMaterial({ color });
}

function shaded(color) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.75, metalness: 0.05 });
}

function addMesh(parent, geometry, material, position, rotation = [0, 0, 0]) {
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(...position);
  mesh.rotation.set(...rotation);
  parent.add(mesh);
  return mesh;
}

function addSignature(group, signature, color) {
  if (signature === "double_band") {
    addMesh(group, new THREE.TorusGeometry(0.105, 0.035, 8, 18), flat(0xffffff), [-0.37, 0.72, 0], [Math.PI / 2, 0, 0]);
    addMesh(group, new THREE.TorusGeometry(0.105, 0.035, 8, 18), flat(0x25304b), [0.37, 0.72, 0], [Math.PI / 2, 0, 0]);
  } else if (signature === "square_lapel") {
    addMesh(group, new THREE.BoxGeometry(0.16, 0.16, 0.06), flat(0xffffff), [0.17, 1.15, 0.26]);
  } else if (signature === "shoulder_bar") {
    addMesh(group, new THREE.BoxGeometry(0.62, 0.08, 0.08), flat(0xffffff), [0, 1.28, 0.23]);
  } else {
    addMesh(group, new THREE.TorusGeometry(0.28, 0.035, 8, 20), flat(color), [0, 1.65, 0], [Math.PI / 2, 0, 0]);
  }
}

function makePerson(role, appearanceId) {
  const spec = appearances[appearanceId];
  const gazeColor = lighten(spec.color);
  const group = new THREE.Group();
  group.userData = { role, appearanceId, bodyColor: spec.color, gazeColor };
  addMesh(group, new THREE.CapsuleGeometry(0.27, 0.58, 4, 10), flat(spec.color), [0, 0.82, 0]);
  addMesh(group, new THREE.SphereGeometry(0.24, 18, 12), shaded(0xd7a98b), [0, 1.62, 0]);
  for (const [name, x] of [["leftArm", -0.35], ["rightArm", 0.35]]) {
    const arm = new THREE.Group();
    arm.name = name;
    arm.position.set(x, 1.16, 0);
    addMesh(arm, new THREE.CylinderGeometry(0.08, 0.1, 0.55, 10), flat(spec.color), [0, -0.25, 0]);
    addMesh(arm, new THREE.SphereGeometry(0.13, 10, 8), shaded(0xd7a98b), [0, -0.56, 0]);
    group.add(arm);
  }
  addSignature(group, spec.signature, spec.color);
  // A large front chest panel plus a face visor, pupils, and nose make the
  // body's forward axis and actual gaze direction readable without consulting
  // the evaluator graph. They rotate with the person rather than billboard.
  addMesh(group, new THREE.BoxGeometry(0.32, 0.34, 0.07), flat(gazeColor), [0, 1.03, 0.275]);
  addMesh(group, new THREE.ConeGeometry(0.115, 0.24, 3), flat(0xffffff), [0, 1.06, 0.325], [Math.PI / 2, 0, 0]);
  addMesh(group, new THREE.BoxGeometry(0.30, 0.10, 0.055), flat(gazeColor), [0, 1.66, 0.225]);
  addMesh(group, new THREE.SphereGeometry(0.045, 8, 6), flat(0x172039), [-0.08, 1.67, 0.265]);
  addMesh(group, new THREE.SphereGeometry(0.045, 8, 6), flat(0x172039), [0.08, 1.67, 0.265]);
  addMesh(group, new THREE.ConeGeometry(0.075, 0.19, 4), flat(gazeColor), [0, 1.57, 0.31], [Math.PI / 2, 0, 0]);
  addMesh(group, new THREE.ConeGeometry(0.13, 0.36, 3), flat(gazeColor), [0, 1.84, 0.20], [Math.PI / 2, 0, 0]);
  return group;
}

function orient(person, target) {
  person.lookAt(target[0], 1.05, target[2]);
}

function gesture(person, kind) {
  const left = person.getObjectByName("leftArm");
  const right = person.getObjectByName("rightArm");
  if (kind === "leader_hold") {
    right.rotation.z = 2.45;
    left.rotation.z = -0.28;
    right.children[1].scale.setScalar(1.45);
  } else if (kind === "present") {
    left.rotation.x = Math.PI * 0.42;
    right.rotation.x = Math.PI * 0.42;
    left.rotation.z = -0.22;
    right.rotation.z = 0.22;
  } else if (kind === "celebrate") {
    left.rotation.z = -2.35;
    right.rotation.z = 2.35;
  } else if (kind === "withdraw") {
    left.rotation.z = 0.32;
    right.rotation.z = -0.32;
    person.scale.y = 0.88;
  }
}

function addLights(scene) {
  scene.add(new THREE.HemisphereLight(0xe8f0ff, 0x28324c, 2.2));
  const key = new THREE.DirectionalLight(0xffffff, 2.8);
  key.position.set(-4, 8, 5);
  scene.add(key);
}

function addMeetingRoom(scene, variant) {
  addMesh(scene, new THREE.BoxGeometry(16, 0.25, 10), shaded(0x26324a), [0, -0.18, 0]);
  addMesh(scene, new THREE.BoxGeometry(16, 5, 0.2), shaded(0x172039), [0, 2.3, -5]);
  addMesh(scene, new THREE.BoxGeometry(4.7, 0.20, 1.45), shaded(0x5f4a3b), [0.1, 0.48, 0.12]);
  for (const x of [-1.7, 1.9]) for (const z of [-0.32, 0.58]) {
    addMesh(scene, new THREE.CylinderGeometry(0.1, 0.1, 1.1, 10), shaded(0x30384a), [x, 0.03, z]);
  }
  const screenX = (variant % 2) * -0.55;
  addMesh(scene, new THREE.BoxGeometry(5.2, 2.75, 0.12), flat(0xe9edf2), [screenX, 2.72, -4.82]);
  addMesh(scene, new THREE.CircleGeometry(0.43, 24), flat(0xc84e4e), [screenX - 1.45, 2.75, -4.74]);
  addMesh(scene, new THREE.BoxGeometry(0.82, 0.82, 0.08), flat(0x2f94a7), [screenX, 2.75, -4.73]);
  addMesh(scene, new THREE.TorusGeometry(0.42, 0.13, 10, 24), flat(0xb48d32), [screenX + 1.48, 2.75, -4.72]);
}

function addOffice(scene, variant) {
  addMesh(scene, new THREE.BoxGeometry(8, 0.25, 8), shaded(0x26324a), [13.5, -0.18, 0]);
  addMesh(scene, new THREE.BoxGeometry(8, 5, 0.2), shaded(0x18243c), [13.5, 2.3, -4]);
  addMesh(scene, new THREE.BoxGeometry(3.2, 0.25, 1.45), shaded(0x684d39), [13.4, 0.7, -0.4]);
  addMesh(scene, new THREE.BoxGeometry(1.1, 1.25, 0.08), flat(0xdbe7f5), [15.8, 2.3, -3.85]);
  if (variant % 2 === 1) addMesh(scene, new THREE.CylinderGeometry(0.32, 0.42, 1.4, 12), shaded(0x426b4a), [10.7, 0.7, -2.8]);
}

function evidenceCard() {
  const card = new THREE.Group();
  addMesh(card, new THREE.BoxGeometry(0.82, 0.56, 0.08), flat(0xc4554e), [0, 0, 0]);
  for (const x of [-0.24, 0, 0.24]) addMesh(card, new THREE.CircleGeometry(0.055, 12), flat(0xffffff), [x, 0, 0.05]);
  return card;
}

function officialMarker() {
  const marker = new THREE.Group();
  addMesh(marker, new THREE.CylinderGeometry(0.29, 0.29, 0.08, 24), flat(0x48d17a), [0, 0, 0], [Math.PI / 2, 0, 0]);
  addMesh(marker, new THREE.TorusGeometry(0.18, 0.045, 8, 20), flat(0xffffff), [0, 0, 0.06]);
  return marker;
}

function pendingMarker() {
  const marker = new THREE.Group();
  addMesh(marker, new THREE.TorusGeometry(0.26, 0.07, 8, 16, Math.PI * 1.55), flat(0xf0ab45), [0, 0, 0]);
  return marker;
}

function meetingPositions(variant) {
  const shift = (variant % 3 - 1) * 0.08;
  return {
    self: [-2.02 + shift, 0, 1.02], coworker: [1.35, 0, -1.68], leader: [-0.88, 0, -1.78],
    audience_01: [-1.92, 0, -0.30], audience_02: [-1.22, 0, 0.35], audience_03: [-0.42, 0, 0.73],
    audience_04: [0.45, 0, 0.76], audience_05: [1.22, 0, 0.36], audience_06: [1.95, 0, -0.32],
  };
}

function setCamera(camera, mode, variant) {
  if (mode === "office") {
    camera.position.set(13.5 + (variant % 2) * 0.18, 3.65, 5.55);
    camera.lookAt(13.5, 1.15, -0.45);
  } else if (mode === "self_reference") {
    camera.position.set(-2.02, 1.65, 3.35);
    camera.lookAt(-2.02, 1.10, 1.02);
  } else {
    camera.position.set(0.08 + (variant % 2) * 0.16, 4.90, 8.05);
    camera.lookAt(0.05, 1.12, -0.42);
  }
}

function addCurrentMarkers(scene, positions, showOfficial = true, showPending = true) {
  if (showOfficial) {
    const official = officialMarker();
    official.position.set(positions.coworker[0], 2.55, positions.coworker[2]);
    scene.add(official);
  }
  if (showPending) {
    const pending = pendingMarker();
    pending.position.set(positions.self[0], 2.5, positions.self[2]);
    scene.add(pending);
  }
}

function buildFrame(request) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b1020);
  addLights(scene);
  const camera = new THREE.PerspectiveCamera(44, WIDTH / HEIGHT, 0.1, 100);
  const frame = request.frame ?? 0;
  const total = request.totalFrames ?? 24;
  const variant = request.variant ?? 0;
  const path = request.path ?? "public_reclaim";
  const view = request.view ?? "episode";
  const blockIndex = request.blockIndex ?? 0;
  const roleAppearance = assignment(blockIndex);
  const authoredGoal = view === "authored_goal";
  const selfReference = view === "self_reference";
  const observed = !authoredGoal && !selfReference && frame < 6;
  const counterfactual = !authoredGoal && !selfReference && frame >= 6;
  const progress = Math.max(0, (frame - 6) / Math.max(1, total - 7));
  const office = (path === "private_evidence" && counterfactual && frame >= 12) || (authoredGoal && path === "private_evidence");
  const visibleRoles = [];
  const pixelIdentities = [];
  let officialVisibleTarget = null;
  let pendingVisibleTarget = null;
  let evidenceVisible = false;

  if (office) {
    addOffice(scene, variant);
    const positions = { self: [12.70, 0, 0.55], leader: [14.35, 0, -1.15] };
    for (const role of ["self", "leader"]) {
      const person = makePerson(role, roleAppearance[role]);
      person.position.set(...positions[role]);
      orient(person, positions[role === "self" ? "leader" : "self"]);
      if (role === "self") gesture(person, "present");
      if (role === "leader") gesture(person, authoredGoal ? "celebrate" : "leader_hold");
      scene.add(person);
      visibleRoles.push(role);
      pixelIdentities.push({ role, appearance_id: roleAppearance[role], body_color: rgbHex(appearances[roleAppearance[role]].color), gaze_color: rgbHex(lighten(appearances[roleAppearance[role]].color)) });
    }
    const card = evidenceCard();
    card.position.set(13.35, 1.55, -0.15);
    card.rotation.x = -0.25;
    scene.add(card);
    evidenceVisible = true;
    if (authoredGoal) {
      const marker = officialMarker();
      marker.position.set(positions.self[0], 2.5, positions.self[2]);
      scene.add(marker);
      officialVisibleTarget = "self";
    } else {
      const pending = pendingMarker();
      pending.position.set(positions.self[0], 2.5, positions.self[2]);
      scene.add(pending);
      pendingVisibleTarget = "self";
    }
  } else {
    addMeetingRoom(scene, variant);
    const positions = meetingPositions(variant);
    const socialProgress = authoredGoal ? 1 : progress;
    for (const role of roleOrder) {
      const person = makePerson(role, roleAppearance[role]);
      const pos = [...positions[role]];
      if ((counterfactual || authoredGoal) && path === "public_reclaim" && role === "self") {
        pos[0] += socialProgress * 2.2;
        pos[2] -= socialProgress * 2.45;
      }
      if (counterfactual && path === "no_response" && role === "self") {
        pos[0] -= progress * 0.38;
        pos[2] += progress * 0.35;
      }
      person.position.set(...pos);
      let target = positions.coworker;
      if ((counterfactual || authoredGoal) && path === "public_reclaim") {
        target = role === "self" ? positions.leader : pos;
        if (role !== "self") target = pos.map((value, index) => index === 0 ? positions.self[0] + socialProgress * 2.2 : (index === 2 ? positions.self[2] - socialProgress * 2.45 : value));
      }
      if (role === "self" && (observed || path === "no_response")) target = positions.coworker;
      orient(person, target);
      if (role === "coworker" && (observed || path === "no_response")) gesture(person, "present");
      if (role === "self" && path === "public_reclaim" && (counterfactual || authoredGoal)) gesture(person, "present");
      if (role === "self" && path === "no_response" && counterfactual) gesture(person, "withdraw");
      if (role === "leader" && path === "public_reclaim" && counterfactual) gesture(person, "leader_hold");
      if (role === "leader" && authoredGoal && path !== "no_response") gesture(person, "celebrate");
      scene.add(person);
      visibleRoles.push(role);
      pixelIdentities.push({ role, appearance_id: roleAppearance[role], body_color: rgbHex(appearances[roleAppearance[role]].color), gaze_color: rgbHex(lighten(appearances[roleAppearance[role]].color)) });
    }
    if ((counterfactual || authoredGoal) && path === "public_reclaim") {
      const card = evidenceCard();
      card.position.set(positions.self[0] + socialProgress * 2.2, 1.40, positions.self[2] - socialProgress * 2.45 + 0.38);
      card.rotation.x = -0.15;
      scene.add(card);
      evidenceVisible = true;
    }
    if (authoredGoal && path !== "no_response") {
      const marker = officialMarker();
      marker.position.set(positions.self[0], 2.5, positions.self[2]);
      scene.add(marker);
      officialVisibleTarget = "self";
    } else {
      addCurrentMarkers(scene, positions, true, true);
      officialVisibleTarget = "coworker";
      pendingVisibleTarget = "self";
    }
  }

  setCamera(camera, selfReference ? "self_reference" : (office ? "office" : "meeting"), variant);
  renderer.render(scene, camera);
  const evidenceClass = selfReference
    ? "observed_grounded"
    : (authoredGoal ? "authored_goal" : (observed ? "observed_grounded" : "authored_counterfactual"));
  return {
    pngDataUrl: renderer.domElement.toDataURL("image/png"),
    evaluatorState: {
      frame,
      evidence_class: evidenceClass,
      source_event_reality_authority: evidenceClass === "observed_grounded",
      may_update_grounded_state: evidenceClass === "observed_grounded",
      room_id: office ? "private_office" : "meeting_room",
      visible_roles: visibleRoles,
      person_count: visibleRoles.length,
      duplicate_role_count: visibleRoles.length - new Set(visibleRoles).size,
      appearance_by_role: roleAppearance,
      pixel_identity_targets: pixelIdentities,
      official_attribution_target: authoredGoal && path !== "no_response" ? "self" : "coworker",
      visible_official_marker_target: officialVisibleTarget,
      visible_pending_marker_target: pendingVisibleTarget,
      evidence_card_visible: evidenceVisible,
      path,
      camera_variant: variant,
      orientation_visible_in_pixels: true
    }
  };
}

window.renderE1rFrame = buildFrame;
window.e1rReady = true;
buildFrame({ path: "public_reclaim", frame: 0, totalFrames: 24, variant: 0, blockIndex: 0 });
