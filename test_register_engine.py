from pathlib import Path

import pytest
from openpyxl import load_workbook

from register_engine import (
    BRANDS,
    PROTOCOLS,
    VALVE_GROUP_PREFIX,
    RowClassification,
    classify_damper,
    classify_row,
    classify_valve,
    detect_damper_groups,
    detect_filter_alarms,
    detect_sensor_groups,
    detect_stage_groups,
    detect_valve_groups,
    filter_standard_list,
    generate,
    list_damper_groups,
    list_feature_groups,
    list_filter_alarms,
    list_sensor_groups,
    list_stage_groups,
    list_valve_groups,
    parse_object_token,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
MODBUS = DATA_DIR / PROTOCOLS["modbus"]["file"]
BACNET = DATA_DIR / PROTOCOLS["bacnet"]["file"]

# Veriden dogrulanan toplam fan satiri sayisi (her protokolde).
EXPECTED_TOTAL_FAN_ROWS = 216
# TempAVG (ortalama oda sicakligi) bloge register listesine HIC eklenmez.
EXPECTED_TOTAL_TEMPAVG_ROWS = 5
# EBM 4+4 secildiginde listede kalan tek "silinmeyen" sayilari bu temele gore okunur.
FAN_BASELINE_REMOVED = EXPECTED_TOTAL_FAN_ROWS - 64 + EXPECTED_TOTAL_TEMPAVG_ROWS


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
    # fan disinda yalnizca TempAVG bloge kalici olarak silinir
    assert res.removed_rows == FAN_BASELINE_REMOVED
    assert res.removed_by_group["TempAVG (ortalama oda sicakligi) - kullanilmiyor"] == EXPECTED_TOTAL_TEMPAVG_ROWS


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
    assert res.removed_rows == EXPECTED_TOTAL_FAN_ROWS - 24 + EXPECTED_TOTAL_TEMPAVG_ROWS

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
    assert res.removed_rows == FAN_BASELINE_REMOVED
    # hicbir sensör satiri silinmemeli (silinen gruplar yalnizca fan bloklari + TempAVG)
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
    # sabit satirlar (BMS sicaklik / nem modu) her zaman kalir
    assert r"BmsTemp_Hum\RoomTempFromBms" in _names(res, "modbus")
    assert r"Hum_Mod_Sel\Room_Abs" in _names(res, "modbus")
    # TempAVG artik hicbir cihazda listeye eklenmez
    assert r"TempAVG\Room_TempAVG" not in _names(res, "modbus")


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
# Karışım motoru seçilmediğinde silinen DamperCont parametre satırları
EXPECTED_DMP_PARAM_ROWS = 3
DMP_PARAM_GROUP = "Damper parametreleri - Karışım hava damper motoru secilmedi"
DMP_PARAM_TOKENS = (r"DamperCont\DmpAutoManSel_BMS", r"DamperCont\DmpMinRef_BMS", r"DamperCont\DmpManRef_BMS")
# CO2 sensoru de isteyen iki satir
EXPECTED_DMP_CO2_ROWS = 2
DMP_CO2_GROUP = "Damper parametreleri - CO2 sensoru secilmedi"
DMP_CO2_TOKENS = (r"DamperCont\CO2_Set_BMS", r"DamperCont\DmpContTypeSel")


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
    assert res.removed_rows == FAN_BASELINE_REMOVED
    names = _names(res, "modbus")
    for token in DMP_PARAM_TOKENS:
        assert token in names


def test_damper_zero_selection_removes_whole_block(tmp_path):
    res = _sensor_run(tmp_path, "modbus", None, damper_selection={}, out_name="none.xlsx")
    assert res.kept_damper_rows == 0
    assert res.removed_rows == (
        FAN_BASELINE_REMOVED + EXPECTED_TOTAL_DAMPER_ROWS + EXPECTED_DMP_PARAM_ROWS + EXPECTED_DMP_CO2_ROWS
    )
    names = _names(res, "modbus")
    assert "DmpMB_Siemens" not in names
    # karisim motoru 0 -> 5 DamperCont parametre satirinin hepsi silinir
    for token in DMP_PARAM_TOKENS + DMP_CO2_TOKENS:
        assert token not in names
    assert res.removed_by_group[DMP_PARAM_GROUP] == EXPECTED_DMP_PARAM_ROWS + EXPECTED_DMP_CO2_ROWS
    # BypassDmpCont satirlari karisim damperinden bagimsiz, her zaman kalir
    assert r"BypassDmpCont\BypassRecMod" in names


def test_damper_unit_counts_per_side(tmp_path):
    selection = {"Sup|Siemens": 2, "Fresh|Siemens": 1, "Return|Siemens": 4,
                 "Ext|Siemens": 0, "Mix|Siemens": 3, "ByPass|Siemens": 4}
    res = _sensor_run(tmp_path, "modbus", None, damper_selection=selection, out_name="mixed.xlsx")
    # taraf basina: 1 pozisyon + N motor x 4 satir
    assert res.kept_damper_rows == (1 + 8) + (1 + 4) + (1 + 16) + 0 + (1 + 12) + (1 + 16)
    assert res.removed_rows == FAN_BASELINE_REMOVED + (EXPECTED_TOTAL_DAMPER_ROWS - res.kept_damper_rows)
    names = _names(res, "modbus")
    assert r"SupDmpMB_Siemens1\Dmp_Fdb" in names
    assert r"SupDmpMB_Siemens2\Dmp_Fdb" not in names
    assert r"FreshDmpMB_Siemens\Dmp_Pos" in names
    assert r"FreshDmpMB_Siemens1\FreshDmpMB_Siemens1.CommAlarm" not in names
    assert "ExtDmpMB_Siemens" not in names
    assert res.removed_by_group["Egzoz damper motoru #1"] == 5
    assert res.removed_by_group["Taze hava damper motoru #2"] == 4


@pytest.mark.parametrize("protocol", ["modbus", "bacnet"])
def test_damper_param_rows_follow_mix_count(tmp_path, protocol):
    """Karisim motoru >= 1 ise DamperCont parametre satirlari kalir, 0 ise hepsi silinir."""
    kept = _sensor_run(tmp_path, protocol, None, damper_selection={"Mix|Siemens": 1},
                       out_name=f"mix1_{protocol}.xlsx")
    names = _names(kept, protocol)
    for token in DMP_PARAM_TOKENS + DMP_CO2_TOKENS:
        assert token in names
    assert DMP_PARAM_GROUP not in kept.removed_by_group

    dropped = _sensor_run(tmp_path, protocol, None, damper_selection={"Mix|Siemens": 0},
                          out_name=f"mix0_{protocol}.xlsx")
    names = _names(dropped, protocol)
    for token in DMP_PARAM_TOKENS + DMP_CO2_TOKENS:
        assert token not in names
    assert dropped.removed_by_group[DMP_PARAM_GROUP] == EXPECTED_DMP_PARAM_ROWS + EXPECTED_DMP_CO2_ROWS


@pytest.mark.parametrize("protocol", ["modbus", "bacnet"])
def test_damper_co2_param_rows_need_co2_sensor(tmp_path, protocol):
    """CO2_Set_BMS ve DmpContTypeSel karisim motoru + en az bir CO2 sensoru ister."""
    all_sensors = {g.obj: [c for c, _ in g.signals] for g in list_sensor_groups(DATA_DIR)}
    assert any("co2" in codes for codes in all_sensors.values())
    mix_only = {"Mix|Siemens": 1}

    with_co2 = _sensor_run(tmp_path, protocol, all_sensors, damper_selection=mix_only,
                           out_name=f"co2on_{protocol}.xlsx")
    names = _names(with_co2, protocol)
    for token in DMP_PARAM_TOKENS + DMP_CO2_TOKENS:
        assert token in names
    assert DMP_CO2_GROUP not in with_co2.removed_by_group

    no_co2 = {obj: [c for c in codes if c != "co2"] for obj, codes in all_sensors.items()}
    without_co2 = _sensor_run(tmp_path, protocol, no_co2, damper_selection=mix_only,
                              out_name=f"co2off_{protocol}.xlsx")
    names = _names(without_co2, protocol)
    for token in DMP_CO2_TOKENS:
        assert token not in names
    for token in DMP_PARAM_TOKENS:  # bunlar yalnizca karisim motoruna bagli
        assert token in names
    assert without_co2.removed_by_group[DMP_CO2_GROUP] == EXPECTED_DMP_CO2_ROWS
    assert DMP_PARAM_GROUP not in without_co2.removed_by_group


def test_damper_param_rows_untouched_without_damper_step(tmp_path):
    """Damper adimi hic kullanilmazsa (selection None) davranis degismez."""
    res = _sensor_run(tmp_path, "modbus", None)
    names = _names(res, "modbus")
    for token in DMP_PARAM_TOKENS + DMP_CO2_TOKENS:
        assert token in names
    assert DMP_PARAM_GROUP not in res.removed_by_group


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
    assert res.removed_rows == FAN_BASELINE_REMOVED


def test_stage_zero_selection_removes_all(tmp_path):
    res = _sensor_run(tmp_path, "bacnet", None, stage_selection={}, out_name="ba.xlsx")
    assert res.kept_stage_rows == 0
    assert res.removed_rows == FAN_BASELINE_REMOVED + EXPECTED_TOTAL_STAGE_ROWS
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


# ---------- SAF / EAF / RunAround blok secimi ----------

# SAF 21+5, EAF 21+5, RunAroundCont 4
EXPECTED_TOTAL_FEATURE_ROWS = 56


def test_list_feature_groups():
    groups = {g.obj: g for g in list_feature_groups(DATA_DIR)}
    assert list(groups) == ["SAF", "EAF", "RunAroundCont"]
    assert groups["SAF"].options[0] == ("main", "Kullaniliyor", 21)
    assert groups["SAF"].options[1] == ("press", "QBM97xx basınç transmitteri", 5)
    assert groups["SAF"].total_rows == 26
    assert groups["RunAroundCont"].total_rows == 4
    assert sum(g.total_rows for g in groups.values()) == EXPECTED_TOTAL_FEATURE_ROWS


def test_feature_full_selection(tmp_path):
    all_opts = {g.obj: [c for c, _, _ in g.options] for g in list_feature_groups(DATA_DIR)}
    res = _sensor_run(tmp_path, "modbus", None, feature_selection=all_opts)
    assert res.total_feature_rows == EXPECTED_TOTAL_FEATURE_ROWS
    assert res.kept_feature_rows == EXPECTED_TOTAL_FEATURE_ROWS
    assert res.removed_rows == FAN_BASELINE_REMOVED


def test_feature_none_selection_removes_blocks(tmp_path):
    res = _sensor_run(tmp_path, "bacnet", None, feature_selection={}, out_name="ba.xlsx")
    assert res.kept_feature_rows == 0
    assert res.removed_rows == FAN_BASELINE_REMOVED + EXPECTED_TOTAL_FEATURE_ROWS
    names = _names(res, "bacnet")
    for token in ("SAF\\", "EAF\\", "QBM97xx", "RunAroundCont"):
        assert token not in names
    # fan ve sensör bloklari etkilenmez
    assert "EBMFanCont" in names


def test_feature_pressure_transmitter_optional(tmp_path):
    selection = {"SAF": ["main"], "EAF": ["main"], "RunAroundCont": ["main"]}
    res = _sensor_run(tmp_path, "modbus", None, feature_selection=selection, out_name="nopress.xlsx")
    assert res.kept_feature_rows == EXPECTED_TOTAL_FEATURE_ROWS - 10
    names = _names(res, "modbus")
    assert r"SAF\SAF.lowAirAlarm" in names
    assert r"SAF\SAF.Air_FlowFan2" in names
    assert r"SAF\SAF.DuctPress" not in names
    assert r"SAF\SAF.PrHighAlmSet" not in names
    assert r"QBM97xx_SAF\QBM97xx_SAF.CommAlarm" not in names
    assert res.removed_by_group["SAF (üfleme fan kontrol bloğu) - QBM97xx basınç transmitteri"] == 5


def test_feature_sub_option_needs_main(tmp_path):
    selection = {"SAF": ["press"], "EAF": ["main", "press"], "RunAroundCont": []}
    res = _sensor_run(tmp_path, "modbus", None, feature_selection=selection, out_name="odd.xlsx")
    names = _names(res, "modbus")
    assert "SAF\\" not in names and "QBM97xx_SAF" not in names
    assert r"EAF\EAF.DuctPress" in names
    assert "RunAroundCont" not in names


# ---------- filtre alarmlari (pop-up ile tek tek secim) ----------

EXPECTED_TOTAL_FILTER_ALARM_ROWS = 19


@pytest.mark.parametrize("protocol", ["modbus", "bacnet"])
def test_detect_filter_alarms_labels(protocol):
    cfg = PROTOCOLS[protocol]
    ws = load_workbook(DATA_DIR / cfg["file"]).active
    alarms = detect_filter_alarms(ws, cfg["name_col"], cfg["label_col"], cfg["header_row"])
    assert len(alarms) == EXPECTED_TOTAL_FILTER_ALARM_ROWS
    labels = {a.token: a.label for a in alarms}
    assert labels["FreshM5FilterAlm"] == "Fresh M5 Filter Alarm"
    # modbus'ta bu satirin etiket sutunu register adiyla ayni; yine de okunur etiket uretilir
    assert "\\" not in labels["CarbonFilterAlm"]
    assert all(a.label and "\\" not in a.label for a in alarms)


def test_list_filter_alarms_union_is_readable():
    alarms = list_filter_alarms(DATA_DIR)
    assert len(alarms) == EXPECTED_TOTAL_FILTER_ALARM_ROWS
    assert {a.token for a in alarms} == {
        "CarbonFilterAlm", "HepaFilterAlm", "H13FilterAlm", "NuclearHepaFilterAlm",
    } | {f"{side}{cls}FilterAlm" for side in ("Fresh", "Return", "Supply") for cls in ("M5", "G4", "F7", "F9", "G2")}


def test_filter_alarm_selection_keeps_only_chosen(tmp_path):
    tokens = [a.token for a in list_filter_alarms(DATA_DIR)]
    all_res = _sensor_run(tmp_path, "modbus", None, alarm_selection=tokens, out_name="alm_all.xlsx")
    some_res = _sensor_run(tmp_path, "modbus", None, alarm_selection=["FreshG4FilterAlm", "H13FilterAlm"],
                           out_name="alm_some.xlsx")
    none_res = _sensor_run(tmp_path, "modbus", None, alarm_selection=[], out_name="alm_none.xlsx")
    assert all_res.kept_alarm_rows == EXPECTED_TOTAL_FILTER_ALARM_ROWS
    assert some_res.kept_alarm_rows == 2
    assert none_res.kept_alarm_rows == 0
    assert all_res.total_alarm_rows == some_res.total_alarm_rows == EXPECTED_TOTAL_FILTER_ALARM_ROWS

    names = _names(some_res, "modbus")
    assert r"Alarm\FreshG4FilterAlm" in names and r"Alarm\H13FilterAlm" in names
    assert r"Alarm\FreshM5FilterAlm" not in names
    assert some_res.removed_by_group["Filtre alarmi - Fresh M5 Filter Alarm"] == 1
    assert none_res.removed_rows - all_res.removed_rows == EXPECTED_TOTAL_FILTER_ALARM_ROWS


@pytest.mark.parametrize("protocol", ["modbus", "bacnet"])
def test_tempavg_group_is_never_included(tmp_path, protocol):
    tokens = [a.token for a in list_filter_alarms(DATA_DIR)]
    res = _sensor_run(tmp_path, protocol, None, alarm_selection=tokens, out_name=f"avg_{protocol}.xlsx")
    names = _names(res, protocol)
    for token in ("Room1En", "Room2En", "Room3En", "Room4En", "Room_TempAVG"):
        assert rf"TempAVG\{token}" not in names
    assert res.removed_by_group["TempAVG (ortalama oda sicakligi) - kullanilmiyor"] == EXPECTED_TOTAL_TEMPAVG_ROWS


def test_tempavg_dropped_even_without_alarm_selection(tmp_path):
    res = _sensor_run(tmp_path, "modbus", None, out_name="avg_noalarm.xlsx")
    assert "TempAVG\\" not in _names(res, "modbus")


def test_alarm_reset_is_always_included(tmp_path):
    res = _sensor_run(tmp_path, "modbus", None, alarm_selection=[], out_name="reset.xlsx")
    names = _names(res, "modbus")
    assert r"Alarm_Reset\Alarm_Reset" in names
    other = _sensor_run(tmp_path, "bacnet", None, out_name="reset_ba.xlsx")
    assert r"Alarm_Reset\Alarm_Reset" in _names(other, "bacnet")


# ---------- fan kapak sensorleri: AHUStart\VANTDOORSW / AHUStart\ASPDOORSW ----------

ASPDOORSW_GROUP = "Fan kapak sensoru - aspirator secilmedi"


@pytest.mark.parametrize("protocol", ["modbus", "bacnet"])
def test_vantdoorsw_is_always_included(tmp_path, protocol):
    """Fan secimi hic olmasa bile vantilator kapak sensoru listede kalmali."""
    res = _sensor_run(
        tmp_path, protocol, None, out_name=f"door_{protocol}.xlsx",
        supply_brand=None, supply_count=0, exhaust_brand=None, exhaust_count=0,
    )
    names = _names(res, protocol)
    assert r"AHUStart\VANTDOORSW" in names
    assert r"AHUStart\ASPDOORSW" not in names
    assert res.removed_by_group[ASPDOORSW_GROUP] == 1


@pytest.mark.parametrize("protocol", ["modbus", "bacnet"])
def test_aspdoorsw_needs_any_exhaust_fan(tmp_path, protocol):
    """Egzoz fani markasi/secilen adetten bagimsiz: en az 1 aspirator varsa satir kalir."""
    no_exhaust = _sensor_run(
        tmp_path, protocol, None, out_name=f"door_no_{protocol}.xlsx",
        exhaust_brand=None, exhaust_count=0,
    )
    one_exhaust = _sensor_run(
        tmp_path, protocol, None, out_name=f"door_one_{protocol}.xlsx",
        exhaust_brand="danfoss", exhaust_count=1,
    )
    assert r"AHUStart\ASPDOORSW" in _names(one_exhaust, protocol)
    assert ASPDOORSW_GROUP not in one_exhaust.removed_by_group
    for res, door_rows in ((one_exhaust, 0), (no_exhaust, 1)):
        assert res.removed_rows == (
            (EXPECTED_TOTAL_FAN_ROWS - res.kept_fan_rows) + EXPECTED_TOTAL_TEMPAVG_ROWS + door_rows
        )


# ---------- su vanalari: CV1 / CV2 / HV1 / HV2 ----------

# CV1 4 + CV2 1 + HV1 4 + HV2 4 = 13 satir/protokol
EXPECTED_TOTAL_VALVE_ROWS = 13
VALVE_ROWS = {
    "CV1": ("CV_Pos", "CV_Fdb_1", "CVModeSel_BMS", "CV_Man_Ref_BMS"),
    "CV2": ("CV_Fdb_2",),
    "HV1": ("HV_Pos", "HV_Fdb_1", "HVModeSel_BMS", "HV_Man_Ref_BMS"),
    "HV2": ("HV_Pos2", "HV_Fdb_2", "HV2ModeSel_BMS", "HV2_Man_Ref_BMS"),
}


@pytest.mark.parametrize(
    "obj,tok,expected",
    [
        ("TmpControl", "CV_Pos", "CV1"),
        ("TmpControl", "CV_Fdb_1", "CV1"),
        ("TmpControl", "CVModeSel_BMS", "CV1"),
        ("TmpControl", "CV_Man_Ref_BMS", "CV1"),
        ("TmpControl", "CV_Fdb_2", "CV2"),
        ("TmpControl", "HV_Pos", "HV1"),
        ("TmpControl", "HV_Fdb_2", "HV2"),
        ("TmpControl", "HV_Pos2", "HV2"),
        ("TmpControl", "HV2ModeSel_BMS", "HV2"),
        ("TmpControl", "HV2_Man_Ref_BMS", "HV2"),
        # vana olmayan TmpControl satirlari secime tabi degil
        ("TmpControl", "Tmp_Set_BMS", None),
        ("TmpControl", "Cooling_Active", None),
        ("TmpControl", "Control_Select_BMS", None),
        ("TmpControl", "CoverMan_Ref_BMS", None),
        # baska nesneler vana sayilmaz
        ("SAF", "SAF.ManualReferanceBMS", None),
        ("AHUStart", "VANTDOORSW", None),
    ],
)
def test_classify_valve(obj, tok, expected):
    assert classify_valve(obj, tok) == expected


@pytest.mark.parametrize("protocol", ["modbus", "bacnet"])
def test_detect_valve_groups(protocol):
    cfg = PROTOCOLS[protocol]
    ws = load_workbook(DATA_DIR / cfg["file"]).active
    groups = {g.key: g for g in detect_valve_groups(ws, cfg["name_col"], cfg["header_row"])}
    assert list(groups) == ["CV1", "CV2", "HV1", "HV2"]
    assert sum(g.rows for g in groups.values()) == EXPECTED_TOTAL_VALVE_ROWS
    assert groups["CV2"].parent == "CV1" and groups["HV2"].parent == "HV1"
    assert groups["CV1"].parent is None
    assert groups["CV1"].label == "Sogutma su vanasi 1 (CV1)"
    assert groups["HV1"].label == "Isitma su vanasi 1 (HV1)"


def test_list_valve_groups_covers_both_protocols():
    groups = list_valve_groups(DATA_DIR)
    assert [g.key for g in groups] == ["CV1", "CV2", "HV1", "HV2"]
    assert {g.rows for g in groups} == {1, 4}


def test_valve_selection_keeps_only_chosen_valves(tmp_path):
    chosen = ["CV1", "HV1", "HV2"]
    res = _sensor_run(tmp_path, "modbus", None, valve_selection=chosen, out_name="valve.xlsx")
    assert res.total_valve_rows == EXPECTED_TOTAL_VALVE_ROWS
    assert res.kept_valve_rows == 12
    names = _names(res, "modbus")
    for key, tokens in VALVE_ROWS.items():
        for token in tokens:
            present = rf"TmpControl\{token}" in names
            assert present == (key in chosen), (key, token, present)
    assert res.removed_by_group[f"{VALVE_GROUP_PREFIX}Sogutma su vanasi 2 (CV2)"] == 1


def test_valve_step_unused_keeps_every_valve_row(tmp_path):
    """vane adimi kullanilmazsa (valve_selection=None) hicbir vana satiri silinmez."""
    res = _sensor_run(tmp_path, "modbus", None, out_name="valve_off.xlsx")
    assert res.total_valve_rows == 0
    names = _names(res, "modbus")
    for tokens in VALVE_ROWS.values():
        for token in tokens:
            assert rf"TmpControl\{token}" in names


def test_valve_none_selection_removes_all_valve_rows(tmp_path):
    baseline = _sensor_run(tmp_path, "modbus", None, out_name="valve_base.xlsx")
    none_res = _sensor_run(tmp_path, "modbus", None, valve_selection=[], out_name="valve_none.xlsx")
    assert none_res.kept_valve_rows == 0
    assert none_res.removed_rows - baseline.removed_rows == EXPECTED_TOTAL_VALVE_ROWS
    names = _names(none_res, "modbus")
    for tokens in VALVE_ROWS.values():
        for token in tokens:
            assert rf"TmpControl\{token}" not in names
    # sicaklik setpoint gibi sabit TmpControl satirlari korunur
    assert r"TmpControl\Tmp_Set_BMS" in names


def test_generate_passes_valve_selection(tmp_path):
    results = generate(
        data_dir=DATA_DIR,
        output_dir=tmp_path,
        device_prefix="AHU-09",
        supply_brand="ebm",
        supply_count=1,
        exhaust_brand="ebm",
        exhaust_count=1,
        valve_selection=["HV1", "HV2"],
    )
    for res in results:
        protocol = "modbus" if res.protocol == "MODBUS" else "bacnet"
        assert res.kept_valve_rows == 8
        names = _names(res, protocol)
        assert "CV_" not in names and "CVModeSel" not in names
        assert r"TmpControl\HV2_Man_Ref_BMS" in names
