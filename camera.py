"""
Seruni Map — Camera System

PAA Concepts Used:
1. Viewport Culling
   Hanya tile yang berada dalam area tampilan (viewport)
   yang diproses dan dirender.

2. Level of Detail (LOD)
   Detail objek disesuaikan dengan tingkat zoom untuk
   mengurangi beban komputasi.

3. Tile Caching
   Hasil render tile disimpan terlebih dahulu agar tidak
   perlu dihitung ulang setiap frame.

4. Time-Space Tradeoff
   Menggunakan memori tambahan untuk menyimpan cache
   demi mempercepat waktu eksekusi saat runtime.
"""

import pygame
from config import (EMPTY, STRAIGHT, CURVE, TJUNCTION, CROSS,
                    TILE_PORTS, get_ports)


class Camera:
    """
    Mengelola viewport dunia (world space) ke layar (screen space).

    Dari sudut pandang PAA, kelas ini membantu mengurangi
    jumlah objek yang perlu diproses dengan menentukan
    area yang benar-benar terlihat oleh pengguna.
    """

    def __init__(self, world_w, world_h, screen_w, screen_h):
        self.x = world_w / 2
        self.y = world_h / 2

        # Nilai zoom awal
        self.zoom = 0.35

        # Batas zoom untuk mencegah tampilan terlalu dekat/jauh
        self.min_zoom = 0.06
        self.max_zoom = 3.0

        self.sw = screen_w
        self.sh = screen_h

        # Variabel drag kamera
        self.dragging = False
        self.drag_start = None
        self.drag_cam = None

    def world_to_screen(self, wx, wy):
        """
        Konversi koordinat dunia ke koordinat layar.

        Kompleksitas Waktu: O(1)
        """
        return ((wx - self.x) * self.zoom + self.sw / 2,
                (wy - self.y) * self.zoom + self.sh / 2)

    def screen_to_world(self, sx, sy):
        """
        Konversi koordinat layar ke koordinat dunia.

        Kompleksitas Waktu: O(1)
        """
        return ((sx - self.sw / 2) / self.zoom + self.x,
                (sy - self.sh / 2) / self.zoom + self.y)

    def get_visible_tiles(self, tile_size, cols, rows):
        """
        Viewport Culling Algorithm

        Menentukan rentang tile yang terlihat pada layar.

        Tanpa optimasi:
            Semua tile diproses
            Kompleksitas ≈ O(cols × rows)

        Dengan viewport culling:
            Hanya tile yang terlihat diproses
            Kompleksitas ≈ O(v)

        di mana v adalah jumlah tile dalam viewport.
        """

        lx, ty = self.screen_to_world(0, 0)
        rx, by = self.screen_to_world(self.sw, self.sh)

        c0 = max(0, int(lx / tile_size) - 1)
        c1 = min(cols, int(rx / tile_size) + 2)

        r0 = max(0, int(ty / tile_size) - 1)
        r1 = min(rows, int(by / tile_size) + 2)

        return c0, c1, r0, r1

    def get_lod(self):
        """
        Level of Detail (LOD)

        Strategi optimasi yang mengurangi jumlah detail
        berdasarkan tingkat zoom.

        HIGH   -> Detail penuh
        MEDIUM -> Detail sedang
        LOW    -> Detail minimum

        Tujuan:
        Mengurangi jumlah operasi rendering saat objek
        terlihat kecil di layar.
        """

        if self.zoom > 0.5:
            return 2   # HIGH

        if self.zoom > 0.2:
            return 1   # MEDIUM

        return 0       # LOW

    def zoom_at(self, mx, my, factor):
        """
        Zoom terhadap posisi kursor.

        Kompleksitas Waktu: O(1)
        """

        wx, wy = self.screen_to_world(mx, my)

        self.zoom = max(
            self.min_zoom,
            min(self.max_zoom, self.zoom * factor)
        )

        nwx, nwy = self.screen_to_world(mx, my)

        self.x -= (nwx - wx)
        self.y -= (nwy - wy)

    def start_drag(self, mx, my):
        """
        Menyimpan posisi awal saat proses drag dimulai.
        """

        self.dragging = True
        self.drag_start = (mx, my)
        self.drag_cam = (self.x, self.y)

    def do_drag(self, mx, my):
        """
        Menggeser kamera berdasarkan pergerakan mouse.

        Kompleksitas Waktu: O(1)
        """

        if not self.dragging:
            return

        dx = (mx - self.drag_start[0]) / self.zoom
        dy = (my - self.drag_start[1]) / self.zoom

        self.x = self.drag_cam[0] - dx
        self.y = self.drag_cam[1] - dy

    def stop_drag(self):
        """
        Mengakhiri proses drag kamera.
        """
        self.dragging = False

    def center_on(self, wx, wy, lerp_t=0.08):
        """
        Smooth Camera Following.

        Menggunakan pendekatan linear interpolation (LERP)
        agar perpindahan kamera terlihat halus.

        Kompleksitas Waktu: O(1)
        """

        self.x += (wx - self.x) * lerp_t
        self.y += (wy - self.y) * lerp_t


class TileCache:
    """
    Tile Cache System

    Konsep PAA:
    Menggunakan teknik caching untuk menghindari
    perhitungan/rendering ulang yang sama berulang kali.

    Trade-off:
    + Runtime lebih cepat
    - Membutuhkan memori tambahan

    Ini merupakan contoh Time-Space Tradeoff.
    """

    def __init__(self, tile_size, draw_funcs):
        self.ts = tile_size
        self.draw_funcs = draw_funcs

        # Cache untuk detail tinggi
        self.high = {}

        # Cache untuk detail menengah
        self.medium = {}

    def build(self, grass_color, road_color, sidewalk_color):
        """
        Preprocessing Stage

        Seluruh kombinasi tile dirender sekali di awal
        lalu disimpan ke dalam cache.

        Keuntungan:
        Runtime tidak perlu membuat ulang surface
        setiap frame.

        Kompleksitas:
        O(jumlah_tipe_tile × jumlah_rotasi)
        dilakukan hanya sekali saat inisialisasi.
        """

        T2 = self.ts
        MG2 = (T2 - 34) // 2
        RW2 = 34

        # Membuat cache HIGH LOD
        for tt in [STRAIGHT, CURVE, TJUNCTION, CROSS]:
            for rot in range(len(TILE_PORTS[tt])):
                s = pygame.Surface((T2, T2))
                s.fill(grass_color)

                self.draw_funcs[tt](s, 0, 0, tt, rot)

                self.high[(tt, rot)] = s

        # Membuat cache MEDIUM LOD
        for tt in [STRAIGHT, CURVE, TJUNCTION, CROSS]:
            for rot in range(len(TILE_PORTS[tt])):
                s = pygame.Surface((T2, T2))
                s.fill(grass_color)

                ports = get_ports(tt, rot)

                pygame.draw.rect(
                    s,
                    road_color,
                    (MG2, MG2, RW2, RW2)
                )

                for p in ports:
                    if p == 0:
                        pygame.draw.rect(
                            s, road_color,
                            (MG2, 0, RW2, T2 // 2)
                        )

                    elif p == 1:
                        pygame.draw.rect(
                            s, road_color,
                            (T2 // 2, MG2, T2 // 2, RW2)
                        )

                    elif p == 2:
                        pygame.draw.rect(
                            s, road_color,
                            (MG2, T2 // 2, RW2, T2 // 2)
                        )

                    elif p == 3:
                        pygame.draw.rect(
                            s, road_color,
                            (0, MG2, T2 // 2, RW2)
                        )

                for d in ({0, 1, 2, 3} - ports):
                    if d == 0:
                        pygame.draw.rect(
                            s, sidewalk_color,
                            (MG2, 0, RW2, 4)
                        )

                    elif d == 2:
                        pygame.draw.rect(
                            s, sidewalk_color,
                            (MG2, T2 - 4, RW2, 4)
                        )

                    elif d == 3:
                        pygame.draw.rect(
                            s, sidewalk_color,
                            (0, MG2, 4, RW2)
                        )

                    elif d == 1:
                        pygame.draw.rect(
                            s, sidewalk_color,
                            (T2 - 4, MG2, 4, RW2)
                        )

                self.medium[(tt, rot)] = s

        # Cache untuk tile kosong
        e = pygame.Surface((T2, T2))
        e.fill(grass_color)

        self.high[(EMPTY, 0)] = e
        self.medium[(EMPTY, 0)] = e

    def get(self, tile_type, rotation, lod):
        """
        Mengambil tile dari cache.

        Menggunakan dictionary (hash table),
        sehingga lookup memiliki kompleksitas
        rata-rata O(1).

        Ini lebih efisien dibanding melakukan
        render ulang setiap kali tile dibutuhkan.
        """

        key = (tile_type, rotation)

        if tile_type == EMPTY:
            key = (EMPTY, 0)

        if lod >= 2:
            return self.high.get(key)

        return self.medium.get(key)