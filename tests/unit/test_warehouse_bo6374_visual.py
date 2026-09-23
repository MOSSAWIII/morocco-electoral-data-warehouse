from __future__ import annotations

import json
from pathlib import Path

from morocco_elections.warehouse.bo6374 import validate_visual_candidate


ROOT = Path(__file__).resolve().parents[2]


def test_page6105_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6105_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [12, 5, 22, 7]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 46
    assert payload["groups"][0]["rows"][0] == {"row": 1, "commune_name_ar": "طنجة", "council_members": 81}
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)
    assert validate_visual_candidate({**payload, "source_sha256": "0" * 64}, source)
    first_group = {**payload["groups"][0], "rows": [{**payload["groups"][0]["rows"][0], "official_council_id": "FAKE"}, *payload["groups"][0]["rows"][1:]]}
    assert validate_visual_candidate({**payload, "groups": [first_group, *payload["groups"][1:]]}, source)


def test_page6106_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6106_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [19, 29]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 48
    assert payload["groups"][0]["rows"][0] == {"row": 1, "commune_name_ar": "القصر الكبير", "council_members": 35}
    assert payload["groups"][1]["rows"][0] == {"row": 20, "commune_name_ar": "الحسيمة", "council_members": 31}
    assert validate_visual_candidate({**payload, "status": "OFFICIAL_COMPLETE"}, source)


def test_page6107_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6107_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [7, 28, 17]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 52
    assert payload["groups"][0]["prefecture_province_ar"] == "الحسيمة (تابع)"
    assert payload["groups"][2]["rows"][0] == {"row": 36, "commune_name_ar": "وزان", "council_members": 31}
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6108_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6108_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [11, 23, 23]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 57
    assert payload["groups"][0]["rows"][0] == {"row": 1, "commune_name_ar": "وجدة", "council_members": 61}
    assert payload["groups"][1]["rows"][0] == {"row": 12, "commune_name_ar": "الناظور", "council_members": 39}
    assert validate_visual_candidate({**payload, "source_sha256": "0" * 64}, source)


def test_page6109_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6109_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [14, 16, 14, 10]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 54
    assert payload["groups"][0]["rows"][0] == {"row": 1, "commune_name_ar": "جرادة", "council_members": 25}
    assert payload["groups"][3]["rows"][-1] == {"row": 54, "commune_name_ar": "مزكيتام", "council_members": 13}
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6110_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6110_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [13, 5, 21, 16]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 55
    assert payload["groups"][1]["rows"][0] == {"row": 14, "commune_name_ar": "فاس", "council_members": 91}
    assert payload["groups"][3]["rows"][-1] == {"row": 55, "commune_name_ar": "راس إيجيري", "council_members": 11}
    assert validate_visual_candidate({**payload, "status": "OFFICIAL_COMPLETE"}, source)


def test_page6111_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6111_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [10, 11, 23]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 44
    assert payload["groups"][0]["rows"][0] == {"row": 1, "commune_name_ar": "أزرو", "council_members": 31}
    assert payload["groups"][2]["rows"][-1] == {"row": 44, "commune_name_ar": "آيت السبع لجروف", "council_members": 23}
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6112_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6112_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [21, 32]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 53
    assert payload["groups"][0]["rows"][0] == {"row": 1, "commune_name_ar": "بولمان", "council_members": 11}
    assert payload["groups"][1]["rows"][-1] == {"row": 53, "commune_name_ar": "الخلالفة", "council_members": 15}
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6113_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6113_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [17, 38]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 55
    assert payload["groups"][0]["prefecture_province_ar"] == "تاونات (تابع)"
    assert payload["groups"][1]["rows"][0] == {"row": 18, "commune_name_ar": "تازة", "council_members": 35}
    assert validate_visual_candidate({**payload, "status": "OFFICIAL_COMPLETE"}, source)


def test_page6114_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6114_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [2, 4, 10, 23, 20]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 59
    assert payload["groups"][0]["rows"][0] == {"row": 1, "commune_name_ar": "الرباط", "council_members": 81}
    assert payload["groups"][4]["rows"][-1] == {"row": 59, "commune_name_ar": "تيداس", "council_members": 13}
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6115_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6115_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [15, 29]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 44
    assert payload["groups"][0]["prefecture_province_ar"] == "الخميسات (تابع)"
    assert payload["groups"][1]["rows"][0] == {"row": 16, "commune_name_ar": "سيدي قاسم", "council_members": 31}
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6116_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6116_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [11, 22, 19]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 52
    assert payload["groups"][0]["rows"][0] == {"row": 1, "commune_name_ar": "سيدي سليمان", "council_members": 31}
    assert payload["groups"][2]["rows"][0] == {"row": 34, "commune_name_ar": "أزيلال", "council_members": 25}
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6117_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6117_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [25, 16]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 41
    assert payload["groups"][0]["prefecture_province_ar"] == "أزيلال (تابع)"
    assert payload["groups"][1]["rows"][0] == {"row": 26, "commune_name_ar": "الفقيه بن صالح", "council_members": 35}
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6118_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6118_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [22, 31]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 53
    assert payload["groups"][0]["rows"][0] == {"row": 1, "commune_name_ar": "خنيفرة", "council_members": 35}
    assert payload["groups"][1]["rows"][0] == {"row": 23, "commune_name_ar": "خريبكة", "council_members": 39}
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6119_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6119_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [2, 6, 27, 5, 5]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 45
    assert payload["groups"][0]["rows"] == [
        {"row": 1, "commune_name_ar": "الدار البيضاء", "council_members": 131},
        {"row": 2, "commune_name_ar": "مشور الدار البيضاء", "council_members": 9},
    ]
    assert payload["groups"][-1]["rows"][-1] == {
        "row": 45,
        "commune_name_ar": "المجاطية أولاد الطالب",
        "council_members": 25,
    }
    assert validate_visual_candidate({**payload, "status": "OFFICIAL_COMPLETE"}, source)


def test_page6120_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6120_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [15, 22]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 37
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "بنسليمان",
        "council_members": 31,
    }
    assert payload["groups"][-1]["rows"][-1] == {
        "row": 37,
        "commune_name_ar": "أولاد زيدان",
        "council_members": 11,
    }
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6121_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6121_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [46]
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "سطات",
        "council_members": 35,
    }
    assert payload["groups"][0]["rows"][-1] == {
        "row": 46,
        "commune_name_ar": "كدانة",
        "council_members": 13,
    }
    assert validate_visual_candidate({**payload, "status": "OFFICIAL_COMPLETE"}, source)


def test_page6122_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6122_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [25, 15]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 40
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "سيدي بنور",
        "council_members": 31,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 26,
        "commune_name_ar": "مراكش",
        "council_members": 81,
    }
    assert validate_visual_candidate({**payload, "source_sha256": "0" * 64}, source)


def test_page6123_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6123_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [35, 18]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 53
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "شيشاوة",
        "council_members": 25,
    }
    assert payload["groups"][-1]["rows"][-1] == {
        "row": 53,
        "commune_name_ar": "تزارت",
        "council_members": 23,
    }
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6124_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6124_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [22, 31]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 53
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "اسني",
        "council_members": 23,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 23,
        "commune_name_ar": "قلعة السراغنة",
        "council_members": 31,
    }
    assert validate_visual_candidate({**payload, "status": "OFFICIAL_COMPLETE"}, source)


def test_page6125_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6125_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [12, 31]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 43
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "أولاد مسعود",
        "council_members": 11,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 13,
        "commune_name_ar": "الصويرة",
        "council_members": 31,
    }
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6126_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6126_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [26, 25]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 51
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "أدغاس",
        "council_members": 11,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 27,
        "commune_name_ar": "ابن جرير",
        "council_members": 31,
    }
    assert validate_visual_candidate({**payload, "source_sha256": "0" * 64}, source)


def test_page6127_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6127_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [25, 11]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 36
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "آسفي",
        "council_members": 51,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 26,
        "commune_name_ar": "اليوسفية",
        "council_members": 31,
    }
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6128_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6128_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [29, 17]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 46
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "الرشيدية",
        "council_members": 31,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 30,
        "commune_name_ar": "ورزازات",
        "council_members": 31,
    }
    assert validate_visual_candidate({**payload, "status": "OFFICIAL_COMPLETE"}, source)


def test_page6129_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6129_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [29, 14]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 43
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "ميدلت",
        "council_members": 31,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 30,
        "commune_name_ar": "تنغير",
        "council_members": 25,
    }
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6130_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6130_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [11, 25, 13]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 49
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "اميضر",
        "council_members": 11,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 37,
        "commune_name_ar": "اكادير",
        "council_members": 61,
    }
    assert validate_visual_candidate({**payload, "status": "OFFICIAL_COMPLETE"}, source)


def test_page6131_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6131_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [6, 22, 24]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 52
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "إنزكان",
        "council_members": 35,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 29,
        "commune_name_ar": "تارودانت",
        "council_members": 31,
    }
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6132_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6132_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [50]
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "أركانة",
        "council_members": 11,
    }
    assert payload["groups"][0]["rows"][-1] == {
        "row": 50,
        "commune_name_ar": "توغمرت",
        "council_members": 11,
    }
    assert validate_visual_candidate({**payload, "status": "OFFICIAL_COMPLETE"}, source)


def test_page6133_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6133_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [15, 25]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 40
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "تيسراس",
        "council_members": 13,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 16,
        "commune_name_ar": "تيزنيت",
        "council_members": 31,
    }
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6134_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6134_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [20, 20, 7]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 47
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "طاطا",
        "council_members": 23,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 41,
        "commune_name_ar": "أسا",
        "council_members": 15,
    }
    assert validate_visual_candidate({**payload, "status": "OFFICIAL_COMPLETE"}, source)


def test_page6135_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6135_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [7, 19, 5, 4, 5, 6]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 46
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "طانطان",
        "council_members": 31,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 41,
        "commune_name_ar": "السمارة",
        "council_members": 31,
    }
    assert validate_visual_candidate({**payload, "official_universe_allowed": True}, source)


def test_page6136_visual_transcription_is_source_pinned_and_candidate_only() -> None:
    registry = json.loads((ROOT / "metadata/warehouse/source_registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry["sources"] if row["source_id"] == "MA_SGG_BO_6374_DECREE_2_15_402_COMMUNES_2015")
    payload = json.loads((ROOT / "metadata/warehouse/bo6374_page6136_visual_transcription.candidate.json").read_text(encoding="utf-8"))
    assert validate_visual_candidate(payload, source) == []
    assert [len(group["rows"]) for group in payload["groups"]] == [7, 6]
    assert sum(len(group["rows"]) for group in payload["groups"]) == 13
    assert payload["groups"][0]["rows"][0] == {
        "row": 1,
        "commune_name_ar": "الداخلة",
        "council_members": 35,
    }
    assert payload["groups"][-1]["rows"][0] == {
        "row": 8,
        "commune_name_ar": "الكويرة",
        "council_members": 11,
    }
    assert validate_visual_candidate({**payload, "status": "OFFICIAL_COMPLETE"}, source)
