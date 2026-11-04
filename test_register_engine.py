from pathlib import Path

import pytest
from openpyxl import load_workbook

from register_engine import (
    BRANDS,
    PROTOCOLS,
    RowClassification,
    classify_damper,
    classify_row,
    detect_damper_groups,
    detect_sensor_groups,
    detect_stage_groups,
    filter_standard_list,
    generate,
    list_damper_groups,
    list_sensor_groups,
    list_stage_groups,
    parse_object_token,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
MODBUS = DATA_DIR / PROTOCOLS["modbus"]["file"]
BACNET = DATA_DIR / PROTOCOLS["bacnet"]["file"]

# Veriden dogrulanan toplam fan satiri sayisi (her protokolde).
EXPECTED_TOTAL_FAN_ROWS = 216


@pytest.mark.parametrize(
    "cell,expected",
    [
        (r"EBMFanCont\SAF Ebm RPM", RowClassification("ebm", "supply", 1)),
        (r"EBMFanCont2\SAF EBM Motor Run Hour", RowClassification("ebm", "supply", 3)),
        (r"EBMFaneExCont1\EAF Ebm Current", RowClassification("ebm", "exhaust", 2)),
        (r"EBMFaneExCont\EBMFaneExCont.MotorAlarm", RowClassification("ebm", "exhaust", 1)),
        (r"ZiehlAbeggSup1\ZiehlAbeggSup2.RPM", RowClassification("ziehl", "supply", 3)),
        (r"ZiehlAbeggExh3\ZiehlAbeggExh3.Power", RowClassification("ziehl", "exhaust", 4)),
        (r"FC101Vant1\FCRunning", RowClassification("danfoss", "exhaust", 1)),
        (r"FC101Asp2\FC101Asp2.kWhCounter", RowClassification("danfoss", "supply", 2)),
        ("0x230A 'WDriveVant2\\WDriveVant2.RPMVal'", RowClassification("welldrive", "exhaust", 2)),
        ("WDriveAsp1.CommAlarm", RowClassification("welldrive", "supply", 1)),
        (r"SupplyAirSensorMB\TmpVal", None),
        (r"SAF\SAF.ManualReferanceBMS", None),
        (r"Alarm\SupplyF9FilterAlm", None),
        (r"EBMFanCont\SAF Ebm RPM=60440", RowClassification("ebm", "supply", 1)),
    ],
)
def test_classify_row(cell, expected):
    assert classify_row(cell) == expected


@pytest.mark.parametrize("standard,out_name", [(MODBUS, "mb.xlsx"), (BACNET, "ba.xlsx")])
def test_full_selection_keeps_everything(standard, out_name, tmp_path):
    """EBM 4+4 secilince (var olan her unite) hicbir satir silinmemeli."""
    res = filter_standard_list(
        protocol="modbus" if standard == MODBUS else "bacnet",
        standard_file=standard,
        output_file=tmp_path / out_name,
        supply_brand="ebm",
        supply_count=4,
        exhaust_brand="ebm",
        exhaust_count=4,
    )
    assert res.total_fan_rows == EXPECTED_TOTAL_FAN_ROWS
    assert res.kept_fan_rows == 64  # 4+4 EBM unites x 8 satir
    assert res.removed_rows == EXPECTED_TOTAL_FAN_ROWS - 64


def test_ebm_supply_2_exhaust_1(tmp_path):
    res = filter_standard_list(
        protocol="modbus",
        standard_file=MODBUS,
        output_file=tmp_path / "mb.xlsx",
        supply_brand="ebm",
        supply_count=2,
        exhaust_brand="ebm",
        exhaust_count=1,
    )
    assert res.kept_fan_rows == 16 + 8  # 2 supply + 1 exhaust unite
    assert res.removed_rows == EXPECTED_TOTAL_FAN_ROWS - 24

    wb = load_workbook(res.output)
    ws = wb.active
    names = [ws[f"B{row}"].value for row in range(5, ws.max_row + 1)]
    joined = "\n".join(str(n) for n in names)
    assert r"EBMFanCont1\SAF Ebm RPM" in joined
    assert "EBMFanCont2" not in joined
    assert "EBMFanCont3" not in joined
    assert "ZiehlAbegg" not in joined
    assert "FC101" not in joined
    assert "WDrive" not in joined
    assert "EBMFaneExCont1" not in joined
    # fan disi satirlar korunmali
    assert r"SupplyAirSensorMB\TmpVal" in joined
    assert r"SAF\SAF.ManualReferanceBMS" in joined


def test_danfoss_supply_only(tmp_path):
    res = filter_standard_list(
        protocol="bacnet",
        standard_file=BACNET,
        output_file=tmp_path / "ba.xlsx",
        supply_brand="danfoss",
        supply_count=2,
        exhaust_brand=None,
        exhaust_count=0,
    )
    assert res.kept_fan_rows == 34  # 2 x (15 durum + 2 alarm) satiri
    wb = load_workbook(res.output)
    ws = wb.active
    joined = "\n".join(str(ws[f"A{row}"].value) for row in range(6, ws.max_row + 1))
    assert "FC101Asp2" in joined
    assert "FC101Vant" not in joined
    assert "ZiehlAbegg" not in joined
    assert "EBMFanCont" not in joined


def test_welldrive_both(tmp_path):
    res = filter_standard_list(
        protocol="modbus",
        standard_file=MODBUS,
        output_file=tmp_path / "mb.xlsx",
        supply_brand="welldrive",
        supply_count=1,
        exhaust_brand="welldrive",
        exhaust_count=2,
    )
    assert res.kept_fan_rows == 11 + 22


def test_table_reference_refreshed(tmp_path):
    res = filter_standard_list(
        protocol="modbus",
        standard_file=MODBUS,
        output_file=tmp_path / "mb.xlsx",
        supply_brand="ziehl",
        supply_count=1,
        exhaust_brand="ziehl",
        exhaust_count=1,
    )
    wb = load_workbook(res.output)
    ws = wb.active
    assert len(ws.tables) == 1
    table = next(iter(ws.tables.values()))
    assert table.ref == f"A4:G{ws.max_row}"
    if table.autoFilter is not None:
        assert table.autoFilter.ref == table.ref


def test_generate_writes_both_files(tmp_path):
    results = generate(
        data_dir=DATA_DIR,
        output_dir=tmp_path,
        device_prefix="AHU-12",
        supply_brand="ebm",
        supply_count=1,
        exhaust_brand="danfoss",
        exhaust_count=2,
    )
    names = sorted(p.name for p in [r.output for r in results])
    assert names == ["AHU-12_BACnet_Reg_List.xlsx", "AHU-12_Modbus_Reg_List.xlsx"]
    for r in results:
        assert r.output.exists()
        assert r.removed_rows > 0


def test_brand_max_units_match_data():
    assert BRANDS["ebm"]["max_units"] == 4
    assert BRANDS["ziehl"]["max_units"] == 4
    assert BRANDS["danfoss"]["max_units"] == 2
    assert BRANDS["welldrive"]["max_units"] == 2


# ---------- sicaklik sensörü algılama ve seçim ----------

# Standart listede sensör sayilmayan (sabit kalan) nesneler
NOT_SENSOR_OBJECTS = {"BmsTemp_Hum", "TempAVG", "Hum_Mod_Sel", "SAF", "EAF", "Alarm"}


def _groups(protocol: str):
    cfg = PROTOCOLS[protocol]
    ws = load_workbook(DATA_DIR / cfg["file"]).active
    return {g.obj: g for g in detect_sensor_groups(ws, cfg["name_col"], cfg["header_row"])}


def test_parse_object_token():
    assert parse_object_token(r"SupplyAirSensorMB\TmpVal") == ("SupplyAirSensorMB", "TmpVal")
    assert parse_object_token(r"SupplyAirSensorMB\TmpVal=60000") == ("SupplyAirSensorMB", "TmpVal")
    assert parse_object_token("0x2304 'SupplyAirSensorMB\\HumVal'") == ("SupplyAirSensorMB", "HumVal")
    assert parse_object_token("WDriveAsp1.CommAlarm") == (None, None)
    assert parse_object_token(None) == (None, None)


@pytest.mark.parametrize("protocol", ["modbus", "bacnet"])
def test_detect_sensor_groups_signals(protocol):
    groups = _groups(protocol)
    assert [c for c, _ in groups["SupplyAirSensorMB"].signals] == ["tmp", "hum", "co2", "ent", "abshum"]
    assert [c for c, _ in groups["AfterCoilAirSensorMB"].signals] == ["tmp", "hum", "co2"]
    assert [c for c, _ in groups["ReturnCO2AirSensorMB"].signals] == ["tmp", "co2"]
    # tek sinyalli sensörler tik kutusu olarak görünecek
    assert [c for c, _ in groups["Room Temp"].signals] == ["tmp"]
    assert [c for c, _ in groups["Room Temp1"].signals] == ["tmp"]
    assert [c for c, _ in groups["Room Hum"].signals] == ["hum"]
    assert [c for c, _ in groups["Room Co2"].signals] == ["co2"]
    assert groups["Room Temp1"].label == "Oda Sıcaklık Sensörü 2"
    assert NOT_SENSOR_OBJECTS.isdisjoint(groups)


def test_list_sensor_groups_unions_both_protocols():
    groups = {g.obj: g for g in list_sensor_groups(DATA_DIR)}
    assert len(groups) == 15
    assert {c for c, _ in groups["ExchngrLeaveTmpSensorMB"].signals} == {"tmp", "hum", "co2"}


def _sensor_run(tmp_path, protocol, sensor_selection, out_name=None, damper_selection=None,
                stage_selection=None, **fan):
    cfg = PROTOCOLS[protocol]
    kwargs = {
        "protocol": protocol,
        "standard_file": DATA_DIR / cfg["file"],
        "output_file": tmp_path / (out_name or f"{protocol}.xlsx"),
        "supply_brand": "ebm",
        "supply_count": 4,
        "exhaust_brand": "ebm",
        "exhaust_count": 4,
    }
    kwargs.update(fan)
    kwargs["sensor_selection"] = sensor_selection
    kwargs["damper_selection"] = damper_selection
    kwargs["stage_selection"] = stage_selection
    return filter_standard_list(**kwargs)


def _names(result, protocol):
    cfg = PROTOCOLS[protocol]
    ws = load_workbook(result.output).active
    return "\n".join(
        str(ws[f"{cfg['name_col']}{row}"].value)
        for row in range(cfg["header_row"] + 1, ws.max_row + 1)
    )


def test_sensor_selection_keeps_fan_baseline_when_all_checked(tmp_path):
    groups = {g.obj: [c for c, _ in g.signals] for g in list_sensor_groups(DATA_DIR)}
    res = _sensor_run(tmp_path, "modbus", groups)
    assert res.kept_fan_rows == 64
    assert res.removed_rows == EXPECTED_TOTAL_FAN_ROWS - 64
    # hicbir sensör satiri silinmemeli (silinen gruplar yalnizca fan bloklari)
    assert not [k for k in res.removed_by_group if "Sens" in k]
    names = _names(res, "modbus")
    assert r"SupplyAirSensorMB\AbsHum" in names
    assert r"SupplyAirSensorMB.CommAlarm" in names


def test_sensor_partial_signal_removal(tmp_path):
    selection = {"SupplyAirSensorMB": ["tmp"]}
    res = _sensor_run(tmp_path, "modbus", selection, exhaust_count=4)
    # 4 olcu satiri + secilmeyen diger 14 sensörün 34 satiri silinir
    names = _names(res, "modbus")
    assert r"SupplyAirSensorMB\TmpVal" in names
    assert r"SupplyAirSensorMB\HumVal" not in names
    assert r"SupplyAirSensorMB\EntVal" not in names
    # en az bir sinyal kalan sensörün haberleşme alarmlari korunur
    assert r"SupplyAirSensorMB.CommAlarm" in names
    # hic sinyali secilmeyen sensörün alarm satiri da silinir
    assert r"FreshAirSensorMB.CommAlarm" not in names
    assert res.removed_by_group["Üfleme Hava Sensörü - Nem"] == 1
    assert res.removed_by_group["Taze Hava Sensörü - Haberleşme Alarmları"] == 1


def test_sensor_removed_row_count_matches_selection(tmp_path):
    all_signals = {g.obj: [c for c, _ in g.signals] for g in list_sensor_groups(DATA_DIR)}
    baseline = _sensor_run(tmp_path, "modbus", all_signals, out_name="all.xlsx")
    res = _sensor_run(tmp_path, "modbus", {}, out_name="none.xlsx")
    # 15 sensör: 40 olcu satiri + 10 CommAlarm satiri
    total_sensor_rows = 50
    assert res.removed_rows - baseline.removed_rows == total_sensor_rows
    assert "Room Temp" not in _names(res, "modbus")
    # sabit satirlar (BMS/ort. sicaklik/nem modu) her zaman kalir
    assert r"BmsTemp_Hum\RoomTempFromBms" in _names(res, "modbus")
    assert r"TempAVG\Room_TempAVG" in _names(res, "modbus")
    assert r"Hum_Mod_Sel\Room_Abs" in _names(res, "modbus")


def test_generate_passes_sensor_selection(tmp_path):
    results = generate(
        data_dir=DATA_DIR,
        output_dir=tmp_path,
        device_prefix="AHU-05",
        supply_brand="ebm",
        supply_count=1,
        exhaust_brand="ebm",
        exhaust_count=1,
        sensor_selection={"Room Temp": ["tmp"]},
    )
    for res in results:
        protocol = "modbus" if res.protocol == "MODBUS" else "bacnet"
        names = _names(res, protocol)
        assert "Room Temp1" not in names
        assert r"Room Temp\Room Temp" in names


# ---------- damper (klape) motoru algılama ve seçim ----------

# Her iki listede de 6 taraf x (1 pozisyon + 4 motor x 4 satır) = 102 satır
EXPECTED_TOTAL_DAMPER_ROWS = 102
DAMPER_SIDES = {"Sup", "Fresh", "Return", "Ext", "Mix", "ByPass"}


@pytest.mark.parametrize(
    "cell,expected",
    [
        (r"SupDmpMB_Siemens\Dmp_Pos", ("Sup|Siemens", 1)),
        (r"SupDmpMB_Siemens1\SupDmpMB_Siemens1.CommAlarm", ("Sup|Siemens", 2)),
        (r"ByPassDmpMB_Siemens3\ByPassDmpMB_Siemens3.Mechanical_fault", ("ByPass|Siemens", 4)),
        (r"FreshDmpMB_Siemens2\Dmp_Fdb=60420", ("Fresh|Siemens", 3)),
        (r"DamperCont\DmpContTypeSel", None),
        (r"BypassDmpCont\BypassRecMod", None),
        (r"SupplyAirSensorMB\TmpVal", None),
        (r"EBMFanCont\SAF Ebm RPM", None),
    ],
)
def test_classify_damper(cell, expected):
    assert classify_damper(cell) == expected


@pytest.mark.parametrize("protocol", ["modbus", "bacnet"])
def test_detect_damper_groups(protocol):
    cfg = PROTOCOLS[protocol]
    ws = load_workbook(DATA_DIR / cfg["file"]).active
    groups = detect_damper_groups(ws, cfg["name_col"], cfg["header_row"])
    assert {g.side for g in groups} == DAMPER_SIDES
    assert all(g.max_units == 4 for g in groups)
    assert all(g.brand == "Siemens" for g in groups)
    assert groups[0].label == "Üfleme damper motoru"


def test_list_damper_groups_covers_both_protocols():
    groups = list_damper_groups(DATA_DIR)
    assert len(groups) == 6
    assert {g.key for g in groups} == {f"{s}|Siemens" for s in DAMPER_SIDES}


def test_damper_full_selection_removes_nothing_extra(tmp_path):
    all_units = {g.key: g.max_units for g in list_damper_groups(DATA_DIR)}
    res = _sensor_run(tmp_path, "modbus", None, damper_selection=all_units)
    assert res.total_damper_rows == EXPECTED_TOTAL_DAMPER_ROWS
    assert res.kept_damper_rows == EXPECTED_TOTAL_DAMPER_ROWS
    assert res.removed_rows == EXPECTED_TOTAL_FAN_ROWS - 64


def test_damper_zero_selection_removes_whole_block(tmp_path):
    res = _sensor_run(tmp_path, "modbus", None, damper_selection={}, out_name="none.xlsx")
    assert res.kept_damper_rows == 0
    assert res.removed_rows == (EXPECTED_TOTAL_FAN_ROWS - 64) + EXPECTED_TOTAL_DAMPER_ROWS
    names = _names(res, "modbus")
    assert "DmpMB_Siemens" not in names
    # damper kontrol/parametre satirlari (DamperCont, BypassDmpCont) sabit kalir
    assert r"DamperCont\DmpContTypeSel" in names
    assert r"BypassDmpCont\BypassRecMod" in names


def test_damper_unit_counts_per_side(tmp_path):
    selection = {"Sup|Siemens": 2, "Fresh|Siemens": 1, "Return|Siemens": 4,
                 "Ext|Siemens": 0, "Mix|Siemens": 3, "ByPass|Siemens": 4}
    res = _sensor_run(tmp_path, "modbus", None, damper_selection=selection, out_name="mixed.xlsx")
    # taraf basina: 1 pozisyon + N motor x 4 satir
    assert res.kept_damper_rows == (1 + 8) + (1 + 4) + (1 + 16) + 0 + (1 + 12) + (1 + 16)
    assert res.removed_rows == (EXPECTED_TOTAL_FAN_ROWS - 64) + (EXPECTED_TOTAL_DAMPER_ROWS - res.kept_damper_rows)
    names = _names(res, "modbus")
    assert r"SupDmpMB_Siemens1\Dmp_Fdb" in names
    assert r"SupDmpMB_Siemens2\Dmp_Fdb" not in names
    assert r"FreshDmpMB_Siemens\Dmp_Pos" in names
    assert r"FreshDmpMB_Siemens1\FreshDmpMB_Siemens1.CommAlarm" not in names
    assert "ExtDmpMB_Siemens" not in names
    assert res.removed_by_group["Egzoz damper motoru #1"] == 5
    assert res.removed_by_group["Taze hava damper motoru #2"] == 4


def test_generate_with_damper_selection(tmp_path):
    results = generate(
        data_dir=DATA_DIR,
        output_dir=tmp_path,
        device_prefix="AHU-07",
        supply_brand="ziehl",
        supply_count=1,
        exhaust_brand=None,
        exhaust_count=0,
        sensor_selection={g.obj: [c for c, _ in g.signals] for g in list_sensor_groups(DATA_DIR)},
        damper_selection={"Sup|Siemens": 1, "ByPass|Siemens": 2},
    )
    for res in results:
        protocol = "modbus" if res.protocol == "MODBUS" else "bacnet"
        assert res.kept_damper_rows == (1 + 4) + (1 + 8)
        names = _names(res, protocol)
        assert r"ByPassDmpMB_Siemens1" in names
        assert "MixDmpMB_Siemens" not in names


# ---------- isitici / DX kademe secimi ----------

# DXControl 24 + ElectricalHeater 5 + PreElectricalHeater 5
EXPECTED_TOTAL_STAGE_ROWS = 34


@pytest.mark.parametrize("protocol", ["modbus", "bacnet"])
def test_detect_stage_groups(protocol):
    cfg = PROTOCOLS[protocol]
    ws = load_workbook(DATA_DIR / cfg["file"]).active
    groups = {g.obj: g for g in detect_stage_groups(ws, cfg["name_col"], cfg["header_row"])}
    assert groups["DXControl"].max_stages == 10
    assert set(groups["DXControl"].general_tokens) == {"DX_mode", "DX_Status1", "CapValuee", "CapValuee1"}
    assert groups["ElectricalHeater"].max_stages == 3
    assert set(groups["ElectricalHeater"].general_tokens) == {"HeaterStage", "HighTempAlarm"}
    assert groups["PreElectricalHeater"].max_stages == 3
    assert "PreHighTempAlarm" in groups["PreElectricalHeater"].general_tokens
    # DX: 10 kademe x 2 satir + 4 genel = 24 ; isiticilar: 3 kademe + 2 genel = 5
    row_counts = {"DXControl": 24, "ElectricalHeater": 5, "PreElectricalHeater": 5}
    assert sum(row_counts[g.obj] for g in groups.values()) == EXPECTED_TOTAL_STAGE_ROWS


def test_list_stage_groups_labels():
    groups = {g.obj: g for g in list_stage_groups(DATA_DIR)}
    assert list(groups) == ["DXControl", "ElectricalHeater", "PreElectricalHeater"]
    assert groups["DXControl"].label == "DX soğutucu kademe sayısı"


def test_stage_full_selection_keeps_rows(tmp_path):
    all_stages = {g.obj: g.max_stages for g in list_stage_groups(DATA_DIR)}
    res = _sensor_run(tmp_path, "modbus", None, stage_selection=all_stages)
    assert res.total_stage_rows == EXPECTED_TOTAL_STAGE_ROWS
    assert res.kept_stage_rows == EXPECTED_TOTAL_STAGE_ROWS
    assert res.removed_rows == EXPECTED_TOTAL_FAN_ROWS - 64


def test_stage_zero_selection_removes_all(tmp_path):
    res = _sensor_run(tmp_path, "bacnet", None, stage_selection={}, out_name="ba.xlsx")
    assert res.kept_stage_rows == 0
    assert res.removed_rows == (EXPECTED_TOTAL_FAN_ROWS - 64) + EXPECTED_TOTAL_STAGE_ROWS
    names = _names(res, "bacnet")
    for token in ("DXControl", "ElectricalHeater", "PreElectricalHeater"):
        assert token not in names


def test_stage_partial_counts(tmp_path):
    selection = {"DXControl": 2, "ElectricalHeater": 1, "PreElectricalHeater": 0}
    res = _sensor_run(tmp_path, "modbus", None, stage_selection=selection, out_name="part.xlsx")
    # DX: 4 genel + 2 kademe x 2 satir ; EH: 2 genel + 1 kademe ; On isitici: hicbir sey
    assert res.kept_stage_rows == (4 + 4) + (2 + 1)
    names = _names(res, "modbus")
    assert r"DXControl\DXControl.Dx2Alarm" in names
    assert r"DXControl\DXControl.DX3Defrost" not in names
    assert r"DXControl\DX_mode" in names
    assert r"DXControl\CapValuee1" in names
    assert r"ElectricalHeater\Heater1_ok" in names
    assert r"ElectricalHeater\Heater2_ok" not in names
    assert r"ElectricalHeater\HighTempAlarm" in names
    assert "PreElectricalHeater" not in names
    assert res.removed_by_group["DX soğutucu kademe sayısı #10"] == 2
    assert res.removed_by_group["Ön elektrikli ısıtıcı kademe sayısı - genel satirlar"] == 2


def test_stage_selection_does_not_touch_sensors(tmp_path):
    selection = {"DXControl": 1, "ElectricalHeater": 0, "PreElectricalHeater": 0}
    res = _sensor_run(tmp_path, "modbus", None, stage_selection=selection, out_name="onlystage.xlsx")
    names = _names(res, "modbus")
    assert r"SupplyAirSensorMB\TmpVal" in names
    assert r"SupDmpMB_Siemens\Dmp_Pos" in names
