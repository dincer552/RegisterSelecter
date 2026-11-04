from pathlib import Path

import pytest
from openpyxl import load_workbook

from register_engine import (
    BRANDS,
    PROTOCOLS,
    RowClassification,
    classify_row,
    filter_standard_list,
    generate,
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
        ("EBMFanCont\SAF Ebm RPM=60440", RowClassification("ebm", "supply", 1)),
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
