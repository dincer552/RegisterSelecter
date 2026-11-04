# REGISTER SELECTER

Standart AHU yaziliminin **tam acik** Modbus ve BACnet register listelerini,
cihazda gercekten bulunan sensör ve fan konfigürasyonuna göre filtreleyip
cihaza özel Excel listeleri üreten Windows masüstü programi.

## Kullanim (adim adim, yukaridan asagiya)

1. **1. Sicaklik Sensorleri** – liste standart Excel'den okunur, cihazda olmayan
   sensorlerin tiki kaldirilir. Tek ölçümlü sensorler tek tik kutusudur
   (örn. *Oda Sıcaklık Sensörü*); sıcaklık + nem + CO2 (+ entropi/mutlak nem)
   içeren sensorlerde her sinyal ayri ayri secilir.
   **Tumunu Sec / Tumunu Kaldir** butonlari ile hizli isaretlenebilir.
2. **2. Fan Secimi** – **Besleme fan markasi**: `ebm-papst`, `Danfoss`, `Ziehl-Abegg`,
   `WellDrive` veya `Yok`, sonra **Adet** (ebm-papst ve Ziehl-Abegg 1-4,
   Danfoss ve WellDrive 1-2). Ayni secim **Egzoz fan markasi** icin de yapilir.
3. **3. Damper (Klape) Motorlari** – damper motorlari da standart Excel'den
   otomatik listelenir (Ufleme, Taze hava, Donus, Egzoz, Karisim, By-pass).
   Her taraf için **tik kutusu + motor adedi** (1-4). Tik kaldirilan tarafin
   pozisyon (`Dmp_Pos`), geri bildirim (`Dmp_Fdb`) ve
   CommAlarm/FeedbackAlarm/Mechanical_fault satirlari tamamen silinir.
4. **4. Isitici / DX Sogutucu Kademeleri** – kademe sayisi girilir (0 = Yok):
   - `DX sogutucu kademe sayisi` 0-10: DxN Alarm + DXN Defrost satirlari sayiya
     gore silinir. `DX_mode`, `DX_Status1`, `CapValuee`, `CapValuee1` genel
     satirlari kademe >= 1 ise kalir.
   - `Elektrikli isitici` ve `On elektrikli isitici` kademe sayisi 0-3:
     `Heater1/2/3_ok` sayiya gore silinir; `HeaterStage` + `HighTempAlarm`
     kademe >= 1 ise kalir.
5. **5. SAF / EAF ve Basincl Sensoru** – blok kullanimi tik kutusu ile secilir:
   - `SAF (ufleme fan kontrol blogu)` 21 satir + ayri `QBM97xx basincl transmitteri`
     (5 satir) tiki.
   - `EAF (egzoz fan kontrol blogu)` 21 satir + ayri `QBM97xx basincl transmitteri`
     (5 satir) tiki.
   - `RunAround (su bataryasi donma korumasi)` 4 satir.
   Blok tiki kaldirilirsa alarm satirlari dahil tum blok silinir; transmitter tiki
   kaldirilirsa `PrHighAlarm`, `PrHighAlmSet`, `DuctPress`, `DuctPressureBMS` ve
   `QBM97xx_*.CommAlarm` satirlari silinir. `Air_FlowFan1/2` satirlari her zaman kalir.
6. **6. Cikti** – cihaz adi (örn. `AHU-01`) ve cikti klasörü.
7. **EXCEL LISTELERINI OLUSTUR** butonuna bas.

Cikti: `AHU-01_Modbus_Reg_List.xlsx` ve `AHU-01_BACnet_Reg_List.xlsx`

## Ne silinir, ne kalir

- Secilmeyen marka bloklari ve secilen adetten fazla ünitelerin satirlari
  (RPM/Power/Current/sicaklik/calisma saati + MotorAlarm/CommAlarm/WARNING/FcAlarm)
  silinir.
- Tik kaldirilan sensorün ölçü satirlari silinir; hicbir sinyali secilmeyen
  sensorün **CommAlarm** satiri da silinir (en az bir sinyal seciliyorsa alarm kalir).
- Secilen adetten fazla damper motorlarinin satirlari ve tik kaldirilan tarafin
  tum satirlari silinir. `DamperCont` / `BypassDmpCont` parametre satirlari silinmez.
- Isitici/DX kademelerinde secilen kademe sayisini asan satirlar silinir;
  kademe 0 ise grubun genel satirlari da silinir.
- Blok tiklari (SAF / EAF / RunAround) kaldirilirsa o blogun tum satirlari silinir;
  blok secili degilse transmitter tiki tek basina hicbir satir geri getirmez.
- Sabit satirlar her zaman korunur: AHU start/stop, batarya, `Air_FlowFan1/2`
  havalandirma satirlari, genel alarm satirlari, `BmsTemp_Hum`, `TempAVG`, `Hum_Mod_Sel`.

## Algilanan sensorler (standart listeden otomatik)

| Sensor | Sinyaller |
|---|---|
| Ufleme / Donus / Taze Hava | Sıcaklık, Nem, CO2, Entropi, Mutlak Nem |
| Batarya Sonrasi / Egzoz / Karsim / DX Sonrasi / IsI Geri Kazanim Sonrasi / Esanjor Cikis | Sıcaklık, Nem, CO2 |
| Donus CO2 Sensörü | Sıcaklık, CO2 |
| Oda Sıcaklık (x2), Oda Nem, Oda CO2, Su Sıcaklık | tek sinyal (tik kutusu) |

Sensor listesi koda gömülü degildir; program standart Excel'i okuyarak
`Nesne\TmpVal`, `Nesne\HumVal`, `Nesne\CO2Val`, `Nesne\EntVal`, `Nesne\AbsHum`
satirlarini bulur. Standart listeye yeni sensor eklersen programda otomatik görünür.

## Damper motoru bloklari (standart listeden otomatik)

| Taraf | Besleme nesne adi | Motorlar |
|---|---|---|
| Ufleme | `SupDmpMB_Siemens..3` | 1-4 |
| Taze hava | `FreshDmpMB_Siemens..3` | 1-4 |
| Donus | `ReturnDmpMB_Siemens..3` | 1-4 |
| Egzoz | `ExtDmpMB_Siemens..3` | 1-4 |
| Karisim | `MixDmpMB_Siemens..3` | 1-4 |
| By-pass | `ByPassDmpMB_Siemens..3` | 1-4 |

Her motor 4 satir (Dmp_Fdb + CommAlarm + FeedbackAlarm + Mechanical_fault),
tarafin kendisi 1 `Dmp_Pos` satiri -> toplam **102 satir/protokol**.
`<Taraf>DmpMB_<Marka>` kalibina uyan yeni markalar da otomatik listelenir.

## Blok secimleri (SAF / EAF / RunAround)

| Blok | Satirlar | Ayri tik |
|---|---|---|
| `SAF` ufleme fan kontrol | 21 | `QBM97xx basincl transmitteri` 5 satir (`PrHighAlarm`, `PrHighAlmSet`, `DuctPress`, `DuctPressureBMS`, `QBM97xx_SAF.CommAlarm`) |
| `EAF` egzoz fan kontrol | 21 | ayni transmitter 5 satir (`QBM97xx_EAF.CommAlarm`) |
| `RunAroundCont` su bataryasi donma korumasi | 4 | - |

Toplam **56 satir/protokol**. Blok isimleri `FEATURE_GROUPS` tablosundan gelir;
standart listeye yeni blok eklerken sadece bu tabloya satir eklemek yeterlidir.

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
