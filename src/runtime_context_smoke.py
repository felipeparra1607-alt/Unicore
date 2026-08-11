from src.runtime_context import (
    build_runtime_context,
    can_write,
    derive_runtime_context,
    is_path_allowed,
)


def main() -> None:
    base = build_runtime_context()

    assert base.conversation_id.startswith("conv_")
    assert base.job_id is None
    assert base.study_session_id is None
    assert base.allow_writes is False
    assert base.allowed_paths == ()

    derived = derive_runtime_context(
        base,
        job_id="job_test",
    )

    assert derived.conversation_id == base.conversation_id
    assert derived.job_id == "job_test"
    assert derived.study_session_id is None

    writable = build_runtime_context(
        allow_writes=True,
    )

    assert can_write(base) is False
    assert can_write(writable) is True

    restricted = build_runtime_context(
        allowed_paths=["data"],
    )

    assert is_path_allowed(
        restricted,
        "data/unicore.db",
    )

    assert not is_path_allowed(
        restricted,
        "src/server.py",
    )

    print("runtime_context smoke: OK")


if __name__ == "__main__":
    main()