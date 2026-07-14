from __future__ import annotations

from app.backend.rei.contract_loader import get_processor_contract


SCENARIO = "I do not want to attend the meeting."


def test_same_behavior_can_have_three_processor_origins() -> None:
    """This is a semantic guard for Codex and future prompt work.

    The visible behavior is identical. The origin must not be collapsed to one processor.
    """
    racio_origin = {
        "processor": "racio",
        "origin": "low utility, poor timing, bad evidence, inefficient sequence, or lack of controllable outcome",
    }
    emocio_origin = {
        "processor": "emocio",
        "origin": "humiliation, dead scene, broken desired image, lack of recognition, or status wound",
    }
    instinkt_origin = {
        "processor": "instinkt",
        "origin": "distrust, exposure, body alarm, boundary issue, attachment/loss risk, or missing safety condition",
    }

    assert SCENARIO
    assert racio_origin["origin"] != emocio_origin["origin"]
    assert emocio_origin["origin"] != instinkt_origin["origin"]
    assert instinkt_origin["origin"] != racio_origin["origin"]


def test_contracts_do_not_reduce_minds_to_popular_terms() -> None:
    racio = get_processor_contract("racio")
    emocio = get_processor_contract("emocio")
    instinkt = get_processor_contract("instinkt")

    assert "objective truth" not in racio["canonical_summary"].lower()
    assert "not generic emotion or empathy" in emocio["canonical_summary"].lower()
    assert "not know images, words, and numbers" in instinkt["canonical_summary"].lower()
