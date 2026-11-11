# Fruit Ninja Game

Game Fruit Ninja berbasis Python, OpenCV, MediaPipe, dan Pygame dengan mode Solo dan Duel Multiplayer. Pemain memotong buah yang melambung menggunakan gerakan tangan di depan kamera.

## Fitur

- Sistem akun pemain (masuk, daftar akun baru, atau bermain sebagai tamu).
- Mode Solo dengan perhitungan skor, peningkatan level, batas maksimal 10 buah terlewat, bom, serta sistem combo streak (pengali poin hingga 4x) dan bonus tebasan ganda.
- Mode Duel Multiplayer untuk 2 pemain dalam satu kamera (sisi kiri dan sisi kanan layar) dengan batas waktu 90 detik, batas 10 buah terlewat per pemain, penanda layar gelap ketika salah satu pemain gugur, combo streak masing-masing pemain.
- Papan peringkat untuk Mode Solo dan Duel Multiplayer beserta fitur ekspor data peringkat ke file Excel.
- Pengaturan musik latar, efek suara, pilihan jari yang dilacak kamera, durasi tahan klik pada menu, dan pratinjau kamera mini.
- Pilihan tema arena permainan, yaitu Gurun Kaktus, Dojo Kayu, Lembah Salju, dan Taman Sakura.

## Kebutuhan

- Python 3.12 atau kebawah
- PIP
- Webcam

Semua pustaka yang dibutuhkan tercantum pada file `requirements.txt`.

## Instalasi dan Cara Menjalankan

1. Clone repositori ini:
   ```bash
   git clone https://github.com/Neararest/Fruit_Ninja_Game.git
   ```
2. Masuk ke direktori proyek:
   ```bash
   cd Fruit_Ninja_Game
   ```
3. Pasang seluruh pustaka yang diperlukan:
   ```bash
   pip install -r requirements.txt
   ```
4. Jalankan permainan:
   ```bash
   python main.py
   ```

## Cara Bermain

1. Masuk menggunakan akun yang sudah dibuat, daftar akun baru, atau pilih main tanpa akun.
2. Pada menu utama, pilih **Main Solo** atau **Duel Multi**. Untuk berinteraksi dengan tombol menu menggunakan kamera, arahkan jari ke tombol dan tahan sejenak hingga lingkaran penuh.
3. Di dalam arena, gerakkan jari di depan kamera untuk menebas buah yang terlempar ke atas dan hindari bom.
4. Pada mode **Duel Multi**, pemain pertama berada di sisi kiri layar dan pemain kedua berada di sisi kanan layar. Pemain yang menebas bom atau melewatkan 10 buah akan gugur lebih dulu, sedangkan pemenang ditentukan dari perolehan skor akhir.
5. Setelah permainan selesai atau saat menjeda permainan (tombol `P` atau `Esc`), pemain dapat mengulang permainan, membuka papan peringkat, atau kembali ke menu utama.

## Struktur Folder

- `assets/` berisi aset gambar buah, ikon tombol, tema arena, efek suara, musik latar, dan font.
- `core/` berisi logika pelacakan tangan (`hand_tracker.py`), fisika buah (`fruit.py`), pengaturan (`settings.py`), audio (`sound_manager.py`), database SQLite (`database.py`), dan ekspor Excel (`dataexcel.py`).
- `game/` berisi logika permainan untuk mode Solo (`solo_game.py`) dan Duel Multiplayer (`multi_game.py`).
- `ui/` berisi komponen antarmuka (`components.py`) serta alur menu dan navigasi (`navigation.py`).
- `main.py` adalah berkas utama untuk menjalankan aplikasi.
- `requirements.txt` berisi daftar pustaka Python yang diperlukan.
