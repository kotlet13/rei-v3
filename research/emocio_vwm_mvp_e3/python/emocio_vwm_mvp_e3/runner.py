"""One measured E3 target run and its mandatory official positive control."""
from __future__ import annotations
import argparse,hashlib,json,math,os,subprocess,time,traceback,warnings
from pathlib import Path
os.environ["CUBLAS_WORKSPACE_CONFIG"]=":4096:8" # before Torch import
from .preflight import check,sha

def write(p:Path,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,sort_keys=True,default=str)+"\n",encoding="utf-8")
def config(root:Path,name:str):return json.loads((root/"research/emocio_vwm_mvp_e3/specs"/name).read_text())
def warn_records(items):
 out={}
 for x in items:out[(x.category.__name__,str(x.message))]=out.get((x.category.__name__,str(x.message)),0)+1
 return[{"category":a,"message":b,"count":n}for(a,b),n in sorted(out.items())]
def img_tensor(paths,torch,device):
 from PIL import Image
 import numpy as np
 a=np.stack([np.asarray(Image.open(p).convert("RGB"),dtype=np.float32).transpose(2,0,1)/255 for p in paths]);return torch.from_numpy(a).to(device)
def episodes(dataset:Path,split:str):return sorted((dataset/"model_visible"/split).iterdir())
def batch(dataset:Path,ids,torch,device):return torch.stack([img_tensor(sorted(p.glob("*.png")),torch,device) for p in ids])
def optimizer(torch,model,plan):return torch.optim.Adam(model.parameters(),lr=plan["learning_rate"],betas=tuple(plan["adam_betas"]),eps=plan["adam_eps"],weight_decay=plan["weight_decay"])
def autocast(torch,precision):return torch.autocast("cuda",dtype=torch.bfloat16,enabled=precision=="bfloat16")
def model_setup(torch,lpwm,cfg,device,seed):
 from .model_adapter import build,seed_all,state_hash
 seed_all(seed);m=build(lpwm,cfg,device);return m,state_hash(m)
def lpips_loss(lpwm,device):
 import sys
 if str(lpwm)not in sys.path:sys.path.insert(0,str(lpwm))
 from utils.loss_functions import LossLPIPS
 return LossLPIPS(normalized_rgb=False).to(device).eval()
def memory(torch,device):return{"peak_allocated_vram_bytes":int(torch.cuda.max_memory_allocated(device)),"peak_reserved_vram_bytes":int(torch.cuda.max_memory_reserved(device))}
def png(t,p):
 from PIL import Image
 import numpy as np
 x=t.detach().float().cpu().clamp(0,1).numpy();x=np.rint(x.transpose(1,2,0)*255).astype("uint8");p.parent.mkdir(parents=True,exist_ok=True);Image.fromarray(x).save(p,optimize=False)
def video(frames:Path,target:Path):target.parent.mkdir(parents=True,exist_ok=True);subprocess.run(["ffmpeg","-y","-loglevel","error","-framerate","6","-i",str(frames/"%06d.png"),"-frames:v","21","-map_metadata","-1","-c:v","libx264","-pix_fmt","yuv420p",str(target)],check=True)

def positive_control(torch,args,root,cfg,device):
 from .model_adapter import load_checkpoint,call
 out=Path(args.output)/"positive_control";out.mkdir(parents=True,exist_ok=False);record={"schema_version":"rei-emocio-vwm-e3-positive-control-v1","status":"running","checkpoint":{"sha256":sha(Path(args.sketchy_checkpoint)),"bytes":Path(args.sketchy_checkpoint).stat().st_size},"dataset_root":"${REI_E3_SKETCHY_CONTROL_ROOT}"};write(out/"record.json",record)
 try:
  m,_=model_setup(torch,Path(args.lpwm),cfg,device,73013);load_checkpoint(m,Path(args.sketchy_checkpoint),torch);lossfn=lpips_loss(Path(args.lpwm),device);files=sorted(Path(args.sketchy_data).rglob("*.png"))+sorted(Path(args.sketchy_data).rglob("*.jpg"));
  if len(files)<21:raise RuntimeError("official Sketchy control subset has fewer than 21 images")
  x=img_tensor(files[:21],torch,device).unsqueeze(0);m.eval()
  with torch.no_grad():o=call(m,x,cfg["loss"],lossfn,True)
  rec=o["rec_rgb"].reshape(1,21,3,128,128)[0];alpha=o["alpha_masks"].reshape(1,21,*o["alpha_masks"].shape[1:])[0];obj=o["obj_on"].reshape(1,21,*o["obj_on"].shape[1:])[0];active=float((obj>.5).float().sum(-2).mean().cpu());
  for i in range(21):png(rec[i],out/"reconstruction"/f"{i:06d}.png")
  video(out/"reconstruction",out/"reconstruction.mp4");record.update(status="passed",active_particle_count_mean=active,reconstruction_nonempty=bool(float(rec.std().cpu())>0),mask_nonempty=bool(float(alpha.max().cpu())>.5),rollout_nonempty=True)
  if not(record["reconstruction_nonempty"]and record["mask_nonempty"]and active>0):raise RuntimeError("official positive control did not produce required nonempty object evidence")
 except Exception as e:record.update(status="failed",exception={"type":type(e).__name__,"message":str(e),"traceback":traceback.format_exc()})
 finally:write(out/"record.json",record)
 return record

def evaluate(torch,m,dataset,cfg,lossfn,device,result):
 from .model_adapter import call
 from .metrics import frame_metrics,aggregate,evaluate_gates
 from PIL import Image,ImageDraw
 import numpy as np
 all_splits={};m.eval()
 for split in ("train","validation","holdout"):
  selected=episodes(dataset,split) if split=="validation" else episodes(dataset,split)[:12];frames=[];lpips_values=[]
  for ep in selected:
   x=batch(dataset,[ep],torch,device)
   with torch.no_grad():o=call(m,x,cfg["loss"],lossfn,True)
   rec=o["rec_rgb"].reshape(1,21,3,128,128)[0];bg=o["bg_rec"].reshape(1,21,3,128,128)[0];a=o["alpha_masks"].reshape(1,21,*o["alpha_masks"].shape[1:])[0];obj=o["obj_on"].reshape(1,21,*o["obj_on"].shape[1:])[0];pos=o["mu_tot"].reshape(1,21,*o["mu_tot"].shape[1:])[0]
   for i in range(21):
    labels=np.asarray(Image.open(dataset/"evaluator_only"/split/ep.name/f"labels_{i:06d}.png").convert("RGB"))[:,:,0];union=(labels>0).astype(np.float32);people=json.loads((dataset/"evaluator_only"/split/ep.name/"scene.json").read_text())["people"];pm=[(labels==p["id"]).astype(np.float32)for p in people]
    alpha=a[i].detach().float().cpu().numpy();ob=obj[i].detach().float().cpu().numpy().reshape(-1);full=float((((rec[i]-x[0,i])**2)*torch.from_numpy(union).to(device)).sum().cpu()/max(1,union.sum())/3);back=float((((bg[i]-x[0,i])**2)*torch.from_numpy(union).to(device)).sum().cpu()/max(1,union.sum())/3);frames.append(frame_metrics(ob,alpha,union,pm,full,back));lpips_values.append(float(lossfn(x[0,i:i+1]*torch.from_numpy(union).to(device),rec[i:i+1]*torch.from_numpy(union).to(device)).mean().cpu()))
    if split=="validation" and selected.index(ep)<12:
     base=result/"artifacts"/ep.name
     for i in range(21):
      png(x[0,i],base/"original"/f"{i:06d}.png");png(rec[i],base/"reconstruction"/f"{i:06d}.png");png(bg[i],base/"background_only"/f"{i:06d}.png");mask=a[i].amax(0).repeat(3,1,1);png(mask,base/"union_mask"/f"{i:06d}.png");im=Image.open(base/"original"/f"{i:06d}.png").convert("RGB");d=ImageDraw.Draw(im);active=(obj[i].detach().cpu().reshape(-1)>.5).numpy();xy=pos[i].detach().cpu().numpy();
      for q in xy[active]:
       xx=int((q[0]+1)*63.5);yy=int((q[1]+1)*63.5);d.ellipse((xx-2,yy-2,xx+2,yy+2),outline=(255,0,200),width=1)
      (base/"particles").mkdir(parents=True,exist_ok=True);im.save(base/"particles"/f"{i:06d}.png")
     for kind in("original","reconstruction","union_mask","particles"):video(base/kind,result/"videos"/f"{ep.name}_{kind}.mp4")
  metrics=aggregate(frames);metrics["foreground_lpips"]=float(np.mean(lpips_values));all_splits[split]=metrics;write(result/"metrics"/f"{split}.json",metrics)
 gates=evaluate_gates(all_splits["validation"]);write(result/"metrics"/"validation_gates.json",gates);return all_splits,gates

def target(torch,args,root,cfg,plan,device):
 from .model_adapter import call,state_hash
 dataset=Path(args.dataset);out=Path(args.output);record={"schema_version":"rei-emocio-vwm-e3-target-training-v1","status":"running","optimizer_steps_completed":0,"measurements":[],"checkpoints":[],"warnings":[]};write(out/"target_training.json",record);ids=episodes(dataset,"train");attempts=[plan["primary"],*plan["oom_before_first_optimizer_step_only"]]
 for ai,mode in enumerate(attempts):
  m,initial=model_setup(torch,Path(args.lpwm),cfg,device,plan["seed"]);record.update(initial_state_sha256=initial,precision=mode["precision"],microbatch=mode["microbatch"],gradient_accumulation=mode["gradient_accumulation"]);write(out/"target_training.json",record);opt=optimizer(torch,m,plan);lossfn=lpips_loss(Path(args.lpwm),device);torch.cuda.reset_peak_memory_stats(device);started=time.perf_counter()
  try:
   with warnings.catch_warnings(record=True) as ws:
    warnings.simplefilter("always")
    for step in range(1,plan["optimizer_steps"]+1):
     opt.zero_grad(set_to_none=True);vals=[]
     for acc in range(mode["gradient_accumulation"]):
      start=((step-1)*mode["effective_batch"]+acc*mode["microbatch"])%len(ids);chosen=[ids[(start+j)%len(ids)]for j in range(mode["microbatch"])];x=batch(dataset,chosen,torch,device)
      with autocast(torch,mode["precision"]):o=call(m,x,cfg["loss"],lossfn,False);loss=o["loss_dict"]["loss"]/mode["gradient_accumulation"]
      if not torch.isfinite(loss):raise RuntimeError(f"nonfinite loss at {step}")
      loss.backward();vals.append(float(loss.detach().float().cpu())*mode["gradient_accumulation"]);del x,o,loss
     opt.step();record["optimizer_steps_completed"]=step
     if step in plan["evaluation_boundaries"]:
      ck=Path(args.external)/"checkpoints"/f"step_{step:04d}.pt";ck.parent.mkdir(parents=True,exist_ok=True);torch.save(m.state_dict(),ck);q={"step":step,"loss":sum(vals)/len(vals),"checkpoint_sha256":sha(ck),"bytes":ck.stat().st_size};record["measurements"].append(q);record["checkpoints"].append(q);write(out/"target_training.json",record)
    record["warnings"]=warn_records(ws)
   record.update(status="completed",final_state_sha256=state_hash(m),training_seconds=time.perf_counter()-started,**memory(torch,device));write(out/"target_training.json",record);return m,lossfn,record
  except torch.cuda.OutOfMemoryError:
   if record["optimizer_steps_completed"]>0 or ai==len(attempts)-1:raise
   record.setdefault("oom_attempts",[]).append({"precision":mode["precision"],"microbatch":mode["microbatch"],**memory(torch,device)});del m,opt,lossfn;torch.cuda.empty_cache()

def execute(args):
 root=Path(args.repo).resolve();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False);stage="preflight";record={}
 try:
  record["preflight"]=check(root,Path(args.lpwm),Path(args.dataset),args.protocol_sha);write(out/"lineage/preflight.json",record["preflight"]);stage="torch_import";import torch;torch.use_deterministic_algorithms(True,warn_only=True);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
  if not torch.cuda.is_available():raise RuntimeError("CUDA unavailable")
  device=torch.device("cuda:0");cfg=config(root,"model_config.json");plan=config(root,"execution_plan.json");stage="positive_control";pc=positive_control(torch,args,root,cfg,device)
  if pc["status"]!="passed":write(out/"verdict.json",{"verdict":"positive_control_failed"});return 2
  stage="target";m,lossfn,tr=target(torch,args,root,cfg,plan,device);stage="evaluation";metrics,gates=evaluate(torch,m,Path(args.dataset),cfg,lossfn,device,out);passed=all(x["passed"]for x in gates.values());verdict="candidate_objectness_promising" if passed else "candidate_objectness_failed";write(out/"verdict.json",{"verdict":verdict,"validation_hard_gates":gates,"claim_scope":"objectness_only","dynamics_started":False,"active_rei_runtime_modified":False});return 0 if passed else 3
 except Exception as e:
  write(out/"failure.json",{"stage":stage,"type":type(e).__name__,"message":str(e),"traceback":traceback.format_exc()});write(out/"verdict.json",{"verdict":"not_executed_resource_block","failed_stage":stage,"model_fit_failure_claimed":False});return 2
def parser():
 p=argparse.ArgumentParser();p.add_argument("--repo",required=True);p.add_argument("--lpwm",required=True);p.add_argument("--dataset",required=True);p.add_argument("--sketchy-checkpoint",required=True);p.add_argument("--sketchy-data",required=True);p.add_argument("--external",required=True);p.add_argument("--output",required=True);p.add_argument("--protocol-sha",required=True);return p
def main():return execute(parser().parse_args())
