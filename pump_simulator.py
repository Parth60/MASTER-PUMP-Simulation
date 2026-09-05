import streamlit as st
import math

st.set_page_config(
    page_title="Pump Design & Selection Simulator",
    page_icon="⚙️",
    layout="wide"
)

st.title("Pump Design & Selection Simulator")
st.caption(
    "General-purpose hydraulic sizing, pump-type screening, impeller selection "
    "and power/energy-cost estimator. Enter your own units on each field."
)

g = 9.81  # m/s^2

# =========================================================
# UNIT CONVERSION HELPERS  (everything is converted to SI
# internally: m3/s, Pa, m, kg/m3, Pa.s, degC)
# =========================================================

FLOW_UNITS = {"m3/h": 1 / 3600, "L/s": 1 / 1000, "US GPM": 6.30902e-5, "m3/s": 1.0}
PRESSURE_UNITS = {"kPa": 1000.0, "bar": 100000.0, "psi": 6894.76, "Pa": 1.0}
LENGTH_UNITS = {"m": 1.0, "ft": 0.3048, "mm": 0.001, "in": 0.0254}
SMALL_LENGTH_UNITS = {"mm": 0.001, "in": 0.0254, "m": 1.0, "\u00b5m": 1e-6}
DENSITY_UNITS = {"kg/m3": 1.0, "lb/ft3": 16.01846, "g/cm3": 1000.0, "SG (vs water)": 1000.0}
VISCOSITY_UNITS = {"cP": 0.001, "mPa.s": 0.001, "Pa.s": 1.0}
POWER_UNITS = {"kW": 1000.0, "hp": 745.7, "W": 1.0}


def value_with_unit(label, default_value, unit_options, default_unit=None, key=None, step=None, min_value=None):
    """Renders a number input + a unit dropdown side by side, returns (value_in_SI, chosen_unit, raw_value)."""
    c1, c2 = st.sidebar.columns([2, 1])
    with c1:
        raw = st.number_input(
            label, value=float(default_value), step=step, min_value=min_value, key=f"{key}_val"
        )
    with c2:
        unit = st.selectbox(
            " ", list(unit_options.keys()),
            index=list(unit_options.keys()).index(default_unit) if default_unit else 0,
            key=f"{key}_unit", label_visibility="collapsed"
        )
    return raw * unit_options[unit], unit, raw


def to_celsius(value, unit):
    if unit == "\u00b0C":
        return value
    if unit == "\u00b0F":
        return (value - 32) * 5 / 9
    if unit == "K":
        return value - 273.15
    return value


def from_si_power(value_w, unit):
    return value_w / POWER_UNITS[unit]


def from_si_length(value_m, unit):
    return value_m / LENGTH_UNITS[unit]


# =========================================================
# SIDEBAR INPUTS
# =========================================================

st.sidebar.header("Fluid Properties")

flow_rate_si, flow_unit, flow_rate_raw = value_with_unit(
    "Flow rate", 120.0, FLOW_UNITS, "m3/h", key="flow", step=5.0, min_value=0.0001
)

density_si, density_unit, _ = value_with_unit(
    "Fluid density", 998.0, DENSITY_UNITS, "kg/m3", key="density", step=10.0, min_value=0.1
)

viscosity_si, viscosity_unit, viscosity_raw_cp = value_with_unit(
    "Dynamic viscosity", 1.0, VISCOSITY_UNITS, "cP", key="visc", step=0.1, min_value=0.001
)
# keep a cP-equivalent value handy for the pump/impeller logic regardless of chosen unit
viscosity_cp = viscosity_si / 0.001

temp_col1, temp_col2 = st.sidebar.columns([2, 1])
with temp_col1:
    temperature_raw = st.number_input("Temperature", value=25.0, step=5.0, key="temp_val")
with temp_col2:
    temperature_unit = st.selectbox(
        " ", ["\u00b0C", "\u00b0F", "K"], key="temp_unit", label_visibility="collapsed"
    )
temperature_c = to_celsius(temperature_raw, temperature_unit)

vapour_pressure_si, vp_unit, _ = value_with_unit(
    "Vapour pressure (abs)", 3.2, PRESSURE_UNITS, "kPa", key="vp", step=1.0, min_value=0.0
)

st.sidebar.header("System Pressures & Elevation")

suction_pressure_si, sp_unit, _ = value_with_unit(
    "Suction pressure (abs)", 101.3, PRESSURE_UNITS, "kPa", key="sp", step=5.0, min_value=0.1
)

discharge_pressure_si, dp_unit, _ = value_with_unit(
    "Discharge pressure (abs)", 500.0, PRESSURE_UNITS, "kPa", key="dp", step=10.0, min_value=0.1
)

elevation_si, elev_unit, _ = value_with_unit(
    "Elevation change (discharge - suction)", 5.0, LENGTH_UNITS, "m", key="elev", step=1.0
)

st.sidebar.header("Pipe & Fittings")

pipe_length_si, pl_unit, _ = value_with_unit(
    "Pipe length", 100.0, LENGTH_UNITS, "m", key="plen", step=10.0, min_value=0.1
)

pipe_diameter_si, pd_unit, _ = value_with_unit(
    "Pipe internal diameter", 150.0, SMALL_LENGTH_UNITS, "mm", key="pdia", step=10.0, min_value=0.001
)

roughness_si, rough_unit, _ = value_with_unit(
    "Pipe roughness", 0.045, SMALL_LENGTH_UNITS, "mm", key="rough", step=0.001, min_value=0.0
)

minor_loss_k = st.sidebar.number_input(
    "Total minor-loss coefficient, \u03a3K", min_value=0.0, value=5.0, step=1.0
)

st.sidebar.header("Mechanical & Process Condition")

pump_efficiency = st.sidebar.slider("Pump efficiency (%)", 30, 95, 80)
motor_efficiency = st.sidebar.slider("Motor efficiency (%)", 50, 99, 92)
solids_percent = st.sidebar.slider("Suspended solids (%)", 0, 50, 0)

fluid_condition = st.sidebar.selectbox(
    "Fluid condition",
    ["Clean liquid", "Mild solids", "Heavy slurry", "Shear-sensitive liquid", "Corrosive liquid"]
)

st.sidebar.header("Energy Cost (optional)")
electricity_cost = st.sidebar.number_input("Electricity cost ($/kWh)", min_value=0.0, value=0.20, step=0.01)
operating_hours = st.sidebar.slider("Operating hours per year", 0, 8760, 8000)

results_unit_system = st.sidebar.radio("Show results in:", ["Metric (kW, m)", "US (hp, ft)"])
power_display_unit = "kW" if results_unit_system.startswith("Metric") else "hp"
length_display_unit = "m" if results_unit_system.startswith("Metric") else "ft"

# =========================================================
# HYDRAULIC CALCULATIONS  (all internal maths in SI units)
# =========================================================

Q = flow_rate_si  # m3/s
area = math.pi * pipe_diameter_si ** 2 / 4
velocity = Q / area if area > 0 else 0

mu = viscosity_si  # Pa.s
reynolds = density_si * velocity * pipe_diameter_si / mu if mu > 0 else 0

if reynolds < 2300 and reynolds > 0:
    friction_factor = 64 / reynolds
    flow_regime = "Laminar"
elif reynolds >= 2300:
    relative_roughness = roughness_si / pipe_diameter_si
    friction_factor = 0.25 / (
        math.log10(relative_roughness / 3.7 + 5.74 / reynolds ** 0.9) ** 2
    )
    flow_regime = "Turbulent"
else:
    friction_factor = 0.0
    flow_regime = "Undefined"

friction_head = friction_factor * (pipe_length_si / pipe_diameter_si) * (velocity ** 2 / (2 * g))
minor_head = minor_loss_k * velocity ** 2 / (2 * g)
pressure_head = (discharge_pressure_si - suction_pressure_si) / (density_si * g)
total_dynamic_head = pressure_head + elevation_si + friction_head + minor_head

hydraulic_power = density_si * g * Q * total_dynamic_head
pump_eta = pump_efficiency / 100
motor_eta = motor_efficiency / 100
shaft_power = hydraulic_power / pump_eta if pump_eta > 0 else 0
electrical_power = shaft_power / motor_eta if motor_eta > 0 else 0

# Simplified NPSHa: assumes entered suction pressure already reflects source-vessel
# static head; velocity head at suction neglected. Preliminary screening only.
npsha = (suction_pressure_si - vapour_pressure_si) / (density_si * g)

annual_energy_cost = (electrical_power / 1000) * operating_hours * electricity_cost

# =========================================================
# PUMP TYPE SCORING
# =========================================================

scores = {
    "Centrifugal Pump": 50,
    "Multistage Centrifugal Pump": 40,
    "Screw Pump": 40,
    "Gear Pump": 35,
    "Progressive Cavity Pump": 35,
    "Diaphragm Pump": 30,
    "Slurry Pump": 30,
}

if viscosity_cp < 50:
    scores["Centrifugal Pump"] += 35
    scores["Multistage Centrifugal Pump"] += 25
elif viscosity_cp < 500:
    scores["Screw Pump"] += 35
    scores["Progressive Cavity Pump"] += 30
else:
    scores["Screw Pump"] += 40
    scores["Progressive Cavity Pump"] += 40
    scores["Gear Pump"] += 25

if total_dynamic_head > 100:
    scores["Multistage Centrifugal Pump"] += 35

if solids_percent > 5:
    scores["Slurry Pump"] += 40
    scores["Progressive Cavity Pump"] += 20
    scores["Centrifugal Pump"] -= 20

if fluid_condition == "Heavy slurry":
    scores["Slurry Pump"] += 40
elif fluid_condition == "Shear-sensitive liquid":
    scores["Progressive Cavity Pump"] += 35
    scores["Screw Pump"] += 20
elif fluid_condition == "Corrosive liquid":
    scores["Diaphragm Pump"] += 25

recommended_pump = max(scores, key=scores.get)

# =========================================================
# IMPELLER SELECTION
# Primary axes requested: viscosity and discharge pressure.
# Solids content is kept as a secondary override since it is
# physically decisive when present.
# =========================================================

discharge_pressure_kpa = discharge_pressure_si / 1000

if solids_percent > 20:
    impeller = "Vortex / recessed impeller (large solids clearance)"
    impeller_reason = "Solids loading above 20% makes a conventional bladed impeller impractical."
elif solids_percent > 5:
    impeller = "Open impeller"
    impeller_reason = "Moderate solids loading (5-20%) needs an unshrouded, self-clearing impeller."
elif viscosity_cp > 500:
    impeller = "Helical / screw-type rotor (positive-displacement duty)"
    impeller_reason = "Above ~500 cP, centrifugal impellers lose efficiency sharply; a positive-displacement rotor is preferred."
elif viscosity_cp > 50:
    impeller = "Semi-open impeller, oversized for viscosity"
    impeller_reason = "50-500 cP is a transition band: a semi-open impeller with wider clearances tolerates the added viscous drag."
elif discharge_pressure_kpa > 1000:
    impeller = "Closed radial impeller, multistage arrangement"
    impeller_reason = "Low viscosity but high discharge pressure calls for a multistage closed-impeller design to build head efficiently."
elif discharge_pressure_kpa > 300:
    impeller = "Closed radial impeller, single stage"
    impeller_reason = "Low viscosity, moderate discharge pressure suits a conventional closed radial impeller."
else:
    impeller = "Open or semi-open low-head impeller"
    impeller_reason = "Low viscosity and low discharge pressure: a simple low-head impeller is adequate and cheaper to maintain."

# =========================================================
# RESULTS DISPLAY
# =========================================================

left, right = st.columns(2)

with left:
    st.subheader("Hydraulic Summary")
    st.metric("Pipe velocity", f"{velocity:.2f} m/s")
    st.metric("Reynolds number", f"{reynolds:,.0f}")
    st.metric("Flow regime", flow_regime)
    st.metric("Friction factor", f"{friction_factor:.4f}")
    st.metric("Friction head loss", f"{from_si_length(friction_head, length_display_unit):.2f} {length_display_unit}")
    st.metric("Minor losses", f"{from_si_length(minor_head, length_display_unit):.2f} {length_display_unit}")
    st.metric("Static pressure head", f"{from_si_length(pressure_head, length_display_unit):.2f} {length_display_unit}")
    st.metric("Total Dynamic Head", f"{from_si_length(total_dynamic_head, length_display_unit):.2f} {length_display_unit}")

with right:
    st.subheader("Pump Performance")
    st.metric("Hydraulic power", f"{from_si_power(hydraulic_power, power_display_unit):.2f} {power_display_unit}")
    st.metric("Pump shaft power", f"{from_si_power(shaft_power, power_display_unit):.2f} {power_display_unit}")
    st.metric("Electrical power", f"{from_si_power(electrical_power, power_display_unit):.2f} {power_display_unit}")
    st.metric("Estimated NPSH Available", f"{from_si_length(npsha, length_display_unit):.2f} {length_display_unit}")
    st.metric("Estimated annual energy cost", f"${annual_energy_cost:,.0f} /year")

st.divider()
st.subheader("Equipment Recommendation")

col1, col2, col3 = st.columns(3)

with col1:
    st.success(f"**Recommended Pump**\n\n{recommended_pump}")

with col2:
    st.info(f"**Recommended Impeller**\n\n{impeller}")
    st.caption(impeller_reason)

with col3:
    if velocity < 0.5:
        velocity_status = "Flow velocity is quite low - check for settling risk with any solids present."
    elif velocity <= 3:
        velocity_status = "Pipe velocity is within a typical reasonable range."
    else:
        velocity_status = "High pipe velocity - consider increasing pipe diameter to reduce erosion/friction."
    st.warning(velocity_status)

st.subheader("Pump Suitability Comparison")
sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
for pump, score in sorted_scores:
    score_clamped = max(0, min(score, 100))
    st.write(f"**{pump} - {score_clamped}/100**")
    st.progress(score_clamped / 100)

st.divider()
st.subheader("Engineering Checks")

if npsha < 3:
    st.error("Low NPSH available. Cavitation may be a serious risk - re-check suction conditions.")
elif npsha < 5:
    st.warning("NPSH margin may be limited. Check manufacturer NPSHR data against this NPSHa.")
else:
    st.success("NPSH available appears reasonable for preliminary screening.")

if temperature_c > 150:
    st.warning("High-temperature service: mechanical seal, casing material, bearings and thermal expansion require additional review.")

if viscosity_cp > 500 and recommended_pump == "Centrifugal Pump":
    st.warning("Viscosity is high for a centrifugal pump recommendation - double-check the scoring against a positive-displacement alternative.")

st.caption(
    "Preliminary design tool only. Final pump and impeller selection must be checked against "
    "manufacturer pump curves, NPSHR, materials of construction, allowable operating region and "
    "applicable engineering standards. NPSHa here is a simplified estimate (suction pressure minus "
    "vapour pressure) and neglects suction-line velocity head - verify against the full system layout."
)
