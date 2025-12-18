# Fruit Ninja Game

Game Fruit Ninja sederhana berbasis Python, OpenCV, dan Pygame dengan mode Solo dan Multiplayer. Pemain memotong buah dengan gerakan tangan di depan kamera (hand tracking).

## Fitur

- Kontrol menggunakan gerakan tangan (webcam + hand tracking).
- Mode Solo (skor, level, batas miss).
- Mode Multiplayer untuk 2 pemain (P1 dan P2) dalam satu kamera.
- Beberapa tema/background (kayu, kaktus, salju, sakura).
- Efek suara dan tampilan Game Over dengan kartu skor dan tombol:
  - Kembali ke menu
  - Main ulang
  - Simpan data skor ke Excel

## Kebutuhan

- Python 3.10+
- PIP
- Webcam
- Sistem operasi yang mendukung Python dan Pygame

Semua dependency di-install lewat `requirements.txt`.

## Instalasi & Menjalankan

1. Clone repository ini:
   git clone https://github.com/Neararest/Fruit_Ninja_Game.git

2. Pindah folder:
   cd Fruit_Ninja_Game

3. Install dependency:
   pip install -r requirements.txt

4. Jalankan game:
   python main.py

## Cara Main

- Pilih mode Solo atau Multi di menu.
- Gerakkan jari di depan kamera untuk memotong buah.
- Hindari bom dan jangan terlalu banyak miss.
- Di Multiplayer, sisi kiri untuk Player 1 dan sisi kanan untuk Player 2.
- Setelah Game Over, gunakan tombol di card untuk kembali ke menu, restart, atau menyimpan skor.

## Struktur Folder

- `assets/` – gambar, suara, font.
- `core/` – logika buah, hand tracking, suara, dan simpan data.
- `game/` – `solo_game.py` dan `multi_game.py`.
- `ui/` – kode menu dan navigasi.
- `main.py` – entry point aplikasi.
