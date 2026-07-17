from supabase import create_client, Client

from config import settings

_client: Client | None = None


def get_supabase_client() -> Client:
    """Return the singleton Supabase client, creating it on first call.

    Deferred so that importing db.client at module level never causes a
    network call or JWT-validation failure at import time.  All call sites
    that previously referenced the module-level ``supabase_client`` name
    must call this function instead.
    """
    global _client
    if _client is None:
        _client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY,
        )
    return _client


# Backward-compatible alias so existing code using
# ``from db.client import supabase_client`` still works at call time
# (the property is evaluated lazily via __getattr__ on the module).
# Any site that does ``supabase_client.table(...)`` will now call
# get_supabase_client() first.
class _LazyClient:
    """Thin proxy that creates the real client on first attribute access."""
    def __getattr__(self, name):
        return getattr(get_supabase_client(), name)


supabase_client: Client = _LazyClient()  # type: ignore[assignment]
