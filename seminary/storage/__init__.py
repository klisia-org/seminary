# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Object-storage seam for large media.

Seminary never imports boto3 or names a cloud provider. When a file is large
enough to be worth offloading (see `routing.should_offload`), the write goes
through `get_storage_backend()`, which resolves whatever app registers
`seminary_storage_backend`. With no storage app installed the resolver returns
`LocalDiskBackend` and every file stays on disk exactly as before — the
supported, and default, deployment.

See `privatedocs/p004-object-storage-for-large-media.md`.
"""

from seminary.storage.backend import (
    LocalDiskBackend,
    StorageBackend,
    get_storage_backend,
    is_offloaded,
    key_from_url,
    object_key,
    url_for_key,
)
from seminary.storage.routing import should_offload

__all__ = [
    "LocalDiskBackend",
    "StorageBackend",
    "get_storage_backend",
    "is_offloaded",
    "key_from_url",
    "limits",
    "object_key",
    "should_offload",
    "url_for_key",
]
