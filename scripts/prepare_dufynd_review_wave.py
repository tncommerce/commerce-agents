"""Bind an explicitly curated review manifest to existing evidence; never publish."""

import json

from scripts.report_dufynd_discovery_release import DATA, evidence_digest


def main():
    path = DATA / "dufynd_release_pilots.json"
    manifest = json.loads(path.read_text())
    facts = {
        f["product_id"]: f
        for f in json.loads((DATA / "dufynd_discovery_qualification.json").read_text())["products"]
    }
    for pilot in manifest["pilots"]:
        # Never rebind an already-reviewed source digest silently.
        if not pilot["evidence_sha256"]:
            pilot["evidence_sha256"] = evidence_digest(facts[pilot["product_id"]])
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
