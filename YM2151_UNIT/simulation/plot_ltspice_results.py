import ltspice
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import os

# Load LTspice raw file
script_dir = os.path.dirname(os.path.abspath(__file__))
raw_file = os.path.join(script_dir, 'level_shifter_cs.raw')
l = ltspice.Ltspice(raw_file)
l.parse()

# Get time and voltage data
time = l.getTime()
V_lv = l.getData('V(LV)')
V_hv = l.getData('V(HV)')
V_ctrl1 = l.getData('V(NCTRL1)')
V_ctrl2 = l.getData('V(NCTRL2)')

# Convert time to microseconds
t_us = time * 1e6

# Create plot
fig, ax = plt.subplots(figsize=(12, 6))

ax.plot(t_us, V_lv, 'b-', linewidth=1.5, label='LV (3.3V side)')
ax.plot(t_us, V_hv, 'r-', linewidth=1.5, label='HV (5V side)')

# Add shaded regions based on control signals
ax.axvspan(0, 2, alpha=0.08, color='blue')
ax.axvspan(4, 6, alpha=0.08, color='red')

# Add annotations
ax.annotate('3.3V -> 5V\nLV drives LOW', xy=(1.0, 0.4), fontsize=10,
            color='blue', ha='center', weight='bold')
ax.annotate('5V -> 3.3V\nHV drives LOW', xy=(5.0, 0.4), fontsize=10,
            color='red', ha='center', weight='bold')

ax.set_xlabel('Time (us)', fontsize=12)
ax.set_ylabel('Voltage (V)', fontsize=12)
ax.set_title('2N7002 Bidirectional Level Shifter Simulation (LTspice)', fontsize=14)
ax.grid(True, alpha=0.3)
ax.legend(loc='upper right')
ax.set_xlim(0, 10)
ax.set_ylim(-0.5, 5.5)

ax.axhline(y=3.3, color='b', linestyle='--', alpha=0.3)
ax.axhline(y=5.0, color='r', linestyle='--', alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(script_dir, 'level_shifter_ltspice.png'), dpi=150)
plt.close()

print("LTspice plot saved: level_shifter_ltspice.png")

# Measurements
print("\n=== LTspice Simulation Results ===")

idx_lv_drive = (time >= 0.5e-6) & (time <= 1.5e-6)
idx_hv_drive = (time >= 4.5e-6) & (time <= 5.5e-6)

print("\n3.3V -> 5V direction (0-2us):")
print(f"  LV minimum: {np.min(V_lv[idx_lv_drive]):.3f} V")
print(f"  HV minimum: {np.min(V_hv[idx_lv_drive]):.3f} V")

print("\n5V -> 3.3V direction (4-6us):")
print(f"  HV minimum: {np.min(V_hv[idx_hv_drive]):.3f} V")
print(f"  LV minimum: {np.min(V_lv[idx_hv_drive]):.3f} V")

# Propagation delays
def find_delay(time, sig_in, sig_out, vth_in, vth_out, t_start, t_end):
    t_in = time[(time >= t_start) & (time <= t_end) & (sig_in < vth_in)]
    t_out = time[(time >= t_start) & (time <= t_end) & (sig_out < vth_out)]
    if len(t_in) > 0 and len(t_out) > 0:
        return t_out[0] - t_in[0]
    return None

d1 = find_delay(time, V_lv, V_hv, 0.5*3.3, 0.5*5.0, 0, 2e-6)
d2 = find_delay(time, V_hv, V_lv, 0.5*5.0, 0.5*3.3, 4e-6, 6e-6)

if d1 is not None:
    print(f"\n3.3V->5V propagation delay: {d1*1e9:.1f} ns")
if d2 is not None:
    print(f"5V->3.3V propagation delay: {d2*1e9:.1f} ns")
