# REGISTER SELECTER

Standart AHU yaziliminin **tam acik** Modbus ve BACnet register listelerini,
cihazinda gercekten bulunan fan konfigürasyonuna göre filtreleyip
cihaza özel Excel listeleri üreten Windows masüstü programi.

## Kullanim

1. **Besleme fan markasi** sec: `ebm-papst`, `Danfoss`, `Ziehl-Abegg`, `WellDrive` veya `Yok`
2. **Adet** sec (ebm-papst ve Ziehl-Abegg icin 1-4, Danfoss ve WellDrive icin 1-2)
3. Ayni secimi **Egzoz fan markasi** icin yap
4. Cihaz adini (örn. `AHU-01`) ve cikti klasörünü sec
5. **EXCEL LISTELERINI OLUSTUR** butonuna bas

Cikti: `AHU-01_Modbus_Reg_List.xlsx` ve `AHU-01_BACnet_List.xlsx`

Seçilmeyen marka bloklari ve secilen adetten fazla ünitelerin satirlari
(RPM/Power/Current/sicaklik/calisma saati + MotorAlarm/CommAlarm/WARNING/FcAlarm
satirlari) silinir. Fan markasi olmayan satirlar (sensörler, batarya, SAF/EAF
kontrol mantigi, AHU start/stop, genel alarm satirlari) aynen korunur.

## Marka bloklari (standart listedeki karsiliklari)

| Marka | Besleme | Egzoz |
|---|---|---|
| ebm-papst | `EBMFanCont..3` | `EBMFaneExCont..3` |
| Danfoss | `FC101Asp1/2` | `FC101Vant1/2` |
| Ziehl-Abegg | `ZiehlAbeggSup..3` | `ZiehlAbeggExh..3` |
| WellDrive | `WDriveAsp1/2` | `WDriveVant1/2` |

## Otomatik guncelleme

- Program her **60 saniyede bir** GitHub Releases sayfasindaki en son surumu
  kontrol eder (`api.github.com/.../releases/latest`).
- Yeni surum varsa üst bardaki yazı **yesil** olur (`YENI SURUM MEVCUT: vX.Y.Z`)
  ve **GUNCELLE** butonu aktif hale gelir.
- Küçük **Manuel Kontrol** butonu ile istedigini an kontrol tetikleyebilirsin.
- GUNCELLE: yeni EXE indirilir, eski EXE'nin yerine konur ve program yeniden
  baslar. (Yalnizca paketlenmis EXE'de calisir.)

## Guncelleme akisi (gelistirici)

1. `version.py` icindeki `__version__` degerini artir
2. `main` dalina push et
3. GitHub Actions: testler -> Windows EXE build -> smoke test -> `vX.Y.Z` tag'i ile
   Release yayinlar
4. Kullanicinin programi 1 dk icinde yesil guncelleme bildirimi gösterir

## Gelistirme

```bash
pip install -r requirements.txt pytest
pytest -v
python app.py
```

EXE manually:

```bash
pyinstaller --onefile --noconsole --name RegisterSelecter --add-data "data;data" app.py
```
