"""Standart AHU register listelerini cihaz konfigürasyonuna gore filtreler.

Silinen satirlar: secilmeyen marka/adet disindaki fan bloklari (EBM, Danfoss,
Ziehl-Abegg, WellDrive), tiklanmayan sicaklik-nem-CO2 sensor satirlari ve
adetini asan damper (klape) motoru satirlari. Sabit kalan satirlar: AHU start,
batarya, SAF/EAF mantigi, BmsTemp_Hum, TempAVG, DamperCont/BypassDmpCont ve
genel alarm satirlari.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

BRANDS: dict[str, dict] = {
    # unit numbering: ebm/ziehl bloklari isimsiz=1, "1" eki=2 ... (suffix_plus_one)
    # danfoss/welldrive bloklari "1" ekiyle baslar (explicit)
    "ebm": {
        "label": "ebm-papst",
        "max_units": 4,
        "unit_mode": "suffix_plus_one",
        "supply": r"EBMFanCont(\d*)",
        "exhaust": r"EBMFaneExCont(\d*)",
    },
    "danfoss": {
        "label": "Danfoss",
        "max_units": 2,
        "unit_mode": "explicit",
        "supply": r"FC101Asp(\d*)",
        "exhaust": r"FC101Vant(\d*)",
    },
    "ziehl": {
        "label": "Ziehl-Abegg",
        "max_units": 4,
        "unit_mode": "suffix_plus_one",
        "supply": r"ZiehlAbeggSup(\d*)",
        "exhaust": r"ZiehlAbeggExh(\d*)",
    },
    "welldrive": {
        "label": "WellDrive",
        "max_units": 2,
        "unit_mode": "explicit",
        "supply": r"WDriveAsp(\d*)",
        "exhaust": r"WDriveVant(\d*)",
    },
}

PROTOCOLS: dict[str, dict] = {
    "modbus": {
        "label": "MODBUS",
        "file": "Standart_Modbus_Reg_List.xlsx",
        "name_col": "B",
        "label_col": "E",
        "header_row": 4,
        "out_suffix": "Modbus_Reg_List",
    },
    "bacnet": {
        "label": "BACNET",
        "file": "Standart_BACnet_List.xlsx",
        "name_col": "A",
        "label_col": "D",
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

# Excel'deki olasi olcu sinyal tokenlari -> (kod, etiket)
SIGNAL_TOKENS: dict[str, tuple[str, str]] = {
    "TmpVal": ("tmp", "Sıcaklık"),
    "HumVal": ("hum", "Nem"),
    "CO2Val": ("co2", "CO2"),
    "CO2Value": ("co2", "CO2"),
    "EntVal": ("ent", "Entropi"),
    "AbsHum": ("abshum", "Mutlak Nem"),
}

OBJECT_LABELS: dict[str, str] = {
    "SupplyAirSensorMB": "Üfleme Hava Sensörü",
    "ReturnAirSensorMB": "Dönüş Hava Sensörü",
    "FreshAirSensorMB": "Taze Hava Sensörü",
    "AfterCoilAirSensorMB": "Batarya Sonrası Hava Sensörü",
    "ExhaustAirSensorMB": "Egzoz Hava Sensörü",
    "AfterDxUnitAirSensorMB": "DX Sonrası Hava Sensörü",
    "AfterHeatRecAirSensorMB": "Isı Geri Kazanım Sonrası Sensör",
    "ExchngrLeaveTmpSensorMB": "Eşanjör Çıkış Sensörü",
    "MixingAirSensorMB": "Karışım Hava Sensörü",
    "ReturnCO2AirSensorMB": "Dönüş CO2 Sensörü",
    "Room Temp": "Oda Sıcaklık Sensörü",
    "Room Temp1": "Oda Sıcaklık Sensörü 2",
    "Room Hum": "Oda Nem Sensörü",
    "Room Co2": "Oda CO2 Sensörü",
    "Water Temp": "Su Sıcaklık Sensörü",
}


def object_label(obj: str) -> str:
    return OBJECT_LABELS.get(obj, obj)


# Damper (klape) motorlari: "<Taraf>DmpMB_<Marka>[<unit eki>]"
# ornek SupDmpMB_Siemens1 = ufleme tarafindaki 2. damper motoru
DAMPER_RE = re.compile(r"^(?P<side>[A-Za-z]+)Dmp(?P<wire>MB)?_(?P<brand>[A-Za-z]+?)(?P<unit>\d*)$")

SIDE_LABELS: dict[str, str] = {
    "Sup": "Üfleme damper motoru",
    "Fresh": "Taze hava damper motoru",
    "Return": "Dönüş hava damper motoru",
    "Ext": "Egzoz damper motoru",
    "Mix": "Karışım hava damper motoru",
    "ByPass": "By-pass damper motoru",
}


@dataclass
class DamperGroup:
    key: str  # "Sup|Siemens"
    side: str
    brand: str
    label: str
    max_units: int


# Kademeli gruplar (DX sogutucu, elektrikli isiticilar). Kademe tokenlari
# excel'deki yazim farklarina gore regex ile taninir; o gruba ait diger
# satirlar (mod/durum/kapasite/alarm) en az bir kademe secildiginde kalir.
STAGE_GROUPS: dict[str, dict] = {
    "DXControl": {
        "label": "DX soğutucu kademe sayısı",
        "stage_patterns": [r"^Dx(\d+)Alarm$", r"^DX(\d+)Defrost$"],
    },
    "ElectricalHeater": {
        "label": "Elektrikli ısıtıcı kademe sayısı",
        "stage_patterns": [r"^Heater(\d+)_ok$"],
    },
    "PreElectricalHeater": {
        "label": "Ön elektrikli ısıtıcı kademe sayısı",
        "stage_patterns": [r"^Heater(\d+)_ok$"],
    },
}

_STAGE_PATTERNS = {
    obj: [re.compile(pattern) for pattern in cfg["stage_patterns"]] for obj, cfg in STAGE_GROUPS.items()
}


@dataclass
class StageGroup:
    obj: str
    label: str
    max_stages: int
    general_tokens: list[str] = field(default_factory=list)


def _stage_unit(obj: str, tok: str) -> int | None:
    """Kademe token'i ise sayiyi, degilse None dondurur ('DXControl.Dx3Alarm')."""
    if not tok:
        return None
    tail = tok[len(obj) + 1:] if tok.startswith(obj + ".") else tok
    for pattern in _STAGE_PATTERNS[obj]:
        match = pattern.match(tail)
        if match:
            return int(match.group(1))
    return None


def detect_stage_groups(ws, name_col: str, header_row: int) -> list[StageGroup]:
    """Kademeli gruplari ve kademe sayilarini standart listeden cikarir."""
    found: dict[str, dict] = {
        obj: {"max": 0, "general": []} for obj in STAGE_GROUPS
    }
    for row in range(header_row + 1, ws.max_row + 1):
        obj, tok = parse_object_token(ws[f"{name_col}{row}"].value)
        if obj not in found or not tok:
            continue
        unit = _stage_unit(obj, tok)
        if unit is None:
            if tok not in found[obj]["general"]:
                found[obj]["general"].append(tok)
        else:
            found[obj]["max"] = max(found[obj]["max"], unit)
    return [
        StageGroup(obj=obj, label=cfg["label"], max_stages=data["max"], general_tokens=list(data["general"]))
        for obj, cfg in STAGE_GROUPS.items()
        for data in [found[obj]]
        if data["max"] > 0
    ]


def list_stage_groups(data_dir: Path) -> list[StageGroup]:
    """Iki protokol dosyasindaki kademeli gruplarin birlesimi."""
    merged: dict[str, StageGroup] = {}
    for cfg in PROTOCOLS.values():
        ws = load_workbook(data_dir / cfg["file"]).active
        for group in detect_stage_groups(ws, cfg["name_col"], cfg["header_row"]):
            cur = merged.get(group.obj)
            if cur is None or group.max_stages > cur.max_stages:
                merged[group.obj] = group
    return [merged[obj] for obj in STAGE_GROUPS if obj in merged]


# Bloksal secimler (SAF/EAF kontrol, RunAround donma korumasi). "main" secilmezse
# grubun tum satirlari silinir; "sub" secenekleri yalnizca main seciliyken etkilidir.
FEATURE_GROUPS: dict[str, dict] = {
    "SAF": {
        "label": "SAF (üfleme fan kontrol bloğu)",
        "sub": {
            "press": {
                "label": "QBM97xx basınç transmitteri",
                "tokens": ["PrHighAlarm", "PrHighAlmSet", "DuctPress", "DuctPressureBMS"],
                "extra_obj": "QBM97xx_SAF",
            },
        },
    },
    "EAF": {
        "label": "EAF (egzoz fan kontrol bloğu)",
        "sub": {
            "press": {
                "label": "QBM97xx basınç transmitteri",
                "tokens": ["PrHighAlarm", "PrHighAlmSet", "DuctPress", "DuctPressureBMS"],
                "extra_obj": "QBM97xx_EAF",
            },
        },
    },
    "RunAroundCont": {
        "label": "RunAround (su bataryası donma koruması)",
        "sub": {},
    },
}

# "QBM97xx_SAF" -> ("SAF", "press")
_EXTRA_OBJECTS: dict[str, tuple[str, str]] = {
    cfg["extra_obj"]: (obj, code)
    for obj, group in FEATURE_GROUPS.items()
    for code, cfg in group["sub"].items()
    if cfg.get("extra_obj")
}


def _feature_state(obj: str, tok: str) -> tuple[str, str] | None:
    """(grup nesnesi, secenek kodu) dondurur; 'main' veya alt secenek."""
    if obj in _EXTRA_OBJECTS:
        return _EXTRA_OBJECTS[obj]
    group = FEATURE_GROUPS.get(obj)
    if group is None:
        return None
    tail = tok[len(obj) + 1:] if tok.startswith(obj + ".") else tok
    for code, cfg in group["sub"].items():
        if tail in cfg["tokens"]:
            return (obj, code)
    return (obj, "main")


@dataclass
class FeatureGroup:
    obj: str
    label: str
    options: list[tuple[str, str, int]]  # (kod, etiket, satir sayisi)
    total_rows: int


def detect_feature_groups(ws, name_col: str, header_row: int) -> list[FeatureGroup]:
    """BLOK secime tabi satirlari ve sayilarini standart listeden cikarir."""
    counts: dict[tuple[str, str], int] = {}
    for row in range(header_row + 1, ws.max_row + 1):
        obj, tok = parse_object_token(ws[f"{name_col}{row}"].value)
        if obj is None:
            continue
        state = _feature_state(obj, tok or "")
        if state is None:
            continue
        counts[state] = counts.get(state, 0) + 1
    groups: list[FeatureGroup] = []
    for obj, group in FEATURE_GROUPS.items():
        main = counts.get((obj, "main"), 0)
        if main == 0:
            continue
        options: list[tuple[str, str, int]] = [("main", "Kullaniliyor", main)]
        for code, sub in group["sub"].items():
            sub_rows = counts.get((obj, code), 0) + counts.get((sub.get("extra_obj", ""), code), 0)
            if sub_rows:
                options.append((code, sub["label"], sub_rows))
        total = sum(count for _c, _l, count in options)
        groups.append(FeatureGroup(obj=obj, label=group["label"], options=options, total_rows=total))
    return groups


def list_feature_groups(data_dir: Path) -> list[FeatureGroup]:
    """Iki protokol dosyasindaki blok gruplarin birlesimi."""
    merged: dict[str, FeatureGroup] = {}
    for cfg in PROTOCOLS.values():
        ws = load_workbook(data_dir / cfg["file"]).active
        for group in detect_feature_groups(ws, cfg["name_col"], cfg["header_row"]):
            cur = merged.get(group.obj)
            if cur is None or group.total_rows > cur.total_rows:
                merged[group.obj] = group
    return [merged[obj] for obj in FEATURE_GROUPS if obj in merged]


# Filtre kirlilik alarmlari: "Alarm\<Token>" satirlari, tek tek secilir.
FILTER_ALARM_OBJECT = "Alarm"
ALARM_GROUP_PREFIX = "Filtre alarmi - "
# Hicbir cihazda kullanilmayan gruplar her zaman listeden cikarilir.
ALWAYS_DROPPED_OBJECTS = {"TempAVG": "TempAVG (ortalama oda sicakligi)"}
# Sabit kalmasi gereken satirlar (sensor dalgina takilmamasi icin acikca tutulur).
ALWAYS_KEPT_OBJECTS = {"Alarm_Reset"}
# AHUStart\... kapak sensorleri: vantilator daima kalir, aspirator yalnizca
# en az bir egzoz fani secildiginde listeye girer.
FAN_DOOR_SWITCH_TOKENS = {"VANTDOORSW": "supply", "ASPDOORSW": "exhaust"}
FAN_DOOR_GROUP_PREFIX = "Fan kapak sensoru - "


@dataclass
class FilterAlarm:
    token: str
    label: str


def _alarm_label(raw_label: str | None, token: str) -> str:
    text = str(raw_label or "").strip()
    if text and "\\" not in text and text.lower() != token.lower():
        return text
    humanized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", token)
    return re.sub(r"Alm$", "Alarm", humanized)


def detect_filter_alarms(ws, name_col: str, label_col: str, header_row: int) -> list[FilterAlarm]:
    alarms: dict[str, FilterAlarm] = {}
    for row in range(header_row + 1, ws.max_row + 1):
        obj, tok = parse_object_token(ws[f"{name_col}{row}"].value)
        if obj != FILTER_ALARM_OBJECT or not tok:
            continue
        alarms.setdefault(tok, FilterAlarm(token=tok, label=_alarm_label(ws[f"{label_col}{row}"].value, tok)))
    return list(alarms.values())


def list_filter_alarms(data_dir: Path) -> list[FilterAlarm]:
    """Iki protokoldeki filtre alarm satirlarinin birlesimi (etiket olarak en okunani)."""
    merged: dict[str, FilterAlarm] = {}
    for cfg in PROTOCOLS.values():
        ws = load_workbook(data_dir / cfg["file"]).active
        for alarm in detect_filter_alarms(ws, cfg["name_col"], cfg["label_col"], cfg["header_row"]):
            cur = merged.get(alarm.token)
            if cur is None or "\\" in cur.label:
                merged[alarm.token] = alarm
    return sorted(merged.values(), key=lambda a: a.label.lower())


def classify_damper(name_cell: str | None) -> tuple[str, int] | None:
    """Damper motoru satiriyse (grup anahtari, unite numarasi) dondurur."""
    obj, _tok = parse_object_token(name_cell)
    if obj is None:
        return None
    match = DAMPER_RE.match(obj)
    if not match:
        return None
    side, brand = match.group("side"), match.group("brand")
    suffix = match.group("unit")
    unit = int(suffix) + 1 if suffix else 1
    return (f"{side}|{brand}", unit)


@dataclass
class SensorGroup:
    obj: str
    label: str
    signals: list[tuple[str, str]]  # (kod, etiket) sirasiyla


def parse_object_token(name_cell: str | None) -> tuple[str, str] | tuple[None, None]:
    r"""'0x2304 'SupplyAirSensorMB\TmpVal=60000' gibisinden (obje, token) cikarir."""
    if not name_cell:
        return None, None
    s = str(name_cell).strip()
    s = re.sub(r"=\d+$", "", s)
    s = re.sub(r"^0x[0-9A-Fa-f]+\s+", "", s).strip("'").strip()
    if "\\" not in s:
        return None, None
    obj, tok = s.split("\\", 1)
    return obj.strip(), tok.strip()


def _signal_for_token(obj: str, tok: str) -> tuple[str, str] | None:
    if tok in SIGNAL_TOKENS:
        return SIGNAL_TOKENS[tok]
    # "Room Temp\Room Temp" ve "Room Temp1\Room Temp" gibi tek degerli nesneler
    if tok.rstrip("0123456789") == obj.rstrip("0123456789"):
        low = tok.lower()
        if "co2" in low:
            return ("co2", "CO2")
        if "hum" in low:
            return ("hum", "Nem")
        if "tmp" in low or "temp" in low:
            return ("tmp", "Sıcaklık")
    return None


def detect_sensor_groups(ws, name_col: str, header_row: int) -> list[SensorGroup]:
    """Standart listedeki gercek sensor nesnelerini ve sinyallerini bulur."""
    groups: dict[str, dict[str, str]] = {}
    for row in range(header_row + 1, ws.max_row + 1):
        obj, tok = parse_object_token(ws[f"{name_col}{row}"].value)
        if obj is None:
            continue
        sig = _signal_for_token(obj, tok)
        if sig:
            groups.setdefault(obj, {})
            if sig[0] not in groups[obj]:
                groups[obj][sig[0]] = sig[1]
    ordered: list[SensorGroup] = []
    for obj, codes in groups.items():
        seen: set[str] = set()
        signals: list[tuple[str, str]] = []
        for token, (code, label) in SIGNAL_TOKENS.items():
            if code in codes and code not in seen:
                signals.append((code, label))
                seen.add(code)
        ordered.append(SensorGroup(obj=obj, label=object_label(obj), signals=signals))
    return ordered


def list_sensor_groups(data_dir: Path) -> list[SensorGroup]:
    """Iki protokol dosyasinda bulunan tum sensör gruplarinin birlesimi."""
    merged: dict[str, SensorGroup] = {}
    for protocol, cfg in PROTOCOLS.items():
        wb = load_workbook(data_dir / cfg["file"], read_only=False)
        for group in detect_sensor_groups(wb.active, cfg["name_col"], cfg["header_row"]):
            cur = merged.get(group.obj)
            if cur is None:
                merged[group.obj] = group
            else:
                codes = {c for c, _ in cur.signals}
                for code, label in group.signals:
                    if code not in codes:
                        cur.signals.append((code, label))
                        codes.add(code)
    return list(merged.values())


def _damper_sort_key(group: DamperGroup) -> tuple[int, str]:
    order = list(SIDE_LABELS)
    return (order.index(group.side) if group.side in order else len(order), group.brand)


def _with_brand_suffix(groups: list[DamperGroup]) -> list[DamperGroup]:
    sides = [g.side for g in groups]
    for group in groups:
        if sides.count(group.side) > 1:
            group.label = f"{group.label} ({group.brand})"
    return sorted(groups, key=_damper_sort_key)


def detect_damper_groups(ws, name_col: str, header_row: int) -> list[DamperGroup]:
    """Standart listedeki damper motoru gruplarini ve unite sayilarini bulur."""
    units: dict[str, set[int]] = {}
    for row in range(header_row + 1, ws.max_row + 1):
        found = classify_damper(ws[f"{name_col}{row}"].value)
        if found is None:
            continue
        key, unit = found
        units.setdefault(key, set()).add(unit)
    groups = [
        DamperGroup(
            key=key,
            side=key.split("|")[0],
            brand=key.split("|")[1],
            label=SIDE_LABELS.get(key.split("|")[0], key.split("|")[0]),
            max_units=max(used),
        )
        for key, used in units.items()
    ]
    return _with_brand_suffix(groups)


def list_damper_groups(data_dir: Path) -> list[DamperGroup]:
    """Iki protokol dosyasinda bulunan damper gruplarinin birlesimi."""
    merged: dict[str, DamperGroup] = {}
    for cfg in PROTOCOLS.values():
        ws = load_workbook(data_dir / cfg["file"]).active
        for group in detect_damper_groups(ws, cfg["name_col"], cfg["header_row"]):
            cur = merged.get(group.key)
            if cur is None or group.max_units > cur.max_units:
                merged[group.key] = group
    for group in merged.values():
        group.label = SIDE_LABELS.get(group.side, group.side)
    return _with_brand_suffix(list(merged.values()))


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
    kept_damper_rows: int = 0
    total_damper_rows: int = 0
    kept_stage_rows: int = 0
    total_stage_rows: int = 0
    kept_feature_rows: int = 0
    total_feature_rows: int = 0
    kept_alarm_rows: int = 0
    total_alarm_rows: int = 0
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
            if BRANDS[brand]["unit_mode"] == "explicit":
                unit = int(suffix) if suffix else 1
            else:
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
        new_ref = f"A{header_row}:{last_col}{ws.max_row}"
        table.ref = new_ref
        if table.autoFilter is not None:
            table.autoFilter.ref = new_ref


def filter_standard_list(
    protocol: str,
    standard_file: Path,
    output_file: Path,
    supply_brand: str | None,
    supply_count: int,
    exhaust_brand: str | None,
    exhaust_count: int,
    sensor_selection: dict[str, list[str]] | None = None,
    damper_selection: dict[str, int] | None = None,
    stage_selection: dict[str, int] | None = None,
    feature_selection: dict[str, list[str]] | None = None,
    alarm_selection: list[str] | None = None,
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

    registered: dict[str, SensorGroup] = {}
    if sensor_selection is not None:
        registered = {g.obj: g for g in detect_sensor_groups(ws, name_col, cfg["header_row"])}

    damper_groups: dict[str, DamperGroup] = {}
    if damper_selection is not None:
        damper_groups = {g.key: g for g in detect_damper_groups(ws, name_col, cfg["header_row"])}

    stage_groups: dict[str, StageGroup] = {}
    if stage_selection is not None:
        stage_groups = {g.obj: g for g in detect_stage_groups(ws, name_col, cfg["header_row"])}

    feature_enabled = feature_selection is not None
    chosen_features = feature_selection or {}

    alarm_enabled = alarm_selection is not None
    chosen_alarms = set(alarm_selection or [])
    alarm_labels: dict[str, str] = {}
    if alarm_enabled:
        alarm_labels = {
            a.token: a.label for a in detect_filter_alarms(ws, name_col, cfg["label_col"], cfg["header_row"])
        }

    removed: list[int] = []
    removed_by_group: dict[str, int] = {}
    kept_fan_rows = 0
    total_fan_rows = 0
    kept_damper_rows = 0
    total_damper_rows = 0
    kept_stage_rows = 0
    total_stage_rows = 0
    kept_feature_rows = 0
    total_feature_rows = 0
    kept_alarm_rows = 0
    total_alarm_rows = 0

    for row in range(first_data_row, ws.max_row + 1):
        value = ws[f"{name_col}{row}"].value
        info = classify_row(value)
        damper_found = classify_damper(value) if damper_groups else None
        parsed_obj, parsed_tok = parse_object_token(value)
        stage_group = stage_groups.get(parsed_obj) if stage_groups and parsed_obj else None
        feature_state = (
            _feature_state(parsed_obj, parsed_tok or "") if feature_enabled and parsed_obj else None
        )
        if info is not None:
            total_fan_rows += 1
            sel_brand, sel_count = selections[info.direction]
            keep = sel_brand is not None and info.brand == sel_brand and info.unit <= sel_count
            if keep:
                kept_fan_rows += 1
                continue
            group = f"{BRANDS[info.brand]['label']} {cfg_label_direction(info.direction)} #{info.unit}"
        elif damper_found is not None:
            key, unit = damper_found
            total_damper_rows += 1
            if unit <= damper_selection.get(key, 0):
                kept_damper_rows += 1
                continue
            group = f"{damper_groups[key].label} #{unit}"
        elif stage_group is not None:
            unit = _stage_unit(stage_group.obj, parsed_tok)
            stages = stage_selection.get(stage_group.obj, 0)
            total_stage_rows += 1
            if unit is None:
                keep = stages >= 1  # mod/durum/kapasite/alarm satirlari
                group = f"{stage_group.label} - genel satirlar"
            else:
                keep = unit <= stages
                group = f"{stage_group.label} #{unit}"
            if keep:
                kept_stage_rows += 1
                continue
        elif feature_state is not None:
            grp_obj, code = feature_state
            chosen = chosen_features.get(grp_obj, [])
            total_feature_rows += 1
            keep = "main" in chosen and (code == "main" or code in chosen)
            if code == "main":
                group = f"{FEATURE_GROUPS[grp_obj]['label']}"
            else:
                group = f"{FEATURE_GROUPS[grp_obj]['label']} - {FEATURE_GROUPS[grp_obj]['sub'][code]['label']}"
            if keep:
                kept_feature_rows += 1
                continue
        elif parsed_obj in ALWAYS_DROPPED_OBJECTS:
            group = f"{ALWAYS_DROPPED_OBJECTS[parsed_obj]} - kullanilmiyor"
        elif parsed_obj in ALWAYS_KEPT_OBJECTS:
            continue  # Alarm_Reset her zaman listeye eklenir
        elif parsed_tok in FAN_DOOR_SWITCH_TOKENS:
            direction = FAN_DOOR_SWITCH_TOKENS[parsed_tok]
            sel_brand, sel_count = selections[direction]
            keep = direction == "supply" or (sel_brand is not None and sel_count >= 1)
            if keep:
                continue
            group = f"{FAN_DOOR_GROUP_PREFIX}aspirator secilmedi"
        elif alarm_enabled and parsed_obj == FILTER_ALARM_OBJECT:
            total_alarm_rows += 1
            if parsed_tok in chosen_alarms:
                kept_alarm_rows += 1
                continue
            group = f"{ALARM_GROUP_PREFIX}{alarm_labels.get(parsed_tok or '', parsed_tok or '')}"
        elif registered:
            obj, tok = parse_object_token(value)
            group_obj = registered.get(obj) if obj else None
            if group_obj is None:
                continue  # bu satir ne fan ne sensor bloku -> sabit kalir
            sig = _signal_for_token(obj, tok)
            chosen = set(sensor_selection.get(obj, []))
            if sig is not None:
                keep = sig[0] in chosen
                group = f"{group_obj.label} - {sig[1]}"
            else:
                keep = bool(chosen)  # CommAlarm gibi nesne satirlari en az bir sinyal seciliyse kalir
                group = f"{group_obj.label} - Haberleşme Alarmları"
            if keep:
                continue
        else:
            continue

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
        kept_damper_rows=kept_damper_rows,
        total_damper_rows=total_damper_rows,
        kept_stage_rows=kept_stage_rows,
        total_stage_rows=total_stage_rows,
        kept_feature_rows=kept_feature_rows,
        total_feature_rows=total_feature_rows,
        kept_alarm_rows=kept_alarm_rows,
        total_alarm_rows=total_alarm_rows,
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
    sensor_selection: dict[str, list[str]] | None = None,
    damper_selection: dict[str, int] | None = None,
    stage_selection: dict[str, int] | None = None,
    feature_selection: dict[str, list[str]] | None = None,
    alarm_selection: list[str] | None = None,
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
                sensor_selection=sensor_selection,
                damper_selection=damper_selection,
                stage_selection=stage_selection,
                feature_selection=feature_selection,
                alarm_selection=alarm_selection,
            )
        )
    return results
