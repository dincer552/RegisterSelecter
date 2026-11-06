"""REGISTER SELECTER - cihaz bazli Modbus/BACnet register listesi uretici."""

from __future__ import annotations

import json
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import updater
from register_engine import (
    ALARM_GROUP_PREFIX,
    ALWAYS_DROPPED_LABELS,
    BRANDS,
    CO_VALVE_GROUP_PREFIX,
    CO_VALVE_OBJECT,
    CO_VALVE_TOKENS,
    DAMPER_PARAM_GROUP_PREFIX,
    DamperGroup,
    FAN_DOOR_GROUP_PREFIX,
    FeatureGroup,
    FilterAlarm,
    HUM_CTRL_GROUP_PREFIX,
    HUM_CTRL_OBJECT,
    HUM_CTRL_TOKENS,
    ROTOR_DEFAULT_MODE,
    ROTOR_GROUP_PREFIX,
    ROTOR_MODES,
    SensorGroup,
    StageGroup,
    VALVE_GROUP_PREFIX,
    ValveGroup,
    generate,
    list_damper_groups,
    list_feature_groups,
    list_filter_alarms,
    list_sensor_groups,
    list_stage_groups,
    list_valve_groups,
    stage_default,
)
from version import __version__

APP_TITLE = "REGISTER SELECTER"
CHECK_INTERVAL_MS = 60_000
WHEEL_NOTCH_ROWS = 3
# Varsayilanlar degistiginde (filtre alarmlari tik siz yapildi) eski kayitlarda
# sakli tikler geri yuklenmesin diye config'e surulen damga.
DEFAULTS_REV = 1

BG = "#f4f6f8"
HEADER_BG = "#1f2a37"
ACCENT = "#0b6e4f"
GREEN_NEW = "#16a34a"
GRAY = "#9aa5b1"
RED = "#b91c1c"

BRAND_CHOICES = [("Yok", None)] + [(cfg["label"], key) for key, cfg in BRANDS.items()]
ROTOR_CHOICES = [(label, key) for key, label in ROTOR_MODES.items()]


def resource_path(relative: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent / relative


def config_file() -> Path:
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    return root / "register_selecter.json"


def fmt_mb(size_bytes: float) -> str:
    return f"{size_bytes / (1024 * 1024):.1f} MB"


class ScrollFrame(tk.Frame):
    """Dikey kaydirilmali bolum kabini."""

    def __init__(self, parent) -> None:
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.inner_id, width=e.width))

    def wheel_scroll(self, delta: int) -> None:
        """Tekerlek tekerlegi kadar kaydirir (App.bind_all cagirisindan gelir)."""
        if delta == 0:
            return
        self.canvas.yview_scroll((-1 if delta > 0 else 1) * WHEEL_NOTCH_ROWS, "units")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_TITLE} v{__version__}")
        self.geometry("960x740")
        self.minsize(800, 560)
        self.configure(bg=BG)

        self._update_info: updater.ReleaseInfo | None = None
        self._update_dialog: tk.Toplevel | None = None
        self.alarm_popup: tk.Toplevel | None = None
        self.progress_bar: ttk.Progressbar | None = None
        self.progress_label: tk.Label | None = None
        self._checking = False
        self._downloading = False
        self._frozen = getattr(sys, "frozen", False)

        self._build_header()
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=16, pady=8)
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        # spinbox/combobox uzerinde tekerlek degeri degistirmesin, sayfayi kaydirdirsin
        for cls in ("Spinbox", "TCombobox"):
            self.bind_class(cls, "<MouseWheel>", lambda e: (self._on_mousewheel(e), "break")[1])
        body = self.scroll.inner
        self._build_sensor_section(body)
        self._build_fan_section(body)
        self._build_damper_section(body)
        self._build_stage_section(body)
        self._build_feature_section(body)
        self._build_alarm_section(body)
        self._build_valve_section(body)
        self._build_rotor_section(body)
        self._build_hum_control_section(body)
        self._build_output_section(body)
        self._load_config()

        self.after(3000, self._auto_check)

    # ---------- mouse wheel ----------
    def _on_mousewheel(self, event) -> None:
        if getattr(event.widget, "winfo_class", lambda: "")() == "Text":
            return  # islem kaydi kendi icerigini kaydirir
        self._wheel_target(event).wheel_scroll(event.delta)

    def _wheel_target(self, event) -> ScrollFrame:
        """Tekerlek olayinin ait oldugu pencerenin kaydirma alanini dondurur."""
        popup = self.alarm_popup
        if popup is not None:
            try:
                if event.widget.winfo_toplevel() is popup:
                    return popup.scroll
            except (tk.TclError, AttributeError):
                pass
        return self.scroll

    # ---------- header ----------
    def _build_header(self) -> None:
        bar = tk.Frame(self, bg=HEADER_BG)
        bar.pack(fill="x")

        left = tk.Frame(bar, bg=HEADER_BG)
        left.pack(side="left", padx=14, pady=10)
        tk.Label(left, text=APP_TITLE, bg=HEADER_BG, fg="white", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(left, text=f"Surum v{__version__}", bg=HEADER_BG, fg=GRAY, font=("Segoe UI", 9)).pack(anchor="w")

        right = tk.Frame(bar, bg=HEADER_BG)
        right.pack(side="right", padx=14)

        self.status_label = tk.Label(right, text="Guncelleme otomatik kontrol ediliyor...", bg=HEADER_BG, fg=GRAY, font=("Segoe UI", 9))
        self.status_label.pack(anchor="e")

        btns = tk.Frame(right, bg=HEADER_BG)
        btns.pack(anchor="e", pady=(4, 0))

        self.check_btn = tk.Button(
            btns, text="Manuel Kontrol", width=14, font=("Segoe UI", 9), relief="flat", cursor="hand2",
            command=self._manual_check,
        )
        self.check_btn.pack(side="right")

        self.update_btn = tk.Button(
            btns,
            text="GUNCELLE",
            width=12,
            font=("Segoe UI", 10, "bold"),
            bg="#374151",
            fg="#cbd5e1",
            relief="flat",
            activebackground="#374151",
            activeforeground="#cbd5e1",
            state="disabled",
            cursor="hand2",
            command=self._start_update,
        )
        self.update_btn.pack(side="right", padx=(0, 8))

    # ---------- section 1: sensors ----------
    def _build_sensor_section(self, parent) -> None:
        sec = tk.LabelFrame(parent, text=" 1. Sicaklik Sensorleri ", bg="white", font=("Segoe UI", 11, "bold"), labelanchor="nw")
        sec.pack(fill="x", padx=2, pady=6)

        self.sensor_vars: dict[str, dict[str, tk.BooleanVar]] = {}
        self.sensor_groups: list[SensorGroup] = []
        try:
            self.sensor_groups = list_sensor_groups(resource_path("data"))
        except Exception as exc:  # noqa: BLE001
            tk.Label(sec, text=f"Standart liste okunamadi: {exc}", bg="white", fg=RED).pack(anchor="w", padx=10, pady=8)
            return

        head = tk.Frame(sec, bg="white")
        head.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(
            head,
            text="Standart Excel'de bulunan sensorler listelendi. Cihazinda olmayanlarin tikini kaldir.",
            bg="white", fg="#4b5563", font=("Segoe UI", 9),
        ).pack(side="left")
        tk.Button(head, text="Tumunu Kaldir", font=("Segoe UI", 8), command=lambda: self._set_all_sensors(False)).pack(side="right", padx=3)
        tk.Button(head, text="Tumunu Sec", font=("Segoe UI", 8), command=lambda: self._set_all_sensors(True)).pack(side="right", padx=3)

        grid = tk.Frame(sec, bg="white")
        grid.pack(fill="x", padx=10, pady=(2, 8))
        for group in self.sensor_groups:
            row = tk.Frame(grid, bg="white")
            row.pack(fill="x", pady=1)
            vars_map: dict[str, tk.BooleanVar] = {}
            if len(group.signals) == 1:
                code, _label = group.signals[0]
                var = tk.BooleanVar(value=True)
                vars_map[code] = var
                tk.Checkbutton(
                    row, text=group.label, variable=var, bg="white", anchor="w",
                    font=("Segoe UI", 10), activebackground="white", selectcolor="white",
                ).pack(side="left")
            else:
                sigs = ", ".join(lbl for _c, lbl in group.signals)
                tk.Label(row, text=f"{group.label} ({sigs})", bg="white", fg="#374151", font=("Segoe UI", 8), width=44, anchor="w").pack(side="left")
                for code, label in group.signals:
                    var = tk.BooleanVar(value=True)
                    vars_map[code] = var
                    tk.Checkbutton(
                        row, text=label, variable=var, bg="white",
                        font=("Segoe UI", 9), activebackground="white", selectcolor="white",
                    ).pack(side="left", padx=2)
            self.sensor_vars[group.obj] = vars_map

    def _set_all_sensors(self, value: bool) -> None:
        for by_code in self.sensor_vars.values():
            for var in by_code.values():
                var.set(value)

    def _sensor_selection(self) -> dict[str, list[str]]:
        return {
            obj: [code for code, var in by_code.items() if var.get()]
            for obj, by_code in self.sensor_vars.items()
        }

    # ---------- section 2: fans ----------
    def _build_fan_section(self, parent) -> None:
        sec = tk.LabelFrame(parent, text=" 2. Fan Secimi ", bg="white", font=("Segoe UI", 11, "bold"), labelanchor="nw")
        sec.pack(fill="x", padx=2, pady=6)

        self.supply_brand_var = tk.StringVar(value=BRANDS["ebm"]["label"])
        self.exhaust_brand_var = tk.StringVar(value=BRANDS["ebm"]["label"])
        self.supply_count_var = tk.StringVar(value="1")
        self.exhaust_count_var = tk.StringVar(value="1")

        rows = [
            ("Besleme fan markasi", 2),
            ("Adet", 3),
            ("Egzoz fan markasi", 5),
            ("Adet", 6),
        ]
        for text, row in rows:
            tk.Label(sec, text=text, bg="white", font=("Segoe UI", 10)).grid(row=row, column=0, sticky="w", padx=14, pady=4)

        self.supply_combo = self._brand_combo(sec, self.supply_brand_var, row=2)
        self.exhaust_combo = self._brand_combo(sec, self.exhaust_brand_var, row=5)
        self.supply_combo.bind("<<ComboboxSelected>>", lambda e: self._on_brand_change(self.supply_combo, self.supply_count_var))
        self.exhaust_combo.bind("<<ComboboxSelected>>", lambda e: self._on_brand_change(self.exhaust_combo, self.exhaust_count_var))

        self.supply_spin = self._count_spin(sec, self.supply_count_var, row=3)
        self.exhaust_spin = self._count_spin(sec, self.exhaust_count_var, row=6)
        self._on_brand_change(self.supply_combo, self.supply_count_var)
        self._on_brand_change(self.exhaust_combo, self.exhaust_count_var)
        tk.Label(
            sec,
            text="Secilmeyen marka ve adetten fazla unite satirlari (alarm satirlari dahil) silinir.",
            bg="white", fg="#4b5563", font=("Segoe UI", 8),
        ).grid(row=7, column=0, columnspan=4, sticky="w", padx=14, pady=(2, 6))

    def _brand_combo(self, parent, var, row):
        names = [label for label, _ in BRAND_CHOICES]
        combo = ttk.Combobox(parent, textvariable=var, values=names, state="readonly", width=18, font=("Segoe UI", 10))
        combo.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        return combo

    def _count_spin(self, parent, var, row):
        spin = tk.Spinbox(parent, from_=1, to=1, textvariable=var, width=6, font=("Segoe UI", 10), justify="center")
        spin.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        return spin

    def _selected_key(self, combo) -> str | None:
        return dict(BRAND_CHOICES).get(combo.get())

    def _on_brand_change(self, combo, count_var) -> None:
        key = self._selected_key(combo)
        spin = self.supply_spin if count_var is self.supply_count_var else self.exhaust_spin
        if key is None:
            spin.configure(values=[], state="disabled")
            count_var.set("0")
        else:
            max_units = BRANDS[key]["max_units"]
            spin.configure(values=[str(i) for i in range(1, max_units + 1)], state="normal")
            current = count_var.get()
            if not current.isdigit() or not 1 <= int(current) <= max_units:
                count_var.set("1")

    # ---------- section 3: dampers ----------
    def _build_damper_section(self, parent) -> None:
        sec = tk.LabelFrame(parent, text=" 3. Damper (Klape) Motorlari ", bg="white", font=("Segoe UI", 11, "bold"), labelanchor="nw")
        sec.pack(fill="x", padx=2, pady=6)

        self.damper_vars: dict[str, tuple[tk.BooleanVar, tk.StringVar]] = {}
        self.damper_groups: list[DamperGroup] = []
        try:
            self.damper_groups = list_damper_groups(resource_path("data"))
        except Exception as exc:  # noqa: BLE001
            tk.Label(sec, text=f"Standart liste okunamadi: {exc}", bg="white", fg=RED).pack(anchor="w", padx=10, pady=8)
            return

        head = tk.Frame(sec, bg="white")
        head.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(
            head,
            text="Her tarafa kac damper motoru baglanacagini sec. Sayilan motorlardan fazlasi ve "
            "secilmeyen tarafin pozisyon/feedback/alarm satirlari silinir. "
            "Karisim motoru 0 ise DamperCont satirlarinin hepsi, bypass motoru 0 ise "
            "BypassDmpCont satirlarinin hepsi silinir; CO2_Set_BMS ve DmpContTypeSel "
            "ayrica en az bir CO2 sensoru secilmesini ister.",
            bg="white", fg="#4b5563", font=("Segoe UI", 9), wraplength=760, justify="left", anchor="w",
        ).pack(side="left")

        grid = tk.Frame(sec, bg="white")
        grid.pack(fill="x", padx=10, pady=(4, 10))
        tk.Label(grid, text="Taraf", bg="white", font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=4)
        tk.Label(grid, text="Motor adet", bg="white", font=("Segoe UI", 8, "bold")).grid(row=0, column=1, sticky="w", padx=4)
        self.damper_spins: dict[str, tk.Spinbox] = {}
        for index, group in enumerate(self.damper_groups, start=1):
            enabled = tk.BooleanVar(value=True)
            count = tk.StringVar(value="1")
            tk.Checkbutton(
                grid, text=group.label, variable=enabled, bg="white", font=("Segoe UI", 10),
                activebackground="white", selectcolor="white",
                command=lambda g=group, v=enabled: self._on_damper_toggle(g, v),
            ).grid(row=index, column=0, sticky="w", padx=4, pady=2)
            spin = tk.Spinbox(
                grid, values=[str(i) for i in range(1, group.max_units + 1)], textvariable=count,
                width=5, font=("Segoe UI", 10), justify="center",
            )
            spin.grid(row=index, column=1, sticky="w", padx=4, pady=2)
            tk.Label(grid, text=f"(max {group.max_units})", bg="white", fg=GRAY, font=("Segoe UI", 8)).grid(row=index, column=2, sticky="w")
            self.damper_vars[group.key] = (enabled, count)
            self.damper_spins[group.key] = spin

    def _on_damper_toggle(self, group: DamperGroup, enabled: tk.BooleanVar) -> None:
        self.damper_spins[group.key].configure(state="normal" if enabled.get() else "disabled")

    def _damper_selection(self) -> dict[str, int]:
        selection: dict[str, int] = {}
        for group in self.damper_groups:
            enabled, count = self.damper_vars[group.key]
            if not enabled.get():
                selection[group.key] = 0
                continue
            value = int(count.get()) if count.get().isdigit() else 1
            selection[group.key] = min(max(value, 1), group.max_units)
        return selection

    # ---------- section 4: kademeli gruplar (isitici / DX / nemlendirici) ----------
    def _build_stage_section(self, parent) -> None:
        sec = tk.LabelFrame(parent, text=" 4. Kademe Sayilari (Isitici / DX / Nemlendirici) ", bg="white", font=("Segoe UI", 11, "bold"), labelanchor="nw")
        sec.pack(fill="x", padx=2, pady=6)

        self.stage_vars: dict[str, tk.StringVar] = {}
        self.stage_groups: list[StageGroup] = []
        try:
            self.stage_groups = list_stage_groups(resource_path("data"))
        except Exception as exc:  # noqa: BLE001
            tk.Label(sec, text=f"Standart liste okunamadi: {exc}", bg="white", fg=RED).pack(anchor="w", padx=10, pady=8)
            return

        tk.Label(
            sec,
            text="Kademe sayisi 0 ise o grubun tum satirlari silinir. Kademe sayisini asan "
            "DxAlarm/DXDefrost, HeaterN_ok ve nemlendirici satirlari (HumModeSelN.Start/ManPosBMS/"
            "ModeSelBMS, Hum_RunStsN, Hum_AlarmN) silinir; mod/durum/kapasite/yuksek sicaklik alarm "
            "ve nem set ayar satirlari en az bir kademe seciliyse kalir. Nemlendirici varsayilan 0'dir.",
            bg="white", fg="#4b5563", font=("Segoe UI", 9), wraplength=760, justify="left", anchor="w",
        ).pack(fill="x", padx=10, pady=(6, 2))

        grid = tk.Frame(sec, bg="white")
        grid.pack(fill="x", padx=10, pady=(4, 10))
        for index, group in enumerate(self.stage_groups, start=1):
            count = tk.StringVar(value=str(stage_default(group)))
            tk.Label(grid, text=group.label, bg="white", font=("Segoe UI", 10)).grid(row=index, column=0, sticky="w", padx=4, pady=2)
            tk.Spinbox(
                grid, values=[str(i) for i in range(0, group.max_stages + 1)], textvariable=count,
                width=5, font=("Segoe UI", 10), justify="center",
            ).grid(row=index, column=1, sticky="w", padx=4, pady=2)
            tk.Label(grid, text=f"0 = Yok, max {group.max_stages}", bg="white", fg=GRAY, font=("Segoe UI", 8)).grid(row=index, column=2, sticky="w")
            self.stage_vars[group.obj] = count

    def _stage_selection(self) -> dict[str, int]:
        selection: dict[str, int] = {}
        for group in self.stage_groups:
            raw = self.stage_vars[group.obj].get()
            value = int(raw) if raw.isdigit() else stage_default(group)
            selection[group.obj] = min(max(value, 0), group.max_stages)
        return selection

    # ---------- section 5: blok özellikleri (SAF / EAF / RunAround) ----------
    def _build_feature_section(self, parent) -> None:
        sec = tk.LabelFrame(parent, text=" 5. SAF / EAF ve Basincl Sensoru ", bg="white", font=("Segoe UI", 11, "bold"), labelanchor="nw")
        sec.pack(fill="x", padx=2, pady=6)

        self.feature_vars: dict[str, dict[str, tk.BooleanVar]] = {}
        self.feature_sub_checks: dict[str, list[tk.Checkbutton]] = {}
        self.feature_groups: list[FeatureGroup] = []
        try:
            self.feature_groups = list_feature_groups(resource_path("data"))
        except Exception as exc:  # noqa: BLE001
            tk.Label(sec, text=f"Standart liste okunamadi: {exc}", bg="white", fg=RED).pack(anchor="w", padx=10, pady=8)
            return

        tk.Label(
            sec,
            text="Kullanmadigin bloklarin tum satirlari (alarm satirlari dahil) silinir. "
            "QBM97xx basincl transmitteri ayrica secilir; blok secili degilse transmitter satirlari da kalmaz.",
            bg="white", fg="#4b5563", font=("Segoe UI", 9), wraplength=760, justify="left", anchor="w",
        ).pack(fill="x", padx=10, pady=(6, 2))

        box = tk.Frame(sec, bg="white")
        box.pack(fill="x", padx=12, pady=(2, 10))
        for group in self.feature_groups:
            vars_by_code: dict[str, tk.BooleanVar] = {}
            rows = tk.Frame(box, bg="white")
            rows.pack(fill="x", pady=2)
            for code, option_label, count in group.options:
                var = tk.BooleanVar(value=True)
                vars_by_code[code] = var
                indent = 0 if code == "main" else 26
                weight = "bold" if code == "main" else "normal"
                text = f"{group.label if code == 'main' else option_label} ({count} satir)"
                check = tk.Checkbutton(
                    rows, text=text,
                    variable=var, bg="white", font=("Segoe UI", 10, weight),
                    activebackground="white", selectcolor="white",
                )
                check.pack(anchor="w", padx=indent)
                if code == "main":
                    var.trace_add("write", lambda *_a, g=group: self._sync_feature_subs(g))
                else:
                    self.feature_sub_checks.setdefault(group.obj, []).append(check)
            self.feature_vars[group.obj] = vars_by_code

        for group in self.feature_groups:
            self._sync_feature_subs(group)

    def _sync_feature_subs(self, group: FeatureGroup) -> None:
        main_on = self.feature_vars[group.obj]["main"].get()
        for check in self.feature_sub_checks.get(group.obj, []):
            check.configure(state="normal" if main_on else "disabled")

    def _feature_selection(self) -> dict[str, list[str]]:
        return {
            group.obj: [code for code, var in self.feature_vars[group.obj].items() if var.get()]
            for group in self.feature_groups
        }

    # ---------- section 6: filtre alarmlari (pop-up) ----------
    def _build_alarm_section(self, parent) -> None:
        sec = tk.LabelFrame(parent, text=" 6. Filtre Alarmlari ", bg="white", font=("Segoe UI", 11, "bold"), labelanchor="nw")
        sec.pack(fill="x", padx=2, pady=6)

        self.alarm_vars: dict[str, tk.BooleanVar] = {}
        self.alarm_alarms: list[FilterAlarm] = []

        tk.Label(
            sec,
            text="Filtre kirlilik alarmlari standart listeden okunur ve pop-up icinde tek tek secilir; "
            "varsayilan hicbiri tikli degildir, secilmeyen alarm satiri listeden silinir. "
            "Alarm_Reset registeri her zaman eklenir; TempAVG, MBUnit (BMS_Check_Read/Write), "
            "BmsTemp_Hum, Cooling/Heating_Active ve WetBulp_Temp satirlari ise hicbir sekilde eklenmez.",
            bg="white", fg="#4b5563", font=("Segoe UI", 9), wraplength=760, justify="left", anchor="w",
        ).pack(fill="x", padx=10, pady=(6, 2))

        row = tk.Frame(sec, bg="white")
        row.pack(fill="x", padx=10, pady=(2, 10))
        btn = tk.Button(
            row, text="FILTRE ALARMLARINI SEC", font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg="white", relief="flat", activebackground="#0a5f45", activeforeground="white",
            cursor="hand2", padx=12, pady=4, command=self._open_alarm_popup,
        )
        btn.pack(side="left")
        self.alarm_summary = tk.Label(row, text="", bg="white", fg=GRAY, font=("Segoe UI", 9))
        self.alarm_summary.pack(side="left", padx=12)

        try:
            self.alarm_alarms = list_filter_alarms(resource_path("data"))
        except Exception as exc:  # noqa: BLE001
            tk.Label(sec, text=f"Standart liste okunamadi: {exc}", bg="white", fg=RED).pack(anchor="w", padx=10, pady=8)
            return
        btn.configure(text=f"FILTRE ALARMLARINI SEC ({len(self.alarm_alarms)})")
        for alarm in self.alarm_alarms:
            self.alarm_vars.setdefault(alarm.token, tk.BooleanVar(value=False))
        self._refresh_alarm_summary()

    def _refresh_alarm_summary(self) -> None:
        chosen = self._alarm_selection()
        self.alarm_summary.configure(text=f"Secili: {len(chosen)}/{len(self.alarm_alarms)} filtre alarmi")
        if self.alarm_popup is not None:
            self.alarm_popup.summary.configure(text=f"Secili: {len(chosen)}/{len(self.alarm_alarms)}")

    def _open_alarm_popup(self) -> None:
        if not self.alarm_alarms:
            return
        if self.alarm_popup is not None:
            self.alarm_popup.lift()
            return
        dlg = tk.Toplevel(self)
        dlg.title("Filtre Alarmlari")
        dlg.configure(bg=BG)
        dlg.geometry("480x540")
        dlg.transient(self)
        dlg.grab_set()
        self.alarm_popup = dlg

        tk.Label(
            dlg, text="Cihazinda bulunan filtre alarmlarini isaretle.", bg=BG, fg="#1f2a37", font=("Segoe UI", 10, "bold")
        ).pack(padx=14, pady=(12, 4), anchor="w")

        box = ScrollFrame(dlg)
        box.pack(fill="both", expand=True, padx=10, pady=4)
        dlg.scroll = box
        for alarm in self.alarm_alarms:
            tk.Checkbutton(
                box.inner, text=f"{alarm.label}   ({alarm.token})", variable=self.alarm_vars[alarm.token],
                bg="white", font=("Segoe UI", 10), activebackground="white", selectcolor="white",
                command=self._refresh_alarm_summary,
            ).pack(anchor="w", padx=10, pady=2, fill="x")

        footer = tk.Frame(dlg, bg=BG)
        footer.pack(fill="x", padx=12, pady=(4, 12))
        tk.Button(footer, text="Tumunu Sec", font=("Segoe UI", 9), command=lambda: self._set_all_alarms(True)).pack(side="left")
        tk.Button(footer, text="Tumunu Kaldir", font=("Segoe UI", 9), command=lambda: self._set_all_alarms(False)).pack(side="left", padx=6)
        dlg.summary = tk.Label(footer, text="", bg=BG, fg=GRAY, font=("Segoe UI", 9))
        dlg.summary.pack(side="left", padx=10)
        tk.Button(footer, text="Kapat", font=("Segoe UI", 9, "bold"), command=self._close_alarm_popup).pack(side="right")
        dlg.bind("<Destroy>", self._on_alarm_popup_destroy, add="+")
        self._refresh_alarm_summary()

    def _on_alarm_popup_destroy(self, _event) -> None:
        self.alarm_popup = None

    def _close_alarm_popup(self) -> None:
        if self.alarm_popup is not None:
            self.alarm_popup.destroy()

    def _set_all_alarms(self, value: bool) -> None:
        for var in self.alarm_vars.values():
            var.set(value)
        self._refresh_alarm_summary()

    def _alarm_selection(self) -> list[str]:
        return [alarm.token for alarm in self.alarm_alarms if self.alarm_vars[alarm.token].get()]

    # ---------- section 7: su vanalari (CV / HV / CO) ----------
    def _build_valve_section(self, parent) -> None:
        sec = tk.LabelFrame(parent, text=" 7. Su Vanalari (CV / HV / CO) ", bg="white", font=("Segoe UI", 11, "bold"), labelanchor="nw")
        sec.pack(fill="x", padx=2, pady=6)

        self.co_valve_var = tk.BooleanVar(value=False)
        self.valve_vars: dict[str, tk.BooleanVar] = {}
        self.valve_checks: dict[str, tk.Checkbutton] = {}
        self.valve_pack_opts: dict[str, dict] = {}
        self.valve_groups: list[ValveGroup] = []
        try:
            self.valve_groups = list_valve_groups(resource_path("data"))
        except Exception as exc:  # noqa: BLE001
            tk.Label(sec, text=f"Standart liste okunamadi: {exc}", bg="white", fg=RED).pack(anchor="w", padx=10, pady=8)
            return

        tk.Label(
            sec,
            text="Her vananin kendi satirlari (Pozisyon, Geri bildirim, Mode Select, Manuel Referans) "
            "tikle eklenir veya silinir. 2. vana kutusu yalnizca 1. vana secildiginde gorunur olur. "
            "`TmpControl\\Frost Alarm` (donma alarmi) HV1 vanasiyla birlikte gelir.",
            bg="white", fg="#4b5563", font=("Segoe UI", 9), wraplength=760, justify="left", anchor="w",
        ).pack(fill="x", padx=10, pady=(6, 2))

        box = tk.Frame(sec, bg="white")
        box.pack(fill="x", padx=12, pady=(2, 10))
        for group in self.valve_groups:
            var = tk.BooleanVar(value=False)
            self.valve_vars[group.key] = var
            opts = {"anchor": "w", "padx": 26 if group.parent else 0, "pady": 2}
            check = tk.Checkbutton(
                box,
                text=f"{group.label} ({group.rows} satir)",
                variable=var,
                bg="white",
                font=("Segoe UI", 10, "normal" if group.parent else "bold"),
                activebackground="white",
                selectcolor="white",
            )
            check.pack(**opts)
            self.valve_checks[group.key] = check
            self.valve_pack_opts[group.key] = opts
            if not group.parent:
                var.trace_add("write", lambda *_a, g=group: self._sync_valve_children(g))

        for group in self.valve_groups:
            if not group.parent:
                self._sync_valve_children(group)

        tk.Checkbutton(
            box,
            text=f"CO vanasi / change over ({len(CO_VALVE_TOKENS)} satir)",
            variable=self.co_valve_var,
            bg="white",
            font=("Segoe UI", 10, "bold"),
            activebackground="white",
            selectcolor="white",
        ).pack(anchor="w", pady=(8, 0))
        tk.Label(
            box,
            text="CO tiki " + ", ".join(CO_VALVE_TOKENS) + f" satirlarini {CO_VALVE_OBJECT} altindan listeye ekler.",
            bg="white", fg="#4b5563", font=("Segoe UI", 8), wraplength=720, justify="left", anchor="w",
        ).pack(anchor="w", pady=(2, 0))

    def _co_valve_enabled(self) -> bool:
        return bool(self.co_valve_var.get())

    def _sync_valve_children(self, parent_group: ValveGroup) -> None:
        """2. vana kutusunu 1. vana secimine gore goruntule/gizle."""
        shown = self.valve_vars[parent_group.key].get()
        for group in self.valve_groups:
            if group.parent != parent_group.key:
                continue
            check = self.valve_checks[group.key]
            if shown:
                check.pack(**self.valve_pack_opts[group.key])
            else:
                check.pack_forget()
                self.valve_vars[group.key].set(False)

    def _valve_selection(self) -> list[str]:
        return [group.key for group in self.valve_groups if self.valve_vars[group.key].get()]

    # ---------- section 8: rotor ----------
    def _build_rotor_section(self, parent) -> None:
        sec = tk.LabelFrame(parent, text=" 8. Rotor (Isi Geri Kazanim) ", bg="white", font=("Segoe UI", 11, "bold"), labelanchor="nw")
        sec.pack(fill="x", padx=2, pady=6)

        self.rotor_var = tk.StringVar(value=ROTOR_MODES[ROTOR_DEFAULT_MODE])
        tk.Label(sec, text="Rotor kontrol modu", bg="white", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=14, pady=5)
        self.rotor_combo = ttk.Combobox(
            sec,
            textvariable=self.rotor_var,
            values=[label for label, _ in ROTOR_CHOICES],
            state="readonly",
            width=18,
            font=("Segoe UI", 10),
        )
        self.rotor_combo.grid(row=0, column=1, sticky="w", padx=4, pady=5)
        tk.Label(
            sec,
            text="Yok: rotor satirlarinin hicbiri eklenmez.   Oransal: RotorControl satirlarinin hepsi "
            "(Mode Select, Manuel Set, Max Speed, Pozisyon, Active, Alarm) eklenir.   "
            "On/Off: yalnizca RotorActive ve Rotor Alarm eklenir.",
            bg="white", fg="#4b5563", font=("Segoe UI", 8), wraplength=760, justify="left", anchor="w",
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=14, pady=(2, 6))

    def _rotor_mode(self) -> str:
        return dict(ROTOR_CHOICES).get(self.rotor_var.get(), ROTOR_DEFAULT_MODE)

    # ---------- section 9: nem kontrolu ----------
    def _build_hum_control_section(self, parent) -> None:
        sec = tk.LabelFrame(parent, text=" 9. Nem Kontrolu ", bg="white", font=("Segoe UI", 11, "bold"), labelanchor="nw")
        sec.pack(fill="x", padx=2, pady=6)

        self.hum_control_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            sec, text="Nem kontrolu var", variable=self.hum_control_var,
            bg="white", font=("Segoe UI", 10), activebackground="white",
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=5)
        tk.Label(
            sec,
            text="Secilirse su satirlar listeye eklenir: "
            + ", ".join(f"{HUM_CTRL_OBJECT}\\{token}" for token in HUM_CTRL_TOKENS)
            + f". Secilmezse bu {len(HUM_CTRL_TOKENS)} nem set ayar satiri silinir. Kademe sayisindan bagimsiz "
            "bir secimdir, ancak kademe 0 ise zaten hicbir nemlendirici satiri listeye girmez.",
            bg="white", fg="#4b5563", font=("Segoe UI", 8), wraplength=760, justify="left", anchor="w",
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=14, pady=(2, 6))

    def _hum_control_enabled(self) -> bool:
        return bool(self.hum_control_var.get())

    # ---------- section 10: output ----------
    def _build_output_section(self, parent) -> None:
        sec = tk.LabelFrame(parent, text=" 10. Cikti ", bg="white", font=("Segoe UI", 11, "bold"), labelanchor="nw")
        sec.pack(fill="x", padx=2, pady=6)

        self.device_var = tk.StringVar(value="AHU-01")
        self.outdir_var = tk.StringVar(value="")

        tk.Label(sec, text="Cihaz adi", bg="white", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=14, pady=5)
        tk.Entry(sec, textvariable=self.device_var, width=24, font=("Segoe UI", 10)).grid(row=0, column=1, columnspan=3, sticky="w", padx=4, pady=5)

        tk.Label(sec, text="Cikti klasoru", bg="white", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", padx=14, pady=5)
        path_row = tk.Frame(sec, bg="white")
        path_row.grid(row=1, column=1, columnspan=3, sticky="w", padx=4, pady=5)
        tk.Entry(path_row, textvariable=self.outdir_var, width=48, font=("Segoe UI", 9)).pack(side="left")
        tk.Button(path_row, text="Gozat...", font=("Segoe UI", 9), command=self._browse_outdir).pack(side="left", padx=6)

        actions = tk.Frame(sec, bg="white")
        actions.grid(row=2, column=0, columnspan=4, sticky="ew", padx=14, pady=10)
        self.gen_btn = tk.Button(
            actions,
            text="EXCEL LISTELERINI OLUSTUR",
            font=("Segoe UI", 11, "bold"),
            bg=ACCENT,
            fg="white",
            relief="flat",
            activebackground="#0a5f45",
            activeforeground="white",
            cursor="hand2",
            padx=18,
            pady=6,
            command=self._generate,
        )
        self.gen_btn.pack(side="left")
        tk.Button(actions, text="Klasoru Ac", font=("Segoe UI", 9), command=self._open_outdir).pack(side="left", padx=10)

        log_sec = tk.Frame(parent, bg=BG)
        log_sec.pack(fill="both", expand=True, padx=2, pady=(2, 6))
        tk.Label(log_sec, text="Islem Kaydi", bg=BG, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.log = tk.Text(log_sec, font=("Consolas", 9), bg="#0f172a", fg="#e2e8f0", relief="flat", height=9)
        self.log.pack(fill="both", expand=True, pady=(4, 0))

    def _browse_outdir(self) -> None:
        chosen = filedialog.askdirectory(title="Cikti klasoru")
        if chosen:
            self.outdir_var.set(chosen)

    def _open_outdir(self) -> None:
        target = self.outdir_var.get().strip()
        if target and Path(target).is_dir():
            import os

            os.startfile(target)  # type: ignore[attr-defined]
        else:
            messagebox.showinfo("Bilgi", "Once bir cikti klasoru secin.")

    # ---------- logging ----------
    def log_line(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ---------- generate ----------
    def _generate(self) -> None:
        supply_key = self._selected_key(self.supply_combo)
        exhaust_key = self._selected_key(self.exhaust_combo)
        sensors = self._sensor_selection()
        dampers = self._damper_selection()
        stages = self._stage_selection()
        features = self._feature_selection()
        valves = self._valve_selection()
        co_valve = self._co_valve_enabled()
        rotor = self._rotor_mode()
        hum_control = self._hum_control_enabled()
        alarms = self._alarm_selection()
        any_sensor = any(sensors.values()) if sensors else True
        any_damper = any(dampers.values()) if dampers else True
        any_stage = any(stages.values()) if stages else True
        any_feature = any(features.values()) if features else True
        if not (any_sensor or any_damper or any_stage or any_feature or supply_key or exhaust_key):
            messagebox.showwarning("Secim yok", "Sensor, damper, kademe, blok, besleme ve egzoz icin hic secim yok.")
            return

        count = int(self.supply_count_var.get() or 1) if supply_key else 0
        ecount = int(self.exhaust_count_var.get() or 1) if exhaust_key else 0
        out_dir = self.outdir_var.get().strip()
        if not out_dir:
            out_dir = filedialog.askdirectory(title="Cikti klasoru")
            if not out_dir:
                return
            self.outdir_var.set(out_dir)

        self.gen_btn.configure(state="disabled")
        try:
            results = generate(
                data_dir=resource_path("data"),
                output_dir=Path(out_dir),
                device_prefix=self.device_var.get(),
                supply_brand=supply_key,
                supply_count=count,
                exhaust_brand=exhaust_key,
                exhaust_count=ecount,
                sensor_selection=sensors,
                damper_selection=dampers,
                stage_selection=stages,
                feature_selection=features,
                valve_selection=valves,
                co_valve=co_valve,
                rotor_mode=rotor,
                hum_control=hum_control,
                alarm_selection=alarms,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Hata", f"Listeler olusturulamadi:\n{exc}")
            self.log_line(f"HATA: {exc}")
        else:
            for res in results:
                self.log_line(
                    f"[{res.protocol}] fan {res.kept_fan_rows}/{res.total_fan_rows}, "
                    f"damper {res.kept_damper_rows}/{res.total_damper_rows}, "
                    f"kademe {res.kept_stage_rows}/{res.total_stage_rows}, "
                    f"blok {res.kept_feature_rows}/{res.total_feature_rows}, "
                    f"vana {res.kept_valve_rows}/{res.total_valve_rows}, "
                    f"co vanasi {res.kept_co_valve_rows}/{res.total_co_valve_rows}, "
                    f"rotor {res.kept_rotor_rows}/{res.total_rotor_rows}, "
                    f"nem kontrolu {res.kept_hum_rows}/{res.total_hum_rows}, "
                    f"filtre alarmi {res.kept_alarm_rows}/{res.total_alarm_rows} satir, "
                    f"toplam {res.removed_rows} satir silindi -> {res.output}"
                )
            buckets = self._removed_groups(results)
            self.log_line("")
            for title, key in (
                ("Silinen sensor gruplari", "sensor"),
                ("Silinen damper motorlari", "damper"),
                ("Silinen kademe satirlari", "stage"),
                ("Silinen blok satirlari", "feature"),
                ("Secilmeyen vana satirlari", "valve"),
                ("Secilmeyen CO vanasi satirlari", "covalve"),
                ("Rotor satirlari", "rotor"),
                ("Nem kontrolu satirlari", "hum"),
                ("Secilmeyen filtre alarmlari", "alarm"),
                ("Her zaman cikarilan gruplar", "dropped"),
                ("Silinen fan bloklari", "fan"),
            ):
                self.log_line(f"{title}: " + (", ".join(
                    f"{name} ({count})" for name, count in sorted(buckets[key].items())
                ) or "-"))
            messagebox.showinfo("Tamam", f"{results[0].output.parent} klasorunde 2 liste olusturuldu.")
        finally:
            self.gen_btn.configure(state="normal")
            self._save_config()

    def _removed_groups(self, results) -> dict[str, dict[str, int]]:
        """Silinen satirlari sensor / damper / kademe / blok / fan olarak siniflandirir."""
        damper_labels = {g.label for g in self.damper_groups}
        sensor_labels = {g.label for g in self.sensor_groups}
        stage_labels = {g.label for g in self.stage_groups}
        feature_labels = {g.label for g in self.feature_groups}
        brand_labels = {b["label"] for b in BRANDS.values()}
        dropped_labels = ALWAYS_DROPPED_LABELS
        buckets: dict[str, dict[str, int]] = {
            "sensor": {}, "damper": {}, "stage": {}, "feature": {},
            "valve": {}, "covalve": {}, "rotor": {}, "hum": {}, "alarm": {}, "dropped": {}, "fan": {}
        }
        for res in results:
            for name, count in res.removed_by_group.items():
                if name.startswith(ALARM_GROUP_PREFIX):
                    kind = "alarm"
                elif name.startswith(dropped_labels):
                    kind = "dropped"
                elif name.startswith(FAN_DOOR_GROUP_PREFIX):
                    kind = "fan"
                elif name.startswith(VALVE_GROUP_PREFIX):
                    kind = "valve"
                elif name.startswith(CO_VALVE_GROUP_PREFIX):
                    kind = "covalve"
                elif name.startswith(ROTOR_GROUP_PREFIX):
                    kind = "rotor"
                elif name.startswith(HUM_CTRL_GROUP_PREFIX):
                    kind = "hum"
                elif name.startswith(DAMPER_PARAM_GROUP_PREFIX):
                    kind = "damper"
                elif any(name.startswith(lbl) for lbl in damper_labels):
                    kind = "damper"
                elif any(name.startswith(lbl) for lbl in sensor_labels):
                    kind = "sensor"
                elif any(name.startswith(lbl) for lbl in stage_labels):
                    kind = "stage"
                elif any(name.startswith(lbl) for lbl in feature_labels):
                    kind = "feature"
                elif any(bl in name for bl in brand_labels):
                    kind = "fan"
                else:
                    continue
                merged = buckets[kind]
                merged[name] = merged.get(name, 0) + count
        return buckets

    # ---------- update ----------
    def _set_status(self, text: str, color: str) -> None:
        self.status_label.configure(text=text, fg=color)

    def _auto_check(self) -> None:
        self._run_check(auto=True)
        self.after(CHECK_INTERVAL_MS, self._auto_check)

    def _manual_check(self) -> None:
        self._run_check(auto=False)

    def _run_check(self, auto: bool) -> None:
        if self._checking:
            return
        self._checking = True
        if not auto:
            self._set_status("Kontrol ediliyor...", GRAY)

        def worker() -> None:
            try:
                info = updater.check_latest_release(__version__)
            except updater.UpdateError as exc:
                self.after(0, self._check_failed, str(exc), auto)
                return
            self.after(0, self._check_done, info)

        threading.Thread(target=worker, daemon=True).start()

    def _check_failed(self, message: str, auto: bool) -> None:
        self._checking = False
        if auto and self._update_info:
            return
        self._set_status(("Kontrol basarisiz: " + message)[:70], RED if not auto else GRAY)

    def _check_done(self, info: updater.ReleaseInfo | None) -> None:
        self._checking = False
        if info is not None:
            self._update_info = info
            ver = ".".join(map(str, info.version))
            self._set_status(f"YENI SURUM MEVCUT: v{ver}", GREEN_NEW)
            self.update_btn.configure(state="normal", bg=GREEN_NEW, fg="white")
        elif str(self.update_btn["state"]) == "disabled":
            self._set_status(f"Guncel - surum v{__version__}", GRAY)

    def _start_update(self) -> None:
        info = self._update_info
        if info is None:
            return
        if not self._frozen:
            messagebox.showinfo(
                "Guncelleme",
                "Guncelleme yalnizca paketlenmis EXE calistirildiginda kullanilabilir.\n"
                "Kaynak koddan calisiyorsunuz.",
            )
            return
        ver = ".".join(map(str, info.version))
        size = f" ({fmt_mb(info.size)})" if info.size else ""
        if not messagebox.askyesno(
            "Guncelle",
            f"v{ver} surumu{size} indirilecek, mevcut EXE'nin yerine konacak ve "
            f"program yeniden baslayacak.\nSu anki surum: v{__version__}. Devam edilsin mi?",
        ):
            return
        self._downloading = True
        self.update_btn.configure(state="disabled")
        self._set_status("Indiriliyor...", GRAY)
        self._open_update_dialog(info)

        def worker() -> None:
            started = time.monotonic()
            last_post = started

            def on_progress(done: int, total: int) -> None:
                nonlocal last_post
                now = time.monotonic()
                if now - last_post < 0.15:
                    return
                last_post = now
                self.after(0, self._update_progress, done, total, now - started)

            try:
                path = updater.download_release(info, progress=on_progress)
            except Exception as exc:  # noqa: BLE001
                self.after(0, self._download_failed, str(exc))
                return
            self.after(0, self._download_done, path)

        threading.Thread(target=worker, daemon=True).start()

    def _open_update_dialog(self, info: updater.ReleaseInfo) -> None:
        ver = ".".join(map(str, info.version))
        dlg = tk.Toplevel(self)
        dlg.title(f"Guncelleme v{ver}")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.attributes("-topmost", True)
        dlg.protocol("WM_DELETE_WINDOW", lambda: None)
        tk.Label(dlg, text=f"{APP_TITLE} v{ver}", bg=BG, fg="#1f2a37", font=("Segoe UI", 11, "bold")).pack(padx=18, pady=(14, 2))
        self.progress_bar = ttk.Progressbar(dlg, orient="horizontal", length=340, mode="determinate", maximum=100)
        self.progress_bar.pack(padx=18, pady=8)
        first = f"{fmt_mb(info.size)} indirilecek" if info.size else "Indiriliyor..."
        self.progress_label = tk.Label(dlg, text=first, bg=BG, fg=GRAY, font=("Consolas", 9))
        self.progress_label.pack(padx=18, pady=(0, 14))
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dlg.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self._update_dialog = dlg

    def _update_progress(self, done: int, total: int, elapsed: float) -> None:
        if total:
            percent = min(100.0, done * 100.0 / total)
            self.progress_bar.configure(value=percent)
            text = f"{fmt_mb(done)} / {fmt_mb(total)}  %{percent:.0f}"
            self._set_status(f"Indiriliyor %{percent:.0f}", GRAY)
        else:
            text = f"{fmt_mb(done)} indirildi"
        if elapsed > 0.3:
            text += f"  {fmt_mb(done / elapsed)}/s"
        self.progress_label.configure(text=text)

    def _close_update_dialog(self) -> None:
        if self._update_dialog is not None:
            self._update_dialog.destroy()
            self._update_dialog = None

    def _download_failed(self, message: str) -> None:
        self._downloading = False
        self._close_update_dialog()
        self.update_btn.configure(state="normal")
        self._set_status("Indirme basarisiz: " + message[:60], RED)
        messagebox.showerror("Guncelleme", f"Indirme basarisiz:\n{message}")

    def _download_done(self, path: Path) -> None:
        self._downloading = False
        size = path.stat().st_size
        self.progress_bar.configure(value=100)
        self.progress_label.configure(text=f"{fmt_mb(size)} indirildi - program yeniden baslatiliyor...")
        self._set_status("Yeniden baslatiliyor...", GREEN_NEW)
        self.log_line(f"Guncelleme indirildi: {path.name} ({fmt_mb(size)})")
        self.after(1200, self._restart, path)

    def _restart(self, path: Path) -> None:
        self._close_update_dialog()
        updater.apply_and_restart(path)
        self.destroy()

    # ---------- config ----------
    def _load_config(self) -> None:
        try:
            cfg = json.loads(config_file().read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            cfg = {}
        self.supply_brand_var.set(cfg.get("supply_brand", self.supply_brand_var.get()))
        self.exhaust_brand_var.set(cfg.get("exhaust_brand", self.exhaust_brand_var.get()))
        self.supply_count_var.set(str(cfg.get("supply_count", 1)))
        self.exhaust_count_var.set(str(cfg.get("exhaust_count", 1)))
        self.device_var.set(cfg.get("device", self.device_var.get()))
        self.outdir_var.set(cfg.get("outdir", str(Path.home() / "Documents")))
        self._on_brand_change(self.supply_combo, self.supply_count_var)
        self._on_brand_change(self.exhaust_combo, self.exhaust_count_var)
        sensors = cfg.get("sensors") or {}
        for obj, by_code in self.sensor_vars.items():
            saved = sensors.get(obj)
            if saved is None:
                continue
            chosen = set(saved)
            for code, var in by_code.items():
                var.set(code in chosen)
        dampers = cfg.get("dampers") or {}
        for group in self.damper_groups:
            saved = dampers.get(group.key)
            if saved is None:
                continue
            enabled, count = self.damper_vars[group.key]
            value = int(saved)
            enabled.set(value > 0)
            count.set(str(min(max(value, 1), group.max_units)))
            self._on_damper_toggle(group, enabled)
        stages = cfg.get("stages") or {}
        for group in self.stage_groups:
            saved = stages.get(group.obj)
            if saved is None:
                continue
            self.stage_vars[group.obj].set(str(min(max(int(saved), 0), group.max_stages)))
        features = cfg.get("features") or {}
        for group in self.feature_groups:
            saved = features.get(group.obj)
            if saved is None:
                continue
            chosen = set(saved)
            for code, var in self.feature_vars[group.obj].items():
                var.set(code in chosen)
            self._sync_feature_subs(group)
        self._apply_saved_alarms(cfg)
        valves = cfg.get("valves")
        if valves is not None:
            chosen = set(valves)
            for group in self.valve_groups:
                if group.parent:
                    continue
                self.valve_vars[group.key].set(group.key in chosen)
                self._sync_valve_children(group)
            # 2. vana tiki, 1. vana kutusunu goruntuleyen senkronizasyondan sonra yuklenir
            for group in self.valve_groups:
                if group.parent and self.valve_vars[group.parent].get():
                    self.valve_vars[group.key].set(group.key in chosen)
        rotor_mode = cfg.get("rotor_mode")
        if rotor_mode in ROTOR_MODES:
            self.rotor_var.set(ROTOR_MODES[rotor_mode])
        self.hum_control_var.set(bool(cfg.get("hum_control", False)))
        self.co_valve_var.set(bool(cfg.get("co_valve", False)))

    def _apply_saved_alarms(self, cfg: dict) -> None:
        """Kayitli filtre alarmi tiklerini geri yukler.

        Varsayilan 'tikli' oldugu donemde yazilan kayitlar (defaults_rev damgasi
        olmayanlar) geri yuklenmez; aksi halde alarmlar hala hepsi secili acilir.
        """
        alarms = cfg.get("alarms")
        if alarms is None or int(cfg.get("defaults_rev", 0)) < DEFAULTS_REV:
            return
        chosen = set(alarms)
        for token, var in self.alarm_vars.items():
            var.set(token in chosen)
        self._refresh_alarm_summary()

    def _save_config(self) -> None:
        cfg = {
            "supply_brand": self.supply_brand_var.get(),
            "exhaust_brand": self.exhaust_brand_var.get(),
            "supply_count": self.supply_count_var.get(),
            "exhaust_count": self.exhaust_count_var.get(),
            "device": self.device_var.get(),
            "outdir": self.outdir_var.get(),
            "sensors": {obj: [c for c, v in by.items() if v.get()] for obj, by in self.sensor_vars.items()},
            "dampers": self._damper_selection(),
            "stages": self._stage_selection(),
            "features": self._feature_selection(),
            "valves": self._valve_selection(),
            "co_valve": self._co_valve_enabled(),
            "rotor_mode": self._rotor_mode(),
            "hum_control": self._hum_control_enabled(),
            "alarms": self._alarm_selection(),
            "defaults_rev": DEFAULTS_REV,
        }
        try:
            config_file().write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def on_close(self) -> None:
        self._save_config()
        self.destroy()


def _run_swap_helper(target: Path) -> None:
    """Indirilen EXE bu modda acilir: eski EXE'yi kendisiyle degistirip ondan yeniden baslar."""
    root = tk.Tk()
    root.title(f"{APP_TITLE} guncelleniyor")
    root.configure(bg=BG)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.protocol("WM_DELETE_WINDOW", lambda: None)
    tk.Label(
        root, text=f"{APP_TITLE} v{__version__} kuruluyor", bg=BG, fg="#1f2a37", font=("Segoe UI", 10, "bold")
    ).pack(padx=18, pady=(14, 4))
    bar = ttk.Progressbar(root, orient="horizontal", length=320, mode="indeterminate")
    bar.pack(padx=18, pady=6)
    bar.start(70)
    info = tk.Label(
        root, text="Eski surum kapaniyor, EXE degistiriliyor...", bg=BG, fg=GRAY,
        font=("Consolas", 9), wraplength=320, justify="left",
    )
    info.pack(padx=18, pady=(0, 14))
    own = Path(sys.executable)

    def note(attempt: int, _error: str) -> None:
        root.after(0, lambda: info.configure(text=f"Eski surum henuz kapanmadi - {attempt}. deneme bekliyor..."))

    def worker() -> None:
        outcome = updater.swap_with_retry(own, target, note=note)
        root.after(0, lambda: _finish_swap(root, outcome, own))

    threading.Thread(target=worker, daemon=True).start()
    root.mainloop()


def _finish_swap(root, outcome, own: Path) -> None:
    if outcome.ok:
        updater.relaunch(outcome.target)
        root.destroy()
        return
    updater.log_swap(f"kullaniciya hata gosterildi: {outcome.error}")
    messagebox.showerror(
        "Guncelleme",
        f"EXE degistirilemedi ({outcome.attempts} deneme, {outcome.elapsed:.0f} sn):\n{outcome.error}\n\n"
        f"Hedef: {outcome.target}\nIndirilen: {own}\nAyrinti: {updater.swap_log_path()}\n\n"
        "Programi tamamen kapatip indirilen dosyayi hedefin uzerine kopyalayabilirsiniz.\n"
        "Yeni surum simdilik indirilen dosyadan baslatiliyor.",
    )
    updater.relaunch(own)
    root.destroy()


def main() -> None:
    if "--selftest" in sys.argv:
        try:
            app = App()
            app.update_idletasks()
            app.destroy()
        except Exception as exc:  # noqa: BLE001
            print(f"SELFTEST FAILED: {exc}")
            raise SystemExit(1)
        print("SELFTEST OK")
        return
    target = updater.parse_replace_target(sys.argv)
    if target is not None:
        if not getattr(sys, "frozen", False):
            print(f"swap yarimcilari yalnizca paketlenmis EXE'de calisir: {target}")
            return
        _run_swap_helper(target)
        return
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
