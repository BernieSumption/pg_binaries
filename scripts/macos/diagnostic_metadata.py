import re


_BUILD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def validate_build_ids(core, vector=None, core_archive_name=None, core_archive_sha256=None):
    core_id = core.get("build_id")
    if not isinstance(core_id, str) or not _BUILD_ID.fullmatch(core_id):
        raise ValueError("archive metadata has missing or invalid core build identifier")
    if vector is None:
        return {"postgresql": core_id}

    vector_id = vector.get("build_id")
    if not isinstance(vector_id, str) or not _BUILD_ID.fullmatch(vector_id):
        raise ValueError("archive metadata has missing or invalid pgvector build identifier")
    if "core_archive" not in vector:
        if vector_id != core_id:
            raise ValueError("combined archive metadata has inconsistent build identifiers")
    else:
        binding = vector["core_archive"]
        if (not isinstance(binding, dict)
                or set(binding) != {"basename", "sha256"}
                or binding.get("basename") != core_archive_name
                or binding.get("sha256") != core_archive_sha256):
            raise ValueError("separate pgvector metadata does not bind the verified core archive")
    return {"postgresql": core_id, "pgvector": vector_id}
