import argparse
import csv
import os
import random
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

# ========================= KONFIGURASI UMUM =========================
SEED_KALENDER   = 2025
JUMLAH_HARI     = 540
TANGGAL_MULAI   = date(2025, 1, 24)
JAM_BUKA        = 6
JAM_TUTUP       = 21
UANG_HARIAN     = (15_000, 150_000)
TANGGAL_GAJIAN  = {25, 26, 1}
PELUANG_PESAING = 0.10        # promo pesaing acak per hari
P_SUBSTITUSI    = 0.40        # peluang pembeli ganti produk lain saat stok habis
PELUANG_SUPPLIER = 0.85       # peluang supplier kategori datang di pagi hari
INFLASI_UMUM    = 0.004       # kenaikan bulanan yang dianggap "wajar" oleh pembeli

POLA_JAM = {
    6: .55, 7: .80, 8: .55, 9: .35, 10: .30, 11: .45,
    12: .60, 13: .40, 14: .25, 15: .35, 16: .50,
    17: .80, 18: .90, 19: .70, 20: .45, 21: .30,
}

# --- Kalender akademik (contoh, sesuaikan) : (mulai, selesai, fase) ---
KALENDER_AKADEMIK = [
    (date(2025, 4, 14),  date(2025, 4, 25),  "UTS"),
    (date(2025, 6, 2),   date(2025, 6, 13),  "UAS"),
    (date(2025, 6, 14),  date(2025, 8, 24),  "LIBUR"),
    (date(2025, 10, 13), date(2025, 10, 24), "UTS"),
    (date(2025, 12, 15), date(2025, 12, 24), "UAS"),
    (date(2025, 12, 25), date(2026, 1, 25),  "LIBUR"),
    (date(2026, 3, 30),  date(2026, 4, 10),  "UTS"),
    (date(2026, 6, 1),   date(2026, 6, 12),  "UAS"),
    (date(2026, 6, 13),  date(2026, 8, 23),  "LIBUR"),
]
# Pengaruh fase akademik ke kunjungan AnakKos & Remaja
FAKTOR_AKADEMIK = {"BIASA": 1.0, "UTS": 1.10, "UAS": 1.20, "LIBUR": 0.35}

# --- Libur nasional (contoh, sesuaikan) ---
LIBUR_NASIONAL = {
    date(2025, 3, 31), date(2025, 4, 1), date(2025, 5, 1), date(2025, 5, 29),
    date(2025, 6, 6), date(2025, 6, 27), date(2025, 8, 17), date(2025, 9, 5),
    date(2025, 12, 25), date(2026, 1, 1), date(2026, 3, 20), date(2026, 3, 21),
    date(2026, 5, 1), date(2026, 5, 27),
}

# --- Guncangan harga beli (tanggal, kategori, pengali) ---
SHOK_HARGA = [
    (date(2025, 9, 1),  "Sembako", 1.10),   # contoh: lonjakan harga pangan
    (date(2025, 11, 15), "Bumbu",  1.07),
    (date(2026, 1, 1),  "Rokok",   1.10),   # contoh: kenaikan cukai
    (date(2026, 3, 1),  "Sembako", 1.08),   # menjelang Lebaran
]

# Inflasi harga beli bulanan per kategori (default 0.005)
INFLASI_KATEGORI = {
    "Sembako": .008, "Bumbu": .006, "Minuman": .004, "Rokok": .003,
    "Frozen": .006, "LPG": .002, "ATK": .004, "Obat": .004,
}

# Elastisitas harga permintaan per kategori (makin besar makin sensitif harga)
ELASTISITAS = {
    "Rokok": .3, "LPG": .2, "Sembako": .6, "Bumbu": .6, "Mi": .8, "Sachet": .8,
    "Minuman": 1.0, "Snack": 1.2, "Perawatan": .8, "Deterjen": .8, "Tisu": .7,
    "Bayi": .4, "Obat": .4, "ATK": .7, "RumahTangga": .7, "Plastik": .8, "Frozen": 1.1,
}

# Margin keuntungan awal per kategori (untuk menghitung harga_beli awal)
MARGIN = {
    "Sembako": .10, "Mi": .12, "Bumbu": .15, "Snack": .25, "Minuman": .20,
    "Sachet": .22, "Rokok": .06, "Perawatan": .15, "Deterjen": .16,
    "Tisu": .18, "Bayi": .12, "Obat": .18, "ATK": .30, "RumahTangga": .25,
    "Plastik": .28, "LPG": .07, "Frozen": .15,
}

# Basis popularitas kategori (makin besar makin cepat berputar)
POP_KATEGORI = {
    "Sembako": 1.2, "Mi": 1.8, "Bumbu": 1.0, "Snack": 1.4, "Minuman": 1.5,
    "Sachet": 1.6, "Rokok": 1.3, "Perawatan": .7, "Deterjen": .8,
    "Tisu": .5, "Bayi": .4, "Obat": .5, "ATK": .4, "RumahTangga": .3,
    "Plastik": .5, "LPG": .6, "Frozen": .7,
}

# Pengali popularitas produk tertentu (barang laku keras / barang lambat)
POP_PRODUK = {
    "Mi goreng Indomie": 2.2, "Mi ayam bawang Indomie": 1.5, "Mi soto Indomie": 1.5,
    "Aqua 600ml": 2.0, "Teh Gelas 350ml": 1.6, "Kopi Kapal Api sachet": 1.9,
    "Kopi Good Day sachet": 1.5, "Surya 16 batang": 1.9, "Surya 12 batang": 1.5,
    "Rinso sachet": 1.4, "Sunlight sachet": 1.4, "Telur ayam 1 butir": 1.6,
    "Beras medium 1kg": 1.5, "Minyakita 1L": 1.4, "Indomie Cup": 1.4,
    "Pop Mie": 1.3, "LPG 3kg": 1.6, "Cornetto": 1.4, "Beng-Beng": 1.5,
    "LPG 5.5kg": 0.4, "LPG 12kg": 0.3, "Beras premium 10kg": 0.5,
}

# Pola jumlah beli per kategori (barang besar biasanya dibeli satuan)
QTY_KATEGORI = {
    "Rokok": ([1, 2], [8, 2]), "Sembako": ([1, 2], [7, 3]),
    "Bayi": ([1, 2], [8, 2]), "Frozen": ([1, 2], [7, 3]),
    "RumahTangga": ([1], [1]), "LPG": ([1], [1]),
}
QTY_DEFAULT = ([1, 2, 3], [6, 3, 1])

# Profil warga -> preferensi kategori belanja
PROFIL = {
    "Ibu":     {"Sembako": 3.0, "Bumbu": 2.5, "Deterjen": 2.0, "Tisu": 1.2, "Plastik": 1.0,
                "Frozen": 1.5, "Bayi": .8, "Perawatan": 1.0, "Minuman": 1.0},
    "Bapak":   {"Rokok": 3.5, "Sachet": 2.0, "LPG": 2.0, "Minuman": 1.0,
                "Obat": .8, "RumahTangga": .8},
    "AnakKos": {"Mi": 3.5, "Snack": 2.5, "Minuman": 2.5, "Sachet": 2.5, "Obat": 1.5,
                "Perawatan": 1.0, "ATK": .8, "Frozen": 1.0},
    "Remaja":  {"Snack": 3.5, "Minuman": 3.0, "Frozen": 2.0, "ATK": 1.5,
                "Sachet": 1.0, "Rokok": .6},
    "Umum":    {"Sembako": 1.5, "Mi": 1.5, "Snack": 1.5, "Minuman": 1.5, "Sachet": 1.5,
                "Bumbu": 1.0, "Deterjen": 1.0, "Perawatan": 1.0, "Obat": 1.0, "Tisu": .8,
                "Plastik": .8, "RumahTangga": .6, "ATK": .6, "Bayi": .5, "LPG": .8,
                "Frozen": 1.0, "Rokok": .8},
}
BOBOT_PROFIL_DEFAULT = [("Ibu", 25), ("Bapak", 25), ("AnakKos", 20), ("Remaja", 18), ("Umum", 12)]

# Ukuran keranjang belanja per kunjungan
UKURAN_KERANJANG = ([1, 2, 3], [6, 3, 1])

# ========================= KONFIGURASI WARUNG =========================
CONFIG_WARUNG = [
    dict(id="W1", nama="Campuran kos-perumahan", seed=1, populasi=60, skala=0.30,
         frac_sku=0.60, mult_harga=1.00, bobot_profil=BOBOT_PROFIL_DEFAULT),
    dict(id="W2", nama="Dekat kampus", seed=2, populasi=90, skala=0.35,
         frac_sku=0.50, mult_harga=0.97, pesaing_permanen_mulai=date(2026, 1, 15),
         bobot_profil=[("Ibu", 10), ("Bapak", 10), ("AnakKos", 45), ("Remaja", 25), ("Umum", 10)]),
    dict(id="W3", nama="Perumahan", seed=3, populasi=45, skala=0.28,
         frac_sku=0.70, mult_harga=1.03,
         bobot_profil=[("Ibu", 40), ("Bapak", 30), ("AnakKos", 5), ("Remaja", 10), ("Umum", 15)]),
    dict(id="W4", nama="Kos padat", seed=4, populasi=80, skala=0.32,
         frac_sku=0.45, mult_harga=1.00,
         bobot_profil=[("Ibu", 5), ("Bapak", 10), ("AnakKos", 60), ("Remaja", 15), ("Umum", 10)]),
    dict(id="W5", nama="Pinggir jalan (pekerja/ojol)", seed=5, populasi=55, skala=0.30,
         frac_sku=0.55, mult_harga=1.02,
         bobot_profil=[("Ibu", 10), ("Bapak", 50), ("AnakKos", 10), ("Remaja", 10), ("Umum", 20)]),
    dict(id="W6", nama="Dekat pasar (ibu-ibu)", seed=6, populasi=50, skala=0.30,
         frac_sku=0.70, mult_harga=0.98, pesaing_permanen_mulai=date(2025, 10, 1),
         bobot_profil=[("Ibu", 50), ("Bapak", 20), ("AnakKos", 5), ("Remaja", 5), ("Umum", 20)]),
]

# ========================= DATA PRODUK =========================
# (kategori, nama_produk, harga_jual)
DATA = [
    # --- 1. Sembako & bahan dapur ---
    ("Sembako", "Beras medium SPHP 5kg", 65000),
    ("Sembako", "Beras premium 5kg", 75000),
    ("Sembako", "Beras premium 10kg", 148000),
    ("Sembako", "Beras medium 1kg", 14000),
    ("Sembako", "Gula pasir Gulaku 1kg", 19000),
    ("Sembako", "Gula pasir Rose Brand 1kg", 18500),
    ("Sembako", "Gula pasir curah 1kg", 18000),
    ("Sembako", "Minyakita 1L", 17000),
    ("Sembako", "Minyak goreng Bimoli 1L", 22000),
    ("Sembako", "Minyak goreng Fortune 1L", 20000),
    ("Sembako", "Minyak goreng Sania 1L", 20500),
    ("Sembako", "Tepung terigu Segitiga Biru 1kg", 14500),
    ("Sembako", "Tepung terigu Kompas 1kg", 12500),
    ("Sembako", "Tepung tapioka Rose Brand 500g", 8000),
    ("Sembako", "Tepung beras Rose Brand 500g", 8500),
    ("Sembako", "Garam Refina 500g", 4000),
    ("Sembako", "Garam Dolphin 500g", 3500),
    ("Sembako", "Telur ayam 1 butir", 2300),
    ("Sembako", "Telur ayam 1kg", 32000),
    ("Sembako", "Santan Kara 65ml", 4000),
    ("Sembako", "Margarin Blue Band 200g", 8000),
    ("Sembako", "Margarin Blue Band 500g", 18000),
    # --- 2. Mi & makanan instan ---
    ("Mi", "Mi goreng Indomie", 3500),
    ("Mi", "Mi ayam bawang Indomie", 3500),
    ("Mi", "Mi soto Indomie", 3500),
    ("Mi", "Mi kari ayam Indomie", 3500),
    ("Mi", "Mi goreng Sedaap", 3500),
    ("Mi", "Mi kuah Sedaap", 3500),
    ("Mi", "Mi goreng Sarimi", 3000),
    ("Mi", "Pop Mie", 6000),
    ("Mi", "Indomie Cup", 6500),
    ("Mi", "Mi jumbo Indomie", 4500),
    ("Mi", "Bihun Rose Brand 320g", 8000),
    ("Mi", "Spaghetti La Fonte 225g", 10000),
    ("Mi", "Makaroni 200g", 7000),
    ("Mi", "Bubur instan 50g", 5000),
    ("Mi", "Oatmeal Quaker 35g", 3500),
    # --- 3. Bumbu & saus ---
    ("Bumbu", "Kecap manis Bango 135ml", 7000),
    ("Bumbu", "Kecap manis ABC 135ml", 6000),
    ("Bumbu", "Kecap manis Sedap 135ml", 5500),
    ("Bumbu", "Saus sambal ABC 135ml", 7000),
    ("Bumbu", "Saus tomat ABC 135ml", 7000),
    ("Bumbu", "Saus sambal sachet ABC", 1500),
    ("Bumbu", "Saus tiram Saori 133ml", 8000),
    ("Bumbu", "Mayones Maestro 100g", 7000),
    ("Bumbu", "Penyedap Royco", 1500),
    ("Bumbu", "Penyedap Masako", 1500),
    ("Bumbu", "Kaldu bubuk Royco 100g", 5500),
    ("Bumbu", "Merica bubuk Ladaku", 1500),
    ("Bumbu", "Terasi ABC 20g", 3000),
    ("Bumbu", "Bawang goreng 50g", 7000),
    ("Bumbu", "Cuka 100ml", 4000),
    ("Bumbu", "Kecap asin ABC 135ml", 6000),
    # --- 4. Snack ---
    ("Snack", "Keripik kentang Chitato 68g", 12000),
    ("Snack", "Snack jagung Chiki", 3000),
    ("Snack", "Snack kentang Qtela 60g", 8000),
    ("Snack", "Snack jagung Cheetos", 3000),
    ("Snack", "Kerupuk 100g", 5000),
    ("Snack", "Basreng 100g", 7000),
    ("Snack", "Makaroni pedas 100g", 6000),
    ("Snack", "Kacang atom Garuda 100g", 7000),
    ("Snack", "Kacang kulit Garuda 100g", 7000),
    ("Snack", "Kacang sukro Garuda 80g", 6000),
    ("Snack", "Kuaci Rebo 100g", 7000),
    ("Snack", "Permen Kopiko", 8000),
    ("Snack", "Permen Relaxa", 7000),
    ("Snack", "Permen karet Big Babol", 2000),
    ("Snack", "Cokelat SilverQueen", 12000),
    ("Snack", "Wafer Tango 115g", 7000),
    ("Snack", "Beng-Beng", 2500),
    ("Snack", "Astor", 2500),
    ("Snack", "Oreo 119g", 8000),
    ("Snack", "Roma Kelapa 300g", 9000),
    ("Snack", "Khong Guan 200g", 9000),
    ("Snack", "Better", 2500),
    # --- 5. Minuman ---
    ("Minuman", "Aqua 330ml", 3000),
    ("Minuman", "Aqua 600ml", 4000),
    ("Minuman", "Aqua 1.5L", 6000),
    ("Minuman", "Le Minerale 600ml", 4000),
    ("Minuman", "Le Minerale 1.5L", 6000),
    ("Minuman", "Teh Pucuk 350ml", 4000),
    ("Minuman", "Teh Botol Sosro 350ml", 5000),
    ("Minuman", "Frestea 350ml", 4000),
    ("Minuman", "Teh Gelas 350ml", 2500),
    ("Minuman", "Good Day 250ml", 5000),
    ("Minuman", "Nescafe 220ml", 6000),
    ("Minuman", "Kopiko 78C 240ml", 6000),
    ("Minuman", "Pocari Sweat 350ml", 7000),
    ("Minuman", "Pocari Sweat 500ml", 9000),
    ("Minuman", "Extra Joss", 2500),
    ("Minuman", "Kukubima sachet", 2500),
    ("Minuman", "Kratingdaeng 150ml", 8000),
    ("Minuman", "Coca-Cola 390ml", 6000),
    ("Minuman", "Sprite 390ml", 6000),
    ("Minuman", "Ultra Milk 250ml", 5500),
    ("Minuman", "Indomilk 190ml", 5000),
    ("Minuman", "Buavita 250ml", 7000),
    # --- 6. Kopi, teh & minuman sachet ---
    ("Sachet", "Kopi Kapal Api sachet", 2000),
    ("Sachet", "Kopi ABC sachet", 2000),
    ("Sachet", "Kopi Good Day sachet", 2000),
    ("Sachet", "Kopi Torabika sachet", 2000),
    ("Sachet", "Kopi susu Good Day sachet", 2000),
    ("Sachet", "Kopi susu Torabika sachet", 2000),
    ("Sachet", "Cappuccino Good Day sachet", 2500),
    ("Sachet", "Teh Sariwangi 1 kantong", 500),
    ("Sachet", "Teh Sariwangi 25 kantong", 8000),
    ("Sachet", "Teh Tong Tji sachet", 1000),
    ("Sachet", "Nutrisari sachet", 2000),
    ("Sachet", "Chocolatos sachet", 2000),
    ("Sachet", "Dancow sachet", 3500),
    ("Sachet", "Milo sachet", 3500),
    ("Sachet", "Extra Joss sachet", 2000),
    # --- 7. Rokok & korek ---
    ("Rokok", "Surya 12 batang", 25000),
    ("Rokok", "Surya 16 batang", 32000),
    ("Rokok", "Gudang Garam Filter 12 batang", 23000),
    ("Rokok", "Gudang Garam 16 batang", 30000),
    ("Rokok", "Djarum Super 12 batang", 24000),
    ("Rokok", "Djarum Super 16 batang", 32000),
    ("Rokok", "Sampoerna Mild 16 batang", 34000),
    ("Rokok", "Sampoerna A 16 batang", 36000),
    ("Rokok", "LA Bold 16 batang", 30000),
    ("Rokok", "LA Ice 16 batang", 31000),
    ("Rokok", "Esse 16 batang", 34000),
    ("Rokok", "Marlboro 16 batang", 42000),
    ("Rokok", "Korek gas", 2000),
    ("Rokok", "Korek kayu", 2000),
    ("Rokok", "Tembakau linting", 15000),
    # --- 8. Sabun, shampoo & personal care ---
    ("Perawatan", "Sabun batang Lifebuoy", 4000),
    ("Perawatan", "Sabun batang Lux", 4500),
    ("Perawatan", "Sabun batang Nuvo", 3500),
    ("Perawatan", "Sabun batang Dettol", 5000),
    ("Perawatan", "Sabun cair Lifebuoy 250ml", 12000),
    ("Perawatan", "Shampoo Sunsilk sachet", 1500),
    ("Perawatan", "Shampoo Pantene sachet", 1500),
    ("Perawatan", "Shampoo Clear sachet", 1500),
    ("Perawatan", "Shampoo H&S sachet", 2000),
    ("Perawatan", "Pasta gigi Pepsodent 75g", 7000),
    ("Perawatan", "Pasta gigi Close Up 65g", 7000),
    ("Perawatan", "Pasta gigi Sensodyne 40g", 20000),
    ("Perawatan", "Sikat gigi Formula", 7000),
    ("Perawatan", "Deodoran Rexona sachet", 4000),
    ("Perawatan", "Deodoran Rexona 45ml", 18000),
    ("Perawatan", "Body lotion Citra 100ml", 10000),
    ("Perawatan", "Parfum Gatsby 100ml", 25000),
    ("Perawatan", "Minyak rambut Gatsby 75g", 15000),
    ("Perawatan", "Pomade Gatsby 80g", 20000),
    # --- 9. Deterjen & kebersihan ---
    ("Deterjen", "Rinso sachet", 2500),
    ("Deterjen", "Soklin sachet", 2000),
    ("Deterjen", "Daia sachet", 2000),
    ("Deterjen", "Attack sachet", 2500),
    ("Deterjen", "Rinso 800g", 18000),
    ("Deterjen", "Molto sachet", 2000),
    ("Deterjen", "Downy sachet", 2000),
    ("Deterjen", "Bayclin 500ml", 8000),
    ("Deterjen", "Sunlight sachet", 2000),
    ("Deterjen", "Sunlight 400ml", 9000),
    ("Deterjen", "Mama Lemon 400ml", 8000),
    ("Deterjen", "Wipol 450ml", 9000),
    ("Deterjen", "Super Pell 450ml", 8000),
    ("Deterjen", "Karbol 500ml", 7000),
    ("Deterjen", "Spons (kebersihan)", 3000),
    ("Deterjen", "Sikat", 7000),
    ("Deterjen", "Kantong sampah", 8000),
    # --- 10. Tisu & kebutuhan pribadi ---
    ("Tisu", "Tisu Paseo", 8000),
    ("Tisu", "Tisu Nice", 7000),
    ("Tisu", "Tisu Tessa", 7000),
    ("Tisu", "Tisu basah Mitu", 8000),
    ("Tisu", "Tisu basah Cussons", 9000),
    ("Tisu", "Pembalut Charm", 10000),
    ("Tisu", "Pembalut Laurier", 10000),
    ("Tisu", "Pembalut Softex", 9000),
    ("Tisu", "Pantyliner Laurier", 12000),
    ("Tisu", "Cotton bud Selection", 5000),
    ("Tisu", "Kapas Selection", 5000),
    # --- 11. Bayi ---
    ("Bayi", "Popok MamyPoko isi 10", 25000),
    ("Bayi", "Popok Sweety isi 10", 22000),
    ("Bayi", "Popok Merries isi 10", 28000),
    ("Bayi", "Susu formula SGM 200g", 25000),
    ("Bayi", "Susu formula Dancow 200g", 30000),
    ("Bayi", "Bubur bayi Promina 120g", 12000),
    ("Bayi", "Biskuit bayi Promina 100g", 10000),
    ("Bayi", "Minyak telon My Baby 60ml", 10000),
    ("Bayi", "Minyak kayu putih Cap Lang 30ml (Bayi)", 10000),
    ("Bayi", "Baby powder My Baby 50g", 7000),
    ("Bayi", "Baby oil My Baby 50ml", 7000),
    # --- 12. Obat bebas & kesehatan ringan ---
    ("Obat", "Paracetamol strip", 3000),
    ("Obat", "Paracetamol Sanmol strip", 4000),
    ("Obat", "Tolak Angin sachet", 4000),
    ("Obat", "Antangin sachet", 3500),
    ("Obat", "Promag strip", 8000),
    ("Obat", "Diapet strip", 7000),
    ("Obat", "Oralit sachet", 2000),
    ("Obat", "Minyak kayu putih Cap Lang 30ml (Obat)", 10000),
    ("Obat", "Balsem Geliga 20g", 8000),
    ("Obat", "FreshCare 10ml", 12000),
    ("Obat", "Salonpas 10 pcs", 15000),
    ("Obat", "Hansaplast 10 pcs", 8000),
    ("Obat", "Masker", 1000),
    ("Obat", "Vitamin C CDR", 3000),
    # --- 13. Alat tulis ---
    ("ATK", "Pulpen Standard AE7", 2500),
    ("ATK", "Pulpen Pilot", 4000),
    ("ATK", "Pensil Faber-Castell", 3000),
    ("ATK", "Penghapus Faber-Castell", 2500),
    ("ATK", "Rautan Joyko", 3000),
    ("ATK", "Penggaris Butterfly 30cm", 3000),
    ("ATK", "Spidol Snowman", 5000),
    ("ATK", "Stabilo", 8000),
    ("ATK", "Correction pen Joyko", 5000),
    ("ATK", "Buku tulis Sinar Dunia", 4000),
    ("ATK", "Buku tulis Kiky", 6000),
    ("ATK", "Buku gambar", 7000),
    ("ATK", "Lem Fox 10g", 3000),
    ("ATK", "Gunting Joyko", 7000),
    ("ATK", "Cutter Joyko", 5000),
    ("ATK", "Map", 2500),
    ("ATK", "Amplop", 1000),
    # --- 14. Rumah tangga ---
    ("RumahTangga", "Sapu lidi", 10000),
    ("RumahTangga", "Sapu ijuk", 20000),
    ("RumahTangga", "Pengki", 12000),
    ("RumahTangga", "Pel", 20000),
    ("RumahTangga", "Ember", 20000),
    ("RumahTangga", "Gayung", 7000),
    ("RumahTangga", "Keset", 15000),
    ("RumahTangga", "Hanger", 3000),
    ("RumahTangga", "Tali per meter", 2000),
    ("RumahTangga", "Lakban", 5000),
    ("RumahTangga", "Isolasi", 3000),
    ("RumahTangga", "Lem Alteco", 4000),
    ("RumahTangga", "Lilin", 2000),
    ("RumahTangga", "Senter", 20000),
    ("RumahTangga", "Baterai AA ABC 2pcs", 8000),
    ("RumahTangga", "Baterai AAA ABC 2pcs", 8000),
    ("RumahTangga", "Bohlam LED Philips 5W", 15000),
    ("RumahTangga", "Bohlam LED Hannochs 9W", 15000),
    ("RumahTangga", "Terminal listrik", 20000),
    ("RumahTangga", "Kabel USB", 15000),
    ("RumahTangga", "Charger", 30000),
    # --- 15. Plastik & kebutuhan dapur ---
    ("Plastik", "Plastik kresek kecil", 5000),
    ("Plastik", "Plastik kresek sedang", 7000),
    ("Plastik", "Plastik kiloan", 10000),
    ("Plastik", "Plastik klip", 5000),
    ("Plastik", "Plastik es", 5000),
    ("Plastik", "Aluminium foil", 10000),
    ("Plastik", "Plastic wrap", 12000),
    ("Plastik", "Tusuk gigi", 3000),
    ("Plastik", "Tusuk sate", 5000),
    ("Plastik", "Sedotan", 5000),
    ("Plastik", "Sendok plastik", 5000),
    ("Plastik", "Gelas plastik", 8000),
    ("Plastik", "Spons cuci piring", 3000),
    ("Plastik", "Lap dapur", 7000),
    # --- 16. LPG & kebutuhan kendaraan ---
    ("LPG", "LPG 3kg", 21000),
    ("LPG", "LPG 5.5kg", 105000),
    ("LPG", "LPG 12kg", 220000),
    ("LPG", "Regulator gas", 100000),
    ("LPG", "Selang gas", 30000),
    ("LPG", "Klem selang", 5000),
    ("LPG", "Oli motor 0.8L", 45000),
    ("LPG", "Oli motor 1L", 60000),
    ("LPG", "Minyak rem 100ml", 15000),
    ("LPG", "Lem ban", 8000),
    ("LPG", "Pengharum mobil", 15000),
    # --- 17. Es krim & frozen food ---
    ("Frozen", "Es krim cone Wall's", 5000),
    ("Frozen", "Es krim cup Wall's", 5000),
    ("Frozen", "Es krim Magnum", 15000),
    ("Frozen", "Cornetto", 12000),
    ("Frozen", "Nugget Fiesta 250g", 25000),
    ("Frozen", "Nugget So Good 250g", 22000),
    ("Frozen", "Sosis So Nice", 15000),
    ("Frozen", "Bakso 250g", 15000),
    ("Frozen", "Tempura 250g", 15000),
    ("Frozen", "Kentang frozen 500g", 20000),
]

# ========================= UTILITAS =========================
def rupiah(n):
    return "Rp" + format(int(n), ",").replace(",", ".")


def bulatkan_harga(x):
    """Harga jual dibulatkan: <10rb ke 100, selebihnya ke 500."""
    langkah = 100 if x < 10_000 else 500
    return max(langkah, int(round(x / langkah) * langkah))


def bulatkan_beli(x):
    return max(50, int(round(x / 50) * 50))


def fase_akademik(tgl):
    for mulai, selesai, fase in KALENDER_AKADEMIK:
        if mulai <= tgl <= selesai:
            return fase
    return "BIASA"


# ========================= KALENDER (bersama semua warung) =========================
@dataclass
class Hari:
    tgl: date
    hujan: bool
    akhir_pekan: bool
    gajian: bool
    libur_nasional: bool
    fase: str


def bangun_kalender(mulai, jumlah_hari, rng):
    """Hujan dibangkitkan sebagai rantai Markov agar mengelompok (lebih sering di musim hujan)."""
    kal, hujan_kemarin = [], False
    for h in range(jumlah_hari):
        tgl = mulai + timedelta(days=h)
        musim_hujan = tgl.month in (11, 12, 1, 2, 3)
        if hujan_kemarin:
            p = 0.65 if musim_hujan else 0.35
        else:
            p = 0.30 if musim_hujan else 0.07
        hujan = rng.random() < p
        hujan_kemarin = hujan
        kal.append(Hari(tgl, hujan, tgl.weekday() >= 5, tgl.day in TANGGAL_GAJIAN,
                        tgl in LIBUR_NASIONAL, fase_akademik(tgl)))
    return kal


# ========================= AGEN & OBJEK =========================
@dataclass
class Item:
    kategori: str
    nama: str
    harga_jual: int
    harga_ref: float        # acuan harga "wajar" (naik mengikuti inflasi umum)
    pasar: float            # harga beli supplier terkini
    hpp: float              # harga pokok rata-rata bergerak
    pop: float
    el: float               # elastisitas harga
    stok: int
    stok_min: int
    stok_target: int
    margin_target: float    # margin yang dijaga saat menyesuaikan harga
    w: float = 1.0          # bobot permintaan (popularitas x efek harga)

    def hitung_bobot(self):
        rasio = min(1.5, max(0.5, self.harga_ref / self.harga_jual))
        self.w = self.pop * (rasio ** self.el)


class Warung:
    def __init__(self, cfg, rng, mulai):
        self.cfg, self.rng, self.mulai = cfg, rng, mulai
        self.id = cfg["id"]
        self.items = self._buat_stok()
        self.per_kat = defaultdict(list)
        for it in self.items:
            self.per_kat[it.kategori].append(it)
        self.pesaing_hari = False
        self.pesaing_permanen = False
        self.log_pembelian, self.log_harga, self.log_stockout = [], [], []
        # stok awal dicatat sebagai pembelian pada hari pertama
        for it in self.items:
            q, it.stok = it.stok, 0
            self._beli(it, q, mulai)

    def _buat_stok(self):
        rng, cfg = self.rng, self.cfg
        per_kat = defaultdict(list)
        for row in DATA:
            per_kat[row[0]].append(row)
        terpilih = []
        for kat, rows in per_kat.items():           # jaga agar tiap kategori terwakili
            n = max(1, round(len(rows) * cfg["frac_sku"]))
            terpilih.extend(rng.sample(rows, n))
        items = []
        for kat, nama, jual_dasar in terpilih:
            beli = bulatkan_beli(jual_dasar * (1 - MARGIN[kat]))
            beli = min(beli, jual_dasar - 50)
            jual = max(bulatkan_harga(jual_dasar * cfg["mult_harga"]), beli + 50)
            pop = POP_KATEGORI[kat] * rng.uniform(0.6, 1.4) * POP_PRODUK.get(nama, 1.0)
            stok = max(3, min(80, round(pop * 20)))
            it = Item(kat, nama, jual, float(jual), float(beli), float(beli), pop,
                      ELASTISITAS[kat], stok, max(2, stok // 4), stok, 1 - beli / jual)
            it.hitung_bobot()
            items.append(it)
        return items

    # ---------- transaksi stok ----------
    def _beli(self, it, qty, tgl):
        harga = bulatkan_beli(it.pasar * self.rng.uniform(0.98, 1.02))
        it.hpp = harga if it.stok <= 0 else (it.stok * it.hpp + qty * harga) / (it.stok + qty)
        it.stok += qty
        self.log_pembelian.append([self.id, tgl.isoformat(), it.nama, it.kategori, qty, harga])

    def jual(self, it, qty):
        q = min(qty, it.stok)
        it.stok -= q
        return max(q, 0)

    # ---------- dinamika harian ----------
    def mulai_hari(self, hari):
        tgl, rng = hari.tgl, self.rng
        self.pesaing_hari = rng.random() < PELUANG_PESAING
        mulai_perm = self.cfg.get("pesaing_permanen_mulai")
        self.pesaing_permanen = bool(mulai_perm and tgl >= mulai_perm)

        ubah_bobot = False
        # inflasi bulanan harga beli & harga acuan pembeli
        if tgl.day == 1 and tgl != self.mulai:
            for it in self.items:
                infl = INFLASI_KATEGORI.get(it.kategori, 0.005)
                it.pasar *= 1 + rng.gauss(infl, 0.004)
                it.harga_ref *= 1 + INFLASI_UMUM
            ubah_bobot = True
        # guncangan harga (komoditas/cukai)
        for tgl_shok, kat, pengali in SHOK_HARGA:
            if tgl == tgl_shok:
                for it in self.per_kat.get(kat, ()):                   it.pasar *= pengali
        # penyesuaian harga jual tiap Senin (ada jeda dari perubahan harga beli)
        if tgl.weekday() == 0:
            self._atur_harga(tgl)
            ubah_bobot = True
        if ubah_bobot:
            for it in self.items:
                it.hitung_bobot()
        self._restock_pagi(tgl)

    def _atur_harga(self, tgl):
        for it in self.items:
            target = max(bulatkan_harga(it.pasar / (1 - it.margin_target)),
                         bulatkan_beli(it.pasar) + 50)
            if abs(target / it.harga_jual - 1) > 0.03:
                self.log_harga.append([self.id, tgl.isoformat(), it.nama, it.harga_jual, target])
                it.harga_jual = target

    def _restock_pagi(self, tgl):
        """Supplier per kategori datang dengan peluang tertentu; isi hingga stok_target."""
        for kat, daftar in self.per_kat.items():
            if self.rng.random() >= PELUANG_SUPPLIER:
                continue
            for it in daftar:
                if it.stok < it.stok_min:
                    self._beli(it, it.stok_target - it.stok, tgl)


class Pembeli:
    def __init__(self, rng, bobot_profil):
        self.rng = rng
        self.profil = rng.choices([p for p, _ in bobot_profil],
                                  weights=[w for _, w in bobot_profil])[0]
        self.aff = {k: v * rng.uniform(0.7, 1.3) for k, v in PROFIL[self.profil].items()}
        self.kepribadian = rng.uniform(0.5, 1.3)
        self.uang = 0.0
        self.kand = None            # cache (item, afinitas) per warung

    def reset_harian(self, gajian):
        self.uang = self.rng.uniform(*UANG_HARIAN)
        if gajian:
            self.uang *= 1.6

    def mau_datang(self, jam, hari, w):
        p = POLA_JAM.get(jam, 0.0) * w.cfg["skala"]
        if hari.akhir_pekan or hari.libur_nasional:
            p *= 1.25
        if hari.hujan:
            p *= 0.45
        if w.pesaing_hari and jam in (10, 16):
            p *= 0.6
        if w.pesaing_permanen:
            p *= 0.85
        if self.profil in ("AnakKos", "Remaja"):
            p *= FAKTOR_AKADEMIK[hari.fase]
        if self.uang < 3_000:
            p *= 0.4
        p *= self.kepribadian
        return self.rng.random() < p

    def _qty(self, it):
        pilih, bobot = QTY_KATEGORI.get(it.kategori, QTY_DEFAULT)
        return self.rng.choices(pilih, weights=bobot)[0]

    def belanja(self, w, tgl, jam):
        """Satu pembelian item. Mengembalikan (item, qty) atau None."""
        rng = self.rng
        if self.kand is None:
            self.kand = [(it, a) for kat, a in self.aff.items() for it in w.per_kat.get(kat, ())]
        if not self.kand:
            return None
        it = rng.choices([k for k, _ in self.kand],
                         weights=[a * k.w for k, a in self.kand])[0]
        qty = self._qty(it)

        if it.stok <= 0:                                   # stok habis -> permintaan hilang
            alt = [x for x in w.per_kat[it.kategori] if x.stok > 0]
            subst = bool(alt) and rng.random() < P_SUBSTITUSI
            w.log_stockout.append([w.id, tgl.isoformat(), f"{jam:02d}:00", it.nama, qty, int(subst)])
            if not subst:
                return None
            it = rng.choices(alt, weights=[x.w for x in alt])[0]
            qty = self._qty(it)

        while qty > 0 and it.harga_jual * qty > self.uang:
            qty -= 1
        if qty == 0:                                       # uang tidak cukup -> batal
            return None
        if it.stok < qty:                                  # stok kurang sebagian
            w.log_stockout.append([w.id, tgl.isoformat(), f"{jam:02d}:00",
                                   it.nama, qty - it.stok, 0])
            qty = it.stok
        terjual = w.jual(it, qty)
        if terjual == 0:
            return None
        self.uang -= it.harga_jual * terjual
        return it, terjual


# ========================= SIMULASI SATU WARUNG =========================
def simulasi(cfg, kalender, mulai):
    rng = random.Random(cfg["seed"])
    w = Warung(cfg, rng, mulai)
    warga = [Pembeli(rng, cfg["bobot_profil"]) for _ in range(cfg["populasi"])]
    baris, bulanan = [], defaultdict(lambda: [0, 0, 0])   # trx, omzet, laba
    n_trx = 0

    for hari in kalender:
        w.mulai_hari(hari)
        for p in warga:
            p.reset_harian(hari.gajian)
        ym = hari.tgl.strftime("%Y-%m")
        for jam in range(JAM_BUKA, JAM_TUTUP + 1):
            for p in warga:
                if not p.mau_datang(jam, hari, w):
                    continue
                ukuran = rng.choices(UKURAN_KERANJANG[0], weights=UKURAN_KERANJANG[1])[0]
                trx_id, ada = None, False
                for _ in range(ukuran):
                    hasil = p.belanja(w, hari.tgl, jam)
                    if hasil is None:
                        break
                    it, qty = hasil
                    if trx_id is None:
                        n_trx += 1
                        trx_id = f"{w.id}-{n_trx:06d}"
                    hpp = int(round(it.hpp))
                    baris.append([w.id, trx_id, hari.tgl.isoformat(), f"{jam:02d}:00",
                                  it.nama, it.kategori, qty, it.harga_jual, hpp, it.stok])
                    b = bulanan[ym]
                    b[1] += it.harga_jual * qty
                    b[2] += (it.harga_jual - hpp) * qty
                    ada = True
                if ada:
                    bulanan[ym][0] += 1

    return dict(warung=w, penjualan=baris, bulanan=bulanan)


# ========================= PEMERIKSAAN KUALITAS DATA =========================
def periksa_kualitas(w, baris, jumlah_hari):
    hari_terjual, omzet = defaultdict(set), Counter()
    for r in baris:
        hari_terjual[r[4]].add(r[2])
        omzet[r[4]] += r[7] * r[6]
    persen_nol = [100 * (1 - len(hari_terjual.get(it.nama, ())) / jumlah_hari) for it in w.items]
    urut = sorted((omzet.get(it.nama, 0) for it in w.items), reverse=True)
    k = max(1, round(0.2 * len(urut)))
    total = sum(urut) or 1
    return statistics.median(persen_nol), 100 * sum(urut[:k]) / total


# ========================= MAIN =========================
def tulis_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(header)
        wr.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hari", type=int, default=JUMLAH_HARI)
    ap.add_argument("--out", default="data_simulasi")
    ap.add_argument("--bulanan", action="store_true", help="cetak ringkasan bulanan per warung")
    args, unknown = ap.parse_known_args() # Modified this line

    assert len({d[1] for d in DATA}) == len(DATA), "Ada nama produk duplikat di DATA"
    os.makedirs(args.out, exist_ok=True)

    kalender = bangun_kalender(TANGGAL_MULAI, args.hari, random.Random(SEED_KALENDER))
    print(f"Periode {kalender[0].tgl} s.d. {kalender[-1].tgl} ({args.hari} hari) | "
          f"{len(CONFIG_WARUNG)} warung | katalog master {len(DATA)} SKU")
    print(f"Hari hujan: {sum(h.hujan for h in kalender)} | "
          f"libur semester: {sum(h.fase == 'LIBUR' for h in kalender)} hari\n")

    semua_jual, semua_beli, semua_stock, semua_harga, info = [], [], [], [], []

    for cfg in CONFIG_WARUNG:
        hasil = simulasi(cfg, kalender, TANGGAL_MULAI)
        w, baris = hasil["warung"], hasil["penjualan"]
        semua_jual += baris
        semua_beli += w.log_pembelian
        semua_stock += w.log_stockout
        semua_harga += w.log_harga

        omzet = sum(r[7] * r[6] for r in baris)
        laba = sum((r[7] - r[8]) * r[6] for r in baris)
        trx = len({r[1] for r in baris})
        med_nol, pareto = periksa_kualitas(w, baris, args.hari)
        info.append([cfg["id"], cfg["nama"], cfg["populasi"], cfg["frac_sku"],
                     len(w.items), cfg["mult_harga"]])

        print(f"[{cfg['id']}] {cfg['nama']}")
        print(f"   SKU aktif={len(w.items)} | baris={len(baris):,} | transaksi={trx:,} | "
              f"omzet={rupiah(omzet)} | laba kotor={rupiah(laba)} "
              f"({100 * laba / max(omzet, 1):.1f}%)者に教えてあげましょう")
        print(f"   stockout={len(w.log_stockout):,} | perubahan harga={len(w.log_harga):,} | "
              f"median hari-tanpa-penjualan per SKU={med_nol:.0f}% | "
              f"20% SKU teratas = {pareto:.0f}% omzet")
        if args.bulanan:
            for ym in sorted(hasil["bulanan"]):
                t, o, l = hasil["bulanan"][ym]
                print(f"     {ym} | trx={t:>5} | omzet={rupiah(o):>14} | laba={rupiah(l):>13}")
        top = Counter()
        for r in baris:
            top[r[4]] += r[6]
        print("   Top 3: " + ", ".join(f"{n} ({q})" for n, q in top.most_common(3)) + "\n")

    d = args.out
    tulis_csv(f"{d}/penjualan.csv",
              ["warung_id", "trx_id", "tanggal", "jam", "produk", "kategori", "jumlah",
               "harga_jual", "harga_beli", "stok_akhir"], semua_jual)
    tulis_csv(f"{d}/pembelian.csv",
              ["warung_id", "tanggal", "produk", "kategori", "jumlah", "harga_beli"], semua_beli)
    tulis_csv(f"{d}/stockout.csv",
              ["warung_id", "tanggal", "jam", "produk", "jumlah_hilang", "disubstitusi"], semua_stock)
    tulis_csv(f"{d}/harga.csv",
              ["warung_id", "tanggal", "produk", "harga_lama", "harga_baru"], semua_harga)
    tulis_csv(f"{d}/kalender.csv",
              ["tanggal", "hari", "hujan", "akhir_pekan", "libur_nasional", "gajian", "fase_akademik"],
              [[h.tgl.isoformat(), h.tgl.strftime("%a"), int(h.hujan), int(h.akhir_pekan),
                int(h.libur_nasional), int(h.gajian), h.fase] for h in kalender])
    tulis_csv(f"{d}/warung.csv",
              ["warung_id", "nama", "populasi", "frac_sku", "sku_aktif", "mult_harga"], info)

    print(f"Total: {len(semua_jual):,} baris penjualan | {len(semua_beli):,} pembelian | "
          f"{len(semua_stock):,} stockout | {len(semua_harga):,} perubahan harga")
    print(f"Tersimpan di folder '{d}/'")


if __name__ == "__main__":
    main()
