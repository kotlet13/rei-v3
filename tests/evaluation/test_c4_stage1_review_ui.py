from __future__ import annotations

from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

from rei.evaluation.c4_blind_review import (
    C4_OUTPUT_POSITIVE_FIELDS,
    C4_OUTPUT_UNCERTAINTY_FIELD,
    C4_PAIR_POSITIVE_FIELDS,
)
from rei.evaluation.c4_stage1_review_runtime import (
    C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY,
    C4_STAGE1_REVIEW_IPC_PROTOCOL,
    C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
    C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
    capture_c4_stage1_review_runtime_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = ROOT / "app/backend/rei/evaluation/c4_stage1_review_ui"


class _UiParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.inline_script = False
        self._inside_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))
        if tag == "script":
            self._inside_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._inside_script = False

    def handle_data(self, data: str) -> None:
        if self._inside_script and data.strip():
            self.inline_script = True


def _assets() -> tuple[str, str, str]:
    return tuple(
        (UI_ROOT / name).read_text(encoding="utf-8")
        for name in ("index.html", "review.css", "review.js")
    )  # type: ignore[return-value]


def test_ui_has_exact_source_two_blind_outputs_and_instructions() -> None:
    html, _, script = _assets()
    parser = _UiParser()
    parser.feed(html)
    ids = {
        attributes["id"]
        for _, attributes in parser.tags
        if attributes.get("id") is not None
    }

    assert {
        "source-image",
        "source-digest",
        "output-image-0",
        "output-image-1",
        "output-code-0",
        "output-code-1",
        "output-digest-0",
        "output-digest-1",
        "output-instruction-0",
        "output-instruction-1",
    }.issubset(ids)
    images = [attributes for tag, attributes in parser.tags if tag == "img"]
    assert [item["id"] for item in images] == [
        "source-image",
        "output-image-0",
        "output-image-1",
    ]
    assert all("src" not in item for item in images)
    assert "packet.candidateSlots" in script
    assert "blindOrderSha256" not in script
    assert "instructionSha256" not in script
    assert 'crypto.subtle.digest("SHA-256"' in script
    assert 'new Blob([image.pngBytes], { type: "image/png" })' in script


def test_every_review_boolean_is_required_and_has_no_default() -> None:
    html, _, script = _assets()
    parser = _UiParser()
    parser.feed(html)
    groups: dict[str, list[dict[str, str | None]]] = defaultdict(list)
    for tag, attributes in parser.tags:
        if tag == "input" and attributes.get("type") == "radio":
            groups[attributes["name"]].append(attributes)  # type: ignore[index]

    output_fields = (*C4_OUTPUT_POSITIVE_FIELDS, C4_OUTPUT_UNCERTAINTY_FIELD)
    expected = {
        *(f"outputs.{index}.{field}" for index in range(2) for field in output_fields),
        *(f"pair.{field}" for field in C4_PAIR_POSITIVE_FIELDS),
    }
    assert set(groups) == expected
    assert len(groups) == 16
    for controls in groups.values():
        assert len(controls) == 2
        assert {item["value"] for item in controls} == {"true", "false"}
        assert all("required" in item for item in controls)
        assert all("checked" not in item for item in controls)
    assert ".checked" not in script
    assert "form.reportValidity()" in script
    assert "data.getAll(name)" in script


def test_ui_has_explicit_submit_cancel_and_unpopulated_reviewer_identity() -> None:
    html, _, script = _assets()
    parser = _UiParser()
    parser.feed(html)
    controls = {
        attributes.get("id"): (tag, attributes)
        for tag, attributes in parser.tags
        if attributes.get("id") is not None
    }

    submit_tag, submit = controls["submit-review"]
    cancel_tag, cancel = controls["cancel-review"]
    reviewer_tag, reviewer = controls["reviewer-pseudonym"]
    assert (submit_tag, submit["type"]) == ("button", "submit")
    assert (cancel_tag, cancel["type"]) == ("button", "button")
    assert reviewer_tag == "input"
    assert reviewer["name"] == "reviewer_pseudonym"
    assert "required" in reviewer
    assert "value" not in reviewer
    assert ".submitReview(" in script
    assert ".cancelReview(" in script


def test_ui_csp_and_assets_are_strictly_offline() -> None:
    html, css, script = _assets()
    parser = _UiParser()
    parser.feed(html)
    csp = [
        attributes["content"]
        for tag, attributes in parser.tags
        if tag == "meta"
        and attributes.get("http-equiv", "").lower() == "content-security-policy"
    ]
    scripts = [attributes for tag, attributes in parser.tags if tag == "script"]
    stylesheets = [
        attributes
        for tag, attributes in parser.tags
        if tag == "link" and attributes.get("rel") == "stylesheet"
    ]

    assert csp == [C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY]
    assert scripts == [{"src": "review.js", "defer": None}]
    assert stylesheets == [{"rel": "stylesheet", "href": "review.css"}]
    assert parser.inline_script is False
    assert all(
        "style" not in attributes
        and not any(name.startswith("on") for name in attributes)
        for _, attributes in parser.tags
    )
    combined = "\n".join((html, css, script)).lower()
    for token in (
        "http://",
        "https://",
        "fetch(",
        "fetch (",
        "xmlhttprequest",
        "websocket",
        "eventsource",
        "sendbeacon",
        "rtcpeerconnection",
        "localstorage",
        "sessionstorage",
        "indexeddb",
        "document.cookie",
        "window.open(",
    ):
        assert token not in combined
    assert "url(" not in css.lower()
    assert "@import" not in css.lower()


def test_ui_exposes_only_blind_content_and_exact_host_revisions() -> None:
    html, css, script = _assets()
    combined = "\n".join((html, css, script)).lower()
    for token in ("longcat", "omnigen", "meituan", "shitao", "provider", "model"):
        assert token not in combined
    assert C4_STAGE1_REVIEW_IPC_PROTOCOL in script
    assert C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION in script
    assert C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION in script
    assert "window.reiReviewHost" in script
    assert ".getReviewPacket(" in script
    assert "sourceImageSha256" not in script
    assert "packetSha256" not in script
    assert "sessionToken" in script
    assert "candidateSlots" in script


def test_ui_bundle_is_byte_pinned_by_the_runtime_manifest() -> None:
    manifest = capture_c4_stage1_review_runtime_manifest(ROOT.resolve())
    assert manifest.asset_count == 3
    assert manifest.ui_bundle_sha256 == (
        "a6c0a268af2fe35ce9981518f9081a4ed852a93f0b3e45d61fae22c3b0e00b8f"
    )
    assert tuple(Path(item.relative_path).name for item in manifest.assets) == (
        "index.html",
        "review.css",
        "review.js",
    )
