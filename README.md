# Fruit Ninja Game

Game Fruit Ninja sederhana berbasis Python, OpenCV, dan Pygame dengan mode Solo dan Multiplayer.

## Fitur

- Kontrol menggunakan gerakan tangan (hand tracking dengan kamera web).
- Mode Solo dengan skor, level, dan nyawa.
- Mode Multiplayer untuk 2 pemain (P1 dan P2) di satu kamera.
- Penyimpanan data skor ke file Excel.

## Kebutuhan

- Python 3.10+
- PIP
- Webcam

Semua dependency bisa di-install dari `requirements.txt`.

## Cara Menjalankan

1. Clone repository ini:
    git clone https://github.com/Neararest/Fruit_Ninja_Game.git
    cd Fruit_Ninja_Game

2. Install dependency:
   pip install -r requirements.txt

3. Jalankan game:
    python main.py

## Cara Main

- Pastikan webcam aktif dan menghadap pemain.
- Gunakan tangan untuk “memotong” buah di layar.
- Hindari bom; jika kena bom atau terlalu banyak miss, game akan berakhir.
- Di mode multiplayer, sisi kiri untuk Player 1 dan sisi kanan untuk Player 2.

## Struktur Folder

- `assets/` – gambar, suara, font.
- `core/` – logika utama (fruit, sound, hand tracker, penyimpanan data).
- `game/` – file game solo dan multiplayer.
- `ui/` – kode menu dan tampilan lain.
- `main.py` – entry point untuk menjalankan game.
