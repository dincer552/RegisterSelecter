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
   **Karisim (Mix) motoru 0 ise** `DamperCont` satirlarinin hepsi
   (`DmpAutoManSel_BMS`, `DmpMinRef_BMS`, `DmpManRef_BMS`, `CO2_Set_BMS`,
   `DmpContTypeSel`) silinir. `CO2_Set_BMS` ve `DmpContTypeSel` icin ek kosul:
   **en az bir CO2 sensoru secili** olmalidir; CO2 secilmezse karisim motoru olsa
   bile bu iki satir listeden cikar.
   **By-pass motoru 0 ise** `BypassDmpCont` satirlarinin hepsi
   (`BypassModeSelLocal_BMS`, `BypassManSetLocal_BMS`, `BypassSetLocal_BMS`,
   `BypassRecMod`) silinir; bu 4 satir karisim motorundan bagimsizdir.
4. **4. Kademe Sayilari (Isitici / DX / Nemlendirici)** – kademe sayisi girilir (0 = Yok):
   - `DX sogutucu kademe sayisi` 0-10: DxN Alarm + DXN Defrost satirlari sayiya
     gore silinir. `DX_mode`, `DX_Status1`, `CapValuee`, `CapValuee1` genel
     satirlari kademe >= 1 ise kalir.
   - `Elektrikli isitici` ve `On elektrikli isitici` kademe sayisi 0-3:
     `Heater1/2/3_ok` sayiya gore silinir; `HeaterStage` + `HighTempAlarm`
     kademe >= 1 ise kalir.
   - `Nemlendirici kademe sayisi` 0-8 (**varsayilan 0**): sayinin ustundeki
     kademelerin `HumModeSelN.Start`, `HumModeSelN.ManPosBMS`,
     `HumModeSelN.ModeSelBMS`, `Hum_RunStsN` ve `Hum_AlarmN` satirlari silinir
     (her kademe 5 satir). Ornegin 2 secilirse icinde 3-8 gecen satirlar gider.
     Sayi 0 ise `Hum_Mod_Sel` blogunun 53 satirinin tamami silinir; sayi >= 1
     ise `NumberOf_Hum`, `SaturTemp`, `CalHumSet`, `HUM_Set_bms`,
     `Sup_HUM_Max/Min_bms`, `DB_HUM_SET_bms`, `HUMContTypeSel_bms`,
     `Humectation ON`, `DeHumectation on`, `HumSet_Abs`, `Room_Abs`, `RoomHumSel`
     genel satirlari da listeye girer.
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
   - `MBUnit\BMS_Check_Read` ve `MBUnit\BMS_Check_Write` satirlari da **hicbir
     sekilde** listeye eklenmez (BMS baglanti test registerlari cihaz listesinde istenmez).
7. **7. Su Vanalari (CV / HV / CO)** – her vananin kendi satirlari tik kutusu ile
   secilir: tikli vananin pozisyon (`CV_Pos` / `HV_Pos`), geri bildirim
   (`CV_Fdb_1` / `HV_Fdb_1`), `Mode Select` ve `Manuel Referans` satirlari listeye
   girer; tik kaldirilan vananin satirlari silinir.
   - **`CV2` ve `HV2` ilk basta gorunmez.** `CV1` tiklaninca `CV2` altinda acilir,
     `HV1` tiklaninca `HV2` acilir. Ana tik kaldirilirsa alt vana otomatik
     kapanir ve tekrar gizlenir.
   - Vana satirlari da standart Excel'den otomatik algilanir; standart listeye
     `TmpControl\CV2_Pos` gibi yeni bir vana satiri eklersen programda belirir.
   - **`CO vanasi / change over (11 satir)`** ayri bir tiktir (varsayilan tikli
     degil). Tikli ise `TmpControl` altindaki 11 change-over satiri listeye girer;
     tikli degilse bu 11 satirin tamamı silinir. CV/HV tiklerinden **bagimsizdir**:
     hic vana secilmese bile CO tiki kendi satirlarini getirir, CO tiki kalksa bile
     secili vanalarin satirlari kalir.
8. **8. Rotor (Isi Geri Kazanim)** – **Rotor kontrol modu** acilir listesi:
   `Yok` (varsayilan), `Oransal`, `On/Off`.
   - `Yok` -> `RotorControl` satirlarinin **hicbiri** listeye girmez.
   - `Oransal` -> `RotorControl` altindaki **tum** satirlar girer (Mode Select,
     Manuel Set, Max Speed, Pozisyon, Active, Alarm).
   - `On/Off` -> yalnizca `RotorControl\RotorActive` ve `RotorControl\Rotor Alarm` girer.
9. **9. Nem Kontrolu** – **Nem kontrolu var** tik kutusu (varsayilan tikli degil).
   Tikli ise `Hum_Mod_Sel\HUM_Set_bms`, `Sup_HUM_Max_bms`, `Sup_HUM_Min_bms`,
   `DB_HUM_SET_bms` ve `HUMContTypeSel_bms` satirlari listeye eklenir; tikli
   degilse bu 5 satir silinir. Kademe sayisindan bagimsiz bir secimdir, fakat
   kademe 0 ise blokun hicbir satiri (bu 5 dahil) listeye girmez.
10. **10. Cikti** – cihaz adi (örn. `AHU-01`) ve cikti klasörü.
11. **EXCEL LISTELERINI OLUSTUR** butonuna bas.

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
  tum satirlari silinir. `DamperCont`'in 5 parametre satiri karisim motorunun
  varligina baglidir: karisim 0 ise hepsi silinir (islem kaydinda
  "Damper parametreleri - Karışım hava damper motoru secilmedi").
  `CO2_Set_BMS` + `DmpContTypeSel` ayrica en az bir CO2 sensoru ister; karisim
  motoru var ama CO2 secilmemisse bu iki satir "Damper parametreleri - CO2
  sensoru secilmedi" olarak silinir. `BypassDmpCont`'in 4 satiri by-pass motorunun
  varligina baglidir: by-pass 0 ise "Damper parametreleri - By-pass damper motoru
  secilmedi" olarak silinir.
- Isitici/DX kademelerinde secilen kademe sayisini asan satirlar silinir;
  kademe 0 ise grubun genel satirlari da silinir. Nemlendiricide ayni kural
  sayiya gore isler: 2 secilirse 3-8 kademelerinin 30 satiri, 0 secilirse
  `Hum_Mod_Sel` blogunun 53 satirinin tamamı silinir.
- **Nem kontrolu** tiki kaldirilirsa `HUM_Set_bms`, `Sup_HUM_Max_bms`,
  `Sup_HUM_Min_bms`, `DB_HUM_SET_bms`, `HUMContTypeSel_bms` satirlari silinir
  (islem kaydinda "Nem kontrolu - nem kontrolu secilmedi"). Kademe 0 ise bu
  5 satir zaten kademe kuraliyla silinir; tik tek basina satirlari geri getirmez.
- Blok tiklari (SAF / EAF / RunAround) kaldirilirsa o blogun tum satirlari silinir;
  blok secili degilse transmitter tiki tek basina hicbir satir geri getirmez.
- Pop-up'ta tik kaldirilan filtre alarmi satiri silinir; `Alarm_Reset` her zaman
  kalir, `TempAVG` grubu ve `MBUnit\BMS_Check_Read/Write` satirlari her zaman
  silinir (secimden bagimsiz).
- Tik kaldirilan su vanasinin (CV1/CV2/HV1/HV2) tum satirlari silinir. `CV2`/`HV2`
  kutusu ana vana secilmedigi surece gorunmez ve secilemez; ana tik kaldirilirsa
  alt vana da otomatik kapanir. Islem kaydinda "Vana satirlari - ..." olarak listelenir.
- **CO vanasi** tiki kaldirilirsa `TmpControl` altindaki 11 change-over satiri
  silinir (islem kaydinda "CO vanasi - secilmedi"). CV/HV tikleriyle bir ilgisi
  yoktur; `TmpControl`'in diger satirlari (`Tmp_Set_BMS`, `Cooling_Active` ...)
  her zaman listeye girer.
- Rotor modu `Yok` ise `RotorControl` satirlarinin 6'si da silinir ("Rotor - rotor
  secilmedi"); `On/Off` ise yalnizca `RotorActive` + `Rotor Alarm` kalir, kalan 4
  satir "Rotor - oransal satirlar (on/off secildi)" olarak listelenir.
- Sabit satirlar her zaman korunur: AHU start/stop, `AHUStart\VANTDOORSW`
  (vantilator kapak sensoru), batarya, `Air_FlowFan1/2`
  havalandirma satirlari, genel alarm satirlari, `BmsTemp_Hum`.
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
Ek olarak `DamperCont`'in 5 parametre satiri karisim motoruna baglidir:
`DmpAutoManSel_BMS`, `DmpMinRef_BMS`, `DmpManRef_BMS` yalnizca karisim motoru
adedi >= 1 iken kalir; `CO2_Set_BMS` ve `DmpContTypeSel` ayni kosula ek olarak
en az bir CO2 sensoru secilmesini ister. `BypassDmpCont`'in 4 satiri
(`BypassModeSelLocal_BMS`, `BypassManSetLocal_BMS`, `BypassSetLocal_BMS`,
`BypassRecMod`) yalnizca by-pass motoru adedi >= 1 iken kalir.

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
- `MBUnit` grubu (2 satir: `BMS_Check_Read`, `BMS_Check_Write`) da secimden
  bagimsiz **her zaman silinir**; islem kaydinda "MBUnit (BMS iletisim kontrolu)
  - kullanilmiyor" olarak listelenir.
- Standart listeye yeni `Alarm\...` satiri eklersen pop-up'ta otomatik belirir.

## Su vanalari (standart listeden otomatik)

`TmpControl\<Token>` satirlari taranir; token kalibi `CV`/`HV` + opsiyonel vana
 numarasi + `Pos` / `Fdb` / `Man_Ref` / `ModeSel` (BACnet listesindeki `=62870`
 gibi adres eki algilamayi engellemez).

| Vana | Etiket | Satirlar | UI |
|---|---|---|---|
| `CV1` | Sogutma su vanasi 1 | 4 (`CV_Pos`, `CV_Fdb_1`, `CVModeSel_BMS`, `CV_Man_Ref_BMS`) | ust seviye tik |
| `CV2` | Sogutma su vanasi 2 | 1 (`CV_Fdb_2`) | **yalnizca `CV1` secilince gorunur** |
| `HV1` | Isitma su vanasi 1 | 4 (`HV_Pos`, `HV_Fdb_1`, `HVModeSel_BMS`, `HV_Man_Ref_BMS`) | ust seviye tik |
| `HV2` | Isitma su vanasi 2 | 4 (`HV_Pos2`, `HV_Fdb_2`, `HV2ModeSel_BMS`, `HV2_Man_Ref_BMS`) | **yalnizca `HV1` secilince gorunur** |

Toplam **13 satir/protokol**. `CV2` su an sadece geri bildirim satirina sahip
(standart listede `CV2ModeSel` / `CV2_Man_Ref` / `CV_Pos2` yok); bu satirlar
standart listeye eklendiginde 2. vana kutusunda otomatik gorunur.

## CO (change over) vanasi satirlari

`TmpControl` blogunun vana kalibina uymayan 11 change-over satiri ayni adimda
**ayri tik** ile secilir (varsayilan kapali):

| Token | Aciklama |
|---|---|
| `COControl_Select` | CO kontrol secimi |
| `CoverVModeSel` | Cover valve mod secimi |
| `CoverMan_Ref` | Cover valve manuel referans |
| `COContTempValue` | CO kontrol sicaklik degeri |
| `ChangeOvFdb` | Change-over geri bildirim |
| `ChangeOvPos` | Change-over pozisyon |
| `COControl_Select_BMS` | BMS CO kontrol secimi |
| `CoverVModeSel_BMS` | BMS cover valve mod secimi |
| `CoverMan_Ref_BMS` | BMS cover valve manuel referans |
| `ChangeOverActive` | Change-over aktif |
| `ChangeOverMode` | Change-over modu |

Toplam **11 satir/protokol** (modbus 531-541, BACnet 532-542). Bu tokenlar
`CV`/`HV` vana kalibina uydugu diye vana tiklerinden ayrilir: liste sabit bir
token tablosuyla (`CO_VALVE_TOKENS`) eslesir, standart listeye yeni
`TmpControl\CO...` satiri eklersen tabloya bir satir eklemek yeterlidir.

## Kademe gruplari (standart listeden otomatik)

| Obje | Etiket | Max kademe | Kademe basina satir | Genel satir | Varsayilan |
|---|---|---|---|---|---|
| `DXControl` | DX sogutucu kademe sayısı | 10 | 2 (`DxNAlarm`, `DXNDefrost`) | 4 | 10 |
| `ElectricalHeater` | Elektrikli ısıtıcı kademe sayısı | 3 | 1 (`HeaterN_ok`) | 2 | 3 |
| `PreElectricalHeater` | Ön elektrikli ısıtıcı kademe sayısı | 3 | 1 (`HeaterN_ok`) | 2 | 3 |
| `Hum_Mod_Sel` | Nemlendirici kademe sayısı | 8 | 5 (`HumModeSelN.Start`, `.ManPosBMS`, `.ModeSelBMS`, `Hum_RunStsN`, `Hum_AlarmN`) | 13 | **0** |

Nemlendirici bloku toplam **53 satir/protokol** (8 kademe x 5 + 13 genel).
Kademe sayisini asan indeksli satirlar "Nemlendirici kademe sayısı #N", sayi 0
iken genel satirlar "Nemlendirici kademe sayısı - genel satirlar" basligiyla
silinir. Standart listeye `Hum_Mod_Sel\HumModeSel9.Start` gibi yeni bir kademe
satiri eklersen 9. kademe kutuda kendiliginden belirir.

## Nem kontrolu satirlari (standart listeden otomatik)

`Hum_Mod_Sel` blogunun 5 nem set ayar satiri ayri **Nem Kontrolu** adiminda
tik ile secilir:

| Token | Aciklama |
|---|---|
| `HUM_Set_bms` | BMS nem set degeri |
| `Sup_HUM_Max_bms` | Ufleme nem ust siniri |
| `Sup_HUM_Min_bms` | Ufleme nem alt siniri |
| `DB_HUM_SET_bms` | Dehumidification set |
| `HUMContTypeSel_bms` | Nem kontrol tipi (0=Supply, 1=Return) |

Tik kaldirilirsa 5 satirin tamamı silinir; tikliyse kademe sayisi >= 1 oldugu
surduce listeye girer.

## Rotor modu (standart listeden otomatik)

`RotorControl` blogu **6 satir/protokol** ve mod secimine gore listeye girer:

| Mod | Kalan satirlar | Adet |
|---|---|---|
| `Yok` (varsayilan) | - | 0 |
| `Oransal` | `RotorModeSelBMS`, `RotorManSetBMS`, `RotorMaxSpeed`, `RotorPos`, `RotorActive`, `Rotor Alarm` | 6 |
| `On/Off` | `RotorActive`, `Rotor Alarm` | 2 |

Rotor secimi ayri bir adimdir; standart listeye yeni `RotorControl\...` satiri
eklersen `Oransal` modunda otomatik olarak listeye girer.

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
