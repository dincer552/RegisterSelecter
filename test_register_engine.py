from pathlib import Path

import pytest
from openpyxl import load_workbook

from register_engine import (
    BRANDS,
    PROTOCOLS,
    RowClassification,
    classify_row,
    detect_sensor_groups,
    filter_standard_list,
    generate,
    list_sensor_groups,
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


def _sensor_run(tmp_path, protocol, sensor_selection, out_name=None, **fan):
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
        protocol = "modbus" if "Modbus" in res.protocol else "bacnet"
        names = _names(res, protocol)
        assert "Room Temp1" not in names
        if protocol == "modbus":
            assert r"Room Temp\Room Temp" in names
