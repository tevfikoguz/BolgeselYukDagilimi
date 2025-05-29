import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

# -----------------------------------------------------------------------------
# VERİ TANIMLAMA SINIFLARI
# -----------------------------------------------------------------------------
class RegionalLoad:
    """Bölgesel bir yükü temsil eder."""
    def __init__(self, name: str, intensity: float, width: float, length: float, color: str = "blue"):
        self.name = name
        self.intensity = intensity  # kN/m^2
        self.width = width          # m (kirişlere dik boyut)
        self.length = length        # m (kirişlere paralel boyut)
        self.color = color

class Beam:
    """Bir kirişi temsil eder."""
    def __init__(self, name: str, position_y: float, length: float):
        self.name = name
        self.position_y = position_y # Kirişin y-eksenindeki konumu (referans noktası)
        self.length = length         # m
        self.distributed_load_contributions = {} # Hangi yükten ne kadar aldığını saklar
        self.total_distributed_load = 0.0

# -----------------------------------------------------------------------------
# HESAPLAMA SINIFI
# -----------------------------------------------------------------------------
class LoadDistributionCalculator:
    """Bölgesel yüklerin kirişlere dağılımını hesaplar."""

    def __init__(self, loads: list[RegionalLoad], beams: list[Beam]):
        """
        Args:
            loads: RegionalLoad nesnelerinin bir listesi.
                   Şu anki implementasyon tam olarak iki yük varsayar (load[0] ve load[1])
                   ve bu yüklerin bitişik olduğunu varsayar.
            beams: Beam nesnelerinin bir listesi.
                   Şu anki implementasyon tam olarak iki kiriş varsayar (beams[0] ve beams[1])
                   ve bu kirişlerin yük alanının dış kenarlarında olduğunu varsayar.
        """
        if len(loads) != 2 or len(beams) != 2:
            raise ValueError("Bu hesaplayıcı şu anda tam olarak 2 yük ve 2 kiriş için tasarlanmıştır.")
        self.loads = loads
        self.beams = beams
        self.calculation_details = {} # Hesaplama adımları için

    def calculate(self):
        """Kirişlere gelen yayılı yükleri hesaplar."""
        load1 = self.loads[0]
        load2 = self.loads[1] # load1'den sonra geldiği varsayılır
        beam1 = self.beams[0] # Yük alanının başlangıcında
        beam2 = self.beams[1] # Yük alanının sonunda

        # Kirişlerin y pozisyonlarını yük genişliklerine göre ayarla (güvenlik için)
        beam1.position_y = 0 # Referans
        beam2.position_y = load1.width + load2.width

        total_width_of_loads = load1.width + load2.width
        tributary_width_per_beam = total_width_of_loads / 2

        self.calculation_details = {
            "total_width_of_loads": total_width_of_loads,
            "tributary_width_per_beam": tributary_width_per_beam,
            f"{beam1.name}_takes_from_{load1.name}": 0.0,
            f"{beam1.name}_takes_from_{load2.name}": 0.0,
            f"{beam2.name}_takes_from_{load1.name}": 0.0,
            f"{beam2.name}_takes_from_{load2.name}": 0.0,
        }

        # --- beam1 (P_L0_S0) için hesaplama ---
        beam1.distributed_load_contributions.clear()
        beam1.total_distributed_load = 0

        # load1'den beam1'e gelen yük
        width_from_load1_for_beam1 = min(load1.width, tributary_width_per_beam)
        q_on_beam1_from_load1 = load1.intensity * width_from_load1_for_beam1
        beam1.distributed_load_contributions[load1.name] = q_on_beam1_from_load1
        beam1.total_distributed_load += q_on_beam1_from_load1
        self.calculation_details[f"{beam1.name}_takes_from_{load1.name}"] = width_from_load1_for_beam1

        # beam1'in etki alanında load1'den sonra kalan kısım
        remaining_trib_width_for_beam1 = tributary_width_per_beam - width_from_load1_for_beam1
        if remaining_trib_width_for_beam1 > 0:
            width_from_load2_for_beam1 = min(load2.width, remaining_trib_width_for_beam1)
            q_on_beam1_from_load2 = load2.intensity * width_from_load2_for_beam1
            beam1.distributed_load_contributions[load2.name] = q_on_beam1_from_load2
            beam1.total_distributed_load += q_on_beam1_from_load2
            self.calculation_details[f"{beam1.name}_takes_from_{load2.name}"] = width_from_load2_for_beam1
        else:
            beam1.distributed_load_contributions[load2.name] = 0.0


        # --- beam2 (P_L1_S0) için hesaplama ---
        beam2.distributed_load_contributions.clear()
        beam2.total_distributed_load = 0

        # load2'den beam2'ye gelen yük
        width_from_load2_for_beam2 = min(load2.width, tributary_width_per_beam)
        q_on_beam2_from_load2 = load2.intensity * width_from_load2_for_beam2
        beam2.distributed_load_contributions[load2.name] = q_on_beam2_from_load2
        beam2.total_distributed_load += q_on_beam2_from_load2
        self.calculation_details[f"{beam2.name}_takes_from_{load2.name}"] = width_from_load2_for_beam2

        # beam2'nin etki alanında load2'den sonra kalan kısım
        remaining_trib_width_for_beam2 = tributary_width_per_beam - width_from_load2_for_beam2
        if remaining_trib_width_for_beam2 > 0:
            width_from_load1_for_beam2 = min(load1.width, remaining_trib_width_for_beam2)
            q_on_beam2_from_load1 = load1.intensity * width_from_load1_for_beam2
            beam2.distributed_load_contributions[load1.name] = q_on_beam2_from_load1
            beam2.total_distributed_load += q_on_beam2_from_load1
            self.calculation_details[f"{beam2.name}_takes_from_{load1.name}"] = width_from_load1_for_beam2
        else:
            beam2.distributed_load_contributions[load1.name] = 0.0

# -----------------------------------------------------------------------------
# RAPORLAMA SINIFI
# -----------------------------------------------------------------------------
class ReportGenerator:
    """Hesaplama sonuçlarını raporlar."""

    @staticmethod
    def print_console_report(beams: list[Beam], loads: list[RegionalLoad]):
        print("\n--- HESAPLAMA SONUÇLARI ---")
        for beam in beams:
            print(f"\nKiriş: {beam.name}")
            for load_name, contribution in beam.distributed_load_contributions.items():
                print(f"  {load_name}'den gelen: {contribution:.3f} kN/m")
            print(f"  Toplam yayılı yük: {beam.total_distributed_load:.3f} kN/m")
        print("--------------------------")

# -----------------------------------------------------------------------------
# GÖRSELLEŞTİRME SINIFI
# -----------------------------------------------------------------------------
class Visualizer:
    """Hesaplama sonuçlarını ve yük düzenini görselleştirir."""

    def __init__(self, loads: list[RegionalLoad], beams: list[Beam], calculation_details: dict):
        self.loads = loads
        self.beams = beams
        self.calculation_details = calculation_details

    def plot(self):
        fig, ax = plt.subplots(figsize=(12, 7)) # Boyutu biraz artırdım

        # Yükleri çiz
        load1 = self.loads[0]
        load2 = self.loads[1]
        beam1 = self.beams[0]
        beam2 = self.beams[1]

        rect_load1 = patches.Rectangle(
            (0, beam1.position_y), load1.length, load1.width,
            linewidth=1, edgecolor='black', facecolor=load1.color, alpha=0.6,
            label=f"{load1.name}: {load1.intensity} kN/m²"
        )
        ax.add_patch(rect_load1)
        ax.text(load1.length / 2, beam1.position_y + load1.width / 2,
                f"{load1.name}\n({load1.width:.1f}m)",
                ha='center', va='center', color='white', fontweight='bold')

        rect_load2 = patches.Rectangle(
            (0, beam1.position_y + load1.width), load2.length, load2.width,
            linewidth=1, edgecolor='black', facecolor=load2.color, alpha=0.6,
            label=f"{load2.name}: {load2.intensity} kN/m²"
        )
        ax.add_patch(rect_load2)
        ax.text(load2.length / 2, beam1.position_y + load1.width + load2.width / 2,
                f"{load2.name}\n({load2.width:.1f}m)",
                ha='center', va='center', color='white', fontweight='bold')

        # Kirişleri çiz
        beam_thickness = self.calculation_details["total_width_of_loads"] * 0.05
        ax.add_patch(patches.Rectangle((0, beam1.position_y - beam_thickness), beam1.length, beam_thickness,
                                       facecolor='gray', edgecolor='black', label=beam1.name))
        ax.add_patch(patches.Rectangle((0, beam2.position_y), beam2.length, beam_thickness,
                                       facecolor='gray', edgecolor='black', label=beam2.name))

        # Yük paylaşım sınırını çiz
        load_division_y = beam1.position_y + self.calculation_details["tributary_width_per_beam"]
        ax.axhline(load_division_y, color='blue', linestyle='--', linewidth=2, label='Yük Paylaşım Sınırı')

        # Etki alanlarını göstermek için oklar
        # Beam 1 etki alanı
        ax.annotate("", xy=(beam1.length * 1.02, beam1.position_y), xytext=(beam1.length * 1.02, load_division_y),
                    arrowprops=dict(arrowstyle="<->", color="darkblue", lw=1.5))
        ax.text(beam1.length * 1.04, beam1.position_y + (load_division_y - beam1.position_y) / 2,
                f"{beam1.name} Etki Alanı\n({self.calculation_details['tributary_width_per_beam']:.2f}m)",
                va='center', ha='left', color="darkblue", fontsize=8, rotation=90)

        # Beam 2 etki alanı
        ax.annotate("", xy=(beam1.length * 1.02, load_division_y), xytext=(beam1.length * 1.02, beam2.position_y),
                    arrowprops=dict(arrowstyle="<->", color="purple", lw=1.5))
        ax.text(beam1.length * 1.04, load_division_y + (beam2.position_y - load_division_y) / 2,
                f"{beam2.name} Etki Alanı\n({self.calculation_details['tributary_width_per_beam']:.2f}m)",
                va='center', ha='left', color="purple", fontsize=8, rotation=90)


        # Eksenleri ve başlığı ayarla
        ax.set_xlabel("Kiriş Boyunca Uzunluk (m)")
        ax.set_ylabel("Kirişlere Dik Genişlik (m)")
        ax.set_title("Bölgesel Yüklerin Kirişlere Dağılımı (Nesne Tabanlı)")
        ax.legend(loc='upper right', bbox_to_anchor=(1.30, 1)) # Efsane konumu
        ax.axis('equal')
        ax.set_xlim(-0.5, beam1.length * 1.35)
        ax.set_ylim(beam1.position_y - beam_thickness * 3, beam2.position_y + beam_thickness * 3)
        plt.grid(True, linestyle=':', alpha=0.7)

        # Hesaplanan yükleri grafiğe ekle
        y_offset_beam1_text = beam1.position_y - beam_thickness * 1.5
        y_offset_beam2_text = beam2.position_y + beam_thickness * 1.5

        for i, beam_obj in enumerate(self.beams):
            text_content = f"{beam_obj.name}:\n"
            for load_name_key, contrib in beam_obj.distributed_load_contributions.items():
                text_content += f"  {load_name_key}: {contrib:.3f} kN/m\n"
            text_content += f"  Toplam: {beam_obj.total_distributed_load:.3f} kN/m"

            y_pos = y_offset_beam1_text if i == 0 else y_offset_beam2_text
            va_align = 'top' if i == 0 else 'bottom'

            ax.text(0.1, y_pos, text_content,
                    va=va_align, ha='left', fontsize=9,
                    bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", alpha=0.8))

        plt.tight_layout(rect=[0, 0, 0.80, 1]) # Efsanenin sığması için sağda boşluk bırak
        plt.show()

# -----------------------------------------------------------------------------
# ANA ÇALIŞMA AKIŞI
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # 1. Veri Girişi: Nesneleri Oluştur
    load_F_obj = RegionalLoad(name="F_0_L", intensity=-0.72, width=0.2, length=2.5, color="red")
    load_G_obj = RegionalLoad(name="G_0_L", intensity=-0.72, width=0.8, length=2.5, color="green")

    # Kirişlerin başlangıç pozisyonları hesaplayıcı içinde ayarlanacak.
    # Burada sadece isim ve uzunluk önemli.
    beam_PL0S0 = Beam(name="P_L0_S0", position_y=0, length=2.5) # position_y geçici
    beam_PL1S0 = Beam(name="P_L1_S0", position_y=0, length=2.5) # position_y geçici

    # 2. Hesaplama
    calculator = LoadDistributionCalculator(loads=[load_F_obj, load_G_obj], beams=[beam_PL0S0, beam_PL1S0])
    calculator.calculate()

    # 3. Raporlama
    ReportGenerator.print_console_report(calculator.beams, calculator.loads)

    # 4. Görselleştirme
    visualizer = Visualizer(calculator.loads, calculator.beams, calculator.calculation_details)
    visualizer.plot()
