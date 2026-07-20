"""REI Native Modalities & Ego Composition package through B11 orchestration."""

from .models.common import PUBLIC_SAFETY_CAVEAT_EN, PUBLIC_SAFETY_CAVEAT_SL


ARCHITECTURE_ID = "rei-native-modalities-ego-composition"
COMMUNICATION_RUNTIME_ID = "rei-native-communication-b9"
CONSCIOUS_RUNTIME_ID = "rei-native-conscious-behavior-b10"
ENGINE_RUNTIME_ID = "rei-native-engine-b11"
PUBLIC_SAFETY_CAVEAT = PUBLIC_SAFETY_CAVEAT_EN

__all__ = [
    "ARCHITECTURE_ID",
    "COMMUNICATION_RUNTIME_ID",
    "CONSCIOUS_RUNTIME_ID",
    "ENGINE_RUNTIME_ID",
    "PUBLIC_SAFETY_CAVEAT",
    "PUBLIC_SAFETY_CAVEAT_EN",
    "PUBLIC_SAFETY_CAVEAT_SL",
]
