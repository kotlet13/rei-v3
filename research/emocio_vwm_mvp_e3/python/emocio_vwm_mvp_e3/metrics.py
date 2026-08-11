"""Frozen, model-independent E3 objectness metric definitions."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

OBJECTNESS_THRESHOLD=.5
ALPHA_THRESHOLD=.5
MIN_MASK_AREA=8
INSTANCE_OVERLAP_RECALL=.25

@dataclass(frozen=True)
class FrameMetrics:
    active: bool; active_count: int; recall: float; precision: float; person_covered: int; person_total: int; bypass: float

def binary(mask: np.ndarray) -> np.ndarray: return np.asarray(mask)>ALPHA_THRESHOLD
def frame_metrics(objectness: np.ndarray, alpha: np.ndarray, truth_union: np.ndarray, person_masks: list[np.ndarray], full_error: float, background_only_error: float) -> FrameMetrics:
    active=np.asarray(objectness)>OBJECTNESS_THRESHOLD; predicted=np.any(np.asarray(alpha)[active]>ALPHA_THRESHOLD,axis=0) if active.any() else np.zeros_like(truth_union,dtype=bool); truth=binary(truth_union)
    tp=int(np.logical_and(predicted,truth).sum()); pp=int(predicted.sum()); gt=int(truth.sum())
    covered=0; total=0
    for mask in person_masks:
        m=binary(mask); area=int(m.sum())
        if area<MIN_MASK_AREA: continue
        total+=1; covered+=int(np.logical_and(predicted,m).sum()/area>=INSTANCE_OVERLAP_RECALL)
    bypass=0.0 if background_only_error<=0 else (background_only_error-full_error)/background_only_error
    return FrameMetrics(bool(active.any()),int(active.sum()),tp/gt if gt else 1.0,tp/pp if pp else 0.0,covered,total,float(bypass))

def aggregate(frames: list[FrameMetrics]) -> dict[str,float|str]:
    def mean(xs): return float(np.mean(xs)) if xs else 0.0
    coverage=sum(x.person_covered for x in frames)/max(1,sum(x.person_total for x in frames))
    out={"active_particle_frame_rate":mean([x.active for x in frames]),"active_particle_count_mean":mean([x.active_count for x in frames]),"foreground_mask_recall":mean([x.recall for x in frames]),"foreground_mask_precision":mean([x.precision for x in frames]),"person_instance_particle_coverage":coverage,"background_bypass_improvement":mean([x.bypass for x in frames])}
    out["classification"]="collapsed_objectness" if out["active_particle_frame_rate"]<.05 or out["active_particle_count_mean"]<.5 else "active_objectness"
    return out

HARD_GATES={"active_particle_frame_rate":(">=",.95),"active_particle_count_mean":(">=",4.0),"foreground_mask_recall":(">=",.70),"foreground_mask_precision":(">=",.50),"person_instance_particle_coverage":(">=",.75),"background_bypass_improvement":(">=",.15),"foreground_lpips":("<=",.22),"classification":("!=","collapsed_objectness")}

def evaluate_gates(metrics: dict) -> dict:
    result={}
    for key,(op,threshold) in HARD_GATES.items():
        value=metrics[key]; passed=value>=threshold if op==">=" else value<=threshold if op=="<=" else value!=threshold
        result[key]={"value":value,"operator":op,"threshold":threshold,"passed":bool(passed)}
    return result
