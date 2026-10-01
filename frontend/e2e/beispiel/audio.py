"""Leise WAV-Dateien für die Beispiel-Besprechungen (8 kHz, 8 Bit, mono).

    python3 e2e/beispiel/audio.py <STORAGE_LOCAL_PATH> <org-id>

Die Länge passt zu duration_sec in daten.sql, damit der Spieler auf
/m/… dieselbe Dauer zeigt wie die Liste.
"""
import os
import random
import sys
import wave

wurzel, org = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(wurzel, org), exist_ok=True)
for mid, sekunden in [
    ("11111111-1111-4111-8111-000000000001", 1260),
    ("11111111-1111-4111-8111-000000000002", 840),
    ("11111111-1111-4111-8111-000000000003", 600),
]:
    pfad = os.path.join(wurzel, org, mid + ".wav")
    if os.path.exists(pfad):
        continue
    w = wave.open(pfad, "wb")
    w.setnchannels(1)
    w.setsampwidth(1)
    w.setframerate(8000)
    zufall = random.Random(1)
    block = bytes(128 + zufall.randint(-6, 6) for _ in range(8000))
    for _ in range(sekunden):
        w.writeframes(block)
    w.close()
