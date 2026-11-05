# REGISTER SELECTER

Standart AHU yaziliminin **tam acik** Modbus ve BACnet register listelerini,
cihazda gercekten bulunan sensör ve fan konfigürasyonuna göre filtreleyip
cihaza özel Excel listeleri üreten Windows masaüstü programi.

## Kullanim (adim adim, yukaridan asagiya)

1. **1. Sicaklik Sensorleri** – liste standart Excel'den okunur, cihazda olmayan
   sensorlerin tiki kaldirilir. Tek ölçümlü sensorler tek tik kutusudur
   (örn. *Oda Sıcaklık Sensörü*); sıcaklık + nem + CO2 (+ entropi/mutlak nem)
   içeren sensorlerde her sinyal ayri ayri secilir.
   **Tumunu Sec / Tumunu Kaldir** butonlari ile hizli isaretlenebilir.
2. **2. Fan Secimi** – **Besleme fan markasi**: `ebm-papst`, `Danfoss`, `Ziehl-Abegg`,
   `WellDrive` veya `Yok`, sonra **Adet** (ebm-papst ve Ziehl-Abegg 1-4,
   Danfoss ve WellDrive 1-2). Ayni secim **Egzoz fan markasi** icin de yapilir.
   Fan kapak sensorleri bu secime baglidir: `AHUStart\VANTDOORSW` (vantilator)
   **her zaman** kalir, `AHUStart\ASPDOORSW` (aspirator) yalnizca **en az 1 egzoz
   fani secildiginde** listeye girer; marka veya adet farketmez.
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
6. **6. Filtre Alarmlari** – **FILTRE ALARMLARINI SEC (19)** butonu pop-up acar.
   Standart Excel'den okunan 19 filtre kirlilik alarmi tek tek tiklanir; tik
   kaldirilan alarmin `Alarm\<Token>` satiri listeden silinir.
   **Tumunu Sec / Tumunu Kaldir** butonlari ve `Secili: x/19` sayaci pop-up
   icinde de guncellenir. Pop-up acikken fare tekerlegi pop-up listesini kaydirdir.
   - `Alarm_Reset\Alarm_Reset` satiri **her zaman** listeye eklenir (tik ile degismez).
   - `TempAVG` grubu (ortalama oda sicakligi) **hicbir sekilde** listeye eklenmez.
7. **7. Cikti** – cihaz adi (örn. `AHU-01`) ve cikti klasörü.
8. **EXCEL LISTELERINI OLUSTUR** butonuna bas.

Cikti: `AHU-01_Modbus_Reg_List.xlsx` ve `AHU-01_BACnet_Reg_List.xlsx`

Bolumler **fare tekerlegi** ile kaydirilir; imlec bir etiketin/tik kutusunun
uzerindeyken de calisir. Tekerlek spinbox veya marka kutusunun uzerindeyken
**degeri degistirmez**, yine sayfayi kaydirdir (yanlislikla secim bozmamak icin).
Islem Kaydi alaninin tekerlegi kendi metnini kaydirir.

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
- Pop-up'ta tik kaldirilan filtre alarmi satiri silinir; `Alarm_Reset` her zaman
  kalir, `TempAVG` grubu her zaman silinir (secimden bagimsiz).
- Sabit satirlar her zaman korunur: AHU start/stop, `AHUStart\VANTDOORSW`
  (vantilator kapak sensoru), batarya, `Air_FlowFan1/2`
  havalandirma satirlari, genel alarm satirlari, `BmsTemp_Hum`, `Hum_Mod_Sel`.
- `AHUStart\ASPDOORSW` (aspirator kapak sensoru) egzoz fani `Yok` secildiginde
  silinir; islem kaydinda "Fan kapak sensoru - aspirator secilmedi" olarak listelenir.

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

## Filtre alarmlari (standart listeden otomatik)

Program `Alarm\<Token>` satirlarini standart Excel'den tarar; pop-up'ta tek tek
secilir. Etiket sutunu bos ya da register adinin ayni ise etiket token'dan
uretilir (`FreshM5FilterAlm` -> `Fresh M5 Filter Alarm`).

| Grup | Token kalibi | Adet |
|---|---|---|
| Taraf bazli kirli filtre alarmlari | `{Fresh,Return,Supply}{M5,G4,F7,F9,G2}FilterAlm` | 15 |
| Ozel filtreler | `CarbonFilterAlm`, `HepaFilterAlm`, `H13FilterAlm`, `NuclearHepaFilterAlm` | 4 |

Toplam **19 alarm satiri/protokol**. Ayrica:

- `Alarm_Reset\Alarm_Reset` (1 satir) **sabit** kalir, pop-up'ta listelenmez.
- `TempAVG` grubu (5 satir) secimden bagimsiz **her zaman silinir**.
- Standart listeye yeni `Alarm\...` satiri eklersen pop-up'ta otomatik belirir.

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
- GUNCELLE: **ilerleme penceresi** acilir ve indirme su an ekranin ortasinda
  canli takip edilir: `3.2 MB / 12.8 MB  %25  2.0 MB/s` (yesil üst bar da
  `Indiriliyor %25` gosterir).
- Indirme biter, pencerede `12.8 MB indirildi - program yeniden baslatiliyor...`
  yazar; kisa bir beklemenin ardindan program **kapanir**, yeni EXE eskisinin
  yerine konur ve **yeni EXE kendiliginden baslar**.
- Indirme yanda kalirsa (boyut tutmuyorsa) veya 1 MB'den kucukse guncelleme
  **iptal edilir**, yarim dosya silinir, eski surum oldugu gibi kalir.
- Pencere indirme sirasinda kapatilamaz; hata olursa GUNCELLE butonu geri acilir.
- (Yalnizca paketlenmis EXE'de calisir; kaynak koddan calistirildiginda bilgi
  verir.)

## Guncelleme akisi (gelistirici)

1. `version.py` icindeki `__version__` degerini artir
2. `main` dalina push et
3. GitHub Actions: testler -> Windows EXE build -> **`--selftest` + smoke test**
   -> `vX.Y.Z` tag'i ile Release yayinlar.
   `RegisterSelecter.exe --selftest` arayuzun tum bolumlerini kurup hatasiz
   cikar; bolumlerden biri patlarsa release hic yayinlanmaz.
4. Kullanicinin programi 1 dk icinde yesil guncelleme bildirimi gösterir

## Gelistirme

```bash
pip install -r requirements.txt pytest
pytest -v            # test_register_engine.py (liste filtre) + test_updater.py (indirme)
python app.py
python app.py --selftest   # arayuz bolumlerini kurup cikar, CI release kapisi
```

EXE manually:

```bash
pyinstaller --onefile --noconsole --name RegisterSelecter --add-data "data;data" app.py
```
