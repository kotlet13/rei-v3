"use strict";

(() => {
  const IPC_PROTOCOL = "rei-c4-stage1-review-ipc-v1";
  const SERVICE_SCHEMA_REVISION = "rei-c4-stage1-review-service-v2";
  const LEDGER_SCHEMA_REVISION = "rei-c4-stage1-review-ledger-v2";
  const OUTPUT_BOOLEAN_FIELDS = Object.freeze([
    "source_subject_present",
    "identity_preserved",
    "unchanged_composition_preserved",
    "option_action_correct",
    "no_extra_actor",
    "no_generated_external_evidence_claim",
    "reviewer_uncertain",
  ]);
  const PAIR_BOOLEAN_FIELDS = Object.freeze([
    "actions_visibly_distinct",
    "same_source_bytes_confirmed",
  ]);
  const PNG_SIGNATURE = Object.freeze([137, 80, 78, 71, 13, 10, 26, 10]);
  const OPAQUE_SLOT = /^slot-[0-9a-f]{64}$/;
  const OPAQUE_SESSION = /^session-[0-9a-f]{64}$/;
  const objectUrls = [];
  let reviewPacket = null;
  let terminalState = false;

  const form = document.getElementById("review-form");
  const status = document.getElementById("review-status");
  const submitButton = document.getElementById("submit-review");
  const cancelButton = document.getElementById("cancel-review");

  function setStatus(message, state = "ready") {
    status.textContent = message;
    status.dataset.state = state;
  }

  function requireRecord(value, expectedKeys, label) {
    if (value === null || typeof value !== "object" || Array.isArray(value) ||
        Object.keys(value).sort().join("\u0000") !== [...expectedKeys].sort().join("\u0000")) {
      throw new TypeError(`${label} has the wrong fields`);
    }
    return value;
  }

  function requireString(value, label, maximumLength = 4096) {
    if (typeof value !== "string" || value.length === 0 || value.length > maximumLength || value.trim() !== value) {
      throw new TypeError(`${label} must be a bounded non-empty string`);
    }
    return value;
  }

  function requireOpaque(value, expression, label) {
    if (typeof value !== "string" || !expression.test(value)) {
      throw new TypeError(`${label} is not a session-scoped opaque value`);
    }
    return value;
  }

  function copyBytes(value, label) {
    let bytes;
    if (value instanceof Uint8Array) {
      bytes = new Uint8Array(value);
    } else if (value instanceof ArrayBuffer) {
      bytes = new Uint8Array(value.slice(0));
    } else if (Array.isArray(value) && value.every((item) => Number.isInteger(item) && item >= 0 && item <= 255)) {
      bytes = Uint8Array.from(value);
    } else {
      throw new TypeError(`${label} must contain blinded PNG bytes`);
    }
    if (bytes.length < PNG_SIGNATURE.length || !PNG_SIGNATURE.every((item, index) => bytes[index] === item)) {
      throw new TypeError(`${label} must contain PNG bytes`);
    }
    return bytes;
  }

  function verifyImage(value, label) {
    const image = requireRecord(value, ["slot", "pngBytes"], label);
    return Object.freeze({
      slot: requireOpaque(image.slot, OPAQUE_SLOT, `${label} slot`),
      pngBytes: copyBytes(image.pngBytes, label),
    });
  }

  function verifyCandidate(value, index) {
    const candidate = requireRecord(value, ["slot", "instruction", "pngBytes"], `Candidate ${index + 1}`);
    return Object.freeze({
      slot: requireOpaque(candidate.slot, OPAQUE_SLOT, `Candidate ${index + 1} slot`),
      instruction: requireString(candidate.instruction, `Candidate ${index + 1} instruction`),
      pngBytes: copyBytes(candidate.pngBytes, `Candidate ${index + 1}`),
    });
  }

  async function opaqueFingerprint(value) {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
    return Array.from(new Uint8Array(digest), (item) => item.toString(16).padStart(2, "0")).join("");
  }

  async function verifyPacket(value) {
    const packet = requireRecord(value, [
      "ipcProtocol",
      "serviceSchemaRevision",
      "ledgerSchemaRevision",
      "sessionToken",
      "referenceSlot",
      "candidateSlots",
    ], "Review packet");
    if (packet.ipcProtocol !== IPC_PROTOCOL || packet.serviceSchemaRevision !== SERVICE_SCHEMA_REVISION || packet.ledgerSchemaRevision !== LEDGER_SCHEMA_REVISION) {
      throw new TypeError("Review packet revisions differ from the pinned runtime");
    }
    const sessionToken = requireOpaque(packet.sessionToken, OPAQUE_SESSION, "Review session");
    const referenceSlot = verifyImage(packet.referenceSlot, "Reference slot");
    const outputs = packet.candidateSlots;
    if (!Array.isArray(outputs) || outputs.length !== 2) {
      throw new TypeError("Review packet must contain exactly two candidate slots");
    }
    const candidateSlots = Object.freeze(outputs.map((item, index) => verifyCandidate(item, index)));
    const slots = [referenceSlot.slot, ...candidateSlots.map((item) => item.slot)];
    const opaqueFingerprints = await Promise.all(slots.map((item) => opaqueFingerprint(item)));
    if (new Set(slots).size !== slots.length || new Set(opaqueFingerprints).size !== slots.length) {
      throw new TypeError("Review packet slots are not unique");
    }
    return Object.freeze({ sessionToken, referenceSlot, candidateSlots });
  }

  function displayImage(elementId, image) {
    const blobUrl = URL.createObjectURL(new Blob([image.pngBytes], { type: "image/png" }));
    objectUrls.push(blobUrl);
    const element = document.getElementById(elementId);
    return new Promise((resolve, reject) => {
      element.addEventListener("load", () => {
        if (element.naturalWidth <= 0 || element.naturalHeight <= 0) {
          reject(new TypeError("A blinded review image decoded without dimensions"));
          return;
        }
        resolve();
      }, { once: true });
      element.addEventListener("error", () => reject(new TypeError("A blinded review image failed to decode")), { once: true });
      element.src = blobUrl;
    });
  }

  async function renderPacket(packet) {
    document.getElementById("source-slot").textContent = packet.referenceSlot.slot;
    const imageLoads = [displayImage("source-image", packet.referenceSlot)];
    packet.candidateSlots.forEach((candidate, index) => {
      document.getElementById(`output-code-${index}`).textContent = candidate.slot;
      document.getElementById(`output-instruction-${index}`).textContent = candidate.instruction;
      imageLoads.push(displayImage(`output-image-${index}`, candidate));
    });
    await Promise.all(imageLoads);
  }

  function selectedBoolean(data, name) {
    const values = data.getAll(name);
    if (values.length !== 1 || (values[0] !== "true" && values[0] !== "false")) {
      throw new TypeError(`Required judgment ${name} is missing`);
    }
    return values[0] === "true";
  }

  function collectSubmission() {
    if (reviewPacket === null) {
      throw new TypeError("Verified review material is unavailable");
    }
    const data = new FormData(form);
    const reviewerPseudonym = requireString(data.get("reviewer_pseudonym"), "Reviewer pseudonym", 200);
    const slotJudgments = reviewPacket.candidateSlots.map((candidate, index) => {
      const judgments = {};
      OUTPUT_BOOLEAN_FIELDS.forEach((field) => {
        judgments[field] = selectedBoolean(data, `outputs.${index}.${field}`);
      });
      return Object.freeze({ slot: candidate.slot, judgments: Object.freeze(judgments) });
    });
    const pairJudgments = {};
    PAIR_BOOLEAN_FIELDS.forEach((field) => {
      pairJudgments[field] = selectedBoolean(data, `pair.${field}`);
    });
    return Object.freeze({
      ipcProtocol: IPC_PROTOCOL,
      sessionToken: reviewPacket.sessionToken,
      reviewerPseudonym,
      slotJudgments: Object.freeze(slotJudgments),
      pairJudgments: Object.freeze(pairJudgments),
    });
  }

  function setControlsDisabled(value) {
    submitButton.disabled = value;
    cancelButton.disabled = value;
  }

  async function initialize() {
    const host = window.reiReviewHost;
    if (host === null || typeof host !== "object" || typeof host.getReviewPacket !== "function" || typeof host.submitReview !== "function" || typeof host.cancelReview !== "function") {
      throw new TypeError("Trusted review host is unavailable");
    }
    const packet = await host.getReviewPacket(Object.freeze({
      ipcProtocol: IPC_PROTOCOL,
      serviceSchemaRevision: SERVICE_SCHEMA_REVISION,
      ledgerSchemaRevision: LEDGER_SCHEMA_REVISION,
    }));
    reviewPacket = await verifyPacket(packet);
    await renderPacket(reviewPacket);
    setControlsDisabled(false);
    setStatus("Verified review material is ready.");
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (terminalState || !form.reportValidity()) {
      return;
    }
    try {
      setControlsDisabled(true);
      setStatus("Submitting sealed review…");
      await window.reiReviewHost.submitReview(collectSubmission());
      terminalState = true;
      setStatus("Sealed review submitted.", "success");
    } catch (error) {
      setControlsDisabled(false);
      setStatus(error instanceof Error ? error.message : "Review submission failed.", "error");
    }
  });

  cancelButton.addEventListener("click", async () => {
    if (terminalState || reviewPacket === null) {
      return;
    }
    try {
      setControlsDisabled(true);
      await window.reiReviewHost.cancelReview(Object.freeze({
        ipcProtocol: IPC_PROTOCOL,
        sessionToken: reviewPacket.sessionToken,
      }));
      terminalState = true;
      setStatus("Review cancelled.", "success");
    } catch (error) {
      setControlsDisabled(false);
      setStatus(error instanceof Error ? error.message : "Review cancellation failed.", "error");
    }
  });

  window.addEventListener("beforeunload", () => {
    objectUrls.forEach((item) => URL.revokeObjectURL(item));
  });

  initialize().catch((error) => {
    setControlsDisabled(true);
    setStatus(error instanceof Error ? error.message : "Review initialization failed.", "error");
  });
})();
