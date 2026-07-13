"""REI Native Modalities & Ego Composition domain package.

B2 exposes strict contracts only. It does not select providers, execute a
native processor, call a model, or replace the legacy ``rei`` runtime.
"""

from .models.common import PUBLIC_SAFETY_CAVEAT_SL


ARCHITECTURE_ID = "rei-native-modalities-ego-composition"

__all__ = ["ARCHITECTURE_ID", "PUBLIC_SAFETY_CAVEAT_SL"]
