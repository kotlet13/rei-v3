import crypto from "node:crypto";
import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const researchRoot = path.resolve(here, "..");
const repoRoot = path.resolve(researchRoot, "..", "..");
const e1rRoot = path.join(repoRoot, "research", "emocio_vwm_mvp_e1r");
const requireFromE1r = createRequire(path.join(e1rRoot, "package.json"));
const { chromium } = requireFromE1r("playwright-core");

const E1R_SOURCE_SHA = "01aa8d3e10c04275e528fd45796d0c4c5bb4ac0b";
const DATASET_SEED = 73013;
const ROUTES = ["public_reclaim", "private_evidence", "no_response"];
const FRAME_COUNT = 24;
const CONDITIONING_FRAMES = 6;
const FPS = 6;

function sha256(data) {
  return crypto.createHash("sha256").update(data).digest("hex");
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
      const target = path.resolve(e1rRoot, relative);
      if (!target.startsWith(e1rRoot + path.sep)) throw new Error("path escape");
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

async function encodeVideo(framesDir, output) {
  await run("ffmpeg", [
    "-y", "-loglevel", "error",
    "-framerate", String(FPS),
    "-start_number", "0",
    "-i", path.join(framesDir, "%06d.png"),
    "-frames:v", String(FRAME_COUNT),
    "-map_metadata", "-1",
    "-metadata:s:v:0", "language=und",
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    output,
  ]);
}

async function writeFrame(page, request, target) {
  const result = await page.evaluate((value) => window.renderE1rFrame(value), request);
  const png = Buffer.from(result.pngDataUrl.split(",", 2)[1], "base64");
  await fs.writeFile(target, png);
  return { png, state: result.evaluatorState };
}

function episodeId(index) {
  return sha256(Buffer.from(JSON.stringify({ schema: "e2-v1", seed: DATASET_SEED, index }))).slice(0, 24);
}

async function main() {
  const outputArg = process.argv[2];
  if (!outputArg) throw new Error("usage: node render_frozen_dataset.mjs ABSOLUTE_OUTPUT_DIRECTORY");
  const output = path.resolve(outputArg);
  if (output === repoRoot || output.startsWith(repoRoot + path.sep)) {
    throw new Error("the frozen training dataset must remain outside the rei-v3 repository");
  }
  try {
    await fs.access(output);
    throw new Error(`refusing to overwrite existing dataset root: ${output}`);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }

  const rendererPinPath = path.join(e1rRoot, "specs", "renderer_pin.json");
  const rendererPin = await readJson(rendererPinPath);
  const browserPath = process.env[rendererPin.browser.required_environment_variable];
  if (!browserPath) throw new Error(`${rendererPin.browser.required_environment_variable} is required`);
  const browserBytes = await fs.readFile(browserPath);
  const browserSha256 = sha256(browserBytes);
  if (browserSha256 !== rendererPin.browser.executable_sha256) {
    throw new Error("browser executable SHA-256 differs from the E1R renderer pin");
  }

  await fs.mkdir(path.join(output, "model_visible"), { recursive: true });
  await fs.mkdir(path.join(output, "evaluator", "episodes"), { recursive: true });
  const { server, port } = await startServer();
  const browser = await chromium.launch({
    executablePath: browserPath,
    headless: true,
    args: rendererPin.launch.arguments,
  });
  const page = await browser.newPage({ viewport: { width: 512, height: 512 }, deviceScaleFactor: 1 });
  await page.goto(`http://127.0.0.1:${port}/lab/index.html`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => window.e1rReady === true);
  const episodes = [];

  try {
    for (let index = 0; index < 12; index += 1) {
      const route = ROUTES[index % ROUTES.length];
      const variant = Math.floor(index / ROUTES.length);
      const id = episodeId(index);
      const frameDir = path.join(output, "model_visible", id);
      await fs.mkdir(frameDir, { recursive: true });
      const frameRecords = [];
      const states = [];
      for (let frame = 0; frame < FRAME_COUNT; frame += 1) {
        const filename = `${String(frame).padStart(6, "0")}.png`;
        const { png, state } = await writeFrame(page, {
          path: route,
          frame,
          totalFrames: FRAME_COUNT,
          variant,
          blockIndex: variant,
          view: "episode",
        }, path.join(frameDir, filename));
        frameRecords.push({
          index: frame,
          path: `model_visible/${id}/${filename}`,
          bytes: png.length,
          sha256: sha256(png),
        });
        states.push({ frame, evidence_class: frame < CONDITIONING_FRAMES ? "observed_grounded" : "authored_counterfactual", state });
      }
      const videoName = "000024.mp4";
      const videoPath = path.join(frameDir, videoName);
      await encodeVideo(frameDir, videoPath);
      const video = await fs.readFile(videoPath);
      const evaluatorPath = path.join(output, "evaluator", "episodes", `${id}.json`);
      const evaluatorRecord = {
        schema_version: "rei-emocio-vwm-e2-evaluator-episode-v1",
        episode_id: id,
        evaluator_only: true,
        route,
        layout_variant: variant,
        source_event_reality_authority: { observed_grounded: true, authored_counterfactual: false },
        terminal_goal_policy: "exact_terminal_frame_of_same_authored_trajectory",
        states,
      };
      await fs.writeFile(evaluatorPath, `${JSON.stringify(evaluatorRecord, null, 2)}\n`, "utf8");
      episodes.push({
        episode_id: id,
        frame_paths: frameRecords,
        video: {
          path: `model_visible/${id}/${videoName}`,
          bytes: video.length,
          sha256: sha256(video),
        },
        observation_prefix_indices: [0, CONDITIONING_FRAMES - 1],
        future_indices: [CONDITIONING_FRAMES, FRAME_COUNT - 1],
        image_goal: {
          path: frameRecords[FRAME_COUNT - 1].path,
          frame_index: FRAME_COUNT - 1,
          sha256: frameRecords[FRAME_COUNT - 1].sha256,
        },
        evaluator_only: {
          route,
          layout_variant: variant,
          record: `evaluator/episodes/${id}.json`,
        },
      });
    }

    const generatorSource = await fs.readFile(fileURLToPath(import.meta.url));
    const manifest = {
      schema_version: "rei-emocio-vwm-e2-dataset-v1",
      reproducible_run_id: sha256(Buffer.from(`${E1R_SOURCE_SHA}:${DATASET_SEED}:e2-v1`)).slice(0, 24),
      source_e1r_sha: E1R_SOURCE_SHA,
      training_mode: "from_scratch",
      episode_count: 12,
      routes_evaluator_only: {
        public_pending: 4,
        private_pending: 4,
        no_response_hold: 4,
      },
      frames_per_episode: FRAME_COUNT,
      conditioning_frames: CONDITIONING_FRAMES,
      width: 128,
      height: 128,
      fps: FPS,
      rgb: true,
      model_visible_root: "model_visible",
      model_visible_content: "visual_media_only",
      evaluator_root: "evaluator",
      generator: {
        source_sha256: sha256(generatorSource),
        e1r_lab_source_sha256: sha256(await fs.readFile(path.join(e1rRoot, "lab", "main.js"))),
        e1r_renderer_pin_sha256: sha256(await fs.readFile(rendererPinPath)),
        browser_product: rendererPin.browser.product,
        browser_version: rendererPin.browser.version,
        browser_executable_sha256: browserSha256,
        three_version: rendererPin.three_version,
        playwright_core_version: rendererPin.playwright_core_version,
        launch_arguments: rendererPin.launch.arguments,
        device_scale_factor: rendererPin.render.device_scale_factor,
        color_space: rendererPin.render.color_space,
        antialias: rendererPin.render.antialias,
      },
      episodes,
    };
    await fs.writeFile(path.join(output, "dataset_manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
}

await main();
