"""Upstream-faithful LPWM constructor, strict load, forward, and rollout calls."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def official_constructor_config(hparams: dict) -> dict:
    """Mirror the pinned upstream train_lpwm.py DLP constructor mapping."""
    source_to_target = {
        "ch": "cdim",
        "context_dist": "ctx_dist",
        "num_static_frames": "n_static_frames",
        "image_goal_condition": "img_goal_condition",
    }
    keys = (
        "ch image_size normalize_rgb n_views n_kp_per_patch patch_size anchor_s n_kp_enc n_kp_prior "
        "pad_mode dropout features_dist learned_feature_dim learned_bg_feature_dim n_fg_categories "
        "n_fg_classes n_bg_categories n_bg_classes scale_std offset_std obj_on_alpha obj_on_beta "
        "obj_res_from_fc obj_ch_mult_prior obj_ch_mult obj_base_ch obj_final_cnn_ch bg_res_from_fc "
        "bg_ch_mult bg_base_ch bg_final_cnn_ch use_resblock num_res_blocks cnn_mid_blocks mlp_hidden_dim "
        "pint_enc_layers pint_enc_heads timestep_horizon num_static_frames predict_delta context_dim "
        "context_dist n_ctx_categories n_ctx_classes ctx_pool_mode pint_dyn_layers pint_dyn_heads pint_dim "
        "pint_ctx_layers pint_ctx_heads action_condition action_dim null_action_embed random_action_condition "
        "random_action_dim language_condition language_embed_dim language_max_len image_goal_condition"
    ).split()
    defaults = {
        "n_views": 1,
        "language_condition": False,
        "language_embed_dim": 0,
        "language_max_len": 64,
        "image_goal_condition": False,
    }
    result = {}
    for source in keys:
        if source in hparams:
            value = hparams[source]
        elif source in defaults:
            value = defaults[source]
        else:
            raise KeyError(f"official hparams missing upstream constructor field: {source}")
        result[source_to_target.get(source, source)] = value
    return result


def build(lpwm_root: Path, constructor: dict, device):
    if str(lpwm_root) not in sys.path:
        sys.path.insert(0, str(lpwm_root))
    from models import DLP

    return DLP(**constructor).to(device)


def strict_load_checkpoint(model, path: Path, torch) -> dict:
    value = torch.load(path, map_location="cpu", weights_only=False)
    container = "root"
    for key in ("model", "state_dict", "model_state_dict"):
        if isinstance(value, dict) and key in value and isinstance(value[key], dict):
            value, container = value[key], key
            break
    if not isinstance(value, dict):
        raise RuntimeError("unsupported official checkpoint container")
    if any(key.startswith("module.") for key in value):
        value = {key.removeprefix("module."): tensor for key, tensor in value.items()}
    loaded = model.load_state_dict(value, strict=True)
    return {
        "container": container,
        "strict": True,
        "missing_keys": list(loaded.missing_keys),
        "unexpected_keys": list(loaded.unexpected_keys),
    }


def state_hash(model) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        value = tensor.detach().cpu().contiguous()
        header = json.dumps(
            {"name": name, "dtype": str(value.dtype), "shape": list(value.shape)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        digest.update(len(header).to_bytes(8, "little"))
        digest.update(header)
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


def inference(model, x):
    return model(
        x,
        deterministic=True,
        warmup=False,
        with_loss=False,
        actions=None,
        actions_mask=None,
        lang_embed=None,
        x_goal=None,
    )


def rollout(model, x):
    return model.sample_from_x(
        x,
        num_steps=15,
        deterministic=True,
        cond_steps=6,
        return_z=True,
        use_all_ctx=False,
        actions=None,
        actions_mask=None,
        lang_embed=None,
        x_goal=None,
        decode=True,
        n_pred_eq_gt=True,
    )
