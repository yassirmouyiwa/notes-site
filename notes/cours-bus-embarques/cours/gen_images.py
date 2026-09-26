#!/usr/bin/env python3
"""Génère les schémas du cours 'Bus de communication embarqués'.
Usage : python3 gen_images.py  -> écrit les PNG dans ./images/
Tous les schémas sont didactiques (échelles de temps non contractuelles)."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

OUT = "images/"
BLUE, RED, GREEN, ORANGE, GREY, PURPLE = "#1f5fa8", "#c0392b", "#1e8449", "#d68910", "#7f8c8d", "#7d3c98"
plt.rcParams.update({"font.size": 10, "font.family": "DejaVu Sans"})


def save(fig, name):
    fig.savefig(OUT + name, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("ok", name)


def steps(ax, times, levels, y0=0, h=0.8, color=BLUE, lw=2):
    """Trace un signal logique : times = instants de changement, levels = niveau (0/1) à partir de chaque instant."""
    t, y = [], []
    for i, (ti, li) in enumerate(zip(times[:-1], levels)):
        t += [ti, times[i + 1]]
        y += [y0 + li * h, y0 + li * h]
    ax.plot(t, y, color=color, lw=lw)


def bits_to_wave(bits, t0=0.0, dt=1.0):
    times = [t0 + i * dt for i in range(len(bits) + 1)]
    return times, list(bits)


def field_bar(ax, fields, y=0, h=1, title=None):
    """fields = [(label, largeur, couleur)]"""
    x = 0
    for label, w, c in fields:
        ax.add_patch(Rectangle((x, y), w, h, facecolor=c, edgecolor="black", lw=1, alpha=0.85))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=8, wrap=True)
        x += w
    ax.set_xlim(-0.5, x + 0.5)
    ax.set_ylim(y - 0.6, y + h + 0.6)
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=11, loc="left", fontweight="bold")
    return x


# ---------------------------------------------------------------- 1. Codages
def fig_codages():
    bits = [1, 0, 1, 1, 0, 0, 1, 0]
    fig, axs = plt.subplots(4, 1, figsize=(10, 6), sharex=True)
    n = len(bits)
    # Horloge
    t = np.arange(0, n + 0.5, 0.5)
    clk = [1 if (i % 2 == 0) else 0 for i in range(len(t) - 1)]
    steps(axs[0], list(t), clk, color=GREY)
    axs[0].set_ylabel("Horloge")
    # NRZ
    steps(axs[1], list(range(n + 1)), bits)
    axs[1].set_ylabel("NRZ")
    # NRZI (convention USB : 0 = transition, 1 = pas de transition)
    lvl, nrzi = 1, []
    for b in bits:
        if b == 0:
            lvl ^= 1
        nrzi.append(lvl)
    steps(axs[2], list(range(n + 1)), nrzi, color=PURPLE)
    axs[2].set_ylabel("NRZI\n(USB)")
    # Manchester IEEE 802.3 : 0 = haut->bas, 1 = bas->haut
    tm, lm = [], []
    for i, b in enumerate(bits):
        tm += [i, i + 0.5]
        lm += [0, 1] if b == 1 else [1, 0]
    tm.append(n)
    steps(axs[3], tm, lm, color=GREEN)
    axs[3].set_ylabel("Manchester\n(IEEE 802.3)")
    for ax in axs:
        ax.set_yticks([])
        ax.set_ylim(-0.3, 1.1)
        for i in range(n + 1):
            ax.axvline(i, color="#ddd", lw=0.8, zorder=0)
    for i, b in enumerate(bits):
        axs[0].text(i + 0.5, 1.0, str(b), ha="center", fontsize=12, fontweight="bold")
    axs[3].set_xlabel("Temps bit")
    fig.suptitle("Codages de ligne : NRZ, NRZI (0 = transition), Manchester (0 = ↓, 1 = ↑)", fontweight="bold")
    save(fig, "00_codages_ligne.png")


# ---------------------------------------------------------------- 2. Débit / distance filaires
def fig_filaire_debit_distance():
    fig, ax = plt.subplots(figsize=(10, 6.5))
    buses = [  # nom, dmin, dmax (m), dbmin, dbmax (bit/s), couleur
        ("SPI", 0.02, 0.5, 1e5, 1e8, BLUE),
        ("I²C", 0.05, 3, 1e4, 3.4e6, GREEN),
        ("UART TTL", 0.05, 2, 300, 3e6, PURPLE),
        ("RS-232", 1, 15, 300, 1.15e6, GREY),
        ("RS-485", 1, 1200, 9600, 3.5e7, ORANGE),
        ("CAN CC", 25, 1000, 1e4, 1e6, RED),
        ("CAN FD (phase data)", 5, 40, 1e6, 8e6, "#e74c3c"),
        ("LIN", 1, 40, 1000, 2e4, "#16a085"),
        ("FlexRay", 1, 24, 2.5e6, 1e7, "#8e44ad"),
        ("100BASE-T1", 1, 15, 9e7, 1e8, "#2c3e50"),
        ("USB 2.0", 0.1, 5, 1.5e6, 4.8e8, "#34495e"),
        ("Ethernet cuivre", 1, 100, 1e7, 1e10, "#5d6d7e"),
        ("PCIe (par voie)", 0.01, 0.5, 2.5e9, 6.4e10, "#922b21"),
        ("MIPI D-PHY/C-PHY", 0.01, 0.3, 8e7, 6e9, "#b7950b"),
    ]
    for name, d0, d1, b0, b1, c in buses:
        ax.add_patch(Rectangle((d0, b0), d1 - d0, b1 - b0, facecolor=c, alpha=0.25, edgecolor=c, lw=1.5))
        ax.text(np.sqrt(d0 * d1), np.sqrt(b0 * b1), name, ha="center", va="center", fontsize=8, color=c, fontweight="bold")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(0.008, 3000); ax.set_ylim(200, 1e11)
    ax.set_xlabel("Distance typique (m)"); ax.set_ylabel("Débit brut (bit/s)")
    ax.set_title("Bus filaires : ordres de grandeur débit / distance (indicatifs)", fontweight="bold")
    ax.grid(True, which="both", alpha=0.3)
    save(fig, "00_filaire_debit_distance.png")


# ---------------------------------------------------------------- 3. Sans fil portée / débit
def fig_sansfil():
    fig, ax = plt.subplots(figsize=(10, 6))
    techs = [
        ("BLE", 1, 100, 1.25e5, 2e6, BLUE),
        ("Zigbee / 802.15.4", 10, 100, 2e4, 2.5e5, GREEN),
        ("Wi-Fi", 10, 150, 1e6, 9.6e9, PURPLE),
        ("LoRaWAN", 1000, 15000, 250, 5.5e3, ORANGE),
        ("NB-IoT", 500, 15000, 2e4, 2.5e5, RED),
        ("LTE-M", 500, 10000, 1e5, 1e6, "#16a085"),
    ]
    for name, d0, d1, b0, b1, c in techs:
        ax.add_patch(Rectangle((d0, b0), d1 - d0, b1 - b0, facecolor=c, alpha=0.25, edgecolor=c, lw=1.5))
        ax.text(np.sqrt(d0 * d1), np.sqrt(b0 * b1), name, ha="center", va="center", fontsize=9, color=c, fontweight="bold")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(0.5, 50000); ax.set_ylim(100, 2e10)
    ax.set_xlabel("Portée typique (m)"); ax.set_ylabel("Débit (bit/s)")
    ax.set_title("Sans fil IoT : portée vs débit (ordres de grandeur)", fontweight="bold")
    ax.grid(True, which="both", alpha=0.3)
    save(fig, "00_sansfil_portee_debit.png")


# ---------------------------------------------------------------- 4. UART
def fig_uart():
    byte = 0x41  # 'A'
    data = [(byte >> i) & 1 for i in range(8)]  # LSB first
    parity = sum(data) % 2  # parité paire
    bits = [1, 1, 0] + data + [parity, 1, 1, 1]
    labels = ["idle", "idle", "START"] + [f"D{i}" for i in range(8)] + ["P", "STOP", "idle", "idle"]
    fig, ax = plt.subplots(figsize=(11, 3.2))
    steps(ax, list(range(len(bits) + 1)), bits)
    for i, (b, l) in enumerate(zip(bits, labels)):
        c = RED if l == "START" else GREEN if l == "STOP" else ORANGE if l == "P" else "black"
        ax.text(i + 0.5, 1.0, l, ha="center", fontsize=8, color=c)
        ax.text(i + 0.5, -0.35, str(b), ha="center", fontsize=9, fontweight="bold")
        ax.axvline(i, color="#ddd", lw=0.8, zorder=0)
        if 3 <= i <= 12:
            ax.plot(i + 0.5, b * 0.8, "v", color=RED, ms=5)
    ax.set_ylim(-0.6, 1.3); ax.set_yticks([0, 0.8]); ax.set_yticklabels(["0 (space)", "1 (mark)"])
    ax.set_xticks([])
    ax.set_title("UART 8E1 : envoi de 'A' = 0x41, LSB en premier, parité paire  (▼ = échantillonnage au milieu du bit)", fontsize=10, fontweight="bold")
    save(fig, "uart_trame.png")


def fig_uart_oversampling():
    fig, ax = plt.subplots(figsize=(10, 3))
    # front descendant du START puis échantillonnage x16
    t = [0, 2, 18, 20]
    steps(ax, t, [1, 0, 1], h=1)
    for k in range(16):
        x = 2 + k
        ax.plot([x, x], [-0.25, -0.1], color=GREY)
        ax.text(x + 0.5, -0.45, str(k + 1), ha="center", fontsize=7)
    for k in (7, 8, 9):
        ax.plot(2 + k + 0.5, 0.0, "o", color=RED)
    ax.annotate("échantillons 8, 9, 10\n→ vote majoritaire", xy=(10.5, 0.05), xytext=(12.5, 0.55),
                arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("détection du front\n(début du START)", xy=(2, 0.5), xytext=(-1.5, 0.55), fontsize=9,
                arrowprops=dict(arrowstyle="->"))
    ax.set_xlim(-2, 21); ax.set_ylim(-0.7, 1.3); ax.axis("off")
    ax.set_title("Réception UART par sur-échantillonnage ×16 (bit START)", fontweight="bold")
    save(fig, "uart_surechantillonnage.png")


# ---------------------------------------------------------------- 5. SPI
def fig_spi_modes():
    data = [1, 0, 1, 0, 0, 1, 0, 1]  # 0xA5 MSB first
    fig, axs = plt.subplots(2, 2, figsize=(13, 6.5))
    for cpol in (0, 1):
        for cpha in (0, 1):
            ax = axs[cpol][cpha]
            # CS
            steps(ax, [-1, 0, 17, 18], [1, 0, 1], y0=4, color=GREY)
            # SCLK : 8 cycles de période 2 démarrant à t=1
            tt, ll = [-1], [cpol]
            for i in range(8):
                tt += [1 + 2 * i, 2 + 2 * i]
                ll += [1 - cpol, cpol]
            tt.append(18)
            steps(ax, tt, ll, y0=2, color=BLUE)
            # MOSI
            if cpha == 0:
                tm = [-1, 0] + [2 + 2 * i for i in range(8)] + [18]
                lm = [1] + data + [1]
                samples = [1 + 2 * i for i in range(8)]
            else:
                tm = [-1, 1] + [3 + 2 * i for i in range(7)] + [17, 18]
                lm = [1] + data + [1]
                samples = [2 + 2 * i for i in range(8)]
            steps(ax, tm, lm, y0=0, color=GREEN)
            for s in samples:
                ax.axvline(s, color=RED, ls="--", lw=0.8)
            for i, b in enumerate(data):
                ax.text(samples[i], -0.45, str(b), ha="center", fontsize=8, color=RED)
            ax.set_yticks([0.4, 2.4, 4.4]); ax.set_yticklabels(["MOSI", "SCLK", "CS"])
            ax.set_xticks([]); ax.set_ylim(-0.8, 5.2)
            mode = cpol * 2 + cpha
            edge = ("montant" if (cpol ^ cpha) == 0 else "descendant")
            ax.set_title(f"Mode {mode} : CPOL={cpol}, CPHA={cpha} — échantillonnage front {edge}", fontsize=10, fontweight="bold")
    fig.suptitle("SPI : les 4 modes (octet 0xA5, MSB en premier ; pointillés rouges = instants d'échantillonnage)", fontweight="bold")
    fig.tight_layout()
    save(fig, "spi_modes.png")


# ---------------------------------------------------------------- 6. I2C
def fig_i2c():
    addr = 0x50
    bits = [(addr >> (6 - i)) & 1 for i in range(7)] + [0]  # + W
    ack = 0
    fig, ax = plt.subplots(figsize=(13, 3.8))
    # SCL
    ts, ls = [0, 1.5], [1, 0]
    for k in range(9):
        ts += [2.5 + 2 * k, 3.5 + 2 * k]
        ls += [1, 0]
    ts += [20.5, 23]; ls += [1]
    steps(ax, ts, ls, y0=2, color=BLUE)
    # SDA (maître)
    td, ld = [0, 1], [1, 0]
    for k, b in enumerate(bits):
        td.append(1.75 + 2 * k); ld.append(b)
    steps(ax, td + [17.75], ld, y0=0, color=GREEN)  # le maître relâche SDA à 17.75 pour l'ACK
    # ACK esclave
    steps(ax, [17.75, 19.75], [ack], y0=0, color=RED, lw=3)
    steps(ax, [19.75, 21, 23], [0, 1], y0=0, color=GREEN)
    labels = ["A6", "A5", "A4", "A3", "A2", "A1", "A0", "R/W̄"]
    for k, l in enumerate(labels):
        ax.text(3 + 2 * k, 1.05, f"{l}\n={bits[k]}", ha="center", fontsize=8)
    ax.text(19, 1.05, "ACK\n(esclave)", ha="center", fontsize=8, color=RED)
    ax.annotate("START\nSDA↓ pendant SCL=1", xy=(1, 0.4), xytext=(-2.5, 1.3), fontsize=8, arrowprops=dict(arrowstyle="->"))
    ax.annotate("STOP\nSDA↑ pendant SCL=1", xy=(21, 0.4), xytext=(21.5, 1.3), fontsize=8, arrowprops=dict(arrowstyle="->"))
    ax.set_yticks([0.4, 2.4]); ax.set_yticklabels(["SDA", "SCL"]); ax.set_xticks([])
    ax.set_xlim(-3, 24); ax.set_ylim(-0.4, 3.2)
    ax.set_title("I²C : adressage de l'esclave 0x50 en écriture (octet d'adresse = 0xA0), ACK en rouge", fontweight="bold")
    save(fig, "i2c_transaction.png")


def fig_i2c_topologie():
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot([0, 10], [3, 3], color=RED, lw=2); ax.text(-0.3, 3, "VDD", ha="right", va="center")
    ax.plot([0, 10], [2, 2], color=GREEN, lw=2); ax.text(-0.3, 2, "SDA", ha="right", va="center")
    ax.plot([0, 10], [1.4, 1.4], color=BLUE, lw=2); ax.text(-0.3, 1.4, "SCL", ha="right", va="center")
    for x, y in ((0.8, 2), (1.6, 1.4)):
        ax.plot([x, x], [3, y], color="black")
        ax.add_patch(Rectangle((x - 0.12, y + 0.2), 0.24, 0.45, facecolor="white", edgecolor="black"))
        ax.plot(x, y, "o", color="black", ms=4)
    ax.text(1.2, 2.75, "Rp (pull-up)", fontsize=8, ha="center")
    nodes = [("Maître\n(MCU)", 3), ("Capteur\n0x68", 5.2), ("EEPROM\n0x50", 7.2), ("RTC\n0x68 ?!", 9.2)]
    for name, x in nodes:
        ax.add_patch(Rectangle((x - 0.7, -0.6), 1.4, 1.0, facecolor="#eaf2f8", edgecolor="black"))
        ax.text(x, -0.1, name, ha="center", va="center", fontsize=8)
        ax.plot([x - 0.2, x - 0.2], [0.4, 2], color=GREEN); ax.plot(x - 0.2, 2, "o", color=GREEN, ms=4)
        ax.plot([x + 0.2, x + 0.2], [0.4, 1.4], color=BLUE); ax.plot(x + 0.2, 1.4, "o", color=BLUE, ms=4)
    ax.text(9.2, -1.0, "conflit d'adresse → à éviter", ha="center", fontsize=8, color=RED)
    ax.set_xlim(-1, 10.5); ax.set_ylim(-1.3, 3.5); ax.axis("off")
    ax.set_title("I²C : bus à collecteur/drain ouvert, résistances de tirage, adresses 7 bits", fontweight="bold")
    save(fig, "i2c_topologie.png")


# ---------------------------------------------------------------- 7. 1-Wire
def fig_onewire():
    fig, axs = plt.subplots(2, 2, figsize=(12, 5.5))
    # Reset/presence
    ax = axs[0][0]
    steps(ax, [0, 1, 9, 10.5, 13, 18], [1, 0, 1, 0, 1], color=BLUE)
    steps(ax, [10.5, 13], [0], color=RED, lw=3)
    ax.text(5, -0.35, "maître : bas ≥ 480 µs", ha="center", fontsize=8)
    ax.text(11.7, -0.35, "présence\n60–240 µs", ha="center", fontsize=8, color=RED)
    ax.text(9.7, 0.95, "15–60 µs", ha="center", fontsize=7)
    ax.set_title("Reset + Presence pulse", fontsize=10, fontweight="bold")
    # Write 1
    ax = axs[0][1]
    steps(ax, [0, 1, 2, 9, 10], [1, 0, 1, 1], color=BLUE)
    ax.text(1.5, -0.35, "1–15 µs", ha="center", fontsize=8)
    ax.text(5.5, -0.35, "slot total ≥ 60 µs", ha="center", fontsize=8)
    ax.set_title("Écriture d'un '1'", fontsize=10, fontweight="bold")
    # Write 0
    ax = axs[1][0]
    steps(ax, [0, 1, 8, 9, 10], [1, 0, 1, 1], color=BLUE)
    ax.text(4.5, -0.35, "bas 60–120 µs", ha="center", fontsize=8)
    ax.set_title("Écriture d'un '0'", fontsize=10, fontweight="bold")
    # Read
    ax = axs[1][1]
    steps(ax, [0, 1, 1.5, 9, 10], [1, 0, 1, 1], color=BLUE)
    steps(ax, [1.5, 4.5], [0], color=RED, lw=3)
    ax.axvline(2.8, color=GREEN, ls="--"); ax.text(2.8, 1.0, "échantillon\n≤ 15 µs", ha="center", fontsize=8, color=GREEN)
    ax.text(3.0, -0.35, "l'esclave maintient bas si bit = 0", ha="center", fontsize=8, color=RED)
    ax.set_title("Lecture (read slot)", fontsize=10, fontweight="bold")
    for row in axs:
        for ax in row:
            ax.set_ylim(-0.6, 1.3); ax.set_yticks([]); ax.set_xticks([])
    fig.suptitle("1-Wire : créneaux temporels (mode standard, échelle indicative) — bleu = maître, rouge = esclave", fontweight="bold")
    fig.tight_layout()
    save(fig, "onewire_slots.png")


# ---------------------------------------------------------------- 8. CAN
def fig_can_trame():
    fig, axs = plt.subplots(2, 1, figsize=(13, 5.5), gridspec_kw={"height_ratios": [1, 1.3]})
    fields = [("SOF\n1", 1.5, "#f5b7b1"), ("Identifiant\n11 bits", 11, "#aed6f1"), ("RTR\n1", 1.5, "#d7bde2"),
              ("IDE\n1", 1.5, "#d7bde2"), ("r0\n1", 1.5, "#d7bde2"), ("DLC\n4", 4, "#f9e79f"),
              ("Données\n0–8 octets", 16, "#abebc6"), ("CRC\n15", 8, "#f5cba7"), ("Dél.\n1", 1.5, "#eee"),
              ("ACK\n1", 1.5, "#f1948a"), ("Dél.\n1", 1.5, "#eee"), ("EOF\n7", 5, "#ccd1d1"), ("IFS\n3", 3, "#e5e8e8")]
    field_bar(axs[0], fields, title="Trame de données CAN 2.0A (identifiant standard) — champ d'arbitrage = ID + RTR")
    # Niveaux physiques
    ax = axs[1]
    bits = [1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 1]
    n = len(bits)
    t = list(range(n + 1))
    canh = [2.5 if b else 3.5 for b in bits]
    canl = [2.5 if b else 1.5 for b in bits]
    for arr, c, name in ((canh, RED, "CAN_H"), (canl, BLUE, "CAN_L")):
        xs, ys = [], []
        for i, v in enumerate(arr):
            xs += [t[i], t[i + 1]]; ys += [v, v]
        ax.plot(xs, ys, color=c, lw=2, label=name)
    for i, b in enumerate(bits):
        ax.text(i + 0.5, 4.0, "R" if b else "D", ha="center", fontsize=9, fontweight="bold", color=GREY if b else "black")
        ax.axvline(i, color="#eee", zorder=0)
    ax.set_ylim(1, 4.4); ax.set_ylabel("Tension (V)"); ax.set_xticks([])
    ax.legend(loc="lower right")
    ax.set_title("Couche physique ISO 11898-2 : récessif (R, '1') Vdiff ≈ 0 V ; dominant (D, '0') Vdiff ≈ 2 V", fontsize=10, fontweight="bold")
    fig.tight_layout()
    save(fig, "can_trame_et_niveaux.png")


def fig_can_arbitrage():
    ids = {"Nœud A (0x135)": 0x135, "Nœud B (0x127)": 0x127, "Nœud C (0x140)": 0x140}
    fig, ax = plt.subplots(figsize=(12, 4.5))
    names = list(ids)
    seqs = {k: [(v >> (10 - i)) & 1 for i in range(11)] for k, v in ids.items()}
    alive = {k: True for k in names}
    lost_at = {}
    bus = []
    for i in range(11):
        vals = [seqs[k][i] for k in names if alive[k]]
        b = min(vals)
        bus.append(b)
        for k in names:
            if alive[k] and seqs[k][i] == 1 and b == 0:
                alive[k] = False; lost_at[k] = i
    rows = names + ["BUS (ET câblé)"]
    for r, k in enumerate(rows):
        y = (len(rows) - 1 - r) * 1.3
        seq = bus if k.startswith("BUS") else seqs[k]
        end = lost_at[k] + 1 if k in lost_at else 11
        steps(ax, list(range(end + 1)), seq[:end], y0=y, color=BLUE if not k.startswith("BUS") else "black")
        if k in lost_at:
            steps(ax, [end - 1, end], [1], y0=y, color=RED, lw=3)
            ax.text(end + 0.2, y + 0.3, f"envoie '1' mais lit '0' au bit {end - 1} → perd, passe en réception", fontsize=8, color=RED)
        ax.text(-0.3, y + 0.4, k, ha="right", va="center", fontsize=9)
        for i in range(min(end, 11)):
            ax.text(i + 0.5, y + 0.85, str(seq[i]), ha="center", fontsize=7)
    ax.set_xlim(-4, 15); ax.axis("off")
    ax.set_title("Arbitrage CAN bit à bit (CSMA/CR) : le dominant '0' écrase le récessif '1' → l'ID le plus faible gagne", fontweight="bold")
    save(fig, "can_arbitrage.png")


# ---------------------------------------------------------------- 9. LIN
def fig_lin():
    fig, axs = plt.subplots(2, 1, figsize=(13, 4.5))
    fields = [("Break\n≥13 bits dom.", 7, "#f5b7b1"), ("Dél.\n≥1", 1.5, "#eee"), ("Sync\n0x55", 5, "#aed6f1"),
              ("PID\nID6 + 2 parités", 5, "#d7bde2"), ("Données\n1–8 octets", 14, "#abebc6"), ("Checksum\n1 octet", 5, "#f5cba7")]
    x = field_bar(axs[0], fields, title="Trame LIN : en-tête (maître/commander) + réponse (esclave/responder)")
    axs[0].annotate("", xy=(0, -0.4), xytext=(18.5, -0.4), arrowprops=dict(arrowstyle="<->"))
    axs[0].text(9.2, -0.55, "Header (maître)", ha="center", va="top", fontsize=8)
    axs[0].annotate("", xy=(18.5, -0.4), xytext=(37.5, -0.4), arrowprops=dict(arrowstyle="<->"))
    axs[0].text(28, -0.55, "Response (maître ou esclave)", ha="center", va="top", fontsize=8)
    bits = [0] + [1, 0, 1, 0, 1, 0, 1, 0] + [1]
    steps(axs[1], list(range(len(bits) + 1)), bits)
    lbl = ["START"] + [f"D{i}" for i in range(8)] + ["STOP"]
    for i, l in enumerate(lbl):
        axs[1].text(i + 0.5, 1.0, l, ha="center", fontsize=8)
    axs[1].set_ylim(-0.3, 1.3); axs[1].axis("off")
    axs[1].set_title("Champ Sync 0x55 (LSB first) : fronts réguliers → l'esclave mesure le débit et recale son oscillateur", fontsize=10, fontweight="bold")
    fig.tight_layout()
    save(fig, "lin_trame.png")


# ---------------------------------------------------------------- 10. FlexRay
def fig_flexray():
    fig, ax = plt.subplots(figsize=(13, 3))
    fields = []
    for i in range(1, 7):
        fields.append((f"Slot\n{i}", 3, "#aed6f1"))
    for i in range(10):
        fields.append(("", 1, "#abebc6"))
    fields += [("Symbol\nwindow", 3, "#f9e79f"), ("NIT", 3, "#d5d8dc")]
    field_bar(ax, fields)
    ax.text(9, 1.5, "Segment STATIQUE (TDMA)\nslots de taille fixe, déterministe", ha="center", fontsize=9, color=BLUE, fontweight="bold")
    ax.text(23, 1.5, "Segment DYNAMIQUE (FTDMA)\nmini-slots, événementiel", ha="center", fontsize=9, color=GREEN, fontweight="bold")
    ax.set_ylim(-0.5, 2.3)
    ax.set_title("Cycle de communication FlexRay (répété 64 fois, cycles 0–63 ; typiquement 1–5 ms)", fontweight="bold", loc="left")
    save(fig, "flexray_cycle.png")


# ---------------------------------------------------------------- 11. RS-485
def fig_rs485():
    fig, axs = plt.subplots(2, 1, figsize=(12, 6), gridspec_kw={"height_ratios": [1.2, 1]})
    ax = axs[0]
    bits = [1, 0, 1, 1, 0, 1, 0, 0, 1]
    n = len(bits)
    noise = 0.25 * np.sin(np.linspace(0, 12, 400))
    t = np.linspace(0, n, 400)
    lv = np.array([bits[min(int(x), n - 1)] for x in t])
    A = 2.5 + 1.0 * (lv * 2 - 1) / 1 * 0.8 + noise
    B = 2.5 - 1.0 * (lv * 2 - 1) / 1 * 0.8 + noise
    ax.plot(t, A, color=RED, label="A (non-inverseur)")
    ax.plot(t, B, color=BLUE, label="B (inverseur)")
    ax.plot(t, A - B, color="black", lw=2, label="A − B (ce que lit le récepteur)")
    ax.axhline(0.2, color=GREEN, ls="--", lw=0.8); ax.axhline(-0.2, color=GREEN, ls="--", lw=0.8)
    ax.text(n + 0.1, 0.2, "+200 mV", fontsize=8, color=GREEN); ax.text(n + 0.1, -0.35, "−200 mV", fontsize=8, color=GREEN)
    ax.legend(fontsize=8, loc="upper right"); ax.set_ylabel("V"); ax.set_xticks([])
    ax.set_title("Transmission différentielle : le bruit de mode commun s'annule dans A − B", fontweight="bold")
    ax = axs[1]
    ax.plot([0, 10], [1.2, 1.2], color=RED, lw=2); ax.plot([0, 10], [0.8, 0.8], color=BLUE, lw=2)
    for x in (0.2, 9.8):
        ax.add_patch(Rectangle((x - 0.1, 0.83), 0.2, 0.34, facecolor="#f9e79f", edgecolor="black"))
        ax.text(x, 1.45, "120 Ω", ha="center", fontsize=8)
    for i, x in enumerate((1.5, 4, 6.5, 8.8)):
        ax.plot([x, x], [1.2, 0.2], color=RED, lw=1); ax.plot([x + 0.2, x + 0.2], [0.8, 0.2], color=BLUE, lw=1)
        ax.add_patch(Rectangle((x - 0.5, -0.5), 1.2, 0.7, facecolor="#eaf2f8", edgecolor="black"))
        ax.text(x + 0.1, -0.15, "Maître" if i == 0 else f"Esclave {i}", ha="center", fontsize=8)
    ax.text(5, 1.7, "Paire torsadée en bus (daisy-chain), terminaison aux DEUX extrémités, stubs courts", ha="center", fontsize=9)
    ax.set_xlim(-0.5, 10.5); ax.set_ylim(-0.7, 2); ax.axis("off")
    fig.tight_layout()
    save(fig, "rs485_differentiel_topologie.png")


# ---------------------------------------------------------------- 12. Modbus
def fig_modbus():
    fig, axs = plt.subplots(2, 1, figsize=(12, 3.8))
    field_bar(axs[0], [("Silence\n≥3,5 car.", 3, "#eee"), ("Adresse\n1 o", 3, "#aed6f1"), ("Code fonction\n1 o", 4, "#d7bde2"),
                       ("Données\n0–252 o", 10, "#abebc6"), ("CRC-16\n2 o (LSB 1er)", 4, "#f5cba7"), ("Silence\n≥3,5 car.", 3, "#eee")],
              title="Modbus RTU (série, RS-485/RS-232) — ADU max 256 octets")
    field_bar(axs[1], [("Transaction ID\n2 o", 4, "#f9e79f"), ("Protocol ID\n2 o (=0)", 4, "#f9e79f"), ("Length\n2 o", 3, "#f9e79f"),
                       ("Unit ID\n1 o", 3, "#aed6f1"), ("Code fonction\n1 o", 4, "#d7bde2"), ("Données\n0–252 o", 9, "#abebc6")],
              title="Modbus TCP (port 502) — en-tête MBAP (jaune) + PDU ; pas de CRC (TCP s'en charge)")
    fig.tight_layout()
    save(fig, "modbus_rtu_vs_tcp.png")


# ---------------------------------------------------------------- 13. EtherCAT
def fig_ethercat():
    fig, ax = plt.subplots(figsize=(12, 3.5))
    ax.add_patch(Rectangle((0, 0.5), 1.6, 1.2, facecolor="#f5b7b1", edgecolor="black"))
    ax.text(0.8, 1.1, "Maître\n(NIC Ethernet\nstandard)", ha="center", va="center", fontsize=8)
    xs = [3, 5.2, 7.4, 9.6]
    for i, x in enumerate(xs):
        ax.add_patch(Rectangle((x, 0.5), 1.5, 1.2, facecolor="#aed6f1", edgecolor="black"))
        ax.text(x + 0.75, 1.1, f"Esclave {i+1}\n(ESC)", ha="center", va="center", fontsize=8)
    for i in range(len(xs)):
        x0 = 1.6 if i == 0 else xs[i - 1] + 1.5
        ax.annotate("", xy=(xs[i], 1.45), xytext=(x0, 1.45), arrowprops=dict(arrowstyle="->", color=GREEN))
        ax.annotate("", xy=(x0, 0.75), xytext=(xs[i], 0.75), arrowprops=dict(arrowstyle="->", color=ORANGE))
    ax.annotate("", xy=(xs[-1] + 1.5, 0.75), xytext=(xs[-1] + 1.5, 1.45), arrowprops=dict(arrowstyle="->", color=GREY,
                connectionstyle="arc3,rad=-1.2"))
    ax.text(5.5, 2.2, "La trame traverse chaque esclave « à la volée » : chacun lit/écrit SA zone pendant le passage (délai ~ ns/100 ns)",
            ha="center", fontsize=9)
    ax.text(5.5, 0.1, "Retour par la paire RX (full-duplex) — le dernier esclave referme la boucle", ha="center", fontsize=8, color=ORANGE)
    ax.set_xlim(-0.3, 12); ax.set_ylim(-0.2, 2.5); ax.axis("off")
    ax.set_title("EtherCAT : traitement à la volée (processing on the fly)", fontweight="bold")
    save(fig, "ethercat_on_the_fly.png")


# ---------------------------------------------------------------- 14. USB
def fig_usb():
    fig, axs = plt.subplots(3, 1, figsize=(12, 4.5))
    field_bar(axs[0], [("SYNC\n8", 3, "#eee"), ("PID\n8", 3, "#d7bde2"), ("ADDR\n7", 3, "#aed6f1"), ("ENDP\n4", 2.5, "#aed6f1"),
                       ("CRC5", 2.5, "#f5cba7"), ("EOP", 2, "#ccd1d1")], title="Paquet TOKEN (IN / OUT / SETUP)")
    field_bar(axs[1], [("SYNC", 3, "#eee"), ("PID\nDATA0/1", 3, "#d7bde2"), ("Données\n0–1023 o", 12, "#abebc6"),
                       ("CRC16", 3, "#f5cba7"), ("EOP", 2, "#ccd1d1")], title="Paquet DATA")
    field_bar(axs[2], [("SYNC", 3, "#eee"), ("PID\nACK/NAK/STALL", 5, "#d7bde2"), ("EOP", 2, "#ccd1d1")], title="Paquet HANDSHAKE")
    fig.suptitle("USB 2.0 : une transaction = Token → Data → Handshake (l'hôte initie TOUT)", fontweight="bold")
    fig.tight_layout()
    save(fig, "usb_transaction.png")


# ---------------------------------------------------------------- 15. 2,4 GHz
def fig_24ghz():
    fig, ax = plt.subplots(figsize=(13, 4.5))
    for ch, f in ((1, 2412), (6, 2437), (11, 2462)):
        ax.add_patch(Rectangle((f - 10, 2), 20, 0.8, facecolor=PURPLE, alpha=0.3, edgecolor=PURPLE))
        ax.text(f, 2.4, f"Wi-Fi ch {ch}", ha="center", fontsize=8)
    for k in range(40):
        f = 2402 + 2 * k
        adv = f in (2402, 2426, 2480)
        ax.add_patch(Rectangle((f - 0.9, 1), 1.8, 0.7, facecolor=RED if adv else BLUE, alpha=0.8 if adv else 0.35))
    ax.text(2441, 0.8, "BLE : 40 canaux de 2 MHz — rouges = advertising 37 (2402), 38 (2426), 39 (2480) placés entre les canaux Wi-Fi 1/6/11",
            ha="center", va="top", fontsize=8)
    for c in range(11, 27):
        f = 2405 + 5 * (c - 11)
        ax.add_patch(Rectangle((f - 1, 0), 2, 0.5, facecolor=GREEN, alpha=0.6))
        ax.text(f, -0.2, str(c), ha="center", va="top", fontsize=7)
    ax.text(2441, -0.55, "IEEE 802.15.4 / Zigbee / Thread : canaux 11–26 (espacement 5 MHz)", ha="center", va="top", fontsize=8)
    ax.set_xlim(2398, 2486); ax.set_ylim(-0.9, 3.1); ax.set_yticks([])
    ax.set_xlabel("Fréquence (MHz) — bande ISM 2400–2483,5 MHz")
    ax.set_title("Coexistence dans la bande 2,4 GHz : Wi-Fi, BLE, 802.15.4", fontweight="bold")
    save(fig, "24ghz_coexistence.png")


# ---------------------------------------------------------------- 16. LoRa chirps
def fig_lora():
    SF, BW, fs = 7, 125e3, 500e3
    M = 2 ** SF
    Ts = M / BW
    ns = int(Ts * fs)
    tt = np.arange(ns) / fs

    def chirp(sym=0, down=False):
        f = (sym * BW / M + BW * tt / Ts) % BW - BW / 2
        if down:
            f = -f
        return f

    freqs = []
    for _ in range(8):
        freqs.append(chirp(0))
    for _ in range(2):
        freqs.append(chirp(0, down=True))
    for s in (32, 100, 5, 77):
        freqs.append(chirp(s))
    f = np.concatenate(freqs)
    phase = 2 * np.pi * np.cumsum(f) / fs
    sig = np.exp(1j * phase)
    fig, ax = plt.subplots(figsize=(13, 4))
    Pxx, fr, tb, im = ax.specgram(sig, NFFT=128, Fs=fs, noverlap=120, sides="twosided", cmap="magma")
    im.set_clim(np.percentile(10*np.log10(Pxx+1e-12), 60), np.max(10*np.log10(Pxx+1e-12)))
    ax.set_ylim(-BW / 2 * 1.2, BW / 2 * 1.2)
    ax.set_xlabel("Temps (s)"); ax.set_ylabel("Fréquence bande de base (Hz)")
    ax.set_title("LoRa (CSS) simulé, SF7 / BW 125 kHz : 8 up-chirps de préambule, 2 down-chirps (sync), puis symboles 32, 100, 5, 77\n"
                 "→ l'information est codée par le décalage cyclique de départ en fréquence", fontsize=10, fontweight="bold")
    save(fig, "lora_chirps_spectrogramme.png")


# ---------------------------------------------------------------- 17. PCIe couches / Automotive archi (schéma blocs)
def fig_archi_vehicule():
    fig, ax = plt.subplots(figsize=(12, 5))

    def box(x, y, w, h, t, c):
        ax.add_patch(Rectangle((x, y), w, h, facecolor=c, edgecolor="black"))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=8)

    box(4.5, 3.8, 3, 0.9, "Passerelle centrale (Gateway)\n+ HPC / domaine", "#f5b7b1")
    box(0, 1.8, 2.6, 0.9, "Domaine moteur\nCAN FD 2–5 Mbit/s", "#aed6f1")
    box(3, 1.8, 2.6, 0.9, "Châssis / freinage\nFlexRay 10 Mbit/s", "#d7bde2")
    box(6.2, 1.8, 2.6, 0.9, "ADAS / caméras\nEthernet 100M–10G", "#abebc6")
    box(9.4, 1.8, 2.6, 0.9, "Habitacle (body)\nCAN 125–500 kbit/s", "#f9e79f")
    box(9.4, 0, 2.6, 0.9, "Lève-vitres, rétros, sièges\nLIN 19,2 kbit/s", "#fdebd0")
    box(0, 3.8, 3, 0.9, "Prise OBD-II\n(CAN diag.)", "#e5e8e8")
    box(9, 3.8, 3, 0.9, "Télématique (TCU)\n4G/5G, Wi-Fi, BT", "#e5e8e8")
    for x in (1.3, 4.3, 7.5, 10.7):
        ax.annotate("", xy=(6, 3.8), xytext=(x, 2.7), arrowprops=dict(arrowstyle="-", lw=1.2))
    ax.annotate("", xy=(10.7, 1.8), xytext=(10.7, 0.9), arrowprops=dict(arrowstyle="-", lw=1.2))
    ax.annotate("", xy=(4.5, 4.25), xytext=(3, 4.25), arrowprops=dict(arrowstyle="-", lw=1.2, color=RED))
    ax.annotate("", xy=(9, 4.25), xytext=(7.5, 4.25), arrowprops=dict(arrowstyle="-", lw=1.2, color=RED))
    ax.text(6, 5.0, "Surfaces d'attaque externes en rouge : OBD-II et télématique → la gateway doit filtrer", ha="center", fontsize=9, color=RED)
    ax.set_xlim(-0.3, 12.3); ax.set_ylim(-0.3, 5.3); ax.axis("off")
    ax.set_title("Architecture réseau d'un véhicule moderne (simplifiée)", fontweight="bold")
    save(fig, "vehicule_architecture.png")


if __name__ == "__main__":
    for f in [fig_codages, fig_filaire_debit_distance, fig_sansfil, fig_uart, fig_uart_oversampling, fig_spi_modes,
              fig_i2c, fig_i2c_topologie, fig_onewire, fig_can_trame, fig_can_arbitrage, fig_lin, fig_flexray, fig_rs485,
              fig_modbus, fig_ethercat, fig_usb, fig_24ghz, fig_lora, fig_archi_vehicule]:
        f()
