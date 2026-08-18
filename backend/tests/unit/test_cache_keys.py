from app.cache.keys import embedding_key, exact_query_key


def test_exact_cache_keys_include_tenant_and_differ_across_tenants() -> None:
    kwargs = dict(
        normalized_query="how do retries work",
        filters={},
        llm_model="m",
        embedding_model="e",
        prompt_version="v1",
        index_version="v1",
        retrieval_config="cfg",
    )
    a = exact_query_key(tenant_id="tenant-a", **kwargs)
    b = exact_query_key(tenant_id="tenant-b", **kwargs)
    assert a != b
    assert a.startswith("qexact:tenant-a:")


def test_embedding_key_is_stable() -> None:
    assert embedding_key("hello", "model", "v1") == embedding_key("hello", "model", "v1")
    assert embedding_key("hello", "model", "v1") != embedding_key("hello", "model", "v2")
