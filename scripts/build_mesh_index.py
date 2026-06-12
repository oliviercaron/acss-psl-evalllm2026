"""Build MeSH lookup index from raw XML data.

Parses desc2026.xml (descriptors) and supp2026.xml (supplementary concepts)
to create term -> descriptor/concept mappings for entity linking.

Output: data/processed/mesh_index.pkl
"""

import json
import pickle
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text.strip().lower())
    t = t.replace("‘", "'").replace("’", "'")
    t = t.replace(chr(0x201C), chr(0x22)).replace(chr(0x201D), chr(0x22))
    return t

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "mesh"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

DESC_XML = RAW_DIR / "desc2026.xml"
SUPP_XML = RAW_DIR / "supp2026.xml"


def parse_descriptors(xml_path: Path) -> dict:
    """Parse descriptor XML using iterparse to handle large files.

    Returns {descriptor_ui: {
        "name": preferred_name,
        "concepts": [{
            "ui": concept_ui,
            "name": concept_name,
            "preferred": bool,
            "terms": [term_strings]
        }]
    }}
    """
    descriptors = {}

    print(f"  Parsing {xml_path.name}...")
    for event, elem in ET.iterparse(str(xml_path), events=("end",)):
        if elem.tag != "DescriptorRecord":
            continue

        dui = elem.findtext("DescriptorUI", "")
        dname = elem.findtext("DescriptorName/String", "")

        concepts = []
        for concept in elem.iter("Concept"):
            cui = concept.findtext("ConceptUI", "")
            cname = concept.findtext("ConceptName/String", "")
            preferred = concept.get("PreferredConceptYN", "N") == "Y"

            terms = []
            for term in concept.iter("Term"):
                tstr = term.findtext("String", "")
                if tstr:
                    terms.append(tstr)

            concepts.append({
                "ui": cui,
                "name": cname,
                "preferred": preferred,
                "terms": terms,
            })

        descriptors[dui] = {"name": dname, "concepts": concepts}
        elem.clear()

    return descriptors


def parse_supplementals(xml_path: Path) -> dict:
    """Parse supplementary concept XML.

    Returns {supp_ui: {
        "name": preferred_name,
        "concepts": [{ui, name, preferred, terms}],
        "mapped_to": [descriptor_uis]
    }}
    """
    supplementals = {}

    print(f"  Parsing {xml_path.name}...")
    for event, elem in ET.iterparse(str(xml_path), events=("end",)):
        if elem.tag != "SupplementalRecord":
            continue

        sui = elem.findtext("SupplementalRecordUI", "")
        sname = elem.findtext("SupplementalRecordName/String", "")

        concepts = []
        for concept in elem.iter("Concept"):
            cui = concept.findtext("ConceptUI", "")
            cname = concept.findtext("ConceptName/String", "")
            preferred = concept.get("PreferredConceptYN", "N") == "Y"

            terms = []
            for term in concept.iter("Term"):
                tstr = term.findtext("String", "")
                if tstr:
                    terms.append(tstr)

            concepts.append({
                "ui": cui,
                "name": cname,
                "preferred": preferred,
                "terms": terms,
            })

        mapped_to = []
        for heading in elem.iter("HeadingMappedTo"):
            dui_elem = heading.find(".//DescriptorReferredTo/DescriptorUI")
            if dui_elem is not None and dui_elem.text:
                mapped_to.append(dui_elem.text.strip("*"))

        supplementals[sui] = {
            "name": sname,
            "concepts": concepts,
            "mapped_to": mapped_to,
        }
        elem.clear()

    return supplementals


def build_term_index(descriptors: dict, supplementals: dict) -> dict:
    """Build lowercase term -> list of {descriptor_ui, concept_ui, name} mapping.

    Indexes all terms from both descriptors and supplementary concepts.
    """
    index = defaultdict(list)

    for dui, desc in descriptors.items():
        for concept in desc["concepts"]:
            entry = {
                "dui": dui,
                "cui": concept["ui"],
                "desc_name": desc["name"],
                "concept_name": concept["name"],
                "preferred": concept["preferred"],
                "type": "descriptor",
            }
            for term in concept["terms"]:
                index[normalize(term)].append(entry)

    for sui, supp in supplementals.items():
        for concept in supp["concepts"]:
            entry = {
                "sui": sui,
                "cui": concept["ui"],
                "supp_name": supp["name"],
                "concept_name": concept["name"],
                "preferred": concept["preferred"],
                "mapped_to": supp["mapped_to"],
                "type": "supplemental",
            }
            for term in concept["terms"]:
                index[normalize(term)].append(entry)

    return dict(index)


def build_concept_to_descriptor(descriptors: dict) -> dict:
    """Build concept_ui (M-prefix) -> descriptor_ui mapping."""
    mapping = {}
    for dui, desc in descriptors.items():
        for concept in desc["concepts"]:
            mapping[concept["ui"]] = dui
    return mapping


def build_supp_to_descriptors(supplementals: dict) -> dict:
    """Build supplemental_ui (C-prefix) -> [descriptor_uis] mapping.

    In the challenge id_kb format, C-prefixed IDs after ':' are
    SupplementalRecordUIs that refine the main descriptor.
    """
    mapping = {}
    for sui, supp in supplementals.items():
        mapping[sui] = supp["mapped_to"]
    return mapping


def main():
    print("Building MeSH index...")

    descriptors = parse_descriptors(DESC_XML)
    print(f"  -> {len(descriptors):,} descriptors loaded")

    supplementals = parse_supplementals(SUPP_XML)
    print(f"  -> {len(supplementals):,} supplementary concepts loaded")

    print("Building term index...")
    term_index = build_term_index(descriptors, supplementals)
    print(f"  -> {len(term_index):,} unique term keys")

    concept_map = build_concept_to_descriptor(descriptors)
    print(f"  -> {len(concept_map):,} concept->descriptor mappings (M-prefix)")

    supp_map = build_supp_to_descriptors(supplementals)
    print(f"  -> {len(supp_map):,} supplemental->descriptor mappings (C-prefix)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    out_path = OUT_DIR / "mesh_index.pkl"
    with open(out_path, "wb") as f:
        pickle.dump(
            {
                "descriptors": descriptors,
                "supplementals": supplementals,
                "by_term": term_index,
                "concept_to_descriptor": concept_map,
                "supp_to_descriptors": supp_map,
            },
            f,
            protocol=pickle.HIGHEST_PROTOCOL,
        )

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Saved to {out_path} ({size_mb:.1f} MB)")

    train_path = Path(__file__).resolve().parent.parent / "data" / "protected" / "train_evalLLM.json"
    if not train_path.exists():
        print("\nSkipping training verification (train_evalLLM.json not found).")
        return
    print("\nVerification with training data...")
    with open(train_path, encoding="utf-8") as f:
        train = json.load(f)

    found_desc, found_concept, total = 0, 0, 0
    missing = []
    for doc in train:
        for ent in doc.get("entities", []):
            if ent["source"] != "MeSH":
                continue
            total += 1

            id_kb = ent["id_kb"]
            if ":" in id_kb:
                dui = id_kb.split(":")[0].strip()
                if "&" in dui:
                    duis = [d.strip() for d in dui.split("&")]
                else:
                    duis = [dui]
            elif "&" in id_kb:
                duis = [d.strip() for d in id_kb.split("&")]
            else:
                duis = [id_kb]

            all_found = all(d in descriptors for d in duis)
            if all_found:
                found_desc += 1
            else:
                missing.append((ent["text"], id_kb))

            if ":" in id_kb:
                concepts_str = id_kb.split(":", 1)[1]
                concept_ids = [c.strip() for c in concepts_str.split("|") if c.strip()]
                c_found = sum(1 for c in concept_ids if c in supp_map)
                if c_found == len(concept_ids):
                    found_concept += 1
                else:
                    for c in concept_ids:
                        if c not in supp_map:
                            missing.append((ent["text"], f"supp:{c}"))

    concepts_total = sum(
        1 for doc in train for ent in doc["entities"]
        if ent["source"] == "MeSH" and ":" in ent["id_kb"]
    )

    print(f"  Descriptor resolution: {found_desc}/{total} found")
    print(f"  Supplemental concept resolution: {found_concept}/{concepts_total} with-concept entries found")
    if missing:
        unique_missing = list(set(missing))[:10]
        print(f"  Sample missing: {unique_missing}")


if __name__ == "__main__":
    main()
