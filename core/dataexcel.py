import os
from openpyxl import Workbook, load_workbook
from datetime import datetime


class GameDataSaver:
    def __init__(self, filename="game_data.xlsx"):
        self.filename = filename

        folder = os.path.dirname(self.filename)
        if folder:
            os.makedirs(folder, exist_ok=True)

    def _get_sheet(self, sheet_name, header):
        if not os.path.exists(self.filename):
            wb = Workbook()
            ws = wb.active
            ws.title = sheet_name
            ws.append(header)
            wb.save(self.filename)

        wb = load_workbook(self.filename)
        if sheet_name not in wb.sheetnames:
            ws = wb.create_sheet(sheet_name)
            ws.append(header)
        else:
            ws = wb[sheet_name]
            # Pastikan header kompatibel
            first_row = [cell.value for cell in ws[1]] if ws.max_row >= 1 else []
            if first_row != header:
                ws.delete_rows(1, 1)
                ws.insert_rows(1)
                for col_idx, val in enumerate(header, start=1):
                    ws.cell(row=1, column=col_idx, value=val)

        return wb, ws

    def save_multiplayer(self, player1, player2, level, p1_name="Player1", p2_name="Player2"):
        sheet_name = "Multiplayer"
        header = ["Tanggal", "Player1", "Player2", "Level", "Pemenang", "HighScore"]

        wb, ws = self._get_sheet(sheet_name, header)

        if player1 > player2:
            winner = p1_name
        elif player2 > player1:
            winner = p2_name
        else:
            winner = "Draw"

        highscore = max(player1, player2)

        ws.append([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            player1,
            player2,
            level,
            winner,
            highscore,
        ])

        rows = list(ws.iter_rows(values_only=True))[1:]
        rows.sort(key=lambda r: (r[5] if len(r) > 5 and isinstance(r[5], (int, float)) else 0), reverse=True)

        ws.delete_rows(2, ws.max_row)
        for r in rows:
            ws.append(r)

        wb.save(self.filename)

    def save_solo(self, score, missed, level, username="Guest"):
        sheet_name = "Soloplayer"
        header = ["Tanggal", "Username", "Score", "Missed", "Level"]

        wb, ws = self._get_sheet(sheet_name, header)

        # Normalisasi baris lama yang hanya punya 4 kolom [Tanggal, Score, Missed, Level]
        existing_rows = list(ws.iter_rows(values_only=True))[1:]
        normalized_rows = []
        for r in existing_rows:
            if not r:
                continue
            if len(r) == 4 or (len(r) >= 4 and isinstance(r[1], (int, float))):
                normalized_rows.append((r[0], "Guest", r[1], r[2], r[3]))
            else:
                normalized_rows.append(tuple(r[:5]))

        normalized_rows.append((
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            username,
            score,
            missed,
            level,
        ))

        normalized_rows.sort(
            key=lambda r: (r[2] if len(r) > 2 and isinstance(r[2], (int, float)) else 0),
            reverse=True,
        )

        ws.delete_rows(2, ws.max_row)
        for r in normalized_rows:
            ws.append(list(r))

        wb.save(self.filename)
