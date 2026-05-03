"""
core/blink.py
=============
BlinkController — Finite State Machine untuk animasi kedip mata natural.

Usage:
    blinker = BlinkController()
    # di dalam game loop:
    blinker.update(current_time)
    draw_eyelid(screen, left_eye_rect, blinker.progress)
"""

import random


class BlinkController:
    """FSM tiga-state: idle → closing → opening → idle (loop)."""

    SPEED_DEFAULT = 0.15   # Fraksi per frame (di 60 FPS ≈ 150 ms untuk menutup penuh)

    def __init__(self, speed: float = SPEED_DEFAULT):
        self.speed       = speed
        self.progress    = 0.0          # 0.0 = mata terbuka, 1.0 = mata tertutup
        self._state      = "closing"    # Mulai langsung kedip pertama saat boot
        self._last_blink = 0            # Timestamp ms kapan terakhir selesai kedip
        self._next_wait  = random.randint(2000, 5000)

    # ── Public API ─────────────────────────────────────────────────────────────

    def update(self, current_time: int) -> float:
        """
        Perbarui state FSM berdasarkan waktu saat ini.

        Args:
            current_time: Nilai dari pygame.time.get_ticks() (milidetik).

        Returns:
            Nilai progress kedip saat ini (0.0 – 1.0).
        """
        if self._state == "closing":
            self.progress += self.speed
            if self.progress >= 1.0:
                self.progress = 1.0
                self._state   = "opening"

        elif self._state == "opening":
            self.progress -= self.speed
            if self.progress <= 0.0:
                self.progress    = 0.0
                self._state      = "idle"
                self._last_blink = current_time
                self._next_wait  = random.randint(2000, 6000)

        elif self._state == "idle":
            if current_time - self._last_blink > self._next_wait:
                self._state = "closing"

        return self.progress

    def force_blink(self):
        """Paksa kedip sekarang (berguna saat transisi ekspresi)."""
        if self._state == "idle":
            self._state = "closing"

    def reset(self):
        """Reset ke kondisi awal (mata terbuka, menunggu kedip berikutnya)."""
        self.progress    = 0.0
        self._state      = "idle"
        self._last_blink = 0
        self._next_wait  = random.randint(500, 1500)
