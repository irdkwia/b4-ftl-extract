import argparse
import os

parser = argparse.ArgumentParser(description="Keitai B4B4 Extractor")
parser.add_argument("input")
parser.add_argument("output")
parser.add_argument(
    "-s",
    "--mix-spare",
    help="Mix spare using filepath '[input (without extension)].oob'.",
    action=argparse.BooleanOptionalAction,
)

args = parser.parse_args()

DATA_SIZE = 0x800
SPARE_SIZE = 0x40


def mix_spare(data, spare):
    assert (len(data) // DATA_SIZE) == (
        len(spare) // SPARE_SIZE
    ), "Data and spare size do not match."

    new_data = bytearray()
    for i in range(len(data) // DATA_SIZE):
        new_data += data[i * DATA_SIZE : (i + 1) * DATA_SIZE]
        new_data += spare[i * SPARE_SIZE : (i + 1) * SPARE_SIZE]
    return bytes(new_data)


with open(args.input, "rb") as file:
    data = file.read()

if args.mix_spare:
    oob = os.path.join(
        os.path.dirname(args.input),
        f"{os.path.splitext(os.path.basename(args.input))[0]}.oob",
    )
    with open(oob, "rb") as file:
        spare = file.read()
    data = mix_spare(data, spare)

os.makedirs(args.output, exist_ok=True)

systems = []
current = bytearray(0)
for i in range(0, len(data), 0x21000):
    if data[i : i + 2] == b"\xB4\xB4":
        # B4 B4: Data Metablock
        current += data[i + 0x840 : i + 0x207C0]
    elif data[i : i + 2] == b"\xA5\xA5":
        # A5 A5: Partition Change Metablock
        systems.append(current)
        current = bytearray(0)

# Keep last partition if not empty
if len(current) > 0:
    systems.append(current)

for j, shuffle in enumerate(systems):
    bseqid = {}
    blocks = {}
    keep_blocks = 0
    bid = 0
    seqid = 0

    for i in range(0, len(shuffle), 0x840):
        if keep_blocks > 0:
            bid += 1
        else:
            bid = int.from_bytes(shuffle[i + 0x804 : i + 0x808], "little")
            seqid = int.from_bytes(shuffle[i + 0x814 : i + 0x818], "little")
            nbytes = int.from_bytes(shuffle[i + 0x810 : i + 0x814], "little")
            if (
                bid == 0xFFFFFFFF
                or seqid == 0xFFFFFFFF
                or int.from_bytes(shuffle[i + 0x802 : i + 0x804], "little") != 0
            ):
                continue
            keep_blocks = nbytes // 0x800
        keep_blocks -= 1
        mseqid = bseqid.get(bid, -1)
        if mseqid < seqid:
            bseqid[bid] = seqid
            blocks[bid] = shuffle[i : i + 0x800]

    reformat = bytearray((max(blocks) + 1) * 0x800)

    for bid, x in blocks.items():
        reformat[bid * 0x800 : (bid + 1) * 0x800] = x

    with open(os.path.join(args.output, "partition_%04d.bin" % j), "wb") as file:
        file.write(reformat)
