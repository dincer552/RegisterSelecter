"""Standart AHU register listelerini cihaz konfigürasyonuna gore filtreler.

Kullanicinin sectigi marka + adet disindaki fan bloklari (EBM, Danfoss,
Ziehl-Abegg, WellDrive) ve o bloklarin alarm satirlari silinir; fan markasi
olmayan satirlar (sensor, batarya, SAF/EAF mantigi, genel alarm satirlari)
oldugu gibi kalir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

BRANDS: dict[str, dict] = {
    "ebm": {
        "label": "ebm-papst",
        "max_units": 4,
        "supply": r"EBMFanCont(\d*)",
        "exhaust": r"EBMFaneExCont(\d*)",
    },
    "danfoss": {
        "label": "Danfoss",
        "max_units": 2,
        "supply": r"FC101Asp(\d*)",
        "exhaust": r"FC101Vant(\d*)",
    },
    "ziehl": {
        "label": "Ziehl-Abegg",
        "max_units": 4,
        "supply": r"ZiehlAbeggSup(\d*)",
        "exhaust": r"ZiehlAbeggExh(\d*)",
    },
    "welldrive": {
        "label": "WellDrive",
        "max_units": 2,
        "supply": r"WDriveAsp(\d*)",
        "exhaust": r"WDriveVant(\d*)",
    },
}

PROTOCOLS: dict[str, dict] = {
    "modbus": {
        "label": "MODBUS",
        "file": "Standart_Modbus_Reg_List.xlsx",
        "name_col": "B",
        "header_row": 4,
        "out_suffix": "Modbus_Reg_List",
    },
    "bacnet": {
        "label": "BACNET",
        "file": "Standart_BACnet_List.xlsx",
        "name_col": "A",
        "header_row": 5,
        "out_suffix": "BACnet_Reg_List",
    },
}

_BRAND_PATTERNS = {
    (brand, direction): re.compile(pattern)
    for brand, cfg in BRANDS.items()
    for direction in ("supply", "exhaust")
    for pattern in [cfg[direction]]
}


@dataclass
class RowClassification:
    brand: str
    direction: str
    unit: int


@dataclass
class FilterResult:
    protocol: str
    output: Path
    kept_rows: int
    removed_rows: int
    kept_fan_rows: int
    total_fan_rows: int
    removed_by_group: dict[str, int] = field(default_factory=dict)


def classify_row(name_cell: str | None) -> RowClassification | None:
    """Register adi satirinin hangi marka/yon/üniteye ait oldugunu bulur.

    Standart listede bazi satirlar yanlis on ek ile yazilmis
    (ornek: ZiehlAbeggSup1\\ZiehlAbeggSup2.RPM). Bu yuzden son (en ozel)
    eslesme kullanilir.
    """
    if not name_cell:
        return None
    best: tuple[int, str, str, int] | None = None
    for (brand, direction), pattern in _BRAND_PATTERNS.items():
        for match in pattern.finditer(name_cell):
            suffix = match.group(1)
            unit = int(suffix) + 1 if suffix else 1
            if best is None or match.start() >= best[0]:
                best = (match.start(), brand, direction, unit)
    if best is None:
        return None
    return RowClassification(brand=best[1], direction=best[2], unit=best[3])


def _delete_row_ranges(ws, rows: list[int]) -> None:
    if not rows:
        return
    rows = sorted(set(rows), reverse=True)
    start = end = rows[0]
    for row in rows[1:]:
        if row == end + 1:
            end = row
            continue
        ws.delete_rows(start, end - start + 1)
        start = end = row
    ws.delete_rows(start, end - start + 1)


def _refresh_table_refs(ws, header_row: int) -> None:
    for table in list(ws.tables.values()):
        last_col = re.match(r"[A-Z]+", table.ref.split(":")[-1]).group(0)
        table.ref = f"A{header_row}:{last_col}{ws.max_row}"


def filter_standard_list(
    protocol: str,
    standard_file: Path,
    output_file: Path,
    supply_brand: str | None,
    supply_count: int,
    exhaust_brand: str | None,
    exhaust_count: int,
) -> FilterResult:
    cfg = PROTOCOLS[protocol]
    selections = {
        "supply": (supply_brand, supply_count),
        "exhaust": (exhaust_brand, exhaust_count),
    }

    wb = load_workbook(standard_file)
    ws = wb.active
    name_col = cfg["name_col"]
    first_data_row = cfg["header_row"] + 1

    removed: list[int] = []
    removed_by_group: dict[str, int] = {}
    kept_fan_rows = 0
    total_fan_rows = 0

    for row in range(first_data_row, ws.max_row + 1):
        info = classify_row(ws[f"{name_col}{row}"].value)
        if info is None:
            continue
        total_fan_rows += 1
        sel_brand, sel_count = selections[info.direction]
        keep = sel_brand is not None and info.brand == sel_brand and info.unit <= sel_count
        if keep:
            kept_fan_rows += 1
            continue
        group = f"{BRANDS[info.brand]['label']} {cfg_label_direction(info.direction)} #{info.unit}"
        removed_by_group[group] = removed_by_group.get(group, 0) + 1
        removed.append(row)

    _delete_row_ranges(ws, removed)
    _refresh_table_refs(ws, cfg["header_row"])

    output_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_file)

    result = FilterResult(
        protocol=cfg["label"],
        output=output_file,
        kept_rows=ws.max_row,
        removed_rows=len(removed),
        kept_fan_rows=kept_fan_rows,
        total_fan_rows=total_fan_rows,
        removed_by_group=removed_by_group,
    )
    return result


def cfg_label_direction(direction: str) -> str:
    return "Besleme" if direction == "supply" else "Egzoz"


def generate(
    data_dir: Path,
    output_dir: Path,
    device_prefix: str,
    supply_brand: str | None,
    supply_count: int,
    exhaust_brand: str | None,
    exhaust_count: int,
) -> list[FilterResult]:
    prefix = device_prefix.strip() or "Cihaz"
    results: list[FilterResult] = []
    for protocol, cfg in PROTOCOLS.items():
        out = output_dir / f"{prefix}_{cfg['out_suffix']}.xlsx"
        results.append(
            filter_standard_list(
                protocol=protocol,
                standard_file=data_dir / cfg["file"],
                output_file=out,
                supply_brand=supply_brand,
                supply_count=supply_count,
                exhaust_brand=exhaust_brand,
                exhaust_count=exhaust_count,
            )
        )
    return results
