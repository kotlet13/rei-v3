import crypto from "node:crypto";
import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const repo = path.resolve(root, "..", "..");

function sha256(data) {
  return crypto.createHash("sha256").update(data).digest("hex");
}

function opaqueId(kind, value) {
  return `${kind}_${sha256(Buffer.from(JSON.stringify(value))).slice(0, 20)}`;
}

async function readJson(filename) {
  return JSON.parse(await fs.readFile(filename, "utf8"));
}

function contentType(filename) {
  if (filename.endsWith(".html")) return "text/html; charset=utf-8";
  if (filename.endsWith(".js")) return "text/javascript; charset=utf-8";
  return "application/octet-stream";
}

async function startServer() {
  const server = http.createServer(async (request, response) => {
    try {
      const urlPath = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
      const relative = urlPath === "/" ? "lab/index.html" : urlPath.slice(1);
      const target = path.resolve(root, relative);
      if (!target.startsWith(root + path.sep)) throw new Error("path escape");
      const data = await fs.readFile(target);
      response.writeHead(200, { "content-type": contentType(target), "cache-control": "no-store" });
      response.end(data);
    } catch {
      response.writeHead(404);
      response.end();
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return { server, port: server.address().port };
}

function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
    child.on("error", reject);
    child.on("close", (code) => code === 0 ? resolve() : reject(new Error(`${command} failed (${code}): ${stderr}`)));
  });
}

async function encodeVideo({ framesDir, startNumber, frameCount, fps, output }) {
  await run("ffmpeg", [
    "-y", "-loglevel", "error",
    "-framerate", String(fps),
    "-start_number", String(startNumber),
    "-i", path.join(framesDir, "f_%04d.png"),
    "-frames:v", String(frameCount),
    "-map_metadata", "-1",
    "-metadata:s:v:0", "language=und",
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    output,
  ]);
}

function frameRequest(pathName, frame, totalFrames, variant, blockIndex, view = "episode") {
  return { path: pathName, frame, totalFrames, variant, blockIndex, view };
}

async function writeFrame(page, request, target) {
  const result = await page.evaluate((value) => window.renderE1rFrame(value), request);
  const png = Buffer.from(result.pngDataUrl.split(",", 2)[1], "base64");
  await fs.writeFile(target, png);
  return { png, state: result.evaluatorState };
}

async function main() {
  const outputArg = process.argv[2];
  if (!outputArg) throw new Error("usage: node tools/render_e1r.mjs OUTPUT_DIRECTORY");
  const output = path.resolve(repo, outputArg);
  const world = await readJson(path.join(root, "specs", "world_manifest.json"));
  const plan = await readJson(path.join(root, "specs", "dataset_plan.json"));
  const phase = await readJson(path.join(root, "specs", "research_phase.json"));
  const rendererPin = await readJson(path.join(root, "specs", "renderer_pin.json"));
  const paths = world.future_paths;
  const edgePath = process.env[rendererPin.browser.required_environment_variable];
  if (!edgePath) throw new Error(`${rendererPin.browser.required_environment_variable} is required`);
  await fs.access(edgePath);
  const browserSha256 = sha256(await fs.readFile(edgePath));
  if (browserSha256 !== rendererPin.browser.executable_sha256) {
    throw new Error("browser executable SHA-256 differs from renderer pin");
  }
  await fs.mkdir(output, { recursive: true });
  const { server, port } = await startServer();
  const browser = await chromium.launch({
    executablePath: edgePath,
    headless: true,
    args: rendererPin.launch.arguments,
  });
  const page = await browser.newPage({ viewport: { width: 512, height: 512 }, deviceScaleFactor: 1 });
  await page.goto(`http://127.0.0.1:${port}/lab/index.html`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => window.e1rReady === true);
  const episodes = [];

  try {
    for (let index = 0; index < plan.exploration_preview_episodes; index += 1) {
      const pathName = paths[index % paths.length];
      const blockIndex = Math.floor(index / paths.length);
      const variant = blockIndex;
      const episodeId = opaqueId("ep", { protocol: "e1r", seed: plan.seed, index });
      const callId = opaqueId("call", { episodeId });
      const evaluatorDir = path.join(output, "evaluator", episodeId);
      const observedFramesDir = path.join(output, "observed_grounded", episodeId, "frames");
      const counterfactualFramesDir = path.join(output, "authored_counterfactual", episodeId, "frames");
      const goalDir = path.join(output, "authored_goal", episodeId);
      const stageDir = path.join(output, "model_visible_staging", callId);
      await Promise.all([
        fs.mkdir(evaluatorDir, { recursive: true }),
        fs.mkdir(observedFramesDir, { recursive: true }),
        fs.mkdir(counterfactualFramesDir, { recursive: true }),
        fs.mkdir(goalDir, { recursive: true }),
        fs.mkdir(stageDir, { recursive: true }),
      ]);
      const observedStates = [];
      const counterfactualStates = [];
      const observedFrames = [];
      const counterfactualFrames = [];
      for (let frame = 0; frame < world.render.frames_per_episode; frame += 1) {
        const observed = frame < world.render.conditioning_frames;
        const framesDir = observed ? observedFramesDir : counterfactualFramesDir;
        const filename = `f_${String(frame).padStart(4, "0")}.png`;
        const { png, state } = await writeFrame(
          page,
          frameRequest(pathName, frame, world.render.frames_per_episode, variant, blockIndex),
          path.join(framesDir, filename),
        );
        const record = { index: frame, filename, sha256: sha256(png), width: 128, height: 128 };
        if (observed) {
          observedStates.push(JSON.stringify({ episode_id: episodeId, ...state }));
          observedFrames.push(record);
        } else {
          counterfactualStates.push(JSON.stringify({ episode_id: episodeId, ...state }));
          counterfactualFrames.push(record);
        }
      }
      const observedGraph = path.join(evaluatorDir, "observed_grounded.jsonl");
      const counterfactualGraph = path.join(evaluatorDir, "authored_counterfactual.jsonl");
      await fs.writeFile(observedGraph, `${observedStates.join("\n")}\n`, "utf8");
      await fs.writeFile(counterfactualGraph, `${counterfactualStates.join("\n")}\n`, "utf8");
      const observedVideoPath = path.join(output, "observed_grounded", episodeId, "observed.mp4");
      const counterfactualVideoPath = path.join(output, "authored_counterfactual", episodeId, "authored.mp4");
      await encodeVideo({ framesDir: observedFramesDir, startNumber: 0, frameCount: world.render.conditioning_frames, fps: world.render.fps, output: observedVideoPath });
      await encodeVideo({ framesDir: counterfactualFramesDir, startNumber: world.render.conditioning_frames, frameCount: world.render.frames_per_episode - world.render.conditioning_frames, fps: world.render.fps, output: counterfactualVideoPath });
      const observedVideo = await fs.readFile(observedVideoPath);
      const counterfactualVideo = await fs.readFile(counterfactualVideoPath);
      const goalPath = path.join(goalDir, "goal.png");
      const { png: goal, state: goalState } = await writeFrame(
        page,
        frameRequest(pathName, world.render.frames_per_episode - 1, world.render.frames_per_episode, variant, blockIndex, "authored_goal"),
        goalPath,
      );
      await fs.writeFile(path.join(evaluatorDir, "authored_goal.json"), `${JSON.stringify({ episode_id: episodeId, ...goalState }, null, 2)}\n`, "utf8");
      const anchorResult = await page.evaluate(
        (value) => window.renderE1rFrame(value),
        frameRequest(pathName, 0, world.render.frames_per_episode, variant, blockIndex, "self_reference"),
      );
      const anchor = Buffer.from(anchorResult.pngDataUrl.split(",", 2)[1], "base64");
      await fs.writeFile(path.join(stageDir, "i0.mp4"), observedVideo);
      await fs.writeFile(path.join(stageDir, "i1.png"), anchor);
      await fs.writeFile(path.join(stageDir, "i2.png"), goal);
      const call = {
        schema_version: "rei-emocio-vwm-clean-media-call-v2",
        conditioning: "latent_action_image_goal",
        inputs: [
          { slot: "observation", media_type: "video/mp4", path: "i0.mp4", sha256: sha256(observedVideo) },
          { slot: "self_reference", media_type: "image/png", path: "i1.png", sha256: sha256(anchor) },
          { slot: "goal", media_type: "image/png", path: "i2.png", sha256: sha256(goal) },
        ],
        sampling: { samples: 8, stochastic: true },
      };
      await fs.writeFile(path.join(stageDir, "call.json"), `${JSON.stringify(call, null, 2)}\n`, "utf8");
      episodes.push({
        episode_id: episodeId,
        split: "exploration_preview",
        counterbalance_block: `cb${blockIndex}`,
        observed_grounded: {
          source_event_reality_authority: true,
          scene_graph: path.relative(output, observedGraph).replaceAll("\\", "/"),
          video: { path: path.relative(output, observedVideoPath).replaceAll("\\", "/"), sha256: sha256(observedVideo) },
          frames: observedFrames,
        },
        authored_counterfactual: {
          source_event_reality_authority: false,
          scene_graph: path.relative(output, counterfactualGraph).replaceAll("\\", "/"),
          video: { path: path.relative(output, counterfactualVideoPath).replaceAll("\\", "/"), sha256: sha256(counterfactualVideo) },
          frames: counterfactualFrames,
        },
        authored_goal: {
          source_event_reality_authority: false,
          evaluator_state: path.relative(output, path.join(evaluatorDir, "authored_goal.json")).replaceAll("\\", "/"),
          image: { path: path.relative(output, goalPath).replaceAll("\\", "/"), sha256: sha256(goal) },
        },
        imagined_completion: { source_event_reality_authority: false, artifacts: [] },
        model_visible_call: path.relative(output, path.join(stageDir, "call.json")).replaceAll("\\", "/"),
        evaluator_only: { path_name: pathName, camera_variant: variant },
      });
    }
    const manifest = {
      schema_version: "rei-emocio-vwm-dataset-manifest-v2",
      phase: "E1R_protocol_correction",
      generated_at: phase.reproducible_timestamp,
      generator: {
        three: rendererPin.three_version,
        playwright_core: rendererPin.playwright_core_version,
        browser_executable: path.basename(edgePath),
        browser_executable_sha256: browserSha256,
        renderer_pin_sha256: sha256(await fs.readFile(path.join(root, "specs", "renderer_pin.json"))),
        renderer_source_sha256: sha256(await fs.readFile(fileURLToPath(import.meta.url))),
        lab_source_sha256: sha256(await fs.readFile(path.join(root, "lab", "main.js"))),
        launch_arguments: rendererPin.launch.arguments,
        device_scale_factor: rendererPin.render.device_scale_factor,
        color_space: rendererPin.render.color_space,
        antialias: rendererPin.render.antialias,
      },
      world_manifest_sha256: sha256(await fs.readFile(path.join(root, "specs", "world_manifest.json"))),
      dataset_plan_sha256: sha256(await fs.readFile(path.join(root, "specs", "dataset_plan.json"))),
      appearance_role_plan_sha256: sha256(await fs.readFile(path.join(root, "specs", "appearance_role_plan.json"))),
      episodes,
      model_invoked: false,
    };
    await fs.writeFile(path.join(output, "dataset_manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
}

await main();
