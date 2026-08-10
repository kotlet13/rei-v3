"""Frozen construction and call adapter for the unmodified upstream LPWM."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any


def seed_everything(seed: int) -> None:
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def build_model(lpwm_root: Path, config: dict[str, Any], device: object) -> object:
    if str(lpwm_root) not in sys.path:
        sys.path.insert(0, str(lpwm_root))
    from models import DLP

    architecture = dict(config["architecture"])
    return DLP(**architecture).to(device)


def canonical_state_hash(model: object) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        cpu = tensor.detach().cpu().contiguous()
        header = json.dumps(
            {"name": name, "dtype": str(cpu.dtype), "shape": list(cpu.shape)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest.update(len(header).to_bytes(8, "little"))
        digest.update(header)
        digest.update(cpu.numpy().tobytes(order="C"))
    return digest.hexdigest()


def training_call(model: object, sequence: object, goal: object, loss: dict[str, Any]) -> dict[str, Any]:
    return model(
        sequence,
        deterministic=False,
        warmup=False,
        with_loss=True,
        beta_kl=loss["beta_kl"],
        beta_dyn=loss["beta_dyn"],
        beta_rec=loss["beta_rec"],
        kl_balance=loss["kl_balance"],
        recon_loss_type=loss["reconstruction"],
        recon_loss_func=None,
        beta_dyn_rec=loss["beta_dyn_rec"],
        num_static=loss["num_static"],
        beta_obj=loss["beta_obj"],
        actions=None,
        actions_mask=None,
        lang_embed=None,
        done_mask=None,
        x_goal=goal,
    )


def sample_call(model: object, sequence: object, goal: object, *, deterministic: bool) -> tuple[object, dict[str, Any]]:
    return model.sample_from_x(
        sequence,
        num_steps=18,
        deterministic=deterministic,
        cond_steps=6,
        return_z=True,
        use_all_ctx=False,
        actions=None,
        actions_mask=None,
        lang_embed=None,
        x_goal=goal,
        decode=True,
        n_pred_eq_gt=True,
        return_context_posterior=True,
    )


__all__ = ["build_model", "canonical_state_hash", "sample_call", "seed_everything", "training_call"]
