import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Set

# -----------------------------------------------------------------------------
# VERİ TANIMLAMA SINIFLARI (Aynı kalır)
# -----------------------------------------------------------------------------
@dataclass
class RegionalLoad:
    name: str
    intensity: float
    y_start: float
    y_end: float
    length: float
    color: str = "blue"

    @property
    def width(self) -> float:
        return abs(self.y_end - self.y_start)

@dataclass
class SegmentContribution:
    load_name: str
    segment_y_start: float
    segment_y_end: float
    effective_width: float
    load_value: float

@dataclass
class Beam:
    name: str
    position_y: float
    length: float
    detailed_contributions: List[SegmentContribution] = field(default_factory=list)
    total_distributed_load: float = 0.0
    debug_trib_y_start: float = 0.0
    debug_trib_y_end: float = 0.0

    def get_total_contribution_from_load(self, load_name: str) -> float:
        total = 0.0
        for contrib in self.detailed_contributions:
            if contrib.load_name == load_name:
                total += contrib.load_value
        return total

    def get_total_effective_width_from_load(self, load_name: str) -> float:
        total_width = 0.0
        for contrib in self.detailed_contributions:
            if contrib.load_name == load_name:
                total_width += contrib.effective_width
        return total_width

# -----------------------------------------------------------------------------
# HESAPLAMA SINIFI (Düzeltilmiş _assign_segments_to_beams ile)
# -----------------------------------------------------------------------------
class GeneralLoadDistributionCalculator:
    def __init__(self, loads: List[RegionalLoad], beams: List[Beam]):
        self.loads = sorted(loads, key=lambda ld: ld.y_start)
        self.beams = sorted(beams, key=lambda bm: bm.position_y)
        self.critical_y_coords: List[float] = []
        self.segments: List[Dict] = []
        self.all_supports_y: List[float] = [] # Kirişler VE yük alanı genel sınırları

    def _prepare_supports_and_critical_coords(self):
        coords: Set[float] = set()
        supports_set: Set[float] = set()

        for load in self.loads:
            coords.add(load.y_start)
            coords.add(load.y_end)
        for beam in self.beams:
            coords.add(beam.position_y)
            supports_set.add(beam.position_y)

        if self.loads:
            min_load_y = min(ld.y_start for ld in self.loads)
            max_load_y = max(ld.y_end for ld in self.loads)
            coords.add(min_load_y)
            coords.add(max_load_y)
            supports_set.add(min_load_y)
            supports_set.add(max_load_y)
        elif self.beams:
            min_beam_y = min(b.position_y for b in self.beams)
            max_beam_y = max(b.position_y for b in self.beams)
            coords.add(min_beam_y)
            coords.add(max_beam_y)
            supports_set.add(min_beam_y)
            supports_set.add(max_beam_y)

        self.critical_y_coords = sorted(list(set(coords)))
        self.all_supports_y = sorted(list(supports_set))


    def _create_segments(self):
        self.segments = []
        if len(self.critical_y_coords) < 2:
            return
        for i in range(len(self.critical_y_coords) - 1):
            y1 = self.critical_y_coords[i]
            y2 = self.critical_y_coords[i+1]
            if abs(y1 - y2) < 1e-9: continue
            segment_mid_y = (y1 + y2) / 2
            segment_width = y2 - y1
            current_segment_load = None
            for load in self.loads:
                if (load.y_start <= y1 + 1e-9 and load.y_end >= y2 - 1e-9):
                    current_segment_load = load
                    break
            if current_segment_load:
                 self.segments.append({
                    "y_start": y1, "y_end": y2, "mid_y": segment_mid_y,
                    "width": segment_width, "load_name": current_segment_load.name,
                    "load_intensity": current_segment_load.intensity
                })

    def _assign_segments_to_beams(self):
        for beam in self.beams:
            beam.detailed_contributions.clear()
            beam.total_distributed_load = 0.0

        if not self.beams or not self.segments:
            return

        # Sistemdeki en alt ve en üst yük alanı sınırlarını al
        min_system_boundary = self.all_supports_y[0] if self.all_supports_y else -float('inf')
        max_system_boundary = self.all_supports_y[-1] if self.all_supports_y else float('inf')

        for i, current_beam in enumerate(self.beams):
            # --- Alt (veya sol) etki sınırı (trib_y_start) ---
            prev_beam = self.beams[i-1] if i > 0 else None
            
            if prev_beam: # Ortada veya sonda bir kiriş (alt sınırı için)
                trib_y_start = (prev_beam.position_y + current_beam.position_y) / 2
            else: # Bu sistemdeki ilk kiriş
                # Eğer ilk kiriş ile sistemin en alt sınırı arasında başka kiriş yoksa,
                # bu aradaki yükün tamamı bu kirişe gelir.
                # Dolayısıyla etki alanı sistemin en alt sınırından başlar.
                trib_y_start = min_system_boundary
            
            # --- Üst (veya sağ) etki sınırı (trib_y_end) ---
            next_beam = self.beams[i+1] if i < len(self.beams) - 1 else None

            if next_beam: # Ortada veya başta bir kiriş (üst sınırı için)
                trib_y_end = (current_beam.position_y + next_beam.position_y) / 2
            else: # Bu sistemdeki son kiriş
                # Eğer son kiriş ile sistemin en üst sınırı arasında başka kiriş yoksa,
                # bu aradaki yükün tamamı bu kirişe gelir.
                # Dolayısıyla etki alanı sistemin en üst sınırında biter.
                trib_y_end = max_system_boundary

            current_beam.debug_trib_y_start = trib_y_start
            current_beam.debug_trib_y_end = trib_y_end
            
            current_beam_total_load = 0.0
            for segment in self.segments:
                overlap_start = max(segment["y_start"], trib_y_start)
                overlap_end = min(segment["y_end"], trib_y_end)

                if overlap_end > overlap_start + 1e-9:
                    effective_width_from_segment = overlap_end - overlap_start
                    load_value = segment["load_intensity"] * effective_width_from_segment
                    
                    contribution = SegmentContribution(
                        load_name=segment["load_name"],
                        segment_y_start=overlap_start,
                        segment_y_end=overlap_end,
                        effective_width=effective_width_from_segment,
                        load_value=load_value
                    )
                    current_beam.detailed_contributions.append(contribution)
                    current_beam_total_load += load_value
            current_beam.total_distributed_load = current_beam_total_load

    def calculate(self):
        self._prepare_supports_and_critical_coords()
        self._create_segments()
        self._assign_segments_to_beams()

# -----------------------------------------------------------------------------
# RAPORLAMA SINIFI (Aynı kalır)
# -----------------------------------------------------------------------------
class ReportGenerator:
    @staticmethod
    def print_detailed_report(beams: List[Beam], loads: List[RegionalLoad], calculator_all_supports_y: List[float]):
        print("\n--- DETAYLI HESAPLAMA SONUÇLARI (Düzeltilmiş Mantıkla) ---")
        for beam in beams:
            print(f"\n{beam.name} kirişine aktarılan yayılı yük (Pozisyon: {beam.position_y:.2f}m):")
            print(f"  Etki Alanı (Hesaplanan): {beam.debug_trib_y_start:.3f}m - {beam.debug_trib_y_end:.3f}m")
            
            if not beam.detailed_contributions:
                print("  Bu kirişe yük aktarılmadı.")
            else:
                sorted_contributions = sorted(beam.detailed_contributions, key=lambda c: (c.load_name, c.segment_y_start))
                for contrib in sorted_contributions:
                    print(f"  {contrib.load_name} ({contrib.segment_y_start:.2f}m - {contrib.segment_y_end:.2f}m arasından): "
                          f"{contrib.load_value:.3f} kN/m (Etki Genişliği: {contrib.effective_width:.3f}m)")
            print(f"  **Toplam: {beam.total_distributed_load:.3f} kN/m**")

        print("\n--- TOPLAM YÜK KONTROLÜ ---")
        total_load_intensity_times_width_system = 0
        for load in loads:
            print(f"\n{load.name} (Genişlik: {load.width:.2f}m [{load.y_start:.2f}-{load.y_end:.2f}], Yoğunluk: {load.intensity:.2f} kN/m²):")
            total_load_intensity_times_width_system += load.intensity * load.width
            
            width_on_beams_for_this_load = 0
            load_contrib_to_beams_details = []
            for beam in beams:
                beam_width_from_this_load = beam.get_total_effective_width_from_load(load.name)
                width_on_beams_for_this_load += beam_width_from_this_load
                if beam_width_from_this_load > 1e-9:
                    load_contrib_to_beams_details.append(f"{beam.name}'e {beam_width_from_this_load:.3f}m")
            
            if load_contrib_to_beams_details:
                print(f"  Bu yükten kirişlere dağıtılan toplam etki genişliği: {width_on_beams_for_this_load:.3f}m ({', '.join(load_contrib_to_beams_details)})")
            else:
                print(f"  Bu yükten kirişlere etki genişliği dağıtılmadı.")
            
            if abs(load.width - width_on_beams_for_this_load) > 1e-6:
                 print(f"  UYARI: {load.name} yükünün kendi genişliği ({load.width:.3f}m) ile kirişlere dağıtılan toplam etki genişliği ({width_on_beams_for_this_load:.3f}m) arasında fark var. "
                       f"Kalan {load.width - width_on_beams_for_this_load:.3f}m sistem sınırlarına gitmiş olabilir (bu yeni mantıkla bu olmamalı).")
            else:
                 print(f"  {load.name} yükünün tamamı kirişlere dağıtılmış görünüyor.")

        print("\nSistemdeki Toplam Yük (Σ Yük Yoğunluğu_i * Genişlik_i) (Referans):")
        print(f"  Değer: {total_load_intensity_times_width_system:.3f} kN/m")
        total_load_on_all_beams = sum(b.total_distributed_load for b in beams)
        print(f"Tüm Kirişler Üzerindeki Toplam Yayılı Yük (Hesaplanan): {total_load_on_all_beams:.3f} kN/m")

        if abs(total_load_intensity_times_width_system - total_load_on_all_beams) < 1e-6:
            print("Doğrulama BAŞARILI: Sistemdeki toplam yük, kirişlere dağıtılan toplam yüke yaklaşık olarak eşittir.")
        else:
            print(f"Doğrulama BAŞARISIZ: Fark = {abs(total_load_intensity_times_width_system - total_load_on_all_beams):.6f} kN/m.")
        print("-----------------------------------------")

# -----------------------------------------------------------------------------
# GÖRSELLEŞTİRME SINIFI (Aynı kalır)
# -----------------------------------------------------------------------------
class Visualizer:
    def __init__(self, loads: List[RegionalLoad], beams: List[Beam]):
        self.loads = loads
        self.beams = beams

    def plot(self, title_suffix=""):
        # Figür boyutunu bilgi kutuları için sağda yer bırakacak şekilde ayarla
        fig, ax = plt.subplots(figsize=(15, 10)) # Genişliği artırabiliriz
        max_beam_length = 0
        all_y_coords_for_plot_range = []
        if self.loads:
            all_y_coords_for_plot_range.extend([ld.y_start for ld in self.loads])
            all_y_coords_for_plot_range.extend([ld.y_end for ld in self.loads])
            max_beam_length = max(ld.length for ld in self.loads) if self.loads else 2.5
        if self.beams:
            all_y_coords_for_plot_range.extend([b.position_y for b in self.beams])
            if not self.loads and self.beams:
                 max_beam_length = max(b.length for b in self.beams) if self.beams else 2.5
        
        if not all_y_coords_for_plot_range:
            min_plot_y, max_plot_y = -1.0, 1.0
            max_beam_length = 2.5
        else:
            min_plot_y = min(all_y_coords_for_plot_range)
            max_plot_y = max(all_y_coords_for_plot_range)

        # Yükleri Çiz
        for load in self.loads:
            ax.add_patch(patches.Rectangle(
                (0, load.y_start), load.length, load.width,
                linewidth=1, edgecolor='black', facecolor=load.color, alpha=0.6,
                label=f"{load.name}: {load.intensity} kN/m² ({load.y_start:.2f}-{load.y_end:.2f}m)"
            ))
            ax.text(load.length / 2, load.y_start + load.width / 2,
                    f"{load.name}\n({load.width:.2f}m)",
                    ha='center', va='center', color='white', fontweight='bold', fontsize=8,
                    bbox=dict(boxstyle="round,pad=0.2", fc=load.color, alpha=0.5))

        # Kirişleri ve Etki Alanlarını Çiz
        beam_render_thickness = (max_plot_y - min_plot_y) * 0.015 if (max_plot_y - min_plot_y) > 1e-6 else 0.03
        trib_colors = plt.cm.get_cmap('tab10').colors 

        for i, beam in enumerate(self.beams):
            ax.add_patch(patches.Rectangle((0, beam.position_y - beam_render_thickness / 2), beam.length, beam_render_thickness,
                                           facecolor='dimgray', edgecolor='black', lw=1.5,
                                           label=f"{beam.name} (y={beam.position_y:.2f}m)"))
            # Kiriş adını artık bilgi kutusunda göstereceğimiz için buradan kaldırabiliriz veya daha küçük yapabiliriz.
            # ax.text(beam.length * 1.02, beam.position_y, beam.name, va='center', ha='left', color='black', fontsize=8)

            trib_color_selected = trib_colors[i % len(trib_colors)]
            if abs(beam.debug_trib_y_end - beam.debug_trib_y_start) > 1e-9:
                indicator_width = max_beam_length * 0.06
                indicator_x_pos = -max_beam_length * 0.08
                ax.add_patch(patches.Rectangle(
                    (indicator_x_pos, beam.debug_trib_y_start), indicator_width,
                    beam.debug_trib_y_end - beam.debug_trib_y_start,
                    facecolor=trib_color_selected, alpha=0.4, edgecolor=trib_color_selected, lw=1
                ))
                ax.text(indicator_x_pos - indicator_width * 0.2 , (beam.debug_trib_y_start + beam.debug_trib_y_end)/2,
                        f"{beam.name}\nEtki Alanı\n({beam.debug_trib_y_start:.2f} - {beam.debug_trib_y_end:.2f})",
                        rotation=90, va='center', ha='right', fontsize=7, color=trib_color_selected)

        # Eksenleri ve Başlığı Ayarla
        ax.set_xlabel("Kiriş Boyunca Uzunluk (m) [Bu eksen sadece görsel referanstır]")
        ax.set_ylabel("Global Y-Koordinatı (m) [Yük Dağılım Yönü]")
        ax.set_title(f"Bölgesel Yüklerin Kirişlere Dağılımı{title_suffix}", fontsize=14, pad=20)
        
        plot_x_padding = max_beam_length * 0.30
        ax.set_xlim(-plot_x_padding, max_beam_length + plot_x_padding * 0.1) # Sağdaki metin için x limitte yer bırakma
        
        plot_y_padding = (max_plot_y - min_plot_y) * 0.20 if (max_plot_y - min_plot_y) > 1e-6 else 0.6
        ax.set_ylim(min_plot_y - plot_y_padding, max_plot_y + plot_y_padding)
        plt.grid(True, linestyle=':', alpha=0.7)

        # Bilgi Kutularını Grafiğin Sağına Yerleştir
        info_text_x_start = max_beam_length + plot_x_padding * 0.15 # Grafiğin sağından başla
        current_info_y = max_plot_y + plot_y_padding * 0.9 # En üstten başla
        line_height_factor_for_right = 0.030 # Sağdaki metin için satır yüksekliği

        # Efsaneyi bilgi kutularının üstüne veya altına yerleştirebiliriz. Şimdilik üstte.
        ax.legend(loc='upper left', bbox_to_anchor=(info_text_x_start / (max_beam_length + plot_x_padding * 1.3) , 1.0), 
                  fontsize=8, framealpha=0.9) # bbox_to_anchor figür koordinatları (0-1 aralığında)
                                            # veya axes koordinatları olabilir. Burada axes'e göre ayarlamaya çalışalım.
                                            # Daha basit: fig.legend veya ax.legend(loc='...') ile daha standart yerleşim
        
        # Efsaneyi manuel olarak ayarlamak yerine, `plt.tight_layout()` veya `fig.subplots_adjust` sonrası `ax.legend()` daha iyi olabilir.
        # Şimdilik mevcut efsane yerleşimini kaldırıp, bilgi kutularının altına alabiliriz.
        # VEYA efsaneyi grafiğin içine, daha az yer kaplayan bir yere koyabiliriz.
        # 'best' loc ile deneyelim:
        handles, labels = ax.get_legend_handles_labels()
        if handles: # Sadece efsane öğesi varsa göster
             ax.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, -0.10), 
                       fancybox=True, shadow=True, ncol=min(3, len(handles)), fontsize=8)


        for i, beam_obj in enumerate(self.beams):
            report_text = f"**{beam_obj.name} (y={beam_obj.position_y:.2f}m):**\n"
            report_text += f"  Etki Alanı: [{beam_obj.debug_trib_y_start:.3f}m - {beam_obj.debug_trib_y_end:.3f}m]\n"
            sorted_contributions = sorted(beam_obj.detailed_contributions, key=lambda c: (c.load_name, c.segment_y_start))
            for contrib in sorted_contributions:
                report_text += (f"  {contrib.load_name} ({contrib.segment_y_start:.2f}m - {contrib.segment_y_end:.2f}m): "
                                f"{contrib.load_value:.3f} kN/m (G: {contrib.effective_width:.3f}m)\n")
            report_text += f"  **Toplam: {beam_obj.total_distributed_load:.3f} kN/m**\n\n"
            
            text_obj = ax.text(info_text_x_start, current_info_y, report_text,
                    verticalalignment='top', horizontalalignment='left', fontsize=7.5, family='monospace',
                    transform=ax.transData, # Veri koordinatlarını kullan
                    bbox=dict(boxstyle="round,pad=0.5", fc=trib_colors[i % len(trib_colors)], alpha=0.25))
            
            num_lines = report_text.count('\n') +1
            # Yüksekliği bbox'tan almak daha doğru olurdu ama şimdilik satır sayısıyla tahmin.
            text_box_height_approx = num_lines * line_height_factor_for_right * (max_plot_y - min_plot_y + 2*plot_y_padding)
            current_info_y -= text_box_height_approx # Bir sonraki metin için y pozisyonu
            if i < len(self.beams) -1 :
                current_info_y -= 0.015 * (max_plot_y - min_plot_y + 2*plot_y_padding) # Kutular arası boşluk


        # Grafiğin sağında bilgi kutuları için yer bırak
        plt.subplots_adjust(left=0.15, right=0.70, top=0.90, bottom=0.15) # Sağ tarafı daralt
        plt.show()

# -----------------------------------------------------------------------------
# ANA ÇALIŞMA AKIŞI (Test Senaryoları)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # --- ÖRNEK 1 ---
    print("--- ÖRNEK 1 ---")
    load_F_ex1 = RegionalLoad(name="F_0_L_ex1", intensity=-0.72, y_start=0.0, y_end=0.2, length=2.5, color="salmon")
    load_G_ex1 = RegionalLoad(name="G_0_L_ex1", intensity=-0.72, y_start=0.2, y_end=1.0, length=2.5, color="lightgreen")
    beam_P0_ex1 = Beam(name="P_L0_S0_ex1", position_y=0.0, length=2.5)
    beam_P1_ex1 = Beam(name="P_L1_S0_ex1", position_y=1.0, length=2.5)
    calculator_ex1 = GeneralLoadDistributionCalculator(loads=[load_F_ex1, load_G_ex1], beams=[beam_P0_ex1, beam_P1_ex1])
    calculator_ex1.calculate()
    ReportGenerator.print_detailed_report(calculator_ex1.beams, calculator_ex1.loads, calculator_ex1.all_supports_y)
    visualizer_ex1 = Visualizer(calculator_ex1.loads, calculator_ex1.beams)
    visualizer_ex1.plot(title_suffix=" (Örnek 1: Kirişler Dışarıda)")

    # --- ÖRNEK 2 ---
    # Beklenen Sonuçlar Örnek 2 (Sizin belirttiğiniz mantığa göre):
    # P_L0_S0_ex2 (0.8m):
    #   Etki Alanı Alt: Sistem sınırı (0.0m) ile P0 (0.8m) arası -> [0.0m - 0.8m] P0'a.
    #   Etki Alanı Üst: P0 (0.8m) ile P1 (1.8m) arası orta nokta -> (0.8+1.8)/2 = 1.3m.  -> [0.8m - 1.3m] P0'a.
    #   P0 Etki Alanı: [0.0m - 1.3m]
    #   F_0_L (0.0m - 1.0m) kesişimi: [0.0m - 1.0m] -> Genişlik 1.0m * -0.72 = -0.72 kN/m
    #   G_0_L (1.0m - 2.0m) kesişimi: [1.0m - 1.3m] -> Genişlik 0.3m * -0.72 = -0.216 kN/m
    #   P_L0_S0_ex2 Toplam: -0.72 + (-0.216) = -0.936 kN/m
    # P_L1_S0_ex2 (1.8m):
    #   Etki Alanı Alt: P0 (0.8m) ile P1 (1.8m) arası orta nokta -> 1.3m. -> [1.3m - 1.8m] P1'e.
    #   Etki Alanı Üst: P1 (1.8m) ile Sistem sınırı (2.0m) arası -> [1.8m - 2.0m] P1'e.
    #   P1 Etki Alanı: [1.3m - 2.0m]
    #   G_0_L (1.0m - 2.0m) kesişimi: [1.3m - 2.0m] -> Genişlik 0.7m * -0.72 = -0.504 kN/m
    #   P_L1_S0_ex2 Toplam: -0.504 kN/m

    print("\n\n--- ÖRNEK 2 (Yeni Mantıkla) ---")
    load_F_ex2 = RegionalLoad(name="F_0_L_ex2", intensity=-0.72, y_start=0.0, y_end=1.0, length=2.5, color="tomato")
    load_G_ex2 = RegionalLoad(name="G_0_L_ex2", intensity=-0.72, y_start=1.0, y_end=2.0, length=2.5, color="mediumseagreen")
    beam_P0_ex2 = Beam(name="P_L0_S0_ex2", position_y=0.8, length=2.5)
    beam_P1_ex2 = Beam(name="P_L1_S0_ex2", position_y=1.8, length=2.5)
    calculator_ex2 = GeneralLoadDistributionCalculator(loads=[load_F_ex2, load_G_ex2], beams=[beam_P0_ex2, beam_P1_ex2])
    calculator_ex2.calculate()
    ReportGenerator.print_detailed_report(calculator_ex2.beams, calculator_ex2.loads, calculator_ex2.all_supports_y)
    visualizer_ex2 = Visualizer(calculator_ex2.loads, calculator_ex2.beams)
    visualizer_ex2.plot(title_suffix=" (Örnek 2: Kirişler İçeride - Yeni Mantık)")
