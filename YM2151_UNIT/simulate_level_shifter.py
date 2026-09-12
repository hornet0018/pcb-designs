import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

# Circuit parameters
V3V3 = 3.3
V5V = 5.0
R1 = 4700.0
R2 = 4700.0
C_lv = 10e-12
C_hv = 10e-12

# Simplified 2N7002 model
Vth = 1.6           # Threshold voltage
Ron_mos = 3.0       # Channel on-resistance at Vgs=3.3V
Roff_mos = 1e9      # Channel off-resistance

# Body diode model
Vf_diode = 0.7      # Forward voltage
Ron_diode = 1.0     # Diode on-resistance
Roff_diode = 1e9    # Diode off-resistance

# Driver switch resistance
Ron_drv = 10.0
Roff_drv = 1e9

def driver_state(t, side):
    """Return driver switch resistance based on time and side
    side: 'lv' for 3.3V side driver (0-2us)
          'hv' for 5V side driver (4-6us)
    """
    if side == 'lv' and 0 <= t <= 2e-6:
        return Ron_drv
    elif side == 'hv' and 4e-6 <= t <= 6e-6:
        return Ron_drv
    else:
        return Roff_drv

def circuit_deriv(t, state):
    """Compute dV/dt for LV and HV nodes"""
    V_lv, V_hv = state
    
    # Driver resistances
    R_drv_lv = driver_state(t, 'lv')
    R_drv_hv = driver_state(t, 'hv')
    
    # Currents into LV node from pull-ups and drivers
    I_pullup_lv = (V3V3 - V_lv) / R1
    I_drv_lv = (0.0 - V_lv) / R_drv_lv
    
    # Currents into HV node from pull-ups and drivers
    I_pullup_hv = (V5V - V_hv) / R2
    I_drv_hv = (0.0 - V_hv) / R_drv_hv
    
    # MOSFET channel (source=LV, drain=HV)
    Vgs = V3V3 - V_lv
    if Vgs > Vth:
        R_channel = Ron_mos
    else:
        R_channel = Roff_mos
    
    I_channel = (V_hv - V_lv) / R_channel
    
    # Body diode (anode=source=LV, cathode=drain=HV)
    # Conducts only when LV > HV + Vf (forward biased)
    Vd = V_lv - V_hv
    if Vd > Vf_diode:
        I_diode = (Vd - Vf_diode) / Ron_diode
    else:
        I_diode = Vd / Roff_diode  # small reverse leakage
    
    # Net current into each node (positive = into node)
    I_lv = I_pullup_lv + I_drv_lv - I_channel - I_diode
    I_hv = I_pullup_hv + I_drv_hv + I_channel + I_diode
    
    dV_lv = I_lv / C_lv
    dV_hv = I_hv / C_hv
    
    return [dV_lv, dV_hv]

# Split simulation into intervals to handle discontinuities
intervals = [
    (0, 2e-6),      # LV driver on
    (2e-6, 4e-6),   # both off
    (4e-6, 6e-6),   # HV driver on
    (6e-6, 10e-6),  # both off
]

all_t = []
all_V_lv = []
all_V_hv = []
state = [V3V3, V5V]

for t_start, t_end in intervals:
    t_eval = np.linspace(t_start, t_end, 2500)
    sol = solve_ivp(circuit_deriv, (t_start, t_end), state, t_eval=t_eval, 
                    method='Radau', max_step=1e-9, rtol=1e-6, atol=1e-9)
    
    all_t.append(sol.t)
    all_V_lv.append(sol.y[0])
    all_V_hv.append(sol.y[1])
    
    # Initial state for next interval
    state = [sol.y[0][-1], sol.y[1][-1]]

t = np.concatenate(all_t)
V_lv = np.concatenate(all_V_lv)
V_hv = np.concatenate(all_V_hv)

# Create plot
fig, ax = plt.subplots(figsize=(12, 6))

# Convert time to microseconds
t_us = t * 1e6

ax.plot(t_us, V_lv, 'b-', linewidth=2, label='LV (3.3V side)')
ax.plot(t_us, V_hv, 'r-', linewidth=2, label='HV (5V side)')

# Add shaded regions
ax.axvspan(0, 2, alpha=0.1, color='blue')
ax.axvspan(4, 6, alpha=0.1, color='red')

# Add annotations
ax.annotate('3.3V side drives LOW\n(ESP32 -> MCP23S17)', xy=(1, 0.3), fontsize=10, 
            color='blue', ha='center', weight='bold')
ax.annotate('5V side drives LOW\n(MCP23S17 -> ESP32)', xy=(5, 0.3), fontsize=10, 
            color='red', ha='center', weight='bold')

ax.set_xlabel('Time (us)', fontsize=12)
ax.set_ylabel('Voltage (V)', fontsize=12)
ax.set_title('2N7002 Bidirectional Level Shifter Simulation\n(CS signal: 3.3V <-> 5V)', fontsize=14)
ax.grid(True, alpha=0.3)
ax.legend(loc='upper right')
ax.set_xlim(0, 10)
ax.set_ylim(-0.5, 5.5)

# Add horizontal lines for logic levels
ax.axhline(y=3.3, color='b', linestyle='--', alpha=0.3)
ax.axhline(y=5.0, color='r', linestyle='--', alpha=0.3)
ax.axhline(y=0.0, color='k', linestyle='-', alpha=0.3)

plt.tight_layout()
plt.savefig('level_shifter_simulation.png', dpi=150)
plt.close()

print("Simulation complete. Saved level_shifter_simulation.png")

# Print some key measurements
print(f"\nLV initial: {V_lv[0]:.3f} V")
print(f"HV initial: {V_hv[0]:.3f} V")

# Find minimum voltages during each drive phase
lv_drive_idx = (t >= 0.5e-6) & (t <= 1.5e-6)
hv_drive_idx = (t >= 4.5e-6) & (t <= 5.5e-6)

print(f"\n3.3V->5V direction (0-2us):")
print(f"  LV min: {np.min(V_lv[lv_drive_idx]):.3f} V")
print(f"  HV min: {np.min(V_hv[lv_drive_idx]):.3f} V")

print(f"\n5V->3.3V direction (4-6us):")
print(f"  HV min: {np.min(V_hv[hv_drive_idx]):.3f} V")
print(f"  LV min: {np.min(V_lv[hv_drive_idx]):.3f} V")

# Calculate propagation delays
def find_crossing(time, signal, threshold, start_time, end_time):
    idx = np.where((time >= start_time) & (time <= end_time) & (signal < threshold))[0]
    if len(idx) > 0:
        return time[idx[0]]
    return None

t_lv_fall = find_crossing(t, V_lv, 0.5*V3V3, 0, 2e-6)
t_hv_fall = find_crossing(t, V_hv, 0.5*V5V, 0, 2e-6)
if t_lv_fall is not None and t_hv_fall is not None:
    print(f"\n3.3V->5V propagation delay: {(t_hv_fall - t_lv_fall)*1e9:.1f} ns")

t_hv_fall2 = find_crossing(t, V_hv, 0.5*V5V, 4e-6, 6e-6)
t_lv_fall2 = find_crossing(t, V_lv, 0.5*V3V3, 4e-6, 6e-6)
if t_hv_fall2 is not None and t_lv_fall2 is not None:
    print(f"5V->3.3V propagation delay: {(t_lv_fall2 - t_hv_fall2)*1e9:.1f} ns")
