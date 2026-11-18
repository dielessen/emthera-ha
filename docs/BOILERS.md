# Boilers

> **The firmware and the project's main repository are not public.** The firmware is not on GitHub;
> [emthera.nl/firmware](https://emthera.nl/firmware) says where it comes from. The Home Assistant
> integration is installed and updated through the Marketplace as described. A few references to pages that are
> not public have no link. Questions or problems: [open an issue](https://github.com/dielessen/emthera-ha/issues).

Any OpenTherm boiler can be read by the Hub, because an OpenTherm boiler describes itself over the line. This list adds what the boiler does not say: its brand and family, how OpenTherm is reached on it and what its fault codes mean. The Hub does not control OpenTherm boilers yet.

*Generated from the boiler profiles by `scripts/generate_boiler_list.py`; do not edit by hand.*

## What the status words mean

- **The maker says it has OpenTherm**: A document of the maker says the boiler has OpenTherm. Nobody has tried it with a Hub yet.
- **Read by a Hub**: Someone shared what a Hub read from this boiler.
- **Tested with a Hub**: The Hub's attended test passed on this boiler.
- **Tested**: The Hub reads the boiler and controls it, and this was tested on a real boiler of this family.
- **Not tried yet**: Nobody has tried this boiler with a Hub yet. It is in the list because the Hub is built for this kind of boiler.
- **Display codes known**: The meaning of the codes on the boiler's own display is known. The product's own tables do not name this family, so this says nothing more about what the product does with the boiler.

## OpenTherm boilers

Each row comes from the maker's own documents. "Fault codes" is the number of codes whose meaning the profile holds, each with its page in the maker's document.

| Brand | Family | Types | How OpenTherm is reached | Status | Fault codes |
|---|---|---|---|---|---|
| ATAG | P-Serie | P20C, P27C, P35C, P20EC, P27EC, P35EC | Terminals on the boiler | The maker says it has OpenTherm | 14 |
| ATAG | QR-CC | Q25CCR, Q30CCR | Terminals on the boiler | The maker says it has OpenTherm | 87 |
| ATAG | QR-Serie | Q25SR, Q38SR, Q51SR, Q60SR, Q25CR, Q38CR, Q42CR, Q51CR | Terminals on the boiler | The maker says it has OpenTherm | 87 |
| ATAG | i Zone | i20CZ, i22ECZ, i24SZ, i30CZ, i32ECZ, i35SZ | Terminals on the boiler | The maker says it has OpenTherm | 17 |
| ATAG | i-Serie | i32S, i20C, i28C, i36C, i20EC, i28EC, i36EC | A module of the maker is needed | The maker says it has OpenTherm | 19 |
| AWB | ThermoElegance 6 | ThermoElegance 6 | Terminals on the boiler | The maker says it has OpenTherm | 25 |
| AWB | ThermoMaster VR | ThermoMaster VR 24, ThermoMaster VR 24T | Terminals on the boiler | The maker says it has OpenTherm | 22 |
| AWB | ThermoSystem HRM/3 | ThermoSystem HRM 120/3, ThermoSystem HRM 160/3, ThermoSystem HRM 200/3, ThermoSystem HRM 240/3, ThermoSystem HRM 280/3 | Not available (only the maker's own bus) | The maker's manual names no OpenTherm connection | 29 |
| Bulex | IsoTwin Condens | IsoTwin Condens 25/30-B (E-BE), IsoTwin Condens 30/35-B (E-BE), IsoTwin Condens 30/35-B (P-BE) | Not available (only the maker's own bus) | The maker's manual names no OpenTherm connection | 43 |
| Bulex | Thema Condens AS / A | Thema Condens AS 12 A (H-BE), Thema Condens AS 25 A (H-BE), Thema Condens 25/30 A (H-BE), Thema Condens 30/35 A (E-BE) | Not available (only the maker's own bus) | The maker's manual names no OpenTherm connection | 43 |
| Bulex | Thema Condens F | Thema Condens F 24/30 | Terminals on the boiler | The maker says it has OpenTherm | 30 |
| Ferroli | BlueHelix Tech RRT | BlueHelix Tech RRT 34 C | Terminals on the boiler | The maker says it has OpenTherm | 27 |
| Ideal | Logic Combi ESP1 | Logic Combi ESP1 24, Logic Combi ESP1 30, Logic Combi ESP1 35 | Terminals on the boiler | The maker says it has OpenTherm | 20 |
| Intergas | Kombi Kompakt HRE | Kombi Kompakt HRE 24/18 A, Kombi Kompakt HRE 28/24 A, Kombi Kompakt HRE 36/30 A, Kombi Kompakt HRE 36/48 A | Terminals on the boiler | The maker says it has OpenTherm | 20 |
| Intergas | Kombi Kompakt HReco | Kombi Kompakt HReco 24, Kombi Kompakt HReco 30, Kombi Kompakt HReco 36 | Terminals on the boiler | The maker says it has OpenTherm | 20 |
| Intergas | Kompakt Solo HRE | Kompakt Solo HRE 18 A, Kompakt Solo HRE 24 A, Kompakt Solo HRE 30 A, Kompakt Solo HRE 48 A | Terminals on the boiler | The maker says it has OpenTherm | 20 |
| Intergas | Prestige | Prestige A cw6 | Terminals on the boiler | The maker says it has OpenTherm | 20 |
| Intergas | Xtreme | Xtreme 24, Xtreme 30, Xtreme 36 | Terminals on the boiler | The maker says it has OpenTherm | 21 |
| Itho Daalderop | Comfort Classic | Comfort Classic | Terminals on the boiler | The maker says it has OpenTherm | 26 |
| Itho Daalderop | Kli-Max 2 | Kli-Max 2 HR24 CW4, Kli-Max 2 HR24 CW4 VKK, Kli-Max 2 HR30 CW5, Kli-Max 2 HR30 CW5 VKK | Terminals on the boiler | The maker says it has OpenTherm | 10 |
| Nefit | EcomLine Excellent | EcomLine Excellent HR, EcomLine Excellent HRC | Not available (only the maker's own bus) | The maker's manual names no OpenTherm connection | 54 |
| Nefit | ProLine | ProLine HRC 24/CW3, ProLine HRC 24/CW4, ProLine HRC 30/CW5 | A module of the maker is needed | The maker says it has OpenTherm | 94 |
| Nefit | TrendLine II | TrendLine HRC25 CW4 II, TrendLine HRC30 CW5 II | A module of the maker is needed | The maker says it has OpenTherm | 124 |
| Remeha | Avanta | Avanta 24c, Avanta 28c, Avanta 35c | Terminals on the boiler | The maker says it has OpenTherm | 17 |
| Remeha | Avanta Ace | Avanta Ace 24c, Avanta Ace 28c, Avanta Ace 35c | Terminals on the boiler | The maker says it has OpenTherm | 60 |
| Remeha | Calenta | Calenta 25L | Terminals on the boiler | The maker says it has OpenTherm | 19 |
| Remeha | Calenta 25s/28c/35s/40c | Calenta 25s, Calenta 28c, Calenta 35s, Calenta 40c | Terminals on the boiler | The maker says it has OpenTherm | 23 |
| Remeha | Calenta 40L | Calenta 40L | Terminals on the boiler | The maker says it has OpenTherm | 23 |
| Remeha | Calenta Ace | Calenta Ace 25ds, Calenta Ace 28c, Calenta Ace 35ds, Calenta Ace 40c | Terminals on the boiler | The maker says it has OpenTherm | 85 |
| Remeha | Tzerra Ace | Tzerra Ace 24C, Tzerra Ace 28C, Tzerra Ace 39C | Terminals on the boiler | The maker says it has OpenTherm | 66 |
| Remeha | Tzerra M | Tzerra M 24c CW3, Tzerra M 28c CW4, Tzerra M 39c CW5 | Terminals on the boiler | The maker says it has OpenTherm | 24 |
| Vaillant | ecoTEC classic | ecoTEC classic VHR NL 18-24/53, ecoTEC classic VHR NL 23-28/53, ecoTEC classic VHR NL 28-34/53 | A module of the maker is needed | The maker says it has OpenTherm | 33 |
| Vaillant | ecoTEC exclusive | ecoTEC exclusive VHR 25/36CF/1-7 (N-NL), ecoTEC exclusive VHR 34/43CF/1-7 (N-NL) | A module of the maker is needed | The maker says it has OpenTherm | 84 |
| Vaillant | ecoTEC plus | ecoTEC plus VHR, ecoTEC plus VHR S | A module of the maker is needed | The maker says it has OpenTherm | 84 |
| Vaillant | ecoTEC pure | ecoTEC pure VHR 18-24/7-2 (K-NL), ecoTEC pure VHR 23-28/7-2 (K-NL), ecoTEC pure VHR 28-34/7-2 (K-NL) | Not available (only the maker's own bus) | The maker's manual names no OpenTherm connection | 37 |

## EMS boilers

Boilers with the Bosch group's EMS bus. The status says whether anyone has tried the boiler with a Hub; the meaning of the display codes is checked against the maker's manuals.

| Brand | Family | Link | Status | Display codes |
|---|---|---|---|---|
| Bosch | Bosch (Junkers) Cerapur | EMS | Display codes known | 56 |
| Bosch | Bosch Condens 7000i W | EMS | Display codes known | 57 |
| Buderus | Buderus Logamax plus GB162 | EMS | Not tried yet | 68 |
| Buderus | Buderus Logamax plus GB172 | EMS+ | Not tried yet | 43 |
| Nefit | Nefit EcomLine Excellent | EMS | Not tried yet | 54 |
| Nefit | Nefit Ecomline Classic | EMS, only through the Bosch EasyControl Adapter | Tested | 54 |
| Nefit | Nefit ProLine | EMS | Display codes known | 94 |
| Nefit | Nefit SmartLine | EMS | Display codes known | 61 |
| Nefit | Nefit TopLine | EMS | Tested | 61 |
| Nefit | Nefit TrendLine II | EMS+ | Not tried yet | 124 |
| Worcester Bosch | Worcester Bosch Greenstar 4000 | EMS | Display codes known | 72 |

## Per family

Information only: a profile says what the maker's documents say, nothing about what the product does with the boiler.

### ATAG P-Serie

- Types: P20C, P27C, P35C, P20EC, P27EC, P35EC
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Connection block position labelled "OpenTherm of Aan/Uit-thermostaat" (figure 9.a): an OpenTherm thermostat or a voltage-free on/off thermostat can go there; the thermostat needs a 2-wire connection and goes on the screw connector plugged into the connection block. A separate "ATAG Zone" bus connection sits beside it (page 42-43)
- Fault codes in the profile: 14

What the manual says about OpenTherm:

- Section 9.1: an OpenTherm thermostat can be connected here; an on/off thermostat (voltage-free) can be connected to the same position. The thermostat must have a 2-wire connection. (page 43)

Documents:

- ATAG Verwarming Nederland B.V., *Installatie- en servicemanual P-Serie*, 8A.51.62.00 / 04.21

### ATAG QR-CC

- Types: Q25CCR, Q30CCR
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Positions 19 and 20 of the terminal block ("OT ON/OFF"); positions 21 and 22 are a second connection of the same kind (for example for a mixing group) (page 33)
- Fault codes in the profile: 87

What the manual says about OpenTherm:

- The maker lists the room controls that can be connected to positions 19 and 20 of the QR-CC: its own One, Round Modulation, WiZe and BrainZ, "or any other brand according to the OpenTherm protocol". Any other thermostat must have a potential-free contact and goes on the same positions 19 and 20. (page 33)
- Parameters 6355 and 6357 choose which external room controller (1, 2 or 3) an OT connection serves, or "via H8/H9 (for on/off)"; per heating circuit the room controller is set to "Intern" (the Siemens control) or "Extern" (OpenTherm), and for hot water "Externe regelaar" means that the settings are made on the OpenTherm controller. (page 34)
- A heat demand through the OpenTherm / on-off input also starts the boiler when the automatic venting programme has not run, so the installation must be completely filled before the plug is put in the socket. (page 36)
- When hot water is configured through OpenTherm no bar shows in the display and the hot water clock programme of the external controller leads; the heating-circuit mode key works only with the Siemens QAA55 controller, not with OpenTherm. (page 37)

Documents:

- ATAG Verwarming Nederland B.V., *Gebruikshandleiding, Installatie- en servicemanual QR-CC*, 8A.51.64.02 / 04.24

### ATAG QR-Serie

- Types: Q25SR, Q38SR, Q51SR, Q60SR, Q25CR, Q38CR, Q42CR, Q51CR
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Positions 19 and 20 of the terminal block ("OT ON/OFF"); positions 21 and 22 are a second connection of the same kind (for example for a mixing group) (page 36)
- Fault codes in the profile: 87

What the manual says about OpenTherm:

- The maker lists the room controls that can be connected to positions 19 and 20 of the QR series: its own One, Round Modulation, WiZe and BrainZ, "or any other brand according to the OpenTherm protocol". Any other thermostat must have a potential-free contact and goes on the same positions 19 and 20. (page 36)
- Parameters 6355 and 6357 choose which external room controller (1, 2 or 3) an OT connection serves, or "via H8/H9 (for on/off)"; per heating circuit the room controller is set to "Intern" (the Siemens control) or "Extern" (OpenTherm), and for hot water "Externe regelaar" means that the settings are made on the OpenTherm controller. (page 37)
- A heat demand through the OpenTherm / on-off input also starts the boiler when the automatic venting programme has not run, so the installation must be completely filled before the plug is put in the socket. (page 39)
- When hot water is configured through OpenTherm no bar shows in the display and the hot water clock programme of the external controller leads; the heating-circuit mode key works only with the Siemens QAA55 controller, not with OpenTherm. (page 40)

Documents:

- ATAG Verwarming Nederland B.V., *Gebruikshandleiding, Installatie- en servicemanual QR-Serie*, 8A.51.63.03 / 04.24

### ATAG i Zone

- Types: i20CZ, i22ECZ, i24SZ, i30CZ, i32ECZ, i35SZ
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Thermostat connection labelled "OpenTherm of Aan/Uit-thermostaat" on the connection block (figure 7.a); a separate "ATAG Zone" bus connection sits beside it (page 50-51)
- Fault codes in the profile: 17

What the manual says about OpenTherm:

- An OpenTherm thermostat can be connected here, and a potential-free on/off thermostat as well; the thermostat needs a 2-wire connection. (page 50)

Documents:

- ATAG Verwarming, *Installatie- en servicemanual i Zone-Serie*, 8H.51.47.00 / 0.19

### ATAG i-Serie

- Types: i32S, i20C, i28C, i36C, i20EC, i28EC, i36EC
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: A module of the maker is needed
- Terminals: Position "BUS" of the connection block (printed "Bus+OT-LPA" in figure 9.a): an ATAG bus thermostat goes directly on BUS; a Round Modulation, WiZe or other OpenTherm thermostat or controller goes first on the OT-LPA and the OT-LPA on BUS. A separate on/off thermostat (voltage-free) has its own position (page 44-45)
- Module: OT-LPA (OpenTherm Low Power Adapter) (article number not named in the manual; page 45)
- Fault codes in the profile: 19

What the manual says about OpenTherm:

- The OT-LPA ("OpenTherm Low Power Adapter") must be connected between the control unit and the thermostat or controller when an ATAG WiZe, Round Modulation or other OpenTherm controller is used. (page 45)

Documents:

- ATAG Verwarming, *Installatie- en servicemanual i-Serie*, 8A.51.36.03 / 01.18

### AWB ThermoElegance 6

- Types: ThermoElegance 6
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: The terminal block on the back of the control box: the terminals for OpenTherm and on/off (yellow and orange wire, figure 5.6.1); a separate pair of terminals is for a mechanical thermostat with 110 mA anticipation current (yellow and blue wire) (page 25-26)
- Fault codes in the profile: 25

What the manual says about OpenTherm:

- The maker says to connect an OpenTherm room thermostat to the terminal block at the back of the control box, to switch the boiler off from the mains while connecting it, and, if the thermostat has a hot water setting, to set it to 63 degC. (page 26)
- With a modulating OpenTherm room thermostat the setting functions on the boiler lapse; they are set on the thermostat (depending on its model). (page 26)
- From the factory the yellow and orange wire on the terminal block are shorted with a blue wire, so the boiler always sees a heat demand for heating; the blue wire must be removed or the boiler burns continuously. (page 26)
- Modulation follows the set or calculated flow temperature (calculated with an outdoor sensor or an OpenTherm room thermostat). When an outdoor sensor or an OpenTherm thermostat is connected, the flow setpoint cannot be changed on the boiler; with an OpenTherm thermostat the hot water setpoint is set on the thermostat, and if it has no hot water function the boiler is set as for an on/off thermostat. (page 18-19)
- For a boiler that does not react to the room thermostat the maker says to check the thermostat and its wiring, the wiring from the terminal block to the connector of the OpenTherm interface, and the wiring from that interface to connector J15 of the main board. (page 35)

Documents:

- AWB cv-ketels, *Bedienings- en installatiehandleiding ThermoElegance 6*, 192366

### AWB ThermoMaster VR

- Types: ThermoMaster VR 24, ThermoMaster VR 24T
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: The 6-pole terminal block at the back of the control box (figure 13): the connections for the communicating (OpenTherm) room thermostat; the terminals for OpenTherm and on/off are marked by the yellow and orange wires (page 12)
- Fault codes in the profile: 22

What the manual says about OpenTherm:

- With an OpenTherm (modulating) room thermostat the setting functions on the boiler lapse; they can be set on the room thermostat (depending on its model). The boiler must be without power while the OpenTherm thermostat is connected. (page 12)
- If the OpenTherm thermostat has a hot water setting, the maker advises 63 degC. (page 12)
- From the factory the yellow and orange wire on the terminal block are linked with a blue wire, so the boiler always sees a heat demand; the blue wire must be removed to prevent the boiler from heating continuously. (page 12)

Documents:

- AWB, *Installatievoorschrift ThermoMaster VR 24 / 24T*, 187138

### AWB ThermoSystem HRM/3

- Types: ThermoSystem HRM 120/3, ThermoSystem HRM 160/3, ThermoSystem HRM 200/3, ThermoSystem HRM 240/3, ThermoSystem HRM 280/3
- Status: The maker's manual names no OpenTherm connection
- How OpenTherm is reached: Not available (only the maker's own bus)
- Terminals: The wiring list names an option for an external or room thermostat on terminals 3-4 (contact), an option on terminals 7-8-9 (analogue), and a bus connection for a digital thermostat (the manual later says to check the "Bus" connection between thermostat and boiler, and shows an eBus plug). The manual names no OpenTherm connection (page 19-20, 42)
- Fault codes in the profile: 29

What the manual says about OpenTherm:

- Section 5.9.2 (connecting an external controller) and the wiring list name a contact input, an analogue input and a bus connection; the manual names no OpenTherm connection and no converter. This profile is about the large ThermoSystem HRM/3 boilers (120 to 280). (page 19-20)
- If a jumper is placed between terminals 3 and 4 and the boiler starts, the external thermostat must be checked. (page 42)

Documents:

- AWB cv-ketels, *Installatievoorschrift ThermoSystem HRM/3 (120/3, 160/3, 200/3, 240/3, 280/3)*, 0020076265_00

### Bulex IsoTwin Condens

- Types: IsoTwin Condens 25/30-B (E-BE), IsoTwin Condens 30/35-B (E-BE), IsoTwin Condens 30/35-B (P-BE)
- Status: The maker's manual names no OpenTherm connection
- How OpenTherm is reached: Not available (only the maker's own bus)
- Terminals: Section 5.7.5 shows the thermostat connections of the electronics as "RT 24V" (a 24 V thermostat), "BUS" (an eBUS thermostat or receiver) and "T ext" (a wired outdoor sensor) on plug X17, and a "FLOOR" input for a floor heating safety thermostat on X18. The manual names no OpenTherm connection (page 14)
- Fault codes in the profile: 43

What the manual says about OpenTherm:

- Section 5.7.5 (connecting a thermostat to the electronics): a 24 V thermostat, an eBUS thermostat or receiver, a wired outdoor sensor and a floor heating safety thermostat; no OpenTherm connection and no module for one is named. (page 14)

Documents:

- Bulex, *Installatie- en onderhoudshandleiding IsoTwin Condens 25/30B (E-BE), 30/35B (E-BE), 30/35B (P-BE)*, 0020244951_03

### Bulex Thema Condens AS / A

- Types: Thema Condens AS 12 A (H-BE), Thema Condens AS 25 A (H-BE), Thema Condens 25/30 A (H-BE), Thema Condens 30/35 A (E-BE)
- Status: The maker's manual names no OpenTherm connection
- How OpenTherm is reached: Not available (only the maker's own bus)
- Terminals: Section 5.7.5 shows the thermostat connections of the electronics as "RT 24V" (a 24 V thermostat), "BUS" (an eBUS thermostat or receiver) and "T ext" (a wired outdoor sensor) on plug X17, and a "FLOOR" input for a floor heating safety thermostat on X18. The manual names no OpenTherm connection (page 15)
- Fault codes in the profile: 43

What the manual says about OpenTherm:

- Section 5.7.5 (connecting a thermostat to the electronics, valid for the combi boiler): a 24 V thermostat, an eBUS thermostat or receiver, a wired outdoor sensor and a floor heating safety thermostat; no OpenTherm connection and no module for one is named. (page 15)

Documents:

- Bulex, *Installatie- en onderhoudshandleiding Thema Condens AS 12 A (H-BE), AS 25 A (H-BE), 25/30 A (H-BE), 30/35 A (E-BE)*, 0020200482_03

### Bulex Thema Condens F 24/30

- Types: Thema Condens F 24/30
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Connection labelled "Opentherm" on the motherboard: "Aansluiting modulerende kamerthermostaat OPENTHERM" (item 1 of the accessory connection figure); the wiring diagram also names an "Opentherm-kaart" (item 18) and the "Aansluiting Opentherm-kamerthermostaat" (item 19); the jumper on the terminals where a room thermostat is connected must be removed (page 29-30)
- Fault codes in the profile: 30

What the manual says about OpenTherm:

- Section 5.9 names separate connections for a modulating OpenTherm room thermostat, an outdoor sensor, a modulating eBUS room thermostat, a 24 V room thermostat and a 230 V room thermostat. (page 29)

Documents:

- Bulex, *Gebruiksaanwijzing en Installatiehandleiding Thema CONDENS F 24/30*, 300772

### Ferroli BlueHelix Tech RRT 34 C

- Types: BlueHelix Tech RRT 34 C
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Terminals 5 and 6 of the terminal block (entry 139 "OpenTherm room timer connection (option)" and entry 72 in figure 22); the manual says the room thermostat connection (entry 72) is also OpenTherm compliant; the jumper on the terminal block must be removed first; every connection must be voltage-free (not 230 V) (page 14, 50)
- Fault codes in the profile: 27

What the manual says about OpenTherm:

- Table 1 (adjustments from the Remote Timer Control with the OpenTherm protocol): the heating and the hot water temperature can be set from the controller menu and from the boiler panel; summer mode on the boiler has priority over a heat demand from the controller; disabling hot water from the controller puts the boiler in Economy mode and switches the eco/comfort button on the boiler panel off; enabling it selects Comfort mode and both modes can then be chosen on the boiler panel; with an outside sensor all weather-compensation settings are made on the controller. (page 8)
- The boiler keeps the last 8 fault codes; they can also be viewed in the menu of the optional OpenTherm remote timer control. (page 31)
- The maker names its own OpenTherm RF smart control (part number Y87RFC2124) for terminals 5 and 6; it needs no 230 V connection. A smart thermostat on terminals 5-6 must be low voltage or OpenTherm compliant. (page 14, 50)

Documents:

- Ferroli, *Instructions for use, installation and maintenance BLUEHELIX TECH RRT 34 C*, cod. 3541O990

### Ideal Logic Combi ESP1

- Types: Logic Combi ESP1 24, Logic Combi ESP1 30, Logic Combi ESP1 35
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: The OpenTherm connection on the right-hand side of the boiler's installer connections area, a pair of terminals labelled "Open Therm" next to "Outside Sensor"; the violet link wire is removed and the 2-core cable of the OpenTherm device is connected (page 33)
- Fault codes in the profile: 20

What the manual says about OpenTherm:

- The manual says to wire an OpenTherm room control or other OpenTherm master device to this connection and not to connect 230 V to these terminals, or the boiler electronics will be damaged. Its example of an OpenTherm device is a Honeywell OT bridge (R8810). (page 33)
- Note 1 of section 2.18: the link wire on the 230 V installer room thermostat/timer connection gives a demand in conjunction with the OpenTherm link wire (the violet one, on the right-hand side of the control box). (page 32)
- With a weather compensation option fitted (user guide, page 4), the central heating temperature knob becomes a method of controlling room temperature; the boiler's outside sensor and the OpenTherm connection sit side by side in the wiring diagram. (page 33)

Documents:

- Ideal Heating, *Installation & Servicing Logic Combi ESP1 24 30 35*, UIN 222353 A07

### Intergas Kombi Kompakt HRE

- Types: Kombi Kompakt HRE 24/18 A, Kombi Kompakt HRE 28/24 A, Kombi Kompakt HRE 36/30 A, Kombi Kompakt HRE 36/48 A
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Connector X2, terminals 11-12 (OpenTherm room thermostat); terminals 6-7 of connector X4 must be open (page 78)
- Fault codes in the profile: 20

What the manual says about OpenTherm:

- The boiler is suitable for a modulating room thermostat that speaks the OpenTherm protocol; the thermostat calculates the flow temperature. (page 23)
- To use the hot water on/off function of the OpenTherm thermostat the tap comfort function must be set to eco or on. (page 23)

Documents:

- Intergas Verwarming B.V., *Installatievoorschrift Kombi Kompakt HRE 24/18 A, 28/24 A, 36/30 A, 36/48 A*, 88557809

### Intergas Kombi Kompakt HReco

- Types: Kombi Kompakt HReco 24, Kombi Kompakt HReco 30, Kombi Kompakt HReco 36
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Connector X4, terminals 11-12 ("OpenTherm thermostaat") (page 76)
- Fault codes in the profile: 20

What the manual says about OpenTherm:

- Section 5.5.2: the boiler is suitable for a modulating room thermostat that speaks the OpenTherm protocol; the thermostat calculates the flow temperature for the wanted room temperature. (page 23)
- To use the hot water on/off function of the OpenTherm thermostat the tap comfort function must be set to eco or on. (page 23)
- If the OpenTherm thermostat supports load control, the boiler switches to load control at a very low heat demand (the display shows LC): it heats at minimum load in intervals. (page 7)
- Service parameter E sets the minimum flow temperature for a heat demand from an OpenTherm or RF thermostat (factory 30 degC, range 10 to 60 degC); parameter E. sets how the boiler answers a demand below it (not answered, minimum flow, or maximum flow as an on/off function). (page 53)
- With an OpenTherm room thermostat the boiler receives the outdoor temperature, but the boiler's own heating curve is not active. (page 57)

Documents:

- Intergas Verwarming B.V., *Installatievoorschrift Kombi Kompakt HReco 24, 30, 36*, 88399809

### Intergas Kompakt Solo HRE

- Types: Kompakt Solo HRE 18 A, Kompakt Solo HRE 24 A, Kompakt Solo HRE 30 A, Kompakt Solo HRE 48 A
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Connector X4, terminals 11-12 ("OpenTherm kamerthermostaat"); terminals 6-7 (on/off thermostat) must be open (page 69)
- Fault codes in the profile: 20

What the manual says about OpenTherm:

- Section 4.5.2: the boiler is suitable for a modulating room thermostat that speaks the OpenTherm protocol; the thermostat calculates the flow temperature. (page 19)
- For a heating-only boiler with an external hot water tank: in the "eco" setting the OpenTherm thermostat can switch the tank keep-warm on and off (if the thermostat supports it); an OpenTherm thermostat without this function, or an on/off thermostat, leaves the tank cold. (page 47)
- Service parameter E sets the minimum flow temperature during a heat demand from an OpenTherm thermostat (factory 30 degC, range 10 to 60 degC); parameter E. ("OT-reactie") sets how the boiler answers a demand below it. (page 49)

Documents:

- Intergas Verwarming B.V., *Installatievoorschrift Kompakt Solo HRE 18 A, 24 A, 30 A, 48 A*, 88077806

### Intergas Prestige

- Types: Prestige A cw6
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Connector X4, terminals 11-12 ("OpenTherm kamerthermostaat"); terminals 6-7 (on/off thermostat) must be open (page 58)
- Fault codes in the profile: 20

What the manual says about OpenTherm:

- Section 5.4.4: the boiler is suitable for a modulating thermostat that speaks the OpenTherm protocol. (page 17)
- With OpenTherm the thermostat decides the heating curve; the boiler only passes on the outdoor temperature when an outdoor sensor is connected. (page 17)

Documents:

- Intergas Verwarming B.V., *Installatievoorschrift Prestige A cw6*, 88136806

### Intergas Xtreme

- Types: Xtreme 24, Xtreme 30, Xtreme 36
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Connector X13, terminals 1-2 ("OpenTherm thermostaat (primaire aansluiting)"; polarity does not matter); an optional second OpenTherm thermostat goes on connector X12, terminals 1-2 (page 24, 81)
- Fault codes in the profile: 21

What the manual says about OpenTherm:

- Section 5.5.1: the boiler has an "OpenTherm Smart Power" connection as standard, so the modulating room thermostat of the maker (Comfort Touch) connects without changes; other OpenTherm thermostats can be connected too (see the manual of that thermostat). (page 24)
- To use the hot water on/off function of the OpenTherm thermostat the tap comfort function must be set to "eco" or "on" and parameter 74 must be 0; the self-learning behaviour of the boiler is then switched off. (page 24, 60)
- If an OpenTherm and an on/off thermostat are both connected, the on/off thermostat has priority over the OpenTherm thermostat. (page 24)
- With an OpenTherm thermostat no frost thermostat can be put in parallel on connector X13; the frost thermostat then goes on X12 (optional). (page 25)
- With an OpenTherm thermostat the thermostat decides the influence of the outdoor sensor; the boiler heating curve is not active (the outdoor temperature is passed on). (page 25, 61)
- A service parameter sets how the boiler answers a heat demand from an OpenTherm thermostat (0: a demand below 30 degC is not answered; 1: answered with the minimum flow temperature limited to 30 degC; 2: answered with the maximum flow temperature, an on/off function). (page 59)

Documents:

- Intergas Verwarming B.V., *Installatievoorschrift Xtreme 24, Xtreme 30, Xtreme 36*, 84004408

### Itho Daalderop Comfort Classic

- Types: Comfort Classic
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Terminal strips behind the display, entry 2a + 2b "OpenTherm kamerthermostaat [1e zone]" (figure of section 3.14); the second zone takes only a voltage-free on/off thermostat (page 44)
- Fault codes in the profile: 26

What the manual says about OpenTherm:

- Section 3.15: a modulating OpenTherm thermostat lets the burner run at different levels; not every modulating thermostat can be connected to the boiler, so the maker asks to check that the thermostat can control the boiler. A thermostat with "power stealing" may be used for the first zone but not for the second zone. (page 45)
- Section 5.2.6: with certain types and brands of modulating room thermostats that use the OpenTherm protocol, the status, warning, blocking and fault messages of the boiler are shown on the display of the room thermostat. (page 76)
- If an outdoor sensor is connected and the weather-dependent control of the OpenTherm room thermostat is used, the boiler menu "WAR REGELING" is not shown; with a thermostat without OpenTherm the boiler uses its own weather-dependent control. (page 51, 62)

Documents:

- Itho Daalderop, *Installatiehandleiding Comfort Classic*, 01-00599-004

### Itho Kli-Max 2

- Types: Kli-Max 2 HR24 CW4, Kli-Max 2 HR24 CW4 VKK, Kli-Max 2 HR30 CW5, Kli-Max 2 HR30 CW5 VKK
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Terminal strip, terminals 1-2 "OpenTherm thermostaat"; terminals 3-4 are for an on/off thermostat and no OpenTherm thermostat may be connected there; terminals 5-6 take the outdoor sensor (page 17)
- Fault codes in the profile: 10

What the manual says about OpenTherm:

- The maker says it has a series of OpenTherm thermostats with which the boiler can be controlled fully modulating. (page 17)
- If an OpenTherm thermostat with weather-dependent control is used, the outdoor sensor goes on terminals 5-6 and the settings for the weather-dependent control are in the OpenTherm thermostat. (page 17)
- With OpenTherm thermostats that have a hot water function, the eco/comfort setting for keeping the internal hot water coil warm works through the connected thermostat. (page 19)

Documents:

- Itho (Daalderop), *Installatiehandleiding Itho HR-combiketel Kli-Max 2 HR24 CW4 / HR24 CW4 VKK, HR30 CW5 / HR30 CW5 VKK*

### Nefit EcomLine Excellent

- Types: EcomLine Excellent HR, EcomLine Excellent HRC
- Status: The maker's manual names no OpenTherm connection
- How OpenTherm is reached: Not available (only the maker's own bus)
- Terminals: Terminals 1 and 2 of the appliance terminal block take an on/off room thermostat (after removing the dummy loop); terminals 3-4 take the digital modulating Nefit ModuLine room thermostat (not polarity sensitive). The manual names no OpenTherm connection (page 1-14)
- Fault codes in the profile: 54

What the manual says about OpenTherm:

- Section 1.4.2 (room control): the appliance has two room thermostat connections, an on/off one and one for the digital modulating ModuLine thermostat; the manual names no OpenTherm connection and no converter. (page 1-14)

Documents:

- Nefit B.V., *Installatie-instructie Nefit EcomLine HR (EcomLine Excellent HR-toestellen)*, 705.427A-4200

### Nefit ProLine

- Types: ProLine HRC 24/CW3, ProLine HRC 24/CW4, ProLine HRC 30/CW5
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: A module of the maker is needed
- Terminals: The modulating controller (for example the Nefit ModuLine 200) goes on the orange plug of the connection strip and an on/off thermostat on the green plug; an OpenTherm room thermostat is connected through the Nefit EMS-OpenTherm-converter (page 17-18)
- Module: Nefit EMS-OpenTherm-converter (article number not named in the manual; page 17)
- Fault codes in the profile: 94

What the manual says about OpenTherm:

- The list of components that can be connected names the Nefit EMS-OpenTherm-converter (accessory); with it an OpenTherm room thermostat can also be connected. (page 17)

Documents:

- Bosch Thermotechniek B.V. (Nefit), *Installatie-instructie Nefit ProLine HRC 24/CW3, HRC 24/CW4, HRC 30/CW5*, 6 720 646 227

### Nefit TrendLine II

- Types: TrendLine HRC25 CW4 II, TrendLine HRC30 CW5 II
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: A module of the maker is needed
- Terminals: Terminal 4 takes an on/off room thermostat and terminal 5 the Nefit modulating (EMS) room thermostat; an OpenTherm room thermostat is connected through the Nefit EMS-OT-converter (page 18)
- Module: Nefit EMS-OT-converter (OpenTherm) (article number not named in the manual; page 17-18)
- Fault codes in the profile: 124

What the manual says about OpenTherm:

- The list of components that can be connected names the Nefit EMS-OT-converter (OpenTherm); the manual says an OpenTherm room thermostat can also be connected by means of this converter (accessory). (page 17-18)

Documents:

- Bosch Thermotechniek B.V. (Nefit), *Installatie-instructie TrendLine HRC25 CW4 II, HRC30 CW5 II*, 6720882261

### Remeha Avanta

- Types: Avanta 24c, Avanta 28c, Avanta 35c
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Terminals 3-4 of connector X6 (the same pair takes an on/off thermostat) (page 41)
- Fault codes in the profile: 17

What the manual says about OpenTherm:

- The boiler has an OpenTherm connection as standard and is suitable for OpenTherm Smart Power. (page 41)
- If the hot water temperature can be set on the OpenTherm controller, the boiler supplies that temperature, at most the value set in the boiler. (page 41)
- With an OpenTherm thermostat no frost thermostat can be connected in parallel on terminals 3-4. (page 42)

Documents:

- Remeha (BDR Thermea Netherlands), *Installatie- en servicehandleiding Hoog rendement gaswandketel Avanta 24c - 28c - 35c*, 119665 v.13

### Remeha Avanta Ace

- Types: Avanta Ace 24c, Avanta Ace 28c, Avanta Ace 35c
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Terminals 7-8 of the M2 connection board: the room thermostat (RT), the OpenTherm (OT) device or the R-Bus device is connected there (page 47)
- Fault codes in the profile: 60

What the manual says about OpenTherm:

- The same terminals take an on/off room thermostat, an OpenTherm thermostat or an R-Bus device; the thermostat must be low voltage. (page 47)
- When the heating curve is set by an OpenTherm thermostat, the curve must not also be set with the boiler's own parameters. (page 69)
- Fault A.02.54 names a power fault on the OpenTherm bus and points at the devices on terminals 7-8. (page 86)

Documents:

- Remeha (BDR Thermea Netherlands), *Installatie- en servicehandleiding Gasgestookte condensatieketel Avanta Ace 24c - 28c - 35c*, 7745710 v.07

### Remeha Calenta 25L

- Types: Calenta 25L
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Terminals "On/off-OT" of the connection connector (the same pair takes an on/off thermostat) (page 39)
- Fault codes in the profile: 19

What the manual says about OpenTherm:

- The boiler has an OpenTherm connection as standard and is suitable for OpenTherm Smart Power. (page 39)
- If the hot water temperature can be set on the OpenTherm controller, the boiler supplies that temperature, at most the value set in the boiler. (page 39)
- An OpenTherm controller can also use the outdoor sensor on the Tout terminals; the heating curve is then set on the controller. (page 40)

Documents:

- Remeha (BDR Thermea Netherlands), *Installatie- en servicehandleiding Hoog rendement gaswandketels Calenta 25L*, 119288-AF

### Remeha Calenta 25s - 28c - 35s - 40c

- Types: Calenta 25s, Calenta 28c, Calenta 35s, Calenta 40c
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Terminals "On/off-OT" of the connection connector (the same pair takes an on/off thermostat) (page 47)
- Fault codes in the profile: 23

What the manual says about OpenTherm:

- The boiler has an OpenTherm connection as standard and is suitable for OpenTherm Smart Power. (page 47)
- If the hot water temperature can be set on the OpenTherm controller, the boiler supplies that temperature, at most the value set in the boiler. (page 47)
- An OpenTherm controller can also use the outdoor sensor on the Tout terminals; the heating curve is then set on the controller. (page 48)
- With an OpenTherm thermostat no frost thermostat may be connected in parallel on the On/off-OT terminals; protect the installation against frost with an outdoor sensor instead. (page 48)
- The maker lists the control methods: on/off, modulating (OpenTherm, for example the qSense or iSense controller) and analogue 0-10 V. (page 20)

Documents:

- Remeha (BDR Thermea Netherlands), *Installatie- en servicehandleiding Hoog rendement gaswandketels Calenta 25s - 28c - 35s - 40c*, 119401-10

### Remeha Calenta 40L

- Types: Calenta 40L
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Terminals "On/off-OT" of the connection connector (the same pair takes an on/off thermostat) (page 43)
- Fault codes in the profile: 23

What the manual says about OpenTherm:

- The boiler has an OpenTherm connection as standard and is suitable for OpenTherm Smart Power. (page 43)
- If the hot water temperature can be set on the OpenTherm controller, the boiler supplies that temperature, at most the value set in the boiler. (page 43)
- An OpenTherm controller can also use the outdoor sensor on the Tout terminals; the heating curve is then set on the controller. (page 44)
- With an OpenTherm thermostat no frost thermostat may be connected in parallel on the On/off-OT terminals; protect the installation against frost with an outdoor sensor instead. (page 44)
- The maker lists the control methods: on/off, modulating (OpenTherm, for example the qSense or iSense controller) and analogue 0-10 V. (page 19)

Documents:

- Remeha (BDR Thermea Netherlands), *Installatie- en servicehandleiding Hoog rendement gaswandketels Calenta 40L*, 126382-10

### Remeha Calenta Ace

- Types: Calenta Ace 25ds, Calenta Ace 28c, Calenta Ace 35ds, Calenta Ace 40c
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Terminals "R-Bus" of the connection connector; the boiler has an R-Bus connection as standard instead of an OT connector, and the R-Bus connector takes an R-Bus thermostat (for example the eTwist), an OpenTherm thermostat or an on/off thermostat; the software recognises which type is connected; the two wires may go either way round (page 54)
- Fault codes in the profile: 85

What the manual says about OpenTherm:

- If the hot water temperature can be set on the thermostat, the boiler supplies that temperature, at most the value set in the boiler. (page 54)
- With an OpenTherm thermostat (for example the eTwist) no frost thermostat can be put in parallel on the R-Bus terminals; frost protection then has to be done with an outdoor sensor. (page 55)
- An OpenTherm controller can use the outdoor sensor of the boiler; the wanted heating curve is then set on the controller (the boiler uses its own curve with an on/off thermostat). (page 55)
- The counter list of the boiler has an entry "OpenTherm controller present? 0 = no, 1 = yes". (page 95)

Documents:

- Remeha (BDR Thermea Netherlands), *Installatie- en servicehandleiding Hoog rendement gaswandketel Calenta Ace 25ds - 28c - 35ds - 40c*, 7685807 v.11

### Remeha Tzerra Ace

- Types: Tzerra Ace 24C, Tzerra Ace 28C, Tzerra Ace 39C
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Terminals "R-Bus" of the connection connector; the boiler has an R-Bus connection instead of a separate OT connector (page 25)
- Fault codes in the profile: 66

What the manual says about OpenTherm:

- The R-Bus connector takes an R-Bus thermostat, an OpenTherm thermostat or an on/off thermostat; the software recognises which type is connected. The two wires can be connected either way round. (page 25)
- If the hot water temperature can be set on the thermostat, the boiler supplies it, at most the value set in the boiler. (page 25)
- With an OpenTherm thermostat no frost thermostat can be connected in parallel on the R-Bus terminals; an OpenTherm controller can use the outdoor sensor. (page 26)

Documents:

- Remeha (BDR Thermea Netherlands), *Installatie- en gebruikershandleiding Hoog rendement gaswandketel Tzerra Ace 24C - 28C - 39C*, 7680248 v.11

### Remeha Tzerra M

- Types: Tzerra M 24c CW3, Tzerra M 28c CW4, Tzerra M 39c CW5
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: Terminals on the boiler
- Terminals: Terminals "On/off-OT" of the connection connector in the connection box (the same pair takes an on/off thermostat) (page 40-41)
- Fault codes in the profile: 24

What the manual says about OpenTherm:

- The boiler has an OpenTherm connection as standard and is suitable for OpenTherm Smart Power. (page 40)
- With an OpenTherm thermostat no frost thermostat may be connected in parallel on the On/off-OT terminals. (page 41)
- The maker lists the control methods: on/off and modulating (OpenTherm, for example the qSense or iSense controller). (page 15)

Documents:

- Remeha (BDR Thermea Netherlands), *Installatie- en servicehandleiding Hoog rendement gaswandketels Tzerra M 24c CW3, 28c CW4, 39c CW5*, 7600997-06

### Vaillant ecoTEC classic VHR

- Types: ecoTEC classic VHR NL 18-24/53, ecoTEC classic VHR NL 23-28/53, ecoTEC classic VHR NL 28-34/53
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: A module of the maker is needed
- Terminals: Section 5.8.5: remove the jumper on the grey plug of the "openTHERM-module", connect the external thermostat to that grey plug and mind the polarity. The boiler's own connections for a thermostat are eBUS and a 24 V "RT" input (X100 or X106), section 5.8.6 (page 18)
- Module: openTHERM module (article number not named in the manual; page 18)
- Fault codes in the profile: 33

What the manual says about OpenTherm:

- The electrical data of the boiler say that with an installed openTHERM module the stand-by consumption is 1 W higher, so the module is an optional part. (page 44)

Documents:

- Vaillant, *Installatie- en onderhoudshandleiding ecoTEC classic VHR...*, 0020275648_03

### Vaillant ecoTEC exclusive

- Types: ecoTEC exclusive VHR 25/36CF/1-7 (N-NL), ecoTEC exclusive VHR 34/43CF/1-7 (N-NL)
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: A module of the maker is needed
- Terminals: The grey ProE plug of the openTHERM module: the jumper in this plug is removed and the external thermostat is connected there (mind the polarity) (page 16)
- Module: openTHERM module (article number not named in the manual; page 16, 75, 77, 80)
- Fault codes in the profile: 84

What the manual says about OpenTherm:

- Section 5.7.6 (connecting an external thermostat to the openTHERM module): remove the jumper on the grey ProE plug of the module, connect the external thermostat to that plug and take the polarity of the connections into account. (page 16)
- The openTHERM module appears in the wiring diagrams of both types (item 3, next to the board and the display board); the manual gives no article number for it. (page 75, 77)
- With an installed openTHERM module the stand-by energy consumption is higher by 1 W in each case. (page 80)

Documents:

- Vaillant, *Installatie- en onderhoudshandleiding ecoTEC exclusive VHR..*, 0020282268_07

### Vaillant ecoTEC plus VHR

- Types: ecoTEC plus VHR, ecoTEC plus VHR S
- Status: The maker says it has OpenTherm
- How OpenTherm is reached: A module of the maker is needed
- Terminals: The external thermostat is connected to the grey plug of the openTHERM module (the jumper on that plug is removed first); no terminals on the boiler's own board are named for OpenTherm (page 19)
- Module: openTHERM module (article number not named in the manual; page 19)
- Fault codes in the profile: 84

What the manual says about OpenTherm:

- Section 5.8.6 is titled "connect an external thermostat to the openTHERM module": remove the jumper on the grey plug, connect the thermostat there and mind the polarity of the connections. (page 19)
- The module appears in the parts list of the boiler; with the openTHERM module installed the standby energy use rises by 1 W, which makes it an optional part. (page 92)
- The own thermostat connection of the boiler described in the manual is the eBUS (+/-) pair. (page 18)

Documents:

- Vaillant, *Installatie- en onderhoudshandleiding ecoTEC plus VHR../VHR S..*, 0020282267_08

### Vaillant ecoTEC pure

- Types: ecoTEC pure VHR 18-24/7-2 (K-NL), ecoTEC pure VHR 23-28/7-2 (K-NL), ecoTEC pure VHR 28-34/7-2 (K-NL)
- Status: The maker's manual names no OpenTherm connection
- How OpenTherm is reached: Not available (only the maker's own bus)
- Terminals: The connection chapter names a 24 V thermostat connection (RT 24 V), an eBUS connection ("eBUS (+/-)") and a connection for a wired outdoor sensor; the wiring lists name a 24 V DC room thermostat and a bus connection for a thermostat or room thermostat. The manual names no OpenTherm connection and no openTHERM module (page 20-21, 45-46)
- Fault codes in the profile: 37

What the manual says about OpenTherm:

- Section 5.7.5 (connecting a thermostat to the electronics): the product takes a 24 V thermostat or an eBUS thermostat or receiver; the manual says to apply no mains voltage to the eBUS (+/-) and RT 24 V terminals. It names no OpenTherm connection and no module for one (the ecoTEC exclusive manual of the same maker does name an openTHERM module). (page 20-21)

Documents:

- Vaillant, *Installatie- en onderhoudshandleiding ecoTEC pure VHR 18-24/7-2, VHR 23-28/7-2, VHR 28-34/7-2 (K-NL)*, 0020231718_04
