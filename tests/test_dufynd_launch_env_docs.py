"""Guard DUFYND storefront launch environment documentation."""

from pathlib import Path

ENV_EXAMPLE = Path(".env.example")
DEPLOYMENT_DOC = Path("docs/deployment.md")

REQUIRED_PUBLIC_VARS = {
    "NEXT_PUBLIC_API_URL",
    "NEXT_PUBLIC_SITE_URL",
    "NEXT_PUBLIC_SITE_INDEXABLE",
    "NEXT_PUBLIC_LEGAL_BUSINESS_NAME",
    "NEXT_PUBLIC_LEGAL_OWNER_NAME",
    "NEXT_PUBLIC_LEGAL_STREET",
    "NEXT_PUBLIC_LEGAL_POSTCODE",
    "NEXT_PUBLIC_LEGAL_CITY",
    "NEXT_PUBLIC_LEGAL_EMAIL",
}


def test_env_example_documents_dufynd_storefront_launch_variables() -> None:
    source = ENV_EXAMPLE.read_text(encoding="utf-8")

    for variable in REQUIRED_PUBLIC_VARS:
        assert f"{variable}=" in source

    assert "NEXT_PUBLIC_SITE_INDEXABLE=false" in source


def test_deployment_docs_explain_dufynd_indexing_gate() -> None:
    source = DEPLOYMENT_DOC.read_text(encoding="utf-8")

    for variable in REQUIRED_PUBLIC_VARS:
        assert variable in source

    assert "npm run launch:check -- --strict" in source
    assert "noindex" in source
    assert "robots.txt" in source
