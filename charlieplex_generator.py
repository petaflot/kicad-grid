#!/usr/bin/env python
"""
    script to generate a Charlieplex input matrix of arbitrary size

    based on
        - "Kicad schematics and PCB python scripting" https://www.youtube.com/watch?v=EP1GtsZ2VfM
        - ZMK PR #1694 "Add charliplex keyscan" https://github.com/zmkfirmware/zmk/pull/1694

    Author: JCZD @ engrenage.ch
    Date:   Thu Dec 19 18:03:52 CET 2024

    TODO (wishlist):
    - automatically make a grid from an entire sheet
    - n-dimensional grids
    - better argument parsing
"""
# how many GPIO lines for the matrix (excluding optional interrupt line)
gridsize = 9, 9
# size of a single cell (on the schematic sheet)
griddim = 11, 7

add_caps = True
add_interrupt_line = True
add_ws2812 = True


from sys import stderr, argv
try:
    from skip import Schematic, Symbol
except ImportError:
    # we refuse to iterate further at this point, let the user do it explicitly
    print("need to `pip install kicad-skip`", file=stderr)
    exit(1)

if not add_ws2812:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <switches_file.kicad_sch>")
        exit(2)
else:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <switches_file.kicad_sch> <leds_file.kicad_sch>")
        exit(2)


# used for.. whatever, just figure it out but this is likely not changed
delete_ref_symbols = True

"""
    constants
"""
unitspace = 2.54

"""
    Helper functions
"""
def units_to_mm(u_int):
    return u*unitspace

def to_grid(gridOrigin, xunits:int, yunits:int):
    return ( gridOrigin[0]+(xunits*unitspace),
            gridOrigin[1]+(yunits*unitspace) )




sch = Schematic("template-charlieplex_switches.kicad_sch")

# reference symbols for switch unit
refswitch = sch.symbol.SW_
refdiode = sch.symbol.D_
if add_caps: refcap = sch.symbol.C_

def createSymbolGrid(basedOn:Symbol, numrows:int, numcols:int, diagonal:bool=None ):
    """
        returns a numrows x numcols matrix ; all omitted elements are None

        arguments:
            diagonal:
                True:   only on the diagonal (row == col)
                False:  everything BUT the diagonal (row != col)
                None:   everything including the diagonal
    """
    table = []

    for i in range(numrows):
        columns = []
        for j in range(numcols):
            if diagonal is None or ( diagonal is True and i == j ) or ( diagonal is False and i != j ):
                newSymbol = basedOn.clone()
                newSymbol.move(*to_grid(basedOn.at, i*griddim[0], j*griddim[1]))
                newSymbol.setAllReferences(f"{basedOn.Reference.value}{i}_{j}")
                columns.append(newSymbol)
            else:
                columns.append(None)
    
        table.append(columns)

    return table

switches = createSymbolGrid(refswitch, *gridsize, False)
diodes = createSymbolGrid(refdiode, *gridsize, False)
if add_caps: caps = createSymbolGrid(refcap, *gridsize, False)

# internal wiring
for i in range(gridsize[0]):
    for j in range(gridsize[1]):
        if i != j:
            w = sch.wire.new()
            w.start_at(switches[i][j].pin.B)
            w.end_at(diodes[i][j].pin.A)

            l = sch.label.new()
            l.value = f"ROW_{j}"
            l.move(switches[i][j].pin.A.location.value, 180)    # NOTE: as of now, rotation doesn't seem to work (upstream)

            l = sch.label.new()
            l.value = f"COL_{i}"
            l.move(diodes[i][j].pin.K.location.value)

            if add_caps:
                w = sch.wire.new()
                w.start_at(switches[i][j].pin.A)
                w.end_at(caps[i][j].pin[0])
                w = sch.wire.new()
                w.start_at(caps[i][j].pin[1])
                w.end_at(diodes[i][j].pin.A)
                junc = sch.junction.new()
                junc.move(*w.end.value)


if add_interrupt_line:
    refzd = sch.symbol.DZD_
    # we're only working on the diagonal we excluded earlier
    zenners = createSymbolGrid(refzd, *gridsize, True)
    for i in range(gridsize[0]):
        for j in range(gridsize[1]):
            if i == j:
                l = sch.label.new()
                l.value = f"ROW_{i}"
                l.move(zenners[i][j].pin[1].location.value, 180)   # NOTE: as of now, rotation doesn't seem to work (upstream)
                l = sch.label.new()
                l.value = f"COL_{i}"
                l.move(zenners[i][j].pin[0].location.value)
                l = sch.global_label.new()
                l.value = "LINTR"
                l.move(zenners[i][j].pin[2].location.value, 180)


# deleting source symbols
if delete_ref_symbols:
    refswitch.delete()
    refdiode.delete()
    refcap.delete()
    refzd.delete()


sch.write(argv[1])






if add_ws2812:
    griddim = 11, 9
    sch = Schematic("template-charlieplex_leds.kicad_sch")
    for sym in (sch.symbol.PWR01, sch.symbol.PWR02, sch.symbol.WS_):
        res = createSymbolGrid(sym, *gridsize, False)
        sym.delete()

    # wiring daisy-chain
    del(l)
    for i in range(gridsize[0]):
        for j in range(gridsize[1]):
            if i != j:
                try:
                    l.clone()
                except NameError:
                    l = sch.label.new()
                    l.value = "WS2812_in"
                finally:
                    l.move(res[i][j].pin[0].location.value)
                l = sch.label.new()
                l.value = f"WS2812_{i*gridsize[0]+j}"
                l.move(res[i][j].pin[1].location.value)

    sch.write(argv[2])
