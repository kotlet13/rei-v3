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
  if (filename.endsWith(".json")) return "application/json";
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

function frameRequest(pathName, frame, totalFrames, variant, view = "episode") {
  return { path: pathName, frame, totalFrames, variant, view };
}

async function main() {
  const outputArg = process.argv[2];
  if (!outputArg) throw new Error("usage: node tools/render_preview.mjs OUTPUT_DIRECTORY");
  const output = path.resolve(repo, outputArg);
  const world = await readJson(path.join(root, "specs", "world_manifest.json"));
  const plan = await readJson(path.join(root, "specs", "dataset_plan.json"));
  const phase = await readJson(path.join(root, "specs", "research_phase.json"));
  const preview = plan.splits.find((item) => item.name === "exploration_preview");
  const paths = world.future_paths;
  const edgePath = process.env.REI_CHROMIUM_EXECUTABLE || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
  await fs.access(edgePath);
  await fs.mkdir(output, { recursive: true });
  const { server, port } = await startServer();
  const browser = await chromium.launch({ executablePath: edgePath, headless: true });
  const page = await browser.newPage({ viewport: { width: 512, height: 512 }, deviceScaleFactor: 1 });
  await page.goto(`http://127.0.0.1:${port}/lab/index.html`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => window.vwmReady === true);

  const episodes = [];
  try {
    for (let index = 0; index < preview.episodes; index += 1) {
      const pathName = paths[index % paths.length];
      const variant = Math.floor(index / paths.length);
      const episodeId = opaqueId("ep", { seed: plan.seed, index });
      const evaluatorDir = path.join(output, "evaluator", episodeId);
      const mediaDir = path.join(output, "grounded", episodeId);
      const stageDir = path.join(output, "model_visible_staging", opaqueId("call", { episodeId }));
      const framesDir = path.join(mediaDir, "frames");
      await fs.mkdir(framesDir, { recursive: true });
      await fs.mkdir(evaluatorDir, { recursive: true });
      await fs.mkdir(stageDir, { recursive: true });
      const graphLines = [];
      const frameArtifacts = [];
      for (let frame = 0; frame < world.render.frames_per_episode; frame += 1) {
        const result = await page.evaluate((request) => window.renderVwmFrame(request), frameRequest(pathName, frame, world.render.frames_per_episode, variant));
        const png = Buffer.from(result.pngDataUrl.split(",", 2)[1], "base64");
        const filename = `f_${String(frame).padStart(4, "0")}.png`;
        await fs.writeFile(path.join(framesDir, filename), png);
        graphLines.push(JSON.stringify({ episode_id: episodeId, ...result.evaluatorState }));
        frameArtifacts.push({ index: frame, filename, sha256: sha256(png), width: 128, height: 128 });
      }
      await fs.writeFile(path.join(evaluatorDir, "scene_graph.jsonl"), `${graphLines.join("\n")}\n`, "utf8");
      const videoPath = path.join(mediaDir, "grounded.mp4");
      await run("ffmpeg", ["-y", "-loglevel", "error", "-framerate", String(world.render.fps), "-i", path.join(framesDir, "f_%04d.png"), "-map_metadata", "-1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", videoPath]);
      const video = await fs.readFile(videoPath);
      const observationPath = path.join(stageDir, "i0.mp4");
      await run("ffmpeg", ["-y", "-loglevel", "error", "-framerate", String(world.render.fps), "-i", path.join(framesDir, "f_%04d.png"), "-frames:v", String(plan.conditioning_frames), "-map_metadata", "-1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", observationPath]);
      const observation = await fs.readFile(observationPath);
      const anchorResult = await page.evaluate((request) => window.renderVwmFrame(request), frameRequest(pathName, 0, 1, variant, "self_anchor"));
      const anchor = Buffer.from(anchorResult.pngDataUrl.split(",", 2)[1], "base64");
      const goalResult = await page.evaluate((request) => window.renderVwmFrame(request), frameRequest(pathName, world.render.frames_per_episode - 1, world.render.frames_per_episode, variant));
      const goal = Buffer.from(goalResult.pngDataUrl.split(",", 2)[1], "base64");
      await fs.writeFile(path.join(stageDir, "i1.png"), anchor);
      await fs.writeFile(path.join(stageDir, "i2.png"), goal);
      const call = {
        schema_version: "rei-emocio-vwm-clean-media-call-v1",
        conditioning: "latent_action_image_goal",
        inputs: [
          { slot: "observation", media_type: "video/mp4", path: "i0.mp4", sha256: sha256(observation) },
          { slot: "self_reference", media_type: "image/png", path: "i1.png", sha256: sha256(anchor) },
          { slot: "goal", media_type: "image/png", path: "i2.png", sha256: sha256(goal) }
        ],
        sampling: { samples: 8, stochastic: true }
      };
      await fs.writeFile(path.join(stageDir, "call.json"), `${JSON.stringify(call, null, 2)}\n`, "utf8");
      episodes.push({
        episode_id: episodeId,
        split: "exploration_preview",
        evaluator_path: path.relative(output, path.join(evaluatorDir, "scene_graph.jsonl")).replaceAll("\\", "/"),
        grounded_video: { path: path.relative(output, videoPath).replaceAll("\\", "/"), sha256: sha256(video) },
        grounded_frames: frameArtifacts,
        model_visible_call: path.relative(output, path.join(stageDir, "call.json")).replaceAll("\\", "/"),
        evaluator_only: { path_name: pathName, variant }
      });
    }
    const rerender = await page.evaluate((request) => window.renderVwmFrame(request), frameRequest(paths[0], 0, world.render.frames_per_episode, 0));
    const rerenderHash = sha256(Buffer.from(rerender.pngDataUrl.split(",", 2)[1], "base64"));
    const manifest = {
      schema_version: "rei-emocio-vwm-dataset-manifest-v1",
      phase: "exploration",
      generated_at: phase.reproducible_timestamp,
      generator: { three: "0.185.1", playwright_core: "1.62.1", browser_executable: path.basename(edgePath) },
      world_manifest_sha256: sha256(await fs.readFile(path.join(root, "specs", "world_manifest.json"))),
      dataset_plan_sha256: sha256(await fs.readFile(path.join(root, "specs", "dataset_plan.json"))),
      episodes,
      deterministic_rerender: {
        source_sha256: episodes[0].grounded_frames[0].sha256,
        rerender_sha256: rerenderHash,
        match: episodes[0].grounded_frames[0].sha256 === rerenderHash
      },
      model_invoked: false,
      imagined_artifacts: []
    };
    await fs.writeFile(path.join(output, "dataset_manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
}

await main();
