"""REGISTER SELECTER - cihaz bazli Modbus/BACnet register listesi uretici."""

from __future__ import annotations

import json
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import updater
from register_engine import BRANDS, generate
from version import __version__

APP_TITLE = "REGISTER SELECTER"
CHECK_INTERVAL_MS = 60_000

BG = "#f4f6f8"
HEADER_BG = "#1f2a37"
ACCENT = "#0b6e4f"
GREEN_NEW = "#16a34a"
GRAY = "#9aa5b1"
RED = "#b91c1c"

BRAND_CHOICES = [("Yok", None)] + [(cfg["label"], key) for key, cfg in BRANDS.items()]


def resource_path(relative: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent / relative


def config_file() -> Path:
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    return root / "register_selecter.json"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_TITLE} v{__version__}")
        self.geometry("880x640")
        self.minsize(760, 560)
        self.configure(bg=BG)

        self._update_info: updater.ReleaseInfo | None = None
        self._checking = False
        self._downloading = False
        self._frozen = getattr(sys, "frozen", False)

        self._build_header()
        self._build_body()
        self._load_config()

        self.after(3000, self._auto_check)

    # ---------- header ----------
    def _build_header(self) -> None:
        bar = tk.Frame(self, bg=HEADER_BG)
        bar.pack(fill="x")

        left = tk.Frame(bar, bg=HEADER_BG)
        left.pack(side="left", padx=14, pady=10)
        tk.Label(left, text=APP_TITLE, bg=HEADER_BG, fg="white", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(left, text=f"Surdum v{__version__}", bg=HEADER_BG, fg=GRAY, font=("Segoe UI", 9)).pack(anchor="w")

        right = tk.Frame(bar, bg=HEADER_BG)
        right.pack(side="right", padx=14)

        self.status_label = tk.Label(right, text="Guncelleme otomatik kontrol ediliyor...", bg=HEADER_BG, fg=GRAY, font=("Segoe UI", 9))
        self.status_label.pack(anchor="e")

        btns = tk.Frame(right, bg=HEADER_BG)
        btns.pack(anchor="e", pady=(4, 0))

        self.check_btn = tk.Button(
            btns, text="Manuel Kontrol", width=14, font=("Segoe UI", 9), relief="flat", cursor="hand2"
        )
        self.check_btn.pack(side="right")
        self.check_btn.configure(command=self._manual_check)

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
        )
        self.update_btn.pack(side="right", padx=(0, 8))
        self.update_btn.configure(command=self._start_update)

    # ---------- body ----------
    def _build_body(self) -> None:
        pad = dict(padx=16, pady=8)
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", **pad)

        form = tk.Frame(top, bg="white", highlightbackground="#d3dbe3", highlightthickness=1)
        form.pack(fill="x")

        title = tk.Label(form, text="Cihaz Secimi", bg="white", font=("Segoe UI", 12, "bold"), anchor="w")
        title.grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(12, 2))
        hint = tk.Label(
            form,
            text="Secilmeyen marka bloklari ve sectiginiz adetten fazla unite satirlari silinir; "
            "diger register satirlari (sensor, batarya, SAF/EAF mantigi) aynen kalir.",
            bg="white", fg="#4b5563", font=("Segoe UI", 9), wraplength=740, justify="left", anchor="w",
        )
        hint.grid(row=1, column=0, columnspan=4, sticky="w", padx=14, pady=(0, 8))

        self.supply_brand_var = tk.StringVar(value=BRANDS["ebm"]["label"])
        self.exhaust_brand_var = tk.StringVar(value=BRANDS["ebm"]["label"])
        self.supply_count_var = tk.StringVar(value="1")
        self.exhaust_count_var = tk.StringVar(value="1")
        self.device_var = tk.StringVar(value="AHU-01")
        self.outdir_var = tk.StringVar(value="")

        labels = [
            ("Besleme fan markasi", self.supply_brand_var, 2),
            ("Adet", self.supply_count_var, 3),
            ("Egzoz fan markasi", self.exhaust_brand_var, 5),
            ("Adet", self.exhaust_count_var, 6),
        ]
        for text, var, row in labels:
            tk.Label(form, text=text, bg="white", font=("Segoe UI", 10)).grid(row=row, column=0, sticky="w", padx=14, pady=5)

        self.supply_combo = self._brand_combo(form, self.supply_brand_var, row=2)
        self.exhaust_combo = self._brand_combo(form, self.exhaust_brand_var, row=5)
        self.supply_combo.bind("<<ComboboxSelected>>", lambda e: self._on_brand_change(self.supply_combo, self.supply_count_var))
        self.exhaust_combo.bind("<<ComboboxSelected>>", lambda e: self._on_brand_change(self.exhaust_combo, self.exhaust_count_var))

        self.supply_spin = self._count_spin(form, self.supply_count_var, row=3)
        self.exhaust_spin = self._count_spin(form, self.exhaust_count_var, row=6)
        self._on_brand_change(self.supply_combo, self.supply_count_var)
        self._on_brand_change(self.exhaust_combo, self.exhaust_count_var)

        tk.Label(form, text="Cihaz adi", bg="white", font=("Segoe UI", 10)).grid(row=8, column=0, sticky="w", padx=14, pady=5)
        dev = tk.Entry(form, textvariable=self.device_var, width=24, font=("Segoe UI", 10))
        dev.grid(row=8, column=1, columnspan=3, sticky="w", padx=4, pady=5)

        tk.Label(form, text="Ciktı klasoru", bg="white", font=("Segoe UI", 10)).grid(row=9, column=0, sticky="w", padx=14, pady=5)
        path_row = tk.Frame(form, bg="white")
        path_row.grid(row=9, column=1, columnspan=3, sticky="w", padx=4, pady=5)
        out_entry = tk.Entry(path_row, textvariable=self.outdir_var, width=48, font=("Segoe UI", 9))
        out_entry.pack(side="left")
        browse = tk.Button(path_row, text="Gozat...", font=("Segoe UI", 9), command=self._browse_outdir)
        browse.pack(side="left", padx=6)

        actions = tk.Frame(form, bg="white")
        actions.grid(row=10, column=0, columnspan=4, sticky="ew", padx=14, pady=12)
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
        open_dir = tk.Button(actions, text="Klasoru Ac", font=("Segoe UI", 9), command=self._open_outdir)
        open_dir.pack(side="left", padx=10)

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="both", expand=True, **pad)
        tk.Label(bottom, text="Islem Kaydi", bg=BG, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.log = tk.Text(bottom, font=("Consolas", 9), bg="#0f172a", fg="#e2e8f0", relief="flat", height=12)
        self.log.pack(fill="both", expand=True, pady=(4, 0))

    def _brand_combo(self, parent, var, row):
        names = [label for label, _ in BRAND_CHOICES]
        combo = ttk.Combobox(parent, textvariable=var, values=names, state="readonly", width=18, font=("Segoe UI", 10))
        combo.grid(row=row, column=1, sticky="w", padx=4, pady=5)
        return combo

    def _count_spin(self, parent, var, row):
        spin = tk.Spinbox(parent, from_=1, to=1, textvariable=var, width=6, font=("Segoe UI", 10), justify="center")
        spin.grid(row=row, column=1, sticky="w", padx=4, pady=5)
        return spin

    def _selected_key(self, combo) -> str | None:
        label = combo.get()
        return dict(BRAND_CHOICES).get(label)

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

    def _browse_outdir(self) -> None:
        chosen = filedialog.askdirectory(title="Ciktı klasoru")
        if chosen:
            self.outdir_var.set(chosen)

    def _open_outdir(self) -> None:
        target = self.outdir_var.get().strip()
        if target and Path(target).is_dir():
            import os

            os.startfile(target)  # type: ignore[attr-defined]
        else:
            messagebox.showinfo("Bilgi", "Once bir ciktı klasoru secin.")

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
        if supply_key is None and exhaust_key is None:
            messagebox.showwarning("Secim yok", "En az bir fan yönü için marka secin (besleme veya egzoz).")
            return

        count = int(self.supply_count_var.get() or 1) if supply_key else 0
        ecount = int(self.exhaust_count_var.get() or 1) if exhaust_key else 0
        out_dir = self.outdir_var.get().strip()
        if not out_dir:
            out_dir = filedialog.askdirectory(title="Ciktı klasoru")
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
            )
        except Exception as exc:  # noqa: BLE001 - surface any failure to the user
            messagebox.showerror("Hata", f"Listeler olusturulamadi:\n{exc}")
            self.log_line(f"HATA: {exc}")
        else:
            for res in results:
                self.log_line(
                    f"[{res.protocol}] {res.kept_fan_rows}/{res.total_fan_rows} fan satiri korundu, "
                    f"{res.removed_rows} satir silindi -> {res.output}"
                )
            self.log_line("")
            self.log_line("Tum silinen bloklar: " + (", ".join(
                f"{k} ({v} satir)" for r in results for k, v in sorted(r.removed_by_group.items())
            ) or "-"))
            messagebox.showinfo("Tamam", f"{results[0].output.parent} klasorunde 2 liste olusturuldu.")
        finally:
            self.gen_btn.configure(state="normal")
            self._save_config()

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
            return  # keep showing a previously found update
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
        if not messagebox.askyesno("Guncelle", f"{info.asset_name} indirilip mevcut surumun yerine konulsun mu?"):
            return
        self._downloading = True
        self.update_btn.configure(state="disabled")
        self._set_status("Indiriliyor...", GRAY)

        def worker() -> None:
            try:
                path = updater.download_release(info)
            except Exception as exc:  # noqa: BLE001
                self.after(0, self._download_failed, str(exc))
                return
            self.after(0, self._download_done, path)

        threading.Thread(target=worker, daemon=True).start()

    def _download_failed(self, message: str) -> None:
        self._downloading = False
        self.update_btn.configure(state="normal")
        self._set_status("Indirme basarisiz: " + message[:60], RED)

    def _download_done(self, path: Path) -> None:
        self._downloading = False
        self._set_status("Yeniden baslatiliyor...", GREEN_NEW)
        self.log_line(f"Guncelleme indirildi: {path.name}")
        updater.apply_and_restart(path)
        self.destroy()

    # ---------- config ----------
    def _load_config(self) -> None:
        try:
            cfg = json.loads(config_file().read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return
        self.supply_brand_var.set(cfg.get("supply_brand", self.supply_brand_var.get()))
        self.exhaust_brand_var.set(cfg.get("exhaust_brand", self.exhaust_brand_var.get()))
        self.supply_count_var.set(str(cfg.get("supply_count", 1)))
        self.exhaust_count_var.set(str(cfg.get("exhaust_count", 1)))
        self.device_var.set(cfg.get("device", self.device_var.get()))
        self.outdir_var.set(cfg.get("outdir", str(Path.home() / "Documents")))
        self._on_brand_change(self.supply_combo, self.supply_count_var)
        self._on_brand_change(self.exhaust_combo, self.exhaust_count_var)

    def _save_config(self) -> None:
        cfg = {
            "supply_brand": self.supply_brand_var.get(),
            "exhaust_brand": self.exhaust_brand_var.get(),
            "supply_count": self.supply_count_var.get(),
            "exhaust_count": self.exhaust_count_var.get(),
            "device": self.device_var.get(),
            "outdir": self.outdir_var.get(),
        }
        try:
            config_file().write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def on_close(self) -> None:  # noqa: RT0101 - used via protocol
        self._save_config()
        self.destroy()


def main() -> None:
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
