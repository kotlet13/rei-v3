"""Frozen adapter for unmodified upstream LPWM."""
from __future__ import annotations
import hashlib,json,random,sys
from pathlib import Path
def seed_all(seed):
 import numpy as np,torch
 random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
def build(lpwm:Path,cfg:dict,device):
 if str(lpwm) not in sys.path:sys.path.insert(0,str(lpwm))
 from models import DLP
 return DLP(**cfg["architecture"]).to(device)
def state_hash(model):
 h=hashlib.sha256()
 for n,t in sorted(model.state_dict().items()):
  x=t.detach().cpu().contiguous();b=json.dumps({"name":n,"dtype":str(x.dtype),"shape":list(x.shape)},sort_keys=True,separators=(",",":")).encode();h.update(len(b).to_bytes(8,"little"));h.update(b);h.update(x.numpy().tobytes())
 return h.hexdigest()
def call(model,x,loss,recon_loss,deterministic=False):
 return model(x,deterministic=deterministic,warmup=True,with_loss=True,beta_kl=loss["beta_kl"],beta_dyn=loss["beta_dyn"],beta_rec=loss["beta_rec"],kl_balance=loss["kl_balance"],recon_loss_type=loss["reconstruction"],recon_loss_func=recon_loss,beta_dyn_rec=loss["beta_dyn_rec"],num_static=loss["num_static"],beta_obj=loss["beta_obj"],actions=None,actions_mask=None,lang_embed=None,done_mask=None,x_goal=None)
def load_checkpoint(model,path,torch):
 value=torch.load(path,map_location="cpu",weights_only=False)
 for key in ("model","state_dict","model_state_dict"):
  if isinstance(value,dict) and key in value and isinstance(value[key],dict):value=value[key];break
 if not isinstance(value,dict):raise RuntimeError("unsupported official checkpoint container")
 if any(k.startswith("module.") for k in value):value={k.removeprefix("module."):v for k,v in value.items()}
 model.load_state_dict(value,strict=True)
