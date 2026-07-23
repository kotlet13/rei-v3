"""Initialize or serve the authenticated, model-free C4 Stage 1 review state.

This daemon owns review secrets and durable consume-once ledgers.  Its built-in
presenter is deliberately fail-closed: the pinned offline HTML host must be
attached in-process before any display acknowledgement can be signed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from rei.evaluation.c4_stage1_review_runtime import (  # noqa: E402
    capture_c4_stage1_review_runtime_manifest,
)
from rei.evaluation.c4_stage1_review_presenter import (  # noqa: E402
    C4Stage1OfflineReviewPresenter,
)
from rei.evaluation.c4_stage1_review_service import (  # noqa: E402
    C4_STAGE1_REVIEW_LOOPBACK_HOST,
    C4Stage1ReviewService,
    C4Stage1ReviewServiceServer,
)


def _absolute(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("C4 Stage 1 paths must be absolute")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=_absolute, required=True)
    parser.add_argument(
        "--artifact-root", type=_absolute, action="append", required=True
    )
    parser.add_argument("--model-root", type=_absolute, action="append", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--readiness-only", action="store_true")
    parser.add_argument("--repository-root", type=_absolute, default=ROOT)
    parser.add_argument("--browser-user-data-dir", type=_absolute)
    parser.add_argument("--runtime-provenance-root", type=_absolute, required=True)
    parser.add_argument("--external-runtime-root", type=_absolute, required=True)
    parser.add_argument("--external-browser-root", type=_absolute, required=True)
    parser.add_argument("--browser-timeout-ms", type=int, default=3_600_000)
    return parser


def _emit(value: object) -> None:
    sys.stdout.write(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    repository_root = arguments.repository_root.resolve(strict=True)
    if repository_root != ROOT.resolve(strict=True):
        raise ValueError(
            "C4 Stage 1 review service must verify the checkout it executes"
        )
    if arguments.browser_user_data_dir is None:
        raise ValueError(
            "Readiness and serving both require a fresh external browser user-data path"
        )
    presenter = C4Stage1OfflineReviewPresenter(
        repository_root=repository_root,
        runtime_manifest=capture_c4_stage1_review_runtime_manifest(repository_root),
        user_data_dir=arguments.browser_user_data_dir,
        runtime_provenance_root=arguments.runtime_provenance_root,
        external_runtime_root=arguments.external_runtime_root,
        external_browser_root=arguments.external_browser_root,
        timeout_ms=arguments.browser_timeout_ms,
    )
    service = C4Stage1ReviewService(
        arguments.state_root,
        artifact_roots=tuple(arguments.artifact_root),
        model_roots=tuple(arguments.model_root),
        presenter=presenter,
        repository_root=repository_root,
    )
    if arguments.readiness_only:
        _emit(
            {
                "readiness": service.readiness.model_dump(mode="json"),
                "health": service.health(),
                "display_presenter_attached": service.health()[
                    "display_presenter_attached"
                ],
            }
        )
        return 0
    with C4Stage1ReviewServiceServer(
        service,
        host=C4_STAGE1_REVIEW_LOOPBACK_HOST,
        port=arguments.port,
    ) as server:
        host, port = server.address
        _emit(
            {
                "readiness": service.readiness.model_dump(mode="json"),
                "health": service.health(),
                "loopback_host": host,
                "loopback_port": port,
                "display_presenter_attached": service.health()[
                    "display_presenter_attached"
                ],
            }
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
